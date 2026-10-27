"""Stage 3.2 Checkpoint A — secure student attribution backend.

The creation ledger is evidence; attribution is the student's explicit,
server-validated claim written as a ``created_in_journey``
``JourneyRecordAssociation``; verification stays with the existing engines.
Attribution never writes a VERIFIED ``StepEvent`` and never completes a
practical step.
"""
import json
from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import attribution, journey_services, verification
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
    JourneyStep,
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
    """Creation eligibility is journey-attempt-scoped: pushing the attempt's
    start past a creation excludes it from eligibility, and attribution
    refuses it."""
    world = _world(db, "attrwindow")
    student = world["student"]
    ucr = _create_ucr_for(student, "TEMPWIN1")
    attempt = world["attempt"]

    # The attempt's start moves past the creation: the record now predates
    # the journey.
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
    # The edition is published, so structure rows are written directly — the
    # same "rows written around the service" pattern the publication tests use.
    # A step can belong to only one journey, so the second journey gets its own.
    second_lesson = HybridLesson.objects.create(
        module=world["step"].lesson.module, slug="attrclaim-2-lesson",
        title="Second journey lesson", order=2,
        summary="Summary.", theory="<p>Theory.</p>",
    )
    second_step = PracticalStep.objects.create(
        lesson=second_lesson, key="attrclaim-2-step", title="Second journey step",
        instruction="Create the second record.", outcome="The record is saved.",
        screen=SCREEN, order=1,
    )
    JourneyStep.objects.create(journey=second, step=second_step, journey_order=1)
    VerificationCondition.objects.create(
        step=second_step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", order=1,
    )
    second_role = JourneyRecordRole.objects.create(
        journey=second, key="declaration", label="Fresh declaration", record_kind="ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW, order=1,
    )
    JourneyConditionBinding.objects.create(
        condition=second_step.conditions.get(), role=second_role,
    )
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
    # The superseded claim still belongs to this attempt: the replaced
    # record cannot be re-claimed — by this attempt, another role, or any
    # other attempt (immutable claim history).
    response = _eligible(world, student)
    ids = [row["record_id"] for row in json.loads(response.content)["eligible"]]
    assert first.pk not in ids


@pytest.mark.django_db
def test_a_replaced_record_cannot_be_claimed_by_another_role_in_the_same_attempt(db):
    """Immutable claim history: the superseded claim on the replaced record
    blocks a second role in the same attempt from claiming it — at the
    service level and at the database level."""
    world = _world(db, "attrsameattempt")
    student = world["student"]
    first = _create_ucr_for(student, "TEMPSAME1")
    second = _create_ucr_for(student, "TEMPSAME2")
    role = world["role"]
    other_role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="declaration-2", label="Second role",
        record_kind="ucr", required=False,
        creation_mode=JourneyRecordRole.CreationMode.NEW, order=2,
    )
    attribution.attribute_creation(world["attempt"], role, _ledger_of(first).pk, student)
    attribution.attribute_creation(world["attempt"], role, _ledger_of(second).pk, student)

    with pytest.raises(attribution.AttributionError) as excinfo:
        attribution.attribute_creation(world["attempt"], other_role, _ledger_of(first).pk, student)
    assert excinfo.value.code == "already_claimed"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyRecordAssociation.objects.create(
                journey_attempt=world["attempt"],
                role=other_role,
                enrolment=world["enrolment"],
                programme_version=world["version"],
                record_kind="ucr",
                record_id=first.pk,
                assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
            )


