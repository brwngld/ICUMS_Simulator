"""Import-UCR foundation — the demonstration-scoped UCR submit.

The second approved write: ``ucr-submit`` POST, routed by the browser's
server-side binding into ``scenarios.demonstration_ucr``. The tests cover the
same authorization chain the save has (flag, manifest, binding, ownership,
lifecycle state), the transition it writes (draft → submitted, final
``KGHTESTUCR`` allocation, scope and ledger exclusion preserved), the event it
records (``ucr.submitted``, ``result_status: submitted``), the refusal shapes
(no draft, already submitted, foreign record, attachments), and every
ordinary surface that must stay untouched — including the ordinary submit
route itself, which keeps working exactly as before when no recording is
bound.
"""
import json

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from demonstration_world import (
    SessionEngine,
    demo_ucr,
    instructor,
    ordinary_ucr,
    recording,
)
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.demonstration_ucr import demonstration_submit_applies, submit_demonstration_ucr
from scenarios.models import UcrDeclaration, allocate_ucr_number

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)

DRAFT_SESSION_KEY = demonstrations.ACTIVE_SESSION_KEY


# --- Helpers -----------------------------------------------------------------


def bind_client(client, world):
    store = client.session
    store[DRAFT_SESSION_KEY] = str(world["session"].pk)
    store.save()


def save_body(**overrides):
    """A valid Create-UCR body, as the simulator page posts it."""
    payload = {
        "draft_id": None,
        "regime": "IM",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Demonstration Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Demonstration Exporter", "country": "CN", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "identity": "C0025673301", "name": "Demonstration Importer", "country": "GH",
            "address": "1 Import Road", "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000002", "designation": "Manager",
        },
        "consignment": {
            "goods": "Training goods", "origin": "CN", "destination": "GH", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def bound_submit_request(world, payload=None, **session_overrides):
    from django.test import RequestFactory

    body = dict(payload or {})
    request = RequestFactory().post(
        "/practical/single-window/ucr/submit/",
        data=json.dumps(body),
        content_type="application/json",
    )
    request.user = world["instructor"]
    request.session = SessionEngine.SessionStore()
    binding = session_overrides.pop(DRAFT_SESSION_KEY, str(world["session"].pk))
    if binding is not None:
        request.session[DRAFT_SESSION_KEY] = binding
    return request


def submit_json(client, payload):
    return client.post(reverse("ucr-submit"), json.dumps(payload), content_type="application/json")


def session_row(world):
    return DemonstrationSession.objects.get(pk=world["session"].pk)


# --- When the branch applies -------------------------------------------------


@pytest.mark.django_db
def test_the_submit_branch_applies_only_for_a_flag_on_bound_browser(db):
    world = recording("submit-applies")
    request = bound_submit_request(world)

    assert demonstration_submit_applies(request) is False  # flag off, even bound
    with enabled:
        assert demonstration_submit_applies(request) is True
        request.session.pop(DRAFT_SESSION_KEY)
        assert demonstration_submit_applies(request) is False  # no binding, flag on


# --- The transition it writes ------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_bound_submit_transitions_the_scoped_draft_and_issues_the_final_number(db):
    world = recording("submit-transition")
    record = demo_ucr(world["session"], regime="IM", status=UcrDeclaration.Status.DRAFT)
    request = bound_submit_request(world, save_body(draft_id=record.pk))

    response = submit_demonstration_ucr(request)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["demonstration"] is True
    assert data["status"] == "submitted"
    assert data["ucr_no"].startswith("KGHTESTUCR")
    assert data["detail_url"] == reverse("ucr-detail", args=[record.pk])
    record.refresh_from_db()
    assert record.status == UcrDeclaration.Status.SUBMITTED
    assert record.ucr_no == data["ucr_no"]
    assert record.submitted_at is not None
    # Still scoped to the session: submitted or not, learners never see it.
    assert record.demonstration_session_id == world["session"].pk
    assert UcrDeclaration.objects.filter(pk=record.pk).exists() is False
    event = DemonstrationEvent.objects.get(session_id=world["session"].pk, record_id=record.pk, action_code="ucr.submitted")
    assert event.event_type == "record_updated"
    assert event.payload["result_status"] == "submitted"
    assert event.payload["regime_code"] == "IM"
    assert "ucr_no" in event.payload["changed_fields"]
    assert event.payload["filled_sections"] == ["consignment", "exporter", "importer", "provider"]
    # The submit is deliberate activity: the inactivity deadline moved with it.
    assert session_row(world).last_activity_at > world["session"].last_activity_at


@pytest.mark.django_db
@enabled
def test_a_repeat_submit_of_the_same_draft_is_refused(db):
    world = recording("submit-repeat")
    record = demo_ucr(world["session"], status=UcrDeclaration.Status.DRAFT)
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)
    body = save_body(draft_id=record.pk)

    assert submit_json(client, body).status_code == 200
    second = submit_json(client, body)

    assert second.status_code == 400
    assert json.loads(second.content)["error"] == "This UCR has already been submitted."
    assert DemonstrationEvent.objects.filter(action_code="ucr.submitted").count() == 1


