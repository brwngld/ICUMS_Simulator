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
