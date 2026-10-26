"""Stage 3 Checkpoint 3.1 — creation-evidence ledger and route transactions.

Every creation route that persists an approved registry record is wrapped in
``transaction.atomic`` (``scenarios/urls.py``), so each POST below proves the
checkpoint guarantee: the simulator record and its
``hybrid.SimulatorRecordCreation`` evidence row commit together, and a forced
evidence failure rolls both back. Model-level tests cover registry filtering,
update suppression, backfill absence, bulk bypass and idempotent registration.

Known documented limitation: ``bulk_create``/raw SQL bypass Django signals
and capture nothing; no supported creation path uses them.
"""
import json

import pytest
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save

from accounts.models import User
from hybrid import creation_ledger
from hybrid.models import SimulatorRecordCreation
from scenarios.models import (
    BoeDeclaration,
    ConsignmentApplication,
    CustomsProcedureCode,
    CustomsRegime,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    UcrDeclaration,
)

SCREEN = "single-window-overview"


def _user(db, username, staff=False):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.test", password="x",
    )
    user.is_staff = staff
    user.save(update_fields=("is_staff",))
    return user


def _staff_client(client, user):
    client.force_login(user)
    return client


def _ucr(user, temp_no, **overrides):
    return UcrDeclaration.objects.create(owner=user, temp_no=temp_no, regime="CO", **overrides)


def _submitted_ucr(user, ucr_no):
    return UcrDeclaration.objects.create(
        owner=user, temp_no=f"TEMP{ucr_no}", ucr_no=ucr_no,
        regime="IM", status=UcrDeclaration.Status.SUBMITTED,
    )


def _consignment(user, ucr, application_no):
    return ConsignmentApplication.objects.create(
        owner=user, ucr=ucr, application_no=application_no,
        status=ConsignmentApplication.Status.DRAFT,
    )


def _mda_chain(user, seed):
    """Agency, application, process, UCR, consignment application and the
    MOTI IDF request that BOE creation reuses."""
    agency = MdaAgency.objects.create(code="MOTI", name="Ministry of Trade and Industry")
    application = MdaApplication.objects.create(mda=agency, code="IDF", name="IDF")
    process = MdaProcess.objects.create(application=application, code="P1", name="Process 1")
    ucr = _ucr(user, f"TEMP{seed}")
    application_row = _consignment(user, ucr, f"APP-{seed}")
    request_row = MdaConsignmentRequest.objects.create(
        consignment_application=application_row,
        owner=user,
        mda=agency,
        application=application,
        process=process,
        consignment_type=MdaConsignmentRequest.ConsignmentType.SINGLE,
        application_no=f"MDANUM{seed}",
    )
    return request_row


# --- Capture mechanics (model level) ------------------------------------------------


@pytest.mark.django_db
def test_every_registry_kind_captures_one_evidence_row(db):
    user = _user(db, "ledger-kinds")

    ucr = _ucr(user, "TEMPKUCR")
    mda = _mda_chain(user, "KMDA")
    boe_ucr = _ucr(user, "TEMPKB")
    boe = BoeDeclaration.objects.create(owner=user, job_no="JOBK1", idf=mda, ucr=boe_ucr)
    app_ucr = _ucr(user, "TEMPKAPP")
    consignment = _consignment(user, app_ucr, "APPK1")

    expected = {
        ("ucr", ucr.pk): ucr,
        ("ucr", mda.consignment_application.ucr_id): mda.consignment_application.ucr,
        ("mda", mda.pk): mda,
        ("consignment", mda.consignment_application_id): mda.consignment_application,
        ("ucr", boe_ucr.pk): boe_ucr,
        ("boe", boe.pk): boe,
        ("ucr", app_ucr.pk): app_ucr,
        ("consignment", consignment.pk): consignment,
    }
    assert SimulatorRecordCreation.objects.count() == len(expected)
    for (kind, record_id), record in expected.items():
        row = SimulatorRecordCreation.objects.get(record_kind=kind, record_id=record_id)
        assert row.owner_id == user.pk
        assert row.record_created_at == record.created_at
        assert row.captured_at is not None


@pytest.mark.django_db
def test_updates_never_generate_new_evidence(db):
    user = _user(db, "ledger-update")
    ucr = _ucr(user, "TEMPUPD")
    assert SimulatorRecordCreation.objects.count() == 1

    ucr.regime = "EX"
    ucr.save()
    ucr.save()

    assert SimulatorRecordCreation.objects.count() == 1


