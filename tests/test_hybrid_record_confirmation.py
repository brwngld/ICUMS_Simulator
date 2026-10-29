"""Batch 7: confirming which simulator record a journey role is about.

The lesson workspace's step card and the journey page ask the learner the same
question — which of my records is this check about — and both answer it through
one service call, so a record the picker calls fresh is a record the check
measures the same way. No new kind of row appears: a NEW-mode role is claimed
from the creation ledger, an EXISTING-mode role is authorised through the journey
service's own replacement, and either way one active association per role is the
invariant, with the superseded row kept as history.
"""
import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import attribution, journey_services
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
    SimulatorRecordCreation,
    VerificationCondition,
)
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration

SCREEN = "single-window-overview"
EXPORTER = "ACME Trading"


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _declaration(owner, temp_no):
    """Create through the real model, so the creation ledger is written exactly
    as it is when the learner saves the record in the simulator."""
    return UcrDeclaration.objects.create(
        owner=owner, temp_no=temp_no, regime="CO", exporter_name=EXPORTER,
    )


def _age(record, moment):
    """Put a record's activity in the past, the way an old saved declaration
    arrives: the auto timestamps are bypassed, nothing else changes."""
    UcrDeclaration.objects.filter(pk=record.pk).update(created_at=moment, updated_at=moment)
    record.refresh_from_db()
    return record


def _work(record):
    """The learner edits the record in the simulator: its activity moves to now."""
    record.save()
    record.refresh_from_db()
    return record


def _creation_of(record):
    return SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)


def _world(db, seed, creation_mode=JourneyRecordRole.CreationMode.EXISTING, gated=False):
    """A published two-step journey whose first step checks a saved UCR against
    one role of the given creation mode, with the learner enrolled.

    ``gated`` adds a second required role that the second step waits on, so the
    journey's own refusal has a real cause to report.
    """
    programme = Programme.objects.create(
        name=f"Confirm {seed}", code=seed, learning_track=Programme.Track.HYBRID,
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
    first = PracticalStep.objects.create(
        lesson=lesson, key=f"{seed}-one", title="Open the declaration",
        instruction="Create it.", outcome="Saved.", screen=SCREEN, order=1,
    )
    second = PracticalStep.objects.create(
        lesson=lesson, key=f"{seed}-two", title="Attach the packing list",
        instruction="Attach it.", outcome="Attached.", screen=SCREEN, order=2,
    )
    condition = VerificationCondition.objects.create(
        step=first, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
        required_status="draft", expected_fields={"exporter_name": EXPORTER}, order=1,
    )
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-j", title=f"{seed} journey",
        order=1, start_mode=PracticalJourney.StartMode.NEW_RECORD,
    )
    assignment_one = journey_services.assign_step(journey, first)
    assignment_two = journey_services.assign_step(journey, second)
    role = journey_services.create_record_role(
        journey, "declaration", "Your declaration", "ucr", required=True,
        creation_mode=creation_mode,
    )
    journey_services.bind_condition(condition, role)
    if gated:
        gate_role = journey_services.create_record_role(
            journey, "packing", "The packing list", "ucr", required=True,
            creation_mode=JourneyRecordRole.CreationMode.EXISTING,
        )
        journey_services.add_dependency(
            journey, assignment_one, assignment_two,
            JourneyDependency.DependencyType.RECORD_AVAILABLE, required_record_role=gate_role,
        )
    for row in (course, module, lesson):
        row.is_published = True
        row.save(update_fields=("is_published",))
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    learner = _learner(db, f"{seed}-learner")
    enrolment = Enrolment.objects.create(student=learner, programme_version=version)
    return {
        "version": version, "course": course, "lesson": lesson, "journey": journey,
        "role": role, "condition": condition, "first": first, "second": second,
        "assignment_one": assignment_one, "assignment_two": assignment_two,
        "learner": learner, "enrolment": enrolment,
    }


def _attempt(world):
    return journey_services.get_or_create_attempt(world["enrolment"], world["journey"])


