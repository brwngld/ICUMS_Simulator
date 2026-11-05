"""Server-side foundation for instructor demonstration recording.

A demonstration is an instructor driving the real simulator while a lesson is
still a draft. Its two products — an event stream and any records the instructor
makes — must never be mistaken for a learner's work, so everything here is built
around one rule: **the browser holds a session UUID and nothing else.** Every
control re-derives the session, its owner and its lesson from the database, and
an event carries only codes drawn from the allowlists below.

What "authorized" means for a demonstration write — the Stage 1B contract,
already enforced here for every entry point:

1. server-side binding — the session UUID comes from the Django session, written
   by ``start_recording``; a UUID in the request body is cross-checked, never trusted;
2. instructor identity — the session row must belong to ``request.user``;
3. lesson scope — the demonstrated lesson must still be a draft edition;
4. lifecycle state — ``recording`` accepts events, ``paused`` and ``stopped``
   accept none, ``discarded`` accepts nothing;
5. explicit route/action permission — ``DEMONSTRATION_ROUTE_PERMISSIONS`` is an
   allowlist of route *names* and methods, and anything absent from it is refused.

``Sec-Fetch-Dest`` deliberately plays no part: it records how a document was
arrived at, not who may act, and a same-origin request from the studio's own page
reports ``empty`` rather than ``iframe``. ``DEMONSTRATION_RECORDING_ENABLED`` is
an entry gate for the endpoints only — it can close a door, never widen one,
because the service below re-checks identity, scope and state on every call.

Ordering does not use ``select_for_update``: SQLite accepts the call and ignores
it, so a row lock here would look like a guarantee while being a no-op. The
sequence counter moves with a conditional update that both engines enforce, and
the unique constraints on ``(session, sequence)`` and
``(session, idempotency_key)`` are the final guard.
"""
import logging
import re
import time
import uuid
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, InterfaceError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone

from onboarding.models import ProgrammeVersion
from scenarios.bindings import VERIFY_RECORDS, checkable_fields

from .models import DemonstrationEvent, DemonstrationSession
from .verification import is_database_contention

logger = logging.getLogger(__name__)

#: Key holding the active demonstration session's UUID in the Django session.
ACTIVE_SESSION_KEY = "hybrid_demonstration_session_id"

#: Stage 2F: the instructor's selected reference UCR and what it is for. Both
#: live in the Django session store — no schema change — and every read
#: re-resolves the record against the instructor-owned demonstration scope
#: (``scenarios.demonstration_ucr.selected_reference``), so the identifier
#: stored here authorizes nothing by itself.
REFERENCE_KEY = "hybrid_demonstration_reference_ucr_id"
REFERENCE_INTENT_KEY = "hybrid_demonstration_reference_intent"

#: Days a stopped session's records and events survive. Stamped at stop time so
#: a later change to this constant cannot move an existing deadline.
RETENTION_DAYS = 30

#: How long a recording may sit untouched before the server seals it. A live
#: session is the one slot its instructor holds — ``start_recording`` refuses a
#: second while any live session exists, and a database constraint enforces the
#: same rule — so an abandoned recording is also an instructor locked out of their
#: own Studio. Sealing, not deleting: the timeline stays reviewable and the normal
#: retention clock starts at the seal.
#:
#: The window is measured from ``last_activity_at``, which only a deliberate
#: instructor action moves — a control pressed or an event recorded. The Studio's
#: own polling reads (``resolve_bound_session``, ``session_payload``, ``timeline``)
#: never touch it, because a page left open on a browser is not someone working.
INACTIVITY_TIMEOUT = timedelta(minutes=30)

SEQUENCE_RETRY_ATTEMPTS = 5
SEQUENCE_RETRY_BASE_DELAY = 0.01

#: Attempts against a database that refused a statement because of a lock rather
#: than because of anything the instructor did. Small and fixed: contention under
#: one instructor's own two browsers clears in a moment, and anything still
#: colliding after four tries is a server problem worth reporting as one.
CONTENTION_RETRY_ATTEMPTS = 4
CONTENTION_RETRY_BASE_DELAY = 0.02

#: States a live binding may sit in. Taken from the model so this module and the
#: database's conditional unique constraint cannot disagree.
LIVE_STATES = DemonstrationSession.LIVE_STATES

#: Every stored value is a *code*: a route name, an action, a regime, a column
#: name. The shape is the enforcement — a name, an address, an email or a goods
#: description contains spaces or punctuation a token cannot match, so free text
#: fails closed even when a caller slips it under an approved key.
_SAFE_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}")
_SAFE_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,23}")


class DemonstrationError(Exception):
    """A controlled refusal: ``code`` is machine-readable, ``status`` the HTTP
    code the endpoint reports, ``message`` safe to show the instructor."""

    def __init__(self, message, code, status=409):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status

    def as_json(self):
        return {"ok": False, "error": self.message, "code": self.code}


# --- Route and action manifest ----------------------------------------------

