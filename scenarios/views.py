from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone
from functools import wraps

from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance

from .models import BillOfLading, CommercialDocument, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument, ScenarioVersion
from .pdfs import build_bill_of_lading_pdf, build_commercial_document_pdf, build_fictitious_document_pdf
from .services import available_actions, perform_action, practical_is_unlocked, record_hint, start_or_resume_attempt
from accounts.models import SimulatorCredential


def _is_simulator_author(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists())


def _has_simulator_access(request):
    if _is_simulator_author(request.user):
        return True
    if not request.user.is_authenticated or request.session.get("simulator_user_id") != str(request.user.pk):
        return False
    credential = SimulatorCredential.objects.filter(user=request.user).first()
    return bool(credential and credential.is_current)


def simulator_access_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not _has_simulator_access(request):
            messages.warning(request, "Enter your current simulator credentials to continue.")
            return redirect("simulator-portal")
        return view(request, *args, **kwargs)
    return wrapped


def simulator_portal(request):
    student_id_hint = request.user.student_id if request.user.is_authenticated else ""
    return render(request, "scenarios/portal.html", {"simulator_access": _has_simulator_access(request), "student_id_hint": student_id_hint})


@require_POST
def simulator_login(request):
    student_id = request.POST.get("student_id", "").strip().upper()
    password = request.POST.get("password", "")
    credential = SimulatorCredential.objects.select_related("user").filter(user__student_id=student_id).first()
    if not credential or not credential.matches(password):
        messages.error(request, "The Student ID or simulator password is invalid or expired.")
        return redirect("simulator-portal")
    user = credential.user
    if not user.is_active:
        messages.error(request, "This student account is inactive.")
        return redirect("simulator-portal")
    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["simulator_user_id"] = str(user.pk)
    messages.success(request, "Simulator access granted.")
    return redirect("simulator-portal")


@require_POST
def simulator_logout(request):
    if _is_simulator_author(request.user):
        messages.warning(
            request,
            "Staff and administrators have permanent simulator access, so simulator sign-out is unavailable. Use the main account sign-out to end your session.",
        )
        return redirect("simulator-portal")
    request.session.pop("simulator_user_id", None)
    messages.info(request, "You have signed out of the simulator workspace.")
    return redirect("simulator-portal")


@require_POST
def simulator_reset_request(request):
    student_id = request.POST.get("student_id", "").strip().upper()
    credential = SimulatorCredential.objects.filter(user__student_id=student_id).first()
    if credential:
        credential.reset_requested_at = timezone.now()
        credential.save(update_fields=("reset_requested_at",))
    messages.success(request, "If the Student ID is registered, the instructor dashboard now shows your reset request.")
    return redirect("simulator-portal")


@simulator_access_required
def cargo_direct_delivery(request):
    """Frontend-only Sea Import > Discharge > Direct Delivery screen."""
    return render(request, "scenarios/cargo_direct_delivery.html")


@simulator_access_required
def cargo_service_request(request):
    """Frontend-only Cargo > Sea Import > Service Request flow."""
    return render(request, "scenarios/cargo_service_request.html")


CARGO_REFERENCE_PAGES = {
    "vessel-arrival": ("Vessel Arrival", "Sea Import · Tracking", ["Vessel Name", "Voyage No.", "Port of Arrival", "Arrival Date"], ["Vessel", "Voyage", "Port", "ETA", "Status"]),
    "vessel-schedule": ("Vessel Schedule", "Sea Import · Tracking", ["Vessel Name", "Voyage No.", "Port of Loading", "Port of Discharge"], ["Vessel", "Voyage", "Loading Port", "Discharge Port", "Schedule"]),
    "manifest-status": ("Sea Manifest Status", "Sea Import · Tracking", ["Manifest No.", "Vessel Name", "Voyage No.", "Status"], ["Manifest No.", "Vessel", "Voyage", "Submitted", "Status"]),
    "boe-status": ("BOE Status", "Sea Import · Tracking", ["BOE No.", "IMP. CODE/EXP. CODE"], ["BOE No.", "Importer/Exporter Code", "Declaration No.", "Status"]),
    "sea-export": ("Sea Export", "Cargo · Sea Export", ["Manifest No.", "Exporter Code or Name", "BL Number", "Status"], ["Manifest No.", "Exporter", "BL Number", "Status"]),
    "air-import": ("Air Import", "Cargo · Air Import", ["AWB No.", "Flight No.", "Importer Code or Name", "Status"], ["AWB No.", "Flight", "Importer", "Status"]),
    "road-manifest": ("Road Manifest", "Cargo · Road Manifest", ["Manifest No.", "Truck No.", "Transporter", "Status"], ["Manifest No.", "Truck No.", "Transporter", "Status"]),
    "transportation": ("Transportation", "Cargo · Transportation", ["Request No.", "Transporter", "Vehicle No.", "Status"], ["Request No.", "Transporter", "Vehicle", "Status"]),
    "customs-area": ("Customs Area", "Cargo · Customs Area", ["Reference No.", "Importer Code or Name", "Location", "Status"], ["Reference No.", "Importer", "Location", "Status"]),
}

