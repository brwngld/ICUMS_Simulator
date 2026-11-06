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
from django.templatetags.static import static
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
    assert static("js/hybrid-attribution.js") in page


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
    assert static("js/hybrid-attribution.js") in page


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
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["second"].pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 1
    assert resumed.context["attempt"]["id"] == str(lesson_attempt.pk)


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
@pytest.mark.parametrize("markup", [False, True])
def test_the_journey_refusal_holds_both_positions_until_a_retry_can_advance(client, db, markup):
    world = _world(db, "conf-gated", gated=True)
    if markup:
        world["second"].title += " <img src=x onerror=alert(1)>"
        world["second"].save(update_fields=("title",))
        world["journey"].record_roles.filter(key="packing").update(label="<b>Required record</b>")
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    record = _declaration(world["learner"], "TEMP-CONF-16")
    _confirm(client, world, {"record_id": record.pk})
    assert _post(client, "check", lesson_attempt, 0).json()["passed"] is True
    attempt = _attempt(world)
    history = list(lesson_attempt.step_events.values())
    associations = list(JourneyRecordAssociation.objects.filter(journey_attempt=attempt).values())

    for _ in range(2):
        refused = _post(client, "advance", lesson_attempt, 0)
        assert refused.status_code == 403
        assert refused.json()["allowed"] is False
        assert refused.json()["journey_moved"] is False
        assert "Attach the packing list" in refused.json()["message"]
        assert "record role" in refused.json()["message"]
        if markup:
            assert "<img" not in refused.json()["message"]
            assert "<b>" not in refused.json()["message"]
            assert "&lt;img" in refused.json()["message"]
            assert "&lt;b&gt;Required record&lt;/b&gt;" in refused.json()["message"]
            assert "<img" in refused.json()["journey_message"]
        lesson_attempt.refresh_from_db()
        attempt.refresh_from_db()
        assert lesson_attempt.current_step_id == world["first"].pk
        assert attempt.current_journey_step_id == world["assignment_one"].pk
        resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
        assert resumed.context["attempt"]["current_index"] == 0
        assert resumed.context["attempt"]["id"] == str(lesson_attempt.pk)

    assert list(lesson_attempt.step_events.values()) == history
    assert list(JourneyRecordAssociation.objects.filter(journey_attempt=attempt).values()) == associations
    gate_role = world["journey"].record_roles.get(key="packing")
    attribution.attribute_record(attempt, gate_role, record_id=record.pk, student=world["learner"])

    retried = _post(client, "advance", lesson_attempt, 0)

    assert retried.status_code == 200
    assert retried.json()["allowed"] is True
    lesson_attempt.refresh_from_db()
    attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["second"].pk
    assert attempt.current_journey_step_id == world["assignment_two"].pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 1


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
    assert _post(client, "advance", lesson_attempt, 0).json()["allowed"] is True
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["second"].pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 1
    assert not JourneyAttempt.objects.filter(enrolment=world["enrolment"]).exists()


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


@pytest.fixture
def checked_progression(client, db):
    world = _world(db, "conf-advance")
    lesson_attempt = _open_workspace(client, world)
    assert _post(client, "open", lesson_attempt, 0).status_code == 200
    record = _declaration(world["learner"], "TEMP-CONF-ADVANCE")
    assert _confirm(client, world, {"record_id": record.pk}).status_code == 200
    assert _post(client, "check", lesson_attempt, 0).json()["passed"] is True
    return world, lesson_attempt


@pytest.mark.django_db
def test_advance_retries_never_move_a_different_journey_step_or_rewind_resume(client, checked_progression):
    world, lesson_attempt = checked_progression
    third = PracticalStep.objects.create(
        lesson=world["lesson"], key="third", title="Finish", order=3, screen=SCREEN,
    )
    third_assignment = JourneyStep.objects.create(journey=world["journey"], step=third, journey_order=3)
    assert _post(client, "advance", lesson_attempt, 0).json()["journey_moved"] is True
    assert _post(client, "open", lesson_attempt, 1).status_code == 200
    attempt = _attempt(world)
    activity = attempt.last_activity_at
    history = list(lesson_attempt.step_events.values())

    retried = _post(client, "advance", lesson_attempt, 0)

    assert retried.status_code == 200
    assert retried.json()["allowed"] is True
    assert retried.json()["journey_moved"] is False
    attempt.refresh_from_db()
    lesson_attempt.refresh_from_db()
    assert attempt.current_journey_step_id == world["assignment_two"].pk
    assert attempt.last_activity_at == activity
    assert lesson_attempt.current_step_id == world["second"].pk
    assert list(lesson_attempt.step_events.values()) == history

    assert _post(client, "advance", lesson_attempt, 1).json()["journey_moved"] is True
    assert _post(client, "advance", lesson_attempt, 0).json()["allowed"] is True
    attempt.refresh_from_db()
    lesson_attempt.refresh_from_db()
    assert attempt.current_journey_step_id == third_assignment.pk
    assert lesson_attempt.current_step_id == third.pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 2
    assert resumed.context["attempt"]["id"] == str(lesson_attempt.pk)


