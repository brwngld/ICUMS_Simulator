from django.contrib import messages
from django.contrib.auth import get_user_model, login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.http import HttpResponse, JsonResponse, FileResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Max
from django.db.models import Case, IntegerField, Value, When
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from functools import wraps
from datetime import date, timedelta
import json

from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance

from .country_codes import COUNTRY_CODES, COUNTRY_CODE_SET

COUNTRY_DISPLAY_NAMES = dict(COUNTRY_CODES)
from .models import (BillOfLading, CommercialDocument, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument,
                     ScenarioVersion, TrainingStakeholder, TrainingServiceProvider, UcrDeclaration, UcrDocumentAttachment,
                     allocate_ucr_number, purge_expired_ucr_drafts)
from .models import BoeDeclaration, BoeStageEvent, ConsignmentApplication, CustomsProcedureCode, CustomsRegime, GhanaHSCode, MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, MdaStatus, PortCode, allocate_application_number, allocate_boe_number, allocate_job_number
from .pdfs import build_bill_of_lading_pdf, build_commercial_document_pdf, build_fictitious_document_pdf
from assessment.service import compute_from_invoice
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


def _review_target(request):
    """Staff review mode: the student whose simulator work the signed-in staff member is viewing.

    Review sessions are strictly view-only; every write endpoint refuses them.
    """
    if not request.user.is_authenticated or not _is_simulator_author(request.user):
        return None
    target_id = request.session.get("simulator_review_user_id")
    if not target_id:
        return None
    return get_user_model().objects.filter(pk=target_id).first()


def _effective_owner(request):
    return _review_target(request) or request.user


def _review_json_guard(request):
    if _review_target(request) is None:
        return None
    return JsonResponse({"error": "Review access is view-only. Exit student review to make changes."}, status=403)


def _review_form_guard(request):
    if _review_target(request) is None:
        return None
    messages.error(request, "Review access is view-only. Exit student review to make changes.")
    return redirect("simulator-portal")


def simulator_access_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not _has_simulator_access(request):
            messages.warning(request, "Enter your current simulator credentials to continue.")
            return redirect(f"{reverse('simulator-portal')}?login=1")
        return view(request, *args, **kwargs)
    return wrapped


def simulator_portal(request):
    student_id_hint = request.user.student_id if request.user.is_authenticated else ""
    return render(request, "scenarios/portal.html", {"simulator_access": _has_simulator_access(request), "student_id_hint": student_id_hint})


@require_POST
def simulator_review_login(request):
    """Staff-only: browse one student's simulator work with view-only access."""
    if not _is_simulator_author(request.user):
        raise PermissionDenied("Student review is a staff feature.")
    query = request.POST.get("student", "").strip()
    if not query:
        messages.error(request, "Enter the student's ID or name to review their work.")
        return redirect("simulator-portal")
    query_lower = query.lower()
    matches = []
    for credential in SimulatorCredential.objects.select_related("user"):
        user = credential.user
        haystacks = [user.student_id or "", user.username, user.first_name, user.last_name, user.get_full_name()]
        if any(field.strip().lower() == query_lower for field in haystacks):
            matches.append(user)
    if not matches:
        messages.error(request, f"No simulator student matches “{query}”.")
    elif len(matches) > 1:
        messages.error(request, f"Several students match “{query}” — use the Student ID instead.")
    else:
        student = matches[0]
        request.session["simulator_review_user_id"] = str(student.pk)
        messages.success(request, f"Reviewing the work of {student.get_full_name() or student.username} ({student.student_id or 'no ID'}) — view only.")
    return redirect("simulator-portal")


@require_POST
def simulator_review_exit(request):
    if not _is_simulator_author(request.user):
        raise PermissionDenied("Student review is a staff feature.")
    request.session.pop("simulator_review_user_id", None)
    messages.info(request, "Student review ended; you are back to your own workspace.")
    return redirect("simulator-portal")


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
    """Sign out is decided by the session type, not by the account's privileges.

    Review mode ends back at the staff member's own workspace; a simulator
    credential session (a student login) always signs out; bare staff sessions
    have permanent simulator access and therefore nothing to sign out of.
    """
    if _review_target(request) is not None:
        request.session.pop("simulator_review_user_id", None)
        messages.info(request, "Student review ended; you are back to your own workspace.")
        return redirect("simulator-portal")
    if request.session.get("simulator_user_id"):
        request.session.pop("simulator_user_id", None)
        messages.info(request, "You have signed out of the simulator workspace.")
        return redirect("simulator-portal")
    if _is_simulator_author(request.user):
        messages.warning(
            request,
            "Staff and administrators have permanent simulator access, so simulator sign-out is unavailable. Use the main account sign-out to end your session.",
        )
        return redirect("simulator-portal")
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
    """Clearance entry point: the Create BOE Declaration selector."""
    regimes = list(CustomsRegime.objects.filter(is_active=True).values_list("code", "name"))
    return render(request, "scenarios/clearance_workspace.html", {"boe_regimes": regimes})


@simulator_access_required
@require_GET
def clearance_cpc_search(request):
    """Return active CPCs belonging to the selected customs regime."""
    regime = request.GET.get("regime", "").strip().upper()[:2]
    query = request.GET.get("q", "").strip()[:240]
    code = request.GET.get("code", "").strip().upper()[:12]
    description = request.GET.get("description", "").strip()[:240]
    records = CustomsProcedureCode.objects.filter(is_active=True, regime__is_active=True, regime__code=regime)
    if query:
        records = records.filter(Q(code__icontains=query) | Q(description__icontains=query))
    if code:
        records = records.filter(code__icontains=code)
    if description:
        records = records.filter(description__icontains=description)
    page = Paginator(records, 100).get_page(request.GET.get("page", 1))
    return JsonResponse({
        "results": [{"code": record.code, "description": record.description} for record in page.object_list],
        "total": page.paginator.count,
        "page": page.number,
        "page_count": page.paginator.num_pages,
    })


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
    context = {"page_title": titles[search_kind]}
    if search_kind == "boe":
        keys = ("job", "boe", "bl_awb", "ucr", "regime", "importer", "exporter", "user_reference", "status", "date_from", "date_to")
        filters = {key: request.GET.get(key, "").strip() for key in keys}
        records = (BoeDeclaration.objects
                   .filter(owner=_effective_owner(request))
                   .select_related("ucr")
                   .order_by("-created_at"))
        if filters["job"]:
            records = records.filter(job_no__icontains=filters["job"])
        if filters["boe"]:
            records = records.filter(declaration_no__icontains=filters["boe"])
        if filters["bl_awb"]:
            records = records.filter(form_data__bl_awb_no__icontains=filters["bl_awb"])
        if filters["ucr"]:
            records = records.filter(ucr__ucr_no__icontains=filters["ucr"])
        if filters["regime"]:
            records = records.filter(regime__iexact=filters["regime"])
        if filters["importer"]:
            records = records.filter(form_data__importer__code__icontains=filters["importer"])
        if filters["exporter"]:
            records = records.filter(form_data__exporter__name__icontains=filters["exporter"])
        if filters["user_reference"]:
            records = records.filter(ucr__user_reference__icontains=filters["user_reference"])
        if filters["status"]:
            records = records.filter(status__iexact=filters["status"])
        if filters["date_from"]:
            records = records.filter(submitted_at__date__gte=filters["date_from"])
        if filters["date_to"]:
            records = records.filter(submitted_at__date__lte=filters["date_to"])
        context.update({
            "records": records,
            "filters": filters,
            "boe_search": True,
            "status_options": [
                (BoeDeclaration.Status.DRAFT, "ER - Draft"),
                (BoeDeclaration.Status.SUBMITTED, "SU - Submitted"),
                (BoeDeclaration.Status.ASSESSED, "AS - Assessed"),
                (BoeDeclaration.Status.ACCEPTED, "AC - Accepted"),
            ],
        })
    return render(request, "scenarios/declaration_search.html", context)


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
    draft = None
    draft_id = request.GET.get("draft")
    if draft_id and draft_id.isdigit():
        candidate = UcrDeclaration.objects.filter(pk=draft_id, owner=_effective_owner(request), status=UcrDeclaration.Status.DRAFT).first()
        if candidate:
            draft = candidate
        else:
            submitted = UcrDeclaration.objects.filter(pk=draft_id, owner=_effective_owner(request)).first()
            if submitted:
                return redirect("ucr-detail", record_id=submitted.pk)
    return render(request, "scenarios/ucr_create.html", {"initial_ucr": _ucr_record_payload(draft) if draft else None})


@simulator_access_required
def training_service_providers(request):
    if not request.user.is_staff:
        raise PermissionDenied("Provider registration is an advanced administration feature.")
    return redirect("admin:scenarios_trainingserviceprovider_add")