@pytest.mark.django_db
def test_reopening_the_bound_step_keeps_the_attributed_record_valid(db):
    """Re-entry is navigation, not a new creation obligation.

    Creation eligibility is journey-attempt-scoped, so reopening the bound
    step leaves the attributed record in place and leaves the learner's other
    creations claimable. What re-entry does change is the step's own freshness
    bound: work last done before the re-entry no longer passes Check-My-Work,
    and the learner has to touch the record again.
    """
    world = _world(db, "attrewindow")
    student = world["student"]
    attempt = world["attempt"]
    step = world["step"]
    ucr = _create_ucr_for(student, "TEMPREWIN", exporter_name="ACME Trading")

    JourneyAttempt.objects.filter(pk=attempt.pk).update(
        started_at=timezone.now() - timedelta(hours=1),
    )
    attempt.refresh_from_db()
    lesson_attempt = LessonAttempt.objects.create(enrolment=world["enrolment"], lesson=step.lesson)

    attribution.attribute_creation(attempt, world["role"], _ledger_of(ucr).pk, student)
    attempt.refresh_from_db()

    # 1. The attributed record still satisfies the role after re-entry.
    verification.record_open(lesson_attempt, step)
    satisfied, message = journey_services.role_satisfied(attempt, world["role"])
    assert satisfied, message
    assert JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt, role=world["role"], is_active=True, record_id=ucr.pk,
    ).exists()

    # 2. Re-entry does not push the claimability of this journey's creations:
    # a record made earlier in the attempt is still listed and still claims.
    second = _create_ucr_for(student, "TEMPREWIN2", exporter_name="OTHER TRADER")
    ids = [row["record_id"] for row in attribution.eligible_for_view(attempt, world["role"])]
    assert second.pk in ids
    attribution.attribute_creation(attempt, world["role"], _ledger_of(second).pk, student)
    attempt.refresh_from_db()
    assert journey_services.role_satisfied(attempt, world["role"])[0]

    # 3. Re-entry authorizes nothing on the step itself: the record was last
    # worked before the learner came back, so the check still fails and no
    # VERIFIED event is written.
    result = verification.verify_step(lesson_attempt, step)
    assert not result["passed"]
    assert not StepEvent.objects.filter(
        attempt=lesson_attempt, step=step, kind=StepEvent.Kind.VERIFIED,
    ).exists()

    # Working the record after re-entry is what satisfies the step.
    ucr.refresh_from_db()
    ucr.save()
    assert verification.verify_step(lesson_attempt, step)["passed"]


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
    # The project's 403 handler redirects authenticated portal users with a
    # warning; nothing is attributed either way.
    assert response.status_code == 302
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

    # The project's 403 handler redirects authenticated portal users with a
    # warning instead of rendering a bare 403 page.
    assert response.status_code == 302


# --- Checkpoint B: student attribution interface -----------------------------


@pytest.mark.django_db
def test_journey_page_displays_eligible_records_with_distinguishing_details(client, db):
    world = _world(db, "attrui-list")
    record = _create_ucr_for(world["student"], "TEMP-UI-001", exporter_name="ACME Trading")
    client.force_login(world["student"])

    response = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk]))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Fresh declaration" in html
    assert "UCR declaration" in html
    assert "No record attributed" in html
    assert "Select record" in html
    assert record.temp_no in html
    assert "Draft" in html


@pytest.mark.django_db
def test_journey_page_explains_when_no_eligible_record_exists(client, db):
    world = _world(db, "attrui-empty")
    client.force_login(world["student"])

    response = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk]))

    assert "No eligible records are available" in response.content.decode()


@pytest.mark.django_db
def test_successful_interface_attribution_refreshes_to_current_record_state(client, db):
    world = _world(db, "attrui-success")
    record = _create_ucr_for(world["student"], "TEMP-UI-002", exporter_name="ACME Trading")
    client.force_login(world["student"])

    response = client.post(
        reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk]),
        data=json.dumps({"creation_id": str(_ledger_of(record).pk)}),
        content_type="application/json",
    )
    assert response.status_code == 200

    page = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk])).content.decode()
    assert "Record attributed but not yet verified" in page
    assert f"Current record: #{record.pk}" in page
    assert "Replace record" in page
    assert "Practical step verified" not in page


@pytest.mark.django_db
def test_interface_allows_backend_validated_replacement(client, db):
    world = _world(db, "attrui-replace")
    first = _create_ucr_for(world["student"], "TEMP-UI-003", exporter_name="ACME Trading")
    second = _create_ucr_for(world["student"], "TEMP-UI-004", exporter_name="ACME Trading")
    client.force_login(world["student"])
    endpoint = reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk])

    assert client.post(endpoint, data=json.dumps({"creation_id": str(_ledger_of(first).pk)}),
                       content_type="application/json").status_code == 200
    assert client.post(endpoint, data=json.dumps({"creation_id": str(_ledger_of(second).pk)}),
                       content_type="application/json").status_code == 200

    active = JourneyRecordAssociation.objects.get(
        journey_attempt=world["attempt"], role=world["role"], is_active=True,
    )
    assert active.record_id == second.pk
    assert JourneyRecordAssociation.objects.filter(
        journey_attempt=world["attempt"], role=world["role"], is_active=False,
        record_id=first.pk,
    ).exists()


