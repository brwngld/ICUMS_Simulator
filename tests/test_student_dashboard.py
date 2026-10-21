"""The student dashboard's redesigned layout.

The scenario mirrors the approved design mockup: a learner three modules into
a five-module programme (module four up next, module five locked), enrolled on
two further programmes they have not started, holding an active simulator
credential. The assertions hold the section order, status wording and data
binding the redesign introduced.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import SimulatorCredential, User
from assessments.models import AnswerOption, Assessment, AssessmentItem, Question, QuestionVersion
from assessments.services import get_or_start_attempt, submit_attempt
from learning.models import Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ProgrammeProgress


def _module_with_assessment(version, code, title, order):
    module = Module.objects.create(programme_version=version, code=code, title=title, order=order, is_published=True)
    lesson = Lesson.objects.create(module=module, slug=f"{code}-lesson", title=f"{title} lesson", order=1, is_published=True)
    question_version = QuestionVersion.objects.create(
        question=Question.objects.create(code=f"{code}-q"), version=1, prompt="Choose the correct response.",
        explanation="Review the example.", points=2, is_published=True,
    )
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=question_version, label="Wrong", is_correct=False, order=2)
    assessment = Assessment.objects.create(
        programme_version=version, module=module, title=f"{title} assessment", pass_percentage=70, is_published=True
    )
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
    return module


def _pass_module(enrolment, module):
    LessonProgress.objects.update_or_create(
        enrolment=enrolment, lesson=module.lessons.first(), defaults={"completed_at": timezone.now()}
    )
    assessment = module.assessments.first()
    question_version = assessment.items.first().question_version
    correct = question_version.options.get(is_correct=True)
    attempt = get_or_start_attempt(enrolment, assessment)
    submit_attempt(attempt, {str(question_version.pk): correct.pk})


@pytest.fixture
def dashboard_setup(db, client):
    user = User.objects.create_user(username="demo-student", email="demo@example.test", password="test-password", first_name="Demo")
    user.groups.add(Group.objects.get(name="Student"))
    disclaimer = DisclaimerVersion.objects.create(version=1, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)

    programme = Programme.objects.create(
        name="Ghana Standards Authority Requirements for Customs Business", code="gsa-requirements",
        description="Learn what the GSA expects of customs business: quality documents, conformity assessment and clearing goods.",
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    modules = [_module_with_assessment(version, f"gsa-m{i}", f"Module {i}", i) for i in range(1, 6)]
    # The programme is sequential: each module unlocks when its predecessor is passed.
    for previous, module in zip(modules, modules[1:]):
        module.prerequisite = previous
        module.save(update_fields=("prerequisite",))

    for title in ("Experience Ladder", "Experience demo"):
        other = Programme.objects.create(
            name=title, code=title.lower().replace(" ", "-"), description=f"A sample programme: {title}."
        )
        other_version = ProgrammeVersion.objects.create(programme=other, version=1, status=ProgrammeVersion.Status.PUBLISHED)
        _module_with_assessment(other_version, f"{other.code}-m1", f"{title} module", 1)
        Enrolment.objects.create(student=user, programme_version=other_version)

    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    return {"client": client, "user": user, "enrolment": enrolment, "modules": modules}


@pytest.mark.django_db
def test_the_dashboard_matches_the_approved_layout(dashboard_setup):
    for module in dashboard_setup["modules"][:3]:
        _pass_module(dashboard_setup["enrolment"], module)
    client = dashboard_setup["client"]
    client.force_login(dashboard_setup["user"])

    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert response.context["modules_left"] == 2
    assert response.context["journey_stage"] == "learn"
    html = response.content.decode()

    assert "3 of 5 modules completed" in html
    assert "2 modules left" in html
    assert 'aria-valuenow="60"' in html
    assert "5 modules" in html  # the roadmap's count pill
    # Module four is the highlighted next step; module five is locked behind it.
    assert "Up next" in html
    assert "Locked until module 4 is passed" in html
    assert html.count("Completed") >= 3
    up_next = dashboard_setup["modules"][3]
    locked = dashboard_setup["modules"][4]
    # Links carry the programme qualifier, so match the path inside the href.
    assert reverse("module-overview", args=[up_next.code]) in html
    assert locked.title in html

    assert "Simulator access" in html
    assert "Active" in html
    assert "My programmes" in html
    assert "3 enrolled" in html
    assert "In progress" in html
    assert "Not started" in html
    assert "Start programme" in html
    assert "Continue" in html
    assert "Learn → Practise → Demonstrate" in html


@pytest.mark.django_db
def test_the_journey_stage_follows_the_learner(dashboard_setup):
    client = dashboard_setup["client"]
    client.force_login(dashboard_setup["user"])
    assert client.get(reverse("dashboard")).context["journey_stage"] == "learn"

    now = timezone.now()
    ProgrammeProgress.objects.create(
        enrolment=dashboard_setup["enrolment"], theory_completed_at=now, orientation_unlocked_at=now, orientation_completed_at=now
    )
    assert client.get(reverse("dashboard")).context["journey_stage"] == "practise"
