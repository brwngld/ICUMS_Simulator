"""UI 4 Stage 1B — the demonstration-scoped UCR save.

One write is approved for a recording: ``ucr-save`` POST, routed by the
browser's server-side binding into ``scenarios.demonstration_ucr``. The tests
cover the whole authorization chain (flag, manifest, binding, ownership, draft
lesson, lifecycle state, inactivity), the records it writes (scope, ownership,
reference allocation under races), the event it records (type, sequence,
payload, transactional consistency with the row), idempotency, and every
ordinary surface that must stay untouched — including the ordinary save route
itself, which must keep working exactly as before when no recording is bound.
"""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import IntegrityError, close_old_connections, connection
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import (
    SessionEngine,
    demo_ucr,
    draft_world,
    instructor,
    ordinary_ucr,
    recording,
)
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.demonstration_ucr import demonstration_save_applies, save_demonstration_ucr
from scenarios.models import UcrDeclaration

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)

DRAFT_SESSION_KEY = demonstrations.ACTIVE_SESSION_KEY


# --- Helpers -----------------------------------------------------------------


def bind_client(client, world):
    """Give this browser the world's server-side binding, as start would."""
    store = client.session
    store[DRAFT_SESSION_KEY] = str(world["session"].pk)
    store.save()


def save_body(**overrides):
    """A valid Create-UCR body, as the simulator page posts it."""
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Demonstration Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Demonstration Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Demonstration Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000002", "designation": "Manager",
        },
        "consignment": {
            "goods": "Training goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def bound_save_request(world, payload=None, **session_overrides):
    """A POST to the save route from the browser that holds the world's binding."""
    from django.test import RequestFactory

    body = dict(payload or {})
    request = RequestFactory().post(
        "/practical/single-window/ucr/save/",
        data=json.dumps(body),
        content_type="application/json",
    )
    request.user = world["instructor"]
    request.session = SessionEngine.SessionStore()
    binding = session_overrides.pop(DRAFT_SESSION_KEY, None) or str(world["session"].pk)
    if binding is not None:
        request.session[DRAFT_SESSION_KEY] = binding
    return request


def post_json(client, payload, **extra):
    return client.post(reverse("ucr-save"), json.dumps(payload), content_type="application/json", **extra)


def demo_rows():
    return list(UcrDeclaration.all_objects.filter(demonstration_session__isnull=False))


def session_row(world):
    return DemonstrationSession.objects.get(pk=world["session"].pk)


# --- When the branch applies -------------------------------------------------


@pytest.mark.django_db
def test_the_branch_applies_only_for_a_flag_on_bound_browser(db):
    world = recording("applies")
    request = bound_save_request(world)

    assert demonstration_save_applies(request) is False  # flag off, even bound
    with enabled:
        assert demonstration_save_applies(request) is True
        request.session.pop(DRAFT_SESSION_KEY)
        assert demonstration_save_applies(request) is False  # no binding, flag on


@pytest.mark.django_db
def test_an_authorized_instructor_save_creates_a_scoped_draft_and_its_event(db):
    world = recording("save-create")
    request = bound_save_request(world, save_body())

    response = save_demonstration_ucr(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["status"] == "draft"
    assert data["demonstration"] is True
    assert data["temp_no"].startswith("DEMOUCR")
    assert data["attachments"] == []
    assert data["recorded"]["sequence"] == 1
    assert data["recorded"]["action_code"] == "ucr.saved"
    record = UcrDeclaration.all_objects.get(pk=data["id"])
    assert record.demonstration_session_id == world["session"].pk
    assert record.owner_id == world["instructor"].pk
    assert record.status == UcrDeclaration.Status.DRAFT
    assert record.exporter_name == "Demonstration Exporter"
    event = DemonstrationEvent.objects.get(session_id=world["session"].pk, sequence=1)
    assert event.event_type == "record_created"
    assert event.record_kind == "ucr"
    assert event.record_id == record.pk
    assert event.payload == {"regime_code": "TN", "result_status": "saved"}
    # The save is deliberate activity: the inactivity deadline moved with it.
    assert session_row(world).last_activity_at > world["session"].last_activity_at


@pytest.mark.django_db
def test_the_save_does_not_create_learner_evidence_or_an_ordinary_record(db):
    world = recording("save-evidence")
    request = bound_save_request(world, save_body())

    data = json.loads(save_demonstration_ucr(request).content)

    record = UcrDeclaration.all_objects.get(pk=data["id"])
    assert record.demonstration_session_id is not None
    assert record not in UcrDeclaration.objects.all()
    assert record not in world["instructor"].ucr_declarations.all()
    assert DemonstrationSession.objects.get(pk=world["session"].pk).ucr_declarations.count() == 0


# --- The authorization chain -------------------------------------------------


@pytest.mark.django_db
def test_a_student_is_never_taken_into_the_demonstration_save(db):
    world = recording("save-student")
    student = User.objects.create_user(username="save-student", email="s@example.test", password="x")
    request = bound_save_request(world, save_body())
    request.user = student
    # The binding in a stolen browser session resolves against its own user
    # only; for the student it resolves to nothing, so the save is refused
    # outright rather than answered with an ordinary draft.
    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "no_active_session"
    assert UcrDeclaration.all_objects.count() == 0
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
def test_a_binding_is_never_resolved_across_instructors(db):
    world = recording("save-cross")
    other = draft_world("save-cross-other")
    request = bound_save_request(world, save_body())
    request.user = other["instructor"]  # holds a binding name it does not own

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "no_active_session"
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_a_paused_session_accepts_no_save(db):
    world = recording("save-paused")
    world["session"].state = DemonstrationSession.State.PAUSED
    world["session"].paused_at = timezone.now()
    world["session"].save(update_fields=("state", "paused_at"))
    request = bound_save_request(world, save_body())

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "session_not_recording"
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_a_stopped_session_is_refused_and_creates_nothing_at_all(db):
    """The binding no longer resolves, so the strict save refuses: no
    demonstration row, and — crucially — no ordinary record either."""
    world = recording("save-stopped")
    world["session"].state = DemonstrationSession.State.STOPPED
    world["session"].stopped_at = timezone.now()
    world["session"].retention_expires_at = timezone.now() + timedelta(days=30)
    world["session"].save(update_fields=("state", "stopped_at", "retention_expires_at"))
    request = bound_save_request(world, save_body())

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "no_active_session"
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_a_discarded_session_is_refused(db):
    world = recording("save-discarded")
    world["session"].state = DemonstrationSession.State.DISCARDED
    world["session"].discarded_at = timezone.now()
    world["session"].save(update_fields=("state", "discarded_at"))
    request = bound_save_request(world, save_body())

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_an_idle_recording_is_sealed_and_the_save_is_refused(db):
    world = recording("save-idle")
    DemonstrationSession.objects.filter(pk=world["session"].pk).update(
        last_activity_at=timezone.now() - demonstrations.INACTIVITY_TIMEOUT - timedelta(minutes=1)
    )
    request = bound_save_request(world, save_body())

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "session_idle"
    assert session_row(world).state == DemonstrationSession.State.STOPPED
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_a_published_lesson_ends_the_demonstration_save(db):
    from onboarding.models import ProgrammeVersion

    world = recording("save-published")
    world["version"].status = ProgrammeVersion.Status.PUBLISHED
    world["version"].save(update_fields=("status",))
    request = bound_save_request(world, save_body())

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "no_active_session"
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
def test_a_forged_binding_value_is_refused_without_creating_anything(db):
    world = recording("save-forged")
    request = bound_save_request(world, save_body(), **{DRAFT_SESSION_KEY: str(uuid.uuid4())})

    with enabled:
        response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert UcrDeclaration.all_objects.count() == 0


# --- The flag keeps the ordinary route itself unchanged ----------------------


@pytest.mark.django_db
def test_with_the_flag_off_a_bound_browser_still_saves_ordinarily(db):
    world = recording("save-flag-off")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    response = post_json(client, save_body())

    assert response.status_code == 200
    record = UcrDeclaration.objects.get(pk=response.json()["id"])
    assert record.demonstration_session_id is None
    assert record.temp_no.startswith("TEMPUCR")
    assert "demonstration" not in response.json()  # the ordinary answer is unchanged
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_an_unbound_browser_saves_ordinarily_while_the_flag_is_on(db):
    world = recording("save-unbound")
    client = Client()
    client.force_login(world["instructor"])

    response = post_json(client, save_body())

    assert response.status_code == 200
    record = UcrDeclaration.objects.get(pk=response.json()["id"])
    assert record.demonstration_session_id is None
    assert record.owner_id == world["instructor"].pk
    assert "demonstration" not in response.json()
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_a_student_with_a_credential_still_saves_ordinarily(db):
    from accounts.models import SimulatorCredential

    student = User.objects.create_user(username="save-sim-student", email="s@example.test", password="x")
    student.student_id = "SIM-001"
    student.save(update_fields=("student_id",))
    credential = SimulatorCredential.objects.create(user=student)
    credential.issue()
    client = Client()
    client.force_login(student)
    session = client.session
    session["simulator_user_id"] = str(student.pk)
    session.save()

    response = post_json(client, save_body())

    assert response.status_code == 200
    record = UcrDeclaration.objects.get(pk=response.json()["id"])
    assert record.owner_id == student.pk
    assert record.demonstration_session_id is None
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_the_demonstration_save_still_requires_a_csrf_token(db):
    world = recording("save-csrf")
    client = Client(enforce_csrf_checks=True)
    client.force_login(world["instructor"])
    bind_client(client, world)

    response = post_json(client, save_body())

    assert response.status_code == 403
    assert UcrDeclaration.all_objects.count() == 0
    assert DemonstrationEvent.objects.count() == 0


# --- Draft addressing --------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_second_save_updates_this_sessions_draft_and_records_an_update(db):
    world = recording("save-update")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    first = post_json(client, save_body()).json()

    changed = save_body(exporter={"name": "Renamed Exporter", "country": "GH", "address": "1 Export Road",
                                  "phone": "+233200000001", "contact": "Export Contact",
                                  "contact_no": "+233200000002", "designation": "Manager"})
    changed["draft_id"] = first["id"]
    response = post_json(client, changed)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == first["id"]
    assert data["temp_no"] == first["temp_no"]  # the reference is never reallocated
    record = UcrDeclaration.all_objects.get(pk=first["id"])
    assert record.exporter_name == "Renamed Exporter"
    event = DemonstrationEvent.objects.get(session_id=world["session"].pk, sequence=2)
    assert event.event_type == "record_updated"
    assert event.record_id == record.pk
    assert event.payload["result_status"] == "updated"
    assert event.payload["changed_fields"] == ["exporter_name"]
    assert set(event.payload["changed_fields"]) <= demonstrations.DEMONSTRATION_UCR_FIELDS


@pytest.mark.django_db
@enabled
def test_an_unchanged_resave_records_an_update_without_changed_fields(db):
    world = recording("save-resave")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    first = post_json(client, save_body()).json()

    again = save_body()
    again["draft_id"] = first["id"]
    response = post_json(client, again)

    assert response.status_code == 200
    event = DemonstrationEvent.objects.get(session_id=world["session"].pk, sequence=2)
    assert event.payload == {"regime_code": "TN", "result_status": "updated"}


@pytest.mark.django_db
@enabled
def test_a_save_addressing_an_ordinary_draft_is_refused(db):
    """A demonstration never writes an ordinary row, not even its owner's."""
    world = recording("save-ordinary-address")
    ordinary = ordinary_ucr(world["instructor"])
    request = bound_save_request(world, save_body(draft_id=ordinary.pk))

    response = save_demonstration_ucr(request)

    assert response.status_code == 403
    assert json.loads(response.content)["code"] == "record_out_of_scope"
    ordinary.refresh_from_db()
    assert ordinary.exporter_name == "ACME Trading"
    assert ordinary.demonstration_session_id is None


@pytest.mark.django_db
@enabled
def test_a_save_addressing_another_sessions_record_is_refused(db):
    world = recording("save-foreign-address")
    other = recording("save-foreign-address-other")
    foreign = demo_ucr(other["session"])
    request = bound_save_request(world, save_body(draft_id=foreign.pk))

    response = save_demonstration_ucr(request)

    assert response.status_code == 403
    assert json.loads(response.content)["code"] == "record_out_of_scope"
    foreign.refresh_from_db()
    assert foreign.exporter_name == "ACME Trading"


@pytest.mark.django_db
@enabled
def test_a_save_addressing_an_unknown_id_is_refused_not_substituted(db):
    world = recording("save-unknown-address")
    request = bound_save_request(world, save_body(draft_id=999_999))

    response = save_demonstration_ucr(request)

    assert response.status_code == 403
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
@enabled
def test_a_hidden_provider_section_saves_with_blank_provider_columns(db):
    """The ordinary route 500s on this shape today (a documented, out-of-scope
    defect); the demonstration save normalizes it instead of inheriting it."""
    world = recording("save-no-provider")
    request = bound_save_request(world, save_body(show_provider=False))

    response = save_demonstration_ucr(request)

    assert response.status_code == 200
    record = UcrDeclaration.all_objects.get(pk=json.loads(response.content)["id"])
    assert record.provider_name == ""
    assert record.declarant_code == ""


@pytest.mark.django_db
@enabled
def test_field_validation_errors_keep_the_ordinary_shape(db):
    world = recording("save-field-errors")
    request = bound_save_request(
        world, save_body(consignment={"goods": "", "origin": "GH", "destination": "CN", "mode": "10"})
    )

    response = save_demonstration_ucr(request)

    assert response.status_code == 400
    assert "consignment.goods" in json.loads(response.content)["errors"]
    assert UcrDeclaration.all_objects.count() == 0


@pytest.mark.django_db
@enabled
def test_attachments_are_refused_before_anything_is_written(db):
    from django.core.files.uploadedfile import SimpleUploadedFile

    world = recording("save-attachments")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    document = save_body(documents=[{"code": "DOC1", "name": "Evidence", "reference": "R-1"}])

    response = client.post(
        reverse("ucr-save"),
        {"payload": json.dumps(document), "file_0": SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 demo")},
    )

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "attachment_denied"
    assert UcrDeclaration.all_objects.count() == 0
    assert DemonstrationEvent.objects.count() == 0


# --- Idempotency -------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_repeated_request_with_the_same_key_returns_the_same_record(db):
    world = recording("save-replay")
    key = uuid.uuid4()
    first = save_demonstration_ucr(bound_save_request(world, save_body(idempotency_key=str(key))))
    second = save_demonstration_ucr(bound_save_request(world, save_body(idempotency_key=str(key))))

    assert first.status_code == second.status_code == 200
    assert json.loads(first.content) == json.loads(second.content)
    assert len(demo_rows()) == 1
    assert DemonstrationEvent.objects.count() == 1
    assert session_row(world).next_sequence == 2  # the retry burned no sequence


@pytest.mark.django_db
@enabled
def test_a_malformed_idempotency_key_is_refused_not_replaced(db):
    world = recording("save-bad-key")
    request = bound_save_request(world, save_body(idempotency_key="not-a-uuid"))

    response = save_demonstration_ucr(request)

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "idempotency_key_invalid"
    assert UcrDeclaration.all_objects.count() == 0


# --- Reference allocation under contention -----------------------------------


@pytest.mark.django_db
@enabled
def test_a_lost_reference_race_is_retried_with_a_fresh_allocation(db, monkeypatch):
    """The allocator hands out a taken reference once; the save must roll that
    attempt back, re-run the allocator, and land on a free reference — never
    re-present the conflicting one."""
    from scenarios import demonstration_ucr

    world = recording("save-race-recovery")
    holder = UcrDeclaration.all_objects.create(
        owner=world["instructor"], temp_no="DEMOUCR26999999", regime="CO",
    )
    real_allocate = demonstration_ucr.allocate_ucr_number
    calls = []

    def racing_allocate(prefix):
        calls.append(prefix)
        return holder.temp_no if len(calls) == 1 else real_allocate(prefix)

    monkeypatch.setattr(demonstration_ucr, "allocate_ucr_number", racing_allocate)
    request = bound_save_request(world, save_body())

    response = save_demonstration_ucr(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["temp_no"] != holder.temp_no
    assert UcrDeclaration.all_objects.filter(temp_no=holder.temp_no).count() == 1
    assert UcrDeclaration.all_objects.filter(temp_no=data["temp_no"], demonstration_session=world["session"]).exists()
    assert DemonstrationEvent.objects.get(record_id=data["id"]).sequence == 1


@pytest.mark.django_db
@enabled
def test_an_exhausted_allocation_budget_is_a_controlled_refusal(db, monkeypatch):
    from scenarios import demonstration_ucr

    world = recording("save-race-exhausted")
    holder = UcrDeclaration.all_objects.create(
        owner=world["instructor"], temp_no="DEMOUCR26999998", regime="CO",
    )
    monkeypatch.setattr(demonstration_ucr, "allocate_ucr_number", lambda prefix: holder.temp_no)
    request = bound_save_request(world, save_body())

    response = save_demonstration_ucr(request)

    assert response.status_code == 503
    assert json.loads(response.content)["code"] == "reference_busy"
    assert UcrDeclaration.all_objects.count() == 1  # only the pre-existing holder
    assert DemonstrationEvent.objects.count() == 0
    assert session_row(world).next_sequence == 1  # nothing was reserved either


@pytest.mark.django_db
@enabled
def test_a_failed_event_creation_rolls_the_record_back(db, monkeypatch):
    """A save without its event is not a save: the row must not survive."""
    from scenarios import demonstration_ucr

    def failing_event(request, **kwargs):
        raise demonstrations.DemonstrationError(
            "The demonstration stream is busy. Try again in a moment.", "sequence_contention", 409
        )

    monkeypatch.setattr(demonstrations, "append_record_event", failing_event)
    world = recording("save-rollback")
    request = bound_save_request(world, save_body())

    response = save_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "sequence_contention"
    assert UcrDeclaration.all_objects.count() == 0
    assert DemonstrationEvent.objects.count() == 0
    assert session_row(world).next_sequence == 1


def _service_save(username, payload, key, barrier):
    """One demonstration save from an independent connection, as two browsers would race."""
    close_old_connections()
    try:
        user = User.objects.get(username=username)
        session = DemonstrationSession.objects.filter(instructor=user, state="recording").first()
        world = {"instructor": user, "session": session}
        body = dict(payload)
        if key:
            body["idempotency_key"] = str(key)
        barrier.wait(timeout=10)
        response = save_demonstration_ucr(bound_save_request(world, body))
        return response.status_code, json.loads(response.content)
    except Exception as error:  # noqa: BLE001 - surfaced in the assertion message
        return ("error", repr(error))
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_two_concurrent_saves_allocate_distinct_references_and_sequences(transactional_db):
    """One instructor, two browsers, one session: whatever the read-then-write
    allocator hands out, the table may never hold one reference twice, and the
    sequences stay unique and ordered."""
    owner = instructor("save-race-owner")
    recording("save-race-a", instructor=owner)
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result(timeout=20)
            for future in [
                pool.submit(_service_save, owner.username, save_body(), None, barrier),
                pool.submit(_service_save, owner.username, save_body(), None, barrier),
            ]
        ]

    succeeded = [data for status, data in outcomes if status == 200]
    for status, data in outcomes:
        assert status in (200, 503), (status, data)
        if status == 503:
            assert data["code"] in ("session_busy", "reference_busy", "sequence_contention")
    persisted = list(UcrDeclaration.all_objects.filter(demonstration_session__isnull=False))
    assert {row.temp_no for row in persisted} == {data["temp_no"] for data in succeeded}
    assert len(persisted) == len({row.temp_no for row in persisted})
    sequences = list(DemonstrationEvent.objects.order_by("sequence").values_list("sequence", flat=True))
    assert sequences == sorted(set(sequences))


@pytest.mark.django_db(transaction=True)
def test_concurrent_saves_with_one_key_persist_one_record(transactional_db):
    """The idempotency constraint is the arbiter: the twin that loses the event
    insert rolls its duplicate record back and answers with the winner's row."""
    owner = instructor("save-key-race-owner")
    recording("save-key-race", instructor=owner)
    key = uuid.uuid4()
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result(timeout=20)
            for future in [
                pool.submit(_service_save, owner.username, save_body(), key, barrier),
                pool.submit(_service_save, owner.username, save_body(), key, barrier),
            ]
        ]

    assert len(demo_rows()) == 1, outcomes
    assert DemonstrationEvent.objects.count() == 1
    winner = demo_rows()[0]
    for status, data in outcomes:
        if status == 200:
            assert data["id"] == winner.pk
            assert data["temp_no"] == winner.temp_no
        else:
            assert status == 503, (status, data)


# --- Isolation after the save ------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_saved_demonstration_record_stays_invisible_to_ordinary_surfaces(db):
    from scenarios.demonstration_ucr import ordinary_ucr_scope_predicate
    from scenarios.models import UcrDocumentAttachment

    world = recording("save-isolation")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    data = post_json(client, save_body()).json()

    # The ordinary listing that student dashboards, assessments and the BOE/MDA
    # joins all read from never sees the row — even for its own owner.
    assert not UcrDeclaration.objects.filter(owner=world["instructor"]).exists()
    assert not UcrDocumentAttachment.objects.filter(ucr_id=data["id"])
    assert not UcrDocumentAttachment.objects.filter(ordinary_ucr_scope_predicate(), ucr_id=data["id"])


@pytest.mark.django_db
@enabled
def test_the_demonstration_save_leaves_ordinary_work_alone(db):
    """Side by side: a save with a binding, then a save from a browser without
    one — the second is still an ordinary instructor draft, and neither
    pollutes the other."""
    world = recording("save-side-by-side")
    demonstrating = Client()
    demonstrating.force_login(world["instructor"])
    bind_client(demonstrating, world)
    demonstration = post_json(demonstrating, save_body()).json()

    ordinary_browser = Client()
    ordinary_browser.force_login(world["instructor"])
    ordinary = post_json(ordinary_browser, save_body()).json()

    demonstration_row = UcrDeclaration.all_objects.get(pk=demonstration["id"])
    ordinary_row = UcrDeclaration.objects.get(pk=ordinary["id"])
    assert demonstration_row.demonstration_session_id == world["session"].pk
    assert demonstration_row.temp_no.startswith("DEMOUCR")
    assert ordinary_row.demonstration_session_id is None
    assert ordinary_row.temp_no.startswith("TEMPUCR")
    assert DemonstrationEvent.objects.count() == 1


# --- The create screen reload (Stage 1B.1) -----------------------------------


def create_screen(client, draft_id=None):
    url = reverse("single-window-create-ucr")
    if draft_id is not None:
        url = f"{url}?draft={draft_id}"
    return client.get(url)


@pytest.mark.django_db
@enabled
def test_a_saved_draft_reloads_into_the_create_screen_for_its_own_session(db):
    """After a save the page re-opens with ?draft=<id>; a bound browser gets its
    own demonstration record back through the session scope."""
    world = recording("reload-own")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    saved = post_json(client, save_body()).json()

    response = create_screen(client, saved["id"])

    assert response.status_code == 200
    html = response.content.decode()
    assert saved["temp_no"] in html  # the initial-draft payload is on the page
    assert "Demonstration Exporter" in html


@pytest.mark.django_db
@enabled
def test_the_reload_survives_a_paused_session(db):
    """GET navigation stays available while paused, draft included."""
    world = recording("reload-paused")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    saved = post_json(client, save_body()).json()
    DemonstrationSession.objects.filter(pk=world["session"].pk).update(
        state=DemonstrationSession.State.PAUSED, paused_at=timezone.now()
    )

    response = create_screen(client, saved["id"])

    assert response.status_code == 200
    assert saved["temp_no"] in response.content.decode()


@pytest.mark.django_db
@enabled
def test_the_reload_never_loads_another_sessions_record_or_an_unknown_id(db):
    world = recording("reload-foreign")
    other = recording("reload-foreign-other")
    foreign = demo_ucr(other["session"])
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    for draft_id in (foreign.pk, 999_999):
        response = create_screen(client, draft_id)
        assert response.status_code == 200
        assert "ACME Trading" not in response.content.decode()


@pytest.mark.django_db
@enabled
def test_the_bound_reload_resolves_through_the_demonstration_scope_only(db):
    """A bound browser does not fall back to the ordinary manager: its own
    ordinary draft is not loaded into the recording's create screen."""
    world = recording("reload-ordinary")
    ordinary = ordinary_ucr(world["instructor"])
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    response = create_screen(client, ordinary.pk)

    assert response.status_code == 200
    assert "ACME Trading" not in response.content.decode()


@pytest.mark.django_db
@enabled
def test_a_stale_binding_reloads_an_empty_screen(db):
    """A binding that no longer resolves loads no demonstration data."""
    world = recording("reload-stale")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    saved = post_json(client, save_body()).json()
    world["session"].state = DemonstrationSession.State.STOPPED
    world["session"].stopped_at = timezone.now()
    world["session"].save(update_fields=("state", "stopped_at"))

    response = create_screen(client, saved["id"])

    assert response.status_code == 200
    assert saved["temp_no"] not in response.content.decode()


@pytest.mark.django_db
@enabled
def test_without_a_binding_the_reload_is_ordinary_and_blind_to_demonstrations(db):
    """The ordinary screen keeps its behaviour: an unbound browser (and a
    student a fortiori) can never load a demonstration draft by id."""
    world = recording("reload-unbound")
    client = Client()
    client.force_login(world["instructor"])
    saved = post_json(client, save_body()).json()  # ordinary path, no binding
    demonstration = demo_ucr(world["session"])

    for draft_id in (demonstration.pk, saved["id"]):
        response = create_screen(client, draft_id)
        assert response.status_code == 200
        assert "ACME Trading" not in response.content.decode()

    ordinary_html = create_screen(client, saved["id"]).content.decode()
    assert ordinary_html.count(saved["temp_no"]) >= 1  # the ordinary draft loads normally


# --- The studio timeline -----------------------------------------------------


@pytest.mark.django_db
@enabled
def test_the_session_endpoint_lists_the_save_in_order(db):
    world = recording("save-timeline")
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    first = post_json(client, save_body()).json()
    changed = save_body()
    changed["draft_id"] = first["id"]
    post_json(client, changed)

    payload = client.get(reverse("hybrid-demonstration-session")).json()

    assert payload["session"]["state"] == "recording"
    assert payload["session"]["event_count"] == 2
    assert payload["session"]["record_count"] == 1
    assert [event["sequence"] for event in payload["events"]] == [1, 2]
    assert [event["event_type"] for event in payload["events"]] == ["record_created", "record_updated"]
    assert payload["events"][0]["record"] == f"ucr:{first['id']}"


@pytest.mark.django_db
def test_the_studio_page_wires_the_recording_client_only_while_enabled(db):
    world = draft_world("save-studio-wiring")
    client = Client()
    client.force_login(world["instructor"])
    url = reverse("hybrid-lesson-demonstration-studio", args=[world["lesson"].pk])

    off = client.get(url)
    off_html = off.content.decode()
    start_url = reverse("hybrid-demonstration-start", args=[world["lesson"].pk])
    assert start_url not in off_html
    # Flag off: the original Stage 1A wording, untouched.
    assert "READ-ONLY FRAME · RECORDING NOT IMPLEMENTED" in off_html
    assert "Recording is simulated" in off_html

    with enabled:
        on = client.get(url)
    html = on.content.decode()
    assert start_url in html
    assert reverse("hybrid-demonstration-discard") in html
    # Flag on: the approved conditional wording replaces the placeholders.
    assert "RECORDING ENABLED · UCR SAVE CAPTURED" in html
    assert "Recording is enabled in this development environment" in html
    assert "No events recorded yet." in html
    assert "Scope boundary" in html
    assert "Discard this recording? Its events and demonstration records will be deleted now." in html
    # ...and none of the flag-off placeholders are rendered with it.
    assert "RECORDING NOT IMPLEMENTED" not in html
    assert "Recording is simulated" not in html
    assert "no captured actions or demonstration records are saved" not in html


@pytest.mark.django_db
def test_reference_conflict_classification_reads_the_driver_code(db):
    """The allocator-conflict classifier reads the driver's SQLSTATE first, not
    an engine's message wording; SQLite's wording is the fallback."""
    from scenarios.demonstration_ucr import _is_reference_conflict

    class _UniqueViolation(Exception):
        pgcode = "23505"

    postgres_shaped = IntegrityError(
        'duplicate key value violates unique constraint "scenarios_ucrdeclaration_temp_no_key"'
    )
    postgres_shaped.__cause__ = _UniqueViolation("scenarios_ucrdeclaration_temp_no_key")
    # Classified by the SQLSTATE the driver carries, on any vendor.
    assert _is_reference_conflict(postgres_shaped) is True

    sqlite_shaped = IntegrityError("UNIQUE constraint failed: scenarios_ucrdeclaration.temp_no")
    assert _is_reference_conflict(sqlite_shaped) is (connection.vendor == "sqlite")

    other = IntegrityError("some constraint the save does not own")
    assert _is_reference_conflict(other) is False
