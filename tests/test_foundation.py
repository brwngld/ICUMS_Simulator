import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from audit.models import AuditEvent


@pytest.mark.django_db
def test_initial_roles_are_seeded():
    assert set(Group.objects.values_list("name", flat=True)) >= {
        "Student",
        "Instructor",
        "Administrator",
    }


@pytest.mark.django_db
def test_user_can_hold_multiple_roles():
    user = User.objects.create_user(username="trainer", email="trainer@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"), Group.objects.get(name="Administrator"))
    assert set(user.groups.values_list("name", flat=True)) == {"Instructor", "Administrator"}


@pytest.mark.django_db
def test_dashboard_requires_authentication(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


@pytest.mark.django_db
def test_authenticated_dashboard_has_training_notice(client):
    user = User.objects.create_user(username="student", email="student@example.test", password="test-password")
    client.force_login(user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"TRAINING SIMULATOR" in response.content
    assert b"NOT OFFICIAL ICUMS" in response.content


@pytest.mark.django_db
def test_successful_login_is_audited(client):
    user = User.objects.create_user(username="audited", email="audited@example.test", password="test-password")
    response = client.post(reverse("login"), {"username": "audited", "password": "test-password"})
    assert response.status_code == 302
    assert AuditEvent.objects.filter(actor=user, action_code="account.login").exists()