for _key, _title, _section in (
    ("export-sea-manifest-boe-matching", "Export Sea Manifest BOE Matching", "Sea Export · Manifest"),
    ("air-service-request", "Service Request", "Air Import · Service Request"),
    ("road-consignment-list", "Road Consignment List", "Road Manifest · Manifest"),
    ("road-consignment-amend-list", "Road Consignment Amend List", "Road Manifest · Manifest"),
    ("vehicle-list", "Vehicle List", "Road Manifest · Manifest"),
    ("vehicle-amend", "Vehicle Amend", "Road Manifest · Manifest"),
    ("bt-declaration", "BT Declaration", "Transportation · Bonded Transportation"),
    ("bt-amendment-declaration", "BT Amendment Declaration", "Transportation · Bonded Transportation"),
    ("holding-area-transfer", "Holding Area Transfer", "Transportation"),
    ("non-exited-bt-report", "List of non-exited BT", "Transportation · Non Exited BT"),
    ("sigmat-route-amend", "SIGMAT Route Amend", "Transportation"),
    ("weighbridge-list", "WeighBridge List", "Transportation · WeighBridge Report"),
    ("dummy-bl-list", "Dummy BL List", "Customs Area · Dummy BL"),
    ("dummy-bl-restoration-list", "Dummy BL Restoration List", "Customs Area · Dummy BL"),
    ("merge-bl-restoration-list", "Merge BL Restoration List", "Customs Area · Merge BL"),
    ("merge-bl-list", "Merge BL List", "Customs Area · Merge BL"),
    ("ucl-release", "UCL Release", "Customs Area · UCL"),
    ("temporary-importation", "Temporary Importation", "Customs Area · Temporary Importation"),
    ("temporary-importation-closure", "Temporary Importation Closure", "Customs Area · Temporary Importation"),
    ("release-of-blocking", "Release of Blocking", "Customs Area"),
):
    CARGO_REFERENCE_PAGES[_key] = (_title, f"Cargo · {_section}", ["Reference No.", "Status", "Register Date"], ["No.", "Reference No.", "Status", "Register Date"])


@simulator_access_required
def cargo_reference_page(request, page_key):
    page = CARGO_REFERENCE_PAGES.get(page_key)
    if page is None:
        raise PermissionDenied("Unknown Cargo reference page.")
    title, section, fields, columns = page
    return render(request, "scenarios/cargo_reference_page.html", {"title": title, "section": section, "fields": fields, "columns": columns})


@simulator_access_required
def clearance_workspace(request):
    """Frontend-only Clearance navigation and Create BOE Declaration preview."""
    declaration_items = [
        "Create BOE Declaration",
        "Search BOE Declaration", "Create Simple Amendment", "Search Simple Amendment",
        "Create Post Entry Declaration", "Search Post Entry Declaration", "Search Cancellation Request",
        "Create Release Prior to BOE", "Search Release Prior to BOE", "Export Booking Schedule Update",
        "Reply to Appeal Correction Query", "Request for BOE Suspension", "Request Physical Inspection by CHA",
        "Request for NBD Allow (Direct Import)", "Request BOE Release in Lab Analysis incomplete",
        "Request for release of BOE Blocking", "Request to change BL No before Manifest Matching",
        "Request to enable BL No Swap", "Request BOE Release without MDA Approval",
        "Request to allow for Importer Name matching", "BOE Annexed Document Registration",
        "Request UCL Check Skip before Manifest Matching",
    ]
    return render(request, "scenarios/clearance_workspace.html", {"declaration_items": declaration_items})


@simulator_access_required
def clearance_reference_page(request, page_key):
    title = page_key.replace("-", " ").title()
    return render(request, "scenarios/clearance_reference_page.html", {"title": title})


