import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from scenarios.models import (
    BoeDeclaration,
    ConsignmentApplication,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    MdaStatus,
    UcrDeclaration,
)

User = get_user_model()


def _seed_mda_request(owner_username="mda-submit-owner"):
    owner = User.objects.create_user(username=owner_username, email=f"{owner_username}@example.test", password="x", is_staff=True)
    moti = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "Ministry of Trade and Industry"})[0]
    idf_application = MdaApplication.objects.get_or_create(mda=moti, code="IDF", defaults={"name": "Import Duty Form"})[0]
    process = MdaProcess.objects.get_or_create(application=idf_application, code="NEW", defaults={"name": "New Application"})[0]
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no="TEMPUCR9900000059", ucr_no="KGHTESTUCR9900000059",
        status=UcrDeclaration.Status.SUBMITTED,
    )
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED,
    )
    record = MdaConsignmentRequest.objects.create(
        consignment_application=consignment,
        mda=moti, application=idf_application, process=process,
        consignment_type="SG", application_no="CD202609MOTIIDF0000088",
    )
    return owner, record


@pytest.mark.django_db
def test_mda_submit_sets_status_and_attaches_to_ucr_edocuments(client):
    owner, record = _seed_mda_request("mda-submit-owner")
    client.force_login(owner)

    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SU, Submitted"

    record.refresh_from_db()
    assert record.status == MdaStatus.SUBMITTED
    assert record.submitted_at is not None

    # The submitted MDA (with its code) appears in the UCR's eDocuments list.
    ucr_page = client.get(reverse("ucr-detail", args=(record.consignment_application.ucr.pk,)))
    assert record.application_no.encode() in ucr_page.content
    assert b"MOTI, Import Duty Form" in ucr_page.content

    # Resubmission stays available and re-stamps the submission.
    again = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert again.status_code == 200
    record.refresh_from_db()
    assert record.status == MdaStatus.SUBMITTED


@pytest.mark.django_db
def test_mda_submit_blocked_in_review_mode(client):
    owner, record = _seed_mda_request("mda-review-owner")
    staff = User.objects.create_user(username="mda-reviewer", email="mda-reviewer@example.test", password="x", is_staff=True)
    client.force_login(staff)
    session = client.session
    session["simulator_review_user_id"] = str(owner.pk)
    session.save()

    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})
    assert response.status_code == 403
    record.refresh_from_db()
    assert record.status == MdaStatus.DRAFT
