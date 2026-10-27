"""Read-only verification state for journey-bound practical steps.

Checkpoint 3.3.2 records what satisfied a step and answers whether that
record still holds. Both halves are predicates only: this module never
creates, updates or deletes a ``StepEvent`` or a
``JourneyVerificationEvidence`` row, and the legacy ``verify_step`` path is
untouched. Student endpoints still run the Checkpoint 1 resolver, so nothing
here changes what a learner sees.

"Current" is deliberately strict and fail-closed. A step counts only when its
opening generation, its condition text, its journey binding and its active
record association all still name the one evidence identity that was
recorded; a step with no conditions never counts. Historical rows are never
enough to satisfy the predicate — they only prove the step is stale — and the
predicate has no ``JourneyAttempt.status`` gate, so a completed journey keeps
its readable history.
"""
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.core.exceptions import PermissionDenied

from scenarios.bindings import VERIFY_RECORDS

from .models import (
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyRecordAssociation,
    JourneyStep,
    JourneyVerificationEvidence,
    LessonAttempt,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)


@dataclass(frozen=True)
class CurrentVerification:
    """The single live evidence identity that satisfies a journey step."""

    journey_attempt_id: UUID
    journey_step_id: UUID
    opening_generation: UUID
    opening_occurred_at: datetime
    verified_at: datetime
    condition_ids: tuple[UUID, ...]
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class NotCurrent:
    """The fail-closed answer: this step is not currently verified, and why."""

    reason: str
    detail: str


def _not_current(reason, detail):
    return NotCurrent(reason=reason, detail=detail)


