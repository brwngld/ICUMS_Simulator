"""Uniform UCR form states: the submitted View page reuses the create form read-only,
and every eDocument row with a code carries a Reference No. (client and server side)."""
import re

import pytest
from django.urls import reverse

from accounts.models import User
from scenarios.models import UcrDeclaration

REFERENCE_RULE_MESSAGE = "Each eDocument needs a Reference No."

# Label targets cover every form field of the shared partial; both pages must offer the same set.
FORM_FIELD_IDS = [
    "ucr-temp", "ucr-regime", "ucr-show-provider", "ucr-declarant", "ucr-provider-country", "ucr-provider-code",
    "ucr-provider-address", "ucr-provider-contact", "ucr-provider-phone", "ucr-provider-email", "ucr-provider-email-2",
    "ucr-exporter-identity", "ucr-exporter-country", "ucr-exporter-address", "ucr-exporter-phone", "ucr-exporter-fax",
    "ucr-exporter-contact", "ucr-exporter-contact-no", "ucr-exporter-designation",
    "ucr-importer-identity", "ucr-importer-country", "ucr-importer-address", "ucr-importer-phone", "ucr-importer-fax",
    "ucr-importer-contact", "ucr-importer-contact-no", "ucr-importer-designation",
    "ucr-goods", "ucr-origin", "ucr-destination", "ucr-mode", "ucr-reference", "ucr-email",
]


def _ucr_payload(**overrides):
    payload = {
        "regime": "EX",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "PRINCEKING LOGISTICS COMPANY LIMITED",
            "country": "GH", "address": "P.O. BOX PMB, ACCRA", "contact": "Prince King",
            "phone": "+233200000000", "email": "princeking@example.test", "email_2": "",
        },
        "exporter": {
            "identity": "C0012345678", "name": "Fictional Exporter Ltd", "country": "GH",
            "address": "Fictional exporter address", "phone": "+233201111111", "fax": "",
            "contact": "Export Contact", "contact_no": "+233201111112", "designation": "Export Manager",
        },
        "importer": {
            "identity": "", "name": "Fictional Importer Ltd", "country": "CN",
            "address": "Fictional importer address", "phone": "+8610000000000", "fax": "",
            "contact": "Import Contact", "contact_no": "+8610000000001", "designation": "Import Manager",
        },
        "consignment": {
            "goods": "Fictional training goods", "origin": "GH", "destination": "CN",
            "mode": "10, Sea Transport", "reference": "REF-001", "email": "",
        },
        "documents": [{"code": "003", "name": "Invoice", "reference": "INV-001"}],
    }
    payload.update(overrides)
    return payload


def _label_targets(content):
    return set(re.findall(r'for="(ucr-[a-z0-9-]+)"', content.decode()))


def _submitted_ucr(client):
    user = User.objects.create_user(username="ucr-uniform", password="test-pass", is_staff=True)
    client.force_login(user)
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    client.post(reverse("ucr-submit"), {**_ucr_payload(), "draft_id": draft_id}, content_type="application/json")
    return user, UcrDeclaration.objects.get(owner=user)


@pytest.mark.django_db
def test_submitted_ucr_renders_the_create_form_read_only(client):
    _, record = _submitted_ucr(client)
    create_page = client.get(reverse("single-window-create-ucr"))
    assert create_page.status_code == 200
    detail = client.get(reverse("ucr-detail", args=[record.pk]))
    assert detail.status_code == 200
    content = detail.content

    # Same form layout: every create-page field label (and therefore field) exists on the view page too.
    create_targets = _label_targets(create_page.content)
    detail_targets = _label_targets(content)
    assert {field_id for field_id in FORM_FIELD_IDS} <= create_targets
    # Same form as the edited view, minus the create-only provider toggle.
    assert create_targets - {"ucr-show-provider"} == detail_targets

    # Read-only state: same controls, readonly inputs, disabled select, no edit actions.
    assert b'id="ucr-goods" rows="3" readonly' in content
    assert b'id="ucr-temp" value="' in content
    # Per the reference, the submitted view carries no status text or badge and
    # omits the Display-Service-Provider toggle.
    assert b"view-mode-badge" not in content
    assert b"ucr-show-provider" not in content
    assert b"view-mode" in content  # panel class hides the required-asterisk spans
    assert b'id="add-document"' not in content
    assert b'id="ucr-save"' not in content and b'id="ucr-submit"' not in content
    assert b'<option value="EX" selected>' in content
    assert b">TIN <span>*</span></label>" in content  # EX regime: exporter identified by TIN
    assert b'value="C0012345678"' in content and b'value="Fictional Exporter Ltd"' in content
    assert b'value="GH"' in content and b'value="Ghana"' in content  # code + name inputs stay separate
    assert b"Fictional training goods" in content
    assert b'data-document-code value="003" readonly' in content
    assert b'value="INV-001" readonly' in content
    assert record.ucr_no.encode() in content

    # The create page itself stays editable and has no view badge.
    create_content = create_page.content
    assert b'id="ucr-goods" rows="3">' in create_content
    assert b"view-mode-badge" not in create_content


