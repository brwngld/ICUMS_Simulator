"""Demonstration-scoped MDA and BOE write services.

Follows the same pattern as ``demonstration_consignment``: a browser bound to
a live recording writes demonstration-scoped records, never ordinary learner
records. Each service re-derives authorization server-side and appends the
record event inside the same transaction. The payloads are the ones the real
simulator screens send — the consignment document's MDA request dialog, the
MDA application page, and the clearance workspace / BOE declaration tabs — so
a recorded walkthrough behaves exactly like the ordinary flow it mirrors.
"""
import json as _json
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.db import IntegrityError, InterfaceError, OperationalError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from hybrid.demonstrations import DemonstrationError, retry_on_contention
from hybrid.models import DemonstrationEvent
from hybrid.verification import is_database_contention

from .models import (
    BoeDeclaration,
    BoeStageEvent,
    ConsignmentApplication,
    CustomsProcedureCode,
    CustomsRegime,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    MdaStatus,
    allocate_boe_number,
    allocate_job_number,
)

logger = logging.getLogger(__name__)

MDA_CREATE_ACTION_CODE = "mda.saved"
MDA_SAVE_ACTION_CODE = "mda.saved"
MDA_SUBMIT_ACTION_CODE = "mda.submitted"
BOE_CREATE_ACTION_CODE = "boe.created"
BOE_SAVE_ACTION_CODE = "boe.saved"
BOE_SUBMIT_ACTION_CODE = "boe.submitted"


def demonstration_mda_boe_applies(request):
    from hybrid.demonstrations import recording_enabled
    from .demonstration_ucr import demonstration_save_applies

    return demonstration_save_applies(request) and recording_enabled()


def _bound_session(request):
    from hybrid import demonstrations

    return demonstrations.require_bound_session(request, require_recording=True)


def _with_retry(operation):
    try:
        return operation()
    except DemonstrationError as error:
        return JsonResponse(error.as_json(), status=error.status)
    except (OperationalError, InterfaceError) as error:
        if not is_database_contention(error):
            raise
        logger.warning("Demonstration MDA/BOE write met database contention: %s", error)
        busy = DemonstrationError("The simulator is busy. Try again in a moment.", "session_busy", 503)
        return JsonResponse(busy.as_json(), status=busy.status)


def _url_argument(request, key):
    """The record id carried by the route itself (``mda/<id>/save/``,
    ``boe/<id>/save-draft/``), not a body key."""
    try:
        return int(str(request.resolver_match.kwargs.get(key, "")))
    except (TypeError, ValueError):
        return None


def _scoped_mda_request(request, session, key="request_id"):
    """The demonstration MDA request the route addresses, or None."""
    record_id = _url_argument(request, key)
    if record_id is None:
        return None
    return MdaConsignmentRequest.all_objects.filter(
        pk=record_id, demonstration_session=session,
    ).first()


def _scoped_boe(request, session, key="declaration_id"):
    """The demonstration BOE declaration the route addresses, or None."""
    record_id = _url_argument(request, key)
    if record_id is None:
        return None
    return BoeDeclaration.all_objects.filter(
        pk=record_id, demonstration_session=session,
    ).first()


# --- MDA scoped services ------------------------------------------------------


def create_demonstration_mda(request):
    def _run():
        session = _bound_session(request)
        return _scoped_mda_create(request, session)

    return _with_retry(_run)


def save_demonstration_mda(request):
    def _run():
        session = _bound_session(request)
        return _scoped_mda_save(request, session)

    return _with_retry(_run)


def submit_demonstration_mda(request):
    def _run():
        session = _bound_session(request)
        return _scoped_mda_submit(request, session)

    return _with_retry(_run)


