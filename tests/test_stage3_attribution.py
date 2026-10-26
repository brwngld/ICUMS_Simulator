"""Stage 3.2 Checkpoint A — secure student attribution backend.

The creation ledger is evidence; attribution is the student's explicit,
server-validated claim written as a ``created_in_journey``
``JourneyRecordAssociation``; verification stays with the existing engines.
Attribution never writes a VERIFIED ``StepEvent`` and never completes a
practical step.
"""
import json

import pytest
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from accounts.models import User
from hybrid import attribution, journey_services
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyRecordAssociation,
    JourneyRecordRole,
    PracticalJourney,
    PracticalStep,
    SimulatorRecordCreation,
    StepEvent,
    VerificationCondition,
)
from scenarios.models import UcrDeclaration
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion

SCREEN = "single-window-overview"


def _student(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.save(update_fields=("is_staff",))
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _world(db, seed):
    """One published journey with a NEW ucr role bound to its condition step,
    the student enrolled, and the attempt started at the entry point."""
    programme = Programme.objects.create(
        name=f"Attribution {seed}", code=seed, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{seed}-c", title=f"{seed} course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{seed}-m", title=f"{seed} module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{seed}-lesson", title=f"{seed} lesson", order=1,
        summary="Summary.", theory="<p>Theory.</p>",
    )
    step = PracticalStep.objects.create(
        lesson=lesson, key=f"{seed}-step", title=f"{seed} step",
        instruction="Create the record.", outcome="The record is saved.",
        screen=SCREEN, order=1,
    )
    condition = VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
    )
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey",
        title=f"{seed} journey", order=1,
        start_mode=PracticalJourney.StartMode.NEW_RECORD,
    )
    journey_services.assign_step(journey, step)
    role = journey_services.create_record_role(
        journey, "declaration", "Fresh declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    journey_services.bind_condition(condition, role)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    student = _student(db, f"{seed}-student")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    attempt = journey_services.get_or_create_attempt(enrolment, journey)
    return {
        "version": version, "journey": journey, "role": role, "student": student,
        "enrolment": enrolment, "attempt": attempt, "step": step,
    }


def _create_ucr_for(student, temp_no, **overrides):
    """Create through the real model so the 3.1 ledger captures it."""
    return UcrDeclaration.objects.create(owner=student, temp_no=temp_no, regime="CO", **overrides)


def _ledger_of(ucr):
    return SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=ucr.pk)


def _attribute(world, ledger_pk, student=None, fail=False):
    client = Client()
    if not fail:
        client.force_login(student or world["student"])
    return client.post(
        reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk]),
        data=json.dumps({"creation_id": str(ledger_pk)}),
        content_type="application/json",
    )


def _eligible(world, student=None):
    client = Client()
    client.force_login(student or world["student"])
    return client.get(
        reverse("hybrid-journey-role-eligible", args=[world["journey"].pk, world["role"].pk])
    )


@pytest.mark.django_db
def test_attribution_satisfies_the_role_but_not_the_step(db):
    """The full happy path: creation captured by the ledger, explicitly
    attributed, role satisfied — and no VERIFIED StepEvent written: the step
    still demands Check-My-Work."""
    world = _world(db, "attrhappy")
    student = world["student"]
    ucr = _create_ucr_for(student, "TEMPATH1")

    response = _attribute(world, _ledger_of(ucr).pk, student)

    assert response.status_code == 200
    association = JourneyRecordAssociation.objects.get(
        journey_attempt=world["attempt"], role=world["role"], is_active=True,
    )
    assert association.assignment_source == JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY
    assert association.record_id == ucr.pk
    assert association.assigned_by_id == student.pk

    satisfied, _message = journey_services.role_satisfied(world["attempt"], world["role"])
    assert satisfied

    rows = journey_services.journey_step_rows(world["attempt"])
    assert all(not row["verified"] for row in rows)
    assert not StepEvent.objects.filter(kind=StepEvent.Kind.VERIFIED).exists()


@pytest.mark.django_db
def test_eligible_listing_returns_only_own_unclaimed_in_window_creations(db):
    world = _world(db, "attrel")
    student = world["student"]
    mine = _create_ucr_for(student, "TEMPREL1")

    other = User.objects.create_user(username="attrel-other", email="o@e.test", password="x")
    theirs = _create_ucr_for(other, "TEMPREL9")

    response = _eligible(world, student)

    assert response.status_code == 200
    body = json.loads(response.content)
    ids = [row["record_id"] for row in body["eligible"]]
    assert mine.pk in ids
    assert theirs.pk not in ids


@pytest.mark.django_db
def test_attribution_of_another_students_creation_is_refused(db):
    world = _world(db, "attrown")
    other = User.objects.create_user(username="attrown-other", email="o@e.test", password="x")
    theirs = _create_ucr_for(other, "TEMPROWN9")

    response = _attribute(world, _ledger_of(theirs).pk, world["student"])

    assert response.status_code == 403
    assert not JourneyRecordAssociation.objects.exists()


@pytest.mark.django_db
def test_a_creation_outside_the_window_is_ineligible(db):
    """The window floor is the attempt's start (or the bound step's last
    opening). Pushing the attempt's start past a creation excludes that
    creation from eligibility and refusal follows at attribution."""
    from datetime import timedelta
    from django.utils import timezone

    world = _world(db, "attrwindow")
    student = world["student"]
    ucr = _create_ucr_for(student, "TEMPWIN1")
    attempt = world["attempt"]

    # The attempt's start moves past the creation: the record now predates
    # the window floor.
    JourneyAttempt.objects.filter(pk=attempt.pk).update(
        started_at=timezone.now() + timedelta(minutes=1),
    )
    attempt.refresh_from_db()

    response = _eligible(world, student)
    ids = [row["record_id"] for row in json.loads(response.content)["eligible"]]
    assert ucr.pk not in ids

    response = _attribute(world, _ledger_of(ucr).pk, student)
    assert response.status_code == 400


