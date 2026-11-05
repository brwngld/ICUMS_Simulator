"""Instructor reference library endpoints (Stage R4-B).

Thin JSON handlers over ``scenarios.reference_library``: every rule — who may
act, which record, which transition — is resolved in the service against the
database. The flag gates entry; instructor identity and ownership are
re-checked inside every service call; a contention-shaped driver error is
answered with the same controlled 503 the demonstration endpoints use, and any
other database error is re-raised rather than swallowed.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from . import demonstrations
from .demonstration_views import REFUSABLE, _refuse

logger = logging.getLogger(__name__)


def _disabled():
    return JsonResponse(
        {"ok": False, "error": "Demonstration recording is not enabled.", "code": "recording_disabled"}, status=403
    )


def _answered(action):
    try:
        return action()
    except REFUSABLE as error:
        response = _refuse(error)
        if response is None:
            raise
        return response


def _record_id(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


@login_required
@require_GET
def reference_library(request):
    """This instructor's references, optionally one state only."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        demonstrations.authorized_instructor(request.user)
        from scenarios.reference_library import list_references

        return JsonResponse({"ok": True, "references": list_references(request.user, request.GET.get("state"))})

    return _answered(run)


@login_required
@require_GET
def reference_detail(request, record_id):
    """One owned reference, with its advisory action flags."""
    if not demonstrations.recording_enabled():
        return _disabled()

    def run():
        demonstrations.authorized_instructor(request.user)
        from scenarios.reference_library import reference_detail as detail

        return JsonResponse({"ok": True, "reference": detail(request.user, _record_id(record_id))})

    return _answered(run)


def _transition(request, record_id, service_name):
    def run():
        demonstrations.authorized_instructor(request.user)
        import scenarios.reference_library as library

        record = getattr(library, service_name)(request.user, _record_id(record_id))
        from scenarios.reference_library import reference_payload

        return JsonResponse({"ok": True, "reference": reference_payload(record)})

    return _answered(run)


@login_required
@require_POST
def reference_promote(request, record_id):
    """Detach an owned temporary demonstration UCR into a working reference."""
    if not demonstrations.recording_enabled():
        return _disabled()
    return _transition(request, record_id, "promote_to_working")


@login_required
@require_POST
def reference_approve(request, record_id):
    """Approve a submitted working reference; approval freezes it."""
    if not demonstrations.recording_enabled():
        return _disabled()
    return _transition(request, record_id, "approve_reference")


@login_required
@require_POST
def reference_retire(request, record_id):
    """Retire an approved reference: preserved, immutable, purge-excluded."""
    if not demonstrations.recording_enabled():
        return _disabled()
    return _transition(request, record_id, "retire_reference")
