"""Stage 3.3 journey verification through the student interface.

These tests drive the real student endpoints — open, check, acknowledge,
advance the journey — and assert what the learner sees at each step together
with the durable rows behind it. They cover the exact-record success path,
every fail-closed refusal, evidence that stops being current (new opening,
replaced record, edited condition) and the full journey through completion.
"""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from accounts.models import User
from hybrid import attribution, journey_evidence, journey_services, verification
from hybrid.journey_evidence import CurrentVerification, NotCurrent
from hybrid.journey_verification import verify_journey_step
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
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
from onboarding.models import (
    DisclaimerAcceptance,
    DisclaimerVersion,
    Enrolment,
    Programme,
    ProgrammeVersion,
)
from scenarios.models import UcrDeclaration

SCREEN = "single-window-overview"
EXISTING = JourneyRecordRole.CreationMode.EXISTING
NEW = JourneyRecordRole.CreationMode.NEW


def _world(db, seed, *, creation_mode=EXISTING, extra_condition=False, free_step=True):
    """Two journey lessons, two saved-record steps, an optional condition-free
    step and an optional second condition bound to a second role."""
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
    lesson_one = HybridLesson.objects.create(
        module=module, slug=f"{seed}-one", title="Lesson one", order=1, theory="<p>Theory</p>",
    )
    lesson_two = HybridLesson.objects.create(
        module=module, slug=f"{seed}-two", title="Lesson two", order=2, theory="<p>Theory</p>",
    )
    step_one = PracticalStep.objects.create(
        lesson=lesson_one, key=f"{seed}-one", title="Step one", order=1, screen=SCREEN,
    )
    step_two = PracticalStep.objects.create(
        lesson=lesson_two, key=f"{seed}-two", title="Step two", order=1, screen=SCREEN,
    )
    steps = [step_one, step_two]
    free = None
    if free_step:
        free = PracticalStep.objects.create(
            lesson=lesson_two, key=f"{seed}-free", title="Free step", order=2, screen=SCREEN,
        )
        steps.append(free)

    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    for step in steps:
        journey_services.assign_step(journey, step)

    role_one = journey_services.create_record_role(
        journey, "declaration", "Declaration", "ucr", creation_mode=creation_mode,
    )
    role_two = journey_services.create_record_role(
        journey, "second", "Second declaration", "ucr", creation_mode=creation_mode,
    )
    condition_one = VerificationCondition.objects.create(
        step=step_one, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
    )
    journey_services.bind_condition(condition_one, role_one)
    condition_two = VerificationCondition.objects.create(
        step=step_two, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
    )
    journey_services.bind_condition(condition_two, role_two)
    role_extra = condition_extra = None
    if extra_condition:
        role_extra = journey_services.create_record_role(
            journey, "extra", "Extra declaration", "ucr", creation_mode=creation_mode,
        )
        condition_extra = VerificationCondition.objects.create(
            step=step_two, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
            required_status="draft", expected_fields={"importer_name": "ACME Imports"}, order=2,
        )
        journey_services.bind_condition(condition_extra, role_extra)

    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))

    student = User.objects.create_user(username=f"{seed}-student", password="x")
    DisclaimerAcceptance.objects.get_or_create(
        user=student,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    attempt_one = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson_one)
    attempt_two = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson_two)
    journey_attempt = journey_services.get_or_create_attempt(enrolment, journey)

    return {
        "lesson_one": lesson_one,
        "lesson_two": lesson_two,
        "module": module,
        "steps": {"one": step_one, "two": step_two, "free": free},
        "assignments": {
            "one": JourneyStep.objects.get(journey=journey, step=step_one),
            "two": JourneyStep.objects.get(journey=journey, step=step_two),
            "free": (
                JourneyStep.objects.get(journey=journey, step=free) if free is not None else None
            ),
        },
        "journey": journey,
        "roles": {"one": role_one, "two": role_two, "extra": role_extra},
        "conditions": {"one": condition_one, "two": condition_two, "extra": condition_extra},
        "student": student,
        "enrolment": enrolment,
        "attempts": {"one": attempt_one, "two": attempt_two},
        "journey_attempt": journey_attempt,
    }


def _record(world, temp_no, **overrides):
    fields = {
        "status": "draft", "exporter_name": "ACME Trading",
        "importer_name": "ACME Imports", "regime": "CO",
    }
    fields.update(overrides)
    return UcrDeclaration.objects.create(owner=world["student"], temp_no=temp_no, **fields)


