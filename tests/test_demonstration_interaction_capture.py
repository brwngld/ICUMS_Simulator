"""UI Universal Recorder Stage A — interaction capture.

The interactions endpoint accepts one ordered batch of universal interaction
events from the recorder served on simulator pages, under exactly the same
gates as every other demonstration route: the flag, an instructor identity,
this browser's own server-side binding, a recording lifecycle state and the
inactivity deadline. Admission is all-or-nothing per batch, every stored value
is an approved code or bounded visible text, no field value has a key to
arrive under, and each event carries an idempotency key so a retry re-reads
its events instead of duplicating them. Interaction events interleave with
navigations and record outcomes on the one sequence the timeline reads.
"""
import json
import uuid

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import recording
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession

enabled = override_settings(DEBUG=True, DEMONSTRATION_RECORDING_ENABLED=True)

DRAFT_SESSION_KEY = demonstrations.ACTIVE_SESSION_KEY
URL = "hybrid-demonstration-interactions"


# --- Helpers -----------------------------------------------------------------


def bind_client(client, world):
    store = client.session
    store[DRAFT_SESSION_KEY] = str(world["session"].pk)
    store.save()


def post_batch(client, events, **overrides):
    body = {"events": events}
    body.update(overrides)
    return client.post(
        reverse(URL), json.dumps(body), content_type="application/json"
    )


def events(world):
    return list(
        DemonstrationEvent.objects.filter(session=world["session"]).order_by("sequence")
    )


def interaction_event(action, control_id, kind="button", **extra):
    event = {
        "action": action,
        "control_kind": kind,
        "control_id": control_id,
        "idempotency_key": str(uuid.uuid4()),
    }
    event.update(extra)
    return event


def session_row(world):
    return DemonstrationSession.objects.get(pk=world["session"].pk)


def bound_client(world):
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    return client


# --- Gating: the flag, identity, binding and lifecycle ------------------------


@pytest.mark.django_db
def test_with_recording_disabled_the_endpoint_refuses(db):
    world = recording("ix-disabled")
    client = bound_client(world)

    response = post_batch(client, [interaction_event("activate", "#ucr-save")])

    assert response.status_code == 403
    assert response.json()["code"] == "recording_disabled"
    assert events(world) == []


@pytest.mark.django_db
@enabled
def test_anonymous_and_student_requests_record_nothing(db):
    world = recording("ix-identity")
    stranger = recording("ix-identity-other")

    anonymous = Client()
    assert post_batch(anonymous, [interaction_event("activate", "#x")]).status_code == 302

    student = User.objects.create_user(username="ix-student", email="s@example.test", password="x")
    student_client = Client()
    student_client.force_login(student)
    answer = post_batch(student_client, [interaction_event("activate", "#x")])
    assert answer.status_code == 403
    assert answer.json()["code"] == "not_instructor"

    forged = Client()
    forged.force_login(world["instructor"])
    for binding in (str(uuid.uuid4()), str(stranger["session"].pk)):
        store = forged.session
        store[DRAFT_SESSION_KEY] = binding
        store.save()
        answer = post_batch(forged, [interaction_event("activate", "#x")])
        assert answer.status_code == 409
        assert answer.json()["code"] == "no_active_session"

    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_a_paused_session_accepts_no_interactions(db):
    world = recording("ix-paused")
    client = bound_client(world)
    from demonstration_world import request_for

    demonstrations.pause_recording(
        request_for(world["instructor"], bound=world["session"].pk),
        world["session"].pk,
        session_row(world).version,
    )

    response = post_batch(client, [interaction_event("activate", "#ucr-save")])

    assert response.status_code == 409
    assert response.json()["code"] == "session_not_recording"
    assert events(world) == []


@pytest.mark.django_db
@enabled
def test_an_idle_recording_is_sealed_by_its_next_batch(db):
    from datetime import timedelta

    world = recording("ix-idle")
    client = bound_client(world)
    DemonstrationSession.objects.filter(pk=world["session"].pk).update(
        last_activity_at=timezone.now() - demonstrations.INACTIVITY_TIMEOUT - timedelta(minutes=1)
    )

    response = post_batch(client, [interaction_event("activate", "#ucr-save")])

    assert response.status_code == 409
    assert response.json()["code"] == "session_idle"
    assert events(world) == []
    assert session_row(world).state == DemonstrationSession.State.STOPPED
    assert DRAFT_SESSION_KEY not in client.session


# --- Capture: the approved verbs, identities and bounded text -----------------