@pytest.mark.django_db
def test_an_anomalous_duplicate_signal_fails_loudly(db):
    """A second created=True dispatch for one record is an anomaly: the unique
    constraint refuses the duplicate and the failure raises from the save —
    the original evidence row remains as history."""
    user = _user(db, "ledger-duplicate")
    ucr = _ucr(user, "TEMPDUP")
    assert SimulatorRecordCreation.objects.count() == 1

    # The IntegrityError marks the surrounding test transaction for rollback,
    # so every assertion happens before the send; the constraint itself is the
    # proof that no duplicate evidence row can exist.
    with pytest.raises(IntegrityError):
        post_save.send(
            UcrDeclaration, instance=ucr, created=True, raw=False,
            using="default", update_fields=None,
        )


@pytest.mark.django_db
def test_unsupported_models_capture_nothing(db):
    user = _user(db, "ledger-unsupported")
    ucr = _ucr(user, "TEMPUNS")
    assert SimulatorRecordCreation.objects.count() == 1

    from scenarios.models import UcrDocumentAttachment

    UcrDocumentAttachment.objects.create(ucr=ucr, row_index=0, original_name="support.pdf")
    MdaAgency.objects.create(code="ZZT1", name="Not a registry agency")

    assert SimulatorRecordCreation.objects.count() == 1


@pytest.mark.django_db
def test_existing_records_are_not_backfilled(db):
    from scenarios.bindings import VERIFY_RECORDS

    ucr_model = VERIFY_RECORDS["ucr"][0]
    user = _user(db, "ledger-nobackfill")
    other = _user(db, "ledger-nobackfill-other")

    creation_ledger.disconnect_capture_receivers()
    try:
        orphan = _ucr(other, "TEMPNB")
    finally:
        creation_ledger.register_capture_receivers()

    ucr = _ucr(user, "TEMPNB2")

    assert SimulatorRecordCreation.objects.count() == 1
    row = SimulatorRecordCreation.objects.get()
    assert row.record_id == ucr.pk
    assert row.owner_id == user.pk
    assert not SimulatorRecordCreation.objects.filter(owner=other).exists()


@pytest.mark.django_db
def test_bulk_create_bypasses_the_ledger_by_documented_design(db):
    user = _user(db, "ledger-bulk")
    UcrDeclaration.objects.bulk_create([
        UcrDeclaration(owner=user, temp_no="TEMPBLK1", regime="CO"),
        UcrDeclaration(owner=user, temp_no="TEMPBLK2", regime="CO"),
    ])

    assert UcrDeclaration.objects.count() == 2
    assert SimulatorRecordCreation.objects.count() == 0


@pytest.mark.django_db
def test_the_ledger_is_evidence_only_and_changes_no_journey_state(db):
    from hybrid.models import JourneyAttempt, JourneyRecordAssociation, JourneyRecordRole

    user = _user(db, "ledger-evidenceonly")
    _ucr(user, "TEMPEO")

    assert SimulatorRecordCreation.objects.count() == 1
    assert JourneyRecordAssociation.objects.count() == 0
    assert JourneyRecordRole.objects.count() == 0
    assert JourneyAttempt.objects.count() == 0


@pytest.mark.django_db
def test_capture_registration_is_idempotent(db):
    user = _user(db, "ledger-reg")
    _ucr(user, "TEMPREG1")
    assert SimulatorRecordCreation.objects.count() == 1

    creation_ledger.register_capture_receivers()
    creation_ledger.register_capture_receivers()

    ucr2 = _ucr(user, "TEMPREG2")
    assert SimulatorRecordCreation.objects.filter(
        record_kind="ucr", record_id=ucr2.pk,
    ).count() == 1


# --- Route-level transaction guarantees (real URLs, real client) ---------------------


def _ucr_payload():
    return {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "DCL001", "code": "SUP001", "name": "Supplier",
            "country": "GH", "address": "1 Supplier Way",
            "contact": "Supplier Contact", "phone": "0200000000",
            "email": "supplier@example.test",
        },
        "exporter": {
            "identity": "", "name": "Exporter", "country": "GH",
            "address": "1 Export Road", "phone": "0210000000",
            "contact": "Export Contact", "contact_no": "C-100",
            "designation": "Exports",
        },
        "importer": {
            "identity": "", "name": "Importer", "country": "NL",
            "address": "1 Import Street", "phone": "0900000000",
            "contact": "Import Contact", "contact_no": "C-200",
            "designation": "Imports",
        },
        "consignment": {
            "mode": "30", "goods": "General merchandise",
            "origin": "GH", "destination": "NL", "reference": "REF-1",
            "email": "",
        },
        "documents": [],
    }


