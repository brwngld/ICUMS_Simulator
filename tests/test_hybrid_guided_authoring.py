"""Guided Material Study authoring — materials, knowledge checks, and the
surfaces that render them.

The prototype's guided-lesson flow merged into the production builder: the
lesson editor's materials stage replaces the old refusal, the studio URL
becomes a gate pointing back at the editor, and the student workspace lists
materials beside the theory with optional (never completion-gating) checks.
"""
import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from accounts.models import User
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    KnowledgeCheck,
    LessonAttempt,
    LessonMaterial,
)
from hybrid.publishing import clone_to_draft, lesson_issues
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _user(db, username):
    return User.objects.create_user(username=username, email=f"{username}@example.test", password="x")


def _instructor(db, username="guided-instructor"):
    user = _user(db, username)
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def _guided_world(db, username="guided-instructor", status=ProgrammeVersion.Status.DRAFT):
    """Instructor plus a programme edition holding one guided lesson."""
    instructor = _instructor(db, username)
    programme = Programme.objects.create(
        name=f"Guided {username}", code=username, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=status)
    published = status == ProgrammeVersion.Status.PUBLISHED
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{username}-c", title=f"{username} course", order=1,
        is_published=published,
    )
    module = HybridModule.objects.create(
        course=course, code=f"{username}-m", title=f"{username} module", order=1, is_published=published,
    )
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{username}-l", title="Reading the tariff", order=1,
        kind=HybridLesson.Kind.GUIDED_MATERIAL_STUDY, is_published=published,
        summary="Read the guide beside the theory.", theory="<p>The tariff explained.</p>",
    )
    return {"instructor": instructor, "version": version, "module": module, "lesson": lesson}


def _editor_url(lesson):
    return reverse("hybrid-lesson-edit", args=[lesson.pk])


def _activities_url(lesson):
    return f"{_editor_url(lesson)}?tab=activities"


def _check_fields(check, prompt="Which chapter covers live animals?", options=None, answer="0"):
    options = options if options is not None else ["Chapter 1", "Chapter 84", "", ""]
    fields = {
        "action": "save_check",
        "check_id": str(check.pk),
        f"check-{check.pk}-prompt": prompt,
        f"check-{check.pk}-answer": answer,
    }
    for slot, text in enumerate(options):
        fields[f"check-{check.pk}-option_{slot}"] = text
    return fields


def _pdf(name="guide.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 a tiny guide", content_type="application/pdf")


# --- Supporting materials ------------------------------------------------------


@pytest.mark.django_db
def test_material_upload_stores_the_file(client, db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), {"action": "add_material", "file": _pdf()})

    assert response.status_code == 302
    assert response["Location"] == _activities_url(world["lesson"])
    material = LessonMaterial.objects.get(lesson=world["lesson"])
    assert material.name() == "guide.pdf"
    assert material.file.name.startswith("lesson_materials/")
    assert (tmp_path / material.file.name).is_file()
    assert "KB" in material.size_display()


@pytest.mark.django_db
def test_material_upload_refuses_unsafe_extensions(client, db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), {
        "action": "add_material",
        "file": SimpleUploadedFile("page.html", b"<script>alert(1)</script>", content_type="text/html"),
    }, follow=True)

    assert not LessonMaterial.objects.filter(lesson=world["lesson"]).exists()
    assert "Attach a document or image" in response.content.decode()


@pytest.mark.django_db
def test_material_upload_refuses_oversized_files(client, db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    client.force_login(world["instructor"])
    oversized = SimpleUploadedFile("big.pdf", b"x" * (25 * 1024 * 1024 + 1), content_type="application/pdf")

    response = client.post(_editor_url(world["lesson"]), {"action": "add_material", "file": oversized}, follow=True)

    assert not LessonMaterial.objects.filter(lesson=world["lesson"]).exists()
    assert "25 MB limit" in response.content.decode()


@pytest.mark.django_db
def test_materials_move_and_renumber_on_delete(client, db):
    world = _guided_world(db)
    first = LessonMaterial.objects.create(lesson=world["lesson"], file="lesson_materials/a.pdf", order=1)
    second = LessonMaterial.objects.create(lesson=world["lesson"], file="lesson_materials/b.pdf", order=2)
    client.force_login(world["instructor"])

    client.post(_editor_url(world["lesson"]), {
        "action": "move_material", "material_id": str(second.pk), "direction": "up",
    })
    first.refresh_from_db()
    second.refresh_from_db()
    assert (second.order, first.order) == (1, 2)

    client.post(_editor_url(world["lesson"]), {"action": "delete_material", "material_id": str(second.pk)})
    assert not LessonMaterial.objects.filter(pk=second.pk).exists()
    first.refresh_from_db()
    assert first.order == 1


@pytest.mark.django_db
def test_deleting_a_material_row_keeps_the_shared_file(client, db, tmp_path, settings):
    """A draft cloned from a published edition shares the blob: removing the
    row must never take the file with it."""
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    client.force_login(world["instructor"])
    client.post(_editor_url(world["lesson"]), {"action": "add_material", "file": _pdf()})
    material = LessonMaterial.objects.get(lesson=world["lesson"])
    stored = tmp_path / material.file.name

    client.post(_editor_url(world["lesson"]), {"action": "delete_material", "material_id": str(material.pk)})

    assert not LessonMaterial.objects.filter(pk=material.pk).exists()
    assert stored.is_file()


# --- Knowledge checks ----------------------------------------------------------


@pytest.mark.django_db
def test_add_check_creates_an_editable_card(client, db):
    world = _guided_world(db)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), {"action": "add_check"}, follow=True)

    check = KnowledgeCheck.objects.get(lesson=world["lesson"])
    assert check.options == ["", "", "", ""]
    assert check.order == 1
    html = response.content.decode()
    assert f'id="check-{check.pk}"' in html
    assert "Save check" in html