@simulator_access_required
def declaration_search(request, search_kind):
    titles = {
        "boe": "Search BOE Declaration",
        "simple-amendment": "Search Simple Amendment",
        "post-entry": "Search Post Entry Declaration",
    }
    return render(request, "scenarios/declaration_search.html", {"page_title": titles[search_kind]})


@simulator_access_required
def declaration_create(request, create_kind):
    titles = {
        "simple-amendment": "Simple Amendment Request",
        "post-entry": "Post Entry Declaration Request",
    }
    return render(request, "scenarios/declaration_create.html", {"page_title": titles[create_kind], "create_kind": create_kind})


@simulator_access_required
def single_window_workspace(request):
    """Send live playground users to the first actionable Single Window step."""
    return redirect("single-window-create-ucr")


@simulator_access_required
def single_window_overview(request):
    """Full navigation map used by pre-programmed lessons."""
    return render(request, "scenarios/single_window_workspace.html")


@simulator_access_required
def single_window_create_ucr(request):
    return render(request, "scenarios/single_window_create_ucr.html")


@simulator_access_required
def single_window_search_ucr(request):
    return render(request, "scenarios/single_window_search_ucr.html")


@simulator_access_required
def single_window_exporter_registration(request, mode):
    return render(request, "scenarios/single_window_exporter_registration.html", {
        "mode": mode,
        "page_title": "Create Exporter Registration" if mode == "create" else "Search Exporter Registration",
    })


@simulator_access_required
def single_window_create_opt_in_out(request):
    return render(request, "scenarios/single_window_create_opt_in_out.html")


@simulator_access_required
def single_window_search_opt_in_out(request):
    return render(request, "scenarios/single_window_search_opt_in_out.html")


@simulator_access_required
def single_window_opt_in_out_detail(request):
    return render(request, "scenarios/single_window_opt_in_out_detail.html")


@simulator_access_required
def single_window_preparation_application(request, mode):
    return render(request, "scenarios/single_window_preparation_application.html", {
        "mode": mode,
        "page_title": "Create Application" if mode == "create" else "Search Application",
    })


@simulator_access_required
def single_window_create_master_application(request):
    return render(request, "scenarios/single_window_create_master_application.html")


