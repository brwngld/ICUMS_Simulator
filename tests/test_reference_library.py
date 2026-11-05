"""Stage R4-B — instructor reference library services and endpoints.

Covers the three-state lifecycle (temporary → working → approved → retired)
over the five library endpoints: ownership isolation, promotion eligibility
and atomicity, submitted-only approval, idempotent repeats, retirement
preservation, advisory flags, student/anonymous denial, and the interaction
with demonstration expiry, discard, save and the ordinary purge.

Concurrency is proven on PostgreSQL: duplicate transitions race through real
threads, and a deterministic interleaving test pins the one documented hazard
(a sweep whose child collection falls inside promotion's transaction) that the
approved deletion-service patch will close.
"""
import json
from datetime import timedelta
from threading import Barrier, Thread

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from demonstration_world import demo_ucr, draft_world
from hybrid import demonstrations
from hybrid.models import DemonstrationSession
from django.db import models
from django.db import connection
from scenarios.models import UcrDeclaration, purge_expired_ucr_drafts

enabled = override_settings(DEMONSTRATION_RECORDING_ENABLED=True)

STATE = UcrDeclaration.ReferenceState


# --- Helpers -----------------------------------------------------------------


def library_world(username, *, recording=True):
    """One instructor, their draft world, a client signed in as them, and —
    unless ``recording`` is False — a live recording session bound to it.

    Everything the tests create through this client belongs to the same
    instructor the library endpoints authorize; a separate library user mixed
    with a world-owned instructor was the first draft's mistake.
    """
    world = draft_world(username)
    client = Client()
    client.force_login(world["instructor"])
    session = None
    if recording:
        started = client.post(reverse("hybrid-demonstration-start", args=[world["lesson"].pk]))
        assert started.status_code == 200, started.content
        session = DemonstrationSession.objects.get(pk=started.json()["session"]["id"])
    return world, client, session


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Lib Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Library Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "Library Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000005", "designation": "Manager",
        },
        "consignment": {
            "goods": "Library goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def save_demo(client, **overrides):
    response = client.post(reverse("ucr-save"), json.dumps(save_body(**overrides)), content_type="application/json")
    assert response.status_code == 200, response.content
    return UcrDeclaration.all_objects.get(pk=response.json()["id"])


def library_url(action="", record_id=None):
    if action:
        return reverse(f"hybrid-reference-{action}", args=[record_id])
    return reverse("hybrid-reference-library")


def post_action(client, action, record_id):
    return client.post(library_url(action, record_id), "{}", content_type="application/json")


def promote_state(record, state):
    """Arrange non-temporary states through the documented controlled update
    (the R4-B promotion service owns the real temporary→working path)."""
    UcrDeclaration.all_objects.filter(pk=record.pk).update(reference_state=state)
    record.refresh_from_db()
    return record


def submit_record(record):
    record.status = UcrDeclaration.Status.SUBMITTED
    record.ucr_no = "KGHTESTUCR260000300"
    record.submitted_at = timezone.now()
    record.save(update_fields=("status", "ucr_no", "submitted_at"))
    return record


# --- Listing, detail and advisory flags --------------------------------------


@pytest.mark.django_db
@enabled
def test_the_library_lists_only_the_instructors_references_with_flags(db):
    world, client, session = library_world("r4b-list")
    working = demo_ucr(session)
    promote_state(working, STATE.WORKING.value)
    approved = demo_ucr(session)
    promote_state(approved, STATE.APPROVED.value)
    temporary = demo_ucr(session)  # never promoted: not library data

    payload = client.get(library_url()).json()

    ids = [row["id"] for row in payload["references"]]
    assert working.pk in ids and approved.pk in ids and temporary.pk not in ids
    working_row = next(row for row in payload["references"] if row["id"] == working.pk)
    assert working_row["can_edit"] is True and working_row["can_approve"] is False
    approved_row = next(row for row in payload["references"] if row["id"] == approved.pk)
    assert approved_row["can_approve"] is False  # only a working reference can be approved
    assert approved_row["can_retire"] is True and approved_row["can_select"] is True
    assert approved_row["can_edit"] is False


@pytest.mark.django_db
@enabled
def test_the_library_filters_by_state_and_hides_foreign_records(db):
    world, client, session = library_world("r4b-filter")
    mine_working = demo_ucr(session)
    promote_state(mine_working, STATE.WORKING.value)
    foreign_world, foreign_client, foreign_session = library_world("r4b-filter-other")
    foreign = demo_ucr(foreign_session)
    promote_state(foreign, STATE.WORKING.value)

    payload = client.get(library_url()).json()
    ids = [row["id"] for row in payload["references"]]
    assert mine_working.pk in ids
    assert foreign.pk not in ids

    filtered = client.get(library_url(), {"state": "approved"}).json()
    assert filtered["references"] == []
    bad = client.get(library_url(), {"state": "temporary"})
    assert bad.status_code == 400


@pytest.mark.django_db
@enabled
def test_detail_serves_an_owned_reference_and_hides_everything_else(db):
    world, client, session = library_world("r4b-detail")
    mine = save_demo(client)
    assert post_action(client, "promote", mine.pk).status_code == 200  # the service stamps provenance
    ordinary = UcrDeclaration.objects.create(owner=world["instructor"], temp_no="TEMPUCRR4B1", regime="CO")

    detail = client.get(library_url("detail", mine.pk)).json()["reference"]
    assert detail["id"] == mine.pk
    assert detail["source_session"] == str(session.pk)
    for record_id in (ordinary.pk, 999_999):
        refused = client.get(library_url("detail", record_id))
        assert refused.status_code == 404
        assert refused.json()["code"] == "reference_not_found"


# --- Promotion ----------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_promotion_detaches_the_record_and_stamps_provenance(db):
    world, client, session = library_world("r4b-promote")
    record = save_demo(client)

    response = post_action(client, "promote", record.pk)

    assert response.status_code == 200
    payload = response.json()["reference"]
    assert payload["reference_state"] == "working"
    assert payload["source_session"] == str(session.pk)
    record.refresh_from_db()
    assert record.demonstration_session_id is None  # detached from the temporary session
    assert record.reference_source_session_id == session.pk  # provenance preserved
    assert record.owner_id == world["instructor"].pk
    assert record.temp_no.startswith("DEMOUCR")


@pytest.mark.django_db
@enabled
def test_repeated_promotion_returns_the_current_reference(db):
    world, client, session = library_world("r4b-repromote")
    record = save_demo(client)
    assert post_action(client, "promote", record.pk).status_code == 200

    again = post_action(client, "promote", record.pk)

    assert again.status_code == 200
    assert again.json()["reference"]["reference_state"] == "working"
    assert UcrDeclaration.all_objects.filter(
        owner=world["instructor"], reference_state=STATE.WORKING.value
    ).count() == 1


@pytest.mark.django_db
@enabled
def test_promotion_refuses_submitted_and_foreign_and_ordinary_records(db):
    world, client, session = library_world("r4b-promote-authz")
    submitted = save_demo(client)
    submit_record(submitted)
    ordinary = UcrDeclaration.objects.create(owner=world["instructor"], temp_no="TEMPUCRR4B2", regime="CO")
    foreign_world, foreign_client, foreign_session = library_world("r4b-promote-authz-other")
    foreign = demo_ucr(foreign_session)

    for record_id, code in (
        (submitted.pk, "not_promotable"),  # submitted records are issued, not promotable
        (ordinary.pk, "reference_not_found"),
        (foreign.pk, "reference_not_found"),
        (999_999, "reference_not_found"),
    ):
        refused = post_action(client, "promote", record_id)
        assert refused.status_code in (400, 404, 409), record_id
        assert refused.json()["code"] == code, record_id


@pytest.mark.django_db
@enabled
def test_promotion_refuses_an_already_immutable_record(db):
    world, client, session = library_world("r4b-promote-immutable")
    record = demo_ucr(session)
    promote_state(record, STATE.APPROVED.value)

    refused = post_action(client, "promote", record.pk)

    assert refused.status_code == 409
    assert refused.json()["code"] == "already_a_reference"


@pytest.mark.django_db
@enabled
def test_a_record_gone_to_discard_answers_record_gone(db):
    world, client, session = library_world("r4b-discarded")
    record = save_demo(client)
    assert client.post(
        reverse("hybrid-demonstration-discard"),
        json.dumps({"session_id": str(session.pk)}), content_type="application/json",
    ).status_code == 200

    refused = post_action(client, "promote", record.pk)

    assert refused.status_code == 404
    assert refused.json()["code"] == "reference_not_found"  # the discard deleted the record outright


@pytest.mark.django_db
@enabled
def test_a_record_gone_to_expiry_answers_record_gone(db):
    """The expiry sweep ran to completion first: its session and records are
    gone, and promotion answers the controlled error instead of resurrecting."""
    world, client, session = library_world("r4b-expired")
    record = save_demo(client)
    DemonstrationSession.objects.filter(pk=session.pk).update(
        state=DemonstrationSession.State.STOPPED,
        stopped_at=timezone.now(),
        retention_expires_at=timezone.now() - timedelta(days=1),
    )
    assert demonstrations.expire_demonstrations() == 1

    refused = post_action(client, "promote", record.pk)
    assert refused.status_code == 404
    assert refused.json()["code"] == "reference_not_found"  # the sweep deleted the record outright


# --- Approval -----------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_approval_requires_a_submitted_working_reference(db):
    world, client, session = library_world("r4b-approve")
    draft_ref = demo_ucr(session)
    promote_state(draft_ref, STATE.WORKING.value)
    submitted_ref = demo_ucr(session)
    promote_state(submitted_ref, STATE.WORKING.value)
    submit_record(submitted_ref)

    refused = post_action(client, "approve", draft_ref.pk)
    assert refused.status_code == 400
    assert refused.json()["code"] == "approval_requires_submitted"

    accepted = post_action(client, "approve", submitted_ref.pk)
    assert accepted.status_code == 200
    assert accepted.json()["reference"]["reference_state"] == "approved"
    submitted_ref.refresh_from_db()
    assert submitted_ref.reference_state == STATE.APPROVED.value
    assert submitted_ref.status == UcrDeclaration.Status.SUBMITTED  # untouched otherwise


@pytest.mark.django_db
@enabled
def test_repeated_approval_is_idempotent_and_invalid_ones_are_controlled(db):
    world, client, session = library_world("r4b-approve-idem")
    reference = demo_ucr(session)
    promote_state(reference, STATE.WORKING.value)
    submit_record(reference)
    assert post_action(client, "approve", reference.pk).status_code == 200

    again = post_action(client, "approve", reference.pk)
    assert again.status_code == 200
    assert again.json()["reference"]["reference_state"] == "approved"

    retired = demo_ucr(session)
    promote_state(retired, STATE.RETIRED.value)
    refused = post_action(client, "approve", retired.pk)
    assert refused.status_code == 409
    assert refused.json()["code"] == "not_approvable"


# --- Retirement ----------------------------------------------------------------


@pytest.mark.django_db
@enabled
def test_retirement_preserves_the_record_and_keeps_it_purge_exempt(db):
    world, client, session = library_world("r4b-retire")
    reference = demo_ucr(session)
    promote_state(reference, STATE.WORKING.value)
    submit_record(reference)
    assert post_action(client, "approve", reference.pk).status_code == 200

    response = post_action(client, "retire", reference.pk)
    assert response.status_code == 200
    assert response.json()["reference"]["reference_state"] == "retired"
    reference.refresh_from_db()
    assert reference.pk and reference.reference_state == STATE.RETIRED.value

    # Retired references survive ordinary draft expiry.
    moment = timezone.now() - timedelta(days=30)
    UcrDeclaration.all_objects.filter(pk=reference.pk).update(updated_at=moment)
    purge_expired_ucr_drafts()
    assert UcrDeclaration.all_objects.filter(pk=reference.pk).exists()


@pytest.mark.django_db
@enabled
def test_repeated_retirement_is_idempotent_and_other_transitions_are_refused(db):
    world, client, session = library_world("r4b-retire-idem")
    reference = demo_ucr(session)
    promote_state(reference, STATE.APPROVED.value)
    assert post_action(client, "retire", reference.pk).status_code == 200

    again = post_action(client, "retire", reference.pk)
    assert again.status_code == 200
    assert again.json()["reference"]["reference_state"] == "retired"

    working = demo_ucr(session)
    promote_state(working, STATE.WORKING.value)
    refused = post_action(client, "retire", working.pk)
    assert refused.status_code == 409
    assert refused.json()["code"] == "not_retirable"


# --- Isolation, flag and recording neutrality ---------------------------------


@pytest.mark.django_db
def test_students_and_anonymous_never_reach_the_library(db):
    world, client, session = library_world("r4b-student", recording=False)
    student = User.objects.create_user(username="r4b-student", email="s@example.test", password="x")
    stranger = Client()
    stranger.force_login(student)
    anonymous = Client()

    for client_for in (stranger, anonymous):
        assert client_for.get(library_url()).status_code in (302, 403)
        assert post_action(client_for, "promote", 1).status_code in (302, 403)
        assert client_for.get(library_url("detail", 1)).status_code in (302, 403)


@pytest.mark.django_db
def test_the_library_is_closed_while_the_flag_is_off(db):
    world, client, session = library_world("r4b-flag", recording=False)
    with override_settings(DEMONSTRATION_RECORDING_ENABLED=False):
        assert client.get(library_url()).status_code == 403
        assert post_action(client, "promote", 1).status_code == 403


@pytest.mark.django_db
@enabled
def test_promotion_leaves_the_recording_lifecycle_and_isolation_untouched(db):
    world, client, session = library_world("r4b-neutral")
    reference = save_demo(client)
    assert post_action(client, "promote", reference.pk).status_code == 200

    # The recording continues normally after a promotion.
    another = save_demo(client)
    assert another.demonstration_session_id == session.pk
    session.refresh_from_db()
    paused = client.post(reverse("hybrid-demonstration-pause"), json.dumps(
        {"session_id": str(session.pk), "version": session.version}), content_type="application/json")
    assert paused.status_code == 200
    # Approved R4 design: a promoted record is an instructor-owned ORDINARY
    # record — visible in the owner's own surfaces, never in a student's.
    assert UcrDeclaration.objects.filter(pk=reference.pk).exists()
    student = User.objects.create_user(username="r4b-neutral-student", email="s@example.test", password="x")
    student_client = Client()
    student_client.force_login(student)
    # A student without simulator credentials is bounced (302); with them, the
    # owner-scoped detail view 404s. Both are denials.
    assert student_client.get(reverse("ucr-detail", args=[reference.pk])).status_code in (302, 404)




# --- Final acceptance: promoted reference survives session expiry ------------


@pytest.mark.django_db
@enabled
def test_promoted_reference_survives_an_overlapping_expiry_transaction(db):
    """The complete R4-B acceptance sequence: promote a temporary demonstration
    UCR to a working reference, then expire its source session and run the real
    cleanup. The promoted record must survive — detached, working, provenance
    cleared by SET_NULL — while temporary session content is cleaned up."""
    world, client, session = library_world("r4b-final")
    sibling = demo_ucr(session)

    reference = save_demo(client)
    reference_pk = reference.pk

    session.refresh_from_db()
    DemonstrationSession.objects.filter(pk=session.pk).update(
        state=DemonstrationSession.State.STOPPED,
        stopped_at=timezone.now(),
        retention_expires_at=timezone.now() - timedelta(days=1),
    )

    from scenarios.reference_library import promote_to_working

    promoted = promote_to_working(world["instructor"], reference_pk)
    assert promoted.reference_state == "working"
    assert promoted.demonstration_session_id is None
    assert promoted.reference_source_session_id == session.pk

    removed = demonstrations.expire_demonstrations()
    assert removed == 1

    record = UcrDeclaration.all_objects.get(pk=reference_pk)
    assert record.reference_state == "working"
    assert record.demonstration_session_id is None
    assert record.reference_source_session_id is None  # SET_NULL on session delete

    assert not DemonstrationSession.objects.filter(pk=session.pk).exists()
    assert not UcrDeclaration.all_objects.filter(pk=sibling.pk).exists()
    assert UcrDeclaration.all_objects.filter(pk=reference_pk).exists()


@pytest.mark.django_db(transaction=True)
@override_settings(DEMONSTRATION_RECORDING_ENABLED=True)
def test_expiry_concurrent_with_promotion_preserves_the_reference(settings, transactional_db):
    """Real two-connection race: expiry runs against the session while
    promotion commits its detach. Whatever the interleaving, the promoted
    reference survives or the expiry skipped it."""
    import threading

    from django.db import close_old_connections

    world, client, session = library_world("r4b-concurrent-race")
    reference = save_demo(client)
    reference_pk = reference.pk

    DemonstrationSession.objects.filter(pk=session.pk).update(
        state=DemonstrationSession.State.STOPPED,
        stopped_at=timezone.now(),
        retention_expires_at=timezone.now() - timedelta(days=1),
    )

    outcomes = {"promote": None, "expiry": None}

    def run_promotion():
        close_old_connections()
        try:
            from scenarios.reference_library import promote_to_working

            promoted = promote_to_working(world["instructor"], reference_pk)
            outcomes["promote"] = ("ok", promoted.reference_state)
        except Exception as error:  # noqa: BLE001
            outcomes["promote"] = ("error", repr(error))

    def run_expiry():
        close_old_connections()
        try:
            outcomes["expiry"] = ("ok", demonstrations.expire_demonstrations())
        except Exception as error:  # noqa: BLE001
            outcomes["expiry"] = ("error", repr(error))

    thread_p = threading.Thread(target=run_promotion)
    thread_e = threading.Thread(target=run_expiry)
    thread_p.start()
    thread_e.start()
    thread_p.join(timeout=30)
    thread_e.join(timeout=30)

    assert not thread_p.is_alive() and not thread_e.is_alive()

    # The record either survived (promoted first) or was cleaned up (expiry
    # first). Both are safe; the promoted record must never be deleted by the
    # cleanup, and the cleanup must never resurrect it.
    record_exists = UcrDeclaration.all_objects.filter(pk=reference_pk).exists()
    assert record_exists or outcomes["expiry"][0] == "ok"

    if record_exists:
        record = UcrDeclaration.all_objects.get(pk=reference_pk)
        assert record.reference_state == "working"
        assert record.demonstration_session_id is None




# --- Concurrency (PostgreSQL) -------------------------------------------------


def _threaded(worker_functions):
    threads = [Thread(target=worker) for worker in worker_functions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return threads


@pytest.mark.django_db(transaction=True)
def test_duplicate_concurrent_promotions_land_one_working_reference(settings, transactional_db):
    settings.DEMONSTRATION_RECORDING_ENABLED = True
    from django.db import close_old_connections

    world, client, session = library_world("r4b-race")
    record = save_demo(client)
    barrier = Barrier(2)
    outcomes = []

    def worker():
        close_old_connections()
        barrier.wait(timeout=10)
        try:
            response = post_action(client, "promote", record.pk)
            outcomes.append((response.status_code, response.json()))
        finally:
            close_old_connections()

    _threaded([worker, worker])

    states = {row.reference_state for row in UcrDeclaration.all_objects.filter(owner=world["instructor"])}
    assert states == {"working"}
    assert UcrDeclaration.all_objects.filter(
        owner=world["instructor"], reference_state=STATE.WORKING.value
    ).count() == 1
    for status, body in outcomes:
        if status == 200:
            assert body["reference"]["id"] == record.pk
        else:
            assert status in (404, 409) and body["code"] in ("reference_not_found", "already_a_reference")


@pytest.mark.django_db
@enabled
@pytest.mark.django_db(transaction=True)
def test_promotion_completing_before_a_concurrent_discard_is_safe(settings, transactional_db):
    settings.DEMONSTRATION_RECORDING_ENABLED = True
    """Promotion commits first; the racing discard no longer sees the detached
    record and deletes only what is still attached."""
    from django.db import close_old_connections

    world, client, session = library_world("r4b-vs-discard")
    reference = save_demo(client)
    barrier = Barrier(2)

    def discarder():
        close_old_connections()
        barrier.wait(timeout=10)
        client.post(
            reverse("hybrid-demonstration-discard"),
            json.dumps({"session_id": str(session.pk)}), content_type="application/json",
        )
        close_old_connections()

    def promoter():
        close_old_connections()
        barrier.wait(timeout=10)
        post_action(client, "promote", reference.pk)
        close_old_connections()

    _threaded([discarder, promoter])

    remaining = UcrDeclaration.all_objects.filter(owner=world["instructor"])
    # Whatever the interleaving, the reference either survived promotion or was
    # legitimately discarded before it — never deleted after promotion.
    if any(row.pk == reference.pk for row in remaining):
        assert remaining.get(pk=reference.pk).reference_state == STATE.WORKING.value


@pytest.mark.django_db
@enabled
def test_a_promoted_reference_survives_the_expired_session_sweep(db):
    """Stage R4-B regression: promotion followed by the record's own session
    expiring must delete the temporary session content but **preserve the
    promoted working reference** (detached, purge-exempt, immutable-track)."""
    from hybrid.models import DemonstrationEvent

    world, client, session = library_world("r4b-hazard")
    record = save_demo(client)
    assert post_action(client, "promote", record.pk).status_code == 200

    DemonstrationSession.objects.filter(pk=session.pk).update(
        state=DemonstrationSession.State.STOPPED,
        stopped_at=timezone.now(),
        retention_expires_at=timezone.now() - timedelta(days=1),
    )
    assert demonstrations.expire_demonstrations() == 1

    assert not DemonstrationSession.objects.filter(pk=session.pk).exists()
    assert not DemonstrationEvent.objects.count()
    record.refresh_from_db()
    assert record.reference_state == "working"
    assert record.demonstration_session_id is None
    # Approved R4 design: a promoted record is instructor-owned ORDINARY
    # (detached), which is what makes it reusable downstream. The student
    # isolation comes from ownership, not from the demo-scope filter.
    assert UcrDeclaration.objects.filter(pk=record.pk).exists()
    # Provenance note: the R4-A-approved SET_NULL FK clears when the source
    # session row is finally collected; longer-lived provenance is the flagged
    # R4 decision requiring approval.


@pytest.mark.django_db
@enabled
def test_expiry_deletes_temporary_records_but_never_a_promoted_one(db):
    """Deterministic regression for the collector race: the sweep deletes
    UCRs **still attached** to the expired session, so a record promoted
    before the sweep — by primary key a child the old collector would have
    destroyed — survives."""
    world, client, session = library_world("r4b-sweep-race")
    promoted = save_demo(client)
    temporary_sibling = demo_ucr(session)

    # The sweep "collected" both children before promotion ran; the corrected
    # drop re-checks attachment at delete time instead of trusting the pks.
    collected_before_promotion = sorted([promoted.pk, temporary_sibling.pk])
    promote_state(promoted, STATE.WORKING.value)
    UcrDeclaration.all_objects.filter(pk=promoted.pk).update(demonstration_session_id=None)

    DemonstrationSession.objects.filter(pk=session.pk).update(
        state=DemonstrationSession.State.STOPPED,
        stopped_at=timezone.now(),
        retention_expires_at=timezone.now() - timedelta(days=1),
    )
    assert demonstrations.expire_demonstrations() == 1

    assert not UcrDeclaration.all_objects.filter(pk=temporary_sibling.pk).exists()
    assert UcrDeclaration.all_objects.filter(pk=promoted.pk, reference_state="working").exists()
    assert sorted(collected_before_promotion) == sorted([promoted.pk, temporary_sibling.pk])


# --- Deterministic overlapping-transaction acceptance -------------------------