@simulator_access_required
@require_GET
def ucr_service_provider_lookup(request):
    code = request.GET.get("code", "").strip().upper()
    matches = TrainingServiceProvider.objects.filter(is_active=True).filter(Q(owner__isnull=True) | Q(owner=request.user))
    if code:
        matches = matches.filter(declarant_code__iexact=code)
    provider = matches.annotate(assigned_first=Case(When(owner=request.user, then=Value(0)), default=Value(1), output_field=IntegerField())).order_by("assigned_first", "declarant_code").first()
    if not provider:
        return JsonResponse({"error": "No service provider is assigned to this simulator account."}, status=404)
    return JsonResponse({"declarant_code": provider.declarant_code, "tin_code": provider.code, "name": provider.name, "country_code": provider.country_code,
                         "address": provider.address, "contact_name": provider.contact_name, "contact_designation": provider.contact_designation,
                         "phone": provider.phone, "email": provider.email, "email_2": provider.email_2})


@simulator_access_required
@require_GET
def ucr_stakeholder_lookup(request):
    code = request.GET.get("code", "").strip().upper()
    if len(code) < 11:
        return JsonResponse({"error": "The code entered is an invalid code.( input at least 11 characters)"}, status=400)
    stakeholder = TrainingStakeholder.objects.select_related("merged_into").filter(code=code).first()
    if stakeholder and stakeholder.merged_into_id:
        stakeholder = stakeholder.merged_into
    results = []
    if stakeholder and stakeholder.is_active:
        labels = dict(TrainingStakeholder.ROLE_CHOICES)
        entries = [(stakeholder.name, stakeholder.address, stakeholder.roles)]
        entries.extend(stakeholder.additional_names.values_list("name", "address", "roles"))
        for name, address, roles in entries:
            role_label = ", ".join(labels.get(role, role) for role in roles)
            results.append({
                "code": stakeholder.code, "name": name,
                "description": f"{name} - ({role_label})" if role_label else name,
                "address": address,
            })
    if not results:
        return JsonResponse({"error": "There is no registered NID/TIN.\nNID/TIN not registered in the Stakeholder System cannot be used.\nPlease contact the system administrator."}, status=404)
    return JsonResponse({"results": results})


UCR_REGIMES = {"EX", "IM", "TN", "TR", "FI", "FO"}
# Mirrors the Create UCR form rules: which party is identified by TIN vs plain name, per regime.
UCR_PARTY_RULES = {
    "EX": ("tin", "name"), "FO": ("tin", "name"),
    "IM": ("name", "tin"), "FI": ("name", "tin"), "TR": ("name", "tin"),
    "TN": ("name", "name"),
}
UCR_PARTY_KIND_LABEL = {"exporter": "Exporter", "importer": "Importer"}
UCR_REGIME_LABELS = {"EX": "Export", "IM": "Import", "TN": "Transhipment", "TR": "Transit", "FI": "Free Zones - Inbound", "FO": "Free Zones - Outbound"}
UCR_REGIME_FAMILIES = {"IM": ("IM", "FI"), "FI": ("IM", "FI"), "EX": ("EX", "FO"), "FO": ("EX", "FO"), "TN": ("TN",), "TR": ("TR",)}


def _ucr_text(payload, section, key):
    value = payload.get(section, {}).get(key, "")
    return str(value).strip() if value is not None else ""


def _ucr_country(payload, section, key, errors, label):
    code = _ucr_text(payload, section, key).upper()
    if code not in COUNTRY_CODE_SET:
        errors[f"{section}.{key}"] = f"{label}: enter a known two-letter country code, or use the search button to pick one."
    return code


def _parse_ucr_payload(request):
    """Validate the Create UCR form payload; returns (payload, errors) with errors keyed 'section.field'."""
    try:
        raw = request.POST.get("payload") if request.content_type and request.content_type.startswith("multipart/form-data") else request.body.decode("utf-8")
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None, {"__all__": "The request body is not valid JSON."}
    if not isinstance(payload, dict):
        return None, {"__all__": "The request body must be a JSON object."}

    errors = {}
    regime = str(payload.get("regime", "")).strip().upper()
    if regime not in UCR_REGIMES:
        errors["regime"] = "Select a regime type."

    provider = {}
    if payload.get("show_provider", True):
        provider = {
            "declarant_code": _ucr_text(payload, "provider", "declarant_code"),
            "code": _ucr_text(payload, "provider", "code"),
            "name": _ucr_text(payload, "provider", "name"),
            "country": _ucr_country(payload, "provider", "country", errors, "Service provider country"),
            "address": _ucr_text(payload, "provider", "address"),
            "contact": _ucr_text(payload, "provider", "contact"),
            "phone": _ucr_text(payload, "provider", "phone"),
            "email": _ucr_text(payload, "provider", "email"),
            "email_2": _ucr_text(payload, "provider", "email_2"),
        }
        if not provider["address"]:
            errors["provider.address"] = "Service provider address is required."
        if not provider["contact"]:
            errors["provider.contact"] = "Service provider contact name is required."
        if not provider["phone"]:
            errors["provider.phone"] = "Service provider telephone number is required."
        for key in ("email", "email_2"):
            if provider[key]:
                try:
                    validate_email(provider[key])
                except ValidationError:
                    errors[f"provider.{key}"] = "Enter a valid approved email address."
            elif key == "email":
                errors["provider.email"] = "Approved email address 1 is required."

    parties = {}
    for role in ("exporter", "importer"):
        kind = UCR_PARTY_RULES.get(regime, ("name", "name"))[0 if role == "exporter" else 1]
        label = UCR_PARTY_KIND_LABEL[role]
        party = {
            "identity": _ucr_text(payload, role, "identity"),
            "name": _ucr_text(payload, role, "name"),
            "country": _ucr_country(payload, role, "country", errors, f"{label} country"),
            "address": _ucr_text(payload, role, "address"),
            "phone": _ucr_text(payload, role, "phone"),
            "fax": _ucr_text(payload, role, "fax"),
            "contact": _ucr_text(payload, role, "contact"),
            "contact_no": _ucr_text(payload, role, "contact_no"),
            "designation": _ucr_text(payload, role, "designation"),
        }
        if kind == "tin":
            if len(party["identity"]) < 11:
                errors[f"{role}.identity"] = f"{label}: enter the TIN / NID (11 characters or more) and search it."
            if not party["name"]:
                errors[f"{role}.name"] = f"{label} name is required."
        elif not party["name"]:
            errors[f"{role}.name"] = f"{label} name is required."
        for key, text in (("address", "address"), ("phone", "telephone number"), ("contact", "contact person"), ("contact_no", "contact number"), ("designation", "contact designation")):
            if not party[key]:
                errors[f"{role}.{key}"] = f"{label} {text} is required."
        parties[role] = party

    mode = _ucr_text(payload, "consignment", "mode")
    if not mode or mode.split(",")[0].strip() not in {"10", "30", "40"}:
        errors["consignment.mode"] = "Select a transport mode."
    goods = _ucr_text(payload, "consignment", "goods")
    if not goods:
        errors["consignment.goods"] = "General goods description is required."
    origin = _ucr_country(payload, "consignment", "origin", errors, "Country of origin")
    destination = _ucr_country(payload, "consignment", "destination", errors, "Country of destination")

    documents = []
    if isinstance(payload.get("documents"), list):
        for entry in payload["documents"][:50]:
            if not isinstance(entry, dict):
                continue
            documents.append({
                "code": str(entry.get("code", "")).strip()[:24],
                "name": str(entry.get("name", "")).strip()[:180],
                "reference": str(entry.get("reference", "")).strip()[:100],
            })
    documents = [entry for entry in documents if entry["code"] or entry["reference"]]

    if errors:
        return None, errors
    raw_draft_id = payload.get("draft_id")
    return {
        "draft_id": int(raw_draft_id) if isinstance(raw_draft_id, (int, str)) and str(raw_draft_id).isdigit() else None,
        "regime": regime,
        "show_provider": bool(payload.get("show_provider", True)),
        "provider": provider,
        "exporter": parties["exporter"],
        "importer": parties["importer"],
        "goods": goods,
        "origin": origin,
        "destination": destination,
        "mode": mode,
        "user_reference": _ucr_text(payload, "consignment", "reference")[:100],
        "ucr_email": _ucr_text(payload, "consignment", "email"),
        "documents": documents,
    }, {}


def _apply_ucr_payload(record, payload):
    record.regime = payload["regime"]
    record.show_provider = payload["show_provider"]
    provider = payload["provider"]
    record.declarant_code = provider["declarant_code"]
    record.provider_code = provider["code"]
    record.provider_name = provider["name"]
    record.provider_country = provider["country"]
    record.provider_address = provider["address"]
    record.provider_contact = provider["contact"]
    record.provider_phone = provider["phone"]
    record.provider_email = provider["email"]
    record.provider_email_2 = provider["email_2"]
    for role in ("exporter", "importer"):
        party = payload[role]
        for key in ("identity", "name", "country", "address", "phone", "fax", "contact", "contact_no", "designation"):
            setattr(record, f"{role}_{key}", party[key])
    record.goods_description = payload["goods"]
    record.origin_country = payload["origin"]
    record.destination_country = payload["destination"]
    record.transport_mode = payload["mode"]
    record.user_reference = payload["user_reference"]
    record.ucr_email = payload["ucr_email"]
    record.documents = payload["documents"]