def _open_workspace(client, world):
    """The learner's first real act in the lesson: open it. This is what has to
    start the journey attempt, so a record made afterwards is inside the window
    the check will read."""
    client.force_login(world["learner"])
    client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    return LessonAttempt.objects.get(enrolment=world["enrolment"], lesson=world["lesson"])


def _post(client, action, attempt, index):
    return client.post(reverse(f"hybrid-step-{action}", args=[attempt.pk, index]))


def _confirm(client, world, payload):
    return client.post(
        reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk]),
        data=json.dumps(payload),
        content_type="application/json",
    )


# --- The rows the learner is shown ----------------------------------------------


@pytest.mark.django_db
def test_an_existing_role_lists_every_record_the_learner_owns(db):
    world = _world(db, "conf-list")
    attempt = _attempt(world)
    mine = _declaration(world["learner"], "TEMP-CONF-1")
    stale = _age(_declaration(world["learner"], "TEMP-CONF-2"), attempt.started_at - timedelta(days=1))
    theirs = _declaration(_learner(db, "conf-list-other"), "TEMP-CONF-3")

    rows = attribution.attributable_rows(attempt, world["role"])

    assert [row["record_id"] for row in rows] == [mine.pk, stale.pk]
    assert theirs.pk not in [row["record_id"] for row in rows]
    assert rows[0]["record_label"] == "TEMP-CONF-1"
    assert rows[0]["record_status"] == "Draft"
    assert rows[0]["in_window"] is True and rows[0]["chosen"] is False
    assert rows[1]["in_window"] is False


@pytest.mark.django_db
def test_the_window_a_row_is_measured_by_is_the_one_the_step_will_use(db):
    """The picker answers for one step: a record last worked before that floor is
    listed, but marked outside the window, because the check on it would refuse
    the record as stale."""
    world = _world(db, "conf-window")
    attempt = _attempt(world)
    record = _work(_age(_declaration(world["learner"], "TEMP-CONF-4"), attempt.started_at - timedelta(days=1)))

    assert attribution.attributable_rows(attempt, world["role"])[0]["in_window"] is True
    assert attribution.attributable_rows(
        attempt, world["role"], window_start=timezone.now() + timedelta(minutes=30),
    )[0]["in_window"] is False


@pytest.mark.django_db
def test_a_new_role_still_lists_only_unclaimed_creations(db):
    world = _world(db, "conf-new", creation_mode=JourneyRecordRole.CreationMode.NEW)
    attempt = _attempt(world)
    record = _declaration(world["learner"], "TEMP-CONF-5")

    rows = attribution.attributable_rows(attempt, world["role"])

    assert [(row["record_id"], row["creation_id"]) for row in rows] == [(record.pk, _creation_of(record).pk)]
    attribution.attribute_record(
        attempt, world["role"], creation_id=rows[0]["creation_id"], student=world["learner"],
    )
    assert attribution.attributable_rows(attempt, world["role"]) == []


@pytest.mark.django_db
def test_the_confirmed_record_is_marked_in_the_list(db):
    world = _world(db, "conf-chosen")
    attempt = _attempt(world)
    record = _declaration(world["learner"], "TEMP-CONF-6")

    attribution.attribute_record(attempt, world["role"], record_id=record.pk, student=world["learner"])

    rows = attribution.attributable_rows(attempt, world["role"])
    assert [(row["record_id"], row["chosen"]) for row in rows] == [(record.pk, True)]


# --- Confirming a record ---------------------------------------------------------


@pytest.mark.django_db
def test_confirming_keeps_one_active_association_and_keeps_history(db):
    world = _world(db, "conf-single")
    attempt = _attempt(world)
    first = _declaration(world["learner"], "TEMP-CONF-7")
    second = _declaration(world["learner"], "TEMP-CONF-8")

    attribution.attribute_record(attempt, world["role"], record_id=first.pk, student=world["learner"])
    attribution.attribute_record(attempt, world["role"], record_id=second.pk, student=world["learner"])

    active = JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt, role=world["role"], is_active=True,
    )
    assert len(active) == 1
    assert active[0].record_id == second.pk
    assert active[0].assignment_source == JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING
    assert active[0].assigned_by_id == world["learner"].pk
    assert JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt, role=world["role"], is_active=False, record_id=first.pk,
    ).exists()


