"""Registration-page redesign and mobile sidebar regression tests.

The signup page matches the Unfold-based login page, carries a Terms and
Conditions disclosure with a required consent checkbox, and keeps the
registration behaviour (Student group, generated Student ID, auto sign-in).
The sidebar drawer scrolls its own content so the account chip (theme,
View site, Log out) is reachable on narrow screens.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User


@pytest.mark.django_db
def test_register_page_matches_the_unfold_login_design(client):
    response = client.get(reverse("register"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "unfold/css/styles.css" in body
    assert "unfold-theme-colors" in body
    assert "app.css" not in body
    assert "ICUMS Simulator" in body
    assert "Training administration" in body
    assert "Sign in" in body  # footnote back to login


@pytest.mark.django_db
def test_register_page_requires_terms_acceptance(client):
    response = client.get(reverse("register"))
    body = response.content.decode()
    assert "Terms and Conditions" in body
    assert "training simulator, not the official ICUMS platform" in body
    assert 'name="terms_accepted"' in body


@pytest.mark.django_db
def test_registration_without_terms_is_rejected(client):
    response = client.post(reverse("register"), {
        "first_name": "Refa",
        "last_name": "Termless",
        "email": "refterm@example.test",
        "password1": "curved-harbour-tariff",
        "password2": "curved-harbour-tariff",
    })
    assert response.status_code == 200
    assert "You must accept the Terms and Conditions to register." in response.content.decode()
    assert not User.objects.filter(email="refterm@example.test").exists()


@pytest.mark.django_db
def test_registration_with_terms_creates_student_and_signs_in(client):
    response = client.post(reverse("register"), {
        "first_name": "Regina",
        "last_name": "Redesign",
        "email": "regina@example.test",
        "password1": "curved-harbour-tariff",
        "password2": "curved-harbour-tariff",
        "terms_accepted": "on",
    })
    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    user = User.objects.get(email="regina@example.test")
    assert user.student_id and user.username == user.student_id
    assert user.groups.filter(name="Student").exists()


@pytest.mark.django_db
def test_sidebar_drawer_scrolls_so_account_chip_stays_reachable(client):
    staff = User.objects.create_user(username="sidebar-scroll", email="ss@example.test", password="test-password", is_staff=True)
    client.force_login(staff)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="nav-sidebar"' in body
    assert "overflow-y-auto" in body
    # The account chip with theme and sign-out lives at the sidebar bottom.
    assert "Log out" in body
