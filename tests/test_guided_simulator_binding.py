"""Phase 1 guided-practice ↔ simulator integration tests.

Covers: step bindings (storage, registry validation, authoring), the
workspace link-out and explicit "Check my work" verification (pass, fail,
ownership, pre-existing-record exclusion), the safe simulator ?next
redirect, and MDA request ownership.
"""

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import SimulatorCredential, User, allocate_student_id
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import ProgrammeProgress
from scenarios.bindings import SIMULATOR_BINDING_ROUTES, validate_binding
from scenarios.models import (
    BoeDeclaration,
    ConsignmentApplication,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    MdaStatus,
    Scenario,
    ScenarioAttempt,
    ScenarioState,
    ScenarioVersion,
    UcrDeclaration,
)
from scenarios.services import start_or_resume_attempt
from scenarios.verification import STEP_OPEN_PREFIX, record_step_open, step_opened_at, verify_step


UCR_BINDING = {
    "route": "single-window-create-ucr",
    "task": "Submit a UCR declaration in the simulator",
    "verify": {"record": "ucr", "status": "submitted"},
}


def login_with_simulator_access(client, user):
    if not user.student_id:
        user.student_id = allocate_student_id(user.first_name or user.username)
        user.save(update_fields=("student_id",))
    credential, _ = SimulatorCredential.objects.get_or_create(user=user)
    credential.issue()
    client.force_login(user)
    session = client.session
    session["simulator_user_id"] = str(user.pk)
    session.save()
    return credential


@pytest.fixture
def guided(db):
    """A student with practical access and an in-progress attempt whose
    current (initial) state carries a UCR binding."""
    user = User.objects.create_user(username="guided-student", email="guided@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    programme = Programme.objects.create(name="Guided Programme", code="guided-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    disclaimer = DisclaimerVersion.objects.create(version=21, title="Training notice", body="Not official ICUMS.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    ProgrammeProgress.objects.create(
        enrolment=enrolment,
        theory_completed_at=timezone.now(),
        orientation_unlocked_at=timezone.now(),
        orientation_completed_at=timezone.now(),
    )
    scenario = Scenario.objects.create(code="guided-binding", title="Guided Binding", area=Scenario.Area.IMPORT)
    scenario_version = ScenarioVersion.objects.create(
        scenario=scenario,
        version=1,
        status=ScenarioVersion.Status.PUBLISHED,
        assistance_mode=ScenarioVersion.AssistanceMode.BEGINNER,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        briefing="Fictional scenario.",
        learning_objective="Bind a step to the simulator.",
    )
    ScenarioState.objects.create(
        scenario_version=scenario_version, key="declare", label="Declare", order=1, is_initial=True,
        binding=dict(UCR_BINDING),
    )
    terminal = ScenarioState.objects.create(scenario_version=scenario_version, key="done", label="Done", order=2, is_terminal=True)
    attempt, _created = start_or_resume_attempt(enrolment, scenario_version)
    return type("Guided", (), {"user": user, "enrolment": enrolment, "version": scenario_version, "attempt": attempt, "terminal": terminal})()


def _submitted_ucr(owner, temp_no):
    return UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="Guided goods", origin_country="CN",
        destination_country="GH", transport_mode="10, Sea Transport", temp_no=temp_no,
        status=UcrDeclaration.Status.SUBMITTED,
    )


# --- binding validation ----------------------------------------------------


@pytest.mark.django_db
def test_binding_validation_rejects_unknown_routes():
    with pytest.raises(ValidationError):
        validate_binding({"route": "https://example.test/evil", "task": "x"})


@pytest.mark.django_db
def test_binding_validation_requires_task_and_known_status():
    with pytest.raises(ValidationError):
        validate_binding({"route": "simulator-portal", "task": ""})
    with pytest.raises(ValidationError):
        validate_binding({"route": "simulator-portal", "task": "t", "verify": {"record": "ucr", "status": "nonsense"}})


@pytest.mark.django_db
def test_binding_validation_normalises_a_valid_binding():
    normalised = validate_binding({"route": "simulator-portal", "task": " Explore the portal "})
    assert normalised == {"route": "simulator-portal", "task": "Explore the portal"}


