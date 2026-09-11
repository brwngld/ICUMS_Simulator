import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assessments.models import Assessment, TheoryAttempt
from audit.models import AuditEvent
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from progress.models import ProgrammeProgress
from reports.models import Certificate, CompletionPolicy, CompletionRecord
from reports.services import approve_completion, issue_certificate
from scenarios.models import ScenarioVersion
from scenarios.services import perform_action, start_or_resume_attempt


@pytest.fixture
def completion_setup(db):
    user = User.objects.create_user(username="completion-student", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    programme = Programme.objects.create(name="Completion Programme", code="completion-programme")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    enrolment = Enrolment.objects.create(student=user, programme_version=version)
    disclaimer = DisclaimerVersion.objects.create(version=91, title="Notice", body="Training only.", is_current=True)
    DisclaimerAcceptance.objects.create(user=user, disclaimer=disclaimer)
    ProgrammeProgress.objects.create(enrolment=enrolment, theory_completed_at=timezone.now(), orientation_unlocked_at=timezone.now(), orientation_completed_at=timezone.now())
    return {"user": user, "enrolment": enrolment}


def add_passed_final_theory(enrolment):
    assessment = Assessment.objects.create(
        programme_version=enrolment.programme_version,
        title="Final theory for completion test",
        assessment_type=Assessment.Type.FINAL_THEORY,
        pass_percentage=70,
        is_published=True,
    )
    return TheoryAttempt.objects.create(
        enrolment=enrolment,
        assessment=assessment,
        attempt_number=1,
        status=TheoryAttempt.Status.SUBMITTED,
        submitted_at=timezone.now(),
        score=10,
        maximum_score=10,
        percentage=100,
        outcome=TheoryAttempt.Outcome.PASS,
    )


def complete_seeded_competency(enrolment):
    call_command("seed_demo_scenario", verbosity=0)
    version = ScenarioVersion.objects.get(scenario__code="fictional-import-competency", version=1)
    attempt, _ = start_or_resume_attempt(enrolment, version)
    for code in (
        "identify-competency-discrepancy",
        "complete-competency-processing",
        "request-competency-shipping-invoice",
        "pay-competency-shipping-invoice",
        "request-competency-shipping-release",
        "complete-competency-clearance",
    ):
        attempt = perform_action(attempt, version.action_definitions.get(code=code))
    return attempt


@pytest.mark.django_db
def test_qualifying_competency_automatically_issues_certificate(client, completion_setup):
    enrolment = completion_setup["enrolment"]
    add_passed_final_theory(enrolment)
    CompletionPolicy.objects.create(programme_version=enrolment.programme_version)
    attempt = complete_seeded_competency(enrolment)

    completion = CompletionRecord.objects.get(enrolment=enrolment)
    assert completion.status == CompletionRecord.Status.COMPLETED
    assert completion.qualifying_evaluation == attempt.evaluation
    assert completion.evidence_snapshot["final_theory_percentage"] == "100.00"
    certificate = completion.certificate
    assert certificate.status == Certificate.Status.ISSUED
    assert issue_certificate(completion).pk == certificate.pk

    client.force_login(completion_setup["user"])
    response = client.get(reverse("certificate-detail", args=(certificate.pk,)))
    assert response.status_code == 200
    assert b"TRAINING SIMULATOR" in response.content
    assert b"not a government-issued professional qualification" in response.content


@pytest.mark.django_db
def test_practice_scenario_does_not_create_completion(completion_setup):
    enrolment = completion_setup["enrolment"]
    add_passed_final_theory(enrolment)
    CompletionPolicy.objects.create(programme_version=enrolment.programme_version)
    call_command("seed_demo_scenario", verbosity=0)
    version = ScenarioVersion.objects.get(scenario__code="fictional-guided-import", version=1)
    attempt, _ = start_or_resume_attempt(enrolment, version)
    for code in (
        "record-document-mismatch", "resolve-document-mismatch", "create-ucr", "create-emda", "create-boe",
        "request-shipping-invoice", "pay-shipping-invoice", "request-shipping-release", "submit-boe",
        "accept-assessment", "record-tax-payment", "complete-field-clearance", "gate-out",
    ):
        attempt = perform_action(attempt, version.action_definitions.get(code=code))
    assert attempt.evaluation.effective_outcome == "pass"
    assert not CompletionRecord.objects.filter(enrolment=enrolment).exists()


@pytest.mark.django_db
def test_approval_policy_waits_for_instructor(completion_setup):
    enrolment = completion_setup["enrolment"]
    add_passed_final_theory(enrolment)
    CompletionPolicy.objects.create(programme_version=enrolment.programme_version, requires_instructor_approval=True)
    complete_seeded_competency(enrolment)
    completion = CompletionRecord.objects.get(enrolment=enrolment)
    assert completion.status == CompletionRecord.Status.PENDING_APPROVAL
    assert not Certificate.objects.exists()

    instructor = User.objects.create_user(username="completion-reviewer", email="completion-reviewer@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    approve_completion(completion, instructor)
    completion.refresh_from_db()
    assert completion.status == CompletionRecord.Status.COMPLETED
    assert completion.approved_by == instructor
    assert Certificate.objects.filter(completion_record=completion).exists()
    assert AuditEvent.objects.filter(actor=instructor, action_code="completion.approved").exists()
