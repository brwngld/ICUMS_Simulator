"""Submitted MDA pages must render the SAME form as the editable pages.

The read-only mode keeps every form field in the DOM (inputs/textareas become
readonly, selects/checkboxes/buttons stay disabled) and shows a "View mode"
badge, so the submitted state looks uniform with the editable state instead of
a greyed-out form.
"""
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
    UcrDeclaration,
)

User = get_user_model()

# Form field markers that must be present on BOTH the editable (draft) and the
# submitted (read-only) render — the view-mode page keeps the full form layout.
SHARED_FIELD_MARKERS = [
    'data-app-field="reference_info"',
    'data-app-field="vessel_name"',
    'data-app-field="marks_numbers"',
    'data-app-field="means_of_transport"',
    'data-app-field="delivery_term"',
    'data-app-field="fob_fcy"',
    'data-app-field="exporter.name"',
    'data-app-field="consignor.name"',
    'data-app-field="importer.code"',
    'data-app-field="consignee.code"',
    'data-app-field="customs_value_ncy"',
    'data-item-field="hs_code"',
    'data-item-field="description"',
]


def _seed_mda_request(owner_username, ucr_no, idf_no):
    owner = User.objects.create_user(username=owner_username, email=f"{owner_username}@example.test", password="x", is_staff=True)
    agency = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "MOTI Authority"})[0]
    application = MdaApplication.objects.get_or_create(mda=agency, code="IDF", defaults={"name": "IDF Application"})[0]
    process = MdaProcess.objects.get_or_create(application=application, code="NEW", defaults={"name": "New Application"})[0]
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no="TEMPUCR" + ucr_no[-7:], ucr_no=ucr_no,
        status=UcrDeclaration.Status.SUBMITTED,
        documents=[{"code": "003", "name": "Invoice", "reference": "INV-UNIFORM"}],
    )
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED,
    )
    record = MdaConsignmentRequest.objects.create(
        consignment_application=consignment,
        owner=owner,
        mda=agency, application=application, process=process,
        consignment_type="SG", application_no=idf_no,
    )
    return owner, record


@pytest.mark.django_db
def test_submitted_mda_renders_uniform_form_with_view_mode_badge():
    owner, record = _seed_mda_request("uniform-submitted", "KGHTESTUCR9900000109", "CD202609MOTIIDF0000109")
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

    page = client.get(reverse("mda-consignment-application", args=(record.pk,)))
    html = page.content.decode()
    assert "window.appReadOnly = true" in html
    assert 'class="view-mode-badge"' in html
    assert "View mode" in html
    assert "application-form.js?v=20261010-1" in html
    for marker in SHARED_FIELD_MARKERS:
        assert marker in html


@pytest.mark.django_db
def test_draft_mda_renders_same_fields_without_view_mode_badge():
    owner, record = _seed_mda_request("uniform-draft", "KGHTESTUCR9900000119", "CD202609MOTIIDF0000119")
    client = Client()
    client.force_login(owner)

    page = client.get(reverse("mda-consignment-application", args=(record.pk,)))
    html = page.content.decode()
    assert "window.appReadOnly = false" in html
    assert "view-mode-badge" not in html
    for marker in SHARED_FIELD_MARKERS:
        assert marker in html
