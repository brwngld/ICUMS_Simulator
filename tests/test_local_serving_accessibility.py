from html.parser import HTMLParser

import pytest
from django.urls import reverse

from accounts.models import User
from start_local import validated_host


def login_simulator_author(client):
    user = User.objects.create_superuser(username="simulator-author", email="simulator-author@example.test", password="test-password")
    client.force_login(user)


class LandmarkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.has_main = False
        self.h1_count = 0
        self.has_skip_link = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        elif tag == "main":
            self.has_main = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "a" and values.get("href") == "#main-content":
            self.has_skip_link = True


def assert_page_landmarks(response):
    parser = LandmarkParser()
    parser.feed(response.content.decode())
    assert parser.lang == "en"
    assert parser.has_main
    assert parser.h1_count == 1
    assert parser.has_skip_link


def test_packaged_server_restricts_binding_to_loopback():
    assert validated_host("127.0.0.1") == "127.0.0.1"
    with pytest.raises(Exception, match="loopback"):
        validated_host("0.0.0.0")


@pytest.mark.django_db
def test_login_page_has_accessible_landmarks(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    assert b'<label for="id_username">' in response.content
    assert b'<label for="id_password">' in response.content


@pytest.mark.django_db
def test_frontend_simulator_portal_uses_main_account_but_not_practical_gate(client):
    user = User.objects.create_user(username="portal-preview", email="portal-preview@example.test", password="test-password")
    client.force_login(user)
    response = client.get(reverse("simulator-portal"))
    assert response.status_code == 200
    assert b"TRAINING SIMULATOR" in response.content
    assert b"Cargo tracking dashboard" in response.content
    assert b"Illustrative only" in response.content
    assert b"Use fictional references only" in response.content
    assert b'id="cargo-search-dialog"' in response.content
    assert b"Cargo search information" in response.content
    assert b"Container/Chassis No." in response.content
    assert b"DO / SR No." in response.content
    assert b'id="boe-search-dialog"' in response.content
    assert b"BOE status search" in response.content
    assert b"Importer/Exporter Code" in response.content
    assert b'Back to student dashboard' in response.content
    assert reverse("dashboard").encode() in response.content
    for item in (b"Cargo", b"Clearance", b"Collection", b"Single Window", b"Agent Management", b"e-Docs", b"Post Clearance Audit", b"AEO", b"More Information", b"DW Service"):
        assert item in response.content


@pytest.mark.django_db
def test_simulator_portal_opens_credential_login(client):
    response = client.get(reverse("simulator-portal"))
    assert response.status_code == 200
    assert b'id="simulator-login-dialog"' in response.content
    assert b"Monthly password" in response.content
    assert b"Register as a new student" in response.content


@pytest.mark.django_db
def test_cargo_direct_delivery_frontend_preview(client):
    login_simulator_author(client)
    response = client.get(reverse("cargo-direct-delivery"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"Direct Delivery", b"Manifest No.", b"BOE Summary Information", b"Container / Chassis List", b"No fictional data found."):
        assert item in response.content
    assert b'Back to student dashboard' in response.content
    assert reverse("dashboard").encode() in response.content
    assert b"cargo/service-request" in response.content


@pytest.mark.django_db
def test_cargo_service_request_frontend_lookup_preview(client):
    login_simulator_author(client)
    response = client.get(reverse("cargo-service-request"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"Service Request", b"BL Number", b"Manifest No.", b"BL Info", b"D/O Information", b"DEMO-BL-2026"):
        assert item in response.content


@pytest.mark.django_db
def test_clearance_workspace_opens_create_boe_with_regime_lookup(client):
    login_simulator_author(client)
    response = client.get(reverse("clearance-workspace"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"Create BOE Declaration", b"Create BoE Type", b"New Declaration", b"Clone Declaration",
                 b"Regime", b"CL. Plan", b"Reuse Document", b"Create Declaration Form"):
        assert item in response.content
    assert b'id="boe-regime-dialog"' in response.content
    assert b'id="boe-regime-search"' in response.content
    assert b'id="boe-reuse-extra"' in response.content
    assert b'id="boe-reuse-number"' in response.content
    assert b'id="boe-reuse-ucr"' in response.content
    assert b'id="boe-cpc-code"' in response.content
    assert b'id="boe-zone-code"' in response.content
    assert b'id="boe-cancelled-ucr"' in response.content
    assert b'id="boe-cpc-dialog"' in response.content
    assert b'id="boe-cpc-search"' in response.content
    assert b'id="boe-zone-dialog"' in response.content
    assert b'id="boe-zone-search"' in response.content
    for zone in (b"ECOWAS Imports", b"General Imports", b"Exports", b"AFRICAN UNION IMP. LEVY",
                 b"Temporary Vehicle Imports", b"Africa Continental Free Trade (AfCFTA)",
                 b"GH-EU Economic Partnership Agreement (EPA)", b"GH-UK Trade Partnership Agreement"):
        assert zone in response.content
    assert b'id="clearancePlanCd"' in response.content
    assert b'value="PMD">PMD, Pre-Manifest Declaration' in response.content
    assert b'value="DPM">DPM, Declaration Post-Manifest' in response.content
    assert b'value="NBD">NBD, Non BL(AWB) Declaration' in response.content
    assert b'value="CGD">CGD, Courier Goods Declaration' in response.content
    assert b"When using Reuse Document 'LOC'" in response.content
    assert b"Direct Export" in response.content
    assert b"Other Operations" in response.content
    assert b"Temporary Export following Import into Home Use" in response.content
    assert b"Register Declaration menu" not in response.content
    assert len(response.context["boe_regimes"]) == 34

    from scenarios.models import CustomsProcedureCode, CustomsRegime
    assert CustomsRegime.objects.count() == 34
    assert CustomsProcedureCode.objects.filter(regime__code="40").count() == 134
    first_page = client.get(reverse("clearance-cpc-search"), {"regime": "40", "page": 1}).json()
    second_page = client.get(reverse("clearance-cpc-search"), {"regime": "40", "page": 2}).json()
    assert first_page["total"] == 134 and len(first_page["results"]) == 100
    assert len(second_page["results"]) == 34
    matched = client.get(reverse("clearance-cpc-search"), {"regime": "40", "q": "Grants and Aids"}).json()
    assert matched["results"][0]["code"] == "40A00"
    assert client.get(reverse("clearance-cpc-search"), {"regime": "10"}).json()["results"] == []
    assert client.get(reverse("admin:scenarios_customsregime_changelist")).status_code == 200
    assert client.get(reverse("admin:scenarios_customsprocedurecode_changelist")).status_code == 200
    regime_admin = client.get(reverse(
        "admin:scenarios_customsregime_change",
        args=(CustomsRegime.objects.get(code="40").pk,),
    ))
    assert regime_admin.status_code == 200
    assert b"admin/css/customs-procedure-code.css" in regime_admin.content
    assert b'rows="2"' in regime_admin.content
    cpc_admin = client.get(reverse("admin:scenarios_customsprocedurecode_add"))
    assert cpc_admin.status_code == 200
    assert b"admin/css/customs-procedure-code.css" in cpc_admin.content
    assert b'rows="2"' in cpc_admin.content


@pytest.mark.django_db
def test_create_ucr_document_row_controls(client):
    login_simulator_author(client)
    response = client.get(reverse("single-window-create-ucr"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    assert b'id="add-document"' in response.content
    assert b'id="document-rows"' in response.content
    assert b"Document Type" in response.content
    assert b"Attached File" in response.content
    assert b'id="document-code-pagination"' in response.content
    assert b'data-code="019"' in response.content
    assert b"Delivery Order" in response.content
    assert b'data-code="029"' in response.content
    assert b'data-code="040"' in response.content
    assert b"Passenger Unaccompanied Baggage Declaration" in response.content
    assert b'data-code="102"' in response.content
    assert b"Note Verbale (MFA Use Only)" in response.content
    assert b'id="document-code-dialog"' in response.content
    assert b"Bill of Lading / Airwaybill" in response.content


@pytest.mark.django_db
def test_search_ucr_frontend_preview_and_navigation(client):
    login_simulator_author(client)
    response = client.get(reverse("single-window-search-ucr"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"Search Unique Consignment Ref.", b"UCR No. or Temp. No.", b"Regime Type", b"Clone UCR", b"Amend"):
        assert item in response.content
    assert b"FI, Free Zones - Inbound" in response.content
    assert b"AP, Approval" in response.content
    assert b"DR, Draft" in response.content

    workspace = client.get(reverse("single-window-overview"))
    assert reverse("single-window-search-ucr").encode() in workspace.content


@pytest.mark.django_db
def test_exporter_registration_create_and_search_previews(client):
    login_simulator_author(client)
    create = client.get(reverse("single-window-create-exporter"))
    assert create.status_code == 200
    assert_page_landmarks(create)
    for item in (b"Create Exporter Registration", b"Header Detail", b"Item List", b"eDoc. List", b"Description of Business"):
        assert item in create.content

    search = client.get(reverse("single-window-search-exporter"))
    assert search.status_code == 200
    assert_page_landmarks(search)
    for item in (b"CC01, GNCCI Certificate EUR1", b"GC01, AfCFTA Certificate of Origin", b"AJ, Approval Joint Inspection", b"CUHQ, GRA CUSTOMS HEADQUARTERS"):
        assert item in search.content


@pytest.mark.django_db
def test_create_opt_in_out_frontend_preview(client):
    login_simulator_author(client)
    response = client.get(reverse("single-window-create-opt-in-out"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"GFZA, Ghana Free Zone Authority", b"GSA, Ghana Standards Authority", b'id="opt-branch"', b"Product Group Fee", b"Importer Address"):
        assert item in response.content
    assert b'id="mda-branch-dialog"' in response.content
    assert b"opt-in-out-branches.js" in response.content
    assert b'id="gsa-product-dialog"' in response.content
    assert b"opt-in-out-gsa-products.js" in response.content
    assert b'id="submit-opt"' in response.content
    assert b"FOR PERSONAL EFFECTS" in response.content

    workspace = client.get(reverse("single-window-overview"))
    assert reverse("single-window-create-opt-in-out").encode() in workspace.content


@pytest.mark.django_db
def test_preparation_application_create_and_search_previews(client):
    login_simulator_author(client)
    create = client.get(reverse("single-window-create-preparation-application"))
    assert create.status_code == 200
    assert_page_landmarks(create)
    for item in (b"New Preparation Request", b"New Master Request", b"New Consignment Request", b"Create Application Form"):
        assert item in create.content

    search = client.get(reverse("single-window-search-preparation-application"))
    assert search.status_code == 200
    assert_page_landmarks(search)
    for item in (b"Application List", b"Application No.", b"Exporter Code or Name", b"Search Application Records"):
        assert item in search.content

    workspace = client.get(reverse("single-window-overview"))
    assert reverse("single-window-create-preparation-application").encode() in workspace.content
    assert reverse("single-window-search-preparation-application").encode() in workspace.content


@pytest.mark.django_db
def test_create_master_application_frontend_preview(client):
    login_simulator_author(client)
    response = client.get(reverse("single-window-create-master-application"))
    assert response.status_code == 200
    assert_page_landmarks(response)
    for item in (b"New Master Request", b"APD, Animal Production Directorate", b"GSA, Ghana Standards Authority", b"FCOM, Fisheries Commission", b"Copy Application", b"Create Application Form"):
        assert item in response.content

    workspace = client.get(reverse("single-window-overview"))
    assert reverse("single-window-create-master-application").encode() in workspace.content


@pytest.mark.django_db
def test_opt_in_out_search_and_submitted_detail_previews(client):
    login_simulator_author(client)
    search = client.get(reverse("single-window-search-opt-in-out"))
    assert search.status_code == 200
    assert_page_landmarks(search)
    for item in (b"Opt In/Out Reporting Search", b"Search Opt In/Out Records", b"Processing Status", b"Opt No."):
        assert item in search.content
    assert reverse("single-window-opt-in-out-detail").encode() in search.content

    detail = client.get(reverse("single-window-opt-in-out-detail"))
    assert detail.status_code == 200
    assert_page_landmarks(detail)
    for item in (b"Opt In/Out General", b"Product Group Fee (GHS)", b"Payment Bill", b"highest applicable fee", b"FOR PERSONAL EFFECTS"):
        assert item in detail.content
