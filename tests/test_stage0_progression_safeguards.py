"""Stage 0 learning-progression safeguards.

1. A module cannot be published without a valid module assessment (students
   complete a module by passing that assessment, so an assessment-less module
   blocks the final exam, orientation, and every practical).
2. Attempt starts serialise on the student's enrolment row so repeated or
   simultaneous starts follow the single-active-attempt/resume rules.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from instructor_portal.views import _course_issues
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Programme, ProgrammeVersion
from scenarios.models import ScenarioActionDefinition, ScenarioState, ScenarioVersion
from scenarios.services import start_or_resume_attempt
from assessments.services import get_or_start_attempt


def _instructor(db):
    user = User.objects.create_user(username="stage0-instructor", email="stage0@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=9, title="Stage 0 notice", body="Training only.", is_current=True)
    )
    return user


def _draft_course(module_assessment=True, assessment_items=True, final_exam=True, final_exam_items=True):
    """A minimal valid draft course; flags control the assessments under test."""
    programme = Programme.objects.create(name="Stage 0 Programme", code="stage0")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="stage0-module", title="Stage 0 Module", order=1)
    lesson = Lesson.objects.create(module=module, slug="stage0-lesson", title="Stage 0 Lesson", order=1)
    ContentBlock.objects.create(lesson=lesson, heading="Key concept", body="Fictional teaching content.", order=1)
    question = Question.objects.create(code="stage0-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Pick the correct one.", explanation="Because.", points=1)
    AnswerOption.objects.create(question_version=question_version, label="Correct", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=ContentBlock.objects.first(), question_version=question_version, order=1)
    if module_assessment:
        assessment = Assessment.objects.create(
            programme_version=version, module=module, title="Stage 0 Module Assessment",
            assessment_type=Assessment.Type.MODULE, pass_percentage=70, is_published=True,
        )
        if assessment_items:
            AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=1)
    if final_exam:
        final = Assessment.objects.create(
            programme_version=version, title="Stage 0 Final Examination",
            assessment_type=Assessment.Type.FINAL_THEORY, pass_percentage=70, is_published=True,
        )
        if final_exam_items:
            AssessmentItem.objects.create(assessment=final, question_version=question_version, order=1)
    return version, module


@pytest.mark.django_db
def test_publish_blocked_when_module_assessment_missing(client):
    instructor = _instructor(None)
    version, _module = _draft_course(module_assessment=False)
    issues = _course_issues(version)
    assert any("Add a module assessment" in issue for issue in issues)

    client.force_login(instructor)
    response = client.post(reverse("course-publish", args=[version.pk]))
    assert response.status_code == 302
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_publish_blocked_when_module_assessment_has_no_questions(client):
    instructor = _instructor(None)
    version, _module = _draft_course(module_assessment=True, assessment_items=False)
    issues = _course_issues(version)
    assert any("must include at least one question" in issue for issue in issues)

    client.force_login(instructor)
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_publish_blocked_when_final_exam_missing(client):
    instructor = _instructor(None)
    version, _module = _draft_course(final_exam=False)
    issues = _course_issues(version)
    assert any("Add a final theory examination" in issue for issue in issues)

    client.force_login(instructor)
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_publish_blocked_when_final_exam_has_no_questions(client):
    instructor = _instructor(None)
    version, _module = _draft_course(final_exam=True, final_exam_items=False)
    issues = _course_issues(version)
    assert any("final theory examination must include at least one question" in issue for issue in issues)

    client.force_login(instructor)
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_publish_succeeds_with_valid_assessments(client):
    instructor = _instructor(None)
    version, module = _draft_course(module_assessment=True, assessment_items=True, final_exam=True, final_exam_items=True)
    assert _course_issues(version) == []

    client.force_login(instructor)
    response = client.post(reverse("course-publish", args=[version.pk]))
    assert response.status_code == 302
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    module.refresh_from_db()
    assert module.is_published


@pytest.mark.django_db
def test_review_page_lists_the_missing_assessment(client):
    instructor = _instructor(None)
    version, _module = _draft_course(module_assessment=False)
    client.force_login(instructor)
    response = client.get(reverse("course-review", args=[version.pk]))
    html = response.content.decode()
    assert "Add a module assessment" in html


@pytest.mark.django_db
def test_repeated_scenario_starts_resume_a_single_attempt():
    from django.utils import timezone
    from onboarding.models import Enrolment
    from progress.models import ProgrammeProgress

    programme = Programme.objects.create(name="Resume Programme", code="resume")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    student = User.objects.create_user(username="stage0-student", email="stage0-student@example.test", password="test-password")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    # Practical starts sit behind the orientation gate; satisfy it to test resume.
    ProgrammeProgress.objects.create(enrolment=enrolment, orientation_completed_at=timezone.now())
    scenario = ScenarioVersion.objects.create(
        scenario=__import__("scenarios.models", fromlist=["Scenario"]).Scenario.objects.create(
            code="stage0-scenario", title="Stage 0 Scenario", area="import"
        ),
        module=None, version=1, briefing="b", learning_objective="o",
    )
    first = ScenarioState.objects.create(scenario_version=scenario, key="step-1", label="Step one", order=1, is_initial=True)
    terminal = ScenarioState.objects.create(scenario_version=scenario, key="complete", label="Done", order=2, is_terminal=True)
    ScenarioActionDefinition.objects.create(
        scenario_version=scenario, code="complete-step-1", label="Step one", from_state=first, to_state=terminal, order=1
    )

    attempt, created = start_or_resume_attempt(enrolment, scenario)
    assert created is True
    for _ in range(3):
        again, created_again = start_or_resume_attempt(enrolment, scenario)
        assert created_again is False
        assert again.pk == attempt.pk


@pytest.mark.django_db
def test_repeated_assessment_starts_return_the_same_attempt():
    from assessments.models import Assessment as TheoryAssessment

    programme = Programme.objects.create(name="Theory Resume Programme", code="theory-resume")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    from onboarding.models import Enrolment

    student = User.objects.create_user(username="stage0-theory", email="stage0-theory@example.test", password="test-password")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    assessment = TheoryAssessment.objects.create(
        programme_version=version, title="Stage 0 Final", assessment_type=TheoryAssessment.Type.FINAL_THEORY,
        pass_percentage=70, is_published=True,
    )
    first = get_or_start_attempt(enrolment, assessment)
    for _ in range(3):
        again = get_or_start_attempt(enrolment, assessment)
        assert again.pk == first.pk


@pytest.mark.django_db
def test_scenario_attempt_limit_still_enforced_after_lock():
    from scenarios.models import Scenario
    from scenarios.services import practical_is_unlocked
    from progress.models import ProgrammeProgress
    from django.utils import timezone
    from django.core.exceptions import PermissionDenied

    programme = Programme.objects.create(name="Limit Programme", code="limit")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    from onboarding.models import Enrolment

    student = User.objects.create_user(username="stage0-limit", email="stage0-limit@example.test", password="test-password")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    ProgrammeProgress.objects.create(enrolment=enrolment, orientation_completed_at=timezone.now())
    assert practical_is_unlocked(enrolment)
    scenario_version = ScenarioVersion.objects.create(
        scenario=Scenario.objects.create(code="stage0-limit-scenario", title="Limited Scenario", area="export"),
        module=None, version=1, briefing="b", learning_objective="o", maximum_attempts=1,
    )
    first = ScenarioState.objects.create(scenario_version=scenario_version, key="step-1", label="Step one", order=1, is_initial=True)
    terminal = ScenarioState.objects.create(scenario_version=scenario_version, key="complete", label="Done", order=2, is_terminal=True)
    ScenarioActionDefinition.objects.create(
        scenario_version=scenario_version, code="complete-step-1", label="Step one", from_state=first, to_state=terminal, order=1
    )
    attempt, created = start_or_resume_attempt(enrolment, scenario_version)
    assert created is True
    # Exhaust the attempt, then confirm the limit still holds with the lock in place.
    from scenarios.services import perform_action

    perform_action(attempt, ScenarioActionDefinition.objects.get(code="complete-step-1"))
    with pytest.raises(PermissionDenied):
        start_or_resume_attempt(enrolment, scenario_version)