@pytest.mark.django_db
def test_a_new_record_role_refuses_a_direct_record_choice(db):
    world = _world(db, "conf-newrefuse", creation_mode=JourneyRecordRole.CreationMode.NEW)
    attempt = _attempt(world)
    record = _declaration(world["learner"], "TEMP-CONF-9")

    with pytest.raises(attribution.AttributionError) as refusal:
        attribution.attribute_record(attempt, world["role"], record_id=record.pk, student=world["learner"])

    assert "created within the journey" in refusal.value.message
    assert not JourneyRecordAssociation.objects.exists()


@pytest.mark.django_db
def test_an_existing_role_refuses_a_creation_claim(db):
    world = _world(db, "conf-oldrefuse")
    attempt = _attempt(world)
    creation_id = _creation_of(_declaration(world["learner"], "TEMP-CONF-10")).pk

    with pytest.raises(attribution.AttributionError) as refusal:
        attribution.attribute_record(attempt, world["role"], creation_id=creation_id, student=world["learner"])

    assert refusal.value.code == "creation_mode_not_new"
    assert not JourneyRecordAssociation.objects.exists()


@pytest.mark.django_db
def test_confirming_another_learners_record_is_refused(db):
    world = _world(db, "conf-theirs")
    attempt = _attempt(world)
    theirs = _declaration(_learner(db, "conf-theirs-other"), "TEMP-CONF-11")

    with pytest.raises(PermissionDenied):
        attribution.attribute_record(attempt, world["role"], record_id=theirs.pk, student=world["learner"])


@pytest.mark.django_db
def test_a_malformed_record_choice_is_a_controlled_refusal(db):
    world = _world(db, "conf-malformed")
    attempt = _attempt(world)

    with pytest.raises(attribution.AttributionError) as refusal:
        attribution.attribute_record(attempt, world["role"], record_id="not-a-record", student=world["learner"])

    assert refusal.value.code == "record_missing"


@pytest.mark.django_db
def test_choosing_nothing_is_a_controlled_refusal(db):
    world = _world(db, "conf-nothing")
    attempt = _attempt(world)

    with pytest.raises(attribution.AttributionError) as refusal:
        attribution.attribute_record(attempt, world["role"], student=world["learner"])

    assert refusal.value.code == "no_selection"


# --- The workspace and the endpoints --------------------------------------------


@pytest.mark.django_db
def test_opening_the_lesson_opens_the_journey_attempt(client, db):
    """The attempt has to exist before the learner makes the record, because its
    start is the floor of the window every later check reads."""
    world = _world(db, "conf-attempt")
    assert not JourneyAttempt.objects.filter(enrolment=world["enrolment"]).exists()

    _open_workspace(client, world)

    attempt = JourneyAttempt.objects.get(enrolment=world["enrolment"], journey=world["journey"])
    assert attempt.started_at is not None
    assert attempt.current_journey_step_id == world["assignment_one"].pk


@pytest.mark.django_db
def test_reopening_the_lesson_resumes_the_same_attempt(client, db):
    world = _world(db, "conf-resume")
    _open_workspace(client, world)

    client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))

    assert JourneyAttempt.objects.filter(enrolment=world["enrolment"], journey=world["journey"]).count() == 1


@pytest.mark.django_db
def test_the_endpoint_confirms_an_existing_record(client, db):
    world = _world(db, "conf-http")
    _open_workspace(client, world)
    record = _declaration(world["learner"], "TEMP-CONF-12")

    response = _confirm(client, world, {"record_id": record.pk})

    assert response.status_code == 200
    assert response.json()["attributed"] is True
    association = JourneyRecordAssociation.objects.get(journey_attempt__journey=world["journey"], is_active=True)
    assert association.record_id == record.pk


