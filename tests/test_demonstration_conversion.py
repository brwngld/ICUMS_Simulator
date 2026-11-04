"""UI 4 Stage 2B — converting a stopped demonstration into draft lesson steps.

The conversion is an authoring read (proposals) followed by an explicit,
once-only apply. The tests cover the proposal rules (order, collapsing, the
save anchored to its screen, no demonstration identifiers in the answer), the
apply gates (flag, ownership, lesson/edition drafts, stopped state, retention,
duplicates), server-side field validation through ``StepForm``, transactional
all-or-nothing behaviour, compatibility with the ordinary lesson editor, and
the isolation boundary between the demonstration and everything else.
"""
import json
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from audit.models import AuditEvent
from demonstration_world import demo_ucr, draft_world, instructor, recording
from hybrid import conversion, demonstrations
from hybrid.models import DemonstrationSession, LessonAttempt, StepEvent
from onboarding.models import Enrolment
from scenarios.models import UcrDeclaration, allocate_ucr_number

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)


# --- Helpers -----------------------------------------------------------------


def drive(world, route_name=None, save=False):
    """Append a navigation or a UCR-save event to the world's live session."""
    from demonstration_world import request_for

    request = request_for(world["instructor"], bound=world["session"].pk)
    if route_name is not None:
        return demonstrations.append_navigation_event(request, route_name=route_name)
    if save:
        record = demo_ucr(world["session"])
        return demonstrations.append_record_event(
            request,
            event_type="record_created",
            record_kind="ucr",
            record_id=record.pk,
            action_code="ucr.saved",
            payload={"regime_code": "TN", "result_status": "saved"},
        )


def stop(world):
    from demonstration_world import request_for

    session = DemonstrationSession.objects.get(pk=world["session"].pk)
    return demonstrations.stop_recording(
        request_for(world["instructor"], bound=session.pk), session.pk, session.version
    )


def demo_walk(world):
    """The canonical demonstration: portal → overview → create → save → search → create again."""
    drive(world, route_name="simulator-portal")
    drive(world, route_name="single-window-overview")
    drive(world, route_name="single-window-create-ucr")
    drive(world, save=True)
    drive(world, route_name="single-window-search-ucr")
    drive(world, route_name="single-window-create-ucr")  # genuine return, later


def proposals_url(world):
    return reverse("hybrid-demonstration-proposals", args=[world["lesson"].pk, world["session"].pk])


def convert_url(world):
    return reverse("hybrid-demonstration-convert", args=[world["lesson"].pk, world["session"].pk])


def client_for(user):
    client = Client()
    client.force_login(user)
    return client


def post_convert(client, world, activities):
    return client.post(convert_url(world), json.dumps({"activities": activities}), content_type="application/json")


def get_proposals(client, world):
    return client.get(proposals_url(world))


def submission(proposals, **overrides):
    """An apply body straight from the proposals, as the review UI submits it."""
    activities = [
        {
            "screen": proposal["screen"],
            "title": proposal["title"],
            "instruction": proposal["instruction"],
            "outcome": proposal["outcome"],
            "hint": "",
            "with_condition": proposal["has_condition"],
        }
        for proposal in proposals
    ]
    for screen, fields in overrides.items():
        for activity in activities:
            if activity["screen"] == screen:
                activity.update(fields)
    return activities


def applied_activities(client, world):
    proposals = json.loads(get_proposals(client, world).content)["activities"]
    return submission(proposals)


# --- Proposals: the read -----------------------------------------------------


@pytest.mark.django_db
@enabled
def test_proposals_follow_first_visit_order_and_collapse_repeats(db):
    world = recording("conv-order")
    demo_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])

    assert [proposal["screen"] for proposal in proposals] == [
        "simulator-portal",
        "single-window-overview",
        "single-window-create-ucr",
        "single-window-search-ucr",
    ]  # the later return to create-ucr collapsed into its first visit


