"""Stage R4-A — schema foundation and protection of instructor reference records.

Approved and retired instructor references are frozen for every supported
application write path: ordinary save, submit, amendment, admin edit/delete and
bulk delete, the demo save service, and the ordinary draft purge. The tests
arrange approved/retired states through the documented bypass (a queryset
update, which is what the future promotion service will replace), so the
guards themselves are what end up exercised.
"""
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession
from scenarios.admin import UcrDeclarationAdmin
from scenarios.models import UcrDeclaration, purge_expired_ucr_drafts

IMMUTABLE = ("approved", "retired")


# --- Helpers -----------------------------------------------------------------


def promote(record, state):
    """Arrange a reference state through the documented bypass (queryset update).

    The future promotion service will replace this; no production path writes
    reference states yet.
    """
    UcrDeclaration.all_objects.filter(pk=record.pk).update(reference_state=state)
    record.refresh_from_db()


def backdate(record):
    """Backdate a draft so the ordinary purge's window applies (queryset
    update, because auto_now fields ignore values passed to create())."""
    moment = timezone.now() - timedelta(days=30)
    UcrDeclaration.all_objects.filter(pk=record.pk).update(updated_at=moment, created_at=moment)
    return record


def instructor_client(username="r4a-instructor"):
    from django.contrib.auth.models import Group

    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    client = Client()
    client.force_login(user)
    return user, client


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "R4A Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "R4A Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "R4A Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000004", "designation": "Manager",
        },
        "consignment": {
            "goods": "R4A goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def post_save(client, payload, draft_id=None):
    body = dict(payload)
    if draft_id is not None:
        body["draft_id"] = draft_id
    return client.post(reverse("ucr-save"), json.dumps(body), content_type="application/json")


def post_submit(client, payload, draft_id):
    body = dict(payload)
    body["draft_id"] = draft_id
    return client.post(reverse("ucr-submit"), json.dumps(body), content_type="application/json")


# --- Defaults: existing behavior preserved -----------------------------------


@pytest.mark.django_db
def test_new_records_default_to_the_temporary_state(db):
    user, client = instructor_client("r4a-default")
    response = post_save(client, save_body())
    assert response.status_code == 200
    record = UcrDeclaration.objects.get(pk=response.json()["id"])
    assert record.reference_state == UcrDeclaration.ReferenceState.TEMPORARY
    assert record.reference_source_session_id is None


@pytest.mark.django_db
def test_ordinary_creation_submission_and_purge_are_unchanged(db):
    user, client = instructor_client("r4a-ordinary")
    saved = post_save(client, save_body())
    submitted = post_submit(client, save_body(), saved.json()["id"])
    assert submitted.status_code == 200
    record = UcrDeclaration.objects.get(pk=submitted.json()["id"])
    assert record.status == UcrDeclaration.Status.SUBMITTED
    assert record.ucr_no.startswith("KGHTESTUCR")

    ordinary_old = backdate(UcrDeclaration.objects.create(
        owner=user, temp_no="TEMPUCR26999990", regime="CO", status=UcrDeclaration.Status.DRAFT,
    ))
    deleted = purge_expired_ucr_drafts()
    assert deleted >= 1
    assert not UcrDeclaration.objects.filter(pk=ordinary_old.pk).exists()  # ordinary expiry unchanged


# --- Approved and retired save refusal ---------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("state", IMMUTABLE := ("approved", "retired"))
def test_an_immutable_reference_refuses_the_ordinary_save(db, state):
    user, client = instructor_client(f"r4a-save-{state}")
    saved = post_save(client, save_body())
    promote(UcrDeclaration.objects.get(pk=saved.json()["id"]), state)
    before = UcrDeclaration.all_objects.get(pk=saved.json()["id"]).exporter_name

    refused = post_save(client, save_body(exporter={"name": "Rewritten", "country": "GH", "address": "x",
                                                   "phone": "1", "contact": "c", "contact_no": "n",
                                                   "designation": "d"}), draft_id=saved.json()["id"])

    assert refused.status_code == 403
    assert refused.json()["code"] == "reference_immutable"
    assert UcrDeclaration.all_objects.get(pk=saved.json()["id"]).exporter_name == before


@pytest.mark.django_db
@pytest.mark.parametrize("state", IMMUTABLE)
def test_the_model_save_guard_is_the_backstop(db, state):
    user, _ = instructor_client(f"r4a-guard-{state}")
    record = UcrDeclaration.objects.create(owner=user, temp_no=f"TEMPUCRR4A{state[:3].upper()}", regime="CO")
    promote(record, state)
    record.refresh_from_db()
    record.exporter_name = "Mutated"

    with pytest.raises(ValidationError) as caught:
        record.save()
    assert caught.value.code == "reference_immutable"
    record.refresh_from_db()
    assert record.exporter_name == ""


@pytest.mark.django_db
@pytest.mark.parametrize("state", IMMUTABLE)
def test_submit_refuses_an_immutable_reference(db, state):
    user, client = instructor_client(f"r4a-submit-{state}")
    saved = post_save(client, save_body())
    promote(UcrDeclaration.objects.get(pk=saved.json()["id"]), state)

    refused = post_submit(client, save_body(), saved.json()["id"])

    assert refused.status_code == 403
    assert refused.json()["code"] == "reference_immutable"
    record = UcrDeclaration.all_objects.get(pk=saved.json()["id"])
    assert record.status == UcrDeclaration.Status.DRAFT
    assert not record.ucr_no


# --- Amendment source immutability -------------------------------------------


@pytest.mark.django_db
# --- Admin safeguards --------------------------------------------------------


@pytest.mark.django_db
def test_admin_refuses_edit_delete_and_bulk_delete_of_immutable_references(db):
    from django.contrib import admin as django_admin
    from django.test import RequestFactory

    user, client = instructor_client("r4a-admin-owner")
    working = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4AWORK", regime="CO")
    approved = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4AAPP", regime="CO")
    promote(approved, "approved")
    retired = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4ARET", regime="CO")
    promote(retired, "retired")

    root = User.objects.create_superuser(username="r4a-root", email="root@example.test", password="x")
    admin_client = Client()
    admin_client.force_login(root)
    request = RequestFactory().get("/admin/scenarios/ucrdeclaration/")
    request.user = root
    model_admin = UcrDeclarationAdmin(UcrDeclaration, django_admin.site)

    assert model_admin.has_change_permission(request, approved) is False
    assert model_admin.has_delete_permission(request, approved) is False
    assert model_admin.has_change_permission(request, retired) is False
    assert model_admin.has_delete_permission(request, retired) is False
    assert model_admin.has_change_permission(request, working) is True  # working stays editable
    assert "delete_selected" not in model_admin.get_actions(request)

    # The admin's own edit POST is refused for an approved record.
    change_url = reverse("admin:scenarios_ucrdeclaration_change", args=[approved.pk])
    response = admin_client.post(change_url, {"regime": "XX", "_save": "Save"})
    assert response.status_code == 403
    approved.refresh_from_db()
    assert approved.regime == "CO"

    # And the delete confirmation view refuses too.
    delete_url = reverse("admin:scenarios_ucrdeclaration_delete", args=[approved.pk])
    assert admin_client.get(delete_url).status_code == 403
    assert admin_client.post(delete_url, {"post": "yes"}).status_code == 403
    assert UcrDeclaration.all_objects.filter(pk=approved.pk).exists()


# --- Purge protection for every non-empty reference state --------------------


@pytest.mark.django_db
def test_purge_protects_every_non_empty_reference_state(db):
    user, _ = instructor_client("r4a-purge")
    ordinary_old = backdate(UcrDeclaration.objects.create(
        owner=user, temp_no="TEMPUCRR4ORD", regime="CO", status=UcrDeclaration.Status.DRAFT,
    ))
    kept = {}
    for state in ("working", "approved", "retired"):
        row = backdate(UcrDeclaration.objects.create(
            owner=user, temp_no=f"TEMPUCRR4{state[:3].upper()}", regime="CO",
            status=UcrDeclaration.Status.DRAFT,
        ))
        promote(row, state)
        kept[state] = row.pk

    deleted = purge_expired_ucr_drafts()
    assert deleted >= 1
    assert not UcrDeclaration.objects.filter(pk=ordinary_old.pk).exists()
    for state, pk in kept.items():
        assert UcrDeclaration.all_objects.filter(pk=pk, reference_state=state).exists()


@pytest.mark.django_db
def test_a_stale_instance_cannot_overwrite_a_reference_approved_since_fetch(db):
    """An instance fetched while the record was working, saved after another
    transaction approved it, is refused by the guard's database read."""
    user, _ = instructor_client("r4a-stale-instance")
    record = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4STALE2", regime="CO")
    stale = UcrDeclaration.all_objects.get(pk=record.pk)  # fetched while temporary
    promote(record, "approved")

    stale.exporter_name = "Mutated after approval"
    with pytest.raises(ValidationError) as caught:
        stale.save()
    assert caught.value.code == "reference_immutable"
    record.refresh_from_db()
    assert record.exporter_name == ""
    assert record.reference_state == "approved"


@pytest.mark.django_db
@pytest.mark.parametrize("state", IMMUTABLE)
def test_an_immutable_reference_cannot_return_to_working_or_temporary_by_save(db, state):
    """The state column itself is protected: no ordinary save may demote an
    approved or retired reference back to working or temporary."""
    user, _ = instructor_client(f"r4a-demote-{state}")
    record = UcrDeclaration.objects.create(owner=user, temp_no=f"TEMPUCRR4DEM{state[:3].upper()}", regime="CO")
    promote(record, state)

    for demoted in (UcrDeclaration.ReferenceState.WORKING, UcrDeclaration.ReferenceState.TEMPORARY):
        record.reference_state = demoted
        with pytest.raises(ValidationError) as caught:
            record.save()
        assert caught.value.code == "reference_immutable"
    record.refresh_from_db()
    assert record.reference_state == state


@pytest.mark.django_db
def test_a_controlled_service_can_perform_the_working_to_approved_transition(db):
    """The guard leaves room for the future R4-B service: an explicit,
    state-checked transition (queryset update, the documented controlled path)
    moves working to approved exactly once, after which the immutability holds."""
    user, _ = instructor_client("r4a-transition")
    record = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4TRAN", regime="CO")
    promote(record, "working")

    def controlled_approve(record_id):
        """The shape the R4-B promotion service will use: a conditional update
        guarded by the current state, applied exactly once."""
        return UcrDeclaration.all_objects.filter(
            pk=record_id, reference_state=UcrDeclaration.ReferenceState.WORKING
        ).update(reference_state=UcrDeclaration.ReferenceState.APPROVED)

    assert controlled_approve(record.pk) == 1
    assert controlled_approve(record.pk) == 0  # re-running transitions nothing
    record.refresh_from_db()
    assert record.reference_state == "approved"
    record.exporter_name = "Post-approval mutation"
    with pytest.raises(ValidationError):
        record.save()
    record.refresh_from_db()
    assert record.exporter_name == ""



# --- Isolation and demo-save refusal -----------------------------------------


@pytest.mark.django_db
def test_an_immutable_reference_stays_invisible_to_students(db):
    user, _ = instructor_client("r4a-isolation")
    approved = UcrDeclaration.objects.create(owner=user, temp_no="TEMPUCRR4ISO", regime="CO")
    promote(approved, "approved")
    from accounts.models import SimulatorCredential

    student = User.objects.create_user(username="r4a-student", email="s@example.test", password="x")
    student.student_id = "R4ASTU01"
    student.save(update_fields=("student_id",))
    credential = SimulatorCredential.objects.create(user=student)
    credential.issue()  # a random monthly password; the session flag grants access
    student_client = Client()
    student_client.force_login(student)
    store = student_client.session
    store["simulator_user_id"] = str(student.pk)
    store.save()

    assert not UcrDeclaration.objects.filter(owner=student).exists()
    assert student_client.get(reverse("ucr-detail", args=[approved.pk])).status_code == 404


@pytest.mark.django_db
@override_settings(DEMONSTRATION_RECORDING_ENABLED=True)
def test_a_stale_continue_selection_cannot_mutate_an_immutable_reference(db):
    """A continue-selection written before the record was approved (the
    sweep-carryover shape) is refused with a controlled error, and the record
    is untouched."""
    from demonstration_world import draft_world

    world = draft_world("r4a-stale")
    client = Client()
    client.force_login(world["instructor"])
    started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
    assert started.status_code == 200
    live = DemonstrationSession.objects.get(pk=started.json()["session"]["id"])

    reference = UcrDeclaration.all_objects.create(
        owner=world["instructor"], demonstration_session=live,
        temp_no="DEMOUCRR4STALE", regime="CO",
    )
    promote(reference, "approved")

    store = client.session
    store[demonstrations.REFERENCE_KEY] = reference.pk
    store[demonstrations.REFERENCE_INTENT_KEY] = "continue"
    store.save()

    refused = client.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    assert refused.status_code == 400
    assert refused.json()["code"] == "reference_immutable"
    reference.refresh_from_db()
    assert reference.reference_state == "approved"
    assert DemonstrationEvent.objects.filter(session_id=live.pk).count() == 0