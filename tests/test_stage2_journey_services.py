"""Stage 2 Checkpoint 3: journey coordination service rules.

Covers canonical ordering and entry points, dependency validation with cycle
detection, attempt lifecycle with version and ownership boundaries, exact
record association with safe replacement, structural readiness, and the
database backstop that keeps concurrent replacements to one active row.
"""
import pytest
from accounts.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from hybrid import journey_services
from hybrid import verification as hybrid_verification
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration

_temp_counter = {"n": 0}


def _ucr(owner):
    _temp_counter["n"] += 1
    return UcrDeclaration.objects.create(
        owner=owner,
        status="draft",
        exporter_name="ACME Trading",
        temp_no=f"TEMPTEST-{_temp_counter['n']}",
    )


@pytest.fixture
def world(db):
    """One hybrid course, one module, three lessons with one step each, plus a
    second course for cross-course checks and two enrolled learners."""
    programme = Programme.objects.create(name="Journey Programme", code="journeys", learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    course = HybridCourse.objects.create(programme_version=version, code="jc", title="Journey Course", order=1)
    module = HybridModule.objects.create(course=course, code="jm", title="Journey Module", order=1)
    lessons, steps = [], []
    for index in range(1, 4):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"jl-{index}", title=f"Journey Lesson {index}", order=index,
        )
        step = PracticalStep.objects.create(lesson=lesson, key=f"js-{index}", title=f"Step {index}", order=1)
        lessons.append(lesson)
        steps.append(step)
    other_course = HybridCourse.objects.create(programme_version=version, code="jc2", title="Other Course", order=2)
    other_module = HybridModule.objects.create(course=other_course, code="jm2", title="Other Module", order=1)
    other_lesson = HybridLesson.objects.create(module=other_module, slug="jl-other", title="Other Lesson", order=1)
    other_step = PracticalStep.objects.create(lesson=other_lesson, key="js-other", title="Other Step", order=1)
    journey = PracticalJourney.objects.create(programme_version=version, course=course, code="j", title="Journey")
    student = User.objects.create_user(username="journey-learner", email="jl@example.test", password="x")
    other = User.objects.create_user(username="other-learner", email="ol@example.test", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    Enrolment.objects.create(student=other, programme_version=version)
    return {
        "version": version, "course": course, "module": module,
        "lessons": lessons, "steps": steps,
        "other_course": other_course, "other_step": other_step,
        "journey": journey, "student": student, "other": other, "enrolment": enrolment,
    }


def _assign_all(world):
    return [journey_services.assign_step(world["journey"], step) for step in world["steps"]]


# --- Structure, canonical ordering, entry points -------------------------------


@pytest.mark.django_db
def test_assignment_follows_the_canonical_curriculum_order(world):
    # Assigned deliberately out of curriculum order; canonical order still wins.
    journey_services.assign_step(world["journey"], world["steps"][2])
    journey_services.assign_step(world["journey"], world["steps"][0])
    journey_services.assign_step(world["journey"], world["steps"][1])

    ordered = journey_services.ordered_assignments(world["journey"])
    assert [a.step.key for a in ordered] == ["js-1", "js-2", "js-3"]
    assert [a.journey_order for a in ordered] == [1, 2, 3]


@pytest.mark.django_db
def test_assign_step_rejects_a_step_from_another_course(world):
    with pytest.raises(ValidationError):
        journey_services.assign_step(world["journey"], world["other_step"])
    assert not JourneyStep.objects.filter(journey=world["journey"]).exists()


@pytest.mark.django_db
def test_assign_step_rejects_a_step_already_assigned_to_a_journey(world):
    journey_services.assign_step(world["journey"], world["steps"][0])
    second_journey = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["course"], code="j-2", title="Second journey", order=2,
    )
    with pytest.raises(ValidationError):
        journey_services.assign_step(second_journey, world["steps"][0])
    assert not JourneyStep.objects.filter(journey=second_journey).exists()