def _attribute(world, role_key, record):
    return journey_services.assign_record(
        world["journey_attempt"], world["roles"][role_key], record.pk,
        JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )


def _attribute_creation(world, role_key, record):
    ledger = SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)
    return attribution.attribute_creation(
        world["journey_attempt"], world["roles"][role_key], ledger.pk, world["student"],
    )


def _open(client, world, lesson_key, index=0):
    return client.post(reverse("hybrid-step-open", args=[world["attempts"][lesson_key].pk, index]))


def _check(client, world, lesson_key, index=0):
    return client.post(reverse("hybrid-step-check", args=[world["attempts"][lesson_key].pk, index]))


def _acknowledge(client, world, lesson_key):
    return client.post(reverse("hybrid-acknowledge-theory", args=[world["attempts"][lesson_key].pk]))


def _advance_journey(client, world):
    return client.post(reverse("hybrid-journey-advance", args=[world["journey"].pk]))


def _opening(world, lesson_key, step_key):
    return StepEvent.objects.get(
        attempt=world["attempts"][lesson_key],
        step=world["steps"][step_key],
        kind=StepEvent.Kind.OPENED,
    )


def _current(world, lesson_key, step_key):
    return journey_evidence.current_verification(
        world["student"], world["attempts"][lesson_key], world["steps"][step_key],
    )


def _verified(client, world, lesson_key, role_key, temp_no, **record_fields):
    """Open the step, create and attribute a record, and check the work."""
    assert _open(client, world, lesson_key).status_code == 200
    record = _record(world, temp_no, **record_fields)
    association = _attribute(world, role_key, record)
    response = _check(client, world, lesson_key)
    return response, record, association


# --- Success and exact-record identity ---------------------------------------


@pytest.mark.django_db
def test_check_my_work_verifies_the_exact_attributed_record(client, db):
    world = _world(db, "flow-success")
    client.force_login(world["student"])
    assert _open(client, world, "one").status_code == 200
    record = _record(world, "TEMP-FLOW-1")
    association = _attribute(world, "one", record)
    decoy = _record(world, "TEMP-FLOW-DECOY")

    response = _check(client, world, "one")

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is True
    assert [result["passed"] for result in payload["results"]] == [True]
    assert payload["lesson_complete"] is False

    evidence = JourneyVerificationEvidence.objects.get(condition=world["conditions"]["one"])
    assert evidence.journey_step_id == world["assignments"]["one"].pk
    assert evidence.association_id == association.pk
    assert evidence.record_id == record.pk
    assert evidence.record_id != decoy.pk
    assert evidence.opening_generation == _opening(world, "one", "one").generation
    assert evidence.condition_fingerprint == journey_evidence.condition_fingerprint(
        world["conditions"]["one"]
    )
    assert evidence.role_id == world["roles"]["one"].pk
    assert StepEvent.objects.filter(
        attempt=world["attempts"]["one"], step=world["steps"]["one"], kind=StepEvent.Kind.VERIFIED,
    ).exists()
    assert isinstance(_current(world, "one", "one"), CurrentVerification)

    assert _acknowledge(client, world, "one").json()["lesson_complete"] is True


@pytest.mark.django_db
def test_a_record_with_the_wrong_saved_values_cannot_pass(client, db):
    world = _world(db, "flow-wrong-values")
    client.force_login(world["student"])
    assert _open(client, world, "one").status_code == 200
    _attribute(world, "one", _record(world, "TEMP-FLOW-WRONG", exporter_name="Someone Else"))

    response = _check(client, world, "one")

    assert response.status_code == 200
    payload = response.json()
    assert payload["passed"] is False
    assert payload["results"][0]["passed"] is False
    assert not JourneyVerificationEvidence.objects.exists()
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()
    assert isinstance(_current(world, "one", "one"), NotCurrent)


@pytest.mark.django_db
def test_a_step_without_an_attributed_record_fails_closed(client, db):
    world = _world(db, "flow-unattributed")
    client.force_login(world["student"])
    assert _open(client, world, "one").status_code == 200
    _record(world, "TEMP-FLOW-UNATTRIBUTED")

    response = _check(client, world, "one")

    assert response.status_code == 403
    assert response.json()["code"] == "association_missing"
    assert not JourneyVerificationEvidence.objects.exists()
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()


