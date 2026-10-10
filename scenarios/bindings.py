"""Approved simulator route bindings for guided-practice steps.

Bindings store Django route *names* (never raw URLs) so the guided engine
survives a simulator URL redesign: the target path is re-resolved with
``reverse()`` at render time, and only routes listed in the registry below
may be bound. The registry is the single approval point for new targets;
keeping it separate from the simulator views means no simulator file needs
to change when the guided engine adopts or retires a target.
"""

from django.core.exceptions import ValidationError

from .models import BoeDeclaration, ConsignmentApplication, MdaConsignmentRequest, UcrDeclaration

#: Route names that a guided step may open. Keys are URL names registered in
#: scenarios/urls.py; values are the labels shown to instructors.
SIMULATOR_BINDING_ROUTES = {
    "simulator-portal": "Simulator portal",
    "single-window-overview": "Single Window overview",
    "single-window-create-ucr": "Create a UCR declaration",
    "single-window-search-ucr": "Search UCR declarations",
    "search-boe-declaration": "Search BOE declarations",
    "clearance-workspace": "Clearance workspace",
    "consignment-application-create": "Create a consignment application",
    "single-window-search-consignment-application": "Search consignment applications",
}

#: Record kinds a step can verify against, mapped to the model and a label.
VERIFY_RECORDS = {
    "ucr": (UcrDeclaration, "UCR declaration"),
    "boe": (BoeDeclaration, "BOE declaration"),
    "consignment": (ConsignmentApplication, "consignment application"),
    "mda": (MdaConsignmentRequest, "MDA application"),
}

_VERIFY_STATUS_CHOICES = None


def binding_route_choices():
    return [("", "— None —")] + sorted(
        (name, label) for name, label in SIMULATOR_BINDING_ROUTES.items()
    )


def _status_choices(model):
    return model._meta.get_field("status").choices


def verify_status_choices():
    """Flattened ``kind:status`` choices grouped by record kind."""
    global _VERIFY_STATUS_CHOICES
    if _VERIFY_STATUS_CHOICES is None:
        choices = [("", "— None —")]
        for kind in VERIFY_RECORDS:
            model, label = VERIFY_RECORDS[kind]
            choices.extend(
                (f"{kind}:{value}", f"{label}: {display}") for value, display in _status_choices(model)
            )
        _VERIFY_STATUS_CHOICES = choices
    return _VERIFY_STATUS_CHOICES


def validate_binding(binding):
    """Normalise and validate a step binding; raises ValidationError."""
    if not binding:
        return {}
    if not isinstance(binding, dict):
        raise ValidationError("Step binding must be a JSON object.")
    route = str(binding.get("route") or "").strip()
    task = str(binding.get("task") or "").strip()
    verify = binding.get("verify") or {}
    if not route and not task and not verify:
        return {}
    if route not in SIMULATOR_BINDING_ROUTES:
        raise ValidationError("Choose a simulator step target from the approved list.")
    if not task:
        raise ValidationError("Describe the simulator task shown to the student.")
    result = {"route": route, "task": task}
    if verify:
        if not isinstance(verify, dict):
            raise ValidationError("Verification must be a JSON object.")
        record = str(verify.get("record") or "").strip()
        status = str(verify.get("status") or "").strip()
        if record not in VERIFY_RECORDS:
            raise ValidationError("Choose a record kind to verify.")
        model, _label = VERIFY_RECORDS[record]
        valid_statuses = {value for value, _display in _status_choices(model)}
        if status not in valid_statuses:
            raise ValidationError("Choose a valid status for the verified record.")
        result["verify"] = {"record": record, "status": status}
    return result