@pytest.mark.django_db
def test_unassign_step_drops_dependencies_and_renumbers(world):
    assignments = _assign_all(world)
    journey = world["journey"]
    journey_services.add_dependency(
        journey, assignments[0], assignments[1],
        JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    journey_services.unassign_step(journey, world["steps"][0])

    assert not JourneyDependency.objects.filter(journey=journey).exists()
    remaining = journey_services.ordered_assignments(journey)
    assert [a.step.key for a in remaining] == ["js-2", "js-3"]
    assert [a.journey_order for a in remaining] == [1, 2]


@pytest.mark.django_db
def test_the_entry_point_is_the_earliest_canonical_step(world):
    # Assigned deliberately out of curriculum order: the entry point is still
    # the earliest step, and forward dependencies never add another one.
    journey_services.assign_step(world["journey"], world["steps"][2])
    journey_services.assign_step(world["journey"], world["steps"][0])
    journey_services.assign_step(world["journey"], world["steps"][1])

    entry = journey_services.entry_point(world["journey"])
    assert entry is not None and entry.step.key == "js-1"

    ordered = journey_services.ordered_assignments(world["journey"])
    journey_services.add_dependency(
        world["journey"], ordered[0], ordered[1], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    journey_services.add_dependency(
        world["journey"], ordered[1], ordered[2], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    assert journey_services.entry_point(world["journey"]).pk == entry.pk


# --- Dependencies: forward-only, same journey, cycles, roles --------------------


@pytest.mark.django_db
def test_add_dependency_enforces_same_journey_and_forward_order(world):
    _assign_all(world)
    journey = world["journey"]
    steps = {step.key: step for step in world["steps"]}

    # A step assigned to a different journey is not a valid edge endpoint.
    second_journey = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["other_course"], code="j-other", title="Other journey",
    )
    foreign_assignment = journey_services.assign_step(second_journey, world["other_step"])

    ordered = journey_services.ordered_assignments(journey)
    with pytest.raises(ValidationError):
        journey_services.add_dependency(
            journey, ordered[0], foreign_assignment, JourneyDependency.DependencyType.STEP_COMPLETED,
        )
    with pytest.raises(ValidationError):
        journey_services.add_dependency(
            journey, ordered[1], ordered[0], JourneyDependency.DependencyType.STEP_COMPLETED,
        )

    assignment = journey_services.add_dependency(
        journey, ordered[0], ordered[1], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    assert assignment.pk is not None


@pytest.mark.django_db
def test_add_dependency_rejects_cycles(world):
    _assign_all(world)
    journey = world["journey"]
    ordered = journey_services.ordered_assignments(journey)

    journey_services.add_dependency(
        journey, ordered[0], ordered[1], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    journey_services.add_dependency(
        journey, ordered[1], ordered[2], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    with pytest.raises(ValidationError):
        journey_services.add_dependency(
            journey, ordered[2], ordered[0], JourneyDependency.DependencyType.STEP_COMPLETED,
        )


@pytest.mark.django_db
def test_record_available_dependency_requires_its_role(world):
    _assign_all(world)
    journey = world["journey"]
    ordered = journey_services.ordered_assignments(journey)
    role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EITHER,
    )

    with pytest.raises(ValidationError):
        journey_services.add_dependency(
            journey, ordered[0], ordered[1], JourneyDependency.DependencyType.RECORD_AVAILABLE,
        )
    dependency = journey_services.add_dependency(
        journey, ordered[0], ordered[1], JourneyDependency.DependencyType.RECORD_AVAILABLE,
        required_record_role=role,
    )
    assert dependency.required_record_role == role
    with pytest.raises(ValidationError):
        journey_services.add_dependency(
            journey, ordered[1], ordered[2], JourneyDependency.DependencyType.STEP_COMPLETED,
            required_record_role=role,
        )


# --- Attempts: creation, retrieval, version match, completion -------------------


@pytest.mark.django_db
def test_get_or_create_attempt_seeds_the_entry_point_and_resumes(world):
    _assign_all(world)
    first = journey_services.get_or_create_attempt(world["enrolment"], world["journey"])
    assert first.current_journey_step.step.key == "js-1"
    assert first.status == JourneyAttempt.Status.IN_PROGRESS

    first.current_journey_step = world["journey"].step_assignments.order_by("journey_order")[1]
    first.save(update_fields=("current_journey_step",))

    resumed = journey_services.get_or_create_attempt(world["enrolment"], world["journey"])
    assert resumed.pk == first.pk
    assert resumed.current_journey_step.step.key == "js-2"


@pytest.mark.django_db
def test_attempt_creation_is_denied_across_versions(world):
    second_version = ProgrammeVersion.objects.create(
        programme=world["version"].programme, version=2,
    )
    enrolment_v2 = Enrolment.objects.create(student=world["student"], programme_version=second_version)
    with pytest.raises(PermissionDenied):
        journey_services.get_or_create_attempt(enrolment_v2, world["journey"])


@pytest.mark.django_db
def test_attempt_retrieval_is_learner_scoped(world):
    _assign_all(world)
    attempt = journey_services.get_or_create_attempt(world["enrolment"], world["journey"])
    assert journey_services.attempt_for_user(world["student"], attempt.pk).pk == attempt.pk
    with pytest.raises(PermissionDenied):
        journey_services.attempt_for_user(world["other"], attempt.pk)


@pytest.mark.django_db
def test_completion_requires_evidence_roles_and_lessons(world):
    """Journey completion reads durable step evidence directly: lesson
    completion flags alone never certify it, and every required record role
    must be satisfied. Optional roles never block."""
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    required_role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", required=True, order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    JourneyRecordRole.objects.create(
        journey=journey, key="note", label="Optional note", record_kind="boe", required=False, order=2,
    )

    # Lesson completion flags alone: no durable step evidence exists yet.
    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=attempt.enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    state = journey_services.journey_completion_state(attempt)
    assert (state["steps_satisfied"], state["steps_total"]) == (0, 3)
    assert (state["roles_satisfied"], state["roles_required"]) == (0, 1)
    assert journey_services.refresh_journey_completion(attempt) is False

    # The engine's evidence path (durable StepEvent stamps on this enrolment's
    # LessonAttempt) satisfies the steps one at a time.
    for lesson_attempt, step in zip(lesson_attempts, world["steps"]):
        hybrid_verification.record_open(lesson_attempt, step)
        hybrid_verification.mark_verified(lesson_attempt, step)

    # Steps verified but the required record role still unsatisfied: the
    # journey stays incomplete until the exact record is assigned.
    assert journey_services.refresh_journey_completion(attempt) is False
    record = _ucr(world["student"])
    journey_services.assign_record(
        attempt, required_role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    state = journey_services.journey_completion_state(attempt)
    assert state["steps_satisfied"] == 3
    assert journey_services.refresh_journey_completion(attempt) is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None
    assert attempt.status == JourneyAttempt.Status.COMPLETED

    # The optional role never blocked completion.
    assert JourneyRecordRole.objects.filter(key="note").exists()


# --- Record associations: ownership, replacement with history, satisfaction ----


@pytest.mark.django_db
def test_assign_record_validates_role_and_ownership(world):
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EITHER,
    )
    other_role = JourneyRecordRole.objects.create(
        journey=journey, key="boe", label="BOE", record_kind="boe", order=2,
    )

    with pytest.raises(ValidationError):
        journey_services.assign_record(attempt, role, 999999, JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY)

    foreign_record = _ucr(world["other"])
    with pytest.raises(PermissionDenied):
        journey_services.assign_record(attempt, role, foreign_record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING)
    with pytest.raises(ValidationError):
        journey_services.assign_record(attempt, other_role, 1, JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY)


@pytest.mark.django_db
def test_replacement_preserves_history_and_keeps_one_active(world):
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EITHER,
    )
    first_record = _ucr(world["student"])
    second_record = _ucr(world["student"])

    # AUTHORIZED_EXISTING keeps the test focused on replacement/backstop
    # mechanics; created-in-journey claims are minted only by the Stage 3.2
    # attribution service.
    first = journey_services.assign_record(
        attempt, role, first_record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    second = journey_services.assign_record(
        attempt, role, second_record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    first.refresh_from_db()
    assert first.is_active is False and first.replaced_at is not None
    assert first.assignment_source == JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING
    assert second.is_active is True and second.replaced_at is None
    assert journey_services.active_record(attempt, role).pk == second.pk
    # History is preserved: both rows remain.
    assert JourneyRecordAssociation.objects.filter(journey_attempt=attempt, role=role).count() == 2


@pytest.mark.django_db
def test_the_database_backstop_blocks_two_active_associations(world):
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EITHER,
    )
    record = _ucr(world["student"])
    journey_services.assign_record(
        attempt, role, record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyRecordAssociation.objects.create(
                journey_attempt=attempt, role=role, enrolment=attempt.enrolment,
                programme_version=attempt.journey.programme_version,
                record_kind="ucr", record_id=record.pk,
                assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
                is_active=True,
            )


@pytest.mark.django_db
def test_role_satisfaction_follows_the_record_world(world):
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )

    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is False and "No record" in message

    record = _ucr(world["student"])
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is True

    record.delete()
    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is False and "no longer exists" in message


@pytest.mark.django_db
def test_an_incomplete_mandatory_step_blocks_journey_completion_despite_a_completed_lesson(world):
    """A completed LessonAttempt flag must not certify an unverified mandatory
    practical step: the journey attempt stays incomplete until the step's own
    authoritative verification evidence exists. Recorded at Checkpoint 3
    acceptance; enforceable since the Checkpoint 5 step-evidence gate."""
    _assign_all(world)
    journey = world["journey"]
    attempt = journey_services.get_or_create_attempt(world["enrolment"], journey)
    required_role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr", label="Primary UCR", record_kind="ucr", required=True, order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    record = _ucr(world["student"])
    journey_services.assign_record(
        attempt, required_role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=attempt.enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    # Lesson completion flags alone: the journey stays incomplete because the
    # mandatory steps carry no durable verification evidence.
    assert journey_services.refresh_journey_completion(attempt) is False
    attempt.refresh_from_db()
    assert attempt.completed_at is None

    # The workspace's evidence path (StepEvent OPENED stamps on the lessons'
    # LessonAttempts) unlocks completion.
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)
    assert journey_services.refresh_journey_completion(attempt) is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None
    assert attempt.status == JourneyAttempt.Status.COMPLETED


# --- Structural readiness -------------------------------------------------------


@pytest.mark.django_db
def test_structural_issues_report_incomplete_and_broken_journeys(world):
    journey = world["journey"]
    assert any("No practical steps" in issue for issue in journey_services.structural_issues(journey))

    assignments = _assign_all(world)
    journey_services.add_dependency(
        journey, assignments[0], assignments[1],
        JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    # A cross-course assignment and a wrong-order dependency, written directly
    # to the ORM the way something bypassing the service would leave them.
    rogue = JourneyStep.objects.create(
        journey=journey, step=world["other_step"], journey_order=9,
    )
    JourneyDependency.objects.create(
        journey=journey, predecessor_step=world["journey"].step_assignments.get(step=world["steps"][2]),
        dependent_step=world["journey"].step_assignments.get(step=world["steps"][0]),
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED, order=2,
    )

    issues = journey_services.structural_issues(journey)
    assert any("another course" in issue for issue in issues)
    assert any("does not follow the journey order" in issue for issue in issues)

    rogue.delete()
    JourneyDependency.objects.filter(order=2).delete()
    # A full cycle among the three steps removes every entry point: 1 -> 2 -> 3 -> 1.
    ordered = journey_services.ordered_assignments(journey)
    JourneyDependency.objects.create(
        journey=journey, predecessor_step=ordered[1], dependent_step=ordered[2],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED, order=2,
    )
    JourneyDependency.objects.create(
        journey=journey, predecessor_step=ordered[2], dependent_step=ordered[0],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED, order=3,
    )
    issues = journey_services.structural_issues(journey)
    assert any("cycle" in issue for issue in issues)


# --- Draft-only structure mutation guards ---------------------------------------


@pytest.mark.django_db
def test_structure_mutations_are_refused_outside_draft_editions(world):
    assignments = _assign_all(world)
    journey = world["journey"]
    fingerprint = [(a.pk, a.journey_order) for a in assignments]
    dependency_count = JourneyDependency.objects.filter(journey=journey).count()

    for status in (ProgrammeVersion.Status.PUBLISHED, ProgrammeVersion.Status.RETIRED):
        ProgrammeVersion.objects.filter(pk=world["version"].pk).update(status=status)
        frozen_journey = PracticalJourney.objects.get(pk=journey.pk)

        with pytest.raises(PermissionDenied):
            journey_services.assign_step(frozen_journey, world["other_step"])
        with pytest.raises(PermissionDenied):
            journey_services.unassign_step(frozen_journey, world["steps"][0])
        with pytest.raises(PermissionDenied):
            journey_services.add_dependency(
                frozen_journey, assignments[0], assignments[1],
                JourneyDependency.DependencyType.STEP_COMPLETED,
            )

    assert [(a.pk, a.journey_order) for a in journey_services.ordered_assignments(journey)] == fingerprint
    assert JourneyDependency.objects.filter(journey=journey).count() == dependency_count
    assert JourneyStep.objects.filter(journey=journey).count() == len(assignments)