@pytest.mark.django_db
def test_stale_interface_selection_returns_a_controlled_error(client, db):
    world = _world(db, "attrui-stale")
    record = _create_ucr_for(world["student"], "TEMP-UI-005", exporter_name="ACME Trading")
    client.force_login(world["student"])
    JourneyAttempt.objects.filter(pk=world["attempt"].pk).update(
        started_at=timezone.now() + timedelta(minutes=1),
    )

    response = client.post(
        reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk]),
        data=json.dumps({"creation_id": str(_ledger_of(record).pk)}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["code"] == "outside_window"
    assert "before the journey started" in response.json()["error"]


@pytest.mark.django_db
def test_instructor_review_session_cannot_list_or_attribute_records(client, db):
    world = _world(db, "attrui-review")
    record = _create_ucr_for(world["student"], "TEMP-UI-006", exporter_name="ACME Trading")
    client.force_login(world["student"])
    session = client.session
    session["simulator_review_user_id"] = str(world["student"].pk)
    session.save()
    eligible_url = reverse(
        "hybrid-journey-role-eligible", args=[world["journey"].pk, world["role"].pk],
    )
    attribute_url = reverse(
        "hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk],
    )

    assert client.get(eligible_url).status_code == 403
    response = client.post(
        attribute_url, data=json.dumps({"creation_id": str(_ledger_of(record).pk)}),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert not JourneyRecordAssociation.objects.exists()
    page = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk])).content.decode()
    assert "Instructor review is view-only" in page
    assert "<form data-attribution-form" not in page


@pytest.mark.django_db
def test_attribution_interface_preserves_csrf_and_post_only_contract(client, db):
    world = _world(db, "attrui-methods")
    record = _create_ucr_for(world["student"], "TEMP-UI-007", exporter_name="ACME Trading")
    endpoint = reverse(
        "hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk],
    )
    enforcing = Client(enforce_csrf_checks=True)
    enforcing.force_login(world["student"])

    assert enforcing.get(endpoint).status_code == 405
    response = enforcing.post(
        endpoint, data=json.dumps({"creation_id": str(_ledger_of(record).pk)}),
        content_type="application/json",
    )
    assert response.status_code == 403
    assert not JourneyRecordAssociation.objects.exists()


@pytest.mark.django_db
def test_interface_distinguishes_attribution_from_step_verification(client, db):
    world = _world(db, "attrui-state")
    record = _create_ucr_for(world["student"], "TEMP-UI-008", exporter_name="ACME Trading")
    attribution.attribute_creation(
        world["attempt"], world["role"], _ledger_of(record).pk, world["student"],
    )
    client.force_login(world["student"])
    journey_url = reverse("hybrid-journey-student", args=[world["journey"].pk])

    before = client.get(journey_url).content.decode()
    assert "Record attributed but not yet verified" in before
    assert "Practical step verified" not in before

    lesson_attempt = LessonAttempt.objects.create(
        enrolment=world["enrolment"], lesson=world["step"].lesson,
    )
    StepEvent.objects.create(
        attempt=lesson_attempt, step=world["step"], kind=StepEvent.Kind.VERIFIED,
    )
    after = client.get(journey_url).content.decode()
    assert "Practical step verified" in after
    assert "Record attributed but not yet verified" not in after


@pytest.mark.django_db
def test_existing_journey_step_content_still_renders_with_attribution_controls(client, db):
    world = _world(db, "attrui-regression")
    client.force_login(world["student"])

    html = client.get(
        reverse("hybrid-journey-student", args=[world["journey"].pk]),
    ).content.decode()

    assert world["journey"].title in html
    assert world["step"].title in html
    assert "Continue in the workspace" in html