def _open_ucr_draft(user):
    return UcrDeclaration.objects.filter(owner=user, status=UcrDeclaration.Status.DRAFT).order_by("-updated_at").first()


def _validate_ucr_attachments(documents, request):
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}
    for key, uploaded in request.FILES.items():
        if not key.startswith("file_") or not key[5:].isdigit():
            continue
        index = int(key[5:])
        if index >= len(documents) or uploaded.size > 10 * 1024 * 1024 or not any(uploaded.name.lower().endswith(ext) for ext in allowed):
            raise ValidationError("Each attachment needs a document row and must be a PDF, image, or Word file under 10 MB.")


def _save_ucr_attachments(record, request):
    for key, uploaded in request.FILES.items():
        if not key.startswith("file_") or not key[5:].isdigit():
            continue
        index = int(key[5:])
        UcrDocumentAttachment.objects.create(ucr=record, row_index=index, file=uploaded, original_name=uploaded.name[:255])


def _requested_ucr_draft(request, payload):
    """Resolve the draft a save/submit applies to; a learner may hold several drafts at once."""
    draft_id = payload.get("draft_id") if payload else None
    if draft_id is None or not str(draft_id).isdigit():
        return None, None
    record = UcrDeclaration.objects.filter(pk=draft_id, owner=request.user).first()
    if record and record.status != UcrDeclaration.Status.DRAFT:
        return None, JsonResponse({"error": "This UCR has already been submitted."}, status=400)
    return record, None


@simulator_access_required
@require_POST
def ucr_save_declaration(request):
    """Save creates or updates the addressed draft and shows its TEMPUCR reference."""
    blocked = _review_json_guard(request)
    if blocked:
        return blocked
    payload, errors = _parse_ucr_payload(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    try:
        _validate_ucr_attachments(payload["documents"], request)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)
    record, error_response = _requested_ucr_draft(request, payload)
    if error_response:
        return error_response
    record = record or UcrDeclaration(owner=request.user)
    _apply_ucr_payload(record, payload)
    if not record.temp_no:
        record.temp_no = allocate_ucr_number(UcrDeclaration.TEMP_PREFIX)
    record.save()
    _save_ucr_attachments(record, request)
    return JsonResponse({"id": record.pk, "temp_no": record.temp_no, "status": record.status,
                         "attachments": _ucr_attachment_payload(record)})


@simulator_access_required
@require_POST
def ucr_submit_declaration(request):
    """Submit closes the addressed draft and issues the final KGHTESTUCR… number."""
    blocked = _review_json_guard(request)
    if blocked:
        return blocked
    payload, errors = _parse_ucr_payload(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    try:
        _validate_ucr_attachments(payload["documents"], request)
    except ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)
    record, error_response = _requested_ucr_draft(request, payload)
    if error_response:
        return error_response
    if record is None:
        return JsonResponse({"error": "Save the UCR as a draft before submitting it."}, status=400)
    _apply_ucr_payload(record, payload)
    record.ucr_no = allocate_ucr_number(UcrDeclaration.UCR_PREFIX)
    record.status = UcrDeclaration.Status.SUBMITTED
    record.submitted_at = timezone.now()
    record.save()
    _save_ucr_attachments(record, request)
    return JsonResponse({"id": record.pk, "temp_no": record.temp_no, "ucr_no": record.ucr_no, "status": record.status,
                         "detail_url": reverse("ucr-detail", args=(record.pk,)),
                         "attachments": _ucr_attachment_payload(record)})


@simulator_access_required
def _ucr_search_queryset(request):
    """Owner's UCRs filtered by the Search UCR criteria; text fields match exactly, not partially."""
    purge_expired_ucr_drafts()
    query = request.GET
    records = UcrDeclaration.objects.filter(owner=_effective_owner(request)).order_by("-created_at")
    searched = False
    if query.get("number", "").strip():
        number = query["number"].strip()
        records = records.filter(Q(temp_no__iexact=number) | Q(ucr_no__iexact=number))
        searched = True
    if query.get("regime"):
        records = records.filter(regime=query["regime"])
        searched = True
    if query.get("exporter", "").strip():
        term = query["exporter"].strip()
        records = records.filter(Q(exporter_identity__iexact=term) | Q(exporter_name__iexact=term))
        searched = True
    if query.get("importer", "").strip():
        term = query["importer"].strip()
        records = records.filter(Q(importer_identity__iexact=term) | Q(importer_name__iexact=term))
        searched = True
    if query.get("reference", "").strip():
        records = records.filter(user_reference__iexact=query["reference"].strip())
        searched = True
    if query.get("status") in (UcrDeclaration.Status.DRAFT, UcrDeclaration.Status.SUBMITTED):
        records = records.filter(status=query["status"])
        searched = True
    for key, lookup in (("date_from", "created_at__date__gte"), ("date_to", "created_at__date__lte")):
        try:
            if query.get(key):
                records = records.filter(**{lookup: date.fromisoformat(query[key])})
                searched = True
        except ValueError:
            pass
    return records, searched


def single_window_search_ucr(request):
    records, searched = _ucr_search_queryset(request)
    # Nothing is listed until the learner enters at least one search criterion.
    return render(request, "scenarios/single_window_search_ucr.html", {
        "records": records[:200] if searched else UcrDeclaration.objects.none(),
        "searched": searched,
        "filters": request.GET,
        "review_mode": _review_target(request) is not None,
    })


@simulator_access_required
@require_GET
def ucr_reference_search(request):
    """JSON picker for forms that reference an issued UCR (e.g. Preparation Application)."""
    query = request.GET.copy()
    for key in ("status", "date_from", "date_to", "reference"):
        query.pop(key, None)
    request.GET = query
    records, searched = _ucr_search_queryset(request)

    def party_display(identity, name):
        if identity and name and identity != name:
            return f"{identity}, {name}"
        return name or identity

    # Consistent with Search UCR: nothing is returned until a criterion is entered.
    results = [
        {
            "ucr_no": record.ucr_no or record.temp_no,
            "regime": UCR_REGIME_LABELS.get(record.regime, record.regime),
            "exporter": party_display(record.exporter_identity, record.exporter_name),
            "importer": party_display(record.importer_identity, record.importer_name),
        }
        for record in (records[:50] if searched else [])
        if record.ucr_no
    ]
    return JsonResponse({"results": results})


def _ucr_attachment_payload(record):
    """First saved attachment per document row so the form can show file names as links."""
    first_by_row = {}
    for attachment in record.attachments.all():
        first_by_row.setdefault(attachment.row_index, attachment)
    return [
        {"row_index": row_index, "name": attachment.original_name, "url": reverse("ucr-attachment", args=(attachment.pk,))}
        for row_index, attachment in sorted(first_by_row.items())
    ]


def _ucr_record_payload(record):
    if record is None:
        return None
    def party(role):
        return {key: getattr(record, f"{role}_{key}") for key in
                ("identity", "name", "country", "address", "phone", "fax", "contact", "contact_no", "designation")}
    return {
        "temp_no": record.temp_no, "regime": record.regime, "show_provider": record.show_provider,
        "provider": {"declarant_code": record.declarant_code, "code": record.provider_code, "name": record.provider_name,
                     "country": record.provider_country, "address": record.provider_address, "contact": record.provider_contact,
                     "phone": record.provider_phone, "email": record.provider_email, "email_2": record.provider_email_2},
        "exporter": party("exporter"), "importer": party("importer"),
        "consignment": {"goods": record.goods_description, "origin": record.origin_country,
                        "destination": record.destination_country, "mode": record.transport_mode,
                        "reference": record.user_reference, "email": record.ucr_email},
        "documents": record.documents,
        "attachments": _ucr_attachment_payload(record),
    }


COUNTRY_DISPLAY_NAMES = dict(COUNTRY_CODES)


def _country_display(code):
    code = (code or "").strip().upper()
    return f"{code}, {COUNTRY_DISPLAY_NAMES.get(code, '')}" if code else ""


def _party_value(identity, name):
    identity, name = (identity or "").strip(), (name or "").strip()
    if identity and name and identity != name:
        return f"{identity}, {name}"
    return name or identity