@pytest.mark.django_db
def test_replaying_equal_order_steps_keeps_the_canonical_resume_position(client, db):
    world = _world(db, "conf-equal-order")
    world["condition"].delete()
    JourneyStep.objects.filter(journey=world["journey"]).delete()
    # Identical titles force canonical ordering to fall through to the same
    # (order, id) tie-breaker the lesson uses, so indices stay aligned.
    shared_title = "Equal-order step"
    world["first"].title = shared_title
    world["second"].title = shared_title
    PracticalStep.objects.bulk_update([world["first"], world["second"]], ["title"])
    PracticalStep.objects.create(
        lesson=world["lesson"], key="third", title=shared_title, order=1, screen=SCREEN,
    )
    world["lesson"].practical_steps.update(order=1)
    steps = list(world["lesson"].practical_steps.order_by("order", "id"))
    assignments = [
        JourneyStep.objects.create(journey=world["journey"], step=step, journey_order=index + 1)
        for index, step in enumerate(steps)
    ]
    lesson_attempt = _open_workspace(client, world)
    for index in range(2):
        assert _post(client, "open", lesson_attempt, index).status_code == 200
        assert _post(client, "advance", lesson_attempt, index).json()["allowed"] is True

    assert _post(client, "advance", lesson_attempt, 0).json()["allowed"] is True

    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == steps[2].pk
    assert _attempt(world).current_journey_step_id == assignments[2].pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 2


@pytest.mark.django_db
def test_a_future_step_cannot_advance_the_current_journey_step(client, checked_progression):
    world, lesson_attempt = checked_progression

    refused = _post(client, "advance", lesson_attempt, 1)

    assert refused.status_code == 403
    assert refused.json()["allowed"] is False
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert _attempt(world).current_journey_step_id == world["assignment_one"].pk


@pytest.mark.django_db
def test_a_missing_journey_attempt_is_not_a_non_journey_fallback(client, db):
    world = _world(db, "conf-missing")
    world["condition"].delete()
    lesson_attempt = LessonAttempt.objects.create(
        enrolment=world["enrolment"], lesson=world["lesson"], current_step=world["first"],
    )
    client.force_login(world["learner"])

    refused = _post(client, "advance", lesson_attempt, 0)

    assert refused.status_code == 403
    assert refused.json()["allowed"] is False
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert not JourneyAttempt.objects.filter(enrolment=world["enrolment"]).exists()


@pytest.mark.django_db
def test_a_condition_free_journey_step_still_waits_for_its_opening(client, db):
    world = _world(db, "conf-unopened")
    world["condition"].delete()
    lesson_attempt = _open_workspace(client, world)

    refused = _post(client, "advance", lesson_attempt, 0)

    assert refused.status_code == 403
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert _attempt(world).current_journey_step_id == world["assignment_one"].pk
    assert _post(client, "open", lesson_attempt, 0).status_code == 200
    assert _post(client, "advance", lesson_attempt, 0).json()["allowed"] is True


@pytest.mark.django_db
@pytest.mark.parametrize("first_is_assigned", [True, False])
def test_mixed_lessons_preserve_progress_outside_journey_transitions(client, db, first_is_assigned):
    world = _world(db, "conf-mixed")
    removed = world["assignment_two"] if first_is_assigned else world["assignment_one"]
    removed.delete()
    VerificationCondition.objects.create(
        step=world["second"], kind=VerificationCondition.Kind.SCREEN_OPENED, order=1,
    )
    lesson_attempt = _open_workspace(client, world)
    _post(client, "open", lesson_attempt, 0)
    record = _declaration(world["learner"], "TEMP-CONF-MIXED")
    _confirm(client, world, {"record_id": record.pk})
    assert _post(client, "check", lesson_attempt, 0).json()["passed"] is True
    attempt = _attempt(world)
    current_assignment_id = attempt.current_journey_step_id

    advanced = _post(client, "advance", lesson_attempt, 0)

    assert advanced.status_code == 200
    assert advanced.json()["allowed"] is True
    assert advanced.json()["journey_moved"] is False
    attempt.refresh_from_db()
    lesson_attempt.refresh_from_db()
    assert attempt.current_journey_step_id == current_assignment_id
    assert attempt.completed_at is None
    assert lesson_attempt.current_step_id == world["second"].pk
    assert lesson_attempt.completed_at is None
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 1
    assert _post(client, "open", lesson_attempt, 1).status_code == 200
    assert _post(client, "check", lesson_attempt, 1).json()["passed"] is True


