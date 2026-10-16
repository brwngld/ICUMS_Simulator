"""The guide panel: the theory & practical step carried into the simulator.

Phase 2 of the guided-practice roadmap. A guided step now shows itself on the
simulator page its own binding points at, so the student reads the task, checks
their work and moves on without leaving the simulator.

What these tests hold to:

* the panel appears only for the student whose in-progress attempt points at
  the page they are standing on, and never during ordinary sandbox use;
* every check is decided by ``scenarios.verification`` against saved records,
  and the only thing the client contributes is the fact that the panel asked;
* a step that declares a task keeps its actions locked until that task has
  verified, whichever endpoint the action is posted to;
* the simulator page itself is never replaced — a check updates the panel.
"""

from datetime import timedelta
from uuid import uuid4

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from django.utils import timezone

from accounts.models import User
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import ProgrammeProgress
from scenarios.models import (
    AssistanceEvent,
    ConsignmentApplication,
    Scenario,
    ScenarioActionDefinition,
    ScenarioAttempt,
    ScenarioState,
    ScenarioVersion,
    UcrDeclaration,
)
from scenarios.verification import step_opened_at

from tests.test_guided_simulator_binding import login_with_simulator_access

STEP_ONE = {
    "route": "single-window-create-ucr",
    "task": "Create and submit the importer UCR declaration",
    "verify": {"record": "ucr", "status": "submitted"},
}
STEP_TWO = {
    "route": "single-window-search-consignment-application",
    "task": "Submit the consignment application built on that declaration",
    "verify": {"record": "consignment", "status": "submitted"},
}


def _oriented(user, code):
    programme = Programme.objects.create(name=f"Panel {code}", code=f"panel-{code}")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    disclaimer = DisclaimerVersion.objects.order_by("version").last() or DisclaimerVersion.objects.create(
        version=1, title="Notice", body="Training only.", is_current=True
    )
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    ProgrammeProgress.objects.create(
        enrolment=enrolment,
        theory_completed_at=timezone.now(),
        orientation_unlocked_at=timezone.now(),
        orientation_completed_at=timezone.now(),
    )
    return enrolment


def _scenario(mode=ScenarioVersion.AssistanceMode.BEGINNER, attempts=None):
    scenario = Scenario.objects.create(
        code=f"panel-{uuid4().hex[:8]}", title="Register an Importer", area=Scenario.Area.IMPORT
    )
    return ScenarioVersion.objects.create(
        scenario=scenario,
        version=1,
        status=ScenarioVersion.Status.PUBLISHED,
        assistance_mode=mode,
        maximum_attempts=attempts,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        briefing="Fictional importer.",
        learning_objective="Work the flow inside the simulator.",
    )


def _three_step(version):
    one = ScenarioState.objects.create(
        scenario_version=version, key="step-1", label="Declare the consignment", order=1, is_initial=True,
        guidance="Open the Single Window and file the declaration.", binding=dict(STEP_ONE),
    )
    two = ScenarioState.objects.create(
        scenario_version=version, key="step-2", label="Apply for the document", order=2, binding=dict(STEP_TWO),
    )
    done = ScenarioState.objects.create(scenario_version=version, key="complete", label="Practical complete", order=3, is_terminal=True)
    record = ScenarioActionDefinition.objects.create(
        scenario_version=version, code="record-ucr", label="Record the declaration", from_state=one, to_state=two,
        effects={"step_1_completed": True}, order=1, beginner_hint="Submit it before you can record it.",
    )
    ScenarioActionDefinition.objects.create(
        scenario_version=version, code="record-document", label="Record the application", from_state=two, to_state=done,
        conditions={"step_1_completed": True}, order=2,
    )
    return one, two, done, record


@pytest.fixture
def panel(db):
    """A student part-way through a three-step guided practical."""
    user = User.objects.create_user(username="panel-student", email="panel@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    enrolment = _oriented(user, "student")
    version = _scenario()
    _three_step(version)
    from scenarios.services import start_or_resume_attempt

    attempt, _created = start_or_resume_attempt(enrolment, version)
    return type("Panel", (), {"user": user, "enrolment": enrolment, "version": version, "attempt": attempt})()


@pytest.fixture
def signed_in(client, panel):
    login_with_simulator_access(client, panel.user)
    return panel


def _submitted_ucr(owner, temp_no, **fields):
    return UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description=fields.pop("goods_description", "Panel goods"),
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no=temp_no, status=UcrDeclaration.Status.SUBMITTED, **fields,
    )


