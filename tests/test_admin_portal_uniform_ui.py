"""Uniform view-mode UI contract for the admin/instructor portal.

The instructor portal must follow the simulator's form-design convention:
submitted (read-only) pages render the SAME form layout and control appearance
as their editable counterparts, with only editability differing (readonly/
disabled attributes), plus a "View mode" badge. The shared contract stylesheet
is static/css/instructor-portal.css, scoped by the .portal-main wrapper.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import Assessment, AssessmentItem, AnswerOption, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import Scenario, ScenarioState, ScenarioVersion

SHARED_CSS = "css/instructor-portal.css"


def make_instructor(username):
    instructor = User.objects.create_user(
        username=username, email=f"{username}@example.test", password="instructor-pass"
    )
    instructor.groups.add(Group.objects.get(name="Instructor"))
    return instructor


def make_draft_course(module_count=0):
    programme = Programme.objects.create(name="Uniform UI Programme", code="uniform-ui")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    for order in range(1, module_count + 1):
        Module.objects.create(
            programme_version=version,
            code=f"uniform-module-{order}",
            title=f"Uniform module {order}",
            description="Module description",
            order=order,
        )
    return version


@pytest.mark.django_db
def test_course_review_links_to_the_student_view_of_each_lesson(client):
    instructor = make_instructor("review-instructor")
    version = make_draft_course(module_count=1)
    module = version.modules.first()
    lesson = Lesson.objects.create(module=module, slug="uniform-lesson", title="Uniform Lesson Title", summary="Uniform summary copy", order=1)
    block = ContentBlock.objects.create(lesson=lesson, kind="text", heading="Key concept", body="Teaching body copy", order=1)
    question = Question.objects.create(code="uniform-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="What is being trained?", explanation="Because the flow requires it.", points=1)
    AnswerOption.objects.create(question_version=question_version, label="The correct step", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="A distractor step", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=question_version, order=1)
    # A complete course includes the module assessment its students need to
    # finish the module; without it the review page legitimately disables
    # publishing.
    module_assessment = Assessment.objects.create(
        programme_version=version, module=module, title="Uniform Module Assessment",
        assessment_type=Assessment.Type.MODULE, pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=module_assessment, question_version=question_version, order=1)
    final_exam = Assessment.objects.create(
        programme_version=version, title="Uniform Final Examination",
        assessment_type=Assessment.Type.FINAL_THEORY, pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=final_exam, question_version=question_version, order=1)

    client.force_login(instructor)
    response = client.get(reverse("course-review", args=(version.pk,)))
    assert response.status_code == 200
    content = response.content.decode()
    # Shared-CSS contract and view-mode indication.
    assert SHARED_CSS in content
    assert "portal-main" in content
    assert "view-mode-badge" in content
    # The review page hands the read-only content review to the student view,
    # so every lesson is reachable there in the learner presentation.
    assert reverse("lesson-preview", args=(lesson.pk,)) in content
    assert reverse("course-preview", args=(version.pk,)) in content
    assert reverse("module-preview", args=(module.pk,)) in content
    # With no outstanding issues nothing is disabled.
    assert "disabled" not in content


@pytest.mark.django_db
def test_course_review_links_to_the_student_view_of_each_practical(client):
    instructor = make_instructor("practical-review-instructor")
    version = make_draft_course(module_count=1)
    module = version.modules.first()
    scenario = Scenario.objects.create(code="uniform-practical", title="Uniform Practical Title", area="import")
    practical = ScenarioVersion.objects.create(
        scenario=scenario,
        module=module,
        version=1,
        assistance_mode=ScenarioVersion.AssistanceMode.BEGINNER,
        purpose=ScenarioVersion.Purpose.PRACTICE,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        maximum_attempts=3,
        briefing="Fictional briefing copy",
        learning_objective="Fictional objective copy",
        initial_data={},
    )
    ScenarioState.objects.create(scenario_version=practical, key="step-1", label="Review documents", order=1, is_initial=True)
    ScenarioState.objects.create(scenario_version=practical, key="step-2", label="Create UCR", order=2)

    client.force_login(instructor)
    response = client.get(reverse("course-review", args=(version.pk,)))
    assert response.status_code == 200
    content = response.content.decode()
    assert SHARED_CSS in content
    assert "view-mode-badge" in content
    # The guided practical is reviewed in the learner presentation, not as a
    # form dump on this page.
    assert reverse("practical-preview", args=(practical.pk,)) in content
    preview = client.get(reverse("practical-preview", args=(practical.pk,))).content.decode()
    assert "Fictional briefing copy" in preview
    assert "Review documents" in preview and "Create UCR" in preview


@pytest.mark.django_db
def test_course_review_blocks_publish_while_issues_outstanding(client):
    instructor = make_instructor("blocking-review-instructor")
    version = make_draft_course(module_count=0)
    client.force_login(instructor)
    response = client.get(reverse("course-review", args=(version.pk,)))
    assert response.status_code == 200
    content = response.content.decode()
    assert SHARED_CSS in content
    assert "view-mode-badge" in content
    assert "Not ready to publish" in content
    # Only the publish button is disabled; no controls are greyed by restyle.
    assert "disabled>Publish course</button>" in content


@pytest.mark.django_db
def test_student_detail_is_marked_as_read_only_view_mode(client):
    instructor = make_instructor("student-detail-instructor")
    student = User.objects.create_user(username="uniform-student", email="uniform-student@example.test", password="student-pass")
    version = make_draft_course(module_count=0)
    enrolment = Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)

    client.force_login(instructor)
    response = client.get(reverse("instructor-student-detail", args=(enrolment.pk,)))
    assert response.status_code == 200
    content = response.content.decode()
    assert SHARED_CSS in content
    assert "portal-main" in content
    assert "view-mode-badge" in content
    assert "shown read-only" in content


@pytest.mark.django_db
def test_credential_reveal_readonly_input_follows_shared_contract(client):
    # Issuance is roster-scoped, so the student must be an enrolled account.
    instructor = make_instructor("credential-uniform-instructor")
    student = User.objects.create_user(username="credential-student", email="credential-student@example.test", password="student-pass")
    student.groups.add(Group.objects.get(name="Student"))
    programme = Programme.objects.create(name="Reveal Contract Programme", code="reveal-contract-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)

    client.force_login(instructor)
    response = client.post(reverse("simulator-credential-issue", args=(student.pk,)))
    assert response.status_code == 200
    content = response.content.decode()
    assert SHARED_CSS in content
    assert "portal-main" in content
    assert 'id="one-time-password"' in content
    assert "readonly" in content


@pytest.mark.django_db
def test_uniform_view_mode_pages_require_instructor_role(client):
    outsider = User.objects.create_user(username="uniform-outsider", email="outsider@example.test", password="outsider-pass")
    version = make_draft_course(module_count=0)
    client.force_login(outsider)
    assert client.get(reverse("course-review", args=(version.pk,))).status_code == 302  # students are redirected with a message
    assert client.get(reverse("instructor-student-detail", args=(version.pk,))).status_code == 302  # students are redirected with a message