# --- workspace rendering ---------------------------------------------------


@pytest.mark.django_db
def test_workspace_shows_task_and_both_buttons_for_bound_step(client, guided):
    login_with_simulator_access(client, guided.user)
    response = client.get(reverse("scenario-workspace", args=[guided.attempt.pk]))
    assert response.status_code == 200
    body = response.content.decode()
    assert "Simulator task:" in body
    assert guided.attempt.current_state.binding["task"] in body
    assert "Open simulator step" in body
    assert "Check my work" in body


@pytest.mark.django_db
def test_workspace_hides_buttons_for_unbound_step(client, guided):
    guided.attempt.current_state.binding = {}
    guided.attempt.current_state.save(update_fields=("binding",))
    login_with_simulator_access(client, guided.user)
    response = client.get(reverse("scenario-workspace", args=[guided.attempt.pk]))
    body = response.content.decode()
    assert "Open simulator step" not in body
    assert "Check my work" not in body


# --- open step -------------------------------------------------------------


@pytest.mark.django_db
def test_open_step_records_timestamp_and_redirects_to_registry_route(client, guided):
    login_with_simulator_access(client, guided.user)
    response = client.post(reverse("scenario-open-step", args=[guided.attempt.pk]))
    assert response.status_code == 302
    assert response.url == reverse(UCR_BINDING["route"])
    attempt = ScenarioAttempt.objects.get(pk=guided.attempt.pk)
    assert step_opened_at(attempt, attempt.current_state) is not None
    assert f"{STEP_OPEN_PREFIX}{attempt.current_state.key}" in attempt.state_data


@pytest.mark.django_db
def test_open_step_is_post_only_and_owner_scoped(client, guided, db):
    login_with_simulator_access(client, guided.user)
    assert client.get(reverse("scenario-open-step", args=[guided.attempt.pk])).status_code == 405
    stranger = User.objects.create_user(username="guided-stranger", password="x")
    login_with_simulator_access(client, stranger)
    assert client.post(reverse("scenario-open-step", args=[guided.attempt.pk])).status_code == 404


# --- check my work ---------------------------------------------------------


@pytest.mark.django_db
def test_check_passes_for_fresh_submitted_record(client, guided):
    login_with_simulator_access(client, guided.user)
    client.post(reverse("scenario-open-step", args=[guided.attempt.pk]))
    _submitted_ucr(guided.user, "TEMPUCR2699000001")
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("Simulator task verified" in m for m in messages)


@pytest.mark.django_db
def test_check_fails_when_no_records_exist(client, guided):
    login_with_simulator_access(client, guided.user)
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("No UCR declaration records exist" in m for m in messages)


@pytest.mark.django_db
def test_check_fails_while_record_is_only_a_draft(client, guided):
    login_with_simulator_access(client, guided.user)
    UcrDeclaration.objects.create(
        owner=guided.user, regime="IM", goods_description="Draft goods", origin_country="CN",
        destination_country="GH", transport_mode="10, Sea Transport", temp_no="TEMPUCR2699000002",
    )
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("requires" in m and "Submitted" in m for m in messages)


@pytest.mark.django_db
def test_check_excludes_records_that_predate_the_task(client, guided):
    login_with_simulator_access(client, guided.user)
    # Record submitted BEFORE the student opens the step...
    _submitted_ucr(guided.user, "TEMPUCR2699000003")
    client.post(reverse("scenario-open-step", args=[guided.attempt.pk]))
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("predate this task" in m for m in messages)
    # ...and one created after the step was opened satisfies it.
    _submitted_ucr(guided.user, "TEMPUCR2699000004")
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("Simulator task verified" in m for m in messages)