def condition_fingerprint(condition):
    """A canonical digest of the fields that make a saved condition itself.

    Only semantic fields are hashed, in one fixed key order and with no
    incidental whitespace, so an untouched condition always fingerprints the
    same while any edit to its kind, record kind, required status or expected
    values changes the digest. Ordering is excluded: reordering conditions
    does not change what they require.
    """
    payload = {
        "kind": condition.kind,
        "record_kind": condition.record_kind,
        "required_status": condition.required_status,
        "expected_fields": condition.expected_fields or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def opening_for(lesson_attempt, step):
    """The singleton ``opened`` row whose generation evidence is bound to.

    Read only: ordinary visits must never rotate the generation or refresh the
    timestamp, so this accessor cannot change what it reports.
    """
    return StepEvent.objects.filter(
        attempt=lesson_attempt,
        step=step,
        kind=StepEvent.Kind.OPENED,
    ).first()


def verification_history(lesson_attempt, step):
    """Every recorded journey success for this step, newest first.

    Deliberately independent of ``JourneyAttempt.status``: a completed
    journey still shows what satisfied each step. Rows are returned exactly
    as stored; they are append-only history and must never be rewritten.
    """
    assignment = JourneyStep.objects.filter(step=step).first()
    if assignment is None:
        return ()
    return tuple(
        JourneyVerificationEvidence.objects.filter(
            lesson_attempt=lesson_attempt,
            journey_step=assignment,
        ).select_related("condition", "role", "association")
    )


def _active_association(attempt, journey, role):
    """The role's active record association, with its integrity problems."""
    association = (
        JourneyRecordAssociation.objects.filter(
            journey_attempt=attempt,
            role=role,
            is_active=True,
        )
        .first()
    )
    if association is None:
        return None, "association_missing"
    if (
        association.enrolment_id != attempt.enrolment_id
        or association.programme_version_id != journey.programme_version_id
        or association.record_kind != role.record_kind
        or association.replaced_at is not None
    ):
        return None, "association_mismatch"
    return association, None


def _record_available(student_id, record_kind, record_id):
    if record_kind not in VERIFY_RECORDS:
        return False
    model = VERIFY_RECORDS[record_kind][0]
    return model.objects.filter(pk=record_id, owner_id=student_id).exists()


def current_verification(user, lesson_attempt, step):
    """``CurrentVerification`` when the recorded evidence still holds.

    Every identifier is derived from the server-resolved attempt and step;
    nothing is accepted from a browser. On any inconsistency the answer is
    ``NotCurrent`` and the caller must treat the step as unverified.
    """
    if not isinstance(lesson_attempt, LessonAttempt) or not isinstance(step, PracticalStep):
        return _not_current("request_invalid", "The verification request is invalid.")
    if lesson_attempt.enrolment.student_id != user.pk:
        raise PermissionDenied("No such lesson attempt for this learner.")
    if step.lesson_id != lesson_attempt.lesson_id:
        return _not_current("step_mismatch", "The step does not belong to this lesson attempt.")

    assignment = (
        JourneyStep.objects.filter(step=step)
        .select_related("journey__course", "step__lesson__module__course")
        .first()
    )
    if assignment is None:
        return _not_current("not_journey_step", "The step is not assigned to a journey.")
    journey = assignment.journey
    enrolment = lesson_attempt.enrolment
    if (
        journey.programme_version_id != enrolment.programme_version_id
        or journey.course.programme_version_id != enrolment.programme_version_id
        or assignment.step.lesson.module.course_id != journey.course_id
    ):
        return _not_current("programme_mismatch", "The journey does not match the learner's enrolment.")

    attempt = JourneyAttempt.objects.filter(enrolment=enrolment, journey=journey).first()
    if attempt is None:
        return _not_current("attempt_missing", "The learner has no attempt on this journey.")

    opening = opening_for(lesson_attempt, step)
    if opening is None:
        return _not_current("opening_missing", "The step was never opened in this attempt.")
    if opening.generation is None:
        return _not_current(
            "opening_missing_generation",
            "The opening predates generation tokens, so it cannot back evidence.",
        )

    conditions = list(step.conditions.order_by("order", "id"))
    if not conditions:
        return _not_current("no_conditions", "The step declares no verification conditions.")
    if any(condition.kind not in VerificationCondition.Kind.values for condition in conditions):
        return _not_current("invalid_condition", "The step has a condition of an unknown kind.")

    saved = [condition for condition in conditions if condition.kind == VerificationCondition.Kind.SAVED_RECORD]
    generation = opening.generation
    rows = list(
        JourneyVerificationEvidence.objects.filter(
            lesson_attempt=lesson_attempt,
            journey_step=assignment,
            opening_generation=generation,
        )
    )
    saved_ids = {condition.pk for condition in saved}
    if any(row.condition_id not in saved_ids for row in rows):
        return _not_current(
            "evidence_unexpected",
            "The opening carries evidence for a condition this step no longer requires.",
        )

    if not saved:
        return CurrentVerification(
            journey_attempt_id=attempt.pk,
            journey_step_id=assignment.pk,
            opening_generation=generation,
            opening_occurred_at=opening.occurred_at,
            verified_at=opening.occurred_at,
            condition_ids=tuple(condition.pk for condition in conditions),
            evidence_ids=(),
        )

    evidence_ids = []
    verified_moments = []
    for condition in saved:
        fingerprint = condition_fingerprint(condition)
        binding = (
            JourneyConditionBinding.objects.filter(condition=condition)
            .select_related("role")
            .first()
        )
        if binding is None:
            return _not_current("binding_missing", "A condition has no journey record binding.")
        role = binding.role
        if role.journey_id != journey.pk:
            return _not_current("binding_mismatch", "A condition is bound outside its journey.")
        if role.record_kind != condition.record_kind:
            return _not_current("record_kind_mismatch", "A role and its condition use different records.")

        association, problem = _active_association(attempt, journey, role)
        if problem:
            return _not_current(problem, "The role's active record association is missing or invalid.")
        if not _record_available(enrolment.student_id, association.record_kind, association.record_id):
            return _not_current("record_unavailable", "The associated simulator record is unavailable.")

        condition_rows = [row for row in rows if row.condition_id == condition.pk]
        if not condition_rows:
            if JourneyVerificationEvidence.objects.filter(
                lesson_attempt=lesson_attempt,
                journey_step=assignment,
                condition=condition,
            ).exists():
                return _not_current(
                    "evidence_stale",
                    "The condition's evidence belongs to an earlier opening.",
                )
            return _not_current("evidence_missing", "The condition has never been evidenced in this opening.")
        if any(row.condition_fingerprint != fingerprint for row in condition_rows):
            return _not_current("evidence_outdated", "The condition changed after it was evidenced.")
        if any(
            (row.role_id, row.association_id) != (role.pk, association.pk)
            for row in condition_rows
        ):
            return _not_current("evidence_conflicted", "The evidence names a different record than the role.")
        if len(condition_rows) > 1:
            return _not_current("evidence_ambiguous", "More than one evidence identity backs the condition.")

        row = condition_rows[0]
        if (
            row.journey_attempt_id != attempt.pk
            or row.journey_step_id != assignment.pk
            or (row.record_kind, row.record_id) != (association.record_kind, association.record_id)
            or row.opening_occurred_at != opening.occurred_at
        ):
            return _not_current("evidence_conflicted", "The evidence does not describe this opening.")
        evidence_ids.append(row.pk)
        verified_moments.append(row.verified_at)

    return CurrentVerification(
        journey_attempt_id=attempt.pk,
        journey_step_id=assignment.pk,
        opening_generation=generation,
        opening_occurred_at=opening.occurred_at,
        verified_at=max(verified_moments),
        condition_ids=tuple(condition.pk for condition in conditions),
        evidence_ids=tuple(evidence_ids),
    )
