"""Learners enrolled on more than one programme.

Without a choice, every student surface resolves the *same* enrolment: the oldest
active one, with the primary key breaking ties because ``enrolled_at`` is not
unique and an unordered query can pick a different row per page.

The choice itself is the ``?programme=<code>`` parameter. Every link the portal
generates carries it, `/programmes/` lists the enrolments to choose between, and
a parameter for a programme the learner is not enrolled in is refused.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from datetime import UTC

from django.utils import timezone

from accounts.models import SimulatorCredential, User, allocate_student_id
from assessments.models import AnswerOption, Assessment, AssessmentItem, Question, QuestionVersion
from learning.models import Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import ProgrammeProgress
from scenarios.models import Scenario, ScenarioAttempt, ScenarioState, ScenarioVersion


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    DisclaimerAcceptance.objects.create(
        user=user, disclaimer=DisclaimerVersion.objects.create(version=1, title="Notice", body="Training only.", is_current=True)
    )
    return user


def _enrolment(learner, code, module_code, assessment_title, enrolled_at=None):
    programme = Programme.objects.create(name=f"Programme {code}", code=code)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=learner, programme_version=version)
    module = Module.objects.create(programme_version=version, code=module_code, title=f"Module {code}", order=1, is_published=True)
    Lesson.objects.create(module=module, slug=f"lesson-{code}", title=f"Lesson {code}", order=1, is_published=True)
    question_version = QuestionVersion.objects.create(question=Question.objects.create(code=f"q-{code}"), version=1, prompt="Pick one", points=1, is_published=True)
    AnswerOption.objects.create(question_version=question_version, label="Right", is_correct=True, order=1)
    assessment = Assessment.objects.create(programme_version=version, module=module, title=assessment_title, pass_percentage=50, is_published=True)
    AssessmentItem.objects.create(assessment=assessment, question_version=question_version)
    if enrolled_at is not None:
        Enrolment.objects.filter(pk=enrolment.pk).update(enrolled_at=enrolled_at)
        enrolment.refresh_from_db()
    return enrolment


def _two_programmes(db, username, first_at, second_at):
    learner = _learner(db, username)
    first = _enrolment(learner, f"{username}-a", f"{username}-a-m", "First assessment", enrolled_at=first_at)
    second = _enrolment(learner, f"{username}-b", f"{username}-b-m", "Second assessment", enrolled_at=second_at)
    return learner, first, second


@pytest.mark.django_db
def test_dashboard_reads_the_oldest_active_enrolment(client, db):
    learner = _learner(db, "oldest-learner")
    first = _enrolment(learner, "first-prog", "first-m", "First assessment", enrolled_at=timezone.datetime(2026, 1, 1, tzinfo=UTC))
    _enrolment(learner, "second-prog", "second-m", "Second assessment", enrolled_at=timezone.datetime(2026, 2, 1, tzinfo=UTC))
    client.force_login(learner)

    response = client.get(reverse("dashboard"))
    assert response.context["enrolment"].pk == first.pk
    html = response.content.decode()
    assert "Module first-prog" in html
    assert "Module second-prog" not in html


@pytest.mark.django_db
def test_dashboard_and_roadmap_agree_when_enrolments_share_a_timestamp(client, db):
    """Same-second enrolments used to be resolved by two different queries."""
    learner = _learner(db, "tied-learner")
    moment = timezone.datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    _enrolment(learner, "tied-a", "tied-a-m", "Tied A assessment", enrolled_at=moment)
    _enrolment(learner, "tied-b", "tied-b-m", "Tied B assessment", enrolled_at=moment)
    client.force_login(learner)

    dashboard_enrolment = client.get(reverse("dashboard")).context["enrolment"]
    roadmap_enrolment = client.get(reverse("roadmap")).context["enrolment"]
    assert dashboard_enrolment.pk == roadmap_enrolment.pk


@pytest.mark.django_db
def test_sidebar_assessment_link_comes_from_the_chosen_enrolment(client, db):
    learner = _learner(db, "sidebar-learner")
    first = _enrolment(learner, "nav-a", "nav-a-m", "Nav A assessment", enrolled_at=timezone.datetime(2026, 4, 1, tzinfo=UTC))
    _enrolment(learner, "nav-b", "nav-b-m", "Nav B assessment", enrolled_at=timezone.datetime(2026, 4, 2, tzinfo=UTC))
    client.force_login(learner)

    assessment = Assessment.objects.get(programme_version=first.programme_version)
    html = client.get(reverse("dashboard")).content.decode()
    assert reverse("assessment-take", args=[assessment.pk]) in html
    other = Assessment.objects.get(programme_version__programme__code="nav-b")
    assert reverse("assessment-take", args=[other.pk]) not in html


@pytest.mark.django_db
def test_the_programme_parameter_opens_the_other_roadmap(client, db):
    learner, _, second = _two_programmes(
        db, "switch-prog", timezone.datetime(2026, 5, 1, tzinfo=UTC), timezone.datetime(2026, 5, 2, tzinfo=UTC)
    )
    client.force_login(learner)

    response = client.get(reverse("roadmap"), {"programme": second.programme_version.programme.code})
    assert response.context["enrolment"].pk == second.pk
    html = response.content.decode()
    assert "Module switch-prog-b" in html
    assert "Module switch-prog-a" not in html


@pytest.mark.django_db
def test_a_module_of_the_other_programme_opens_once_it_is_chosen(client, db):
    learner, _, second = _two_programmes(
        db, "deep-link", timezone.datetime(2026, 6, 1, tzinfo=UTC), timezone.datetime(2026, 6, 2, tzinfo=UTC)
    )
    client.force_login(learner)
    url = reverse("module-overview", args=[second.programme_version.modules.first().code])

    assert client.get(url).status_code == 404
    chosen = client.get(url, {"programme": second.programme_version.programme.code})
    assert chosen.status_code == 200
    assert chosen.context["enrolment"].pk == second.pk


@pytest.mark.django_db
def test_links_from_a_programme_page_stay_on_that_programme(client, db):
    learner, _, second = _two_programmes(
        db, "sticky", timezone.datetime(2026, 7, 1, tzinfo=UTC), timezone.datetime(2026, 7, 2, tzinfo=UTC)
    )
    client.force_login(learner)
    code = second.programme_version.programme.code

    html = client.get(reverse("roadmap"), {"programme": code}).content.decode()
    page_links = [
        link for link in _html_links(html)
        if link.startswith(reverse("roadmap")) and link != reverse("roadmap")
    ]
    assert page_links, "the roadmap should link into its own module and lesson pages"
    assert all(f"programme={code}" in link for link in page_links)


@pytest.mark.django_db
def test_the_programmes_page_lists_every_enrolment(client, db):
    learner = _learner(db, "listed")
    _enrolment(learner, "listed-a", "listed-a-m", "Listed A assessment", enrolled_at=timezone.datetime(2026, 8, 1, tzinfo=UTC))
    _enrolment(learner, "listed-b", "listed-b-m", "Listed B assessment", enrolled_at=timezone.datetime(2026, 8, 2, tzinfo=UTC))
    client.force_login(learner)

    html = client.get(reverse("my-programmes")).content.decode()
    assert "Programme listed-a" in html
    assert "Programme listed-b" in html
    assert "0 of 1 modules complete" in html
    assert f"{reverse('roadmap')}?programme=listed-b" in html


@pytest.mark.django_db
def test_the_dashboard_only_lists_programmes_when_there_is_a_choice(client, db):
    learner = _learner(db, "chosen")
    _enrolment(learner, "chosen-a", "chosen-a-m", "Chosen A assessment", enrolled_at=timezone.datetime(2026, 9, 1, tzinfo=UTC))
    client.force_login(learner)
    assert "My programmes" not in client.get(reverse("dashboard")).content.decode()

    _enrolment(learner, "chosen-b", "chosen-b-m", "Chosen B assessment", enrolled_at=timezone.datetime(2026, 9, 2, tzinfo=UTC))
    html = client.get(reverse("dashboard")).content.decode()
    assert "My programmes" in html
    assert "Programme chosen-b" in html


@pytest.mark.django_db
def test_the_sidebar_offers_the_programmes_page_with_a_second_enrolment(client, db):
    learner = _learner(db, "nav-multi")
    _enrolment(learner, "nav-multi-a", "nav-multi-a-m", "Nav multi A assessment", enrolled_at=timezone.datetime(2026, 10, 1, tzinfo=UTC))
    client.force_login(learner)
    assert reverse("my-programmes") not in client.get(reverse("dashboard")).content.decode()

    _enrolment(learner, "nav-multi-b", "nav-multi-b-m", "Nav multi B assessment", enrolled_at=timezone.datetime(2026, 10, 2, tzinfo=UTC))
    assert reverse("my-programmes") in client.get(reverse("dashboard")).content.decode()


@pytest.mark.django_db
def test_a_programme_the_learner_is_not_enrolled_on_is_refused(client, db):
    learner = _learner(db, "only-one")
    _enrolment(learner, "only-one-a", "only-one-a-m", "Only one assessment")
    client.force_login(learner)

    response = client.get(reverse("roadmap"), {"programme": "someone-else"})
    assert response.status_code == 302
    assert response.headers["location"] == reverse("dashboard")


@pytest.mark.django_db
def test_practical_training_opens_on_the_programme_that_was_oriented(client, db):
    """The gate is per enrolment, so the programme chosen is the one checked."""
    learner, _, second = _two_programmes(
        db, "practical-gate", timezone.datetime(2026, 11, 1, tzinfo=UTC), timezone.datetime(2026, 11, 2, tzinfo=UTC)
    )
    _oriented(second)
    _simulator_client(client, learner)

    assert client.get(reverse("scenario-list")).status_code == 302
    chosen = client.get(reverse("scenario-list"), {"programme": second.programme_version.programme.code})
    assert chosen.status_code == 200


@pytest.mark.django_db
def test_a_scenario_starts_on_the_programme_that_owns_it(client, db):
    """Losing the parameter must not attach the attempt to the oldest enrolment.

    The scenario names its own programme, so the practical pages read the
    enrolment from it rather than from whichever one the request resolves.
    """
    learner, first, second = _two_programmes(
        db, "owning", timezone.datetime(2026, 12, 1, tzinfo=UTC), timezone.datetime(2026, 12, 2, tzinfo=UTC)
    )
    _oriented(first)
    _oriented(second)
    version = _scenario(second, "owning-scenario")
    _simulator_client(client, learner)

    started = client.post(reverse("scenario-start", args=[version.pk]))
    assert started.status_code == 302
    assert ScenarioAttempt.objects.get().enrolment_id == second.pk


@pytest.mark.django_db
def test_practical_links_carry_the_chosen_programme(client, db):
    learner, _, second = _two_programmes(
        db, "sticky-practical", timezone.datetime(2027, 1, 1, tzinfo=UTC), timezone.datetime(2027, 1, 2, tzinfo=UTC)
    )
    _oriented(second)
    version = _scenario(second, "sticky-practical-scenario")
    _simulator_client(client, learner)
    code = second.programme_version.programme.code
    query = {"programme": code}

    listing = client.get(reverse("scenario-list"), query).content.decode()
    assert f"{reverse('scenario-detail', args=[version.pk])}?programme={code}" in listing
    detail = client.get(reverse("scenario-detail", args=[version.pk]), query).content.decode()
    assert f"{reverse('scenario-start', args=[version.pk])}?programme={code}" in detail


@pytest.mark.django_db
def test_a_scenario_page_keeps_its_navigation_on_that_programme(client, db):
    """The workspace url carries no parameter, so the page has to say the programme."""
    learner, _, second = _two_programmes(
        db, "mid-scenario", timezone.datetime(2027, 2, 1, tzinfo=UTC), timezone.datetime(2027, 2, 2, tzinfo=UTC)
    )
    _oriented(second)
    version = _scenario(second, "mid-scenario-scenario")
    _simulator_client(client, learner)
    client.post(reverse("scenario-start", args=[version.pk]))

    html = client.get(reverse("scenario-workspace", args=[ScenarioAttempt.objects.get().pk])).content.decode()
    assert f"{reverse('scenario-list')}?programme={second.programme_version.programme.code}" in html


@pytest.mark.django_db
def test_a_single_programme_learner_keeps_plain_practical_links(client, db):
    learner = _learner(db, "solo-practical")
    enrolment = _enrolment(learner, "solo-a", "solo-a-m", "Solo assessment")
    _oriented(enrolment)
    version = _scenario(enrolment, "solo-scenario")
    _simulator_client(client, learner)

    html = client.get(reverse("scenario-list")).content.decode()
    assert reverse("scenario-detail", args=[version.pk]) in html
    assert "programme=" not in html


def _oriented(enrolment):
    """Walk the progression the practical pages demand: passed theory, done orientation."""
    ProgrammeProgress.objects.create(
        enrolment=enrolment,
        theory_completed_at=timezone.now(),
        orientation_unlocked_at=timezone.now(),
        orientation_completed_at=timezone.now(),
    )


def _scenario(enrolment, code):
    module = enrolment.programme_version.modules.first()
    version = ScenarioVersion.objects.create(
        scenario=Scenario.objects.create(code=code, title=f"Scenario {code}", area=Scenario.Area.IMPORT),
        module=module,
        version=1,
        status=ScenarioVersion.Status.PUBLISHED,
        assistance_mode=ScenarioVersion.AssistanceMode.BEGINNER,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        briefing="Fictional scenario.",
        learning_objective="Open the programme that owns this scenario.",
    )
    ScenarioState.objects.create(scenario_version=version, key="start", label="Start", order=1, is_initial=True)
    return version


def _simulator_client(client, learner):
    """A logged-in learner who also holds the current simulator credentials."""
    if not learner.student_id:
        learner.student_id = allocate_student_id(learner.first_name or learner.username)
        learner.save(update_fields=("student_id",))
    credential, _ = SimulatorCredential.objects.get_or_create(user=learner)
    credential.issue()
    client.force_login(learner)
    session = client.session
    session["simulator_user_id"] = str(learner.pk)
    session.save()


def _html_links(html):
    """Every href in a rendered page, in document order."""
    from html.parser import HTMLParser

    class Collector(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.hrefs += [value for name, value in attrs if name == "href" and value]

    parser = Collector()
    parser.feed(html)
    return parser.hrefs
