"""Stage 3.3 Checkpoint 2D.2A: provenance and exact-record evaluation foundation.

The resolver, the locked revalidation and the evaluator are read-only. These
tests prove the shared provenance rule, the exact-record boundary (no
owner-wide fallback), lock-aware revalidation of journey state, and that
nothing here writes evidence or verifies a step.
"""
import uuid
from dataclasses import replace
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import User
from hybrid import attribution, journey_evidence, journey_services
from hybrid.journey_evidence import NotCurrent
from hybrid.journey_verification import (
    JourneyVerificationResolutionError,
    evaluate_exact_condition,
    revalidate_journey_verification,
    resolve_journey_verification,
)
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
    SimulatorRecordCreation,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


NEW = JourneyRecordRole.CreationMode.NEW
EXISTING = JourneyRecordRole.CreationMode.EXISTING


def _world(db, seed, *, conditions=("saved",), creation_mode=EXISTING, two_steps=False):
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
    first_step = None
    if two_steps:
        first_step = PracticalStep.objects.create(
            lesson=lesson, key="step-1", title="Step 1", screen="single-window-overview", order=1,
        )
    target = PracticalStep.objects.create(
        lesson=lesson,
        key="step-2" if two_steps else "step-1",
        title="Step 2" if two_steps else "Step 1",
        screen="single-window-overview",
        order=2 if two_steps else 1,
    )

    conditions_list = []
    saved = []
    for index, kind in enumerate(conditions, start=1):
        if kind == "saved":
            condition = VerificationCondition.objects.create(
                step=target,
                kind=VerificationCondition.Kind.SAVED_RECORD,
                record_kind="ucr",
                required_status="draft",
                expected_fields={"exporter_name": "ACME Trading"},
                order=index,
            )
            saved.append(condition)
        else:
            condition = VerificationCondition.objects.create(
                step=target, kind=VerificationCondition.Kind.SCREEN_OPENED, order=index,
            )
        conditions_list.append(condition)

    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    for step in ([first_step] if first_step is not None else []) + [target]:
        journey_services.assign_step(journey, step)
    role = journey_services.create_record_role(
        journey, "declaration", "Declaration", "ucr", creation_mode=creation_mode,
    )
    for condition in saved:
        journey_services.bind_condition(condition, role)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))

    student = User.objects.create_user(username=f"{seed}-student", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    journey_attempt = journey_services.get_or_create_attempt(enrolment, journey)
    assignment = JourneyStep.objects.get(journey=journey, step=target)
    journey_attempt.current_journey_step = assignment
    journey_attempt.save(update_fields=("current_journey_step",))

    opening = StepEvent.objects.create(
        attempt=lesson_attempt,
        step=target,
        kind=StepEvent.Kind.OPENED,
        occurred_at=timezone.now(),
        generation=uuid.uuid4(),
    )
    record = UcrDeclaration.objects.create(
        owner=student, temp_no=f"{seed}-ucr", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    if creation_mode == EXISTING:
        ledger = None
        association = journey_services.assign_record(
            journey_attempt, role, record.pk,
            JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
        )
    else:
        ledger = SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)
        association = attribution.attribute_creation(
            journey_attempt, role, ledger.pk, student,
        )

    return {
        "version": version,
        "course": course,
        "lesson": lesson,
        "first_step": first_step,
        "step": target,
        "conditions": conditions_list,
        "saved": saved,
        "journey": journey,
        "role": role,
        "student": student,
        "enrolment": enrolment,
        "lesson_attempt": lesson_attempt,
        "journey_attempt": journey_attempt,
        "assignment": assignment,
        "opening": opening,
        "record": record,
        "ledger": ledger,
        "association": association,
    }


def _revalidate(world, user=None):
    return revalidate_journey_verification(
        user or world["student"], world["lesson_attempt"], world["step"],
    )


def _assert_code(world, code, user=None):
    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        _revalidate(world, user=user)
    assert excinfo.value.code == code
    return excinfo.value


def _not_current_reason(world):
    result = journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], world["step"],
    )
    assert isinstance(result, NotCurrent)
    return result.reason


def _historical_evidence(world):
    condition = world["saved"][0]
    return JourneyVerificationEvidence.objects.create(
        journey_attempt=world["journey_attempt"],
        lesson_attempt=world["lesson_attempt"],
        journey_step=world["assignment"],
        condition=condition,
        condition_fingerprint=journey_evidence.condition_fingerprint(condition),
        role=world["role"],
        association=world["association"],
        record_kind=world["association"].record_kind,
        record_id=world["association"].record_id,
        opening_generation=world["opening"].generation,
        opening_occurred_at=world["opening"].occurred_at,
        verified_at=timezone.now(),
    )


