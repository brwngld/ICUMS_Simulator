"""Tests for the BOE declaration Tax tab: the compute_tax_preview service and the panel include.

Service tests seed the GhanaHSCode tariff and mirror the reference declaration
(customs value NCY 88,096.00 / FCY 7,576.00, one item HS 4015190000, import duty
20%, VAT 0%, NHIL 0%).  The panel include is rendered standalone with the
documented context contract, following tests/test_boe_summary_tab.py.

Formatting contract: every money value the service returns is a string WITH
thousands separators (e.g. "17,619.20"); rates use four decimals ("20.0000").

Known product-owner gap (do not "fix" here): the GHS Disinfection Fee (code 63)
basis is not reproduced, so it stays "0.00".  The reference screenshot's grand
total (23,441.71) includes 581.42 for that fee; this service therefore totals
22,860.29 (item subtotal 22,843.29 is unaffected).
"""
import types

import pytest
from django.template.loader import render_to_string

from assessment.service import TAX_CATALOG, compute_tax_preview
from scenarios.models import GhanaHSCode

TEMPLATE_NAME = "scenarios/boe_tax_panel.html"
REFERENCE_HS = "4015190000"

EXPECTED_DECLARATION_PAYABLE = {
    "01": "17,619.20",
    "02": "0.00",
    "05": "0.00",
    "06": "440.48",
    "32": "352.38",
    "33": "52.86",
    "45": "12.00",
    "47": "0.00",
    "48": "8.81",
    "56": "880.96",
    "63": "0.00",  # GHS Disinfection Fee — basis unknown, stays 0.00 by design
    "72": "5.00",
    "78": "1,761.92",
    "87": "660.72",
    "88": "0.00",
    "89": "8.81",
    "93": "880.96",
    "98": "176.19",
}

EXPECTED_CATALOG_CODES = ["01", "02", "05", "06", "32", "33", "45", "47", "48", "56", "63", "72", "78", "87", "88", "89", "93", "98"]
EXPECTED_ITEM_CODES = ["01", "02", "05", "06", "32", "33", "47", "48", "56", "78", "87", "88", "89", "93", "98"]


def reference_form_data():
    return {
        "cpc": "40D01",
        "fob_fcy": "7576.00",
        "fob_ncy": "88096.00",
        "freight_ncy": "0.00",
        "insurance_ncy": "0.00",
        "customs_value_fcy": "7576.00",
        "customs_value_ncy": "88096.00",
        "items": [{
            "item_no": "0001",
            "hs_code": REFERENCE_HS,
            "cpc": "40D01",
            "fob_ncy": "88096.00",
            "customs_value_ncy": "88096.00",
        }],
    }


@pytest.fixture
def tariff(db):
    # Migration 0033 seeds the real tariff into every test database, so the
    # reference row may already exist; force the reference rates either way.
    tariff = GhanaHSCode.objects.get_or_create(
        code=REFERENCE_HS,
        defaults={"description": "Medical examination gloves", "import_duty": "20", "import_vat": "0", "import_excise": "0", "nhil_rate": "0"},
    )[0]
    tariff.import_duty = "20"
    tariff.import_vat = "0"
    tariff.import_excise = "0"
    tariff.nhil_rate = "0"
    tariff.save()
    return tariff


def preview():
    return compute_tax_preview(reference_form_data())


# --- Service: declaration-level catalog -------------------------------------


@pytest.mark.django_db
def test_tax_preview_catalog_has_all_18_rows_ordered_by_code(tariff):
    rows = preview()["declaration_rows"]
    assert [row["code"] for row in rows] == EXPECTED_CATALOG_CODES
    assert [row["code"] for row in TAX_CATALOG] == EXPECTED_CATALOG_CODES
    for row in rows:
        assert row["user_defined"] == "N"
        assert row["exempted"] == "0.00"
        assert row["suspended"] == "0.00"
    names = {row["code"]: row["name"] for row in rows}
    assert names["45"] == "Ghana Shippers Authority SNF Fee"
    assert names["63"] == "GHS Disinfection Fee"
    assert names["87"] == "Ghana Export-Import Bank (EXIM) Levy"


