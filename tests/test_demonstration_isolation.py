"""UI 4 Stage 1A — a demonstration never becomes ordinary work.

An instructor's recording run writes real rows into the real ``UcrDeclaration``
table. Each test below puts a demonstration record and an ordinary record side
by side and asks one question of every ordinary surface — simulator search,
direct detail, the owner's own relation, the admin changelist, the dashboard,
the creation ledger, the attribution picker, verification and the retention
sweeps: *can it see the demonstration row?*

A surface that would pass because its owner filter already excludes the record
proves nothing, so the interesting cases use one user who is both the
demonstrating instructor and the enrolled learner: only the manager can tell
those two rows apart. The last tests cover the paths a filtered manager
structurally cannot guard — a join arriving at a UCR from another model, and
the table-wide reference allocator.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.contrib import admin
from django.db import IntegrityError, InterfaceError, OperationalError, close_old_connections, transaction
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import demo_ucr, draft_world, dual_role_world, instructor, ordinary_ucr, recording, request_for
from hybrid import attribution, demonstrations, verification
from hybrid.models import DemonstrationEvent, DemonstrationSession, JourneyRecordAssociation, LessonAttempt
from scenarios.demonstration_ucr import (
    demonstration_ucrs,
    get_demonstration_ucr,
    next_demonstration_temp_no,
    ordinary_ucr_scope_predicate,
)
from scenarios.models import (
    BoeDeclaration,
    ConsignmentApplication,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    UcrDeclaration,
    UcrDocumentAttachment,
    allocate_ucr_number,
    purge_expired_ucr_drafts,
)


# --- Ordinary business queries ------------------------------------------------


@pytest.mark.django_db
def test_the_ordinary_manager_reports_only_ordinary_records(db):
    world = recording("iso-manager")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])

    assert list(UcrDeclaration.objects.values_list("pk", flat=True)) == [ordinary.pk]
    assert set(UcrDeclaration.all_objects.values_list("pk", flat=True)) == {ordinary.pk, demonstration.pk}
    # ``objects`` is the default manager, so every unqualified query in the
    # product takes the ordinary path without having to remember a filter.
    assert UcrDeclaration._default_manager is UcrDeclaration.objects


@pytest.mark.django_db
def test_simulator_search_lists_the_ordinary_record_and_never_the_demonstration(db):
    world = recording("iso-search")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    client = Client()
    client.force_login(world["instructor"])

    listed = client.get(reverse("single-window-search-ucr"), {"number": ordinary.temp_no})
    assert listed.status_code == 200
    assert [row.pk for row in listed.context["records"]] == [ordinary.pk]

    refused = client.get(reverse("single-window-search-ucr"), {"number": demonstration.temp_no})
    assert refused.status_code == 200
    # The criterion is echoed back into the form, so the page is read from its
    # result list: a search that matches nothing lists nothing — not the
    # demonstration row.
    assert [row.pk for row in refused.context["records"]] == []


@pytest.mark.django_db
def test_direct_detail_access_refuses_a_demonstration_record(db):
    world = recording("iso-detail")
    demonstration = demo_ucr(world["session"])
    owner_client = Client()
    owner_client.force_login(world["instructor"])

    # Not even its own owner can open it: the detail view resolves through the
    # ordinary manager, so as far as the simulator is concerned the row is not there.
    assert owner_client.get(reverse("ucr-detail", args=[demonstration.pk])).status_code == 404

    stranger = Client()
    stranger.force_login(instructor("iso-detail-other"))
    assert stranger.get(reverse("ucr-detail", args=[demonstration.pk])).status_code == 404


@pytest.mark.django_db
def test_the_owners_own_relation_hides_their_demonstration_records(db):
    world = recording("iso-relation")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])

    assert list(world["instructor"].ucr_declarations.values_list("pk", flat=True)) == [ordinary.pk]
    assert demonstration.pk not in [row.pk for row in world["instructor"].ucr_declarations.all()]


@pytest.mark.django_db
def test_the_sessions_reverse_accessor_is_inert_and_the_scoped_helper_is_the_way_in(db):
    """Documented shape, not a bug to trip over later.

    A reverse manager subclasses the related model's *default* manager, so
    ``session.ucr_declarations`` carries the ordinary-record filter as well as
    its own session filter. The two cannot both be satisfied, which makes that
    accessor permanently empty rather than subtly leaky — and means
    ``scenarios.demonstration_ucr.demonstration_ucrs()`` is the only supported
    route to a session's records.
    """
    world = recording("iso-reverse")
    record = demo_ucr(world["session"])

    assert list(world["session"].ucr_declarations.all()) == []
    assert [row.pk for row in demonstration_ucrs(world["session"])] == [record.pk]


@pytest.mark.django_db
def test_admin_changelist_omits_demonstration_records(db):
    world = recording("iso-admin")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    admin = User.objects.create_superuser(username="iso-admin-root", email="root@example.test", password="x")
    client = Client()
    client.force_login(admin)

    page = client.get(reverse("admin:scenarios_ucrdeclaration_changelist"))

    assert page.status_code == 200
    assert ordinary.temp_no.encode() in page.content
    assert demonstration.temp_no.encode() not in page.content


@pytest.mark.django_db
def test_the_admin_dashboard_counts_only_ordinary_records(db):
    from core.admin_dashboard import dashboard_callback

    world = recording("iso-dash")
    demo_ucr(world["session"])
    ordinary_ucr(world["instructor"])

    request = RequestFactory().get("/admin/")
    request.user = User.objects.create_superuser(username="iso-dash-root", email="dash@example.test", password="x")
    context = dashboard_callback(request, {})

    tile = next(card for card in context["dash"]["cards"] if card["label"] == "UCR declarations")
    assert tile["value"] == 1
    assert UcrDeclaration.all_objects.count() == 2


@pytest.mark.django_db
def test_only_the_exact_session_scope_returns_a_demonstration_record(db):
    first = recording("iso-scope-a")
    second = recording("iso-scope-b")
    record = demo_ucr(first["session"])

    assert [row.pk for row in demonstration_ucrs(first["session"])] == [record.pk]
    assert list(demonstration_ucrs(second["session"])) == []
    assert get_demonstration_ucr(second["session"], record.pk) is None
    assert get_demonstration_ucr(first["session"], record.pk).pk == record.pk
    # A primary key alone never resolves.
    assert get_demonstration_ucr(first["session"], 999999) is None
    assert get_demonstration_ucr(first["session"], 0) is None


# --- Ledger, attribution, verification ---------------------------------------


@pytest.mark.django_db
def test_a_demonstration_record_captures_no_creation_evidence(db):
    from hybrid.models import SimulatorRecordCreation

    world = recording("iso-ledger")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])

    assert SimulatorRecordCreation.objects.filter(record_kind="ucr", record_id=demonstration.pk).exists() is False
    assert SimulatorRecordCreation.objects.filter(record_kind="ucr", record_id=ordinary.pk).exists() is True
    assert SimulatorRecordCreation.objects.filter(owner=world["instructor"]).count() == 1


@pytest.mark.django_db
def test_the_attribution_picker_offers_the_ordinary_record_only(db):
    world = dual_role_world("iso-pick")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["person"])

    rows = attribution.attributable_rows(world["attempt"], world["role"])

    assert [row["record_id"] for row in rows] == [ordinary.pk]
    assert demonstration.pk not in [row["record_id"] for row in rows]


@pytest.mark.django_db
def test_a_forged_demonstration_record_id_cannot_be_attributed(db):
    world = dual_role_world("iso-forged")
    demonstration = demo_ucr(world["session"])

    with pytest.raises(attribution.AttributionError) as caught:
        attribution.attribute_record(
            world["attempt"], world["role"], record_id=demonstration.pk, student=world["person"],
        )

    assert caught.value.code == "not_attributable"
    assert "does not exist" in caught.value.message
    assert JourneyRecordAssociation.objects.filter(
        journey_attempt=world["attempt"], role=world["role"], is_active=True,
    ).exists() is False


@pytest.mark.django_db
def test_verification_ignores_a_demonstration_record_that_otherwise_matches(db):
    world = dual_role_world("iso-verify")
    lesson_attempt = LessonAttempt.objects.create(enrolment=world["enrolment"], lesson=world["lesson"])
    # The demonstration row matches the condition exactly, is owned by this very
    # learner and is newer than the attempt: only the manager can keep it out.
    demo_ucr(world["session"])

    assert verification.verify_step(lesson_attempt, world["step"])["passed"] is False
    assert verification.step_satisfied(lesson_attempt, world["step"]) is False

    ordinary_ucr(world["person"])
    assert verification.verify_step(lesson_attempt, world["step"])["passed"] is True


@pytest.mark.django_db
def test_completion_is_not_advanced_by_a_demonstration_record(db):
    world = dual_role_world("iso-completion")
    lesson_attempt = LessonAttempt.objects.create(enrolment=world["enrolment"], lesson=world["lesson"])
    demo_ucr(world["session"])

    assert verification.satisfied_steps(lesson_attempt) == set()
    verification.refresh_completion(lesson_attempt)
    lesson_attempt.refresh_from_db()
    assert lesson_attempt.completed_at is None


# --- Cleanup sweeps ----------------------------------------------------------


@pytest.mark.django_db
def test_the_ordinary_draft_purge_leaves_demonstration_drafts_alone(db):
    world = recording("iso-purge")
    stale = timezone.now() - timedelta(days=30)
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    UcrDeclaration.all_objects.filter(pk=demonstration.pk).update(updated_at=stale)
    UcrDeclaration.all_objects.filter(pk=ordinary.pk).update(updated_at=stale)

    deleted = purge_expired_ucr_drafts(max_age_days=7)

    assert deleted >= 1
    assert UcrDeclaration.all_objects.filter(pk=ordinary.pk).exists() is False
    assert UcrDeclaration.all_objects.filter(pk=demonstration.pk).exists() is True


@pytest.mark.django_db
def test_retention_expiry_removes_only_that_sessions_own_rows(db):
    expiring = recording("iso-expire")
    survivor = recording("iso-survivor")
    sealed = recording("iso-not-due")
    dropped = recording("iso-discarded")
    stranger = ordinary_ucr(instructor("iso-stranger"))

    expiring_ucr = demo_ucr(expiring["session"])
    DemonstrationEvent.objects.create(
        session=expiring["session"], sequence=1,
        event_type=DemonstrationEvent.EventType.NAVIGATION, action_code="portal.opened",
    )
    kept_ucr = demo_ucr(survivor["session"])
    not_due_ucr = demo_ucr(sealed["session"])
    dropped_ucr = demo_ucr(dropped["session"])
    DemonstrationEvent.objects.create(
        session=dropped["session"], sequence=1,
        event_type=DemonstrationEvent.EventType.NAVIGATION, action_code="portal.opened",
    )
    now = timezone.now()
    # The deadline stamped at stop time is the fact the sweep reads.
    sealed["session"].state = DemonstrationSession.State.STOPPED
    sealed["session"].stopped_at = now - timedelta(days=1)
    sealed["session"].retention_expires_at = now + timedelta(days=29)
    sealed["session"].save()
    expiring["session"].state = DemonstrationSession.State.STOPPED
    expiring["session"].stopped_at = now - timedelta(days=31)
    expiring["session"].retention_expires_at = now - timedelta(days=1)
    expiring["session"].save()

    # A discard empties the session on the spot and puts its tombstone on the
    # same thirty-day clock, so nothing but metadata is left to collect later.
    demonstrations.discard_recording(
        request_for(dropped["instructor"], bound=dropped["session"].pk), dropped["session"].pk
    )
    tombstone = DemonstrationSession.objects.get(pk=dropped["session"].pk)
    assert tombstone.state == DemonstrationSession.State.DISCARDED
    assert DemonstrationEvent.objects.filter(session_id=tombstone.pk).count() == 0
    assert UcrDeclaration.all_objects.filter(pk=dropped_ucr.pk).exists() is False
    assert abs(
        tombstone.retention_expires_at
        - (tombstone.discarded_at + timedelta(days=demonstrations.RETENTION_DAYS))
    ) <= timedelta(seconds=5)
    tombstone.retention_expires_at = now - timedelta(days=1)
    tombstone.save()

    removed = demonstrations.expire_demonstrations()

    assert removed == 2
    assert DemonstrationSession.objects.filter(pk=expiring["session"].pk).exists() is False
    assert DemonstrationSession.objects.filter(pk=tombstone.pk).exists() is False
    assert UcrDeclaration.all_objects.filter(pk=expiring_ucr.pk).exists() is False
    assert DemonstrationEvent.objects.filter(session_id=expiring["session"].pk).count() == 0
    # Untouched: a still-live session, a sealed session whose deadline has not
    # arrived, and every ordinary row.
    assert DemonstrationSession.objects.filter(pk=survivor["session"].pk).exists() is True
    assert UcrDeclaration.all_objects.filter(pk=kept_ucr.pk).exists() is True
    assert UcrDeclaration.all_objects.filter(pk=not_due_ucr.pk).exists() is True
    assert UcrDeclaration.all_objects.filter(pk=stranger.pk).exists() is True
    # Idempotent.
    assert demonstrations.expire_demonstrations() == 0


# --- What a manager cannot guard --------------------------------------------


@pytest.mark.django_db
def test_a_join_arrives_at_the_demonstration_row_and_the_scope_predicate_excludes_it(db):
    """Documented limit: the base manager is unfiltered so foreign keys work.

    A queryset that starts on another model reaches the UCR through the base
    manager. Those queries have to name their scope themselves;
    ``ordinary_ucr_scope_predicate`` is the shared spelling of it.
    """
    world = recording("iso-join")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    UcrDocumentAttachment.objects.create(
        ucr=demonstration, row_index=0, file="ucr_attachments/demo.pdf", original_name="demo.pdf",
    )
    UcrDocumentAttachment.objects.create(
        ucr=ordinary, row_index=0, file="ucr_attachments/ordinary.pdf", original_name="ordinary.pdf",
    )

    reachable = UcrDocumentAttachment.objects.all().select_related("ucr")
    assert demonstration.pk in [row.ucr_id for row in reachable]

    scoped = reachable.filter(ordinary_ucr_scope_predicate())
    assert [row.ucr_id for row in scoped] == [ordinary.pk]


@pytest.mark.django_db
def test_the_allocator_skips_a_number_already_held_by_a_demonstration_row(db):
    world = recording("iso-alloc")
    first = allocate_ucr_number(UcrDeclaration.UCR_PREFIX)
    stem = first[: len(first) - 7]
    squatting = f"{stem}0000009"
    # A demonstration row carrying an ordinary-shaped issued number — what a
    # mis-scoped write or a future import could produce. The scan has to see it,
    # because that column is unique across the whole table.
    demo_ucr(world["session"], ucr_no=squatting)

    allocated = allocate_ucr_number(UcrDeclaration.UCR_PREFIX)

    assert allocated == f"{stem}0000010"


def _allocate_and_persist(kind, owner_username, barrier):
    """One racing allocation, persisted through the real unique column."""
    close_old_connections()
    try:
        owner = User.objects.get(username=owner_username)
        session = DemonstrationSession.objects.filter(instructor=owner).first()
        barrier.wait(timeout=5)
        temp_no = (
            next_demonstration_temp_no() if kind == "demo" else allocate_ucr_number(UcrDeclaration.TEMP_PREFIX)
        )
        with transaction.atomic():
            UcrDeclaration.all_objects.create(
                owner=owner,
                demonstration_session=session if kind == "demo" else None,
                temp_no=temp_no,
                regime="CO",
            )
        return ("ok", temp_no)
    except IntegrityError:
        return ("collision", None)
    except (OperationalError, InterfaceError) as error:
        if not verification.is_database_contention(error):
            raise
        return ("contended", None)
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocation_cannot_persist_the_same_reference_twice(transactional_db):
    """The allocator is a read-then-write scan; the unique column is the arbiter.

    Two demonstration and two ordinary allocations race on the same instant.
    Whatever the scan returns, the table may not end up holding one reference
    twice, and a lost race has to surface as an integrity error rather than a
    duplicate row. Stage 1B's save service is expected to retry on that error.
    """
    owner = instructor("iso-race-owner")
    recording("iso-race", instructor=owner)
    barrier = Barrier(4)

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = [future.result(timeout=10) for future in [
            pool.submit(_allocate_and_persist, kind, owner.username, barrier)
            for kind in ("demo", "demo", "ordinary", "ordinary")
        ]]

    persisted = list(UcrDeclaration.all_objects.values_list("temp_no", flat=True))
    # The race has to actually put something in the table: four allocations that
    # all came back empty would satisfy the uniqueness check by doing nothing.
    assert {kind for kind, _ in outcomes} <= {"ok", "collision", "contended"}, outcomes
    assert persisted, outcomes
    assert len(persisted) == len(set(persisted))
    assert sum(1 for kind, _ in outcomes if kind == "ok") == len(persisted)


# --- The scope column is not a form field -----------------------------------


@pytest.mark.django_db
def test_no_model_form_can_offer_the_demonstration_scope(db):
    """``editable=False`` is what makes the help text's claim true.

    A ``ModelForm`` built over every field — the shape an admin or a future
    editor uses — cannot see the scope column at all, so there is no widget to
    forge and no ``clean_<field>`` that could be bypassed.
    """
    from django.forms.models import modelform_factory

    from scenarios.admin import UcrDeclarationAdmin

    field = UcrDeclaration._meta.get_field("demonstration_session")
    assert field.editable is False

    everything = modelform_factory(UcrDeclaration, fields="__all__")
    assert "demonstration_session" not in everything().fields
    # The ``temp_no``/``ucr_no`` references are already shielded the same way;
    # the scope column now belongs to that group.
    assert {"temp_no", "ucr_no"}.isdisjoint(everything().fields)

    request = RequestFactory().get("/admin/scenarios/ucrdeclaration/")
    request.user = User.objects.create_superuser(username="iso-form-root", email="form@example.test", password="x")
    admin_form = UcrDeclarationAdmin(UcrDeclaration, admin_site=admin.site).get_form(request)
    assert "demonstration_session" not in admin_form().fields


@pytest.mark.django_db
def test_an_administrative_edit_leaves_the_demonstration_scope_untouched(db):
    """The scope column survives an admin edit — and the row stays unreachable.

    Two mechanisms hold here. The change view resolves the object through the
    ordinary manager, so a demonstration row never reaches a change form at all;
    and even if a future surface renders one, ``exclude`` plus
    ``editable=False`` leave no widget to clear. The ordinary record next to it
    is still fully editable, which is the proof that the exclusion did not break
    administrative work.
    """
    world = recording("iso-admin-edit")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    admin_user = User.objects.create_superuser(username="iso-admin-edit-root", email="edit@example.test", password="x")
    client = Client()
    client.force_login(admin_user)

    def post_change(row):
        return client.post(
            reverse("admin:scenarios_ucrdeclaration_change", args=[row.pk]),
            {"regime": "CO", "exporter_name": "Edited by an administrator", "_save": "Save"},
        )

    refused = post_change(demonstration)
    assert refused.status_code == 302
    # No change form is ever rendered for a demonstration row — the changelist
    # and the change view both resolve objects through the ordinary manager.
    assert client.get(
        reverse("admin:scenarios_ucrdeclaration_change", args=[demonstration.pk])
    ).status_code == 302
    demonstration.refresh_from_db()
    assert demonstration.demonstration_session_id == world["session"].pk
    assert demonstration.exporter_name == "ACME Trading"

    accepted = post_change(ordinary)
    assert accepted.status_code == 302
    ordinary.refresh_from_db()
    assert ordinary.exporter_name == "Edited by an administrator"
    assert ordinary.demonstration_session_id is None
    # The demonstration row is still invisible to every ordinary surface.
    assert demonstration.temp_no not in list(UcrDeclaration.objects.values_list("temp_no", flat=True))


@pytest.mark.django_db
def test_the_service_still_sets_scope_by_assignment(db):
    """Non-editable means not offerable in a form, not unwritable by the service."""
    world = draft_world("iso-service-write")
    session = DemonstrationSession.objects.create(
        lesson=world["lesson"], instructor=world["instructor"],
        state=DemonstrationSession.State.RECORDING, started_at=timezone.now(),
    )
    record = demo_ucr(session, exporter_name="Assigned by the service")

    assert record.demonstration_session_id == session.pk
    assert get_demonstration_ucr(session, record.pk).pk == record.pk


# --- Ordinary save and submit cannot address a demonstration draft ----------


def _save_payload(**overrides):
    """A valid Create-UCR body, as the simulator page posts it."""
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Ordinary Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Ordinary Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Ordinary Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000002", "designation": "Manager",
        },
        "consignment": {
            "goods": "Training goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def _post_json(client, route, payload):
    return client.post(reverse(route), json.dumps(payload), content_type="application/json")


@pytest.mark.django_db
def test_an_ordinary_save_addressing_a_demonstration_draft_is_refused(db):
    world = recording("scope-save")
    demonstration = demo_ucr(world["session"])
    client = Client()
    client.force_login(world["instructor"])

    response = _post_json(client, "ucr-save", _save_payload(draft_id=demonstration.pk))

    assert response.status_code == 403
    assert response.json()["code"] == "record_out_of_scope"
    # No ordinary row was created in its place, and the addressed row is untouched.
    assert UcrDeclaration.objects.filter(owner=world["instructor"]).count() == 0
    demonstration.refresh_from_db()
    assert demonstration.exporter_name == "ACME Trading"
    assert demonstration.status == UcrDeclaration.Status.DRAFT
    assert demonstration.demonstration_session_id == world["session"].pk


@pytest.mark.django_db
def test_an_ordinary_submit_addressing_a_demonstration_draft_is_refused(db):
    world = recording("scope-submit")
    demonstration = demo_ucr(world["session"])
    client = Client()
    client.force_login(world["instructor"])

    response = _post_json(client, "ucr-submit", _save_payload(draft_id=demonstration.pk))

    assert response.status_code == 403
    assert response.json()["code"] == "record_out_of_scope"
    demonstration.refresh_from_db()
    assert demonstration.status == UcrDeclaration.Status.DRAFT
    assert not demonstration.ucr_no
    assert UcrDeclaration.objects.filter(owner=world["instructor"]).count() == 0


@pytest.mark.django_db
def test_another_users_demonstration_draft_answers_exactly_like_an_unknown_id(db):
    """A refusal that confirmed the row exists would itself be a disclosure."""
    world = recording("scope-stranger")
    demonstration = demo_ucr(world["session"])
    intruder = instructor("scope-intruder")
    client = Client()
    client.force_login(intruder)

    addressed = _post_json(client, "ucr-save", _save_payload(draft_id=demonstration.pk))
    unknown = _post_json(client, "ucr-save", _save_payload(draft_id=999_999))

    assert addressed.status_code == unknown.status_code == 200
    assert addressed.json().keys() == unknown.json().keys()
    assert "record_out_of_scope" not in addressed.content.decode()
    created = UcrDeclaration.objects.get(pk=addressed.json()["id"])
    assert created.owner == intruder
    assert created.demonstration_session_id is None
    demonstration.refresh_from_db()
    assert demonstration.exporter_name == "ACME Trading"


@pytest.mark.django_db
def test_an_ordinary_draft_is_still_saved_by_its_owner(db):
    world = recording("scope-ordinary")
    ordinary = ordinary_ucr(world["instructor"])
    client = Client()
    client.force_login(world["instructor"])

    response = _post_json(client, "ucr-save", _save_payload(draft_id=ordinary.pk))

    assert response.status_code == 200
    assert response.json()["id"] == ordinary.pk
    ordinary.refresh_from_db()
    assert ordinary.importer_name == "Ordinary Importer"
    assert ordinary.demonstration_session_id is None


# --- Attachments and admin joins (Stage 1A.1 D7) ----------------------------


def _attachment(ucr, name):
    return UcrDocumentAttachment.objects.create(
        ucr=ucr, row_index=0, file=f"ucr_attachments/{name}", original_name=name,
    )


def _uploaded_pdf():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile("evidence.pdf", b"%PDF-1.4 demonstration", content_type="application/pdf")


@pytest.mark.django_db
def test_the_attachment_route_refuses_a_demonstration_file_even_for_its_owner(db, settings, tmp_path):
    """The route resolves the attachment, then the UCR by join — so it names its scope."""
    settings.MEDIA_ROOT = str(tmp_path)
    (tmp_path / "ucr_attachments").mkdir()
    (tmp_path / "ucr_attachments" / "ordinary.pdf").write_bytes(b"%PDF-1.4 ordinary")
    (tmp_path / "ucr_attachments" / "demo.pdf").write_bytes(b"%PDF-1.4 demonstration")
    world = recording("scope-attachment")
    demonstration = demo_ucr(world["session"])
    ordinary = ordinary_ucr(world["instructor"])
    demo_row = _attachment(demonstration, "demo.pdf")
    ordinary_row = _attachment(ordinary, "ordinary.pdf")
    owner = Client()
    owner.force_login(world["instructor"])

    # Owner-based access is unchanged for ordinary work...
    assert owner.get(reverse("ucr-attachment", args=[ordinary_row.pk])).status_code == 200
    # ...and the demonstration file is not reachable by id, not even for the
    # instructor who recorded it.
    assert owner.get(reverse("ucr-attachment", args=[demo_row.pk])).status_code == 404
    assert UcrDocumentAttachment.objects.filter(pk=demo_row.pk, ucr__demonstration_session__isnull=True).exists() is False

    stranger = Client()
    stranger.force_login(instructor("scope-attachment-stranger"))
    assert stranger.get(reverse("ucr-attachment", args=[ordinary_row.pk])).status_code == 404
    assert stranger.get(reverse("ucr-attachment", args=[demo_row.pk])).status_code == 404


@pytest.mark.django_db
def test_the_media_path_join_never_serves_a_demonstration_attachment(db, settings, tmp_path):
    """``/media/`` is the second way to a file; it starts on the attachment too."""
    settings.MEDIA_ROOT = str(tmp_path)
    (tmp_path / "ucr_attachments").mkdir()
    (tmp_path / "ucr_attachments" / "ordinary.pdf").write_bytes(b"%PDF-1.4 ordinary")
    (tmp_path / "ucr_attachments" / "demo.pdf").write_bytes(b"%PDF-1.4 demonstration")
    world = recording("scope-media")
    _attachment(demo_ucr(world["session"]), "demo.pdf")
    _attachment(ordinary_ucr(world["instructor"]), "ordinary.pdf")
    owner = Client()
    owner.force_login(world["instructor"])

    assert owner.get("/media/ucr_attachments/ordinary.pdf").status_code == 200
    assert owner.get("/media/ucr_attachments/demo.pdf").status_code == 404

    # Staff and Administrators review ordinary work; the demonstration scope is
    # not ordinary work, so no role reaches around the rule.
    reviewer = User.objects.create_superuser(username="scope-media-root", email="media@example.test", password="x")
    staff = Client()
    staff.force_login(reviewer)
    assert staff.get("/media/ucr_attachments/demo.pdf").status_code == 404


@pytest.mark.django_db
def test_a_posted_file_cannot_be_attached_to_a_demonstration_draft(db):
    """The save endpoint refuses before ``_save_ucr_attachments`` runs."""
    world = recording("scope-upload")
    demonstration = demo_ucr(world["session"])
    client = Client()
    client.force_login(world["instructor"])

    response = client.post(
        reverse("ucr-save"),
        json.dumps(_save_payload(
            draft_id=demonstration.pk,
            documents=[{"code": "INV", "name": "Invoice", "reference": "INV-1"}],
        )),
        content_type="application/json",
        FILES={"file_0": _uploaded_pdf()},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "record_out_of_scope"
    assert UcrDocumentAttachment.objects.count() == 0
    assert UcrDeclaration.all_objects.filter(owner=world["instructor"]).count() == 1


def _mda_world(owner, ucr, suffix):
    """The IDF → consignment → MDA chain the BOE hangs off, over one UCR."""
    agency = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "Ministry of Trade and Industry"})[0]
    application = MdaApplication.objects.get_or_create(mda=agency, code="IDF", defaults={"name": "Import Duty Form"})[0]
    process = MdaProcess.objects.get_or_create(application=application, code="NEW", defaults={"name": "New Application"})[0]
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, application_no=f"CD{suffix}",
        status=ConsignmentApplication.Status.SUBMITTED,
    )
    return MdaConsignmentRequest.objects.create(
        consignment_application=consignment, owner=owner, mda=agency, application=application,
        process=process, consignment_type="SG", application_no=f"IDF{suffix}",
    )


@pytest.mark.django_db
def test_admin_lists_and_searches_hold_back_rows_built_on_a_demonstration(db):
    """Three joined models, three admin joins that must name the ordinary scope."""
    world = recording("scope-admin-join")
    demonstration = demo_ucr(world["session"], ucr_no="KGHTESTUCR9000000009", status=UcrDeclaration.Status.SUBMITTED)
    first = ordinary_ucr(world["instructor"], ucr_no="KGHTESTUCR9000000001", status=UcrDeclaration.Status.SUBMITTED)
    second = ordinary_ucr(world["instructor"], ucr_no="KGHTESTUCR9000000002", status=UcrDeclaration.Status.SUBMITTED)
    demo_idf = _mda_world(world["instructor"], demonstration, "DEMO0001")
    ordinary_idf = _mda_world(world["instructor"], first, "ORD00001")
    BoeDeclaration.objects.create(owner=world["instructor"], job_no="JOBDEMO0001", idf=demo_idf, ucr=demonstration)
    BoeDeclaration.objects.create(owner=world["instructor"], job_no="JOBORD00001", idf=ordinary_idf, ucr=second)

    client = Client()
    client.force_login(User.objects.create_superuser(username="scope-admin-root", email="join@example.test", password="x"))

    def listed(route, **params):
        """Rows the changelist actually rendered — not text a search box echoes back."""
        response = client.get(reverse(route), params)
        assert response.status_code == 200, route
        return [row.pk for row in response.context["cl"].result_list]

    ordinary_boe = BoeDeclaration.objects.get(job_no="JOBORD00001")
    demo_boe = BoeDeclaration.objects.get(job_no="JOBDEMO0001")
    cases = [
        ("admin:scenarios_consignmentapplication_changelist",
         ordinary_idf.consignment_application, demo_idf.consignment_application),
        ("admin:scenarios_mdaconsignmentrequest_changelist", ordinary_idf, demo_idf),
        ("admin:scenarios_boedeclaration_changelist", ordinary_boe, demo_boe),
    ]
    for route, ordinary_row, demo_row in cases:
        shown = listed(route)
        assert ordinary_row.pk in shown, route
        assert demo_row.pk not in shown, route

    # Search runs through the same queryset, so naming the demonstration UCR
    # (or a row attached to it) must not be a way around the listing rule.
    mda_changelist = "admin:scenarios_mdaconsignmentrequest_changelist"
    boe_changelist = "admin:scenarios_boedeclaration_changelist"
    assert listed(mda_changelist, q=demonstration.ucr_no) == []
    assert listed(mda_changelist, q=demo_idf.application_no) == []
    assert listed(boe_changelist, q=demo_idf.application_no) == []
    # The ordinary rows still answer to the same searches.
    assert ordinary_idf.pk in listed(mda_changelist, q=ordinary_idf.application_no)
    assert listed(boe_changelist, q=ordinary_idf.application_no) == [ordinary_boe.pk]
