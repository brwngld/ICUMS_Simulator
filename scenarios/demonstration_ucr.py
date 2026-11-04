"""Exact-session access to demonstration UCR records.

``UcrDeclaration.objects`` already excludes demonstration rows, so an ordinary
simulator query is safe without knowing this module exists. What a filtered
manager *cannot* do is authorize a demonstration query: the scope has to be
named explicitly, and it has to be the session the server resolved — never a
value from the request. Every function here takes a resolved
``DemonstrationSession`` and nothing takes a session id.

Stage 1B adds the one approved write: ``save_demonstration_ucr`` creates or
updates a demonstration draft from the Create UCR form while the browser's
bound session is recording. It reuses the ordinary route's parser and field
application, allocates the ``DEMOUCR`` reference with a savepoint-per-attempt
retry against the unique column, and appends the record event inside the same
transaction, so a failed save can never leave a recorded success behind.
"""
import json
import logging
import time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, InterfaceError, OperationalError, connection, transaction
from django.db.models import Q
from django.http import JsonResponse

from hybrid.models import DemonstrationEvent
from hybrid.verification import driver_sqlstate, is_database_contention

from .models import UcrDeclaration, allocate_ucr_number

#: The temporary-reference namespace for demonstration drafts. Distinct from
#: ``TEMPUCR`` because the allocator's scan and the table-wide unique column
#: must never be able to hand the same number to a learner and a demonstration.
DEMONSTRATION_TEMP_PREFIX = UcrDeclaration.DEMO_TEMP_PREFIX


def demonstration_ucrs(session):
    """This session's UCR records, and only these.

    The unfiltered manager is the point of entry because demonstration rows are
    exactly what the ordinary manager hides; the session filter is what makes it
    safe. ``owner`` is re-checked against the session's instructor so a row that
    was somehow scoped to this session but owned by someone else stays invisible.
    """
    return (
        UcrDeclaration.all_objects.filter(demonstration_session=session, owner=session.instructor)
        .select_related("owner")
        .order_by("-updated_at")
    )


def count_demonstration_ucrs(session):
    return demonstration_ucrs(session).count()


def get_demonstration_ucr(session, record_id):
    """One record by id, inside this session — the ``ucr-detail`` authorization.

    A primary key alone never resolves: a guess, a replayed id, or an ordinary
    learner's record all come back as ``None``.
    """
    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id < 1:
        return None
    return demonstration_ucrs(session).filter(pk=record_id).first()


def demonstration_record_in_session(session, *, record_kind, record_id):
    """Whether ``record_kind``/``record_id`` names a record this session owns."""
    if record_kind != "ucr":
        # Only UCR is in scope for demonstration recording; BOE, MDA and
        # consignment are denied, so no event may claim them.
        return False
    return get_demonstration_ucr(session, record_id) is not None


def delete_demonstration_ucrs(session):
    """Remove this session's records. Ordinary rows cannot be reached.

    Attachments cascade with the record they belong to. Demonstration uploads
    are not enabled, so no stored file is orphaned here; before uploads are
    approved, discard has to collect storage names and delete blobs on commit.
    """
    deleted, _ = demonstration_ucrs(session).delete()
    return deleted


def next_demonstration_temp_no():
    """The next ``DEMOUCR`` reference, allocated against every row in the table."""
    return allocate_ucr_number(DEMONSTRATION_TEMP_PREFIX)


def ordinary_ucr_scope_predicate():
    """The explicit ordinary filter, for querysets that reach a UCR by join.

    A model manager cannot help there: ``UcrDocumentAttachment.objects`` and any
    ``select_related("ucr")`` traverse to the UCR through the base manager, which
    is deliberately unfiltered so foreign keys keep working. A query that starts
    on another model and reads through to a UCR has to name the scope itself.
    """
    return Q(ucr__demonstration_session__isnull=True)


# --- The Stage 1B write: a scoped UCR save -----------------------------------

logger = logging.getLogger(__name__)

