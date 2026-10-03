"""Tests for the BOE declaration Summary tab panel include template.

The panel is rendered standalone with the documented context contract; no DB
access is required, so no django_db marker is used.
"""
import types

from django.template.loader import render_to_string

TEMPLATE_NAME = "scenarios/boe_summary_panel.html"


def build_context(**overrides):
    """Build a context dict matching the Summary tab contract exactly."""
    declaration = types.SimpleNamespace(
        declaration_no="BOE-0001234",
        job_no="2610020010GCH001156",
        status="draft",
        status_code_display="DR, Draft",
        submitted_at=None,
        cpc="40001",
        zone="TMA1",
        regime="40, Import into home consumption (Direct Import)",
        ucr=types.SimpleNamespace(
            ucr_no="KGHCEPSUCR2600693625",
            transport_mode="10, Sea Transport",
        ),
        idf=types.SimpleNamespace(application_no="CD202609MOTIIDF0000001"),
    )
    context = {
        "declaration": declaration,
        "is_draft": True,
        "summary_header": {
            "job_no": "2610020010GCH001156",
            "regime": "40, Import into home consumption (Direct Import)",
            "boe_no": "1001234",
            "submission_date": "02/10/2026",
            "status": "DR, Draft",
            "processing_status": "",
            "manifest_no": "26MAE000229",
            "bl_awb_no": "275461345",
        },
        "user_tax_rows": [
            {"item_no": "1", "code": "IMP", "name": "Import Duty", "amount": "1,515.20"},
        ],
        "summary_items": [
            {
                "item_no": "0001",
                "hs_code": "4015190000",
                "cpc": "40001",
                "valuation_method": "Transaction Value",
                "gross_weight": "26,359.7450",
                "net_weight": "26,359.7450",
                "fob_fcy": "7,576.00",
                "freight_fcy": "0.00",
                "insurance_fcy": "0.00",
                "other_costs_fcy": "0.00",
                "customs_value_fcy": "7,576.00",
                "customs_value_ncy": "88,096.00",
            },
        ],
        "summary_item_totals": {
            "gross_weight": "26,359.7450",
            "net_weight": "26,359.7450",
            "fob_fcy": "7,576.00",
            "freight_fcy": "0.00",
            "insurance_fcy": "0.00",
            "other_costs_fcy": "0.00",
            "customs_value_fcy": "7,576.00",
            "customs_value_ncy": "88,096.00",
        },
        "general_values": {
            "job_no": "2610020010GCH001156",
            "boe_no": "1001234",
            "ucr_no": "KGHCEPSUCR2600693625",
            "regime": "40, Import into home consumption (Direct Import)",
            "customs_office": "TMA1, CEPS TEMA",
            "user_reference": "CO/KING",
            "doc_date": "02/10/2026",
            "expiry_date": "05/10/2026",
            "dec_date": "02/10/2026",
            "exporter_name": "GLODENGATE HOLDINGS LIMITED",
            "exporter_country": "AE, United Arab Emirates",
            "exporter_address": "1438, TAMANI ARTS OFFICE BUILDING BUSINESS BAY DUBAI",
            "importer_country": "GH, Ghana",
            "importer_address": "OBOOM ROAD BLOCK 31 Awutu Senya East CENTRAL KASOA GH",
            "consignee_address": "OBOOM ROAD BLOCK 31 Awutu Senya East CENTRAL KASOA GH",
            "taxpayer_code": "P0036108545, COSMIST ENTERPRISE",
            "declarant_tin": "C0064358704",
            "declarant_code": "CH001156",
            "declarant_name": "NISOV SHIPPING & LOGISTICS LTD",
            "declarant_address": "N/A",
        },
        "importer_code": "P0036108545",
        "importer_name": "COSMIST ENTERPRISE",
        "consignee_code": "P0036108545",
        "consignee_name": "COSMIST ENTERPRISE",
        "taxpayer": "importer",
        "bl_values": {
            "manifest_no": "26MAE000229",
            "bl_awb_no": "275461345",
            "manifest_date": "30/09/2026",
            "customs_area": "",
            "location_code": "WTTMA1MPS3",
            "location_name": "MERIDIAN PORT SERVICES LIMITED",
            "vessel_name": "MAERSK HIDALGO",
            "voyage_no": "593W",
            "manifest_freight": "",
            "nationality": "SG, Singapore",
            "port_of_loading": "THLCH, Laem Chabang",
            "place_of_landing": "GHTEM, Tema",
            "etd": "",
            "gross_weight": "26,359.75",
            "net_weight": "26,359.75",
            "package_unit": "CT",
            "package_count": "4,735",
            "volume": "71.025",
            "consignment_country": "TH, Thailand",
            "consignment_date": "",
            "container_indicator": "F, F Indicator",
            "risk_level": "",
            "marks_numbers": "AS ADD 1 X 40FT CONTAINER STC LATEX MEDICAL EXAM GLOVES",
            "containers_20": "",
            "containers_30": "1",
            "containers_cars": "",
            "container_category": "E, Etc",
        },
        "containers": [
            {"packing": "C, Container", "number": "TEMU7744442", "size": "45G1", "seal": "TH1330409"},
        ],
        "invoice_values": {
            "delivery_term": "CIF, COST, INSURANCE & FREIGHT",
            "country_of_delivery": "GH, Ghana",
            "delivery_place": "TEMA",
            "currency": "USD, US $",
            "exchange_rate": "11.6283",
            "fob_fcy": "7,576.00",
            "fob_ncy": "88,096.00",
            "freight_fcy": "0.00",
            "freight_ncy": "0.00",
            "insurance_fcy": "0.00",
            "insurance_ncy": "0.00",
            "other_fcy": "0.00",
            "other_ncy": "0.00",
            "invoice_fcy": "7,576.00",
            "invoice_ncy": "88,096.00",
        },
        "mode_of_payment_display": "07, Bank Draft",
        "system_documents": [
            {"code": "003", "name": "INVOICE", "requirement": "Y", "reference": "INVOICE"},
            {"code": "005", "name": "BILL OF LADING / AIRWAYBILL", "requirement": "Y", "reference": "BL"},
            {"code": "UCR", "name": "UCR(Unique Consgn. Ref.)", "requirement": "Y", "reference": "KGHCEPSUCR2600693625"},
        ],
        "user_documents": [
            {"code": "021", "name": "PACKING LIST", "requirement": "Y", "reference": "PKL"},
        ],
    }
    context.update(overrides)
    return context