@pytest.mark.django_db
def test_final_journey_completion_is_retryable(client, checked_progression):
    world, lesson_attempt = checked_progression
    assert _post(client, "advance", lesson_attempt, 0).status_code == 200
    assert _post(client, "open", lesson_attempt, 1).status_code == 200
    assert client.post(reverse("hybrid-acknowledge-theory", args=[lesson_attempt.pk])).json()["lesson_complete"] is True
    assert _post(client, "advance", lesson_attempt, 1).json()["journey_moved"] is True
    attempt = _attempt(world)
    completed_at = attempt.completed_at

    retried = _post(client, "advance", lesson_attempt, 1)

    assert retried.status_code == 200
    assert retried.json()["allowed"] is True
    attempt.refresh_from_db()
    lesson_attempt.refresh_from_db()
    assert attempt.status == JourneyAttempt.Status.COMPLETED
    assert attempt.completed_at == completed_at
    assert attempt.current_journey_step_id == world["assignment_two"].pk
    assert lesson_attempt.current_step_id == world["second"].pk


@pytest.mark.django_db
def test_advancement_across_lessons_preserves_resume(client, checked_progression):
    world, lesson_attempt = checked_progression
    next_lesson = HybridLesson.objects.create(
        module=world["lesson"].module, slug="next", title="Next", order=2,
        summary="Summary.", theory="<p>Theory.</p>", is_published=True,
    )
    world["second"].lesson = next_lesson
    world["second"].order = 1
    world["second"].save(update_fields=("lesson", "order"))
    assert client.post(reverse("hybrid-acknowledge-theory", args=[lesson_attempt.pk])).json()["lesson_complete"] is True

    advanced = _post(client, "advance", lesson_attempt, 0)

    assert advanced.status_code == 200
    assert advanced.json()["journey_moved"] is True
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert _attempt(world).current_journey_step_id == world["assignment_two"].pk
    next_page = client.get(reverse("hybrid-workspace", args=[next_lesson.pk]))
    assert next_page.status_code == 200
    assert next_page.context["attempt"]["current_index"] == 0
    assert JourneyAttempt.objects.filter(enrolment=world["enrolment"]).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("failure_point", ["journey", "lesson"])
def test_advancement_rolls_back_both_positions_on_exception(client, checked_progression, monkeypatch, failure_point):
    world, lesson_attempt = checked_progression
    attempt = _attempt(world)
    activity = attempt.last_activity_at
    if failure_point == "journey":
        original_advance = journey_services.journey_advance

        def fail_after_advance(journey_attempt):
            result = original_advance(journey_attempt)
            assert result[1] is True
            raise RuntimeError("advance failed")

        monkeypatch.setattr(journey_services, "journey_advance", fail_after_advance)
    else:
        original_save = LessonAttempt.save

        def fail_after_save(instance, *args, **kwargs):
            original_save(instance, *args, **kwargs)
            if instance.current_step_id == world["second"].pk:
                raise RuntimeError("advance failed")

        monkeypatch.setattr(LessonAttempt, "save", fail_after_save)

    with pytest.raises(RuntimeError, match="advance failed"):
        _post(client, "advance", lesson_attempt, 0)

    attempt.refresh_from_db()
    lesson_attempt.refresh_from_db()
    assert attempt.current_journey_step_id == world["assignment_one"].pk
    assert attempt.last_activity_at == activity
    assert lesson_attempt.current_step_id == world["first"].pk
    resumed = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert resumed.context["attempt"]["current_index"] == 0


@pytest.mark.django_db
def test_advance_rejects_evidence_invalidated_by_record_replacement(client, checked_progression):
    world, lesson_attempt = checked_progression
    replacement = _declaration(world["learner"], "TEMP-CONF-REPLACEMENT")
    assert _confirm(client, world, {"record_id": replacement.pk}).status_code == 200

    refused = _post(client, "advance", lesson_attempt, 0)

    assert refused.status_code == 403
    assert refused.json()["allowed"] is False
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert _attempt(world).current_journey_step_id == world["assignment_one"].pk
    assert JourneyRecordAssociation.objects.filter(journey_attempt=_attempt(world)).count() == 2


@pytest.mark.django_db
def test_advance_keeps_owner_login_post_and_step_bounds_checks(client, db, checked_progression):
    world, lesson_attempt = checked_progression
    url = reverse("hybrid-step-advance", args=[lesson_attempt.pk, 0])
    assert client.get(url).status_code == 405
    assert _post(client, "advance", lesson_attempt, 99).status_code == 404
    client.force_login(_learner(db, "conf-advance-stranger"))
    assert client.post(url).status_code == 404
    client.logout()
    assert client.post(url).status_code == 302
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.current_step_id == world["first"].pk
    assert _attempt(world).current_journey_step_id == world["assignment_one"].pk
