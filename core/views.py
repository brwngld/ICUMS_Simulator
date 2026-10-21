import mimetypes
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views import defaults as django_views

from accounts.context_processors import role_context
from assessments.models import Assessment
from audit.models import AuditEvent
from reports.models import CompletionRecord
from learning.services import programme_rows
from learning.views import roadmap_context
from onboarding.services import enrolment_for_request, needs_disclaimer_acceptance, programme_href, requested_enrolment
from progress.models import ProgrammeProgress
from accounts.models import SimulatorCredential
from scenarios.models import UcrDocumentAttachment
from .admin_dashboard import dashboard_callback, render_student_page


@login_required
def dashboard(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = requested_enrolment(request)
    learning = None
    if enrolment:
        learning = roadmap_context(enrolment.programme_version, enrolment)
    summaries = learning["visible_modules"] if learning else []
    final_assessment = Assessment.objects.filter(programme_version=enrolment.programme_version, assessment_type=Assessment.Type.FINAL_THEORY, is_published=True).first() if enrolment else None
    programme_progress = ProgrammeProgress.objects.filter(enrolment=enrolment).first() if enrolment else None
    completion_record = CompletionRecord.objects.filter(enrolment=enrolment).first() if enrolment else None
    roles = role_context(request)
    completed_modules = sum(item["assessment_state"] == "passed" for item in summaries)
    total_modules = len(summaries)
    module_completion_percentage = round(completed_modules / total_modules * 100) if total_modules else 0
    modules_left = max(total_modules - completed_modules, 0)
    # The first module the learner can still work on: the roadmap highlights
    # it as "Up next" and the journey cards follow the same position.
    next_module_pk = next(
        (item["module"].pk for item in summaries if item["unlocked"] and item["assessment_state"] != "passed"),
        None,
    )
    journey_stage = (
        "demonstrate" if completion_record
        else "practise" if programme_progress and programme_progress.orientation_completed_at
        else "learn"
    )

    primary_action = None
    if enrolment:
        if programme_progress and programme_progress.orientation_completed_at:
            primary_action = {
                "eyebrow": "Practical training",
                "title": "Continue your guided simulator training",
                "description": "Your theory training and simulator orientation are complete. Continue with the available practical activities.",
                "label": "Continue practical training",
                "url": programme_href(reverse("scenario-list"), enrolment),
            }
        elif programme_progress and programme_progress.orientation_unlocked_at:
            primary_action = {
                "eyebrow": "Simulator orientation",
                "title": "Complete your simulator orientation",
                "description": "Your theory requirements are complete. Finish orientation to unlock practical training.",
                "label": "Continue to orientation",
                "url": programme_href(reverse("orientation"), enrolment),
            }
        elif learning["theory_completed"] and final_assessment:
            primary_action = {
                "eyebrow": "Final theory examination",
                "title": final_assessment.title,
                "description": "You have completed every module. Take the final theory examination to continue toward practical training.",
                "label": "Take final theory examination",
                "url": learning["final_assessment_url"],
            }
        elif learning["next_assessment"]:
            assessment = learning["next_assessment"]
            primary_action = {
                "eyebrow": "Module assessment",
                "title": assessment.title,
                "description": "You have completed this module's lessons. Check your understanding to unlock the next stage.",
                "label": "Take module assessment",
                "url": learning["next_assessment_url"],
            }
        elif learning["next_lesson"]:
            lesson = learning["next_lesson"]
            primary_action = {
                "eyebrow": "Theory training",
                "title": lesson.module.title,
                "description": "Your next module is ready. Continue with its lessons and knowledge checks.",
                "label": "Continue learning",
                "url": learning["next_lesson_url"],
            }

    context = {
        "role_names": set(request.user.groups.values_list("name", flat=True)),
        "enrolment": enrolment,
        "module_summaries": summaries,
        "programme_progress": programme_progress,
        "final_assessment": final_assessment,
        "completion_record": completion_record,
        "simulator_credential": SimulatorCredential.objects.filter(user=request.user).first(),
        "can_access_instructor_portal": roles["can_access_instructor_portal"],
        "has_active_enrolment": roles["has_active_enrolment"],
        "can_access_practical": roles["can_access_practical"],
        "primary_action": primary_action,
        "completed_modules": completed_modules,
        "total_modules": total_modules,
        "module_completion_percentage": module_completion_percentage,
        "modules_left": modules_left,
        "next_module_pk": next_module_pk,
        "journey_stage": journey_stage,
        # The switcher list. Every row links to its own programme's roadmap, so
        # a learner enrolled on two programmes can reach the second one.
        "programmes": programme_rows(request.user),
        "roadmap_url": programme_href(reverse("roadmap"), enrolment),
    }
    # Presentation context only: the student/tutor home renders the shared
    # Unfold shell with its role-appropriate navigation. This supplies the
    # sidebar content without touching Django Admin's has_permission gate —
    # admin resources remain protected by the middleware and model perms.
    context["sidebar_navigation"] = admin.site.get_sidebar_list(request)
    return render_student_page(request, "core/dashboard_unfold.html", context)


@login_required
def my_programmes(request):
    """Every programme the learner is enrolled in, each linking to its own roadmap.

    Without this page the others stay unreachable: a request resolves one
    enrolment, and every row here names the programme it wants.
    """
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    return render_student_page(request, "core/my_programmes.html", {"programmes": programme_rows(request.user)})


@login_required
@require_http_methods(["GET", "POST"])
def orientation(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = enrolment_for_request(request)
    programme_progress = ProgrammeProgress.objects.filter(enrolment=enrolment, orientation_unlocked_at__isnull=False).first()
    if programme_progress is None:
        raise PermissionDenied("Pass the final theory examination before starting orientation.")
    if request.method == "POST" and programme_progress.orientation_completed_at is None:
        with transaction.atomic():
            programme_progress.orientation_completed_at = timezone.now()
            programme_progress.save(update_fields=("orientation_completed_at", "updated_at"))
            AuditEvent.objects.create(
                actor=request.user,
                action_code="orientation.completed",
                target_type="enrolment",
                target_id=str(enrolment.pk),
                summary="Completed simulator orientation.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        return redirect("dashboard")
    return render_student_page(request, "core/orientation.html", {"programme_progress": programme_progress})


def permission_denied(request, exception=None):
    """Handler for 403 (config/urls.py handler403).

    Portal access gates raise PermissionDenied with a human-readable
    reason ("No active programme enrolment was found.", "Complete
    simulator orientation…"). For authenticated users on the portal,
    answer those with a warning message and a redirect back to the page
    they came from instead of Django's bare 403 page. The admin keeps
    Django's own behaviour, as do anonymous users.
    """
    if request.user.is_authenticated and not request.path.startswith("/admin/"):
        message = str(exception) if exception and str(exception) else "You don't have access to that page."
        messages.warning(request, message)
        candidate = request.META.get("HTTP_REFERER")
        if candidate:
            parts = urlsplit(candidate)
            if parts.netloc and parts.netloc != request.get_host():
                candidate = None  # never bounce off-site
            elif parts.path == request.path:
                candidate = None  # don't redirect straight back onto the gate
        return redirect(candidate or reverse("dashboard"))
    return django_views.permission_denied(request, exception)


# Course and module covers are public artwork and lesson rich-text images are
# part of the published reading, but everything else under MEDIA_ROOT is a
# learner's own material (simulator attachments), served only to its owner or
# to staff.
PUBLIC_MEDIA_PREFIXES = ("course_covers/", "module_covers/", "lesson_rich_text/")
OWNED_MEDIA_PREFIXES = ("ucr_attachments/",)


def media_file(request, path):
    """Serve one media file after checking the viewer may see it.

    A controlled FileResponse replaces ``django.views.static.serve``: paths
    that escape MEDIA_ROOT answer 404 and every response carries
    ``X-Content-Type-Options: nosniff``. Learner uploads resolve to their
    owning record, so one signed-in user cannot fetch another's documents by
    storage path (audit SEC-01/SEC-11).
    """
    root = Path(settings.MEDIA_ROOT).resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise Http404("No such file.")
    if not path.startswith(PUBLIC_MEDIA_PREFIXES):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if path.startswith(OWNED_MEDIA_PREFIXES) and not _may_see_private_media(request, path):
            raise Http404("No such file.")
    response = FileResponse(candidate.open("rb"), content_type=mimetypes.guess_type(path)[0] or "application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _may_see_private_media(request, path):
    """Owner, staff, or an Instructor/Administrator reviewing that work."""
    attachment = UcrDocumentAttachment.objects.filter(file=path).select_related("ucr").first()
    if attachment is None:
        return False
    user = request.user
    return (
        attachment.ucr.owner_id == user.pk
        or user.is_staff
        or user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    )