def _scoped_mda_create(request, session):
    """Create the demonstration MDA request from the consignment document's
    MDA dialog payload, mirroring ``application_mda_request_create``."""
    from hybrid import demonstrations
    from .views import (
        MDA_SEQUENCE_RETRY_ATTEMPTS,
        _allocate_mda_application_number,
        _application_record_payload,
        _is_monthly_sequence_collision,
    )

    demonstrations.assert_route_authorized("application-mda-request-create", "POST")

    payload = _json.loads(request.body.decode("utf-8"))
    consignment_id = str(payload.get("consignment_application_id") or "")
    consignment = ConsignmentApplication.all_objects.filter(
        pk=int(consignment_id), demonstration_session=session,
    ).first() if consignment_id.isdigit() else None
    if consignment is None:
        raise DemonstrationError(
            "Link the MDA request to a demonstration consignment application.",
            "consignment_not_found", 400,
        )
    mda = MdaAgency.objects.filter(pk=payload.get("mda_id"), is_active=True).first()
    application = MdaApplication.objects.filter(
        pk=payload.get("application_id"), mda=mda, is_active=True,
    ).first() if mda else None
    process = MdaProcess.objects.filter(
        pk=payload.get("process_id"), application=application, is_active=True,
    ).first() if application else None
    if mda is None or application is None or process is None:
        raise DemonstrationError(
            "Choose the agency, application and process before creating the request.",
            "mda_options_invalid", 400,
        )

    snapshot = _application_record_payload(consignment)
    snapshot["ucr_no"] = consignment.ucr.ucr_no
    snapshot = _json.loads(_json.dumps(snapshot, cls=DjangoJSONEncoder))

    record = MdaConsignmentRequest(
        owner=consignment.owner, demonstration_session=session,
        consignment_application=consignment,
        mda=mda, application=application, process=process,
        consignment_type=str(payload.get("consignment_type", "")).strip(),
        master_no=str(payload.get("master_no", "")).strip(),
        form_data=snapshot,
    )
    try:
        for allocation_attempt in range(MDA_SEQUENCE_RETRY_ATTEMPTS):
            number, sequence_month, monthly_sequence = _allocate_mda_application_number(
                mda.code, application.code,
            )
            record.application_no = number
            record.sequence_month = sequence_month
            record.monthly_sequence = monthly_sequence
            record.full_clean(exclude=("application_no", "sequence_month", "monthly_sequence"))
            try:
                with transaction.atomic():
                    record.save()
            except IntegrityError as exc:
                if not _is_monthly_sequence_collision(exc) or allocation_attempt + 1 == MDA_SEQUENCE_RETRY_ATTEMPTS:
                    raise
                continue
            break
    except ValidationError as exc:
        message = next(iter(exc.message_dict.values()))[0] if hasattr(exc, "message_dict") else exc.messages[0]
        raise DemonstrationError(str(message), "mda_invalid", 400)

    demonstrations.append_record_event(
        request,
        event_type=DemonstrationEvent.EventType.RECORD_CREATED,
        record_kind="mda", record_id=record.pk,
        action_code=MDA_CREATE_ACTION_CODE,
        payload={"application_no": record.application_no, "result_status": "saved"},
    )
    return JsonResponse({
        "id": record.pk,
        "mda": mda.code,
        "application": f"{application.code}, {application.name}",
        "process": f"{process.code}, {process.name}",
        "application_no": record.application_no,
        "url": reverse("mda-consignment-application", args=(record.pk,)),
        "status": record.get_status_display(),
        "created_at": timezone.localtime(record.created_at).strftime("%d/%m/%Y %H:%M:%S"),
    }, status=201)