#: Route names a demonstration may address, with the methods allowed. This is
#: the approval record for Stage 1B: a route gains a write method only here.
#: ``ucr-save`` carries ``POST`` now that a scoped save service exists
#: (``scenarios.demonstration_ucr.save_demonstration_ucr``) — it is the only
#: write any demonstration may make, and it stays gated behind the binding,
#: the lifecycle state and the idle deadline. ``ucr-submit``, clone, amend,
#: attachments, BOE, MDA and consignment are absent, so they are refused by
#: construction rather than by memory.
DEMONSTRATION_ROUTE_PERMISSIONS = {
    "simulator-portal": frozenset({"GET"}),
    "single-window-overview": frozenset({"GET"}),
    "single-window-create-ucr": frozenset({"GET"}),
    "single-window-search-ucr": frozenset({"GET"}),
    "ucr-detail": frozenset({"GET"}),
    "ucr-service-provider-lookup": frozenset({"GET"}),
    "ucr-stakeholder-lookup": frozenset({"GET"}),
    "ucr-save": frozenset({"POST"}),
}

#: Approved ``action_code`` per navigable route. A route absent here is allowed
#: but produces no event, rather than inventing a code for it.
DEMONSTRATION_NAVIGATION_ACTIONS = {
    "simulator-portal": "portal.opened",
    "single-window-overview": "single_window.opened",
    "single-window-create-ucr": "ucr.create_form_opened",
    "single-window-search-ucr": "ucr.search_opened",
    "ucr-detail": "ucr.detail_opened",
}

#: Payload keys per event type, and nothing else. ``selection`` is not a declared
#: event type at all: field-level capture is a later stage.
DEMONSTRATION_EVENT_PAYLOAD_KEYS = {
    DemonstrationEvent.EventType.NAVIGATION: frozenset({"result_status"}),
    DemonstrationEvent.EventType.RECORD_CREATED: frozenset({"regime_code", "transport_mode_code", "result_status"}),
    DemonstrationEvent.EventType.RECORD_UPDATED: frozenset({"changed_fields", "regime_code", "result_status"}),
}

#: Outcomes a recording may report. Anything else — including a validation
#: message — is refused, so no server-generated text can reach a payload.
DEMONSTRATION_RESULT_STATUSES = frozenset({"opened", "saved", "updated"})

#: UCR columns a demonstration may name as having changed. The registry the
#: verification engine already uses, so the two never drift apart.
DEMONSTRATION_UCR_FIELDS = frozenset(name for name, _label, _kind in checkable_fields("ucr"))


def recording_enabled():
    """The entry gate. Default-off, and never a substitute for authorization."""
    from django.conf import settings

    return bool(getattr(settings, "DEMONSTRATION_RECORDING_ENABLED", False))


# --- Identity ----------------------------------------------------------------


def authorized_instructor(user):
    """The Studio's own rule: superuser, or a member of Instructor/Administrator.

    The canonical gate lives with the instructor portal and is reused rather than
    restated, because the simulator's broader author check also admits bare
    ``is_staff`` — and staff browsing is not authority to open a recording.
    """
    from instructor_portal.views import _require_instructor

    if not user.is_authenticated:
        raise PermissionDenied("Instructor access is required.")
    _require_instructor(user)


def _as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (AttributeError, TypeError, ValueError):
        return None


def _idempotency_key(value):
    """The caller's retry key, or a fresh one when they sent none.

    A supplied key that is not a UUID is refused, not quietly replaced: a client
    that mangles its own key would otherwise get a second event where it meant a
    retry, and the duplicate would look like a repeated action in the timeline.
    """
    if value is None or value == "":
        return uuid.uuid4()
    parsed = _as_uuid(value)
    if parsed is None:
        raise DemonstrationError("The demonstration idempotency key must be a UUID.", "idempotency_key_invalid", 400)
    return parsed


#: Public form of ``_idempotency_key`` for the scoped save service
#: (``scenarios.demonstration_ucr``), which has to resolve the caller's key
#: *before* it writes so a repeated request reuses the record already saved.
client_idempotency_key = _idempotency_key


# --- Contention --------------------------------------------------------------


def _retry_on_contention(operation, *, attempts=CONTENTION_RETRY_ATTEMPTS):
    """Run ``operation`` again while the database says the reason was a collision.

    Each attempt re-runs the *whole* operation, so a conditional update re-reads
    the row instead of replaying a value the winner already moved. ``operation``
    must open its own transaction: a PostgreSQL lock error aborts the transaction
    it happened in, so retrying inside a caller's atomic block would only fail
    again — and when the budget runs out the caller gets a controlled refusal
    rather than a driver exception escaping as an HTTP 500.
    """
    for attempt in range(attempts):
        try:
            return operation()
        except (OperationalError, InterfaceError) as error:
            if not is_database_contention(error):
                raise
            _sleep_before(attempt, delay=CONTENTION_RETRY_BASE_DELAY, attempts=CONTENTION_RETRY_ATTEMPTS)
    raise DemonstrationError("The demonstration is busy. Try again in a moment.", "session_busy", 503)


