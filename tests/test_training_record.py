"""The instructor's training-record page (the Review redesign).

One enrolled student, two published modules — the first passed with its
lessons completed, the second untouched — plus a theory attempt history and a
second programme for the switcher. The page must show all of it read-only.
"""

from datetime import timedelta

from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

import pytest

from accounts.models import User
from assessments.models import AnswerOption, Assessment, AssessmentItem, Question, QuestionVersion
from assessments.models import TheoryAttempt
from assessments.services import get_or_start_attempt, submit_attempt
from learning.models import Lesson, Module
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress


@pytest.fixture
def record_setup(db, client):
    instructor = User.objects.create_user(username="record-instructor", email="ri@example.test", password="x")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    student = User.objects.create_user(username="record-student", email="rs@example.test", password="x", first_name="Demo", last_name="Student")

    programme = Programme.objects.create(
        name="Ghana Standards Authority Requirements for Customs Business", code="gsa-record",
        target_audience="Learners", learning_approach="Guided",
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status="published")
    enrolment = Enrolment.objects.create(student=student, programme_version=version, enrolled_by=instructor)

    modules = []
    for order, title in enumerate(("Quality Documents and Key Terms", "Clearing Imported Goods with the GSA"), start=1):
        module = Module.objects.create(programme_version=version, code=f"gsa-rec-m{order}", title=title, order=order, is_published=True)
        lesson = Lesson.objects.create(module=module, slug=f"gsa-rec-m{order}-lesson", title=f"{title} — lesson", order=1, is_published=True)
        question_version = QuestionVersion.objects.create(
            question=Question.objects.create(code=f"gsa-rec-m{order}-q"), version=1, prompt="Choose the correct response.",
            explanation="Review.", points=2, is_published=True,
        )
        AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
        AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
        assessment = Assessment.objects.create(programme_version=version, module=module, title=f"{title} assessment", pass_percentage=70, is_published=True)
        AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
        modules.append({"module": module, "lesson": lesson, "assessment": assessment, "question_version": question_version})

    other = Programme.objects.create(name="Experience Ladder (sample)", code="ladder-record", target_audience="Learners", learning_approach="Self-paced")
    other_version = ProgrammeVersion.objects.create(programme=other, version=1, status="published")
    other_enrolment = Enrolment.objects.create(student=student, programme_version=other_version, enrolled_by=instructor)
    return {
        "client": client, "instructor": instructor, "student": student,
        "enrolment": enrolment, "modules": modules, "other_enrolment": other_enrolment,
    }


def _pass_module(enrolment, entry):
    LessonProgress.objects.update_or_create(
        enrolment=enrolment, lesson=entry["lesson"], defaults={"completed_at": timezone.now()}
    )
    assessment = entry["assessment"]
    question_version = assessment.items.first().question_version
    attempt = get_or_start_attempt(enrolment, assessment)
    submit_attempt(attempt, {str(question_version.pk): question_version.options.get(is_correct=True).pk})
    # Submit recomputes duration from real elapsed time; pin it for the display test.
    TheoryAttempt.objects.filter(pk=attempt.pk).update(duration_seconds=125)


def test_the_training_record_shows_the_mockup_sections(record_setup):
    entry = record_setup["modules"][0]
    _pass_module(record_setup["enrolment"], entry)
    client = record_setup["client"]
    client.force_login(record_setup["instructor"])

    response = client.get(reverse("instructor-student-detail", args=[record_setup["enrolment"].pk]))
    assert response.status_code == 200
    html = response.content.decode()

    assert "Training record" in html
    assert "shown read-only" in html
    assert "view-mode-badge" in html
    # The programme switcher lists both enrolments, current one active.
    assert "2 enrolled" in html
    assert "Experience Ladder (sample)" in html
    # Stats reflect one of two modules complete.
    assert "1/2" in html
    # The completed module reads as completed; the other as not started.
    assert "Completed" in html
    assert "Not started" in html
    assert "Clearing Imported Goods with the GSA — lesson" in html


def test_the_attempts_table_and_best_chips_render(record_setup):
    entry = record_setup["modules"][0]
    _pass_module(record_setup["enrolment"], entry)
    client = record_setup["client"]
    client.force_login(record_setup["instructor"])

    html = client.get(reverse("instructor-student-detail", args=[record_setup["enrolment"].pk])).content.decode()
    assert "1 attempt across 1 assessment." in html
    assert "Best: 100% · Pass (attempt 1)" in html
    assert "2 min" in html  # 125 seconds, formatted
    assert "Pass" in html


def test_an_untouched_programme_shows_empty_states(record_setup):
    client = record_setup["client"]
    client.force_login(record_setup["instructor"])
    html = client.get(reverse("instructor-student-detail", args=[record_setup["enrolment"].pk])).content.decode()
    assert "No assessment attempts yet" in html
    assert "No practical attempts yet" in html


def test_the_programme_switcher_links_each_enrolment(record_setup):
    client = record_setup["client"]
    client.force_login(record_setup["instructor"])
    html = client.get(reverse("instructor-student-detail", args=[record_setup["other_enrolment"].pk])).content.decode()
    assert reverse("instructor-student-detail", args=[record_setup["enrolment"].pk]) in html


def test_lessons_completed_show_their_state(record_setup):
    entry = record_setup["modules"][0]
    LessonProgress.objects.update_or_create(
        enrolment=record_setup["enrolment"], lesson=entry["lesson"], defaults={"completed_at": timezone.now()}
    )
    client = record_setup["client"]
    client.force_login(record_setup["instructor"])
    html = client.get(reverse("instructor-student-detail", args=[record_setup["enrolment"].pk])).content.decode()
    assert html.count("In progress") >= 1  # the module row, from its touched lesson
    assert "0/1" in html or "1 lesson recorded" in html