@pytest.mark.django_db
def test_tax_preview_declaration_payable_matches_reference(tariff):
    rows = preview()["declaration_rows"]
    payable = {row["code"]: row["payable"] for row in rows}
    assert payable == EXPECTED_DECLARATION_PAYABLE


@pytest.mark.django_db
def test_tax_preview_totals_and_item_subtotal(tariff):
    result = preview()
    # 22,860.29 = item subtotal 22,843.29 + SNF 12.00 + MoTI 5.00 (63 stays 0.00).
    assert result["totals"]["tax"] == "22,860.29"
    assert result["totals"]["payable"] == "22,860.29"
    assert result["totals"]["exempted"] == "0.00"
    assert result["totals"]["guarantee"] == "0.00"
    assert result["item_total"] == "22,843.29"
    total_of_rows = sum(int(row["payable"].replace(",", "").replace(".", "")) for row in result["declaration_rows"])
    assert total_of_rows == 2286029  # rows add up exactly to the displayed total


@pytest.mark.django_db
def test_tax_preview_customs_value_block(tariff):
    assert preview()["customs_value"] == {"fcy": "7,576.00", "ncy": "88,096.00"}


# --- Service: per-item breakdown --------------------------------------------


@pytest.mark.django_db
def test_tax_preview_item_summary_row(tariff):
    items = preview()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["index"] == 0
    assert item["item_no"] == "0001"
    assert item["hs_code"] == REFERENCE_HS
    assert item["cpc"] == "40D01"
    assert item["fob_ncy"] == "88,096.00"
    assert item["customs_value_ncy"] == "88,096.00"
    assert item["exempted"] == "0.00"
    assert item["suspended"] == "0.00"
    assert item["payable"] == "22,843.29"


@pytest.mark.django_db
def test_tax_preview_item_rows_replicate_reference_detail(tariff):
    # The reference shows all 15 item-level rows, including zero-rate ones
    # (02/05/47/88); the three flat declaration fees (45/63/72) are excluded.
    rows = preview()["items"][0]["rows"]
    assert [row["code"] for row in rows] == EXPECTED_ITEM_CODES
    by_code = {row["code"]: row for row in rows}
    assert by_code["01"] == {
        "code": "01", "name": "Import Duty", "base": "88,096.00", "tbc": "24",
        "rate": "20.0000", "exempted": "0.00", "suspended": "0.00", "payable": "17,619.20",
    }
    assert by_code["02"]["base"] == "105,715.20"  # CV + import duty
    assert by_code["02"]["tbc"] == "31"
    assert by_code["02"]["rate"] == "0.0000"
    assert by_code["32"]["tbc"] == "25"
    assert by_code["33"]["base"] == "352.38"  # the Network Charge amount
    assert by_code["33"]["tbc"] == "52"
    assert by_code["33"]["rate"] == "15.0000"
    assert by_code["33"]["payable"] == "52.86"
    assert by_code["48"]["payable"] == "8.81"
    assert by_code["78"]["payable"] == "1,761.92"
    assert by_code["87"]["rate"] == "0.7500"
    assert by_code["89"]["payable"] == "8.81"
    assert by_code["98"]["rate"] == "0.2000"
    assert by_code["98"]["payable"] == "176.19"


@pytest.mark.django_db
def test_tax_preview_rates_follow_hs_code_fields(tariff):
    tariff.import_duty = "18.500"
    tariff.import_vat = "12.5%"
    tariff.nhil_rate = "5%"
    tariff.save()
    rows = preview()["items"][0]["rows"]
    by_code = {row["code"]: row for row in rows}
    assert by_code["01"]["rate"] == "18.5000"
    assert by_code["01"]["payable"] == "16,297.76"  # 18.5% of 88,096.00
    assert by_code["02"]["rate"] == "12.5000"
    assert by_code["47"]["rate"] == "5.0000"


