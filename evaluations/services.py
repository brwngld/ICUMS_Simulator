from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from scenarios.models import ScenarioAttempt

from .models import CriterionResult, EvaluationRevision, InstructorFeedback, PracticalEvaluation, RemediationRecommendation, RubricVersion


def _evaluate_rule(criterion, attempt, action_codes, assistance_count):
    rule = criterion.evaluation_rule
    rule_type = rule.get("type")
    maximum = criterion.maximum_points
    if rule_type == "completion":
        passed = attempt.status == ScenarioAttempt.Status.COMPLETED
        return (maximum if passed else 0, passed, {"completed": passed})
    if rule_type == "required_actions":
        required = list(rule.get("action_codes", []))
        found = [code for code in required if code in action_codes]
        passed = bool(required) and len(found) == len(required)
        points = round(maximum * len(found) / len(required)) if required else 0
        return (points, passed, {"required": required, "found": found, "missing": [code for code in required if code not in found]})
    if rule_type == "state_flags":
        expected = rule.get("equals", {})
        matched = {key: attempt.state_data.get(key) == value for key, value in expected.items()}
        passed = bool(expected) and all(matched.values())
        return (maximum if passed else 0, passed, {"expected": expected, "matched": matched})
    if rule_type == "assistance_limit":
        allowed = int(rule.get("maximum_events", 0))
        passed = assistance_count <= allowed
        deduction = int(rule.get("deduction_per_extra", maximum))
        points = max(0, maximum - max(0, assistance_count - allowed) * deduction)
        return (points, passed, {"assistance_events": assistance_count, "maximum_events": allowed})
    raise ValidationError(f"Unsupported rubric rule type: {rule_type}")


@transaction.atomic
def evaluate_attempt(attempt):
    if attempt.status != ScenarioAttempt.Status.COMPLETED:
        raise ValidationError("Only completed attempts can be evaluated.")
    existing = PracticalEvaluation.objects.filter(attempt=attempt).first()
    if existing:
        return existing
    try:
        rubric_version = attempt.scenario_version.rubric_version
    except RubricVersion.DoesNotExist:
        return None
    if rubric_version.status != RubricVersion.Status.PUBLISHED:
        return None
    action_codes = list(attempt.actions.order_by("sequence").values_list("action_code", flat=True))
    assistance_count = attempt.assistance_events.count()
    elapsed_seconds = max(0, int(((attempt.completed_at or timezone.now()) - attempt.started_at).total_seconds()))
    evaluation = PracticalEvaluation.objects.create(
        attempt=attempt,
        rubric_version=rubric_version,
        system_outcome=PracticalEvaluation.Outcome.FAIL,
        elapsed_seconds=elapsed_seconds,
    )
    total = 0
    maximum = 0
    mandatory_failure = False
    for criterion in rubric_version.criteria.all():
        points, passed, evidence = _evaluate_rule(criterion, attempt, action_codes, assistance_count)
        result = CriterionResult.objects.create(
            evaluation=evaluation,
            criterion=criterion,
            awarded_points=points,
            passed=passed,
            evidence=evidence,
            feedback="Criterion met." if passed else "Criterion needs further work.",
        )
        total += points
        maximum += criterion.maximum_points
        mandatory_failure = mandatory_failure or (criterion.mandatory and not passed)
        if not passed and (criterion.remediation_resource_id or criterion.remediation_scenario_id):
            RemediationRecommendation.objects.create(
                evaluation=evaluation,
                criterion_result=result,
                resource=criterion.remediation_resource,
                scenario_version=criterion.remediation_scenario,
                reason=f"Review and practise: {criterion.title}.",
            )
    percentage = (Decimal(total) / Decimal(maximum) * 100).quantize(Decimal("0.01")) if maximum else Decimal("0.00")
    evaluation.system_score = total
    evaluation.maximum_score = maximum
    evaluation.system_percentage = percentage
    evaluation.system_outcome = PracticalEvaluation.Outcome.PASS if percentage >= rubric_version.pass_percentage and not mandatory_failure else PracticalEvaluation.Outcome.FAIL
    evaluation.save(update_fields=("system_score", "maximum_score", "system_percentage", "system_outcome"))
    return evaluation


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@transaction.atomic
def revise_outcome(evaluation, instructor, revised_outcome, reason, ip_address=None):
    _require_instructor(instructor)
    reason = reason.strip()
    if revised_outcome not in PracticalEvaluation.Outcome.values:
        raise ValidationError("Choose a valid revised outcome.")
    if len(reason) < 10:
        raise ValidationError("Provide a meaningful reason of at least 10 characters.")
    revision = EvaluationRevision.objects.create(
        evaluation=evaluation,
        instructor=instructor,
        original_outcome=evaluation.effective_outcome,
        revised_outcome=revised_outcome,
        reason=reason,
    )
    AuditEvent.objects.create(
        actor=instructor,
        action_code="practical_evaluation.revised",
        target_type="practical_evaluation",
        target_id=str(evaluation.pk),
        summary=f"Practical outcome revised from {revision.original_outcome} to {revision.revised_outcome}.",
        metadata={"reason": reason},
        ip_address=ip_address,
    )
    return revision


@transaction.atomic
def add_feedback(attempt, instructor, body, visible_to_student=True):
    _require_instructor(instructor)
    body = body.strip()
    if len(body) < 3:
        raise ValidationError("Feedback is too short.")
    return InstructorFeedback.objects.create(attempt=attempt, instructor=instructor, body=body, visible_to_student=visible_to_student)