def _sleep_before(retry_index, *, delay=SEQUENCE_RETRY_BASE_DELAY, attempts=SEQUENCE_RETRY_ATTEMPTS):
    """Back off, but not after the attempt that will be the last one."""
    if retry_index + 1 < attempts:
        time.sleep(delay * (retry_index + 1))


#: Public form of ``_retry_on_contention`` for the scoped save service
#: (``scenarios.demonstration_ucr``): a demonstration save is a write like any
#: lifecycle control, so a lock that aborts its transaction is retried whole
#: before the request is answered with a controlled 503.
retry_on_contention = _retry_on_contention


# --- Binding -----------------------------------------------------------------


def bind_request(request, session):
    """Record the server-resolved session as this browser's active recording."""
    request.session[ACTIVE_SESSION_KEY] = str(session.pk)


def unbind_request(request):
    request.session.pop(ACTIVE_SESSION_KEY, None)


def _clear_reference(request):
    """Stage 2F.1: the reference selection is a recording-time convenience.

    It never outlives the recording it was made in — a new recording must begin
    with an explicit reference choice, so no lesson can silently inherit the
    previous lesson's reference. Cleared only after a lifecycle operation has
    actually succeeded; a refused start, stop or discard leaves the instructor's
    selection exactly as it was.
    """
    from scenarios.demonstration_ucr import clear_reference

    clear_reference(request)


def set_reference_selection(request, record_id, intent):
    """Stage 2F: remember the instructor's reference choice in their session."""
    request.session[REFERENCE_KEY] = int(record_id)
    request.session[REFERENCE_INTENT_KEY] = intent


def clear_reference_selection(request):
    request.session.pop(REFERENCE_KEY, None)
    request.session.pop(REFERENCE_INTENT_KEY, None)


def reference_selection(request):
    """The stored ``(record_id, intent)``, or ``None``."""
    record_id = request.session.get(REFERENCE_KEY)
    intent = request.session.get(REFERENCE_INTENT_KEY)
    if record_id is None or intent is None:
        return None
    return record_id, intent


def resolve_bound_session(request):
    """This request's live demonstration session, or ``None``.

    Ownership is a database fact (``instructor=request.user``), the state and the
    lesson are re-read on every call, and a binding that no longer resolves is
    dropped so a stale cookie cannot be replayed against someone else's session.
    """
    bound = _as_uuid(request.session.get(ACTIVE_SESSION_KEY, ""))
    if bound is None:
        return None

    def select():
        return DemonstrationSession.objects.filter(
            pk=bound, instructor=request.user
        ).select_related("lesson__module__course__programme_version").first()

    # A read is retried too: under PostgreSQL a plain SELECT can still wait on a
    # lock held by the writer that took the row over, and an instructor whose own
    # two browsers are racing should not get a page that failed for that reason.
    session = _retry_on_contention(select)
    if session is None or not session.live() or not lesson_is_draft(session):
        unbind_request(request)
        return None
    return session


def lesson_is_draft(session):
    return session.lesson.module.course.programme_version.status == ProgrammeVersion.Status.DRAFT


def require_bound_session(request, session_id=None, *, require_recording=False):
    """The bound session, or a refusal an endpoint can hand straight to the browser."""
    session = resolve_bound_session(request)
    if session is None:
        raise DemonstrationError("No demonstration session is active for this instructor.", "no_active_session")
    if session_id is not None and _as_uuid(session_id) != session.pk:
        # The browser named a session it does not hold: a guessed, replayed or
        # simply wrong UUID. Never honored, even when it exists and is live.
        raise DemonstrationError("That demonstration session is not the one active in this browser.", "session_mismatch")
    if require_recording and session.state != DemonstrationSession.State.RECORDING:
        raise DemonstrationError("This demonstration session is not recording.", "session_not_recording")
    _refuse_if_idle(request, session)
    return session


# --- Inactivity --------------------------------------------------------------


def _is_idle(session, moment=None, timeout=INACTIVITY_TIMEOUT):
    """Has this live recording gone past the inactivity window?

    Measured from ``last_activity_at``, never from ``updated_at``: the row's
    automatic stamp also moves on a rename or a counter write, and the counter
    writes are what the sweep is deciding about.
    """
    if not session.live():
        return False
    return (moment or timezone.now()) - session.last_activity_at >= timeout