@pytest.mark.django_db
def test_tax_preview_without_tariff_row_keeps_zero_rates(db):
    GhanaHSCode.objects.filter(code=REFERENCE_HS).delete()  # the seeded tariff may include it
    result = compute_tax_preview(reference_form_data())
    payable = {row["code"]: row["payable"] for row in result["declaration_rows"]}
    assert payable["01"] == "0.00"
    # Only the tariff-derived taxes (duty/VAT/NHIL) zero out; the fixed-rate
    # levies (ECOWAS, Network Charge chain, Withholding, SPL, EXIM, Inspection,
    # AU) plus the flat fees still apply: 5,224.09 + 17.00 flats.
    assert result["totals"]["payable"] == "5,241.09"


def test_tax_preview_empty_form_data():
    result = compute_tax_preview({})
    assert [row["code"] for row in result["declaration_rows"]] == EXPECTED_CATALOG_CODES
    assert all(row["payable"] == "0.00" for row in result["declaration_rows"]) is False  # flats stay
    assert result["items"] == []
    assert result["item_total"] == "0.00"
    assert result["totals"]["payable"] == "17.00"
    assert result["customs_value"] == {"fcy": "0.00", "ncy": "0.00"}


# --- views.py: initial-phase context helper ---------------------------------


def test_boe_tax_panel_context_builds_zero_phase_contract():
    from scenarios.views import _boe_tax_panel_context

    declaration = types.SimpleNamespace(
        pk=7,
        cpc="40D01",
        form_data={
            "customs_value_fcy": "7576.00",
            "customs_value_ncy": "88096.00",
            "items": [{"item_no": "0001", "hs_code": REFERENCE_HS, "fob_ncy": "88096.00", "customs_value_ncy": "88096.00"}],
        },
    )
    context = _boe_tax_panel_context(declaration)
    assert [row["code"] for row in context["tax_rows"]] == EXPECTED_CATALOG_CODES
    assert all(row["payable"] == "0.00" for row in context["tax_rows"])
    assert context["tax_totals"] == {"tax": "0.00", "exempted": "0.00", "guarantee": "0.00", "payable": "0.00"}
    assert context["tax_items"] == [{
        "index": 0, "item_no": "0001", "hs_code": REFERENCE_HS, "cpc": "40D01",
        "fob_ncy": "88,096.00", "customs_value_ncy": "88,096.00", "payable": "0.00",
    }]
    assert context["tax_cv"] == {"fcy": "7,576.00", "ncy": "88,096.00"}


def test_boe_tax_panel_context_item_cpc_falls_back_to_declaration():
    from scenarios.views import _boe_tax_panel_context

    declaration = types.SimpleNamespace(pk=7, cpc="40001", form_data={"items": [{"hs_code": ""}]})
    context = _boe_tax_panel_context(declaration)
    assert context["tax_items"][0]["cpc"] == "40001"
    assert context["tax_items"][0]["item_no"] == "0001"
    assert context["tax_cv"] == {"fcy": "0.00", "ncy": "0.00"}


# --- Include template (standalone render, documented context contract) ------


def build_context(**overrides):
    declaration = types.SimpleNamespace(
        pk=42,
        job_no="2610020010GCH001156",
        status="draft",
        status_code_display="DR, Draft",
        form_data={"customs_value_fcy": "7,576.00", "customs_value_ncy": "88,096.00"},
    )
    zero_rows = [
        {"code": entry["code"], "name": entry["name"], "user_defined": "N", "exempted": "0.00", "suspended": "0.00", "payable": "0.00"}
        for entry in TAX_CATALOG
    ]
    context = {
        "declaration": declaration,
        "is_draft": True,
        "tax_rows": zero_rows,
        "tax_totals": {"tax": "0.00", "exempted": "0.00", "guarantee": "0.00", "payable": "0.00"},
        "tax_items": [{
            "index": 0, "item_no": "0001", "hs_code": "4015190000", "cpc": "40D01",
            "fob_ncy": "88,096.00", "customs_value_ncy": "88,096.00", "payable": "0.00",
        }],
        "tax_cv": {"fcy": "7,576.00", "ncy": "88,096.00"},
    }
    context.update(overrides)
    return context


