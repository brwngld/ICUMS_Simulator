"""Course hierarchy, difficulty ladder and progression gates.

Covers the verification list in the programme-hierarchy brief: the
Programme → Course → Module → Lesson structure, level grouping, unlock rules,
backend enforcement on every learner route, migration safety for existing
progress, the instructor build-and-publish path and the compact sidebar.
"""
import importlib

import pytest
from django.apps import apps as global_apps
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from assessments.services import get_or_start_attempt, submit_attempt
from instructor_portal.views import _course_issues, _publish_blockers
from learning.models import ContentBlock, Course, Lesson, Module
from learning.services import (
    DIFFICULTY_LEVELS,
    course_is_available,
    course_is_completed,
    level_states,
    locked_course_message,
    module_is_locked,
    programme_theory_completed,
    unlocked_difficulties,
)
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress
from scenarios.services import practical_is_unlocked

_course_migration = importlib.import_module("learning.migrations.0007_course")


def _programme(db, code="ladder", status=ProgrammeVersion.Status.PUBLISHED):
    programme = Programme.objects.create(name=f"{code.title()} Programme", code=code)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=status)
    return programme, version


def _course(version, index, difficulty="", required=True, published=True):
    return Course.objects.create(
        programme_version=version,
        code=f"{version.programme.code}-course-{index}",
        title=f"Course {index}",
        description=f"Course {index} description.",
        difficulty=difficulty,
        order=index,
        is_required=required,
        is_published=published,
    )


def _module(version, index, course=None, published=True):
    module = Module.objects.create(
        programme_version=version, course=course, code=f"{version.programme.code}-m{index}",
        title=f"Module {index}", order=index, is_published=published,
    )
    lesson = Lesson.objects.create(module=module, slug=f"lesson-{index}", title=f"Lesson {index}", order=1, is_published=True)
    ContentBlock.objects.create(lesson=lesson, heading="Key concept", body="Fictional teaching content.", order=1)
    return module


def _question(code, prompt="Pick one."):
    question = Question.objects.create(code=code)
    question_version = QuestionVersion.objects.create(
        question=question, version=1, prompt=prompt, explanation="Because.", points=1, is_published=True
    )
    correct = AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
    return question_version, correct


def _assessment(version, module, index):
    question_version, correct = _question(f"{version.programme.code}-q{index}")
    assessment = Assessment.objects.create(
        programme_version=version, module=module, title=f"Module {index} Assessment",
        assessment_type=Assessment.Type.MODULE, pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=1)
    LessonCheck.objects.create(
        lesson=module.lessons.first(), after_block=module.lessons.first().blocks.first(),
        question_version=question_version, order=1,
    )
    return assessment, correct


def _final_exam(version, index=99):
    question_version, _correct = _question(f"{version.programme.code}-final-{index}")
    assessment = Assessment.objects.create(
        programme_version=version, title=f"Final {index}", assessment_type=Assessment.Type.FINAL_THEORY,
        pass_percentage=70, is_published=True,
    )
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=1)
    return assessment


