"""Stage 3.3 Checkpoint 1: read-only journey verification resolution."""
from dataclasses import FrozenInstanceError
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import User
from hybrid import attribution, journey_services, verification
from hybrid.journey_verification import (
    JourneyVerificationResolutionError,
    resolve_journey_verification,
)
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    SimulatorRecordCreation,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def _world(db, seed="resolver", second_step=False):
    programme = Programme.objects.create(
        name=seed, code=seed, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{seed}-course", title="Course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{seed}-module", title="Module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{seed}-lesson", title="Lesson", order=1, theory="<p>Theory</p>",
    )
    steps = []
    count = 2 if second_step else 1
    for index in range(1, count + 1):
        steps.append(PracticalStep.objects.create(
            lesson=lesson, key=f"step-{index}", title=f"Step {index}",
            screen="single-window-overview", order=index,
        ))
    target = steps[-1]
    condition = VerificationCondition.objects.create(
        step=target, kind=VerificationCondition.Kind.SAVED_RECORD,
        record_kind="ucr", required_status="draft",
        expected_fields={"exporter_name": "ACME Trading"}, order=1,
    )
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    for step in steps:
        journey_services.assign_step(journey, step)
    role = journey_services.create_record_role(
        journey, "declaration", "Declaration", "ucr",
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    journey_services.bind_condition(condition, role)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    student = User.objects.create_user(username=f"{seed}-student", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    journey_attempt = journey_services.get_or_create_attempt(enrolment, journey)
    return {
        "version": version, "course": course, "lesson": lesson, "steps": steps,
        "step": target, "condition": condition, "journey": journey, "role": role,
        "student": student, "enrolment": enrolment, "lesson_attempt": lesson_attempt,
        "journey_attempt": journey_attempt,
    }


def _record(world, reference="TEMP-RESOLVE"):
    return UcrDeclaration.objects.create(
        owner=world["student"], temp_no=reference, status="draft",
        exporter_name="ACME Trading", regime="CO",
    )


def _attribute(world, record):
    evidence = SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)
    return attribution.attribute_creation(
        world["journey_attempt"], world["role"], evidence.pk, world["student"],
    )


def _resolve(world, user=None):
    return resolve_journey_verification(
        user or world["student"], world["lesson_attempt"], world["step"],
    )


def _assert_code(world, code, user=None):
    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        _resolve(world, user=user)
    assert excinfo.value.code == code


@pytest.mark.django_db
def test_resolves_the_exact_attributed_record_and_returns_frozen_context(db):
    world = _world(db, "resolver-happy")
    other_match = _record(world, "TEMP-OTHER")
    selected = _record(world, "TEMP-SELECTED")
    association = _attribute(world, selected)

    context = _resolve(world)

    assert context.journey_attempt_id == world["journey_attempt"].pk
    assert len(context.selections) == 1
    selection = context.selection_for(world["condition"])
    assert selection.record_id == selected.pk
    assert selection.record_id != other_match.pk
    assert selection.association_id == association.pk
    with pytest.raises(FrozenInstanceError):
        selection.record_id = other_match.pk
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()


@pytest.mark.django_db
def test_non_journey_step_returns_none_without_affecting_legacy_lessons(db):
    world = _world(db, "resolver-legacy")
    legacy = PracticalStep.objects.create(
        lesson=world["lesson"], key="legacy", title="Legacy", order=2,
    )
    assert resolve_journey_verification(world["student"], world["lesson_attempt"], legacy) is None


@pytest.mark.django_db
def test_cross_student_and_unauthorized_attempts_are_rejected(db):
    world = _world(db, "resolver-owner")
    selected = _record(world)
    association = _attribute(world, selected)
    other = User.objects.create_user(username="resolver-other", password="x")
    other_record = UcrDeclaration.objects.create(owner=other, temp_no="TEMP-OTHER-OWNER", regime="CO")

    JourneyRecordAssociation.objects.filter(pk=association.pk).update(record_id=other_record.pk)
    _assert_code(world, "record_unavailable")
    with pytest.raises(PermissionDenied):
        _resolve(world, user=other)


@pytest.mark.django_db
def test_cross_journey_binding_and_cross_version_enrolment_fail_closed(db):
    world = _world(db, "resolver-scope")
    selected = _record(world)
    _attribute(world, selected)
    other_journey = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["course"],
        code="other-journey", title="Other journey", order=2,
    )
    other_role = JourneyRecordRole.objects.create(
        journey=other_journey, key="other", label="Other", record_kind="ucr", order=1,
    )
    JourneyConditionBinding.objects.filter(condition=world["condition"]).update(role=other_role)
    _assert_code(world, "binding_mismatch")

    JourneyConditionBinding.objects.filter(condition=world["condition"]).update(role=world["role"])
    other_version = ProgrammeVersion.objects.create(
        programme=world["version"].programme, version=2,
    )
    Enrolment.objects.filter(pk=world["enrolment"].pk).update(programme_version=other_version)
    world["lesson_attempt"] = LessonAttempt.objects.select_related("enrolment").get(pk=world["lesson_attempt"].pk)
    _assert_code(world, "programme_mismatch")


