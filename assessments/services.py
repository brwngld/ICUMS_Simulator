from decimal import Decimal
import random

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from progress.models import ModuleProgress, ProgrammeProgress

from .models import TheoryAttempt, TheoryAttemptItem, TheoryResponse


@transaction.atomic
def get_or_start_attempt(enrolment, assessment):
    existing = assessment.attempts.filter(enrolment=enrolment, status=TheoryAttempt.Status.IN_PROGRESS).first()
    if existing:
        return existing
    previous_number = assessment.attempts.filter(enrolment=enrolment).aggregate(value=Max("attempt_number"))["value"] or 0
    if assessment.maximum_attempts is not None and previous_number >= assessment.maximum_attempts:
        raise PermissionDenied("No further attempts are available for this assessment.")
    attempt = TheoryAttempt.objects.create(enrolment=enrolment, assessment=assessment, attempt_number=previous_number + 1)
    question_versions = [item.question_version for item in assessment.items.select_related("question_version")]
    if assessment.randomize_questions:
        random.shuffle(question_versions)
    TheoryAttemptItem.objects.bulk_create(
        TheoryAttemptItem(attempt=attempt, question_version=question, order=index)
        for index, question in enumerate(question_versions, start=1)
    )
    return attempt


@transaction.atomic
def submit_attempt(attempt, answers):
    if attempt.status != TheoryAttempt.Status.IN_PROGRESS:
        raise ValueError("Only an in-progress attempt can be submitted.")
    assessment = attempt.assessment
    score = 0
    maximum = 0
    for item in attempt.items.select_related("question_version").prefetch_related("question_version__options"):
        question = item.question_version
        maximum += question.points
        selected = question.options.filter(pk=answers.get(str(question.pk))).first()
        correct = bool(selected and selected.is_correct)
        awarded = question.points if correct else 0
        score += awarded
        TheoryResponse.objects.create(
            attempt=attempt,
            question_version=question,
            selected_option=selected,
            is_correct=correct,
            awarded_score=awarded,
        )
    percentage = (Decimal(score) / Decimal(maximum) * 100).quantize(Decimal("0.01")) if maximum else Decimal("0.00")
    attempt.status = TheoryAttempt.Status.SUBMITTED
    attempt.submitted_at = timezone.now()
    attempt.duration_seconds = max(0, int((attempt.submitted_at - attempt.started_at).total_seconds()))
    attempt.score = score
    attempt.maximum_score = maximum
    attempt.percentage = percentage
    attempt.outcome = TheoryAttempt.Outcome.PASS if percentage >= assessment.pass_percentage else TheoryAttempt.Outcome.FAIL
    attempt.save()
    if attempt.outcome == TheoryAttempt.Outcome.PASS and assessment.module_id:
        ModuleProgress.objects.update_or_create(
            enrolment=attempt.enrolment,
            module=assessment.module,
            defaults={"status": ModuleProgress.Status.COMPLETED, "completed_at": attempt.submitted_at},
        )
    if attempt.outcome == TheoryAttempt.Outcome.PASS and assessment.assessment_type == assessment.Type.FINAL_THEORY:
        ProgrammeProgress.objects.update_or_create(
            enrolment=attempt.enrolment,
            defaults={"theory_completed_at": attempt.submitted_at, "orientation_unlocked_at": attempt.submitted_at},
        )
    return attempt
