"""Stage 2F — instructor reference UCR selection in the Demonstration Studio.

A recording instructor may pick one of their own earlier demonstration UCRs as
a reference: "copy values" prefills a brand-new record, "continue" addresses
the reference on later saves. The selection itself lives in the instructor's
browser session (no schema change), never writes the reference record, and
every read re-resolves the instructor-owned demonstration scope — foreign
records, ordinary records and unknown ids never resolve.
"""
import json

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import demo_ucr, draft_world, ordinary_ucr
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.demonstration_ucr import get_demonstration_ucr
from scenarios.models import UcrDeclaration

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)


# --- Helpers -----------------------------------------------------------------


def make_world(seed):
    world = draft_world(seed)
    client = Client()
    client.force_login(world["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
    assert started.status_code == 200, started.content
    session = DemonstrationSession.objects.get(pk=started.json()["session"]["id"])
    return world, client, session


def stop_session(client, session):
    session.refresh_from_db()
    return client.post(
        reverse("hybrid-demonstration-stop"),
        json.dumps({"session_id": str(session.pk), "version": session.version}),
        content_type="application/json",
    )


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Ref Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Reference Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Reference Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000003", "designation": "Manager",
        },
        "consignment": {
            "goods": "Reference goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def save_draft(client, session, **overrides):
    """One demonstration save against the bound recording, as the frame posts it."""
    body = save_body(**overrides)
    response = client.post(reverse("ucr-save"), json.dumps(body), content_type="application/json")
    assert response.status_code == 200, response.content
    return UcrDeclaration.all_objects.get(pk=response.json()["id"])


def reference_url(world, action=""):
    return reverse(f"hybrid-demonstration-reference{action}", args=[world["lesson"].pk])


def select(client, world, record_id, intent):
    return client.post(
        reference_url(world, "-select"),
        json.dumps({"record_id": record_id, "intent": intent}),
        content_type="application/json",
    )


# --- Selection: authorization, validation, immutability ----------------------


@pytest.mark.django_db
@enabled
def test_selecting_an_owned_reference_stores_it_without_touching_the_record(db):
    world, client, session = make_world("ref-own")
    reference = save_draft(client, session)
    before = (
        reference.exporter_name, reference.temp_no, reference.status,
        reference.demonstration_session_id, reference.updated_at,
    )

    response = select(client, world, reference.pk, "continue")

    assert response.status_code == 200
    assert response.json()["selected"]["id"] == reference.pk
    reference.refresh_from_db()
    assert (
        reference.exporter_name, reference.temp_no, reference.status,
        reference.demonstration_session_id, reference.updated_at,
    ) == before  # selection is a zero-write operation
    selected = client.get(reference_url(world)).json()["selected"]
    assert selected["id"] == reference.pk and selected["intent"] == "continue"


@pytest.mark.django_db
@enabled
def test_a_submitted_reference_selects_for_copy_but_not_continue(db):
    world, client, session = make_world("ref-submitted")
    reference = save_draft(client, session)
    reference.status = UcrDeclaration.Status.SUBMITTED
    reference.ucr_no = "KGHTESTUCR260000100"
    reference.submitted_at = timezone.now()
    reference.save(update_fields=("status", "ucr_no", "submitted_at"))

    refused = select(client, world, reference.pk, "continue")
    assert refused.status_code == 400
    assert refused.json()["code"] == "reference_not_draft"

    accepted = select(client, world, reference.pk, "copy")
    assert accepted.status_code == 200
    assert accepted.json()["selected"]["intent"] == "copy"


@pytest.mark.django_db
@enabled
def test_foreign_and_ordinary_records_are_never_selectable(db):
    world, client, session = make_world("ref-authz")
    other_world = make_world("ref-authz-other")
    foreign = save_draft(other_world[1], other_world[2])
    ordinary = ordinary_ucr(world["instructor"])

    for record_id in (foreign.pk, ordinary.pk, 999_999):
        response = select(client, world, record_id, "continue")
        assert response.status_code == 404, record_id
        assert response.json()["code"] == "reference_not_found"
    assert client.get(reference_url(world)).json()["selected"] is None


@pytest.mark.django_db
@enabled
def test_an_unknown_intent_and_the_flag_are_refused(db):
    world, client, session = make_world("ref-intent")
    reference = save_draft(client, session)

    bad_intent = select(client, world, reference.pk, "mutate")
    assert bad_intent.status_code == 400

    with override_settings(DEMONSTRATION_RECORDING_ENABLED=False):
        refused = select(client, world, reference.pk, "copy")
        assert refused.status_code == 403
        assert refused.json()["code"] == "recording_disabled"


# --- Copy: a new record, the reference untouched -----------------------------


@pytest.mark.django_db
@enabled
def test_copy_prefill_saves_a_new_record_and_leaves_the_reference_alone(db):
    world, client, session = make_world("ref-copy")
    reference = save_draft(client, session)
    select(client, world, reference.pk, "copy")

    response = client.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    assert response.status_code == 200
    created = UcrDeclaration.all_objects.get(pk=response.json()["id"])

    assert created.pk != reference.pk  # a new record, never a duplicate claim on the reference
    assert created.demonstration_session_id == session.pk
    assert created.exporter_name == "Reference Exporter"
    reference.refresh_from_db()
    assert reference.exporter_name == "Reference Exporter"
    assert reference.demonstration_session_id == session.pk  # its own session, unchanged
    assert UcrDeclaration.all_objects.filter(owner=world["instructor"]).count() == 2


# --- Continue: saves address the reference, never duplicating ----------------


@pytest.mark.django_db
@enabled
def test_continue_addresses_the_reference_across_sessions(db):
    """Select a record from an earlier (stopped) session; a save in the new
    recording updates that record instead of creating a duplicate."""
    world, client, first_session = make_world("ref-continue")
    reference = save_draft(client, first_session)
    assert stop_session(client, first_session).status_code == 200

    # A second recording on the same lesson; the reference predates it.
    restarted = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
    assert restarted.status_code == 200
    second_session = DemonstrationSession.objects.get(pk=restarted.json()["session"]["id"])
    select(client, world, reference.pk, "continue")

    changed = save_body(exporter={"name": "Continued Exporter", "country": "GH", "address": "1 Export Road",
                                  "phone": "+233200000001", "contact": "Export Contact",
                                  "contact_no": "+233200000002", "designation": "Manager"})
    response = client.post(reverse("ucr-save"), json.dumps(changed), content_type="application/json")

    assert response.status_code == 200
    assert response.json()["id"] == reference.pk  # the same record, not a copy
    reference.refresh_from_db()
    assert reference.exporter_name == "Continued Exporter"
    assert reference.demonstration_session_id == first_session.pk  # stays on its original session
    assert UcrDeclaration.all_objects.filter(
        owner=world["instructor"], demonstration_session__isnull=False
    ).count() == 1
    # The new recording's timeline records the continued save against the record.
    event = DemonstrationEvent.objects.get(session_id=second_session.pk)
    assert event.record_id == reference.pk
    assert event.event_type == "record_updated"


@pytest.mark.django_db
@enabled
def test_the_selection_survives_a_page_reload_and_session_resume(db):
    world, client, session = make_world("ref-resume")
    reference = save_draft(client, session)
    select(client, world, reference.pk, "continue")

    # A fresh request through the same browser session: the selection persists.
    payload = client.get(reference_url(world)).json()
    assert payload["selected"]["id"] == reference.pk
    assert [option["id"] for option in payload["options"]] == [reference.pk]

    # And the create screen reloads the reference record's values for the demo.
    screen = client.get(f"{reverse('single-window-create-ucr')}?draft={reference.pk}")
    assert screen.status_code == 200
    assert reference.temp_no in screen.content.decode()


@pytest.mark.django_db
@enabled
def test_clearing_the_reference_returns_to_new_record_saves(db):
    world, client, session = make_world("ref-clear")
    reference = save_draft(client, session)
    select(client, world, reference.pk, "continue")

    cleared = client.post(reference_url(world, "-clear"), "{}", content_type="application/json")
    assert cleared.status_code == 200
    assert client.get(reference_url(world)).json()["selected"] is None

    response = client.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    assert response.status_code == 200
    assert response.json()["id"] != reference.pk
    assert UcrDeclaration.all_objects.filter(
        owner=world["instructor"], demonstration_session__isnull=False
    ).count() == 2


# --- Scope widening: instructor-owned, never broader -------------------------


@pytest.mark.django_db
@enabled
def test_instructor_scope_resolves_across_sessions_but_never_across_owners(db):
    """One instructor, two sessions: the widened scope resolves across them.
    A different instructor's demo record and any ordinary record never do."""
    world, client, first_session = make_world("ref-scope")
    reference = save_draft(client, first_session)
    stop_session(client, first_session)
    second = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
    second_session = DemonstrationSession.objects.get(pk=second.json()["session"]["id"])
    ordinary = ordinary_ucr(world["instructor"])
    stranger_world = make_world("ref-scope-other")
    strangers_record = save_draft(stranger_world[1], stranger_world[2])

    # The same instructor, a different session: resolves (Stage 2F widening).
    assert get_demonstration_ucr(second_session, reference.pk) is not None
    # Another instructor's demo record and any ordinary record never resolve.
    assert get_demonstration_ucr(first_session, strangers_record.pk) is None
    assert get_demonstration_ucr(first_session, ordinary.pk) is None
    assert ordinary.demonstration_session_id is None


@pytest.mark.django_db
@enabled
def test_recording_lifecycle_unchanged_by_selection(db):
    world, client, session = make_world("ref-lifecycle")
    reference = save_draft(client, session)
    select(client, world, reference.pk, "continue")

    session.refresh_from_db()
    paused = client.post(reverse("hybrid-demonstration-pause"), json.dumps(
        {"session_id": str(session.pk), "version": session.version}), content_type="application/json")
    assert paused.status_code == 200
    resumed = client.post(reverse("hybrid-demonstration-resume"), json.dumps(
        {"session_id": str(session.pk), "version": paused.json()["session"]["version"]}),
        content_type="application/json")
    assert resumed.status_code == 200
    stopped = stop_session(client, session)
    assert stopped.status_code == 200
    assert DemonstrationSession.objects.get(pk=session.pk).state == "stopped"
    # The selection outlives the recording: it is the instructor's library.
    assert client.get(reference_url(world)).json()["selected"]["id"] == reference.pk


# --- The reference picker endpoint -------------------------------------------


@pytest.mark.django_db
@enabled
def test_the_reference_picker_lists_only_this_instructors_records(db):
    world, client, session = make_world("ref-picker")
    mine = save_draft(client, session)
    other_world = make_world("ref-picker-other")
    theirs = save_draft(other_world[1], other_world[2])

    payload = client.get(reference_url(world)).json()

    ids = [option["id"] for option in payload["options"]]
    assert mine.pk in ids and theirs.pk not in ids
    assert payload["selected"] is None


@pytest.mark.django_db
@enabled
def test_students_and_anonymous_never_reach_the_reference_endpoints(db):
    world = draft_world("ref-student")
    student = User.objects.create_user(username="ref-student", email="s@example.test", password="x")
    stranger_client = Client()
    stranger_client.force_login(student)
    anonymous = Client()

    for client_for in (stranger_client, anonymous):
        assert client_for.get(reference_url(world)).status_code in (302, 403)
        assert client_for.post(
            reference_url(world, "-select"), json.dumps({}), content_type="application/json"
        ).status_code in (302, 403)
        assert client_for.post(
            reference_url(world, "-clear"), json.dumps({}), content_type="application/json"
        ).status_code in (302, 403)
    assert UcrDeclaration.all_objects.count() == 0
