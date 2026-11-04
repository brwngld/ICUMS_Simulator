"""UI 4 Stage 1C — demonstration navigation capture.

The frame boundary records one navigation event per approved simulator screen
an instructor's live recording drives. The tests walk the gate exactly as a
request meets it: an instructor document navigation (``Sec-Fetch-Dest: iframe``)
on an approved prefix, a 200 HTML response, a route in
``DEMONSTRATION_NAVIGATION_ACTIONS``, the flag on, and the browser's own
server-side binding resolving to a ``recording`` session. Everything else —
fetches, lookups, students, paused or sealed sessions, refreshes of the screen
already open — records nothing, and nothing here can fail the page.
"""
import json
import uuid
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import SessionEngine, ordinary_ucr, recording
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.models import UcrDeclaration

frame = override_settings(DEBUG=True, DEMONSTRATION_RECORDING_ENABLED=True)
FRAME_HEADERS = {"HTTP_SEC_FETCH_DEST": "iframe", "HTTP_SEC_FETCH_SITE": "same-origin"}

DRAFT_SESSION_KEY = demonstrations.ACTIVE_SESSION_KEY


# --- Helpers -----------------------------------------------------------------


def bind_client(client, world):
    store = client.session
    store[DRAFT_SESSION_KEY] = str(world["session"].pk)
    store.save()


def screen(client, name, *args, headers=None):
    return client.get(reverse(name, args=args), **(headers or FRAME_HEADERS))


def events(world):
    return list(
        DemonstrationEvent.objects.filter(session=world["session"]).order_by("sequence")
    )


def navigation_routes(world):
    return [event.route_name for event in events(world) if event.event_type == "navigation"]


