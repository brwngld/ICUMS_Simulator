"""Instructor demonstration lifecycle endpoints.

Thin by design: every rule — who may act, which session is active, what state
accepts this call — is resolved in ``hybrid.demonstrations`` against the database,
so a view that forgot a check could not create an unsafe one. The browser sends a
session UUID and an expected version at most; both are verified, never trusted.

``DEMONSTRATION_RECORDING_ENABLED`` gates entry. When it is off these routes
refuse, and turning it on widens nothing: identity, lesson scope and lifecycle
state are re-checked after it.

A database that refused a statement because of a lock is answered here too. The
service retries its own collisions and ends in a controlled ``session_busy``, but
the read-only parts of a request — the payload counts and the timeline — are
outside that, so ``_refuse`` maps a contention-shaped driver error to the same 503
rather than letting it become an unhandled HTTP 500. Any other database error is
re-raised untouched, because a swallowed defect looks exactly like a busy server.

No simulator write happens here, and nothing in the studio's own page is wired to
these routes yet — Stage 1A is the foundation, not the recorder.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import InterfaceError, OperationalError
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from . import demonstrations
from .instructor_views import _draft_lesson

logger = logging.getLogger(__name__)

#: What an endpoint may answer with JSON instead of raising.
REFUSABLE = (demonstrations.DemonstrationError, PermissionDenied, OperationalError, InterfaceError)


def _disabled():
    return JsonResponse(
        {"ok": False, "error": "Demonstration recording is not enabled.", "code": "recording_disabled"}, status=403
    )


def _body(request):
    """The JSON object the client sent, or an empty one.

    A malformed body is not a refusal condition: every field here is optional and
    the service re-derives authority from the session, so an unreadable body is
    treated as no body rather than trusted less carefully.
    """
    if not request.body:
        return {}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _refuse(error):
    if isinstance(error, demonstrations.DemonstrationError):
        return JsonResponse(error.as_json(), status=error.status)
    if isinstance(error, PermissionDenied):
        return JsonResponse(
            {"ok": False, "error": "Instructor access is required.", "code": "not_instructor"}, status=403
        )
    if isinstance(error, (OperationalError, InterfaceError)) and demonstrations.is_database_contention(error):
        # The last net, not the first line of defence: every write path and the
        # binding read retry inside the service, so reaching here means a lock
        # surfaced somewhere the request was only *reading* — the timeline or the
        # counts. The instructor is told to try again; the log says why.
        logger.warning("Demonstration endpoint met database contention: %s", error)
        busy = demonstrations.DemonstrationError(
            "The demonstration is busy. Try again in a moment.", "session_busy", 503
        )
        return JsonResponse(busy.as_json(), status=busy.status)
    return None


def _answered(action):
    """Run one endpoint body and answer with its JSON or with the refusal it raised.

    The response is built inside the guard as well as the state change, because a
    demonstration *read* can meet a lock too — the payload counts and the timeline
    run on their own statements. One place to widen, rather than five.
    """
    try:
        return action()
    except REFUSABLE as error:
        response = _refuse(error)
        if response is None:
            raise
        return response


@login_required
@require_POST
def demonstration_start(request, lesson_id):
    """Open a recording for one draft lesson and bind it to this browser."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        session = demonstrations.start_recording(request, _draft_lesson(lesson_id))
        return JsonResponse({"ok": True, "session": demonstrations.session_payload(session)})

    return _answered(run)


@login_required
@require_POST
def demonstration_pause(request):
    return _control(request, demonstrations.pause_recording)


@login_required
@require_POST
def demonstration_resume(request):
    return _control(request, demonstrations.resume_recording)


@login_required
@require_POST
def demonstration_stop(request):
    return _control(request, demonstrations.stop_recording)


def _control(request, transition):
    if not demonstrations.recording_enabled():
        return _disabled()
    body = _body(request)

    def run():
        session = transition(request, body.get("session_id"), body.get("version"))
        return JsonResponse({"ok": True, "session": demonstrations.session_payload(session)})

    return _answered(run)


@login_required
@require_POST
def demonstration_discard(request):
    """Confirm-and-remove: the session's events and demonstration records go now."""
    if not demonstrations.recording_enabled():
        return _disabled()
    session_id = _body(request).get("session_id") or request.session.get(demonstrations.ACTIVE_SESSION_KEY, "")

    def run():
        session = demonstrations.discard_recording(request, session_id)
        return JsonResponse({"ok": True, "session": demonstrations.session_payload(session)})

    return _answered(run)


