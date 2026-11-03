"""UI 4 Stage 1A — recording security, lifecycle and event integrity.

The five rules that make a demonstration action legitimate are tested where the
service enforces them — server-side binding, instructor identity, draft lesson
scope, lifecycle state, and an explicit route/action allowlist — and, for the
endpoints, at the gate the browser actually meets.

``DEMONSTRATION_RECORDING_ENABLED`` is exercised both ways: off, every endpoint
refuses; on, the service still refuses anything that fails identity, scope or
state, because the flag can close a door and never widen one.
"""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import (
    IntegrityError,
    InterfaceError,
    OperationalError,
    close_old_connections,
    connection,
    transaction,
)
from django.db.models.query import QuerySet
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import demo_ucr, draft_world, instructor, lesson, recording, request_for
from hybrid import demonstration_views, demonstrations, instructor_views, verification
from hybrid.models import DemonstrationEvent, DemonstrationSession
from onboarding.models import ProgrammeVersion
from scenarios.demonstration_ucr import next_demonstration_temp_no
from scenarios.models import UcrDeclaration

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)


# --- Helpers -----------------------------------------------------------------


def capture_request(world):
    """A request from the browser that holds this world's session."""
    return request_for(world["instructor"], bound=world["session"].pk)


def append_navigation(world, route_name="simulator-portal", **kwargs):
    return demonstrations.append_navigation_event(capture_request(world), route_name=route_name, **kwargs)


def live_session(world):
    return DemonstrationSession.objects.get(pk=world["session"].pk)


# --- The feature flag --------------------------------------------------------


@pytest.mark.django_db
def test_every_recording_endpoint_refuses_while_the_flag_is_off(db):
    world = recording("flag-off")
    client = Client()
    client.force_login(world["instructor"])
    lesson_id = world["lesson"].pk

    responses = [
        client.post(reverse("hybrid-demonstration-start", args=[lesson_id])),
        client.post(reverse("hybrid-demonstration-pause")),
        client.post(reverse("hybrid-demonstration-resume")),
        client.post(reverse("hybrid-demonstration-stop")),
        client.post(reverse("hybrid-demonstration-discard"), {"session_id": str(world["session"].pk)}),
        client.get(reverse("hybrid-demonstration-session")),
    ]

    assert {response.status_code for response in responses} == {403}
    assert {response.json()["code"] for response in responses} == {"recording_disabled"}
    # Refused means unchanged: the session this world started with is as it was.
    assert live_session(world).state == "recording"


@pytest.mark.django_db
@enabled
def test_the_flag_does_not_replace_authorization(db):
    """On, the service still judges identity and draft scope for itself."""
    world = recording("flag-authz")
    student = User.objects.create_user(username="flag-student", email="s@example.test", password="x")
    client = Client()
    client.force_login(student)

    refused = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))

    assert refused.status_code == 403
    assert refused.json()["code"] == "not_instructor"
    # Nothing new was opened: only the world's own pre-made session exists.
    assert DemonstrationSession.objects.filter(instructor=student).count() == 0


# --- Who may record ----------------------------------------------------------


@pytest.mark.django_db
def test_bare_staff_is_not_authority_to_record(db):
    """Decision 6: the Studio's canonical rule, not the simulator's wider one."""
    staff = User.objects.create_user(username="bare-staff", email="staff@example.test", password="x", is_staff=True)
    assert staff.is_staff is True
    assert staff.groups.count() == 0

    with pytest.raises(PermissionDenied):
        demonstrations.authorized_instructor(staff)

    world = draft_world("staff-world")
    with pytest.raises(PermissionDenied):
        demonstrations.start_recording(request_for(staff), world["lesson"])
    assert DemonstrationSession.objects.filter(instructor=staff).count() == 0


@pytest.mark.django_db
def test_a_superuser_may_record(db):
    root = User.objects.create_superuser(username="root-recorder", email="root@example.test", password="x")
    world = draft_world("root-world", given_instructor=root)

    session = demonstrations.start_recording(request_for(root), world["lesson"])

    assert session.state == DemonstrationSession.State.RECORDING
    assert session.instructor_id == root.pk


@pytest.mark.django_db
def test_anonymous_browsers_are_redirected_not_served(db):
    client = Client()
    response = client.post(reverse("hybrid-demonstration-start", args=[uuid.uuid4()]))

    assert response.status_code == 302
    assert settings.LOGIN_URL in response.url


@pytest.mark.django_db
@enabled
def test_a_post_without_a_csrf_token_is_refused_and_persists_nothing(db):
    world = draft_world("csrf")
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(world["instructor"])

    response = csrf_client.post(
        reverse("hybrid-demonstration-start", args=[world["lesson"].pk]),
        content_type="application/json",
    )

    assert response.status_code == 403
    assert DemonstrationSession.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_a_get_is_not_accepted_by_the_lifecycle_routes(db):
    world = recording("methods")
    client = Client()
    client.force_login(world["instructor"])

    assert client.get(reverse("hybrid-demonstration-start", args=[world["lesson"].pk])).status_code == 405
    assert client.get(reverse("hybrid-demonstration-stop")).status_code == 405


@pytest.mark.django_db
def test_a_published_lesson_cannot_be_recorded(db):
    world = recording("published-lesson")
    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.start_recording(request_for(world["instructor"]), world["lesson"])

    assert caught.value.code == "lesson_not_draft"
    assert caught.value.status == 403


@pytest.mark.django_db
@enabled
def test_the_start_route_only_resolves_a_draft_lesson(db):
    world = recording("route-draft")
    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))
    client = Client()
    client.force_login(world["instructor"])

    assert client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk])).status_code == 404


# --- Binding -----------------------------------------------------------------


@pytest.mark.django_db
def test_start_binds_the_server_resolved_session_to_this_browser(db):
    world = draft_world("bind")
    request = request_for(world["instructor"])

    session = demonstrations.start_recording(request, world["lesson"])

    assert request.session[demonstrations.ACTIVE_SESSION_KEY] == str(session.pk)
    assert demonstrations.resolve_bound_session(request).pk == session.pk
    assert session.lesson_id == world["lesson"].pk


@pytest.mark.django_db
def test_a_forged_session_identifier_is_never_honored(db):
    mine = recording("forged-mine")
    theirs = recording("forged-theirs")
    request = request_for(mine["instructor"], bound=mine["session"].pk)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.require_bound_session(request, theirs["session"].pk)

    assert caught.value.code == "session_mismatch"
    assert live_session(theirs).state == "recording"


@pytest.mark.django_db
def test_a_binding_never_resolves_another_instructors_session(db):
    """Ownership is a database fact on the read, not a value in the cookie."""
    mine = recording("cross-mine")
    theirs = recording("cross-theirs")
    intruder = request_for(mine["instructor"], bound=theirs["session"].pk)

    assert demonstrations.resolve_bound_session(intruder) is None
    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.append_navigation_event(intruder, route_name="simulator-portal")
    assert caught.value.code == "no_active_session"
    assert DemonstrationEvent.objects.filter(session_id=theirs["session"].pk).count() == 0