@pytest.mark.django_db
@enabled
def test_the_ucr_save_is_anchored_to_its_screen_as_a_condition_suggestion(db):
    world = recording("conv-save")
    demo_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])
    create = next(proposal for proposal in proposals if proposal["screen"] == "single-window-create-ucr")

    assert create["has_condition"] is True
    assert "UCR declaration" in create["condition_label"]
    assert create["title"] == "Create a UCR declaration"
    assert create["instruction"] and create["outcome"]  # publication-ready drafts
    assert all(
        proposal["has_condition"] is False
        for proposal in proposals
        if proposal["screen"] != "single-window-create-ucr"
    )


@pytest.mark.django_db
@enabled
def test_proposals_never_carry_demonstration_record_identifiers(db):
    world = recording("conv-no-ids")
    demo_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])
    payload = json.dumps(proposals)
    record = UcrDeclaration.all_objects.filter(demonstration_session=world["session"]).first()

    assert record is not None
    assert record.temp_no not in payload
    # The proposal shape carries only authoring fields — no record references,
    # no event payload values, nothing keyed to the demonstration's rows.
    assert all(
        set(proposal) == {
            "screen", "screen_label", "title", "instruction", "outcome", "hint",
            "has_condition", "condition_label",
        }
        for proposal in proposals
    )
    assert "record" not in json.dumps([sorted(proposal) for proposal in proposals])


@pytest.mark.django_db
@enabled
def test_conversion_leaves_the_recording_and_its_events_untouched(db):
    world = recording("conv-immutable")
    demo_walk(world)
    stop(world)
    events_before = list(
        DemonstrationSession.objects.get(pk=world["session"].pk).events.order_by("sequence")
    )
    version_before = DemonstrationSession.objects.get(pk=world["session"].pk).version

    client = client_for(world["instructor"])
    get_proposals(client, world)
    post_convert(client, world, applied_activities(client, world))

    session = DemonstrationSession.objects.get(pk=world["session"].pk)
    assert [event.pk for event in session.events.order_by("sequence")] == [event.pk for event in events_before]
    assert session.state == DemonstrationSession.State.STOPPED
    assert session.version == version_before  # conversion never touches the recording


# --- Application -------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_stopped_recording_converts_into_editor_ready_steps(db):
    world = recording("conv-apply")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])

    proposals = json.loads(get_proposals(client, world).content)["activities"]
    response = post_convert(client, world, submission(proposals, **{
        "single-window-create-ucr": {"title": "Create and save a UCR draft"},
    }))

    assert response.status_code == 200
    data = json.loads(response.content)
    assert [step["order"] for step in data["steps"]] == [1, 2, 3, 4]
    created = list(world["lesson"].practical_steps.order_by("order"))
    assert [step.screen for step in created] == [
        "simulator-portal", "single-window-overview", "single-window-create-ucr", "single-window-search-ucr",
    ]
    assert created[2].title == "Create and save a UCR draft"  # the instructor's edit landed
    condition = created[2].conditions.get()
    assert condition.kind == "saved_record"
    assert condition.record_kind == "ucr"
    assert condition.required_status == "draft"
    assert not any(step.conditions.exists() for step in created if step.pk != created[2].pk)
    assert DemonstrationSession.objects.get(pk=world["session"].pk).state == "stopped"
    assert AuditEvent.objects.filter(
        action_code=conversion.CONVERSION_ACTION_CODE, target_id=str(world["session"].pk),
    ).exists()


@pytest.mark.django_db
@enabled
def test_deselected_activities_are_not_created_and_order_is_the_submitted_one(db):
    world = recording("conv-select")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    proposals = json.loads(get_proposals(client, world).content)["activities"]

    chosen = [
        proposal for proposal in proposals
        if proposal["screen"] in ("single-window-create-ucr", "single-window-search-ucr")
    ]
    chosen.reverse()  # the instructor's submitted order, not the proposal order
    response = post_convert(client, world, submission(chosen))

    assert response.status_code == 200
    created = list(world["lesson"].practical_steps.order_by("order"))
    assert [step.screen for step in created] == ["single-window-search-ucr", "single-window-create-ucr"]


@pytest.mark.django_db
@enabled
def test_a_second_application_of_the_same_recording_is_refused(db):
    world = recording("conv-duplicate")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    body = applied_activities(client, world)
    assert post_convert(client, world, body).status_code == 200

    refused = post_convert(client, world, body)

    assert refused.status_code == 409
    assert json.loads(refused.content)["code"] == "already_converted"
    assert world["lesson"].practical_steps.count() == 4  # nothing doubled