def session_row(world):
    return DemonstrationSession.objects.get(pk=world["session"].pk)


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Navigation Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Navigation Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Navigation Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000002", "designation": "Manager",
        },
        "consignment": {
            "goods": "Training goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def post_json(client, payload):
    return client.post(reverse("ucr-save"), json.dumps(payload), content_type="application/json")


# --- Capture on approved screens ---------------------------------------------


@pytest.mark.django_db
@frame
def test_an_approved_screen_navigation_is_captured(db):
    world = recording("nav-create")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    before = session_row(world).last_activity_at

    response = screen(client, "single-window-create-ucr")

    assert response.status_code == 200
    captured = events(world)
    assert len(captured) == 1
    event = captured[0]
    assert event.event_type == "navigation"
    assert event.sequence == 1
    assert event.route_name == "single-window-create-ucr"
    assert event.action_code == "ucr.create_form_opened"
    assert event.payload == {"result_status": "opened"}
    assert event.record_id is None
    assert event.record_kind == ""
    # Reaching a screen is deliberate activity: the inactivity deadline moved.
    assert session_row(world).last_activity_at > before


@pytest.mark.django_db
@frame
def test_each_approved_route_records_its_own_action_code(db):
    world = recording("nav-routes")
    ordinary = ordinary_ucr(world["instructor"])
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    for name, args, action in (
        ("simulator-portal", (), "portal.opened"),
        ("single-window-overview", (), "single_window.opened"),
        ("single-window-create-ucr", (), "ucr.create_form_opened"),
        ("single-window-search-ucr", (), "ucr.search_opened"),
        ("ucr-detail", (ordinary.pk,), "ucr.detail_opened"),
    ):
        response = screen(client, name, *args)
        assert response.status_code == 200, name
        assert navigation_routes(world)[-1] == name
        assert events(world)[-1].action_code == action

    assert [event.sequence for event in events(world)] == [1, 2, 3, 4, 5]


@pytest.mark.django_db
@frame
def test_a_saved_ucr_reload_and_a_search_read_as_separate_screens(db):
    """The create screen reached through ?draft= is the same approved screen;
    the query string itself is not part of the recorded destination."""
    world = recording("nav-draft")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    saved = json.loads(post_json(client, save_body()).content)

    response = client.get(
        f"{reverse('single-window-create-ucr')}?draft={saved['id']}", **FRAME_HEADERS
    )

    assert response.status_code == 200
    assert navigation_routes(world) == ["single-window-create-ucr"]
    assert events(world)[-1].payload == {"result_status": "opened"}
    assert events(world)[-1].sequence == 2  # the save is event 1, the screen event 2


# --- Noise never records -----------------------------------------------------


@pytest.mark.django_db
@frame
def test_a_refresh_of_the_current_screen_is_not_recorded_twice(db):
    """Consecutive requests for the screen the recording is already on are one
    logical navigation; leaving and returning is a real one."""
    world = recording("nav-refresh")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    assert screen(client, "single-window-create-ucr").status_code == 200
    assert screen(client, "single-window-create-ucr").status_code == 200
    assert navigation_routes(world) == ["single-window-create-ucr"]

    assert screen(client, "single-window-search-ucr").status_code == 200
    assert screen(client, "single-window-create-ucr").status_code == 200

    assert navigation_routes(world) == [
        "single-window-create-ucr",
        "single-window-search-ucr",
        "single-window-create-ucr",
    ]


@pytest.mark.django_db
@frame
def test_background_and_lookup_requests_never_record(db):
    """Fetches (``Sec-Fetch-Dest: empty``) never reach the frame boundary, and
    a JSON answer is not a screen even when it arrives inside the frame."""
    world = recording("nav-noise")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    # A fetch-shaped request for an approved screen: not a document navigation.
    assert client.get(reverse("single-window-create-ucr")).status_code == 200

    # The JSON lookup endpoints, however they arrive: no navigation events.
    assert client.get(
        reverse("ucr-stakeholder-lookup"), {"code": "C00297059921"}, **FRAME_HEADERS
    ).status_code in (200, 400, 404)
    assert client.get(
        reverse("clearance-cpc-search"), {"regime": "IM"}, **FRAME_HEADERS
    ).status_code == 200

    assert events(world) == []


@pytest.mark.django_db
@frame
def test_refused_and_missing_screens_record_nothing(db):
    world = recording("nav-refused")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    # Outside the frame's approved prefixes.
    assert client.get(reverse("simulator-more-information"), **FRAME_HEADERS).status_code == 403
    # A detail page that does not resolve is not a screen the demonstration visited.
    assert screen(client, "ucr-detail", 999_999).status_code == 404

    assert events(world) == []


def drive(client, world, action):
    """Run one lifecycle control for the world's session through the service,
    carrying the version the browser would have."""
    from demonstration_world import request_for

    return action(
        request_for(world["instructor"], bound=world["session"].pk),
        world["session"].pk,
        session_row(world).version,
    )


# --- Authorization and lifecycle boundaries ----------------------------------


@pytest.mark.django_db
@frame
def test_a_forged_or_foreign_binding_captures_nothing(db):
    world = recording("nav-forged")
    stranger = recording("nav-forged-other")
    client = Client()
    client.force_login(world["instructor"])

    for binding in (str(uuid.uuid4()), str(stranger["session"].pk)):
        store = client.session
        store[DRAFT_SESSION_KEY] = binding
        store.save()
        response = screen(client, "single-window-create-ucr")
        assert response.status_code == 200

    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@frame
def test_paused_navigation_records_nothing_and_resume_captures_again(db):
    world = recording("nav-paused")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    drive(client, world, demonstrations.pause_recording)

    assert screen(client, "single-window-create-ucr").status_code == 200
    assert events(world) == []  # paused recordings accept no events

    drive(client, world, demonstrations.resume_recording)
    assert screen(client, "single-window-search-ucr").status_code == 200
    assert [event.sequence for event in events(world)] == [1]  # the pause burned no sequence
    assert navigation_routes(world) == ["single-window-search-ucr"]


@pytest.mark.django_db
@frame
def test_a_stopped_session_records_nothing_and_loses_its_binding(db):
    world = recording("nav-stopped")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    drive(client, world, demonstrations.stop_recording)

    response = screen(client, "single-window-create-ucr")

    assert response.status_code == 200
    assert events(world) == []
    assert DRAFT_SESSION_KEY not in client.session  # the stale binding was dropped


@pytest.mark.django_db
@frame
def test_a_discarded_session_records_nothing(db):
    world = recording("nav-discarded")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    from demonstration_world import request_for

    demonstrations.discard_recording(
        request_for(world["instructor"], bound=world["session"].pk), world["session"].pk
    )

    response = screen(client, "single-window-create-ucr")

    assert response.status_code == 200
    assert events(world) == []


@pytest.mark.django_db
@frame
def test_an_idle_recording_is_sealed_by_its_next_navigation_not_extended(db):
    world = recording("nav-idle")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    DemonstrationSession.objects.filter(pk=world["session"].pk).update(
        last_activity_at=timezone.now() - demonstrations.INACTIVITY_TIMEOUT - timedelta(minutes=1)
    )

    response = screen(client, "single-window-create-ucr")

    assert response.status_code == 200
    assert events(world) == []
    assert session_row(world).state == DemonstrationSession.State.STOPPED
    assert DRAFT_SESSION_KEY not in client.session


@pytest.mark.django_db
def test_recording_disabled_records_no_navigation(db):
    world = recording("nav-disabled")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    with override_settings(DEBUG=True):
        response = screen(client, "single-window-create-ucr")

    assert response.status_code == 200
    assert DemonstrationEvent.objects.count() == 0
    assert session_row(world).state == DemonstrationSession.State.RECORDING


@pytest.mark.django_db
@frame
def test_ordinary_students_never_record_navigation(db):
    world = recording("nav-student")
    student = User.objects.create_user(username="nav-student", email="s@example.test", password="x")
    client = Client()
    client.force_login(student)

    response = screen(client, "single-window-create-ucr")

    assert response.status_code in (200, 302)  # students browse the simulator normally
    assert DemonstrationEvent.objects.count() == 0
    assert session_row(world).state == DemonstrationSession.State.RECORDING


# --- Ordering and interaction with the UCR save stream -----------------------


@pytest.mark.django_db
@frame
def test_navigation_and_save_events_share_one_sequence(db):
    """Screens and saves interleave in the one deterministic order the server
    recorded them, whatever order the requests arrived in."""
    world = recording("nav-interleave")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    assert screen(client, "single-window-create-ucr").status_code == 200
    saved = json.loads(post_json(client, save_body()).content)
    assert screen(client, "single-window-search-ucr").status_code == 200

    captured = events(world)
    assert [(event.sequence, event.event_type) for event in captured] == [
        (1, "navigation"),
        (2, "record_created"),
        (3, "navigation"),
    ]
    assert captured[1].record_id == saved["id"]

    payload = client.get(reverse("hybrid-demonstration-session")).json()
    assert [event["sequence"] for event in payload["events"]] == [1, 2, 3]
    assert payload["events"][0]["route_name"] == "single-window-create-ucr"
    assert payload["events"][2]["action_code"] == "ucr.search_opened"
    assert payload["session"]["event_count"] == 3


@pytest.mark.django_db
@frame
def test_a_demonstration_record_reload_keeps_the_timeline_single_sourced(db):
    """The 1B.1 draft reload and the 1C navigation capture meet on one screen:
    the saved record reloads into the form, the screen is captured once (the
    reload is the screen the recording is already on), and the record itself
    stays scoped to the session."""
    world = recording("nav-reload")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    saved = json.loads(post_json(client, save_body()).content)

    assert screen(client, "single-window-create-ucr").status_code == 200
    reloaded = client.get(
        f"{reverse('single-window-create-ucr')}?draft={saved['id']}", **FRAME_HEADERS
    )

    assert reloaded.status_code == 200
    assert saved["temp_no"] in reloaded.content.decode()
    assert navigation_routes(world) == ["single-window-create-ucr"]
    assert [(event.sequence, event.event_type) for event in events(world)] == [
        (1, "record_created"),
        (2, "navigation"),
    ]  # the reload is the screen the recording is already on: captured once
    record = UcrDeclaration.all_objects.get(pk=saved["id"])
    assert record.demonstration_session_id == world["session"].pk
