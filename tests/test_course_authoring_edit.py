"""Stage 1 — draft editing: course name, modules (with prerequisite cycle
validation), lessons (details, reading sections, knowledge check), and
guided-practical content. Editing is draft-scoped: published courses cannot
be edited through the builder."""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import Assessment, AssessmentItem, AnswerOption, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Programme, ProgrammeVersion, Enrolment
from scenarios.models import Scenario, ScenarioState, ScenarioVersion


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="edit-instructor", email="edit@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=8, title="Stage 1 notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def draft_course(db):
    programme = Programme.objects.create(name="Editable Programme", code="editable")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module_a = Module.objects.create(programme_version=version, code="module-a", title="Module A", order=1)
    lesson = Lesson.objects.create(module=module_a, slug="editable-lesson", title="Editable Lesson", summary="Original summary", order=1)
    block = ContentBlock.objects.create(lesson=lesson, kind="text", heading="Original heading", body="Original body.", order=1)
    question = Question.objects.create(code="editable-question")
    question_version = QuestionVersion.objects.create(question=question, version=1, prompt="Original prompt?", explanation="Original explanation.", points=1)
    correct = AnswerOption.objects.create(question_version=question_version, label="Original correct", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Original distractor", is_correct=False, order=2)
    LessonCheck.objects.create(lesson=lesson, after_block=block, question_version=question_version, order=1)
    return {"version": version, "module_a": module_a, "lesson": lesson, "block": block, "question_version": question_version, "correct": correct}


@pytest.mark.django_db
def test_course_edit_renames_draft_course(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.post(reverse("course-edit", args=[draft_course["version"].pk]), {"name": "Renamed Programme"})
    assert response.status_code == 302
    draft_course["version"].refresh_from_db()
    assert draft_course["version"].programme.name == "Renamed Programme"


@pytest.mark.django_db
def test_published_course_cannot_be_edited(client, instructor):
    programme = Programme.objects.create(name="Published Programme", code="published")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    client.force_login(instructor)
    response = client.post(reverse("course-edit", args=[version.pk]), {"name": "Should Not Apply"})
    assert response.status_code == 404
    programme.refresh_from_db()
    assert programme.name == "Published Programme"


@pytest.mark.django_db
def test_module_edit_updates_fields_and_prerequisite(client, instructor, draft_course):
    module_b = Module.objects.create(programme_version=draft_course["version"], code="module-b", title="Module B", order=2)
    client.force_login(instructor)
    response = client.post(
        reverse("module-edit", args=[module_b.pk]),
        {"title": "Module B renamed", "description": "New description", "prerequisite": str(draft_course["module_a"].pk)},
    )
    assert response.status_code == 302
    module_b.refresh_from_db()
    assert module_b.title == "Module B renamed"
    assert module_b.description == "New description"
    assert module_b.prerequisite_id == draft_course["module_a"].pk


@pytest.mark.django_db
def test_module_edit_rejects_prerequisite_cycle(client, instructor, draft_course):
    module_a = draft_course["module_a"]
    module_b = Module.objects.create(programme_version=draft_course["version"], code="module-b", title="Module B", order=2, prerequisite=module_a)
    client.force_login(instructor)
    response = client.post(
        reverse("module-edit", args=[module_a.pk]),
        {"title": module_a.title, "description": "", "prerequisite": str(module_b.pk)},
    )
    # Module A must not require Module B when Module B already requires A.
    assert response.status_code == 200
    module_a.refresh_from_db()
    assert module_a.prerequisite_id is None
    assert "cycle" in response.content.decode().lower()


@pytest.mark.django_db
def test_lesson_edit_updates_details_blocks_and_check(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    check = LessonCheck.objects.get(lesson=lesson)
    distractor = check.question_version.options.get(is_correct=False)
    client.force_login(instructor)
    response = client.post(
        reverse("lesson-edit", args=[lesson.pk]),
        {
            "title": "Edited Lesson",
            "summary": "Edited summary.",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(draft_course["block"].pk),
            "form-0-heading": "Edited heading",
            "form-0-body": "Edited body copy.",
            "prompt": "Edited prompt?",
            "explanation": "Edited explanation.",
            "option_1": "Edited correct label",
            "option_2": "Edited distractor label",
            "correct_option": str(distractor.pk),
        },
    )
    assert response.status_code == 302
    lesson.refresh_from_db()
    assert lesson.title == "Edited Lesson"
    assert lesson.summary == "Edited summary."
    draft_course["block"].refresh_from_db()
    assert draft_course["block"].heading == "Edited heading"
    assert draft_course["block"].body == "Edited body copy."
    check.question_version.refresh_from_db()
    assert check.question_version.prompt == "Edited prompt?"
    assert check.question_version.explanation == "Edited explanation."
    assert check.question_version.options.get(pk=distractor.pk).label == "Edited distractor label"
    assert check.question_version.options.get(pk=distractor.pk).is_correct is True
    assert check.question_version.options.get(pk=draft_course["correct"].pk).is_correct is False


@pytest.mark.django_db
def test_lesson_edit_requires_correct_option_choice(client, instructor, draft_course):
    """The form refuses to save a check whose correct answer is not one of its options."""
    lesson = draft_course["lesson"]
    client.force_login(instructor)
    response = client.post(
        reverse("lesson-edit", args=[lesson.pk]),
        {
            "title": "Broken", "summary": "Broken",
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(draft_course["block"].pk), "form-0-heading": "h", "form-0-body": "b",
            "prompt": "p", "explanation": "e",
            "option_1": "a", "option_2": "b",
            "correct_option": "999999",
        },
    )
    assert response.status_code == 200
    lesson.refresh_from_db()
    assert lesson.title != "Broken"


@pytest.mark.django_db
def test_practical_edit_updates_content_and_states(client, instructor, draft_course):
    scenario = Scenario.objects.create(code="editable-practical", title="Editable Practical", area="import")
    practical = ScenarioVersion.objects.create(
        scenario=scenario, module=draft_course["module_a"], version=1,
        assistance_mode="beginner", briefing="Original briefing", learning_objective="Original objective", maximum_attempts=3,
    )
    state = ScenarioState.objects.create(scenario_version=practical, key="step-1", label="Original stage", guidance="Original guidance", order=1, is_initial=True)
    client.force_login(instructor)
    response = client.post(
        reverse("practical-edit", args=[practical.pk]),
        {
            "briefing": "Edited briefing",
            "learning_objective": "Edited objective",
            "assistance_mode": "intermediate",
            "maximum_attempts": "5",
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(state.pk),
            "form-0-label": "Edited stage",
            "form-0-guidance": "Edited stage guidance",
        },
    )
    assert response.status_code == 302
    practical.refresh_from_db()
    assert practical.briefing == "Edited briefing"
    assert practical.learning_objective == "Edited objective"
    assert practical.assistance_mode == "intermediate"
    assert practical.maximum_attempts == 5
    state.refresh_from_db()
    assert state.label == "Edited stage"
    assert state.guidance == "Edited stage guidance"


@pytest.mark.django_db
def test_edit_views_are_instructor_only(client, student_client_factory=None):
    from django.test import Client

    student = User.objects.create_user(username="edit-student", email="edit-student@example.test", password="test-password")
    client = Client()
    client.force_login(student)
    for url in [reverse("course-edit", args=["00000000-0000-0000-0000-000000000000"]), reverse("module-edit", args=["00000000-0000-0000-0000-000000000000"])]:
        assert client.get(url).status_code == 302  # redirected with a message, never an error page
