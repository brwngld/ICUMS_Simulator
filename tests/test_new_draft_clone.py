"""Creating a new draft from a published course copies its authoring content.

The draft must carry everything an instructor would otherwise retype, use fresh
question and scenario version rows so editing it cannot change the live course,
and must never carry learner records with it.
"""
import base64

import pytest
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from evaluations.models import Rubric, RubricCriterion, RubricVersion
from learning.models import ContentBlock, Lesson, Module, Resource
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress
from reports.models import CompletionPolicy
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioDocument, ScenarioState, ScenarioVersion

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def media_root(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"


def _question(code, prompt):
    version = QuestionVersion.objects.create(question=Question.objects.create(code=code), version=1, prompt=prompt, explanation="Because.", points=1)
    AnswerOption.objects.create(question_version=version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=version, label="Wrong", is_correct=False, order=2)
    return version


@pytest.fixture
def live_course(db):
    instructor = User.objects.create_user(username="clone-author", email="clone@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=instructor,
        disclaimer=DisclaimerVersion.objects.create(version=21, title="Clone notice", body="Training only.", is_current=True),
    )

    programme = Programme.objects.create(name="Clone Programme", code="clone-programme")
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED, published_at=timezone.now()
    )
    first = Module.objects.create(
        programme_version=version, code="clone-one", title="Module One", order=1, difficulty="intermediate", is_published=True
    )
    first.cover_image.save("clone-one.png", ContentFile(PNG_BYTES), save=False)
    first.save()
    second = Module.objects.create(
        programme_version=version, code="clone-two", title="Module Two", order=2, prerequisite=first, is_published=True
    )

    lesson = Lesson.objects.create(module=first, slug="clone-lesson", title="Clone Lesson", order=1, is_published=True)
    ContentBlock.objects.create(lesson=lesson, heading="Intro", body="Read this first.", order=1)
    detail = ContentBlock.objects.create(lesson=lesson, heading="Detail", body="The detail.", order=2)
    Resource.objects.create(title="Reference note", url="https://example.test/note").lessons.add(lesson)
    LessonCheck.objects.create(lesson=lesson, after_block=detail, question_version=_question("clone-check", "Which lane?"), order=1)

    module_assessment = Assessment.objects.create(
        programme_version=version, module=first, title="Module One Assessment",
        assessment_type=Assessment.Type.MODULE, pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=module_assessment, question_version=_question("clone-module-item", "Module question?"))
    final_exam = Assessment.objects.create(
        programme_version=version, title="Final Examination",
        assessment_type=Assessment.Type.FINAL_THEORY, pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=final_exam, question_version=_question("clone-final-item", "Final question?"))

    scenario = Scenario.objects.create(code="clone-practical", title="Clone Practical", area="import")
    practical = ScenarioVersion.objects.create(
        scenario=scenario, module=first, version=1, status=ScenarioVersion.Status.PUBLISHED,
        briefing="Brief the learner.", learning_objective="Clear the consignment.", published_at=timezone.now(),
    )
    start = ScenarioState.objects.create(scenario_version=practical, key="start", label="Start", order=1, is_initial=True)
    finish = ScenarioState.objects.create(scenario_version=practical, key="finish", label="Finish", order=2, is_terminal=True)
    ScenarioActionDefinition.objects.create(scenario_version=practical, code="go", label="Proceed", from_state=start, to_state=finish)
    ScenarioDocument.objects.create(scenario_version=practical, document_type="ucr", title="UCR")
    rubric = Rubric.objects.create(code="clone-rubric", title="Clone rubric")
    rubric_version = RubricVersion.objects.create(
        rubric=rubric, version=1, scenario_version=practical,
        status=RubricVersion.Status.PUBLISHED, pass_percentage=70, published_at=timezone.now(),
    )
    RubricCriterion.objects.create(
        rubric_version=rubric_version, code="accuracy", title="Accuracy", dimension="accuracy",
        maximum_points=5, evaluation_rule={"type": "completion"},
    )

    learner = User.objects.create_user(username="clone-learner", email="clone-learner@example.test", password="test-password")
    learner.groups.add(Group.objects.get(name="Student"))
    LessonProgress.objects.create(
        enrolment=Enrolment.objects.create(student=learner, programme_version=version),
        lesson=lesson,
        completed_at=timezone.now(),
    )

    return {"instructor": instructor, "programme": programme, "version": version, "first": first, "second": second, "lesson": lesson}


def _create_draft(client, live_course):
    client.force_login(live_course["instructor"])
    response = client.post(reverse("course-new-draft", args=[live_course["version"].pk]))
    assert response.status_code == 302
    return ProgrammeVersion.objects.get(programme=live_course["programme"], version=2)