def _student(db, version, username="ladder-learner"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    DisclaimerAcceptance.objects.create(
        user=user,
        disclaimer=DisclaimerVersion.objects.create(version=1, title="Notice", body="Training only.", is_current=True),
    )
    return user, enrolment


def _instructor(db, username="ladder-instructor"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.create(version=7, title="Instructor notice", body="Training only.", is_current=True),
    )
    return user


def _pass(enrolment, assessment, correct):
    attempt = get_or_start_attempt(enrolment, assessment)
    submit_attempt(attempt, {str(assessment.items.first().question_version_id): correct.pk})
    return attempt


def _read(enrolment, module):
    """Mark every lesson in the module complete, as finishing them does."""
    for lesson in module.lessons.all():
        LessonProgress.objects.update_or_create(
            enrolment=enrolment, lesson=lesson, defaults={"completed_at": timezone.now()}
        )


def _beginner_pair(db, code="ladder"):
    """One level, two courses, each with a module and a passing assessment."""
    programme, version = _programme(db, code)
    learner, enrolment = _student(db, version, f"{code}-learner")
    cards = []
    for index in (1, 2):
        course = _course(version, index, "beginner")
        module = _module(version, index, course)
        assessment, correct = _assessment(version, module, index)
        cards.append({"course": course, "module": module, "assessment": assessment, "correct": correct})
    return programme, version, learner, enrolment, cards


# ── §1 structure ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_programme_holds_several_courses_each_with_modules_and_lessons(db):
    _programme_, version = _programme(db, "multi")
    first = _course(version, 1, "beginner")
    second = _course(version, 2, "beginner")
    _module(version, 1, first)
    _module(version, 2, first)
    _module(version, 3, second)

    assert version.courses.count() == 2
    assert first.modules.count() == 2
    assert second.modules.count() == 1
    assert second.modules.first().lessons.first().module.course == second


@pytest.mark.django_db
def test_course_code_is_unique_within_a_version(db):
    _programme_, version = _programme(db, "unique")
    _course(version, 1, "beginner")
    with transaction.atomic(), pytest.raises(IntegrityError):
        Course.objects.create(programme_version=version, code="unique-course-1", title="Clash", difficulty="beginner")
    _programme_, other = _programme(db, "unique-two")
    assert _course(other, 1, "beginner").pk
    assert Course.objects.count() == 2


# ── §2/§3 level grouping and gating ─────────────────────────────────────────


@pytest.mark.django_db
def test_roadmap_groups_courses_by_level_and_keeps_levels_in_order(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "group")
    advanced = _course(version, 9, "advanced")
    _module(version, 9, advanced)

    states = level_states(version, enrolment)
    assert [item["difficulty"] for item in states] == DIFFICULTY_LEVELS
    assert {item.title for item in states[0]["courses"]} == {"Course 1", "Course 2"}
    assert [item["label"] for item in states[1:3]] == ["Beginner to Intermediate", "Intermediate"]
    assert {item.title for item in states[-1]["courses"]} == {"Course 9"}
    assert not {c.pk for c in states[0]["courses"]} & {c.pk for c in states[-1]["courses"]}


@pytest.mark.django_db
def test_beginner_level_is_available_before_any_progress(db):
    _programme_, version, _learner, enrolment, _cards = _beginner_pair(db, "first")
    states = level_states(version, enrolment)
    assert states[0]["state"] == "available"
    assert [item["state"] for item in states[1:]] == ["locked"] * 4
    assert unlocked_difficulties(version, enrolment) == {"beginner"}


@pytest.mark.django_db
def test_next_level_unlocks_only_after_every_required_beginner_course(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "gate")
    next_level = _course(version, 3, "beginner-intermediate")
    _module(version, 3, next_level)

    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    assert not course_is_completed(enrolment, cards[1]["course"])
    assert module_is_locked(enrolment, next_level.modules.first())

    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])
    assert course_is_completed(enrolment, cards[1]["course"])
    assert not module_is_locked(enrolment, next_level.modules.first())
    states = level_states(version, enrolment)
    assert states[0]["state"] == "completed"
    assert states[1]["state"] == "available"


@pytest.mark.django_db
def test_a_failed_assessment_does_not_complete_a_course(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "score")
    next_level = _course(version, 3, "beginner-intermediate")
    _module(version, 3, next_level)

    assessment = cards[0]["assessment"]
    question_version = assessment.items.first().question_version
    wrong = AnswerOption.objects.create(question_version=question_version, label="Also wrong", is_correct=False, order=3)
    attempt = _pass(enrolment, assessment, wrong)

    assert attempt.outcome == attempt.Outcome.FAIL
    assert not course_is_completed(enrolment, cards[0]["course"])
    assert module_is_locked(enrolment, next_level.modules.first())


@pytest.mark.django_db
def test_lesson_views_alone_do_not_complete_a_course(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "lessons")
    ModuleProgress.objects.create(enrolment=enrolment, module=cards[0]["module"], status=ModuleProgress.Status.IN_PROGRESS)
    LessonProgress.objects.create(enrolment=enrolment, lesson=cards[0]["module"].lessons.first())
    assert not course_is_completed(enrolment, cards[0]["course"])