@pytest.mark.django_db
def test_every_bound_condition_and_role_must_pass(client, db):
    world = _world(db, "flow-two-roles", extra_condition=True)
    client.force_login(world["student"])
    first, _record_row, _association = _verified(
        client, world, "one", "one", "TEMP-FLOW-ROLE-ONE",
    )
    assert first.json()["passed"] is True
    _advance_journey(client, world)
    assert _open(client, world, "two").status_code == 200
    _attribute(world, "two", _record(world, "TEMP-FLOW-ROLE-TWO"))

    blocked = _check(client, world, "two")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "association_missing"
    assert not JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["two"],
    ).exists()

    _attribute(world, "extra", _record(world, "TEMP-FLOW-ROLE-EXTRA"))
    passed = _check(client, world, "two")

    assert passed.status_code == 200
    assert passed.json()["passed"] is True
    assert JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["two"],
    ).count() == 2
    assert set(
        JourneyVerificationEvidence.objects.filter(
            journey_step=world["assignments"]["two"],
        ).values_list("role_id", flat=True)
    ) == {world["roles"]["two"].pk, world["roles"]["extra"].pk}


# --- Provenance ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_created_in_journey_record_verifies_through_its_ledger(client, db):
    world = _world(db, "flow-created", creation_mode=NEW)
    client.force_login(world["student"])
    assert _open(client, world, "one").status_code == 200
    record = _record(world, "TEMP-FLOW-CREATED")
    association = _attribute_creation(world, "one", record)

    response = _check(client, world, "one")

    assert response.status_code == 200
    assert response.json()["passed"] is True
    assert JourneyVerificationEvidence.objects.get(
        condition=world["conditions"]["one"],
    ).association_id == association.pk


@pytest.mark.django_db
def test_a_record_created_before_the_journey_cannot_verify(client, db):
    world = _world(db, "flow-outside-window", creation_mode=NEW)
    client.force_login(world["student"])
    record = _record(world, "TEMP-FLOW-EARLY")
    assert _open(client, world, "one").status_code == 200
    record.refresh_from_db()
    record.save()
    _attribute_creation(world, "one", record)
    ledger_created = SimulatorRecordCreation.objects.get(
        record_kind="ucr", record_id=record.pk,
    ).record_created_at
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        started_at=ledger_created + timedelta(microseconds=1),
    )

    response = _check(client, world, "one")

    assert response.status_code == 403
    assert response.json()["code"] == "record_predates_journey"
    assert not JourneyVerificationEvidence.objects.exists()


# --- Repeats and failures -----------------------------------------------------


@pytest.mark.django_db
def test_repeated_check_my_work_records_one_evidence_row(client, db):
    world = _world(db, "flow-repeat")
    client.force_login(world["student"])
    response, _record_row, _association = _verified(
        client, world, "one", "one", "TEMP-FLOW-REPEAT",
    )
    assert response.json()["passed"] is True

    second = _check(client, world, "one")

    assert second.status_code == 200
    assert second.json()["passed"] is True
    assert JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["one"],
    ).count() == 1
    assert StepEvent.objects.filter(
        attempt=world["attempts"]["one"], step=world["steps"]["one"], kind=StepEvent.Kind.VERIFIED,
    ).count() == 1


@pytest.mark.django_db
def test_a_failed_check_leaves_the_step_and_journey_where_they_were(client, db):
    world = _world(db, "flow-failed")
    client.force_login(world["student"])
    assert _open(client, world, "one").status_code == 200
    _attribute(world, "one", _record(world, "TEMP-FLOW-FAILED", status="submitted"))

    response = _check(client, world, "one")

    assert response.json()["passed"] is False
    assert verification.attempt_snapshot(world["attempts"]["one"])["satisfied"] == []
    rows = journey_services.journey_step_rows(world["journey_attempt"])
    assert rows[0]["satisfied"] is False
    assert rows[0]["requirement"] == "Pass Check my work on this step."

    _advance_journey(client, world)
    world["journey_attempt"].refresh_from_db()
    assert world["journey_attempt"].current_journey_step_id == world["assignments"]["one"].pk
    assert world["journey_attempt"].completed_at is None


# --- Evidence that stops being current ---------------------------------------