@pytest.mark.django_db
@enabled
def test_one_batch_of_approved_interactions_records_in_order(db):
    world = recording("ix-capture")
    client = bound_client(world)

    response = post_batch(client, [
        interaction_event("activate", "#ucr-save", label="Save"),
        interaction_event("choose", "#ucr-regime", kind="select", label="Regime", selection="TN — Temporary Admission"),
        interaction_event("toggle", "#ucr-show-provider", kind="checkbox", label="Service provider"),
        interaction_event("complete", "form:ucr-form [name=exporter_name]", kind="input", label="Exporter name"),
        interaction_event("submit", "#ucr-form", kind="form"),
        interaction_event("activate", "a[href='/practical/single-window/']", kind="link", label="Single Window"),
    ])

    assert response.status_code == 200
    assert response.json()["accepted"] == 6
    captured = events(world)
    assert [event.sequence for event in captured] == [1, 2, 3, 4, 5, 6]
    assert [event.action_code for event in captured] == [
        "activate", "choose", "toggle", "complete", "submit", "activate",
    ]
    assert all(event.event_type == "interaction" for event in captured)
    assert captured[0].payload == {"control_kind": "button", "control_id": "#ucr-save", "label": "Save"}
    assert captured[1].payload["selection"] == "TN — Temporary Admission"
    assert captured[4].payload["control_kind"] == "form"
    # Nothing here is a field value: no payload key can even carry one.
    assert all("value" not in event.payload for event in captured)
    # A deliberate interaction moves the inactivity deadline, like any control.
    assert session_row(world).last_activity_at is not None


@pytest.mark.django_db
@enabled
def test_interactions_interleave_with_navigations_and_record_outcomes(db):
    world = recording("ix-interleave")
    client = bound_client(world)

    assert client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe").status_code == 200
    assert post_batch(client, [interaction_event("activate", "#ucr-show-provider")]).status_code == 200
    assert client.get(reverse("single-window-search-ucr"), HTTP_SEC_FETCH_DEST="iframe").status_code == 200

    captured = events(world)
    assert [(event.sequence, event.event_type) for event in captured] == [
        (1, "navigation"),
        (2, "interaction"),
        (3, "navigation"),
    ]
    payload = client.get(reverse("hybrid-demonstration-session")).json()
    assert [event["sequence"] for event in payload["events"]] == [1, 2, 3]
    assert payload["events"][1]["payload"]["control_id"] == "#ucr-show-provider"


@pytest.mark.django_db
@enabled
def test_interactions_persist_across_pages_with_their_own_context(db):
    """The recorder is served on every simulator screen; a batch's route name
    travels as context. Two batches naming two screens both survive — and the
    route name stays metadata, never the proof of a screen."""
    world = recording("ix-persist")
    client = bound_client(world)

    assert post_batch(client, [
        interaction_event("activate", "#ucr-save", label="Save", route_name="single-window-create-ucr"),
    ]).status_code == 200
    assert post_batch(client, [
        interaction_event("activate", "a[href='/practical/']", kind="link", label="Home", route_name="simulator-portal"),
    ]).status_code == 200

    captured = events(world)
    assert [event.route_name for event in captured] == [
        "single-window-create-ucr", "simulator-portal",
    ]
    assert [event.sequence for event in captured] == [1, 2]


# --- Sanitization: the fail-closed payload rules -------------------------------


@pytest.mark.django_db
@enabled
def test_an_unapproved_action_or_kind_refuses_the_whole_batch(db):
    world = recording("ix-action")
    client = bound_client(world)

    for bad in (
        [interaction_event("hover", "#x")],
        [interaction_event("activate", "#x"), interaction_event("keypress", "#y")],
        [interaction_event("activate", "#x", kind="canvas")],
    ):
        response = post_batch(client, bad)
        assert response.status_code in (400, 403)
        assert events(world) == []  # all-or-nothing: nothing was written


@pytest.mark.django_db
@enabled
def test_an_interaction_without_a_control_identity_is_refused(db):
    world = recording("ix-identity-required")
    client = bound_client(world)

    response = post_batch(client, [interaction_event("activate", "   ")])

    assert response.status_code == 400
    assert events(world) == []


@pytest.mark.django_db
@enabled
def test_labels_and_selections_are_bounded_visible_text(db):
    world = recording("ix-text")
    client = bound_client(world)

    response = post_batch(client, [
        interaction_event("activate", "#x", label="Save  this\tdeclaration\nnow"),
        interaction_event("activate", "#y", label="A" * 500, selection="B" * 500),
    ])

    assert response.status_code == 200
    captured = events(world)
    assert captured[0].payload["label"] == "Save this declaration now"
    assert len(captured[1].payload["label"]) == 120
    assert len(captured[1].payload["selection"]) == 120


@pytest.mark.django_db
@enabled
def test_control_identifiers_are_capped_and_single_line(db):
    world = recording("ix-identity-text")
    client = bound_client(world)

    response = post_batch(client, [
        interaction_event("activate", "button:nth-of-type(2) > span:nth-of-type(1)"),
        interaction_event("activate", "#x\n\twith break"),
        interaction_event("activate", "z" * 400),
    ])

    assert response.status_code == 200
    captured = events(world)
    assert captured[0].payload["control_id"] == "button:nth-of-type(2) > span:nth-of-type(1)"
    assert captured[1].payload["control_id"] == "#x with break"
    assert len(captured[2].payload["control_id"]) == 120