def seal_abandoned_session(session, now=None, *, timeout=INACTIVITY_TIMEOUT):
    """Close a recording nobody touched for the whole window.

    Sealing *is* a stop, so nothing new becomes reviewable or expirable here: the
    timeline stands, the records stand, ``retention_expires_at`` starts its thirty
    days from the seal, and the conditional unique constraint releases the
    instructor's one live-session slot. The seal is not instructor activity, so
    ``last_activity_at`` stays where the abandoned run left it — that gap between
    it and ``stopped_at`` is what tells a lapsed recording from a stopped one
    without a second state or a reason column.

    Returns the sealed session, or ``None`` when it was still current or when a
    concurrent control moved it first. A sweep is never in a race to win.
    """
    moment = now or timezone.now()
    if not _is_idle(session, moment, timeout):
        return None
    try:
        _transition(
            session,
            from_state=session.state,
            to_state=DemonstrationSession.State.STOPPED,
            expected_version=session.version,
            stamps={
                "stopped_at": moment,
                "retention_expires_at": moment + timedelta(days=RETENTION_DAYS),
            },
            stamp_activity=False,
        )
    except DemonstrationError:
        return None
    return _reload(session.pk)


def seal_abandoned_sessions(now=None, *, timeout=INACTIVITY_TIMEOUT):
    """Seal every abandoned recording on the clock — the sweep the command runs.

    A browser that was simply closed sends nothing more, so this is the only
    mechanism that reaches those; an instructor who comes back to a live-but-idle
    session is refused by ``_refuse_if_idle`` on their first control instead. Both
    paths call the same predicate on the same column, so the deadline cannot be
    met one way and missed another.
    """
    moment = now or timezone.now()
    abandoned = list(
        DemonstrationSession.objects.filter(
            state__in=LIVE_STATES, last_activity_at__lt=moment - timeout
        ).order_by("last_activity_at")
    )
    sealed = 0
    for session in abandoned:
        if seal_abandoned_session(session, moment, timeout=timeout) is not None:
            sealed += 1
    return sealed


#: What the browser is told when the window has passed. Both paths — the sweep
#: that already closed the session and the control that closes it now — report the
#: same code and the same sentence, so a late click and a polled page agree.
IDLE_MESSAGE = (
    "Recording stopped automatically after 30 minutes of inactivity. "
    "Your recorded activity has been preserved."
)


def _refuse_if_idle(request, session):
    """Enforce the deadline where an action is being authorized.

    A control pressed after the window is not a late keystroke on the old
    recording, it is the beginning of a new one, so the session is sealed, the
    binding dropped and the instructor asked to start again. ``live_session_for``
    reads ``recording`` and ``paused`` under one predicate, and this is reached
    from both, so the two live states lapse exactly alike.
    """
    if not _is_idle(session):
        return
    # Best effort: a sweep already running has the same outcome, and a control
    # that lost the race is the winner's answer anyway.
    seal_abandoned_session(session)
    unbind_request(request)
    _clear_reference(request)
    raise DemonstrationError(IDLE_MESSAGE, "session_idle", 409)


# --- Lifecycle ---------------------------------------------------------------


def live_session_for(user):
    """The instructor's current recording or pause, if they hold one."""

    def select():
        return DemonstrationSession.objects.filter(
            instructor=user, state__in=LIVE_STATES
        ).order_by("-started_at").first()

    return _retry_on_contention(select)


def lesson_is_recording(lesson_ids):
    """Whether any of these lessons holds a recording or pause in progress.

    Deleting an authorised draft lesson cascades to its session, its events and
    any scoped records, so the builder asks this before removing a lesson or a
    module that contains one. The answer is a boolean on purpose: the builder is
    told the lesson is in use, never by whom.

    A database too busy to answer is not permission to delete, so exhaustion of
    the contention budget answers ``True`` (the builder's refusal) instead of
    raising: the delete fails closed and the instructor can try again.
    """
    ids = list(lesson_ids)

    def ask():
        return DemonstrationSession.objects.filter(
            lesson_id__in=ids, state__in=LIVE_STATES
        ).exists()

    try:
        return _retry_on_contention(ask)
    except DemonstrationError:
        logger.warning(
            "Could not confirm whether lessons %s hold a live recording; refusing the delete.",
            ids,
        )
        return True


def start_recording(request, lesson):
    """Open a recording for this instructor's draft lesson and bind it to the browser."""
    authorized_instructor(request.user)
    if lesson.module.course.programme_version.status != ProgrammeVersion.Status.DRAFT:
        raise DemonstrationError(
            "A demonstration needs a lesson in a draft programme edition.", "lesson_not_draft", 403
        )
    held = live_session_for(request.user)
    if held is not None and seal_abandoned_session(held) is not None:
        # The recording nobody came back to is closed by this call, so the slot it
        # held is the instructor's again. Nothing was deleted: the abandoned
        # timeline stays reviewable until its own retention deadline.
        held = None
    if held is not None:
        # Refused rather than silently replaced: a still-current session may hold
        # records the instructor still means to review.
        raise DemonstrationError(
            "You already have a demonstration in progress. Stop or discard it before recording another lesson.",
            "session_active",
        )
    def attempt():
        # Each attempt owns its transaction: the conditional unique constraint is
        # the arbiter between two browsers starting at one instant, and its
        # IntegrityError has to roll the loser's row back before it is classified.
        with transaction.atomic():
            return DemonstrationSession.objects.create(
                lesson=lesson,
                instructor=request.user,
                state=DemonstrationSession.State.RECORDING,
                started_at=timezone.now(),
            )

    try:
        session = _retry_on_contention(attempt)
    except IntegrityError as exc:
        if not _is_live_session_conflict(exc):
            raise
        # Two browsers started at the same instant; the conditional unique
        # constraint is the arbiter, and the loser gets the same refusal.
        raise DemonstrationError(
            "You already have a demonstration in progress. Stop or discard it before recording another lesson.",
            "session_active",
        ) from exc
    bind_request(request, session)
    # Stage 2F.1: a new recording begins with an explicit reference choice —
    # no lesson can silently inherit the previous recording's reference.
    _clear_reference(request)
    return session