@pytest.mark.django_db
def test_new_draft_carries_the_whole_content_graph(client, live_course):
    draft = _create_draft(client, live_course)

    assert draft.status == ProgrammeVersion.Status.DRAFT
    modules = {module.code: module for module in draft.modules.all()}
    assert set(modules) == {"clone-one", "clone-two"}
    assert modules["clone-one"].difficulty == "intermediate"
    assert modules["clone-two"].prerequisite_id == modules["clone-one"].pk
    assert not draft.modules.filter(is_published=True).exists()
    assert not draft.assessments.filter(is_published=True).exists()

    lesson = modules["clone-one"].lessons.get(slug="clone-lesson")
    assert not lesson.is_published
    assert [block.heading for block in lesson.blocks.all()] == ["Intro", "Detail"]
    assert [option.label for option in lesson.knowledge_checks.get().question_version.options.all()] == ["Right", "Wrong"]

    check = lesson.knowledge_checks.get()
    # The copied check must follow the copied section, not the live course's one.
    assert check.after_block.lesson_id == lesson.pk
    assert check.question_version.prompt == "Which lane?"

    assert list(lesson.resources.values_list("title", flat=True)) == ["Reference note"]

    module_assessment = modules["clone-one"].assessments.get(assessment_type=Assessment.Type.MODULE)
    assert module_assessment.items.get().question_version.prompt == "Module question?"
    assert draft.assessments.get(assessment_type=Assessment.Type.FINAL_THEORY).items.get().question_version.prompt == "Final question?"

    assert modules["clone-one"].cover_image.read() == PNG_BYTES
    assert client.get(reverse("course-builder-detail", args=[draft.pk])).status_code == 200


@pytest.mark.django_db
def test_draft_cover_is_a_separate_file(client, live_course):
    draft = _create_draft(client, live_course)
    source = live_course["first"].cover_image
    copy = draft.modules.get(code="clone-one").cover_image

    assert copy.name != source.name
    assert copy.read() == source.read()
    copy.delete(save=False)
    assert source.storage.exists(source.name)


@pytest.mark.django_db
def test_new_draft_carries_an_independent_copy_of_a_guided_practical(client, live_course):
    draft = _create_draft(client, live_course)

    source = live_course["first"].guided_practicals.get()
    copy = draft.modules.get(code="clone-one").guided_practicals.get()
    assert copy.pk != source.pk
    assert (copy.scenario_id, copy.version, copy.status) == (source.scenario_id, 2, ScenarioVersion.Status.DRAFT)
    assert copy.published_at is None
    assert [state.key for state in copy.states.all()] == ["start", "finish"]
    assert copy.states.get(key="start").is_initial

    action = copy.action_definitions.get(code="go")
    # Both ends of the action point at the copied states.
    assert action.from_state.scenario_version_id == copy.pk
    assert action.to_state.scenario_version_id == copy.pk
    assert copy.documents.get().title == "UCR"

    rubric_copy = copy.rubric_version
    assert rubric_copy.pk != source.rubric_version.pk
    assert rubric_copy.version == 2
    assert rubric_copy.status == RubricVersion.Status.DRAFT
    assert rubric_copy.criteria.get().code == "accuracy"


@pytest.mark.django_db
def test_draft_edits_cannot_reach_the_published_course(client, live_course):
    source_version = live_course["version"]
    source_lesson = live_course["lesson"]
    source_check = source_lesson.knowledge_checks.get()
    source_practical = source_lesson.module.guided_practicals.get()
    before = {
        "prompt": source_check.question_version.prompt,
        "option": source_check.question_version.options.first().label,
        "body": source_lesson.blocks.get(order=2).body,
        "briefing": source_practical.briefing,
        "question_code": source_check.question_version.question.code,
    }

    draft = _create_draft(client, live_course)
    draft_lesson = draft.modules.get(code="clone-one").lessons.get(slug="clone-lesson")
    draft_lesson.blocks.filter(order=2).update(body="Rewritten for the new edition.")
    draft_check = draft_lesson.knowledge_checks.get()
    draft_check.question_version.prompt = "Which lane now?"
    draft_check.question_version.save()
    draft_check.question_version.options.first().delete()
    draft_practical = draft.modules.get(code="clone-one").guided_practicals.get()
    draft_practical.briefing = "A different briefing."
    draft_practical.save()

    source_check.question_version.refresh_from_db()
    source_practical.refresh_from_db()
    assert source_check.question_version.prompt == before["prompt"]
    assert source_check.question_version.options.first().label == before["option"]
    assert source_lesson.blocks.get(order=2).body == before["body"]
    assert source_practical.briefing == before["briefing"]
    assert Question.objects.filter(code=before["question_code"]).exists()
    assert source_version.modules.get(code="clone-one").lessons.get(slug="clone-lesson").is_published


@pytest.mark.django_db
def test_new_draft_never_carries_learner_records(client, live_course):
    draft = _create_draft(client, live_course)

    assert not LessonProgress.objects.filter(lesson__module__programme_version=draft).exists()
    assert draft.enrolments.count() == 0
    assert Lesson.objects.filter(module__programme_version=draft).count() == 1


@pytest.mark.django_db
def test_draft_keeps_the_completion_settings_of_the_edition(client, live_course):
    CompletionPolicy.objects.create(
        programme_version=live_course["version"], requires_instructor_approval=True, certificate_template_version=3
    )

    draft = _create_draft(client, live_course)

    policy = draft.completion_policy
    assert (policy.requires_instructor_approval, policy.certificate_template_version, policy.is_active) == (True, 3, True)
    assert live_course["version"].completion_policy.pk != policy.pk


@pytest.mark.django_db
def test_a_draft_course_gets_no_second_copy(client, live_course):
    live_course["version"].status = ProgrammeVersion.Status.DRAFT
    live_course["version"].save(update_fields=("status",))
    client.force_login(live_course["instructor"])

    response = client.post(reverse("course-new-draft", args=[live_course["version"].pk]))

    assert response.status_code == 302
    assert ProgrammeVersion.objects.filter(programme=live_course["programme"]).count() == 1