@pytest.mark.django_db
def test_a_record_claimed_by_another_attempt_cannot_be_reclaimed(db):
    world = _world(db, "attrclaim")
    student = world["student"]
    second = PracticalJourney.objects.create(
        programme_version=world["version"], course=world["journey"].course,
        code="attrclaim-2", title="Second journey", order=2,
        start_mode=PracticalJourney.StartMode.NEW_RECORD,
    )
    journey_services.assign_step(second, world["step"])
    second_role = journey_services.create_record_role(
        second, "declaration", "Fresh declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    journey_services.bind_condition(world["step"].conditions.get(), second_role)
    attempt_a = journey_services.get_or_create_attempt(world["enrolment"], world["journey"])
    attempt_b = journey_services.get_or_create_attempt(world["enrolment"], second)

    ucr = _create_ucr_for(student, "TEMPCLAIM1")
    attribution.attribute_creation(attempt_a, world["role"], _ledger_of(ucr).pk, student)

    with pytest.raises(attribution.AttributionError) as excinfo:
        attribution.attribute_creation(attempt_b, second_role, _ledger_of(ucr).pk, student)
    assert excinfo.value.code == "already_claimed"

    # The database constraint is the backstop even around the service.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyRecordAssociation.objects.create(
                journey_attempt=attempt_b,
                role=second_role,
                enrolment=world["enrolment"],
                programme_version=world["version"],
                record_kind="ucr",
                record_id=ucr.pk,
                assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
            )


@pytest.mark.django_db
def test_replacement_releases_the_old_claim_and_keeps_history(db):
    world = _world(db, "attrreplace")
    student = world["student"]
    first = _create_ucr_for(student, "TEMPREP1")
    second = _create_ucr_for(student, "TEMPREP2")
    role = world["role"]

    attribution.attribute_creation(world["attempt"], role, _ledger_of(first).pk, student)
    attribution.attribute_creation(world["attempt"], role, _ledger_of(second).pk, student)

    active = JourneyRecordAssociation.objects.get(
        journey_attempt=world["attempt"], role=role, is_active=True,
    )
    assert active.record_id == second.pk
    superseded = JourneyRecordAssociation.objects.get(
        journey_attempt=world["attempt"], role=role, is_active=False,
    )
    assert superseded.record_id == first.pk
    assert superseded.replaced_at is not None
    # The released record is eligible again for the owner.
    response = _eligible(world, student)
    ids = [row["record_id"] for row in json.loads(response.content)["eligible"]]
    assert first.pk in ids


@pytest.mark.django_db
def test_a_completed_attempt_refuses_attribution(db):
    world = _world(db, "attrcomplete")
    student = world["student"]
    attempt = world["attempt"]
    JourneyAttempt.objects.filter(pk=attempt.pk).update(
        status=JourneyAttempt.Status.COMPLETED, completed_at=attempt.started_at,
    )
    attempt.refresh_from_db()
    ucr = _create_ucr_for(student, "TEMPCOMP1")

    with pytest.raises(attribution.AttributionError) as excinfo:
        attribution.attribute_creation(attempt, world["role"], _ledger_of(ucr).pk, student)
    assert excinfo.value.code == "attempt_not_in_progress"


@pytest.mark.django_db
def test_a_deleted_record_fails_the_role_closed(db):
    world = _world(db, "attrdeleted")
    student = world["student"]
    ucr = _create_ucr_for(student, "TEMPGONE")
    attribution.attribute_creation(world["attempt"], world["role"], _ledger_of(ucr).pk, student)

    UcrDeclaration.objects.filter(pk=ucr.pk).delete()

    satisfied, message = journey_services.role_satisfied(world["attempt"], world["role"])
    assert not satisfied and "no longer exists" in message


@pytest.mark.django_db
def test_attribution_requires_the_student_and_post(client, db):
    world = _world(db, "attrpost")
    student = world["student"]
    ucr = _create_ucr_for(student, "TEMPPOST")
    ledger = _ledger_of(ucr)
    attribute_url = reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk])

    # Another student without an enrolment in this edition never resolves the
    # journey attempt for them.
    stranger = _student(db, "attrpost-other")
    stranger_client = Client()
    stranger_client.force_login(stranger)
    response = stranger_client.post(
        attribute_url, data=json.dumps({"creation_id": str(ledger.pk)}),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert not JourneyRecordAssociation.objects.exists()

    # CSRF is enforced for browser flows.
    enforcing = Client(enforce_csrf_checks=True)
    enforcing.force_login(student)
    response = enforcing.post(
        attribute_url, data=json.dumps({"creation_id": str(ledger.pk)}),
        content_type="application/json",
    )
    assert response.status_code == 403

    # GET never mutates.
    student_client = Client()
    student_client.force_login(student)
    response = student_client.get(attribute_url)
    assert response.status_code == 405
    assert JourneyRecordAssociation.objects.count() == 0


@pytest.mark.django_db
def test_the_eligible_listing_requires_the_student(client, db):
    world = _world(db, "attrelro")
    other = _student(db, "attrelro-other")
    client = Client()
    client.force_login(other)

    response = client.get(
        reverse("hybrid-journey-role-eligible", args=[world["journey"].pk, world["role"].pk]),
    )

    assert response.status_code == 403
