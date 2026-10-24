"""Stage 1 hybrid foundation: learning-track isolation and the curriculum tree.

The hybrid system hangs its content off the same ``Programme`` /
``ProgrammeVersion`` / ``Enrolment`` spine the theory portal uses, so the one
thing Stage 1 must prove is that the two tracks can never resolve each other's
enrolments however their enrolment dates are ordered — and that a learner
whose programmes are all theory notices nothing at all.
"""
from datetime import UTC, datetime

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import RequestFactory
from django.urls import reverse

from accounts.models import User
from hybrid import services as hybrid_services
from hybrid.models import HybridCourse, HybridLesson, HybridModule
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from onboarding.services import active_enrolments, enrolment_for_request, requested_enrolment


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name="Student")[0])
    disclaimer, _ = DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
    )
    DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)
    return user


def _programme(code, track=Programme.Track.THEORY):
    """A published programme edition on the given track."""
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=track)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    return programme, version


def _enrolment(learner, code, track=Programme.Track.THEORY, enrolled_at=None):
    _, version = _programme(code, track)
    enrolment = Enrolment.objects.create(student=learner, programme_version=version)
    if enrolled_at is not None:
        Enrolment.objects.filter(pk=enrolment.pk).update(enrolled_at=enrolled_at)
        enrolment.refresh_from_db()
    return enrolment


def _request(path="/", user=None, **query):
    request = RequestFactory().get(path, query)
    request.user = user
    return request


# --- The track discriminator -------------------------------------------------


@pytest.mark.django_db
def test_a_programme_created_the_old_way_lands_on_the_theory_track(db):
    programme = Programme.objects.create(name="Legacy programme", code="legacy")
    assert programme.learning_track == Programme.Track.THEORY


def test_the_track_discriminator_offers_exactly_the_two_tracks():
    assert set(Programme.Track.values) == {"theory", "hybrid"}


@pytest.mark.django_db
def test_no_pending_model_changes_were_left_unmigrated():
    from django.core.management import call_command

    call_command("makemigrations", check=True, dry_run=True, verbosity=0)


# --- Existing theory resolution is unchanged ---------------------------------