@pytest.mark.django_db
def test_check_ignores_other_students_records(client, guided):
    login_with_simulator_access(client, guided.user)
    client.post(reverse("scenario-open-step", args=[guided.attempt.pk]))
    stranger = User.objects.create_user(username="guided-rival", password="x")
    _submitted_ucr(stranger, "TEMPUCR2699000005")
    response = client.post(reverse("scenario-check-step", args=[guided.attempt.pk]), follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert not any("Simulator task verified" in m for m in messages)


@pytest.mark.django_db
def test_check_does_not_advance_the_state_machine(client, guided):
    login_with_simulator_access(client, guided.user)
    client.post(reverse("scenario-open-step", args=[guided.attempt.pk]))
    _submitted_ucr(guided.user, "TEMPUCR2699000006")
    client.post(reverse("scenario-check-step", args=[guided.attempt.pk]))
    attempt = ScenarioAttempt.objects.get(pk=guided.attempt.pk)
    assert attempt.status == ScenarioAttempt.Status.IN_PROGRESS
    assert attempt.current_state.key == "declare"


# --- other record kinds ----------------------------------------------------


@pytest.mark.django_db
def test_verification_covers_consignment_boe_and_mda_records(guided):
    state = guided.attempt.current_state

    state.binding = {"route": "single-window-search-consignment-application", "task": "t",
                     "verify": {"record": "consignment", "status": "submitted"}}
    state.save(update_fields=("binding",))
    record_step_open(guided.attempt, state)
    ucr = _submitted_ucr(guided.user, "TEMPUCR2699000010")
    ConsignmentApplication.objects.create(owner=guided.user, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED)
    assert verify_step(guided.attempt, state).passed

    agency = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "MOTI"})[0]
    application = MdaApplication.objects.get_or_create(mda=agency, code="IDF", defaults={"name": "IDF"})[0]
    process = MdaProcess.objects.get_or_create(application=application, code="NEW", defaults={"name": "New"})[0]

    state.binding = {"route": "search-boe-declaration", "task": "t",
                     "verify": {"record": "boe", "status": "submitted"}}
    state.save(update_fields=("binding",))
    record_step_open(guided.attempt, state)
    consignment = ConsignmentApplication.objects.create(
        owner=guided.user, ucr=_submitted_ucr(guided.user, "TEMPUCR2699000011"),
        status=ConsignmentApplication.Status.DRAFT,
    )
    idf = MdaConsignmentRequest.objects.create(
        consignment_application=consignment, owner=guided.user, mda=agency, application=application,
        process=process, consignment_type="SG", application_no="CD202610MOTIIDF0000999",
        status=MdaStatus.APPROVED,
    )
    BoeDeclaration.objects.create(
        owner=guided.user, idf=idf, ucr=idf.consignment_application.ucr, job_no="2610100001GCH000001",
        status=BoeDeclaration.Status.SUBMITTED,
    )
    assert verify_step(guided.attempt, state).passed

    state.binding = {"route": "single-window-search-consignment-application", "task": "t",
                     "verify": {"record": "mda", "status": MdaStatus.SUBMITTED}}
    state.save(update_fields=("binding",))
    record_step_open(guided.attempt, state)
    idf.status = MdaStatus.SUBMITTED
    idf.save(update_fields=("status", "updated_at"))
    assert verify_step(guided.attempt, state).passed


@pytest.mark.django_db
def test_misconfigured_or_missing_verification_reports_clearly(guided):
    state = guided.attempt.current_state
    state.binding = {"route": "simulator-portal", "task": "t"}
    state.save(update_fields=("binding",))
    result = verify_step(guided.attempt, state)
    assert not result.passed
    assert "no verification configured" in result.message


# --- safe simulator ?next redirect ----------------------------------------


@pytest.mark.django_db
def test_gate_stashes_destination_and_login_returns_to_it(client, guided):
    client.force_login(guided.user)  # Django-authenticated but no simulator session yet
    target = reverse("clearance-workspace")
    response = client.get(target)
    assert response.status_code == 302
    assert response.url.startswith(reverse("simulator-portal"))
    assert client.session.get("simulator_login_next") == target

    credential, _ = SimulatorCredential.objects.get_or_create(user=guided.user)
    raw_password = credential.issue()  # also allocates the student ID
    response = client.post(reverse("simulator-login"), {"student_id": guided.user.student_id, "password": raw_password})
    assert response.status_code == 302
    assert response.url == target
    assert "simulator_login_next" not in client.session


