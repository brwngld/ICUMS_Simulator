"""Server-side verification of guided-practice simulator tasks.

Phase 1 (E1 decision): a guided step may point at an approved simulator
route; the student performs the task in a separate tab, returns, and asks
for an explicit "Check my work". Verification is action-level — the
required record must exist, belong to this student, carry the required
workflow status, and show activity at or after the moment the student
opened the step (falling back to the attempt start), so unrelated
pre-existing records cannot satisfy a new task.

Verification reports pass/fail and feedback; it never advances the state
machine — progression remains governed by the scenario's own actions.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .bindings import VERIFY_RECORDS
from .models import ScenarioAttempt

#: Reserved ``state_data`` namespace for step-open timestamps. Authored
#: conditions/effects use bare keys (e.g. ``step_1_completed``), so a
#: leading underscore keeps bookkeeping keys out of the engine's equality
#: checks by convention.
STEP_OPEN_PREFIX = "_sim_open."


@dataclass
class VerifyResult:
    passed: bool
    message: str


def record_step_open(attempt, state):
    """Store the moment the student opened this step's simulator page."""
    key = f"{STEP_OPEN_PREFIX}{state.key}"
    with transaction.atomic():
        locked = ScenarioAttempt.objects.select_for_update().get(pk=attempt.pk)
        locked.state_data[key] = timezone.now().isoformat()
        locked.save(update_fields=("state_data", "last_saved_at"))
        attempt.state_data = dict(locked.state_data)


def step_opened_at(attempt, state):
    raw = (attempt.state_data or {}).get(f"{STEP_OPEN_PREFIX}{state.key}")
    if not raw:
        return None
    try:
        return timezone.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _latest_activity(record):
    moments = [
        getattr(record, "updated_at", None),
        getattr(record, "submitted_at", None),
        getattr(record, "created_at", None),
    ]
    moments = [moment for moment in moments if moment is not None]
    return max(moments) if moments else None


def verify_step(attempt, state):
    """Verify the current step's simulator task for this attempt."""
    binding = state.binding if isinstance(state.binding, dict) else {}
    spec = binding.get("verify") or {}
    task = str(binding.get("task") or "").strip()
    if not spec:
        return VerifyResult(False, "This step has no verification configured yet. Ask your instructor if the task is complete.")
    record_kind = spec.get("record")
    if record_kind not in VERIFY_RECORDS:
        return VerifyResult(False, "This step's verification is misconfigured. Ask your instructor to repair it.")
    model, record_label = VERIFY_RECORDS[record_kind]
    required_status = spec.get("status")
    required_display = dict(model._meta.get_field("status").choices).get(required_status, required_status)

    owner = attempt.enrolment.student
    bound = step_opened_at(attempt, state) or attempt.started_at
    owned = model.objects.filter(owner=owner)
    if not owned.exists():
        return VerifyResult(False, f"No {record_label} records exist for your account yet. Complete the task in the simulator, then check again.")

    matching = owned.filter(status=required_status)
    if matching.exists():
        fresh = [record for record in matching if (_latest_activity(record) or record.created_at) >= bound]
        if fresh:
            summary = f"Simulator task verified: {task}." if task else f"Simulator task verified: {record_label} at {required_display}."
            return VerifyResult(True, summary)
        return VerifyResult(
            False,
            f"Your {record_label} records with status “{required_display}” all predate this task. "
            "Complete the task now, then check again.",
        )

    latest = owned.order_by("-created_at").first()
    latest_display = latest.get_status_display() if latest else "unknown"
    return VerifyResult(
        False,
        f"Your latest {record_label} is “{latest_display}” — this task requires “{required_display}”. "
        "Complete the task in the simulator, then check again.",
    )
