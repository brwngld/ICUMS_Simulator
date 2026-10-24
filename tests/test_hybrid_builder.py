"""Stage 3 smoke: the instructor builder authors the same rows the student
workspace renders, inside draft editions only."""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
from hybrid.models import HybridCourse, HybridLesson, HybridModule, PracticalStep
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _user(db, username, group_name):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _instructor(db, username="builder"):
    return _user(db, username, "Instructor")


def _student(db, username="learner"):
    return _user(db, username, "Student")


def _hybrid_programme(code="build-prog"):
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    return programme, version


def _course(version, code="course-one"):
    return HybridCourse.objects.create(
        programme_version=version, code=code, title=f"{code} title", order=1,
    )


def _module(course, code="module-one"):
    return HybridModule.objects.create(course=course, code=code, title=f"{code} title", order=1)


def _lesson(module, slug="lesson-one"):
    return HybridLesson.objects.create(module=module, slug=slug, title=f"{slug} title", order=1)


def _formset_data(step=None, step_screen="single-window-create-ucr", step_title="Renamed step",
                  theory_body="<p>Body copy</p>"):
    # The theory form keeps the "form" prefix on purpose (the shared
    # rich-text editor binds textarea ids like id_form-body); the step
    # formset uses its own "steps" prefix.
    data = {
        "form-body": theory_body,
        "steps-TOTAL_FORMS": "1", "steps-INITIAL_FORMS": "1",
        "steps-MIN_NUM_FORMS": "0", "steps-MAX_NUM_FORMS": "1000",
    }
    if step is not None:
        data.update({
            "steps-0-id": str(step.pk), "steps-0-title": step_title,
            "steps-0-instruction": "Do the thing.", "steps-0-outcome": "The thing is done.",
            "steps-0-hint": "Look again.", "steps-0-screen": step_screen,
        })
    return data


# --- Access -------------------------------------------------------------------


@pytest.mark.django_db
def test_only_instructors_open_the_builder(client, db):
    _student(db, "not-staff")
    client.force_login(User.objects.get(username="not-staff"))
    response = client.get(reverse("hybrid-builder"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_anonymous_visitors_are_sent_to_login(client, db):
    response = client.get(reverse("hybrid-builder"))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]


@pytest.mark.django_db
def test_the_builder_lists_hybrid_programmes_and_their_editions(client, db):
    instructor = _instructor(db)
    programme, version = _hybrid_programme("listed")
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder")).content.decode()
    assert programme.name in html
    assert "Draft edition" in html


# --- Course and module authoring -----------------------------------------------


@pytest.mark.django_db
def test_creating_a_course_opens_or_reuses_a_draft_edition(client, db):
    instructor = _instructor(db)
    programme, version = _hybrid_programme("drafts")
    client.force_login(instructor)
    response = client.post(reverse("hybrid-builder"), {"programme": programme.pk, "title": "Cargo basics", "description": ""})
    assert response.status_code == 302
    course = HybridCourse.objects.get(title="Cargo basics")
    assert course.programme_version == version
    assert course.programme_version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_a_course_cannot_be_created_on_a_theory_programme(client, db):
    instructor = _instructor(db)
    theory = Programme.objects.create(name="Theory only", code="theory-only", learning_track=Programme.Track.THEORY)
    client.force_login(instructor)
    response = client.post(reverse("hybrid-builder"), {"programme": theory.pk, "title": "Smuggled course", "description": ""})
    assert response.status_code == 400
    assert not HybridCourse.objects.filter(title="Smuggled course").exists()


@pytest.mark.django_db
def test_published_editions_are_not_editable(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("locked")
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    course = _course(version)
    module = _module(course)
    lesson = _lesson(module)
    client.force_login(instructor)
    assert client.get(reverse("hybrid-course-edit", args=[course.pk])).status_code == 404
    assert client.get(reverse("hybrid-module-edit", args=[module.pk])).status_code == 404
    assert client.get(reverse("hybrid-lesson-edit", args=[lesson.pk])).status_code == 404


@pytest.mark.django_db
def test_modules_and_lessons_are_created_under_the_draft(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("crud")
    course = _course(version)
    client.force_login(instructor)

    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "create_module", "title": "Paperwork", "description": ""})
    module = HybridModule.objects.get(course=course, title="Paperwork")

    response = client.post(
        reverse("hybrid-module-edit", args=[module.pk]),
        {"action": "create_lesson", "title": "First journey", "summary": "About the journey."},
    )
    assert response.status_code == 302
    assert reverse("hybrid-lesson-edit", args=[HybridLesson.objects.get(module=module, title="First journey").pk]) in response.url
    lesson = HybridLesson.objects.get(module=module, title="First journey")
    assert lesson.slug == "first-journey"


@pytest.mark.django_db
def test_a_module_with_lessons_cannot_be_silently_deleted(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("protect")
    course = _course(version)
    module = _module(course)
    _lesson(module)
    client.force_login(instructor)
    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "delete_module", "module_id": module.pk})
    assert HybridModule.objects.filter(pk=module.pk).exists()


# --- The five-tab lesson editor -------------------------------------------------


