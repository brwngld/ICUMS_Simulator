import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scenarios.models import BoeDeclaration, BoeStageEvent, ConsignmentApplication, MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, UcrDeclaration

User = get_user_model()


@pytest.mark.django_db
def _make_idf(owner, ucr_no, idf_no="CD202609MOTIIDF0000001"):
    moti = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "Ministry of Trade and Industry"})[0]
    idf_application = MdaApplication.objects.get_or_create(mda=moti, code="IDF", defaults={"name": "Import Duty Form"})[0]
    MdaProcess.objects.get_or_create(application=idf_application, code="NEW", defaults={"name": "New Application"})
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        ucr_no=ucr_no, status=UcrDeclaration.Status.SUBMITTED,
    )
    from onboarding.models import Enrolment, Programme, ProgrammeVersion

    programme = Programme.objects.create(name=f"P-{ucr_no}", code=f"p-{ucr_no}")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    enrolment = Enrolment.objects.create(student=owner, programme_version=version, enrolled_by=owner)
    consignment = ConsignmentApplication.objects.create(
        owner=owner,
        ucr=ucr,
        application_no=f"CD-{ucr_no}",
        status=ConsignmentApplication.Status.SUBMITTED,
        currency="JPY",
        exchange_rate=0.0696,
        fob_fcy=1534800.00,
        fob_ncy=106822.08,
        freight_ncy=11583.70,
        exporter_name="TRANSGLOBAL, Exporter",
        importer_code="C0000000003, Cedar Simulator Logistics Ltd",
        items=[{"hs_code": "8703240000", "description": "MOTOR CAR", "quantity": "1"}],
    )
    enrolment.delete()  # only the consignment linkage is needed for this test
    return MdaConsignmentRequest.objects.create(
        consignment_application=consignment,
        mda=moti,
        application=idf_application,
        process=MdaProcess.objects.filter(application=idf_application).first(),
        consignment_type="SG",
        application_no=idf_no,
    )


@pytest.mark.django_db
def test_idf_lookup_validates_and_shows_attached_ucr(client):
    staff = User.objects.create_user(username="idf-declarant", email="idf-declarant@example.test", password="x", is_staff=True)
    client.force_login(staff)
    _make_idf(staff, "KGHTESTUCR9900000009")

    missing = client.get(reverse("boe-idf-lookup"), {"number": "CD202609MOTIIDF9999999"})
    assert missing.json()["valid"] is False

    found = client.get(reverse("boe-idf-lookup"), {"number": "cd202609motiidf0000001"})
    assert found.json()["valid"] is True
    assert found.json()["ucr_no"] == "KGHTESTUCR9900000009"


@pytest.mark.django_db
def test_boe_create_enforces_single_ucr_use(client):
    staff = User.objects.create_user(username="idf-declarant2", email="idf-declarant2@example.test", password="x", is_staff=True)
    client.force_login(staff)
    idf = _make_idf(staff, "KGHTESTUCR9900000019")

    # Only the IDF reuse document is available in this training step.
    blocked = client.post(reverse("boe-create"), {"reuse": "NONE"}, content_type="application/json")
    assert blocked.status_code == 400

    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json")
    assert created.status_code == 200
    job_no = created.json()["job_no"]
    assert "GCH" in job_no  # job numbers are allocated at creation

    declaration = BoeDeclaration.objects.get(job_no=job_no)
    assert declaration.ucr.ucr_no == "KGHTESTUCR9900000019"
    assert declaration.status == "draft"
    assert declaration.declaration_no == ""  # the BoE number only exists after submission

    # The same UCR can never be declared twice.
    again = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json")
    assert again.status_code == 400
    assert "already been used" in again.json()["error"]


@pytest.mark.django_db
def test_boe_tabs_follow_the_declaration_status(client):
    staff = User.objects.create_user(username="idf-declarant3", email="idf-declarant3@example.test", password="x", is_staff=True)
    client.force_login(staff)
    idf = _make_idf(staff, "KGHTESTUCR9900000029")
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    page_url = reverse("boe-declaration", args=(declaration.pk,))

    # Draft: the Tax tab is present; Customs Response is not.
    draft = client.get(page_url)
    assert b'data-boe-tab="tax"' in draft.content
    assert b"Customs Response" not in draft.content

    # Submission generates the BoE number and opens the customs response stages.
    client.post(reverse("boe-submit", args=(declaration.pk,)))
    submitted = client.get(page_url)
    assert b"BOE Received" in submitted.content
    assert b'data-boe-tab="tax"' not in submitted.content
    refreshed = BoeDeclaration.objects.get(pk=declaration.pk)
    assert refreshed.status == "submitted"
    assert refreshed.declaration_no.startswith("BOE")

    # The system assesses once the officers register the Assessment stage.
    declaration = BoeDeclaration.objects.get(pk=declaration.pk)
    BoeStageEvent.objects.create(declaration=declaration, name="Assessment")
    refreshed = BoeDeclaration.objects.get(pk=declaration.pk)
    assert refreshed.status == BoeDeclaration.Status.ASSESSED
    assert refreshed.assessment_total is not None
    assessed_page = client.get(page_url)
    assert b">Assessment<" in assessed_page.content

    # Bill of Tax stays empty until accepted, then fills with the assessment.
    accepted = client.get(page_url)
    assert b"becomes available once the assessment has been accepted" in accepted.content
    refreshed.status = BoeDeclaration.Status.ACCEPTED
    refreshed.save(update_fields=("status",))
    accepted_page = client.get(page_url)
    assert b"becomes available once" not in accepted_page.content
    assert refreshed.assessment_total.__str__().encode() in accepted_page.content or str(refreshed.assessment_total).encode() in accepted_page.content