SINGLE_WINDOW_REFERENCE_PAGES = {
    "transfer-ucr": {
        "title": "Transfer UCR", "section": "Registration · Unique Consignment Reference",
        "panel": "Search Transfer UCR",
        "fields": ["UCR No.", "Status", "Importer TIN/Name", "Exporter TIN/Name", "Agent Code", "Agent Company Name", "Submitted Date", "Approval Date"],
        "columns": ["No.", "UCR No.", "Importer", "Exporter", "Mandator Company", "Agent Company", "Date Submitted", "Date Approved", "Status"],
        "status_options": ["DR, Draft", "SU, Submit", "RJ, Reject", "RS, Re-submit", "AP, Approved"],
        "show_new": True,
    },
    "received-ucr": {
        "title": "Received UCR", "section": "Registration · Unique Consignment Reference",
        "panel": "Search Received UCR",
        "fields": ["UCR No.", "Importer TIN/Name", "Exporter TIN/Name", "Mandator Code", "Mandator Company Name", "Submitted Date", "Approval Date"],
        "columns": ["No.", "UCR No.", "Importer", "Exporter", "Mandator Code", "Mandator Company Name", "Date Submitted", "Date Approved", "Status"],
    },
    "fcie-create": {"title": "Create FCIE Registration", "section": "Registration · FCIE Registration", "panel": "New Registration", "fields": ["Application Ref. No.", "Importer Code", "Importer Name", "Registration Type", "Remarks"]},
    "fcie-search": {"title": "Search FCIE Registration", "section": "Registration · FCIE Registration", "panel": "Registration Search", "fields": ["Application No.", "Importer Code or Name", "Status", "Register Date"], "columns": ["No.", "Application No.", "Importer", "Status", "Register Date"]},
    "master-search": {"title": "Search Master Application", "section": "Application · Master Application", "panel": "Application List", "fields": ["Application No.", "eMDA", "Applicant Code or Name", "Status", "Register Date"], "columns": ["No.", "Application No.", "eMDA", "Applicant", "Process", "Status", "Register Date"]},
    "consignment-create": {"title": "Create Consignment Application", "section": "Application · Consignment Application", "panel": "New Consignment Request", "fields": ["UCR No.", "Master Application No.", "eMDA", "Application", "Process"]},
    "consignment-search": {"title": "Search Consignment Application", "section": "Application · Consignment Application", "panel": "Application List", "fields": ["UCR No.", "Application No.", "Exporter Code or Name", "Importer Code or Name", "Register Date"], "columns": ["No.", "Application No.", "UCR No.", "Exporter", "Importer", "Register Date"]},
    "bank-create": {"title": "Create Bank Pre-Registration", "section": "Letter of Commitment · Bank Pre-Registration", "panel": "New Bank Pre-Registration", "fields": ["Bank", "Branch", "Applicant TIN", "Applicant Name", "Reference No."]},
    "bank-search": {"title": "Search Bank Pre-Registration", "section": "Letter of Commitment · Bank Pre-Registration", "panel": "Bank Pre-Registration Search", "fields": ["Registration No.", "Bank", "Applicant Code or Name", "Register Date"], "columns": ["No.", "Registration No.", "Bank", "Applicant", "Status", "Register Date"]},
    "letter-create": {"title": "Create Letter of Commitment", "section": "Letter of Commitment", "panel": "New Letter of Commitment", "fields": ["Bank Registration No.", "Importer Code", "UCR No.", "Currency", "Amount", "Remarks"]},
    "letter-search": {"title": "Search Letter of Commitment", "section": "Letter of Commitment", "panel": "Letter of Commitment Search", "fields": ["Commitment No.", "Importer Code or Name", "Bank", "Status", "Register Date"], "columns": ["No.", "Commitment No.", "Importer", "Bank", "Amount", "Status", "Register Date"]},
    "application": {"title": "Previous Application Data", "section": "Previous Data", "panel": "Search Application", "fields": ["Application No.", "Applicant Code or Name", "eMDA", "Register Date"], "columns": ["No.", "Application No.", "eMDA", "Applicant", "Status", "Register Date"]},
    "exporter": {"title": "Previous Exporter Registration Data", "section": "Previous Data", "panel": "Search Exporter Registration", "fields": ["Application Ref. No.", "Exporter Code or Name", "Certificate", "Register Date"], "columns": ["No.", "Application No.", "Exporter", "Certificate", "Status", "Register Date"]},
    "letter": {"title": "Previous Letter of Commitment Data", "section": "Previous Data", "panel": "Search Letter of Commitment", "fields": ["Commitment No.", "Importer Code or Name", "Bank", "Register Date"], "columns": ["No.", "Commitment No.", "Importer", "Bank", "Status", "Register Date"]},
    "bank": {"title": "Previous Bank Registration Data", "section": "Previous Data", "panel": "Search Pre Bank Registration", "fields": ["Registration No.", "Bank", "Applicant Code or Name", "Register Date"], "columns": ["No.", "Registration No.", "Bank", "Applicant", "Status", "Register Date"]},
    "opt-in": {"title": "Previous Opt In Data", "section": "Previous Data", "panel": "Search Opt In", "fields": ["Opt No.", "MDA", "Importer Code or Name", "Register Date"], "columns": ["No.", "Opt No.", "MDA", "Importer", "Status", "Register Date"]},
}


@simulator_access_required
def single_window_reference_page(request, page_key):
    page = SINGLE_WINDOW_REFERENCE_PAGES.get(page_key)
    if page is None:
        raise PermissionDenied("Unknown Single Window reference page.")
    return render(request, "scenarios/single_window_reference_page.html", {"page": page, "page_key": page_key})


def _enrolment_with_access(request):
    if needs_disclaimer_acceptance(request.user):
        return None, redirect("disclaimer")
    enrolment = active_enrolment_for(request.user)
    if not practical_is_unlocked(enrolment):
        raise PermissionDenied("Complete simulator orientation before beginning practical training.")
    return enrolment, None


@login_required
@simulator_access_required
def scenario_list(request):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    versions = ScenarioVersion.objects.filter(status=ScenarioVersion.Status.PUBLISHED).filter(
        Q(module__programme_version=enrolment.programme_version) | Q(module__isnull=True)
    ).select_related("scenario", "module")
    attempts = {attempt.scenario_version_id: attempt for attempt in ScenarioAttempt.objects.filter(enrolment=enrolment, status=ScenarioAttempt.Status.IN_PROGRESS)}
    return render(request, "scenarios/list.html", {"scenario_versions": versions, "attempts": attempts})


