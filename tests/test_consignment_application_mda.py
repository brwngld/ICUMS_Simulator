"""Tests for the Consignment Application → Create Application page:
the New Consignment Request panel, the UCR-based create flow, and the
Copy Application flow that clones an existing MDA application's data."""
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


def _seed_world():
    """A learner with an issued UCR, a target MDA, and an existing IDF application to copy from."""
    owner = User.objects.create_user(username="consignment-mdas", email="consignment-mdas@example.test", password="x", is_staff=True)
    moti = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "Ministry of Trade and Industry"})[0]
    gsa = MdaAgency.objects.get_or_create(code="GSA", defaults={"name": "Ghana Standards Authority"})[0]
    idf_application = MdaApplication.objects.get_or_create(mda=moti, code="IDF", defaults={"name": "Import Duty Form"})[0]
    gsa_application = MdaApplication.objects.get_or_create(mda=gsa, code="GSA", defaults={"name": "Ghana Standards Authority Permit"})[0]
    MdaProcess.objects.get_or_create(application=idf_application, code="NEW", defaults={"name": "New Application"})
    MdaProcess.objects.get_or_create(application=gsa_application, code="REG", defaults={"name": "Product Registration"})
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no="TEMPUCR9900000299", ucr_no="KGHTESTUCR9900000299",
        status=UcrDeclaration.Status.SUBMITTED,
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-9"}],
    )
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED,
        application_no="CD202610MOTIIDF0000299",
    )
    source = MdaConsignmentRequest.objects.create(
        consignment_application=consignment, mda=moti, application=idf_application,
        process=MdaProcess.objects.filter(application=idf_application).first(),
        consignment_type="SG", application_no="CD202610MOTIIDF0000299",
        status=MdaStatus.APPROVED,
        form_data={"exporter.name": "EXPORT EXPERTS", "goods_description": "VEHICLE", "fob_fcy": "5000"},
    )
    return owner, source, gsa, gsa_application


@pytest.mark.django_db
def test_new_consignment_request_page_renders(client):
    owner, source, gsa, gsa_application = _seed_world()
    client.force_login(owner)
    page = client.get(reverse("single-window-create-consignment-application"))
    assert page.status_code == 200
    assert b"NEW CONSIGNMENT REQUEST" in page.content
    assert b'id="consignment-type"' in page.content
    assert b'id="consignment-mdas"' in page.content
    assert b'id="consignment-copy"' in page.content
    assert b"Copy Application" in page.content
    assert b"Create Application Form" in page.content


@pytest.mark.django_db
def test_create_application_form_builds_request_from_the_ucr(client):
    owner, source, gsa, gsa_application = _seed_world()
    client.force_login(owner)

    missing_ucr = client.post(reverse("consignment-application-mda-create"), {
        "consignment_type": "SG", "mda_id": source.mda_id,
    }, content_type="application/json")
    assert missing_ucr.status_code == 400
    assert b"issued UCR" in missing_ucr.content

    created = client.post(reverse("consignment-application-mda-create"), {
        "ucr_no": "KGHTESTUCR9900000299",
        "consignment_type": "SG",
        "mda_id": source.mda_id,
        "application_id": source.application_id,
        "process_id": source.process_id,
    }, content_type="application/json")
    assert created.status_code == 200
    assert created.json()["application_no"].startswith("PCD")

    record = MdaConsignmentRequest.objects.get(application_no=created.json()["application_no"])
    assert record.status == MdaStatus.DRAFT
    assert record.consignment_application.ucr.ucr_no == "KGHTESTUCR9900000299"
    # The request carries only the UCR's data (no copied source data).
    assert record.form_data.get("goods_description") == "VEHICLE"
    assert "fob_fcy" not in (record.form_data or {})

    # The target Consignment Document draft exists exactly once for the UCR.
    drafts = ConsignmentApplication.objects.filter(owner=owner, ucr=record.consignment_application.ucr, status=ConsignmentApplication.Status.DRAFT)
    assert drafts.count() == 1


@pytest.mark.django_db
def test_copy_application_clones_source_data_onto_the_selected_mda(client):
    owner, source, gsa, gsa_application = _seed_world()
    client.force_login(owner)

    # Unknown numbers are rejected.
    missing = client.post(reverse("consignment-application-copy"), {
        "source_no": "CD202610MOTIIDF9999999",
        "ucr_no": "KGHTESTUCR9900000299",
        "consignment_type": "SG",
        "mda_id": gsa.pk,
        "application_id": gsa_application.pk,
        "process_id": MdaProcess.objects.filter(application=gsa_application).first().pk,
    }, content_type="application/json")
    assert missing.status_code == 400
    assert b"No MDA application found with that number." in missing.content

    copied = client.post(reverse("consignment-application-copy"), {
        "source_no": source.application_no,
        "ucr_no": "KGHTESTUCR9900000299",
        "consignment_type": "SG",
        "mda_id": gsa.pk,
        "application_id": gsa_application.pk,
        "process_id": MdaProcess.objects.filter(application=gsa_application).first().pk,
    }, content_type="application/json")
    assert copied.status_code == 200

    record = MdaConsignmentRequest.objects.get(application_no=copied.json()["application_no"])
    assert record.mda_id == gsa.pk
    assert record.status == MdaStatus.DRAFT
    # The source's data was cloned onto the new request.
    assert (record.form_data or {}).get("exporter.name") == "EXPORT EXPERTS"
    assert (record.form_data or {}).get("fob_fcy") == "5000"
