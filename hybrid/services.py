"""Enrolment resolution and learner-flow services for Theory & Practical.

Thin, explicit wrappers over the shared onboarding resolvers: a hybrid page
must only ever resolve a hybrid-track enrolment, never the oldest active
enrolment overall. The theory surfaces get the mirror-image guarantee through
the resolvers' own default track, so neither system can inherit the other's
enrolment however the two enrolments are ordered.
"""
from onboarding.models import Programme
from onboarding.services import active_enrolments as _track_active_enrolments
from onboarding.services import enrolment_for_request as _track_enrolment_for_request
from onboarding.services import requested_enrolment as _track_requested_enrolment

from .models import LessonAttempt


def active_enrolments(user):
    """The learner's active enrolments on hybrid-track programmes, oldest first."""
    return _track_active_enrolments(user, track=Programme.Track.HYBRID)


def requested_enrolment(request):
    """The ``?programme=``-selected hybrid enrolment, or the oldest hybrid one."""
    return _track_requested_enrolment(request, track=Programme.Track.HYBRID)


def enrolment_for_request(request):
    """The hybrid enrolment a Theory & Practical page renders on, or a 403."""
    return _track_enrolment_for_request(request, track=Programme.Track.HYBRID)


def _seed_first_step(attempt):
    first = attempt.lesson.practical_steps.order_by("order", "id").first()
    if first:
        attempt.current_step = first
        attempt.save(update_fields=("current_step",))
    return attempt


def get_or_create_attempt(enrolment, lesson):
    """The learner's current attempt for this lesson.

    Practical lessons are training, not examinations: a completed attempt is
    never reopened or overwritten, and an open one is always resumed. The
    database constraint (one open attempt per enrolment and lesson) makes the
    two cases unambiguous:

    - an open attempt exists → it is the current attempt, resumed;
    - only completed attempts exist → the completed one is returned unchanged
      (the workspace offers an explicit Practise Again action instead of
      restarting anything implicitly);
    - no attempt exists → a fresh one is created, as on first entry.
    """
    attempt = (
        LessonAttempt.objects.filter(enrolment=enrolment, lesson=lesson)
        .order_by("-started_at")
        .first()
    )
    if attempt is not None and attempt.completed_at is None:
        return attempt
    if attempt is None:
        attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
        return _seed_first_step(attempt)
    return attempt


def start_practice_attempt(enrolment, lesson):
    """Begin a fresh practice attempt on a lesson the learner already completed.

    Only ever called from the explicit Practise Again action. The previous
    attempt and all of its evidence are left exactly as they are — course
    progression reads any completed attempt — and the new attempt starts from
    the first step with its own verification state. An open attempt is
    returned unchanged: the constraint keeps one open attempt per enrolment
    and lesson, and a repeat action never multiplies them.
    """
    open_attempt = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson=lesson, completed_at__isnull=True,
    ).first()
    if open_attempt is not None:
        return open_attempt
    previous = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson=lesson, completed_at__isnull=False,
    ).order_by("-started_at").first()
    attempt = LessonAttempt.objects.create(
        enrolment=enrolment, lesson=lesson,
        theory_acknowledged_at=previous.theory_acknowledged_at if previous else None,
    )
    return _seed_first_step(attempt)


def is_practice_attempt(attempt):
    """Whether this attempt is a repeat of an already-completed lesson.

    Practical lessons are training: a repeat attempt may be walked freely —
    Check my work still verifies exactly as on the first pass, but it never
    locks the doors. Practice mode is a fact about the attempt's situation,
    not stored state: an attempt is practising whenever an earlier attempt of
    the same enrolment and lesson has already completed. The first pass —
    and any attempt made before anything completed — is never practice.
    """
    return LessonAttempt.objects.filter(
        enrolment=attempt.enrolment,
        lesson=attempt.lesson,
        completed_at__isnull=False,
        started_at__lt=attempt.started_at,
    ).exists()


