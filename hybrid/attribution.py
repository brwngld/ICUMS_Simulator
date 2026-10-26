"""Stage 3.2 Checkpoint A: secure student attribution of ledger-backed
creations to journey record roles.

Three operations stay separate: the creation ledger
(``SimulatorRecordCreation``) is immutable evidence written by the capture
receiver; attribution is the student's explicit claim written here as a
``JourneyRecordAssociation`` with ``source=created_in_journey``; verification
is the existing engines, untouched. This module never writes a VERIFIED
``StepEvent`` and never completes a practical step — attribution satisfies a
*role gate* only, and only for a creation backed by an authoritative ledger
row.

Eligibility (server-derived, never client-supplied): the ledger row is the
student's, of the role's kind, unattributed to any attempt, and created at or
after the window floor — the attempt's start, or the learner's last opening
of the role's bound condition step if that is later (the same freshness bound
Check-My-Work applies). Concurrency: the caller's transaction holds the
attempt row lock; the partial unique constraint
``unique_active_created_in_journey_claim`` is the cross-attempt
record-claim gate on both SQLite and PostgreSQL — a race is refused by the
database and surfaced as a controlled ``AttributionError``.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from .models import (
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    SimulatorRecordCreation,
    StepEvent,
)


class AttributionError(Exception):
    """A controlled, student-visible attribution refusal."""

    def __init__(self, message, status=400, code="not_attributable"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _bound_step(role):
    """The step whose condition is bound to this role, or None."""
    binding = (
        JourneyConditionBinding.objects.filter(role=role)
        .select_related("condition__step")
        .first()
    )
    return binding.condition.step if binding else None


def _window_floor(attempt, role):
    """The earliest creation moment eligible for this role: the attempt's
    start, or the learner's last entry into the role's bound condition step
    if that is later — the freshness bound Check-My-Work already applies."""
    floor = attempt.started_at
    step = _bound_step(role)
    if step is not None:
        lesson_attempt = LessonAttempt.objects.filter(
            enrolment=attempt.enrolment, lesson=step.lesson,
        ).first()
        if lesson_attempt is not None:
            event = (
                StepEvent.objects.filter(
                    attempt=lesson_attempt, step=step, kind=StepEvent.Kind.OPENED,
                )
                .order_by("-occurred_at")
                .first()
            )
            if event is not None and event.occurred_at > floor:
                floor = event.occurred_at
    return floor


def _active_claim_exists(record_kind, record_id):
    return JourneyRecordAssociation.objects.filter(
        record_kind=record_kind,
        record_id=record_id,
        assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
        is_active=True,
    ).exists()


def eligible_creations(attempt, role):
    """The student's unclaimed, in-window creations eligible for this role,
    newest first. Server-derived only; the request supplies nothing."""
    floor = _window_floor(attempt, role)
    claimed = set(
        JourneyRecordAssociation.objects.filter(
            record_kind=role.record_kind,
            assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
            is_active=True,
        ).values_list("record_id", flat=True)
    )
    rows = SimulatorRecordCreation.objects.filter(
        owner=attempt.enrolment.student,
        record_kind=role.record_kind,
        record_created_at__gte=floor,
    ).order_by("-record_created_at", "-id")

    return [row for row in rows if row.record_id not in claimed]


def attribute_creation(attempt, role, ledger_id, student):
    """Attribute one ledger-backed creation to one required NEW record role.

    Validates the full chain server-side — attempt ownership/status, role
    coherence and mode, ledger ownership and kind, creation window, record
    existence and ownership, claim uniqueness — then writes the association
    inside the attempt row lock. Raises ``AttributionError`` (controlled),
    ``PermissionDenied`` (another learner's attempt or record) or
    ``IntegrityError``-derived ``AttributionError`` (lost concurrency race).
    """
    if attempt.enrolment.student_id != student.pk:
        raise PermissionDenied("No such journey attempt for this learner.")
    if attempt.journey_id != role.journey_id:
        raise ValidationError({"role": "The record role must belong to the attempted journey."})
    if attempt.status != JourneyAttempt.Status.IN_PROGRESS:
        raise AttributionError(
            "Only an in-progress journey attempt can attribute records.",
            status=409, code="attempt_not_in_progress",
        )
    if role.creation_mode != JourneyRecordRole.CreationMode.NEW:
        raise AttributionError(
            "This checkpoint attributes newly created records only.",
            code="creation_mode_not_new",
        )

    try:
        ledger = SimulatorRecordCreation.objects.get(pk=ledger_id)
    except SimulatorRecordCreation.DoesNotExist:
        raise AttributionError("That creation record does not exist.", code="unknown_creation")
    if ledger.owner_id != student.pk or ledger.record_kind != role.record_kind:
        raise PermissionDenied("That creation does not belong to this learner.")
    if _active_claim_exists(ledger.record_kind, ledger.record_id):
        raise AttributionError(
            "This creation has already been attributed to a journey.",
            status=409, code="already_claimed",
        )

    model = VERIFY_RECORDS[role.record_kind][0]
    if not model.objects.filter(pk=ledger.record_id, owner_id=student.pk).exists():
        raise AttributionError("The simulator record for this creation no longer exists.",
                               code="record_missing")

    with transaction.atomic():
        locked = JourneyAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.status != JourneyAttempt.Status.IN_PROGRESS:
            raise AttributionError("The journey attempt is no longer in progress.",
                                   status=409, code="attempt_not_in_progress")
        floor = _window_floor(locked, role)
        if ledger.record_created_at < floor:
            raise AttributionError(
                "This record was created before the step was (re)opened.",
                code="outside_window",
            )
        replaced = JourneyRecordAssociation.objects.filter(
            journey_attempt=locked, role=role, is_active=True,
        )
        now = timezone.now()
        replaced.update(is_active=False, replaced_at=now)
        try:
            with transaction.atomic():
                association = JourneyRecordAssociation.objects.create(
                    journey_attempt=locked,
                    role=role,
                    enrolment=locked.enrolment,
                    programme_version=locked.journey.programme_version,
                    record_kind=role.record_kind,
                    record_id=ledger.record_id,
                    assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
                    assigned_by=student,
                )
        except Exception:
            # The per-record claim constraint lost a race with another
            # attempt: surface it as the controlled refusal. The savepoint
            # keeps the surrounding transaction usable for the refusal.
            raise AttributionError(
                "This creation was just attributed to another journey.",
                status=409, code="already_claimed",
            )
        locked.last_activity_at = now
        locked.save(update_fields=("last_activity_at",))
    return association


def eligible_for_view(attempt, role):
    """Serialisable eligible rows for the (future) student interface."""
    return [
        {
            "creation_id": row.pk,
            "record_id": row.record_id,
            "record_created_at": row.record_created_at,
        }
        for row in eligible_creations(attempt, role)
    ]
