"""Optional module cover images: instructor upload/replace/remove and the
learner surfaces that show them. Removing a cover must never touch progress,
lessons or assessment state."""
import base64

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import User
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def author(db):
    instructor = User.objects.create_user(username="cover-author", email="cover@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=instructor,
        disclaimer=DisclaimerVersion.objects.create(version=9, title="Cover notice", body="Training only.", is_current=True),
    )
    programme = Programme.objects.create(name="Cover Programme", code="cover-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="covered-module", title="Covered Module", order=1)
    Lesson.objects.create(module=module, slug="covered-lesson", title="Covered Lesson", order=1, is_published=True)
    ContentBlock.objects.create(lesson=module.lessons.first(), heading="Body", body="Lesson body.")
    return {"instructor": instructor, "programme": programme, "version": version, "module": module}


def _upload(name="cover.png"):
    return SimpleUploadedFile(name, PNG_BYTES, content_type="image/png")


def _publish_for_learner(author):
    author["module"].is_published = True
    author["module"].save(update_fields=("is_published",))
    author["version"].status = ProgrammeVersion.Status.PUBLISHED
    author["version"].save(update_fields=("status",))
    learner = User.objects.create_user(username="cover-learner", email="learner@example.test", password="test-password")
    learner.groups.add(Group.objects.get(name="Student"))
    enrolment = Enrolment.objects.create(student=learner, programme_version=author["version"])
    DisclaimerAcceptance.objects.create(
        user=learner,
        disclaimer=DisclaimerVersion.objects.create(version=10, title="Learner notice", body="Training only.", is_current=True),
    )
    return learner


@pytest.mark.django_db
def test_instructor_uploads_module_cover(client, author):
    client.force_login(author["instructor"])
    response = client.post(
        reverse("module-edit", args=[author["module"].pk]),
        {"title": "Covered Module", "description": "", "cover_image": _upload()},
    )
    assert response.status_code == 302
    author["module"].refresh_from_db()
    assert author["module"].cover_image.name.startswith("module_covers/cover")
    assert author["module"].cover_image.storage.exists(author["module"].cover_image.name)


@pytest.mark.django_db
def test_replacing_and_removing_cover_deletes_the_old_file(client, author):
    client.force_login(author["instructor"])
    client.post(reverse("module-edit", args=[author["module"].pk]), {"title": "Covered Module", "cover_image": _upload("first.png")})
    author["module"].refresh_from_db()
    first_name = author["module"].cover_image.name

    client.post(reverse("module-edit", args=[author["module"].pk]), {"title": "Covered Module", "cover_image": _upload("second.png")})
    author["module"].refresh_from_db()
    assert author["module"].cover_image.name != first_name
    assert not author["module"].cover_image.storage.exists(first_name)

    client.post(reverse("module-edit", args=[author["module"].pk]), {"title": "Covered Module", "clear_cover_image": "on"})
    author["module"].refresh_from_db()
    assert not author["module"].cover_image
    assert author["module"].lessons.count() == 1
    assert author["module"].lessons.first().blocks.count() == 1


@pytest.mark.django_db
def test_cover_omitted_from_post_leaves_existing_image(client, author):
    client.force_login(author["instructor"])
    client.post(reverse("module-edit", args=[author["module"].pk]), {"title": "Covered Module", "cover_image": _upload()})
    author["module"].refresh_from_db()
    stored = author["module"].cover_image.name

    client.post(reverse("module-edit", args=[author["module"].pk]), {"title": "Renamed Module"})
    author["module"].refresh_from_db()
    assert author["module"].title == "Renamed Module"
    assert author["module"].cover_image.name == stored


@pytest.mark.django_db
def test_learner_sees_cover_on_module_and_course_overview(client, author):
    author["module"].cover_image = _upload()
    author["module"].save()
    author["programme"].cover_image = _upload("programme.png")
    author["programme"].save()
    learner = _publish_for_learner(author)
    client.force_login(learner)

    module_page = client.get(reverse("module-overview", args=[author["module"].code]))
    assert module_page.status_code == 200
    assert b"mod-hero-image" in module_page.content
    assert author["module"].cover_image.url.encode() in module_page.content
    assert b"image/default-module.png" not in module_page.content

    course_page = client.get(reverse("roadmap"))
    assert course_page.status_code == 200
    assert b"course-module-thumb" in course_page.content
    assert author["programme"].cover_image.url.encode() in course_page.content
    assert b"image/default-course.png" not in course_page.content


@pytest.mark.django_db
def test_learner_without_cover_sees_no_broken_image(client, author):
    learner = _publish_for_learner(author)
    client.force_login(learner)
    module_page = client.get(reverse("module-overview", args=[author["module"].code]))
    assert b"image/default-module.png" in module_page.content
    assert b'src=""' not in module_page.content
    course_page = client.get(reverse("roadmap"))
    assert b"image/default-course.png" in course_page.content
    assert b"course-module-thumb" not in course_page.content
    assert b"course-module-number" in course_page.content