def _ucr_form_context(record):
    """Shared context for the create-form-shaped View and Amend pages."""
    from .country_codes import COUNTRY_CODES

    attachments_by_row = {}
    for attachment in record.attachments.all():
        attachments_by_row.setdefault(attachment.row_index, []).append(attachment)
    document_rows = [
        {"number": index + 1, "document": document, "attachments": attachments_by_row.get(index, [])}
        for index, document in enumerate(record.documents)
    ]
    values = {
        "ucr_no": record.ucr_no or record.temp_no,
        "regime": f"{record.regime}, {UCR_REGIME_LABELS.get(record.regime, record.regime)}",
        "declarant_code": record.declarant_code,
        "provider_code": _party_value(record.provider_code, record.provider_name),
        "provider_country": _country_display(record.provider_country),
        "exporter_party": _party_value(record.exporter_identity, record.exporter_name),
        "exporter_country": _country_display(record.exporter_country),
        "importer_party": _party_value(record.importer_identity, record.importer_name),
        "importer_country": _country_display(record.importer_country),
        "origin_country": _country_display(record.origin_country),
        "destination_country": _country_display(record.destination_country),
    }
    return {
        "record": record,
        "values": values,
        "country_names": dict(COUNTRY_CODES),
        "regime_labels": UCR_REGIME_LABELS,
        "regime_family_choices": [(code, UCR_REGIME_LABELS.get(code, code)) for code in UCR_REGIME_FAMILIES.get(record.regime, (record.regime,))],
        "document_rows": document_rows,
    }


@simulator_access_required
@require_GET
def ucr_detail(request, record_id):
    record = get_object_or_404(UcrDeclaration.objects.select_related("source_ucr"), pk=record_id, owner=_effective_owner(request))
    context = _ucr_form_context(record)
    context["review_mode"] = _review_target(request) is not None
    return render(request, "scenarios/ucr_detail.html", context)


@simulator_access_required
@require_GET
def ucr_attachment(request, attachment_id):
    attachment = get_object_or_404(UcrDocumentAttachment.objects.select_related("ucr"), pk=attachment_id, ucr__owner=_effective_owner(request))
    return FileResponse(attachment.file.open("rb"), filename=attachment.original_name)


def _copy_ucr_fields(draft, source):
    excluded = {"id", "owner", "temp_no", "ucr_no", "status", "created_at", "updated_at", "submitted_at", "source_ucr", "derivation"}
    for field in UcrDeclaration._meta.concrete_fields:
        if field.name not in excluded:
            setattr(draft, field.attname, getattr(source, field.attname))
    draft.documents = [dict(item) for item in source.documents]


def _copy_ucr_attachments(draft, source):
    for attachment in source.attachments.all():
        UcrDocumentAttachment.objects.create(ucr=draft, row_index=attachment.row_index, file=attachment.file.name, original_name=attachment.original_name)


@simulator_access_required
@require_POST
def ucr_clone(request, record_id):
    """Clone copies every detail of the source into a fresh TEMPUCR draft; cloning is unlimited."""
    blocked = _review_form_guard(request)
    if blocked:
        return blocked
    source = get_object_or_404(UcrDeclaration, pk=record_id, owner=request.user)
    draft = UcrDeclaration(owner=request.user)
    _copy_ucr_fields(draft, source)
    _copy_ucr_attachments(draft, source)
    draft.temp_no = allocate_ucr_number(UcrDeclaration.TEMP_PREFIX)
    draft.source_ucr = source
    draft.derivation = "clone"
    draft.save()
    messages.success(request, f"Cloned as draft {draft.temp_no}. Finish and submit it whenever you are ready.")
    return redirect(f"{reverse('single-window-create-ucr')}?draft={draft.pk}")


@simulator_access_required
def ucr_amend(request, record_id):
    """Amend keeps the UCR read-only except for the regime and eDocuments; submitting issues a new linked number."""
    blocked = _review_form_guard(request)
    if blocked:
        return blocked
    source = get_object_or_404(UcrDeclaration.objects.select_related("source_ucr"), pk=record_id, owner=request.user)
    if source.status != UcrDeclaration.Status.SUBMITTED:
        messages.error(request, "Submit the original UCR before creating an amendment.")
        return redirect("ucr-detail", record_id=record_id)

    if request.method == "GET":
        context = _ucr_form_context(source)
        context["review_mode"] = _review_target(request) is not None
        return render(request, "scenarios/ucr_amend.html", context)

    regime = request.POST.get("regime", "").strip().upper()
    family = UCR_REGIME_FAMILIES.get(source.regime, (source.regime,))
    if regime not in family:
        messages.error(request, "The regime can only move within its own family (e.g. IM with FI, or EX with FO).")
        return redirect("ucr-amend", record_id=record_id)
    new_documents = []
    try:
        posted = json.loads(request.POST.get("new_documents", "[]"))
        if isinstance(posted, list):
            new_documents = [
                {"code": str(entry.get("code", ""))[:24].strip(), "name": str(entry.get("name", ""))[:180].strip(),
                 "reference": str(entry.get("reference", ""))[:100].strip()}
                for entry in posted[:50] if isinstance(entry, dict)
            ]
    except json.JSONDecodeError:
        pass
    new_documents = [entry for entry in new_documents if entry["code"] or entry["reference"]]

    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}
    uploads = [(key, file) for key, file in request.FILES.items() if key.startswith("file_") and key[5:].isdigit()]
    for key, uploaded in uploads:
        if uploaded.size > 10 * 1024 * 1024 or not any(uploaded.name.lower().endswith(ext) for ext in allowed_extensions):
            messages.error(request, "Attachments must be PDF, image, or Word files under 10 MB.")
            return redirect("ucr-amend", record_id=record_id)

    source.regime = regime
    source.documents = source.documents + new_documents
    source.save()
    base_index = len(source.documents) - len(new_documents)
    for key, uploaded in uploads:
        UcrDocumentAttachment.objects.create(ucr=source, row_index=base_index + int(key[5:]), file=uploaded, original_name=uploaded.name[:255])
    messages.success(request, f"Amendment submitted. {source.ucr_no} has been updated.")
    return redirect("ucr-detail", record_id=source.pk)


APPLICATION_PARTY_FIELDS = ("name", "physical_country", "physical_address", "postal_country", "tel", "fax", "email", "postal_address", "mda_ref", "sector", "warehouse")
APPLICATION_DECIMAL_FIELDS = ("exchange_rate", "fob_fcy", "fob_ncy", "freight_fcy", "freight_ncy", "insurance_fcy", "insurance_ncy",
                             "other_costs_fcy", "other_costs_ncy", "customs_value_fcy", "customs_value_ncy")
APPLICATION_CURRENCY_RATES = {"GHS": "1", "USD": "12.41", "GBP": "16.22", "EUR": "14.08", "CAD": "9.02", "CHF": "13.90",
                              "JPY": "0.085", "SEK": "1.20", "NOK": "1.18", "DKK": "1.89", "AUD": "8.10", "ZAR": "0.71",
                              "CNY": "1.71", "NZD": "7.35", "NGN": "0.008", "XOF": "0.021"}
APPLICATION_DELIVERY_TERMS = {"CFR", "CIF", "CIP", "CPT", "DAF", "DAP", "DDP", "DAT", "DDU", "DEQ", "DES", "EXW", "FAS", "FCA", "FOB", "ZZZ"}


def _application_initial_from_ucr(ucr):
    """Prefill a new Consignment Document from its issued UCR (dotted party keys match the form fields)."""
    exporter_name = ucr.exporter_identity and ucr.exporter_name and ucr.exporter_identity != ucr.exporter_name and f"{ucr.exporter_identity}, {ucr.exporter_name}" or (ucr.exporter_name or ucr.exporter_identity or "")
    importer_code = ucr.importer_identity and ucr.importer_name and ucr.importer_identity != ucr.importer_name and f"{ucr.importer_identity}, {ucr.importer_name}" or (ucr.importer_name or ucr.importer_identity or "")
    return {
        "reference_info": ucr.user_reference,
        "exporter.name": exporter_name, "exporter.physical_country": ucr.exporter_country,
        "exporter.physical_address": ucr.exporter_address, "exporter.postal_country": ucr.exporter_country,
        "exporter.tel": ucr.exporter_phone, "exporter.fax": ucr.exporter_fax,
        "exporter.postal_address": ucr.exporter_address,
        "consignor_same": False,
        "importer.code": importer_code,
        "importer.physical_country": ucr.importer_country, "importer.physical_address": ucr.importer_address,
        "importer.postal_country": ucr.importer_country, "importer.tel": ucr.importer_phone,
        "importer.fax": ucr.importer_fax, "importer.postal_address": ucr.importer_address,
        "consignee_same": False,
        "means_of_transport": ucr.transport_mode, "items": [],
    }


def _application_record_payload(record):
    payload = {}
    for role in ("exporter", "consignor", "importer", "consignee"):
        if role in ("consignor", "consignee"):
            payload[f"{role}_same"] = getattr(record, f"{role}_same")
        for key in APPLICATION_PARTY_FIELDS:
            if key == "name" and role in ("importer", "consignee"):
                payload[f"{role}.code"] = getattr(record, f"{role}_code")
            else:
                payload[f"{role}.{key}"] = getattr(record, f"{role}_{key}")
    for field in ("reference_info", "means_of_transport", "vessel_name", "voyage_no", "shipment_date", "carrier", "manifest_no", "bl_awb_no", "marks_numbers",
                  "port_arrival", "port_departure", "customs_office", "freight_station", "inland_transport_co", "inland_transport_ref",
                  "cargo_type", "containers_up_to_20", "containers_30_plus", "delivery_term", "currency", "exchange_rate",
                  "fob_fcy", "fob_ncy", "freight_fcy", "freight_ncy", "insurance_fcy", "insurance_ncy",
                  "other_costs_fcy", "other_costs_ncy", "customs_value_fcy", "customs_value_ncy", "items"):
        payload[field] = getattr(record, field)
    ucr = record.ucr
    payload["exporter.name"] = ucr.exporter_identity and ucr.exporter_name and ucr.exporter_identity != ucr.exporter_name and f"{ucr.exporter_identity}, {ucr.exporter_name}" or (ucr.exporter_name or ucr.exporter_identity or payload["exporter.name"])
    payload["importer.code"] = ucr.importer_identity and ucr.importer_name and ucr.importer_identity != ucr.importer_name and f"{ucr.importer_identity}, {ucr.importer_name}" or (ucr.importer_name or ucr.importer_identity or payload["importer.code"])
    return payload


