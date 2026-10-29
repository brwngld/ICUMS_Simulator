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
from scenarios.bindings import VERIFY_RECORDS

from . import attribution as attribution_services
from . import journey_services, journey_verification
from . import services
from . import verification
from .models import (
    HybridCourse,
    HybridLesson,
    JourneyAttempt,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
)
from .publishing import learner_edition_progress


def _role_rows(attempt, roles, rows, review_mode):
    """One record role as a learner sees it: what it holds, what it is still
    waiting for, and which of the learner's records may be confirmed for it.

    ``roles`` is the caller's selection — every required role of the journey on
    the journey page, the roles bound to one step's checks in a workspace card —
    and ``rows`` is that journey's step reading, which the caller already has, so
    naming a role never re-evaluates the journey. Each role's freshness floor is
    the opening moment of the step its check lives on: the same floor the check
    reads, so a record the picker lists as current is a record the check measures
    the same way. Instructor review renders the same rows with no choices.
    """
    by_step = {row["step"].pk: row for row in rows}
    window_by_step = {}
    out = []
    for role in roles:
        binding = role.condition_bindings.select_related("condition__step").first()
        step_row = by_step.get(binding.condition.step_id) if binding else None
        if step_row is None or step_row["lesson_attempt"] is None:
            window_start = attempt.started_at
        else:
            window_start = window_by_step.setdefault(
                step_row["step"].pk,
                max(attempt.started_at, verification.opened_at(step_row["lesson_attempt"], step_row["step"])),
            )
        satisfied, message = journey_services.role_satisfied(attempt, role)
        association = journey_services.active_record(attempt, role)
        step_verified = bool(step_row and step_row["verified"])
        if step_verified and satisfied:
            row_state = "verified"
            state_label = "Practical step verified"
        elif association and satisfied:
            row_state = "attributed"
            state_label = "Record attributed but not yet verified"
        elif association:
            row_state = "ineligible"
            state_label = "Record no longer eligible"
        else:
            row_state = "empty"
            state_label = "No record attributed"
        out.append({
            "role": role,
            "record_type_label": VERIFY_RECORDS[role.record_kind][1],
            "satisfied": satisfied,
            "message": message,
            "association": association,
            "step_verified": step_verified,
            "state": row_state,
            "state_label": state_label,
            "eligible": (
                [] if review_mode
                else attribution_services.attributable_rows(attempt, role, window_start=window_start)
            ),
            "can_attribute": (
                attempt.status == JourneyAttempt.Status.IN_PROGRESS and not review_mode
            ),
        })
    return out


def _lesson_journeys(lesson):
    """The journey each of this lesson's practical steps runs inside, keyed by
    step id.

    A step no journey has claimed stays an ordinary lesson step: the workspace
    gives it no record confirmation and the lesson engine keeps checking it
    against the learner's own records, exactly as it always has.
    """
    return {
        assignment.step_id: assignment.journey
        for assignment in JourneyStep.objects.filter(step__lesson=lesson).select_related("journey")
    }


