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
        temp_no="TEMPUCR" + ucr_no[-7:],
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

    # A second draft BOE (different UCR/IDF) is created without a number clash.
    idf_two = _make_idf(staff, "KGHTESTUCR9900000029", idf_no="CD202609MOTIIDF0000029")
    second = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf_two.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json")
    assert second.status_code == 200
    second_declaration = BoeDeclaration.objects.get(job_no=second.json()["job_no"])
    assert second_declaration.declaration_no == ""


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


@pytest.mark.django_db
def test_search_boe_lists_drafts_and_submitted(client):
    from django.test import Client

    staff = User.objects.create_user(username="boe-searcher", email="boe-searcher@example.test", password="x", is_staff=True)
    client.force_login(staff)
    idf = _make_idf(staff, "KGHTESTUCR9900000039")
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    search_url = reverse("search-boe-declaration")
    page_url = reverse("boe-declaration", args=(declaration.pk,))

    # The draft is listed without any search criteria.
    page = client.get(search_url)
    assert page.status_code == 200
    assert created["job_no"].encode() in page.content
    assert b"DR - Draft" in page.content

    # Draft tab set: General through Tax; no Bill of Tax, no Customs Response.
    draft_page = client.get(page_url)
    assert b'id="general-user-reference"' in draft_page.content
    assert b'value="importer"' in draft_page.content
    assert b'data-boe-tab="bill"' not in draft_page.content
    assert b"Customs Response" not in draft_page.content

    # The General tab saves the editable draft fields (user reference, taxpayer).
    saved = client.post(reverse("boe-save-draft", args=(declaration.pk,)), {
        "user_reference": "DUTY", "taxpayer": "declarant", "consignee_same": False,
    }, content_type="application/json")
    assert saved.status_code == 200
    declaration.refresh_from_db()
    assert declaration.form_data["user_reference"] == "DUTY"
    assert declaration.form_data["taxpayer"] == "declarant"

    # The saved user reference is found by exact match only.
    exact = client.get(search_url, {"user_reference": "DUTY"})
    assert created["job_no"].encode() in exact.content
    partial = client.get(search_url, {"user_reference": "DUT"})
    assert created["job_no"].encode() not in partial.content

    # Submission generates the BoE number and opens the customs response stages.
    client.post(reverse("boe-submit", args=(declaration.pk,)))
    declaration.refresh_from_db()
    assert declaration.status == BoeDeclaration.Status.SUBMITTED
    assert declaration.declaration_no.startswith("BOE")
    page = client.get(search_url)
    assert declaration.declaration_no.encode() in page.content
    assert b"SU - Submitted" in page.content
    submitted_page = client.get(page_url)
    assert b"BOE Received" in submitted_page.content
    assert b'data-boe-tab="tax"' not in submitted_page.content
    assert b'id="general-user-reference"' not in submitted_page.content  # view mode

    # Staff in review mode see the reviewed student's BOEs.
    student = User.objects.create_user(username="boe-reviewee", email="boe-reviewee@example.test", password="x")
    student_idf = _make_idf(student, "KGHTESTUCR9900000049", idf_no="CD202609MOTIIDF0000049")
    student_boe = BoeDeclaration.objects.create(
        owner=student,
        idf=student_idf,
        ucr=student_idf.consignment_application.ucr,
        job_no="2609250003GCH000003",
        form_data={"fob_ncy": "10000", "items": []},
    )
    iclient = Client()
    iclient.force_login(staff)
    isession = iclient.session
    isession["simulator_review_user_id"] = str(student.pk)
    isession.save()
    review_page = iclient.get(search_url)
    assert student_boe.job_no.encode() in review_page.content

    # Filters narrow the results; another student's records stay private.
    filtered = client.get(search_url, {"boe": declaration.declaration_no})
    assert declaration.declaration_no.encode() in filtered.content
    empty = client.get(search_url, {"boe": "BOE999999"})
    assert b"No data found." in empty.content


@pytest.mark.django_db
def test_bl_awb_tab_edits_and_saves(client):
    from django.test import Client

    staff = User.objects.create_user(username="bl-awb-user", email="bl-awb-user@example.test", password="x", is_staff=True)
    client.force_login(staff)
    idf = _make_idf(staff, "KGHTESTUCR9900000059")
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    page_url = reverse("boe-declaration", args=(declaration.pk,))

    # Draft page renders the reference BL/AWB fields and container controls.
    draft_page = client.get(page_url)
    assert b'id="bl-manifest-no"' in draft_page.content
    assert b'id="bl-location-code"' in draft_page.content
    assert b'Container Indicator (G/F/L)' in draft_page.content
    assert b'container-add' in draft_page.content
    assert b"Number Of Containers Status" in draft_page.content
    # Item weights prefill the gross/net weight totals.
    assert b"200" in draft_page.content

    # Saving the BL/AWB section stores its fields and the container list.
    saved = client.post(reverse("boe-save-draft", args=(declaration.pk,)), {
        "section": "bl_awb",
        "fields": {
            "manifest_no": "MAN-001", "bl_awb_no": "DUTY",
            "customs_office": "TMA1, CEPS TEMA",
            "location_code": "WITMA1GVHE", "location_name": "GOLDEN JUBILEE VEHICLE",
            "vessel_name": "GOLDEN JUBILEE", "voyage_no": "V-9",
            "gross_weight": "126345", "net_weight": "26345",
            "package_unit": "PK", "package_count": "1",
            "consignment_country": "US, United States",
            "container_indicator": "F, F Indicator",
            "marks_numbers": "AS ADD",
        },
        "containers": [{"packing": "PK", "number": "CONT-1", "size": "40", "seal": "SEAL-1"}],
    }, content_type="application/json")
    assert saved.status_code == 200

    declaration.refresh_from_db()
    assert declaration.form_data["bl"]["bl_awb_no"] == "DUTY"
    assert declaration.form_data["bl"]["container_indicator"] == "F, F Indicator"
    assert declaration.form_data["containers"][0]["number"] == "CONT-1"

    # The rendered draft now reflects the saved values.
    rendered = client.get(page_url)
    assert b"CONT-1" in rendered.content
    assert b"F, F Indicator" in rendered.content
