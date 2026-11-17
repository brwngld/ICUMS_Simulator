"""Lesson-type foundation — the two lesson kinds and type-aware navigation.

``HybridLesson.kind`` separates Interactive Practical (authored in the
Demonstration Studio) from Guided Material Study (theory plus supporting
materials and optional knowledge checks, written in the lesson editor's
materials stage). Existing lessons are Interactive Practical by default;
both kinds now author and publish through their own readiness shapes.
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
def test_the_module_page_offers_the_type_choice(db):
    world = _module_world(db, "kind-choice")
    client = Client()
    client.force_login(world["instructor"])

    html = client.get(_module_url(world["module"])).content.decode()

    assert "Lesson type" in html
    assert "Interactive Practical" in html
    assert "Guided Material Study" in html
    # Both options are now selectable: Guided Material Study lessons author in
    # the lesson editor's materials stage.
    assert 'value="guided_material_study"' in html
    guided_option = html.split('value="guided_material_study"', 1)[1].split(">", 1)[0]
    assert "disabled" not in guided_option


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
    # The approved order: details and theory first in the lesson editor; the
    # Demonstration Studio is entered from there.
    assert response["Location"] == reverse("hybrid-lesson-edit", args=[lesson.pk])
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
    assert response["Location"] == reverse("hybrid-lesson-edit", args=[lesson.pk])


@pytest.mark.django_db
def test_creating_a_guided_material_study_lesson_opens_the_editor(db):
    """The lifted refusal: a Guided Material Study lesson is created and its
    kind is stored, and the editor it opens carries the guided materials
    stage rather than the practical-activities cards."""
    world = _module_world(db, "kind-guided-create")
    client = Client()
    client.force_login(world["instructor"])

    response = client.post(_module_url(world["module"]), {
        "action": "create_lesson",
        "title": "Materials lesson",
        "kind": HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
        "summary": "Reading and materials.",
    })

    lesson = HybridLesson.objects.get(module=world["module"], title="Materials lesson")
    assert lesson.kind == HybridLesson.Kind.GUIDED_MATERIAL_STUDY
    assert response.status_code == 302
    assert response["Location"] == reverse("hybrid-lesson-edit", args=[lesson.pk])

    html = client.get(response["Location"]).content.decode()
    assert "Supporting materials" in html
    assert "Knowledge checks" in html
    assert "Add practical activity" not in html
    assert "Open Demonstration Studio" not in html


@pytest.mark.django_db
def test_module_rows_are_type_aware(db):
    """Interactive rows lead to the Demonstration Studio with the full editor
    as fallback; a Guided row offers the editor (where its materials and
    knowledge checks live) and says plainly that the studio is not its tool."""
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
    assert reverse("hybrid-lesson-edit", args=[guided.pk]) in html
    assert _studio_url(guided) not in html
    assert "Guided Material Study" in html
    assert "Demonstration Studio applies to Interactive Practical lessons" in html


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
def test_guided_readiness_asks_for_materials_not_practical_steps(db):
    """Publication readiness is kind-aware: a Guided lesson is held back by
    missing supporting materials, never by practical steps — and one attached
    document satisfies it."""
    from hybrid.models import LessonMaterial

    world = _module_world(db, "kind-publish")
    guided = HybridLesson.objects.create(
        module=world["module"], slug="guided", title="Guided",
        order=1, kind=HybridLesson.Kind.GUIDED_MATERIAL_STUDY,
        summary="A guided reading.", theory="<p>Read alongside the document.</p>",
    )

    issues = " ".join(lesson_issues(guided))
    assert "No supporting materials yet" in issues
    assert "No practical steps yet" not in issues

    LessonMaterial.objects.create(lesson=guided, file="lesson_materials/notice.pdf", order=1)

    assert lesson_issues(guided) == []


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
