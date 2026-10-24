"""Publication readiness, the publish sweep, and clone-to-draft.

An edition publishes as it stands: courses whose lessons are complete get
their ``is_published`` flags flipped and the edition becomes the one new
enrolments land on; unfinished courses stay unpublished (partial publish, as
the theory builder does). Publishing never rewrites rows a learner is
enrolled on — the edition's identity moves, the content does not. Improving
a published edition means cloning it into a fresh empty-marked draft with
this module's cloner; existing enrolments keep their pinned version.
"""
from django.db import transaction
from django.utils import timezone

from learning.rich_text import plain_text
from onboarding.models import ProgrammeVersion

from .models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    LessonAttempt,
    PracticalStep,
    VerificationCondition,
)


def lesson_issues(lesson):
    """What a reviewer still has to fill in before this lesson is complete."""
    issues = []
    if not lesson.summary.strip():
        issues.append("The lesson summary is missing.")
    if not plain_text(lesson.theory).strip():
        issues.append("No theory reading yet — write the lesson's theory.")
    steps = list(lesson.practical_steps.all())
    if not steps:
        issues.append("No practical steps yet — the journey is empty.")
    for index, step in enumerate(steps, start=1):
        if not step.instruction.strip():
            issues.append(f"Step {index} ({step.title}) has no instruction.")
        if not step.outcome.strip():
            issues.append(f"Step {index} ({step.title}) has no expected outcome.")
        if not step.screen:
            issues.append(f"Step {index} ({step.title}) has no simulator screen.")
    return issues


def course_blockers(course):
    """Why this course is not ready to publish; empty when it is ready."""
    blockers = []
    modules = list(course.hybrid_modules.order_by("order", "title"))
    if not modules:
        return ["Add at least one module."]
    for module in modules:
        lessons = list(module.hybrid_lessons.order_by("order", "title"))
        if not lessons:
            blockers.append(f"Module “{module.title}” has no lessons.")
            continue
        for lesson in lessons:
            blockers.extend(f"Lesson “{lesson.title}”: {issue}" for issue in lesson_issues(lesson))
    return blockers


def edition_blockers(version):
    """Edition-level readiness, with every course's outstanding issues named.

    Publishing is all-or-nothing at the edition level: the publish action
    refuses until every course in the edition is ready, because a skipped
    course inside a published edition could never be published afterwards.
    """
    courses = list(version.hybrid_courses.order_by("order", "title"))
    if not courses:
        return ["The edition has no courses yet."]
    blockers = []
    for course in courses:
        issues = course_blockers(course)
        if issues:
            blockers.append(f"Course “{course.title}”: " + " ".join(issues))
    return blockers


@transaction.atomic
def publish_edition(version):
    """Flip a draft edition to published, publishing ready courses only.

    Returns (published_courses, skipped_courses). Idempotent for an already
    published edition (re-running refreshes nothing but is harmless).
    """
    if version.status == ProgrammeVersion.Status.PUBLISHED:
        courses = list(version.hybrid_courses.filter(is_published=True))
        return courses, []
    courses = list(version.hybrid_courses.order_by("order", "title"))
    published, skipped = [], []
    for course in courses:
        if course_blockers(course):
            skipped.append(course)
            continue
        course.is_published = True
        course.save(update_fields=("is_published",))
        for module in course.hybrid_modules.all():
            module.is_published = True
            module.save(update_fields=("is_published",))
            for lesson in module.hybrid_lessons.all():
                lesson.is_published = True
                lesson.save(update_fields=("is_published",))
        published.append(course)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.save(update_fields=("status", "published_at"))
    return published, skipped


@transaction.atomic
def clone_to_draft(version):
    """Copy a published edition into a fresh draft the instructor can improve.

    The learner-facing rows of ``version`` are never touched: the clone
    creates new rows under a new ProgrammeVersion, and every existing
    enrolment keeps its pinned version by construction.
    """
    last = ProgrammeVersion.objects.filter(programme=version.programme).order_by("-version").first()
    draft = ProgrammeVersion.objects.create(
        programme=version.programme,
        version=(last.version + 1) if last else 1,
        status=ProgrammeVersion.Status.DRAFT,
    )
    for course in version.hybrid_courses.order_by("order", "title"):
        course_copy = HybridCourse.objects.create(
            programme_version=draft,
            code=course.code,
            title=course.title,
            description=course.description,
            order=course.order,
        )
        for module in course.hybrid_modules.order_by("order", "title"):
            module_copy = HybridModule.objects.create(
                course=course_copy,
                code=module.code,
                title=module.title,
                description=module.description,
                order=module.order,
            )
            for lesson in module.hybrid_lessons.order_by("order", "title"):
                lesson_copy = HybridLesson.objects.create(
                    module=module_copy,
                    slug=lesson.slug,
                    title=lesson.title,
                    summary=lesson.summary,
                    theory=lesson.theory,
                    order=lesson.order,
                )
                for step in lesson.practical_steps.order_by("order", "id"):
                    step_copy = PracticalStep.objects.create(
                        lesson=lesson_copy,
                        key=step.key,
                        title=step.title,
                        instruction=step.instruction,
                        outcome=step.outcome,
                        hint=step.hint,
                        screen=step.screen,
                        order=step.order,
                    )
                    for condition in step.conditions.order_by("order", "id"):
                        VerificationCondition.objects.create(
                            step=step_copy,
                            kind=condition.kind,
                            record_kind=condition.record_kind,
                            required_status=condition.required_status,
                            expected_fields=condition.expected_fields,
                            order=condition.order,
                        )
    return draft


def learner_edition_progress(enrolment, version):
    """Completed/total published lesson counts across the edition."""
    lessons = HybridLesson.objects.filter(
        is_published=True,
        module__is_published=True,
        module__course__is_published=True,
        module__course__programme_version=version,
    )
    total = lessons.count()
    completed = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson__in=lessons, completed_at__isnull=False,
    ).count()
    return completed, total