def _scoped_mda_save(request, session):
    """Save the demonstration MDA application page, mirroring
    ``mda_consignment_application_save``."""
    from hybrid import demonstrations
    from .views import _missing_ucr_documents

    demonstrations.assert_route_authorized("mda-consignment-application-save", "POST")

    target = _scoped_mda_request(request, session)
    if target is None:
        raise DemonstrationError("No demonstration MDA request found.", "mda_not_found", 400)

    payload = _json.loads(request.body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise DemonstrationError("The request body must be a JSON object.", "payload_invalid", 400)

    approval_save = bool(payload.pop("approval_save", False))
    if approval_save:
        missing = _missing_ucr_documents(target)
        if missing:
            return JsonResponse(
                {"error": "Attach " + ", ".join(missing) + " to the UCR before requesting approval."},
                status=400,
            )
    target.approval_terms = bool(payload.pop("approval_terms", False))
    target.approval_purpose = str(payload.pop("approval_purpose", "")).strip()[:2000]
    target.approval_remarks = str(payload.pop("approval_remarks", "")).strip()[:5000]
    parties = payload.pop("additional_parties", [])
    target.additional_parties = parties if isinstance(parties, list) else []
    target.form_data = payload
    target.save(update_fields=("approval_terms", "approval_purpose", "approval_remarks", "additional_parties", "form_data", "updated_at"))

    demonstrations.append_record_event(
        request,
        event_type=DemonstrationEvent.EventType.RECORD_UPDATED,
        record_kind="mda", record_id=target.pk,
        action_code=MDA_SAVE_ACTION_CODE,
        payload={"application_no": target.application_no, "result_status": "saved"},
    )
    return JsonResponse({"id": target.pk, "application_no": target.application_no, "status": target.get_status_display()})


def _scoped_mda_submit(request, session):
    """Submit the demonstration MDA application, mirroring
    ``mda_consignment_application_submit`` (IDF and GSA auto-approve)."""
    from hybrid import demonstrations
    from .views import _attach_generated_mda_document

    demonstrations.assert_route_authorized("mda-consignment-application-submit", "POST")

    target = _scoped_mda_request(request, session)
    if target is None:
        raise DemonstrationError("No demonstration MDA request found.", "mda_not_found", 400)
    if target.status not in (MdaStatus.DRAFT, "PP"):
        raise DemonstrationError("This MDA request has already been submitted.", "already_submitted", 400)

    with transaction.atomic():
        application_code = (target.application.code or "").upper()
        mda_code = (target.mda.code or "").upper()
        target.status = MdaStatus.SUBMITTED
        target.submitted_at = timezone.now()
        if application_code.startswith("IDF") or mda_code == "GSA":
            target.status = MdaStatus.APPROVED
        target.save(update_fields=("status", "submitted_at", "updated_at"))
        if target.status == MdaStatus.APPROVED:
            _attach_generated_mda_document(target)

        demonstrations.append_record_event(
            request,
            event_type=DemonstrationEvent.EventType.RECORD_UPDATED,
            record_kind="mda", record_id=target.pk,
            action_code=MDA_SUBMIT_ACTION_CODE,
            payload={"application_no": target.application_no, "result_status": "submitted"},
        )

    return JsonResponse({
        "id": target.pk,
        "application_no": target.application_no,
        "status": target.get_status_display(),
        "submitted_at": timezone.localtime(target.submitted_at).strftime("%d/%m/%Y %H:%M:%S"),
    })


# --- BOE scoped services -------------------------------------------------------


def create_demonstration_boe(request):
    def _run():
        session = _bound_session(request)
        return _scoped_boe_create(request, session)

    return _with_retry(_run)


def save_demonstration_boe(request):
    def _run():
        session = _bound_session(request)
        return _scoped_boe_save(request, session)

    return _with_retry(_run)


def submit_demonstration_boe(request):
    def _run():
        session = _bound_session(request)
        return _scoped_boe_submit(request, session)

    return _with_retry(_run)


def _scoped_boe_create(request, session):
    """Create the demonstration BOE from the clearance workspace's IDF reuse
    payload, mirroring ``boe_create``."""
    from django.urls import reverse
    from hybrid import demonstrations
    from .views import CUSTOMS_ZONES, _application_record_payload

    demonstrations.assert_route_authorized("boe-create", "POST")

    payload = _json.loads(request.body.decode("utf-8") or "{}") if request.body else {}
    reuse = str(payload.get("reuse", "")).strip().upper()
    if reuse != "IDF":
        raise DemonstrationError("Only the IDF reuse document is available in this training step.", "reuse_invalid", 400)
    idf_number = str(payload.get("idf_number", "")).strip()
    idf = MdaConsignmentRequest.all_objects.filter(
        application_no__iexact=idf_number, mda__code="MOTI",
        demonstration_session=session,
    ).first()
    if idf is None:
        raise DemonstrationError("The IDF number is not valid. Check it and try again.", "idf_not_found", 400)

    regime = str(payload.get("regime", "")).strip().upper()[:2]
    cpc = str(payload.get("cpc", "")).strip().upper()[:12]
    zone = str(payload.get("zone", "")).strip().upper()[:3]

    if not CustomsRegime.objects.filter(code=regime, is_active=True).exists():
        raise DemonstrationError("Select a valid regime before creating the declaration.", "regime_invalid", 400)
    if not cpc:
        raise DemonstrationError("Select the CPC code before creating the declaration.", "cpc_missing", 400)
    if not CustomsProcedureCode.objects.filter(code=cpc, is_active=True, regime__code=regime, regime__is_active=True).exists():
        raise DemonstrationError("The CPC code is not valid for the selected regime. Check it and try again.", "cpc_invalid", 400)
    if not zone or zone not in dict(CUSTOMS_ZONES):
        raise DemonstrationError("Select the zone before creating the declaration.", "zone_invalid", 400)

    ucr = idf.consignment_application.ucr
    if BoeDeclaration.all_objects.filter(ucr=ucr, demonstration_session=session).exists():
        raise DemonstrationError("This UCR has already been used in a BOE declaration.", "already_declared", 400)

    with transaction.atomic():
        declaration = BoeDeclaration(
            owner=request.user, demonstration_session=session,
            idf=idf, ucr=ucr, regime=regime, cpc=cpc, zone=zone,
            form_data=_json.loads(_json.dumps(_application_record_payload(idf.consignment_application), cls=DjangoJSONEncoder)),
            job_no=allocate_job_number(),
        )
        declaration.save()

        demonstrations.append_record_event(
            request,
            event_type=DemonstrationEvent.EventType.RECORD_CREATED,
            record_kind="boe", record_id=declaration.pk,
            action_code=BOE_CREATE_ACTION_CODE,
            payload={"job_no": declaration.job_no, "result_status": "saved"},
        )

    return JsonResponse({"url": reverse("boe-declaration", args=(declaration.pk,)), "job_no": declaration.job_no})


def _scoped_boe_save(request, session):
    """Save one BOE tab on the demonstration declaration, mirroring
    ``boe_save_general_draft`` through the shared section applier."""
    from hybrid import demonstrations
    from .views import _apply_boe_section

    demonstrations.assert_route_authorized("boe-save-draft", "POST")

    target = _scoped_boe(request, session)
    if target is None:
        raise DemonstrationError("No demonstration BOE draft found.", "boe_not_found", 400)
    if target.status != BoeDeclaration.Status.DRAFT:
        raise DemonstrationError("This BOE has already been submitted.", "already_submitted", 400)

    try:
        payload = _json.loads(request.body.decode("utf-8") or "{}")
    except _json.JSONDecodeError:
        return JsonResponse({"error": "The request body is not valid JSON."}, status=400)

    section, error = _apply_boe_section(target, payload)
    if error:
        return error
    target.save(update_fields=("form_data", "updated_at"))

    demonstrations.append_record_event(
        request,
        event_type=DemonstrationEvent.EventType.RECORD_UPDATED,
        record_kind="boe", record_id=target.pk,
        action_code=BOE_SAVE_ACTION_CODE,
        payload={"job_no": target.job_no, "result_status": "saved"},
    )
    return JsonResponse({"saved": True, "section": section})


def _scoped_boe_submit(request, session):
    """Submit the demonstration BOE, mirroring ``boe_submit`` including the
    HS-called MDA approval check resolved through the demonstration scope."""
    from django.contrib import messages
    from hybrid import demonstrations
    from .views import required_mda_agencies

    demonstrations.assert_route_authorized("boe-submit", "POST")

    target = _scoped_boe(request, session)
    if target is None:
        raise DemonstrationError("No demonstration BOE draft found.", "boe_not_found", 400)
    if target.status != BoeDeclaration.Status.DRAFT:
        raise DemonstrationError("This BOE has already been submitted.", "already_submitted", 400)

    hs_codes = [str(item.get("hs_code", "")).strip() for item in (target.form_data or {}).get("items") or []]
    active_agencies = set(MdaAgency.objects.filter(is_active=True).values_list("code", flat=True))
    pending = []
    for agency in required_mda_agencies(hs_codes):
        if agency not in active_agencies:
            continue  # e.g. DVLA has no application workflow in the simulator yet
        approved = MdaConsignmentRequest.all_objects.filter(
            consignment_application__ucr=target.ucr, demonstration_session=session,
            mda__code=agency, status=MdaStatus.APPROVED,
        ).exists()
        if not approved:
            pending.append(agency)
    if pending:
        message = (
            "Attach the approved " + " and ".join(pending)
            + " application(s) to the UCR before submitting this declaration."
        )
        if request.headers.get("Accept", "").startswith("application/json"):
            return JsonResponse({"error": message}, status=400)
        messages.error(request, message)
        return redirect("boe-declaration", target.pk)

    with transaction.atomic():
        target.status = BoeDeclaration.Status.SUBMITTED
        target.submitted_at = timezone.now()
        if not target.declaration_no:
            target.declaration_no = allocate_boe_number()
        target.save(update_fields=("status", "submitted_at", "declaration_no", "updated_at"))
        BoeStageEvent.objects.create(declaration=target, name="BOE Received", created_by=request.user)

        demonstrations.append_record_event(
            request,
            event_type=DemonstrationEvent.EventType.RECORD_UPDATED,
            record_kind="boe", record_id=target.pk,
            action_code=BOE_SUBMIT_ACTION_CODE,
            payload={"declaration_no": target.declaration_no, "result_status": "submitted"},
        )

    message = f"Declaration {target.declaration_no} was submitted."
    if request.headers.get("Accept", "").startswith("application/json"):
        return JsonResponse({
            "id": target.pk, "declaration_no": target.declaration_no,
            "job_no": target.job_no, "status": target.status,
        })
    messages.success(request, message)
    return redirect("boe-declaration", target.pk)