def _is_live_session_conflict(exc):
    message = str(exc).lower()
    return (
        "one_live_demonstration_session_per_instructor" in message
        or "hybrid_demonstrationsession.instructor_id" in message
    )


def pause_recording(request, session_id=None, expected_version=None):
    """Stop capture, keep the browser's place. GET navigation stays available."""
    session = require_bound_session(request, session_id)
    _transition(
        session,
        from_state=DemonstrationSession.State.RECORDING,
        to_state=DemonstrationSession.State.PAUSED,
        expected_version=expected_version,
        stamps={"paused_at": timezone.now()},
    )
    return _reload(session.pk)


def resume_recording(request, session_id=None, expected_version=None):
    """Reopen the same session. Sequence numbering continues from where it was."""
    session = require_bound_session(request, session_id)
    _transition(
        session,
        from_state=DemonstrationSession.State.PAUSED,
        to_state=DemonstrationSession.State.RECORDING,
        expected_version=expected_version,
        stamps={},
    )
    return _reload(session.pk)


def stop_recording(request, session_id=None, expected_version=None):
    """Seal the stream. Records and events stay owner-reviewable until they expire."""
    session = require_bound_session(request, session_id)
    now = timezone.now()
    _transition(
        session,
        from_state=session.state,
        to_state=DemonstrationSession.State.STOPPED,
        expected_version=expected_version,
        stamps={"stopped_at": now, "retention_expires_at": now + timedelta(days=RETENTION_DAYS)},
    )
    unbind_request(request)
    _clear_reference(request)
    return _reload(session.pk)


def _transition(session, *, from_state, to_state, expected_version, stamps, stamp_activity=True):
    """One state change, guarded by the version the caller last saw.

    The conditional update is the whole check: an intervening control, a second
    tab, or a stale version means zero rows match and the caller gets a refusal
    instead of a silently overwritten state. ``paused_at`` is left as history on
    a resumed session — the model only requires the stamp while paused.

    ``stamp_activity`` separates an action from a decision: a control the
    instructor pressed moves ``last_activity_at``, the seal the server applies for
    them must not, or an abandoned recording would look current at the moment it
    was closed.

    ``_retry_on_contention`` covers the other way a zero-row update can arrive —
    the database refusing the statement rather than rejecting the predicate. On
    PostgreSQL an ``UPDATE`` on a row another transaction holds waits for it, then
    re-evaluates its own ``WHERE`` against the committed row, so a genuine lost
    race still ends in ``stale_session``; a lock timeout or deadlock is the part
    worth running again. Each attempt owns its transaction, because a lock error
    aborts the one it happened in.
    """
    version = _version(expected_version)
    condition = {"pk": session.pk, "instructor_id": session.instructor_id, "state": from_state, "version": version}
    updates = {**stamps, "state": to_state, "version": F("version") + 1}
    if stamp_activity:
        updates["last_activity_at"] = timezone.now()

    def attempt():
        with transaction.atomic():
            if DemonstrationSession.objects.filter(**condition).update(**updates) != 1:
                raise DemonstrationError(
                    "This demonstration session changed since your last action. Reload the studio and try again.",
                    "stale_session",
                )

    _retry_on_contention(attempt)


def _version(expected_version):
    try:
        version = int(expected_version)
    except (TypeError, ValueError):
        raise DemonstrationError("The demonstration session version is missing.", "version_required") from None
    if version < 1:
        raise DemonstrationError("The demonstration session version is missing.", "version_required")
    return version


def _reload(session_pk):
    return DemonstrationSession.objects.get(pk=session_pk)


# --- Discard and retention ---------------------------------------------------


