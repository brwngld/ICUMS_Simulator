import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, LessonCheckResponse, Question, QuestionVersion, TheoryAttempt
from learning.models import ContentBlock, Lesson, Module, Resource
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress


@pytest.fixture
def theory_setup(db):
    user = User.objects.create_user(username="learner", email="learner@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    programme = Programme.objects.create(name="Test Programme", code="test-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    disclaimer = DisclaimerVersion.objects.create(version=1, title="Training notice", body="This is not official ICUMS.", is_current=True)
    module = Module.objects.create(programme_version=version, code="module-one", title="Module One", order=1, is_published=True)
    lesson = Lesson.objects.create(module=module, slug="lesson-one", title="Lesson One", order=1, is_published=True)
    ContentBlock.objects.create(lesson=lesson, heading="Example", body="Fictional lesson content.")
    resource = Resource.objects.create(title="Review Lesson One")
    resource.lessons.add(lesson)
    question = Question.objects.create(code="question-one")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Choose the correct response.", explanation="Review the example.", points=2, is_published=True, remediation_resource=resource)
    correct = AnswerOption.objects.create(question_version=question_version, label="Correct", is_correct=True, order=1)
    wrong = AnswerOption.objects.create(question_version=question_version, label="Incorrect", is_correct=False, order=2)
    assessment = Assessment.objects.create(programme_version=version, module=module, title="Module One Assessment", pass_percentage=70, is_published=True)
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
    return {"user": user, "enrolment": enrolment, "disclaimer": disclaimer, "module": module, "lesson": lesson, "assessment": assessment, "question": question_version, "correct": correct, "wrong": wrong}


@pytest.mark.django_db
def test_current_disclaimer_blocks_dashboard_until_accepted(client, theory_setup):
    client.force_login(theory_setup["user"])
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert response.url == reverse("disclaimer")
    response = client.post(reverse("disclaimer"), {"accept": "yes"})
    assert response.status_code == 302
    assert DisclaimerAcceptance.objects.filter(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"]).exists()


@pytest.mark.django_db
def test_lesson_completion_is_saved_and_opens_assessment(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.post(reverse("lesson-detail", args=(theory_setup["module"].code, theory_setup["lesson"].slug)))
    assert response.status_code == 302
    assert response.url == reverse("assessment-take", args=(theory_setup["assessment"].pk,))
    assert LessonProgress.objects.filter(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at__isnull=False).exists()


@pytest.mark.django_db
def test_failed_attempt_keeps_remediation_and_does_not_complete_module(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at=theory_setup["disclaimer"].published_at)
    client.force_login(theory_setup["user"])
    response = client.post(reverse("assessment-take", args=(theory_setup["assessment"].pk,)), {str(theory_setup["question"].pk): str(theory_setup["wrong"].pk)})
    attempt = TheoryAttempt.objects.get()
    assert response.status_code == 302
    assert attempt.outcome == TheoryAttempt.Outcome.FAIL
    assert attempt.percentage == 0
    assert attempt.responses.get().question_version.remediation_resource is not None
    assert not ModuleProgress.objects.filter(enrolment=theory_setup["enrolment"], module=theory_setup["module"], status=ModuleProgress.Status.COMPLETED).exists()


@pytest.mark.django_db
def test_attempts_are_append_only_and_time_does_not_change_score(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at=theory_setup["disclaimer"].published_at)
    client.force_login(theory_setup["user"])
    url = reverse("assessment-take", args=(theory_setup["assessment"].pk,))
    answer = {str(theory_setup["question"].pk): str(theory_setup["correct"].pk)}
    client.post(url, answer)
    client.post(url, answer)
    attempts = list(TheoryAttempt.objects.order_by("attempt_number"))
    assert [attempt.attempt_number for attempt in attempts] == [1, 2]
    assert all(attempt.score == 2 and attempt.percentage == 100 for attempt in attempts)
    assert all(attempt.duration_seconds is not None for attempt in attempts)
    assert ModuleProgress.objects.get(enrolment=theory_setup["enrolment"], module=theory_setup["module"]).status == ModuleProgress.Status.COMPLETED


@pytest.mark.django_db
def test_assessment_is_locked_until_all_lessons_are_completed(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.get(reverse("assessment-take", args=(theory_setup["assessment"].pk,)))
    assert response.status_code == 403
    assert not TheoryAttempt.objects.exists()


@pytest.mark.django_db
def test_assessment_from_another_programme_is_forbidden(client, theory_setup):
    other_programme = Programme.objects.create(name="Other Programme", code="other-programme")
    other_version = ProgrammeVersion.objects.create(programme=other_programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    other_assessment = Assessment.objects.create(programme_version=other_version, title="Other Final", assessment_type=Assessment.Type.FINAL_THEORY, is_published=True)
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.get(reverse("assessment-take", args=(other_assessment.pk,)))
    assert response.status_code == 403


@pytest.mark.django_db
def test_lesson_position_and_embedded_check_are_saved(client, theory_setup):
    second_block = ContentBlock.objects.create(lesson=theory_setup["lesson"], heading="Second", body="Second section.", order=2)
    first_block = theory_setup["lesson"].blocks.order_by("order").first()
    check = LessonCheck.objects.create(lesson=theory_setup["lesson"], after_block=first_block, question_version=theory_setup["question"])
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    lesson_url = reverse("lesson-detail", args=(theory_setup["module"].code, theory_setup["lesson"].slug))
    response = client.post(lesson_url, {"action": "answer_check", "position": 0, "check_id": check.pk, "option": theory_setup["correct"].pk})
    assert response.status_code == 302
    assert LessonCheckResponse.objects.get().is_correct is True
    response = client.post(lesson_url, {"action": "continue", "position": 0})
    progress = LessonProgress.objects.get(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"])
    assert response.url.endswith("?step=1")
    assert progress.last_position == 0
    assert progress.completed_at is None
    assert second_block.order == 2


@pytest.mark.django_db
def test_attempt_question_set_is_frozen_and_attempt_limit_is_enforced(client, theory_setup):
    theory_setup["assessment"].maximum_attempts = 1
    theory_setup["assessment"].save(update_fields=("maximum_attempts",))
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at=theory_setup["disclaimer"].published_at)
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    url = reverse("assessment-take", args=(theory_setup["assessment"].pk,))
    response = client.get(url)
    assert response.status_code == 200
    attempt = TheoryAttempt.objects.get()
    assert attempt.items.count() == 1
    extra_question = Question.objects.create(code="late-question")
    extra_version = QuestionVersion.objects.create(question=extra_question, version=1, prompt="Added later", points=10, is_published=True)
    AssessmentItem.objects.create(assessment=theory_setup["assessment"], question_version=extra_version, order=2)
    client.post(url, {str(theory_setup["question"].pk): str(theory_setup["correct"].pk)})
    attempt.refresh_from_db()
    assert attempt.maximum_score == 2
    assert attempt.percentage == 100
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_final_theory_pass_unlocks_orientation(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at=theory_setup["disclaimer"].published_at)
    ModuleProgress.objects.create(enrolment=theory_setup["enrolment"], module=theory_setup["module"], status=ModuleProgress.Status.COMPLETED)
    final = Assessment.objects.create(programme_version=theory_setup["enrolment"].programme_version, title="Final Theory", assessment_type=Assessment.Type.FINAL_THEORY, pass_percentage=70, is_published=True)
    AssessmentItem.objects.create(assessment=final, question_version=theory_setup["question"])
    client.force_login(theory_setup["user"])
    response = client.post(reverse("assessment-take", args=(final.pk,)), {str(theory_setup["question"].pk): str(theory_setup["correct"].pk)})
    assert response.status_code == 302
    programme_progress = ProgrammeProgress.objects.get(enrolment=theory_setup["enrolment"])
    assert programme_progress.orientation_unlocked_at is not None
    orientation_url = reverse("orientation")
    assert client.get(orientation_url).status_code == 200
    client.post(orientation_url)
    programme_progress.refresh_from_db()
    assert programme_progress.orientation_completed_at is not None


@pytest.mark.django_db
def test_instructor_portal_rejects_student_and_allows_instructor(client, theory_setup):
    client.force_login(theory_setup["user"])
    assert client.get(reverse("instructor-dashboard")).status_code == 403
    instructor = User.objects.create_user(username="instructor", email="instructor@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(instructor)
    response = client.get(reverse("instructor-dashboard"))
    assert response.status_code == 200
    assert b"learner" in response.content