def lesson_workspace_context(lesson, attempt=None, review_mode=False):
    """Everything the workspace template needs to render one lesson.

    Shared by the student workspace (published content, enrolment-scoped)
    and the instructor preview (draft content) so the two can never drift.
    The attempt snapshot is what lets the browser resume exactly where the
    server says the learner stands; the preview passes no attempt, which puts
    the workspace's step controls into their inert preview mode.

    A step the curriculum assigns to a journey is worked *inside* that journey,
    so opening the lesson opens the journey attempt too: ``started_at`` is the
    floor of the record-creation window, and a record the learner makes after
    reading the task only counts if the attempt already exists. Review mode
    renders the same page without writing anything.
    """
    journey_by_step = _lesson_journeys(lesson) if attempt is not None else {}
    journeys = {journey.pk: journey for journey in journey_by_step.values()}
    journey_attempts = {}
    if journeys and not review_mode:
        journey_attempts = {
            pk: journey_services.get_or_create_attempt(attempt.enrolment, journey)
            for pk, journey in journeys.items()
        }
    rows_by_journey = {
        pk: journey_services.journey_step_rows(journey_attempt)
        for pk, journey_attempt in journey_attempts.items()
    }
    step_views = []
    for index, step in enumerate(lesson.practical_steps.all()):
        journey = journey_by_step.get(step.pk)
        journey_attempt = journey_attempts.get(journey.pk) if journey else None
        step_views.append({
            "index": index,
            "step": step,
            "screen_url": reverse(step.screen) if step.screen else "",
            "screen_label": step.screen_label(),
            "journey": journey,
            "role_rows": [] if journey_attempt is None else _role_rows(
                journey_attempt,
                JourneyRecordRole.objects.filter(
                    journey=journey, condition_bindings__condition__step=step,
                ).distinct().order_by("order", "id"),
                rows_by_journey[journey.pk],
                review_mode,
            ),
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
        "review_mode": review_mode,
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
        rows = journey_services.journey_step_rows(attempt) if attempt else None
        journeys.append({
            "journey": journey,
            "attempt_exists": attempt is not None,
            "complete": attempt is not None and attempt.completed_at is not None,
            # Before an attempt exists there are no rows to count, and the card
            # still has to name the journey's size: the assigned steps are the
            # total, and the learner is standing at the first one. Once every
            # step is satisfied the learner is still read as standing on the
            # last one — the journey card says "Journey complete" only when the
            # whole journey has actually closed, and the two must not disagree.
            "current_position": (
                min(sum(1 for row in rows if row["satisfied"]) + 1, len(rows)) if rows else 1
            ),
            "position_total": (len(rows) if rows else journey.step_assignments.count()),
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
    review_mode = bool(request.session.get("simulator_review_user_id"))
    return render_student_page(
        request,
        "hybrid/workspace.html",
        lesson_workspace_context(lesson, attempt, review_mode=review_mode),
    )


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
    try:
        verification.record_open(attempt, step)
    except verification.JourneyOpeningError as exc:
        return JsonResponse({"ok": False, "error": exc.message, "code": exc.code}, status=403)
    # A condition-free step is satisfied by being opened, so entering it can be
    # the last thing a lesson was waiting for.
    verification.refresh_completion(attempt)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def step_check(request, attempt_id, step_index):
    """Run the step's conditions entirely server-side; a pass writes the
    durable verified stamp and may complete the lesson.

    A step assigned to a journey is checked by the exact-record journey
    engine, which re-resolves the step's evidence under its locks, records the
    immutable evidence rows and refreshes both completion signals in the same
    transaction. Anything else keeps the legacy owner-wide engine unchanged.
    """
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    try:
        result = journey_verification.verify_journey_step(request.user, attempt, step)
    except journey_verification.JourneyVerificationPending as exc:
        return JsonResponse({"ok": False, "error": exc.message, "code": exc.code}, status=409)
    except journey_verification.JourneyVerificationResolutionError as exc:
        return JsonResponse({"ok": False, "error": exc.message, "code": exc.code}, status=403)
    if result is None:
        result = verification.verify_step(attempt, step)
        if result["passed"]:
            attempt.current_step = step
            attempt.save(update_fields=("current_step",))
        result["lesson_complete"] = verification.refresh_completion(attempt)
    return JsonResponse(result)


def _advance_journey(lesson_attempt, step):
    """Move the journey position with the lesson position, and report the
    journey's own word on it.

    Next is how the learner says "this activity is done", so a step worked
    inside a journey has to advance that journey too — left behind, the next
    journey-checked step would refuse as ``step_not_current`` while the lesson
    itself had moved on. The journey engine owns the ceiling and the
    dependencies, so this can only ever be refused by the learner's own
    outstanding evidence; the pair is ``(moved, sentence)``, and the card is
    what reads the sentence back to the learner.
    """
    assignment = JourneyStep.objects.filter(step=step).select_related("journey").first()
    if assignment is None:
        return False, ""
    journey_attempt = JourneyAttempt.objects.filter(
        enrolment=lesson_attempt.enrolment, journey=assignment.journey,
    ).first()
    if journey_attempt is None:
        return False, ""
    _locked, moved, message = journey_services.journey_advance(journey_attempt)
    return moved, message


@login_required
@require_POST
def step_advance(request, attempt_id, step_index):
    """The server-side half of step sequencing: a step that declares
    verification holds the journey until its current evidence passes (hiding
    the button is not the enforcement)."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    if verification.step_requires_verification(step) and not verification.step_satisfied(attempt, step):
        return JsonResponse(
            {"allowed": False, "message": "This step must pass “Check my work” before the next one opens."},
            status=403,
        )
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    if step_index + 1 < len(steps):
        attempt.current_step = steps[step_index + 1]
        attempt.save(update_fields=("current_step",))
    moved, message = _advance_journey(attempt, step)
    return JsonResponse({"allowed": True, "journey_moved": moved, "journey_message": message})


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
    review_mode = bool(request.session.get("simulator_review_user_id"))
    role_rows = _role_rows(
        attempt,
        JourneyRecordRole.objects.filter(journey=journey, required=True).order_by("order", "id"),
        rows,
        review_mode,
    )
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
        "review_mode": review_mode,
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
    """The records this learner may confirm for one required record role —
    server-generated only; the request supplies nothing."""
    if request.session.get("simulator_review_user_id"):
        return JsonResponse({"error": "Instructor review is view-only."}, status=403)
    journey = get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
    )
    enrolment = services.enrolment_for_request(request)
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    attempt = get_object_or_404(JourneyAttempt, enrolment=enrolment, journey=journey)
    role = get_object_or_404(JourneyRecordRole, pk=role_id, journey=journey)
    rows = attribution_services.attributable_rows(attempt, role)
    return JsonResponse({"role_id": str(role.pk), "eligible": rows})


@login_required
@require_POST
def journey_role_attribute(request, journey_id, role_id):
    """Confirm one record for this role — a creation the learner made inside the
    journey, or an existing record the role asks them to reuse. Server-validated
    end to end; a refusal is a controlled JSON error, never a silent one."""
    if request.session.get("simulator_review_user_id"):
        return JsonResponse({"error": "Instructor review is view-only."}, status=403)
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
    try:
        attribution_services.attribute_record(
            attempt,
            role,
            creation_id=payload.get("creation_id"),
            record_id=payload.get("record_id"),
            student=request.user,
        )
    except attribution_services.AttributionError as exc:
        return JsonResponse({"error": exc.message, "code": exc.code}, status=exc.status)
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    return JsonResponse({
        "role_id": str(role.pk),
        "attributed": True,
        "message": "Record attributed to this journey role.",
    })
