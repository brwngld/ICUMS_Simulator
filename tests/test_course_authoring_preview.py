"""Stage 4 — instructor preview of draft learning content.

Previews reuse the student presentation, are clearly labelled, are
instructor-only, and are strictly read-only: no attempts, progress,
completions, certificates, or progression changes may result from viewing.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import (
    Assessment,
    AssessmentItem,
    LessonCheck,
    Question,
    QuestionVersion,
    AnswerOption,
    TheoryAttempt,
)
from evaluations.models import PracticalEvaluation
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress
from reports.models import Certificate, CompletionRecord
from scenarios.models import (
    Scenario,
    ScenarioActionDefinition,
    ScenarioAttempt,
    ScenarioState,
    ScenarioVersion,
)


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="preview-instructor", email="preview@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=4, title="Stage 4 notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def draft_content(db):
    programme = Programme.objects.create(name="Preview Programme", code="preview")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="preview-module", title="Preview Module", order=1)
    lesson = Lesson.objects.create(module=module, slug="preview-lesson", title="Preview Lesson", summary="A draft lesson.", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Draft heading", body="Draft teaching body.", order=1)
    question = Question.objects.create(code="preview-check-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Check prompt?", explanation="Because.", points=1)
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=question_version, order=1)
    assessment = Assessment.objects.create(
        programme_version=version, module=module, title="Preview Module Assessment",
        assessment_type=Assessment.Type.MODULE,
    )
    exam = Assessment.objects.create(
        programme_version=version, title="Preview Final Exam", assessment_type=Assessment.Type.FINAL_THEORY,
    )
    scenario = Scenario.objects.create(code="preview-practical", title="Preview Practical", area="import")
    practical = ScenarioVersion.objects.create(
        scenario=scenario, module=module, version=1, assistance_mode="beginner",
        briefing="Preview briefing", learning_objective="Preview objective", maximum_attempts=3,
    )
    initial = ScenarioState.objects.create(scenario_version=practical, key="step-1", label="Preview stage", guidance="Do the thing.", order=1, is_initial=True)
    terminal = ScenarioState.objects.create(scenario_version=practical, key="complete", label="Done", order=2, is_terminal=True)
    ScenarioActionDefinition.objects.create(
        scenario_version=practical, code="complete-step-1", label="Preview stage", from_state=initial, to_state=terminal, order=1,
    )
    return {
        "version": version, "module": module, "lesson": lesson, "assessment": assessment,
        "exam": exam, "practical": practical,
    }


@pytest.mark.django_db
def test_instructor_can_preview_draft_lesson(client, instructor, draft_content):
    client.force_login(instructor)
    response = client.get(reverse("lesson-preview", args=[draft_content["lesson"].pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "PREVIEW" in html
    assert "Preview Lesson" in html
    assert "Draft teaching body." in html
    assert "Check prompt?" in html


@pytest.mark.django_db
def test_instructor_can_preview_assessments(client, instructor, draft_content):
    client.force_login(instructor)
    for assessment in (draft_content["assessment"], draft_content["exam"]):
        response = client.get(reverse("assessment-preview", args=[assessment.pk]))
        assert response.status_code == 200
        html = response.content.decode()
        assert "PREVIEW" in html
        assert assessment.title in html


@pytest.mark.django_db
def test_instructor_can_preview_guided_practical(client, instructor, draft_content):
    client.force_login(instructor)
    response = client.get(reverse("practical-preview", args=[draft_content["practical"].pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "PREVIEW" in html
    assert "Preview briefing" in html
    assert "Preview stage" in html


@pytest.mark.django_db
def test_previews_are_read_only(client, instructor, draft_content):
    """Viewing previews must not create attempts, progress, completions,
    certificates, or unlock anything."""
    client.force_login(instructor)
    client.get(reverse("lesson-preview", args=[draft_content["lesson"].pk]))
    client.get(reverse("assessment-preview", args=[draft_content["assessment"].pk]))
    client.get(reverse("assessment-preview", args=[draft_content["exam"].pk]))
    client.get(reverse("practical-preview", args=[draft_content["practical"].pk]))
    client.post(reverse("lesson-preview", args=[draft_content["lesson"].pk]))  # POST rejected

    assert LessonProgress.objects.count() == 0
    assert ModuleProgress.objects.count() == 0
    assert ProgrammeProgress.objects.count() == 0
    assert TheoryAttempt.objects.count() == 0
    assert ScenarioAttempt.objects.count() == 0
    assert PracticalEvaluation.objects.count() == 0
    assert CompletionRecord.objects.count() == 0
    assert Certificate.objects.count() == 0
    # The practical's guided flow is untouched: no terminal state reached.
    draft_content["practical"].refresh_from_db()
    assert draft_content["practical"].attempts.count() == 0


@pytest.mark.django_db
def test_lesson_preview_post_is_rejected(client, instructor, draft_content):
    """The student lesson template posts to the current path; preview must
    reject that so no progress action can ever fire."""
    client.force_login(instructor)
    response = client.post(reverse("lesson-preview", args=[draft_content["lesson"].pk]), {"action": "continue", "position": "0"})
    assert response.status_code == 405
    assert LessonProgress.objects.count() == 0


@pytest.mark.django_db
def test_draft_content_previews_without_publishing(client, instructor, draft_content):
    draft_content["version"].refresh_from_db()
    assert draft_content["version"].status == ProgrammeVersion.Status.DRAFT
    assert not draft_content["lesson"].is_published
    assert not draft_content["assessment"].is_published
    client.force_login(instructor)
    response = client.get(reverse("lesson-preview", args=[draft_content["lesson"].pk]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_unauthorized_users_cannot_preview(client, draft_content):
    student = User.objects.create_user(username="preview-student", email="preview-student@example.test", password="test-password")
    client.force_login(student)
    for url in [
        reverse("lesson-preview", args=[draft_content["lesson"].pk]),
        reverse("assessment-preview", args=[draft_content["assessment"].pk]),
        reverse("practical-preview", args=[draft_content["practical"].pk]),
    ]:
        assert client.get(url).status_code == 302  # redirected with a message
    from django.test import Client

    anonymous = Client()
    response = anonymous.get(reverse("lesson-preview", args=[draft_content["lesson"].pk]))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_builder_links_to_previews(client, instructor, draft_content):
    client.force_login(instructor)
    response = client.get(reverse("course-builder-detail", args=[draft_content["version"].pk]))
    html = response.content.decode()
    assert reverse("lesson-preview", args=[draft_content["lesson"].pk]) in html
    assert reverse("practical-preview", args=[draft_content["practical"].pk]) in html


@pytest.mark.django_db
def test_student_delivery_unchanged_by_preview(client, student_with_progress=None):
    """Guard: the student lesson flow still works exactly as before."""
    programme = Programme.objects.create(name="Guard Programme", code="guard")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    student = User.objects.create_user(username="guard-student", email="guard@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.get_or_create(
        user=student, disclaimer=DisclaimerVersion.objects.create(version=3, title="Guard notice", body="Training only.", is_current=True)
    )
    Enrolment.objects.create(student=student, programme_version=version, status="active")
    module = Module.objects.create(programme_version=version, code="guard-module", title="Guard Module", order=1, is_published=True)
    lesson = Lesson.objects.create(module=module, slug="guard-lesson", title="Guard Lesson", order=1, is_published=True)
    ContentBlock.objects.create(lesson=lesson, heading="h", body="b", order=1)
    client.force_login(student)
    response = client.get(reverse("lesson-detail", args=[module.code, lesson.slug]))
    assert response.status_code == 200
    assert "PREVIEW" not in response.content.decode()  # student view is never labelled as preview
    assert LessonProgress.objects.count() == 1  # normal student behaviour intact
