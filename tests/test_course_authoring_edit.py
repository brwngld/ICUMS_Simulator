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
    basic_response = client.post(
        reverse("course-edit", args=[draft_course["version"].pk]),
        {"tab": "basic", "name": "Renamed Programme", "description": "Updated course description."},
    )
    assert basic_response.status_code == 302
    overview_response = client.post(
        reverse("course-edit", args=[draft_course["version"].pk]),
        {
            "tab": "overview",
            "name": "Renamed Programme",
            "overview_summary": "Understand the complete standards process.",
            "target_audience": "Customs officers and trade practitioners.",
            "learning_outcomes": "Interpret standards\nApply conformity rules",
            "learning_approach": "Read guided lessons\nComplete practical examples",
        },
    )
    assert overview_response.status_code == 302
    draft_course["version"].refresh_from_db()
    programme = draft_course["version"].programme
    programme.refresh_from_db()
    assert programme.name == "Renamed Programme"
    assert programme.overview_summary == "Understand the complete standards process."
    assert programme.target_audience == "Customs officers and trade practitioners."
    assert programme.get_outcomes_list() == ["Interpret standards", "Apply conformity rules"]
    assert programme.get_learning_approach_list() == ["Read guided lessons", "Complete practical examples"]


@pytest.mark.django_db
def test_course_editor_exposes_all_four_overview_cards(client, instructor, draft_course):
    client.force_login(instructor)

    response = client.get(reverse("course-edit", args=[draft_course["version"].pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'data-authoring-panel="overview"' in content
    assert 'data-structured-field="lines"' in content
    assert "What you’ll learn" in content
    assert "Who is this for?" in content
    assert "Skills you’ll build" in content
    assert "How you’ll learn" in content
    assert "Overview readiness" in content


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
        {
            "title": "Module B renamed",
            "description": "New description",
            "difficulty": "beginner-intermediate",
            "prerequisite": str(draft_course["module_a"].pk),
        },
    )
    assert response.status_code == 302
    module_b.refresh_from_db()
    assert module_b.title == "Module B renamed"
    assert module_b.description == "New description"
    assert module_b.difficulty == "beginner-intermediate"
    assert module_b.prerequisite_id == draft_course["module_a"].pk


@pytest.mark.django_db
def test_module_editor_offers_the_five_course_difficulty_levels(client, instructor, draft_course):
    client.force_login(instructor)
    response = client.get(reverse("module-edit", args=[draft_course["module_a"].pk]))
    page = response.content.decode()
    for value, label in Programme.Difficulty.ladder_choices():
        assert f'value="{value}"' in page
        assert label in page
    assert 'value="advanced"' in page
    # "Beginner to Advanced" describes a whole main course, so it is not a ladder rung.
    assert 'value="beginner-advanced"' not in page
    assert page.count('name="difficulty"') == 1


@pytest.mark.django_db
def test_module_difficulty_is_optional_and_blankable(client, instructor, draft_course):
    module = draft_course["module_a"]
    module.difficulty = Programme.Difficulty.ADVANCED
    module.save(update_fields=("difficulty",))
    client.force_login(instructor)
    response = client.post(reverse("module-edit", args=[module.pk]), {"title": module.title, "description": "", "difficulty": ""})
    assert response.status_code == 302
    module.refresh_from_db()
    assert module.difficulty == ""


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
def test_lesson_editor_renders_structured_details_workspace(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    lesson.objectives = "Identify the document.\nExplain its purpose."
    lesson.key_terms = "Manifest :: A list of cargo.\nDeclaration :: A customs submission."
    lesson.save(update_fields=("objectives", "key_terms"))
    client.force_login(instructor)

    response = client.get(reverse("lesson-edit", args=[lesson.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'class="authoring-tabs authoring-assessment-tabs authoring-lesson-tabs"' in content
    assert 'data-structured-field="objectives"' in content
    assert 'data-structured-field="key-terms"' in content
    assert "Lesson readiness" in content
    assert "2 objectives" in content
    assert "2 terms" in content


@pytest.mark.django_db
def test_lesson_sections_support_multiple_blocks_per_type(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    client.force_login(instructor)

    for kind in ("text", "text", "example", "example", "notice", "notice"):
        response = client.post(reverse("lesson-section-add", args=[lesson.pk]), {"kind": kind})
        assert response.status_code == 302

    assert lesson.blocks.filter(kind="text").count() == 3
    assert lesson.blocks.filter(kind="example").count() == 2
    assert lesson.blocks.filter(kind="notice").count() == 2

    page = client.get(reverse("lesson-edit", args=[lesson.pk]))
    assert page.status_code == 200
    content = page.content.decode()
    assert content.count("+ Key concept") == 1
    assert "7 sections" in content
    # each kind is numbered separately, in the order the learner meets it
    assert "Key concept 3" in content
    assert "Worked example 2" in content
    assert "Important note 2" in content


@pytest.mark.django_db
def test_lesson_section_move_swaps_with_the_adjacent_section_across_kinds(client, instructor, draft_course):
    """Moving a section swaps it with the section right beside it in the learner's
    order — never a leap past other kinds — so two key concepts can be gathered."""
    lesson = draft_course["lesson"]
    original = draft_course["block"]  # text, order 1
    example = ContentBlock.objects.create(lesson=lesson, kind="example", heading="Example", body="Example body.", order=2)
    second_concept = ContentBlock.objects.create(lesson=lesson, kind="text", heading="Second concept", body="Second concept body.", order=3)
    client.force_login(instructor)

    response = client.post(
        reverse("lesson-section-move", args=[lesson.pk, second_concept.pk]),
        {"direction": "up"},
    )
    assert response.status_code == 302
    original.refresh_from_db()
    example.refresh_from_db()
    second_concept.refresh_from_db()
    assert (original.order, second_concept.order, example.order) == (1, 2, 3)

    response = client.post(
        reverse("lesson-section-move", args=[lesson.pk, second_concept.pk]),
        {"direction": "down"},
    )
    assert response.status_code == 302
    example.refresh_from_db()
    second_concept.refresh_from_db()
    assert (original.order, example.order, second_concept.order) == (1, 2, 3)


@pytest.mark.django_db
def test_lesson_section_move_and_delete_preserve_practice_question(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    original = draft_course["block"]
    check = LessonCheck.objects.get(lesson=lesson)
    second = ContentBlock.objects.create(
        lesson=lesson, kind="text", heading="Second concept", body="Second concept body.", order=2,
    )
    client.force_login(instructor)

    response = client.post(
        reverse("lesson-section-move", args=[lesson.pk, second.pk]),
        {"direction": "up"},
    )
    assert response.status_code == 302
    original.refresh_from_db()
    second.refresh_from_db()
    assert second.order < original.order

    response = client.post(reverse("lesson-section-delete", args=[lesson.pk, original.pk]))
    assert response.status_code == 302
    assert not ContentBlock.objects.filter(pk=original.pk).exists()
    check.refresh_from_db()
    assert check.after_block_id == second.pk


@pytest.mark.django_db
def test_lesson_preview_pages_every_block_in_a_section(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    ContentBlock.objects.create(
        lesson=lesson, kind="text", heading="Second concept", body="Additional concept body.", order=2,
    )
    client.force_login(instructor)
    preview = reverse("lesson-preview", args=[lesson.pk]) + "?section=concepts"

    first = client.get(preview)
    second = client.get(preview + "&part=2")

    assert first.status_code == second.status_code == 200
    first, second = first.content.decode(), second.content.decode()
    assert "Original body." in first and "Additional concept body." not in first
    assert "Additional concept body." in second and "Part 2 of 2" in second
    assert "Original body." not in second


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
    assert draft_course["block"].body == "<p>Edited body copy.</p>"
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
def test_instructor_can_add_edit_and_remove_additional_practice_questions(client, instructor, draft_course):
    lesson = draft_course["lesson"]
    client.force_login(instructor)
    add_url = reverse("lesson-practice-add", args=[lesson.pk])
    response = client.post(
        add_url,
        {
            "prompt": "Additional practice question?",
            "points": "1",
            "explanation": "Additional explanation.",
            "option_1": "Yes",
            "option_2": "No",
            "correct_position": "1",
        },
    )
    assert response.status_code == 302
    checks = list(lesson.knowledge_checks.order_by("order", "id"))
    assert len(checks) == 2
    assert [check.order for check in checks] == [1, 2]
    added = checks[1]
    assert added.question_version.prompt == "Additional practice question?"

    options = list(added.question_version.options.order_by("order"))
    response = client.post(
        reverse("lesson-practice-edit", args=[lesson.pk, added.pk]),
        {
            "prompt": "Updated additional question?",
            "explanation": "Updated explanation.",
            "option_1": "Updated yes",
            "option_2": "Updated no",
            "correct_option": str(options[1].pk),
        },
    )
    assert response.status_code == 302
    added.question_version.refresh_from_db()
    assert added.question_version.prompt == "Updated additional question?"
    assert added.question_version.options.get(pk=options[1].pk).is_correct is True

    response = client.post(reverse("lesson-practice-delete", args=[lesson.pk, added.pk]))
    assert response.status_code == 302
    assert list(lesson.knowledge_checks.values_list("order", flat=True)) == [1]


@pytest.mark.django_db
def test_lesson_create_uses_the_tabbed_editor_flow(client, instructor, draft_course):
    """The slim create only makes the draft and opens the tabbed editor; sections,
    practice checks and the optional module-assessment link are added there."""
    module = draft_course["module_a"]
    client.force_login(instructor)

    response = client.post(
        reverse("lesson-create", args=[module.pk]),
        {"title": "New Lesson", "summary": "New summary.", "objectives": "Do a thing.", "key_terms": "Term :: meaning."},
    )
    assert response.status_code == 302
    lesson = module.lessons.get(title="New Lesson")
    assert lesson.summary == "New summary."
    assert lesson.blocks.count() == 0
    assert lesson.knowledge_checks.count() == 0
    assert response.url == f"{reverse('lesson-edit', args=[lesson.pk])}?tab=details"

    client.post(reverse("lesson-section-add", args=[lesson.pk]), {"kind": "text"})
    response = client.post(
        reverse("lesson-practice-add", args=[lesson.pk]),
        {
            "prompt": "Practice check?",
            "points": "1",
            "explanation": "Because.",
            "option_1": "Right",
            "option_2": "Wrong",
            "correct_position": "1",
            "add_to_assessment": "on",
        },
    )
    assert response.status_code == 302
    check = lesson.knowledge_checks.get()
    assert check.question_version.prompt == "Practice check?"
    assessment = module.assessments.get(assessment_type=Assessment.Type.MODULE)
    assert assessment.items.filter(question_version=check.question_version).exists()

    # without the checkbox the check stays lesson-only
    response = client.post(
        reverse("lesson-practice-add", args=[lesson.pk]),
        {
            "prompt": "Second check?",
            "points": "1",
            "explanation": "",
            "option_1": "Right",
            "option_2": "Wrong",
            "correct_position": "1",
        },
    )
    assert response.status_code == 302
    assert assessment.items.count() == 1
    assert lesson.knowledge_checks.count() == 2


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
def test_practical_builder_has_its_own_instructor_workspace(client, instructor, draft_course):
    scenario = Scenario.objects.create(code="workspace-practical", title="Create a UCR", area="import")
    practical = ScenarioVersion.objects.create(
        scenario=scenario,
        module=draft_course["module_a"],
        version=1,
        assistance_mode="beginner",
        briefing="Create a fictional UCR.",
        learning_objective="Complete the UCR workflow.",
    )
    ScenarioState.objects.create(
        scenario_version=practical,
        key="step-1",
        label="Save the UCR draft",
        order=1,
        is_initial=True,
    )
    client.force_login(instructor)

    response = client.get(reverse("practical-builder-index"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "Practical/Theory Builder" in html
    assert "Create a UCR" in html
    assert reverse("practical-edit", args=[practical.pk]) in html
    assert reverse("practical-builder", args=[draft_course["module_a"].pk]) in html


@pytest.mark.django_db
def test_edit_views_are_instructor_only(client, student_client_factory=None):
    from django.test import Client

    student = User.objects.create_user(username="edit-student", email="edit-student@example.test", password="test-password")
    client = Client()
    client.force_login(student)
    for url in [reverse("course-edit", args=["00000000-0000-0000-0000-000000000000"]), reverse("module-edit", args=["00000000-0000-0000-0000-000000000000"])]:
        assert client.get(url).status_code == 302  # redirected with a message, never an error page