def render(**overrides):
    return render_to_string(TEMPLATE_NAME, build_context(**overrides))


def test_summary_panel_renders_all_sections():
    html = render()
    for heading in (
        "Summary",
        "User Defined Tax Summary",
        "General",
        "Exporter",
        "Importer",
        "Consignee",
        "Declarant Code",
        "Taxpayer",
        "BL/AWB Details",
        "Container / Chassis List",
        "Invoice Details",
        "Additional Info.",
        "System Defined Attached Documents",
        "User Defined Attached Documents",
        "Item List",
    ):
        assert heading in html, f"missing section heading: {heading}"


def test_summary_panel_renders_contract_values():
    html = render()
    for value in (
        "2610020010GCH001156",  # job no
        "40, Import into home consumption (Direct Import)",  # regime
        "1001234",  # boe no
        "KGHCEPSUCR2600693625",  # ucr no
        "TMA1, CEPS TEMA",  # customs office
        "CO/KING",  # user reference
        "GLODENGATE HOLDINGS LIMITED",  # exporter
        "P0036108545",  # importer/consignee code
        "COSMIST ENTERPRISE",
        "C0064358704",  # declarant tin
        "CH001156",  # declarant code
        "26MAE000229",  # manifest no
        "275461345",  # bl/awb no
        "10, Sea Transport",  # transport mode from declaration.ucr
        "MAERSK HIDALGO",
        "TEMU7744442",  # container no
        "07, Bank Draft",  # mode of payment
        "88,096.00",  # customs value ncy
        "Transaction Value",  # valuation method
    ):
        assert value in html, f"missing expected value: {value}"


def test_summary_panel_view_tables_use_two_pairs_per_row():
    html = render()
    # 4-column label/value pairs in the Summary header block
    assert '<th>Job No.</th><td>2610020010GCH001156</td><th>Regime</th>' in html
    assert '<th>Manifest No.</th><td>26MAE000229</td><th>BL/AWB No.</th>' in html


