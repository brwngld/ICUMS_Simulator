"""Demonstration-to-lesson conversion (Stage 2B).

A stopped recording is a authoring draft: its timeline already names the
screens the demonstration drove and the record it saved. This module turns
that timeline into *proposed* activities and, on the instructor's explicit
confirmation, into ordinary ``PracticalStep``/``VerificationCondition`` rows on
the same draft lesson — nothing more. The verification engine, the lesson
builder and every student surface are untouched: converted steps are exactly
the rows the editor's own forms create, and publication readiness judges them
like any other step.

Rules the service enforces:

- **Proposal is a read.** ``proposals_for`` never writes, and never surfaces a
  demonstration record's id or payload values — only route names and the
  registry's own labels travel to the review interface.
- **Screens collapse to their first visit.** Revisiting a screen is demonstration,
  not curriculum; the proposal list holds each distinct approved route once, in
  the order it was first reached.
- **A save belongs to its screen.** Record events carry no route of their own,
  so a UCR save is attached to the screen the recording was on when it saved
  (``single-window-create-ucr`` in practice), and a re-save strengthens the
  same proposal instead of creating a second one.
- **The condition is a suggestion.** The proposed verification is the same
  saved-record pair the editor's own condition form would create (an approved
  record kind in an approved status) — validated by the model's own ``clean``
  at apply time.
- **Application is explicit, once, and all-or-nothing.** Steps are created
  only from the server's own re-derived proposals (a submitted screen that is
  not one of them is refused), every field passes ``StepForm`` exactly as the
  editor would validate it, and one ``AuditEvent`` per session — written in
  the same transaction, under a row lock on the session — is what makes a
  second application of the same recording a refusal instead of a duplicate.
"""
from django.db import transaction
from django.utils import timezone

from audit.models import AuditEvent
from scenarios.bindings import SIMULATOR_BINDING_ROUTES, VERIFY_RECORDS

from .demonstrations import (
    DemonstrationError,
    authorized_instructor,
    recording_enabled,
)
from .forms import StepForm
from .models import DemonstrationSession, PracticalStep, VerificationCondition

#: The one suggested verification pair. The demonstration save writes a draft
#: UCR by construction, so the proposed condition is the pair the editor's own
#: condition form offers for it.
PROPOSED_RECORD_KIND = "ucr"
PROPOSED_REQUIRED_STATUS = "draft"

#: The audit record that marks a recording as converted. Append-only, written
#: inside the apply transaction, and the duplicate-application gate.
CONVERSION_ACTION_CODE = "demonstration.converted"
CONVERSION_TARGET_TYPE = "hybrid_demonstrationsession"

#: Where a save proposal anchors when its screen was never navigated to. The
#: studio's UCR save always happens on the Create UCR screen.
_UCR_SAVE_ANCHOR_ROUTE = "single-window-create-ucr"


def _screen_label(route):
    return SIMULATOR_BINDING_ROUTES.get(route, route)


def proposals_for(session):
    """Proposed activities read from a stopped session's timeline, in order.

    The session must be the caller's own, stopped, and still inside its
    retention window — resolved by :func:`conversion_session` before this is
    called. Each proposal is an ordinary activity draft: a registry-approved
    screen with drafted title/instruction/outcome text, plus the suggested
    saved-record condition when a UCR save happened on that screen. No
    demonstration record identifier and no event payload value is included.
    """
    condition_label = None
    record_model, record_label = VERIFY_RECORDS[PROPOSED_RECORD_KIND]
    statuses = dict(record_model._meta.get_field("status").choices)
    condition_label = f"A {record_label} saved as “{statuses[PROPOSED_REQUIRED_STATUS]}”"

    by_route = {}
    order = []
    current_route = None
    for event in session.events.order_by("sequence"):
        if event.event_type == "navigation" and event.route_name in SIMULATOR_BINDING_ROUTES:
            current_route = event.route_name
            if current_route not in by_route:
                by_route[current_route] = {"screen": current_route, "has_condition": False, "saves": 0}
                order.append(current_route)
        elif event.event_type in ("record_created", "record_updated") and event.record_kind == PROPOSED_RECORD_KIND:
            route = current_route or _UCR_SAVE_ANCHOR_ROUTE
            if route not in by_route:
                by_route[route] = {"screen": route, "has_condition": False, "saves": 0}
                order.append(route)
            by_route[route]["has_condition"] = True
            by_route[route]["saves"] += 1

    proposals = []
    for route in order:
        item = by_route[route]
        label = _screen_label(route)
        instruction = f"Open the {label} screen in the simulator and complete the activity shown."
        outcome = (
            f"A saved {record_label.lower()} draft exists for this activity."
            if item["has_condition"]
            else f"The {label} screen has been reached."
        )
        proposals.append({
            "screen": route,
            "screen_label": label,
            "title": label,
            "instruction": instruction,
            "outcome": outcome,
            "hint": "",
            "has_condition": item["has_condition"],
            "condition_label": condition_label if item["has_condition"] else "",
        })
    return proposals


