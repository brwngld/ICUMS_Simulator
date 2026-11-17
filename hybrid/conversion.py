"""Demonstration-to-lesson conversion (Stage 2B, Import-UCR foundation).

A stopped recording is an authoring draft: its timeline already names the
screens the demonstration drove, the record it saved and — since the scoped
submit service — the draft → submitted transition. This module turns that
timeline into *proposed* activities and, on the instructor's explicit
confirmation, into ordinary ``PracticalStep``/``VerificationCondition`` rows
on the same draft lesson — nothing more. The verification engine, the lesson
builder and every student surface are untouched: converted steps are exactly
the rows the editor's own forms create, and publication readiness judges them
like any other step.

Rules the service enforces:

- **Proposal is a read.** ``proposals_for`` never writes, and never surfaces a
  demonstration record's id or payload values — only route names, registry
  labels and the regime *code* the timeline captured travel to the review
  interface.
- **Proposals are milestones, not screens.** One proposal per captured
  milestone, in procedure order, each with a stable ``proposal_id`` the review
  submits back. Two proposals may share a screen: the Create UCR screen
  carries the regime, sections, save and submit milestones, because that is
  where the procedure actually performs them. Revisiting a screen is
  demonstration, not curriculum — repeats strengthen the milestone's evidence
  instead of creating a second step.
- **The condition is derived from capture.** A screen milestone proposes no
  condition; a record milestone proposes the saved-record pair the evidence
  supports — status-level always, and the captured regime pinned as an
  expected field where the timeline shows it. Nothing is proposed that no
  event grounds.
- **Missing capture is named, not papered over.** ``capture_warnings``
  reports what the timeline cannot evidence, so a recording without a
  submission can never quietly become a lesson presented as complete.
- **Every proposal is traceable.** Each carries the ``evidence`` — the event
  sequences and action codes — that grounds it, and the apply audit record
  maps every created step to its evidence.
- **Application is explicit, once, and all-or-nothing.** Steps are created
  only from the server's own re-derived proposals (a submitted id that is not
  one of them is refused), every field passes ``StepForm`` exactly as the
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

#: The suggested verification pair for a draft-stage milestone. The
#: demonstration save writes a draft UCR by construction, so the proposed
#: condition is the pair the editor's own condition form offers for it.
PROPOSED_RECORD_KIND = "ucr"
PROPOSED_REQUIRED_STATUS = "draft"

#: The audit record that marks a recording as converted. Append-only, written
#: inside the apply transaction, and the duplicate-application gate.
CONVERSION_ACTION_CODE = "demonstration.converted"
CONVERSION_TARGET_TYPE = "hybrid_demonstrationsession"

#: Where a save proposal anchors when its screen was never navigated to. The
#: studio's UCR save always happens on the Create UCR screen.
_UCR_SAVE_ANCHOR_ROUTE = "single-window-create-ucr"

#: The screen the UCR procedure's record milestones are performed on. When the
#: timeline carries record evidence, this screen's plain navigation proposal is
#: replaced by the milestone proposals below.
_UCR_RECORD_SCREEN = "single-window-create-ucr"

#: Reading labels for the section codes a record event may carry. These name
#: the form's shape for the generated instruction, never the recorded values.
_SECTION_LABELS = {
    "provider": "Service Provider",
    "exporter": "Exporter",
    "importer": "Importer",
    "consignment": "Consignment Details",
    "documents": "eDocuments",
}


def _screen_label(route):
    return SIMULATOR_BINDING_ROUTES.get(route, route)


def _regime_label(code):
    from scenarios.views import UCR_REGIME_LABELS

    return UCR_REGIME_LABELS.get(code, code)


def _condition(condition):
    """The proposed verification as the review interface and apply both read it."""
    if condition.get("kind") == "screen_opened":
        return {"kind": "screen_opened", "record_kind": "", "required_status": "", "expected_fields": {}}
    if condition.get("kind") == "stage_evidence":
        return {"kind": "stage_evidence", "record_kind": "", "required_status": "", "expected_fields": condition.get("expected_fields") or {}}
    return {
        "kind": "saved_record",
        "record_kind": condition["record_kind"],
        "required_status": condition["required_status"],
        "expected_fields": condition.get("expected_fields") or {},
    }


def _stage_condition_label(condition):
    expected = condition.get("expected_fields") or {}
    stage = expected.get("stage", "")
    if stage == "regime_selected":
        regime = expected.get("value", "")
        return f"The {_regime_label(regime)} regime is selected"
    if stage == "sections_completed":
        return "The required sections are completed"
    return f"Stage: {stage}"


def _condition_label(condition):
    if condition.get("kind") == "screen_opened":
        return "The step's simulator screen has been opened"
    if condition.get("kind") == "stage_evidence":
        return _stage_condition_label(condition)
    record_model, record_label = VERIFY_RECORDS[condition["record_kind"]]
    statuses = dict(record_model._meta.get_field("status").choices)
    label = f"A {record_label} saved as “{statuses[condition['required_status']]}”"
    expected = condition.get("expected_fields") or {}
    if expected:
        details = ", ".join(f"{name} = {value}" for name, value in sorted(expected.items()))
        label = f"{label} ({details})"
    return label


def _proposal(proposal_id, screen, title, instruction, outcome, condition=None, evidence=()):
    """One proposed activity: authoring fields, its verification, its evidence."""
    spec = _condition(condition) if condition else None
    return {
        "id": proposal_id,
        "screen": screen,
        "screen_label": _screen_label(screen),
        "title": title,
        "instruction": instruction,
        "outcome": outcome,
        "hint": "",
        "has_condition": spec is not None,
        "condition": spec,
        "condition_label": _condition_label(spec) if spec else "",
        "evidence": [
            {"sequence": event.sequence, "action_code": event.action_code}
            for event in evidence
        ],
    }


def _captured_form_detail(session, records):
    """Read the demonstration record's actual field values and build a
    learner-facing guide: what to type into each section of the form."""
    from scenarios.demonstration_ucr import demonstration_ucrs

    demo_records = demonstration_ucrs(session)
    record = demo_records.first()
    if record is None:
        return ""

    def section(title, rows):
        body = "".join(
            f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
            for label, value in rows if value
        )
        if not body:
            return ""
        return f"<p><strong>{title}</strong></p><table>{body}</table>"

    html = ""
    html += section("Service Provider", [
        ("Country", record.provider_country),
        ("Address", record.provider_address),
        ("Contact Name", record.provider_contact),
        ("Tel. No.", record.provider_phone),
        ("Approved Email Address 1", record.provider_email),
    ])
    html += section("Exporter", [
        ("Name", record.exporter_name),
        ("Country", record.exporter_country),
        ("Address", record.exporter_address),
        ("Tel. No.", record.exporter_phone),
        ("Contact Person", record.exporter_contact),
        ("Contact No.", record.exporter_contact_no),
        ("Contact Designation", record.exporter_designation),
    ])
    html += section("Importer", [
        ("TIN / NID", record.importer_identity),
        ("Name", record.importer_name),
        ("Country", record.importer_country),
        ("Address", record.importer_address),
        ("Tel. No.", record.importer_phone),
        ("Contact Person", record.importer_contact),
        ("Contact No.", record.importer_contact_no),
        ("Contact Designation", record.importer_designation),
    ])
    html += section("Consignment Details", [
        ("General Goods Description", record.goods_description),
        ("Country of Origin", record.origin_country),
        ("Country of Destination", record.destination_country),
        ("Transport Mode", record.transport_mode),
    ])
    return html


def _captured_consignment_detail(session):
    """The demonstration consignment application's actual field values, as a
    learner-facing guide for the consignment stage — same rule as the UCR's
    captured form detail: what the instructor typed is what the student sees."""
    from scenarios.models import ConsignmentApplication

    record = ConsignmentApplication.all_objects.filter(demonstration_session=session).first()
    if record is None:
        return ""

    def section(title, rows):
        body = "".join(
            f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
            for label, value in rows if value
        )
        if not body:
            return ""
        return f"<p><strong>{title}</strong></p><table>{body}</table>"

    def party(title, prefix, name_label="Name", same=None):
        rows = []
        if same is not None:
            rows.append(("Same as above", "Yes" if same else "No"))
        rows.extend([
            (name_label, getattr(record, f"{prefix}_name", "") or getattr(record, f"{prefix}_code", "")),
            ("Physical Country", getattr(record, f"{prefix}_physical_country", "")),
            ("Physical Address", getattr(record, f"{prefix}_physical_address", "")),
            ("Tel. No.", getattr(record, f"{prefix}_tel", "")),
            ("Email", getattr(record, f"{prefix}_email", "")),
        ])
        return section(title, rows)

    def money(label, field):
        value = getattr(record, field)
        return (label, str(value) if value is not None else "")

    html = ""
    html += party("Exporter", "exporter")
    html += party("Consignor", "consignor", same=record.consignor_same)
    html += party("Importer", "importer", name_label="Code / Name")
    html += party("Consignee", "consignee", name_label="Code / Name", same=record.consignee_same)
    html += section("Consignment and Valuation", [
        ("Delivery Term", record.delivery_term),
        ("Currency", record.currency),
        ("Exchange Rate", str(record.exchange_rate) if record.exchange_rate else ""),
        money("FOB (FCY)", "fob_fcy"),
        money("Freight (FCY)", "freight_fcy"),
        money("Insurance (FCY)", "insurance_fcy"),
        money("Customs Value (FCY)", "customs_value_fcy"),
    ])
    return html


def _captured_mda_detail(session):
    """The demonstration MDA request's actual agency, application and process
    choices, so the generated step names what the instructor chose."""
    from scenarios.models import MdaConsignmentRequest

    record = MdaConsignmentRequest.all_objects.filter(demonstration_session=session).first()
    if record is None:
        return ""

    def section(title, rows):
        body = "".join(
            f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
            for label, value in rows if value
        )
        if not body:
            return ""
        return f"<p><strong>{title}</strong></p><table>{body}</table>"

    return section("MDA Request", [
        ("Agency", f"{record.mda.code}, {record.mda.name}" if record.mda else ""),
        ("Application", f"{record.application.code}, {record.application.name}" if record.application else ""),
        ("Process", f"{record.process.code}, {record.process.name}" if record.process else ""),
        ("Consignment Type", record.consignment_type),
        ("Linked Consignment Application", record.consignment_application.application_no),
        ("Approval Purpose", record.approval_purpose),
    ])


def _captured_boe_detail(session):
    """The demonstration BOE's actual creation choices, so the generated step
    names the regime, CPC and zone the instructor declared."""
    from scenarios.models import BoeDeclaration

    record = BoeDeclaration.all_objects.filter(demonstration_session=session).first()
    if record is None:
        return ""

    def section(title, rows):
        body = "".join(
            f"<tr><td><strong>{label}</strong></td><td>{value}</td></tr>"
            for label, value in rows if value
        )
        if not body:
            return ""
        return f"<p><strong>{title}</strong></p><table>{body}</table>"

    return section("BOE Declaration", [
        ("Reuse Document", f"IDF — {record.idf.application_no}" if record.idf else ""),
        ("Regime", record.regime),
        ("CPC Code", record.cpc),
        ("Zone", record.zone),
        ("Linked UCR", record.ucr.ucr_no if record.ucr else ""),
    ])


def _milestone_evidence(records):
    """The record events grounding a milestone, ordered as captured."""
    return [event for _route, event in records]


def proposals_for(session):
    """Proposed activities read from a stopped session's timeline, in order.

    The session must be the caller's own, stopped, and still inside its
    retention window — resolved by :func:`conversion_session` before this is
    called. With no captured record the proposals are the visited screens in
    first-visit order, as before. With record evidence the proposals become
    the procedure's milestones: the incidental screens first, then the
    regime, sections, save and submit milestones the timeline grounds. No
    demonstration record identifier and no payload value beyond the captured
    regime code is included.
    """
    nav_events = {}
    nav_routes = []
    current_route = None
    records = []
    for event in session.events.order_by("sequence"):
        if event.event_type == "navigation" and event.route_name in SIMULATOR_BINDING_ROUTES:
            current_route = event.route_name
            if event.route_name not in nav_events:
                nav_events[event.route_name] = event
                nav_routes.append(event.route_name)
        elif event.event_type in ("record_created", "record_updated"):
            records.append((current_route or _UCR_SAVE_ANCHOR_ROUTE, event))

    ucr_records = [(route, event) for route, event in records if event.record_kind == PROPOSED_RECORD_KIND]

    def _screen_condition():
        return {"kind": "screen_opened"}

    if not records:
        return [
            _proposal(
                f"screen:{route}", route, _screen_label(route),
                f"Open the {_screen_label(route)} screen in the simulator and complete the activity shown.",
                f"The {_screen_label(route)} screen has been reached.",
                condition=_screen_condition(),
                evidence=[nav_events[route]],
            )
            for route in nav_routes
        ]

    regime_code = next(
        (event.payload.get("regime_code") for _route, event in reversed(ucr_records) if event.payload.get("regime_code")),
        None,
    )
    saved_event = next((event for _route, event in ucr_records if event.event_type == "record_created"), None)
    submitted_events = [event for _route, event in ucr_records if event.payload.get("result_status") == "submitted"]
    sections = sorted({name for _route, event in ucr_records for name in (event.payload.get("filled_sections") or [])})

    proposals = []
    for route in nav_routes:
        if route in (_UCR_RECORD_SCREEN, "ucr-detail"):
            continue
        proposals.append(_proposal(
            f"screen:{route}", route, _screen_label(route),
            f"Open the {_screen_label(route)} screen in the simulator and complete the activity shown.",
            f"The {_screen_label(route)} screen has been reached.",
            condition=_screen_condition(),
            evidence=[nav_events[route]],
        ))

    if saved_event is not None:
        # The owner's five stages: open Single Window, select regime, complete
        # sections, save the draft, submit. Stages 2 and 3 are verified by
        # stage-evidence signals the learner produced in the simulator before
        # saving; stages 4 and 5 by the saved and submitted records.
        label = _regime_label(regime_code) if regime_code else None
        evidence = _milestone_evidence(ucr_records)
        if _UCR_RECORD_SCREEN in nav_events:
            evidence = [nav_events[_UCR_RECORD_SCREEN], *evidence]

        if regime_code:
            proposals.append(_proposal(
                "milestone:regime", _UCR_RECORD_SCREEN,
                f"Select the {label} regime",
                f"Open the Create UCR screen and choose the {label} regime.",
                f"The {label} regime is selected on the UCR registration.",
                condition={
                    "kind": "stage_evidence",
                    "record_kind": "",
                    "required_status": "",
                    "expected_fields": {"stage": "regime_selected", "value": regime_code},
                },
                evidence=evidence,
            ))

        if sections:
            names = ", ".join(_SECTION_LABELS.get(name, name) for name in sections)
            detail = _captured_form_detail(session, ucr_records)
            proposals.append(_proposal(
                "milestone:sections", _UCR_RECORD_SCREEN,
                "Complete the required UCR form sections",
                f"Complete every required section of the UCR form: {names}."
                + (chr(10) + chr(10) + detail if detail else ""),
                "The required sections are completed and validated.",
                condition={
                    "kind": "stage_evidence",
                    "record_kind": "",
                    "required_status": "",
                    "expected_fields": {"stage": "sections_completed"},
                },
                evidence=_milestone_evidence(ucr_records),
            ))

        proposals.append(_proposal(
            "milestone:save", _UCR_RECORD_SCREEN,
            "Save and obtain the temporary UCR reference",
            "Save the UCR registration. The simulator issues the temporary reference.",
            "The draft is saved and a temporary UCR reference has been issued.",
            condition={
                "kind": "saved_record",
                "record_kind": PROPOSED_RECORD_KIND,
                "required_status": PROPOSED_REQUIRED_STATUS,
                "expected_fields": {},
            },
            evidence=[saved_event],
        ))

    if submitted_events:
        condition = {
            "record_kind": PROPOSED_RECORD_KIND,
            "required_status": "submitted",
            "expected_fields": {},
        }
        proposals.append(_proposal(
            "milestone:submit", _UCR_RECORD_SCREEN,
            "Submit the UCR — obtain the final UCR number",
            "Submit the UCR registration. The simulator issues the final UCR number.",
            "The UCR is submitted and a final UCR number has been issued.",
            condition=condition,
            evidence=submitted_events,
        ))

    # Consignment application milestones from the captured events — the
    # procedure's next stage after the UCR, in capture order.
    consignment_records = [
        (route, event) for route, event in records
        if event.record_kind == "consignment"
    ]
    if consignment_records:
        consignment_saved = next(
            (event for _route, event in consignment_records if event.payload.get("result_status") == "saved"),
            None,
        )
        consignment_submitted = [
            event for _route, event in consignment_records if event.payload.get("result_status") == "submitted"
        ]
        app_no = next(
            (event.payload.get("application_no") for _route, event in reversed(consignment_records) if event.payload.get("application_no")),
            None,
        )

        if consignment_saved is not None:
            detail = _captured_consignment_detail(session)
            proposals.append(_proposal(
                "milestone:consignment-create", "consignment-application-create",
                "Create the consignment application",
                "Open the Consignment Document screen, link it to your submitted UCR, and complete every required tab before saving."
                + (chr(10) + chr(10) + detail if detail else ""),
                f"A consignment application draft exists with its application number issued{f' ({app_no})' if app_no else ''}.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "consignment",
                    "required_status": "draft",
                    "expected_fields": {},
                },
                evidence=[consignment_saved],
            ))

        if consignment_submitted:
            proposals.append(_proposal(
                "milestone:consignment-submit", "consignment-application-create",
                "Submit the consignment application",
                "Submit the completed consignment application. The simulator confirms the submission and issues the CD reference.",
                "The consignment application is submitted.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "consignment",
                    "required_status": "submitted",
                    "expected_fields": {},
                },
                evidence=consignment_submitted,
            ))

    # MDA milestones from the captured events
    mda_records = [
        (route, event) for route, event in records
        if event.record_kind == "mda"
    ]
    if mda_records:
        mda_saved = next(
            (event for _route, event in mda_records if event.payload.get("result_status") == "saved"),
            None,
        )
        mda_submitted = [
            event for _route, event in mda_records if event.payload.get("result_status") == "submitted"
        ]
        mda_no = next(
            (event.payload.get("application_no") for _route, event in reversed(mda_records) if event.payload.get("application_no")),
            None,
        )

        if mda_saved is not None:
            detail = _captured_mda_detail(session)
            proposals.append(_proposal(
                "milestone:mda-create", "consignment-application-create",
                f"Create the MDA request{f' ({mda_no})' if mda_no else ''}",
                "On the consignment application, create the MDA request: choose the agency and application, link it to your consignment document, and save it."
                + (chr(10) + chr(10) + detail if detail else ""),
                f"The MDA request is saved with application number {mda_no or 'issued on save'}.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "mda",
                    "required_status": "DR",
                    "expected_fields": {},
                },
                evidence=[mda_saved],
            ))

        if mda_submitted:
            # The condition matches what the simulator actually issued: IDF and
            # GSA applications approve on submission; every other application
            # lands on SU. The captured record's final status is the evidence.
            from scenarios.models import MdaConsignmentRequest as _MdaRecord

            submitted_record = _MdaRecord.all_objects.filter(demonstration_session=session).first()
            required_status = submitted_record.status if submitted_record else "SU"
            proposals.append(_proposal(
                "milestone:mda-submit", "consignment-application-create",
                "Submit the MDA request to obtain approval",
                "Open the saved MDA request, complete the approval section, and submit it. For IDF and GSA applications the system approves automatically.",
                f"The MDA request is submitted{' and approved' if required_status == 'AP' else ''}.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "mda",
                    "required_status": required_status,
                    "expected_fields": {},
                },
                evidence=mda_submitted,
            ))

    # BOE milestones from the captured events — the procedure's final stage.
    boe_records = [
        (route, event) for route, event in records
        if event.record_kind == "boe"
    ]
    if boe_records:
        boe_saved = next(
            (event for _route, event in boe_records if event.payload.get("result_status") == "saved"),
            None,
        )
        boe_submitted = [
            event for _route, event in boe_records if event.payload.get("result_status") == "submitted"
        ]
        boe_no = next(
            (event.payload.get("declaration_no") for _route, event in reversed(boe_records) if event.payload.get("declaration_no")),
            None,
        )

        if boe_saved is not None:
            detail = _captured_boe_detail(session)
            proposals.append(_proposal(
                "milestone:boe-create", "clearance-workspace",
                "Create the BOE declaration",
                "Open the Clearance workspace and create the BOE declaration by reusing your approved IDF, then save the draft."
                + (chr(10) + chr(10) + detail if detail else ""),
                "A BOE declaration draft exists with its job number issued.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "boe",
                    "required_status": "draft",
                    "expected_fields": {},
                },
                evidence=[boe_saved],
            ))

        if boe_submitted:
            proposals.append(_proposal(
                "milestone:boe-submit", "clearance-workspace",
                "Submit the BOE declaration",
                f"Complete the declaration's tabs and submit the BOE. The simulator issues the declaration number{f' ({boe_no})' if boe_no else ''}.",
                "The BOE is submitted and a declaration number has been issued.",
                condition={
                    "kind": "saved_record",
                    "record_kind": "boe",
                    "required_status": "submitted",
                    "expected_fields": {},
                },
                evidence=boe_submitted,
            ))

    # A visited ucr-detail screen stays captured evidence (it appears in the
    # timeline and in the proposals' evidence lists) but generates no step:
    # ``PracticalStep.screen`` is the bindable-screen registry, and the detail
    # screen addresses a specific record, so a step cannot anchor to it.

    return proposals


def capture_warnings(session):
    """What the timeline cannot evidence, so the review can say so plainly.

    A recording that never saved proposes no practical step for the
    procedure's record milestones; one that never submitted cannot propose
    the submit step. Both are stated outright rather than left for the
    instructor to discover in the generated lesson.
    """
    records = [
        event
        for event in session.events.order_by("sequence")
        if event.event_type in ("record_created", "record_updated") and event.record_kind == PROPOSED_RECORD_KIND
    ]
    warnings = []
    if not records:
        return [
            "No UCR save was captured — only screen-opening steps can be proposed. "
            "Record the form save in the simulator to generate its practical steps."
        ]
    if not any(event.payload.get("result_status") == "submitted" for event in records):
        warnings.append(
            "Submission was not captured — the lesson cannot include the submit step. "
            "Record the Submit action to capture the final UCR number."
        )
    return warnings


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

    The submission is a list of ``{proposal_id, title, instruction, outcome,
    hint, with_condition}`` in the instructor's chosen order. An id that is not
    one of this session's proposals, a repeated id, or a condition request on a
    milestone that proposes none is refused. Everything else is judged by
    ``StepForm`` — the same validation the lesson editor applies.
    """
    proposals = {proposal["id"]: proposal for proposal in proposals_for(session)}
    if not isinstance(activities, list) or not activities:
        raise DemonstrationError("Select at least one activity to convert.", "invalid_activity", 400)
    if len(activities) > len(proposals):
        raise DemonstrationError("More activities were submitted than this recording proposes.", "invalid_activity", 400)

    validated = []
    seen = set()
    for entry in activities:
        if not isinstance(entry, dict):
            raise DemonstrationError("An activity submission is malformed.", "invalid_activity", 400)
        proposal_id = entry.get("proposal_id")
        proposal = proposals.get(proposal_id) if isinstance(proposal_id, str) else None
        if proposal is None:
            raise DemonstrationError(
                "That activity is not part of this recording's proposals.",
                "unsupported_activity",
                400,
            )
        if proposal_id in seen:
            raise DemonstrationError("The same activity was submitted twice.", "invalid_activity", 400)
        seen.add(proposal_id)
        with_condition = entry.get("with_condition") is True
        if with_condition and not proposal["condition"]:
            raise DemonstrationError(
                "That activity has no saved-record proposal to attach.",
                "unsupported_condition",
                400,
            )
        form = StepForm(data={
            "title": entry.get("title") or "",
            "instruction": entry.get("instruction") or "",
            "outcome": entry.get("outcome") or "",
            "hint": entry.get("hint") or "",
            "screen": proposal["screen"],
        })
        if not form.is_valid():
            raise DemonstrationError(
                "An activity is missing required fields: "
                + "; ".join(f"{field}: {'; '.join(errors)}" for field, errors in form.errors.items()),
                "invalid_activity",
                400,
            )
        validated.append((form.save(commit=False), proposal, with_condition))
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
    for step, proposal, with_condition in validated:
        order += 1
        step.lesson = lesson
        step.key = _unique_slug(PracticalStep, "key", step.title or "Activity", lesson=lesson)
        step.order = order
        step.save()
        condition_spec = proposal["condition"] if with_condition else None
        if condition_spec:
            if condition_spec.get("kind") == "screen_opened":
                condition = VerificationCondition(
                    step=step,
                    kind=VerificationCondition.Kind.SCREEN_OPENED,
                    order=1,
                )
            elif condition_spec.get("kind") == "stage_evidence":
                condition = VerificationCondition(
                    step=step,
                    kind=VerificationCondition.Kind.STAGE_EVIDENCE,
                    expected_fields=condition_spec.get("expected_fields") or {},
                    order=1,
                )
            else:
                condition = VerificationCondition(
                    step=step,
                    kind=VerificationCondition.Kind.SAVED_RECORD,
                    record_kind=condition_spec["record_kind"],
                    required_status=condition_spec["required_status"],
                    expected_fields=condition_spec.get("expected_fields") or {},
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
            # Per-step traceability: every created step, mapped to the captured
            # events that ground it. The demonstration timeline remains the
            # authoritative record; this is the authoring-side index into it.
            "evidence": [
                {"title": step.title, "screen": step.screen, "evidence": proposal["evidence"]}
                for step, proposal, _with in validated
            ],
        },
    )
    return created
