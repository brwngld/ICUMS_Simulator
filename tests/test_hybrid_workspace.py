"""Stage 2 smoke: the hybrid workspace renders database-driven lessons beside
the live simulator, and refuses learners/lessons it should refuse."""
import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse

from accounts.models import User
from hybrid.models import HybridCourse, HybridLesson, HybridModule, PracticalStep
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name="Student")[0])
    disclaimer, _ = DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
    )
    DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)
    return user


def _edition(code, track=Programme.Track.HYBRID):
    """A published programme edition on a track, with its enrolment-less spine."""
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=track)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    return version


def _hybrid_lesson(version, code="lesson", with_content=True):
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{code}-course", title=f"{code} course", order=1, is_published=True,
    )
    module = HybridModule.objects.create(
        course=course, code=f"{code}-module", title=f"{code} module", order=1, is_published=True,
    )
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{code}-lesson", title=f"{code} journey", order=1, is_published=True,
        summary="A summary of the lesson.", theory="<p>Read this before the steps.</p>",
    )
    if with_content:
        PracticalStep.objects.create(
            lesson=lesson, key="open", title="Open the overview", order=1,
            instruction="Open the Single Window overview.", outcome="The overview is open.",
            hint="Use the navigation.", screen="single-window-overview",
        )
        PracticalStep.objects.create(
            lesson=lesson, key="search", title="Search declarations", order=2,
            instruction="Search the declarations.", outcome="The search form is open.",
            screen="single-window-search-ucr",
        )
    return lesson


# --- The workspace renders the lesson from the database -----------------------


@pytest.mark.django_db
def test_the_workspace_renders_the_lesson_from_the_database(client, db):
    learner = _learner(db, "hyb-reader")
    version = _edition("hyb-read")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version)
    client.force_login(learner)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert lesson.title in html
    assert "Read this before the steps." in html
    assert "Open the overview" in html
    assert "Search declarations" in html
    assert "Open the Single Window overview." in html
    assert "The overview is open." in html
    assert "Use the navigation." in html
    assert reverse("single-window-overview") in html


@pytest.mark.django_db
def test_every_step_card_carries_its_registered_screen(client, db):
    learner = _learner(db, "hyb-screens")
    version = _edition("hyb-screens")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version)
    PracticalStep.objects.create(
        lesson=lesson, key="same-screen", title="Stay on this screen", order=3,
        instruction="Keep working on the search screen.", screen="",  # blank keeps the current screen
    )
    client.force_login(learner)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert f'data-screen-url="{reverse("single-window-overview")}"' in html
    assert f'data-screen-url="{reverse("single-window-search-ucr")}"' in html
    assert 'data-screen-url=""' in html


@pytest.mark.django_db
def test_only_the_current_step_card_is_visible(client, db):
    learner = _learner(db, "hyb-cards")
    version = _edition("hyb-cards")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version)
    client.force_login(learner)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert 'data-hyb-step-card="0" data-screen-url' in html  # first card: server-visible
    assert 'data-hyb-step-card="1" data-screen-url' in html
    assert "hidden" in html
    assert "Step 1 of 2" in html


@pytest.mark.django_db
def test_a_lesson_without_steps_frames_the_simulator_portal(client, db):
    learner = _learner(db, "hyb-theoryonly")
    version = _edition("hyb-theoryonly")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version, code="nosteps", with_content=False)
    client.force_login(learner)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert f'src="{reverse("simulator-portal")}"' in html
    assert "no practical steps yet" in html


# --- Access rules -------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_learners_are_sent_to_login(client, db):
    version = _edition("hyb-anon")
    lesson = _hybrid_lesson(version)
    response = client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]


@pytest.mark.django_db
def test_a_theory_track_learner_is_refused_the_hybrid_workspace(client, db):
    learner = _learner(db, "theory-visitor")
    theory_version = _edition("theory-side", track=Programme.Track.THEORY)
    Enrolment.objects.create(student=learner, programme_version=theory_version)
    lesson = _hybrid_lesson(_edition("hyb-side"))
    client.force_login(learner)

    response = client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_a_hybrid_learner_still_needs_the_disclaimer(client, db):
    learner = _learner(db, "hyb-nodisclaimer")
    DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
    )
    version = _edition("hyb-nodisc")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version)
    DisclaimerAcceptance.objects.filter(user=learner).delete()
    client.force_login(learner)

    response = client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    assert response.status_code == 302
    assert reverse("disclaimer") in response.url


@pytest.mark.django_db
def test_an_unpublished_lesson_is_not_served(client, db):
    learner = _learner(db, "hyb-draft")
    version = _edition("hyb-draft")
    Enrolment.objects.create(student=learner, programme_version=version)
    lesson = _hybrid_lesson(version, code="draftlesson")
    HybridLesson.objects.filter(pk=lesson.pk).update(is_published=False)
    client.force_login(learner)
    assert client.get(reverse("hybrid-workspace", args=[lesson.pk])).status_code == 404


@pytest.mark.django_db
def test_a_lesson_from_another_edition_is_not_served(client, db):
    learner = _learner(db, "hyb-other")
    own = _edition("hyb-own")
    Enrolment.objects.create(student=learner, programme_version=own)
    other = _edition("hyb-other-v")
    foreign = _hybrid_lesson(other, code="foreign")
    client.force_login(learner)
    assert client.get(reverse("hybrid-workspace", args=[foreign.pk])).status_code == 404


# --- Content model behaviour ----------------------------------------------------


@pytest.mark.django_db
def test_step_screens_must_come_from_the_approved_registry(db):
    version = _edition("hyb-registry")
    lesson = _hybrid_lesson(version, code="registry", with_content=False)
    ok = PracticalStep(lesson=lesson, key="ok", title="Ok", screen="single-window-create-ucr", order=1)
    ok.full_clean()  # does not raise

    bad = PracticalStep(lesson=lesson, key="bad", title="Bad", screen="ucr-detail", order=2)
    with pytest.raises(ValidationError) as excinfo:
        bad.full_clean()
    assert "screen" in excinfo.value.message_dict


@pytest.mark.django_db
def test_theory_bodies_are_sanitised_on_save(db):
    version = _edition("hyb-sanitise")
    lesson = _hybrid_lesson(version, code="sanitise", with_content=False)
    lesson.theory = "<p>Fine</p><script>alert(1)</script>"
    lesson.save()
    assert "<script" not in lesson.theory
    assert "<p>Fine</p>" in lesson.theory


@pytest.mark.django_db
def test_steps_keep_their_configured_order(db):
    version = _edition("hyb-order")
    lesson = _hybrid_lesson(version, code="ordering", with_content=False)
    PracticalStep.objects.create(lesson=lesson, key="c", title="Third", order=3)
    PracticalStep.objects.create(lesson=lesson, key="a", title="First", order=1)
    PracticalStep.objects.create(lesson=lesson, key="b", title="Second", order=2)
    assert [step.key for step in lesson.practical_steps.all()] == ["a", "b", "c"]


@pytest.mark.django_db
def test_step_keys_are_unique_within_a_lesson(db):
    from django.db import IntegrityError, transaction

    version = _edition("hyb-keys")
    lesson = _hybrid_lesson(version, code="keys", with_content=False)
    PracticalStep.objects.create(lesson=lesson, key="dup", title="One", order=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            PracticalStep.objects.create(lesson=lesson, key="dup", title="Two", order=2)


# --- Project health --------------------------------------------------------------


def test_system_check_passes():
    call_command("check")