def conversion_session(user, lesson, session_id):
    """The one convertible session: this instructor's, on this lesson, stopped, unexpired.

    Every refusal is a controlled ``DemonstrationError`` the endpoint reports
    as JSON. A session of another lesson, another instructor, or an unknown id
    is the same ``session_gone`` refusal, so the error never confirms that a
    foreign recording exists.
    """
    authorized_instructor(user)
    from onboarding.models import ProgrammeVersion

    if lesson.module.course.programme_version.status != ProgrammeVersion.Status.DRAFT:
        raise DemonstrationError("Activities can only be converted in a draft lesson.", "lesson_not_draft", 403)
    session = DemonstrationSession.objects.filter(pk=session_id, instructor=user, lesson=lesson).first()
    if session is None:
        raise DemonstrationError("No such demonstration recording for this lesson.", "session_gone", 404)
    if session.state != DemonstrationSession.State.STOPPED:
        raise DemonstrationError(
            "Only a stopped recording can be converted. Stop the recording first.",
            "recording_not_stopped",
            409,
        )
    if session.retention_expires_at is not None and session.retention_expires_at <= timezone.now():
        raise DemonstrationError(
            "This recording's retention window has ended; its timeline is no longer available.",
            "session_expired",
            409,
        )
    return session


def _validated_activities(session, activities):
    """Match the submission against the server's own proposals and validate every field.

    The submission is a list of ``{screen, title, instruction, outcome, hint,
    with_condition}`` in the instructor's chosen order. A screen that is not
    one of this session's proposals, a repeated screen, or a condition request
    on a screen that saved nothing is refused. Everything else is judged by
    ``StepForm`` — the same validation the lesson editor applies.
    """
    proposals = {proposal["screen"]: proposal for proposal in proposals_for(session)}
    if not isinstance(activities, list) or not activities:
        raise DemonstrationError("Select at least one activity to convert.", "invalid_activity", 400)
    if len(activities) > len(proposals):
        raise DemonstrationError("More activities were submitted than this recording proposes.", "invalid_activity", 400)

    validated = []
    seen = set()
    for entry in activities:
        if not isinstance(entry, dict):
            raise DemonstrationError("An activity submission is malformed.", "invalid_activity", 400)
        screen = entry.get("screen")
        proposal = proposals.get(screen) if isinstance(screen, str) else None
        if proposal is None:
            raise DemonstrationError(
                "That activity's screen is not part of this recording's proposals.",
                "unsupported_screen",
                400,
            )
        if screen in seen:
            raise DemonstrationError("The same screen was submitted twice.", "invalid_activity", 400)
        seen.add(screen)
        with_condition = entry.get("with_condition") is True
        if with_condition and not proposal["has_condition"]:
            raise DemonstrationError(
                "That screen has no saved-record proposal to attach.",
                "unsupported_condition",
                400,
            )
        form = StepForm(data={
            "title": entry.get("title") or "",
            "instruction": entry.get("instruction") or "",
            "outcome": entry.get("outcome") or "",
            "hint": entry.get("hint") or "",
            "screen": screen,
        })
        if not form.is_valid():
            raise DemonstrationError(
                "An activity is missing required fields: "
                + "; ".join(f"{field}: {'; '.join(errors)}" for field, errors in form.errors.items()),
                "invalid_activity",
                400,
            )
        validated.append((form.save(commit=False), with_condition))
    return validated


@transaction.atomic
def apply_proposals(user, lesson, session_id, activities):
    """Create the selected steps and conditions on the draft lesson, once.

    The session row is locked for the whole transaction so two concurrent
    applications of the same recording serialise: the second one finds the
    audit marker the first one wrote and refuses. The lock reads the session —
    it changes nothing about the recording itself, and the lifecycle's
    compare-and-set version is left exactly as the timeline left it.
    """
    from instructor_portal.views import _unique_slug

    if not recording_enabled():
        raise DemonstrationError("Demonstration recording is not enabled.", "recording_disabled", 403)
    session = conversion_session(user, lesson, session_id)
    # Serialise concurrent conversions of this recording before the marker read.
    DemonstrationSession.objects.select_for_update().get(pk=session.pk)
    if AuditEvent.objects.filter(
        action_code=CONVERSION_ACTION_CODE, target_type=CONVERSION_TARGET_TYPE, target_id=str(session.pk),
    ).exists():
        raise DemonstrationError(
            "This recording has already been converted into lesson steps. "
            "Edit the existing activities in the lesson editor instead.",
            "already_converted",
            409,
        )
    validated = _validated_activities(session, activities)

    created = []
    order = lesson.practical_steps.count()
    for step, with_condition in validated:
        order += 1
        step.lesson = lesson
        step.key = _unique_slug(PracticalStep, "key", step.title or "Activity", lesson=lesson)
        step.order = order
        step.save()
        if with_condition:
            condition = VerificationCondition(
                step=step,
                kind=VerificationCondition.Kind.SAVED_RECORD,
                record_kind=PROPOSED_RECORD_KIND,
                required_status=PROPOSED_REQUIRED_STATUS,
                order=1,
            )
            condition.full_clean()
            condition.save()
        created.append(step)

    AuditEvent.objects.create(
        actor=user,
        action_code=CONVERSION_ACTION_CODE,
        target_type=CONVERSION_TARGET_TYPE,
        target_id=str(session.pk),
        summary=f"Converted {len(created)} demonstration activities into lesson steps.",
        metadata={
            "lesson_id": str(lesson.pk),
            "screens": [step.screen for step in created],
        },
    )
    return created
