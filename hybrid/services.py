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


def get_or_create_attempt(enrolment, lesson):
    """The learner's single attempt for this lesson, resuming where it stopped."""
    attempt, created = LessonAttempt.objects.get_or_create(enrolment=enrolment, lesson=lesson)
    if created:
        first = lesson.practical_steps.order_by("order", "id").first()
        if first:
            attempt.current_step = first
            attempt.save(update_fields=("current_step",))
    return attempt


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
    completed = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson__in=[lesson.pk for lesson in lessons], completed_at__isnull=False,
    ).count()
    return completed >= len(lessons)


def lesson_is_unlocked(enrolment, lesson):
    """The server-side half of the sequencing gate the roadmap displays."""
    states = module_lesson_states(enrolment, lesson.module)
    state = next((item for item in states if item["lesson"].pk == lesson.pk), None)
    return bool(state and state["unlocked"])