@pytest.mark.django_db
def test_a_new_opening_generation_makes_old_evidence_stale(client, db):
    world = _world(db, "flow-reopened")
    client.force_login(world["student"])
    response, _record_row, _association = _verified(
        client, world, "one", "one", "TEMP-FLOW-REOPENED",
    )
    assert response.json()["passed"] is True
    opening = _opening(world, "one", "one")
    original_generation = opening.generation
    StepEvent.objects.filter(pk=opening.pk).update(generation=uuid.uuid4())

    stale = _current(world, "one", "one")
    assert isinstance(stale, NotCurrent)
    assert stale.reason == "evidence_stale"
    assert journey_services.journey_step_rows(world["journey_attempt"])[0]["satisfied"] is False

    again = _check(client, world, "one")

    assert again.json()["passed"] is True
    assert JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["one"], opening_generation=original_generation,
    ).count() == 1
    assert JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["one"],
    ).count() == 2
    assert isinstance(_current(world, "one", "one"), CurrentVerification)


@pytest.mark.django_db
def test_replacing_the_attributed_record_requires_reverification(client, db):
    world = _world(db, "flow-replaced")
    client.force_login(world["student"])
    response, first_record, first_association = _verified(
        client, world, "one", "one", "TEMP-FLOW-REPLACED-1",
    )
    assert response.json()["passed"] is True

    replacement_record = _record(world, "TEMP-FLOW-REPLACED-2")
    replacement = _attribute(world, "one", replacement_record)

    conflicted = _current(world, "one", "one")
    assert isinstance(conflicted, NotCurrent)
    assert conflicted.reason == "evidence_conflicted"
    assert journey_services.journey_step_rows(world["journey_attempt"])[0]["satisfied"] is False

    again = _check(client, world, "one")

    assert again.json()["passed"] is True
    assert isinstance(_current(world, "one", "one"), CurrentVerification)
    assert JourneyVerificationEvidence.objects.filter(
        condition=world["conditions"]["one"],
    ).count() == 2
    assert JourneyVerificationEvidence.objects.filter(
        condition=world["conditions"]["one"], association=replacement,
    ).exists()
    assert JourneyVerificationEvidence.objects.filter(
        condition=world["conditions"]["one"], association=first_association,
    ).exists()
    assert first_record.pk != replacement_record.pk


@pytest.mark.django_db
def test_editing_a_condition_requires_reverification(client, db):
    world = _world(db, "flow-edited")
    client.force_login(world["student"])
    response, _record_row, _association = _verified(
        client, world, "one", "one", "TEMP-FLOW-EDITED",
    )
    assert response.json()["passed"] is True
    condition = world["conditions"]["one"]
    original_fingerprint = journey_evidence.condition_fingerprint(condition)
    VerificationCondition.objects.filter(pk=condition.pk).update(
        expected_fields={"importer_name": "ACME Imports"},
    )

    outdated = _current(world, "one", "one")
    assert isinstance(outdated, NotCurrent)
    assert outdated.reason == "evidence_outdated"
    assert journey_services.journey_step_rows(world["journey_attempt"])[0]["satisfied"] is False

    again = _check(client, world, "one")

    assert again.json()["passed"] is True
    assert JourneyVerificationEvidence.objects.filter(
        condition=condition, condition_fingerprint=original_fingerprint,
    ).count() == 1
    assert JourneyVerificationEvidence.objects.filter(condition=condition).count() == 2
    assert isinstance(_current(world, "one", "one"), CurrentVerification)


# --- Progression and completion ----------------------------------------------


@pytest.mark.django_db
def test_the_journey_advances_and_completes_through_the_student_pages(client, db):
    world = _world(db, "flow-complete")
    client.force_login(world["student"])

    response, _record_one, _association_one = _verified(
        client, world, "one", "one", "TEMP-FLOW-COMPLETE-1",
    )
    assert response.json()["passed"] is True
    assert _acknowledge(client, world, "one").json()["lesson_complete"] is True

    _advance_journey(client, world)
    world["journey_attempt"].refresh_from_db()
    assert world["journey_attempt"].current_journey_step_id == world["assignments"]["two"].pk

    second, _record_two, _association_two = _verified(
        client, world, "two", "two", "TEMP-FLOW-COMPLETE-2",
    )
    assert second.json()["passed"] is True
    # Legacy lesson rule: a condition-free step counts without being opened.
    assert _acknowledge(client, world, "two").json()["lesson_complete"] is True

    _advance_journey(client, world)
    world["journey_attempt"].refresh_from_db()
    assert world["journey_attempt"].current_journey_step_id == world["assignments"]["free"].pk
    assert _open(client, world, "two", index=1).status_code == 200

    _advance_journey(client, world)
    world["journey_attempt"].refresh_from_db()

    assert world["journey_attempt"].status == JourneyAttempt.Status.COMPLETED
    assert world["journey_attempt"].completed_at is not None


