"""Demonstration-scoped consignment application save and submit.

Follows the same pattern as ``demonstration_ucr``: a browser bound to a live
recording session that saves or submits a consignment application writes a
demonstration-scoped record (``demonstration_session`` set), never an ordinary
learner record. The scoped service re-derives every authorization server-side
and appends the record event inside the same transaction.
"""
import logging

from django.core.serializers.json import DjangoJSONEncoder
from django.db import InterfaceError, OperationalError, transaction
from django.http import JsonResponse

from hybrid.demonstrations import DemonstrationError, retry_on_contention
from hybrid.models import DemonstrationEvent
from hybrid.verification import is_database_contention

from .models import ConsignmentApplication, MdaConsignmentRequest, UcrDeclaration, allocate_application_number

logger = logging.getLogger(__name__)

CONSIGNMENT_SAVE_ACTION_CODE = "consignment.saved"
CONSIGNMENT_SUBMIT_ACTION_CODE = "consignment.submitted"


def demonstration_consignment_applies(request):
    from hybrid.demonstrations import recording_enabled
    from .demonstration_ucr import demonstration_save_applies

    return demonstration_save_applies(request) and recording_enabled()


def _bound_session(request):
    from hybrid import demonstrations

    return demonstrations.require_bound_session(request, require_recording=True)


def _parse_payload(request, session):
    """Parse the consignment application payload, resolving the UCR through
    the demonstration scope (the ordinary manager can't see it), and
    flattening the party sections the same way the ordinary parser does."""
    import json as _json
    from .views import APPLICATION_PARTY_FIELDS

    payload = _json.loads(request.body.decode("utf-8"))
    ucr_no = str(payload.get("ucr_no", "")).strip()
    ucr = UcrDeclaration.all_objects.filter(
        owner=request.user, ucr_no__iexact=ucr_no, status="submitted",
        demonstration_session=session,
    ).first()
    if ucr is None:
        raise DemonstrationError(
            "Link the application to one of your demonstration UCR numbers.",
            "ucr_not_found", 400,
        )

    data = {"ucr": ucr, "app_id": payload.get("app_id")}
    for role in ("exporter", "consignor", "importer", "consignee"):
        section = payload.get(role, {})
        if not isinstance(section, dict):
            section = {}
        data[f"{role}_same"] = bool(section.get("same", False))
        for key in APPLICATION_PARTY_FIELDS:
            # The consignment form names the importer/consignee field "code";
            # the ordinary parser maps it onto the record's name column.
            source_key = "code" if key == "name" and role in ("importer", "consignee") else key
            data[f"{role}_{key}"] = str(section.get(source_key, "") or "").strip()[:2000]
    if data["consignor_same"]:
        for key in APPLICATION_PARTY_FIELDS:
            if key != "same":
                data[f"consignor_{key}"] = data[f"exporter_{key}"]
    if data["consignee_same"]:
        for key in APPLICATION_PARTY_FIELDS:
            if key != "same":
                data[f"consignee_{key}"] = data[f"importer_{key}"]

    # Copy the consignment/valuation fields; the record has no goods
    # description column (the UCR carries it), so only known fields apply.
    for key in ("currency", "exchange_rate", "fob_fcy", "fob_ncy",
                "freight_fcy", "freight_ncy", "insurance_fcy", "insurance_ncy",
                "other_costs_fcy", "other_costs_ncy", "customs_value_fcy", "customs_value_ncy"):
        if key in payload:
            data[key] = payload[key]

    return data


def _resolve_demo_ucr(request, session, ucr_no):
    """Resolve a submitted UCR through the demonstration scope."""
    from .demonstration_ucr import get_demonstration_ucr

    record = get_demonstration_ucr(session, ucr_no)
    if record is None:
        return None
    if record.status != "submitted":
        return None
    return record


def save_demonstration_consignment(request):
    """Scoped consignment save; controlled refusals never raise."""
    def _run():
        session = _bound_session(request)
        return _scoped_save(request, session)

    return _with_contention_retry(_run)


