"""Stage 1 — Instructor Demonstration Studio integration.

Covers instructor gating, draft-lesson scoping, page content (prototype
landmarks, honest non-operational recording markers), the lesson-editor
entry link, and that nothing persists: the studio is a GET-only, client-side
demonstration surface.
"""
import pytest
from django.test import Client
from django.urls import reverse

from accounts.models import User
from django.contrib.auth.models import Group
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    PracticalStep,
    SimulatorRecordCreation,
)


def _instructor(db, username="studio-instructor"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def _student(db, username="studio-student"):
    return User.objects.create_user(username=username, email=f"{username}@example.test", password="x")


def _draft_lesson_world(db, username="studio-instructor"):
    """Instructor + draft course/module/lesson/step, mirroring the builder."""
    instructor = _instructor(db, username)
    programme_version = _programme_version(db)
    course = HybridCourse.objects.create(
        programme_version=programme_version, code=f"{username}-c", title=f"{username} course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{username}-m", title=f"{username} module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{username}-lesson", title=f"{username} lesson", order=1,
        summary="Summary.", theory="<p>Theory.</p>",
    )
    PracticalStep.objects.create(
        lesson=lesson, key=f"{username}-step", title=f"{username} step",
        instruction="Create the record.", outcome="The record is saved.",
        screen="single-window-overview", order=1,
    )
    return {"instructor": instructor, "version": programme_version,
            "course": course, "module": module, "lesson": lesson}


def _programme_version(db):
    from onboarding.models import Programme, ProgrammeVersion

    programme = Programme.objects.create(
        name="Studio programme", code="studio", learning_track=Programme.Track.HYBRID,
    )
    return ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)


def _studio_url(lesson):
    return reverse("hybrid-lesson-demonstration-studio", args=[lesson.pk])


def _editor_url(lesson):
    return reverse("hybrid-lesson-edit", args=[lesson.pk])


@pytest.mark.django_db
def test_instructor_sees_the_studio_for_a_draft_lesson(db):
    world = _draft_lesson_world(db)
    client = Client()
    client.force_login(world["instructor"])

    response = client.get(_studio_url(world["lesson"]))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Instructor Demonstration Studio" in html
    # Prototype landmarks: three tabs, mock-simulator disclaimer, capture
    # timeline, review steps, student preview.
    assert "1 · Demonstrate" in html
    assert "2 · Review steps" in html
    assert "3 · Student preview" in html
    assert "TRAINING SIMULATOR — NOT OFFICIAL ICUMS" in html
    assert "Capture timeline" in html
    assert "Review captured journey" in html
    assert "Student workspace preview" in html
    # Honest non-operational markers.
    assert "RECORDING NOT YET IMPLEMENTED" in html
    assert "no backend records are created" in html.lower() or "No backend records are created" in html
    # Lesson identity in the breadcrumb.
    assert world["lesson"].title in html


@pytest.mark.django_db
def test_anonymous_users_are_redirected_to_login(db):
    world = _draft_lesson_world(db)
    client = Client()

    response = client.get(_studio_url(world["lesson"]))

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"] or response["Location"] == "/"


@pytest.mark.django_db
def test_students_cannot_open_the_studio(db):
    world = _draft_lesson_world(db)
    student = _student(db, "studio-no")
    client = Client()
    client.force_login(student)

    response = client.get(_studio_url(world["lesson"]))

    # The project's 403 handler redirects authenticated portal users with a
    # warning instead of rendering a bare 403 page.
    assert response.status_code == 302


@pytest.mark.django_db
def test_only_draft_lessons_open_the_studio(db):
    """Draft-scoped like the rest of the builder: a published lesson's studio
    is a 404, mirroring _draft_lesson."""
    world = _draft_lesson_world(db)
    from onboarding.models import ProgrammeVersion

    world["lesson"].module.course.programme_version.status = ProgrammeVersion.Status.PUBLISHED
    world["lesson"].module.course.programme_version.save(update_fields=("status",))
    client = Client()
    client.force_login(world["instructor"])

    response = client.get(_studio_url(world["lesson"]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_the_lesson_editor_links_to_the_studio(db):
    world = _draft_lesson_world(db)
    client = Client()
    client.force_login(world["instructor"])

    html = client.get(_editor_url(world["lesson"])).content.decode()

    assert _studio_url(world["lesson"]) in html
    assert "Open Demonstration Studio" in html


@pytest.mark.django_db
def test_the_studio_persists_nothing(db):
    """The studio is a GET-only, client-side surface: no GET mutation, no
    evidence rows, no demonstration records."""
    world = _draft_lesson_world(db)
    client = Client()
    client.force_login(world["instructor"])

    response = client.get(_studio_url(world["lesson"]))
    client.post(_studio_url(world["lesson"]))

    assert response.status_code == 200
    assert SimulatorRecordCreation.objects.count() == 0
    # POST is not allowed on a GET-only page.
    assert client.post(_studio_url(world["lesson"])).status_code in (403, 405)
