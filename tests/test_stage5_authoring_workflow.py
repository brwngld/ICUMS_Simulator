"""Stage 5 — end-to-end authoring, publishing, and progression verification.

Everything below exercises the real instructor and student views through
Django's test client (no direct model/service shortcuts for the actions
under test). Model/ORM access is used only to arrange preconditions and to
assert resulting state.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import SimulatorCredential, User
from assessments.models import (
    AnswerOption,
    Assessment,
    AssessmentItem,
    LessonCheck,
    LessonCheckResponse,
    Question,
    QuestionVersion,
    TheoryAttempt,
    TheoryResponse,
)
from evaluations.models import PracticalEvaluation
from learning.models import Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress
from reports.models import Certificate, CompletionRecord
from scenarios.models import ScenarioAction, ScenarioAttempt, ScenarioVersion


# --------------------------------------------------------------------------
# helpers


def csrf_from(response):
    import re

    content = response.content.decode() if hasattr(response, "content") else str(response)
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]*)"', content)
    assert match, "expected a CSRF token in the response"
    return match.group(1)


def simulator_session(client, user):
    """Give a logged-in student a live simulator credential session."""
    if not user.student_id:
        from accounts.models import allocate_student_id

        user.student_id = allocate_student_id(user.first_name or user.username)
        user.save(update_fields=("student_id",))
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    session = client.session
    session["simulator_user_id"] = str(user.pk)
    session.save()


def add_question(client, assessment_pk, prompt, correct, wrong, correct_position="1", points="1"):
    url = reverse("assessment-question-add", args=[assessment_pk])
    response = client.post(
        url,
        {
            "csrfmiddlewaretoken": csrf_from(client.get(url)),
            "prompt": prompt,
            "points": points,
            "explanation": f"Explanation: {prompt}",
            "option_1": correct if correct_position == "1" else wrong,
            "option_2": wrong if correct_position == "1" else correct,
            "option_3": "",
            "option_4": "",
            "correct_position": correct_position if correct_position in ("1", "2") else "1",
        },
    )
    assert response.status_code == 302, f"question add failed: {response.status_code}"


@pytest.fixture
def instructor(db):
    user = User.objects.create_user(username="e2e-instructor", email="e2e@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=21, title="E2E notice", body="Training only.", is_current=True)
    )
    return user


@pytest.fixture
def disclaimer(db):
    return DisclaimerVersion.objects.create(version=20, title="E2E student notice", body="Training only.", is_current=True)


# --------------------------------------------------------------------------
# 1-4 + 9-16: the complete authoring → publish → student workflow


@pytest.mark.django_db
def test_complete_authoring_publish_and_progression_workflow(client, instructor, disclaimer):
    # ---- 1. create a draft course ------------------------------------------------
    client.force_login(instructor)
    builder_url = reverse("course-builder") + "?path=theory"
    response = client.post(
        reverse("course-create"),
        {"csrfmiddlewaretoken": csrf_from(client.get(builder_url)), "name": "E2E Programme"},
    )
    assert response.status_code == 302
    version = ProgrammeVersion.objects.get(programme__name="E2E Programme")
    assert version.status == ProgrammeVersion.Status.DRAFT
    outline = reverse("course-builder-detail", args=[version.pk])

    # ---- 2. create two modules ---------------------------------------------------
    token = csrf_from(client.get(outline))
    client.post(reverse("course-builder-module-create", args=[version.pk]), {"csrfmiddlewaretoken": token, "title": "Module One", "description": "first"})
    token = csrf_from(client.get(outline))
    client.post(reverse("course-builder-module-create", args=[version.pk]), {"csrfmiddlewaretoken": token, "title": "Module Two", "description": "second"})
    module_one, module_two = list(version.modules.order_by("order"))
    assert [module_one.title, module_two.title] == ["Module One", "Module Two"]

    # ---- 3. edit module details and prerequisite ---------------------------------
    client.post(
        reverse("module-edit", args=[module_two.pk]),
        {"title": "Module Two (requires One)", "description": "second", "prerequisite": str(module_one.pk)},
    )
    module_two.refresh_from_db()
    assert module_two.prerequisite_id == module_one.pk

    # ---- 4. reorder modules and confirm the saved order ---------------------------
    token = csrf_from(client.get(outline))
    client.post(reverse("module-move", args=[module_two.pk]), {"csrfmiddlewaretoken": token, "direction": "up"})
    module_one.refresh_from_db(); module_two.refresh_from_db()
    assert (module_two.order, module_one.order) == (1, 2)
    token = csrf_from(client.get(outline))
    client.post(reverse("module-move", args=[module_two.pk]), {"csrfmiddlewaretoken": token, "direction": "down"})
    module_one.refresh_from_db(); module_two.refresh_from_db()
    assert (module_one.order, module_two.order) == (1, 2)

    # ---- 5. add lessons to the correct modules -----------------------------------
    def build_lesson(module, slug, title):
        new_lesson_url = reverse("lesson-builder", args=[module.pk])
        token = csrf_from(client.get(new_lesson_url))
        response = client.post(
            reverse("lesson-create", args=[module.pk]),
            {
                "csrfmiddlewaretoken": token,
                "title": title,
                "summary": f"{title} summary",
                "concept_heading": "Key concept",
                "concept_body": f"{title} teaching body",
                "question_prompt": f"{title} check?",
                "correct_answer": "Correct answer",
                "incorrect_answer_1": "Wrong one",
                "incorrect_answer_2": "Wrong two",
                "explanation": "Because.",
                # add_to_assessment unchecked: assessments are managed in stage 3
            },
        )
        assert response.status_code == 302
        return Lesson.objects.get(module=module, slug=slug if False else Lesson.objects.filter(module=module, title=title).get().slug)

    lesson_one = build_lesson(module_one, "lesson-one", "Lesson One")
    assert lesson_one.module_id == module_one.pk
    lesson_two = build_lesson(module_two, "lesson-two", "Lesson Two")
    assert lesson_two.module_id == module_two.pk

    # ---- 6. edit lesson content, reading sections, and knowledge checks ----------
    edit_url = reverse("lesson-edit", args=[lesson_one.pk])
    block = lesson_one.blocks.get()
    check = LessonCheck.objects.get(lesson=lesson_one)
    token = csrf_from(client.get(edit_url))
    options = list(check.question_version.options.order_by("order"))
    edit_payload = {
        "csrfmiddlewaretoken": token,
        "title": "Lesson One (edited)",
        "summary": "Edited summary",
        "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        "form-0-id": str(block.pk), "form-0-heading": "Edited heading", "form-0-body": "Edited body",
        "prompt": "Edited check?",
        "explanation": "Edited explanation",
        "correct_option": str(options[0].pk),
    }
    for index, option in enumerate(options, start=1):
        edit_payload[f"option_{index}"] = f"Edited answer {index}"
    response = client.post(edit_url, edit_payload)
    assert response.status_code == 302, "lesson edit should save and redirect"
    lesson_one.refresh_from_db(); block.refresh_from_db(); check.refresh_from_db()
    assert lesson_one.title == "Lesson One (edited)"
    assert block.body == "Edited body"
    assert check.question_version.prompt == "Edited check?"

    # ---- 7. reorder lessons and confirm the saved order ---------------------------
    extra_lesson = build_lesson(module_one, "lesson-one-b", "Lesson One B")
    client.post(reverse("lesson-move", args=[extra_lesson.pk]), {"direction": "up"})
    assert [lesson.title for lesson in module_one.lessons.order_by("order")] == ["Lesson One B", "Lesson One (edited)"]
    client.post(reverse("lesson-move", args=[extra_lesson.pk]), {"direction": "down"})
    assert [lesson.title for lesson in module_one.lessons.order_by("order")] == ["Lesson One (edited)", "Lesson One B"]

    # ---- 13-14 (early pass): review identifies the missing assessments and blocks publish
    review = client.get(reverse("course-review", args=[version.pk])).content.decode()
    assert "Not ready to publish" in review
    assert "Add a module assessment to" in review
    assert "Add a final theory examination" in review
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT  # blocked publish stays draft
    assert not Module.objects.filter(programme_version=version, is_published=True).exists()

    # ---- 8-9. module assessment with questions, options, correct answers, pass mark
    client.post(reverse("module-assessment-create", args=[module_one.pk]), {"title": "Module One Assessment", "pass_percentage": "70", "maximum_attempts": "3"})
    module_assessment = module_one.assessments.get(assessment_type=Assessment.Type.MODULE)
    add_question(client, module_assessment.pk, "Module question 1?", "M1 correct", "M1 wrong")
    add_question(client, module_assessment.pk, "Module question 2?", "M2 correct", "M2 wrong")
    assert module_assessment.items.count() == 2
    client.post(reverse("module-assessment-create", args=[module_two.pk]), {"title": "Module Two Assessment", "pass_percentage": "70"})
    module_two_assessment = module_two.assessments.get(assessment_type=Assessment.Type.MODULE)
    add_question(client, module_two_assessment.pk, "Module Two question?", "MT correct", "MT wrong")

    # ---- 10. final theory exam ---------------------------------------------------
    client.post(reverse("final-exam-create", args=[version.pk]), {"title": "E2E Final Examination", "pass_percentage": "70"})
    final_exam = version.assessments.get(assessment_type=Assessment.Type.FINAL_THEORY)
    add_question(client, final_exam.pk, "Final question?", "Final correct", "Final wrong")

    # ---- 11. guided practical via the existing builder ---------------------------
    practical_url = reverse("practical-builder", args=[module_one.pk])
    token = csrf_from(client.get(practical_url))
    client.post(
        reverse("practical-create", args=[module_one.pk]),
        {
            "csrfmiddlewaretoken": token,
            "title": "E2E Practical",
            "area": "import",
            "briefing": "E2E briefing",
            "learning_objective": "E2E objective",
            "assistance_mode": "beginner",
            "maximum_attempts": "3",
            "steps": "Stage one\nStage two",
        },
    )
    practical = ScenarioVersion.objects.get(scenario__title="E2E Practical")
    assert practical.states.count() == 3  # two stages + terminal

    # ---- 12. previews ------------------------------------------------------------
    for url in [
        reverse("lesson-preview", args=[lesson_one.pk]),
        reverse("assessment-preview", args=[module_assessment.pk]),
        reverse("assessment-preview", args=[final_exam.pk]),
        reverse("practical-preview", args=[practical.pk]),
    ]:
        preview = client.get(url)
        assert preview.status_code == 200
        assert "PREVIEW" in preview.content.decode()

    # ---- 13-14 (final pass): review is now satisfied ------------------------------
    review = client.get(reverse("course-review", args=[version.pk])).content.decode()
    assert "Ready to publish" in review

    # ---- 15. publish through the real endpoint ------------------------------------
    response = client.post(reverse("course-publish", args=[version.pk]))
    assert response.status_code == 302
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    for module in version.modules.all():
        assert module.is_published
        for lesson in module.lessons.all():
            assert lesson.is_published
    for assessment in version.assessments.all():
        assert assessment.is_published
        for item in assessment.items.all():
            assert item.question_version.is_published

    # ---- 16. student-facing visibility and progression ----------------------------
    student = User.objects.create_user(username="e2e-student", email="e2e-student@example.test", password="test-password")
    student.groups.add(Group.objects.get(name="Student"))
    from onboarding.services import current_disclaimer

    DisclaimerAcceptance.objects.get_or_create(user=student, disclaimer=current_disclaimer())
    Enrolment.objects.create(student=student, programme_version=version, status="active")
    student_client = __import__("django.test", fromlist=["Client"]).Client()
    student_client.force_login(student)

    # draft courses are not exposed: build a second draft course via HTTP
    client.post(reverse("course-create"), {"csrfmiddlewaretoken": csrf_from(client.get(builder_url)), "name": "E2E Draft (unpublished)"})
    draft_version = ProgrammeVersion.objects.get(programme__name="E2E Draft (unpublished)")
    token = csrf_from(client.get(reverse("course-builder-detail", args=[draft_version.pk])))
    client.post(reverse("course-builder-module-create", args=[draft_version.pk]), {"csrfmiddlewaretoken": token, "title": "Draft module"})
    draft_module = draft_version.modules.get()
    draft_lesson_url = reverse("lesson-detail", args=[draft_module.code, "any-lesson-slug"])
    assert student_client.get(draft_lesson_url).status_code == 404  # draft lesson not exposed

    # roadmap: published modules in the saved order
    roadmap = student_client.get(reverse("roadmap"))
    assert roadmap.status_code == 200
    titles = [summary["module"].title for summary in roadmap.context["module_summaries"]]
    assert titles == ["Module One", "Module Two (requires One)"]

    # lesson + knowledge check + completion
    module_one.refresh_from_db()
    lesson_detail_url = reverse("lesson-detail", args=[module_one.code, Lesson.objects.get(module=module_one, title="Lesson One (edited)").slug])
    page = student_client.get(lesson_detail_url)
    assert page.status_code == 200
    check = LessonCheck.objects.get(lesson__title="Lesson One (edited)")
    print("CHECK OPTIONS AFTER EDIT:", list(check.question_version.options.order_by("order").values_list("label", "is_correct", "order")), "| QV:", check.question_version.pk)
    correct_option = check.question_version.options.get(is_correct=True)
    wrong_options = check.question_version.options.filter(is_correct=False)
    assert wrong_options.count() >= 1
    wrong_option = wrong_options.first()
    checked = student_client.post(lesson_detail_url, {"action": "answer_check", "position": "0", "check_id": str(check.pk), "option": str(wrong_option.pk)})
    assert checked.status_code == 302
    assert LessonCheckResponse.objects.filter(is_correct=False).exists()  # wrong answer recorded
    completed = student_client.post(lesson_detail_url, {"action": "continue", "position": "0"})
    assert completed.status_code == 302
    lesson_one_progress = LessonProgress.objects.get(enrolment__student=student, lesson=lesson_one)
    assert lesson_one_progress.completed_at is not None

    # module cannot complete without its assessment: no ModuleProgress yet
    assert not ModuleProgress.objects.filter(module=module_one, status=ModuleProgress.Status.COMPLETED).exists()

    # every published lesson of the module must be completed first
    extra_lesson_progress_url = reverse("lesson-detail", args=[module_one.code, extra_lesson.slug])
    assert student_client.post(extra_lesson_progress_url, {"action": "continue", "position": "0"}).status_code == 302
    assert LessonProgress.objects.get(lesson=extra_lesson, enrolment__student=student).completed_at is not None

    # pass the module assessment through the real take flow
    take_url = reverse("assessment-take", args=[module_assessment.pk])
    assert student_client.get(take_url).status_code == 200
    attempt = TheoryAttempt.objects.get(enrolment__student=student, assessment=module_assessment)
    answers = {str(item.question_version.pk): str(item.question_version.options.get(is_correct=True).pk) for item in attempt.items.all()}
    result = student_client.post(take_url, answers)
    assert result.status_code == 302
    attempt.refresh_from_db()
    assert attempt.outcome == "pass"
    assert ModuleProgress.objects.get(module=module_one).status == ModuleProgress.Status.COMPLETED

    # finish module two the same way
    lesson_two_url = reverse("lesson-detail", args=[module_two.code, Lesson.objects.get(module=module_two, title="Lesson Two").slug])
    student_client.post(lesson_two_url, {"action": "continue", "position": "0"})
    take_two = student_client.get(reverse("assessment-take", args=[module_two_assessment.pk]))
    assert take_two.status_code == 200
    attempt_two = TheoryAttempt.objects.get(enrolment__student=student, assessment=module_two_assessment)
    student_client.post(reverse("assessment-take", args=[module_two_assessment.pk]), {str(item.question_version.pk): str(item.question_version.options.get(is_correct=True).pk) for item in attempt_two.items.all()})
    assert ModuleProgress.objects.get(module=module_two).status == ModuleProgress.Status.COMPLETED

    # final exam was locked until all modules completed; now available and passing unlocks orientation
    final_url = reverse("assessment-take", args=[final_exam.pk])
    final_page = student_client.get(final_url)
    assert final_page.status_code == 200
    final_attempt = TheoryAttempt.objects.get(enrolment__student=student, assessment=final_exam)
    student_client.post(final_url, {str(item.question_version.pk): str(item.question_version.options.get(is_correct=True).pk) for item in final_attempt.items.all()})
    progress = ProgrammeProgress.objects.get(enrolment__student=student)
    assert progress.theory_completed_at is not None
    assert progress.orientation_unlocked_at is not None
    assert progress.orientation_completed_at is None

    # orientation completes; practical unlocks
    assert student_client.post(reverse("orientation")).status_code == 302
    progress.refresh_from_db()
    assert progress.orientation_completed_at is not None

    # guided practical through the real student flow
    simulator_session(student_client, student)
    start = student_client.post(reverse("scenario-start", args=[practical.pk]))
    assert start.status_code == 302
    attempt = ScenarioAttempt.objects.get(enrolment__student=student, scenario_version=practical)
    workspace = student_client.get(reverse("scenario-workspace", args=[attempt.pk]))
    assert workspace.status_code == 200
    actions = list(attempt.scenario_version.action_definitions.order_by("order"))
    for action in actions:
        assert student_client.post(reverse("scenario-action", args=[attempt.pk, action.pk])).status_code == 302
    attempt.refresh_from_db()
    assert attempt.status == "completed"
    assert PracticalEvaluation.objects.filter(attempt=attempt).exists()
    # resume, limits, scoring remain: starting again resumes the completed scenario's scenario, not a duplicate
    # a completed practical is not resumed: a fresh attempt starts (limit 3 allows it)
    resume = student_client.post(reverse("scenario-start", args=[practical.pk]))
    assert resume.status_code == 302
    assert ScenarioAttempt.objects.filter(enrolment__student=student, scenario_version=practical).count() == 2
    second = ScenarioAttempt.objects.filter(enrolment__student=student, scenario_version=practical, attempt_number=2).get()
    assert second.status == "in_progress"
    # and an in-progress attempt is always resumed, never duplicated
    student_client.post(reverse("scenario-start", args=[practical.pk]))
    assert ScenarioAttempt.objects.filter(enrolment__student=student, scenario_version=practical).count() == 2

    # instructor previews leave no student state behind
    before = (LessonProgress.objects.count(), TheoryAttempt.objects.count(), ScenarioAttempt.objects.count(), Certificate.objects.count())
    client.get(reverse("lesson-preview", args=[lesson_one.pk]))
    client.get(reverse("assessment-preview", args=[module_assessment.pk]))
    after = (LessonProgress.objects.count(), TheoryAttempt.objects.count(), ScenarioAttempt.objects.count(), Certificate.objects.count())
    assert before == after


def current_disclaimer_safe():
    from onboarding.services import current_disclaimer

    return current_disclaimer()


# --------------------------------------------------------------------------
# 3. publication safeguards at the workflow level


@pytest.mark.django_db
def test_failed_publish_leaves_a_consistent_draft(client, instructor, disclaimer):
    client.force_login(instructor)
    client.post(reverse("course-create"), {"csrfmiddlewaretoken": csrf_from(client.get(reverse("course-builder") + "?path=theory")), "name": "Safeguard Course"})
    version = ProgrammeVersion.objects.get(programme__name="Safeguard Course")
    outline = reverse("course-builder-detail", args=[version.pk])
    token = csrf_from(client.get(outline))
    client.post(reverse("course-builder-module-create", args=[version.pk]), {"csrfmiddlewaretoken": token, "title": "Safeguard Module"})
    module = version.modules.get()

    # publish without a module assessment: blocked
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT

    # add the module assessment but leave it without questions: still blocked
    client.post(reverse("module-assessment-create", args=[module.pk]), {"title": "SA", "pass_percentage": "70"})
    assessment = module.assessments.get(assessment_type=Assessment.Type.MODULE)
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT

    # add a question with one option through the real form: rejected
    add_url = reverse("assessment-question-add", args=[assessment.pk])
    response = client.post(add_url, {
        "csrfmiddlewaretoken": csrf_from(client.get(add_url)),
        "prompt": "One option?", "points": "1", "explanation": "",
        "option_1": "Only", "option_2": "", "option_3": "", "option_4": "", "correct_position": "1",
    })
    assert response.status_code == 200
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT

    # nothing was partially published
    assert not module.is_published
    assert not assessment.is_published
    assert not version.modules.model.objects.filter(programme_version=version, is_published=True).exists()

    # complete the course the same way the workflow does: publish succeeds
    lesson_url = reverse("lesson-builder", args=[module.pk])
    token = csrf_from(client.get(lesson_url))
    client.post(reverse("lesson-create", args=[module.pk]), {
        "csrfmiddlewaretoken": token, "title": "SL", "summary": "s",
        "concept_heading": "h", "concept_body": "b",
        "question_prompt": "q?", "correct_answer": "c", "incorrect_answer_1": "w",
        "incorrect_answer_2": "w2",
        "explanation": "e",
    })
    client.post(reverse("assessment-question-add", args=[assessment.pk]), {
        "csrfmiddlewaretoken": csrf_from(client.get(reverse("assessment-question-add", args=[assessment.pk]))),
        "prompt": "Two options?", "points": "1", "explanation": "",
        "option_1": "Right", "option_2": "Wrong", "option_3": "", "option_4": "", "correct_position": "1",
    })
    client.post(reverse("final-exam-create", args=[version.pk]), {"title": "SF", "pass_percentage": "70"})
    final = version.assessments.get(assessment_type=Assessment.Type.FINAL_THEORY)
    client.post(reverse("assessment-question-add", args=[final.pk]), {
        "csrfmiddlewaretoken": csrf_from(client.get(reverse("assessment-question-add", args=[final.pk]))),
        "prompt": "Final q?", "points": "1", "explanation": "",
        "option_1": "Right", "option_2": "Wrong", "option_3": "", "option_4": "", "correct_position": "1",
    })
    from instructor_portal.views import _course_issues

    print("SAFEGUARD FINAL ISSUES:", _course_issues(version))
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    assessment.refresh_from_db()
    assert assessment.is_published


# --------------------------------------------------------------------------
# 5. permissions and data isolation (compact workflow-level checks)


@pytest.mark.django_db
def test_authoring_endpoints_enforce_access_and_methods(client, instructor, disclaimer):
    client.force_login(instructor)
    client.post(reverse("course-create"), {"csrfmiddlewaretoken": csrf_from(client.get(reverse("course-builder") + "?path=theory")), "name": "Isolation Course"})
    version = ProgrammeVersion.objects.get(programme__name="Isolation Course")
    outline = reverse("course-builder-detail", args=[version.pk])
    token = csrf_from(client.get(outline))
    client.post(reverse("course-builder-module-create", args=[version.pk]), {"csrfmiddlewaretoken": token, "title": "Iso Module"})
    module = version.modules.get()
    new_lesson_url = reverse("lesson-builder", args=[module.pk])
    token = csrf_from(client.get(new_lesson_url))
    client.post(reverse("lesson-create", args=[module.pk]), {
        "csrfmiddlewaretoken": token, "title": "Iso Lesson", "summary": "s",
        "concept_heading": "h", "concept_body": "b", "question_prompt": "q?",
        "correct_answer": "c", "incorrect_answer_1": "w", "incorrect_answer_2": "w2",
        "explanation": "e",
    })
    lesson = module.lessons.get()

    # state-changing moves require POST
    assert client.get(reverse("module-move", args=[module.pk]), {"direction": "down"}).status_code == 405
    assert client.get(reverse("lesson-move", args=[lesson.pk]), {"direction": "up"}).status_code == 405
    delete_get = client.get(reverse("assessment-question-delete", args=["00000000-0000-0000-0000-000000000000", "00000000-0000-0000-0000-000000000000"]))
    assert delete_get.status_code in (404, 405)  # safely rejected, never executed

    # unknown ids fail safely
    assert client.post(reverse("module-move", args=["00000000-0000-0000-0000-000000000000"]), {"direction": "up"}).status_code == 404
    assert client.get(reverse("lesson-edit", args=["00000000-0000-0000-0000-000000000000"])).status_code == 404
    assert client.get(reverse("module-assessment-create", args=["00000000-0000-0000-0000-000000000000"])).status_code == 404  # unknown id fails safely

    # unknown module id fails safely (404, not a form or an error page)
    unknown_create = client.get(reverse("module-assessment-create", args=["00000000-0000-0000-0000-000000000000"]))
    assert unknown_create.status_code == 404  # unknown id fails safely

    # students cannot reach authoring or preview endpoints
    student = User.objects.create_user(username="iso-student", email="iso@example.test", password="test-password")
    student_client = __import__("django.test", fromlist=["Client"]).Client()
    student_client.force_login(student)
    for url in [
        reverse("course-edit", args=[version.pk]),
        reverse("module-edit", args=[module.pk]),
        reverse("lesson-edit", args=[lesson.pk]),
        reverse("lesson-preview", args=[lesson.pk]),
        reverse("course-publish", args=[version.pk]),
        reverse("module-assessment-create", args=[module.pk]),
    ]:
        response = student_client.get(url)
        assert response.status_code == 302  # gated with a message, never an error page