def _open(client, attempt):
    return client.post(reverse("scenario-open-step", args=[attempt.pk]))


def _check(client, attempt, from_panel=True):
    payload = {"guide": "1"} if from_panel else {}
    return client.post(reverse("scenario-check-step", args=[attempt.pk]), payload)


# --- where the panel appears -----------------------------------------------


@pytest.mark.django_db
def test_the_panel_appears_on_the_page_the_step_points_at(client, signed_in):
    response = client.get(reverse("single-window-create-ucr"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Theory &amp; Guide" in body
    assert "Register an Importer" in body
    assert "Step 1 of 3" in body
    assert STEP_ONE["task"] in body
    assert "Check my work" in body
    assert "Open the Single Window and file the declaration." in body


@pytest.mark.django_db
def test_no_panel_on_a_page_the_step_does_not_point_at(client, signed_in):
    assert "Theory &amp; Guide" not in client.get(reverse("clearance-workspace")).content.decode()


@pytest.mark.django_db
def test_no_panel_without_an_attempt(client, db):
    user = User.objects.create_user(username="panel-bare", email="bare@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    _oriented(user, "bare")
    login_with_simulator_access(client, user)
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()


@pytest.mark.django_db
def test_no_panel_for_another_students_attempt(client, signed_in, db):
    rival = User.objects.create_user(username="panel-rival", email="rival@example.test", password="test-password")
    rival.groups.add(Group.objects.get(name="Student"))
    _oriented(rival, "rival")
    login_with_simulator_access(client, rival)
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()


@pytest.mark.django_db
def test_no_panel_for_an_instructor_browsing_the_sandbox(client, signed_in, db):
    instructor = User.objects.create_user(username="panel-tutor", email="tutor@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(instructor)
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()


@pytest.mark.django_db
def test_staff_reviewing_a_student_sees_no_panel(client, signed_in, db):
    instructor = User.objects.create_user(username="panel-reviewer", email="reviewer@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    client.force_login(instructor)
    session = client.session
    session["simulator_review_user_id"] = str(signed_in.user.pk)
    session.save()
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()


@pytest.mark.django_db
def test_a_completed_attempt_leaves_the_sandbox_alone(client, signed_in):
    ScenarioAttempt.objects.filter(pk=signed_in.attempt.pk).update(status=ScenarioAttempt.Status.COMPLETED)
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()


@pytest.mark.django_db
def test_walking_into_the_step_is_opening_the_step(client, signed_in):
    client.get(reverse("single-window-create-ucr"))
    attempt = ScenarioAttempt.objects.get(pk=signed_in.attempt.pk)
    assert step_opened_at(attempt, attempt.current_state) is not None


@pytest.mark.django_db
def test_the_panel_follows_the_attempt_the_student_is_actually_on(client, signed_in):
    """Two attempts pointing at the same page: the live one is the one shown."""
    from scenarios.services import start_or_resume_attempt

    ScenarioAttempt.objects.filter(pk=signed_in.attempt.pk).update(started_at=timezone.now() - timedelta(days=1))
    newer = _scenario()
    newer.scenario.title = "Apply for a Exporter Permit"
    newer.scenario.save(update_fields=("title",))
    _three_step(newer)
    start_or_resume_attempt(signed_in.enrolment, newer)

    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "Apply for a Exporter Permit" in body
    assert "Register an Importer" not in body


# --- checking from the panel ------------------------------------------------


@pytest.mark.django_db
def test_a_check_from_the_panel_returns_to_the_simulator_page(client, signed_in):
    _open(client, signed_in.attempt)
    response = _check(client, signed_in.attempt)
    assert response.status_code == 302
    assert response.url == reverse("single-window-create-ucr")


@pytest.mark.django_db
def test_a_failed_check_says_so_in_the_panel_without_losing_the_page(client, signed_in):
    _open(client, signed_in.attempt)
    response = client.post(reverse("scenario-check-step", args=[signed_in.attempt.pk]), {"guide": "1"}, follow=True)
    body = response.content.decode()
    assert "No UCR declaration records exist" in body
    assert response.redirect_chain == [(reverse("single-window-create-ucr"), 302)]


@pytest.mark.django_db
def test_a_check_updates_the_panel_without_a_page_load(client, signed_in):
    """The fetch path: a student mid-declaration keeps their unsaved work."""
    _open(client, signed_in.attempt)
    response = client.post(
        reverse("scenario-check-step", args=[signed_in.attempt.pk]), {"guide": "1"}, HTTP_X_GUIDE_PANEL="1"
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert 'data-guide-body' in body
    assert "No UCR declaration records exist" in body
    assert "<html" not in body.lower()


@pytest.mark.django_db
def test_a_stale_record_still_fails_from_the_panel(client, signed_in):
    _submitted_ucr(signed_in.user, "TEMPUCR2699000030")
    stale = timezone.now() - timedelta(minutes=5)
    UcrDeclaration.objects.filter(temp_no="TEMPUCR2699000030").update(created_at=stale, updated_at=stale, submitted_at=stale)
    _open(client, signed_in.attempt)
    body = client.post(reverse("scenario-check-step", args=[signed_in.attempt.pk]), {"guide": "1"}, follow=True).content.decode()
    assert "predate this task" in body


@pytest.mark.django_db
def test_wrong_saved_values_keep_the_step_locked(client, signed_in):
    state = signed_in.attempt.current_state
    state.binding = {**STEP_ONE, "verify": {"record": "ucr", "status": "submitted", "fields": {"goods_description": "HOUSEHOLD GOODS"}}}
    state.save(update_fields=("binding",))
    _open(client, signed_in.attempt)
    _submitted_ucr(signed_in.user, "TEMPUCR2699000031")
    body = client.post(reverse("scenario-check-step", args=[signed_in.attempt.pk]), {"guide": "1"}, follow=True).content.decode()
    assert "do not match this task" in body
    assert "Record the declaration" not in body


@pytest.mark.django_db
def test_the_panel_reports_only_what_the_database_supports(client, signed_in):
    """Forging the panel's fields cannot buy a pass."""
    _open(client, signed_in.attempt)
    body = client.post(
        reverse("scenario-check-step", args=[signed_in.attempt.pk]),
        {"guide": "1", "passed": "true", "result": "Simulator task verified", "returnUrl": "/admin/"},
        follow=True,
    ).content.decode()
    assert "Simulator task verified" not in body
    assert "No UCR declaration records exist" in body


# --- the lock ---------------------------------------------------------------


@pytest.mark.django_db
def test_a_step_holds_its_action_until_the_task_verifies(client, signed_in):
    _open(client, signed_in.attempt)
    record = ScenarioActionDefinition.objects.get(scenario_version=signed_in.version, code="record-ucr")
    response = client.post(reverse("scenario-action", args=[signed_in.attempt.pk, record.pk]), {"guide": "1"})
    assert response.status_code == 302
    assert response.url == reverse("single-window-create-ucr")
    attempt = ScenarioAttempt.objects.get(pk=signed_in.attempt.pk)
    assert attempt.current_state.key == "step-1"
    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "has not been verified yet" in body


@pytest.mark.django_db
def test_the_lock_holds_on_the_workspace_path_too(client, signed_in):
    _open(client, signed_in.attempt)
    record = ScenarioActionDefinition.objects.get(scenario_version=signed_in.version, code="record-ucr")
    response = client.post(reverse("scenario-action", args=[signed_in.attempt.pk, record.pk]))
    assert response.status_code == 302
    assert response.url == reverse("scenario-workspace", args=[signed_in.attempt.pk])
    assert ScenarioAttempt.objects.get(pk=signed_in.attempt.pk).current_state.key == "step-1"


@pytest.mark.django_db
def test_a_locked_step_offers_no_action_button(client, signed_in):
    _open(client, signed_in.attempt)
    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "Record the declaration" not in body
    assert "The next step unlocks after a successful check." in body


@pytest.mark.django_db
def test_a_verified_step_offers_its_action(client, signed_in):
    _open(client, signed_in.attempt)
    _submitted_ucr(signed_in.user, "TEMPUCR2699000032")
    _check(client, signed_in.attempt)
    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "Simulator task verified" in body
    assert "Record the declaration" in body


@pytest.mark.django_db
def test_the_pass_is_recorded_server_side(client, signed_in):
    _open(client, signed_in.attempt)
    _submitted_ucr(signed_in.user, "TEMPUCR2699000033")
    _check(client, signed_in.attempt, from_panel=False)
    attempt = ScenarioAttempt.objects.get(pk=signed_in.attempt.pk)
    assert any(key.startswith("_sim_verified.") for key in attempt.state_data)
    assert attempt.current_state.key == "step-1"  # a pass records, it never advances


# --- hints and assistance modes ---------------------------------------------


@pytest.mark.django_db
def test_a_hint_shows_in_the_panel_and_is_logged(client, signed_in):
    _open(client, signed_in.attempt)
    response = client.post(reverse("scenario-hint", args=[signed_in.attempt.pk]), {"guide": "1"}, follow=True)
    assert response.redirect_chain == [(reverse("single-window-create-ucr"), 302)]
    assert "Submit it before you can record it." in response.content.decode()
    assert AssistanceEvent.objects.filter(attempt=signed_in.attempt, kind=AssistanceEvent.Kind.HINT).count() == 1


@pytest.mark.django_db
def test_advanced_mode_shows_the_task_and_nothing_else(client, panel):
    version = panel.version
    version.assistance_mode = ScenarioVersion.AssistanceMode.ADVANCED
    version.save(update_fields=("assistance_mode",))
    ScenarioAttempt.objects.filter(pk=panel.attempt.pk).update(assistance_mode=ScenarioVersion.AssistanceMode.ADVANCED)
    login_with_simulator_access(client, panel.user)
    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert STEP_ONE["task"] in body
    assert "Hint" not in body
    assert "Open the Single Window and file the declaration." not in body


# --- the whole flow ----------------------------------------------------------


@pytest.mark.django_db
def test_the_guided_flow_runs_inside_the_simulator(client, signed_in):
    """Step 1 → step 2 → complete, without ever leaving a simulator page."""
    step_one = reverse("single-window-create-ucr")
    step_two = reverse("single-window-search-consignment-application")

    client.get(step_one)
    _submitted_ucr(signed_in.user, "TEMPUCR2699000040")
    _check(client, signed_in.attempt)
    record = ScenarioActionDefinition.objects.get(scenario_version=signed_in.version, code="record-ucr")
    onward = client.post(reverse("scenario-action", args=[signed_in.attempt.pk, record.pk]), {"guide": "1"})
    assert onward.url == step_two

    second = ScenarioAttempt.objects.get(pk=signed_in.attempt.pk)
    assert second.current_state.key == "step-2"
    body = client.get(step_two).content.decode()
    assert "Step 2 of 3" in body
    assert STEP_TWO["task"] in body

    ConsignmentApplication.objects.create(
        owner=signed_in.user, ucr=UcrDeclaration.objects.get(temp_no="TEMPUCR2699000040"),
        status=ConsignmentApplication.Status.SUBMITTED,
    )
    _check(client, second)
    apply_action = ScenarioActionDefinition.objects.get(scenario_version=signed_in.version, code="record-document")
    finished = client.post(reverse("scenario-action", args=[second.pk, apply_action.pk]), {"guide": "1"})
    # The last step has no simulator page of its own, so the panel hands the
    # student back to the workspace rather than stranding them on the search.
    assert finished.url == reverse("scenario-workspace", args=[second.pk])
    assert ScenarioAttempt.objects.get(pk=second.pk).status == ScenarioAttempt.Status.COMPLETED


@pytest.mark.django_db
def test_the_panel_survives_a_refresh(client, signed_in):
    _open(client, signed_in.attempt)
    _submitted_ucr(signed_in.user, "TEMPUCR2699000041")
    _check(client, signed_in.attempt)
    first = client.get(reverse("single-window-create-ucr")).content.decode()
    second = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "Simulator task verified" in first
    assert "Simulator task verified" not in second  # a result is read once
    assert "Step 1 of 3" in second  # and the step itself is simply still there


@pytest.mark.django_db
def test_the_panel_is_collapsible_and_announces_its_results(client, signed_in):
    body = client.get(reverse("single-window-create-ucr")).content.decode()
    assert "<details" in body
    assert "<summary" in body
    assert 'role="status"' in body
    assert "data-guide-feedback" in body
    assert 'name="guide" value="1"' in body


@pytest.mark.django_db
def test_attempt_limits_are_unchanged_by_the_panel(client, signed_in, db):
    from django.core.exceptions import PermissionDenied

    from scenarios.services import start_or_resume_attempt

    ScenarioAttempt.objects.filter(pk=signed_in.attempt.pk).update(status=ScenarioAttempt.Status.ABANDONED)
    signed_in.version.maximum_attempts = 1
    signed_in.version.save(update_fields=("maximum_attempts",))
    with pytest.raises(PermissionDenied):
        start_or_resume_attempt(signed_in.enrolment, signed_in.version)
    assert "Theory &amp; Guide" not in client.get(reverse("single-window-create-ucr")).content.decode()
