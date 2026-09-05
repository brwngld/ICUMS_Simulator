import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import ProgrammeProgress
from scenarios.models import AssistanceEvent, Scenario, ScenarioAction, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument, ScenarioState, ScenarioVersion
from scenarios.services import available_actions, perform_action, start_or_resume_attempt


@pytest.fixture
def scenario_setup(db):
    user = User.objects.create_user(username="practical-student", email="practical@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    programme = Programme.objects.create(name="Practical Programme", code="practical-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    disclaimer = DisclaimerVersion.objects.create(version=20, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    ProgrammeProgress.objects.create(
        enrolment=enrolment,
        theory_completed_at=timezone.now(),
        orientation_unlocked_at=timezone.now(),
        orientation_completed_at=timezone.now(),
    )
    scenario = Scenario.objects.create(code="engine-test", title="Engine Test", area=Scenario.Area.IMPORT)
    scenario_version = ScenarioVersion.objects.create(
        scenario=scenario,
        version=1,
        status=ScenarioVersion.Status.PUBLISHED,
        assistance_mode=ScenarioVersion.AssistanceMode.BEGINNER,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        briefing="Fictional scenario.",
        learning_objective="Test state transitions.",
        initial_data={"parallel_ready": True, "parallel_done": False},
    )
    initial = ScenarioState.objects.create(scenario_version=scenario_version, key="review", label="Review", order=1, is_initial=True)
    middle = ScenarioState.objects.create(scenario_version=scenario_version, key="process", label="Process", order=2)
    terminal = ScenarioState.objects.create(scenario_version=scenario_version, key="complete", label="Complete", order=3, is_terminal=True)
    first = ScenarioActionDefinition.objects.create(
        scenario_version=scenario_version,
        code="record-review",
        label="Record review",
        from_state=initial,
        to_state=middle,
        effects={"reviewed": True},
        success_feedback="Review recorded.",
        beginner_hint="Review the documents first.",
        order=1,
    )
    finish = ScenarioActionDefinition.objects.create(
        scenario_version=scenario_version,
        code="finish",
        label="Finish",
        from_state=middle,
        to_state=terminal,
        conditions={"parallel_done": True},
        order=2,
    )
    parallel = ScenarioActionDefinition.objects.create(
        scenario_version=scenario_version,
        code="parallel-work",
        label="Complete parallel work",
        conditions={"parallel_ready": True, "parallel_done": False},
        effects={"parallel_done": True},
        order=50,
    )
    document = ScenarioDocument.objects.create(
        scenario_version=scenario_version,
        document_type="Invoice",
        title="Fictional Invoice",
        reference="FIC-001",
        learner_data={"Quantity": "10 cartons"},
        evaluator_data={"secret_issue": "quantity_mismatch"},
    )
    return {
        "user": user,
        "enrolment": enrolment,
        "scenario_version": scenario_version,
        "initial": initial,
        "middle": middle,
        "terminal": terminal,
        "first": first,
        "finish": finish,
        "parallel": parallel,
        "document": document,
    }


@pytest.mark.django_db
def test_practical_training_requires_completed_orientation(client, scenario_setup):
    ProgrammeProgress.objects.filter(enrolment=scenario_setup["enrolment"]).update(orientation_completed_at=None)
    client.force_login(scenario_setup["user"])
    assert client.get(reverse("scenario-list")).status_code == 403


@pytest.mark.django_db
def test_starting_again_resumes_same_in_progress_attempt(scenario_setup):
    first_attempt, created = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    resumed_attempt, resumed_created = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    assert created is True
    assert resumed_created is False
    assert resumed_attempt.pk == first_attempt.pk
    assert ScenarioAttempt.objects.count() == 1


@pytest.mark.django_db
def test_valid_transition_records_state_effect_and_append_only_action(scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    updated = perform_action(attempt, scenario_setup["first"])
    assert updated.current_state == scenario_setup["middle"]
    assert updated.state_data["reviewed"] is True
    action = ScenarioAction.objects.get(attempt=updated)
    assert (action.sequence, action.action_code, action.state_before, action.state_after) == (1, "record-review", "review", "process")


@pytest.mark.django_db
def test_invalid_out_of_sequence_action_is_rejected_without_history(scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    with pytest.raises(ValidationError):
        perform_action(attempt, scenario_setup["finish"])
    assert not ScenarioAction.objects.exists()


@pytest.mark.django_db
def test_parallel_action_changes_conditions_without_changing_main_state(scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    assert {action.code for action in available_actions(attempt)} == {"record-review", "parallel-work"}
    updated = perform_action(attempt, scenario_setup["parallel"])
    assert updated.current_state == scenario_setup["initial"]
    assert updated.state_data["parallel_done"] is True
    assert "parallel-work" not in {action.code for action in available_actions(updated)}


@pytest.mark.django_db
def test_terminal_transition_completes_attempt(scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    attempt = perform_action(attempt, scenario_setup["parallel"])
    attempt = perform_action(attempt, scenario_setup["first"])
    attempt = perform_action(attempt, scenario_setup["finish"])
    assert attempt.status == ScenarioAttempt.Status.COMPLETED
    assert attempt.completed_at is not None
    assert [action.sequence for action in attempt.actions.all()] == [1, 2, 3]
    assert available_actions(attempt) == []


@pytest.mark.django_db
def test_beginner_hint_is_recorded_and_competency_hint_is_forbidden(client, scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    client.force_login(scenario_setup["user"])
    assert client.post(reverse("scenario-hint", args=(attempt.pk,))).status_code == 302
    assert AssistanceEvent.objects.filter(attempt=attempt, kind=AssistanceEvent.Kind.HINT).exists()
    attempt.assistance_mode = ScenarioVersion.AssistanceMode.COMPETENCY
    attempt.save(update_fields=("assistance_mode",))
    assert client.post(reverse("scenario-hint", args=(attempt.pk,))).status_code == 403


@pytest.mark.django_db
def test_workspace_shows_learner_document_data_but_not_evaluator_data(client, scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    client.force_login(scenario_setup["user"])
    response = client.get(reverse("scenario-workspace", args=(attempt.pk,)))
    assert response.status_code == 200
    assert b"10 cartons" in response.content
    assert b"quantity_mismatch" not in response.content


@pytest.mark.django_db
def test_student_cannot_open_another_students_attempt(client, scenario_setup):
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], scenario_setup["scenario_version"])
    intruder = User.objects.create_user(username="intruder", email="intruder@example.test", password="test-password")
    client.force_login(intruder)
    assert client.get(reverse("scenario-workspace", args=(attempt.pk,))).status_code == 404


@pytest.mark.django_db
def test_seeded_import_scenario_reaches_gate_out_with_parallel_shipping_work(scenario_setup):
    call_command("seed_demo_scenario", verbosity=0)
    version = ScenarioVersion.objects.get(scenario__code="fictional-guided-import", version=1)
    attempt, _ = start_or_resume_attempt(scenario_setup["enrolment"], version)

    def act(code):
        nonlocal attempt
        definition = version.action_definitions.get(code=code)
        attempt = perform_action(attempt, definition)

    for action_code in (
        "record-document-mismatch",
        "resolve-document-mismatch",
        "create-ucr",
        "create-emda",
        "create-boe",
        "request-shipping-invoice",
        "pay-shipping-invoice",
        "request-shipping-release",
        "submit-boe",
        "accept-assessment",
        "record-tax-payment",
        "complete-field-clearance",
        "gate-out",
    ):
        act(action_code)

    assert attempt.status == ScenarioAttempt.Status.COMPLETED
    assert attempt.current_state.key == "gate-out"
    assert attempt.actions.count() == 13
    assert attempt.state_data["shipping_release_requested"] is True
