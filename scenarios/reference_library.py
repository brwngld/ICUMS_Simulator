"""Instructor reference library services (Stage R4-B).

The three-state lifecycle over ``UcrDeclaration.reference_state``:

    temporary (attached demo record) → working → approved → retired

Every transition is an explicit instructor action, executed as one atomic
**conditional update** guarded by the expected source state — the documented
controlled path that coexists with R4-A's ``save()`` immutability chokepoint.
A transition whose guard matches zero rows is re-read and answered
idempotently (the target state is already reached and owned) or with a
controlled error (the record moved somewhere invalid).

Locking strategy for promotion versus session deletion (expiry sweep and
discard): promotion takes ``FOR UPDATE`` on the source **session row first**,
so any terminal transaction that already holds it (its last statement writes
the session row) fully completes — including its record deletions — before
promotion re-verifies anything; then promotion takes ``FOR UPDATE`` on the UCR
row and re-checks eligibility under both locks. A record deleted by a
committed expiry or discard answers ``record_gone``; a record detached by an
in-flight promotion answers idempotently.

Known residual window (documented, pending the approved deletion-service
patch): Django's deletion collector gathers child primary keys *before* its
delete statements, and deletes **by primary key**. A sweep whose child
collection falls inside promotion's transaction can therefore still delete the
just-detached row afterwards. All other orderings are safe; the deterministic
test ``test_a_sweep_collect_inside_the_promotion_window_documents_the_hazard``
pins this behavior until the re-checking delete is approved.
"""
from django.db import models, transaction

from .models import UcrDeclaration

#: The states a listed library record can be in, in lifecycle order.
REFERENCE_STATES = (
    UcrDeclaration.ReferenceState.WORKING,
    UcrDeclaration.ReferenceState.APPROVED,
    UcrDeclaration.ReferenceState.RETIRED,
)


def _gate():
    """The feature gate, re-checked inside every service."""
    from hybrid import demonstrations

    if not demonstrations.recording_enabled():
        raise demonstrations.DemonstrationError(
            "Demonstration recording is not enabled.", "recording_disabled", 403
        )


def reference_payload(record):
    """The JSON shape every endpoint returns for one reference, with the
    advisory action flags the frontend renders from."""
    state = record.reference_state
    return {
        "id": record.pk,
        "number": record.ucr_no or record.temp_no,
        "status": record.status,
        "regime": record.regime,
        "exporter_name": record.exporter_name,
        "importer_name": record.importer_name,
        "reference_state": state,
        "source_session": str(record.reference_source_session_id) if record.reference_source_session_id else None,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
        "can_edit": state == UcrDeclaration.ReferenceState.WORKING,
        "can_approve": state == UcrDeclaration.ReferenceState.WORKING
        and record.status == UcrDeclaration.Status.SUBMITTED,
        "can_retire": state == UcrDeclaration.ReferenceState.APPROVED,
        "can_select": state == UcrDeclaration.ReferenceState.APPROVED,
    }


def list_references(user, state=None):
    """This instructor's references, newest first, optionally one state only."""
    _gate()
    from hybrid import demonstrations

    if state is not None and state not in REFERENCE_STATES:
        raise demonstrations.DemonstrationError(
            "That reference state is not one of the library states.", "reference_state_invalid", 400
        )
    queryset = UcrDeclaration.all_objects.filter(owner=user, reference_state__in=REFERENCE_STATES)
    if state is not None:
        queryset = queryset.filter(reference_state=state)
    return [reference_payload(record) for record in queryset.order_by("-updated_at")]


def reference_detail(user, record_id):
    """One owned reference by id; anything else is the same not-found answer."""
    _gate()
    record = _owned_reference(user, record_id)
    if record is None:
        raise _not_found()
    return reference_payload(record)


def _owned_reference(user, record_id):
    """The record only when it is one of this instructor's references.

    Ordinary records, temporary demonstration records and other instructors'
    records never resolve — an unknown id, a foreign id and an
    not-yet-a-reference id are deliberately indistinguishable.
    """
    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id < 1:
        return None
    return (
        UcrDeclaration.all_objects.filter(
            pk=record_id,
            owner=user,
            reference_state__in=REFERENCE_STATES,
        )
        .select_related("owner")
        .first()
    )


def _not_found():
    from hybrid import demonstrations

    return demonstrations.DemonstrationError(
        "No such reference record is available.", "reference_not_found", 404
    )


def _refreshed(record_id):
    return UcrDeclaration.all_objects.select_related("owner").get(pk=record_id)