@pytest.mark.django_db
def test_save_check_stores_question_options_and_answer(client, db):
    world = _guided_world(db)
    check = KnowledgeCheck.objects.create(lesson=world["lesson"], options=["", "", "", ""], order=1)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), _check_fields(check, answer="1"))

    assert response.status_code == 302
    check.refresh_from_db()
    assert check.prompt == "Which chapter covers live animals?"
    assert check.options == ["Chapter 1", "Chapter 84", "", ""]
    assert check.answer_index == 1


@pytest.mark.django_db
def test_save_check_refuses_a_single_option(client, db):
    world = _guided_world(db)
    check = KnowledgeCheck.objects.create(lesson=world["lesson"], options=["", "", "", ""], order=1)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), _check_fields(check, options=["Only one", "", "", ""]))

    assert response.status_code == 400
    assert "at least two options" in response.content.decode()
    check.refresh_from_db()
    assert check.prompt == ""


@pytest.mark.django_db
def test_save_check_refuses_a_blank_correct_answer(client, db):
    world = _guided_world(db)
    check = KnowledgeCheck.objects.create(lesson=world["lesson"], options=["", "", "", ""], order=1)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), _check_fields(check, answer="2"))

    assert response.status_code == 400
    assert "Mark a filled-in option" in response.content.decode()
    check.refresh_from_db()
    assert check.prompt == ""


@pytest.mark.django_db
def test_checks_move_and_renumber_on_delete(client, db):
    world = _guided_world(db)
    first = KnowledgeCheck.objects.create(lesson=world["lesson"], prompt="One", options=["a", "b"], order=1)
    second = KnowledgeCheck.objects.create(lesson=world["lesson"], prompt="Two", options=["a", "b"], order=2)
    client.force_login(world["instructor"])

    client.post(_editor_url(world["lesson"]), {"action": "move_check", "check_id": str(first.pk), "direction": "down"})
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.order, second.order) == (2, 1)

    client.post(_editor_url(world["lesson"]), {"action": "delete_check", "check_id": str(first.pk)})
    assert not KnowledgeCheck.objects.filter(pk=first.pk).exists()
    second.refresh_from_db()
    assert second.order == 1


@pytest.mark.django_db
def test_guided_actions_stay_instructor_only(client, db):
    world = _guided_world(db)
    student = _user(db, "guided-student")
    student_client = Client()
    student_client.force_login(student)

    response = student_client.post(_editor_url(world["lesson"]), {"action": "add_check"})

    assert response.status_code == 302
    assert not KnowledgeCheck.objects.filter(lesson=world["lesson"]).exists()


@pytest.mark.django_db
def test_step_actions_are_refused_on_a_guided_lesson(client, db):
    """A step on a guided lesson would be invisible in its workspace yet still
    demanded by completion — the editor refuses the action outright."""
    from hybrid.models import PracticalStep

    world = _guided_world(db)
    client.force_login(world["instructor"])

    response = client.post(_editor_url(world["lesson"]), {"action": "add_step"}, follow=True)

    assert not PracticalStep.objects.filter(lesson=world["lesson"]).exists()
    assert "no practical activities" in response.content.decode()
    # The inert add-step form does not reach the guided page either.
    assert 'id="add-step-form"' not in response.content.decode()


# --- Readiness and cloning -----------------------------------------------------


@pytest.mark.django_db
def test_guided_readiness_needs_one_material_and_no_steps(db):
    world = _guided_world(db)
    lesson = world["lesson"]

    issues = lesson_issues(lesson)
    assert issues == ["No supporting materials yet — attach at least one document."]

    LessonMaterial.objects.create(lesson=lesson, file="lesson_materials/guide.pdf", order=1)
    KnowledgeCheck.objects.create(lesson=lesson, options=["", "", "", ""], order=1)

    # Checks stay optional: even a blank one never blocks publication.
    assert lesson_issues(lesson) == []


