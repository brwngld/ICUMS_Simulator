"""Exact-session access to demonstration UCR records.

``UcrDeclaration.objects`` already excludes demonstration rows, so an ordinary
simulator query is safe without knowing this module exists. What a filtered
manager *cannot* do is authorize a demonstration query: the scope has to be
named explicitly, and it has to be the session the server resolved — never a
value from the request. Every function here takes a resolved
``DemonstrationSession`` and nothing takes a session id.

Stage 1A ships reads, cleanup and numbering only. There is no demonstration
write path: ``ucr-save`` stays off until a scoped save service exists, because
the current view resolves a draft through the ordinary manager and would
silently create an ordinary instructor record instead of updating the
demonstration draft.
"""
from django.db.models import Q

from .models import UcrDeclaration, allocate_ucr_number

#: The temporary-reference namespace for demonstration drafts. Distinct from
#: ``TEMPUCR`` because the allocator's scan and the table-wide unique column
#: must never be able to hand the same number to a learner and a demonstration.
DEMONSTRATION_TEMP_PREFIX = UcrDeclaration.DEMO_TEMP_PREFIX


def demonstration_ucrs(session):
    """This session's UCR records, and only these.

    The unfiltered manager is the point of entry because demonstration rows are
    exactly what the ordinary manager hides; the session filter is what makes it
    safe. ``owner`` is re-checked against the session's instructor so a row that
    was somehow scoped to this session but owned by someone else stays invisible.
    """
    return (
        UcrDeclaration.all_objects.filter(demonstration_session=session, owner=session.instructor)
        .select_related("owner")
        .order_by("-updated_at")
    )


def count_demonstration_ucrs(session):
    return demonstration_ucrs(session).count()


def get_demonstration_ucr(session, record_id):
    """One record by id, inside this session — the ``ucr-detail`` authorization.

    A primary key alone never resolves: a guess, a replayed id, or an ordinary
    learner's record all come back as ``None``.
    """
    if isinstance(record_id, bool) or not isinstance(record_id, int) or record_id < 1:
        return None
    return demonstration_ucrs(session).filter(pk=record_id).first()


def demonstration_record_in_session(session, *, record_kind, record_id):
    """Whether ``record_kind``/``record_id`` names a record this session owns."""
    if record_kind != "ucr":
        # Only UCR is in scope for demonstration recording; BOE, MDA and
        # consignment are denied, so no event may claim them.
        return False
    return get_demonstration_ucr(session, record_id) is not None


def delete_demonstration_ucrs(session):
    """Remove this session's records. Ordinary rows cannot be reached.

    Attachments cascade with the record they belong to. Demonstration uploads
    are not enabled, so no stored file is orphaned here; before uploads are
    approved, discard has to collect storage names and delete blobs on commit.
    """
    deleted, _ = demonstration_ucrs(session).delete()
    return deleted


def next_demonstration_temp_no():
    """The next ``DEMOUCR`` reference, allocated against every row in the table."""
    return allocate_ucr_number(DEMONSTRATION_TEMP_PREFIX)


def ordinary_ucr_scope_predicate():
    """The explicit ordinary filter, for querysets that reach a UCR by join.

    A model manager cannot help there: ``UcrDocumentAttachment.objects`` and any
    ``select_related("ucr")`` traverse to the UCR through the base manager, which
    is deliberately unfiltered so foreign keys keep working. A query that starts
    on another model and reads through to a UCR has to name the scope itself.
    """
    return Q(ucr__demonstration_session__isnull=True)