def _evaluate(world, condition, locked=None):
    locked = locked or _revalidate(world)
    return evaluate_exact_condition(
        condition,
        opening=world["opening"],
        selection=locked.context.selection_for(condition),
        record=locked.record_for(condition),
    )


# --- Valid provenance ---------------------------------------------------------


@pytest.mark.django_db
def test_an_authorized_existing_record_resolves_exactly(db):
    world = _world(db, "check-existing", creation_mode=EXISTING)
    decoy = UcrDeclaration.objects.create(
        owner=world["student"], temp_no="check-existing-decoy", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )

    locked = _revalidate(world)
    selection = locked.context.selection_for(world["saved"][0])

    assert selection.record_id == world["record"].pk
    assert selection.record_id != decoy.pk
    assert locked.record_for(world["saved"][0]).pk == world["record"].pk
    assert locked.opening_generation == world["opening"].generation
    assert _evaluate(world, world["saved"][0], locked).passed is True
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()


@pytest.mark.django_db
def test_a_created_in_journey_record_resolves_through_its_ledger(db):
    world = _world(db, "check-created", creation_mode=NEW)

    locked = _revalidate(world)
    selection = locked.context.selection_for(world["saved"][0])

    assert selection.record_id == world["record"].pk
    assert world["ledger"].record_id == selection.record_id
    assert locked.record_for(world["saved"][0]).pk == world["record"].pk
    assert _evaluate(world, world["saved"][0], locked).passed is True


# --- Broken provenance --------------------------------------------------------


@pytest.mark.django_db
def test_created_in_journey_provenance_requires_the_ledger_row(db):
    world = _world(db, "check-no-ledger", creation_mode=NEW)
    SimulatorRecordCreation.objects.filter(pk=world["ledger"].pk).delete()

    _assert_code(world, "creation_evidence_missing")
    assert _not_current_reason(world) == "creation_evidence_missing"


@pytest.mark.django_db
def test_a_creation_that_predates_the_journey_is_refused(db):
    world = _world(db, "check-pre-start", creation_mode=NEW)
    SimulatorRecordCreation.objects.filter(pk=world["ledger"].pk).update(
        record_created_at=world["journey_attempt"].started_at - timedelta(minutes=1),
    )

    _assert_code(world, "record_predates_journey")
    assert _not_current_reason(world) == "record_predates_journey"


