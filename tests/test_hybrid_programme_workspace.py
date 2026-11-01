"""UI 2 — the instructor Programme Workspace.

Covers access and permissions, edition selection with edition-scoped
statistics and courses, draft vs published/retired behaviour, the Add course
dialog round-trip (CSRF, validation, preserved input, no-JS fallback),
publish and new-draft actions, publication readiness from the real backend
blockers, the empty programme state, and the Manage course link into the
existing course editor."""
import re

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from accounts.models import User
from hybrid.models import HybridCourse, HybridLesson, HybridModule, PracticalStep
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


def _instructor(db, username="workspace-instructor"):
    return _user(db, username, "Instructor")


def _hybrid_programme(code):
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    return programme, version


def _course(version, code, title=None):
    return HybridCourse.objects.create(
        programme_version=version, code=code, title=title or f"{code} title", order=1,
    )


def _module(course, code):
    return HybridModule.objects.create(course=course, code=code, title=f"{code} title", order=1)


def _lesson(module, slug):
    return HybridLesson.objects.create(module=module, slug=slug, title=f"{slug} title", order=1)


def _ready_course(version, code):
    """A course with nothing left to fill in — course_blockers returns empty."""
    lesson = HybridLesson.objects.create(
        module=_module(_course(version, code), f"{code}-module"),
        slug=f"{code}-lesson", title=f"{code} lesson", order=1,
        summary="What the learner practises.", theory="<p>Theory reading.</p>",
    )
    PracticalStep.objects.create(
        lesson=lesson, title="Open the window", instruction="Do the thing.",
        outcome="The thing is done.", screen="single-window-create-ucr", order=1,
    )
    return HybridCourse.objects.get(code=code)


def _url(programme, **params):
    url = reverse("hybrid-programme-detail", args=[programme.pk])
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return url


# --- Access and permissions -------------------------------------------------------


@pytest.mark.django_db
def test_instructors_open_the_workspace(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("open-workspace")
    client.force_login(instructor)
    response = client.get(_url(programme))
    assert response.status_code == 200
    html = response.content.decode()
    assert programme.name in html
    assert "Editions &amp; publishing" in html


@pytest.mark.django_db
def test_a_student_cannot_open_the_workspace(client, db):
    _user(db, "not-staff", "Student")
    programme, _ = _hybrid_programme("student-denied")
    client.force_login(User.objects.get(username="not-staff"))
    response = client.get(_url(programme))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_anonymous_visitors_are_sent_to_login(db):
    programme, _ = _hybrid_programme("anon-denied")
    response = Client().get(_url(programme))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]


@pytest.mark.django_db
def test_theory_and_inactive_programmes_are_not_workspaces(client, db):
    instructor = _instructor(db)
    theory = Programme.objects.create(name="Theory only", code="theory-only", learning_track=Programme.Track.THEORY)
    ProgrammeVersion.objects.create(programme=theory, version=1, status=ProgrammeVersion.Status.DRAFT)
    inactive, _ = _hybrid_programme("inactive-prog")
    inactive.is_active = False
    inactive.save(update_fields=("is_active",))
    client.force_login(instructor)
    assert client.get(_url(theory)).status_code == 404
    assert client.get(_url(inactive)).status_code == 404


# --- Identity, editions and edition-scoped statistics --------------------------------


@pytest.mark.django_db
def test_the_workspace_shows_identity_and_every_edition(client, db):
    instructor = _instructor(db)
    programme, first = _hybrid_programme("identity")
    first.status = ProgrammeVersion.Status.RETIRED
    first.save(update_fields=("status",))
    _edition(programme, 2, ProgrammeVersion.Status.PUBLISHED)
    _edition(programme, 3, ProgrammeVersion.Status.DRAFT)
    client.force_login(instructor)
    response = client.get(_url(programme))
    html = response.content.decode()
    assert programme.name in html
    assert "Programme code" in html
    for label in ("Draft edition — current", "Published edition", "Retired edition"):
        assert label in html
    # Default selection: the open draft.
    assert response.context["selected"]["version_number"] == 3
    assert response.context["selected_is_draft"] is True


@pytest.mark.django_db
def test_the_default_edition_falls_back_to_the_latest_published(client, db):
    instructor = _instructor(db)
    programme, first = _hybrid_programme("published-only")
    first.status = ProgrammeVersion.Status.PUBLISHED
    first.save(update_fields=("status",))
    client.force_login(instructor)
    response = client.get(_url(programme))
    assert response.context["selected"]["version_number"] == 1
    assert response.context["selected_is_draft"] is False
    assert "read-only" in response.content.decode()


