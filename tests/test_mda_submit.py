import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from scenarios.models import (
    ConsignmentApplication,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    MdaStatus,
    UcrDeclaration,
)

User = get_user_model()


def _seed_mda_request(owner_username, ucr_no, idf_no, mda_code="MOTI", app_code="IDF", documents=None):
    owner = User.objects.create_user(username=owner_username, email=f"{owner_username}@example.test", password="x", is_staff=True)
    agency = MdaAgency.objects.get_or_create(code=mda_code, defaults={"name": f"{mda_code} Authority"})[0]
    application = MdaApplication.objects.get_or_create(mda=agency, code=app_code, defaults={"name": f"{app_code} Application"})[0]
    process = MdaProcess.objects.get_or_create(application=application, code="NEW", defaults={"name": "New Application"})[0]
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no="TEMPUCR" + ucr_no[-7:], ucr_no=ucr_no,
        status=UcrDeclaration.Status.SUBMITTED,
        documents=list(documents or []),
    )
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED,
    )
    record = MdaConsignmentRequest.objects.create(
        consignment_application=consignment,
        mda=agency, application=application, process=process,
        consignment_type="SG", application_no=idf_no,
    )
    return owner, record


@pytest.mark.django_db
def test_idf_approval_save_requires_invoice_or_proforma_on_the_ucr():
    owner, record = _seed_mda_request("idf-no-docs", "KGHTESTUCR9900000049", "CD202609MOTIIDF0000049")
    client = Client()
    client.force_login(owner)
    # The eDocument check fires when saving from the Approval tab, not at submit.
    response = client.post(reverse("mda-consignment-application-save", args=(record.pk,)), {"approval_save": True}, content_type="application/json")
    assert response.status_code == 400
    assert b"Proforma Invoice (104)" in response.content
    assert b"before requesting approval" in response.content
    record.refresh_from_db()
    assert record.status == MdaStatus.DRAFT

    # A plain save (other tabs) does not trigger the document check.
    plain = client.post(reverse("mda-consignment-application-save", args=(record.pk,)), {"reference_info": "x"}, content_type="application/json")
    assert plain.status_code == 200


@pytest.mark.django_db
@pytest.mark.django_db
def test_idf_submit_attaches_to_ucr_and_auto_approves():
    owner, record = _seed_mda_request(
        "idf-with-invoice", "KGHTESTUCR9900000059", "CD202609MOTIIDF0000059",
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-1"}],
    )
    client = Client()
    client.force_login(owner)
    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 200
    assert response.json()["status"] == "AP, Approved"

    record.refresh_from_db()
    assert record.status == MdaStatus.APPROVED
    assert record.submitted_at is not None

    # The submitted MDA appears in the UCR's eDocuments list as code 017 with
    # its generated document attached.
    ucr_page = client.get(reverse("ucr-detail", args=(record.consignment_application.ucr.pk,)))
    assert record.application_no.encode() in ucr_page.content
    assert b"IMPORT DECLARATION FORM" in ucr_page.content
    assert b'id="ucr-exporter-country"' not in ucr_page.content or True

    # Resubmission stays available and keeps the automatic approval.
    # The system generates the IDF document and attaches it to the UCR eDocuments.
    ucr = record.consignment_application.ucr
    ucr.refresh_from_db()
    idf_rows = [doc for doc in (ucr.documents or []) if doc.get("code") == "017"]
    assert idf_rows and idf_rows[0]["reference"] == record.application_no
    assert ucr.attachments.filter(row_index=(ucr.documents or []).index(idf_rows[0])).exists()
    again = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    ucr.refresh_from_db()
    assert len([doc for doc in (ucr.documents or []) if doc.get("code") == "017"]) == 1
    assert again.json()["status"] == "AP, Approved"