@pytest.mark.django_db
def test_order_within_a_level_does_not_over_restrict(db):
    """Both courses at an open level are reachable in any order."""
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "freeorder")
    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])
    assert not module_is_locked(enrolment, cards[0]["module"])
    assert not module_is_locked(enrolment, cards[1]["module"])


@pytest.mark.django_db
def test_optional_course_does_not_gate_the_next_level(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "gatemix")
    optional = _course(version, 3, "beginner", required=False)
    _module(version, 4, optional)
    next_level = _course(version, 5, "beginner-intermediate")
    _module(version, 5, next_level)

    assert not module_is_locked(enrolment, optional.modules.first())
    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])
    assert not module_is_locked(enrolment, next_level.modules.first())
    assert not course_is_completed(enrolment, optional)


@pytest.mark.django_db
def test_an_empty_level_does_not_unlock_the_next_one(db):
    """§3: a level with no required courses must not silently open the ladder."""
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "empty")
    advanced = _course(version, 7, "advanced")
    _module(version, 7, advanced)
    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])

    states = level_states(version, enrolment)
    assert states[0]["state"] == "completed"
    assert states[1]["state"] == "available" and not states[1]["courses"]
    assert states[2]["state"] == "locked"
    assert states[-1]["state"] == "locked"
    assert module_is_locked(enrolment, advanced.modules.first())


@pytest.mark.django_db
def test_unpublished_courses_neither_gate_nor_appear(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "draftgate")
    draft = _course(version, 4, "beginner", published=False)
    loose = _module(version, 4, draft, published=False)

    assert all(draft not in list(item["courses"]) for item in level_states(version, enrolment))
    assert not course_is_available(enrolment, draft)
    assert module_is_locked(enrolment, loose)

    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])
    assert level_states(version, enrolment)[1]["state"] == "available"


@pytest.mark.django_db
def test_course_without_a_level_stays_open(db):
    """Blank difficulty keeps legacy content reachable and non-gating."""
    _programme_, version = _programme(db, "unlevelled")
    _learner, enrolment = _student(db, version, "unlevelled-learner")
    course = _course(version, 1, "")
    module = _module(version, 1, course)

    assert course_is_available(enrolment, course)
    assert not module_is_locked(enrolment, module)
    assert not any(item["courses"] for item in level_states(version, enrolment))


# ── §3 backend enforcement on every learner route ───────────────────────────


@pytest.mark.django_db
def test_locked_course_and_module_urls_are_refused(client, db):
    """§3: locks live in the views, so a direct URL gets nowhere."""
    _programme_, version, learner, _enrolment, _cards = _beginner_pair(db, "enforce")
    advanced = _course(version, 5, "advanced")
    advanced_module = _module(version, 5, advanced)
    advanced_lesson = advanced_module.lessons.first()
    advanced_assessment, _correct = _assessment(version, advanced_module, 5)

    client.force_login(learner)
    locked_targets = [
        reverse("course-overview", args=[advanced.code]),
        reverse("module-overview", args=[advanced_module.code]),
        reverse("lesson-detail", args=[advanced_module.code, advanced_lesson.slug]),
        reverse("assessment-take", args=[advanced_assessment.pk]),
    ]
    for path in locked_targets:
        response = client.get(path)
        assert response.status_code == 302, path
        assert response.url == reverse("dashboard"), path
        followed = client.get(response.url)
        assert locked_course_message(advanced) in " ".join(str(m) for m in followed.context["messages"])

    # Nothing from the locked course is ever rendered for that learner.
    response = client.get(reverse("roadmap"))
    assert reverse("module-overview", args=[advanced_module.code]) not in response.content.decode()


@pytest.mark.django_db
def test_unpublished_course_url_is_not_found(client, db):
    _programme_, version, learner, _enrolment, _cards = _beginner_pair(db, "hidden")
    draft = _course(version, 6, "intermediate", published=False)
    client.force_login(learner)
    assert client.get(reverse("course-overview", args=[draft.code])).status_code == 404