@login_required
@simulator_access_required
def scenario_detail(request, version_id):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    version = get_object_or_404(ScenarioVersion.objects.select_related("scenario"), pk=version_id, status=ScenarioVersion.Status.PUBLISHED)
    active_attempt = ScenarioAttempt.objects.filter(enrolment=enrolment, scenario_version=version, status=ScenarioAttempt.Status.IN_PROGRESS).first()
    return render(request, "scenarios/detail.html", {"scenario_version": version, "active_attempt": active_attempt})


@login_required
@simulator_access_required
@require_POST
def scenario_start(request, version_id):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    version = get_object_or_404(ScenarioVersion, pk=version_id, status=ScenarioVersion.Status.PUBLISHED)
    attempt, created = start_or_resume_attempt(enrolment, version)
    messages.success(request, "Scenario started." if created else "Your saved scenario has been resumed.")
    return redirect("scenario-workspace", attempt_id=attempt.pk)


@login_required
@simulator_access_required
def scenario_workspace(request, attempt_id):
    attempt = get_object_or_404(
        ScenarioAttempt.objects.select_related("enrolment", "scenario_version__scenario", "current_state").prefetch_related("scenario_version__documents", "scenario_version__bills_of_lading__cargo_items", "scenario_version__commercial_documents__line_items", "actions"),
        pk=attempt_id,
        enrolment__student=request.user,
    )
    return render(request, "scenarios/workspace.html", {"attempt": attempt, "available_actions": available_actions(attempt)})


@login_required
@simulator_access_required
@require_POST
def scenario_action(request, attempt_id, action_id):
    attempt = get_object_or_404(ScenarioAttempt, pk=attempt_id, enrolment__student=request.user)
    action = get_object_or_404(ScenarioActionDefinition, pk=action_id)
    try:
        updated = perform_action(attempt, action)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scenario-workspace", attempt_id=attempt.pk)
    if action.success_feedback:
        messages.success(request, action.success_feedback)
    if updated.status == ScenarioAttempt.Status.COMPLETED and hasattr(updated, "evaluation"):
        return redirect("practical-evaluation", evaluation_id=updated.evaluation.pk)
    return redirect("scenario-workspace", attempt_id=updated.pk)


@login_required
@simulator_access_required
@require_POST
def scenario_hint(request, attempt_id):
    attempt = get_object_or_404(ScenarioAttempt.objects.select_related("current_state", "scenario_version"), pk=attempt_id, enrolment__student=request.user)
    hint = record_hint(attempt)
    messages.info(request, hint)
    return redirect("scenario-workspace", attempt_id=attempt.pk)


@login_required
@simulator_access_required
def scenario_document_pdf(request, document_id):
    document = get_object_or_404(ScenarioDocument.objects.select_related("scenario_version__scenario"), pk=document_id)
    is_author = request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    is_learner = document.scenario_version.attempts.filter(enrolment__student=request.user).exists()
    if not (is_author or is_learner):
        raise PermissionDenied("This training document is not available to your account.")
    response = HttpResponse(build_fictitious_document_pdf(document), content_type="application/pdf")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    filename = f"training-{document.pdf_layout}-{document.reference or document.pk}.pdf".replace(" ", "-")
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


@login_required
@simulator_access_required
def bill_of_lading_pdf(request, bill_id):
    bill = get_object_or_404(BillOfLading.objects.select_related("scenario_version__scenario").prefetch_related("cargo_items"), pk=bill_id)
    is_author = request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    is_learner = bill.status == BillOfLading.Status.PUBLISHED and bill.scenario_version.attempts.filter(enrolment__student=request.user).exists()
    if not (is_author or is_learner):
        raise PermissionDenied("This training Bill of Lading is not available to your account.")
    response = HttpResponse(build_bill_of_lading_pdf(bill), content_type="application/pdf")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="training-bl-{bill.reference}.pdf"'
    return response


@login_required
@simulator_access_required
def commercial_document_pdf(request, document_id):
    document = get_object_or_404(CommercialDocument.objects.select_related("scenario_version__scenario").prefetch_related("line_items"), pk=document_id)
    is_author = request.user.is_staff or request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    is_learner = document.status == CommercialDocument.Status.PUBLISHED and document.scenario_version.attempts.filter(enrolment__student=request.user).exists()
    if not (is_author or is_learner):
        raise PermissionDenied("This training commercial document is not available to your account.")
    response = HttpResponse(build_commercial_document_pdf(document), content_type="application/pdf")
    disposition = "attachment" if request.GET.get("download") == "1" else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="training-{document.document_type}-{document.reference}.pdf"'
    return response
