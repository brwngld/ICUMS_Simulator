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


def drive(world, route_name=None, save=False, submit=False):
    """Append a navigation, a UCR-save or a UCR-submit event to the world's live session."""
    from demonstration_world import request_for

    request = request_for(world["instructor"], bound=world["session"].pk)
    if route_name is not None:
        return demonstrations.append_navigation_event(request, route_name=route_name)
    record = demo_ucr(world["session"])
    if submit:
        return demonstrations.append_record_event(
            request,
            event_type="record_updated",
            record_kind="ucr",
            record_id=record.pk,
            action_code="ucr.submitted",
            payload={
                "regime_code": "TN",
                "result_status": "submitted",
                "filled_sections": ["consignment", "exporter", "importer", "provider"],
            },
        )
    if save:
        return demonstrations.append_record_event(
            request,
            event_type="record_created",
            record_kind="ucr",
            record_id=record.pk,
            action_code="ucr.saved",
            payload={
                "regime_code": "TN",
                "result_status": "saved",
                "filled_sections": ["consignment", "exporter", "importer", "provider"],
            },
        )


def stop(world):
    from demonstration_world import request_for

    session = DemonstrationSession.objects.get(pk=world["session"].pk)
    return demonstrations.stop_recording(
        request_for(world["instructor"], bound=session.pk), session.pk, session.version
    )


def demo_walk(world):
    """A demonstration with one save: portal → overview → create → save → search → create again."""
    drive(world, route_name="simulator-portal")
    drive(world, route_name="single-window-overview")
    drive(world, route_name="single-window-create-ucr")
    drive(world, save=True)
    drive(world, route_name="single-window-search-ucr")
    drive(world, route_name="single-window-create-ucr")  # genuine return, later


def import_ucr_walk(world):
    """The Import-UCR foundation's canonical demonstration: the whole procedure.

    Overview → Create UCR (regime chosen on the form) → save (sections
    validated, temporary reference) → submit (final number) → detail screen.
    """
    drive(world, route_name="single-window-overview")
    drive(world, route_name="single-window-create-ucr")
    drive(world, save=True)
    drive(world, submit=True)
    drive(world, route_name="ucr-detail")


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
            "proposal_id": proposal["id"],
            "title": proposal["title"],
            "instruction": proposal["instruction"],
            "outcome": proposal["outcome"],
            "hint": "",
            "with_condition": proposal["has_condition"],
        }
        for proposal in proposals
    ]
    for proposal_id, fields in overrides.items():
        for activity in activities:
            if activity["proposal_id"] == proposal_id:
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

    # The incidental screens in first-visit order (the later return to
    # create-ucr collapsed into its first visit), then the one attested
    # create milestone: choosing the regime, completing the sections and
    # saving are one action on one screen, attested by the saved draft.
    assert [proposal["id"] for proposal in proposals] == [
        "screen:simulator-portal",
        "screen:single-window-overview",
        "screen:single-window-search-ucr",
        "milestone:regime",
        "milestone:sections",
        "milestone:save",
    ]
    assert len({proposal["id"] for proposal in proposals}) == len(proposals)