@pytest.mark.django_db
def test_clone_to_draft_copies_materials_and_checks(db, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    material = LessonMaterial.objects.create(lesson=world["lesson"], file="lesson_materials/guide.pdf", order=1)
    check = KnowledgeCheck.objects.create(
        lesson=world["lesson"], prompt="Which chapter?", options=["Chapter 1", "Chapter 84"],
        answer_index=0, order=1,
    )

    draft = clone_to_draft(world["version"])

    cloned = draft.hybrid_courses.get().hybrid_modules.get().hybrid_lessons.get()
    assert cloned.kind == HybridLesson.Kind.GUIDED_MATERIAL_STUDY
    cloned_material = cloned.materials.get()
    assert cloned_material.file.name == material.file.name
    assert cloned_material.pk != material.pk
    cloned_check = cloned.knowledge_checks.get()
    assert cloned_check.pk != check.pk
    assert (cloned_check.prompt, cloned_check.options, cloned_check.answer_index) == (
        check.prompt, check.options, check.answer_index,
    )


# --- The studio gate -----------------------------------------------------------


@pytest.mark.django_db
def test_the_studio_url_gates_a_guided_lesson_back_to_the_editor(client, db):
    world = _guided_world(db)
    client.force_login(world["instructor"])

    html = client.get(reverse("hybrid-lesson-demonstration-studio", args=[world["lesson"].pk])).content.decode()

    assert "No Demonstration Studio here" in html
    assert _editor_url(world["lesson"]) in html
    # Neither the recording controls nor their script reach the page.
    assert 'id="start"' not in html
    assert "demonstrationRecording" not in html


# --- Preview and the student workspace -----------------------------------------


def _published_guided(db, username, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db, username, status=ProgrammeVersion.Status.PUBLISHED)
    material = LessonMaterial.objects.create(lesson=world["lesson"], file="lesson_materials/guide.pdf", order=1)
    # size_display stats the blob, so the row needs a real file behind it.
    stored = tmp_path / material.file.name
    stored.parent.mkdir(parents=True, exist_ok=True)
    stored.write_bytes(b"%PDF-1.4 a tiny guide")
    KnowledgeCheck.objects.create(
        lesson=world["lesson"], prompt="Which chapter covers live animals?",
        options=["Chapter 1", "Chapter 84"], answer_index=0, order=1,
    )
    return world


@pytest.mark.django_db
def test_preview_lists_materials_and_marks_the_answer(client, db, tmp_path, settings):
    world = _published_guided(db, "guided-preview", tmp_path, settings)
    client.force_login(world["instructor"])

    html = client.get(reverse("hybrid-lesson-preview", args=[world["lesson"].pk])).content.decode()

    assert "guide.pdf" in html
    assert "Which chapter covers live animals?" in html
    assert "Chapter 84" in html
    assert "Correct answer" in html
    assert "Materials" in html
    assert "<iframe" not in html


@pytest.mark.django_db
def test_the_student_workspace_hides_answers_and_frames_materials(client, db, tmp_path, settings):
    world = _published_guided(db, "guided-student-view", tmp_path, settings)
    learner = _user(db, "guided-learner")
    learner.groups.add(Group.objects.get_or_create(name="Student")[0])
    disclaimer, _ = DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True},
    )
    DisclaimerAcceptance.objects.get_or_create(user=learner, disclaimer=disclaimer)
    Enrolment.objects.create(student=learner, programme_version=world["version"])
    client.force_login(learner)

    html = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk])).content.decode()

    theory_html = client.get(reverse("hybrid-lesson-theory", args=[world["lesson"].pk])).content.decode()
    assert "The tariff explained." in theory_html
    assert "guide.pdf" in html
    assert "Open the document" in html
    assert "Which chapter covers live animals?" in html
    assert "Chapter 1" in html
    assert "Correct answer" not in html
    assert "Materials" in html
    assert "<iframe" not in html


@pytest.mark.django_db
def test_a_guided_lesson_completes_on_theory_acknowledgement(client, db, tmp_path, settings):
    """No steps exist to satisfy, and knowledge checks never gate completion:
    acknowledging the theory completes the lesson."""
    world = _published_guided(db, "guided-complete", tmp_path, settings)
    learner = _user(db, "guided-completer")
    learner.groups.add(Group.objects.get_or_create(name="Student")[0])
    disclaimer, _ = DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True},
    )
    DisclaimerAcceptance.objects.get_or_create(user=learner, disclaimer=disclaimer)
    Enrolment.objects.create(student=learner, programme_version=world["version"])
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    attempt = LessonAttempt.objects.get(enrolment__student=learner, lesson=world["lesson"])

    response = client.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk]))

    assert response.json() == {"ok": True, "lesson_complete": True}
    attempt.refresh_from_db()
    assert attempt.completed_at is not None


# --- Media serving -------------------------------------------------------------


@pytest.mark.django_db
def test_material_files_are_served_as_published_reading(client, db, tmp_path, settings):
    """Materials sit beside lesson rich-text images: curriculum content served
    from the controlled media view, with nosniff and traversal protection."""
    settings.MEDIA_ROOT = tmp_path
    world = _guided_world(db)
    client.force_login(world["instructor"])
    client.post(_editor_url(world["lesson"]), {"action": "add_material", "file": _pdf()})
    material = LessonMaterial.objects.get(lesson=world["lesson"])

    response = Client().get(f"/media/{material.file.name}")

    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"
    assert b"".join(response.streaming_content) == b"%PDF-1.4 a tiny guide"