def _edition(programme, version, status):
    return ProgrammeVersion.objects.create(programme=programme, version=version, status=status)


@pytest.mark.django_db
def test_edition_selection_scopes_statistics_and_courses(client, db):
    instructor = _instructor(db)
    programme, first = _hybrid_programme("scoping")
    _course(first, "v1-course")
    second = _edition(programme, 2, ProgrammeVersion.Status.PUBLISHED)
    _course(second, "v2-course")
    draft = _edition(programme, 3, ProgrammeVersion.Status.DRAFT)
    course_v3 = _course(draft, "v3-course")
    _lesson(_module(course_v3, "v3-module"), "v3-lesson")
    client.force_login(instructor)
    # Default: the open draft.
    response = client.get(_url(programme))
    assert response.context["selected"]["version_number"] == 3
    assert response.context["selected"]["courses"] == 1
    assert [row["course"].code for row in response.context["courses"]] == ["v3-course"]
    # Selected: the published edition, with its own courses and read-only flag.
    response = client.get(_url(programme, edition=2))
    assert response.context["selected"]["version_number"] == 2
    assert [row["course"].code for row in response.context["courses"]] == ["v2-course"]
    assert response.context["selected_is_draft"] is False
    assert "Read-only" in response.content.decode()
    # An unknown edition number falls back to the current one.
    response = client.get(_url(programme, edition=99))
    assert response.context["selected"]["version_number"] == 3


@pytest.mark.django_db
def test_retired_editions_are_read_only_and_muted(client, db):
    instructor = _instructor(db)
    programme, first = _hybrid_programme("retired-view")
    _course(first, "retired-course")
    first.status = ProgrammeVersion.Status.RETIRED
    first.save(update_fields=("status",))
    client.force_login(instructor)
    response = client.get(_url(programme, edition=1))
    html = response.content.decode()
    assert response.context["selected"]["status"] == ProgrammeVersion.Status.RETIRED
    assert "Retired editions are kept for the record and cannot be edited" in html
    assert "Publish edition" not in html
    assert 'href="' + reverse("hybrid-course-edit", args=[HybridCourse.objects.get(code="retired-course").pk]) + '"' not in html


# --- Courses --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_workspace_lists_courses_with_counts_and_readiness(client, db):
    instructor = _instructor(db)
    programme, draft = _hybrid_programme("course-list")
    _ready_course(draft, "ready-course")
    _course(draft, "empty-course")  # no modules — a real backend blocker
    client.force_login(instructor)
    rows = {row["course"].code: row for row in client.get(_url(programme)).context["courses"]}
    assert rows["ready-course"]["blockers"] == []  # nothing left to fill in
    assert rows["ready-course"]["modules"] == 1
    assert any("Add at least one module." in b for b in rows["empty-course"]["blockers"])
    html = client.get(_url(programme)).content.decode()
    assert "Not publish-ready" in html
    assert "Manage course" in html


