"""Checkpoint 3.3.2: schema and read-only journey verification primitives."""
import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import journey_evidence, journey_services, verification
from hybrid.journey_evidence import CurrentVerification, NotCurrent
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    JourneyVerificationEvidence,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def _world(db, seed="evidence", *, conditions=("saved",), other_step_condition=False):
    programme = Programme.objects.create(name=seed, code=seed, learning_track=Programme.Track.HYBRID)
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
    first = PracticalStep.objects.create(
        lesson=lesson, key="step-1", title="Step 1", screen="single-window-overview", order=1,
    )
    target = PracticalStep.objects.create(
        lesson=lesson, key="step-2", title="Step 2", screen="single-window-overview", order=2,
    )

    saved = []
    for index, kind in enumerate(conditions, start=1):
        if kind == "saved":
            saved.append(VerificationCondition.objects.create(
                step=target,
                kind=VerificationCondition.Kind.SAVED_RECORD,
                record_kind="ucr",
                required_status="draft",
                expected_fields={"exporter_name": "ACME Trading"},
                order=index,
            ))
        else:
            VerificationCondition.objects.create(
                step=target, kind=VerificationCondition.Kind.SCREEN_OPENED, order=index,
            )
    other_condition = None
    if other_step_condition:
        other_condition = VerificationCondition.objects.create(
            step=first,
            kind=VerificationCondition.Kind.SAVED_RECORD,
            record_kind="ucr",
            required_status="draft",
            expected_fields={"exporter_name": "ACME Trading"},
            order=1,
        )

    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    for step in (first, target):
        journey_services.assign_step(journey, step)
    role = journey_services.create_record_role(
        journey, "declaration", "Declaration", "ucr",
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    for condition in saved:
        journey_services.bind_condition(condition, role)
    if other_condition is not None:
        journey_services.bind_condition(other_condition, role)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))

    student = User.objects.create_user(username=f"{seed}-student", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    journey_attempt = journey_services.get_or_create_attempt(enrolment, journey)
    journey_attempt.current_journey_step = JourneyStep.objects.get(journey=journey, step=target)
    journey_attempt.save(update_fields=("current_journey_step",))

    record = UcrDeclaration.objects.create(
        owner=student, temp_no=f"{seed}-ucr", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    association = journey_services.assign_record(
        journey_attempt, role, record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    opening = StepEvent.objects.create(
        attempt=lesson_attempt, step=target, kind=StepEvent.Kind.OPENED,
        occurred_at=timezone.now(), generation=uuid.uuid4(),
    )
    return {
        "student": student,
        "enrolment": enrolment,
        "lesson": lesson,
        "lesson_attempt": lesson_attempt,
        "journey": journey,
        "journey_attempt": journey_attempt,
        "assignment": JourneyStep.objects.get(journey=journey, step=target),
        "other_assignment": JourneyStep.objects.get(journey=journey, step=first),
        "step": target,
        "first_step": first,
        "conditions": list(target.conditions.order_by("order", "id")),
        "saved": saved,
        "other_condition": other_condition,
        "role": role,
        "record": record,
        "association": association,
        "opening": opening,
    }


def _evidence(world, condition, **overrides):
    values = {
        "journey_attempt": world["journey_attempt"],
        "lesson_attempt": world["lesson_attempt"],
        "journey_step": world["assignment"],
        "condition": condition,
        "condition_fingerprint": journey_evidence.condition_fingerprint(condition),
        "role": world["role"],
        "association": world["association"],
        "record_kind": world["association"].record_kind,
        "record_id": world["association"].record_id,
        "opening_generation": world["opening"].generation,
        "opening_occurred_at": world["opening"].occurred_at,
        "verified_at": timezone.now(),
    }
    values.update(overrides)
    return JourneyVerificationEvidence.objects.create(**values)


def _check(world, user=None):
    return journey_evidence.current_verification(
        user or world["student"], world["lesson_attempt"], world["step"],
    )


def _assert_not_current(world, reason):
    result = _check(world)
    assert isinstance(result, NotCurrent)
    assert result.reason == reason


# --- Condition shapes ---------------------------------------------------------


@pytest.mark.django_db
def test_a_single_saved_condition_is_current_when_its_evidence_still_matches(db):
    world = _world(db, "single")
    condition = world["saved"][0]
    evidence = _evidence(world, condition)

    result = _check(world)

    assert isinstance(result, CurrentVerification)
    assert result.journey_attempt_id == world["journey_attempt"].pk
    assert result.journey_step_id == world["assignment"].pk
    assert result.opening_generation == world["opening"].generation
    assert result.opening_occurred_at == world["opening"].occurred_at
    assert result.condition_ids == (condition.pk,)
    assert result.evidence_ids == (evidence.pk,)
    assert result.verified_at == evidence.verified_at


@pytest.mark.django_db
def test_every_saved_condition_needs_its_own_evidence(db):
    world = _world(db, "two-saved", conditions=("saved", "saved"))
    first, second = world["saved"]
    _evidence(world, first)
    _assert_not_current(world, "evidence_missing")

    _evidence(world, second)
    result = _check(world)
    assert isinstance(result, CurrentVerification)
    assert set(result.condition_ids) == {first.pk, second.pk}
    assert len(result.evidence_ids) == 2


@pytest.mark.django_db
def test_a_screen_opened_only_step_is_satisfied_by_its_opening_generation(db):
    world = _world(db, "screen-only", conditions=("screen",))

    result = _check(world)

    assert isinstance(result, CurrentVerification)
    assert result.evidence_ids == ()
    assert result.condition_ids == (world["conditions"][0].pk,)
    assert result.opening_generation == world["opening"].generation


@pytest.mark.django_db
def test_a_mixed_step_still_requires_its_saved_record_evidence(db):
    world = _world(db, "mixed", conditions=("screen", "saved"))
    assert _check(world).reason == "evidence_missing"

    saved = world["saved"][0]
    evidence = _evidence(world, saved)
    result = _check(world)

    assert isinstance(result, CurrentVerification)
    assert result.evidence_ids == (evidence.pk,)
    assert set(result.condition_ids) == {condition.pk for condition in world["conditions"]}


@pytest.mark.django_db
def test_a_step_with_no_conditions_is_never_current(db):
    world = _world(db, "no-conditions", conditions=())

    _assert_not_current(world, "no_conditions")


# --- Opening generation -------------------------------------------------------


@pytest.mark.django_db
def test_a_step_without_an_opening_row_is_not_current(db):
    world = _world(db, "no-opening")
    _evidence(world, world["saved"][0])
    world["opening"].delete()

    _assert_not_current(world, "opening_missing")


@pytest.mark.django_db
def test_an_opening_without_a_generation_cannot_back_evidence(db):
    world = _world(db, "legacy-opening")
    _evidence(world, world["saved"][0])
    StepEvent.objects.filter(pk=world["opening"].pk).update(generation=None)

    _assert_not_current(world, "opening_missing_generation")


@pytest.mark.django_db
def test_evidence_from_an_earlier_opening_is_stale(db):
    world = _world(db, "stale-generation")
    _evidence(world, world["saved"][0], opening_generation=uuid.uuid4())

    _assert_not_current(world, "evidence_stale")


# --- Evidence integrity -------------------------------------------------------


@pytest.mark.django_db
def test_missing_evidence_is_not_current(db):
    world = _world(db, "missing")

    _assert_not_current(world, "evidence_missing")


@pytest.mark.django_db
def test_evidence_for_an_edited_condition_is_outdated(db):
    world = _world(db, "edited-condition")
    condition = world["saved"][0]
    _evidence(world, condition)
    VerificationCondition.objects.filter(pk=condition.pk).update(
        expected_fields={"exporter_name": "Someone Else"},
    )

    _assert_not_current(world, "evidence_outdated")


@pytest.mark.django_db
def test_evidence_naming_a_superseded_record_is_conflicted(db):
    world = _world(db, "superseded")
    _evidence(world, world["saved"][0])
    second_record = UcrDeclaration.objects.create(
        owner=world["student"], temp_no="TEMP-SUPERSEDE", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    replacement = journey_services.assign_record(
        world["journey_attempt"], world["role"], second_record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    assert replacement.pk != world["association"].pk
    assert journey_services.active_record(world["journey_attempt"], world["role"]).pk == replacement.pk

    _assert_not_current(world, "evidence_conflicted")


@pytest.mark.django_db
def test_evidence_for_a_condition_outside_the_step_is_unexpected(db):
    world = _world(db, "unexpected", other_step_condition=True)
    _evidence(world, world["other_condition"])

    _assert_not_current(world, "evidence_unexpected")


@pytest.mark.django_db
def test_evidence_for_a_screen_condition_is_unexpected(db):
    world = _world(db, "unexpected-screen", conditions=("screen",))
    _evidence(world, world["conditions"][0])

    _assert_not_current(world, "evidence_unexpected")


@pytest.mark.django_db
def test_evidence_for_another_journey_attempt_is_conflicted(db):
    world = _world(db, "foreign-attempt")
    other_journey = PracticalJourney.objects.create(
        programme_version=world["enrolment"].programme_version,
        course=world["journey"].course,
        code="second-journey-for-foreign-attempt",
        title="Other journey",
        order=2,
    )
    other_attempt = journey_services.get_or_create_attempt(world["enrolment"], other_journey)
    _evidence(world, world["saved"][0], journey_attempt=other_attempt)

    _assert_not_current(world, "evidence_conflicted")


@pytest.mark.django_db
def test_evidence_naming_the_wrong_role_is_conflicted(db):
    world = _world(db, "wrong-role")
    other_role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="second-declaration", label="Second declaration",
        record_kind="ucr", order=2,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    _evidence(world, world["saved"][0], role=other_role)

    _assert_not_current(world, "evidence_conflicted")


@pytest.mark.django_db
def test_evidence_with_a_different_frozen_record_identity_is_conflicted(db):
    world = _world(db, "frozen-record")
    _evidence(world, world["saved"][0], record_id=world["association"].record_id + 1)

    _assert_not_current(world, "evidence_conflicted")


@pytest.mark.django_db
def test_conflicting_opening_timestamps_cannot_be_recorded(db):
    """The frozen opening timestamp is not part of the identity, so a second
    row for the same identity with a different timestamp is a duplicate the
    database refuses outright. The predicate never has to arbitrate between
    two timestamps for one identity."""
    world = _world(db, "conflicting-timestamps")
    condition = world["saved"][0]
    evidence = _evidence(world, condition)

    with pytest.raises(IntegrityError), transaction.atomic():
        _evidence(
            world,
            condition,
            opening_occurred_at=world["opening"].occurred_at - timedelta(seconds=1),
        )

    assert JourneyVerificationEvidence.objects.filter(condition=condition).count() == 1
    result = _check(world)
    assert isinstance(result, CurrentVerification)
    assert result.evidence_ids == (evidence.pk,)


@pytest.mark.django_db
def test_the_same_success_cannot_be_recorded_twice(db):
    world = _world(db, "identity")
    condition = world["saved"][0]
    _evidence(world, condition)

    with pytest.raises(IntegrityError), transaction.atomic():
        _evidence(world, condition)


@pytest.mark.django_db
def test_evidence_rows_are_append_only(db):
    world = _world(db, "append-only")
    evidence = _evidence(world, world["saved"][0])
    evidence.record_id += 1

    with pytest.raises(ValidationError):
        evidence.save()


# --- Bindings, associations and records ---------------------------------------


@pytest.mark.django_db
def test_a_binding_outside_the_journey_is_rejected(db):
    world = _world(db, "foreign-binding")
    _evidence(world, world["saved"][0])
    other_journey = PracticalJourney.objects.create(
        programme_version=world["enrolment"].programme_version,
        course=world["journey"].course,
        code="other-journey",
        title="Other journey",
        order=2,
    )
    foreign_role = JourneyRecordRole.objects.create(
        journey=other_journey, key="declaration", label="Declaration",
        record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    JourneyConditionBinding.objects.filter(condition=world["saved"][0]).update(role=foreign_role)

    _assert_not_current(world, "binding_mismatch")


@pytest.mark.django_db
def test_a_role_using_a_different_record_kind_is_rejected(db):
    world = _world(db, "kind-mismatch")
    _evidence(world, world["saved"][0])
    JourneyRecordRole.objects.filter(pk=world["role"].pk).update(record_kind="boe")

    _assert_not_current(world, "record_kind_mismatch")


@pytest.mark.django_db
def test_a_step_whose_role_has_no_active_record_is_not_current(db):
    world = _world(db, "no-association")
    _evidence(world, world["saved"][0])
    JourneyRecordAssociation.objects.filter(pk=world["association"].pk).update(
        is_active=False, replaced_at=timezone.now(),
    )

    _assert_not_current(world, "association_missing")


@pytest.mark.django_db
def test_a_deleted_record_is_unavailable(db):
    world = _world(db, "deleted-record")
    _evidence(world, world["saved"][0])
    world["record"].delete()

    _assert_not_current(world, "record_unavailable")


@pytest.mark.django_db
def test_a_record_owned_by_another_learner_is_unavailable(db):
    world = _world(db, "foreign-record")
    _evidence(world, world["saved"][0])
    intruder = User.objects.create_user(username="foreign-record-owner", password="x")
    UcrDeclaration.objects.filter(pk=world["record"].pk).update(owner=intruder)

    _assert_not_current(world, "record_unavailable")


@pytest.mark.django_db
def test_a_learner_without_a_journey_attempt_is_not_current(db):
    world = _world(db, "no-attempt")
    _evidence(world, world["saved"][0])
    # The association protects the attempt, and the evidence protects the
    # association, so an attempt can only disappear once its evidence does.
    JourneyVerificationEvidence.objects.filter(journey_attempt=world["journey_attempt"]).delete()
    JourneyRecordAssociation.objects.filter(pk=world["association"].pk).delete()
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).delete()

    _assert_not_current(world, "attempt_missing")


# --- Boundaries ---------------------------------------------------------------


@pytest.mark.django_db
def test_another_learners_lesson_attempt_is_denied(db):
    world = _world(db, "intruder")
    intruder = User.objects.create_user(username="intruder-attempt", password="x")

    with pytest.raises(PermissionDenied):
        journey_evidence.current_verification(intruder, world["lesson_attempt"], world["step"])


@pytest.mark.django_db
def test_a_legacy_step_is_not_a_journey_step(db):
    world = _world(db, "legacy")
    legacy_step = PracticalStep.objects.create(
        lesson=world["lesson"], key="legacy", title="Legacy",
        screen="single-window-overview", order=3,
    )

    result = journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], legacy_step,
    )

    assert isinstance(result, NotCurrent)
    assert result.reason == "not_journey_step"


@pytest.mark.django_db
def test_the_legacy_verifier_still_works_beside_the_new_schema(db):
    world = _world(db, "legacy-verifier")
    legacy_step = PracticalStep.objects.create(
        lesson=world["lesson"], key="legacy", title="Legacy",
        screen="single-window-overview", order=3,
    )
    VerificationCondition.objects.create(
        step=legacy_step, kind=VerificationCondition.Kind.SCREEN_OPENED, order=1,
    )
    verification.record_open(world["lesson_attempt"], legacy_step)

    result = verification.verify_step(world["lesson_attempt"], legacy_step)

    assert result["passed"] is True
    assert StepEvent.objects.filter(
        attempt=world["lesson_attempt"], step=legacy_step, kind=StepEvent.Kind.VERIFIED,
    ).exists()


@pytest.mark.django_db
def test_a_completed_journey_keeps_readable_history_and_current_state(db):
    world = _world(db, "completed")
    evidence = _evidence(world, world["saved"][0])
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED, completed_at=timezone.now(),
    )
    LessonAttempt.objects.filter(pk=world["lesson_attempt"].pk).update(completed_at=timezone.now())

    history = journey_evidence.verification_history(world["lesson_attempt"], world["step"])
    result = _check(world)

    assert [row.pk for row in history] == [evidence.pk]
    assert isinstance(result, CurrentVerification)


@pytest.mark.django_db
def test_the_predicates_write_nothing(db):
    world = _world(db, "no-writes")
    _evidence(world, world["saved"][0])
    before = (StepEvent.objects.count(), JourneyVerificationEvidence.objects.count())

    _check(world)
    journey_evidence.verification_history(world["lesson_attempt"], world["step"])

    assert (StepEvent.objects.count(), JourneyVerificationEvidence.objects.count()) == before


# --- Schema -------------------------------------------------------------------


@pytest.mark.django_db
def test_a_step_has_at_most_one_opening_row(db):
    world = _world(db, "opened-singleton")

    with pytest.raises(IntegrityError), transaction.atomic():
        StepEvent.objects.create(
            attempt=world["lesson_attempt"], step=world["step"],
            kind=StepEvent.Kind.OPENED, generation=uuid.uuid4(),
        )


def test_the_condition_fingerprint_is_canonical():
    condition = VerificationCondition(
        kind=VerificationCondition.Kind.SAVED_RECORD,
        record_kind="ucr",
        required_status="draft",
        expected_fields={"exporter_name": "ACME Trading", "regime": "CO"},
        order=1,
    )
    baseline = journey_evidence.condition_fingerprint(condition)

    condition.expected_fields = {"regime": "CO", "exporter_name": "ACME Trading"}
    condition.order = 7
    assert journey_evidence.condition_fingerprint(condition) == baseline

    condition.expected_fields = {"exporter_name": "Someone Else", "regime": "CO"}
    assert journey_evidence.condition_fingerprint(condition) != baseline
    assert len(baseline) == 64
    assert baseline == baseline.lower()


# --- Deletion protection ------------------------------------------------------


@pytest.mark.django_db
def test_a_lesson_attempt_with_evidence_cannot_be_deleted(db):
    world = _world(db, "protected-attempt")
    evidence = _evidence(world, world["saved"][0])
    lesson_attempt_id = world["lesson_attempt"].pk

    with pytest.raises(ProtectedError), transaction.atomic():
        world["lesson_attempt"].delete()

    assert LessonAttempt.objects.filter(pk=lesson_attempt_id).exists()
    assert JourneyVerificationEvidence.objects.filter(pk=evidence.pk).exists()


@pytest.mark.django_db
def test_a_lesson_attempt_without_evidence_still_deletes(db):
    world = _world(db, "deletable-attempt")
    lesson_attempt_id = world["lesson_attempt"].pk

    world["lesson_attempt"].delete()

    assert not LessonAttempt.objects.filter(pk=lesson_attempt_id).exists()


@pytest.mark.django_db
def test_the_admin_refuses_to_delete_an_attempt_with_evidence(db, client):
    world = _world(db, "admin-delete")
    evidence = _evidence(world, world["saved"][0])
    administrator = User.objects.create_superuser(
        username="admin-delete-operator",
        email="admin-delete@example.test",
        password="admin-password",
    )
    client.force_login(administrator)

    response = client.post(
        reverse("admin:hybrid_lessonattempt_delete", args=(world["lesson_attempt"].pk,)),
        {"post": "yes"},
    )

    assert response.status_code == 200
    assert LessonAttempt.objects.filter(pk=world["lesson_attempt"].pk).exists()
    assert JourneyVerificationEvidence.objects.filter(pk=evidence.pk).exists()
