"""Publication readiness, the publish sweep, and clone-to-draft.

An edition publishes as it stands: courses whose lessons are complete get
their ``is_published`` flags flipped and the edition becomes the one new
enrolments land on; unfinished courses stay unpublished (partial publish, as
the theory builder does). Journey-integrity failures are the exception: they
block the whole edition, so even a direct service call cannot flip an edition
to published while one of its journeys is not publishable. Publishing never
rewrites rows a learner is enrolled on — the edition's identity moves, the
content does not. Improving a published edition means cloning it into a fresh
empty-marked draft with this module's cloner; existing enrolments keep their
pinned version.
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from learning.rich_text import plain_text
from onboarding.models import ProgrammeVersion
from scenarios.bindings import VERIFY_RECORDS

from . import journey_services
from .models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
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
    """Why this course is not ready to publish; empty when it is ready.

    Journeys belonging to the course are validated with it: a journey sitting on
    another edition's course, one whose structure or dependencies are invalid,
    or one whose required record roles cannot be satisfied under the current
    runtime blocks publication of the whole edition.
    """
    blockers = []
    modules = list(course.hybrid_modules.order_by("order", "title"))
    if not modules:
        # Reported, not returned: a course that has no modules yet can still
        # carry journeys, and those have to be readied with it.
        blockers.append("Add at least one module.")
    for module in modules:
        lessons = list(module.hybrid_lessons.order_by("order", "title"))
        if not lessons:
            blockers.append(f"Module “{module.title}” has no lessons.")
            continue
        for lesson in lessons:
            blockers.extend(f"Lesson “{lesson.title}”: {issue}" for issue in lesson_issues(lesson))
    for journey in course.practical_journeys.order_by("order", "title"):
        blockers.extend(
            f"Journey “{journey.title}”: {blocker}"
            for blocker in journey_scope_issues(journey) + journey_publication_blockers(journey)
        )
    return blockers


def journey_publication_blockers(journey):
    """Why this journey makes its edition unpublishable; empty when publishable.

    Structural integrity comes from ``journey_services.structural_issues`` —
    the same list the organizer's readiness view reads, so the two surfaces can
    never disagree about structure. Then runtime satisfiability: a required
    record role with creation mode “new” can never be satisfied, because the
    simulator schema carries no authoritative creation provenance and role
    satisfaction fails closed on created-in-journey associations — such a role
    blocks publication until provenance support exists. Optional roles never
    block; they warn. A saved-record condition the verification engine cannot
    even evaluate blocks too, because nothing could ever clear the step.
    """
    blockers = list(journey_services.structural_issues(journey))
    blockers.extend(
        f'required record role “{role.label}” cannot be satisfied: the system '
        "cannot yet verify that a record was created within a journey."
        for role in journey.record_roles.filter(
            required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
        )
    )
    blockers.extend(unverifiable_condition_issues(journey))
    return blockers


def journey_publication_warnings(journey):
    """Non-blocking publication notes for this journey: optional record roles
    that cannot currently be satisfied, and saved-record conditions not bound
    to record roles. Unbound conditions only earn a note while the verification
    engine can still check them on its own — a condition it cannot check is a
    blocker, see ``unverifiable_condition_issues``."""
    unbound = journey_services.unbound_condition_issues(journey)
    warnings = []
    for role in journey.record_roles.filter(
        required=False, creation_mode=JourneyRecordRole.CreationMode.NEW,
    ):
        warnings.append(
            f'optional record role “{role.label}” cannot currently be satisfied '
            "(creation provenance is not yet verifiable)."
        )
    # A saved-record condition the verification engine cannot check at all is a
    # blocker, not a note: calling it a warning would tell the instructor a
    # learner can still clear the step.
    if unbound and not unverifiable_condition_issues(journey):
        warnings.extend(unbound)
    return warnings


def unverifiable_condition_issues(journey):
    """Saved-record conditions on this journey's steps that the verification
    engine cannot evaluate at all, because their record kind is not in the
    approved registry. Bounded by what ``hybrid.verification`` actually reads:
    a registered kind is always checkable, bound to a role or not, so an
    unbound condition only warns."""
    issues = []
    for assignment in journey.step_assignments.select_related("step").all():
        uncheckable = [
            condition
            for condition in assignment.step.conditions.all()
            if condition.kind == VerificationCondition.Kind.SAVED_RECORD
            and condition.record_kind not in VERIFY_RECORDS
        ]
        if uncheckable:
            kinds = " ".join(sorted({condition.record_kind or "unset" for condition in uncheckable}))
            issues.append(
                f'step “{assignment.step.title}” has a saved-record condition on “{kinds}”, '
                "which is not an approved simulator record."
            )
    return issues


def journey_scope_issues(journey):
    """A journey must sit on a course of its own edition. The model checks this
    on a form; publication checks it for every journey of the edition, so a row
    written around the form cannot publish content into the wrong edition or
    strand a clone."""
    course_version = (
        HybridCourse.objects.filter(pk=journey.course_id).values_list("programme_version_id", flat=True).first()
    )
    if course_version != journey.programme_version_id:
        return ["its course belongs to another edition."]
    return []


def edition_journey_blockers(version, courses=None):
    """Journey-integrity blockers for every journey of the edition, carried or
    unattributed: invalid structure, a course/version reference pointing outside
    the edition, a saved-record condition the verification engine cannot
    evaluate, or a required NEW record role the runtime cannot satisfy.

    These four block the whole edition, never one course: a journey spans
    lessons, so no course boundary contains the failure. This is the walk the
    edition gate performs; ``publish_edition`` performs it too, so a direct
    service call cannot publish past it.
    """
    if courses is None:
        courses = list(version.hybrid_courses.order_by("order", "title"))
    carried = {journey.pk for course in courses for journey in course.practical_journeys.all()}
    blockers = []
    for journey in PracticalJourney.objects.filter(programme_version=version).order_by("order", "title"):
        issues = journey_publication_blockers(journey)
        if journey.pk not in carried:
            issues = journey_scope_issues(journey) + issues
        blockers.extend(f"Journey “{journey.title}”: {issue}" for issue in issues)
    return blockers


def edition_blockers(version):
    """Edition-level readiness, with every course and every journey of the
    edition accounted for.

    Publishing is all-or-nothing at the edition level: the publish action
    refuses until every course in the edition is ready, because a skipped
    course inside a published edition could never be published afterwards.
    Journeys are validated for the whole edition — a course carries its own, and
    one that no course of the edition carries is checked here, so an
    unattributed or cross-edition journey cannot slip past the sweep.
    """
    courses = list(version.hybrid_courses.order_by("order", "title"))
    if not courses:
        return ["The edition has no courses yet."]
    blockers = []
    carried = {journey.pk for course in courses for journey in course.practical_journeys.all()}
    for course in courses:
        issues = course_blockers(course)
        if issues:
            blockers.append(f"Course “{course.title}”: " + " ".join(issues))
    unattributed = version.practical_journeys.exclude(pk__in=carried).order_by("order", "title")
    for journey in unattributed:
        issues = journey_scope_issues(journey) + journey_publication_blockers(journey)
        if issues:
            blockers.append(f"Journey “{journey.title}”: " + " ".join(issues))
    return blockers


@transaction.atomic
def publish_edition(version):
    """Flip a draft edition to published, publishing ready courses only.

    Returns (published_courses, skipped_courses, warnings). Warnings carry
    journey executability and binding notes for the published courses — they
    never block. Idempotent for an already published edition (re-running
    refreshes nothing but is harmless).

    Raises ``ValidationError`` when any journey of the edition — carried or
    unattributed — fails its publication checks (invalid structure, a
    course/version reference outside the edition, a verification condition the
    engine cannot evaluate, a required NEW record role the runtime cannot
    satisfy). Journey-integrity failures block the whole edition, so this
    refusal applies to direct service calls exactly as it does through the
    organizer's edition gate; nothing is written when it raises. The
    course-skip path is unaffected: only lesson-completeness blockers send a
    course to ``skipped_courses``, and the edition still publishes around them
    once its journeys are sound.
    """
    if version.status == ProgrammeVersion.Status.PUBLISHED:
        courses = list(version.hybrid_courses.filter(is_published=True))
        return courses, [], []
    journey_blockers = edition_journey_blockers(version)
    if journey_blockers:
        raise ValidationError(
            "This edition cannot be published while one of its journeys is not "
            "publishable: " + " ".join(journey_blockers)
        )
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
    warnings = []
    for course in published:
        for journey in course.practical_journeys.order_by("order", "title"):
            warnings.extend(
                f"Journey “{journey.title}”: {warning}"
                for warning in journey_publication_warnings(journey)
            )
    return published, skipped, warnings


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
    step_map = {}
    condition_map = {}
    course_map = {}
    for course in version.hybrid_courses.order_by("order", "title"):
        course_copy = HybridCourse.objects.create(
            programme_version=draft,
            code=course.code,
            title=course.title,
            description=course.description,
            order=course.order,
        )
        course_map[course.pk] = course_copy
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
                    step_map[step.pk] = step_copy
                    for condition in step.conditions.order_by("order", "id"):
                        condition_copy = VerificationCondition.objects.create(
                            step=step_copy,
                            kind=condition.kind,
                            record_kind=condition.record_kind,
                            required_status=condition.required_status,
                            expected_fields=condition.expected_fields,
                            order=condition.order,
                        )
                        condition_map[condition.pk] = condition_copy
    # Journeys span lessons, so they are copied once the whole edition's steps
    # and conditions exist: inside the course loop a journey could reach a step
    # the draft does not have yet, and would be copied once per course.
    clone_journeys(version, draft, course_map, step_map, condition_map)
    return draft


def clone_journeys(source_version, draft, course_map, step_map, condition_map):
    """Copy the source edition's practical journeys onto the draft, remapping
    every step, role, condition and dependency reference to the cloned rows.

    Learner state is never copied: ``JourneyAttempt``,
    ``JourneyRecordAssociation``, ``LessonAttempt`` and ``StepEvent`` belong to
    enrolments pinned to their own editions, and the draft has no enrolments.

    Every reference is validated before anything is created: a journey whose
    course or steps sit on another edition, a dependency that names a step
    assignment outside its own journey, or a condition binding that reaches
    past the journey raises ``ValidationError`` naming the journey and the
    invalid reference. ``clone_to_draft`` is atomic, so a refused clone leaves
    no draft and no partial content behind.
    """
    journeys = list(
        PracticalJourney.objects.filter(programme_version=source_version).order_by("course__order", "order", "title")
    )
    for journey in journeys:
        if journey.course_id not in course_map:
            raise ValidationError(
                f'Journey “{journey.title}” ({journey.code}) references course pk {journey.course_id}, '
                "which is not part of the source edition.",
            )
        assignment_ids = set()
        for assignment in journey.step_assignments.select_related("step").order_by("journey_order", "id"):
            if assignment.step_id not in step_map:
                raise ValidationError(
                    f'Journey “{journey.title}” ({journey.code}) references step '
                    f'“{assignment.step.title}” (pk {assignment.step_id}), which is not part of '
                    "the source edition.",
                )
            assignment_ids.add(assignment.pk)
        for dependency in journey.dependencies.select_related(
            "predecessor_step__step", "dependent_step__step",
        ).order_by("order", "id"):
            outside = [
                role for role in (
                    ("predecessor", dependency.predecessor_step_id),
                    ("dependent", dependency.dependent_step_id),
                ) if role[1] not in assignment_ids
            ]
            if outside:
                named = " and ".join(f"{side} step assignment pk {pk}" for side, pk in outside)
                raise ValidationError(
                    f'Journey “{journey.title}” ({journey.code}) has a dependency whose {named} '
                    "does not belong to this journey.",
                )
        journey_role_ids = set(journey.record_roles.values_list("pk", flat=True))
        for binding in JourneyConditionBinding.objects.filter(
            condition__step__journey_assignment__journey=journey,
        ).select_related("condition__step", "role"):
            if binding.condition_id not in condition_map:
                raise ValidationError(
                    f'Journey “{journey.title}” ({journey.code}) binds a condition on step '
                    f'“{binding.condition.step.title}” (pk {binding.condition_id}), which is not part '
                    "of the source edition.",
                )
            if binding.role_id not in journey_role_ids:
                raise ValidationError(
                    f'Journey “{journey.title}” ({journey.code}) binds a condition to role '
                    f'“{binding.role.label}” (pk {binding.role_id}), which belongs to another journey.',
                )

    for journey in journeys:
        journey_copy = PracticalJourney.objects.create(
            programme_version=draft,
            course=course_map[journey.course_id],
            code=journey.code,
            title=journey.title,
            description=journey.description,
            order=journey.order,
            start_mode=journey.start_mode,
        )
        role_map = {}
        for role in journey.record_roles.order_by("order", "id"):
            role_map[role.pk] = JourneyRecordRole.objects.create(
                journey=journey_copy,
                key=role.key,
                label=role.label,
                record_kind=role.record_kind,
                required=role.required,
                creation_mode=role.creation_mode,
                order=role.order,
            )
        assignment_map = {}
        for assignment in journey.step_assignments.order_by("journey_order", "id"):
            assignment_map[assignment.pk] = JourneyStep.objects.create(
                journey=journey_copy,
                step=step_map[assignment.step_id],
                journey_order=assignment.journey_order,
            )
        for dependency in journey.dependencies.order_by("order", "id"):
            JourneyDependency.objects.create(
                journey=journey_copy,
                predecessor_step=assignment_map[dependency.predecessor_step_id],
                dependent_step=assignment_map[dependency.dependent_step_id],
                dependency_type=dependency.dependency_type,
                required_record_role=(
                    role_map[dependency.required_record_role_id]
                    if dependency.required_record_role_id
                    else None
                ),
                order=dependency.order,
            )
        for binding in JourneyConditionBinding.objects.filter(
            condition__step__journey_assignment__journey=journey,
        ).order_by("condition_id", "role_id"):
            JourneyConditionBinding.objects.create(
                condition=condition_map[binding.condition_id],
                role=role_map[binding.role_id],
            )


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