@pytest.mark.django_db
def test_the_endpoint_still_accepts_a_creation_claim(client, db):
    world = _world(db, "conf-http-new", creation_mode=JourneyRecordRole.CreationMode.NEW)
    _open_workspace(client, world)
    record = _declaration(world["learner"], "TEMP-CONF-13")

    response = _confirm(client, world, {"creation_id": str(_creation_of(record).pk)})

    assert response.status_code == 200
    assert JourneyRecordAssociation.objects.get(is_active=True).record_id == record.pk


@pytest.mark.django_db
def test_the_endpoint_refuses_an_empty_choice(client, db):
    world = _world(db, "conf-http-empty")
    _open_workspace(client, world)

    response = _confirm(client, world, {})

    assert response.status_code == 400
    assert response.json()["code"] == "no_selection"


# --- The picker the learner reads ------------------------------------------------


@pytest.mark.django_db
def test_the_step_card_lists_the_records_this_step_is_about(client, db):
    """The confirmation lives beside the simulator screen it belongs to: the
    workspace's own step card names the role and offers the learner's records."""
    world = _world(db, "conf-render")
    _open_workspace(client, world)
    record = _declaration(world["learner"], "TEMP-CONF-18")

    page = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk])).content.decode()

    assert "Required records" in page
    assert "Your declaration" in page
    assert 'data-attribution-key="record_id"' in page
    assert f'value="{record.pk}"' in page
    assert "TEMP-CONF-18" in page
    assert reverse(
        "hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk],
    ) in page
    assert "js/hybrid-attribution.js" in page


@pytest.mark.django_db
def test_the_step_card_lists_an_aged_record_and_marks_it(client, db):
    """Ruling 3: every record the learner owns is shown, and the ones the check
    would refuse as stale say so instead of quietly disappearing."""
    world = _world(db, "conf-render-old")
    lesson_attempt = _open_workspace(client, world)
    attempt = _attempt(world)
    _post(client, "open", lesson_attempt, 0)
    _age(_declaration(world["learner"], "TEMP-CONF-19"), attempt.started_at - timedelta(days=3))

    page = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk])).content.decode()

    assert "TEMP-CONF-19" in page
    assert "Changed before this step." in page


@pytest.mark.django_db
def test_the_journey_page_offers_the_same_choices(client, db):
    """One lister, one payload contract on both surfaces: the journey page's
    choices are the same rows, and a NEW-mode role still claims a creation."""
    world = _world(db, "conf-render-journey", creation_mode=JourneyRecordRole.CreationMode.NEW)
    _open_workspace(client, world)
    record = _declaration(world["learner"], "TEMP-CONF-20")

    page = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk])).content.decode()

    assert 'data-attribution-key="creation_id"' in page
    assert f'value="{_creation_of(record).pk}"' in page
    assert "js/hybrid-attribution.js" in page


@pytest.mark.django_db
def test_no_page_offers_a_choice_the_learner_cannot_answer(client, db):
    """Instructor review and the draft preview render the same lesson without
    writing an attempt or claiming a record on the learner's behalf."""
    world = _world(db, "conf-render-view")
    _declaration(world["learner"], "TEMP-CONF-21")

    review = Client()
    review.force_login(world["learner"])
    session = review.session
    session["simulator_review_user_id"] = str(world["learner"].pk)
    session.save()
    review_page = review.get(reverse("hybrid-workspace", args=[world["lesson"].pk])).content.decode()
    assert "<form data-attribution-form" not in review_page
    assert not JourneyAttempt.objects.filter(enrolment=world["enrolment"]).exists()

    instructor = _learner(db, "conf-render-teacher")
    instructor.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    preview = Client()
    preview.force_login(instructor)
    preview_page = preview.get(reverse("hybrid-lesson-preview", args=[world["lesson"].pk])).content.decode()
    assert "<form data-attribution-form" not in preview_page


# --- The end to end the brief asks for ------------------------------------------


