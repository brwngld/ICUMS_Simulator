"""Login-page redesign regression tests.

The page is a standalone Unfold-design-system document: sidebar-identical
branding (indigo gear square, "ICUMS Simulator / Training administration"),
Unfold field/button components, its own accessibility contract (lang, one
main, one h1, skip link) — and none of the legacy app-shell chrome or
marketing copy. The authentication mechanism, validation copy, redirects
and audit behaviour are unchanged.
"""

import pytest
from django.urls import reverse

from accounts.models import User


@pytest.mark.django_db
def test_login_page_is_built_on_the_unfold_design_system(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    body = response.content.decode()
    # Unfold assets and palette, not the legacy app shell.
    assert "unfold/css/styles.css" in body
    assert "unfold-theme-colors" in body
    assert "app.css" not in body
    assert "app-shell.js" not in body
    # Sidebar-identical branding: gear square + exact wording.
    assert "material-symbols-outlined md-18\">settings" in body
    assert "ICUMS Simulator" in body
    assert "Training administration" in body
    # Inputs carry Unfold's BASE_INPUT_CLASSES (same as the admin login).
    assert "rounded-default" in body and "focus:outline-primary-600" in body
    # How-the-training-works tiles.
    for word in ("Learn", "Practise", "Progress"):
        assert f'>{word}</span>' in body


@pytest.mark.django_db
def test_login_page_drops_the_legacy_shell_and_marketing(client):
    response = client.get(reverse("login"))
    body = response.content.decode()
    assert "Learning simulator" not in body          # app-shell brand caption
    assert "Your next chapter" not in body           # legacy marketing copy
    assert "Learn. Practise. Progress." not in body
    assert "auth-story" not in body                  # legacy stylesheet hooks


@pytest.mark.django_db
def test_login_preserves_labels_notice_and_register_link(client):
    response = client.get(reverse("login"))
    body = response.content.decode()
    assert '<label for="id_username"' in body
    assert '<label for="id_password"' in body
    assert "not official ICUMS" in body
    assert "Register for a learning account" in body


@pytest.mark.django_db
def test_login_still_succeeds_and_redirects(client):
    User.objects.create_user(username="login-redesign", email="lr@example.test", password="test-password")
    response = client.post(reverse("login"), {"username": "login-redesign", "password": "test-password"})
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_login_still_fails_with_the_same_message(client):
    response = client.post(reverse("login"), {"username": "nobody", "password": "wrong"})
    assert response.status_code == 200
    assert "Your username or password was not accepted." in response.content.decode()