def discard_recording(request, session_id):
    """Remove a session's events and demonstration records at once.

    Allowed from any state that still holds data — recording, paused or stopped —
    and only by the owner. The session row survives as a discarded tombstone with
    its timestamps and a thirty-day deadline on it, so the record of there having
    been a recording expires on the same schedule as a stopped one's data. Ordinary
    records cannot be reached: both deletes are constrained to rows naming this
    session.
    """
    authorized_instructor(request.user)
    bound = _as_uuid(session_id)
    if bound is None:
        raise DemonstrationError("No such demonstration session.", "session_gone")
    session = DemonstrationSession.objects.filter(pk=bound, instructor=request.user).first()
    if session is None:
        raise DemonstrationError("No such demonstration session.", "session_gone")
    if session.state == DemonstrationSession.State.DISCARDED:
        unbind_request(request)
        _clear_reference(request)
        return session
    moment = timezone.now()

    def attempt():
        with transaction.atomic():
            DemonstrationEvent.objects.filter(session=session).delete()
            _delete_demonstration_records(session)
            updated = DemonstrationSession.objects.filter(
                pk=session.pk, instructor=request.user, state=session.state
            ).update(
                state=DemonstrationSession.State.DISCARDED,
                discarded_at=moment,
                last_activity_at=moment,
                # The tombstone goes on the same clock a stop puts the data on.
                # Before this it was stamped ``None`` and never collected, so every
                # discard an instructor ever made stood in the table forever; the
                # data under it is already gone, so what expires now is metadata only.
                retention_expires_at=moment + timedelta(days=RETENTION_DAYS),
                version=F("version") + 1,
            )
            if updated != 1:
                raise DemonstrationError("This demonstration session changed since your last action.", "stale_session")

    _retry_on_contention(attempt)
    unbind_request(request)
    _clear_reference(request)
    return _reload(session.pk)


def expire_demonstrations(now=None):
    """Delete sealed sessions whose retention deadline has arrived.

    Both terminal shapes are collected, because both are now on a clock. A stopped
    or inactivity-sealed session still holds its events and demonstration records,
    and the cascade takes them with the row. A discarded one holds only metadata —
    discard deletes the data underneath it at once — so collecting the tombstone is
    what stops abandoned rows accumulating forever.

    The deadline is the fact, not a recomputation: ``stop_recording`` and
    ``seal_abandoned_session`` stamp ``retention_expires_at`` from the window in force at
    that moment, so a later change to ``RETENTION_DAYS`` cannot move an existing
    session's expiry. A session with no deadline — a recording or a pause — is never
    collected, and an instructor may have a browser open on one. Ordinary records are
    unreachable: the cascade only follows rows that name the session, and the
    queryset selects demonstration sessions by state and deadline alone.

    Idempotent, and one session the database will not release does not stop the run:
    a lock that outlasts the retry budget is logged and left for the next sweep.
    """
    moment = now or timezone.now()
    expired = list(
        DemonstrationSession.objects.filter(
            state__in=(DemonstrationSession.State.STOPPED, DemonstrationSession.State.DISCARDED),
            retention_expires_at__isnull=False,
            retention_expires_at__lte=moment,
        )
    )
    removed = 0
    for session in expired:
        def drop(target=session):
            """Delete one expired session and its temporary content.

            Stage R4-B correction: the children are deleted by explicit
            **conditional** statements instead of the collector's gathered
            primary keys, so a UCR promoted while this sweep was running —
            whose primary key may already have been collected — is re-checked
            at delete time and skipped rather than destroyed by pk:

            1. events of this session (no downstream references),
            2. UCRs **still attached** to this session (``_delete_
               demonstration_records`` filters ``demonstration_session`` and
               the owner, so a row a concurrent promotion detached —
               ``reference_state = working`` and the FK set NULL — no longer
               matches and survives),
            3. the session row itself, whose remaining cascade children are
               none: the promoted reference's ``reference_source_session``
               uses ``SET_NULL``.
            """
            with transaction.atomic():
                DemonstrationEvent.objects.filter(session=target).delete()
                _delete_demonstration_records(target)
                target.delete()

        try:
            _retry_on_contention(drop)
        except DemonstrationError as refusal:
            logger.warning("Demonstration %s not expired yet (%s); the next sweep will try again.", session.pk, refusal.code)
            continue
        removed += 1
    return removed


def _delete_demonstration_records(session):
    from scenarios.demonstration_ucr import delete_demonstration_ucrs

    delete_demonstration_ucrs(session)


# --- Event capture -----------------------------------------------------------


def append_navigation_event(request, *, route_name, idempotency_key=None, result_status="opened"):
    """One approved screen reached inside the bound recording."""
    if route_name not in DEMONSTRATION_NAVIGATION_ACTIONS:
        raise DemonstrationError(
            "This simulator screen is not part of the approved demonstration workflow.", "route_denied", 403
        )
    assert_route_authorized(route_name, "GET")
    session = require_bound_session(request, require_recording=True)
    return _append(
        session,
        event_type=DemonstrationEvent.EventType.NAVIGATION,
        action_code=DEMONSTRATION_NAVIGATION_ACTIONS[route_name],
        route_name=route_name,
        payload={"result_status": _result_status(result_status)},
        idempotency_key=idempotency_key,
    )


def navigation_is_current_screen(session, route_name):
    """Whether ``route_name`` is already the screen this recording is on.

    The frame can request the same screen twice in a row — a refresh, a redirect
    that lands where it started — and the timeline must not grow for it. The
    recording's *last* navigation decides: the same screen asked for again is
    the same logical navigation, while leaving and returning is a real one. The
    destination is compared at screen level (the route name), because that is
    what a navigation event records — never the query string behind it.
    """
    last = DemonstrationEvent.objects.filter(
        session=session, event_type=DemonstrationEvent.EventType.NAVIGATION,
    ).order_by("-sequence").first()
    return last is not None and last.route_name == route_name