def test_summary_panel_taxpayer_label_variants():
    assert "IM, Importer" in render()
    assert "CN, Consignee" in render(taxpayer="consignee")
    assert "CH, Declarant" in render(taxpayer="declarant")


def test_summary_panel_draft_shows_action_bars_and_add_button():
    html = render(is_draft=True)
    for button_id in (
        'id="summary-print"',
        'id="summary-back"',
        'id="summary-save-draft"',
        'id="summary-submit"',
        'id="summary-print-bottom"',
        'id="summary-back-bottom"',
        'id="summary-save-draft-bottom"',
        'id="summary-submit-bottom"',
    ):
        assert button_id in html, f"missing draft action button: {button_id}"
    assert "secondary-button" in html
    assert "Save as Draft" in html
    assert "Submit" in html
    # Add placeholder in the tax table header + red reminder note
    assert '<button class="ucr-row-action" type="button" disabled' in html
    assert ">Add</button>" in html
    assert "*Please ensure User Defined Taxes(if required) are inserted before submission" in html
    assert 'class="required-note"' in html


def test_summary_panel_non_draft_hides_draft_only_controls():
    html = render(is_draft=False)
    assert 'id="summary-print"' not in html
    assert 'id="summary-submit"' not in html
    assert "summary-print-bottom" not in html
    assert "*Please ensure User Defined Taxes" not in html
    assert ">Add</button>" not in html
    # Read-only content is still rendered
    assert "BL/AWB Details" in html
    assert "KGHCEPSUCR2600693625" in html


def test_summary_panel_empty_states():
    html = render(user_tax_rows=[], containers=[])
    assert "No Data." in html  # user defined tax summary empty row
    assert "No data found." in html  # container list empty row
    assert "TEMU7744442" not in html


def test_summary_panel_item_list_totals_and_pagination():
    html = render()
    assert "Item No." in html
    assert "Customs Value NCY" in html
    assert "<th colspan=\"4\">Total</th>" in html
    for total_value in (
        "26,359.7450",
        "7,576.00",
        "88,096.00",
    ):
        assert total_value in html
    assert "Total : 1" in html
    assert "Page : 1/1" in html


def test_summary_panel_document_tables_render():
    html = render()
    assert "BILL OF LADING / AIRWAYBILL" in html  # system documents
    assert "UCR(Unique Consgn. Ref.)" in html
    assert "PACKING LIST" in html  # user documents with counter numbering
    empty_html = render(user_documents=[])
    assert "No data found." in empty_html


# --- Page-level integration (summary include rendered inside the declaration page) ---

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scenarios.models import BoeDeclaration


@pytest.mark.django_db
def test_summary_tab_renders_inside_the_declaration_page(client):
    User = get_user_model()
    staff = User.objects.create_user(username="summary-page-user", email="summary-page-user@example.test", password="x", is_staff=True)
    client.force_login(staff)
    from tests.test_boe_declaration import _make_idf

    idf = _make_idf(staff, "KGHTESTUCR9900000089")
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    page_url = reverse("boe-declaration", args=(declaration.pk,))

    draft_page = client.get(page_url)
    assert b"User Defined Tax Summary" in draft_page.content
    assert b"System Defined Attached Documents" in draft_page.content
    assert b"User Defined Attached Documents" in draft_page.content
    assert b"BL/AWB Details" in draft_page.content
    assert b"Container / Chassis List" in draft_page.content
    assert b"Invoice Details" in draft_page.content
    assert b"No Data." in draft_page.content  # empty user tax summary
    assert b'id="summary-submit"' in draft_page.content
    assert b"*Please ensure User Defined Taxes(if required) are inserted before submission" in draft_page.content

    # Submission removes the draft-only summary controls and issues the BoE number.
    client.post(reverse("boe-submit", args=(declaration.pk,)))
    declaration.refresh_from_db()
    submitted_page = client.get(page_url)
    assert declaration.declaration_no.encode() in submitted_page.content
    assert b'id="summary-submit"' not in submitted_page.content
    assert b"*Please ensure User Defined Taxes" not in submitted_page.content
