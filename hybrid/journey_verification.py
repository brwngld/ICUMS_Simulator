"""Read-only resolution of journey-authorized verification records.

Checkpoint 3.3.1 deliberately stops before evaluation: this module proves
which exact simulator record the existing verifier may inspect, but it does
not call that verifier and never writes a ``StepEvent``.  Every identifier is
derived from the server-resolved lesson attempt and practical step; no
journey, role, association or record identifier is accepted from a browser.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied

from scenarios.bindings import VERIFY_RECORDS

from . import journey_services, verification
from .models import (
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyStep,
    LessonAttempt,
    PracticalStep,
    SimulatorRecordCreation,
    VerificationCondition,
)


class JourneyVerificationResolutionError(Exception):
    """A controlled, non-sensitive failure to resolve journey evidence."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class AuthorizedRecordSelection:
    """Exact server-authorized record identity for one saved condition."""

    condition_id: UUID
    role_id: UUID
    association_id: UUID
    record_kind: str
    record_id: int
    freshness_floor: datetime


@dataclass(frozen=True)
class JourneyVerificationContext:
    """Immutable scalar context suitable for the existing evaluator."""

    lesson_attempt_id: UUID
    journey_attempt_id: UUID
    journey_step_id: UUID
    step_id: UUID
    selections: tuple[AuthorizedRecordSelection, ...]

    def selection_for(self, condition):
        return next(
            (selection for selection in self.selections if selection.condition_id == condition.pk),
            None,
        )


def _fail(message, code):
    raise JourneyVerificationResolutionError(message, code)


def _record_activity(record):
    moments = [
        getattr(record, "updated_at", None),
        getattr(record, "submitted_at", None),
        getattr(record, "created_at", None),
    ]
    return max((moment for moment in moments if moment is not None), default=None)


def _require_reachable(attempt, assignment):
    """Require the assignment to be the attempt's current, reachable step."""
    if attempt.current_journey_step_id != assignment.pk:
        _fail("This journey step is not currently available.", "step_not_current")

    rows = journey_services.journey_step_rows(attempt)
    row_by_assignment = {row["assignment"].pk: row for row in rows}
    target_index = next(
        (index for index, row in enumerate(rows) if row["assignment"].pk == assignment.pk),
        None,
    )
    if target_index is None:
        _fail("This step is not assigned to the journey.", "step_not_assigned")
    if any(not row["satisfied"] for row in rows[:target_index]):
        _fail("This journey step is locked by earlier work.", "progression_blocked")

    dependencies = JourneyDependency.objects.filter(
        journey=attempt.journey,
        dependent_step=assignment,
    ).select_related("predecessor_step", "required_record_role")
    for dependency in dependencies:
        if dependency.dependency_type == JourneyDependency.DependencyType.RECORD_AVAILABLE:
            role = dependency.required_record_role
            if role is None or role.journey_id != attempt.journey_id:
                _fail("This journey dependency is invalid.", "dependency_invalid")
            if not journey_services.role_satisfied(attempt, role)[0]:
                _fail("This journey step is waiting for a required record.", "dependency_blocked")
        else:
            predecessor = row_by_assignment.get(dependency.predecessor_step_id)
            if predecessor is None or not predecessor["satisfied"]:
                _fail("This journey step is waiting for an earlier step.", "dependency_blocked")