@pytest.mark.django_db
def test_an_empty_programme_shows_the_empty_state(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("empty-workspace")
    client.force_login(instructor)
    html = client.get(_url(programme)).content.decode()
    assert "No courses in this edition yet" in html
    assert "Add course" in html


@pytest.mark.django_db
def test_manage_course_opens_the_existing_course_editor(client, db):
    instructor = _instructor(db)
    programme, draft = _hybrid_programme("manage-course")
    course = _course(draft, "linked-course")
    client.force_login(instructor)
    html = client.get(_url(programme)).content.decode()
    assert reverse("hybrid-course-edit", args=[course.pk]) in html
    assert client.get(reverse("hybrid-course-edit", args=[course.pk])).status_code == 200


# --- The Add course dialog ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_dialog_opens_without_javascript_and_carries_csrf(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("dialog-open")
    client.force_login(instructor)
    html = client.get(_url(programme, **{"new": "course"})).content.decode()
    assert re.search(r'<dialog[^>]*\bopen\b[^>]*>', html)
    assert "data-has-errors" not in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'value="create_course"' in html
    # The scoped programme rides along as a hidden field.
    assert f'value="{programme.pk}"' in html


@pytest.mark.django_db
def test_a_valid_course_post_creates_it_in_the_open_draft(client, db):
    instructor = _instructor(db)
    programme, draft = _hybrid_programme("course-create")
    client.force_login(instructor)
    response = client.post(
        _url(programme),
        {"action": "create_course", "programme": programme.pk, "title": "Cargo basics", "description": "Handling"},
    )
    assert response.status_code == 302
    assert reverse("hybrid-course-edit", args=[HybridCourse.objects.get(title="Cargo basics").pk]) in response.url
    course = HybridCourse.objects.get(title="Cargo basics")
    assert course.programme_version == draft
    assert course.code == "cargo-basics"


@pytest.mark.django_db
def test_two_same_titled_courses_get_distinct_codes(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("duplicate-codes")
    client.force_login(instructor)
    for _ in range(2):
        response = client.post(
            _url(programme), {"action": "create_course", "programme": programme.pk, "title": "Same title", "description": ""},
        )
        assert response.status_code == 302
    codes = sorted(HybridCourse.objects.values_list("code", flat=True))
    assert codes == ["same-title", "same-title-2"]


@pytest.mark.django_db
def test_an_invalid_course_post_reopens_the_dialog_with_values(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("dialog-errors")
    client.force_login(instructor)
    response = client.post(
        _url(programme),
        {"action": "create_course", "programme": programme.pk, "title": "", "description": "Kept description"},
    )
    assert response.status_code == 400
    html = response.content.decode()
    assert "data-has-errors" in html
    assert "Kept description" in html
    assert "This field is required." in html  # the empty title, nothing else


@pytest.mark.django_db
def test_a_forged_programme_pk_is_refused(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("scoped-course")
    other, _ = _hybrid_programme("other-programme")
    client.force_login(instructor)
    response = client.post(
        _url(programme),
        {"action": "create_course", "programme": other.pk, "title": "Smuggled", "description": ""},
    )
    assert response.status_code == 400
    assert not HybridCourse.objects.filter(title="Smuggled").exists()


@pytest.mark.django_db
def test_creating_a_course_requires_a_csrf_token(db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("csrf-course")
    client = Client(enforce_csrf_checks=True)
    client.force_login(instructor)
    response = client.post(
        _url(programme), {"action": "create_course", "programme": programme.pk, "title": "No token", "description": ""},
    )
    assert response.status_code == 403
    assert not HybridCourse.objects.filter(title="No token").exists()


# --- Publishing and new drafts -------------------------------------------------------------


@pytest.mark.django_db
def test_publishing_from_the_workspace_publishes_the_draft(client, db):
    instructor = _instructor(db)
    programme, draft = _hybrid_programme("publish-workspace")
    _ready_course(draft, "publish-course")
    client.force_login(instructor)
    response = client.post(
        _url(programme), {"action": "publish_edition", "version_id": draft.pk},
    )
    assert response.status_code == 302
    assert reverse("hybrid-programme-detail", args=[programme.pk]) in response.url
    draft.refresh_from_db()
    assert draft.status == ProgrammeVersion.Status.PUBLISHED


@pytest.mark.django_db
def test_publishing_reports_blockers_instead_of_publishing(client, db):
    instructor = _instructor(db)
    programme, draft = _hybrid_programme("publish-blocked")
    client.force_login(instructor)
    response = client.post(_url(programme), {"action": "publish_edition", "version_id": draft.pk})
    assert response.status_code == 302
    draft.refresh_from_db()
    assert draft.status == ProgrammeVersion.Status.DRAFT
    messages = [str(m) for m in response.wsgi_request._messages]
    assert any("not ready to publish" in m for m in messages)


@pytest.mark.django_db
def test_another_programmes_version_cannot_be_published(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("publish-scoped")
    stranger, other_draft = _hybrid_programme("stranger-edition")
    client.force_login(instructor)
    response = client.post(_url(programme), {"action": "publish_edition", "version_id": other_draft.pk})
    assert response.status_code == 404
    other_draft.refresh_from_db()
    assert other_draft.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_new_draft_clones_a_published_edition_from_the_workspace(client, db):
    instructor = _instructor(db)
    programme, first = _hybrid_programme("new-draft")
    _lesson(_module(_course(first, "cloned-course"), "cloned-module"), "cloned-lesson")
    first.status = ProgrammeVersion.Status.PUBLISHED
    first.save(update_fields=("status",))
    client.force_login(instructor)
    response = client.post(_url(programme), {"action": "new_draft", "version_id": first.pk})
    assert response.status_code == 302
    draft = ProgrammeVersion.objects.get(programme=programme, status=ProgrammeVersion.Status.DRAFT)
    assert draft.version == 2
    assert draft.hybrid_courses.count() == 1  # cloned content
    # Retired and published editions stay immutable.
    retired = _edition(programme, 3, ProgrammeVersion.Status.RETIRED)
    assert client.post(_url(programme), {"action": "new_draft", "version_id": retired.pk}).status_code == 404
    assert client.post(_url(programme), {"action": "publish_edition", "version_id": retired.pk}).status_code == 404