@pytest.mark.django_db
def test_ucr_save_route_commits_record_and_evidence_together(client, db):
    user = _user(db, "route-ucr", staff=True)
    _staff_client(client, user)

    response = client.post(
        "/practical/single-window/ucr/save/",
        data=json.dumps(_ucr_payload()),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert UcrDeclaration.objects.filter(owner=user, temp_no__startswith="TEMPUCR").exists()
    assert SimulatorRecordCreation.objects.count() == 1
    row = SimulatorRecordCreation.objects.get()
    assert row.owner_id == user.pk
    assert row.record_created_at == UcrDeclaration.objects.get().created_at


@pytest.mark.django_db
def test_ucr_save_route_rolls_back_record_and_evidence_on_capture_failure(client, db, monkeypatch):
    user = _user(db, "route-ucr-fail", staff=True)
    _staff_client(client, user)

    def broken(*args, **kwargs):
        raise RuntimeError("ledger storage unavailable")

    monkeypatch.setattr(SimulatorRecordCreation.objects, "create", broken)

    with pytest.raises(RuntimeError):
        client.post(
            "/practical/single-window/ucr/save/",
            data=json.dumps(_ucr_payload()),
            content_type="application/json",
        )

    assert UcrDeclaration.objects.count() == 0
    assert SimulatorRecordCreation.objects.count() == 0


@pytest.mark.django_db
def test_ucr_clone_route_commits_clone_and_evidence(client, db):
    user = _user(db, "route-clone", staff=True)
    _staff_client(client, user)
    source = _ucr(user, "TEMPCLONESRC")

    response = client.post(f"/practical/single-window/ucr/{source.pk}/clone/")

    assert response.status_code == 302  # redirects to the new draft
    clone = UcrDeclaration.objects.exclude(pk=source.pk).get()
    assert clone.owner_id == user.pk
    assert clone.derivation == "clone"
    rows = SimulatorRecordCreation.objects.order_by("record_created_at")
    assert [row.record_id for row in rows] == [source.pk, clone.pk]


@pytest.mark.django_db
def test_ucr_clone_route_rolls_back_clone_and_evidence_on_capture_failure(client, db, monkeypatch):
    user = _user(db, "route-clone-fail", staff=True)
    _staff_client(client, user)
    source = _ucr(user, "TEMPCLONEFAIL")

    def broken(*args, **kwargs):
        raise RuntimeError("ledger storage unavailable")

    monkeypatch.setattr(SimulatorRecordCreation.objects, "create", broken)

    with pytest.raises(RuntimeError):
        client.post(f"/practical/single-window/ucr/{source.pk}/clone/")

    assert UcrDeclaration.objects.filter(derivation="clone").count() == 0
    assert UcrDeclaration.objects.filter(pk=source.pk).exists()
    assert SimulatorRecordCreation.objects.count() == 1


@pytest.mark.django_db
def test_boe_create_route_commits_declaration_and_evidence(client, db):
    CustomsRegime.objects.create(code="IM", name="Imports", is_active=True)
    regime = CustomsRegime.objects.get(code="IM")
    CustomsProcedureCode.objects.create(
        regime=regime, code="IM40", description="Straight entry", is_active=True,
    )
    user = _user(db, "route-boe", staff=True)
    _staff_client(client, user)
    mda = _mda_chain(user, "BOEROUTE")

    response = client.post(
        "/practical/clearance/boe/create/",
        data=json.dumps({
            "reuse": "IDF",
            "idf_number": mda.application_no,
            "regime": "IM",
            "cpc": "IM40",
            "zone": "GEN",
        }),
        content_type="application/json",
    )

    assert response.status_code == 200
    boe = BoeDeclaration.objects.get()  # single declaration in this test
    assert boe.idf_id == mda.pk and boe.ucr_id == mda.consignment_application.ucr_id
    assert sorted(SimulatorRecordCreation.objects.values_list("record_kind", flat=True)) == [
        "boe", "consignment", "mda", "ucr",
    ]


@pytest.mark.django_db
def test_boe_create_route_rolls_back_declaration_and_evidence_on_capture_failure(
    client, db, monkeypatch,
):
    CustomsRegime.objects.create(code="IM", name="Imports", is_active=True)
    CustomsProcedureCode.objects.create(
        regime=CustomsRegime.objects.get(code="IM"), code="IM4000",
        description="Straight entry", is_active=True,
    )
    user = _user(db, "route-boe-fail", staff=True)
    _staff_client(client, user)
    mda = _mda_chain(user, "BOEFAIL")

    def broken(*args, **kwargs):
        raise RuntimeError("ledger storage unavailable")

    monkeypatch.setattr(SimulatorRecordCreation.objects, "create", broken)

    with pytest.raises(RuntimeError):
        client.post(
            "/practical/clearance/boe/create/",
            data=json.dumps({
                "reuse": "IDF", "idf_number": mda.application_no,
                "regime": "IM", "cpc": "IM4000", "zone": "GEN",
            }),
            content_type="application/json",
        )

    assert BoeDeclaration.objects.count() == 0
    # The chain's own evidence rows survive; the declaration and its evidence
    # rolled back with the route transaction.
    assert sorted(SimulatorRecordCreation.objects.values_list("record_kind", flat=True)) == [
        "consignment", "mda", "ucr",
    ]


@pytest.mark.django_db
def test_application_save_route_commits_application_and_evidence(client, db):
    user = _user(db, "route-app", staff=True)
    _staff_client(client, user)
    _submitted_ucr(user, "KGHTESTUCRAP1")

    payload = {
        "ucr_no": "KGHTESTUCRAP1",
        "exporter": {"name": "Exporter", "physical_country": "GH",
                     "physical_address": "1 Export Road", "tel": "0210000000"},
        "consignor": {"name": "Consignor", "physical_country": "GH",
                      "physical_address": "2 Consign Road", "tel": "0210000001"},
        "importer": {"code": "IMP001", "name": "Importer", "physical_country": "NL",
                     "physical_address": "3 Import Street", "tel": "0900000000"},
        "consignee": {"code": "CON001", "name": "Consignee", "physical_country": "NL",
                      "physical_address": "4 Consign Street", "tel": "0900000001"},
    }

    response = client.post(
        "/practical/single-window/application/consignment-document/save/",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200, response.content.decode()[:400]
    application = ConsignmentApplication.objects.get(owner=user)
    assert application.status == ConsignmentApplication.Status.DRAFT
    assert application.application_no
    assert SimulatorRecordCreation.objects.filter(
        record_kind="consignment", record_id=application.pk,
    ).exists()


@pytest.mark.django_db
def test_application_save_route_rolls_back_on_evidence_failure(client, db, monkeypatch):
    user = _user(db, "route-app-fail", staff=True)
    _staff_client(client, user)
    _submitted_ucr(user, "KGHTESTUCRAF1")

    def broken(*args, **kwargs):
        raise RuntimeError("ledger storage unavailable")

    monkeypatch.setattr(SimulatorRecordCreation.objects, "create", broken)

    payload = {
        "ucr_no": "KGHTESTUCRAF1",
        "exporter": {"name": "Exporter", "physical_country": "GH",
                     "physical_address": "1 Export Road", "tel": "0210000000"},
        "consignor": {"name": "Consignor", "physical_country": "GH",
                      "physical_address": "2 Consign Road", "tel": "0210000001"},
        "importer": {"code": "IMP001", "name": "Importer", "physical_country": "NL",
                     "physical_address": "3 Import Street", "tel": "0900000000"},
        "consignee": {"code": "CON001", "name": "Consignee", "physical_country": "NL",
                      "physical_address": "4 Consign Street", "tel": "0900000001"},
    }

    with pytest.raises(RuntimeError):
        client.post(
            "/practical/single-window/application/consignment-document/save/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    assert ConsignmentApplication.objects.filter(owner=user).count() == 0
    # The fixture UCR's own evidence survives; the application and its
    # evidence rolled back with the route transaction.
    assert sorted(SimulatorRecordCreation.objects.values_list("record_kind", flat=True)) == ["ucr"]


@pytest.mark.django_db
def test_mda_dialog_route_keeps_its_own_atomic_on_capture_failure(client, db, monkeypatch):
    """The MDA dialog route already wraps itself in transaction.atomic: a
    capture failure inside it still rolls the MDA request back — the
    guarantee does not depend on the route wrappers."""
    user = _user(db, "route-mda", staff=True)
    _staff_client(client, user)
    ucr = _submitted_ucr(user, "KGHTESTUCRMDA")
    application = ConsignmentApplication.objects.create(
        owner=user, ucr=ucr, application_no="APPMDA1",
        status=ConsignmentApplication.Status.DRAFT,
    )
    agency = MdaAgency.objects.create(code="MOTIX", name="Ministry of Trade")
    mda_application = MdaApplication.objects.create(mda=agency, code="IDF", name="IDF")
    process = MdaProcess.objects.create(application=mda_application, code="P1", name="Process")

    def broken(*args, **kwargs):
        raise RuntimeError("ledger storage unavailable")

    monkeypatch.setattr(SimulatorRecordCreation.objects, "create", broken)

    with pytest.raises(RuntimeError):
        client.post(
            "/practical/single-window/application/consignment-document/mda-requests/",
            data=json.dumps({
                "consignment_application_id": application.pk,
                "mda_id": agency.pk,
                "application_id": mda_application.pk,
                "process_id": process.pk,
                "consignment_type": "SG",
            }),
            content_type="application/json",
        )

    assert MdaConsignmentRequest.objects.count() == 0
    assert ConsignmentApplication.objects.count() == 1
    # The fixture rows' evidence survives; the MDA request and its evidence
    # rolled back inside the view's own transaction.
    assert sorted(SimulatorRecordCreation.objects.values_list("record_kind", flat=True)) == [
        "consignment", "ucr",
    ]
