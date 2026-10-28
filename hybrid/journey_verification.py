"""Read-only resolution and exact-record evaluation for journey verification.

This checkpoint stops before Check My Work integration: the module proves
which exact simulator record a journey step authorizes, can revalidate that
selection under the agreed row locks, and evaluates one condition against the
resolved record. It never writes a ``StepEvent`` or a
``JourneyVerificationEvidence`` row. Every identifier is derived from the
server-resolved lesson attempt and practical step; no journey, role,
association or record identifier is accepted from a browser.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction

from scenarios.bindings import VERIFY_RECORDS

from . import journey_services, verification
from .journey_provenance import check_provenance
from .models import (
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyStep,
    LessonAttempt,
    PracticalStep,
    StepEvent,
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


@dataclass(frozen=True)
class LockedJourneyVerification:
    """A context revalidated under the agreed row locks.

    ``records`` pairs each saved condition with the one record its active
    association authorizes, so a caller evaluates conditions without ever
    querying the learner's records again. The locks protect a subsequent
    write only while the caller's surrounding transaction remains open.
    """

    context: JourneyVerificationContext
    opening_generation: UUID
    opening_occurred_at: datetime
    records: tuple[tuple[UUID, object], ...]

    def record_for(self, condition):
        return next(
            (record for condition_id, record in self.records if condition_id == condition.pk),
            None,
        )


@dataclass(frozen=True)
class ExactConditionResult:
    """The outcome of evaluating one condition against resolved evidence."""

    passed: bool
    code: str | None
    message: str


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


def _require_journey_scope(enrolment, assignment):
    """The journey, its course and the step must all share the enrolment."""
    journey = assignment.journey
    if (
        journey.programme_version_id != enrolment.programme_version_id
        or journey.course.programme_version_id != enrolment.programme_version_id
        or assignment.step.lesson.module.course_id != journey.course_id
    ):
        _fail("This journey does not match the learner's enrolment.", "programme_mismatch")


def _resolve_selection(attempt, lesson_attempt, assignment, condition, *, for_update=False):
    """The exact record authorized for one saved condition.

    Returns ``(selection, record)`` so callers that evaluate the condition
    never repeat the lookup and never broaden it to the learner's records.
    """
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

    associations = JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt,
        role=role,
        is_active=True,
    )
    if for_update:
        associations = associations.select_for_update()
    association = associations.first()
    if association is None:
        _fail("No active record is attributed to this journey role.", "association_missing")
    if (
        association.enrolment_id != attempt.enrolment_id
        or association.programme_version_id != attempt.journey.programme_version_id
    ):
        _fail("The attributed record does not match this journey.", "association_mismatch")

    failure, record = check_provenance(attempt, role, association)
    if failure is not None and record is None:
        _fail(failure.message, failure.code)

    if attempt.started_at is None:
        _fail(
            "The journey attempt has no start time, so record freshness cannot be established.",
            "provenance_invalid",
        )
    opened = verification.opened_at(lesson_attempt, assignment.step)
    freshness_floor = max(attempt.started_at, opened)
    activity = _record_activity(record)
    if activity is None or activity < freshness_floor:
        _fail("The attributed record predates the current verification window.", "record_stale")
    # A creation-window refusal is only raised after freshness, preserving the
    # resolver's original refusal precedence when both observations fail.
    if failure is not None:
        _fail(failure.message, failure.code)

    return AuthorizedRecordSelection(
        condition_id=condition.pk,
        role_id=role.pk,
        association_id=association.pk,
        record_kind=association.record_kind,
        record_id=association.record_id,
        freshness_floor=freshness_floor,
    ), record


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
    _require_journey_scope(enrolment, assignment)

    attempt = JourneyAttempt.objects.filter(enrolment=enrolment, journey=journey).first()
    if attempt is None:
        _fail("No journey attempt is available for this learner.", "attempt_missing")
    if attempt.status != JourneyAttempt.Status.IN_PROGRESS:
        _fail("The journey attempt is not in progress.", "attempt_not_in_progress")
    _require_reachable(attempt, assignment)

    selections = []
    for condition in step.conditions.order_by("order", "id"):
        if condition.kind != VerificationCondition.Kind.SAVED_RECORD:
            continue
        selection, _record = _resolve_selection(attempt, lesson_attempt, assignment, condition)
        selections.append(selection)
    return JourneyVerificationContext(
        lesson_attempt_id=lesson_attempt.pk,
        journey_attempt_id=attempt.pk,
        journey_step_id=assignment.pk,
        step_id=step.pk,
        selections=tuple(selections),
    )


def revalidate_journey_verification(user, lesson_attempt, step):
    """Revalidate one journey verification selection under the agreed locks.

    Returns ``LockedJourneyVerification`` for a journey step, or ``None`` when
    the step is not assigned to a journey (the same three-way contract the
    public resolver uses). Invalid, completed or unreachable journey state is
    a controlled refusal, never a legacy fallback.

    Locks are taken in one fixed order — JourneyAttempt, LessonAttempt, the
    OPENED StepEvent, then each JourneyRecordAssociation — so this function can
    later be called by the verification writer inside its own transaction
    without deadlocking against attribution or opening. Nothing is written.
    """
    if not isinstance(lesson_attempt, LessonAttempt) or not isinstance(step, PracticalStep):
        _fail("The verification request is invalid.", "request_invalid")
    if lesson_attempt.enrolment.student_id != user.pk:
        raise PermissionDenied("No such lesson attempt for this learner.")
    if step.lesson_id != lesson_attempt.lesson_id:
        _fail("The step does not belong to this lesson attempt.", "step_mismatch")

    assignment = (
        JourneyStep.objects.filter(step=step)
        .select_related("journey__course", "step__lesson__module__course")
        .first()
    )
    if assignment is None:
        return None
    _require_journey_scope(lesson_attempt.enrolment, assignment)

    with transaction.atomic():
        attempt = (
            JourneyAttempt.objects.select_for_update()
            .select_related("journey__course", "enrolment")
            .filter(enrolment_id=lesson_attempt.enrolment_id, journey_id=assignment.journey_id)
            .first()
        )
        if attempt is None:
            _fail("No journey attempt is available for this learner.", "attempt_missing")
        if attempt.status != JourneyAttempt.Status.IN_PROGRESS:
            _fail("The journey attempt is not in progress.", "attempt_not_in_progress")

        locked_lesson_attempt = (
            LessonAttempt.objects.select_for_update()
            .select_related("enrolment", "lesson__module__course")
            .get(pk=lesson_attempt.pk)
        )
        if locked_lesson_attempt.enrolment.student_id != user.pk:
            raise PermissionDenied("No such lesson attempt for this learner.")
        locked_step = (
            PracticalStep.objects.select_related("lesson__module__course")
            .filter(pk=step.pk, lesson_id=locked_lesson_attempt.lesson_id)
            .first()
        )
        if locked_step is None:
            _fail("The step does not belong to this lesson attempt.", "step_mismatch")
        locked_assignment = (
            JourneyStep.objects.select_related("journey__course", "step__lesson__module__course")
            .filter(pk=assignment.pk, step=locked_step)
            .first()
        )
        if locked_assignment is None:
            _fail("This step is not assigned to the journey.", "step_not_assigned")
        if locked_assignment.journey_id != attempt.journey_id:
            _fail("This journey does not match the learner's enrolment.", "programme_mismatch")
        _require_journey_scope(locked_lesson_attempt.enrolment, locked_assignment)
        _require_reachable(attempt, locked_assignment)

        opening = (
            StepEvent.objects.select_for_update()
            .filter(
                attempt=locked_lesson_attempt,
                step=locked_step,
                kind=StepEvent.Kind.OPENED,
            )
            .first()
        )
        if opening is None:
            _fail("The step was never opened in this attempt.", "opening_missing")
        if opening.generation is None:
            _fail(
                "The opening has no generation token, so it cannot back verification evidence.",
                "opening_missing_generation",
            )

        selections = []
        records = []
        for condition in locked_step.conditions.order_by("order", "id"):
            if condition.kind != VerificationCondition.Kind.SAVED_RECORD:
                continue
            selection, record = _resolve_selection(
                attempt, locked_lesson_attempt, locked_assignment, condition, for_update=True,
            )
            selections.append(selection)
            records.append((condition.pk, record))

        return LockedJourneyVerification(
            context=JourneyVerificationContext(
                lesson_attempt_id=locked_lesson_attempt.pk,
                journey_attempt_id=attempt.pk,
                journey_step_id=locked_assignment.pk,
                step_id=locked_step.pk,
                selections=tuple(selections),
            ),
            opening_generation=opening.generation,
            opening_occurred_at=opening.occurred_at,
            records=tuple(records),
        )


def evaluate_exact_condition(condition, *, opening, selection=None, record=None):
    """Evaluate one condition against evidence the server already authorized.

    ``opening`` must be the persisted OPENED event for the attempt and step;
    ``screen_opened`` is satisfied by that opening generation alone.
    ``saved_record`` additionally requires the exact ``record`` named by
    ``selection`` — the learner's other records are never considered. Activity
    freshness is a separate question owned by this evaluator, but ``updated_at``
    only ever proves the record was touched inside the window; it never proves
    who touched it. Nothing is written and no ``VERIFIED`` event is created.
    """
    if condition.kind not in VerificationCondition.Kind.values:
        return ExactConditionResult(False, "invalid_condition", "The condition has an unknown kind.")
    if opening is None or opening.kind != StepEvent.Kind.OPENED:
        return ExactConditionResult(False, "opening_missing", "The step has no persisted opening.")
    if opening.generation is None:
        return ExactConditionResult(
            False,
            "opening_missing_generation",
            "The opening has no generation token, so it cannot back verification evidence.",
        )
    if condition.kind == VerificationCondition.Kind.SCREEN_OPENED:
        return ExactConditionResult(True, None, "Verified.")

    if selection is None or record is None:
        return ExactConditionResult(
            False, "record_unavailable", "The exact attributed record is unavailable.",
        )
    entry = VERIFY_RECORDS.get(selection.record_kind)
    if entry is None:
        return ExactConditionResult(
            False, "record_kind_mismatch", "The selection names an unapproved record kind.",
        )
    model = entry[0]
    if condition.record_kind != selection.record_kind:
        return ExactConditionResult(
            False, "record_kind_mismatch", "The condition and its selection use different record kinds.",
        )
    if not isinstance(record, model) or record.pk != selection.record_id:
        return ExactConditionResult(
            False, "record_mismatch", "The record is not the exact record the selection authorizes.",
        )

    if record.status != condition.required_status:
        return ExactConditionResult(
            False, "record_status_mismatch", "The record is not saved with the required status.",
        )

    expected = condition.expected_fields if isinstance(condition.expected_fields, dict) else {}
    concrete_fields = {field.name for field in model._meta.concrete_fields}
    for field_name, expected_value in expected.items():
        if field_name not in concrete_fields or getattr(record, field_name) != expected_value:
            return ExactConditionResult(
                False, "record_fields_mismatch", "A required saved value does not match.",
            )

    activity = _record_activity(record)
    if activity is None or activity < selection.freshness_floor:
        return ExactConditionResult(
            False, "record_stale", "The attributed record predates the current verification window.",
        )
    return ExactConditionResult(True, None, "Verified.")