@login_required
@require_GET
def demonstration_session(request):
    """What this browser is holding: the bound session and its ordered timeline."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        demonstrations.authorized_instructor(request.user)
        session = demonstrations.resolve_bound_session(request)
        if session is None:
            return JsonResponse({"ok": True, "session": None, "events": []})
        return JsonResponse({
            "ok": True,
            "session": demonstrations.session_payload(session),
            "events": demonstrations.timeline(session),
        })

    return _answered(run)


# --- Stage 2B: conversion of a stopped recording into draft lesson steps -----


def _lesson_for_conversion(lesson_id):
    """The draft lesson a conversion addresses; published lessons 404 like the builder."""
    return _draft_lesson(lesson_id)


@login_required
@require_GET
def demonstration_proposals(request, lesson_id, session_id):
    """The proposed activities a stopped recording offers, for the Review tab.

    A read: nothing is written, and the answer carries route names and
    registry labels only — no demonstration record ids, no payload values.
    """
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        from . import conversion

        lesson = _lesson_for_conversion(lesson_id)
        session = conversion.conversion_session(request.user, lesson, session_id)
        return JsonResponse({
            "ok": True,
            "session": demonstrations.session_payload(session),
            "activities": conversion.proposals_for(session),
        })

    return _answered(run)


@login_required
@require_POST
def demonstration_convert(request, lesson_id, session_id):
    """Apply the instructor's selected, edited proposals to the draft lesson.

    One transaction; the audit marker written inside it is what makes a second
    application of the same recording a refusal instead of a duplicate. The
    body is the ordered activity list the review interface submitted; every
    field is revalidated server-side against the authoring rules.
    """
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        from . import conversion

        lesson = _lesson_for_conversion(lesson_id)
        body = _body(request)
        activities = body.get("activities")
        created = conversion.apply_proposals(request.user, lesson, session_id, activities)
        return JsonResponse({
            "ok": True,
            "steps": [
                {
                    "id": str(step.pk),
                    "title": step.title,
                    "screen": step.screen,
                    "order": step.order,
                    "conditions": [
                        condition.describe() for condition in step.conditions.all()
                    ],
                }
                for step in created
            ],
            "lesson_url": reverse("hybrid-lesson-edit", args=[lesson.pk]) + "?tab=activities",
        })

    return _answered(run)


# --- Stage 2F: instructor reference UCR selection -----------------------------


def _reference_payload(request):
    from scenarios.demonstration_ucr import reference_options, selected_reference

    record, intent = selected_reference(request)
    selected = None
    if record is not None:
        selected = {
            "id": record.pk,
            "number": record.ucr_no or record.temp_no,
            "status": record.status,
            "regime": record.regime,
            "exporter_name": record.exporter_name,
            "intent": intent,
        }
    return {"ok": True, "selected": selected, "options": reference_options(request.user)}


@login_required
@require_GET
def demonstration_reference(request, lesson_id):
    """The reference picker's data: eligible records and the current selection."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        demonstrations.authorized_instructor(request.user)
        _draft_lesson(lesson_id)
        return JsonResponse(_reference_payload(request))

    return _answered(run)


@login_required
@require_POST
def demonstration_reference_select(request, lesson_id):
    """Select (or re-select) the reference UCR and its intended use."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        from scenarios.demonstration_ucr import select_reference

        demonstrations.authorized_instructor(request.user)
        _draft_lesson(lesson_id)
        body = _body(request)
        record = select_reference(request, body.get("record_id"), body.get("intent"))
        return JsonResponse({
            "ok": True,
            "selected": {
                "id": record.pk,
                "number": record.ucr_no or record.temp_no,
                "status": record.status,
                "intent": body.get("intent"),
            },
        })

    return _answered(run)


@login_required
@require_POST
def demonstration_reference_clear(request, lesson_id):
    """Drop the reference selection; later saves create new records again."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        from scenarios.demonstration_ucr import clear_reference

        demonstrations.authorized_instructor(request.user)
        _draft_lesson(lesson_id)
        clear_reference(request)
        return JsonResponse({"ok": True})

    return _answered(run)