@pytest.mark.django_db
def test_the_final_check_completes_a_journey_whose_lessons_are_done(client, db):
    world = _world(db, "flow-auto-complete", free_step=False)
    client.force_login(world["student"])

    first, _record_one, _association_one = _verified(
        client, world, "one", "one", "TEMP-FLOW-AUTO-1",
    )
    assert first.json()["passed"] is True
    assert _acknowledge(client, world, "one").json()["lesson_complete"] is True
    _advance_journey(client, world)

    assert _open(client, world, "two").status_code == 200
    _attribute(world, "two", _record(world, "TEMP-FLOW-AUTO-2"))
    assert _acknowledge(client, world, "two").json()["lesson_complete"] is False

    final = _check(client, world, "two")

    payload = final.json()
    assert payload["passed"] is True
    assert payload["lesson_complete"] is True
    assert payload["journey_complete"] is True
    world["journey_attempt"].refresh_from_db()
    assert world["journey_attempt"].status == JourneyAttempt.Status.COMPLETED

    repeat = _check(client, world, "two")
    assert repeat.status_code == 200
    assert repeat.json()["passed"] is True


# --- Fail-closed plumbing ----------------------------------------------------


@pytest.mark.django_db
def test_a_check_before_the_opening_persists_reports_a_retryable_pending(client, db):
    world = _world(db, "flow-pending")
    client.force_login(world["student"])

    response = _check(client, world, "one")

    assert response.status_code == 409
    assert response.json()["code"] == "opening_pending"
    assert not JourneyVerificationEvidence.objects.exists()


@pytest.mark.django_db
def test_a_legacy_step_outside_every_journey_still_verifies(client, db):
    world = _world(db, "flow-legacy")
    client.force_login(world["student"])
    lesson = HybridLesson.objects.create(
        module=world["module"], slug="flow-legacy-lesson", title="Legacy lesson", order=3,
        theory="<p>Theory</p>",
    )
    step = PracticalStep.objects.create(
        lesson=lesson, key="flow-legacy-step", title="Legacy step", order=1, screen=SCREEN,
    )
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SCREEN_OPENED, order=1,
    )
    attempt = LessonAttempt.objects.create(enrolment=world["enrolment"], lesson=lesson)

    assert client.post(reverse("hybrid-step-open", args=[attempt.pk, 0])).status_code == 200
    response = client.post(reverse("hybrid-step-check", args=[attempt.pk, 0]))

    assert response.status_code == 200
    assert response.json()["passed"] is True
    assert StepEvent.objects.filter(
        attempt=attempt, step=step, kind=StepEvent.Kind.VERIFIED,
    ).exists()
    assert not JourneyVerificationEvidence.objects.exists()


# --- Concurrency -------------------------------------------------------------


def _threaded_check(attempt_id, step_id, student_id, barrier):
    close_old_connections()
    try:
        barrier.wait(timeout=10)
        student = User.objects.get(pk=student_id)
        lesson_attempt = LessonAttempt.objects.get(pk=attempt_id)
        step = PracticalStep.objects.get(pk=step_id)
        return ("ok", verify_journey_step(student, lesson_attempt, step)["passed"])
    except Exception as exc:  # the assertion inspects the refusal
        return ("error", type(exc).__name__, str(exc))
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_concurrent_checks_record_a_single_evidence_row(transactional_db):
    # Repair migration-test ordering before opening separate connections.
    # Migrate the hybrid app to its latest migration — what ``migrate hybrid``
    # does. Pinning an ancestor would roll newer migrations back out of the
    # shared test database, breaking every suite that runs afterwards.
    executor = MigrationExecutor(connection)
    executor.migrate([key for key in executor.loader.graph.leaf_nodes() if key[0] == "hybrid"])
    world = _world(transactional_db, "flow-concurrent")
    verification.record_open(world["attempts"]["one"], world["steps"]["one"])
    _attribute(world, "one", _record(world, "TEMP-FLOW-CONCURRENT"))
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _threaded_check,
                world["attempts"]["one"].pk,
                world["steps"]["one"].pk,
                world["student"].pk,
                barrier,
            )
            for _index in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]

    assert any(result[0] == "ok" for result in results), results
    assert all(result[1] is True for result in results if result[0] == "ok"), results
    assert JourneyVerificationEvidence.objects.filter(
        journey_step=world["assignments"]["one"],
    ).count() == 1
    assert StepEvent.objects.filter(
        attempt=world["attempts"]["one"], step=world["steps"]["one"], kind=StepEvent.Kind.VERIFIED,
    ).count() == 1
