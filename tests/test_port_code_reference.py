"""Port-code reference data and the Port Code Help dialog.

Batch 1 seeds 4,000 ports from the ICUMS Common Code list (pages 1-200).
The lookup dialog follows the ICUMS design: Code/Name/Country filters, a
No./Code/Name/Country table, click to highlight, double-click or Select to
populate the form field.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import SimulatorCredential, User, allocate_student_id
from scenarios.models import PortCode, UcrDeclaration


@pytest.fixture
def simulator_student(db):
    user = User.objects.create_user(username="port-student", email="port@example.test", password="test-password", first_name="Port")
    user.student_id = allocate_student_id("Port")
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
def test_batch1_port_codes_are_seeded():
    assert PortCode.objects.count() >= 4000
    # An admin-maintained row coexists with the seeded batch (the migration
    # inserts with ignore_conflicts, so pre-existing rows are never replaced).
    PortCode.objects.get_or_create(code="GHTEM", defaults={"name": "Accra", "country_code": "GH", "country_name": "Ghana"})
    assert PortCode.objects.filter(code="GHTEM").exists()
    for code, name, country in [
        ("ACP1", "CIRRUS OIL SERVICES LTD", "Ghana"),
        ("ADALV", "Andorra la Vella", "Andorra"),
        ("ATAHO", "Althofen", "Austria"),
    ]:
        port = PortCode.objects.get(code=code)
        assert port.name == name
        assert port.country_name == country


@pytest.mark.django_db
def test_port_search_by_code_name_and_country(simulator_client):
    by_code = simulator_client.get(reverse("application-port-code-search"), {"code": "ACP1"}).json()
    codes = [row["code"] for row in by_code["results"]]
    assert codes[0] == "ACP1"  # partial match also finds ACP11 etc., like the real lookup
    assert by_code["total"] >= 1

    by_name = simulator_client.get(reverse("application-port-code-search"), {"name": "Andorra la Vella"}).json()
    assert any(row["code"] == "ADALV" for row in by_name["results"])

    by_country = simulator_client.get(reverse("application-port-code-search"), {"country": "Ghana"}).json()
    ghana_codes = {row["code"] for row in by_country["results"]}
    assert "ACP1" in ghana_codes

    empty = simulator_client.get(reverse("application-port-code-search"), {"code": "ZZZZZZ"}).json()
    assert empty["results"] == []
    assert empty["total"] == 0


@pytest.mark.django_db
def test_port_search_paginates(simulator_client):
    first = simulator_client.get(reverse("application-port-code-search"), {"page": 1}).json()
    assert len(first["results"]) == 10
    assert first["page_count"] >= 100
    second = simulator_client.get(reverse("application-port-code-search"), {"page": 2}).json()
    assert [row["code"] for row in second["results"]] != [row["code"] for row in first["results"]]


@pytest.mark.django_db
def test_port_dialog_follows_the_icums_design(simulator_client, simulator_student):
    ucr = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="TEMPUCRPORTS01", status="submitted",
        regime="10", declarant_code="PRT001",
    )
    response = simulator_client.get(reverse("consignment-application-create") + f"?ucr={ucr.ucr_no}")
    html = response.content.decode()
    assert "Port Code Help" in html
    assert "double-click a row" in html
    assert 'id="app-port-select"' in html
    assert 'id="app-port-filter-code"' in html
    assert 'id="app-port-filter-name"' in html
    assert 'id="app-port-filter-country"' in html
    assert "<th>No.</th><th>Code</th><th>Name</th><th>Country</th>" in html


@pytest.mark.django_db
def test_transport_lookup_fields_follow_the_icums_layout(simulator_client, simulator_student):
    """Each lookup is three parts, as in ICUMS: code field, search icon, then
    the resolved name display (Port of Arrival, Port of Departure, Customs
    Office)."""
    ucr = UcrDeclaration.objects.create(
        owner=simulator_student, ucr_no="TEMPUCRPORTLAY1", status="submitted",
        regime="10", declarant_code="PLY001",
    )
    response = simulator_client.get(reverse("consignment-application-create") + f"?ucr={ucr.ucr_no}")
    html = response.content.decode()
    import re

    for field in ("port_arrival", "port_departure"):
        pattern = rf'<input data-app-field="{field}"[^>]*><button type="button" data-app-port-search="{field}"[^>]*>.*?</button><input data-app-port-name-for="{field}"[^>]*readonly'
        assert re.search(pattern, html, re.S), f"{field} is not code | icon | name"
    pattern = r'<input data-app-field="customs_office"[^>]*><button type="button" data-app-customs-search="customs_office"[^>]*>.*?</button><input data-app-port-name-for="customs_office"[^>]*readonly'
    assert re.search(pattern, html, re.S), "customs_office is not code | icon | name"
