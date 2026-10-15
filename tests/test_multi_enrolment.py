"""Multi-enrolment consistency.

A learner can hold several active enrolments while the portal has no way to
choose between them, so every student surface must resolve the *same* one: the
oldest active enrolment, with the primary key breaking ties because
``enrolled_at`` is not unique and an unordered query can pick a different row
per page.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from datetime import UTC

from django.utils import timezone

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, Question, QuestionVersion
from learning.models import Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=1, title="Notice", body="Training only.", is_current=True)
    )
    return user


def _enrolment(learner, code, module_code, assessment_title, enrolled_at=None):
    programme = Programme.objects.create(name=f"Programme {code}", code=code)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=learner, programme_version=version)
    module = Module.objects.create(programme_version=version, code=module_code, title=f"Module {code}", order=1, is_published=True)
    question_version = QuestionVersion.objects.create(question=Question.objects.create(code=f"q-{code}"), version=1, prompt="Pick one", points=1, is_published=True)
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    assessment = Assessment.objects.create(programme_version=version, module=module, title=assessment_title, pass_percentage=50, is_published=True)
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
    if enrolled_at is not None:
        Enrolment.objects.filter(pk=enrolment.pk).update(enrolled_at=enrolled_at)
        enrolment.refresh_from_db()
    return enrolment


@pytest.mark.django_db
def test_dashboard_reads_the_oldest_active_enrolment(client, db):
    learner = _learner(db, "oldest-learner")
    first = _enrolment(learner, "first-prog", "first-m", "First assessment", enrolled_at=timezone.datetime(2026, 1, 1, tzinfo=UTC))
    _enrolment(learner, "second-prog", "second-m", "Second assessment", enrolled_at=timezone.datetime(2026, 2, 1, tzinfo=UTC))
    client.force_login(learner)

    response = client.get(reverse("dashboard"))
    assert response.context["enrolment"].pk == first.pk
    html = response.content.decode()
    assert "Module first-prog" in html
    assert "Module second-prog" not in html


@pytest.mark.django_db
def test_dashboard_and_roadmap_agree_when_enrolments_share_a_timestamp(client, db):
    """Same-second enrolments used to be resolved by two different queries."""
    learner = _learner(db, "tied-learner")
    moment = timezone.datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    _enrolment(learner, "tied-a", "tied-a-m", "Tied A assessment", enrolled_at=moment)
    _enrolment(learner, "tied-b", "tied-b-m", "Tied B assessment", enrolled_at=moment)
    client.force_login(learner)

    dashboard_enrolment = client.get(reverse("dashboard")).context["enrolment"]
    roadmap_enrolment = client.get(reverse("roadmap")).context["enrolment"]
    assert dashboard_enrolment.pk == roadmap_enrolment.pk


@pytest.mark.django_db
def test_sidebar_assessment_link_comes_from_the_chosen_enrolment(client, db):
    learner = _learner(db, "sidebar-learner")
    first = _enrolment(learner, "nav-a", "nav-a-m", "Nav A assessment", enrolled_at=timezone.datetime(2026, 4, 1, tzinfo=UTC))
    _enrolment(learner, "nav-b", "nav-b-m", "Nav B assessment", enrolled_at=timezone.datetime(2026, 4, 2, tzinfo=UTC))
    client.force_login(learner)

    assessment = Assessment.objects.get(programme_version=first.programme_version)
    html = client.get(reverse("dashboard")).content.decode()
    assert reverse("assessment-take", args=[assessment.pk]) in html
    other = Assessment.objects.get(programme_version__programme__code="nav-b")
    assert reverse("assessment-take", args=[other.pk]) not in html