def render(**overrides):
    return render_to_string(TEMPLATE_NAME, build_context(**overrides))


def test_tax_panel_renders_sections_and_red_note():
    html = render()
    assert "* From this tab, you can calculate the tax amount on the BOE declaration before customs verification starts." in html
    assert 'class="required-note"' in html
    for heading in ("Total Payable Tax", "Total Customs Value", "Calculation of Duties/Taxes", "Item"):
        assert heading in html, f"missing section heading: {heading}"
    assert "<section" not in html  # inner content only — no page scaffold


def test_tax_panel_payable_tax_grid_ids_and_prefill():
    html = render()
    for element_id in ("tax-total", "tax-exempted", "tax-guarantee", "tax-payable", "tax-cv-fcy", "tax-cv-ncy"):
        assert f'id="{element_id}"' in html, f"missing id: {element_id}"
    assert "2610020010GCH001156" in html  # job no from declaration
    assert "DR, Draft" in html  # status from declaration
    assert "7,576.00" in html and "88,096.00" in html  # customs values prefilled


def test_tax_panel_customs_value_falls_back_to_form_data():
    html = render(tax_cv=None)
    assert 'id="tax-cv-fcy">7,576.00<' in html
    assert 'id="tax-cv-ncy">88,096.00<' in html
    empty = render(tax_cv=None, declaration=types.SimpleNamespace(pk=42, job_no="J", status="draft", status_code_display="", form_data={}))
    assert 'id="tax-cv-fcy">0.00<' in empty
    assert 'id="tax-cv-ncy">0.00<' in empty


def test_tax_panel_renders_18_declaration_rows_with_zero_amounts():
    html = render()
    assert html.count('class="tax-payable-cell"') == 18  # the JS selector text also mentions the class
    assert html.count('<td class="tax-payable-cell"') == 18
    assert html.count('data-tax-code="') == 19  # 18 cells + the JS fill selector
    for code in EXPECTED_CATALOG_CODES:
        assert f'data-tax-code="{code}"' in html
    assert ">Import Duty</td>" in html
    assert ">African Union Import Levy</td>" in html
    assert 'id="tax-total-row"' in html
    assert "Total Taxes" in html
    assert html.count(">0.00<") >= 18  # initial phase: nothing computed yet


def test_tax_panel_compute_button_and_post_url():
    html = render()
    assert 'id="tax-compute"' in html
    assert "secondary-button" in html
    assert "Compute Tax" in html
    from django.urls import reverse
    assert reverse("boe-compute-tax", args=[42]) in html


def test_tax_panel_item_radio_table_and_detail_containers():
    html = render()
    assert 'name="tax-item-radio"' in html
    assert 'data-index="0"' in html
    for column in ("Item No.", "HS", "CPC", "FOB(GHS)", "Customs Value(GHS)", "Amount Exempted(GHS)", "Amount Suspended(GHS)", "Amount Payable(GHS)"):
        assert column in html
    assert "4015190000" in html and "40D01" in html
    assert html.count('class="tax-item-payable"') == 1  # the JS selector text also mentions the class
    assert 'data-tax-item-detail="0"' in html
    assert "hidden" in html  # detail containers start hidden
    assert "Total Taxes by Item" in html
    assert html.count('class="tax-itemtotal-cell"') == 3  # the JS selector text also mentions the class


def test_tax_panel_script_wires_fetch_and_details():
    html = render()
    assert "boe-tab-tax" not in html  # the wrapper section stays with the integrator
    assert "tax-payable-cell[data-tax-code=" in html  # declaration cells filled from the response
    assert ".tax-item-detail-body[data-index=" in html  # per-item rows rebuilt via DOM
    assert "Compute failed." in html
    assert "X-CSRFToken" in html  # POST follows the page's fetch conventions


