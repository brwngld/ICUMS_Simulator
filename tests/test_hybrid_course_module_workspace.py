"""UI 3 — the Course and Module workspaces.

Covers access, overview statistics, course-level publication readiness, the
Add-module and Add-lesson dialog round-trips (CSRF, validation errors,
preserved input, no-JS fallback), module/lesson ordering, removal
confirmations (?confirm= no-JS fallback, ProtectedError preservation) and
navigation between the workspaces."""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from hybrid.models import HybridCourse, HybridLesson, HybridModule, PracticalJourney, PracticalStep
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Programme, ProgrammeVersion


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


@pytest.fixture
def instructor(db):
    return _user(db, "cm-instructor", "Instructor")


@pytest.fixture
def student(db):
    return _user(db, "cm-student", "Student")


@pytest.fixture
def draft_course(db):
    programme = Programme.objects.create(name="CM Programme", code="cm-programme", learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    course = HybridCourse.objects.create(programme_version=version, code="cm-course", title="CM course", order=1)
    return course


def _module(course, code, title=None):
    return HybridModule.objects.create(course=course, code=code, title=title or f"{code} title", order=1)


def _lesson(module, slug, summary="", theory=""):
    return HybridLesson.objects.create(module=module, slug=slug, title=f"{slug} title", order=1, summary=summary, theory=theory)


def _ready_lesson(module, slug):
    lesson = _lesson(module, slug, summary="What the learner practises.", theory="<p>Theory reading.</p>")
    PracticalStep.objects.create(
        lesson=lesson, title="Open the window", instruction="Do the thing.",
        outcome="The thing is done.", screen="single-window-create-ucr", order=1,
    )
    return lesson


def _course_url(course, **params):
    url = reverse("hybrid-course-edit", args=[course.pk])
    return url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")


def _module_url(module, **params):
    url = reverse("hybrid-module-edit", args=[module.pk])
    return url + ("?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else "")


# --- Access --------------------------------------------------------------------------


@pytest.mark.django_db
def test_instructors_open_both_workspaces(client, instructor, draft_course):
    client.force_login(instructor)
    assert client.get(_course_url(draft_course)).status_code == 200
    module = _module(draft_course, "m1")
    assert client.get(_module_url(module)).status_code == 200


@pytest.mark.django_db
def test_students_are_sent_to_the_dashboard(client, student, draft_course):
    client.force_login(student)
    response = client.get(_course_url(draft_course))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_anonymous_visitors_are_sent_to_login(db, draft_course):
    from django.test import Client
    client = Client()
    assert client.get(_course_url(draft_course)).status_code == 302
    assert client.get(_module_url(HybridModule.objects.create(course=draft_course, code="m", title="M", order=1))).status_code == 302


# --- Course workspace: statistics and readiness ------------------------------------------


@pytest.mark.django_db
def test_the_course_workspace_shows_statistics_and_readiness(client, instructor, draft_course):
    module_a = _module(draft_course, "m-a")
    _ready_lesson(module_a, "done-lesson")
    module_b = _module(draft_course, "m-b")
    _lesson(module_b, "bare-lesson")  # no summary/theory/steps
    PracticalJourney.objects.create(programme_version=draft_course.programme_version, course=draft_course, title="J1", order=1)
    client.force_login(instructor)
    response = client.get(_course_url(draft_course))
    html = response.content.decode()
    # Statistics come from the real records.
    assert response.context["lesson_count"] == 2
    assert len(response.context["blockers"]) >= 2  # bare lesson + journey requirements
    assert "Items to resolve" in html
    assert "Not ready to publish" in html
    assert "Show details" in html


@pytest.mark.django_db
def test_a_fully_ready_course_reads_ready_to_publish(client, instructor, draft_course):
    _ready_lesson(_module(draft_course, "only"), "whole-lesson")
    client.force_login(instructor)
    response = client.get(_course_url(draft_course))
    assert response.context["blockers"] == []
    assert "Ready to publish" in response.content.decode()


# --- Add module dialog -----------------------------------------------------------------


@pytest.mark.django_db
def test_the_add_module_dialog_opens_without_javascript(client, instructor, draft_course):
    client.force_login(instructor)
    html = client.get(_course_url(draft_course, **{"new": "module"})).content.decode()
    assert "<dialog" in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'value="create_module"' in html
    assert 'id="module-dialog"' in html


@pytest.mark.django_db
def test_an_invalid_module_post_reopens_the_dialog_with_values(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(
        _course_url(draft_course),
        {"action": "create_module", "title": "", "description": "Kept description"},
    )
    assert response.status_code == 400
    html = response.content.decode()
    assert "data-has-errors" in html
    assert "Kept description" in html
    assert "This field is required." in html
    assert not HybridModule.objects.filter(course=draft_course).exists()


@pytest.mark.django_db
def test_a_valid_module_post_creates_it_with_a_slug(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(
        _course_url(draft_course),
        {"action": "create_module", "title": "The Single Window", "description": ""},
    )
    assert response.status_code == 302
    assert reverse("hybrid-course-edit", args=[draft_course.pk]) in response.url
    module = HybridModule.objects.get(course=draft_course, title="The Single Window")
    assert module.code == "the-single-window"


# --- Ordering --------------------------------------------------------------------------


@pytest.mark.django_db
def test_modules_move_up_and_down(client, instructor, draft_course):
    first = _module(draft_course, "m1", "Alpha")
    first.order = 1
    first.save(update_fields=("order",))
    second = _module(draft_course, "m2", "Beta")
    second.order = 2
    second.save(update_fields=("order",))
    client.force_login(instructor)
    response = client.post(
        _course_url(draft_course),
        {"action": "move_module", "module_id": second.pk, "direction": "up"},
    )
    assert response.status_code == 302
    assert list(draft_course.hybrid_modules.order_by("order").values_list("title", flat=True)) == ["Beta", "Alpha"]


@pytest.mark.django_db
def test_lessons_move_up_and_down(client, instructor, draft_course):
    module = _module(draft_course, "m1")
    one = _lesson(module, "one")
    one.order = 1
    one.save(update_fields=("order",))
    two = _lesson(module, "two")
    two.order = 2
    two.save(update_fields=("order",))
    client.force_login(instructor)
    response = client.post(
        _module_url(module),
        {"action": "move_lesson", "lesson_id": two.pk, "direction": "up"},
    )
    assert response.status_code == 302
    assert list(module.hybrid_lessons.order_by("order").values_list("slug", flat=True)) == ["two", "one"]


# --- Removal confirmations ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_module_removal_confirmation_renders_without_javascript(client, instructor, draft_course):
    module = _module(draft_course, "removable")
    client.force_login(instructor)
    html = client.get(_course_url(draft_course, **{"confirm": f"module-{module.pk}"})).content.decode()
    assert f'id="confirm-module-{module.pk}"' in html
    assert "Remove module?" in html
    assert module.title in html
    assert 'value="delete_module"' in html


@pytest.mark.django_db
def test_confirming_module_removal_deletes_an_empty_module(client, instructor, draft_course):
    module = _module(draft_course, "empty")
    client.force_login(instructor)
    response = client.post(
        _course_url(draft_course),
        {"action": "delete_module", "module_id": module.pk},
    )
    assert response.status_code == 302
    assert not HybridModule.objects.filter(pk=module.pk).exists()


@pytest.mark.django_db
def test_a_module_with_lessons_still_refuses_to_be_removed(client, instructor, draft_course):
    module = _module(draft_course, "full")
    _lesson(module, "kept")
    client.force_login(instructor)
    response = client.post(
        _course_url(draft_course),
        {"action": "delete_module", "module_id": module.pk},
    )
    assert response.status_code == 302
    assert HybridModule.objects.filter(pk=module.pk).exists()


@pytest.mark.django_db
def test_the_lesson_removal_confirmation_and_deletion(client, instructor, draft_course):
    module = _module(draft_course, "m1")
    lesson = _lesson(module, "removable")
    client.force_login(instructor)
    html = client.get(_module_url(module, **{"confirm": f"lesson-{lesson.pk}"})).content.decode()
    assert "Remove lesson?" in html
    assert lesson.title in html
    assert 'value="delete_lesson"' in html
    response = client.post(
        _module_url(module),
        {"action": "delete_lesson", "lesson_id": lesson.pk},
    )
    assert response.status_code == 302
    assert not HybridLesson.objects.filter(pk=lesson.pk).exists()


# --- Module workspace: lesson cards and readiness ----------------------------------------------


@pytest.mark.django_db
def test_the_module_workspace_marks_unready_interactive_lessons(client, instructor, draft_course):
    module = _module(draft_course, "m1")
    _ready_lesson(module, "ready-lesson")
    bare = _lesson(module, "bare-lesson")
    bare.kind = HybridLesson.Kind.INTERACTIVE_PRACTICAL
    bare.save(update_fields=("kind",))
    client.force_login(instructor)
    response = client.get(_module_url(module))
    rows = {row["lesson"].slug: row for row in response.context["lesson_rows"]}
    assert rows["ready-lesson"]["issues"] == []
    assert rows["bare-lesson"]["issues"]  # summary, theory and steps are missing
    html = response.content.decode()
    assert "Not publish-ready" in html
    assert response.context["not_ready_count"] == 1


@pytest.mark.django_db
def test_the_module_workspace_counts_interactive_and_theory(client, instructor, draft_course):
    module = _module(draft_course, "m1")
    _ready_lesson(module, "one")
    written = _lesson(module, "two", summary="S.", theory="<p>T.</p>")
    written.kind = HybridLesson.Kind.GUIDED_MATERIAL_STUDY
    written.save(update_fields=("kind",))
    client.force_login(instructor)
    response = client.get(_module_url(module))
    assert response.context["interactive_count"] == 1
    assert response.context["theory_count"] == 2
    assert response.context["not_ready_count"] == 0


# --- Navigation --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_navigation_links_between_the_workspaces(client, instructor, draft_course):
    module = _module(draft_course, "m1")
    client.force_login(instructor)
    course_html = client.get(_course_url(draft_course)).content.decode()
    assert reverse("hybrid-programme-detail", args=[draft_course.programme_version.programme_id]) in course_html
    assert reverse("hybrid-module-edit", args=[module.pk]) in course_html
    module_html = client.get(_module_url(module)).content.decode()
    assert reverse("hybrid-course-edit", args=[draft_course.pk]) in module_html
    assert reverse("hybrid-programme-detail", args=[draft_course.programme_version.programme_id]) in module_html
    # The stale landing link is gone.
    assert ">All courses</a>" not in course_html
