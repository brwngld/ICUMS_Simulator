"""Authoritative creation-evidence capture for approved simulator records.

Stage 3, Checkpoint 3.1 (transaction-integrity correction). Registers
``post_save`` receivers for the four approved registry models
(``scenarios.bindings.VERIFY_RECORDS``) and writes one
``hybrid.SimulatorRecordCreation`` evidence row per created record.

Transaction semantics
---------------------
Every creation route that persists an approved registry record is wrapped in
``transaction.atomic`` (``scenarios/urls.py``), so the capture insert below
joins the record's own transaction: record and evidence commit together or
roll back together. A capture failure raises out of the view and fails the
student's save loudly — mandatory provenance never swallows errors and never
compensates by deletion. ``save_base`` itself only marks the transaction for
rollback on error (Django 5.2.18, ``django/db/models/base.py:999``), and
``post_save`` fires after that block.

Known boundary: ``bulk_create``/raw SQL bypass signals entirely and capture
nothing (no supported creation path uses them), and non-request callers
(admin, shell) fail loudly instead of capturing. Fixture loads (``raw=True``)
are not student creations and are skipped.

The ledger is evidence only: nothing in the journey engine reads it, so it
cannot by itself claim a journey role or complete a journey.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from scenarios.bindings import VERIFY_RECORDS

from .models import SimulatorRecordCreation

logger = logging.getLogger(__name__)

_KIND_BY_MODEL = {model: kind for kind, (model, _label) in VERIFY_RECORDS.items()}
_CAPTURE_DISPATCH_UID = "hybrid-creation-ledger-capture"


def _capture(sender, instance, created, **kwargs):
    """Write one evidence row for a created registry record.

    Mandatory provenance: no try/except here. The capture insert runs inside
    the creating request's transaction (every creation route is wrapped in
    ``transaction.atomic`` in ``scenarios/urls.py``), so a capture failure
    raises out of the view and rolls the record back — record and evidence
    commit together or not at all. Non-request callers (admin, shell) fail
    just as loudly.
    """
    kind = _KIND_BY_MODEL.get(sender)
    if kind is None or not created or kwargs.get("raw"):
        # Fixture loads and bulk operations are not student creations;
        # updates never capture.
        return
    SimulatorRecordCreation.objects.create(
        record_kind=kind,
        record_id=instance.pk,
        owner_id=instance.owner_id,
        record_created_at=instance.created_at,
    )


def register_capture_receivers():
    """Connect one capture receiver per approved registry model.

    Called once from ``HybridConfig.ready()``. ``dispatch_uid`` makes the
    connection idempotent, so repeated imports can never register a
    duplicate.
    """
    for model in _KIND_BY_MODEL:
        post_save.connect(
            _capture,
            sender=model,
            dispatch_uid=_CAPTURE_DISPATCH_UID + "-" + model.__name__,
        )


def disconnect_capture_receivers():
    """Remove the capture receivers. Test helper only: production code never
    disconnects capture, and no backfill pass exists."""
    for model in _KIND_BY_MODEL:
        post_save.disconnect(
            sender=model,
            dispatch_uid=_CAPTURE_DISPATCH_UID + "-" + model.__name__,
        )