@pytest.mark.django_db
@enabled
def test_the_ucr_save_is_anchored_to_its_screen_as_a_condition_suggestion(db):
    world = recording("conv-save")
    demo_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])
    regime = next(p for p in proposals if p["id"] == "milestone:regime")
    sections_p = next(p for p in proposals if p["id"] == "milestone:sections")
    save = next(p for p in proposals if p["id"] == "milestone:save")

    assert regime["has_condition"] is True
    assert regime["condition"]["kind"] == "stage_evidence"
    assert regime["condition"]["expected_fields"] == {"stage": "regime_selected", "value": "TN"}
    assert sections_p["has_condition"] is True
    assert sections_p["condition"]["kind"] == "stage_evidence"
    assert save["has_condition"] is True
    assert save["condition"]["kind"] == "saved_record"
    assert "UCR declaration" in save["condition_label"]
    assert regime["instruction"] and regime["outcome"]
    assert all(proposal["has_condition"] is True for proposal in proposals)
    assert all(
        proposal["condition"]["kind"] == "screen_opened"
        for proposal in proposals
        if proposal["id"].startswith("screen:")
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
    assert '"record_id"' not in payload  # no event names a demonstration record
    # The proposal shape carries only authoring fields, the derived condition
    # and the evidence references — no record references, nothing keyed to the
    # demonstration's rows. The captured regime *code* is the one payload value
    # that travels, because the regime step's condition is pinned to it.
    assert all(
        set(proposal) == {
            "id", "screen", "screen_label", "title", "instruction", "outcome", "hint",
            "has_condition", "condition", "condition_label", "evidence",
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
        "milestone:save": {"title": "Create and save a UCR draft"},
    }))

    assert response.status_code == 200
    data = json.loads(response.content)
    assert [step["order"] for step in data["steps"]] == [1, 2, 3, 4, 5, 6]
    created = list(world["lesson"].practical_steps.order_by("order"))
    assert [step.screen for step in created] == [
        "simulator-portal", "single-window-overview", "single-window-search-ucr",
        "single-window-create-ucr", "single-window-create-ucr", "single-window-create-ucr",
    ]
    assert created[5].title == "Create and save a UCR draft"  # the instructor's edit landed
    # Every step carries its own attestation.
    screen_conditions = [step.conditions.get() for step in created[:3]]
    assert all(condition.kind == "screen_opened" for condition in screen_conditions)
    regime_condition = created[3].conditions.get()
    assert regime_condition.kind == "stage_evidence"
    assert regime_condition.expected_fields == {"stage": "regime_selected", "value": "TN"}
    sections_condition = created[4].conditions.get()
    assert sections_condition.kind == "stage_evidence"
    save_condition = created[5].conditions.get()
    assert (save_condition.kind, save_condition.record_kind, save_condition.required_status) == ("saved_record", "ucr", "draft")
    assert DemonstrationSession.objects.get(pk=world["session"].pk).state == "stopped"
    audit = AuditEvent.objects.get(
        action_code=conversion.CONVERSION_ACTION_CODE, target_id=str(world["session"].pk),
    )
    # Every created step is traceable to the events that ground it.
    evidence = audit.metadata["evidence"]
    assert [entry["title"] for entry in evidence] == [step.title for step in created]
    assert all(entry["evidence"] for entry in evidence)
    save_entry = next(entry for entry in evidence if entry["title"] == "Create and save a UCR draft")
    assert any(item["action_code"] == "ucr.saved" for item in save_entry["evidence"])


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
        if proposal["id"] in ("screen:single-window-search-ucr", "milestone:save")
    ]
    chosen.reverse()  # the instructor's submitted order, not the proposal order
    response = post_convert(client, world, submission(chosen))

    assert response.status_code == 200
    created = list(world["lesson"].practical_steps.order_by("order"))
    assert [step.screen for step in created] == ["single-window-create-ucr", "single-window-search-ucr"]


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
    assert world["lesson"].practical_steps.count() == 6  # nothing doubled


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
def test_an_unsupported_activity_is_refused(db):
    world = recording("conv-screen")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])

    response = post_convert(client, world, [{
        # A plausible id this recording never proposed.
        "proposal_id": "screen:clearance-workspace",
        "title": "Forged", "instruction": "x", "outcome": "y", "with_condition": False,
    }])

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "unsupported_activity"
    assert world["lesson"].practical_steps.count() == 0


@pytest.mark.django_db
@enabled
def test_a_screen_step_attests_to_its_own_reach(db):
    """A screen milestone's condition is screen_opened — the step verifies
    that the learner reached it, never a record that was never saved."""
    world = recording("conv-condition")
    drive(world, route_name="single-window-search-ucr")
    stop(world)
    client = client_for(world["instructor"])
    proposals = json.loads(get_proposals(client, world).content)["activities"]
    assert proposals[0]["condition"]["kind"] == "screen_opened"

    applied = client.post(convert_url(world), json.dumps({"activities": submission(proposals)}), content_type="application/json")
    assert applied.status_code == 200
    step = world["lesson"].practical_steps.first()
    condition = step.conditions.get()
    assert condition.kind == "screen_opened"
    assert condition.record_kind == "" and condition.required_status == ""