# --- Refusals ----------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_a_submit_without_a_draft_is_refused(db):
    world = recording("submit-no-draft")
    request = bound_submit_request(world, save_body())

    response = submit_demonstration_ucr(request)

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "no_draft_to_submit"
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_a_submit_addressing_an_ordinary_draft_is_refused(db):
    world = recording("submit-ordinary")
    ordinary = ordinary_ucr(world["instructor"])
    request = bound_submit_request(world, save_body(draft_id=ordinary.pk))

    response = submit_demonstration_ucr(request)

    # The scoped scope never resolves an ordinary row — the submission cannot
    # be quietly written as one either.
    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "no_draft_to_submit"
    ordinary.refresh_from_db()
    assert ordinary.status == UcrDeclaration.Status.DRAFT


@pytest.mark.django_db
@enabled
def test_a_submit_addressing_another_instructors_demonstration_is_refused(db):
    world = recording("submit-foreign")
    stranger_session = recording("submit-foreign-other", instructor=instructor("submit-foreign-stranger"))["session"]
    foreign = demo_ucr(stranger_session)
    request = bound_submit_request(world, save_body(draft_id=foreign.pk))

    response = submit_demonstration_ucr(request)

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "no_draft_to_submit"


@pytest.mark.django_db
@enabled
def test_a_submit_cannot_carry_attachments(db):
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.test import RequestFactory

    world = recording("submit-attachments")
    record = demo_ucr(world["session"], status=UcrDeclaration.Status.DRAFT)
    request = RequestFactory().post(
        "/practical/single-window/ucr/submit/",
        data={
            "payload": json.dumps(save_body(draft_id=record.pk)),
            "file_0": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4 trivial"),
        },
    )
    request.user = world["instructor"]
    request.session = SessionEngine.SessionStore()
    request.session[DRAFT_SESSION_KEY] = str(world["session"].pk)

    response = submit_demonstration_ucr(request)

    assert response.status_code == 400
    assert json.loads(response.content)["code"] == "attachment_denied"
    record.refresh_from_db()
    assert record.status == UcrDeclaration.Status.DRAFT


@pytest.mark.django_db
@enabled
def test_an_unbound_browser_cannot_submit_into_a_demonstration(db):
    world = recording("submit-unbound")
    record = demo_ucr(world["session"], status=UcrDeclaration.Status.DRAFT)
    request = bound_submit_request(world, save_body(draft_id=record.pk), **{DRAFT_SESSION_KEY: None})

    response = submit_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "no_active_session"
    record.refresh_from_db()
    assert record.status == UcrDeclaration.Status.DRAFT


@pytest.mark.django_db
@enabled
def test_a_paused_recording_refuses_the_submit(db):
    from demonstration_world import request_for

    world = recording("submit-paused")
    record = demo_ucr(world["session"], status=UcrDeclaration.Status.DRAFT)
    demonstrations.pause_recording(
        request_for(world["instructor"], bound=world["session"].pk), world["session"].pk, world["session"].version
    )
    request = bound_submit_request(world, save_body(draft_id=record.pk))

    response = submit_demonstration_ucr(request)

    assert response.status_code == 409
    assert json.loads(response.content)["code"] == "session_not_recording"
    record.refresh_from_db()
    assert record.status == UcrDeclaration.Status.DRAFT


# --- The ordinary route stays untouched --------------------------------------


@pytest.mark.django_db
def test_with_the_flag_off_a_bound_browser_still_submits_ordinarily(db):
    world = recording("submit-flag-off")
    record = ordinary_ucr(world["instructor"])
    client = Client()
    client.force_login(world["instructor"])
    bind_client(client, world)

    response = submit_json(client, save_body(draft_id=record.pk))

    assert response.status_code == 200
    data = response.json()
    assert data["ucr_no"].startswith("KGHTESTUCR")
    assert "demonstration" not in data
    record.refresh_from_db()
    assert record.status == UcrDeclaration.Status.SUBMITTED
    assert record.demonstration_session_id is None
    assert DemonstrationEvent.objects.count() == 0


@pytest.mark.django_db
@enabled
def test_the_ordinary_submit_of_a_learner_draft_is_unchanged_by_the_branch(db):
    from accounts.models import SimulatorCredential, User

    world = recording("submit-learner")
    learner = User.objects.create_user(username="submit-learner", email="sl@example.test", password="x")
    SimulatorCredential.objects.create(user=learner).issue()
    draft = ordinary_ucr(learner)
    client = Client()
    client.force_login(learner)
    session = client.session
    session["simulator_user_id"] = str(learner.pk)
    session.save()
    body = save_body(draft_id=draft.pk)

    response = submit_json(client, body)

    assert response.status_code == 200
    data = response.json()
    assert data["ucr_no"].startswith("KGHTESTUCR")
    assert "demonstration" not in data
    draft.refresh_from_db()
    assert draft.status == UcrDeclaration.Status.SUBMITTED
    assert DemonstrationEvent.objects.count() == 0