def append_record_event(
    request, *, event_type, record_kind, record_id, action_code, payload, idempotency_key=None
):
    """One demonstration record the server just saved, inside the caller's transaction.

    The record reference is checked against the session that owns it, so a caller
    cannot attach an event to another instructor's record — or to a learner's.
    """
    session = require_bound_session(request, require_recording=True)
    from scenarios.demonstration_ucr import demonstration_record_in_session

    if not demonstration_record_in_session(session, record_kind=record_kind, record_id=record_id):
        raise DemonstrationError("That record does not belong to this demonstration.", "record_out_of_scope", 403)
    return _append(
        session,
        event_type=event_type,
        action_code=action_code,
        record_kind=record_kind,
        record_id=record_id,
        payload=payload,
        idempotency_key=idempotency_key,
    )


def _append(
    session, *, event_type, action_code, payload, idempotency_key=None, route_name="", record_kind="", record_id=None
):
    """Reserve the next sequence and write the event — or return the retried one.

    Counter and event commit together or not at all, so a rolled-back write
    leaves no success event. A duplicate idempotency key rolls the reservation
    back and hands the caller the event that was already written, so a client
    that lost its response can retry without creating a phantom action or burning
    a sequence number. A collision on the counter — a moved row, a lock, or two
    reservations that reached the same number — restarts the whole operation, and
    the budget ends in a controlled refusal rather than a driver exception.
    """
    key = _idempotency_key(idempotency_key)
    fields = _validated(
        event_type=event_type,
        action_code=action_code,
        route_name=route_name,
        record_kind=record_kind,
        record_id=record_id,
        payload=payload,
    )
    state = session.state
    moment = timezone.now()
    for retry_index in range(SEQUENCE_RETRY_ATTEMPTS):
        try:
            with transaction.atomic():
                with transaction.atomic():
                    reserved = _reserve_sequence(session.pk, state, moment)
                    event = DemonstrationEvent.objects.create(
                        session_id=session.pk, idempotency_key=key, sequence=reserved, **fields
                    )
                return event
        except IntegrityError as exc:
            if _is_sequence_conflict(exc):
                # Two reservations reached one number. The savepoint above rolled
                # the counter back with the event, so the retry re-reads it; after
                # the budget this is the same controlled refusal as a lost race,
                # never a bare integrity error reaching the browser as a 500.
                _sleep_before(retry_index)
                continue
            if not _is_idempotency_conflict(exc):
                raise
            existing = DemonstrationEvent.objects.filter(session_id=session.pk, idempotency_key=key).first()
            if existing is None:
                raise
            return existing
        except (SequenceContention, OperationalError) as exc:
            if isinstance(exc, OperationalError) and not is_database_contention(exc):
                raise
            _sleep_before(retry_index)
            continue
    raise DemonstrationError("The demonstration stream is busy. Try again in a moment.", "sequence_contention")


class SequenceContention(Exception):
    """The counter moved underneath us; retry the whole reservation."""


def _reserve_sequence(session_pk, expected_state, moment):
    """Move the counter and return the sequence number this event owns.

    The reservation stamps activity in the same statement. Reaching an approved
    screen or saving a scoped record is the deliberate act the inactivity deadline
    is measured from, so the counter and the deadline move together or not at all —
    an event that rolled back must not have extended the recording either.
    """
    session = DemonstrationSession.objects.filter(pk=session_pk, state=expected_state).first()
    if session is None:
        raise SequenceContention()
    updated = DemonstrationSession.objects.filter(
        pk=session_pk, state=expected_state, version=session.version, next_sequence=session.next_sequence
    ).update(
        version=F("version") + 1, next_sequence=session.next_sequence + 1, last_activity_at=moment
    )
    if updated != 1:
        raise SequenceContention()
    return session.next_sequence


def _is_idempotency_conflict(exc):
    message = str(exc).lower()
    return "unique_demonstration_event_idempotency" in message or (
        "hybrid_demonstrationevent.session_id" in message and "idempotency_key" in message
    )


def _is_sequence_conflict(exc):
    """A collision on ``(session, sequence)`` — two reservations, one number.

    The conditional update in ``_reserve_sequence`` should make this impossible,
    so it means the counter moved in a way this code did not anticipate: another
    writer outside the service, or an import that rewrote ``next_sequence``. It is
    still a retryable shape, and after the budget it is the same controlled
    ``sequence_contention`` refusal as a lost race — never a bare integrity error
    surfacing as an HTTP 500.
    """
    message = str(exc).lower()
    return "unique_demonstration_event_sequence" in message or (
        "hybrid_demonstrationevent.session_id" in message and "sequence" in message
    )


