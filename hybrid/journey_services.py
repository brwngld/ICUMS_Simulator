"""Journey coordination services (Stage 2, Checkpoint 3).

Cross-row rules that the seven journey models cannot express as table
constraints: canonical curriculum ordering, dependency cycle detection,
journey attempt lifecycle, and safe record-association replacement with
preserved history.

Transaction boundaries
----------------------
Every mutating service runs inside ``transaction.atomic()``. Record
association replacement additionally locks the journey attempt row
(``select_for_update``) so two concurrent replacements serialise before
either reads the active set; on top of that, the partial unique constraint
``unique_active_record_per_role`` is the database backstop that makes a
duplicate active association impossible even if the lock is contended. On
SQLite the database-wide write lock serialises whole transactions and the
constraint backstop carries the guarantee; on PostgreSQL the attempt row
lock is the operating mechanism — that combination still needs dedicated
PostgreSQL concurrency tests (see the Checkpoint 3 report's deferred items).

Authorisation boundaries enforced here
--------------------------------------
A journey attempt is always resolved through an enrolment: retrieval for
another learner raises ``PermissionDenied``, and an attempt can only be
created or evaluated against a journey in the enrolment's own programme
version. Authoring scope violations — a step or record role from another
course or version — raise ``ValidationError``, mirroring the models'
``clean()`` validation. Journey structure mutations (assignment,
unassignment, reordering, dependency changes) are draft-only: published and
retired editions refuse them.

Deliberately out of scope
-------------------------
Journey-aware "Check my work" verification. Completion is evaluated from the
existing per-lesson ``LessonAttempt`` completion signals plus required
journey record roles; no journey condition is evaluated at runtime in this
checkpoint.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from .models import (
    HybridLesson,
    JourneyAttempt,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    ProgrammeVersion,
)

CANONICAL_ORDER = (
    "step__lesson__module__course__order",
    "step__lesson__module__course__title",
    "step__lesson__module__order",
    "step__lesson__module__title",
    "step__lesson__order",
    "step__lesson__title",
    "step__order",
    "step__title",
    "step__id",
)


# --- Structure: assignments, canonical ordering, entry points -----------------


def ordered_assignments(journey):
    """The journey's step assignments in canonical curriculum order.

    Canonical order is the hybrid curriculum order — course, module, lesson,
    then the step's own order — regardless of the order in which steps were
    assigned. ``journey_order`` is kept in sync with this sequence.
    """
    return list(
        JourneyStep.objects.filter(journey=journey)
        .select_related("step", "step__lesson", "step__lesson__module", "step__lesson__module__course")
        .order_by(*CANONICAL_ORDER, "journey_order", "id")
    )


def _require_same_course(journey, step):
    if step.lesson.module.course_id != journey.course_id:
        raise ValidationError({"step": "The step must belong to the journey's course."})


def _require_draft_version(journey):
    """Structure mutations live in draft editions only. Published and retired
    editions are immutable for everyone."""
    if journey.programme_version.status != ProgrammeVersion.Status.DRAFT:
        raise PermissionDenied("Journey structure can only be changed in a draft edition.")


def assign_step(journey, step):
    """Assign an existing practical step to the journey (draft editions only)."""
    _require_draft_version(journey)
    _require_same_course(journey, step)
    with transaction.atomic():
        if JourneyStep.objects.filter(step=step).exists():
            raise ValidationError({"step": "This practical step is already assigned to a journey."})
        # Append past the current end (the check constraint floors orders at 1);
        # the canonical renumber immediately puts it in its curriculum position.
        next_order = (
            JourneyStep.objects.filter(journey=journey).aggregate(order_max=models.Max("journey_order"))[
                "order_max"
            ]
            or 0
        ) + 1
        assignment = JourneyStep.objects.create(journey=journey, step=step, journey_order=next_order)
        sync_journey_order(journey)
    return assignment


def unassign_step(journey, step):
    """Remove an assignment and any dependencies that referenced it (draft editions only)."""
    _require_draft_version(journey)
    with transaction.atomic():
        JourneyDependency.objects.filter(
            journey=journey, predecessor_step__step=step,
        ).delete()
        JourneyDependency.objects.filter(
            journey=journey, dependent_step__step=step,
        ).delete()
        JourneyStep.objects.filter(journey=journey, step=step).delete()
        sync_journey_order(journey)


def sync_journey_order(journey):
    """Renumber ``journey_order`` 1..N following the canonical curriculum order.

    The rows are first shifted above the target range in one statement so the
    renumber never collides with the unique (journey, journey_order) constraint.
    """
    with transaction.atomic():
        JourneyStep.objects.filter(journey=journey).update(journey_order=F("journey_order") + 10000)
        for position, assignment in enumerate(ordered_assignments(journey), start=1):
            if assignment.journey_order != position:
                JourneyStep.objects.filter(pk=assignment.pk).update(journey_order=position)


def entry_point(journey):
    """The journey's single derived entry point: the earliest assigned step in
    canonical curriculum order.

    Dependencies never create additional entry points or shortcuts — they are
    forward-only relative to the canonical order, so the earliest assigned
    step always precedes every other step in the journey.
    """
    assignments = ordered_assignments(journey)
    return assignments[0] if assignments else None


# --- Dependencies: forward-only edges and cycle detection ---------------------


def _reachable(edges, start, target):
    stack, seen = [start], set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(dependent for predecessor, dependent in edges if predecessor == current)
    return False


def journey_edges(journey):
    return set(
        JourneyDependency.objects.filter(journey=journey).values_list(
            "predecessor_step_id", "dependent_step_id"
        )
    )


def dependency_creates_cycle(journey, predecessor, dependent):
    """True when adding predecessor -> dependent would close a cycle."""
    edges = journey_edges(journey)
    return _reachable(edges, dependent.pk, predecessor.pk)


def add_dependency(journey, predecessor, dependent, dependency_type, required_record_role=None):
    """Create a forward prerequisite edge between two assigned journey steps
    (draft editions only)."""
    _require_draft_version(journey)
    if predecessor.journey_id != journey.pk or dependent.journey_id != journey.pk:
        raise ValidationError({"journey": "Both steps must belong to this journey."})
    if predecessor.journey_order >= dependent.journey_order:
        raise ValidationError({"dependent_step": "Dependencies must follow the journey order."})
    if dependency_creates_cycle(journey, predecessor, dependent):
        raise ValidationError({"dependent_step": "This dependency would create a cycle."})
    if required_record_role is not None and required_record_role.journey_id != journey.pk:
        raise ValidationError({"required_record_role": "The record role must belong to this journey."})
    if bool(required_record_role) != (dependency_type == JourneyDependency.DependencyType.RECORD_AVAILABLE):
        raise ValidationError(
            {"required_record_role": "Only record-available dependencies may carry a record role."}
        )
    with transaction.atomic():
        dependency = JourneyDependency.objects.create(
            journey=journey,
            predecessor_step=predecessor,
            dependent_step=dependent,
            dependency_type=dependency_type,
            required_record_role=required_record_role,
            order=journey.dependencies.count() + 1,
        )
    return dependency


def dependency_issues(journey):
    """Structural problems in persisted dependency rows (data written without
    the service, e.g. by the admin), reported rather than raised."""
    issues = []
    assignments = {a.pk: a for a in ordered_assignments(journey)}
    for dependency in JourneyDependency.objects.filter(journey=journey).order_by("order", "id"):
        predecessor = assignments.get(dependency.predecessor_step_id)
        dependent = assignments.get(dependency.dependent_step_id)
        if predecessor is None or dependent is None:
            issues.append(f"Dependency {dependency.pk} references steps outside this journey.")
            continue
        if predecessor.journey_order >= dependent.journey_order:
            issues.append(
                f"Dependency {dependency.pk} does not follow the journey order "
                f"({predecessor.journey_order} → {dependent.journey_order})."
            )
        if dependency.required_record_role_id and dependency.required_record_role.journey_id != journey.pk:
            issues.append(f"Dependency {dependency.pk} references a record role from another journey.")
    return issues


def dependency_cycle(journey):
    """Return a dependency cycle as a list of step ids, or None."""
    edges = journey_edges(journey)
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {step_id: WHITE for edge in edges for step_id in edge}
    stack = []

    def visit(node):
        colour[node] = GREY
        stack.append(node)
        for predecessor, dependent in edges:
            if predecessor != node:
                continue
            next_node = dependent
            if colour.get(next_node, WHITE) == GREY:
                return stack[stack.index(next_node):] + [next_node]
            if colour.get(next_node, WHITE) == WHITE and visit(next_node):
                return True
        stack.pop()
        colour[node] = BLACK
        return None

    for node in list(colour):
        if colour[node] == WHITE:
            cycle = visit(node)
            if cycle:
                return cycle
    return None


# --- Attempts: creation, retrieval, version matching, completion --------------


def get_or_create_attempt(enrolment, journey):
    """The enrolment's single attempt for this journey, seeded at the entry point."""
    if enrolment.programme_version_id != journey.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    with transaction.atomic():
        attempt, created = JourneyAttempt.objects.get_or_create(enrolment=enrolment, journey=journey)
        if created:
            attempt.status = JourneyAttempt.Status.IN_PROGRESS
            attempt.current_journey_step = entry_point(journey)
            attempt.started_at = timezone.now()
            attempt.save()
    return attempt


