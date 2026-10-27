"""Stage 3.3 shared-role semantics: one ``JourneyRecordRole`` may serve several
journey steps, and a record produced for an early step is legitimately reused
by later ones.

Creation eligibility is journey-attempt-scoped — the ledger row, the learner's
ownership and ``JourneyAttempt.started_at`` — never step-scoped: entering or
re-entering a step must not retroactively invalidate an attributed record.
Step-specific freshness stays with the verification engines, which bound the
record's *activity* to the one step being checked.
"""
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
    JourneyRecordAssociation,
    JourneyRecordRole,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    SimulatorRecordCreation,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration

SCREEN = "single-window-overview"
STEP_NAMES = ("create", "submit", "verify")


def _shared_world(db, seed, started_minutes_ago=60):
    """One NEW ucr role bound to a saved-record condition on each of three
    steps, each in its own lesson: create, then submit, then verify."""
    programme = Programme.objects.create(
        name=seed, code=seed, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{seed}-course", title="Course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{seed}-mod", title="Module", order=1)
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    role = journey_services.create_record_role(
        journey, "declaration", "Declaration", "ucr",
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )

    steps = {}
    for index, name in enumerate(STEP_NAMES, start=1):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"{seed}-{name}", title=f"{name.title()} lesson",
            order=index, theory="<p>Theory</p>",
        )
        step = PracticalStep.objects.create(
            lesson=lesson, key=f"{seed}-{name}", title=f"Step {name}", order=index, screen=SCREEN,
        )
        assignment = journey_services.assign_step(journey, step)
        condition = VerificationCondition.objects.create(
            step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
            required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
        )
        journey_services.bind_condition(condition, role)
        steps[name] = (step, assignment)

    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    student = User.objects.create_user(username=f"{seed}-student", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    lesson_attempts = {
        name: LessonAttempt.objects.create(enrolment=enrolment, lesson=steps[name][0].lesson)
        for name in STEP_NAMES
    }
    attempt = journey_services.get_or_create_attempt(enrolment, journey)
    JourneyAttempt.objects.filter(pk=attempt.pk).update(
        started_at=timezone.now() - timedelta(minutes=started_minutes_ago),
    )
    attempt.refresh_from_db()
    return {
        "version": version, "journey": journey, "role": role, "student": student,
        "enrolment": enrolment, "attempt": attempt, "steps": steps,
        "lesson_attempts": lesson_attempts,
    }


def _open(world, name):
    step, _assignment = world["steps"][name]
    return verification.record_open(world["lesson_attempts"][name], step)


def _record(world, temp_no, **overrides):
    fields = {"status": "draft", "exporter_name": "ACME Trading", "regime": "CO"}
    fields.update(overrides)
    return UcrDeclaration.objects.create(owner=world["student"], temp_no=temp_no, **fields)


def _ledger(record):
    return SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)


def _attribute(world, record):
    return attribution.attribute_creation(
        world["attempt"], world["role"], _ledger(record).pk, world["student"],
    )


def _touch(record):
    record.refresh_from_db()
    record.save()
    return record


def _make_second_step_reachable(world):
    """Verify step 1 and move the attempt onto step 2, so step 2 is the
    current, reachable step for the resolver."""
    step1, _assignment1 = world["steps"]["create"]
    step2, assignment2 = world["steps"]["submit"]
    verification.mark_verified(world["lesson_attempts"]["create"], step1)
    world["attempt"].current_journey_step = assignment2
    world["attempt"].save(update_fields=("current_journey_step",))
    return step2, world["lesson_attempts"]["submit"]


def _reuse_record_at_step_two(world, temp_no="TEMP-SHARED-9"):
    """Attribute a step-1 record, work it at step 2, and make step 2 current —
    the shared setup for the later-step and fail-closed tests."""
    record = _record(world, temp_no)
    _open(world, "create")
    _attribute(world, record)
    _open(world, "submit")
    _touch(record)
    step2, lesson_attempt2 = _make_second_step_reachable(world)
    return step2, lesson_attempt2, record


@pytest.mark.django_db
def test_one_record_role_is_bound_to_three_journey_steps(db):
    world = _shared_world(db, "shared-shape")
    bound_titles = [
        binding.condition.step.title
        for binding in world["role"].condition_bindings.select_related("condition__step")
    ]
    assert len(bound_titles) == 3
    assert len(set(bound_titles)) == 3


