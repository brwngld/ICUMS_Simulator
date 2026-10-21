"""Regression tests: the simulator navigation.

Two layers, both restored to the original simulator information
architecture:

- The identity row (reference 004): the brand lockup, the nine service
  areas between the paging arrows, and the sign-in control — one row on
  every simulator page, active state following the current area. The
  header strip above it carries the page's own eyebrow and title instead
  of the admin greeting.
- The left sidebar: like the original in-page sidebars, each area's pages
  see only their own menu tree, as Unfold collapsible sections with the
  original section and leaf labels. The workspace home and the logged-out
  explainer carry no area tree at all, and until simulator access is
  granted the home panel leads with the way in.
- The service areas are only navigable with simulator access, so a reader
  without it is offered the More information page where the area bar
  would be.
- The admin chrome that only serves a signed-in user (sidebar, header
  strip) is skipped for a visitor.
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
    b"DW Service",
]

# route -> (own sections that must be present, other-area sections that
# must be absent)
AREA_PAGES = [
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


def _identity_row(body):
    """The single row at the top of every simulator page: lockup, service
    areas between the paging arrows, then the sign-in control."""
    start = body.index('class="sim-brandbar"')
    return body[start : body.index("<script>", start)]


@pytest.mark.django_db
def test_the_service_menu_lives_inside_the_identity_row(client):
    _author_client(client)
    body = client.get(reverse("simulator-portal")).content.decode()
    row = _identity_row(body)
    assert "brand-lockup.png" in row
    assert row.index('class="sim-brand-logo"') < row.index('class="sim-top-nav"')
    assert row.index('data-sim-nav="-1"') < row.index('class="sim-top-nav"') < row.index('data-sim-nav="1"')
    assert row.count('class="sim-nav-arrow"') == 2
    for item in TOP_MENU_ITEMS:
        assert f">{item.decode()}<" in row, f"{item!r} left the row"
    # One row, not two: the menu appears nowhere else on the page.
    assert body.count('class="sim-top-nav"') == 1
    assert "More Information" not in body


@pytest.mark.django_db
def test_the_portal_sign_in_control_lives_in_the_identity_row(client, db):
    body = client.get(reverse("simulator-portal")).content.decode()
    assert "data-open-simulator-login" in _identity_row(body)
    page_head = body[body.index('<div class="dash sim-page">') : body.index("tracking-search")]
    assert "data-open-simulator-login" not in page_head


@pytest.mark.django_db
def test_a_signed_in_portal_offers_sign_out_from_the_identity_row(client):
    _author_client(client)
    body = client.get(reverse("simulator-portal")).content.decode()
    assert "data-open-review-dialog" in _identity_row(body)


@pytest.mark.django_db
def test_the_header_carries_the_page_identity(client):
    """The greeting gives way to the page's own eyebrow and title."""
    _author_client(client)
    body = client.get(reverse("simulator-portal")).content.decode()
    header = body[body.index('id="header-inner"') : body.index('class="sim-brandbar"')]
    assert "Practical training environment" in header
    assert "Cargo tracking dashboard" in header
    assert "Welcome" not in header
    # and it is not repeated down in the page body
    assert body.count("Cargo tracking dashboard") == 1


@pytest.mark.django_db
def test_a_page_without_an_identity_keeps_the_admin_header(client):
    """Only pages that name themselves take over the header strip."""
    _author_client(client)
    body = client.get(reverse("cargo-direct-delivery")).content.decode()
    assert 'class="sim-header-title"' not in body
    assert 'class="sim-header-eyebrow"' not in body
    assert 'class="sim-brandbar"' in body



@pytest.mark.django_db
def test_a_visitor_sees_no_admin_chrome(client):
    body = client.get(reverse("simulator-portal")).content.decode()
    assert 'id="nav-sidebar"' not in body
    assert 'id="header-inner"' not in body
    assert "permission to view or edit anything" not in body
    # The identity row and the sign-in control still describe the page.
    assert 'class="sim-brandbar"' in body
    assert "data-open-simulator-login" in body


@pytest.mark.django_db
def test_the_workspace_home_carries_no_area_menu(client):
    """The home is a launcher: its areas are entered from the brand bar, so
    the Cargo tree belongs to the Cargo pages and not here."""
    _author_client(client)
    body = client.get(reverse("simulator-portal")).content.decode()
    for section in ("Sea Import", "Petroleum Management", "Create BOE Declaration", "Declaration Report", "Previous Data"):
        assert section not in body, f"area section {section!r} left the Cargo pages"
    assert "Student dashboard" in body
    assert "Workspace home" in body


@pytest.mark.django_db
@pytest.mark.parametrize("username,is_staff", (("home-learner", False), ("home-author", True)))
def test_the_area_bar_is_offered_only_with_simulator_access(client, username, is_staff):
    """Every service area is gated behind simulator access, so a learner who
    has not signed in to the playground is not shown a row of bounces."""
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x", is_staff=is_staff)
    client.force_login(user)
    body = client.get(reverse("simulator-portal")).content.decode()
    assert 'class="sim-brandbar"' in body
    assert ("class=\"sim-top-nav\"" in body) is is_staff
    assert ('href="/practical/more-information/"' in body) is not is_staff


@pytest.mark.django_db
def test_the_home_panel_leads_with_the_way_in_until_access_is_granted(client):
    """Login, Forgot Password? and Request Account sit in the side panel as
    direct links, so nobody has to open the dialog to find them."""
    learner = User.objects.create_user(username="nav-learner", email="nl@example.test", password="x")
    client.force_login(learner)
    body = client.get(reverse("simulator-portal")).content.decode()
    assert "/practical/portal/?login=1" in body
    assert "/practical/portal/?login=1&amp;reset=1" in body
    assert reverse("register") in body
    panel = body[body.index('id="nav-sidebar"') :]
    for label in ("Login", "Forgot Password?", "Request Account"):
        assert label in panel, f"{label!r} never reached the panel"

    _author_client(client)
    author_body = client.get(reverse("simulator-portal")).content.decode()
    assert "Forgot Password?" not in author_body[author_body.index('id="nav-sidebar"') :]


@pytest.mark.django_db
def test_the_more_information_page_answers_a_visitor(client, db):
    """The explainer stands where the area bar would be, and it has to be
    readable before anyone can sign in."""
    from onboarding.models import DisclaimerVersion

    DisclaimerVersion.objects.create(version=99, title="Not the real ICUMS", body="This is a training simulator.\nNothing here touches Customs.", is_current=True)
    response = client.get(reverse("simulator-more-information"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Not the real ICUMS" in body
    assert "This is a training simulator." in body
    assert 'class="sim-brandbar"' in body
    assert "class=\"sim-top-nav\"" not in body
    assert reverse("register") in body


@pytest.mark.django_db
def test_the_admin_chrome_returns_for_a_signed_in_user(client):
    _author_client(client)
    body = client.get(reverse("simulator-portal")).content.decode()
    assert 'id="nav-sidebar"' in body
    assert 'id="header-inner"' in body


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
