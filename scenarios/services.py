from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from progress.models import ProgrammeProgress

from .models import AssistanceEvent, ScenarioAction, ScenarioAttempt, ScenarioVersion


def practical_is_unlocked(enrolment):
    return ProgrammeProgress.objects.filter(enrolment=enrolment, orientation_completed_at__isnull=False).exists()


def _conditions_match(conditions, state_data):
    return isinstance(conditions, dict) and all(state_data.get(key) == value for key, value in conditions.items())


def available_actions(attempt):
    if attempt.status != ScenarioAttempt.Status.IN_PROGRESS:
        return []
    definitions = attempt.scenario_version.action_definitions.filter(Q(from_state=attempt.current_state) | Q(from_state__isnull=True)).select_related("to_state")
    return [definition for definition in definitions if _conditions_match(definition.conditions, attempt.state_data)]


@transaction.atomic
def start_or_resume_attempt(enrolment, scenario_version):
    if not practical_is_unlocked(enrolment):
        raise PermissionDenied("Complete simulator orientation before beginning practical training.")
    existing = ScenarioAttempt.objects.filter(enrolment=enrolment, scenario_version=scenario_version, status=ScenarioAttempt.Status.IN_PROGRESS).first()
    if existing:
        return existing, False
    initial_state = scenario_version.states.filter(is_initial=True).first()
    if initial_state is None:
        raise ValidationError("This scenario has no initial state.")
    previous_number = ScenarioAttempt.objects.filter(enrolment=enrolment, scenario_version=scenario_version).aggregate(value=Max("attempt_number"))["value"] or 0
    attempt = ScenarioAttempt.objects.create(
        enrolment=enrolment,
        scenario_version=scenario_version,
        attempt_number=previous_number + 1,
        assistance_mode=scenario_version.assistance_mode,
        current_state=initial_state,
        state_data=dict(scenario_version.initial_data),
    )
    return attempt, True


@transaction.atomic
def perform_action(attempt, action_definition, input_data=None):
    locked = ScenarioAttempt.objects.select_for_update().select_related("current_state", "scenario_version").get(pk=attempt.pk)
    if locked.status != ScenarioAttempt.Status.IN_PROGRESS:
        raise ValidationError("This attempt is no longer in progress.")
    if action_definition.scenario_version_id != locked.scenario_version_id:
        raise PermissionDenied("This action does not belong to the current scenario.")
    permitted_ids = {action.pk for action in available_actions(locked)}
    if action_definition.pk not in permitted_ids:
        raise ValidationError("That action is not available in the current state.")
    before = locked.current_state.key
    next_data = dict(locked.state_data)
    next_data.update(action_definition.effects)
    locked.state_data = next_data
    if action_definition.to_state_id:
        locked.current_state = action_definition.to_state
    if locked.current_state.is_terminal:
        locked.status = ScenarioAttempt.Status.COMPLETED
        locked.completed_at = timezone.now()
    locked.save(update_fields=("state_data", "current_state", "status", "completed_at", "last_saved_at"))
    sequence = locked.actions.aggregate(value=Max("sequence"))["value"] or 0
    ScenarioAction.objects.create(
        attempt=locked,
        sequence=sequence + 1,
        action_definition=action_definition,
        action_code=action_definition.code,
        state_before=before,
        state_after=locked.current_state.key,
        input_data=input_data or {},
        feedback_shown=action_definition.success_feedback,
    )
    return locked


@transaction.atomic
def record_hint(attempt):
    if attempt.assistance_mode in (ScenarioVersion.AssistanceMode.ADVANCED, ScenarioVersion.AssistanceMode.COMPETENCY):
        raise PermissionDenied("Hints are not available in this mode.")
    hint = next((action.beginner_hint for action in available_actions(attempt) if action.beginner_hint), "Review the current status and available documents.")
    AssistanceEvent.objects.create(attempt=attempt, kind=AssistanceEvent.Kind.HINT, context_code=attempt.current_state.key, content_shown=hint)
    return hint
