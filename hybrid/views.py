"""Student-facing Theory & Practical views."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.admin_dashboard import render_student_page
from onboarding.services import needs_disclaimer_acceptance

from . import attribution as attribution_services
from . import journey_services
from . import services
from . import verification
from .models import (
    HybridCourse,
    HybridLesson,
    JourneyAttempt,
    JourneyRecordRole,
    LessonAttempt,
    PracticalJourney,
)
from .publishing import learner_edition_progress


def lesson_workspace_context(lesson, attempt=None):
    """Everything the workspace template needs to render one lesson.

    Shared by the student workspace (published content, enrolment-scoped)
    and the instructor preview (draft content) so the two can never drift.
    The attempt snapshot is what lets the browser resume exactly where the
    server says the learner stands; the preview passes no attempt, which puts
    the workspace's step controls into their inert preview mode.
    """
    step_views = []
    for index, step in enumerate(lesson.practical_steps.all()):
        step_views.append({
            "index": index,
            "step": step,
            "screen_url": reverse(step.screen) if step.screen else "",
            "screen_label": step.screen_label(),
        })
    # A lesson whose steps all omit a screen frames the simulator portal.
    frame_url = next(
        (item["screen_url"] for item in step_views if item["screen_url"]),
        reverse("simulator-portal"),
    )
    context = {
        "title": lesson.title,
        "lesson": lesson,
        "theory": lesson.theory,
        "step_views": step_views,
        "frame_url": frame_url,
        "attempt": None,
    }
    if attempt is not None:
        context["attempt"] = verification.attempt_snapshot(attempt)
    return context


def _edition_lesson(enrolment, lesson_id):
    """The published lesson of the learner's own edition, sequencing applied.

    A lesson of another programme version — or an unpublished one — is a
    plain 404; a lesson whose module predecessor is incomplete is refused
    outright, so direct URLs cannot bypass the required order (D7).
    """
    lesson = get_object_or_404(
        HybridLesson.objects.filter(
            is_published=True,
            module__is_published=True,
            module__course__is_published=True,
            module__course__programme_version=enrolment.programme_version,
        ).select_related("module__course__programme_version"),
        pk=lesson_id,
    )
    if not services.lesson_is_unlocked(enrolment, lesson):
        raise PermissionDenied("Finish the previous lesson before opening this one.")
    return lesson


@login_required
def roadmap(request):
    """The Theory & Practical learning flow: courses, modules, lessons, with
    completion and lock states resolved from the learner's own attempts."""
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    programme = enrolment.programme_version.programme
    courses = []
    for course in HybridCourse.objects.filter(
        programme_version=enrolment.programme_version, is_published=True,
    ).order_by("order", "title"):
        module_rows = []
        for module in course.hybrid_modules.filter(is_published=True).order_by("order", "title"):
            states = services.module_lesson_states(enrolment, module)
            module_rows.append({
                "module": module,
                "lessons": states,
                "complete": services.module_complete(enrolment, module),
            })
        courses.append({"course": course, "modules": module_rows})
    completed, total = learner_edition_progress(enrolment, enrolment.programme_version)
    journeys = []
    for journey in PracticalJourney.objects.filter(
        programme_version=enrolment.programme_version,
        course__is_published=True,
    ).order_by("course__order", "order", "title"):
        attempt = JourneyAttempt.objects.filter(enrolment=enrolment, journey=journey).first()
        position_total = JourneyRecordRole.objects.filter(journey=journey).count()
        rows = journey_services.journey_step_rows(attempt) if attempt else None
        journeys.append({
            "journey": journey,
            "attempt_exists": attempt is not None,
            "complete": attempt is not None and attempt.completed_at is not None,
            "current_position": (sum(1 for row in rows if row["satisfied"]) + 1) if rows else 1,
            "position_total": len(rows) if rows else 0,
        })
    return render_student_page(request, "hybrid/roadmap.html", {
        "title": "Theory & Practical",
        "programme": programme,
        "courses": courses,
        "completed": completed,
        "total": total,
        "journeys": journeys,
    })


@login_required
def workspace(request, lesson_id):
    """The two-panel Theory & Practical workspace for one lesson.

    The left panel is the lesson's own reading and practical journey; the
    right panel frames the real simulator screen the current step points at
    (same-origin, the whole page, exactly as the /test Practice Desk does).
    Opening the lesson resumes the learner's single attempt — the workspace
    never restarts a journey.
    """
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    lesson = _edition_lesson(enrolment, lesson_id)
    attempt = services.get_or_create_attempt(enrolment, lesson)
    return render_student_page(request, "hybrid/workspace.html", lesson_workspace_context(lesson, attempt))


def _attempt_and_step(request, attempt_id, step_index):
    """Owner-scoped attempt + the step at the requested position."""
    attempt = LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request.user).first()
    if attempt is None:
        return None, None, JsonResponse({"ok": False, "error": "No such attempt."}, status=404)
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    if not 0 <= step_index < len(steps):
        return attempt, None, JsonResponse({"ok": False, "error": "No such step."}, status=404)
    return attempt, steps[step_index], None