@pytest.mark.django_db
def test_a_binding_dropped_by_stop_cannot_be_replayed(db):
    world = draft_world("stale-binding")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])
    demonstrations.stop_recording(request, str(session.pk), session.version)

    assert request.session.get(demonstrations.ACTIVE_SESSION_KEY) is None
    replay = request_for(world["instructor"], bound=session.pk)
    assert demonstrations.resolve_bound_session(replay) is None


@pytest.mark.django_db
def test_publishing_the_edition_drops_a_live_binding(db):
    world = recording("publish-binding")
    request = capture_request(world)
    assert demonstrations.resolve_bound_session(request).pk == world["session"].pk

    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))

    assert demonstrations.resolve_bound_session(request) is None
    assert request.session.get(demonstrations.ACTIVE_SESSION_KEY) is None
    assert demonstrations.lesson_is_draft(live_session(world)) is False


# --- Lifecycle ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_second_recording_is_refused_while_one_is_live(db):
    world = draft_world("one-live")
    request = request_for(world["instructor"])
    demonstrations.start_recording(request, world["lesson"])

    second_lesson = lesson("one-live-second", world["version"])["lesson"]
    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.start_recording(request_for(world["instructor"]), second_lesson)

    assert caught.value.code == "session_active"
    assert DemonstrationSession.objects.filter(instructor=world["instructor"]).count() == 1


@pytest.mark.django_db
def test_the_lifecycle_walk_stamps_and_seals(db):
    world = draft_world("walk")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])

    paused = demonstrations.pause_recording(request, str(session.pk), session.version)
    assert paused.state == "paused"
    assert paused.paused_at is not None

    resumed = demonstrations.resume_recording(request, str(session.pk), paused.version)
    assert resumed.state == "recording"

    stopped = demonstrations.stop_recording(request, str(session.pk), resumed.version)
    assert stopped.state == "stopped"
    assert stopped.retention_expires_at == stopped.stopped_at + timezone.timedelta(days=demonstrations.RETENTION_DAYS)
    assert stopped.version == session.version + 3

    # Sealed: the browser is unbound, so nothing more can be appended.
    assert demonstrations.resolve_bound_session(request) is None


@pytest.mark.django_db
def test_a_stopped_session_can_be_recorded_again(db):
    world = draft_world("restart")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])
    demonstrations.stop_recording(request, str(session.pk), session.version)

    again = demonstrations.start_recording(request_for(world["instructor"]), world["lesson"])

    assert again.pk != session.pk
    assert DemonstrationSession.objects.filter(instructor=world["instructor"]).count() == 2


@pytest.mark.django_db
def test_invalid_transitions_are_refused(db):
    world = draft_world("transitions")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])
    paused = demonstrations.pause_recording(request, str(session.pk), session.version)

    # Pausing an already-paused session asks for a transition that did not happen.
    with pytest.raises(demonstrations.DemonstrationError) as double_pause:
        demonstrations.pause_recording(request, str(session.pk), paused.version)
    assert double_pause.value.code == "stale_session"

    stopped = demonstrations.stop_recording(request, str(session.pk), paused.version)
    with pytest.raises(demonstrations.DemonstrationError) as resume_after_stop:
        demonstrations.resume_recording(request, str(session.pk), stopped.version)
    assert resume_after_stop.value.code == "no_active_session"

    with pytest.raises(demonstrations.DemonstrationError) as stop_again:
        demonstrations.stop_recording(
            request_for(world["instructor"], bound=session.pk), str(session.pk), stopped.version
        )
    assert stop_again.value.code == "no_active_session"


@pytest.mark.django_db
def test_a_stale_version_refuses_the_control(db):
    world = draft_world("stale-version")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])
    demonstrations.pause_recording(request, str(session.pk), session.version)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.resume_recording(request, str(session.pk), session.version)  # the version it started with

    assert caught.value.code == "stale_session"
    assert DemonstrationSession.objects.get(pk=session.pk).state == "paused"


@pytest.mark.django_db
def test_a_control_without_a_version_is_refused(db):
    world = recording("no-version")
    request = capture_request(world)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.pause_recording(request, str(world["session"].pk), None)

    assert caught.value.code == "version_required"
    assert live_session(world).state == "recording"


@pytest.mark.django_db
@enabled
def test_the_lifecycle_endpoints_drive_the_same_service(db):
    world = draft_world("endpoints")
    client = Client()
    client.force_login(world["instructor"])

    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk])).json()
    assert started["ok"] is True
    body = {"session_id": started["session"]["id"], "version": started["session"]["version"]}

    def control(name, payload):
        return client.post(
            reverse(name), json.dumps(payload), content_type="application/json"
        ).json()

    paused = control("hybrid-demonstration-pause", {**body, "version": started["session"]["version"]})
    assert paused["session"]["state"] == "paused"

    resumed = control("hybrid-demonstration-resume", {**body, "version": paused["session"]["version"]})
    assert resumed["session"]["state"] == "recording"

    stopped = control("hybrid-demonstration-stop", {**body, "version": resumed["session"]["version"]})
    assert stopped["session"]["state"] == "stopped"
    assert stopped["session"]["retention_expires_at"] is not None

    # The browser no longer holds a session.
    assert client.get(reverse("hybrid-demonstration-session")).json()["session"] is None