def _resolve_selection(attempt, lesson_attempt, assignment, condition):
    binding = (
        JourneyConditionBinding.objects.filter(condition=condition)
        .select_related("role")
        .first()
    )
    if binding is None:
        _fail("This verification condition has no journey record binding.", "binding_missing")
    role = binding.role
    if role.journey_id != attempt.journey_id:
        _fail("This verification condition is bound outside its journey.", "binding_mismatch")
    if role.record_kind != condition.record_kind:
        _fail("The journey record role does not match this condition.", "record_kind_mismatch")

    association = JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt,
        role=role,
        is_active=True,
    ).first()
    if association is None:
        _fail("No active record is attributed to this journey role.", "association_missing")
    if (
        association.enrolment_id != attempt.enrolment_id
        or association.programme_version_id != attempt.journey.programme_version_id
        or association.record_kind != role.record_kind
    ):
        _fail("The attributed record does not match this journey.", "association_mismatch")
    if association.assignment_source not in JourneyRecordAssociation.AssignmentSource.values:
        _fail("The attributed record has no authorized provenance.", "provenance_mismatch")
    if (
        role.creation_mode == role.CreationMode.NEW
        and association.assignment_source != JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY
    ):
        _fail("The attributed record has no authorized provenance.", "provenance_mismatch")
    if (
        role.creation_mode == role.CreationMode.EXISTING
        and association.assignment_source != JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING
    ):
        _fail("The attributed record has no authorized provenance.", "provenance_mismatch")

    model = VERIFY_RECORDS[condition.record_kind][0]
    record = model.objects.filter(
        pk=association.record_id,
        owner_id=attempt.enrolment.student_id,
    ).first()
    if record is None:
        _fail("The attributed simulator record is unavailable.", "record_unavailable")

    opened = verification.opened_at(lesson_attempt, assignment.step)
    freshness_floor = max(attempt.started_at, opened)
    activity = _record_activity(record)
    if activity is None or activity < freshness_floor:
        _fail("The attributed record predates the current verification window.", "record_stale")

    if association.assignment_source == JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY:
        evidence = SimulatorRecordCreation.objects.filter(
            record_kind=association.record_kind,
            record_id=association.record_id,
            owner_id=attempt.enrolment.student_id,
        ).first()
        if evidence is None:
            _fail("Creation evidence is unavailable for the attributed record.", "creation_evidence_missing")
        if evidence.record_created_at < freshness_floor:
            _fail("The attributed record predates the current verification window.", "record_stale")

    return AuthorizedRecordSelection(
        condition_id=condition.pk,
        role_id=role.pk,
        association_id=association.pk,
        record_kind=association.record_kind,
        record_id=association.record_id,
        freshness_floor=freshness_floor,
    )


def resolve_journey_verification(user, lesson_attempt, step):
    """Return the journey's exact record selections, or ``None`` for legacy.

    ``lesson_attempt`` and ``step`` are expected to have been resolved by the
    existing owner-scoped request path.  Their ownership and relationship are
    nevertheless rechecked here so the resolver is safe to reuse elsewhere.
    """
    if not isinstance(lesson_attempt, LessonAttempt) or not isinstance(step, PracticalStep):
        _fail("The verification request is invalid.", "request_invalid")
    if lesson_attempt.enrolment.student_id != user.pk:
        raise PermissionDenied("No such lesson attempt for this learner.")
    if step.lesson_id != lesson_attempt.lesson_id:
        _fail("The step does not belong to this lesson attempt.", "step_mismatch")

    assignment = (
        JourneyStep.objects.filter(step=step)
        .select_related("journey", "journey__course", "step__lesson__module__course")
        .first()
    )
    if assignment is None:
        return None
    journey = assignment.journey
    enrolment = lesson_attempt.enrolment
    if (
        journey.programme_version_id != enrolment.programme_version_id
        or journey.course.programme_version_id != enrolment.programme_version_id
        or assignment.step.lesson.module.course_id != journey.course_id
    ):
        _fail("This journey does not match the learner's enrolment.", "programme_mismatch")

    attempt = JourneyAttempt.objects.filter(enrolment=enrolment, journey=journey).first()
    if attempt is None:
        _fail("No journey attempt is available for this learner.", "attempt_missing")
    if attempt.status != JourneyAttempt.Status.IN_PROGRESS:
        _fail("The journey attempt is not in progress.", "attempt_not_in_progress")
    _require_reachable(attempt, assignment)

    selections = tuple(
        _resolve_selection(attempt, lesson_attempt, assignment, condition)
        for condition in step.conditions.order_by("order", "id")
        if condition.kind == VerificationCondition.Kind.SAVED_RECORD
    )
    return JourneyVerificationContext(
        lesson_attempt_id=lesson_attempt.pk,
        journey_attempt_id=attempt.pk,
        journey_step_id=assignment.pk,
        step_id=step.pk,
        selections=selections,
    )
