"""Customs Office reference and Help dialog.

The 77 Ghana customs offices (CEPS stations) are admin-managed like the
port codes, with their own search endpoint and an ICUMS-styled help
dialog (Code/Name filters, No./Code/Code Name table, click to highlight,
double-click or Select to populate).
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import SimulatorCredential, User, allocate_student_id
from scenarios.models import CustomsOfficeCode, UcrDeclaration


@pytest.fixture
def simulator_student(db):
    user = User.objects.create_user(username="co-student", email="co@example.test", password="test-password", first_name="Co")
    user.student_id = allocate_student_id("Co")
    user.groups.add(Group.objects.get(name="Student"))
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    return user


@pytest.fixture
def simulator_client(client, simulator_student):
    client.force_login(simulator_student)
    session = client.session
    session["simulator_user_id"] = str(simulator_student.pk)
    session.save()
    return client


@pytest.mark.django_db
def test_customs_offices_are_seeded():
    assert CustomsOfficeCode.objects.count() == 77
    for code, name in [
        ("AFO1", "CEPS AFLAO"),
        ("TMA1", "CEPS TEMA"),
        ("CUHQ", "GRA - CUSTOMS HEADQUARTERS"),
        ("ZUR1", "ZUARUNGU CUSTOMS POST"),
    ]:
        office = CustomsOfficeCode.objects.get(code=code)
        assert office.name == name
        assert office.is_active


@pytest.mark.django_db
def test_customs_office_search_filters_and_paginates(simulator_client):
    search = reverse("application-customs-office-search")
    by_code = simulator_client.get(search, {"code": "TMA1"}).json()
    assert [row["code"] for row in by_code["results"]] == ["TMA1"]
    assert by_code["total"] == 1

    by_name = simulator_client.get(search, {"name": "BOLGATANGA"}).json()
    assert {row["code"] for row in by_name["results"]} == {"BLG1", "BLG9"}

    first = simulator_client.get(search, {"page": 1}).json()
    assert len(first["results"]) == 10
    assert first["page_count"] == 8  # 77 offices, 10 per page
    empty = simulator_client.get(search, {"code": "ZZZZ"}).json()
    assert empty["results"] == []


@pytest.mark.django_db
def test_customs_office_dialog_follows_the_icums_design(simulator_client, simulator_student):
    ucr = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="TEMPUCRCUST01", status="submitted",
        regime="10", declarant_code="CUS001",
    )
    response = simulator_client.get(reverse("consignment-application-create") + f"?ucr={ucr.ucr_no}")
    html = response.content.decode()
    assert "Customs Office Help" in html
    assert "Click a row to select the customs office" in html
    assert 'id="app-customs-select"' in html
    assert "<th>No.</th><th>Code</th><th>Code Name</th>" in html
    # the customs office field opens the customs dialog, not the port dialog
    assert 'data-app-customs-search="customs_office"' in html
    assert 'data-app-port-search="customs_office"' not in html


@pytest.mark.django_db
def test_search_dialogs_use_inline_labels_and_in_row_search(simulator_client, simulator_student):
    """Sweep: the picker dialogs carry the ICUMS subtitle, and the UCR search
    dialogs keep their Search button inside the filter row."""
    ucr = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="TEMPUCRSWP02", status="submitted",
        regime="10", declarant_code="SWP002",
    )
    html = simulator_client.get(reverse("consignment-application-create") + f"?ucr={ucr.ucr_no}").content.decode()
    for phrase in (
        "Click a row to select the country code",
        "Click a row to select the currency code",
        "Click a row to select the HS code",
    ):
        assert phrase in html

    from scenarios.models import UcrDeclaration as _U

    prep = simulator_client.get(reverse("single-window-create-preparation-application")).content.decode()
    assert 'id="ucr-reference-submit"' in prep
    assert prep.index('id="ucr-reference-submit"') > prep.index('id="ucr-reference-importer"')
    assert prep.index('id="ucr-reference-submit"') < prep.index('id="ucr-reference-results"')
