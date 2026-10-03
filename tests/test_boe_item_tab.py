"""Tests for the BOE declaration Item tab: item list, per-item detail, annexed documents."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scenarios.models import BoeDeclaration
from tests.test_boe_declaration import _make_idf

User = get_user_model()


@pytest.mark.django_db
def _make_draft_boe(client, ucr_no, username="item-tab-user"):
    """Create a staff declarant plus a draft BOE seeded from an IDF consignment."""
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x", is_staff=True)
    client.force_login(user)
    idf = _make_idf(user, ucr_no)
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "40001", "zone": "GEN",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    return user, declaration


def _draft_save_url(declaration):
    return reverse("boe-save-draft", args=(declaration.pk,))


def _page_url(declaration):
    return reverse("boe-declaration", args=(declaration.pk,))


@pytest.mark.django_db
def test_item_tab_renders_seeded_list_and_actions(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000001", username="item-list-user")
    page = client.get(_page_url(declaration))
    content = page.content

    # The Item tab button and panel are in the DOM (panel content is hidden but present).
    assert b'data-boe-tab="item"' in content
    assert b"Item List" in content
    assert b'id="item-list-table"' in content

    # The consignment item seeded from the IDF/MDA is listed with its HS code.
    assert b"8703240000" in content
    assert b"data-item-detail=\"0\"" in content
    assert b"Annexed Document" in content

    # Draft action buttons: Add, Duplicate, Excel Upload (disabled), Delete, Update Valuation Method.
    assert b"Add Item" in content
    assert b"Duplicate Item" in content
    assert b"Excel upload is not part of this training step" in content
    assert b"Delete Item" in content
    assert b"Update Valuation Method" in content
    assert b"1. Transaction Value" in content
    assert b"6. Fall-back Value" in content
    assert b'id="item-valuation-select"' in content

    # The HS code calls for a DVLA permit: it shows as a System Defined Annexed Document.
    assert b"DVLA VEHICLE APPROVAL" in content
    assert b"System Defined Annexed Document" in content
    assert b"User Defined Annexed Document" in content


@pytest.mark.django_db
def test_items_bulk_add_duplicate_valuation_and_delete_persist(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000002", username="item-bulk-user")
    url = _draft_save_url(declaration)

    added = client.post(url, {"section": "items_bulk", "action": "add", "index": 0}, content_type="application/json")
    assert added.status_code == 200
    declaration.refresh_from_db()
    items = declaration.form_data["items"]
    assert len(items) == 2
    assert items[1]["hs_code"] == ""  # a blank item ready for the detail form

    duplicated = client.post(url, {"section": "items_bulk", "action": "duplicate", "index": 0}, content_type="application/json")
    assert duplicated.status_code == 200
    declaration.refresh_from_db()
    items = declaration.form_data["items"]
    assert len(items) == 3
    assert items[2]["hs_code"] == "8703240000"  # clone of the seeded item
    assert items[2]["description"] == "MOTOR CAR"

    valuated = client.post(url, {
        "section": "items_bulk", "action": "valuation",
        "indices": [1, 2], "valuation_method": "4. Deductive Value",
    }, content_type="application/json")
    assert valuated.status_code == 200
    declaration.refresh_from_db()
    items = declaration.form_data["items"]
    assert items[1]["valuation_method"] == "4. Deductive Value"
    assert items[2]["valuation_method"] == "4. Deductive Value"

    deleted = client.post(url, {"section": "items_bulk", "action": "delete", "indices": [0, 1]}, content_type="application/json")
    assert deleted.status_code == 200
    declaration.refresh_from_db()
    items = declaration.form_data["items"]
    assert len(items) == 1
    assert items[0]["hs_code"] == "8703240000"
    assert items[0]["item_no"] == "0001"  # item numbers are renumbered after deletion

    # The trimmed list renders with the updated valuation method.
    page = client.get(_page_url(declaration))
    assert b"Deductive Value" in page.content


@pytest.mark.django_db
def test_item_section_save_persists_fields_and_numbers(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000003", username="item-save-user")
    url = _draft_save_url(declaration)

    saved = client.post(url, {
        "section": "item", "index": 0,
        "fields": {
            "hs_code": "8703240000",
            "description": "MOTOR CAR 2.0 PETROL",
            "cpc": "40001",
            "state_of_goods": "01, NEW",
            "zone": "GEN",
            "country_of_origin": "JP",
            "package_unit": "PK",
            "package_quantity": "2",
            "gross_weight": "1,500.500",
            "net_weight": "1,400.250",
            "item_quantity": "2",
            "item_quantity_unit": "KGM",
            "unit_fob_fcy": "100",
            "fob_fcy": "200",
            "freight_fcy": "10",
            "insurance_fcy": "5",
            "other_costs_fcy": "1",
            "valuation_method": "1. Transaction Value",
            "vehicle_indicator": "N",
        },
    }, content_type="application/json")
    assert saved.status_code == 200

    declaration.refresh_from_db()
    item = declaration.form_data["items"][0]
    assert item["item_no"] == "0001"  # zero-padded item number assigned on first save
    assert item["cpc"] == "40001"
    assert item["zone"] == "GEN"
    assert item["valuation_method"] == "1. Transaction Value"
    assert item["gross_weight"] == "1500.500"  # thousands separators stripped by the numeric tolerance
    assert item["quantity"] == "1"  # seeded consignment keys are preserved
    # Customs value is recomputed server-side from the value components.
    assert item["customs_value_fcy"] == "216.00"
    assert item["customs_value_ncy"] == "0.00"

    # The rendered draft shows the saved values in the item detail form.
    page = client.get(_page_url(declaration))
    assert b'id="item-0-cpc"' in page.content
    assert b'value="40001"' in page.content
    assert b'value="0001"' in page.content
    assert b"MOTOR CAR 2.0 PETROL" in page.content


@pytest.mark.django_db
def test_item_taxes_save_persists_and_aggregates(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000004", username="item-tax-user")
    url = _draft_save_url(declaration)

    saved = client.post(url, {
        "section": "item_taxes", "index": 0,
        "taxes": [{"code": "IMP", "name": "Import Duty", "amount": "1,515.20"}],
    }, content_type="application/json")
    assert saved.status_code == 200

    declaration.refresh_from_db()
    assert declaration.form_data["items"][0]["user_taxes"] == [
        {"code": "IMP", "name": "Import Duty", "amount": "1,515.20"},
    ]

    page = client.get(_page_url(declaration))
    # The tax row renders in the item detail User Defined Tax Item table...
    assert b"Import Duty" in page.content
    assert b'value="1,515.20"' in page.content
    # ...and is aggregated for the Summary tab contract.
    assert page.context["user_tax_rows"] == [
        {"item_no": "0001", "code": "IMP", "name": "Import Duty", "amount": "1,515.20"},
    ]

    # Summary contract additions carried on the same response.
    assert page.context["summary_header"]["job_no"] == declaration.job_no
    assert page.context["summary_items"][0]["item_no"] == "0001"
    assert page.context["summary_item_totals"]["fob_fcy"] == page.context["summary_items"][0]["fob_fcy"]


@pytest.mark.django_db
def test_item_annexed_save_renders_manual_rows_and_hs_rule(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000005", username="item-annex-user")
    url = _draft_save_url(declaration)

    saved = client.post(url, {
        "section": "item_annexed", "index": 0,
        "rows": [{"code": "", "description": "PORT HEALTH CLEARANCE", "requirement": "Y", "reference": "PH-2026-001"}],
    }, content_type="application/json")
    assert saved.status_code == 200

    declaration.refresh_from_db()
    assert declaration.form_data["items"][0]["annexed_manual"] == [
        {"code": "", "description": "PORT HEALTH CLEARANCE", "requirement": "Y", "reference": "PH-2026-001"},
    ]

    page = client.get(_page_url(declaration))
    assert b"PORT HEALTH CLEARANCE" in page.content
    assert b'class="annexed-manual-row"' in page.content
    # HS 8703... calls for a DVLA permit: system defined, not user defined.
    assert b"DVLA VEHICLE APPROVAL" in page.content
    assert b"System Defined Annexed Document" in page.content
    assert b"User Defined Annexed Document" in page.content


@pytest.mark.django_db
def test_submitted_declaration_item_tab_readonly(client):
    user, declaration = _make_draft_boe(client, "KGHTESTUCR9901000006", username="item-readonly-user")
    client.post(reverse("boe-submit", args=(declaration.pk,)))

    page = client.get(_page_url(declaration))
    content = page.content
    assert b'data-boe-tab="item"' in content
    assert b"8703240000" in content  # the item list still renders, read-only
    # No draft editing controls survive submission.
    assert b"Add Item" not in content
    assert b'class="item-row-check"' not in content
    assert b'id="item-add"' not in content
    assert b"Save Item" not in content
    assert b"Save Annexed Docs" not in content
    assert b">Excel Upload</button>" not in content
    assert b"data-item-detail=" not in content