@simulator_access_required
def consignment_application_create(request):
    """Create or resume the Consignment Document application built on an issued UCR."""
    application = None
    app_id = request.GET.get("app", "")
    if app_id.isdigit():
        application = ConsignmentApplication.objects.filter(pk=app_id, owner=_effective_owner(request)).first()
    ucr = application.ucr if application else None
    if ucr is None:
        ucr_no = request.GET.get("ucr", "").strip()
        ucr = UcrDeclaration.objects.filter(owner=_effective_owner(request), ucr_no__iexact=ucr_no, status=UcrDeclaration.Status.SUBMITTED).first() if ucr_no else None
        if ucr is None:
            messages.error(request, "Choose an issued UCR number before creating an application form.")
            return redirect("single-window-create-preparation-application")
        if application is None:
            application = ConsignmentApplication.objects.filter(owner=_effective_owner(request), ucr=ucr, status=ConsignmentApplication.Status.DRAFT).first()
    initial = _application_record_payload(application) if application else _application_initial_from_ucr(ucr)
    if initial.get("shipment_date"):
        initial["shipment_date"] = initial["shipment_date"].isoformat()
    for field in APPLICATION_DECIMAL_FIELDS:
        if initial.get(field) is not None:
            initial[field] = str(initial[field])
    mda_requests = [{
        "id": record.pk,
        "mda": record.mda.code,
        "application": f"{record.application.code}, {record.application.name}",
        "process": f"{record.process.code}, {record.process.name}",
        "application_no": record.application_no,
        "created_at": timezone.localtime(record.created_at).strftime("%d/%m/%Y %H:%M:%S"),
        "status": record.get_status_display(),
        "url": reverse("mda-consignment-application", args=(record.pk,)),
    } for record in application.mda_requests.select_related("mda", "application", "process") ] if application else []
    return render(request, "scenarios/consignment_application.html", {
        "application": application,
        "ucr": ucr,
        "initial": initial,
        "mda_requests": mda_requests,
        "approval_parties": [],
        "mda_mode": False,
        "display_application_no": application.application_no if application else "Generated after save",
        "application_type_text": "CD, Consignment Document",
        "read_only": bool(application and application.status == ConsignmentApplication.Status.SUBMITTED) or _review_target(request) is not None,
        "exporter_party_label": "Code" if UCR_PARTY_RULES.get(ucr.regime, ("name", "name"))[0] == "tin" else "Name",
        "importer_party_label": "Code" if UCR_PARTY_RULES.get(ucr.regime, ("name", "name"))[1] == "tin" else "Name",
    })


@simulator_access_required
def mda_consignment_application(request, request_id):
    record = get_object_or_404(
        MdaConsignmentRequest.objects.select_related(
            "consignment_application__ucr", "mda", "application", "process"
        ),
        pk=request_id,
        consignment_application__owner=request.user,
    )
    parent = record.consignment_application
    initial = record.form_data or _application_record_payload(parent)
    attachments = {attachment.row_index: attachment for attachment in parent.ucr.attachments.all()}
    documents = []
    for index, document in enumerate(parent.ucr.documents or []):
        attachment = attachments.get(index)
        documents.append({
            "code": document.get("code", ""),
            "name": document.get("name", ""),
            "reference": document.get("reference", ""),
            "file_name": attachment.original_name if attachment else "",
            "file_url": reverse("ucr-attachment", args=(attachment.pk,)) if attachment else "",
        })
    return render(request, "scenarios/consignment_application.html", {
        "application": parent,
        "ucr": parent.ucr,
        "initial": initial,
        "mda_requests": [],
        "approval_parties": record.additional_parties,
        "mda_mode": True,
        "mda_request": record,
        "mda_documents": documents,
        "display_application_no": record.application_no,
        "application_type_text": f"{record.application.code}, {record.application.name}",
        "read_only": False,
        "exporter_party_label": "Name",
        "importer_party_label": "Code",
    })


@simulator_access_required
@require_POST
def mda_consignment_application_save(request, request_id):
    blocked = _review_json_guard(request)
    if blocked:
        return blocked
    record = get_object_or_404(MdaConsignmentRequest, pk=request_id, consignment_application__owner=_effective_owner(request))
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "The request body is not valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "The request body must be a JSON object."}, status=400)
    record.approval_terms = bool(payload.pop("approval_terms", False))
    record.approval_purpose = str(payload.pop("approval_purpose", "")).strip()[:2000]
    record.approval_remarks = str(payload.pop("approval_remarks", "")).strip()[:5000]
    parties = payload.pop("additional_parties", [])
    record.additional_parties = parties if isinstance(parties, list) else []
    record.form_data = payload
    record.save(update_fields=("approval_terms", "approval_purpose", "approval_remarks", "additional_parties", "form_data"))
    return JsonResponse({"id": record.pk, "application_no": record.application_no, "status": record.get_status_display()})


@simulator_access_required
@require_GET
def application_hs_code_search(request):
    """Search the extracted Ghana tariff using partial code and description matches."""
    code = "".join(character for character in request.GET.get("code", "") if character.isdigit())[:10]
    description = request.GET.get("description", "").strip()[:200]
    length = request.GET.get("length", "10")
    if length not in {"2", "4", "10"}:
        length = "10"
    records = GhanaHSCode.objects.all()
    if code:
        records = records.filter(code__startswith=code)
    if description:
        records = records.filter(description__icontains=description)
    if length in {"2", "4"}:
        prefix_length = int(length)
        seen = set()
        grouped = []
        for record in records.iterator(chunk_size=500):
            prefix = record.code[:prefix_length]
            if prefix in seen:
                continue
            seen.add(prefix)
            grouped.append(record)
        page = Paginator(grouped, 10).get_page(request.GET.get("page", 1))
    else:
        page = Paginator(records, 10).get_page(request.GET.get("page", 1))
    results = []
    for record in page.object_list:
        shown_code = record.code[:int(length)]
        results.append({
            "code": shown_code,
            "full_code": record.code,
            "description": record.description,
            "prohibited": "N",
            "quantity_unit": record.quantity_unit,
            "import_duty": record.import_duty,
            "import_vat": record.import_vat,
            "nhil_rate": record.nhil_rate,
            "supplementary_unit": "",
        })
    return JsonResponse({"results": results, "total": page.paginator.count, "page": page.number, "page_count": page.paginator.num_pages})


@simulator_access_required
@require_GET
def application_port_code_search(request):
    """Search active admin-managed port codes using partial matching."""
    code = request.GET.get("code", "").strip().upper()[:12]
    name = request.GET.get("name", "").strip()[:180]
    country = request.GET.get("country", "").strip()[:100]
    records = PortCode.objects.filter(is_active=True)
    if code:
        records = records.filter(code__icontains=code)
    if name:
        records = records.filter(name__icontains=name)
    if country:
        records = records.filter(Q(country_code__icontains=country) | Q(country_name__icontains=country))
    page = Paginator(records, 10).get_page(request.GET.get("page", 1))
    results = [
        {
            "code": record.code,
            "name": record.name,
            "country_code": record.country_code,
            "country_name": record.country_name,
        }
        for record in page.object_list
    ]
    return JsonResponse({"results": results, "total": page.paginator.count, "page": page.number, "page_count": page.paginator.num_pages})


@simulator_access_required
@require_GET
def application_mda_options(request):
    """Return the admin-configured MDA → application → process hierarchy."""
    agencies = MdaAgency.objects.filter(is_active=True).prefetch_related("applications__processes")
    results = []
    for agency in agencies:
        applications = []
        for application in agency.applications.all():
            if not application.is_active:
                continue
            applications.append({
                "id": application.pk,
                "code": application.code,
                "name": application.name,
                "processes": [
                    {"id": process.pk, "code": process.code, "name": process.name}
                    for process in application.processes.all()
                    if process.is_active
                ],
            })
        results.append({"id": agency.pk, "code": agency.code, "name": agency.name, "applications": applications})
    return JsonResponse({"results": results})


