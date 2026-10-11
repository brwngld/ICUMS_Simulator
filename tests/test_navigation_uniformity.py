"""Regression tests: the simulator navigation.

Two layers, both restored to the original simulator information
architecture:

- The logged-in top menu (reference 004): ten service areas on every
  simulator page, active state following the current area.
- The left sidebar: like the original in-page sidebars, each area's pages
  see only their own menu tree (the portal home keeps the Cargo tree, as
  it originally did), as Unfold collapsible sections with the original
  section and leaf labels.
"""

import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

TOP_MENU_ITEMS = [
    b"Cargo",
    b"Clearance",
    b"Collection",
    b"Single Window",
    b"Agent Management",
    b"e-Docs",
    b"Post Clearance Audit",
    b"AEO",
    b"More Information",
    b"DW Service",
]

# route -> (own sections that must be present, other-area sections that
# must be absent)
AREA_PAGES = [
    ("simulator-portal", ["Sea Import", "Tracking", "Direct Delivery"], ["Declaration Report", "Previous Data"]),
    ("cargo-direct-delivery", ["Sea Import", "Customs Area", "Direct Delivery"], ["Declaration Report", "Previous Data"]),
    ("cargo-service-request", ["Sea Import"], ["Petroleum Management", "Create UCR"]),
    ("clearance-workspace", ["Declaration", "Petroleum Management", "Create BOE Declaration"], ["Sea Import", "Previous Data"]),
    ("search-boe-declaration", ["Declaration"], ["Sea Import", "Create UCR"]),
    ("single-window-overview", ["Registration", "Previous Data", "Create UCR"], ["Sea Import", "Petroleum Management"]),
    ("single-window-create-ucr", ["Registration"], ["Sea Import", "Petroleum Management"]),
    ("single-window-search-ucr", ["Registration"], ["Sea Import", "Declaration Report"]),
]


def _author_client(client):
    staff = User.objects.create_user(username="nav-uniform-staff", email="nav@example.test", password="x", is_staff=True)
    client.force_login(staff)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("route,own,absent", AREA_PAGES)
def test_top_menu_and_area_sidebar(client, route, own, absent):
    _author_client(client)
    response = client.get(reverse(route))
    assert response.status_code == 200
    body = response.content
    for item in TOP_MENU_ITEMS:
        assert item in body, f"top-menu item {item!r} missing on {route}"
    assert b'aria-label="Logged-in simulator navigation"' in body
    for section in own:
        assert section.encode() in body, f"own section {section!r} missing on {route}"
    for section in absent:
        assert section.encode() not in body, f"other-area section {section!r} leaked onto {route}"
    # The shared workspace links are always present.
    assert b"Student dashboard" in body
    assert b"Workspace home" in body


@pytest.mark.django_db
def test_top_menu_active_state_follows_the_area(client):
    _author_client(client)
    for route, area in (
        ("cargo-direct-delivery", "Cargo"),
        ("clearance-workspace", "Clearance"),
        ("single-window-create-ucr", "Single Window"),
    ):
        body = client.get(reverse(route)).content.decode()
        currents = re.findall(r'aria-current="page"[^>]*>([^<]+)</a>', body)
        assert currents == [area], f"{route}: active top-menu items were {currents}"


@pytest.mark.django_db
def test_every_sidebar_destination_resolves(client):
    client = _author_client(client)
    hrefs = set()
    for route in ("simulator-portal", "clearance-workspace", "single-window-overview"):
        body = client.get(reverse(route)).content.decode()
        hrefs.update(re.findall(r'href="(/practical/[^"#]+)"', body))
    assert len(hrefs) > 60  # the three trees carry the full simulator map
    for href in sorted(hrefs):
        response = client.get(href)
        assert response.status_code == 200, f"{href} returned {response.status_code}"


@pytest.mark.django_db
def test_guided_practical_pages_keep_the_learning_navigation(client):
    """The guided scenario pages are learning surfaces: they keep the
    student navigation, not the simulator menus."""
    staff = User.objects.create_user(username="nav-guided-staff", email="ng@example.test", password="x", is_staff=True)
    client.force_login(staff)
    response = client.get(reverse("scenario-list"))
    assert response.status_code in (200, 302)
    if response.status_code == 200:
        assert b"Create BOE Declaration" not in response.content
        assert b"Theory" in response.content