def attempt_for(enrolment, journey):
    """The enrolment's own attempt, with the version match re-checked."""
    attempt = JourneyAttempt.objects.select_related("journey").filter(
        enrolment=enrolment, journey=journey
    ).first()
    if attempt and attempt.journey.programme_version_id != enrolment.programme_version_id:
        raise PermissionDenied("This journey belongs to a different programme version.")
    return attempt


def attempt_for_user(user, attempt_id):
    """Ownership boundary: a learner's journey attempt is never resolved for
    another learner, whatever id they present."""
    attempt = JourneyAttempt.objects.select_related("journey").filter(
        pk=attempt_id, enrolment__student=user
    ).first()
    if attempt is None:
        raise PermissionDenied("No such journey attempt for this learner.")
    return attempt


def completion_state(attempt):
    """Everything journey completion requires, as counts: the lessons carrying
    journey steps completed through the existing per-lesson signals, and the
    required journey record roles satisfied by an active, still-owned record.
    Optional roles never block completion."""
    lessons = HybridLesson.objects.filter(
        id__in=JourneyStep.objects.filter(journey_id=attempt.journey_id).values_list(
            "step__lesson_id", flat=True
        )
    )
    lessons_completed = LessonAttempt.objects.filter(
        enrolment=attempt.enrolment, lesson__in=lessons, completed_at__isnull=False,
    ).count()
    required_roles = JourneyRecordRole.objects.filter(
        journey_id=attempt.journey_id, required=True,
    ).order_by("order", "id")
    roles_satisfied = sum(1 for role in required_roles if role_satisfied(attempt, role)[0])
    return {
        "lessons_completed": lessons_completed,
        "lessons_total": lessons.count(),
        "roles_satisfied": roles_satisfied,
        "roles_required": required_roles.count(),
    }