@pytest.mark.django_db
@enabled
def test_blank_required_fields_are_refused_by_the_authoring_rules(db):
    world = recording("conv-fields")
    demo_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    proposals = json.loads(get_proposals(client, world).content)["activities"]

    response = post_convert(client, world, submission(proposals, **{
        "screen:simulator-portal": {"title": "", "instruction": ""},
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
    step = world["lesson"].practical_steps.filter(
        screen="single-window-create-ucr",
        conditions__kind="saved_record",
    ).first()
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
    step = world["lesson"].practical_steps.filter(
        screen="single-window-create-ucr",
        conditions__kind="saved_record",
    ).first()

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


# --- The Import-UCR foundation: the whole procedure, captured ----------------


@pytest.mark.django_db
@enabled
def test_the_import_ucr_procedure_generates_the_complete_sequence(db):
    """Overview → regime → sections → save → submit — the five stages, all
    evidence-backed. The detail visit stays captured evidence in the timeline
    but anchors no step (the detail screen addresses a record, not a binding)."""
    world = recording("conv-import")
    import_ucr_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])

    assert [proposal["id"] for proposal in proposals] == [
        "screen:single-window-overview",
        "milestone:regime", "milestone:sections", "milestone:save",
        "milestone:submit",
    ]
    by_id = {proposal["id"]: proposal for proposal in proposals}
    assert by_id["milestone:regime"]["condition"]["expected_fields"] == {"stage": "regime_selected", "value": "TN"}
    assert by_id["milestone:submit"]["condition"]["required_status"] == "submitted"
    assert by_id["screen:single-window-overview"]["condition"]["kind"] == "screen_opened"
    # The create milestone names the regime the capture actually shows.
    assert "Transhipment" in by_id["milestone:regime"]["title"]
    assert "final UCR number" in by_id["milestone:submit"]["outcome"]
    # Every proposal grounds itself in captured evidence, and the submit step's
    # evidence is the submission event itself.
    assert all(proposal["evidence"] for proposal in proposals)
    assert by_id["milestone:submit"]["evidence"][0]["action_code"] == "ucr.submitted"
    assert conversion.capture_warnings(world["session"]) == []


@pytest.mark.django_db
@enabled
def test_a_recording_without_a_submission_warns_instead_of_inventing_the_step(db):
    world = recording("conv-no-submit")
    demo_walk(world)
    stop(world)

    proposals = conversion.proposals_for(world["session"])
    warnings = conversion.capture_warnings(world["session"])

    assert "milestone:submit" not in [proposal["id"] for proposal in proposals]
    assert len(warnings) == 1
    assert "Submission was not captured" in warnings[0]


@pytest.mark.django_db
@enabled
def test_a_recording_without_a_save_warns_and_proposes_screens_only(db):
    world = recording("conv-no-save")
    drive(world, route_name="single-window-overview")
    drive(world, route_name="single-window-create-ucr")
    stop(world)

    proposals = conversion.proposals_for(world["session"])
    warnings = conversion.capture_warnings(world["session"])

    assert [proposal["id"] for proposal in proposals] == [
        "screen:single-window-overview",
        "screen:single-window-create-ucr",
    ]
    assert all(
        proposal["condition"]["kind"] == "screen_opened"
        for proposal in proposals
    )
    assert len(warnings) == 1
    assert "No UCR save was captured" in warnings[0]


@pytest.mark.django_db
@enabled
def test_the_submit_condition_verifies_a_real_student_submission(db):
    """End to end: the generated submit step passes only on the learner's own
    submitted UCR — never on the demonstration's."""
    from hybrid.verification import verify_step

    world = recording("conv-import-engine")
    import_ucr_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    post_convert(client, world, applied_activities(client, world))
    submit_step = world["lesson"].practical_steps.get(key__contains="submit-the-ucr")

    learner = User.objects.create_user(username="conv-import-learner", email="il@example.test", password="x")
    enrolment = Enrolment.objects.create(student=learner, programme_version=world["version"])
    attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=world["lesson"])
    StepEvent.objects.create(attempt=attempt, step=submit_step, kind=StepEvent.Kind.OPENED, occurred_at=timezone.now())

    # The demonstration's own submitted record never satisfies the check.
    assert verify_step(attempt, submit_step)["passed"] is False

    # The learner's own draft does not either — the step requires a submission.
    draft = UcrDeclaration.objects.create(
        owner=learner,
        temp_no=allocate_ucr_number(UcrDeclaration.TEMP_PREFIX),
        regime="TN",
        status=UcrDeclaration.Status.DRAFT,
    )
    assert verify_step(attempt, submit_step)["passed"] is False

    draft.status = UcrDeclaration.Status.SUBMITTED
    draft.ucr_no = allocate_ucr_number(UcrDeclaration.UCR_PREFIX)
    draft.submitted_at = timezone.now()
    draft.save()
    assert verify_step(attempt, submit_step)["passed"] is True


@pytest.mark.django_db
@enabled
def test_the_regime_condition_requires_the_captured_regime(db):
    from hybrid.verification import verify_step

    world = recording("conv-import-regime")
    import_ucr_walk(world)
    stop(world)
    client = client_for(world["instructor"])
    post_convert(client, world, applied_activities(client, world))
    regime_step = world["lesson"].practical_steps.get(key__contains="regime")
    assert regime_step.conditions.get().expected_fields == {"stage": "regime_selected", "value": "TN"}

    learner = User.objects.create_user(username="conv-regime-learner", email="rl@example.test", password="x")
    enrolment = Enrolment.objects.create(student=learner, programme_version=world["version"])
    attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=world["lesson"])
    StepEvent.objects.create(attempt=attempt, step=regime_step, kind=StepEvent.Kind.OPENED, occurred_at=timezone.now())

    # No stage evidence yet: refused.
    assert verify_step(attempt, regime_step)["passed"] is False

    # Stage evidence with the wrong regime: refused.
    attempt.stage_evidence = {"regime_selected": "EX"}
    attempt.save(update_fields=("stage_evidence",))
    assert verify_step(attempt, regime_step)["passed"] is False

    # Stage evidence with the captured regime: passes.
    attempt.stage_evidence = {"regime_selected": "TN"}
    attempt.save(update_fields=("stage_evidence",))
    assert verify_step(attempt, regime_step)["passed"] is True
