"""Shared, read-only authorization of journey-attributed records.

One rule set decides whether an active ``JourneyRecordAssociation`` may stand
for a journey record role: the declared assignment source must be compatible
with the role's creation mode, the association must name an approved record
kind, the exact record must exist and belong to the enrolled learner, and a
``created_in_journey`` claim must be backed by the exact immutable creation
ledger row, created no earlier than the journey attempt started.

The resolver, the currentness predicate and the future verification writer all
call this module so authorization cannot drift between them. Nothing here
writes, and nothing here evaluates a condition: record status, expected saved
values and activity freshness remain separate concerns owned by the evaluator.
"""
from dataclasses import dataclass

from scenarios.bindings import VERIFY_RECORDS

from .models import (
    JourneyRecordAssociation,
    JourneyRecordRole,
    SimulatorRecordCreation,
)


@dataclass(frozen=True)
class ProvenanceFailure:
    """A controlled, non-sensitive reason an attribution is not authorized."""

    code: str
    message: str


def check_provenance(attempt, role, association):
    """``(failure, record)`` for one attribution; ``failure`` is None when valid.

    Read-only. The record is returned so callers never repeat the lookup and
    never broaden it to the learner's other records. When the only failure is
    the creation window, the record is returned as well: a caller that owns
    activity freshness can decide which refusal takes precedence without
    repeating the record lookup.
    """
    if association is None:
        return ProvenanceFailure(
            "association_missing", "No active record is attributed to this journey role.",
        ), None
    if association.record_kind != role.record_kind:
        return ProvenanceFailure(
            "association_mismatch", "The attributed record does not match this journey.",
        ), None

    source = association.assignment_source
    creation_mode = role.creation_mode
    if source not in JourneyRecordAssociation.AssignmentSource.values:
        return ProvenanceFailure(
            "provenance_mismatch", "The attributed record has no authorized provenance.",
        ), None
    if creation_mode not in JourneyRecordRole.CreationMode.values:
        return ProvenanceFailure(
            "provenance_mismatch", "The record role has no authorized creation mode.",
        ), None
    if (
        creation_mode == JourneyRecordRole.CreationMode.NEW
        and source != JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY
    ):
        return ProvenanceFailure(
            "provenance_mismatch", "The attributed record has no authorized provenance.",
        ), None
    if (
        creation_mode == JourneyRecordRole.CreationMode.EXISTING
        and source != JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING
    ):
        return ProvenanceFailure(
            "provenance_mismatch", "The attributed record has no authorized provenance.",
        ), None

    entry = VERIFY_RECORDS.get(association.record_kind)
    if entry is None:
        return ProvenanceFailure(
            "record_kind_mismatch", "The journey record role names an unapproved record kind.",
        ), None
    record = entry[0].objects.filter(
        pk=association.record_id,
        owner_id=attempt.enrolment.student_id,
    ).first()
    if record is None:
        return ProvenanceFailure(
            "record_unavailable", "The attributed simulator record is unavailable.",
        ), None

    if source == JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY:
        evidence = SimulatorRecordCreation.objects.filter(
            record_kind=association.record_kind,
            record_id=association.record_id,
            owner_id=attempt.enrolment.student_id,
        ).first()
        if evidence is None:
            return ProvenanceFailure(
                "creation_evidence_missing",
                "Creation evidence is unavailable for the attributed record.",
            ), None
        if attempt.started_at is None:
            return ProvenanceFailure(
                "provenance_invalid",
                "The journey attempt has no start time, so creation provenance cannot be established.",
            ), None
        if evidence.record_created_at < attempt.started_at:
            return ProvenanceFailure(
                "record_predates_journey",
                "The attributed record was created before this journey started.",
            ), record

    return None, record