def completion_issues(attempt):
    """Human-readable list of what still stands between this attempt and
    journey completion."""
    state = completion_state(attempt)
    issues = []
    if state["lessons_completed"] < state["lessons_total"]:
        issues.append(
            f"Lessons complete: {state['lessons_completed']} of {state['lessons_total']}."
        )
    missing_roles = state["roles_required"] - state["roles_satisfied"]
    if missing_roles:
        issues.append(f"{missing_roles} required record role(s) not yet satisfied.")
    return issues


def refresh_completion(attempt):
    """Mark the journey attempt complete only when every lesson carrying a
    journey step is complete for this enrolment AND every required record
    role is satisfied by an exact, still-owned simulator record. Returns True
    when the attempt is (or already was) complete."""
    if attempt.completed_at is not None:
        return True
    if not completion_issues(attempt):
        attempt.completed_at = timezone.now()
        attempt.status = JourneyAttempt.Status.COMPLETED
        attempt.save(update_fields=("completed_at", "status"))
        return True
    return False


# --- Record associations: exact identity, ownership, safe replacement ---------


def active_record(attempt, role):
    return JourneyRecordAssociation.objects.filter(
        journey_attempt=attempt, role=role, is_active=True
    ).first()


def assign_record(attempt, role, record_id, source, assigned_by=None):
    """Assign one exact simulator record to a role, replacing any active
    association while preserving its row as history."""
    if role.journey_id != attempt.journey_id:
        raise ValidationError({"role": "The record role must belong to the attempted journey."})
    if source not in JourneyRecordAssociation.AssignmentSource.values:
        raise ValidationError({"assignment_source": "Unknown assignment source."})
    model = VERIFY_RECORDS[role.record_kind][0]
    owner_id = attempt.enrolment.student_id
    if not model.objects.filter(pk=record_id, owner_id=owner_id).exists():
        if model.objects.filter(pk=record_id).exists():
            raise PermissionDenied("That simulator record belongs to another learner.")
        raise ValidationError(f"That {role.record_kind.upper()} record does not exist.")
    with transaction.atomic():
        locked = JourneyAttempt.objects.select_for_update().get(pk=attempt.pk)
        now = timezone.now()
        JourneyRecordAssociation.objects.filter(
            journey_attempt=locked, role=role, is_active=True,
        ).update(is_active=False, replaced_at=now)
        association = JourneyRecordAssociation.objects.create(
            journey_attempt=locked,
            role=role,
            enrolment=locked.enrolment,
            programme_version=locked.journey.programme_version,
            record_kind=role.record_kind,
            record_id=record_id,
            assignment_source=source,
            assigned_by=assigned_by,
        )
    return association


def role_satisfied(attempt, role):
    """(satisfied, message) for one record role: an active association whose
    record still exists and still belongs to the learner."""
    association = active_record(attempt, role)
    if association is None:
        return False, "No record has been assigned to this role yet."
    model, label = VERIFY_RECORDS[role.record_kind]
    if not model.objects.filter(pk=association.record_id, owner=attempt.enrolment.student).exists():
        return False, f"The assigned {label} record no longer exists for this learner."
    return True, f"{label} record assigned."


# --- Structural readiness ------------------------------------------------------


def structural_issues(journey):
    """Everything that makes this journey structurally incomplete, for the
    Review surfaces. Cycle and cross-scope problems are reported (they can
    only exist in rows written without the service's validation)."""
    issues = []
    assignments = ordered_assignments(journey)
    if not assignments:
        issues.append("No practical steps are assigned to this journey.")
        return issues
    for assignment in assignments:
        if assignment.step.lesson.module.course_id != journey.course_id:
            issues.append(f"Step “{assignment.step.title}” belongs to another course.")
    issues.extend(dependency_issues(journey))
    cycle = dependency_cycle(journey)
    if cycle:
        issues.append("The dependency graph contains a cycle.")
    if not journey.record_roles.exists():
        issues.append("No record roles are defined for this journey.")
    return issues
