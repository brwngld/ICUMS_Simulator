"""Retiring a published course: read-only for instructors, still open to learners.

Retirement is the only close an authoring version with learner history can get —
deleting needs a draft with no enrolments. These pin down what retiring does and,
just as importantly, what it deliberately does not do: it never revokes access.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from learning.models import Module
from onboarding.models import Enrolment, Programme, ProgrammeVersion


@pytest.fixture
def course(db):
    instructor = User.objects.create_user(username="retire-author", email="retire@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    programme = Programme.objects.create(name="Retiring Programme", code="retire-programme")
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED, published_at=timezone.now()
    )
    Module.objects.create(programme_version=version, code="retire-one", title="Module One", order=1, is_published=True)
    return {"instructor": instructor, "programme": programme, "version": version}


def _retire(client, course, version=None):
    client.force_login(course["instructor"])
    return client.post(reverse("course-retire", args=[(version or course["version"]).pk]))


@pytest.mark.django_db
def test_retiring_a_published_course_makes_it_retired(client, course):
    response = _retire(client, course)

    assert response.status_code == 302
    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.RETIRED


@pytest.mark.django_db
def test_a_draft_is_closed_by_publishing_or_deleting_not_retiring(client, course):
    course["version"].status = ProgrammeVersion.Status.DRAFT
    course["version"].save(update_fields=("status",))

    _retire(client, course)

    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_retiring_twice_leaves_the_course_retired(client, course):
    _retire(client, course)
    _retire(client, course)

    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.RETIRED


@pytest.mark.django_db
def test_retiring_leaves_an_enrolled_learner_working_through_it(client, course):
    """The enrolment, not the version status, is what grants access."""
    learner = User.objects.create_user(username="retire-learner", email="rl@example.test", password="test-password")
    learner.groups.add(Group.objects.get(name="Student"))
    Enrolment.objects.create(student=learner, programme_version=course["version"])

    _retire(client, course)

    assert course["version"].enrolments.filter(student=learner, status=Enrolment.Status.ACTIVE).exists()
    assert course["version"].modules.filter(is_published=True).exists()


@pytest.mark.django_db
def test_only_a_published_course_offers_the_retire_button(client, course):
    client.force_login(course["instructor"])
    retire_url = reverse("course-retire", args=[course["version"].pk])
    offered = lambda: retire_url in client.get(reverse("course-builder")).content.decode()

    assert offered()
    _retire(client, course)
    assert not offered()


@pytest.mark.django_db
def test_an_instructor_cannot_retire_through_a_get(client, course):
    client.force_login(course["instructor"])

    response = client.get(reverse("course-retire", args=[course["version"].pk]))

    assert response.status_code == 405
    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.PUBLISHED
