"""Lesson-type foundation — the two lesson kinds and type-aware navigation.

``HybridLesson.kind`` separates Interactive Practical (authored in the
Demonstration Studio) from Guided Material Study (type stored, authoring and
publication still to come). Existing lessons are Interactive Practical by
default; Guided Material Study cannot be created from the instructor UI and
cannot publish, so no incomplete authoring path exists.
"""
import pytest
from django.test import Client
from django.urls import reverse

from django.contrib.auth.models import Group

from hybrid.models import HybridCourse, HybridLesson, HybridModule
from hybrid.publishing import clone_to_draft, lesson_issues
from onboarding.models import Programme, ProgrammeVersion


def _instructor(db, username="kind-instructor"):
    user = _user(db, username)
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def _user(db, username):
    from accounts.models import User

    return User.objects.create_user(username=username, email=f"{username}@example.test", password="x")


def _module_world(db, username="kind-instructor"):
    """Instructor plus a draft programme/course/module — the creation surface."""
    instructor = _instructor(db, username)
    programme = Programme.objects.create(
        name=f"Kinds {username}", code=username, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{username}-c", title=f"{username} course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{username}-m", title=f"{username} module", order=1)
    return {"instructor": instructor, "version": version, "course": course, "module": module}


def _module_url(module):
    return reverse("hybrid-module-edit", args=[module.pk])


def _studio_url(lesson):
    return reverse("hybrid-lesson-demonstration-studio", args=[lesson.pk])


@pytest.mark.django_db
def test_existing_style_rows_are_interactive_practical(db):
    """The migration's default: a lesson created without a kind — i.e. every
    lesson that predates the field — is an Interactive Practical."""
    world = _module_world(db, "kind-default")
    lesson = HybridLesson.objects.create(
        module=world["module"], slug="before", title="Before the field", order=1,
    )

    assert lesson.kind == HybridLesson.Kind.INTERACTIVE_PRACTICAL
    assert lesson.get_kind_display() == "Interactive Practical"


@pytest.mark.django_db
def test_the_module_page_offers_the_type_choice_with_guided_disabled(db):
    world = _module_world(db, "kind-choice")
    client = Client()
    client.force_login(world["instructor"])

    html = client.get(_module_url(world["module"])).content.decode()

    assert "Lesson type" in html
    assert "Interactive Practical" in html
    assert "Guided Material Study" in html
    # The Guided option is rendered but marked unavailable.
    assert 'value="guided_material_study"' in html
    guided_option = html.split('value="guided_material_study"', 1)[1].split(">", 1)[0]
    assert "disabled" in guided_option


@pytest.mark.django_db
def test_creating_an_interactive_lesson_opens_the_demonstration_studio(db):
    world = _module_world(db, "kind-create")
    client = Client()
    client.force_login(world["instructor"])

    response = client.post(_module_url(world["module"]), {
        "action": "create_lesson",
        "title": "UCR walkthrough",
        "kind": HybridLesson.Kind.INTERACTIVE_PRACTICAL,
        "summary": "Demonstrate the Single Window.",
    })

    lesson = HybridLesson.objects.get(module=world["module"], title="UCR walkthrough")
    assert lesson.kind == HybridLesson.Kind.INTERACTIVE_PRACTICAL
    assert response.status_code == 302
    assert response["Location"] == _studio_url(lesson)
    # The studio itself still renders for the fresh lesson.
    assert client.get(_studio_url(lesson)).status_code == 200


@pytest.mark.django_db
def test_a_post_without_a_kind_still_creates_interactive_practical(db):
    """Backward compatibility: scripted or legacy POSTs that predate the field
    create Interactive Practical lessons, exactly as the builder always has."""
    world = _module_world(db, "kind-legacy")
    client = Client()
    client.force_login(world["instructor"])

    response = client.post(_module_url(world["module"]), {
        "action": "create_lesson", "title": "Legacy flow", "summary": "",
    })

    lesson = HybridLesson.objects.get(module=world["module"], title="Legacy flow")
    assert lesson.kind == HybridLesson.Kind.INTERACTIVE_PRACTICAL
    assert response["Location"] == _studio_url(lesson)


@pytest.mark.django_db
def test_creating_a_guided_material_study_lesson_is_refused(db):
    """No incomplete authoring path: even a posted disabled option is refused,
    and no lesson row appears anywhere."""
    world = _module_world(db, "kind-refuse")
    client = Client()
    client.force_login(world["instructor"])

    response = client.post(_module_url(world["module"]), {
        "action": "create_lesson",
        "title": "Materials lesson",
        "kind": HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
        "summary": "Reading and materials.",
    })

    assert response.status_code == 302
    assert response["Location"] == _module_url(world["module"])
    assert not HybridLesson.objects.filter(module=world["module"]).exists()


@pytest.mark.django_db
def test_module_rows_are_type_aware(db):
    """Interactive rows lead to the Demonstration Studio with the full editor
    as fallback; a Guided row (only reachable via the ORM today) is labelled
    and offers no authoring entry."""
    world = _module_world(db, "kind-rows")
    interactive = HybridLesson.objects.create(
        module=world["module"], slug="interactive", title="Interactive lesson",
        order=1, summary="S.", theory="<p>Theory.</p>",
    )
    guided = HybridLesson.objects.create(
        module=world["module"], slug="guided", title="Guided lesson",
        order=2, kind=HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
    )
    client = Client()
    client.force_login(world["instructor"])

    html = client.get(_module_url(world["module"])).content.decode()

    assert _studio_url(interactive) in html
    assert "Open Demonstration Studio" in html
    assert "Full editor" in html
    assert reverse("hybrid-lesson-edit", args=[guided.pk]) not in html
    assert _studio_url(guided) not in html
    assert "Guided Material Study" in html
    assert "Material Studio coming soon" in html


@pytest.mark.django_db
def test_clone_to_draft_preserves_the_lesson_kind(db):
    world = _module_world(db, "kind-clone")
    HybridLesson.objects.create(
        module=world["module"], slug="interactive", title="Interactive",
        order=1, summary="S.", theory="<p>T.</p>",
    )
    HybridLesson.objects.create(
        module=world["module"], slug="guided", title="Guided",
        order=2, kind=HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
    )

    draft = clone_to_draft(world["version"])

    cloned = {lesson.title: lesson.kind for lesson in draft.hybrid_courses.get().hybrid_modules.get().hybrid_lessons.all()}
    assert cloned == {
        "Interactive": HybridLesson.Kind.INTERACTIVE_PRACTICAL,
        "Guided": HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
    }


@pytest.mark.django_db
def test_guided_material_study_lessons_cannot_publish_yet(db):
    """Publication keeps demanding learning-material functionality: a Guided
    lesson still fails the readiness gate, so the existing edition blocker —
    not new logic — is what holds it back until the Material Studio exists."""
    world = _module_world(db, "kind-publish")
    guided = HybridLesson.objects.create(
        module=world["module"], slug="guided", title="Guided",
        order=1, kind=HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
    )

    issues = " ".join(lesson_issues(guided))

    assert "No practical steps yet" in issues


@pytest.mark.django_db
def test_lesson_type_pages_require_the_instructor_group(db):
    """The type-aware surfaces stay gated: anonymous users and plain students
    never reach the module page or the studio it links to."""
    world = _module_world(db, "kind-guard")
    lesson = HybridLesson.objects.create(
        module=world["module"], slug="interactive", title="Interactive", order=1,
    )
    student = _user(db, "kind-student")
    student_client = Client()
    student_client.force_login(student)

    # The project's 403 handler redirects authenticated users instead of a
    # bare 403.
    assert student_client.get(_module_url(world["module"])).status_code == 302
    assert student_client.get(_studio_url(lesson)).status_code == 302
    assert student_client.post(_module_url(world["module"]), {
        "action": "create_lesson", "title": "Sneaky", "kind": HybridLesson.Kind.INTERACTIVE_PRACTICAL,
    }).status_code == 302
    assert not HybridLesson.objects.filter(title="Sneaky").exists()

    anonymous = Client()
    assert anonymous.get(_module_url(world["module"])).status_code == 302
    assert anonymous.get(_studio_url(lesson)).status_code == 302
