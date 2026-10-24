"""Server-side verification for hybrid practical steps.

The browser reports nothing here that the server trusts: a step's conditions
are evaluated against the learner's own saved simulator records and the
durable ``StepEvent`` ledger. Freshness follows the guided-practical engine's
rule — a qualifying record must show activity at or after the moment the
learner opened the step — so unrelated pre-existing records can never satisfy
a new task. Only a passing check writes a ``verified`` event, and the partial
unique constraint makes a second one impossible; the browser merely learns
the result.
"""
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from .models import LessonAttempt, StepEvent, VerificationCondition


def step_conditions(step):
    return list(step.conditions.order_by("order", "id"))


def step_requires_verification(step):
    """A step with no conditions asks for nothing and never blocks progress."""
    return step.conditions.exists()


def opened_at(attempt, step):
    """The freshness bound: when the learner last entered this step."""
    event = StepEvent.objects.filter(attempt=attempt, step=step, kind=StepEvent.Kind.OPENED).first()
    return event.occurred_at if event else attempt.started_at


def record_open(attempt, step):
    """Record (or refresh) the moment the learner entered the step."""
    event, _created = StepEvent.objects.get_or_create(
        attempt=attempt, step=step, kind=StepEvent.Kind.OPENED, defaults={"occurred_at": timezone.now()},
    )
    if not _created:
        StepEvent.objects.filter(pk=event.pk).update(occurred_at=timezone.now())
    return event


def is_verified(attempt, step):
    return StepEvent.objects.filter(attempt=attempt, step=step, kind=StepEvent.Kind.VERIFIED).exists()


def mark_verified(attempt, step):
    """Stamp the checkpoint once; repeats are absorbed by the constraint."""
    event, _created = StepEvent.objects.get_or_create(
        attempt=attempt, step=step, kind=StepEvent.Kind.VERIFIED, defaults={"occurred_at": timezone.now()},
    )
    return event


def _latest_activity(record):
    moments = [
        getattr(record, "updated_at", None),
        getattr(record, "submitted_at", None),
        getattr(record, "created_at", None),
    ]
    moments = [moment for moment in moments if moment is not None]
    return max(moments) if moments else None


def _verify_saved_record(attempt, condition):
    model, model_label = VERIFY_RECORDS[condition.record_kind]
    owner = attempt.enrolment.student
    bound = opened_at(attempt, condition.step)
    owned = model.objects.filter(owner=owner)
    if not owned.exists():
        return False, f"No {model_label} records exist for your account yet. Complete the task in the simulator, then check again."

    expected = condition.expected_fields if isinstance(condition.expected_fields, dict) else {}
    matching = owned.filter(status=condition.required_status, **expected)
    if matching.exists():
        if any((_latest_activity(record) or record.created_at) >= bound for record in matching):
            return True, "Verified."
        return False, (
            f"Your {model_label} records with the required status all predate this step. "
            "Complete the task now, then check again."
        )
    if expected and owned.filter(status=condition.required_status).exists():
        return False, (
            f"Your {model_label} has the required status, but the saved values do not match. "
            "Correct the record, then check again."
        )
    latest = owned.order_by("-created_at").first()
    latest_display = latest.get_status_display() if latest else "unknown"
    choices = dict(model._meta.get_field("status").choices)
    required_display = choices.get(condition.required_status, condition.required_status)
    return False, (
        f"Your latest {model_label} is “{latest_display}” — this step requires “{required_display}”. "
        "Complete the task in the simulator, then check again."
    )


def _verify_screen_opened(attempt, condition):
    if StepEvent.objects.filter(attempt=attempt, step=condition.step, kind=StepEvent.Kind.OPENED).exists():
        return True, "Verified."
    return False, "Open the step's simulator screen first, then check again."


def verify_step(attempt, step):
    """Evaluate every condition; return a JSON-safe result dictionary."""
    results = []
    for condition in step_conditions(step):
        if condition.kind == VerificationCondition.Kind.SAVED_RECORD:
            passed, message = _verify_saved_record(attempt, condition)
        else:
            passed, message = _verify_screen_opened(attempt, condition)
        results.append({"label": condition.describe(), "passed": passed, "message": message})
    passed = bool(results) and all(result["passed"] for result in results)
    if passed:
        mark_verified(attempt, step)
    return {"passed": passed, "results": results}


def satisfied_steps(attempt):
    """Which of the lesson's steps are satisfied (verified or condition-free)."""
    steps = list(attempt.lesson.practical_steps.all())
    verified = set(
        StepEvent.objects.filter(attempt=attempt, kind=StepEvent.Kind.VERIFIED).values_list("step_id", flat=True)
    )
    return {
        step.pk for step in steps
        if step.pk in verified or not step_requires_verification(step)
    }


def refresh_completion(attempt):
    """Write lesson completion when theory is acknowledged and all steps are
    satisfied; returns True when the attempt is (or just became) complete."""
    if attempt.completed_at:
        return True
    if attempt.theory_acknowledged_at is None:
        return False
    if satisfied_steps(attempt) != {step.pk for step in attempt.lesson.practical_steps.all()}:
        return False
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=("completed_at",))
    return True


def attempt_snapshot(attempt):
    """The JSON the workspace embeds so the browser can resume exactly where
    the server says the learner stands."""
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    satisfied = satisfied_steps(attempt)
    current_index = 0
    if attempt.current_step and attempt.current_step in steps:
        current_index = steps.index(attempt.current_step)
    return {
        "id": str(attempt.pk),
        "current_index": current_index,
        "satisfied": [steps.index(step) for step in steps if step.pk in satisfied],
        "theory_acknowledged": attempt.theory_acknowledged_at is not None,
        "lesson_complete": attempt.completed_at is not None,
        "requires": {
            str(step.pk): [
                {"kind": condition.kind, "label": condition.describe()}
                for condition in step_conditions(step)
            ]
            for step in steps
        },
    }


def attempt_for(request_user, attempt_id):
    """The user's own attempt, or None — never another learner's."""
    return LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request_user).first()