@pytest.mark.django_db
@enabled
def test_extra_fields_in_a_control_body_are_ignored(db):
    """The request supplies a session id and a version; authority comes from above."""
    world = draft_world("evil-body")
    client = Client()
    client.force_login(world["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk])).json()

    response = client.post(
        reverse("hybrid-demonstration-pause"),
        json.dumps({
            "session_id": started["session"]["id"],
            "version": started["session"]["version"],
            "state": "recording",
            "instructor": str(uuid.uuid4()),
            "lesson": str(uuid.uuid4()),
            "retention_expires_at": None,
        }),
        content_type="application/json",
    )

    assert response.json()["session"]["state"] == "paused"
    assert response.json()["session"]["id"] == started["session"]["id"]


@pytest.mark.django_db
@enabled
def test_a_body_naming_another_instructors_session_is_refused(db):
    mine = draft_world("body-mine")
    theirs = recording("body-theirs")
    client = Client()
    client.force_login(mine["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[mine["lesson"].pk])).json()

    refused = client.post(
        reverse("hybrid-demonstration-pause"),
        json.dumps({"session_id": str(theirs["session"].pk), "version": started["session"]["version"]}),
        content_type="application/json",
    )

    assert refused.status_code == 409
    assert refused.json()["code"] == "session_mismatch"
    assert DemonstrationSession.objects.get(pk=theirs["session"].pk).state == "recording"


# --- Abandoned recordings (Stage 1A.1) --------------------------------------


def _backdate(session, minutes):
    """Move the activity stamp back without touching state or version."""
    DemonstrationSession.objects.filter(pk=session.pk).update(
        last_activity_at=timezone.now() - timedelta(minutes=minutes)
    )
    session.refresh_from_db()
    return session


@pytest.mark.django_db
def test_inactivity_is_measured_from_deliberate_activity_not_from_the_clock(db):
    world = recording("idle-boundary")

    assert demonstrations._is_idle(_backdate(world["session"], 29)) is False
    assert demonstrations._is_idle(_backdate(world["session"], 30)) is True

    # A read is not an action. Polling the studio must not hold a recording open,
    # or a page left on a desk would keep the session live indefinitely.
    request = capture_request(world)
    before = DemonstrationSession.objects.get(pk=world["session"].pk)

    assert demonstrations.resolve_bound_session(request) is not None

    after = DemonstrationSession.objects.get(pk=world["session"].pk)
    assert after.last_activity_at == before.last_activity_at
    assert after.version == before.version
    assert after.state == "recording"


@pytest.mark.django_db
def test_a_control_and_a_capture_each_move_the_deadline(db):
    world = recording("idle-activity")
    _backdate(world["session"], 20)

    paused = demonstrations.pause_recording(capture_request(world), str(world["session"].pk), 1)
    assert paused.last_activity_at > timezone.now() - timedelta(minutes=1)

    resumed = demonstrations.resume_recording(capture_request(world), str(world["session"].pk), paused.version)
    _backdate(resumed, 25)
    append_navigation(world)

    after = live_session(world)
    assert after.last_activity_at > timezone.now() - timedelta(minutes=1)
    assert after.state == "recording"


@pytest.mark.django_db
def test_a_control_after_the_window_seals_the_session_and_keeps_its_timeline(db):
    world = recording("idle-seal")
    append_navigation(world)
    record = demo_ucr(live_session(world))
    version = live_session(world).version
    _backdate(live_session(world), 31)
    request = capture_request(world)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.stop_recording(request, str(world["session"].pk), version)

    assert caught.value.code == "session_idle"
    assert caught.value.status == 409
    sealed = DemonstrationSession.objects.get(pk=world["session"].pk)
    assert sealed.state == "stopped"
    assert sealed.stopped_at is not None
    # The seal is the server's decision, not instructor activity: the gap between
    # the last real action and the seal is what marks the run as abandoned.
    assert sealed.last_activity_at < sealed.stopped_at - timedelta(minutes=30)
    assert sealed.retention_expires_at == sealed.stopped_at + timedelta(days=demonstrations.RETENTION_DAYS)
    assert request.session.get(demonstrations.ACTIVE_SESSION_KEY) is None
    # Nothing was thrown away: the timeline and the scoped record stay reviewable.
    assert [row["sequence"] for row in demonstrations.timeline(sealed)] == [1]
    assert UcrDeclaration.all_objects.filter(pk=record.pk).exists() is True


@pytest.mark.django_db
def test_a_paused_session_lapses_on_the_same_clock(db):
    world = recording("idle-paused")
    paused = demonstrations.pause_recording(capture_request(world), str(world["session"].pk), 1)
    _backdate(paused, 31)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.resume_recording(capture_request(world), str(world["session"].pk), paused.version)

    assert caught.value.code == "session_idle"
    assert DemonstrationSession.objects.get(pk=world["session"].pk).state == "stopped"


@pytest.mark.django_db
def test_the_sweep_seals_both_live_states_and_no_one_else(db):
    stale = recording("sweep-recording")
    stale_paused = recording("sweep-paused")
    paused = demonstrations.pause_recording(capture_request(stale_paused), str(stale_paused["session"].pk), 1)
    current = recording("sweep-current")
    terminal = recording("sweep-terminal")
    demonstrations.stop_recording(capture_request(terminal), str(terminal["session"].pk), 1)
    _backdate(stale["session"], 31)
    _backdate(paused, 31)
    _backdate(current["session"], 5)

    assert demonstrations.seal_abandoned_sessions() == 2

    assert DemonstrationSession.objects.get(pk=stale["session"].pk).state == "stopped"
    assert DemonstrationSession.objects.get(pk=stale_paused["session"].pk).state == "stopped"
    assert DemonstrationSession.objects.get(pk=current["session"].pk).state == "recording"
    assert DemonstrationSession.objects.get(pk=terminal["session"].pk).state == "stopped"
    # Running again finds nothing: the sweep is idempotent.
    assert demonstrations.seal_abandoned_sessions() == 0


@pytest.mark.django_db
def test_starting_again_frees_the_slot_an_abandoned_recording_held(db):
    world = recording("idle-restart")
    record = demo_ucr(world["session"])
    append_navigation(world)
    _backdate(live_session(world), 45)
    second_lesson = lesson("idle-restart-second", world["version"])["lesson"]

    started = demonstrations.start_recording(capture_request(world), second_lesson)

    assert started.pk != world["session"].pk
    assert started.state == "recording"
    abandoned = DemonstrationSession.objects.get(pk=world["session"].pk)
    assert abandoned.state == "stopped"
    assert abandoned.retention_expires_at is not None
    # The lapsed run is preserved for review, not deleted to free the slot.
    assert DemonstrationEvent.objects.filter(session_id=abandoned.pk).count() == 1
    assert UcrDeclaration.all_objects.filter(pk=record.pk).exists() is True


@pytest.mark.django_db
def test_a_sealed_session_stays_terminal_but_its_owner_can_still_discard(db):
    world = recording("idle-terminal")
    append_navigation(world)
    version = live_session(world).version
    _backdate(live_session(world), 31)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.pause_recording(capture_request(world), str(world["session"].pk), version)
    assert caught.value.code == "session_idle"

    # No late control reopens it, whatever version the browser thought it held.
    for control in (demonstrations.resume_recording, demonstrations.pause_recording):
        with pytest.raises(demonstrations.DemonstrationError) as refused:
            control(capture_request(world), str(world["session"].pk), version + 1)
        assert refused.value.code == "no_active_session"

    # The owner can still clear the data out; nobody else has a path at all.
    discarded = demonstrations.discard_recording(capture_request(world), str(world["session"].pk))
    assert discarded.state == "discarded"


@pytest.mark.django_db
def test_no_administrator_can_take_over_a_live_recording(db):
    from django.contrib import admin as django_admin

    world = recording("idle-admin")
    administrator = User.objects.create_superuser(
        username="idle-root", email="root@example.test", password="x"
    )
    request = request_for(administrator, bound=world["session"].pk)

    assert demonstrations.resolve_bound_session(request) is None
    for control in (demonstrations.stop_recording, demonstrations.resume_recording):
        with pytest.raises(demonstrations.DemonstrationError) as refused:
            control(request, str(world["session"].pk), 1)
        assert refused.value.code == "no_active_session"
    with pytest.raises(demonstrations.DemonstrationError) as discard:
        demonstrations.discard_recording(request, str(world["session"].pk))
    assert discard.value.code == "session_gone"

    # There is no administrative handle to take over with: the two models are
    # not registered, so no changelist, inline or bulk action reaches a session.
    assert django_admin.site.is_registered(DemonstrationSession) is False
    assert django_admin.site.is_registered(DemonstrationEvent) is False
    assert DemonstrationSession.objects.get(pk=world["session"].pk).state == "recording"


@pytest.mark.django_db
def test_the_cleanup_command_runs_both_sweeps(db):
    from django.core.management import call_command
    from io import StringIO

    idle = recording("command-idle")
    stopped = recording("command-stopped")
    discarded = recording("command-discarded")
    current = recording("command-current")
    ordinary = UcrDeclaration.objects.create(
        owner=stopped["instructor"], temp_no=next_demonstration_temp_no(), regime="CO"
    )
    _backdate(idle["session"], 31)
    demonstrations.stop_recording(capture_request(stopped), str(stopped["session"].pk), 1)
    demonstrations.discard_recording(capture_request(discarded), str(discarded["session"].pk))
    DemonstrationSession.objects.filter(
        pk__in=[stopped["session"].pk, discarded["session"].pk]
    ).update(retention_expires_at=timezone.now() - timedelta(minutes=1))

    out = StringIO()
    call_command("expire_demonstrations", stdout=out)

    assert "Sealed 1 abandoned, removed 2 expired." in out.getvalue()
    # The abandoned run was sealed, not deleted; the two due rows were collected.
    assert DemonstrationSession.objects.get(pk=idle["session"].pk).state == "stopped"
    assert DemonstrationSession.objects.filter(pk=stopped["session"].pk).exists() is False
    assert DemonstrationSession.objects.filter(pk=discarded["session"].pk).exists() is False
    assert DemonstrationSession.objects.filter(pk=current["session"].pk).exists() is True
    # Ordinary work and the lesson itself are outside this sweep's reach.
    assert UcrDeclaration.all_objects.filter(pk=ordinary.pk).exists() is True
    idle["lesson"].refresh_from_db()


# --- Capture -----------------------------------------------------------------


@pytest.mark.django_db
def test_sequences_are_monotonic_across_pause_and_resume(db):
    world = recording("sequences")
    request = capture_request(world)

    first = demonstrations.append_navigation_event(request, route_name="simulator-portal")
    assert first.sequence == 1

    version = live_session(world).version
    paused = demonstrations.pause_recording(request, str(world["session"].pk), version)
    with pytest.raises(demonstrations.DemonstrationError) as while_paused:
        demonstrations.append_navigation_event(request, route_name="simulator-portal")
    assert while_paused.value.code == "session_not_recording"

    resumed = demonstrations.resume_recording(request, str(world["session"].pk), paused.version)
    second = demonstrations.append_navigation_event(request, route_name="single-window-overview")

    assert [first.sequence, second.sequence] == [1, 2]
    assert live_session(world).next_sequence == 3
    assert resumed.state == "recording"


@pytest.mark.django_db
def test_a_duplicate_idempotency_key_returns_the_original_event(db):
    world = recording("idempotent")
    request = capture_request(world)
    key = str(uuid.uuid4())

    first = demonstrations.append_navigation_event(request, route_name="simulator-portal", idempotency_key=key)
    retry = demonstrations.append_navigation_event(request, route_name="simulator-portal", idempotency_key=key)

    assert retry.pk == first.pk
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 1
    # The rolled-back reservation did not burn a sequence number.
    assert live_session(world).next_sequence == 2


@pytest.mark.django_db
def test_a_malformed_idempotency_key_is_refused_not_replaced(db):
    """A supplied key means "this attempt", so a broken one cannot be guessed at.

    Silently generating a fresh key would turn a client that mangled its own key
    into two events with two sequence numbers — the timeline would show an action
    twice, and the client would never learn its retry never retried. Absence is
    still tolerated (a first attempt has no key), an unparseable value is not.
    """
    world = recording("bad-key")
    request = capture_request(world)

    for value in ("not-a-uuid", "1", {"x": 1}, "5" * 40):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.append_navigation_event(request, route_name="simulator-portal", idempotency_key=value)
        assert caught.value.code == "idempotency_key_invalid"
        assert caught.value.status == 400

    # Nothing was written and no number was spent, on any of the attempts.
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 0
    assert live_session(world).next_sequence == 1
    # A key-less call still works, and so does a well-formed one.
    anonymous = demonstrations.append_navigation_event(request, route_name="simulator-portal")
    assert anonymous.sequence == 1
    key = uuid.uuid4()
    keyed = demonstrations.append_navigation_event(request, route_name="simulator-portal", idempotency_key=key)
    assert keyed.sequence == 2
    # The same key as text — the shape a JSON body carries — is the same attempt.
    retried = demonstrations.append_navigation_event(request, route_name="simulator-portal", idempotency_key=str(key))
    assert retried.pk == keyed.pk
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 2


@pytest.mark.django_db
def test_capture_stops_the_moment_the_session_stops_recording(db):
    world = recording("sealed")
    request = capture_request(world)
    append_navigation(world)
    demonstrations.stop_recording(request, str(world["session"].pk), live_session(world).version)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.append_navigation_event(request, route_name="simulator-portal")
    assert caught.value.code == "no_active_session"
    assert live_session(world).next_sequence == 2


@pytest.mark.django_db
def test_an_unapproved_event_type_or_action_is_refused(db):
    world = recording("event-types")
    request = capture_request(world)
    record = demo_ucr(world["session"])

    cases = (
        ({"event_type": "selection", "record_kind": "ucr", "record_id": record.pk,
          "action_code": "ucr.field_changed", "payload": {}}, "event_denied"),
        ({"event_type": "record_created", "record_kind": "ucr", "record_id": record.pk,
          "action_code": "created a UCR for ACME", "payload": {}}, "action_denied"),
        ({"event_type": "record_created", "record_kind": "boe", "record_id": record.pk,
          "action_code": "boe.saved", "payload": {}}, "record_out_of_scope"),
        ({"event_type": "record_created", "record_kind": "ucr", "record_id": "abc",
          "action_code": "ucr.saved", "payload": {}}, "record_out_of_scope"),
    )
    for kwargs, code in cases:
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.append_record_event(request, **kwargs)
        assert caught.value.code == code
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 0


@pytest.mark.django_db
def test_a_record_event_requires_the_record_to_belong_to_this_session(db):
    world = recording("record-scope")
    other = recording("record-scope-other")
    request = capture_request(world)
    foreigns = demo_ucr(other["session"])
    ordinary = UcrDeclaration.objects.create(
        owner=world["instructor"], temp_no=next_demonstration_temp_no(), regime="CO",
    )

    for record_id in (foreigns.pk, ordinary.pk, 999999):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.append_record_event(
                request, event_type="record_updated", record_kind="ucr", record_id=record_id,
                action_code="ucr.saved", payload={"result_status": "updated"},
            )
        assert caught.value.code == "record_out_of_scope"
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 0


@pytest.mark.django_db
def test_a_record_event_for_this_sessions_record_is_captured(db):
    world = recording("record-event")
    request = capture_request(world)
    record = demo_ucr(world["session"])

    event = demonstrations.append_record_event(
        request, event_type="record_created", record_kind="ucr", record_id=record.pk,
        action_code="ucr.saved", payload={"regime_code": "CO", "result_status": "saved"},
    )

    assert event.sequence == 1
    assert event.payload == {"regime_code": "CO", "result_status": "saved"}
    assert event.record_id == record.pk


# --- Payload discipline ------------------------------------------------------


@pytest.mark.django_db
def test_free_text_is_rejected_even_under_an_approved_key(db):
    world = recording("free-text")
    request = capture_request(world)
    record = demo_ucr(world["session"])

    def attempt(payload):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.append_record_event(
                request, event_type="record_updated", record_kind="ucr", record_id=record.pk,
                action_code="ucr.saved", payload=payload,
            )
        return caught.value

    for payload in (
        {"regime_code": "General Cargo regime"},
        {"transport_mode_code": "Sea freight by vessel"},
        {"changed_fields": ["ACME Trading"]},
        {"changed_fields": ["not_a_column"]},
        {"changed_fields": []},
        {"note": "the instructor typed something"},
        {"result_status": "failed"},
        {"result_status": "Declaration rejected: missing TIN"},
    ):
        assert attempt(payload).code == "payload_rejected"
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 0


@pytest.mark.django_db
def test_a_payload_must_be_an_object(db):
    world = recording("payload-shape")
    request = capture_request(world)
    record = demo_ucr(world["session"])

    for payload in (["exporter_name"], "exporter_name", 7):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.append_record_event(
                request, event_type="record_updated", record_kind="ucr", record_id=record.pk,
                action_code="ucr.saved", payload=payload,
            )
        assert caught.value.code == "payload_rejected"


@pytest.mark.django_db
def test_changed_fields_are_column_names_from_the_verification_registry(db):
    world = recording("fields")
    request = capture_request(world)
    record = demo_ucr(world["session"])

    event = demonstrations.append_record_event(
        request, event_type="record_updated", record_kind="ucr", record_id=record.pk,
        action_code="ucr.saved", payload={"changed_fields": ["exporter_name", "regime"], "result_status": "updated"},
    )

    assert event.payload["changed_fields"] == ["exporter_name", "regime"]
    assert set(event.payload["changed_fields"]) <= demonstrations.DEMONSTRATION_UCR_FIELDS


@pytest.mark.django_db
def test_no_value_in_a_payload_can_carry_an_email_or_an_address(db):
    world = recording("pii")
    request = capture_request(world)
    record = demo_ucr(world["session"], provider_email="acme@example.test")

    with pytest.raises(demonstrations.DemonstrationError):
        demonstrations.append_record_event(
            request, event_type="record_updated", record_kind="ucr", record_id=record.pk,
            action_code="ucr.saved", payload={"regime_code": "acme@example.test"},
        )
    assert DemonstrationEvent.objects.filter(session_id=world["session"].pk).count() == 0


# --- The route manifest ------------------------------------------------------


def test_the_manifest_reads_approved_routes_and_denies_every_write():
    for route in ("simulator-portal", "single-window-overview", "single-window-create-ucr",
                  "single-window-search-ucr", "ucr-detail"):
        assert demonstrations.assert_route_authorized(route, "GET") is True
        for method in ("POST", "PUT", "DELETE"):
            with pytest.raises(demonstrations.DemonstrationError) as caught:
                demonstrations.assert_route_authorized(route, method)
            assert caught.value.code == "route_denied"


def test_ucr_save_is_listed_but_carries_no_method_until_stage_1b():
    assert "ucr-save" in demonstrations.DEMONSTRATION_ROUTE_PERMISSIONS
    assert demonstrations.DEMONSTRATION_ROUTE_PERMISSIONS["ucr-save"] == frozenset()
    for method in ("GET", "POST", "PUT", "DELETE"):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.assert_route_authorized("ucr-save", method)
        assert caught.value.code == "route_denied"


def test_everything_outside_the_manifest_is_denied_by_construction():
    for route in ("ucr-submit", "ucr-attachment", "ucr-clone", "ucr-amend", "boe-create",
                  "mda-consignment-application-save", "application-save", "consignment-submit", "",
                  "single-window-overview "):
        with pytest.raises(demonstrations.DemonstrationError) as caught:
            demonstrations.assert_route_authorized(route, "GET")
        assert caught.value.code == "route_denied"


@pytest.mark.django_db
def test_navigation_capture_uses_the_manifest_and_never_invents_a_code(db):
    world = recording("navigation")

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        append_navigation(world, route_name="ucr-submit")
    assert caught.value.code == "route_denied"

    event = append_navigation(world, route_name="ucr-detail")
    assert (event.route_name, event.action_code) == ("ucr-detail", "ucr.detail_opened")
    assert event.event_type == "navigation"


@pytest.mark.django_db
def test_a_route_name_that_is_not_a_token_is_refused(db):
    world = recording("route-name-shape")

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations._validated(
            event_type="navigation", action_code="portal.opened",
            route_name="/practical/portal/?teacher=Ada", record_kind="", record_id=None, payload={},
        )
    assert caught.value.code == "route_denied"


# --- Contention and ordering -------------------------------------------------


@pytest.mark.django_db
def test_contention_retries_the_whole_operation(db, monkeypatch):
    world = recording("retry")
    calls = {"count": 0}
    original = demonstrations._reserve_sequence

    def flaky(session_pk, expected_state, moment):
        calls["count"] += 1
        if calls["count"] == 1:
            raise demonstrations.SequenceContention()
        return original(session_pk, expected_state, moment)

    monkeypatch.setattr(demonstrations, "_reserve_sequence", flaky)

    event = append_navigation(world)

    assert event.sequence == 1
    assert calls["count"] == 2
    assert live_session(world).next_sequence == 2


@pytest.mark.django_db
def test_lock_contention_is_retried_and_other_errors_are_not(db, monkeypatch):
    world = recording("contention")
    original = demonstrations._reserve_sequence
    state = {"locked": True}

    def contended(session_pk, expected_state, moment):
        if state["locked"]:
            state["locked"] = False
            raise _contention_error()
        return original(session_pk, expected_state, moment)

    monkeypatch.setattr(demonstrations, "_reserve_sequence", contended)
    assert append_navigation(world).sequence == 1

    def broken(session_pk, expected_state, moment):
        raise _fatal_error()

    monkeypatch.setattr(demonstrations, "_reserve_sequence", broken)
    with pytest.raises(OperationalError):
        append_navigation(world, route_name="single-window-overview")


@pytest.mark.django_db
def test_the_retry_budget_is_bounded_and_reports_busy(db, monkeypatch):
    world = recording("exhaust")
    attempts = {"count": 0}

    def always_contended(session_pk, expected_state, moment):
        attempts["count"] += 1
        raise demonstrations.SequenceContention()

    monkeypatch.setattr(demonstrations, "_reserve_sequence", always_contended)

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        append_navigation(world)

    assert caught.value.code == "sequence_contention"
    assert attempts["count"] == demonstrations.SEQUENCE_RETRY_ATTEMPTS
    assert live_session(world).next_sequence == 1


def _threaded_append(session_pk, username, route, barrier):
    close_old_connections()
    try:
        user = User.objects.get(username=username)
        barrier.wait(timeout=5)
        event = demonstrations.append_navigation_event(request_for(user, bound=session_pk), route_name=route)
        return ("appended", event.sequence)
    except demonstrations.DemonstrationError as refusal:
        # The service's own bounded answer to a race it could not land. Only the
        # busy codes are legitimate here: a refusal for scope, state or identity
        # would mean the race opened a door the rules are supposed to keep shut.
        if refusal.code not in {"sequence_contention", "session_busy"}:
            raise
        return ("busy", refusal.code)
    except (OperationalError, InterfaceError) as error:
        # The engine can refuse a simultaneous write outright, and the retry
        # budget can run out under load. That is contention, not the sequence
        # rule; the deterministic proofs are the contention tests above.
        if not verification.is_database_contention(error):
            raise
        return ("contended", None)
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_two_simultaneous_appends_take_distinct_sequences(transactional_db):
    world = recording("concurrent-append")
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result(timeout=10) for future in [
            pool.submit(_threaded_append, world["session"].pk, world["instructor"].username, route, barrier)
            for route in ("simulator-portal", "single-window-overview")
        ]]

    sequences = sorted(sequence for kind, sequence in outcomes if kind == "appended")
    # At least one write has to land. With none, every assertion below is
    # vacuously true and the test would pass on a run where SQLite turned both
    # browsers away — and any other answer than an append, an engine lock or the
    # service's own busy refusal is a failure, not a shade of success.
    assert sequences, outcomes
    assert {kind for kind, _ in outcomes} <= {"appended", "busy", "contended"}, outcomes
    assert len(sequences) == len(set(sequences)), outcomes
    assert sequences == list(range(1, len(sequences) + 1)), outcomes
    persisted = DemonstrationEvent.objects.filter(session_id=world["session"].pk)
    assert persisted.count() == len(sequences)
    assert set(persisted.values_list("sequence", flat=True)) == set(sequences)
    # A reservation that rolled back must not have burned a number either.
    assert DemonstrationSession.objects.get(pk=world["session"].pk).next_sequence == len(sequences) + 1


def _threaded_start(lesson_pk, username, barrier):
    close_old_connections()
    try:
        user = User.objects.get(username=username)
        draft = instructor_views._draft_lesson(lesson_pk)
        barrier.wait(timeout=5)
        try:
            return ("started", demonstrations.start_recording(request_for(user), draft).pk)
        except demonstrations.DemonstrationError as error:
            if error.code == "session_busy":
                return ("busy", error.code)
            return ("refused", error.code)
        except (OperationalError, InterfaceError) as error:
            if not verification.is_database_contention(error):
                raise
            return ("contended", None)
    finally:
        close_old_connections()


@pytest.mark.django_db
def test_the_database_forbids_two_live_sessions_for_one_instructor(db):
    """The conditional unique constraint arbitrates, independent of any pre-check."""
    world = recording("one-live-constraint")

    with pytest.raises(IntegrityError), transaction.atomic():
        DemonstrationSession.objects.create(
            lesson=world["lesson"], instructor=world["instructor"],
            state=DemonstrationSession.State.RECORDING, started_at=timezone.now(),
        )

    assert DemonstrationSession.objects.filter(instructor=world["instructor"]).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_browsers_cannot_open_two_live_sessions(transactional_db):
    """Two simultaneous starts leave at most one live session.

    SQLite reports a simultaneous write as a locked table rather than losing the
    constraint check, so an engine-level contention refusal is a legitimate
    outcome here; what may never happen is two live sessions for one instructor.
    One of the two browsers still has to get an answer it acted on — a run where
    both were turned away by the engine would leave the constraint untested and
    the assertions below vacuous. The deterministic proof of the constraint is the
    test above, and the same-instant PostgreSQL race is listed for verification in
    ``docs/demonstration-recording-operations.md``.
    """
    world = draft_world("concurrent-start")
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [future.result(timeout=10) for future in [
            pool.submit(_threaded_start, world["lesson"].pk, world["instructor"].username, barrier)
            for _ in range(2)
        ]]

    live = DemonstrationSession.objects.filter(
        instructor=world["instructor"], state=DemonstrationSession.State.RECORDING
    )
    kinds = {kind for kind, _ in outcomes}
    assert kinds <= {"started", "refused", "busy", "contended"}, outcomes
    assert "started" in kinds and live.count() == 1, outcomes
    assert len([pk for kind, pk in outcomes if kind == "started"]) == live.count()
    assert [code for kind, code in outcomes if kind == "refused"] == ["session_active"]


# --- Review, discard and the studio page ------------------------------------


@pytest.mark.django_db
def test_the_timeline_orders_by_sequence_never_by_timestamp(db):
    world = recording("timeline")
    for route in ("simulator-portal", "single-window-overview", "single-window-search-ucr"):
        append_navigation(world, route_name=route)
    # The first event is stamped newest: sequence, not the clock, is authoritative.
    DemonstrationEvent.objects.filter(session=world["session"], sequence=1).update(
        created_at=timezone.now() + timezone.timedelta(days=1)
    )

    rows = demonstrations.timeline(live_session(world))

    assert [row["sequence"] for row in rows] == [1, 2, 3]
    assert [row["action_code"] for row in rows] == ["portal.opened", "single_window.opened", "ucr.search_opened"]


@pytest.mark.django_db
@enabled
def test_the_session_endpoint_reports_state_and_ordered_events(db):
    world = draft_world("session-view")
    client = Client()
    client.force_login(world["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk])).json()
    demonstrations.append_navigation_event(
        request_for(world["instructor"], bound=started["session"]["id"]), route_name="simulator-portal"
    )

    payload = client.get(reverse("hybrid-demonstration-session")).json()

    assert payload["ok"] is True
    assert payload["session"]["state"] == "recording"
    assert payload["session"]["event_count"] == 1
    assert payload["session"]["record_count"] == 0
    assert [event["sequence"] for event in payload["events"]] == [1]


@pytest.mark.django_db
@enabled
def test_the_studio_page_itself_still_persists_nothing(db):
    """The read-only demonstration surface is untouched by Stage 1A."""
    world = draft_world("studio")
    client = Client()
    client.force_login(world["instructor"])

    response = client.get(reverse("hybrid-lesson-demonstration-studio", args=[world["lesson"].pk]))

    assert response.status_code == 200
    assert DemonstrationSession.objects.count() == 0
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
def test_discard_removes_the_events_and_records_of_one_session_only(db):
    mine = recording("discard")
    theirs = recording("discard-other")
    request = capture_request(mine)
    append_navigation(mine)
    record = demo_ucr(mine["session"])
    their_record = demo_ucr(theirs["session"])
    ordinary = UcrDeclaration.objects.create(
        owner=mine["instructor"], temp_no=next_demonstration_temp_no(), regime="CO",
    )

    session = demonstrations.discard_recording(request, str(mine["session"].pk))

    assert session.state == "discarded"
    # The tombstone is not kept forever: it goes on the same clock a stop puts
    # the session's data on, so the record that there was a recording lapses too.
    assert session.retention_expires_at == session.discarded_at + timedelta(days=demonstrations.RETENTION_DAYS)
    assert DemonstrationEvent.objects.filter(session_id=mine["session"].pk).count() == 0
    assert UcrDeclaration.all_objects.filter(pk=record.pk).exists() is False
    assert request.session.get(demonstrations.ACTIVE_SESSION_KEY) is None
    # Untouched: another session's record and every ordinary row.
    assert UcrDeclaration.all_objects.filter(pk=their_record.pk).exists() is True
    assert UcrDeclaration.objects.filter(pk=ordinary.pk).exists() is True


@pytest.mark.django_db
def test_discard_uses_the_scoped_helper_and_leaves_ordinary_rows(db):
    from scenarios.demonstration_ucr import delete_demonstration_ucrs

    world = recording("discard-scoped")
    mine = demo_ucr(world["session"])
    ordinary = UcrDeclaration.objects.create(
        owner=world["instructor"], temp_no=next_demonstration_temp_no(), regime="CO",
    )

    removed = delete_demonstration_ucrs(live_session(world))

    assert removed >= 1
    assert UcrDeclaration.all_objects.filter(pk=mine.pk).exists() is False
    assert UcrDeclaration.all_objects.filter(pk=ordinary.pk).exists() is True


@pytest.mark.django_db
def test_only_the_owner_may_discard(db):
    mine = recording("discard-owner")
    stranger = recording("discard-stranger")

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.discard_recording(request_for(stranger["instructor"]), str(mine["session"].pk))

    assert caught.value.code == "session_gone"
    assert DemonstrationSession.objects.filter(pk=mine["session"].pk).exists() is True


@pytest.mark.django_db
def test_a_garbage_session_identifier_is_refused_not_500(db):
    world = recording("garbage-id")

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.discard_recording(request_for(world["instructor"]), "not-a-uuid")

    assert caught.value.code == "session_gone"


@pytest.mark.django_db
def test_an_instructor_may_discard_a_stopped_session_before_its_deadline(db):
    world = draft_world("discard-stopped")
    request = request_for(world["instructor"])
    session = demonstrations.start_recording(request, world["lesson"])
    stopped = demonstrations.stop_recording(request, str(session.pk), session.version)
    record = demo_ucr(stopped)

    discarded = demonstrations.discard_recording(request, str(stopped.pk))

    assert discarded.state == "discarded"
    # Discarding a stopped session keeps the session row but drops its deadline
    # forward onto the tombstone's own clock — the data it held is already gone.
    assert discarded.retention_expires_at > timezone.now()
    assert discarded.retention_expires_at == discarded.discarded_at + timedelta(days=demonstrations.RETENTION_DAYS)
    assert UcrDeclaration.all_objects.filter(pk=record.pk).exists() is False


@pytest.mark.django_db
def test_a_discarded_session_accepts_nothing_further(db):
    world = recording("discard-again")
    request = capture_request(world)
    demonstrations.discard_recording(request, str(world["session"].pk))

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.append_navigation_event(
            request_for(world["instructor"], bound=world["session"].pk), route_name="simulator-portal"
        )
    assert caught.value.code == "no_active_session"
    # Discarding twice is a no-op, not an error.
    assert demonstrations.discard_recording(request, str(world["session"].pk)).state == "discarded"


@pytest.mark.django_db
def test_the_error_shape_the_browser_sees_is_machine_readable(db):
    world = recording("error-shape")

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations.require_bound_session(request_for(world["instructor"]))

    assert caught.value.as_json() == {
        "ok": False,
        "error": "No demonstration session is active for this instructor.",
        "code": "no_active_session",
    }


# --- Contention (Stage 1A.1) --------------------------------------------------


class _DriverLock(OperationalError):
    """A driver error carrying the SQLSTATE, the way psycopg reports a collision."""

    def __init__(self, code):
        super().__init__(f"simulated {code}")
        self.pgcode = code


def _contention_error():
    """The refusal the running backend raises when a statement loses a lock.

    Django rebuilds driver exceptions and keeps the original as ``__cause__``
    (``django/db/utils.py``), so a real PostgreSQL collision reaches the retry
    loop as a plain ``OperationalError`` whose cause carries the SQLSTATE. SQLite
    says the same thing in the message and has no code at all.
    """
    if connection.vendor == "postgresql":
        error = OperationalError("could not obtain lock on relation")
        error.__cause__ = _DriverLock("55P03")
        return error
    return OperationalError("database is locked")


def _fatal_error():
    """A statement error that no honest retry can improve."""
    if connection.vendor == "postgresql":
        error = OperationalError("simulated unique violation")
        error.__cause__ = _DriverLock("23505")
        return error
    return OperationalError("no such table: hybrid_demonstrationevent")


@pytest.mark.parametrize("code", ["40001", "40P01", "55P03"])
def test_postgres_names_its_collisions_by_sqlstate(db, monkeypatch, code):
    """The PostgreSQL branch, tested as a unit against the driver's own shape."""
    from django.db import connection

    monkeypatch.setattr(connection, "vendor", "postgresql", raising=False)
    assert demonstrations.is_database_contention(_DriverLock(code)) is True


def test_django_wrapped_postgres_collision_is_recognised(db, monkeypatch):
    """Django's wrapper strips the code into ``__cause__``; the classifier follows it."""
    from django.db import connection

    monkeypatch.setattr(connection, "vendor", "postgresql", raising=False)
    wrapped = OperationalError("could not obtain lock on relation")
    wrapped.__cause__ = _DriverLock("55P03")
    assert wrapped.__cause__ is not None
    assert getattr(wrapped, "sqlstate", None) is None
    assert demonstrations.is_database_contention(wrapped) is True
    wrapped.__cause__ = _DriverLock("23505")
    assert demonstrations.is_database_contention(wrapped) is False


@pytest.mark.skipif(connection.vendor != "postgresql", reason="needs a real PostgreSQL lock")
@pytest.mark.django_db
def test_a_real_postgres_lock_refusal_is_contention(db):
    """A lock this engine actually refuses is classified by its SQLSTATE.

    A second psycopg connection holds ``ACCESS EXCLUSIVE`` on a throwaway table;
    ``NOWAIT`` makes PostgreSQL answer 55P03 rather than wait.
    """
    import psycopg
    from django.conf import settings as django_settings

    config = django_settings.DATABASES["default"]
    holder = psycopg.connect(
        host=config["HOST"],
        port=config["PORT"],
        user=config["USER"],
        password=config["PASSWORD"],
        dbname=config["NAME"],
    )
    try:
        holder.execute("drop table if exists _pg_lock_probe")
        holder.execute("create table _pg_lock_probe (id integer)")
        holder.commit()
        holder.execute("lock table _pg_lock_probe in access exclusive mode")
        with pytest.raises(OperationalError) as caught:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("lock table _pg_lock_probe in access exclusive mode nowait")
        assert getattr(caught.value.__cause__, "sqlstate", None) == "55P03"
        assert demonstrations.is_database_contention(caught.value) is True
    finally:
        holder.rollback()
        holder.execute("drop table if exists _pg_lock_probe")
        holder.commit()
        holder.close()


def test_a_postgres_error_that_is_not_a_collision_is_not_retried(db, monkeypatch):
    from django.db import connection

    monkeypatch.setattr(connection, "vendor", "postgresql", raising=False)
    # 23505 unique violation, 23503 foreign key, 22001 value too long — all bugs,
    # all fatal, none of them improved by running them again.
    for code in ("23505", "23503", "22001"):
        assert demonstrations.is_database_contention(_DriverLock(code)) is False


def test_sqlite_says_contention_only_in_words(db, monkeypatch):
    from django.db import connection

    monkeypatch.setattr(connection, "vendor", "sqlite", raising=False)
    assert demonstrations.is_database_contention(OperationalError("database is locked")) is True
    assert demonstrations.is_database_contention(OperationalError("database table is locked: x")) is True
    assert demonstrations.is_database_contention(OperationalError("no such table: x")) is False
    # An engine with no rule here never looks like a lock.
    monkeypatch.setattr(connection, "vendor", "oracle", raising=False)
    assert demonstrations.is_database_contention(_DriverLock("55P03")) is False


@pytest.mark.django_db
def test_a_locked_statement_is_run_again_until_it_lands(db, monkeypatch):
    monkeypatch.setattr(demonstrations.time, "sleep", lambda *_: None)
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise _contention_error()
        return "written"

    assert demonstrations._retry_on_contention(flaky) == "written"
    assert len(attempts) == 3


@pytest.mark.django_db
def test_contention_that_outlasts_the_budget_becomes_a_refusal(db, monkeypatch):
    monkeypatch.setattr(demonstrations.time, "sleep", lambda *_: None)
    attempts = []

    def always_locked():
        attempts.append(1)
        raise _contention_error()

    with pytest.raises(demonstrations.DemonstrationError) as caught:
        demonstrations._retry_on_contention(always_locked)

    assert caught.value.code == "session_busy"
    assert caught.value.status == 503
    assert len(attempts) == demonstrations.CONTENTION_RETRY_ATTEMPTS


@pytest.mark.django_db
def test_a_statement_error_is_never_mistaken_for_a_lock(db):
    def broken():
        raise _fatal_error()

    with pytest.raises(OperationalError):
        demonstrations._retry_on_contention(broken)


@pytest.mark.django_db
def test_a_lifecycle_transition_repeats_after_a_lock_and_applies_once(db, monkeypatch):
    """The pause really did go through the retry: one refused statement, then the win."""
    world = recording("busy-transition")
    request = capture_request(world)
    version = live_session(world).version
    real_update = QuerySet.update
    statements = []

    def flaky_update(queryset, *args, **kwargs):
        if queryset.model is DemonstrationSession:
            statements.append(1)
            if len(statements) == 1:
                raise _contention_error()
        return real_update(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "update", flaky_update)
    monkeypatch.setattr(demonstrations.time, "sleep", lambda *_: None)

    session = demonstrations.pause_recording(request, str(world["session"].pk), version)

    assert session.state == DemonstrationSession.State.PAUSED
    assert len(statements) == 2


@pytest.mark.django_db
def test_a_binding_read_reruns_after_a_lock(db, monkeypatch):
    """Every entry point goes through the retry, including the read-only ones."""
    world = recording("busy-read")
    request = capture_request(world)
    refused = []

    def refuse_once(execute, sql, params, many, context):
        if "hybrid_demonstrationsession" in sql and not refused:
            refused.append(sql)
            raise _contention_error()
        return execute(sql, params, many, context)

    monkeypatch.setattr(demonstrations.time, "sleep", lambda *_: None)

    with connection.execute_wrapper(refuse_once):
        session = demonstrations.resolve_bound_session(request)

    assert session.pk == world["session"].pk
    assert len(refused) == 1


@pytest.mark.django_db
def test_a_database_too_busy_to_answer_keeps_the_lesson(db, monkeypatch):
    """The builder's question fails closed: busy means undeletable, never a 500."""
    world = recording("busy-lesson-guard")
    monkeypatch.setattr(demonstrations.time, "sleep", lambda *_: None)
    real_exists = QuerySet.exists

    def locked(queryset):
        if queryset.model is DemonstrationSession:
            raise _contention_error()
        return real_exists(queryset)

    monkeypatch.setattr(QuerySet, "exists", locked)

    assert demonstrations.lesson_is_recording([world["lesson"].pk]) is True


@enabled
@pytest.mark.django_db
def test_an_endpoint_answers_a_lock_with_503_not_500(db, monkeypatch):
    world = recording("busy-endpoint")
    bound_request = request_for(world["instructor"], bound=world["session"].pk, method="GET")

    def locked(session):
        raise _contention_error()

    monkeypatch.setattr(demonstrations, "session_payload", locked)

    response = demonstration_views.demonstration_session(bound_request)

    assert response.status_code == 503
    assert json.loads(response.content) == {
        "ok": False,
        "error": "The demonstration is busy. Try again in a moment.",
        "code": "session_busy",
    }


@enabled
@pytest.mark.django_db
def test_an_endpoint_still_propagates_an_error_that_is_not_a_lock(db, monkeypatch):
    world = recording("broken-endpoint")
    bound_request = request_for(world["instructor"], bound=world["session"].pk, method="GET")

    def broken(session):
        raise _fatal_error()

    monkeypatch.setattr(demonstrations, "session_payload", broken)

    with pytest.raises(OperationalError):
        demonstration_views.demonstration_session(bound_request)
