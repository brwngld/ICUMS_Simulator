"""Regression tests: every simulator-portal page renders the same shared top navigation.

The canonical navigation is templates/scenarios/_portal_top_nav.html (10 items, fixed
order, fixed hrefs). These tests log in with a staff user (staff always has simulator
access) and assert that each representative page renders that shared partial, including
the previously-drifting pages (DW Service was missing on some, and the declaration
search/create pages carried a reduced inline sidebar).
"""
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from scenarios.models import ConsignmentApplication, GhanaHSCode, UcrDeclaration

User = get_user_model()

CANONICAL_NAV_TEXTS = [
    "Cargo",
    "Clearance",
    "Collection",
    "Single Window",
    "Agent Management",
    "e-Docs",
    "Post Clearance Audit",
    "AEO",
    "More Information",
    "DW Service",
]


def _extract_top_nav(content):
    match = re.search(r'<nav class="portal-top-nav"[^>]*>.*?</nav>', content, re.S)
    return match.group(0) if match else ""


def _nav_link_texts(nav_html):
    return re.findall(r"<a\b[^>]*>(.*?)</a>", nav_html)


def _assert_canonical_top_nav(response):
    assert response.status_code == 200
    content = response.content.decode()
    nav_html = _extract_top_nav(content)
    assert nav_html, "page does not render the portal top navigation"
    assert 'aria-label="Logged-in simulator navigation"' in nav_html
    assert _nav_link_texts(nav_html) == CANONICAL_NAV_TEXTS
    return content


@pytest.fixture
def staff_client(client):
    user = User.objects.create_user(
        username="nav-staff",
        email="nav-staff@example.test",
        password="x",
        is_staff=True,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_clearance_workspace_top_nav(staff_client):
    response = staff_client.get(reverse("clearance-workspace"))
    content = _assert_canonical_top_nav(response)
    clearance_link = re.search(r'<a href="[^"]*clearance[^"]*"[^>]*>Clearance</a>', content)
    assert clearance_link and 'aria-current="page"' in clearance_link.group(0)


@pytest.mark.django_db
def test_clearance_reference_page_top_nav(staff_client):
    response = staff_client.get(
        reverse("clearance-reference-page", kwargs={"page_key": "petroleum-lifting-summary"})
    )
    content = _assert_canonical_top_nav(response)
    # Full shared clearance sidebar (not a reduced inline copy) includes the Petroleum section.
    assert "Petroleum Management" in content


@pytest.mark.django_db
def test_declaration_search_uses_full_shared_sidebar(staff_client):
    response = staff_client.get(reverse("search-boe-declaration"))
    content = _assert_canonical_top_nav(response)
    assert "Petroleum Management" in content


@pytest.mark.django_db
def test_cargo_direct_delivery_top_nav(staff_client):
    response = staff_client.get(reverse("cargo-direct-delivery"))
    content = _assert_canonical_top_nav(response)
    cargo_link = re.search(r'<a href="[^"]*cargo[^"]*"[^>]*>Cargo</a>', content)
    assert cargo_link and 'aria-current="page"' in cargo_link.group(0)


@pytest.mark.django_db
def test_single_window_create_ucr_top_nav(staff_client):
    # single-window-workspace redirects to the first actionable Single Window step.
    response = staff_client.get(reverse("single-window-workspace"), follow=True)
    content = _assert_canonical_top_nav(response)
    single_window_link = re.search(r'<a href="[^"]*single-window[^"]*"[^>]*>Single Window</a>', content)
    assert single_window_link and 'aria-current="page"' in single_window_link.group(0)


@pytest.mark.django_db
def test_consignment_application_top_nav(staff_client):
    response = staff_client.get(reverse("single-window-create-consignment-application"))
    _assert_canonical_top_nav(response)


@pytest.mark.django_db
def test_assessment_detail_top_nav(staff_client):
    GhanaHSCode.objects.update_or_create(
        code="8703240000", defaults={"description": "MOTOR CARS", "import_duty": "20.00"}
    )
    ucr = UcrDeclaration.objects.create(
        owner=User.objects.get(username="nav-staff"),
        regime="IM",
        goods_description="VEHICLE",
        origin_country="CN",
        destination_country="GH",
        transport_mode="10, Sea Transport",
        ucr_no="KGHTESTUCR9900000002",
        status=UcrDeclaration.Status.SUBMITTED,
    )
    application = ConsignmentApplication.objects.create(
        owner=ucr.owner,
        ucr=ucr,
        status=ConsignmentApplication.Status.SUBMITTED,
        currency="JPY",
        exchange_rate=0.0696,
        fob_fcy=1534800.00,
        fob_ncy=106822.08,
        freight_ncy=11583.70,
        items=[{"hs_code": "8703240000", "description": "MOTOR CAR", "quantity": "1"}],
    )
    response = staff_client.get(reverse("assessment-detail", kwargs={"application_id": application.pk}))
    _assert_canonical_top_nav(response)