def submit_demonstration_consignment(request):
    """Scoped consignment submit; controlled refusals never raise."""
    def _run():
        session = _bound_session(request)
        return _scoped_submit(request, session)

    return _with_contention_retry(_run)


def _with_contention_retry(operation):
    try:
        return operation()
    except DemonstrationError as error:
        return JsonResponse(error.as_json(), status=error.status)
    except (OperationalError, InterfaceError) as error:
        if not is_database_contention(error):
            raise
        logger.warning("Demonstration consignment write met database contention: %s", error)
        busy = DemonstrationError("The simulator is busy. Try again in a moment.", "session_busy", 503)
        return JsonResponse(busy.as_json(), status=busy.status)


def _scoped_save(request, session):
    from hybrid import demonstrations

    demonstrations.assert_route_authorized("application-save", "POST")

    data = _parse_payload(request, session)
    ucr = data["ucr"]

    app_id = str(data.get("app_id") or "")
    target = None
    if app_id.isdigit():
        target = ConsignmentApplication.all_objects.filter(
            pk=int(app_id), demonstration_session=session,
        ).first()
        if target and target.status != ConsignmentApplication.Status.DRAFT:
            raise DemonstrationError("This application has already been submitted.", "already_submitted", 400)

    with transaction.atomic():
        if target is None:
            record = ConsignmentApplication(owner=request.user, demonstration_session=session, ucr=ucr)
        else:
            record = target
        _apply_data(record, data)
        if not record.application_no:
            record.application_no = allocate_application_number()
        record.save()

        event_type = (
            DemonstrationEvent.EventType.RECORD_UPDATED if target is not None
            else DemonstrationEvent.EventType.RECORD_CREATED
        )
        payload = {
            "application_no": record.application_no,
            "regime_code": ucr.regime,
            "result_status": "saved",
        }
        demonstrations.append_record_event(
            request,
            event_type=event_type,
            record_kind="consignment",
            record_id=record.pk,
            action_code=CONSIGNMENT_SAVE_ACTION_CODE,
            payload=payload,
        )

    return JsonResponse({
        "id": record.pk,
        "application_no": record.application_no,
        "status": record.status,
    })


def _scoped_submit(request, session):
    from hybrid import demonstrations

    demonstrations.assert_route_authorized("application-submit", "POST")

    import json as _json

    payload = _json.loads(request.body.decode("utf-8"))
    app_id = str(payload.get("app_id") or "")
    target = ConsignmentApplication.all_objects.filter(
        pk=int(app_id), demonstration_session=session,
    ).first() if app_id.isdigit() else None
    if target is None:
        raise DemonstrationError(
            "Save the application before submitting it.", "no_draft_to_submit", 400,
        )
    if target.status != ConsignmentApplication.Status.DRAFT:
        raise DemonstrationError("This application has already been submitted.", "already_submitted", 400)

    from django.utils import timezone

    with transaction.atomic():
        target.status = ConsignmentApplication.Status.SUBMITTED
        target.submitted_at = timezone.now()
        target.save()
        payload = {
            "application_no": target.application_no,
            "regime_code": target.ucr.regime,
            "result_status": "submitted",
        }
        demonstrations.append_record_event(
            request,
            event_type=DemonstrationEvent.EventType.RECORD_UPDATED,
            record_kind="consignment",
            record_id=target.pk,
            action_code=CONSIGNMENT_SUBMIT_ACTION_CODE,
            payload=payload,
        )

    return JsonResponse({
        "id": target.pk,
        "application_no": target.application_no,
        "status": target.status,
    })


def _apply_data(record, data):
    from .views import _apply_application_payload

    _apply_application_payload(record, data)


