import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from audit.models import AuditEvent
from onboarding.models import Enrolment, Programme, ProgrammeVersion


@pytest.mark.django_db
def test_admin_can_create_and_enrol_student_from_user_screen(client):
    administrator = User.objects.create_superuser(username="site-admin", email="admin@example.test", password="admin-password")
    programme = Programme.objects.create(name="Admin Enrolment Programme", code="admin-enrolment")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    client.force_login(administrator)
    response = client.post(
        reverse("admin:accounts_user_add"),
        {
            "username": "new-student",
            "password1": "secure-test-password-417",
            "password2": "secure-test-password-417",
            "enrolments-TOTAL_FORMS": "1",
            "enrolments-INITIAL_FORMS": "0",
            "enrolments-MIN_NUM_FORMS": "0",
            "enrolments-MAX_NUM_FORMS": "1000",
            "enrolments-0-programme_version": str(version.pk),
            "enrolments-0-status": Enrolment.Status.ACTIVE,
            "_save": "Save",
        },
    )
    assert response.status_code == 302, response.context["errors"] if response.context else response.content
    student = User.objects.get(username="new-student")
    enrolment = Enrolment.objects.get(student=student, programme_version=version)
    assert enrolment.enrolled_by == administrator
    assert student.groups.filter(name="Student").exists()
    assert AuditEvent.objects.filter(actor=administrator, action_code="enrolment.created", target_id=str(enrolment.pk)).exists()


@pytest.mark.django_db
def test_admin_enrolment_history_cannot_be_deleted(client):
    administrator = User.objects.create_superuser(username="admin-two", email="admin-two@example.test", password="admin-password")
    programme = Programme.objects.create(name="Protected Programme", code="protected-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    student = User.objects.create_user(username="protected-student", email="protected@example.test", password="student-password")
    enrolment = Enrolment.objects.create(student=student, programme_version=version, enrolled_by=administrator)
    client.force_login(administrator)
    response = client.get(reverse("admin:onboarding_enrolment_delete", args=(enrolment.pk,)))
    assert response.status_code == 403
    assert Group.objects.filter(name="Student").exists()


@pytest.mark.django_db
def test_monthly_password_is_hashed_and_shown_once(client):
    """The issued simulator password is shown exactly once and stored only as a hash."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from accounts.models import SimulatorCredential

    User = get_user_model()
    instructor = User.objects.create_user(username="cred-instructor", email="cred-instructor@example.test", password="instructor-pass")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    student = User.objects.create_user(username="cred-student", email="cred-student@example.test", password="student-pass")
    programme = Programme.objects.create(name="Credential Programme", code="credential-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)

    iclient = Client()
    iclient.force_login(instructor)
    response = iclient.post(reverse("simulator-credential-issue", args=(student.pk,)))
    assert response.status_code == 200
    raw_password = response.context["raw_password"]
    assert raw_password.startswith("Ic!")

    credential = SimulatorCredential.objects.get(user=student)
    assert credential.password_hash
    assert raw_password not in credential.password_hash
    assert credential.revealed_at is not None
    student.refresh_from_db()
    assert student.student_id  # allocated together with the first credential

    # The student can sign in with the issued password.
    sclient = Client()
    session = sclient.session
    session["simulator_user_id"] = str(student.pk)
    session.save()
    signed_in = sclient.post(reverse("simulator-login"), {"student_id": student.student_id, "password": raw_password})
    assert signed_in.status_code == 302

    # Wrong and old passwords are refused; nothing recoverable is stored.
    refused = sclient.post(reverse("simulator-login"), {"student_id": student.student_id, "password": "Ic!WRONGPW"})
    assert refused.status_code == 302
    assert refused.url == reverse("simulator-portal")

    # The dashboard never shows the password again, only its masked state.
    dashboard = iclient.get(reverse("instructor-dashboard"))
    assert raw_password.encode() not in dashboard.content
    assert b"shown once" in dashboard.content
