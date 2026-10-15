"""Partial publishing: a course can go live with only the modules — and only
the lessons — an instructor has actually finished."""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _instructor(username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.create(version=11, title="Partial publish notice", body="Training only.", is_current=True),
    )
    return user


def _finished_lesson(module, slug, *, with_check=True):
    lesson = Lesson.objects.create(module=module, slug=slug, title=slug.replace("-", " ").title(), order=module.lessons.count() + 1)
    block = ContentBlock.objects.create(lesson=lesson, kind="text", heading="Concept", body="Explanation.", order=1)
    if with_check:
        question = Question.objects.create(code=f"{slug}-question")
        version = QuestionVersion.objects.create(question=question, version=1, prompt="Pick one.", explanation="Because.", points=1)
        AnswerOption.objects.create(question_version=version, label="Right", is_correct=True, order=1)
        AnswerOption.objects.create(question_version=version, label="Wrong", is_correct=False, order=2)
        LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=version, order=1)
    return lesson


def _course_with_two_modules(db):
    programme = Programme.objects.create(name="Partial Programme", code="partial")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    finished = Module.objects.create(programme_version=version, code="finished", title="Finished Module", order=1)
    unfinished = Module.objects.create(programme_version=version, code="unfinished", title="Unfinished Module", order=2)
    for module in (finished, unfinished):
        assessment = Assessment.objects.create(
            programme_version=version, module=module, title=f"{module.title} Assessment",
            assessment_type=Assessment.Type.MODULE, pass_percentage=70,
        )
        question = Question.objects.create(code=f"{module.code}-exam")
        question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Pick one.", explanation="Because.", points=1)
        AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
        AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
        AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
    final = Assessment.objects.create(
        programme_version=version, title="Final Examination",
        assessment_type=Assessment.Type.FINAL_THEORY, pass_percentage=70,
    )
    question = Question.objects.create(code="final-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Pick one.", explanation="Because.", points=1)
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
    AssessmentItem.objects.create(assessment=final, question_version=question_version)
    return {"version": version, "finished": finished, "unfinished": unfinished}


@pytest.mark.django_db
def test_publish_releases_finished_modules_and_holds_back_the_rest(client, db):
    course = _course_with_two_modules(db)
    _finished_lesson(course["finished"], "complete-lesson")
    _finished_lesson(course["unfinished"], "half-written-lesson", with_check=False)
    instructor = _instructor("partial-instructor")
    client.force_login(instructor)

    response = client.post(reverse("course-publish", args=[course["version"].pk]))
    assert response.status_code == 302
    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.PUBLISHED

    course["finished"].refresh_from_db()
    course["unfinished"].refresh_from_db()
    assert course["finished"].is_published
    assert not course["unfinished"].is_published
    assert course["finished"].lessons.first().is_published
    assert not course["unfinished"].lessons.first().is_published


@pytest.mark.django_db
def test_publish_releases_only_the_finished_lessons_of_a_module(client, db):
    course = _course_with_two_modules(db)
    _finished_lesson(course["finished"], "ready-one")
    _finished_lesson(course["finished"], "ready-two")
    _finished_lesson(course["finished"], "missing-check", with_check=False)
    client.force_login(_instructor("lesson-instructor"))

    client.post(reverse("course-publish", args=[course["version"].pk]))
    published = set(course["finished"].lessons.filter(is_published=True).values_list("slug", flat=True))
    assert published == {"ready-one", "ready-two"}


@pytest.mark.django_db
def test_learner_sees_published_module_and_not_the_draft_one(client, db):
    course = _course_with_two_modules(db)
    _finished_lesson(course["finished"], "visible-lesson")
    instructor = _instructor("learner-instructor")
    client.force_login(instructor)
    client.post(reverse("course-publish", args=[course["version"].pk]))

    learner = User.objects.create_user(username="partial-learner", email="partial-learner@example.test", password="test-password")
    learner.groups.add(Group.objects.get(name="Student"))
    Enrolment.objects.create(student=learner, programme_version=course["version"])
    DisclaimerAcceptance.objects.create(
        user=learner,
        disclaimer=DisclaimerVersion.objects.create(version=12, title="Learner notice", body="Training only.", is_current=True),
    )
    client.force_login(learner)
    roadmap = client.get(reverse("roadmap"))
    assert "Finished Module".encode() in roadmap.content
    assert "Unfinished Module".encode() not in roadmap.content
    assert client.get(reverse("module-overview", args=[course["finished"].code])).status_code == 200
    assert client.get(reverse("module-overview", args=[course["unfinished"].code])).status_code in (302, 403, 404)


@pytest.mark.django_db
def test_publish_is_blocked_when_no_module_is_finished(client, db):
    course = _course_with_two_modules(db)
    _finished_lesson(course["finished"], "no-knowledge-check", with_check=False)
    client.force_login(_instructor("blocked-instructor"))

    response = client.post(reverse("course-publish", args=[course["version"].pk]))
    assert response.status_code == 302
    course["version"].refresh_from_db()
    assert course["version"].status == ProgrammeVersion.Status.DRAFT
    assert not Module.objects.filter(programme_version=course["version"], is_published=True).exists()


@pytest.mark.django_db
def test_review_page_shows_what_publishes_and_what_waits(client, db):
    course = _course_with_two_modules(db)
    _finished_lesson(course["finished"], "ready")
    _finished_lesson(course["unfinished"], "waiting", with_check=False)
    client.force_login(_instructor("review-instructor"))

    page = client.get(reverse("course-review", args=[course["version"].pk])).content.decode()
    assert "Publishes now" in page
    assert "Stays in draft" in page
    assert "Ready to publish" in page