def dispose_practice_records(attempt):
    """Throw a practice run's scratch records away.

    Called when the practice attempt completes (or when its completed
    workspace is next opened): the run verified against these records and
    they were never learner evidence, so the whole set is deleted. The
    attempt itself and its verified-step history stay preserved, and any
    earlier attempt is untouched. Returns the number of records removed."""
    from scenarios.models import UcrDeclaration

    deleted, _ = UcrDeclaration.all_objects.filter(practice_attempt=attempt).delete()
    return deleted


def edition_lesson_counts(enrolment, programme_version):
    """Edition-wide lesson counts for the Course Overview progress ring."""
    from .publishing import learner_edition_progress

    completed, total = learner_edition_progress(enrolment, programme_version)
    in_progress = (
        LessonAttempt.objects.filter(
            enrolment=enrolment,
            lesson__module__course__programme_version=programme_version,
            lesson__is_published=True,
            lesson__module__is_published=True,
            lesson__module__course__is_published=True,
            completed_at__isnull=True,
        )
        .values("lesson_id")
        .distinct()
        .count()
    )
    in_progress = min(in_progress, total - completed)
    return {
        "completed": completed,
        "in_progress": in_progress,
        "not_started": max(total - completed - in_progress, 0),
        "total": total,
    }


def next_lesson_for(enrolment, programme_version):
    """The lesson the learner should open next: first unlocked, not completed."""
    from .models import HybridCourse

    for course in HybridCourse.objects.filter(
        programme_version=programme_version, is_published=True,
    ).order_by("order", "title"):
        for state in module_lesson_states_multi(enrolment, course):
            if state["unlocked"] and not state["complete"]:
                return state
    return None


def module_lesson_states_multi(enrolment, course):
    """Every published lesson of a course, in curriculum order, with states.

    Like :func:`module_lesson_states`, flattened across the course's modules
    so the Course Overview can name the single "next" lesson edition-wide.
    """
    from django.urls import reverse

    from .models import HybridModule

    flattened = []
    for module in HybridModule.objects.filter(course=course, is_published=True).order_by("order", "title"):
        for state in module_lesson_states(enrolment, module):
            flattened.append({
                **state,
                "module": module,
                "course": course,
                "url": reverse("hybrid-workspace", args=[state["lesson"].pk]),
            })
    return flattened


def module_lesson_states(enrolment, module):
    """The module's published lessons in order with progression states.

    Sequential progression (D7) is enforced within the module: a lesson opens
    once it is the first one or the previous lesson's attempt is complete.
    Completed lessons stay open for revisiting — completion is never reset.
    """
    lessons = list(module.hybrid_lessons.filter(is_published=True).order_by("order", "title"))
    completed = set(
        LessonAttempt.objects.filter(
            enrolment=enrolment, lesson__in=[lesson.pk for lesson in lessons], completed_at__isnull=False,
        ).values_list("lesson_id", flat=True)
    )
    states = []
    previous_complete = True
    for lesson in lessons:
        states.append({
            "lesson": lesson,
            "complete": lesson.pk in completed,
            "unlocked": previous_complete,
        })
        previous_complete = lesson.pk in completed
    return states


def module_complete(enrolment, module):
    """D6: a module is complete when every published lesson in it is."""
    lessons = list(module.hybrid_lessons.filter(is_published=True))
    if not lessons:
        return False
    # Distinct lessons, never attempt rows: a repeated attempt must not
    # inflate a module past its lesson count.
    completed = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson__in=[lesson.pk for lesson in lessons], completed_at__isnull=False,
    ).values("lesson_id").distinct().count()
    return completed >= len(lessons)


def lesson_is_unlocked(enrolment, lesson):
    """The server-side half of the sequencing gate the roadmap displays."""
    states = module_lesson_states(enrolment, lesson.module)
    state = next((item for item in states if item["lesson"].pk == lesson.pk), None)
    return bool(state and state["unlocked"])