@pytest.mark.django_db
def test_open_course_url_renders_for_the_learner(client, db):
    _programme_, version, learner, _enrolment, cards = _beginner_pair(db, "open")
    client.force_login(learner)
    response = client.get(reverse("course-overview", args=[cards[0]["course"].code]))
    html = response.content.decode()
    assert response.status_code == 200
    assert "Course 1" in html
    assert reverse("module-overview", args=[cards[0]["module"].code]) in html
    assert response.context["show_levels"] is False


@pytest.mark.django_db
def test_roadmap_locks_future_levels_without_lesson_content(client, db):
    _programme_, version, learner, _enrolment, cards = _beginner_pair(db, "roadmaplock")
    advanced = _course(version, 8, "advanced")
    advanced_module = _module(version, 8, advanced)
    client.force_login(learner)
    response = client.get(reverse("roadmap"))
    html = response.content.decode()
    assert response.context["show_levels"] is True
    assert "Course 1" in html and "Course 8" in html
    # A locked level names its course but never links its course page or modules.
    assert reverse("course-overview", args=[advanced.code]) not in html
    assert reverse("module-overview", args=[advanced_module.code]) not in html


@pytest.mark.django_db
def test_ladder_row_counts_two_required_courses(client, db):
    _programme_, version, learner, _enrolment, _cards = _beginner_pair(db, "laddercount2")
    client.force_login(learner)
    assert "0 of 2 required courses complete." in client.get(reverse("roadmap")).content.decode()


@pytest.mark.django_db
def test_ladder_row_counts_one_required_course_in_the_singular(client, db):
    _programme_, version = _programme(db, "laddercount1")
    only = _course(version, 1, "beginner")
    _module(version, 1, only)
    learner, _enrolment = _student(db, version, "laddercount1-learner")
    client.force_login(learner)
    html = client.get(reverse("roadmap")).content.decode()
    assert "0 of 1 required course complete." in html
    assert "0 of  required course" not in html


@pytest.mark.django_db
def test_dashboard_locks_a_levelled_module_that_is_not_open_yet(client, db):
    """The dashboard tracks the whole programme, so a levelled learner still
    sees real progress and the locked modules that explain it."""
    programme, version = _programme(db, "dashladder")
    learner, enrolment = _student(db, version, "dashladder-learner")
    beginner = _course(version, 1, "beginner")
    beginner_module = _module(version, 1, beginner)
    advanced = _course(version, 2, "advanced")
    advanced_module = _module(version, 2, advanced)
    _read(enrolment, beginner_module)
    _pass(enrolment, *_assessment(version, beginner_module, 1))

    client.force_login(learner)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert response.context["total_modules"] == 2
    assert response.context["completed_modules"] == 1
    html = response.content.decode()
    assert "Your programme has no published modules yet." not in html
    assert reverse("module-overview", args=[advanced_module.code]) not in html


@pytest.mark.django_db
def test_assessment_behind_a_locked_level_is_not_the_next_action(client, db):
    """Lesson progress recorded before content was levelled must not offer a
    locked module's assessment as the learner's next step."""
    programme, version = _programme(db, "dashlock")
    learner, enrolment = _student(db, version, "dashlock-learner")

    beginner = _course(version, 1, "beginner")
    beginner_module = _module(version, 1, beginner)
    _read(enrolment, beginner_module)
    _pass(enrolment, *_assessment(version, beginner_module, 1))

    # Nothing sits at the levels in between, so "advanced" stays locked even
    # though its lessons were already read.
    advanced = _course(version, 9, "advanced")
    advanced_module = _module(version, 9, advanced)
    advanced_assessment, _options = _assessment(version, advanced_module, 9)
    _read(enrolment, advanced_module)

    client.force_login(learner)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert response.context["primary_action"] is None
    assert reverse("assessment-take", args=[advanced_assessment.pk]) not in response.content.decode()


@pytest.mark.django_db
def test_sidebar_links_only_assessments_the_learner_can_open(client, db):
    """A locked course keeps its assessment out of the global sidebar too."""
    _programme_, version, learner, _enrolment, cards = _beginner_pair(db, "dashnav")
    advanced = _course(version, 8, "advanced")
    advanced_module = _module(version, 8, advanced)
    advanced_assessment, _options = _assessment(version, advanced_module, 8)
    client.force_login(learner)
    response = client.get(reverse("dashboard"))
    html = response.content.decode()
    assert reverse("assessment-take", args=[cards[0]["assessment"].pk]) in html
    assert reverse("assessment-take", args=[advanced_assessment.pk]) not in html


