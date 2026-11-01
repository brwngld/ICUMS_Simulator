"""UI 1 — the approved Theory & Practical builder landing page.

Covers the programme dashboard: summary statistics (draft-if-present-else-
latest-published, retired excluded), server-side search and Draft/Published
filtering without duplicate cards, the New-programme dialog round-trip
(CSRF, validation errors, preserved values, no-JS fallback) and the temporary
Manage-programme target (the existing programme-scoped route)."""
import re

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from accounts.models import User
from hybrid.models import HybridCourse, HybridLesson, HybridModule
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


def _instructor(db, username="landing-instructor"):
    return _user(db, username, "Instructor")


def _hybrid_programme(code):
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    return programme, version


def _edition(programme, version, status):
    return ProgrammeVersion.objects.create(programme=programme, version=version, status=status)


def _course(version, code):
    return HybridCourse.objects.create(programme_version=version, code=code, title=f"{code} title", order=1)


def _module(course, code):
    return HybridModule.objects.create(course=course, code=code, title=f"{code} title", order=1)


def _lesson(module, slug):
    return HybridLesson.objects.create(module=module, slug=slug, title=f"{slug} title", order=1)


def _fill(version, courses, modules_per_course, lessons_per_module):
    for c in range(courses):
        course = _course(version, f"{version.pk.hex[:6]}-c{c}")
        for m in range(modules_per_course):
            module = _module(course, f"{version.pk.hex[:6]}-m{c}-{m}")
            for l in range(lessons_per_module):
                _lesson(module, f"{version.pk.hex[:6]}-l{c}-{m}-{l}")


# --- The dashboard --------------------------------------------------------------