def _allocate_mda_application_number(mda_code, application_code):
    """Generate a fictional 21-character number using one sequence per month."""
    cleaned_mda = "".join(character for character in mda_code.upper() if character.isalnum())
    prefix = "PCD" if cleaned_mda == "MOTI" else "CD"
    application_part = "IDF" if cleaned_mda == "MOTI" else "".join(
        character for character in application_code.upper() if character.isalnum()
    )
    sequence_month = timezone.localtime().strftime("%Y%m")
    stem_without_application = f"{prefix}{sequence_month}{cleaned_mda}"
    application_part = application_part[:max(1, 21 - len(stem_without_application) - 4)]
    stem = f"{stem_without_application}{application_part}"
    monthly_sequence = (MdaConsignmentRequest.objects.filter(sequence_month=sequence_month)
                        .aggregate(highest=Max("monthly_sequence"))["highest"] or 0) + 1
    suffix_width = 21 - len(stem)
    if len(str(monthly_sequence)) > suffix_width:
        raise ValidationError("The monthly MDA application sequence is exhausted.")
    return f"{stem}{monthly_sequence:0{suffix_width}d}", sequence_month, monthly_sequence


@simulator_access_required
@require_POST
def application_mda_request_create(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
        consignment_application = get_object_or_404(ConsignmentApplication, pk=payload.get("consignment_application_id"))
        if consignment_application.owner_id != request.user.id and not _is_simulator_author(request.user):
            raise PermissionDenied
        mda = get_object_or_404(MdaAgency, pk=payload.get("mda_id"), is_active=True)
        application = get_object_or_404(MdaApplication, pk=payload.get("application_id"), mda=mda, is_active=True)
        process = get_object_or_404(MdaProcess, pk=payload.get("process_id"), application=application, is_active=True)
        snapshot = _application_record_payload(consignment_application)
        snapshot["ucr_no"] = consignment_application.ucr.ucr_no
        snapshot = json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))
        with transaction.atomic():
            number, sequence_month, monthly_sequence = _allocate_mda_application_number(mda.code, application.code)
            record = MdaConsignmentRequest(
                consignment_application=consignment_application,
                mda=mda,
                application=application,
                process=process,
                consignment_type=payload.get("consignment_type", ""),
                master_no=str(payload.get("master_no", "")).strip(),
                application_no=number,
                sequence_month=sequence_month,
                monthly_sequence=monthly_sequence,
                form_data=snapshot,
            )
            record.full_clean()
            record.save()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "The request body is not valid JSON."}, status=400)
    except ValidationError as exc:
        message = next(iter(exc.message_dict.values()))[0] if hasattr(exc, "message_dict") else exc.messages[0]
        return JsonResponse({"error": message}, status=400)
    return JsonResponse({
        "id": record.pk,
        "mda": mda.code,
        "application": f"{application.code}, {application.name}",
        "process": f"{process.code}, {process.name}",
        "application_no": record.application_no,
        "url": reverse("mda-consignment-application", args=(record.pk,)),
        "status": record.get_status_display(),
        "created_at": timezone.localtime(record.created_at).strftime("%d/%m/%Y %H:%M:%S"),
    }, status=201)


def _parse_application_payload(request):
    """Validate the application form payload; returns (data, error_response)."""
    from datetime import date as date_type
    from decimal import Decimal, InvalidOperation, ROUND_DOWN

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse({"error": "The request body is not valid JSON."}, status=400)
    if not isinstance(payload, dict):
        return None, JsonResponse({"error": "The request body must be a JSON object."}, status=400)

    ucr_no = str(payload.get("ucr_no", "")).strip()
    ucr = UcrDeclaration.objects.filter(owner=request.user, ucr_no__iexact=ucr_no, status=UcrDeclaration.Status.SUBMITTED).first()
    if ucr is None:
        return None, JsonResponse({"error": "Link the application to one of your issued UCR numbers."}, status=400)

    data = {"ucr": ucr, "app_id": payload.get("app_id")}
    for role in ("exporter", "consignor", "importer", "consignee"):
        section = payload.get(role, {})
        if not isinstance(section, dict):
            section = {}
        data[f"{role}_same"] = bool(section.get("same", False))
        for key in APPLICATION_PARTY_FIELDS:
            source_key = "code" if key == "name" and role in ("importer", "consignee") else key
            data[f"{role}_{key}"] = str(section.get(source_key, "") or "").strip()[:2000]
    if data["consignor_same"]:
        for key in APPLICATION_PARTY_FIELDS:
            data[f"consignor_{key}"] = data[f"exporter_{key}"]
    if data["consignee_same"]:
        for key in APPLICATION_PARTY_FIELDS:
            data[f"consignee_{key}"] = data[f"importer_{key}"]
    required_general = {
        "Exporter name": data["exporter_name"], "Exporter physical country": data["exporter_physical_country"],
        "Exporter physical address": data["exporter_physical_address"], "Exporter telephone": data["exporter_tel"],
        "Consignor name": data["consignor_name"], "Consignor physical country": data["consignor_physical_country"],
        "Consignor physical address": data["consignor_physical_address"], "Consignor telephone": data["consignor_tel"],
        "Importer code": data["importer_name"], "Importer physical country": data["importer_physical_country"],
        "Importer physical address": data["importer_physical_address"], "Importer telephone": data["importer_tel"],
        "Consignee code": data["consignee_name"], "Consignee physical country": data["consignee_physical_country"],
        "Consignee physical address": data["consignee_physical_address"], "Consignee telephone": data["consignee_tel"],
    }
    missing_general = [label for label, value in required_general.items() if not value]
    if missing_general:
        return None, JsonResponse({"error": "Complete all required General fields before saving.", "fields": missing_general}, status=400)
    for field in ("reference_info", "means_of_transport", "vessel_name", "voyage_no", "carrier", "manifest_no", "bl_awb_no", "marks_numbers",
                  "port_arrival", "port_departure", "customs_office", "freight_station", "inland_transport_co", "inland_transport_ref",
                  "cargo_type", "delivery_term", "currency"):
        data[field] = str(payload.get(field, "") or "").strip()[:200]
    for field in APPLICATION_DECIMAL_FIELDS:
        raw = str(payload.get(field, "") or "").strip().replace(",", "")
        try:
            data[field] = Decimal(raw) if raw else None
        except InvalidOperation:
            return None, JsonResponse({"error": f"{field.replace('_', ' ').title()} must be a number."}, status=400)
    data["delivery_term"] = data["delivery_term"].split(",", 1)[0].upper()
    data["currency"] = data["currency"].split(",", 1)[0].upper()
    if data["delivery_term"] and data["delivery_term"] not in APPLICATION_DELIVERY_TERMS:
        return None, JsonResponse({"error": "Choose a recognised delivery term."}, status=400)
    if data["currency"] and data["currency"] not in APPLICATION_CURRENCY_RATES:
        return None, JsonResponse({"error": "Choose a currency from the Common Code search."}, status=400)
    if data["currency"]:
        rate = Decimal(APPLICATION_CURRENCY_RATES[data["currency"]])
        data["exchange_rate"] = rate
        component_fields = ("fob_fcy", "freight_fcy", "insurance_fcy", "other_costs_fcy")
        for field in component_fields:
            data[field] = data[field] or Decimal("0")
            data[field.replace("_fcy", "_ncy")] = (data[field] * rate).quantize(Decimal("0.01"))
        data["customs_value_fcy"] = sum((data[field] for field in component_fields), Decimal("0")).quantize(Decimal("0.01"))
        data["customs_value_ncy"] = (data["customs_value_fcy"] * rate).quantize(Decimal("0.01"))
    for field in ("containers_up_to_20", "containers_30_plus"):
        raw = str(payload.get(field, "") or "0").strip()
        data[field] = int(raw) if raw.isdigit() else 0
    raw_date = str(payload.get("shipment_date", "") or "").strip()
    try:
        data["shipment_date"] = date_type.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        return None, JsonResponse({"error": "Shipment Date must be a valid date."}, status=400)
    raw_items = payload.get("items", [])
    items = []
    remaining_fob = data.get("fob_fcy") or Decimal("0")
    if isinstance(raw_items, list):
        for entry in raw_items[:200]:
            if not isinstance(entry, dict):
                continue
            try:
                quantity = Decimal(str(entry.get("quantity", "") or "0").replace(",", ""))
                unit_fob = Decimal(str(entry.get("unit_fob_fcy", "") or "0").replace(",", ""))
            except InvalidOperation:
                return None, JsonResponse({"error": "Item quantity and Unit FOB FCY must be numbers."}, status=400)
            if quantity < 0 or unit_fob < 0:
                return None, JsonResponse({"error": "Item quantity and Unit FOB FCY cannot be negative."}, status=400)
            calculated_fob = (quantity * unit_fob).quantize(Decimal("0.01"))
            if calculated_fob > remaining_fob and quantity:
                unit_fob = (remaining_fob / quantity).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
                calculated_fob = min(remaining_fob, (quantity * unit_fob).quantize(Decimal("0.01")))
            calculated_ncy = (calculated_fob * (data.get("exchange_rate") or Decimal("0"))).quantize(Decimal("0.01"))
            unit_ncy = (unit_fob * (data.get("exchange_rate") or Decimal("0"))).quantize(Decimal("0.000001"))
            item = {
                "hs_code": str(entry.get("hs_code", "")).strip()[:24],
                "hs_name": str(entry.get("hs_name", "")).strip()[:300],
                "description": str(entry.get("description", "")).strip()[:500],
                "state_of_goods": str(entry.get("state_of_goods", "")).strip()[:12],
                "quantity_unit": str(entry.get("quantity_unit", "")).strip()[:12],
                "quantity": str(entry.get("quantity", "")).strip()[:20],
                "supplementary_unit": str(entry.get("supplementary_unit", "")).strip()[:12],
                "supplementary_quantity": str(entry.get("supplementary_quantity", "")).strip()[:20],
                "package_unit": str(entry.get("package_unit", "")).strip()[:12],
                "package_quantity": str(entry.get("package_quantity", "")).strip()[:20],
                "origin_country": str(entry.get("origin_country", "")).strip()[:2],
                "net_weight": str(entry.get("net_weight", "")).strip()[:20],
                "gross_weight": str(entry.get("gross_weight", "")).strip()[:20],
                "currency": str(entry.get("currency", "")).strip()[:8],
                "exchange_rate": str(entry.get("exchange_rate", "")).strip()[:20],
                "price_fcy": str(calculated_fob.quantize(Decimal("0.01"))),
                "price_ncy": str(calculated_ncy.quantize(Decimal("0.01"))),
                "unit_fob_fcy": str(unit_fob),
                "unit_fob_ncy": str(unit_ncy),
                "fob_fcy": str(calculated_fob.quantize(Decimal("0.01"))),
                "fob_ncy": str(calculated_ncy.quantize(Decimal("0.01"))),
                "remarks": str(entry.get("remarks", "")).strip()[:500],
            }
            items.append(item)
            remaining_fob = max(Decimal("0"), remaining_fob - calculated_fob)
    data["items"] = [item for item in items if any(item.values())]
    return data, None