def test_boe_compute_tax_view_exists_for_integrator_route():
    import scenarios.views as views

    view = getattr(views, "boe_compute_tax", None)
    assert callable(view)
    assert view.__name__ == "boe_compute_tax"  # simulator_access_required preserves the name via @wraps
    assert "Compute the estimated duty preview" in (view.__doc__ or "")


# --- Page-level integration (tax panel inside the declaration page) ----------

import pytest  # noqa: E402  (module-level imports stay above; pytest already imported)
from django.contrib.auth import get_user_model  # noqa: E402
from django.urls import reverse  # noqa: E402

from scenarios.models import BoeDeclaration  # noqa: E402


@pytest.mark.django_db
def test_tax_tab_renders_inside_the_declaration_page_and_computes(client):
    User = get_user_model()
    staff = User.objects.create_user(username="tax-page-user", email="tax-page-user@example.test", password="x", is_staff=True)
    client.force_login(staff)
    from tests.test_boe_declaration import _make_idf

    idf = _make_idf(staff, "KGHTESTUCR9900000099")
    created = client.post(reverse("boe-create"), {
        "reuse": "IDF", "idf_number": idf.application_no,
        "regime": "IM", "cpc": "4000000", "zone": "ECO",
    }, content_type="application/json").json()
    declaration = BoeDeclaration.objects.get(job_no=created["job_no"])
    data = declaration.form_data or {}
    data["customs_value_ncy"] = "88096.00"
    data["customs_value_fcy"] = "7576.00"
    data["items"] = [{**(data.get("items") or [{}])[0], "hs_code": "4015190000", "customs_value_ncy": "88096.00", "fob_ncy": "88096.00", "cpc": "40D01"}]
    declaration.form_data = data
    declaration.save(update_fields=("form_data", "updated_at"))
    page_url = reverse("boe-declaration", args=(declaration.pk,))

    draft_page = client.get(page_url)
    assert b"Compute Tax" in draft_page.content
    assert b"Total Payable Tax" in draft_page.content
    assert b"Calculation of Duties/Taxes" in draft_page.content
    assert draft_page.content.count(b'class="tax-payable-cell"') == 18
    assert b"Import Duty" in draft_page.content
    # Original phase: every amount is still zero before the Compute Tax click.
    assert b'id="tax-payable">0.00<' in draft_page.content

    # The compute endpoint reproduces the reference arithmetic.
    compute = client.post(reverse("boe-compute-tax", args=(declaration.pk,)), content_type="application/json")
    assert compute.status_code == 200
    tax = compute.json()["tax"]
    payable = {row["code"]: row["payable"] for row in tax["declaration_rows"]}
    assert payable["01"] == "17,619.20"  # 20% import duty on 88,096.00 (seeded tariff)
    assert tax["totals"]["tax"] == "22,860.29"  # minus the unreproduced Disinfection Fee

    # HS 4015190000 calls for FDA: submission is blocked until an approved FDA
    # application is attached to the UCR.
    blocked = client.post(reverse("boe-submit", args=(declaration.pk,)), HTTP_ACCEPT="application/json")
    assert blocked.status_code == 400
    assert b"approved FDA" in blocked.content

    from scenarios.models import MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, MdaStatus
    fda = MdaAgency.objects.get_or_create(code="FDA", defaults={"name": "Food and Drugs Authority"})[0]
    fda_app = MdaApplication.objects.get_or_create(mda=fda, code="FDA", defaults={"name": "FDA Product Registration"})[0]
    MdaProcess.objects.get_or_create(application=fda_app, code="REG", defaults={"name": "Product Registration"})
    MdaConsignmentRequest.objects.create(
        consignment_application=declaration.idf.consignment_application,
        mda=fda, application=fda_app,
        process=MdaProcess.objects.filter(application=fda_app).first(),
        consignment_type="SG", application_no="CD202610FDAFR0000999", status=MdaStatus.APPROVED,
    )
    # The Tax tab (and its compute button) disappears once submitted.
    client.post(reverse("boe-submit", args=(declaration.pk,)))
    submitted_page = client.get(page_url)
    assert b"Compute Tax" not in submitted_page.content