def _validated(*, event_type, action_code, route_name, record_kind, record_id, payload):
    """Collapse an event to storable, allowlisted facts. Anything unexpected refuses."""
    if event_type not in DEMONSTRATION_EVENT_PAYLOAD_KEYS:
        raise DemonstrationError("That event type is not approved for demonstrations.", "event_denied", 403)
    if not isinstance(action_code, str) or not _SAFE_CODE.fullmatch(action_code):
        raise DemonstrationError("That demonstration action is not approved.", "action_denied", 403)
    if not isinstance(route_name, str) or (route_name and not _SAFE_TOKEN.fullmatch(route_name)):
        raise DemonstrationError("That simulator screen is not approved for demonstrations.", "route_denied", 403)
    if record_id is not None:
        if record_kind not in VERIFY_RECORDS:
            raise DemonstrationError("That record kind is not approved for demonstrations.", "event_denied", 403)
        if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id < 1:
            raise DemonstrationError(
                "A demonstration record reference must be a positive identifier.", "record_out_of_scope", 403
            )
    return {
        "event_type": event_type,
        "action_code": action_code,
        "route_name": route_name,
        "record_kind": record_kind if record_id is not None else "",
        "record_id": record_id,
        "payload": _sanitized_payload(event_type, payload),
    }


def _sanitized_payload(event_type, payload):
    """Keep only approved keys, and only short semantic tokens inside them.

    See ``_SAFE_CODE``: the shape rule is what makes "codes, never text" a
    constraint instead of a promise.
    """
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise DemonstrationError("A demonstration payload must be a JSON object.", "payload_rejected", 400)
    allowed = DEMONSTRATION_EVENT_PAYLOAD_KEYS[event_type]
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise DemonstrationError("A demonstration payload cannot carry " + ", ".join(unknown) + ".", "payload_rejected", 400)
    clean = {}
    for key, value in payload.items():
        if key == "changed_fields":
            if not isinstance(value, (list, tuple)) or not value or len(value) > 40:
                raise DemonstrationError(
                    "Changed fields must be a short list of form column names.", "payload_rejected", 400
                )
            names = sorted(set(value))
            if any(not isinstance(name, str) or name not in DEMONSTRATION_UCR_FIELDS for name in names):
                raise DemonstrationError("That is not an approved UCR form column.", "payload_rejected", 400)
            clean[key] = names
            continue
        if key in {"regime_code", "transport_mode_code"}:
            if not isinstance(value, str) or not _SAFE_CODE.fullmatch(value):
                raise DemonstrationError("A demonstration payload carries codes, not text.", "payload_rejected", 400)
            clean[key] = value
            continue
        if key == "result_status":
            clean[key] = _result_status(value)
    return clean


def _result_status(value):
    if value not in DEMONSTRATION_RESULT_STATUSES:
        raise DemonstrationError("That outcome is not an approved demonstration result.", "payload_rejected", 400)
    return value


# --- Review ------------------------------------------------------------------


def assert_route_authorized(route_name, method):
    """The manifest gate Stage 1B wires into the frame boundary.

    Refuses everything not on the manifest: an unknown route, a route that is not
    approved at all, and any method the route does not carry. ``ucr-save`` has no
    methods yet, so every demonstration write is refused until the scoped save
    service lands.
    """
    allowed = DEMONSTRATION_ROUTE_PERMISSIONS.get(str(route_name or ""))
    if allowed is None or str(method).upper() not in allowed:
        raise DemonstrationError(
            "This simulator action is not approved for a demonstration recording.", "route_denied", 403
        )
    return True


def timeline(session):
    """The session's events, in the order the server recorded them.

    Ordered by ``sequence`` and never by ``created_at``: two events written in one
    transaction can share a timestamp, but no two can share a sequence.
    """
    return [
        {
            "id": str(event.pk),
            "sequence": event.sequence,
            "event_type": event.event_type,
            "action_code": event.action_code,
            "route_name": event.route_name,
            "record": f"{event.record_kind}:{event.record_id}" if event.record_id else "",
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for event in DemonstrationEvent.objects.filter(session=session).order_by("sequence")
    ]


def session_payload(session):
    """The studio's whole view of a session: state, counters, and nothing else."""
    return {
        "id": str(session.pk),
        "state": session.state,
        "lesson": str(session.lesson_id),
        "version": session.version,
        "next_sequence": session.next_sequence,
        "started_at": session.started_at.isoformat(),
        "last_activity_at": session.last_activity_at.isoformat(),
        "paused_at": session.paused_at.isoformat() if session.paused_at else None,
        "stopped_at": session.stopped_at.isoformat() if session.stopped_at else None,
        "discarded_at": session.discarded_at.isoformat() if session.discarded_at else None,
        "retention_expires_at": session.retention_expires_at.isoformat() if session.retention_expires_at else None,
        "event_count": DemonstrationEvent.objects.filter(session=session).count(),
        "record_count": _demonstration_record_count(session),
    }


def _demonstration_record_count(session):
    from scenarios.demonstration_ucr import count_demonstration_ucrs

    return count_demonstration_ucrs(session)