@pytest.mark.django_db
def test_the_landing_renders_the_approved_dashboard(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("dashboard")
    client.force_login(instructor)
    response = client.get(reverse("hybrid-builder"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "New programme" in html
    assert programme.name in html
    assert "Draft edition" in html
    assert 'id="programme-dialog"' in html
    assert "Programme code" in html
    # The old creation forms are gone from the landing experience.
    assert "Create course" not in html
    assert 'name="programme"' not in html


@pytest.mark.django_db
def test_summary_counts_the_draft_edition_when_one_exists(client, db):
    instructor = _instructor(db)
    both, first = _hybrid_programme("both-editions")
    first.status = ProgrammeVersion.Status.PUBLISHED
    first.save(update_fields=("status",))
    _fill(first, courses=1, modules_per_course=1, lessons_per_module=2)
    _fill(_edition(both, 2, ProgrammeVersion.Status.DRAFT), courses=2, modules_per_course=2, lessons_per_module=3)
    only_draft, _ = _hybrid_programme("draft-only")
    _fill(only_draft.versions.get(), courses=1, modules_per_course=1, lessons_per_module=1)
    client.force_login(instructor)
    response = client.get(reverse("hybrid-builder"))
    # draft "both-editions" v2: 2 courses × 2 modules × 3 lessons; "draft-only": 1×1×1.
    assert response.context["landing_stats"] == {
        "programmes": 2, "courses": 3, "modules": 5, "lessons": 13,
    }


@pytest.mark.django_db
def test_summary_falls_back_to_the_latest_published_and_skips_retired(client, db):
    instructor = _instructor(db)
    retired_then_published, first = _hybrid_programme("retired-published")
    first.status = ProgrammeVersion.Status.RETIRED
    first.save(update_fields=("status",))
    _fill(first, courses=5, modules_per_course=5, lessons_per_module=5)
    _fill(_edition(retired_then_published, 2, ProgrammeVersion.Status.PUBLISHED), courses=1, modules_per_course=1, lessons_per_module=1)
    retired_only, first = _hybrid_programme("retired-only")
    first.status = ProgrammeVersion.Status.RETIRED
    first.save(update_fields=("status",))
    _fill(first, courses=2, modules_per_course=1, lessons_per_module=1)
    published_then_draft, first = _hybrid_programme("published-draft")
    first.status = ProgrammeVersion.Status.PUBLISHED
    first.save(update_fields=("status",))
    _fill(first, courses=2, modules_per_course=0, lessons_per_module=0)
    _fill(_edition(published_then_draft, 2, ProgrammeVersion.Status.DRAFT), courses=1, modules_per_course=0, lessons_per_module=0)
    client.force_login(instructor)
    response = client.get(reverse("hybrid-builder"))
    assert response.context["landing_stats"] == {
        "programmes": 3, "courses": 2, "modules": 1, "lessons": 1,
    }


# --- Search and filtering ---------------------------------------------------------


@pytest.mark.django_db
def test_search_matches_name_and_code(client, db):
    instructor = _instructor(db)
    coastal, _ = _hybrid_programme("coastal-x")
    inland, _ = _hybrid_programme("inland-y")
    client.force_login(instructor)
    found = client.get(reverse("hybrid-builder"), {"q": "coastal"}).context["programme_rows"]
    assert [row["programme"].pk for row in found] == [coastal.pk]
    found = client.get(reverse("hybrid-builder"), {"q": "inland-y"}).context["programme_rows"]
    assert [row["programme"].pk for row in found] == [inland.pk]
    response = client.get(reverse("hybrid-builder"), {"q": "zzz"})
    assert response.context["programme_rows"] == []
    assert "No programmes match" in response.content.decode()


@pytest.mark.django_db
def test_status_filter_matches_programmes_having_the_status_without_duplicates(client, db):
    instructor = _instructor(db)
    both, first = _hybrid_programme("two-editions")
    first.status = ProgrammeVersion.Status.PUBLISHED
    first.save(update_fields=("status",))
    _edition(both, 2, ProgrammeVersion.Status.DRAFT)
    draft_only, _ = _hybrid_programme("draft-only")
    client.force_login(instructor)
    # Rows render in the queryset's name order; each programme appears once.
    rows = client.get(reverse("hybrid-builder"), {"status": "draft"}).context["programme_rows"]
    assert [row["programme"].pk for row in rows] == [draft_only.pk, both.pk]
    rows = client.get(reverse("hybrid-builder"), {"status": "published"}).context["programme_rows"]
    assert [row["programme"].pk for row in rows] == [both.pk]
    # Combined search and filter.
    rows = client.get(reverse("hybrid-builder"), {"status": "draft", "q": "two-editions"}).context["programme_rows"]
    assert [row["programme"].pk for row in rows] == [both.pk]


@pytest.mark.django_db
def test_the_landing_shows_an_empty_state_without_programmes(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    response = client.get(reverse("hybrid-builder"))
    html = response.content.decode()
    assert "No Theory &amp; Practical programmes yet" in html or "No Theory & Practical programmes yet" in html
    assert "hyb-toolbar" not in html


# --- The New programme dialog -------------------------------------------------------


@pytest.mark.django_db
def test_the_dialog_opens_without_javascript(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder"), {"new": "programme"}).content.decode()
    assert re.search(r'<dialog[^>]*\bopen\b[^>]*>', html)
    assert "data-has-errors" not in html


@pytest.mark.django_db
def test_the_dialog_carries_csrf_and_the_creation_action(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder")).content.decode()
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'value="create_programme"' in html


@pytest.mark.django_db
def test_an_invalid_programme_post_reopens_the_dialog_with_values(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Kept name", "code": ""},
    )
    assert response.status_code == 400
    html = response.content.decode()
    assert "data-has-errors" in html
    assert 'value="Kept name"' in html
    # The empty code field is the one required error; the name kept its value.
    assert html.count("This field is required.") == 1


@pytest.mark.django_db
def test_a_taken_code_is_refused_in_the_dialog_without_creating(client, db):
    instructor = _instructor(db)
    existing, _ = _hybrid_programme("taken-code")
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Lookalike", "code": existing.code},
    )
    assert response.status_code == 400
    assert "already exists" in response.content.decode()
    assert not Programme.objects.filter(name="Lookalike").exists()


@pytest.mark.django_db
def test_creating_a_programme_still_redirects_with_a_draft_edition(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Coastal clearance", "code": "coastal-clearance"},
    )
    assert response.status_code == 302
    programme = Programme.objects.get(code="coastal-clearance")
    assert programme.learning_track == Programme.Track.HYBRID
    version = programme.versions.get()
    assert (version.version, version.status) == (1, ProgrammeVersion.Status.DRAFT)


@pytest.mark.django_db
def test_creating_a_programme_requires_a_csrf_token(db):
    instructor = _instructor(db)
    client = Client(enforce_csrf_checks=True)
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "No token", "code": "no-token"},
    )
    assert response.status_code == 403
    assert not Programme.objects.filter(code="no-token").exists()


# --- Manage programme (temporary target) ---------------------------------------------


@pytest.mark.django_db
def test_manage_programme_opens_the_workspace(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("managed")
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder")).content.decode()
    assert f'href="{reverse("hybrid-programme-detail", args=[programme.pk])}"' in html


@pytest.mark.django_db
def test_the_scoped_route_keeps_the_programme_authoring_page(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("scoped-page")
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder"), {"programme": programme.pk}).content.decode()
    assert programme.name in html
    assert "Create course" in html
    assert "<select" not in html
    assert 'name="programme"' in html
