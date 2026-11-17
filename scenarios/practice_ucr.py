"""Practice-run access to lesson-scoped UCR scratch records.

A lesson's Practise Again attempt is a retry: the learner re-performs the
procedure and the stage checks verify *what they just did*. Those scratch
records live in the same table as real declarations — the number series and
the record shape are identical — but they are scoped to the attempt
(``UcrDeclaration.practice_attempt``), so:

- the ordinary manager never returns them: search, listings and every
  ``hybrid`` enumeration stay clean, no matter how many times the learner
  practises;
- the creation ledger captures none of them (a practice run is not learner
  evidence), exactly like demonstrations;
- the whole set is deleted when the practice run completes — the run verifies
  against the records and then throws them away, so the next retry starts
  truly clean.

Like ``demonstration_ucr``, every function here takes a *resolved* attempt
and never a raw session id, and a browser that believes it is practising
with a stale binding is refused rather than silently written as an ordinary
row. The responses mirror the ordinary route's shapes so the simulator page's
own script works unchanged.
"""
import json
import logging

from django.db import InterfaceError, OperationalError, transaction
from django.http import JsonResponse

from hybrid.demonstrations import DemonstrationError, retry_on_contention
from hybrid.models import LessonAttempt
from hybrid.services import is_practice_attempt
from hybrid.verification import is_database_contention

from .models import UcrDeclaration, allocate_ucr_number

logger = logging.getLogger(__name__)

#: Session key binding a browser to its open practice attempt. Set when the
#: workspace renders an open practice attempt, cleared when the attempt
#: completes (records disposed) or a non-practice workspace renders.
PRACTICE_ACTIVE_KEY = "hybrid_practice_attempt_id"

#: The provider columns the ordinary parser only fills when the provider
#: section is shown; a practice save normalizes a hidden section to blanks.
_PROVIDER_KEYS = ("declarant_code", "code", "name", "country", "address", "contact", "phone", "email", "email_2")


def practice_ucr_applies(request):
    """Whether this UCR write belongs to an open practice run."""
    return bool(request.session.get(PRACTICE_ACTIVE_KEY))


def bound_practice_attempt(request):
    """The request's own open practice attempt, or ``None`` (clearing a stale key).

    Ownership, practice status and openness are re-derived from the database on
    every call — a key that no longer resolves is dropped, never trusted.
    """
    from hybrid.demonstrations import _as_uuid

    bound = _as_uuid(request.session.get(PRACTICE_ACTIVE_KEY, ""))
    if bound is None:
        return None
    attempt = LessonAttempt.objects.filter(pk=bound, enrolment__student=request.user).first()
    if attempt is None or attempt.completed_at is not None or not is_practice_attempt(attempt):
        request.session.pop(PRACTICE_ACTIVE_KEY, None)
        return None
    return attempt


def clear_practice_binding(request):
    request.session.pop(PRACTICE_ACTIVE_KEY, None)


def practice_create_draft(request, draft_id):
    """The scoped draft a practising browser's Create UCR screen may load."""
    if not practice_ucr_applies(request):
        return None
    if draft_id is None or not str(draft_id).isdigit():
        return None
    attempt = bound_practice_attempt(request)
    if attempt is None:
        return None
    record = UcrDeclaration.all_objects.filter(pk=int(draft_id), practice_attempt=attempt).first()
    if record is None or record.status != UcrDeclaration.Status.DRAFT:
        return None
    return record


def practice_records(attempt):
    """This attempt's scratch records, and only these."""
    return UcrDeclaration.all_objects.filter(practice_attempt=attempt).order_by("-updated_at")


def delete_practice_ucrs(attempt):
    """Throw the run's scratch records away. Ordinary rows cannot be reached."""
    deleted, _ = practice_records(attempt).delete()
    return deleted


def _parsed_payload(request):
    from .views import _parse_ucr_payload

    return _parse_ucr_payload(request)


def _apply_payload(record, parsed):
    from .views import _apply_ucr_payload

    if not parsed["show_provider"]:
        parsed = {**parsed, "provider": {key: "" for key in _PROVIDER_KEYS}}
    _apply_ucr_payload(record, parsed)


def _scoped_save(request, attempt):
    parsed, errors = _parsed_payload(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    if request.FILES:
        raise DemonstrationError(
            "Attachments cannot be recorded in a practice run.", "attachment_denied", 400
        )

    draft_id = parsed.get("draft_id")
    target = None
    if draft_id is not None:
        target = UcrDeclaration.all_objects.filter(pk=draft_id, practice_attempt=attempt).first()
    if target is not None and target.status != UcrDeclaration.Status.DRAFT:
        raise DemonstrationError("This UCR has already been submitted.", "already_submitted", 400)

    with transaction.atomic():
        if target is None:
            record = UcrDeclaration(owner=request.user, practice_attempt=attempt)
            _apply_payload(record, parsed)
            record.temp_no = allocate_ucr_number(UcrDeclaration.PRACTICE_PREFIX)
            record.save()
        else:
            record = target
            _apply_payload(record, parsed)
            record.save()
    return JsonResponse({
        "id": record.pk,
        "temp_no": record.temp_no,
        "status": record.status,
        "attachments": [],
    })


def _scoped_submit(request, attempt):
    parsed, errors = _parsed_payload(request)
    if errors:
        return JsonResponse({"errors": errors}, status=400)
    if request.FILES:
        raise DemonstrationError(
            "Attachments cannot be recorded in a practice run.", "attachment_denied", 400
        )

    draft_id = parsed.get("draft_id")
    target = UcrDeclaration.all_objects.filter(pk=draft_id, practice_attempt=attempt).first() if draft_id else None
    if target is None:
        raise DemonstrationError(
            "Save the UCR as a draft before submitting it.", "no_draft_to_submit", 400
        )
    if target.status != UcrDeclaration.Status.DRAFT:
        raise DemonstrationError("This UCR has already been submitted.", "already_submitted", 400)

    from django.urls import reverse
    from django.utils import timezone

    with transaction.atomic():
        _apply_payload(target, parsed)
        target.ucr_no = allocate_ucr_number(UcrDeclaration.UCR_PREFIX)
        target.status = UcrDeclaration.Status.SUBMITTED
        target.submitted_at = timezone.now()
        target.save()
    return JsonResponse({
        "id": target.pk,
        "temp_no": target.temp_no,
        "ucr_no": target.ucr_no,
        "status": target.status,
        "detail_url": reverse("ucr-detail", args=(target.pk,)),
        "attachments": [],
    })


def _run_scoped(request, operation):
    """Retry contention exactly like the demonstration services; refuse the rest."""
    def attempt():
        resolved = bound_practice_attempt(request)
        if resolved is None:
            raise DemonstrationError(
                "Your practice run has ended. Reopen the lesson to practise again.",
                "practice_not_active",
                409,
            )
        return operation(request, resolved)

    try:
        return retry_on_contention(attempt)
    except DemonstrationError as error:
        return JsonResponse(error.as_json(), status=error.status)
    except (OperationalError, InterfaceError) as error:
        if not is_database_contention(error):
            raise
        logger.warning("Practice UCR write met database contention: %s", error)
        busy = DemonstrationError("The simulator is busy. Try again in a moment.", "session_busy", 503)
        return JsonResponse(busy.as_json(), status=busy.status)


def save_practice_ucr(request):
    """The scoped save, answered as JSON; controlled refusals never raise."""
    return _run_scoped(request, _scoped_save)


def submit_practice_ucr(request):
    """The scoped submit, answered as JSON; controlled refusals never raise."""
    return _run_scoped(request, _scoped_submit)
