"""Rich-text lesson images: upload validation, storage, clone copying and cleanup.

Uploaded files live under ``lesson_rich_text/`` (not a public media prefix), each one is
recorded in ``RichTextImage`` so the lesson that owns it is known, and a file is only
deleted when no lesson body in any edition still references it.
"""
from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from learning.models import ContentBlock, Lesson, Module, RichTextImage
from learning.rich_text_images import prune_lesson, store_image
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


@pytest.fixture(autouse=True)
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def author(db):
    instructor = User.objects.create_user(username="image-author", email="image@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=instructor, disclaimer=DisclaimerVersion.objects.create(version=31, title="Image notice", body="Training only.", is_current=True)
    )
    programme = Programme.objects.create(name="Image Programme", code="image-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="image-module", title="Image Module", order=1)
    lesson = Lesson.objects.create(module=module, slug="image-lesson", title="Image Lesson", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Concept", body="Concept text.", order=1)
    return {"instructor": instructor, "programme": programme, "version": version, "module": module, "lesson": lesson, "block": block}


def _png(width=40, height=24):
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), (10, 120, 200)).save(buffer, format="PNG")
    return SimpleUploadedFile("inspection.png", buffer.getvalue(), content_type="image/png")


def _upload(client, author, upload, alt="Inspection flow"):
    return client.post(reverse("lesson-rich-image-upload", args=[author["lesson"].pk]), {"file": upload, "alt": alt})


@pytest.mark.django_db
def test_instructor_uploads_an_image_into_a_draft_lesson(client, author):
    client.force_login(author["instructor"])
    response = _upload(client, author, _png())
    assert response.status_code == 200
    payload = response.json()
    assert payload["url"].startswith("/media/lesson_rich_text/")
    assert payload["alt"] == "Inspection flow"
    assert (payload["width"], payload["height"]) == (40, 24)
    record = RichTextImage.objects.get()
    assert record.lesson_id == author["lesson"].pk
    assert record.created_by_id == author["instructor"].pk
    assert record.file.name.startswith("lesson_rich_text/")


@pytest.mark.django_db
def test_an_oversized_image_is_rejected(client, author):
    client.force_login(author["instructor"])
    response = _upload(client, author, SimpleUploadedFile("big.png", b"x" * (3 * 1024 * 1024), content_type="image/png"))
    assert response.status_code == 400
    assert "2 MB" in response.json()["error"]
    assert RichTextImage.objects.count() == 0


@pytest.mark.django_db
def test_an_svg_or_non_image_is_rejected(client, author):
    client.force_login(author["instructor"])
    svg = SimpleUploadedFile("diagram.svg", b"<svg onload=\"alert(1)\"></svg>", content_type="image/svg+xml")
    response = _upload(client, author, svg)
    assert response.status_code == 400
    assert "JPEG, PNG, WebP or GIF" in response.json()["error"]
    assert RichTextImage.objects.count() == 0


@pytest.mark.django_db
def test_a_large_image_is_downscaled_to_the_maximum_edge(client, author):
    image = store_image(author["lesson"], _png(width=3000, height=1200))
    from PIL import Image

    with Image.open(image.file.path) as opened:
        assert max(opened.size) == 1600


@pytest.mark.django_db
def test_learners_and_published_lessons_cannot_receive_uploads(client, author):
    student = User.objects.create_user(username="image-student", email="image-student@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    Enrolment.objects.create(student=student, programme_version=author["version"], status="active")
    client.force_login(student)
    assert client.post(reverse("lesson-rich-image-upload", args=[author["lesson"].pk]), {"file": _png()}).status_code in (302, 403)

    client.force_login(author["instructor"])
    author["version"].status = ProgrammeVersion.Status.PUBLISHED
    author["version"].save(update_fields=("status",))
    response = client.post(reverse("lesson-rich-image-upload", args=[author["lesson"].pk]), {"file": _png()})
    assert response.status_code == 404


@pytest.mark.django_db
def test_pruning_keeps_a_referenced_image_and_drops_an_unreferenced_one(author):
    keep = store_image(author["lesson"], _png())
    drop = store_image(author["lesson"], _png())
    author["block"].body = f'<figure><img src="{keep.file.url}" alt="Flow"><figcaption>Flow</figcaption></figure>'
    author["block"].save()

    assert prune_lesson(author["lesson"]) == 1
    assert RichTextImage.objects.filter(pk=keep.pk).exists()
    assert not RichTextImage.objects.filter(pk=drop.pk).exists()
    assert not drop.file.storage.exists(drop.file.name)


@pytest.mark.django_db
def test_pruning_never_deletes_a_file_another_lesson_references(author):
    shared = store_image(author["lesson"], _png())
    other = Lesson.objects.create(module=author["module"], slug="other-lesson", title="Other Lesson", order=2)
    ContentBlock.objects.create(lesson=other, heading="Other", body=f'<p><img src="{shared.file.url}" alt="Shared"></p>', order=1)

    assert prune_lesson(author["lesson"]) == 0
    assert shared.file.storage.exists(shared.file.name)


@pytest.mark.django_db
def test_a_new_draft_gets_its_own_copy_of_every_referenced_image(client, author):
    image = store_image(author["lesson"], _png())
    author["block"].body = f'<figure><img src="{image.file.url}" alt="Flow"><figcaption>Flow</figcaption></figure>'
    author["block"].save()
    author["version"].status = ProgrammeVersion.Status.PUBLISHED
    author["version"].published_at = timezone.now()
    author["version"].save(update_fields=("status", "published_at"))
    author["module"].is_published = True
    author["lesson"].is_published = True
    author["module"].save(update_fields=("is_published",))
    author["lesson"].save(update_fields=("is_published",))

    client.force_login(author["instructor"])
    response = client.post(reverse("course-new-draft", args=[author["version"].pk]))
    assert response.status_code == 302
    draft = ProgrammeVersion.objects.exclude(pk=author["version"].pk).get()
    draft_lesson = Lesson.objects.get(module__programme_version=draft, slug=author["lesson"].slug)
    draft_image = RichTextImage.objects.get(lesson=draft_lesson)

    assert draft_image.file.name != image.file.name
    assert draft_image.file.storage.exists(draft_image.file.name)
    body = draft_lesson.blocks.get().body
    assert draft_image.file.name in body and image.file.name not in body

    # Removing the published lesson's image must not blank the draft's copy.
    image.file.delete(save=False)
    image.delete()
    assert draft_image.file.storage.exists(draft_image.file.name)
