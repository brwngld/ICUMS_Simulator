"""Student-facing Theory & Practical views."""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape
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
    # The pane frames the real simulator home. The student drives the
    # simulator's own navigation — the workspace never redirects the frame as
    # steps advance; each step card names the screen its work happens on.
    # A Guided Material Study lesson has no simulator walkthrough: its right
    # pane lists the supporting materials and its checks render under the
    # theory, so the frame is not used at all.
    is_guided = lesson.kind == HybridLesson.Kind.GUIDED_MATERIAL_STUDY
    frame_url = reverse("simulator-portal")
    context = {
        "title": lesson.title,
        "lesson": lesson,
        "theory": lesson.theory,
        "step_views": step_views,
        "frame_url": frame_url,
        "is_guided": is_guided,
        "materials": list(lesson.materials.order_by("order", "id")) if is_guided else [],
        "knowledge_checks": list(lesson.knowledge_checks.order_by("order", "id")) if is_guided else [],
        "attempt": None,
        "review_mode": review_mode,
    }
    if attempt is not None:
        snapshot = verification.attempt_snapshot(attempt)
        # Practice mode: a repeat of an already-completed lesson. Check my work
        # behaves exactly as on the first pass — same engine, same messages,
        # same evidence — but the steps never lock, so the learner can walk
        # the guide freely and practise what they want.
        snapshot["practice"] = services.is_practice_attempt(attempt)
        context["attempt"] = snapshot
        # Practical lessons are training: a completed attempt can be repeated
        # with a fresh one. Journey-bound steps are worked inside their
        # journey's own lifecycle, so the repeat action is offered only where
        # the legacy engine owns every step.
        context["can_practise_again"] = (
            attempt.completed_at is not None and not journey_by_step and not review_mode
        )
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
    """The Theory & Practical Course Overview: the student learning portal.

    Reuses the approved theory Course Overview design (course-overview.css)
    over the hybrid curriculum — Programme → Course → Module → Lesson, with
    per-course progress, completion and the lesson the learner should open
    next. Completion and lock states come from the learner's own attempts.
    """
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    programme = enrolment.programme_version.programme
    course_rows = []
    module_total = 0
    lesson_total = 0
    for course in HybridCourse.objects.filter(
        programme_version=enrolment.programme_version, is_published=True,
    ).order_by("order", "title"):
        module_rows = []
        course_completed = 0
        course_lessons = 0
        for module in course.hybrid_modules.filter(is_published=True).order_by("order", "title"):
            states = services.module_lesson_states(enrolment, module)
            completed_count = sum(1 for state in states if state["complete"])
            module_rows.append({
                "module": module,
                "lessons": states,
                "complete": services.module_complete(enrolment, module),
                "completed_count": completed_count,
                "lesson_count": len(states),
            })
            module_total += 1
            course_completed += completed_count
            course_lessons += len(states)
        course_rows.append({
            "course": course,
            "modules": module_rows,
            "completed_count": course_completed,
            "lesson_count": course_lessons,
        })
        lesson_total += course_lessons
    counts = services.edition_lesson_counts(enrolment, enrolment.programme_version)
    next_state = services.next_lesson_for(enrolment, enrolment.programme_version)
    percentage = round(counts["completed"] / counts["total"] * 100) if counts["total"] else 0
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
        "title": "Course Overview",
        "programme": programme,
        "courses": course_rows,
        "module_total": module_total,
        "lesson_total": lesson_total,
        "completed": counts["completed"],
        "total": counts["total"],
        "lesson_counts": counts,
        "course_percentage": percentage,
        "next_state": next_state,
        "journeys": journeys,
    })


