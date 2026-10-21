"""The learner's credential-management page.

The page is honest about what the backend knows: the Student ID signs in to
the simulator, the password was shown exactly once and lives only as a hash
(so it is never re-displayed), and renewal requests ride the existing
reset-request field the instructor roster already surfaces.
"""

from datetime import timedelta

from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest

from django.contrib.auth.hashers import make_password

from accounts.models import SimulatorCredential, User
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion


@pytest.fixture
def student(db):
    user = User.objects.create_user(username="cred-page", email="cred-page@example.test", password="test-password", first_name="Cred")
    disclaimer = DisclaimerVersion.objects.create(version=1, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    return user


def _issue(student, *, issued_days_ago=20, expires_in_days=10):
    if not student.student_id:
        # issue() allocates a Student ID alongside the credential.
        student.student_id = "CRE00001/26"
        student.save(update_fields=("student_id",))
    credential, _ = SimulatorCredential.objects.get_or_create(user=student)
    now = timezone.now()
    credential.issued_at = now - timedelta(days=issued_days_ago)
    credential.expires_at = now + timedelta(days=expires_in_days)
    credential.password_hash = make_password(credential.recompute_password())
    credential.save()
    return credential


def _client(client, student):
    client.force_login(student)
    return client


def test_the_page_requires_signing_in(client, db):
    assert client.get(reverse("account-credential")).status_code == 302


def test_without_a_credential_the_page_says_so(client, student):
    _client(client, student)
    html = client.get(reverse("account-credential")).content.decode()
    assert "No simulator credential yet" in html
    assert "Not issued" in html


def test_an_active_credential_shows_status_username_and_never_the_password(client, student):
    credential = _issue(student)
    credential.revealed_at = timezone.now()  # the student already had their one view
    credential.save()
    _client(client, student)
    response = client.get(reverse("account-credential"))
    html = response.content.decode()

    assert "Your credential is active" in html
    assert student.student_id in html  # the simulator username
    assert "Copy" in html
    assert "••••••••••••" in html
    assert "shown once" in html.lower()  # the password cannot be re-displayed
    assert credential.recompute_password() not in html
    # The renewal window is not open yet.
    assert "Renewal requests open" in html
    assert 'value="request-renewal"' not in html


def test_an_expiring_credential_opens_the_renewal_form(client, student):
    _issue(student, expires_in_days=3)
    _client(client, student)
    html = client.get(reverse("account-credential")).content.decode()
    assert "expires in 3 days" in html
    assert 'value="request-renewal"' in html
    assert "I forgot my password" in html

    response = client.post(
        reverse("account-credential"),
        {"action": "request-renewal", "reason": "forgot", "note": "Practical session on Monday."},
    )
    assert response.status_code == 302
    credential = SimulatorCredential.objects.get(user=student)
    assert credential.reset_requested_at is not None
    assert credential.reset_reason == "forgot"
    assert credential.reset_note == "Practical session on Monday."

    html = client.get(reverse("account-credential")).content.decode()
    assert "Instructor review" in html
    assert "Cancel request" in html


def test_an_expired_credential_allows_the_request_too(client, student):
    _issue(student, expires_in_days=-2)
    _client(client, student)
    html = client.get(reverse("account-credential")).content.decode()
    assert "Your credential has expired" in html
    assert 'value="request-renewal"' in html


def test_a_request_made_out_of_window_is_refused(client, student):
    _issue(student, expires_in_days=20)
    _client(client, student)
    response = client.post(
        reverse("account-credential"),
        {"action": "request-renewal", "reason": "expiring", "note": ""},
    )
    assert response.status_code == 302
    credential = SimulatorCredential.objects.get(user=student)
    assert credential.reset_requested_at is None


def test_a_pending_request_can_be_cancelled(client, student):
    credential = _issue(student, expires_in_days=3)
    credential.reset_requested_at = timezone.now()
    credential.reset_reason = "expiring"
    credential.save()

    _client(client, student)
    response = client.post(reverse("account-credential"), {"action": "cancel-renewal"})
    assert response.status_code == 302
    credential.refresh_from_db()
    assert credential.reset_requested_at is None
    assert credential.reset_reason == ""


def test_the_settings_and_dashboard_link_to_the_page(client, student):
    _issue(student)
    _client(client, student)
    settings_html = client.get(reverse("account-settings")).content.decode()
    dashboard_html = client.get(reverse("dashboard")).content.decode()
    assert reverse("account-credential") in settings_html
    assert reverse("account-credential") in dashboard_html


def test_the_instructor_roster_shows_the_renewal_reason(client, student, db):
    from django.contrib.auth.models import Group
    from onboarding.models import Enrolment, Programme, ProgrammeVersion

    credential = _issue(student, expires_in_days=2)
    credential.reset_requested_at = timezone.now()
    credential.reset_reason = "forgot"
    credential.save()
    instructor = User.objects.create_user(username="cred-roster-instructor", email="cri@example.test", password="x")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    programme = Programme.objects.create(name="Roster Programme", code="roster-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)

    roster = Client()
    roster.force_login(instructor)
    html = roster.get(reverse("instructor-dashboard")).content.decode()
    assert "Student requested reset" in html
    assert "I forgot my password" in html


def test_a_fresh_issue_reveals_the_password_exactly_once(client, student):
    _issue(student)
    _client(client, student)
    credential = SimulatorCredential.objects.get(user=student)

    first = client.get(reverse("account-credential"))
    password = credential.recompute_password()
    html = first.content.decode()
    assert password in html
    assert "only time it's shown" in html
    assert "Copy" in html

    credential.refresh_from_db()
    assert credential.revealed_at is not None
    assert credential.matches(password)  # the shown password signs in

    second = client.get(reverse("account-credential")).content.decode()
    assert password not in second
    assert "shown once" in second.lower()


def test_the_shown_password_signs_in_to_the_simulator(client, student):
    _issue(student)
    _client(client, student)
    page = client.get(reverse("account-credential")).content.decode()
    credential = SimulatorCredential.objects.get(user=student)
    password = credential.recompute_password()
    assert password in page

    simulator = Client()
    response = simulator.post(reverse("simulator-login"), {"student_id": student.student_id, "password": password}, follow=True)
    assert response.status_code == 200
    assert simulator.session.get("simulator_user_id") == str(student.pk)


def test_reissuing_changes_the_password_and_reopens_the_reveal(client, student):
    _issue(student)
    _client(client, student)
    first_password = SimulatorCredential.objects.get(user=student).recompute_password()
    assert first_password in client.get(reverse("account-credential")).content.decode()

    credential = SimulatorCredential.objects.get(user=student)
    credential.issue()  # the instructor resets a month later
    assert SimulatorCredential.objects.get(user=student).recompute_password() != first_password

    _client(client, student)
    page = client.get(reverse("account-credential")).content.decode()
    assert SimulatorCredential.objects.get(user=student).recompute_password() in page