def promote_to_working(user, record_id):
    """Detach an owned temporary demonstration UCR into a working reference.

    One atomic **conditional update** carries the whole transition: the guard
    matches only a temporary, still-attached, draft record owned by the caller,
    and provenance is captured from the old row inside the same statement
    (``SET reference_source_session = demonstration_session_id,
    demonstration_session_id = NULL``). A concurrent expiry, discard or save
    therefore resolves by PostgreSQL row locking plus EvalPlanQual re-check on
    the UCR row itself — no session-row lock is taken, which removes any
    lock-ordering cycle with the discard path (UCR rows first, session last).
    A guard that matches zero rows is classified by re-reading the record:
    missing/ordinary → not found; already working → idempotent; approved or
    retired → already immutable; submitted → not promotable.
    """
    from hybrid import demonstrations

    _gate()

    def attempt():
        with transaction.atomic():
            updated = UcrDeclaration.all_objects.filter(
                pk=record_id,
                owner=user,
                reference_state=UcrDeclaration.ReferenceState.TEMPORARY,
                demonstration_session_id__isnull=False,
                status=UcrDeclaration.Status.DRAFT,
            ).update(
                reference_state=UcrDeclaration.ReferenceState.WORKING,
                reference_source_session_id=models.F("demonstration_session_id"),
                demonstration_session_id=None,
            )
            if updated == 1:
                return _refreshed(record_id), True

            # The guard matched nothing: classify against current table state.
            record = (
                UcrDeclaration.all_objects.filter(pk=record_id, owner=user).select_related("owner").first()
            )
            if record is None:
                # Missing, ordinary, or no longer attached: answered exactly
                # like an unknown id, never confirmed.
                raise _not_found()
            if record.reference_state == UcrDeclaration.ReferenceState.WORKING:
                return record, False  # repeated request: already promoted
            if record.reference_state in UcrDeclaration.IMMUTABLE_REFERENCE_STATES:
                raise demonstrations.DemonstrationError(
                    "This record is already an approved or retired reference.",
                    "already_a_reference",
                    409,
                )
            if record.status != UcrDeclaration.Status.DRAFT:
                raise demonstrations.DemonstrationError(
                    "A submitted UCR cannot be promoted; copy its values instead.",
                    "not_promotable",
                    400,
                )
            # Temporary but no longer attached (promoted concurrently raced a
            # cleanup): answered exactly like an unknown id, never confirmed.
            raise _not_found()

    from hybrid import demonstrations as demos

    record, _created = demos.retry_on_contention(attempt)
    return record


def approve_reference(user, record_id):
    """Approve a **submitted** working reference; approval freezes it."""
    from hybrid import demonstrations

    _gate()

    def attempt():
        with transaction.atomic():
            record = (
                UcrDeclaration.all_objects.select_for_update()
                .filter(pk=record_id, owner=user, reference_state=UcrDeclaration.ReferenceState.WORKING)
                .first()
            )
            if record is None:
                existing = _owned_reference(user, record_id)
                if existing is not None and existing.reference_state == (
                    UcrDeclaration.ReferenceState.APPROVED
                ):
                    return existing, False  # repeated request: already approved
                raise demonstrations.DemonstrationError(
                    "Only a working reference can be approved.", "not_approvable", 409
                )
            if record.status != UcrDeclaration.Status.SUBMITTED:
                raise demonstrations.DemonstrationError(
                    "Submit the reference UCR before approving it.", "approval_requires_submitted", 400
                )
            updated = UcrDeclaration.all_objects.filter(
                pk=record.pk, reference_state=UcrDeclaration.ReferenceState.WORKING
            ).update(reference_state=UcrDeclaration.ReferenceState.APPROVED)
            if updated != 1:
                raise demonstrations.DemonstrationError(
                    "This reference changed while approving it. Try again.", "not_approvable", 409
                )
            return _refreshed(record.pk), True

    from hybrid import demonstrations as demos

    record, _created = demos.retry_on_contention(attempt)
    return record


def retire_reference(user, record_id):
    """Retire an approved reference: preserved, immutable, purge-excluded."""
    from hybrid import demonstrations

    _gate()

    def attempt():
        with transaction.atomic():
            record = (
                UcrDeclaration.all_objects.select_for_update()
                .filter(pk=record_id, owner=user, reference_state=UcrDeclaration.ReferenceState.APPROVED)
                .first()
            )
            if record is None:
                existing = _owned_reference(user, record_id)
                if existing is not None and existing.reference_state == (
                    UcrDeclaration.ReferenceState.RETIRED
                ):
                    return existing, False  # repeated request: already retired
                raise demonstrations.DemonstrationError(
                    "Only an approved reference can be retired.", "not_retirable", 409
                )
            updated = UcrDeclaration.all_objects.filter(
                pk=record.pk, reference_state=UcrDeclaration.ReferenceState.APPROVED
            ).update(reference_state=UcrDeclaration.ReferenceState.RETIRED)
            if updated != 1:
                raise demonstrations.DemonstrationError(
                    "This reference changed while retiring it. Try again.", "not_retirable", 409
                )
            return _refreshed(record.pk), True

    from hybrid import demonstrations as demos

    record, _created = demos.retry_on_contention(attempt)
    return record