@pytest.mark.django_db
def test_ucr_save_rejects_document_without_reference(client):
    user = User.objects.create_user(username="ucr-ref-guard", password="test-pass", is_staff=True)
    client.force_login(user)
    missing = _ucr_payload(documents=[{"code": "003", "name": "Invoice", "reference": ""}])
    response = client.post(reverse("ucr-save"), missing, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["errors"]["documents"] == REFERENCE_RULE_MESSAGE
    assert not UcrDeclaration.objects.filter(owner=user).exists()

    # Submit is blocked by the same rule and leaves the draft untouched.
    draft_id = client.post(reverse("ucr-save"), _ucr_payload(), content_type="application/json").json()["id"]
    blocked = client.post(reverse("ucr-submit"), {**missing, "draft_id": draft_id}, content_type="application/json")
    assert blocked.status_code == 400
    assert blocked.json()["errors"]["documents"] == REFERENCE_RULE_MESSAGE
    assert UcrDeclaration.objects.get(pk=draft_id).status == "draft"

    # A reference-only row (no code yet, e.g. waiting on its attachment) is still allowed.
    reference_only = _ucr_payload(documents=[{"code": "", "name": "", "reference": "PENDING-1"}])
    allowed = client.post(reverse("ucr-save"), reference_only, content_type="application/json")
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_ucr_save_persists_filled_document_references(client):
    user = User.objects.create_user(username="ucr-ref-ok", password="test-pass", is_staff=True)
    client.force_login(user)
    payload = _ucr_payload(documents=[
        {"code": "003", "name": "Invoice", "reference": "INV-77"},
        {"code": "005", "name": "Bill of Lading / Airwaybill", "reference": "  BL-2026  "},
    ])
    response = client.post(reverse("ucr-save"), payload, content_type="application/json")
    assert response.status_code == 200
    record = UcrDeclaration.objects.get(owner=user)
    assert record.documents[0]["reference"] == "INV-77"
    assert record.documents[1]["reference"] == "BL-2026"  # stripped, persisted

    submitted = client.post(reverse("ucr-submit"), {**payload, "draft_id": record.pk}, content_type="application/json")
    assert submitted.status_code == 200
    detail = client.get(reverse("ucr-detail", args=[record.pk]))
    assert b'value="BL-2026" readonly' in detail.content


@pytest.mark.django_db
def test_ucr_amend_rejects_new_document_without_reference(client):
    user = User.objects.create_user(username="ucr-amend-ref", password="test-pass", is_staff=True)
    client.force_login(user)
    source = UcrDeclaration.objects.create(
        owner=user, regime="IM", goods_description="Amend goods", origin_country="CN", destination_country="GH",
        transport_mode="40, Air Transport", documents=[{"code": "003", "name": "Invoice", "reference": "INV-1"}],
        temp_no="TEMPUCR2600000041", ucr_no="KGHTESTUCR2600000041", status="submitted",
    )
    response = client.post(reverse("ucr-amend", args=[source.pk]), {
        "regime": "FI",
        "new_documents": '[{"code": "005", "name": "Bill of Lading / Airwaybill", "reference": ""}]',
    })
    assert response.status_code == 302
    assert response.url == reverse("ucr-amend", args=[source.pk])
    source.refresh_from_db()
    assert source.regime == "IM"  # nothing was applied
    assert source.documents == [{"code": "003", "name": "Invoice", "reference": "INV-1"}]

    # The amend page renders the shared create-form layout with only regime + eDocuments editable.
    page = client.get(reverse("ucr-amend", args=[source.pk]))
    assert page.status_code == 200
    content = page.content
    assert _label_targets(page.content) == _label_targets(client.get(reverse("single-window-create-ucr")).content)
    assert b'id="ucr-regime" required name="regime" form="ucr-amend-form"' in content
    assert b'id="ucr-goods" rows="3" readonly' in content
    assert b'value="INV-1" readonly' in content
    assert b"data-existing-row" in content
    assert b'id="add-document"' in content
    assert b"Only the Regime Type and eDocuments Details can be changed" in content
    assert b"view-mode-badge" not in content  # amend is an editable flow, not view mode