@pytest.mark.django_db
def test_record_created_at_step_one_survives_later_step_openings(db):
    """The reported defect, permanently: opening steps 2 and 3 must not
    un-satisfy the role that step 1's record legitimately fills."""
    world = _shared_world(db, "shared-reuse")
    _open(world, "create")
    record = _record(world, "TEMP-SHARED-1")
    association = _attribute(world, record)
    world["attempt"].refresh_from_db()

    satisfied, message = journey_services.role_satisfied(world["attempt"], world["role"])
    assert satisfied, message

    for name in ("submit", "verify"):
        _open(world, name)
        world["attempt"].refresh_from_db()
        satisfied, message = journey_services.role_satisfied(world["attempt"], world["role"])
        assert satisfied, f"after opening {name}: {message}"
        assert JourneyRecordAssociation.objects.filter(
            journey_attempt=world["attempt"], role=world["role"], is_active=True, pk=association.pk,
        ).exists(), f"opening {name} superseded the attribution"

    state = journey_services.journey_completion_state(world["attempt"])
    assert state["roles_satisfied"] == state["roles_required"] == 1


@pytest.mark.django_db
def test_reopening_a_shared_role_step_keeps_the_record_available(db):
    """Re-entry is navigation: the attributed record stays the role's active
    record, and no superseded association is written."""
    world = _shared_world(db, "shared-reopen")
    _open(world, "create")
    record = _record(world, "TEMP-SHARED-2")
    _attribute(world, record)

    for _repeat in range(3):
        _open(world, "create")
        _open(world, "submit")
    world["attempt"].refresh_from_db()

    assert journey_services.role_satisfied(world["attempt"], world["role"])[0]
    assert journey_services.active_record(world["attempt"], world["role"]).record_id == record.pk
    assert not JourneyRecordAssociation.objects.filter(
        journey_attempt=world["attempt"], role=world["role"], is_active=False,
    ).exists()
    # Availability is not verification: re-entry writes no VERIFIED event.
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()


@pytest.mark.django_db
def test_a_pre_attempt_record_is_ineligible_for_a_shared_role(db):
    world = _shared_world(db, "shared-preattempt")
    record = _record(world, "TEMP-SHARED-3")
    JourneyAttempt.objects.filter(pk=world["attempt"].pk).update(
        started_at=timezone.now() + timedelta(minutes=1),
    )
    world["attempt"].refresh_from_db()
    _open(world, "create")

    ids = [row["record_id"] for row in attribution.eligible_for_view(world["attempt"], world["role"])]
    assert record.pk not in ids
    with pytest.raises(attribution.AttributionError) as excinfo:
        _attribute(world, record)
    assert excinfo.value.code == "outside_window"


@pytest.mark.django_db
def test_another_students_record_is_rejected_for_a_shared_role(db):
    world = _shared_world(db, "shared-foreign")
    other = User.objects.create_user(username="shared-foreign-other", password="x")
    theirs = UcrDeclaration.objects.create(
        owner=other, temp_no="TEMP-SHARED-FOREIGN", status="draft",
        exporter_name="ACME Trading", regime="CO",
    )
    _open(world, "create")

    ids = [row["record_id"] for row in attribution.eligible_for_view(world["attempt"], world["role"])]
    assert theirs.pk not in ids
    with pytest.raises(PermissionDenied):
        attribution.attribute_creation(world["attempt"], world["role"], _ledger(theirs).pk, world["student"])
    assert not JourneyRecordAssociation.objects.exists()


@pytest.mark.django_db
def test_a_record_claimed_by_another_journey_cannot_be_reused(db):
    """Permanent claim uniqueness outlives the R1 bound: the other journey's
    record is neither listed nor attributable, even though it postdates this
    attempt's start."""
    world = _shared_world(db, "shared-claim")
    # Journey structure is authored in a draft edition, then republished.
    world["version"].status = ProgrammeVersion.Status.DRAFT
    world["version"].save(update_fields=("status",))
    other_journey = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["journey"].course,
        code="shared-claim-other", title="Other journey", order=2,
    )
    other_role = journey_services.create_record_role(
        other_journey, "declaration", "Declaration", "ucr",
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))

    other_attempt = journey_services.get_or_create_attempt(world["enrolment"], other_journey)
    claimed = _record(world, "TEMP-SHARED-4")
    attribution.attribute_creation(other_attempt, other_role, _ledger(claimed).pk, world["student"])

    _open(world, "create")
    ids = [row["record_id"] for row in attribution.eligible_for_view(world["attempt"], world["role"])]
    assert claimed.pk not in ids
    with pytest.raises(attribution.AttributionError) as excinfo:
        _attribute(world, claimed)
    assert excinfo.value.code == "already_claimed"