#: Attempts to land a free ``DEMOUCR`` reference before the save is refused.
#: The allocator is a read-then-write scan and the unique column is the arbiter,
#: so a lost race is a normal outcome, not an error — but a caller that keeps
#: colliding past this budget is answered with a controlled refusal, never a
#: bare integrity error and never a silently different reference.
REFERENCE_ALLOCATION_ATTEMPTS = 5
REFERENCE_ALLOCATION_BASE_DELAY = 0.02

#: The one ``action_code`` a demonstration save records. The event's
#: ``event_type`` already separates created from updated; the action stays the
#: save the instructor pressed.
UCR_SAVE_ACTION_CODE = "ucr.saved"

#: The provider columns the ordinary parser only fills when the provider section
#: is shown. A demonstration save normalizes a hidden section to blanks rather
#: than inheriting the ordinary route's known ``KeyError`` defect
#: (demonstration-recording-operations.md, open risks).
_PROVIDER_KEYS = ("declarant_code", "code", "name", "country", "address", "contact", "phone", "email", "email_2")


def demonstration_save_applies(request):
    """Whether this ``ucr-save`` POST belongs to a demonstration.

    The flag is the entry gate and the server-side binding is the discriminator:
    a browser either holds a recording (its key is in the Django session) or it
    does not, and an ordinary save never consults either. A key that no longer
    resolves is *not* ordinary traffic either — the strict save refuses it rather
    than silently writing an ordinary row from a browser that believes it is
    demonstrating.
    """
    from hybrid import demonstrations

    if not demonstrations.recording_enabled():
        return False
    return bool(request.session.get(demonstrations.ACTIVE_SESSION_KEY))


def demonstration_create_draft(request, draft_id):
    """The draft a bound browser's Create UCR screen may load, or ``None``.

    Stage 1B.1: after a save the simulator page re-opens with ``?draft=<id>``,
    and that id names a demonstration record the ordinary manager cannot see.
    A bound browser therefore resolves the screen through its session scope
    only — binding, ownership, lesson scope and live state re-derived exactly
    as the save does (``recording`` and ``paused`` both count: GET navigation
    stays available while paused). Anything that does not resolve to this
    session's own draft — an ordinary row, another session's record, an unknown
    id, a binding that no longer resolves — is ``None``, so the screen renders
    as if no draft were named and never confirms a row it cannot see.
    """
    from hybrid import demonstrations

    if not demonstration_save_applies(request):
        return None
    if draft_id is None or not str(draft_id).isdigit():
        return None
    try:
        session = demonstrations.require_bound_session(request)
    except demonstrations.DemonstrationError:
        return None
    record = get_demonstration_ucr(session, int(draft_id))
    if record is not None and record.status != UcrDeclaration.Status.DRAFT:
        return None
    return record


def save_demonstration_ucr(request):
    """The scoped save, answered as JSON; controlled refusals never raise.

    Every rule is re-derived server-side — manifest, binding, ownership, draft
    lesson, ``recording`` state, the idle deadline — before the payload is even
    parsed, exactly as the lifecycle endpoints do. Field errors keep the
    ordinary route's ``{"errors": …}`` shape so the simulator page's own
    handling works unchanged.
    """
    from hybrid import demonstrations

    try:
        return _save_demonstration_ucr(request)
    except demonstrations.DemonstrationError as error:
        return JsonResponse(error.as_json(), status=error.status)
    except (OperationalError, InterfaceError) as error:
        # The last net, as in hybrid.demonstration_views: the service retried its
        # own collisions, so reaching here means a lock surfaced while the
        # request was only reading. Anything else is re-raised, because a
        # swallowed defect looks exactly like a busy server.
        if not is_database_contention(error):
            raise
        logger.warning("Demonstration UCR save met database contention: %s", error)
        busy = demonstrations.DemonstrationError(
            "The demonstration is busy. Try again in a moment.", "session_busy", 503
        )
        return JsonResponse(busy.as_json(), status=busy.status)