@login_required
def lesson_theory(request, lesson_id):
    """The standalone theory page for one lesson.

    The student reads the theory, acknowledges it, then starts the practical.
    A 'Start the practical' button appears once the theory is acknowledged
    (or immediately if it was already acknowledged on a prior visit)."""
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    lesson = _edition_lesson(enrolment, lesson_id)
    attempt = services.get_or_create_attempt(enrolment, lesson)
    review_mode = bool(request.session.get("simulator_review_user_id"))
    return render_student_page(request, "hybrid/theory.html", {
        "title": f"{lesson.title} · Theory",
        "lesson": lesson,
        "theory": lesson.theory,
        "attempt": {"id": str(attempt.pk), "theory_acknowledged": attempt.theory_acknowledged_at is not None} if attempt and not review_mode else None,
        "review_mode": review_mode,
    })


@login_required
def workspace(request, lesson_id):
    """The two-panel Theory & Practical workspace for one lesson.

    The left panel is the lesson's own reading and practical journey; the
    right panel frames the real simulator (same-origin, the whole page,
    chrome and navigation included). Opening the lesson resumes the learner's
    open attempt; a completed lesson reopens as review, with an explicit
    Practise Again action — the workspace never restarts anything implicitly.
    """
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    lesson = _edition_lesson(enrolment, lesson_id)
    attempt = services.get_or_create_attempt(enrolment, lesson)
    review_mode = bool(request.session.get("simulator_review_user_id"))

    # Bind the browser to an open practice run so the simulator's own save and
    # submit routes land in the attempt's scratch scope; clear it the moment
    # this page is anything else, so ordinary simulator work stays ordinary.
    from scenarios.practice_ucr import PRACTICE_ACTIVE_KEY

    if not review_mode and attempt.completed_at is None and services.is_practice_attempt(attempt):
        request.session[PRACTICE_ACTIVE_KEY] = str(attempt.pk)
    else:
        request.session.pop(PRACTICE_ACTIVE_KEY, None)
    return render_student_page(
        request,
        "hybrid/workspace.html",
        lesson_workspace_context(lesson, attempt, review_mode=review_mode),
    )


@login_required
@require_POST
def practise_again(request, lesson_id):
    """Start a fresh practice attempt on a completed lesson.

    Training lessons may be repeated: the previous attempt and its evidence
    are untouched, course progression still reads them, and the new attempt
    begins at the first step with its own verification state. Refused while
    an open attempt exists (the database constraint agrees), for journey-bound
    lessons (their steps live in the journey's own lifecycle), and for lessons
    the learner's sequencing has not unlocked.
    """
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = services.enrolment_for_request(request)
    lesson = _edition_lesson(enrolment, lesson_id)
    if _lesson_journeys(lesson):
        raise PermissionDenied("This lesson's steps are worked inside a Practical Workflow.")
    services.start_practice_attempt(enrolment, lesson)
    return redirect("hybrid-workspace", lesson_id=lesson.pk)


def _attempt_and_step(request, attempt_id, step_index):
    """Owner-scoped attempt + the step at the requested position."""
    attempt = LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request.user).first()
    if attempt is None:
        return None, None, JsonResponse({"ok": False, "error": "No such attempt."}, status=404)
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    if not 0 <= step_index < len(steps):
        return attempt, None, JsonResponse({"ok": False, "error": "No such step."}, status=404)
    return attempt, steps[step_index], None


def _dispose_if_practice_run_complete(request, attempt):
    """A practice run's scratch records live only as long as the run.

    The moment the attempt completes, its records are thrown away (the
    verified-step history stays), and the browser's practice binding is
    cleared so ordinary simulator work resumes being ordinary."""
    attempt.refresh_from_db(fields=("completed_at",))
    if attempt.completed_at is None or not services.is_practice_attempt(attempt):
        return
    from scenarios.practice_ucr import clear_practice_binding

    services.dispose_practice_records(attempt)
    clear_practice_binding(request)


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
    _dispose_if_practice_run_complete(request, attempt)
    return JsonResponse(result)