# ── §8 migration safety ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_compatibility_migration_wraps_legacy_modules_and_is_repeatable(db):
    _programme_, version = _programme(db, "legacy")
    _learner, enrolment = _student(db, version, "legacy-learner")
    modules = [_module(version, index) for index in (1, 2, 3)]
    assessment, correct = _assessment(version, modules[1], 1)
    _pass(enrolment, assessment, correct)
    Course.objects.all().delete()  # the data migration ran against an empty table in test runs

    _course_migration.add_courses(global_apps, None)
    assert version.courses.count() == 1
    course = version.courses.get()
    assert course.is_published is True
    assert course.difficulty == ""  # unset legacy levels are never reclassified
    assert list(course.modules.order_by("order")) == modules
    assert ModuleProgress.objects.filter(enrolment=enrolment, status=ModuleProgress.Status.COMPLETED).count() == 1

    _course_migration.add_courses(global_apps, None)
    assert version.courses.count() == 1
    assert Module.objects.filter(course__isnull=True).count() == 0


@pytest.mark.django_db
def test_compatibility_migration_uses_a_shared_module_level_and_reverses_cleanly(db):
    _programme_, version = _programme(db, "uniform")
    first = _module(version, 1)
    second = _module(version, 2)
    Module.objects.filter(pk__in=[first.pk, second.pk]).update(difficulty="beginner")
    Course.objects.all().delete()

    _course_migration.add_courses(global_apps, None)
    course = version.courses.get()
    assert course.difficulty == "beginner"
    assert list(course.modules.order_by("order")) == [first, second]

    _course_migration.drop_courses(global_apps, None)
    assert Course.objects.count() == 0
    assert Module.objects.filter(course__isnull=True).count() == 2


@pytest.mark.django_db
def test_module_and_assessment_progress_survive_the_new_hierarchy(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "keep")
    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    before = ModuleProgress.objects.get(enrolment=enrolment, module=cards[0]["module"])
    attempts = list(enrolment.theory_attempts.values_list("pk", flat=True))

    assert course_is_completed(enrolment, cards[0]["course"])
    assert ModuleProgress.objects.get(pk=before.pk).module_id == cards[0]["module"].pk
    assert sorted(enrolment.theory_attempts.values_list("pk", flat=True)) == sorted(attempts)


@pytest.mark.django_db
def test_course_progress_survives_a_new_draft_clone(db):
    """§8: a fresh draft must not disturb the live learner's records."""
    programme, version = _programme(db, "cloneme")
    _learner, enrolment = _student(db, version, "cloneme-learner")
    course = _course(version, 1, "beginner")
    module = _module(version, 1, course)
    assessment, correct = _assessment(version, module, 1)
    _pass(enrolment, assessment, correct)

    from instructor_portal.views import _clone_course_content

    new_version = ProgrammeVersion.objects.create(programme=programme, version=2, status=ProgrammeVersion.Status.DRAFT)
    _clone_course_content(version, new_version)

    assert new_version.courses.count() == 1
    assert not new_version.courses.first().is_published
    assert new_version.modules.first().course == new_version.courses.first()
    assert ModuleProgress.objects.filter(enrolment=enrolment, module=module, status=ModuleProgress.Status.COMPLETED).exists()
    assert enrolment.programme_version_id == version.pk


# ── §9 preserved gates ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_final_theory_orientation_and_practical_gates_still_hold(db):
    _programme_, version, _learner, enrolment, cards = _beginner_pair(db, "gates")
    _final_exam(version)

    assert not programme_theory_completed(enrolment)
    assert not practical_is_unlocked(enrolment)
    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    assert not programme_theory_completed(enrolment)
    _pass(enrolment, cards[1]["assessment"], cards[1]["correct"])
    assert programme_theory_completed(enrolment)
    assert not practical_is_unlocked(enrolment)  # orientation is still the next gate

    ProgrammeProgress.objects.update_or_create(enrolment=enrolment, defaults={"orientation_completed_at": timezone.now()})
    assert practical_is_unlocked(enrolment)


