"""Stage R4-D1 — Reference Library page integration.

Tests the Django page view, the five lifecycle endpoints in their production
context, instructor isolation, CSRF enforcement, and lifecycle transitions.
"""
import json
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import demo_ucr, draft_world
from hybrid import demonstrations
from hybrid.models import DemonstrationSession
from scenarios.models import UcrDeclaration, purge_expired_ucr_drafts

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)
STATE = UcrDeclaration.ReferenceState


def library_world(username, *, recording=True):
    world = draft_world(username)
    client = Client()
    client.force_login(world["instructor"])
    session = None
    if recording:
        started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
        assert started.status_code == 200, started.content
        session = DemonstrationSession.objects.get(pk=started.json()["session"]["id"])
    return world, client, session


def save_demo(client, **overrides):
    body = {
        "regime": "TN", "show_provider": True,
        "provider": {"declarant_code": "CH1", "code": "C1", "name": "P", "country": "GH",
                     "address": "A", "contact": "C", "phone": "1", "email": "provider@example.test", "email_2": ""},
        "exporter": {"name": "R4D1 Exporter", "country": "GH", "address": "A", "phone": "1",
                     "contact": "C", "contact_no": "N", "designation": "D"},
        "importer": {"name": "R4D1 Importer", "country": "CN", "address": "A", "phone": "2",
                     "contact": "C", "contact_no": "N", "designation": "D"},
        "consignment": {"goods": "R4D1 goods", "origin": "GH", "destination": "CN", "mode": "10, Sea"},
    }
    body.update(overrides)
    response = client.post(reverse("ucr-save"), json.dumps(body), content_type="application/json")
    assert response.status_code == 200, response.content
    return UcrDeclaration.all_objects.get(pk=response.json()["id"])


def promote_state(record, state):
    UcrDeclaration.all_objects.filter(pk=record.pk).update(reference_state=state)
    record.refresh_from_db()
    return record


def submit_record(record):
    record.status = UcrDeclaration.Status.SUBMITTED
    record.ucr_no = "KGHTESTUCR260000400"
    record.submitted_at = timezone.now()
    record.save(update_fields=("status", "ucr_no", "submitted_at"))
    return record


def library_url():
    return reverse("hybrid-reference-library-page")


def api_url(action="", record_id=None):
    if action:
        return reverse(f"hybrid-reference-{action}", args=[record_id])
    return reverse("hybrid-reference-library")


def post_action(client, action, record_id):
    return client.post(api_url(action, record_id), "{}", content_type="application/json")


# --- Page access --------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_the_page_serves_for_an_instructor(db):
    world, client, session = library_world("r4d1-page")
    response = client.get(library_url())
    assert response.status_code == 200
    html = response.content.decode()
    assert "Reference Library" in html
    assert "/instructor/hybrid/reference-library" in html  # the list endpoint URL is wired


@pytest.mark.django_db
def test_the_page_redirects_anonymous_and_students(db):
    world = draft_world("r4d1-anon")
    student = User.objects.create_user(username="r4d1-student", email="s@example.test", password="x")
    anon = Client()
    student_client = Client()
    student_client.force_login(student)

    assert anon.get(library_url()).status_code == 302
    assert student_client.get(library_url()).status_code == 302


# --- Lifecycle via the production endpoints ------------------------------------


@pytest.mark.django_db
@enabled
def test_promote_working_approve_retire_full_lifecycle(db):
    world, client, session = library_world("r4d1-lifecycle")
    record = save_demo(client)

    # Promote
    response = post_action(client, "promote", record.pk)
    assert response.status_code == 200
    assert response.json()["reference"]["reference_state"] == "working"
    record.refresh_from_db()
    assert record.demonstration_session_id is None

    # Submit (needed for approval)
    submit_record(record)

    # Approve
    response = post_action(client, "approve", record.pk)
    assert response.status_code == 200
    assert response.json()["reference"]["reference_state"] == "approved"

    # Retire
    response = post_action(client, "retire", record.pk)
    assert response.status_code == 200
    assert response.json()["reference"]["reference_state"] == "retired"


@pytest.mark.django_db
@enabled
def test_promotion_preserves_ownership_and_isolation(db):
    world, client, session = library_world("r4d1-ownership")
    record = save_demo(client)

    assert post_action(client, "promote", record.pk).status_code == 200

    record.refresh_from_db()
    assert record.owner_id == world["instructor"].pk
    assert record.demonstration_session_id is None

    # Ordinary manager sees the promoted record (instructor-owned ordinary)
    assert UcrDeclaration.objects.filter(pk=record.pk).exists()

    # Student cannot access it
    student = User.objects.create_user(username="r4d1-student", email="s@example.test", password="x")
    student_client = Client()
    student_client.force_login(student)
    assert student_client.get(reverse("ucr-detail", args=[record.pk])).status_code in (302, 404)


@pytest.mark.django_db
@enabled
def test_approval_requires_submitted_status(db):
    world, client, session = library_world("r4d1-approve")
    record = save_demo(client)
    promote_state(record, STATE.WORKING.value)

    refused = post_action(client, "approve", record.pk)
    assert refused.status_code == 400
    assert refused.json()["code"] == "approval_requires_submitted"


@pytest.mark.django_db
@enabled
def test_retirement_only_from_approved(db):
    world, client, session = library_world("r4d1-retire")
    record = save_demo(client)
    promote_state(record, STATE.WORKING.value)

    refused = post_action(client, "retire", record.pk)
    assert refused.status_code == 409
    assert refused.json()["code"] == "not_retirable"


@pytest.mark.django_db
@enabled
def test_csrf_enforcement_on_mutations(db):
    world, client, session = library_world("r4d1-csrf")
    record = save_demo(client)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(world["instructor"])

    response = csrf_client.post(api_url("promote", record.pk), "{}", content_type="application/json")
    assert response.status_code == 403
    record.refresh_from_db()
    assert record.reference_state == STATE.TEMPORARY.value


# --- Isolation and purge -------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_promoted_records_survive_purge(db):
    world, client, session = library_world("r4d1-purge")
    record = save_demo(client)
    promote_state(record, STATE.WORKING.value)
    moment = timezone.now() - timedelta(days=30)
    UcrDeclaration.all_objects.filter(pk=record.pk).update(updated_at=moment)

    purge_expired_ucr_drafts()

    assert UcrDeclaration.all_objects.filter(pk=record.pk).exists()