@pytest.mark.django_db
def test_missing_binding_or_active_association_fails_closed(db):
    world = _world(db, "resolver-missing")
    selected = _record(world)
    association = _attribute(world, selected)
    JourneyConditionBinding.objects.filter(condition=world["condition"]).delete()
    _assert_code(world, "binding_missing")

    JourneyConditionBinding.objects.create(condition=world["condition"], role=world["role"])
    JourneyRecordAssociation.objects.filter(pk=association.pk).update(
        is_active=False, replaced_at=timezone.now(),
    )
    _assert_code(world, "association_missing")


@pytest.mark.django_db
def test_mismatched_kind_and_missing_simulator_record_fail_closed(db):
    world = _world(db, "resolver-record")
    selected = _record(world)
    association = _attribute(world, selected)
    JourneyRecordAssociation.objects.filter(pk=association.pk).update(record_kind="boe")
    _assert_code(world, "association_mismatch")

    JourneyRecordAssociation.objects.filter(pk=association.pk).update(record_kind="ucr")
    selected.delete()
    _assert_code(world, "record_unavailable")


@pytest.mark.django_db
def test_missing_creation_evidence_fails_closed(db):
    world = _world(db, "resolver-evidence")
    selected = _record(world)
    _attribute(world, selected)
    SimulatorRecordCreation.objects.filter(record_kind="ucr", record_id=selected.pk).delete()
    _assert_code(world, "creation_evidence_missing")


@pytest.mark.django_db
def test_assignment_source_must_match_the_role_creation_mode(db):
    world = _world(db, "resolver-provenance")
    selected = _record(world)
    association = _attribute(world, selected)
    JourneyRecordAssociation.objects.filter(pk=association.pk).update(
        assignment_source=JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    _assert_code(world, "provenance_mismatch")


@pytest.mark.django_db
def test_attempt_start_and_latest_step_opening_are_freshness_floors(db):
    world = _world(db, "resolver-fresh")
    selected = _record(world)
    _attribute(world, selected)
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        started_at=timezone.now() + timedelta(minutes=1),
    )
    world["journey_attempt"].refresh_from_db()
    _assert_code(world, "record_stale")

    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        started_at=selected.created_at - timedelta(minutes=1),
    )
    world["journey_attempt"].refresh_from_db()
    verification.record_open(world["lesson_attempt"], world["step"])
    StepEvent.objects.filter(
        attempt=world["lesson_attempt"], step=world["step"], kind=StepEvent.Kind.OPENED,
    ).update(occurred_at=timezone.now() + timedelta(minutes=1))
    _assert_code(world, "record_stale")


@pytest.mark.django_db
def test_noncurrent_and_progression_blocked_steps_are_unreachable(db):
    world = _world(db, "resolver-reach", second_step=True)
    selected = _record(world)
    _attribute(world, selected)
    _assert_code(world, "step_not_current")

    second_assignment = JourneyStep.objects.get(journey=world["journey"], step=world["step"])
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        current_journey_step=second_assignment,
    )
    world["journey_attempt"].refresh_from_db()
    _assert_code(world, "progression_blocked")


@pytest.mark.django_db
def test_record_dependency_is_enforced_even_if_current_step_is_corrupted_forward(db):
    world = _world(db, "resolver-dependency", second_step=True)
    selected = _record(world)
    _attribute(world, selected)
    first_assignment, second_assignment = JourneyStep.objects.filter(
        journey=world["journey"],
    ).order_by("journey_order")
    verification.record_open(world["lesson_attempt"], world["steps"][0])
    dependency_role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="dependency", label="Dependency",
        record_kind="ucr", creation_mode=JourneyRecordRole.CreationMode.EXISTING, order=2,
    )
    JourneyDependency.objects.create(
        journey=world["journey"], predecessor_step=first_assignment,
        dependent_step=second_assignment,
        dependency_type=JourneyDependency.DependencyType.RECORD_AVAILABLE,
        required_record_role=dependency_role, order=1,
    )
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        current_journey_step=second_assignment,
    )
    world["journey_attempt"].refresh_from_db()
    _assert_code(world, "dependency_blocked")


@pytest.mark.django_db
def test_completed_and_missing_journey_attempts_are_rejected(db):
    world = _world(db, "resolver-status")
    selected = _record(world)
    _attribute(world, selected)
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED,
    )
    _assert_code(world, "attempt_not_in_progress")

    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).delete()
    _assert_code(world, "attempt_missing")