@pytest.mark.django_db
def test_theory_resolution_still_takes_the_oldest_active_enrolment(db):
    learner = _learner(db, "solo-theory")
    first = _enrolment(learner, "theory-a", enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    _enrolment(learner, "theory-b", enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    assert requested_enrolment(_request(user=learner)).pk == first.pk


@pytest.mark.django_db
def test_the_theory_programme_parameter_still_selects_an_enrolment(db):
    learner = _learner(db, "theory-choice")
    _enrolment(learner, "theory-a", enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    second = _enrolment(learner, "theory-b", enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    request = _request("/theory/", user=learner, programme="theory-b")
    assert requested_enrolment(request).pk == second.pk


@pytest.mark.django_db
def test_an_unknown_programme_parameter_still_selects_nothing(db):
    learner = _learner(db, "theory-unknown")
    _enrolment(learner, "theory-real")
    request = _request("/theory/", user=learner, programme="no-such-code")
    assert requested_enrolment(request) is None
    with pytest.raises(PermissionDenied):
        enrolment_for_request(request)


@pytest.mark.django_db
def test_active_enrolments_without_a_track_still_lists_both_tracks(db):
    """Listing surfaces such as My Programmes count every track."""
    learner = _learner(db, "list-both")
    theory = _enrolment(learner, "list-theory", track=Programme.Track.THEORY)
    hybrid = _enrolment(learner, "list-hybrid", track=Programme.Track.HYBRID)
    assert {e.pk for e in active_enrolments(learner)} == {theory.pk, hybrid.pk}


# --- Track isolation ---------------------------------------------------------


@pytest.mark.django_db
def test_a_theory_page_never_inherits_an_older_hybrid_enrolment(db):
    """The regression Stage 1 exists to fix: the fallback used to be the oldest
    enrolment overall, so an earlier Theory & Practical enrolment hijacked the
    theory portal. The hybrid enrolment here is deliberately the older one."""
    learner = _learner(db, "both-tracks")
    hybrid = _enrolment(learner, "hybrid-old", track=Programme.Track.HYBRID, enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    theory = _enrolment(learner, "theory-new", track=Programme.Track.THEORY, enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    assert hybrid.enrolled_at < theory.enrolled_at
    assert requested_enrolment(_request(user=learner)).pk == theory.pk


@pytest.mark.django_db
def test_a_hybrid_programme_parameter_selects_nothing_on_a_theory_route(db):
    learner = _learner(db, "param-guard")
    _enrolment(learner, "hybrid-p", track=Programme.Track.HYBRID)
    request = _request("/theory/", user=learner, programme="hybrid-p")
    assert requested_enrolment(request) is None
    with pytest.raises(PermissionDenied):
        enrolment_for_request(request)


@pytest.mark.django_db
def test_hybrid_resolution_ignores_theory_enrolments_whichever_is_older(db):
    learner = _learner(db, "hybrid-side")
    _enrolment(learner, "theory-old", track=Programme.Track.THEORY, enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    hybrid = _enrolment(learner, "hybrid-new", track=Programme.Track.HYBRID, enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    assert hybrid_services.active_enrolments(learner).first().pk == hybrid.pk
    assert hybrid_services.requested_enrolment(_request("/hybrid/", user=learner)).pk == hybrid.pk


@pytest.mark.django_db
def test_hybrid_fallback_takes_the_oldest_hybrid_enrolment(db):
    learner = _learner(db, "two-hybrid")
    first = _enrolment(learner, "hyb-a", track=Programme.Track.HYBRID, enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    _enrolment(learner, "hyb-b", track=Programme.Track.HYBRID, enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    assert hybrid_services.requested_enrolment(_request(user=learner)).pk == first.pk


@pytest.mark.django_db
def test_a_theory_only_learner_has_no_hybrid_enrolment_to_resolve(db):
    learner = _learner(db, "theory-only")
    _enrolment(learner, "theory-solo")
    assert list(hybrid_services.active_enrolments(learner)) == []
    assert hybrid_services.requested_enrolment(_request(user=learner)) is None
    with pytest.raises(PermissionDenied):
        hybrid_services.enrolment_for_request(_request(user=learner))


# --- Route behaviour ---------------------------------------------------------


@pytest.mark.django_db
def test_the_theory_roadmap_renders_for_a_learner_holding_both_tracks(client, db):
    """End to end: the hybrid enrolment came first, the roadmap still shows the
    theory programme."""
    learner = _learner(db, "roadmap-both")
    _enrolment(learner, "hyb-first", track=Programme.Track.HYBRID, enrolled_at=datetime(2026, 1, 1, tzinfo=UTC))
    theory = _enrolment(learner, "the-second", track=Programme.Track.THEORY, enrolled_at=datetime(2026, 2, 1, tzinfo=UTC))
    client.force_login(learner)
    response = client.get(reverse("roadmap"))
    assert response.status_code == 200
    assert response.context["enrolment"].pk == theory.pk


@pytest.mark.django_db
def test_a_hybrid_only_learner_is_refused_the_theory_roadmap_with_a_redirect(client, db):
    """The portal's usual warning-and-redirect, the same answer a learner with
    no enrolment at all has always had."""
    learner = _learner(db, "hybrid-only")
    _enrolment(learner, "hyb-only", track=Programme.Track.HYBRID)
    client.force_login(learner)
    response = client.get(reverse("roadmap"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    followed = client.get(response.url)
    message_text = " ".join(str(m) for m in followed.context["messages"])
    assert "No active programme enrolment was found." in message_text


@pytest.mark.django_db
def test_the_hybrid_namespace_serves_only_gated_pages(client, db):
    """Stage 4 added the roadmap and workspace to /hybrid/; everything under
    the prefix stays login- and enrolment-gated, and unknown paths are
    still plain 404s."""
    learner = _learner(db, "hybrid-visitor")
    _enrolment(learner, "hyb-visitor", track=Programme.Track.HYBRID)
    client.force_login(learner)
    assert client.get("/hybrid/").status_code == 200
    assert client.get("/hybrid/lessons/00000000-0000-0000-0000-000000000000/").status_code == 404


@pytest.mark.django_db
def test_anonymous_visitors_get_no_hybrid_page(client, db):
    assert client.get("/hybrid/").status_code == 302
    assert reverse("login") in client.get("/hybrid/").headers["location"]


@pytest.mark.django_db
def test_anonymous_visitors_are_sent_to_login(client, db):
    response = client.get(reverse("roadmap"))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]


# --- Curriculum models -------------------------------------------------------


@pytest.mark.django_db
def test_the_curriculum_hangs_off_the_version_not_the_enrolment(db):
    learner = _learner(db, "content-owner")
    _, version = _programme("content", Programme.Track.HYBRID)
    enrolment = Enrolment.objects.create(student=learner, programme_version=version)
    course = HybridCourse.objects.create(programme_version=version, code="c1", title="Course 1")
    module = HybridModule.objects.create(course=course, code="m1", title="Module 1")
    lesson = HybridLesson.objects.create(module=module, slug="l1", title="Lesson 1")

    assert version.hybrid_courses.get().pk == course.pk
    assert course.hybrid_modules.get().pk == module.pk
    assert module.hybrid_lessons.get().pk == lesson.pk

    enrolment.delete()
    assert HybridLesson.objects.filter(pk=lesson.pk).exists()


@pytest.mark.django_db
def test_curriculum_parents_are_protected_from_deletion(db):
    _, version = _programme("protect", Programme.Track.HYBRID)
    course = HybridCourse.objects.create(programme_version=version, code="pc", title="P course")
    module = HybridModule.objects.create(course=course, code="pm", title="P module")
    HybridLesson.objects.create(module=module, slug="pl", title="P lesson")
    with pytest.raises(ProtectedError):
        version.delete()
    with pytest.raises(ProtectedError):
        course.delete()
    with pytest.raises(ProtectedError):
        module.delete()


@pytest.mark.django_db
def test_curriculum_ordering_is_deterministic(db):
    _, version = _programme("ordering", Programme.Track.HYBRID)
    HybridCourse.objects.create(programme_version=version, code="o-b", title="B course", order=2)
    HybridCourse.objects.create(programme_version=version, code="o-a", title="A course", order=1)
    course = HybridCourse.objects.get(code="o-a")
    HybridModule.objects.create(course=course, code="om-b", title="B module", order=3)
    HybridModule.objects.create(course=course, code="om-a", title="A module", order=2)
    assert [c.code for c in HybridCourse.objects.all()] == ["o-a", "o-b"]
    assert [m.code for m in HybridModule.objects.all()] == ["om-a", "om-b"]
    # Equal orders fall back to the title, so order never depends on row ids.
    HybridCourse.objects.create(programme_version=version, code="o-c", title="C course", order=2)
    assert [c.code for c in HybridCourse.objects.filter(programme_version=version)] == ["o-a", "o-b", "o-c"]


@pytest.mark.django_db
def test_course_codes_are_unique_within_a_programme_version(db):
    _, first = _programme("codes-a", Programme.Track.HYBRID)
    _, second = _programme("codes-b", Programme.Track.HYBRID)
    HybridCourse.objects.create(programme_version=first, code="shared", title="First shared")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HybridCourse.objects.create(programme_version=first, code="shared", title="Duplicate")
    other_edition = HybridCourse.objects.create(programme_version=second, code="shared", title="Other edition")
    assert other_edition.pk is not None


@pytest.mark.django_db
def test_module_codes_are_unique_within_a_course(db):
    _, version = _programme("mod-codes", Programme.Track.HYBRID)
    first = HybridCourse.objects.create(programme_version=version, code="mc-1", title="Course one")
    second = HybridCourse.objects.create(programme_version=version, code="mc-2", title="Course two")
    HybridModule.objects.create(course=first, code="shared", title="Module one")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HybridModule.objects.create(course=first, code="shared", title="Duplicate")
    other_course = HybridModule.objects.create(course=second, code="shared", title="Other course")
    assert other_course.pk is not None


@pytest.mark.django_db
def test_lesson_slugs_are_unique_within_a_module(db):
    _, version = _programme("lesson-slugs", Programme.Track.HYBRID)
    course = HybridCourse.objects.create(programme_version=version, code="ls", title="Slug course")
    first = HybridModule.objects.create(course=course, code="lsm-1", title="Module one")
    second = HybridModule.objects.create(course=course, code="lsm-2", title="Module two")
    HybridLesson.objects.create(module=first, slug="shared", title="Lesson one")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            HybridLesson.objects.create(module=first, slug="shared", title="Duplicate")
    other_module = HybridLesson.objects.create(module=second, slug="shared", title="Other module")
    assert other_module.pk is not None


# --- Existing practical resolution still sees every track ---------------------


@pytest.mark.django_db
def test_practical_scenario_scoping_still_sees_both_tracks(db):
    """The scenario engine pins practical pages to the enrolment owning the
    attempt by filtering the unfiltered active_enrolments; that path must keep
    seeing every track."""
    learner = _learner(db, "scenario-scope")
    _enrolment(learner, "sc-theory", track=Programme.Track.THEORY)
    _enrolment(learner, "sc-hybrid", track=Programme.Track.HYBRID)
    codes = {e.programme_version.programme.code for e in active_enrolments(learner)}
    assert codes == {"sc-theory", "sc-hybrid"}