def _advance_journey(lesson_attempt, step):
    """Return (allowed, moved, message), or None for an unassigned step."""
    assignment = JourneyStep.objects.filter(step=step).select_related("journey").first()
    if assignment is None:
        return None
    journey_attempt = JourneyAttempt.objects.select_for_update().filter(
        enrolment=lesson_attempt.enrolment, journey=assignment.journey,
    ).first()
    if journey_attempt is None:
        return False, False, "No journey attempt is available for this learner."
    current = journey_attempt.current_journey_step
    if current is None or current.journey_id != assignment.journey_id:
        return False, False, "This journey step is not currently available."
    if current.journey_order > assignment.journey_order:
        return True, False, ""
    if current.pk != assignment.pk:
        return False, False, "This journey step is not currently available."
    _locked, moved, message = journey_services.journey_advance(journey_attempt)
    has_successor = JourneyStep.objects.filter(
        journey=assignment.journey, journey_order__gt=assignment.journey_order,
    ).exists()
    # Final journey completion can still require later, unassigned lesson steps.
    return moved or not has_successor, moved, message


@login_required
@require_POST
@transaction.atomic
def step_advance(request, attempt_id, step_index):
    """Commit required journey advancement and the lesson position together.

    The satisfaction gate is the guided sequence itself and applies on every
    attempt — first pass or practice repeat alike. Practice mode only marks
    the repeat (the workspace shows it, previous attempts stay preserved);
    it never unlocks anything."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    if verification.step_requires_verification(step) and not verification.step_satisfied(attempt, step):
        return JsonResponse(
            {"allowed": False, "message": "This step must pass “Check my work” before the next one opens."},
            status=403,
        )
    journey_result = _advance_journey(attempt, step)
    allowed, moved, message = journey_result if journey_result is not None else (True, False, "")
    if not allowed:
        # The existing workspace renders failure messages as HTML.
        return JsonResponse(
            {"allowed": False, "message": escape(message), "journey_moved": moved, "journey_message": message},
            status=403,
        )
    attempt = LessonAttempt.objects.select_for_update().get(pk=attempt.pk)
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    current_index = next(
        (index for index, item in enumerate(steps) if item.pk == attempt.current_step_id), -1,
    )
    if step_index + 1 < len(steps) and (journey_result is None or current_index <= step_index):
        attempt.current_step = steps[step_index + 1]
        attempt.save(update_fields=("current_step",))
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
    _dispose_if_practice_run_complete(request, attempt)
    return JsonResponse({"ok": True, "lesson_complete": lesson_complete})


@login_required
@require_POST
def stage_evidence(request, attempt_id):
    """Record a form-progress signal from the simulator iframe.

    The workspace JS watches the iframe for regime selection and section
    completion, and posts here so the attempt carries evidence for those
    stages. This is not learner-creation evidence (the creation ledger is
    untouched) — it is the attempt's own form-progress trail that
    stage-evidence conditions verify against."""
    attempt = LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request.user).first()
    if attempt is None:
        return JsonResponse({"ok": False, "error": "No such attempt."}, status=404)
    import json as _json
    body = _json.loads(request.body) if request.body else {}
    stage = body.get("stage", "")
    if stage not in ("regime_selected", "sections_completed"):
        return JsonResponse({"ok": False, "error": "Unknown stage."}, status=400)
    evidence = dict(attempt.stage_evidence or {})
    if stage == "regime_selected":
        evidence["regime_selected"] = body.get("value", "")
    elif stage == "sections_completed":
        evidence["sections_completed"] = True
    attempt.stage_evidence = evidence
    attempt.save(update_fields=("stage_evidence",))
    verification.refresh_completion(attempt)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def step_hint(request, attempt_id, step_index):
    """A live hint: check the learner's current state against this step's
    conditions and return what's missing or wrong — not a generic message.

    The workspace JS may include the iframe's current form state so the hint
    can name the specific fields that are still empty."""
    attempt, step, error = _attempt_and_step(request, attempt_id, step_index)
    if error:
        return error
    import json as _json
    form_state = {}
    if request.body:
        try:
            form_state = _json.loads(request.body)
        except (ValueError, TypeError):
            form_state = {}

    hint = verification.build_step_hint(attempt, step, form_state)
    return JsonResponse({"ok": True, "hint": hint})


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