@pytest.mark.django_db
def test_confirming_the_record_lets_the_step_pass_and_the_journey_move(client, db):
    """Open the lesson, work the record, confirm it, check, move on: the journey
    position follows the lesson position because Next advances both."""
    world = _world(db, "conf-flow")
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    record = _declaration(world["learner"], "TEMP-CONF-14")
    assert _confirm(client, world, {"record_id": record.pk}).status_code == 200

    checked = _post(client, "check", lesson_attempt, 0)

    assert checked.status_code == 200, checked.content
    assert checked.json()["passed"] is True

    advanced = _post(client, "advance", lesson_attempt, 0)
    assert advanced.status_code == 200
    assert advanced.json()["journey_moved"] is True
    assert advanced.json()["journey_message"] == "Advanced to the next step."
    attempt = JourneyAttempt.objects.get(enrolment=world["enrolment"], journey=world["journey"])
    assert attempt.current_journey_step_id == world["assignment_two"].pk


@pytest.mark.django_db
def test_an_unconfirmed_record_keeps_the_step_and_the_journey_where_they_are(client, db):
    world = _world(db, "conf-unconfirmed")
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    _declaration(world["learner"], "TEMP-CONF-15")

    refused = _post(client, "check", lesson_attempt, 0)

    assert refused.status_code == 403
    assert refused.json()["code"] == "association_missing"
    assert _post(client, "advance", lesson_attempt, 0).status_code == 403
    attempt = JourneyAttempt.objects.get(enrolment=world["enrolment"], journey=world["journey"])
    assert attempt.current_journey_step_id == world["assignment_one"].pk


@pytest.mark.django_db
def test_the_journey_reports_its_own_refusal_when_the_next_step_waits(client, db):
    """The lesson can move while the journey holds, and what the learner hears is
    the journey engine's own reason, naming the record role still outstanding."""
    world = _world(db, "conf-gated", gated=True)
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    record = _declaration(world["learner"], "TEMP-CONF-16")
    _confirm(client, world, {"record_id": record.pk})
    assert _post(client, "check", lesson_attempt, 0).json()["passed"] is True

    advanced = _post(client, "advance", lesson_attempt, 0)

    assert advanced.json()["allowed"] is True
    assert advanced.json()["journey_moved"] is False
    assert "Attach the packing list" in advanced.json()["journey_message"]
    assert "record role" in advanced.json()["journey_message"]
    attempt = JourneyAttempt.objects.get(enrolment=world["enrolment"], journey=world["journey"])
    assert attempt.current_journey_step_id == world["assignment_one"].pk


@pytest.mark.django_db
def test_a_step_of_an_unassigned_lesson_keeps_the_legacy_engine(client, db):
    """Compatibility: a lesson whose steps no journey claimed stays a plain
    lesson — no attempt is opened for it, and its saved-record check keeps the
    owner-wide engine it always had."""
    world = _world(db, "conf-plain")
    JourneyStep.objects.filter(journey=world["journey"]).delete()
    client.force_login(world["learner"])
    client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert not JourneyAttempt.objects.filter(enrolment=world["enrolment"]).exists()
    lesson_attempt = LessonAttempt.objects.get(enrolment=world["enrolment"], lesson=world["lesson"])
    _post(client, "open", lesson_attempt, 0)
    _declaration(world["learner"], "TEMP-CONF-17")

    checked = _post(client, "check", lesson_attempt, 0)

    assert checked.json()["passed"] is True
    assert "journey_complete" not in checked.json()
    advanced = _post(client, "advance", lesson_attempt, 0)
    assert advanced.json()["allowed"] is True
    assert advanced.json()["journey_moved"] is False
    assert advanced.json()["journey_message"] == ""


@pytest.mark.django_db
def test_the_roadmap_never_names_a_step_past_the_last_one(client, db):
    """Every step verified while the journey itself is still open would read as
    "Step 2 of 1": the position is where the learner stands, so it stops at the
    last step and the journey's own completion stays the journey's word."""
    world = _world(db, "conf-count")
    JourneyStep.objects.filter(journey=world["journey"], step=world["second"]).delete()
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    record = _declaration(world["learner"], "TEMP-CONF-22")
    _confirm(client, world, {"record_id": record.pk})
    assert _post(client, "check", lesson_attempt, 0).json()["passed"] is True

    page = client.get(reverse("hybrid-roadmap")).content.decode()

    assert "Step 1 of 1" in page
    assert "Step 2 of 1" not in page