@pytest.mark.django_db
def test_assignment_source_must_match_the_creation_mode(db):
    existing = _world(db, "check-source-existing", creation_mode=EXISTING)
    JourneyRecordAssociation.objects.filter(pk=existing["association"].pk).update(
        assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    )
    _assert_code(existing, "provenance_mismatch")
    assert _not_current_reason(existing) == "provenance_mismatch"

    created = _world(db, "check-source-created", creation_mode=NEW)
    JourneyRecordAssociation.objects.filter(pk=created["association"].pk).update(
        assignment_source=JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    _assert_code(created, "provenance_mismatch")
    assert _not_current_reason(created) == "provenance_mismatch"


@pytest.mark.django_db
def test_a_record_owned_by_another_learner_is_refused(db):
    world = _world(db, "check-owner")
    intruder = User.objects.create_user(username="check-owner-intruder", password="x")
    UcrDeclaration.objects.filter(pk=world["record"].pk).update(owner=intruder)

    _assert_code(world, "record_unavailable")
    assert _not_current_reason(world) == "record_unavailable"


@pytest.mark.django_db
def test_an_association_with_the_wrong_record_kind_is_refused(db):
    world = _world(db, "check-kind")
    JourneyRecordAssociation.objects.filter(pk=world["association"].pk).update(
        record_kind="boe",
    )

    _assert_code(world, "association_mismatch")
    assert _not_current_reason(world) == "association_mismatch"


@pytest.mark.django_db
def test_a_created_in_journey_claim_must_name_the_ledgered_record(db):
    world = _world(db, "check-identity", creation_mode=NEW)
    other = UcrDeclaration.objects.create(
        owner=world["student"], temp_no="check-identity-other", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    # The ledger row is the exact-identity proof: moving it to another record
    # leaves the association's record without creation evidence.
    SimulatorRecordCreation.objects.filter(record_kind="ucr", record_id=other.pk).delete()
    SimulatorRecordCreation.objects.filter(pk=world["ledger"].pk).update(
        record_id=other.pk,
    )

    _assert_code(world, "creation_evidence_missing")


@pytest.mark.django_db
def test_only_the_active_association_is_ever_used(db):
    world = _world(db, "check-replaced")
    replacement_record = UcrDeclaration.objects.create(
        owner=world["student"], temp_no="check-replaced-new", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    replacement = journey_services.assign_record(
        world["journey_attempt"], world["role"], replacement_record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    locked = _revalidate(world)
    selection = locked.context.selection_for(world["saved"][0])

    assert selection.association_id == replacement.pk
    assert selection.record_id == replacement_record.pk
    assert world["association"].pk != replacement.pk

    JourneyRecordAssociation.objects.filter(pk=replacement.pk).update(
        is_active=False, replaced_at=timezone.now(),
    )
    _assert_code(world, "association_missing")
    assert _not_current_reason(world) == "association_missing"


# --- Journey state ------------------------------------------------------------


@pytest.mark.django_db
def test_a_journey_outside_the_enrolment_version_is_refused(db):
    world = _world(db, "check-version")
    other_version = ProgrammeVersion.objects.create(
        programme=world["version"].programme, version=2,
    )
    Enrolment.objects.filter(pk=world["enrolment"].pk).update(
        programme_version=other_version,
    )
    world["lesson_attempt"] = LessonAttempt.objects.select_related("enrolment").get(
        pk=world["lesson_attempt"].pk,
    )

    _assert_code(world, "programme_mismatch")


@pytest.mark.django_db
def test_a_condition_bound_to_another_journey_is_refused(db):
    world = _world(db, "check-binding")
    other_journey = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["course"],
        code="check-binding-other", title="Other journey", order=2,
    )
    other_role = JourneyRecordRole.objects.create(
        journey=other_journey, key="other-declaration", label="Other",
        record_kind="ucr", order=1, creation_mode=EXISTING,
    )
    JourneyConditionBinding.objects.filter(condition=world["saved"][0]).update(
        role=other_role,
    )

    _assert_code(world, "binding_mismatch")


@pytest.mark.django_db
def test_a_completed_journey_cannot_be_revalidated(db):
    world = _world(db, "check-completed")
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED, completed_at=timezone.now(),
    )

    _assert_code(world, "attempt_not_in_progress")


@pytest.mark.django_db
def test_a_missing_attempt_is_refused(db):
    world = _world(db, "check-attempt")
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).delete()

    _assert_code(world, "attempt_missing")


@pytest.mark.django_db
def test_a_future_step_is_refused(db):
    world = _world(db, "check-future", two_steps=True)
    first_assignment = JourneyStep.objects.get(
        journey=world["journey"], step=world["first_step"],
    )
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        current_journey_step=first_assignment,
    )

    _assert_code(world, "step_not_current")


@pytest.mark.django_db
def test_a_blocked_step_is_refused(db):
    world = _world(db, "check-blocked", two_steps=True)

    _assert_code(world, "progression_blocked")


@pytest.mark.django_db
def test_an_opening_generation_is_required(db):
    world = _world(db, "check-generation")
    StepEvent.objects.filter(pk=world["opening"].pk).update(generation=None)
    world["opening"].refresh_from_db()

    _assert_code(world, "opening_missing_generation")
    assert evaluate_exact_condition(
        world["saved"][0], opening=world["opening"],
    ).code == "opening_missing_generation"

    StepEvent.objects.filter(pk=world["opening"].pk).delete()
    _assert_code(world, "opening_missing")
    assert evaluate_exact_condition(
        world["saved"][0], opening=None,
    ).code == "opening_missing"


@pytest.mark.django_db
def test_another_learners_attempt_cannot_be_revalidated(db):
    world = _world(db, "check-intruder")
    intruder = User.objects.create_user(username="check-intruder-user", password="x")

    with pytest.raises(PermissionDenied):
        _revalidate(world, user=intruder)


# --- Condition evaluation -----------------------------------------------------


@pytest.mark.django_db
def test_a_screen_only_step_is_evaluated_from_the_opening(db):
    world = _world(db, "check-screen", conditions=("screen",))

    locked = _revalidate(world)

    assert locked.context.selections == ()
    assert locked.records == ()
    assert evaluate_exact_condition(
        world["conditions"][0], opening=world["opening"],
    ).passed is True