@pytest.mark.django_db
def test_draft_courses_do_not_change_existing_progression(db):
    programme, version = _programme(db, "draftsafe")
    _learner, enrolment = _student(db, version, "draftsafe-learner")
    live = _module(version, 1)
    assessment, correct = _assessment(version, live, 1)

    draft_version = ProgrammeVersion.objects.create(programme=programme, version=2, status=ProgrammeVersion.Status.DRAFT)
    draft_course = _course(draft_version, 1, "beginner")
    _module(draft_version, 1, draft_course, published=False)

    assert level_states(version, enrolment)[0]["state"] == "available"
    _pass(enrolment, assessment, correct)
    assert programme_theory_completed(enrolment)


# ── §7 instructor builder ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_instructor_creates_edits_and_publishes_a_course(client, db):
    instructor = _instructor(db)
    _programme_, version = _programme(db, "build", status=ProgrammeVersion.Status.DRAFT)
    client.force_login(instructor)

    response = client.post(
        reverse("programme-course-create", args=[version.pk]),
        {"title": "Clearing Basics", "description": "First subject area.", "difficulty": "beginner", "is_required": "on"},
    )
    course = version.courses.get()
    assert response.status_code == 302
    assert response.url == reverse("programme-course-edit", args=[course.pk])
    assert course.code == "clearing-basics"
    assert course.is_published is False

    client.post(
        reverse("programme-course-edit", args=[course.pk]),
        {"title": "Clearing Basics", "description": "Updated.", "difficulty": "intermediate"},
    )
    course.refresh_from_db()
    assert course.difficulty == "intermediate"
    assert course.description == "Updated."

    # An empty course cannot enter the required progression path.
    assert any("Clearing Basics" in issue for issue in _course_issues(version))
    assert any("Clearing Basics" in issue for issue in _publish_blockers(version, []))

    module = _module(version, 1, course, published=False)
    _assessment(version, module, 1)
    _final_exam(version)
    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    course.refresh_from_db()
    module.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    assert course.is_published is True
    assert module.is_published


@pytest.mark.django_db
def test_publish_stays_blocked_when_the_only_course_is_empty(client, db):
    instructor = _instructor(db, "blocked-instructor")
    _programme_, version = _programme(db, "blocked", status=ProgrammeVersion.Status.DRAFT)
    _course(version, 1, "beginner")
    module = _module(version, 1)  # never moved into a course
    _assessment(version, module, 1)
    _final_exam(version)
    client.force_login(instructor)

    client.post(reverse("course-publish", args=[version.pk]))
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT
    assert _course_issues(version)


@pytest.mark.django_db
def test_instructor_assigns_a_module_to_a_course(client, db):
    instructor = _instructor(db, "assign-instructor")
    _programme_, version = _programme(db, "assign", status=ProgrammeVersion.Status.DRAFT)
    course = _course(version, 1, "beginner")
    module = _module(version, 1, published=False)
    client.force_login(instructor)

    client.post(
        reverse("module-edit", args=[module.pk]),
        {"title": module.title, "description": "", "difficulty": "", "course": str(course.pk), "prerequisite": ""},
    )
    module.refresh_from_db()
    assert module.course_id == course.pk

    # A partial POST without the course field must not detach the module.
    client.post(reverse("module-edit", args=[module.pk]), {"title": module.title})
    module.refresh_from_db()
    assert module.course_id == course.pk


@pytest.mark.django_db
def test_course_with_modules_cannot_be_deleted(client, db):
    instructor = _instructor(db, "delete-instructor")
    _programme_, version = _programme(db, "todelete", status=ProgrammeVersion.Status.DRAFT)
    course = _course(version, 1, "beginner")
    module = _module(version, 1, course, published=False)
    client.force_login(instructor)

    client.post(reverse("programme-course-delete", args=[course.pk]))
    assert Course.objects.filter(pk=course.pk).exists()

    Module.objects.filter(course=course).update(course=None)
    client.post(reverse("programme-course-delete", args=[course.pk]))
    assert not Course.objects.filter(pk=course.pk).exists()
    assert Module.objects.filter(pk=module.pk).exists()