@pytest.mark.django_db
def test_the_resolver_accepts_a_reused_record(db):
    """A record created for step 1 verifies legitimately at step 2: the
    journey-scoped provenance bound passes and the step's activity bound is
    met by work done during this visit."""
    world = _shared_world(db, "shared-resolver")
    _open(world, "create")
    record = _record(world, "TEMP-SHARED-5")
    _attribute(world, record)

    _open(world, "submit")
    _touch(record)
    step2, lesson_attempt2 = _make_second_step_reachable(world)

    context = resolve_journey_verification(world["student"], lesson_attempt2, step2)
    assert [selection.record_id for selection in context.selections] == [record.pk]


@pytest.mark.django_db
def test_reopening_a_step_refuses_stale_step_verification(db):
    """Reuse never shortcuts the step itself: re-entering step 2 without
    working the record again leaves this visit's verification stale."""
    world = _shared_world(db, "shared-stale")
    _open(world, "create")
    record = _record(world, "TEMP-SHARED-6")
    _attribute(world, record)
    _open(world, "submit")
    _touch(record)
    step2, lesson_attempt2 = _make_second_step_reachable(world)

    _open(world, "submit")
    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        resolve_journey_verification(world["student"], lesson_attempt2, step2)
    assert excinfo.value.code == "record_stale"


@pytest.mark.django_db
def test_creation_provenance_and_step_freshness_are_separate_bounds(db):
    """A record older than the attempt fails creation provenance even when its
    activity is fresh enough for the step, and the role reports the journey
    bound rather than any step opening."""
    world = _shared_world(db, "shared-provenance", started_minutes_ago=0)
    _open(world, "create")
    record = _record(world, "TEMP-SHARED-7")
    _attribute(world, record)
    step1, _assignment1 = world["steps"]["create"]

    JourneyAttempt.objects.filter(pk=world["attempt"].pk).update(started_at=timezone.now())
    world["attempt"].refresh_from_db()
    _touch(record)

    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        resolve_journey_verification(world["student"], world["lesson_attempts"]["create"], step1)
    assert excinfo.value.code == "record_predates_journey"

    satisfied, message = journey_services.role_satisfied(world["attempt"], world["role"])
    assert not satisfied
    assert "before this journey started" in message


@pytest.mark.django_db
def test_a_removed_condition_binding_raises_rather_than_falling_back(db):
    world = _shared_world(db, "shared-fallback-binding")
    step2, lesson_attempt2, _record_row = _reuse_record_at_step_two(world)
    JourneyConditionBinding.objects.filter(condition=step2.conditions.first()).delete()

    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        resolve_journey_verification(world["student"], lesson_attempt2, step2)
    assert excinfo.value.code == "binding_missing"


@pytest.mark.django_db
def test_a_missing_active_association_raises_rather_than_falling_back(db):
    world = _shared_world(db, "shared-fallback-association")
    step2, lesson_attempt2, _record_row = _reuse_record_at_step_two(world)
    JourneyRecordAssociation.objects.filter(
        journey_attempt=world["attempt"], role=world["role"],
    ).update(is_active=False, replaced_at=timezone.now())

    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        resolve_journey_verification(world["student"], lesson_attempt2, step2)
    assert excinfo.value.code == "association_missing"


@pytest.mark.django_db
def test_a_deleted_attributed_record_raises_rather_than_falling_back(db):
    world = _shared_world(db, "shared-fallback-record")
    step2, lesson_attempt2, record = _reuse_record_at_step_two(world)
    record.delete()

    with pytest.raises(JourneyVerificationResolutionError) as excinfo:
        resolve_journey_verification(world["student"], lesson_attempt2, step2)
    assert excinfo.value.code == "record_unavailable"


@pytest.mark.django_db
def test_only_a_non_journey_step_falls_back_to_legacy_verification(db):
    """``None`` — the legacy owner-wide path — is reserved for steps that are
    not assigned to a journey at all."""
    world = _shared_world(db, "shared-fallback-legacy")
    step2, lesson_attempt2, _record_row = _reuse_record_at_step_two(world)
    assert resolve_journey_verification(world["student"], lesson_attempt2, step2) is not None

    legacy_step = PracticalStep.objects.create(
        lesson=lesson_attempt2.lesson, key="legacy-step", title="Legacy step", order=9,
    )
    assert resolve_journey_verification(world["student"], lesson_attempt2, legacy_step) is None
