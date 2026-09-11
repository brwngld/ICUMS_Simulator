import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from assessments.models import Assessment, TheoryAttempt
from audit.models import AuditEvent
from evaluations.models import PracticalEvaluation
from progress.models import ProgrammeProgress
from scenarios.models import ScenarioVersion

from .models import Certificate, CompletionPolicy, CompletionRecord


def _qualifying_theory_attempt(enrolment):
    return (
        TheoryAttempt.objects.filter(
            enrolment=enrolment,
            assessment__assessment_type=Assessment.Type.FINAL_THEORY,
            status=TheoryAttempt.Status.SUBMITTED,
            outcome=TheoryAttempt.Outcome.PASS,
        )
        .order_by("-submitted_at")
        .first()
    )


def _certificate_number(completion_record):
    year = (completion_record.completed_at or timezone.now()).year
    token = uuid.uuid4().hex[:10].upper()
    return f"ICUMS-TRAIN-{year}-{token}"


def issue_certificate(completion_record):
    if completion_record.status != CompletionRecord.Status.COMPLETED:
        raise ValidationError("A certificate can only be issued for a completed training record.")
    certificate, _ = Certificate.objects.get_or_create(
        completion_record=completion_record,
        defaults={
            "certificate_number": _certificate_number(completion_record),
            "template_version": completion_record.policy_snapshot["certificate_template_version"],
        },
    )
    return certificate


@transaction.atomic
def process_completion_for_evaluation(evaluation):
    enrolment = evaluation.attempt.enrolment
    if evaluation.effective_outcome != PracticalEvaluation.Outcome.PASS:
        return None
    if evaluation.attempt.scenario_version.purpose != ScenarioVersion.Purpose.COMPETENCY:
        return None
    theory_attempt = _qualifying_theory_attempt(enrolment)
    progress = ProgrammeProgress.objects.filter(enrolment=enrolment, orientation_completed_at__isnull=False).first()
    if theory_attempt is None or progress is None:
        return None
    try:
        policy = enrolment.programme_version.completion_policy
    except CompletionPolicy.DoesNotExist:
        return None
    if not policy.is_active:
        return None
    existing = CompletionRecord.objects.filter(enrolment=enrolment).first()
    if existing:
        return existing
    now = timezone.now()
    status = CompletionRecord.Status.PENDING_APPROVAL if policy.requires_instructor_approval else CompletionRecord.Status.COMPLETED
    completion = CompletionRecord.objects.create(
        enrolment=enrolment,
        qualifying_evaluation=evaluation,
        status=status,
        evidence_snapshot={
            "final_theory_attempt_id": str(theory_attempt.pk),
            "final_theory_percentage": str(theory_attempt.percentage),
            "practical_evaluation_id": str(evaluation.pk),
            "practical_system_percentage": str(evaluation.system_percentage),
            "practical_effective_outcome": evaluation.effective_outcome,
        },
        policy_snapshot={
            "requires_instructor_approval": policy.requires_instructor_approval,
            "certificate_template_version": policy.certificate_template_version,
        },
        completed_at=now if status == CompletionRecord.Status.COMPLETED else None,
    )
    if completion.status == CompletionRecord.Status.COMPLETED:
        issue_certificate(completion)
    return completion


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@transaction.atomic
def approve_completion(completion, instructor, ip_address=None):
    _require_instructor(instructor)
    if completion.status == CompletionRecord.Status.COMPLETED:
        return completion
    now = timezone.now()
    completion.status = CompletionRecord.Status.COMPLETED
    completion.completed_at = now
    completion.approved_by = instructor
    completion.approved_at = now
    completion.save(update_fields=("status", "completed_at", "approved_by", "approved_at"))
    issue_certificate(completion)
    AuditEvent.objects.create(
        actor=instructor,
        action_code="completion.approved",
        target_type="completion_record",
        target_id=str(completion.pk),
        summary="Training completion approved and certificate issued.",
        ip_address=ip_address,
    )
    return completion