@pytest.mark.django_db
def test_the_editor_saves_details_theory_and_steps_together(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("editor")
    lesson = _lesson(_module(_course(version)))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Old step", order=1, screen="single-window-overview")
    client.force_login(instructor)

    data = {"title": "Renamed lesson", "summary": "Fresh summary", "active_tab": "details"}
    data.update(_formset_data(step=step))
    response = client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), data)
    assert response.status_code == 302

    lesson.refresh_from_db()
    step.refresh_from_db()
    assert lesson.title == "Renamed lesson"
    assert lesson.summary == "Fresh summary"
    assert "<p>Body copy</p>" in lesson.theory
    assert step.title == "Renamed step"
    assert step.screen == "single-window-create-ucr"


@pytest.mark.django_db
def test_a_step_screen_is_limited_to_the_approved_registry(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("registry")
    lesson = _lesson(_module(_course(version)))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Open", order=1, screen="single-window-overview")
    client.force_login(instructor)

    data = {"title": lesson.title, "summary": "", "active_tab": "simulator"}
    data.update(_formset_data(step=step, step_screen="javascript:alert(1)"))
    response = client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), data)
    assert response.status_code == 400
    step.refresh_from_db()
    assert step.screen == "single-window-overview"


@pytest.mark.django_db
def test_steps_can_be_added_moved_and_removed(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("steps")
    lesson = _lesson(_module(_course(version)))
    first = PracticalStep.objects.create(lesson=lesson, key="first", title="First", order=1)
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[lesson.pk])

    client.post(editor, {"action": "add_step", "active_tab": "journey"})
    second = PracticalStep.objects.get(lesson=lesson, title="New step")
    assert second.order == 2 and second.key.startswith("new-step")

    client.post(editor, {"action": "move_step", "step_id": second.pk, "direction": "up", "active_tab": "journey"})
    first.refresh_from_db(); second.refresh_from_db()
    assert (first.order, second.order) == (2, 1)

    client.post(editor, {"action": "delete_step", "step_id": second.pk})
    assert not PracticalStep.objects.filter(pk=second.pk).exists()
    first.refresh_from_db()
    assert first.order == 1


@pytest.mark.django_db
def test_the_review_tab_reports_what_is_missing(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("review")
    lesson = _lesson(_module(_course(version)))
    client.force_login(instructor)
    response = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk]))
    issues = " ".join(response.context["issues"])
    assert "No theory reading yet" in issues
    assert "No practical steps yet" in issues


# --- Preview --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_preview_renders_draft_content_for_instructors_only(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("preview")
    lesson = _lesson(_module(_course(version)))
    PracticalStep.objects.create(
        lesson=lesson, key="open", title="Open the overview", order=1,
        instruction="Open it.", screen="single-window-overview",
    )
    client.force_login(instructor)
    html = client.get(reverse("hybrid-lesson-preview", args=[lesson.pk])).content.decode()
    assert lesson.title in html
    assert "Open the overview" in html
    assert "Instructor preview" in html

    student = _student(db, "peeking")
    client.force_login(student)
    assert client.get(reverse("hybrid-lesson-preview", args=[lesson.pk])).status_code == 302


# --- The milestone: builder-authored content drives the student workspace --------


@pytest.mark.django_db
def test_an_instructor_authored_lesson_renders_in_the_student_workspace(client, db):
    """The whole point of Stage 3: an instructor authors a lesson through the
    builder alone, and the Stage 2 workspace renders it with no code changes.
    Publishing the edition is Stage 4, so the test flips the flags directly."""
    instructor = _instructor(db)
    programme, version = _hybrid_programme("milestone")
    client.force_login(instructor)

    client.post(reverse("hybrid-builder"), {"programme": programme.pk, "title": "Milestone course", "description": ""})
    course = HybridCourse.objects.get(title="Milestone course")
    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "create_module", "title": "Milestone module", "description": ""})
    module = HybridModule.objects.get(course=course)
    client.post(reverse("hybrid-module-edit", args=[module.pk]), {"action": "create_lesson", "title": "Milestone journey", "summary": ""})
    lesson = HybridLesson.objects.get(module=module)

    client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), {"action": "add_step", "active_tab": "journey"})
    step = PracticalStep.objects.get(lesson=lesson)

    data = {"title": "Milestone journey", "summary": "Authored entirely in the builder.", "active_tab": "journey"}
    data.update(_formset_data(step=step, step_title="Open the single window", theory_body="<p>Authored theory.</p>"))
    client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), data)

    # Stand-in for the Stage 4 publication sweep: publish the draft edition.
    ProgrammeVersion.objects.filter(pk=version.pk).update(status=ProgrammeVersion.Status.PUBLISHED)
    HybridCourse.objects.filter(pk=course.pk).update(is_published=True)
    HybridModule.objects.filter(pk=module.pk).update(is_published=True)
    HybridLesson.objects.filter(pk=lesson.pk).update(is_published=True)

    student = _student(db, "milestone-learner")
    Enrolment.objects.create(student=student, programme_version=ProgrammeVersion.objects.get(pk=version.pk))
    client.force_login(student)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert "Milestone journey" in html
    assert "Authored entirely in the builder." in html
    assert "Authored theory." in html
    assert "Open the single window" in html
    assert reverse("single-window-create-ucr") in html