def create_demonstration_consignment_mda(request):
    """The New Consignment Request panel's ``Create Application Form``: create
    the demonstration-scoped consignment draft from the UCR's data and its
    first MDA request, mirroring ``consignment_application_mda_create``."""
    from django.urls import reverse
    from hybrid import demonstrations
    from .models import MdaAgency, MdaApplication, MdaProcess
    from .views import (
        _allocate_mda_application_number,
        _application_initial_from_ucr,
        _initial_to_model_fields,
    )

    def _run():
        session = _bound_session(request)
        demonstrations.assert_route_authorized("consignment-application-mda-create", "POST")

        import json as _json

        payload = _json.loads(request.body.decode("utf-8"))
        ucr_no = str(payload.get("ucr_no", "")).strip()
        ucr = UcrDeclaration.all_objects.filter(
            owner=request.user, ucr_no__iexact=ucr_no,
            status=UcrDeclaration.Status.SUBMITTED, demonstration_session=session,
        ).first() if ucr_no else None
        if ucr is None:
            raise DemonstrationError("Search and choose an issued UCR number first.", "ucr_not_found", 400)

        consignment_type = str(payload.get("consignment_type", "")).strip().upper()
        master_no = str(payload.get("master_no", "")).strip()
        mda = MdaAgency.objects.filter(pk=payload.get("mda_id"), is_active=True).first()
        application = MdaApplication.objects.filter(
            pk=payload.get("application_id"), mda=mda, is_active=True,
        ).first() if mda else None
        process = MdaProcess.objects.filter(
            pk=payload.get("process_id"), application=application, is_active=True,
        ).first() if application else None
        if mda is None or application is None or process is None:
            raise DemonstrationError("Select the MDA, Application, and Process.", "mda_options_invalid", 400)

        initial = _initial_to_model_fields(_application_initial_from_ucr(ucr))
        with transaction.atomic():
            application_record = ConsignmentApplication.all_objects.filter(
                owner=request.user, ucr=ucr, status=ConsignmentApplication.Status.DRAFT,
                demonstration_session=session,
            ).first()
            if application_record is None:
                application_record = ConsignmentApplication(
                    owner=request.user, ucr=ucr, demonstration_session=session,
                    status=ConsignmentApplication.Status.DRAFT, **initial,
                )
                application_record.save()
                # The draft's sequential number is issued on its first explicit
                # save, so the creation event carries none — an empty code would
                # fail the codes-never-text payload rule.
                consignment_payload = {"regime_code": ucr.regime, "result_status": "saved"}
                if application_record.application_no:
                    consignment_payload["application_no"] = application_record.application_no
                demonstrations.append_record_event(
                    request,
                    event_type=DemonstrationEvent.EventType.RECORD_CREATED,
                    record_kind="consignment", record_id=application_record.pk,
                    action_code=CONSIGNMENT_SAVE_ACTION_CODE,
                    payload=consignment_payload,
                )

            record = MdaConsignmentRequest(
                consignment_application=application_record, owner=application_record.owner,
                demonstration_session=session,
                mda=mda, application=application, process=process,
                consignment_type=consignment_type, master_no=master_no,
                form_data=_json.loads(_json.dumps(_application_initial_from_ucr(ucr), cls=DjangoJSONEncoder)),
            )
            number, sequence_month, monthly_sequence = _allocate_mda_application_number(mda.code, application.code)
            record.application_no = number
            record.sequence_month = sequence_month
            record.monthly_sequence = monthly_sequence
            try:
                record.full_clean(exclude=("form_data",))
            except Exception as exc:
                raise DemonstrationError(str(getattr(exc, "messages", [str(exc)])[0]), "mda_invalid", 400)
            record.save()

            demonstrations.append_record_event(
                request,
                event_type=DemonstrationEvent.EventType.RECORD_CREATED,
                record_kind="mda", record_id=record.pk,
                action_code="mda.saved",
                payload={"application_no": record.application_no, "result_status": "saved"},
            )

        return JsonResponse({
            "url": reverse("mda-consignment-application", args=(record.pk,)),
            "application_no": record.application_no,
        })

    return _with_contention_retry(_run)