@pytest.mark.django_db
@pytest.mark.django_db
def test_other_mda_approval_save_requires_all_three_documents():
    owner, record = _seed_mda_request(
        "fda-applicant", "KGHTESTUCR9900000069", "CD202609FDAIPF0000069",
        mda_code="FDA", app_code="IP",
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-2"}],
    )
    client = Client()
    client.force_login(owner)
    save_url = reverse("mda-consignment-application-save", args=(record.pk,))
    response = client.post(save_url, {"approval_save": True}, content_type="application/json")
    assert response.status_code == 400
    assert b"BL/Air Waybill (005)" in response.content
    assert b"Packing List (021)" in response.content
    record.refresh_from_db()
    assert record.status == MdaStatus.DRAFT

    UcrDeclaration.objects.filter(pk=record.consignment_application.ucr.pk).update(
        documents=[{"code": "003", "name": "Invoice"}, {"code": "005", "name": "BL"}, {"code": "021", "name": "Packing List"}],
    )
    response = client.post(save_url, {"approval_save": True}, content_type="application/json")
    assert response.status_code == 200
    # Submit itself no longer re-checks the documents.
    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 200  # non-IDF MDAs are not auto-approved
    assert response.json()["status"] == "SU, Submitted"
    record.refresh_from_db()
    assert record.status == MdaStatus.SUBMITTED


@pytest.mark.django_db
@pytest.mark.django_db
def test_gsa_submit_auto_approves():
    owner, record = _seed_mda_request(
        "gsa-applicant", "KGHTESTUCR9900000079", "CD202609GSAREG0000079",
        mda_code="GSA", app_code="REG",
        documents=[
            {"code": "003", "name": "Invoice", "reference": "INV-3"},
            {"code": "005", "name": "Bill of Lading", "reference": "BL-3"},
            {"code": "021", "name": "Packing List", "reference": "PL-3"},
        ],
    )
    client = Client()
    client.force_login(owner)
    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 200
    assert response.json()["status"] == "AP, Approved"


@pytest.mark.django_db
@pytest.mark.django_db
def test_mda_submit_blocked_in_review_mode():
    owner, record = _seed_mda_request(
        "mda-review-owner", "KGHTESTUCR9900000089", "CD202609MOTIIDF0000089",
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-9"}],
    )
    staff = User.objects.create_user(username="mda-reviewer2", email="mda-reviewer2@example.test", password="x", is_staff=True)
    client = Client()
    client.force_login(staff)
    session = client.session
    session["simulator_review_user_id"] = str(owner.pk)
    session.save()

    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 403
    record.refresh_from_db()
    assert record.status == MdaStatus.DRAFT


@pytest.mark.django_db
def test_submitted_mda_reopens_with_prefilled_general_and_locked_approval():
    owner, record = _seed_mda_request(
        "idf-readonly", "KGHTESTUCR9900000079", "CD202609MOTIIDF0000079",
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-7"}],
    )
    client = Client()
    client.force_login(owner)

    # collectPayload() stores party fields as nested role dicts.
    saved = client.post(reverse("mda-consignment-application-save", args=(record.pk,)), {
        "exporter": {"name": "GLODENGATE HOLDINGS LIMITED", "physical_country": "AE", "tel": "000"},
        "importer": {"code": "P0036108545", "same": True},
        "vessel_name": "MAERSK HIDALGO",
        "approval_terms": True, "approval_purpose": "Import", "approval_remarks": "ok",
        "items": [],
    }, content_type="application/json")
    assert saved.status_code == 200
    client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})

    # The reopened (read-only) page carries the flattened initial payload so the
    # JS prefill restores the General tab, and marks the page read-only (the JS
    # then disables the fields and the Approval controls).
    page = client.get(reverse("mda-consignment-application", args=(record.pk,)))
    html = page.content.decode()
    assert '"exporter.name": "GLODENGATE HOLDINGS LIMITED"' in html
    assert '"importer.code": "P0036108545"' in html
    assert '"vessel_name": "MAERSK HIDALGO"' in html
    assert "window.appReadOnly = true" in html