@pytest.mark.django_db
def test_unsafe_next_destinations_are_ignored(client, guided, db):
    client.force_login(guided.user)
    credential, _ = SimulatorCredential.objects.get_or_create(user=guided.user)
    raw_password = credential.issue()
    for unsafe in ("https://example.test/evil", "//example.test/evil", "/admin/", "practical/portal/"):
        session = client.session
        session["simulator_login_next"] = unsafe
        session.save()
        response = client.post(reverse("simulator-login"), {"student_id": guided.user.student_id, "password": raw_password})
        assert response.status_code == 302
        assert response.url == reverse("simulator-portal")


# --- authoring -------------------------------------------------------------


def _draft_course_payload(state):
    return {
        "briefing": "Fictional briefing.",
        "learning_objective": "Learn the flow.",
        "assistance_mode": "beginner",
        "maximum_attempts": "3",
        "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
        "form-0-id": str(state.pk),
    }


def _attach_to_draft_course(guided, code):
    programme_version = ProgrammeVersion.objects.create(
        programme=Programme.objects.create(name=f"Draft Course {code}", code=f"draft-course-{code}"),
        version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    from learning.models import Module
    module = Module.objects.create(programme_version=programme_version, code=f"draft-module-{code}", title="Draft Module", order=1)
    guided.version.status = ScenarioVersion.Status.DRAFT
    guided.version.module = module
    guided.version.save(update_fields=("status", "module"))


@pytest.mark.django_db
def test_practical_edit_saves_a_binding(client, guided, db):
    instructor = User.objects.create_user(username="binding-instructor", email="i@example.test", password="x")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    _attach_to_draft_course(guided, "one")
    client.force_login(instructor)

    state = guided.version.states.get(key="declare")
    payload = _draft_course_payload(state)
    payload.update({
        "form-0-label": "Declare",
        "form-0-guidance": "Guidance text.",
        "form-0-binding_route": "simulator-portal",
        "form-0-binding_task": "Explore the simulator portal",
        "form-0-binding_verify": "ucr:submitted",
    })
    response = client.post(reverse("practical-edit", args=[guided.version.pk]), payload)
    assert response.status_code == 302
    state.refresh_from_db()
    assert state.binding == {"route": "simulator-portal", "task": "Explore the simulator portal",
                             "verify": {"record": "ucr", "status": "submitted"}}


@pytest.mark.django_db
def test_practical_edit_rejects_unapproved_routes(client, guided, db):
    instructor = User.objects.create_user(username="binding-instructor-2", email="i2@example.test", password="x")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    _attach_to_draft_course(guided, "two")
    client.force_login(instructor)

    state = guided.version.states.get(key="declare")
    payload = _draft_course_payload(state)
    payload.update({
        "form-0-label": "Declare",
        "form-0-guidance": "Guidance text.",
        "form-0-binding_route": "not-a-real-route",
        "form-0-binding_task": "Broken",
        "form-0-binding_verify": "ucr:submitted",
    })
    response = client.post(reverse("practical-edit", args=[guided.version.pk]), payload)
    assert response.status_code == 200  # form re-renders with errors
    state.refresh_from_db()
    assert state.binding == UCR_BINDING  # unchanged


# --- MDA ownership ---------------------------------------------------------


@pytest.mark.django_db
def test_mda_records_are_owner_scoped_after_migration(guided):
    stranger = User.objects.create_user(username="mda-stranger", password="x")
    agency = MdaAgency.objects.get_or_create(code="MOTI", defaults={"name": "MOTI"})[0]
    application = MdaApplication.objects.get_or_create(mda=agency, code="IDF", defaults={"name": "IDF"})[0]
    process = MdaProcess.objects.get_or_create(application=application, code="NEW", defaults={"name": "New"})[0]
    own_consignment = ConsignmentApplication.objects.create(
        owner=guided.user, ucr=_submitted_ucr(guided.user, "TEMPUCR2699000020"), status=ConsignmentApplication.Status.DRAFT)
    record = MdaConsignmentRequest.objects.create(
        consignment_application=own_consignment, owner=guided.user, mda=agency, application=application,
        process=process, consignment_type="SG", application_no="CD202610MOTIIDF0001020")
    assert MdaConsignmentRequest.objects.filter(owner=guided.user).count() == 1
    assert not MdaConsignmentRequest.objects.filter(owner=stranger).exists()
    assert record.owner == record.consignment_application.owner