@pytest.mark.django_db
@enabled
def test_an_unknown_route_name_is_refused_as_context(db):
    world = recording("ix-route")
    client = bound_client(world)

    response = post_batch(client, [
        interaction_event("activate", "#x", route_name="not-a-route"),
    ])

    assert response.status_code == 403
    assert response.json()["code"] == "route_denied"
    assert events(world) == []


@pytest.mark.django_db
@enabled
def test_a_mangled_idempotency_key_is_refused(db):
    world = recording("ix-key")
    client = bound_client(world)

    response = post_batch(client, [interaction_event("activate", "#x", idempotency_key="not-a-uuid")])

    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_invalid"
    assert events(world) == []


# --- Batches: shape, size and retry -------------------------------------------


@pytest.mark.django_db
@enabled
def test_malformed_and_oversized_batches_refuse_without_writing(db):
    world = recording("ix-batch")
    client = bound_client(world)

    assert post_batch(client, "not-a-list").status_code == 400
    assert post_batch(client, []).status_code == 400
    assert post_batch(client, [{"action": "activate"}]).status_code == 400
    assert post_batch(client, [[1, 2], [3]]).status_code == 400
    too_many = [
        interaction_event("activate", f"#control-{index}") for index in range(demonstrations.INTERACTION_BATCH_LIMIT + 1)
    ]
    assert post_batch(client, too_many).status_code == 400

    assert events(world) == []


@pytest.mark.django_db
@enabled
def test_a_full_batch_is_accepted_at_the_ceiling(db):
    world = recording("ix-ceiling")
    client = bound_client(world)
    batch = [interaction_event("activate", f"#control-{index}") for index in range(demonstrations.INTERACTION_BATCH_LIMIT)]

    response = post_batch(client, batch)

    assert response.status_code == 200
    assert response.json()["accepted"] == demonstrations.INTERACTION_BATCH_LIMIT
    assert [event.sequence for event in events(world)] == list(range(1, 41))


@pytest.mark.django_db
@enabled
def test_a_retry_with_the_same_keys_returns_the_same_events(db):
    world = recording("ix-retry")
    client = bound_client(world)
    batch = [
        interaction_event("activate", "#ucr-save", label="Save"),
        interaction_event("toggle", "#ucr-show-provider", kind="checkbox"),
    ]

    first = post_batch(client, batch)
    assert first.status_code == 200
    before = list(events(world))

    resent = [dict(item) for item in batch]  # the client retries the whole batch verbatim
    second = post_batch(client, resent)

    assert second.status_code == 200
    assert second.json()["accepted"] == 2
    assert events(world) == before  # no duplicates, no burned sequences
    assert [event.sequence for event in events(world)] == [1, 2]


@pytest.mark.django_db
@enabled
def test_a_partial_retry_only_returns_the_events_it_covers(db):
    """A client that lost a response and re-sends just the missing events gets
    deduplication for those, and fresh sequences for genuinely new ones."""
    world = recording("ix-partial")
    client = bound_client(world)
    first_key = str(uuid.uuid4())
    assert post_batch(client, [interaction_event("activate", "#a", idempotency_key=first_key)]).status_code == 200

    response = post_batch(client, [
        interaction_event("activate", "#a", idempotency_key=first_key),
        interaction_event("activate", "#b"),
    ])

    assert response.status_code == 200
    captured = events(world)
    assert [event.sequence for event in captured] == [1, 2]
    assert captured[0].payload["control_id"] == "#a"
    assert captured[1].payload["control_id"] == "#b"


# --- The shell serves the recorder only inside an authorized context ----------


@pytest.mark.django_db
@enabled
def test_a_recording_instructor_browser_gets_the_recorder_script(db):
    world = recording("ix-shell")
    client = bound_client(world)

    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")

    html = response.content.decode()
    assert 'id="demonstration-recorder"' in html
    assert "/static/js/demonstration-recorder.js" in html
    assert reverse(URL) in html
    assert 'data-route="single-window-create-ucr"' in html


@pytest.mark.django_db
@enabled
def test_a_paused_session_renders_simulator_pages_without_the_recorder(db):
    world = recording("ix-shell-paused")
    client = bound_client(world)
    from demonstration_world import request_for

    demonstrations.pause_recording(
        request_for(world["instructor"], bound=world["session"].pk),
        world["session"].pk,
        session_row(world).version,
    )

    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")

    assert response.status_code == 200
    assert 'id="demonstration-recorder"' not in response.content.decode()


@pytest.mark.django_db
@enabled
def test_ordinary_students_never_get_the_recorder(db):
    world = recording("ix-shell-student")
    student = User.objects.create_user(username="ix-shell-student-1", email="s@example.test", password="x")
    client = Client()
    client.force_login(student)

    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")

    assert response.status_code in (200, 302)  # students browse the simulator normally
    assert 'id="demonstration-recorder"' not in response.content.decode()


@pytest.mark.django_db
def test_without_the_flag_even_a_recording_browser_gets_no_recorder(db):
    world = recording("ix-shell-disabled")
    client = bound_client(world)

    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")

    assert response.status_code == 200
    assert 'id="demonstration-recorder"' not in response.content.decode()
