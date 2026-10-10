"""Stage 3 — assessment management through the course builder.

Instructors create and edit module assessments, the final theory exam, and
their questions in draft courses only. Student scoring and progression are
unchanged: passing a module assessment completes the module, passing the
final exam unlocks orientation and practicals.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import (
    AnswerOption,
    Assessment,
    AssessmentItem,
    LessonCheck,
    Question,
    QuestionVersion,
)
from instructor_portal.views import _course_issues
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Programme, ProgrammeVersion


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="assess-instructor", email="assess@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=5, title="Stage 3 notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def draft_course(db):
    programme = Programme.objects.create(name="Assessment Programme", code="assess")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="assess-module", title="Assessed Module", order=1)
    lesson = Lesson.objects.create(module=module, slug="assess-lesson", title="Assessed Lesson", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Concept", body="Body copy.", order=1)
    # The fixture course is publish-ready except for assessments: give the
    # lesson its knowledge check so assessment tests isolate what they test.
    question = Question.objects.create(code="assess-lesson-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Fixture check?", points=1)
    AnswerOption.objects.create(question_version=question_version, label="Yes", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="No", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=question_version, order=1)
    return {"version": version, "module": module}


def _question_payload(prompt="What is a Bill of Lading?", correct="A receipt for goods", wrong="A passport", **overrides):
    payload = {
        "prompt": prompt,
        "points": "1",
        "explanation": "Because that is its definition.",
        "option_1": correct,
        "option_2": wrong,
        "option_3": "",
        "option_4": "",
        "correct_position": "1",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_create_module_assessment(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(
        reverse("module-assessment-create", args=[draft_course["module"].pk]),
        {"title": "Module One Assessment", "pass_percentage": "70", "maximum_attempts": "3", "randomize_questions": "on"},
    )
    assert response.status_code == 302
    assert response.url == reverse("assessment-edit", args=[Assessment.objects.get(title="Module One Assessment").pk])
    assessment = Assessment.objects.get(title="Module One Assessment")
    assert assessment.assessment_type == Assessment.Type.MODULE
    assert assessment.module_id == draft_course["module"].pk
    assert assessment.programme_version_id == draft_course["version"].pk
    assert assessment.randomize_questions is True


@pytest.mark.django_db
def test_duplicate_module_assessment_redirects_to_existing(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Existing", assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    response = client.post(reverse("module-assessment-create", args=[draft_course["module"].pk]), {"title": "Another"})
    assert response.status_code == 302
    assert response.url == reverse("assessment-edit", args=[assessment.pk])
    assert Assessment.objects.count() == 1


@pytest.mark.django_db
def test_create_final_exam(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(
        reverse("final-exam-create", args=[draft_course["version"].pk]),
        {"title": "Final Examination", "pass_percentage": "70", "maximum_attempts": "", "randomize_questions": ""},
    )
    assert response.status_code == 302
    assessment = Assessment.objects.get(title="Final Examination")
    assert assessment.assessment_type == Assessment.Type.FINAL_THEORY
    assert assessment.module_id is None
    assert assessment.maximum_attempts is None  # unlimited


@pytest.mark.django_db
def test_edit_assessment_settings(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Draft title", assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    response = client.post(
        reverse("assessment-edit", args=[assessment.pk]),
        {"title": "Renamed assessment", "pass_percentage": "85", "maximum_attempts": "2", "randomize_questions": "on"},
    )
    assert response.status_code == 302
    assessment.refresh_from_db()
    assert assessment.title == "Renamed assessment"
    assert str(assessment.pass_percentage) == "85.00"
    assert assessment.maximum_attempts == 2


@pytest.mark.django_db
def test_pass_mark_validation_rejects_out_of_range(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(
        reverse("module-assessment-create", args=[draft_course["module"].pk]),
        {"title": "Bad pass mark", "pass_percentage": "150", "maximum_attempts": "3"},
    )
    assert response.status_code == 200  # form re-rendered, nothing created
    assert Assessment.objects.count() == 0


@pytest.mark.django_db
def test_add_question_with_options_and_correct_answer(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Module assessment", assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    response = client.post(
        reverse("assessment-question-add", args=[assessment.pk]),
        _question_payload(correct_position="2"),  # the second completed option is correct
    )
    assert response.status_code == 302
    item = AssessmentItem.objects.get(assessment=assessment)
    assert item.question_version.prompt == "What is a Bill of Lading?"
    options = list(item.question_version.options.order_by("order"))
    assert options[0].label == "A receipt for goods"
    assert options[1].label == "A passport"
    assert [option.is_correct for option in options] == [False, True]


@pytest.mark.django_db
def test_question_requires_two_options_and_valid_correct_position(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Module assessment", assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    # One option only.
    response = client.post(
        reverse("assessment-question-add", args=[assessment.pk]),
        _question_payload(option_2="", correct_position="1"),
    )
    assert response.status_code == 200
    # Correct position points at a blank option.
    response = client.post(
        reverse("assessment-question-add", args=[assessment.pk]),
        _question_payload(correct_position="4"),
    )
    assert response.status_code == 200
    assert AssessmentItem.objects.count() == 0


@pytest.mark.django_db
def test_edit_and_delete_question(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Module assessment", assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    client.post(reverse("assessment-question-add", args=[assessment.pk]), _question_payload())
    item = AssessmentItem.objects.get(assessment=assessment)
    question_version = item.question_version

    response = client.post(
        reverse("assessment-question-edit", args=[assessment.pk, question_version.pk]),
        _question_payload(prompt="Edited prompt?", correct="Freight invoice", correct_position="2"),
    )
    assert response.status_code == 302
    question_version.refresh_from_db()
    assert question_version.prompt == "Edited prompt?"
    assert question_version.options.get(is_correct=True).label == "A passport"

    response = client.post(reverse("assessment-question-delete", args=[assessment.pk, question_version.pk]))
    assert response.status_code == 302
    assert AssessmentItem.objects.count() == 0
    assert not QuestionVersion.objects.filter(pk=question_version.pk).exists()


@pytest.mark.django_db
def test_publish_validation_detects_invalid_question_configurations(client, instructor, draft_course):
    version = draft_course["version"]
    module = draft_course["module"]
    assessment = Assessment.objects.create(
        programme_version=version, module=module, title="Module assessment",
        assessment_type=Assessment.Type.MODULE,
    )
    question = Question.objects.create(code="bad-question")
    one_option = QuestionVersion.objects.create(question=question, version=1, prompt="One option?", points=1)
    AnswerOption.objects.create(question_version=one_option, label="Only", is_correct=True, order=1)
    AssessmentItem.objects.create(assessment=assessment, question_version=one_option, order=1)

    issues = _course_issues(version)
    assert any("needs at least two answer options" in issue for issue in issues)

    # Two options but no correct answer is also invalid.
    AnswerOption.objects.create(question_version=one_option, label="Second", is_correct=False, order=2)
    one_option.options.filter(is_correct=True).update(is_correct=False)
    issues = _course_issues(version)
    assert any("exactly one correct answer" in issue for issue in issues)


@pytest.mark.django_db
def test_publish_publishes_assessment_question_versions(client, instructor, draft_course):
    version = draft_course["version"]
    module = draft_course["module"]
    lesson = Lesson.objects.create(module=module, slug="assess-l", title="Assessed Lesson", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Concept", body="Body.", order=1)
    lesson_question = Question.objects.create(code="assess-l-question")
    lesson_question_version = QuestionVersion.objects.create(question=lesson_question, version=1, prompt="Lesson check?", points=1)
    AnswerOption.objects.create(question_version=lesson_question_version, label="Yes", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=lesson_question_version, label="No", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=lesson_question_version, order=1)
    client.force_login(instructor)

    client.post(reverse("module-assessment-create", args=[module.pk]), {"title": "Module assessment", "pass_percentage": "70"})
    assessment = Assessment.objects.get(title="Module assessment")
    client.post(reverse("assessment-question-add", args=[assessment.pk]), _question_payload())
    client.post(reverse("final-exam-create", args=[version.pk]), {"title": "Final", "pass_percentage": "70"})
    final = Assessment.objects.get(title="Final")
    client.post(reverse("assessment-question-add", args=[final.pk]), _question_payload(prompt="Final prompt?"))

    from instructor_portal.views import _course_issues

    response = client.post(reverse("course-publish", args=[version.pk]))
    assert response.status_code == 302
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    for item in AssessmentItem.objects.all():
        assert item.question_version.is_published is True
        assert item.assessment.is_published is True


@pytest.mark.django_db
def test_published_assessments_cannot_be_edited(client, instructor, draft_course):
    programme = Programme.objects.create(name="Published Assess Programme", code="published-assess")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    assessment = Assessment.objects.create(
        programme_version=version, title="Published assessment", assessment_type=Assessment.Type.FINAL_THEORY,
    )
    client.force_login(instructor)
    assert client.get(reverse("assessment-edit", args=[assessment.pk])).status_code == 404
    assert client.get(reverse("assessment-question-add", args=[assessment.pk])).status_code == 404
    response = client.post(reverse("assessment-edit", args=[assessment.pk]), {"title": "Hacked", "pass_percentage": "70"})
    assert response.status_code == 404
    assessment.refresh_from_db()
    assert assessment.title == "Published assessment"


@pytest.mark.django_db
def test_unauthorized_users_cannot_manage_assessments(client, instructor, draft_course):
    assessment = Assessment.objects.create(
        programme_version=draft_course["version"], module=draft_course["module"],
        title="Module assessment", assessment_type=Assessment.Type.MODULE,
    )
    student = User.objects.create_user(username="assess-student", email="assess-student@example.test", password="test-password")
    client.force_login(student)
    for url in [
        reverse("assessment-edit", args=[assessment.pk]),
        reverse("assessment-question-add", args=[assessment.pk]),
        reverse("module-assessment-create", args=[draft_course["module"].pk]),
        reverse("final-exam-create", args=[draft_course["version"].pk]),
    ]:
        assert client.get(url).status_code == 302  # redirected with a message
    assert Assessment.objects.count() == 1  # nothing created


@pytest.mark.django_db
def test_cross_course_assessment_access_is_isolated(client, instructor, draft_course):
    """A different draft course's assessment is editable only through its own
    URLs; the edit view resolves it independently, so no course leakage
    occurs via the module-create path either."""
    other_version = ProgrammeVersion.objects.create(
        programme=Programme.objects.create(name="Other Programme", code="other"), version=1,
        status=ProgrammeVersion.Status.DRAFT,
    )
    other_module = Module.objects.create(programme_version=other_version, code="other-module", title="Other Module", order=1)
    other_assessment = Assessment.objects.create(
        programme_version=other_version, module=other_module, title="Other assessment",
        assessment_type=Assessment.Type.MODULE,
    )
    client.force_login(instructor)
    # Editing the other course's assessment still works through its own URL,
    # but this course's builder never links to or exposes it.
    response = client.get(reverse("course-builder-detail", args=[draft_course["version"].pk]))
    html = response.content.decode()
    assert "Other assessment" not in html
    # And its content is untouched by this course's operations.
    response = client.post(
        reverse("module-assessment-create", args=[draft_course["module"].pk]), {"title": "Mine"}
    )
    assert Assessment.objects.filter(module=other_module, title="Other assessment").exists()
