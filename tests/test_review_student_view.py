"""Review page student view — the instructor sees the course as an enrolled student.

`course-preview` and `module-preview` reuse the learner templates and their
context builders, passing no enrolment so that draft content is included,
nothing is marked complete, and every link stays inside the read-only previews.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import Assessment, AnswerOption, LessonCheck, Question, QuestionVersion, TheoryAttempt
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="view-instructor", email="view-instructor@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=11, title="Student view notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def draft(db):
    programme = Programme.objects.create(name="View Programme", code="course-view")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(
        programme_version=version, code="view-module", title="View Module", order=1, description="Draft module."
    )
    lesson = Lesson.objects.create(module=module, slug="view-lesson", title="View Lesson", summary="Draft lesson.", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Draft heading", body="Draft teaching body.", order=1)
    question = Question.objects.create(code="view-check-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="View check?", explanation="Because.", points=1)
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=question_version, order=1)
    assessment = Assessment.objects.create(
        programme_version=version, module=module, title="View Module Assessment", assessment_type=Assessment.Type.MODULE
    )
    exam = Assessment.objects.create(
        programme_version=version, title="View Final Exam", assessment_type=Assessment.Type.FINAL_THEORY
    )
    return {"version": version, "module": module, "lesson": lesson, "assessment": assessment, "exam": exam}


@pytest.mark.django_db
def test_course_student_view_shows_the_draft_as_learners_see_it(client, instructor, draft):
    client.force_login(instructor)
    response = client.get(reverse("course-preview", args=[draft["version"].pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "how enrolled students will see the course" in html
    # Draft content is included even though nothing is published.
    assert "View Module" in html
    assert "View Lesson" in html
    assert "View Module Assessment" in html


@pytest.mark.django_db
def test_module_student_view_links_to_the_read_only_lesson_and_assessment(client, instructor, draft):
    client.force_login(instructor)
    response = client.get(reverse("module-preview", args=[draft["module"].pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "how enrolled students will see the course" in html
    assert reverse("lesson-preview", args=[draft["lesson"].pk]) in html
    assert reverse("assessment-preview", args=[draft["assessment"].pk]) in html
    # A draft lesson has no learner route, so no learner link may appear.
    assert reverse("lesson-detail", args=[draft["module"].code, draft["lesson"].slug]) not in html


@pytest.mark.django_db
def test_review_page_links_to_every_student_view(client, instructor, draft):
    client.force_login(instructor)
    response = client.get(reverse("course-review", args=[draft["version"].pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("course-preview", args=[draft["version"].pk]) in html
    assert reverse("module-preview", args=[draft["module"].pk]) in html
    assert reverse("lesson-preview", args=[draft["lesson"].pk]) in html
    assert reverse("assessment-preview", args=[draft["exam"].pk]) in html


@pytest.mark.django_db
def test_student_views_create_no_learner_records(client, instructor, draft):
    client.force_login(instructor)
    client.get(reverse("course-preview", args=[draft["version"].pk]))
    client.get(reverse("module-preview", args=[draft["module"].pk]))
    client.post(reverse("module-preview", args=[draft["module"].pk]))
    assert LessonProgress.objects.count() == 0
    assert ModuleProgress.objects.count() == 0
    assert ProgrammeProgress.objects.count() == 0
    assert TheoryAttempt.objects.count() == 0


@pytest.mark.django_db
def test_learners_cannot_open_the_instructor_student_views(client, instructor, draft):
    student = User.objects.create_user(username="view-student", email="view-student@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.get_or_create(
        user=student, disclaimer=DisclaimerVersion.objects.create(version=12, title="Learner notice", body="Training only.", is_current=True)
    )
    Enrolment.objects.create(student=student, programme_version=draft["version"], status="active")
    client.force_login(student)
    for url in [
        reverse("course-preview", args=[draft["version"].pk]),
        reverse("module-preview", args=[draft["module"].pk]),
    ]:
        assert client.get(url).status_code in (302, 403)


@pytest.mark.django_db
def test_published_learner_pages_keep_their_own_links(client, instructor, draft):
    """The shared context builder must not leak preview behaviour into delivery."""
    for instance in (draft["module"], draft["lesson"], draft["assessment"], draft["exam"]):
        instance.is_published = True
        instance.save()
    draft["version"].status = ProgrammeVersion.Status.PUBLISHED
    draft["version"].save()
    student = User.objects.create_user(username="delivered-student", email="delivered@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.get_or_create(
        user=student, disclaimer=DisclaimerVersion.objects.create(version=13, title="Delivery notice", body="Training only.", is_current=True)
    )
    Enrolment.objects.create(student=student, programme_version=draft["version"], status="active")
    client.force_login(student)
    response = client.get(reverse("roadmap"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "how enrolled students will see the course" not in html
    assert reverse("module-overview", args=[draft["module"].code]) in html
    assert reverse("lesson-detail", args=[draft["module"].code, draft["lesson"].slug]) in html

    overview = client.get(reverse("module-overview", args=[draft["module"].code]))
    assert overview.status_code == 200
    overview_html = overview.content.decode()
    assert reverse("lesson-detail", args=[draft["module"].code, draft["lesson"].slug]) in overview_html
    assert reverse("assessment-take", args=[draft["assessment"].pk]) in overview_html
