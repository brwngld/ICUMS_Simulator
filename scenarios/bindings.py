"""Approved simulator route bindings for guided-practice steps.

Bindings store Django route *names* (never raw URLs) so the guided engine
survives a simulator URL redesign: the target path is re-resolved with
``reverse()`` at render time, and only routes listed in the registry below
may be bound. The registry is the single approval point for new targets;
keeping it separate from the simulator views means no simulator file needs
to change when the guided engine adopts or retires a target.

The same registry answers the authoring questions that go with a target:
which record kinds can be verified, in which statuses, and which of their
saved columns can be pinned to an exact value.
"""

from django.core.exceptions import ValidationError
from django.db.models import BooleanField, CharField, IntegerField, TextField

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


#: Columns that describe the record's lifecycle rather than its content, so
#: pinning an exact value to one would verify the engine, not the learner.
_LIFECYCLE_COLUMNS = {"id", "status", "created_at", "updated_at", "submitted_at"}


def _value_kind(field):
    """How a form should accept this column's exact value, or None if it cannot.

    Decimal, date and JSON columns are deliberately left out: their Python
    values do not survive the JSON storage of a verification condition, so an
    expectation typed for one could never compare equal to the saved record.
    """
    if isinstance(field, BooleanField):
        return "boolean"
    if isinstance(field, IntegerField):
        return "number"
    if isinstance(field, (CharField, TextField)):
        return "text"
    return None


def checkable_fields(record_kind):
    """Ordered ``(column, label, value_kind)`` triples for one record kind.

    Only columns whose exact value can be typed and compared are listed, so a
    form can offer a saved value only where verification can actually honour it.
    """
    model, _label = VERIFY_RECORDS[record_kind]
    fields = []
    for field in model._meta.fields:
        if field.is_relation or field.name in _LIFECYCLE_COLUMNS:
            continue
        value_kind = _value_kind(field)
        if value_kind is None:
            continue
        fields.append((field.name, str(field.verbose_name), value_kind))
    return fields


def verify_field_choices():
    """Grouped ``kind:column`` choices for the exact-value editor.

    Grouped by record kind rather than filtered to the condition's own, so the
    select never has to be rebuilt by script and a mismatch is a server-side
    error the instructor can read instead of a silently wrong expectation.
    """
    choices = [("", "— None —")]
    for kind in VERIFY_RECORDS:
        _model, label = VERIFY_RECORDS[kind]
        choices.append(
            (
                label,
                [
                    (f"{kind}:{name}", column_label or name)
                    for name, column_label, _value_kind in checkable_fields(kind)
                ],
            )
        )
    return choices


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
        expected_fields = verify.get("fields") or {}
        if not isinstance(expected_fields, dict):
            raise ValidationError("Expected saved values must be a JSON object.")
        allowed_fields = {
            field.name for field in model._meta.fields
            if not field.is_relation and field.name not in {"id", "status", "created_at", "updated_at", "submitted_at"}
        }
        unknown_fields = sorted(set(expected_fields) - allowed_fields)
        if unknown_fields:
            raise ValidationError("Unknown saved-value field(s): " + ", ".join(unknown_fields) + ".")
        if any(isinstance(value, (dict, list)) for value in expected_fields.values()):
            raise ValidationError("Expected saved values must contain only text, numbers, booleans, or null.")
        result["verify"] = {"record": record, "status": status}
        if expected_fields:
            result["verify"]["fields"] = expected_fields
    return result