def _save_demonstration_ucr(request):
    from hybrid import demonstrations

    demonstrations.assert_route_authorized("ucr-save", "POST")

    # The whole save re-runs when a lock aborts it — the same treatment every
    # lifecycle control gets — because an aborted attempt committed nothing and
    # a retry re-derives the session, the idempotency pre-check and the
    # reference allocation against table truth. The budget's exhaustion is the
    # controlled 503, not a driver exception reaching the browser.
    def attempt():
        session = demonstrations.require_bound_session(request, require_recording=True)
        return _scoped_save(request, session)

    return demonstrations.retry_on_contention(attempt)


def _scoped_save(request, session):
    from hybrid import demonstrations

    parsed, errors = _parsed_payload(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    if request.FILES:
        # Attachments stay out of scope for Stage 1B: no demonstration file is
        # ever written, so no upload can orphan itself against a discard.
        raise demonstrations.DemonstrationError(
            "Attachments cannot be recorded in a demonstration.", "attachment_denied", 400
        )

    key = demonstrations.client_idempotency_key(_request_idempotency_key(request))

    # A repeated request answers with the record its key already saved: no
    # second row, no second event, no second reference burned.
    record, event = _record_for_key(session, key)
    if record is not None:
        return _saved_response(record, event)

    draft_id = parsed.get("draft_id")
    target = None
    if draft_id is not None:
        target = get_demonstration_ucr(session, draft_id)
        if target is None:
            # An ordinary draft of one's own, another session's record, or an
            # unknown id — all the same refusal. A demonstration save never
            # falls through to an ordinary write.
            raise demonstrations.DemonstrationError(
                "This declaration is not available for this operation.", "record_out_of_scope", 403
            )
        if target.status != UcrDeclaration.Status.DRAFT:
            raise demonstrations.DemonstrationError("This UCR has already been submitted.", "already_submitted", 400)

    try:
        with transaction.atomic():
            if target is None:
                record = _insert_scoped_record(session, parsed)
                event_type = DemonstrationEvent.EventType.RECORD_CREATED
                payload = {"regime_code": parsed["regime"], "result_status": "saved"}
            else:
                record = target
                before = {name: getattr(record, name) for name in demonstrations.DEMONSTRATION_UCR_FIELDS}
                _apply_payload(record, parsed)
                record.save()
                event_type = DemonstrationEvent.EventType.RECORD_UPDATED
                payload = {"regime_code": parsed["regime"], "result_status": "updated"}
                changed = sorted(name for name, value in before.items() if value != getattr(record, name))
                if changed:
                    payload["changed_fields"] = changed
            event = demonstrations.append_record_event(
                request,
                event_type=event_type,
                record_kind="ucr",
                record_id=record.pk,
                action_code=UCR_SAVE_ACTION_CODE,
                payload=payload,
                idempotency_key=key,
            )
            if event.record_id != record.pk:
                # This key was claimed by a concurrent twin while this attempt
                # wrote its own row. The twin's record is the answer; the
                # duplicate this attempt wrote must not survive the request.
                transaction.set_rollback(True)
                raise _KeyClaimed(event)
    except _KeyClaimed as claimed:
        record = get_demonstration_ucr(session, claimed.event.record_id)
        if record is None:
            raise demonstrations.DemonstrationError(
                "That record does not belong to this demonstration.", "record_out_of_scope", 403
            ) from None
        event = claimed.event
    return _saved_response(record, event)


class _KeyClaimed(Exception):
    """Control flow only: the idempotency key belonged to an earlier save."""

    def __init__(self, event):
        super().__init__(event)
        self.event = event


def _parsed_payload(request):
    """The ordinary route's own validation and normalization, untouched."""
    from .views import _parse_ucr_payload

    return _parse_ucr_payload(request)


def _apply_payload(record, parsed):
    """The ordinary route's field application, with the hidden-provider shape."""
    from .views import _apply_ucr_payload

    if not parsed["show_provider"]:
        parsed = {**parsed, "provider": {key: "" for key in _PROVIDER_KEYS}}
    _apply_ucr_payload(record, parsed)


def _request_idempotency_key(request):
    """The save's retry key: a form field beside the payload, or a JSON body key.

    Absent means a fresh key for a fresh action, exactly like the lifecycle
    endpoints; a malformed supplied key is refused, never replaced. The body
    fallback is JSON-only: a multipart stream is consumed by ``request.POST``
    during payload parsing, and touching ``request.body`` afterwards raises —
    the browser always posts multipart, so this is the shape that matters.
    """
    value = request.POST.get("idempotency_key")
    if value in (None, "") and not (request.content_type or "").startswith("multipart/form-data"):
        try:
            body = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
            body = None
        if isinstance(body, dict):
            value = body.get("idempotency_key")
    return value


def _record_for_key(session, key):
    """The record a previous save with this key produced, with its event."""
    event = DemonstrationEvent.objects.filter(
        session=session,
        idempotency_key=key,
        event_type__in=(DemonstrationEvent.EventType.RECORD_CREATED, DemonstrationEvent.EventType.RECORD_UPDATED),
        record_id__isnull=False,
    ).first()
    if event is None:
        return None, None
    return get_demonstration_ucr(session, event.record_id), event


def _insert_scoped_record(session, parsed):
    """Create the demonstration draft, allocating its reference with bounded retries.

    Each attempt owns a savepoint: under READ COMMITTED two callers can be
    handed the same candidate and the loser finds out only when its ``INSERT``
    hits the table-wide unique column. That error aborts a PostgreSQL
    transaction, so it must roll back only this attempt; the retry re-runs the
    allocator against table truth and can never re-present the conflicting
    reference. No row lock is taken around the scan — a new row has nothing to
    lock, and locking ``UcrDeclaration`` rows would contend with the lifecycle
    transitions for no protection the unique index does not already give.
    """
    from hybrid import demonstrations

    for attempt in range(REFERENCE_ALLOCATION_ATTEMPTS):
        try:
            with transaction.atomic():
                record = UcrDeclaration(owner=session.instructor, demonstration_session=session)
                _apply_payload(record, parsed)
                record.temp_no = allocate_ucr_number(UcrDeclaration.DEMO_TEMP_PREFIX)
                record.save()
                return record
        except IntegrityError as error:
            if not _is_reference_conflict(error):
                raise
        except ValidationError:
            # The allocator's own bounded scan came up empty; give it another
            # turn rather than surfacing its message as a 500.
            pass
        if attempt + 1 < REFERENCE_ALLOCATION_ATTEMPTS:
            time.sleep(REFERENCE_ALLOCATION_BASE_DELAY * (attempt + 1))
    raise demonstrations.DemonstrationError(
        "Could not allocate the next reference number. Please try again.", "reference_busy", 503
    )


def _is_reference_conflict(error):
    """Whether this integrity error is the unique column refusing a duplicate.

    Classified by the driver's own SQLSTATE first (PostgreSQL 23505, named for
    this table's reference columns), with SQLite's message wording as the
    fallback — never a broad "any unique error" that could swallow a genuinely
    unexpected constraint.
    """
    message = str(error).lower()
    if driver_sqlstate(error) == "23505":
        return "scenarios_ucrdeclaration" in message and ("temp_no" in message or "ucr_no" in message)
    if connection.vendor == "sqlite":
        return "unique constraint failed" in message and "scenarios_ucrdeclaration.temp_no" in message
    return False


def _saved_response(record, event):
    """The shape the simulator page already reads, plus what was recorded.

    ``demonstration`` is what the page's script reads to keep its message and
    its Submit affordance honest inside a recording: a demonstration save is
    save-only — there is no submission to instruct about and no button to
    enable.
    """
    return JsonResponse(
        {
            "id": record.pk,
            "temp_no": record.temp_no,
            "status": record.status,
            "attachments": [],
            "demonstration": True,
            "recorded": {
                "event_id": str(event.pk),
                "sequence": event.sequence,
                "action_code": event.action_code,
            },
        }
    )
