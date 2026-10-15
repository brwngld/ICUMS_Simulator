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
def test_dashboard_recommends_the_next_lesson(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert response.context["primary_action"]["label"] == "Continue learning"
    assert response.context["primary_action"]["url"] == reverse(
        "lesson-detail", args=(theory_setup["module"].code, theory_setup["lesson"].slug)
    )
    html = response.content.decode()
    assert "Your learning roadmap" in html
    assert "Your training journey" in html
    assert "Account access" not in html


@pytest.mark.django_db
def test_dashboard_prioritises_module_assessment_after_lessons(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(
        enrolment=theory_setup["enrolment"],
        lesson=theory_setup["lesson"],
        completed_at=theory_setup["disclaimer"].published_at,
    )
    client.force_login(theory_setup["user"])

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert response.context["primary_action"]["label"] == "Take module assessment"
    assert response.context["primary_action"]["url"] == reverse(
        "assessment-take", args=(theory_setup["assessment"].pk,)
    )
    assert "Take module assessment" in response.content.decode()


@pytest.mark.django_db
def test_lesson_completion_is_saved_and_returns_to_module_overview(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    lesson_url = reverse("lesson-detail", args=(theory_setup["module"].code, theory_setup["lesson"].slug))
    response = client.post(lesson_url)
    for _ in range(4):
        response = client.post(response.url, {"action": "continue"})
    assert response.status_code == 302
    assert response.url == reverse("module-overview", args=(theory_setup["module"].code,))
    assert LessonProgress.objects.filter(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at__isnull=False).exists()


@pytest.mark.django_db
def test_lesson_sections_unlock_sequentially(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    first_url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "objectives"))
    practice_url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "practice"))
    assert client.get(first_url).status_code == 200
    locked = client.get(practice_url)
    assert locked.status_code == 302
    assert locked.url == first_url
    response = client.post(first_url, {"action": "continue"})
    assert response.url.endswith("/concepts/")


@pytest.mark.django_db
def test_lesson_base_url_resumes_first_unfinished_section(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.get(reverse("lesson-detail", args=(theory_setup["module"].code, theory_setup["lesson"].slug)))
    assert response.status_code == 302
    assert response.url.endswith("/objectives/")
    response = client.get(response.url)
    html = response.content.decode()
    assert "Mark Complete &amp; Continue" in html
    assert "learning-workspace-grid" in html
    assert "learning-workspace-aside" in html
    assert "Module 1" in html
    # §4: the global sidebar carries one roadmap entry, not individual lessons.
    assert "1. Lesson One" not in html
    assert "my-learning-lesson" not in html
    assert [crumb["title"] for crumb in response.context["breadcrumbs"]] == [
        "Home", "Theoretical Training", "Module 1", "Lesson 1"
    ]


@pytest.mark.django_db
def test_lesson_resources_card_only_appears_when_resources_exist(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "objectives"))

    with_resource = client.get(url).content.decode()
    assert "Lesson Resources" in with_resource
    assert "Review Lesson One" in with_resource
    assert with_resource.index("Lesson progress") < with_resource.index("Lesson Resources")

    resource = Resource.objects.get(title="Review Lesson One")
    resource.lessons.remove(theory_setup["lesson"])
    without_resource = client.get(url).content.decode()
    assert "Lesson Resources" not in without_resource


