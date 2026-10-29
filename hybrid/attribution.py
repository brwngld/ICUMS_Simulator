"""Stage 3.2 Checkpoint A: secure student attribution of ledger-backed
creations to journey record roles.

Three operations stay separate: the creation ledger
(``SimulatorRecordCreation``) is immutable evidence written by the capture
receiver; attribution is the student's explicit claim — a NEW-mode role is
claimed here against its ledger row (``source=created_in_journey``), an
EXISTING-mode role is authorised through ``journey_services.assign_record``
(``source=authorized_existing``); verification is the existing engines,
untouched. This module never writes a VERIFIED ``StepEvent`` and never completes
a practical step — attribution satisfies a *role gate* only, and for a NEW-mode
role only a creation backed by an authoritative ledger row can satisfy it.

Eligibility (server-derived, never client-supplied): the ledger row is the
student's, of the role's kind, unattributed to any attempt, and created at or
after ``JourneyAttempt.started_at``. Creation eligibility is journey-scoped,
never step-scoped: one record role may serve several journey steps and a record
produced for an early step is legitimately reused by later ones, so entering or
re-entering a step never invalidates a record already attributed. Step-specific
freshness is the separate, narrower question the verification engines own — they
bound the record's *activity* to the one step being checked.
Concurrency: the caller's transaction holds the
attempt row lock; the partial unique constraint
``unique_active_created_in_journey_claim`` is the cross-attempt
record-claim gate on both SQLite and PostgreSQL — a race is refused by the
database and surfaced as a controlled ``AttributionError``.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from . import journey_services, verification
from .models import (
    JourneyAttempt,
    JourneyRecordAssociation,
    JourneyRecordRole,
    SimulatorRecordCreation,
)


class AttributionError(Exception):
    """A controlled, student-visible attribution refusal."""

    def __init__(self, message, status=400, code="not_attributable"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _claim_exists(record_kind, record_id):
    """True when the record has ever been claimed as created-in-journey —
    superseded claims count: a claimed record cannot be re-claimed by another
    attempt (database constraint ``unique_active_created_in_journey_claim``
    enforces the same rule, superseded rows included)."""
    return JourneyRecordAssociation.objects.filter(
        record_kind=record_kind,
        record_id=record_id,
        assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    ).exists()


def eligible_creations(attempt, role):
    """The student's unclaimed creations this journey attempt may still claim
    for this role, newest first. Server-derived only; the request supplies
    nothing."""
    claimed = set(
        JourneyRecordAssociation.objects.filter(
            record_kind=role.record_kind,
            assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
        ).values_list("record_id", flat=True)
    )
    rows = SimulatorRecordCreation.objects.filter(
        owner=attempt.enrolment.student,
        record_kind=role.record_kind,
        record_created_at__gte=attempt.started_at,
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
    if _claim_exists(ledger.record_kind, ledger.record_id):
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
        if ledger.record_created_at < locked.started_at:
            raise AttributionError(
                "This record was created before the journey started.",
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
        except IntegrityError:
            # The per-record claim constraint lost a race with another
            # attempt: surface it as the controlled refusal. The savepoint
            # keeps the surrounding transaction usable for the refusal.
            # Anything else — a missing ledger table, a broken FK — must
            # propagate rather than be reported as a lost race.
            raise AttributionError(
                "This creation was just attributed to another journey.",
                status=409, code="already_claimed",
            )
        locked.last_activity_at = now
        locked.save(update_fields=("last_activity_at",))
    return association


#: The fields each record kind is recognised by, in the order the learner meets
#: them: the first non-empty one names the row in the picker.
_RECORD_LABEL_FIELDS = {
    "ucr": ("ucr_no", "temp_no", "user_reference"),
    "boe": ("declaration_no", "reference", "trader_reference"),
    "consignment": ("application_no", "reference"),
    "mda": ("application_no", "reference"),
}


def _record_label(role, record):
    for field_name in _RECORD_LABEL_FIELDS.get(role.record_kind, ()):
        value = getattr(record, field_name, None)
        if value:
            return str(value)
    return f"Record #{record.pk}"


def _picker_row(role, record, window_start, chosen_record_id, *, creation_id=None, created_at=None):
    """One serialisable picker row, carrying the same freshness reading the
    verification engines will make of the same record."""
    activity = verification.record_activity(record)
    return {
        "creation_id": creation_id,
        "record_id": record.pk,
        "record_label": _record_label(role, record),
        "record_status": record.get_status_display(),
        "record_created_at": created_at,
        "last_activity_at": activity,
        "in_window": activity is not None and activity >= window_start,
        "chosen": record.pk == chosen_record_id,
    }


def _newest_worked_first(rows):
    """Rows with no activity timestamp at all sort last, so ``None`` never has to
    compare against a datetime."""
    return sorted(
        rows,
        key=lambda row: (row["last_activity_at"] is None, row["last_activity_at"]),
        reverse=True,
    )


def attributable_rows(attempt, role, *, window_start=None):
    """Every record the learner may confirm for one role, newest activity first.

    A NEW-mode role offers the learner's unclaimed ledger creations — the
    authoritative creation row is the only thing that can ever satisfy such a
    role, so an unattributable record is not listed at all. An EXISTING-mode
    role offers every record the learner owns, since reusing one is what the
    instructor asked for; each row reports whether its activity reaches
    ``window_start``, the same floor the check will use, so the learner is never
    pointed at a record the step is going to refuse as stale.

    These rows are presentation only. Confirming still submits one opaque id and
    every ownership, mode, window and claim rule is re-checked server-side.
    """
    window_start = window_start or attempt.started_at
    active = JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt, role=role, is_active=True,
    ).first()
    chosen_record_id = active.record_id if active else None
    model = VERIFY_RECORDS[role.record_kind][0]

    if role.creation_mode == JourneyRecordRole.CreationMode.EXISTING:
        return _newest_worked_first([
            _picker_row(
                role, record, window_start, chosen_record_id,
                created_at=getattr(record, "created_at", None),
            )
            for record in model.objects.filter(owner=attempt.enrolment.student)
        ])

    creations = eligible_creations(attempt, role)
    records = model.objects.in_bulk(row.record_id for row in creations)
    return _newest_worked_first([
        _picker_row(
            role, records[row.record_id], window_start, chosen_record_id,
            creation_id=row.pk, created_at=row.record_created_at,
        )
        for row in creations
        if row.record_id in records
    ])


def attribute_record(attempt, role, *, creation_id=None, record_id=None, student):
    """Confirm which record fills one role, from either surface of the product.

    ``creation_id`` claims a ledger-backed creation the learner made inside this
    journey; ``record_id`` authorises one of the learner's own existing records
    for a role the instructor set to reuse one. Either way exactly one
    association stays active: both services supersede the previous row under the
    attempt lock and keep it as history, so nothing here writes a
    ``JourneyRecordAssociation`` itself and no second claim can race in.
    """
    if creation_id and record_id:
        raise AttributionError(
            "Choose one record — a creation and a record cannot be confirmed together.",
            code="ambiguous_selection",
        )
    if creation_id:
        return attribute_creation(attempt, role, creation_id, student)
    if not record_id:
        raise AttributionError("Select a record to attribute.", code="no_selection")
    try:
        return journey_services.assign_record(
            attempt,
            role,
            record_id,
            JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
            assigned_by=student,
        )
    except ValidationError as error:
        raise AttributionError(" ".join(error.messages), code="not_attributable") from error
    except (TypeError, ValueError) as error:
        # A non-numeric record id from a hand-made request: the same controlled
        # refusal as a record that is not there, never a server error.
        raise AttributionError(
            "The simulator record for this creation no longer exists.", code="record_missing",
        ) from error