# --- Gates: identity, lesson, lifecycle, flag --------------------------------


@pytest.mark.django_db
@enabled
def test_another_instructors_recording_is_an_unknown_session(db):
    world = recording("conv-foreign")
    demo_walk(world)
    stop(world)
    stranger = instructor("conv-foreign-other")

    client = client_for(stranger)
    assert get_proposals(client, world).status_code == 404
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 404
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_session_of_another_lesson_cannot_convert_this_lesson(db):
    world = recording("conv-cross-lesson")
    demo_walk(world)
    stop(world)
    other = draft_world("conv-cross-lesson-other")

    client = client_for(world["instructor"])
    url = reverse("hybrid-demonstration-proposals", args=[other["lesson"].pk, world["session"].pk])
    assert client.get(url).status_code == 404
    convert = reverse("hybrid-demonstration-convert", args=[other["lesson"].pk, world["session"].pk])
    assert client.post(
        convert, json.dumps({"activities": [{"screen": "simulator-portal"}]}), content_type="application/json"
    ).status_code == 404
    assert other["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_published_lesson_refuses_conversion(db):
    from onboarding.models import ProgrammeVersion

    world = recording("conv-published")
    demo_walk(world)
    stop(world)
    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 404
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 404
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_live_recording_cannot_convert(db):
    world = recording("conv-live")
    demo_walk(world)
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 409
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 409
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_paused_recording_cannot_convert(db):
    world = recording("conv-paused")
    demo_walk(world)
    from demonstration_world import request_for

    session = DemonstrationSession.objects.get(pk=world["session"].pk)
    demonstrations.pause_recording(
        request_for(world["instructor"], bound=session.pk), session.pk, session.version
    )
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 409
    assert json.loads(get_proposals(client, world).content)["code"] == "recording_not_stopped"
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_discarded_recording_cannot_convert(db):
    world = recording("conv-discarded")
    demo_walk(world)
    stop(world)
    from demonstration_world import request_for

    demonstrations.discard_recording(
        request_for(world["instructor"], bound=world["session"].pk), world["session"].pk
    )
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 409
    assert json.loads(get_proposals(client, world).content)["code"] == "recording_not_stopped"
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 409
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_an_expired_recording_cannot_convert(db):
    world = recording("conv-expired")
    demo_walk(world)
    stop(world)
    DemonstrationSession.objects.filter(pk=world["session"].pk).update(
        retention_expires_at=timezone.now() - timedelta(days=1)
    )
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 409
    assert json.loads(get_proposals(client, world).content)["code"] == "session_expired"
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 409
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
def test_conversion_refuses_while_the_flag_is_off(db):
    world = recording("conv-flag")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])

    assert get_proposals(client, world).status_code == 403
    assert json.loads(get_proposals(client, world).content)["code"] == "recording_disabled"
    assert post_convert(client, world, [{"screen": "simulator-portal"}]).status_code == 403
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_bare_staff_account_is_not_authority_to_convert(db):
    world = recording("conv-staff")
    demo_walk(world)
    stop(world)
    staff = User.objects.create_user(username="conv-staff", email="s@example.test", password="x", is_staff=True)
    client = client_for(staff)

    assert get_proposals(client, world).status_code == 403
    assert json.loads(get_proposals(client, world).content)["code"] == "not_instructor"
    assert world["lesson"].practical_steps.count() == 0


# --- Field validation and rollback -------------------------------------------