@login_required
@require_POST
def step_open(request, attempt_id, step_index):
    """Record the learner entering a step: the freshness bound for every
    saved-record condition is taken from this moment."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    verification.record_open(attempt, step)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def step_check(request, attempt_id, step_index):
    """Run the step's conditions entirely server-side; a pass writes the
    durable verified stamp and may complete the lesson."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    result = verification.verify_step(attempt, step)
    if result["passed"]:
        attempt.current_step = step
        attempt.save(update_fields=("current_step",))
    lesson_complete = verification.refresh_completion(attempt)
    return JsonResponse({**result, "lesson_complete": lesson_complete})


@login_required
@require_POST
def step_advance(request, attempt_id, step_index):
    """The server-side half of step sequencing: a step that declares
    verification holds the journey until it passes (hiding the button is not
    the enforcement)."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    if verification.step_requires_verification(step) and not verification.is_verified(attempt, step):
        return JsonResponse(
            {"allowed": False, "message": "This step must pass “Check my work” before the next one opens."},
            status=403,
        )
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    if step_index + 1 < len(steps):
        attempt.current_step = steps[step_index + 1]
        attempt.save(update_fields=("current_step",))
    return JsonResponse({"allowed": True})


@login_required
@require_POST
def acknowledge_theory(request, attempt_id):
    """D5: an explicit theory acknowledgement, required for completion but
    never a gate on reaching the practical journey."""
    attempt = LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request.user).first()
    if attempt is None:
        return JsonResponse({"ok": False, "error": "No such attempt."}, status=404)
    if attempt.theory_acknowledged_at is None:
        attempt.theory_acknowledged_at = timezone.now()
        attempt.save(update_fields=("theory_acknowledged_at",))
    lesson_complete = verification.refresh_completion(attempt)
    return JsonResponse({"ok": True, "lesson_complete": lesson_complete})


# --- Student journey page and runtime -------------------------------------------


@login_required
def journey_student(request, journey_id):
    """The learner's view of one published practical journey: canonical step
    order with per-step status, required record roles with live satisfaction,
    resume control, and completion state. Entry creates (or resumes) the
    learner's single journey attempt."""
    journey = get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
    )
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    attempt = journey_services.get_or_create_attempt(enrolment, journey)
    rows = journey_services.journey_step_rows(attempt)
    required_roles = JourneyRecordRole.objects.filter(
        journey=journey, required=True
    ).order_by("order", "id")
    role_rows = [
        {
            "role": role,
            "satisfied": journey_services.role_satisfied(attempt, role)[0],
            "message": journey_services.role_satisfied(attempt, role)[1],
            "association": journey_services.active_record(attempt, role),
        }
        for role in required_roles
    ]
    attempt.refresh_from_db()
    complete = attempt.completed_at is not None
    current_step = attempt.current_journey_step.step if attempt.current_journey_step_id else None
    for row in rows:
        row["is_current"] = (
            attempt.current_journey_step_id is not None
            and row["assignment"].pk == attempt.current_journey_step_id
        )
    return render_student_page(request, "hybrid/journey_student.html", {
        "title": "Journey · " + journey.title,
        "journey": journey,
        "attempt": attempt,
        "rows": rows,
        "role_rows": role_rows,
        "complete": complete,
        "current_step": current_step,
    })


@login_required
@require_POST
def journey_advance(request, journey_id):
    """POST-only journey progression: the learner's demonstrated position can
    only move forward, and only when the current step's evidence is complete.
    The service owns the progression ceiling, dependency checks and completion
    evaluation."""
    journey = get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
    )
    enrolment = services.enrolment_for_request(request)
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    attempt = get_object_or_404(JourneyAttempt, enrolment=enrolment, journey=journey)
    _attempt, moved, message = journey_services.journey_advance(attempt)
    if moved:
        messages.success(request, message)
    else:
        messages.warning(request, message)
    return redirect("hybrid-journey-student", journey_id=journey.pk)


@login_required
def journey_role_eligible(request, journey_id, role_id):
    """The student's eligible, unattributed creations for one required NEW
    record role — server-generated only; the request supplies nothing."""
    journey = get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
    )
    enrolment = services.enrolment_for_request(request)
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    attempt = get_object_or_404(JourneyAttempt, enrolment=enrolment, journey=journey)
    role = get_object_or_404(JourneyRecordRole, pk=role_id, journey=journey)
    rows = attribution_services.eligible_for_view(attempt, role)
    return JsonResponse({"role_id": str(role.pk), "eligible": rows})


@login_required
@require_POST
def journey_role_attribute(request, journey_id, role_id):
    """Attribute one ledger-backed creation to this role. Server-validated
    end to end; a refusal is a controlled JSON error, never a silent one."""
    journey = get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
    )
    enrolment = services.enrolment_for_request(request)
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    attempt = get_object_or_404(JourneyAttempt, enrolment=enrolment, journey=journey)
    role = get_object_or_404(JourneyRecordRole, pk=role_id, journey=journey)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "The request body is not valid JSON."}, status=400)
    creation_id = payload.get("creation_id")
    if not creation_id:
        return JsonResponse({"error": "Select a creation to attribute."}, status=400)
    try:
        attribution_services.attribute_creation(attempt, role, creation_id, request.user)
    except attribution_services.AttributionError as exc:
        return JsonResponse({"error": exc.message, "code": exc.code}, status=exc.status)
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    return JsonResponse({
        "role_id": str(role.pk),
        "attributed": True,
        "message": "Record attributed to this journey role.",
    })