def _apply_application_payload(record, data):
    for key, value in data.items():
        if key in ("ucr", "app_id"):
            continue
        setattr(record, key, value)


@simulator_access_required
@require_POST
def application_save_declaration(request):
    """Save issues the sequential CD number on first save and keeps the draft editable."""
    blocked = _review_json_guard(request)
    if blocked:
        return blocked
    data, error_response = _parse_application_payload(request)
    if error_response:
        return error_response
    record = None
    app_id = str(data.get("app_id") or "")
    if app_id.isdigit():
        record = ConsignmentApplication.objects.filter(pk=app_id, owner=_effective_owner(request), status=ConsignmentApplication.Status.DRAFT).first()
        if record is None:
            return JsonResponse({"error": "This application has already been submitted."}, status=400)
    record = record or ConsignmentApplication(owner=request.user, ucr=data["ucr"])
    _apply_application_payload(record, data)
    if not record.application_no:
        record.application_no = allocate_application_number()
    record.save()
    return JsonResponse({"id": record.pk, "application_no": record.application_no, "status": record.status})


@simulator_access_required
@require_POST
def application_submit_declaration(request):
    """Submit closes the draft; the CD number stays as the application's reference."""
    blocked = _review_json_guard(request)
    if blocked:
        return blocked
    data, error_response = _parse_application_payload(request)
    if error_response:
        return error_response
    app_id = str(data.get("app_id") or "")
    record = ConsignmentApplication.objects.filter(pk=app_id, owner=_effective_owner(request), status=ConsignmentApplication.Status.DRAFT).first() if app_id.isdigit() else None
    if record is None:
        return JsonResponse({"error": "Save the application before submitting it."}, status=400)
    _apply_application_payload(record, data)
    record.status = ConsignmentApplication.Status.SUBMITTED
    record.submitted_at = timezone.now()
    record.save()
    return JsonResponse({"id": record.pk, "application_no": record.application_no, "status": record.status})


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
    filters = {key: request.GET.get(key, "").strip() for key in ("ucr", "number", "exporter", "importer", "date_from", "date_to")}
    records = ConsignmentApplication.objects.none()
    has_criteria = any(filters.values())
    search_attempted = request.GET.get("searched") == "1"
    if mode == "search" and has_criteria:
        records = ConsignmentApplication.objects.filter(owner=_effective_owner(request)).select_related("ucr")
        if filters["ucr"]:
            records = records.filter(ucr__ucr_no__icontains=filters["ucr"])
        if filters["number"]:
            records = records.filter(application_no__icontains=filters["number"])
        if filters["exporter"]:
            records = records.filter(Q(exporter_name__icontains=filters["exporter"]) | Q(ucr__exporter_identity__icontains=filters["exporter"]) | Q(ucr__exporter_name__icontains=filters["exporter"]))
        if filters["importer"]:
            records = records.filter(Q(importer_code__icontains=filters["importer"]) | Q(ucr__importer_identity__icontains=filters["importer"]) | Q(ucr__importer_name__icontains=filters["importer"]))
        if filters["date_from"]:
            records = records.filter(created_at__date__gte=filters["date_from"])
        if filters["date_to"]:
            records = records.filter(created_at__date__lte=filters["date_to"])
    return render(request, "scenarios/single_window_preparation_application.html", {
        "mode": mode,
        "page_title": "Create Application" if mode == "create" else "Search Application",
        "filters": filters,
        "records": records,
        "search_error": search_attempted and not has_criteria,
        "review_mode": _review_target(request) is not None,
        "breadcrumb_section": "Preparation Application",
        "breadcrumb_create_path": reverse("single-window-create-preparation-application"),
        "breadcrumb_search_path": reverse("single-window-search-preparation-application"),
    })


@simulator_access_required
def single_window_create_consignment_application(request):
    """Consignment Application entry screen; mirrors the Preparation Application create flow."""
    return render(request, "scenarios/single_window_preparation_application.html", {
        "mode": "create",
        "page_title": "Create Application",
        "breadcrumb_section": "Consignment Application",
        "breadcrumb_create_path": reverse("single-window-create-consignment-application"),
        "breadcrumb_search_path": reverse("single-window-search-consignment-application"),
    })


@simulator_access_required
def single_window_search_consignment_application(request):
    """Consignment Application search; the records are the MDA applications created from consignment documents."""
    filters = {key: request.GET.get(key, "").strip() for key in
               ("ucr", "number", "exporter", "importer", "mda", "application", "date_from", "date_to", "status")}
    records = (MdaConsignmentRequest.objects
               .filter(consignment_application__owner=_effective_owner(request))
               .select_related("consignment_application__ucr", "mda", "application", "process")
               .order_by("-created_at"))
    if filters["ucr"]:
        records = records.filter(consignment_application__ucr__ucr_no__icontains=filters["ucr"])
    if filters["number"]:
        records = records.filter(application_no__icontains=filters["number"])
    if filters["exporter"]:
        records = records.filter(
            Q(consignment_application__exporter_name__icontains=filters["exporter"])
            | Q(consignment_application__ucr__exporter_identity__icontains=filters["exporter"])
            | Q(consignment_application__ucr__exporter_name__icontains=filters["exporter"]))
    if filters["importer"]:
        records = records.filter(
            Q(consignment_application__importer_code__icontains=filters["importer"])
            | Q(consignment_application__ucr__importer_identity__icontains=filters["importer"])
            | Q(consignment_application__ucr__importer_name__icontains=filters["importer"]))
    if filters["mda"]:
        records = records.filter(mda__code__iexact=filters["mda"])
    if filters["application"]:
        records = records.filter(application__pk=filters["application"]) if filters["application"].isdigit() else records.none()
    if filters["status"]:
        records = records.filter(status__iexact=filters["status"])
    if filters["date_from"]:
        records = records.filter(created_at__date__gte=filters["date_from"])
    if filters["date_to"]:
        records = records.filter(created_at__date__lte=filters["date_to"])
    return render(request, "scenarios/single_window_search_consignment_application.html", {
        "filters": filters,
        "records": records,
        "review_mode": _review_target(request) is not None,
        "mdas": MdaAgency.objects.filter(is_active=True).order_by("code"),
        "mda_applications": MdaApplication.objects.filter(is_active=True).select_related("mda").order_by("mda__code", "code"),
        "status_options": MdaStatus.choices,
    })


@simulator_access_required
@require_POST
def mda_request_delete(request):
    """Only draft MDA applications can be deleted from the Consignment Application search."""
    blocked = _review_form_guard(request)
    if blocked:
        return blocked
    mda_id = str(request.POST.get("mda_request_id", "")).strip()
    record = (MdaConsignmentRequest.objects.filter(pk=mda_id, consignment_application__owner=request.user).first()
              if mda_id.isdigit() else None)
    if record is None:
        messages.error(request, "Select an MDA application record to delete.")
    elif record.status != MdaStatus.DRAFT:
        messages.error(request, "Only draft MDA applications can be deleted.")
    else:
        application_no = record.application_no
        record.delete()
        messages.success(request, f"Draft MDA application {application_no} was deleted.")
    return redirect("single-window-search-consignment-application")