@pytest.mark.django_db
@enabled
def test_an_unsupported_screen_is_refused(db):
    world = recording("conv-screen")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])

    response = post_convert(client, world, [{
        # An approved simulator screen this recording never opened.
        "screen": "clearance-workspace",
        "title": "Forged", "instruction": "x", "outcome": "y", "with_condition": False,
    }])

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "unsupported_screen"
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_condition_cannot_be_attached_where_nothing_was_saved(db):
    world = recording("conv-condition")
    drive(world, route_name="single-window-search-ucr")
    stop(world)
    client = client_for(world["instructor"])
    proposals = json.loads(get_proposals(client, world).content)["activities"]
    assert proposals[0]["has_condition"] is False

    response = post_convert(client, world, submission(proposals, **{
        "single-window-search-ucr": {"with_condition": True},
    }))

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "unsupported_condition"
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_blank_required_fields_are_refused_by_the_authoring_rules(db):
    world = recording("conv-fields")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    proposals = json.loads(get_proposals(client, world).content)["activities"]

    response = post_convert(client, world, submission(proposals, **{
        "simulator-portal": {"title": "", "instruction": ""},
    }))

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "invalid_activity"
    assert world["lesson"].practical_steps.count() == 0  # the whole batch rolled back


@pytest.mark.django_db
@enabled
def test_a_malformed_body_is_refused_without_writing(db):
    world = recording("conv-malformed")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])

    for body in ({}, {"activities": []}, {"activities": "nope"}, {"activities": [{"title": "no screen"}]}):
        response = client.post(convert_url(world), json.dumps(body), content_type="application/json")
        assert response.status_code == 400, body
    assert world["lesson"].practical_steps.count() == 0


# --- Compatibility with the lesson editor and the engine ---------------------


@pytest.mark.django_db
@enabled
def test_converted_steps_are_ordinary_editor_rows(db):
    from hybrid.publishing import course_blockers

    world = recording("conv-editor")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    post_convert(client, world, applied_activities(client, world))

    # The activities stage renders the converted steps through the ordinary cards.
    editor = client.get(reverse("hybrid-lesson-edit", args=[world["lesson"].pk]) + "?tab=activities")
    assert editor.status_code == 200
    assert "Create a UCR declaration" in editor.content.decode()

    # A converted step edits through the ordinary activity card.
    step = world["lesson"].practical_steps.get(screen="single-window-create-ucr")
    response = client.post(
        reverse("hybrid-lesson-edit", args=[world["lesson"].pk]),
        {
            "action": "save_activity",
            "step_id": str(step.pk),
            f"step-{step.pk}-title": "Save a UCR draft",
            f"step-{step.pk}-instruction": step.instruction,
            f"step-{step.pk}-outcome": step.outcome,
            f"step-{step.pk}-hint": "",
            f"step-{step.pk}-screen": step.screen,
            "active_tab": "activities",
        },
    )
    assert response.status_code in (302, 200)
    step.refresh_from_db()
    assert step.title == "Save a UCR draft"

    # Publication readiness judges converted steps like any other: this world's
    # only lesson now contributes no blockers of its own.
    blockers = course_blockers(world["lesson"].module.course)
    assert not any(world["lesson"].title in blocker for blocker in blockers)


@pytest.mark.django_db
@enabled
def test_the_condition_verifies_an_ordinary_student_draft(db):
    """End to end: the proposed condition is exactly what the engine checks,
    against the learner's own ordinary records — never the demonstration's."""
    from hybrid.verification import verify_step

    world = recording("conv-engine")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    post_convert(client, world, applied_activities(client, world))
    step = world["lesson"].practical_steps.get(screen="single-window-create-ucr")

    learner = User.objects.create_user(username="conv-learner", email="l@example.test", password="x")
    enrolment = Enrolment.objects.create(student=learner, programme_version=world["version"])
    attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=world["lesson"])
    StepEvent.objects.create(attempt=attempt, step=step, kind=StepEvent.Kind.OPENED, occurred_at=timezone.now())

    # No record yet: refused.
    assert verify_step(attempt, step)["passed"] is False

    # The demonstration's own record never satisfies a learner's check; the
    # learner's ordinary draft does.
    own = UcrDeclaration.all_objects.filter(demonstration_session=world["session"]).first()
    assert verify_step(attempt, step)["passed"] is False

    UcrDeclaration.objects.create(
        owner=learner,
        temp_no=allocate_ucr_number(UcrDeclaration.TEMP_PREFIX),
        regime="TN",
        status=UcrDeclaration.Status.DRAFT,
    )
    assert verify_step(attempt, step)["passed"] is True
    assert own.demonstration_session_id == world["session"].pk  # untouched throughout
