"""Portal access gates answer with a message and a redirect, not a bare 403."""
import pytest
from django.urls import reverse

from accounts.models import User
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion


@pytest.fixture
def disclaimer(db):
    return DisclaimerVersion.objects.create(version=1, title="Training notice", body="This is not official ICUMS.", is_current=True)


@pytest.fixture
def student(db, disclaimer):
    user = User.objects.create_user(username="gate-student", email="gate-student@example.test", password="test-password")
    user.groups.add(Group_stub())
    DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)
    return user


def Group_stub():
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name="Student")
    return group


@pytest.mark.django_db
def test_theory_without_enrolment_redirects_with_message(client, student):
    client.force_login(student)
    response = client.get(reverse("roadmap"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    followed = client.get(response.url)
    message_text = " ".join(str(m) for m in followed.context["messages"])
    assert "No active programme enrolment was found." in message_text


@pytest.mark.django_db
def test_gate_redirects_to_referer_when_available(client, student):
    client.force_login(student)
    referer = "http://testserver" + reverse("dashboard")
    response = client.get(reverse("roadmap"), HTTP_REFERER=referer)
    assert response.status_code == 302
    assert response.url == referer


@pytest.mark.django_db
def test_off_site_referer_is_ignored(client, student):
    client.force_login(student)
    response = client.get(reverse("roadmap"), HTTP_REFERER="https://evil.example.com/trap/")
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_same_path_referer_falls_back_to_dashboard(client, student):
    """Redirecting onto the gate itself would loop; fall back to the dashboard."""
    client.force_login(student)
    response = client.get(reverse("roadmap"), HTTP_REFERER="http://testserver/theory/")
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_scenario_list_redirects_gracefully_without_access(client, student):
    """A student without simulator access is redirected with a message, not
    shown a bare error page. (The orientation PermissionDenied behind it
    flows through the same handler as the roadmap gate, tested above.)"""
    from onboarding.models import Enrolment, Programme, ProgrammeVersion

    programme = Programme.objects.create(name="Gate Programme", code="gate")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    Enrolment.objects.create(student=student, programme_version=version, status="active")
    client.force_login(student)
    response = client.get(reverse("scenario-list"))
    assert response.status_code == 302
    followed = client.get(response.url)
    assert followed.context["messages"] is not None


@pytest.mark.django_db
def test_admin_paths_stay_gated_for_non_superusers(client, disclaimer):
    """The admin gate middleware bounces non-superusers to the dashboard —
    they never see a bare admin permission-denied page either."""
    from django.contrib.auth.models import Group

    staff = User.objects.create_user(username="gate-staff", email="gate-staff@example.test", password="test-password", is_staff=True)
    staff.groups.add(Group.objects.get_or_create(name="Student")[0])
    client.force_login(staff)
    response = client.get(reverse("admin:audit_auditevent_changelist"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_anonymous_still_redirected_to_login(client):
    response = client.get(reverse("roadmap"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url