@simulator_access_required
@require_POST
def application_delete(request):
    blocked = _review_form_guard(request)
    if blocked:
        return blocked
    app_id = str(request.POST.get("application_id", "")).strip()
    record = ConsignmentApplication.objects.filter(pk=app_id, owner=request.user).first() if app_id.isdigit() else None
    if record is None:
        messages.error(request, "Select an application record to delete.")
    elif record.status != ConsignmentApplication.Status.DRAFT:
        messages.error(request, "Submitted applications cannot be deleted.")
    else:
        application_no = record.application_no
        record.delete()
        messages.success(request, f"Draft application {application_no} was deleted.")
    return redirect("single-window-search-preparation-application")


@simulator_access_required
def single_window_create_master_application(request):
    return render(request, "scenarios/single_window_create_master_application.html")


@simulator_access_required
@require_GET
def boe_idf_lookup(request):
    """Validate an IDF number and return the UCR attached to it."""
    number = request.GET.get("number", "").strip()
    if not number:
        return JsonResponse({"valid": False, "error": "Enter an IDF number."})
    idf = (MdaConsignmentRequest.objects
           .filter(application_no__iexact=number, mda__code="MOTI")
           .select_related("consignment_application__ucr")
           .first())
    if idf is None:
        return JsonResponse({"valid": False, "error": "No IDF with that number exists in the system."})
    ucr = idf.consignment_application.ucr
    if BoeDeclaration.objects.filter(ucr=ucr).exists():
        return JsonResponse({"valid": False, "error": "This IDF's UCR has already been used in a BOE declaration."})
    return JsonResponse({"valid": True, "ucr_no": ucr.ucr_no, "idf_no": idf.application_no})


@simulator_access_required
@require_POST
def boe_create(request):
    """Create a BOE declaration from a reuse document; a UCR can only be declared once."""
    payload = json.loads(request.body.decode("utf-8") or "{}") if request.body else {}
    reuse = str(payload.get("reuse", "")).strip().upper()
    if reuse != "IDF":
        return JsonResponse({"error": "Only the IDF reuse document is available in this training step."}, status=400)
    idf_number = str(payload.get("idf_number", "")).strip()
    idf = (MdaConsignmentRequest.objects
           .filter(application_no__iexact=idf_number, mda__code="MOTI")
           .select_related("consignment_application__ucr")
           .first())
    if idf is None:
        return JsonResponse({"error": "The IDF number is not valid. Check it and try again."}, status=400)
    ucr = idf.consignment_application.ucr
    if BoeDeclaration.objects.filter(ucr=ucr).exists():
        return JsonResponse({"error": "This UCR has already been used in a BOE declaration."}, status=400)
    declaration = BoeDeclaration.objects.create(
        owner=request.user,
        idf=idf,
        ucr=ucr,
        regime=str(payload.get("regime", "")).strip().upper()[:2],
        cpc=str(payload.get("cpc", "")).strip().upper()[:12],
        zone=str(payload.get("zone", "")).strip().upper()[:3],
        form_data=json.loads(json.dumps(_application_record_payload(idf.consignment_application), cls=DjangoJSONEncoder)),
        job_no=allocate_job_number(),
    )
    return JsonResponse({"url": reverse("boe-declaration", args=(declaration.pk,)), "job_no": declaration.job_no})


@simulator_access_required
def boe_declaration(request, declaration_id):
    """The tabbed BOE declaration; tab visibility follows the declaration status."""
    declaration = get_object_or_404(
        BoeDeclaration.objects.select_related("ucr", "idf__consignment_application"),
        pk=declaration_id, owner=request.user,
    )
    data = declaration.form_data or {}
    items = data.get("items") or []
    hs_codes = [str(item.get("hs_code", "")).strip() for item in items]
    status = declaration.status

    fob_ncy = data.get("fob_ncy")
    freight_ncy = data.get("freight_ncy")
    insurance_ncy = data.get("insurance_ncy")
    tax_rows, tax_summary = compute_from_invoice(fob_ncy, freight_ncy, insurance_ncy, hs_codes)

    regime_name = CustomsRegime.objects.filter(code=declaration.regime).values_list("name", flat=True).first() or ""
    country = lambda code: f"{code}, {COUNTRY_DISPLAY_NAMES.get((code or '').strip().upper(), '')}" if code else ""
    consignee_same = bool(data.get("consignee_same"))
    doc_date = timezone.localtime(declaration.created_at)
    expiry_date = doc_date + timedelta(days=90)
    general_sections = [
        ("Header", [
            ("Job No.", declaration.job_no),
            ("Status", declaration.status_code_display),
            ("BoE No.", declaration.declaration_no),
            ("UCR No. *", declaration.ucr.ucr_no),
            ("Regime *", declaration.regime + (f" — {regime_name}" if regime_name else "")),
            ("Customs Office *", data.get("customs_office", "")),
            ("CL. Plan *", "PMD — PMD, Pre-Arrival Declaration"),
            ("Declaration Form Type *", "G — G, General"),
            ("User Reference No.", declaration.ucr.user_reference),
            ("Doc Date *", doc_date.strftime("%d/%m/%Y")),
            ("Expiry Date For First Payment *", expiry_date.strftime("%d/%m/%Y")),
            ("Dec Date", timezone.localtime(declaration.submitted_at).strftime("%d/%m/%Y") if declaration.submitted_at else ""),
            ("Post Entry Date", ""),
        ]),
        ("Exporter", [
            ("Exporter Name *", data.get("exporter.name", "")),
            ("Country of Exporter *", country(data.get("exporter.physical_country"))),
            ("Exporter Address *", data.get("exporter.physical_address", "")),
        ]),
        ("Importer", [
            ("Importer Code *", data.get("importer.code", "")),
            ("Country of Importer *", country(data.get("importer.physical_country"))),
            ("Importer Address *", data.get("importer.physical_address", "")),
        ]),
        ("Consignee", [
            ("Same as Importer", "Yes" if data.get("consignee_same") else "No"),
            ("Consignee Code *", data.get("consignee.code", "")),
            ("Consignee Address *", data.get("consignee.physical_address", "")),
        ]),
        ("Declarant Code", [
            ("Declarant TIN", declaration.ucr.provider_code),
            ("Declarant Code", declaration.ucr.declarant_code),
            ("Declarant Name", declaration.ucr.provider_name),
            ("Declarant Address", declaration.ucr.provider_address),
        ]),
        ("Taxpayer", [
            ("Taxpayer Code", data.get("importer.code", "")),
            ("Taxpayer *", "Importer"),
        ]),
    ]
    transport = [
        ("Means of Transport", data.get("means_of_transport", "")),
        ("Vessel Name", data.get("vessel_name", "")),
        ("Voyage No.", data.get("voyage_no", "")),
        ("Shipment Date", data.get("shipment_date", "")),
        ("Carrier", data.get("carrier", "")),
        ("BL/AWB No.", data.get("bl_awb_no", "")),
        ("Port of Arrival", data.get("port_arrival", "")),
        ("Port of Departure", data.get("port_departure", "")),
        ("Customs Office", data.get("customs_office", "")),
    ]
    invoice = [
        ("Delivery Term", data.get("delivery_term", "")),
        ("Currency", data.get("currency", "")),
        ("Exchange Rate", data.get("exchange_rate", "")),
        ("FOB FCY", data.get("fob_fcy", "")),
        ("FOB Ncy", data.get("fob_ncy", "")),
        ("Freight Ncy", data.get("freight_ncy", "")),
        ("Insurance Ncy", data.get("insurance_ncy", "")),
        ("Customs Value Ncy", data.get("customs_value_ncy", "")),
    ]

    return render(request, "scenarios/boe_declaration.html", {
        "declaration": declaration,
        "general_sections": general_sections,
        "transport_fields": transport,
        "invoice_fields": invoice,
        "items": items,
        "tax_rows": tax_rows,
        "tax_total": tax_summary["total"],
        "customs_value": tax_summary["customs_value"],
    })


@simulator_access_required
@require_POST
def boe_submit(request, declaration_id):
    """Submit a draft BOE; the declaration enters the customs response stages."""
    declaration = get_object_or_404(BoeDeclaration, pk=declaration_id, owner=request.user)
    if declaration.status != BoeDeclaration.Status.DRAFT:
        messages.info(request, f"Declaration {declaration.declaration_no} has already been submitted.")
        return redirect("boe-declaration", declaration_id=declaration.pk)
    declaration.status = BoeDeclaration.Status.SUBMITTED
    declaration.submitted_at = timezone.now()
    if not declaration.declaration_no:
        declaration.declaration_no = allocate_boe_number()
    declaration.save(update_fields=("status", "submitted_at", "declaration_no", "updated_at"))
    BoeStageEvent.objects.create(declaration=declaration, name="BOE Received", created_by=request.user)
    messages.success(request, f"Declaration {declaration.declaration_no} was submitted.")
    return redirect("boe-declaration", declaration_id=declaration.pk)


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