@pytest.mark.django_db
def test_builder_page_groups_modules_under_their_course(client, db):
    instructor = _instructor(db, "builder-instructor")
    _programme_, version = _programme(db, "builder", status=ProgrammeVersion.Status.DRAFT)
    course = _course(version, 1, "beginner")
    _module(version, 1, course, published=False)
    _module(version, 2, published=False)  # still unassigned
    client.force_login(instructor)

    response = client.get(reverse("course-builder-detail", args=[version.pk]))
    html = response.content.decode()
    assert response.status_code == 200
    assert [item["course"].pk for item in response.context["course_groups"]] == [course.pk]
    assert [item.pk for item in response.context["loose_modules"]] == [version.modules.get(code="builder-m2").pk]
    assert "Modules without a course" in html
    assert reverse("programme-course-edit", args=[course.pk]) in html


@pytest.mark.django_db
def test_builder_course_rows_offer_both_move_directions(client, db):
    """Both arrows on a course row have to post their own direction, or the
    ladder can never move a course down."""
    instructor = _instructor(db, "coursemove-instructor")
    _programme_, version = _programme(db, "coursemove", status=ProgrammeVersion.Status.DRAFT)
    first = _course(version, 1, "beginner")
    second = _course(version, 2, "beginner")
    client.force_login(instructor)

    html = client.get(reverse("course-builder-detail", args=[version.pk])).content.decode()
    assert 'name="direction" value="up"' in html
    assert 'name="direction" value="down"' in html

    response = client.post(reverse("programme-course-move", args=[first.pk]), {"direction": "down"})
    assert response.status_code == 302
    assert [item.pk for item in version.courses.order_by("order")] == [second.pk, first.pk]


# ── §4 sidebar ──────────────────────────────────────────────────────────────


def _nav_links(groups):
    links = []
    stack = list(groups)
    while stack:
        item = stack.pop()
        if item.get("link"):
            links.append(item["link"])
        stack.extend(item.get("items", []))
    return links


@pytest.mark.django_db
def test_sidebar_offers_one_roadmap_entry_and_no_modules(client, db):
    _programme_, version, learner, enrolment, cards = _beginner_pair(db, "sidebar")
    _pass(enrolment, cards[0]["assessment"], cards[0]["correct"])
    client.force_login(learner)

    response = client.get(reverse("dashboard"))
    html = response.content.decode()
    links = _nav_links(response.context["sidebar_navigation"])
    assert "Learning Roadmap" in html
    assert reverse("roadmap") in links
    assert not [link for link in links if "/theory/modules/" in link]
    assert not [link for link in links if "/theory/" in link and link != reverse("roadmap")]
    assert "my-learning-lesson" not in html


# ── §5 roadmap at scale ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_roadmap_handles_sixty_modules_grouped_into_courses(client, db):
    _programme_, version = _programme(db, "scale")
    learner, _enrolment = _student(db, version, "scale-learner")
    for course_index in range(1, 7):
        course = _course(version, course_index, DIFFICULTY_LEVELS[(course_index - 1) % 5])
        for offset in range(10):
            _module(version, course_index * 10 + offset, course)
    client.force_login(learner)

    response = client.get(reverse("roadmap"))
    html = response.content.decode()
    assert response.status_code == 200
    assert version.modules.count() == 60
    # Levelled modules are reached through their course card, never linked flat.
    assert response.context["module_summaries"] == []
    assert sum(len(item["courses"]) for item in response.context["levels"]) == 6
    assert reverse("module-overview", args=["scale-m60"]) not in html
    # The hero, the summary strip and the assessment tab report the whole
    # programme; only the module listings themselves move onto the ladder.
    assert response.context["module_total"] == 60
    assert len(response.context["visible_modules"]) == 60
    assert "▤ 60 modules" in html
    assert "No published theory modules are available." not in html
    assert "No assessments published" not in html

    first_course = version.courses.get(code="scale-course-1")
    response = client.get(reverse("course-overview", args=[first_course.code]))
    assert response.status_code == 200
    assert len(response.context["module_summaries"]) == 10