@pytest.mark.django_db
def test_saved_state_must_match_the_condition(db):
    world = _world(db, "check-state")
    locked = _revalidate(world)
    condition = world["saved"][0]
    selection = locked.context.selection_for(condition)
    record = locked.record_for(condition)

    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=selection, record=record,
    ).passed is True

    UcrDeclaration.objects.filter(pk=record.pk).update(status="submitted")
    record.refresh_from_db()
    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=selection, record=record,
    ).code == "record_status_mismatch"

    UcrDeclaration.objects.filter(pk=record.pk).update(
        status="draft", exporter_name="Someone Else",
    )
    record.refresh_from_db()
    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=selection, record=record,
    ).code == "record_fields_mismatch"

    decoy = UcrDeclaration.objects.create(
        owner=world["student"], temp_no="check-state-decoy", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=selection, record=decoy,
    ).code == "record_mismatch"

    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=None, record=None,
    ).code == "record_unavailable"


@pytest.mark.django_db
def test_record_activity_must_meet_the_freshness_floor(db):
    world = _world(db, "check-fresh")
    locked = _revalidate(world)
    condition = world["saved"][0]
    selection = locked.context.selection_for(condition)

    stale = replace(selection, freshness_floor=timezone.now() + timedelta(minutes=5))
    assert evaluate_exact_condition(
        condition, opening=world["opening"], selection=stale,
        record=locked.record_for(condition),
    ).code == "record_stale"

    StepEvent.objects.filter(pk=world["opening"].pk).update(
        occurred_at=timezone.now() + timedelta(minutes=5),
    )
    _assert_code(world, "record_stale")


@pytest.mark.django_db
def test_several_conditions_can_share_one_exact_record(db):
    world = _world(db, "check-shared", conditions=("saved", "saved"))
    first, second = world["saved"]

    locked = _revalidate(world)
    first_selection = locked.context.selection_for(first)
    second_selection = locked.context.selection_for(second)

    assert first_selection.record_id == second_selection.record_id == world["record"].pk
    assert locked.record_for(first).pk == locked.record_for(second).pk == world["record"].pk
    assert _evaluate(world, first, locked).passed is True
    assert _evaluate(world, second, locked).passed is True


@pytest.mark.django_db
def test_an_unknown_condition_kind_is_refused(db):
    world = _world(db, "check-invalid-kind")
    condition = VerificationCondition.objects.create(
        step=world["step"], kind="action_journal", order=5,
    )

    result = evaluate_exact_condition(condition, opening=world["opening"])

    assert result.passed is False
    assert result.code == "invalid_condition"


# --- History and read-only boundaries ----------------------------------------


@pytest.mark.django_db
def test_historical_evidence_survives_a_provenance_break(db):
    world = _world(db, "check-history")
    evidence = _historical_evidence(world)
    before = (StepEvent.objects.count(), JourneyVerificationEvidence.objects.count())

    world["record"].delete()

    result = journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], world["step"],
    )
    assert isinstance(result, NotCurrent)
    assert result.reason == "record_unavailable"
    history = journey_evidence.verification_history(
        world["lesson_attempt"], world["step"],
    )
    assert [row.pk for row in history] == [evidence.pk]
    assert (StepEvent.objects.count(), JourneyVerificationEvidence.objects.count()) == before


@pytest.mark.django_db
def test_the_foundation_writes_nothing(db):
    world = _world(db, "check-read-only")
    condition = world["saved"][0]
    before = (
        StepEvent.objects.count(),
        JourneyVerificationEvidence.objects.count(),
        JourneyRecordAssociation.objects.count(),
    )

    locked = _revalidate(world)
    _evaluate(world, condition, locked)
    journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], world["step"],
    )

    assert (
        StepEvent.objects.count(),
        JourneyVerificationEvidence.objects.count(),
        JourneyRecordAssociation.objects.count(),
    ) == before


@pytest.mark.django_db
def test_legacy_resolution_is_unchanged(db):
    world = _world(db, "check-legacy")
    legacy_step = PracticalStep.objects.create(
        lesson=world["lesson"], key="legacy", title="Legacy",
        screen="single-window-overview", order=5,
    )

    assert resolve_journey_verification(
        world["student"], world["lesson_attempt"], legacy_step,
    ) is None
    assert revalidate_journey_verification(
        world["student"], world["lesson_attempt"], legacy_step,
    ) is None
    result = journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], legacy_step,
    )
    assert isinstance(result, NotCurrent)
    assert result.reason == "not_journey_step"
