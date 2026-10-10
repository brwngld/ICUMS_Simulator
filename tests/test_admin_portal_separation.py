"""Admin landing, View site, Advanced Admin link, and portal breadcrumbs.

Covers the admin/portal separation: administrators sign in to the Unfold
admin dashboard, reach the portal through "View site" with their own
session and an "Advanced Admin" sidebar link back, and students/tutors
never see that link.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Programme, ProgrammeVersion


@pytest.fixture
def disclaimer(db):
    return DisclaimerVersion.objects.create(version=1, title="Training notice", body="This is not official ICUMS.", is_current=True)


def _accept(user, disclaimer):
    DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)


@pytest.fixture
def student(db, disclaimer):
    user = User.objects.create_user(username="portal-student", email="student@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    _accept(user, disclaimer)
    return user


@pytest.fixture
def tutor(db, disclaimer):
    user = User.objects.create_user(username="portal-tutor", email="tutor@example.test", password="test-password", is_staff=True)
    user.groups.add(Group.objects.get(name="Instructor"))
    _accept(user, disclaimer)
    return user


@pytest.fixture
def admin_user(db, disclaimer):
    user = User.objects.create_superuser(username="portal-admin", email="admin@example.test", password="test-password")
    _accept(user, disclaimer)
    return user


@pytest.fixture
def programme(db):
    programme = Programme.objects.create(name="Separation Programme", code="separation")
    ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    return programme


def test_admin_login_lands_on_admin_dashboard(client, admin_user):
    response = client.post(reverse("login"), {"username": "portal-admin", "password": "test-password"})
    assert response.status_code == 302
    assert response.url == reverse("admin:index")


def test_student_login_lands_on_portal_dashboard(client, student):
    response = client.post(reverse("login"), {"username": "portal-student", "password": "test-password"})
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


def test_login_honours_explicit_next_for_staff(client, admin_user):
    response = client.post(reverse("login") + "?next=/accounts/password-change/", {"username": "portal-admin", "password": "test-password"})
    assert response.status_code == 302
    assert response.url == "/accounts/password-change/"


def test_view_site_link_present_for_admin(client, admin_user):
    client.force_login(admin_user)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 200
    assert b"View site" in response.content
    assert 'href="/"' in response.content.decode()


def test_admin_portal_sidebar_shows_student_navigation_and_advanced_admin(client, admin_user, programme):
    client.force_login(admin_user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Advanced Admin" in content
    assert "Simulator sandbox" in content
    # The admin changelist navigation must not leak into the portal.
    assert "Simulator credentials" not in content


def test_admin_pages_keep_admin_navigation(client, admin_user):
    client.force_login(admin_user)
    response = client.get(reverse("admin:index"))
    content = response.content.decode()
    assert "Advanced Admin" not in content
    assert "Simulator credentials" in content


def test_student_never_sees_advanced_admin(client, student, programme):
    client.force_login(student)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert "Advanced Admin" not in response.content.decode()


def test_tutor_never_sees_advanced_admin(client, tutor, programme):
    client.force_login(tutor)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert "Advanced Admin" not in response.content.decode()


def test_student_cannot_reach_admin_changelist(client, student):
    client.force_login(student)
    response = client.get(reverse("admin:audit_auditevent_changelist"))
    assert response.status_code in (302, 403)


def test_instructor_student_detail_breadcrumb(client, tutor, student, programme):
    from onboarding.models import Enrolment

    enrolment = Enrolment.objects.create(student=student, programme_version=ProgrammeVersion.objects.first())
    tutor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(tutor)
    response = client.get(reverse("instructor-student-detail", args=[enrolment.pk]))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'href="/instructor/"' in content
    assert "Instructor" in content
    assert student.get_full_name() in content or student.username in content


def test_dashboard_has_no_breadcrumb_trail(client, student, programme):
    client.force_login(student)
    response = client.get(reverse("dashboard"))
    content = response.content.decode()
    # Top-level pages keep a plain title like the admin overview.
    assert "breadcrumbs" not in response.context or response.context["breadcrumbs"] == []


def test_course_builder_detail_renders_full_shell(client, tutor, student, programme):
    """Regression: this page once rendered without the admin chrome context,
    which left the header (sidebar toggle, breadcrumbs) empty."""
    from learning.models import Module
    from onboarding.models import Enrolment

    version = ProgrammeVersion.objects.filter(status=ProgrammeVersion.Status.DRAFT).first() or ProgrammeVersion.objects.create(
        programme=programme, version=2, status=ProgrammeVersion.Status.DRAFT
    )
    Module.objects.create(programme_version=version, code="draft-module", title="Draft Module", order=1)
    enrolment = Enrolment.objects.create(student=student, programme_version=ProgrammeVersion.objects.first())
    client.force_login(tutor)
    response = client.get(reverse("course-builder-detail", args=[version.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "sidebarToggle" in html                      # sidebar hide/show control
    assert 'href="/instructor/"' in html                # breadcrumb trail
    assert version.programme.name in html
    assert "Course builder" in html
    assert response.context["breadcrumbs"], "expected a breadcrumb trail"