@pytest.mark.django_db
def test_sidebar_summarizes_current_section_and_refresher_is_contextual(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    LessonProgress.objects.create(
        enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], last_position=1,
    )
    concepts_url = reverse(
        "lesson-section",
        args=(theory_setup["module"].code, theory_setup["lesson"].slug, "concepts"),
    )
    concepts_page = client.get(concepts_url)
    concepts_html = concepts_page.content.decode()
    progress_card = concepts_html.split('class="lrn-card lrn-progress-card"', 1)[1].split(
        'class="lrn-card lrn-resources-card"', 1
    )[0]
    assert "Current section" in progress_card
    assert "Key concepts" in progress_card
    assert "lrn-nav-item" not in progress_card
    assert "Need a refresher?" not in concepts_html

    progress = LessonProgress.objects.get(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"])
    progress.last_position = 2
    progress.save(update_fields=("last_position", "updated_at"))
    example_url = reverse(
        "lesson-section",
        args=(theory_setup["module"].code, theory_setup["lesson"].slug, "example"),
    )
    example_html = client.get(example_url).content.decode()
    assert "Need a refresher?" in example_html
    assert f'href="{concepts_url}"' in example_html
    assert "Review key concepts →" in example_html


@pytest.mark.django_db
def test_module_overview_uses_real_lesson_and_assessment_state(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.get(reverse("module-overview", args=(theory_setup["module"].code,)))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Learning objectives" in html
    assert "Lessons in this module" in html
    assert "Module One Assessment" in html
    assert "Start module" in html
    assert response.context["progress_percentage"] == 0


@pytest.mark.django_db
def test_section_completion_is_explicit_and_idempotent(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "objectives"))
    client.get(url)
    progress = LessonProgress.objects.get(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"])
    assert progress.last_position == 0
    client.post(url, {"action": "continue"})
    client.post(url, {"action": "continue"})
    progress.refresh_from_db()
    assert progress.last_position == 1


@pytest.mark.django_db
def test_course_overview_uses_real_progress_modules_and_assessments(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    programme = theory_setup["enrolment"].programme_version.programme
    programme.overview_summary = "Understand standards and conformity requirements."
    programme.target_audience = "Customs officers learning the standards process."
    programme.learning_approach = "Read guided lessons\nApply knowledge in the simulator"
    programme.save(update_fields=("overview_summary", "target_audience", "learning_approach"))
    client.force_login(theory_setup["user"])
    response = client.get(reverse("roadmap"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "course-overview-layout" in html
    assert "Course modules" in html
    assert "Module One" in html
    assert "Lesson One" in html
    assert "Module assessments" in html
    assert "Understand standards and conformity requirements." in html
    assert "Customs officers learning the standards process." in html
    assert "Read guided lessons" in html
    assert "Apply knowledge in the simulator" in html
    assert response.context["total_lessons"] == 1
    assert response.context["course_percentage"] == 0
    assert response.context["next_lesson"] == theory_setup["lesson"]


@pytest.mark.django_db
def test_assessment_answers_resume_after_refresh_and_return_to_lesson(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], completed_at=theory_setup["disclaimer"].published_at)
    client.force_login(theory_setup["user"])
    lesson_url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "practice"))
    assessment_url = reverse("assessment-take", args=(theory_setup["assessment"].pk,))
    response = client.get(f"{assessment_url}?return_to={lesson_url}")
    attempt = TheoryAttempt.objects.get()
    save = client.post(
        assessment_url,
        {
            "action": "save_progress",
            "return_to": lesson_url,
            str(theory_setup["question"].pk): str(theory_setup["wrong"].pk),
        },
    )
    assert save.status_code == 204
    resumed = client.get(f"{assessment_url}?return_to={lesson_url}")
    assert "learning-workspace-page" in resumed.content.decode()
    assert "quiz-layout learning-workspace-grid" in resumed.content.decode()
    assert "quiz-aside learning-workspace-aside" in resumed.content.decode()
    assert "Mark for review" in resumed.content.decode()
    assert resumed.context["return_to"] == lesson_url
    assert resumed.context["saved_answers"][theory_setup["question"].pk] == theory_setup["wrong"].pk
    assert resumed.context["attempt"].pk == attempt.pk


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
    assert response.status_code == 302  # redirected back with a message, not a bare 403
    assert not TheoryAttempt.objects.exists()


@pytest.mark.django_db
def test_assessment_from_another_programme_is_forbidden(client, theory_setup):
    other_programme = Programme.objects.create(name="Other Programme", code="other-programme")
    other_version = ProgrammeVersion.objects.create(programme=other_programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    other_assessment = Assessment.objects.create(programme_version=other_version, title="Other Final", assessment_type=Assessment.Type.FINAL_THEORY, is_published=True)
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    response = client.get(reverse("assessment-take", args=(other_assessment.pk,)))
    assert response.status_code == 302  # other-programme assessments redirect with a message


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
    # Sections are dedicated pages: continuing from the base URL walks them in
    # order, and completing the last one finishes the lesson (-> assessment).
    seen = []
    for _ in range(6):
        response = client.post(lesson_url, {"action": "continue"})
        assert response.status_code == 302
        seen.append(response.url)
        if "/assessment" in response.url or "/theory/" not in response.url:
            break
    assert any(url.endswith("/practice/") for url in seen), seen
    progress = LessonProgress.objects.get(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"])
    assert progress.completed_at is not None
    assert second_block.order == 2


@pytest.mark.django_db
def test_practice_page_renders_and_answers_multiple_questions_independently(client, theory_setup):
    block = theory_setup["lesson"].blocks.get()
    first_check = LessonCheck.objects.create(
        lesson=theory_setup["lesson"], after_block=block,
        question_version=theory_setup["question"], order=1,
    )
    second_question = Question.objects.create(code="question-two")
    second_version = QuestionVersion.objects.create(
        question=second_question, version=1, prompt="Choose the second response.",
        explanation="Second explanation.", points=1, is_published=True,
    )
    second_correct = AnswerOption.objects.create(
        question_version=second_version, label="Second correct", is_correct=True, order=1,
    )
    AnswerOption.objects.create(
        question_version=second_version, label="Second wrong", is_correct=False, order=2,
    )
    second_check = LessonCheck.objects.create(
        lesson=theory_setup["lesson"], after_block=block,
        question_version=second_version, order=2,
    )
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    LessonProgress.objects.create(enrolment=theory_setup["enrolment"], lesson=theory_setup["lesson"], last_position=4)
    client.force_login(theory_setup["user"])
    url = reverse("lesson-section", args=(theory_setup["module"].code, theory_setup["lesson"].slug, "practice"))

    page = client.get(url)
    html = page.content.decode()
    assert html.index("Choose the correct response.") < html.index("Choose the second response.")
    assert "Question 1 of 2" in html
    assert "Question 2 of 2" in html
    assert "Theory assessment" not in html

    answered = client.post(
        url,
        {"action": "answer_check", "check_id": str(second_check.pk), "option": str(second_correct.pk)},
    )
    assert answered.status_code == 302
    assert LessonCheckResponse.objects.filter(
        enrolment=theory_setup["enrolment"], lesson_check=second_check, is_correct=True,
    ).count() == 1
    assert not LessonCheckResponse.objects.filter(lesson_check=first_check).exists()

    invalid = client.post(
        url,
        {"action": "answer_check", "check_id": "not-a-question", "option": str(theory_setup["correct"].pk)},
    )
    assert invalid.status_code == 302
    assert invalid.url.endswith("/practice/#feedback")
    assert LessonCheckResponse.objects.count() == 1


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
    assert client.get(url).status_code == 302  # attempt limit redirects with a message


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
    assert client.get(reverse("instructor-dashboard")).status_code == 302  # students are sent back with a message
    instructor = User.objects.create_user(username="instructor", email="instructor@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(instructor)
    response = client.get(reverse("instructor-dashboard"))
    assert response.status_code == 200
    assert b"learner" in response.content


@pytest.mark.django_db
def test_module_difficulty_badge_appears_only_when_set(client, theory_setup):
    DisclaimerAcceptance.objects.create(user=theory_setup["user"], disclaimer=theory_setup["disclaimer"])
    client.force_login(theory_setup["user"])
    module = theory_setup["module"]

    without = client.get(reverse("module-overview", args=[module.code]))
    assert "◇ Intermediate".encode() not in without.content
    assert "◇ Intermediate".encode() not in client.get(reverse("roadmap")).content

    module.difficulty = "intermediate"
    module.save(update_fields=("difficulty",))
    module_page = client.get(reverse("module-overview", args=[module.code]))
    assert "◇ Intermediate".encode() in module_page.content
    course_page = client.get(reverse("roadmap"))
    assert b"course-level" in course_page.content
    assert "◇ Intermediate".encode() in course_page.content
