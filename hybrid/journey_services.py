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
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from .models import (
    HybridLesson,
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
    ProgrammeVersion,
    StepEvent,
    VerificationCondition,
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


def journey_step_rows(attempt):
    """Per assigned journey step: this enrolment's LessonAttempt, the
    authoritative durable evidence, satisfaction, and the outstanding
    requirement.

    Evidence rules (read-only; the workspace's Check-My-Work endpoint is the
    only writer): a condition-bearing step is satisfied by a VERIFIED StepEvent
    on this enrolment's own LessonAttempt for that exact step; a condition-free
    step is satisfied by an OPENED StepEvent — the learner demonstrably entered
    the step's screen. Evidence from another learner, lesson attempt or
    curriculum version can never match these keys.
    """
    rows = []
    for position, assignment in enumerate(ordered_assignments(attempt.journey), start=1):
        lesson_attempt = LessonAttempt.objects.filter(
            enrolment=attempt.enrolment, lesson=assignment.step.lesson
        ).first()
        verified = opened = False
        if lesson_attempt is not None:
            verified = StepEvent.objects.filter(
                attempt=lesson_attempt, step=assignment.step, kind=StepEvent.Kind.VERIFIED
            ).exists()
            opened = StepEvent.objects.filter(
                attempt=lesson_attempt, step=assignment.step, kind=StepEvent.Kind.OPENED
            ).exists()
        requires_check = VerificationCondition.objects.filter(step=assignment.step).exists()
        satisfied = verified if requires_check else opened
        if requires_check and not verified:
            requirement = "Pass Check my work on this step."
        elif not opened:
            requirement = "Open this step's simulator screen."
        else:
            requirement = ""
        rows.append({
            "position": position,
            "assignment": assignment,
            "step": assignment.step,
            "lesson_attempt": lesson_attempt,
            "verified": verified,
            "opened": opened,
            "requires_check": requires_check,
            "satisfied": satisfied,
            "requirement": requirement,
        })
    return rows


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


def journey_completion_state(attempt):
    """Authoritative journey completion state, read from durable evidence —
    never from lesson completion flags alone.

    Steps: a condition-bearing step is satisfied only by a VERIFIED StepEvent
    on this enrolment's LessonAttempt for that exact step; a condition-free
    step is satisfied by having been opened (an OPENED StepEvent — the
    learner demonstrably entered the step's screen). Roles: every required
    record role must have an active association whose exact record still
    exists and belongs to the learner. Lessons: the existing lesson completion
    requirements (completion flag and theory acknowledgement) must also hold.
    """
    rows = journey_step_rows(attempt)
    required_roles = list(
        JourneyRecordRole.objects.filter(journey=attempt.journey, required=True).order_by("order", "id")
    )
    role_states = [(role, *role_satisfied(attempt, role)) for role in required_roles]
    lesson_attempts = list(
        LessonAttempt.objects.filter(
            enrolment=attempt.enrolment,
            lesson_id__in=JourneyStep.objects.filter(journey=attempt.journey).values_list(
                "step__lesson_id", flat=True
            ),
        )
    )
    lessons_complete = bool(lesson_attempts) and all(
        attempt_row.completed_at is not None and attempt_row.theory_acknowledged_at is not None
        for attempt_row in lesson_attempts
    )
    return {
        "rows": rows,
        "steps_satisfied": sum(1 for row in rows if row["satisfied"]),
        "steps_total": len(rows),
        "role_states": role_states,
        "roles_satisfied": sum(1 for _role, satisfied, _message in role_states if satisfied),
        "roles_required": len(role_states),
        "lessons_complete": lessons_complete,
    }


def journey_completion_issues(attempt):
    """Human-readable list of what still stands between this attempt and
    journey completion."""
    state = journey_completion_state(attempt)
    issues = []
    for row in state["rows"]:
        if not row["satisfied"]:
            issues.append(
                'Step ' + str(row["position"]) + ' ("' + row["step"].title + '"): ' + row["requirement"]
            )
    for _role, satisfied, message in state["role_states"]:
        if not satisfied:
            issues.append(message)
    if not state["lessons_complete"] and state["steps_total"]:
        issues.append("Complete each journey lesson (theory acknowledged and steps verified).")
    return issues


def refresh_journey_completion(attempt):
    """Mark the journey attempt complete only when every mandatory step carries
    authoritative verification evidence, every required record role is
    satisfied, and the existing lesson completion requirements hold.
    Idempotent; evaluation is read-only until every gate passes."""
    if attempt.completed_at is not None:
        return True
    state = journey_completion_state(attempt)
    complete = (
        state["steps_total"] > 0
        and state["steps_satisfied"] == state["steps_total"]
        and state["roles_satisfied"] == state["roles_required"]
        and state["lessons_complete"]
    )
    if complete:
        attempt.completed_at = timezone.now()
        attempt.status = JourneyAttempt.Status.COMPLETED
        attempt.save(update_fields=("completed_at", "status", "last_activity_at"))
        return True
    return False


def advance_journey_attempt(attempt):
    """Move ``current_journey_step`` to the next canonical step when the
    learner's evidence allows it. The walk stops at the first unsatisfied
    step, so nothing beyond the progression ceiling can ever be reached, and
    dependency edges (step-completed, record-available) are enforced on the
    target. POST-only callers; transactional and row-locked."""
    with transaction.atomic():
        locked = JourneyAttempt.objects.select_for_update().select_related(
            "journey", "current_journey_step"
        ).get(pk=attempt.pk)
        rows = journey_step_rows(locked)
        if not rows:
            return locked, False, "This journey has no assigned steps yet."
        current_index = 0
        if locked.current_journey_step_id:
            for index, row in enumerate(rows):
                if row["assignment"].pk == locked.current_journey_step_id:
                    current_index = index
                    break
        target = current_index + 1
        if target >= len(rows):
            return locked, False, "This is the final step of the journey."

        # Progression ceiling: walk from the entry point; the first
        # unsatisfied step locks everything after it.
        reachable = [True]
        for index in range(1, len(rows)):
            reachable.append(reachable[index - 1] and rows[index - 1]["satisfied"])
        if not reachable[target]:
            message = (
                '"' + rows[target]["step"].title + '" is locked until the earlier steps are complete.'
            )
            return locked, False, message

        # Dependency edges into the target step.
        for dependency in JourneyDependency.objects.filter(journey=locked.journey, dependent_step=rows[target]["assignment"]):
            if dependency.dependency_type == JourneyDependency.DependencyType.RECORD_AVAILABLE:
                role_ok, _message = role_satisfied(locked, dependency.required_record_role)
                if not role_ok:
                    message = (
                        '"' + rows[target]["step"].title + '" needs the record role "'
                        + dependency.required_record_role.label + '" satisfied first.'
                    )
                    return locked, False, message
            else:
                predecessor_row = next(
                    (row for row in rows if row["assignment"].pk == dependency.predecessor_step_id), None,
                )
                if predecessor_row and not predecessor_row["satisfied"]:
                    message = (
                        '"' + predecessor_row["step"].title + '" must be completed first.'
                    )
                    return locked, False, message

        locked.current_journey_step = rows[target]["assignment"]
        locked.last_activity_at = timezone.now()
        locked.save(update_fields=("current_journey_step", "last_activity_at"))

        # Completion evaluation, on the POST that earned it: authoritative
        # step evidence, required roles, and the existing lesson requirements.
        rows_now = journey_step_rows(locked)
        required_roles = JourneyRecordRole.objects.filter(journey=locked.journey, required=True)
        roles_ok = all(role_satisfied(locked, role)[0] for role in required_roles)
        lesson_rows = LessonAttempt.objects.filter(
            enrolment=locked.enrolment,
            lesson_id__in=[row["step"].lesson_id for row in rows_now],
        )
        lessons_complete = lesson_rows.count() == len(rows_now) and all(
            attempt_row.completed_at is not None and attempt_row.theory_acknowledged_at is not None
            for attempt_row in lesson_rows
        )
        if all(row["satisfied"] for row in rows_now) and roles_ok and lessons_complete:
            if locked.completed_at is None:
                locked.completed_at = timezone.now()
                locked.status = JourneyAttempt.Status.COMPLETED
                locked.save(update_fields=("completed_at", "status"))
        return locked, True, "Step complete."


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
    # Creation-mode compatibility: a new-record role can only ever be filled
    # by a record created inside the journey; an existing-record role only by
    # an authorized assignment.
    if role.creation_mode == JourneyRecordRole.CreationMode.NEW and source != JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY:
        raise ValidationError("This role requires a record created within the journey.")
    if role.creation_mode == JourneyRecordRole.CreationMode.EXISTING and source != JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING:
        raise ValidationError("This role requires an authorized existing record.")
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
    """(satisfied, message) for one record role.

    Fail-closed provenance rule (Checkpoint 5 correction): an association
    declared ``created_in_journey`` can never satisfy a role on its own,
    because the simulator schema carries no authoritative link between a
    record's creation and a journey attempt. Ownership, freshness and source
    checks all pass, but creation provenance itself is unprovable, so the
    role stays unsatisfied until a simulator-side creation stamp exists.
    Authorized existing-record roles are unaffected: their ``authorized_existing``
    source is the authorized assignment process itself.
    """
    association = active_record(attempt, role)
    if association is None:
        return False, "No record has been assigned to this role yet."
    model, label = VERIFY_RECORDS[role.record_kind]
    record = model.objects.filter(pk=association.record_id, owner=attempt.enrolment.student).first()
    if record is None:
        return False, f"The assigned {label} record no longer exists for this learner."
    if association.assignment_source == JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY:
        return False, (
            f"The {label} record requirement is open: the system cannot yet verify "
            "that this record was created within this journey."
        )
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
            issues.append('Step "' + assignment.step.title + '" belongs to another course.')
    issues.extend(dependency_issues(journey))
    cycle = dependency_cycle(journey)
    if cycle:
        issues.append("The dependency graph contains a cycle.")
    if not journey.record_roles.exists():
        issues.append("No record roles are defined for this journey.")
    return issues


# --- Authoring: journeys, record roles, dependencies, bindings -----------------
# All authoring mutations are draft-edition only; every function re-checks the
# edition status so a stale page or a bypassed view still cannot mutate a
# published or retired curriculum.


def _unique_journey_code(version, seed):
    base = re.sub(r"[^a-z0-9]+", "-", (seed or "").lower()).strip("-") or "journey"
    candidate, number = base, 2
    while PracticalJourney.objects.filter(programme_version_id=version.pk, code=candidate).exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def create_journey(version, course, title, description="", start_mode=PracticalJourney.StartMode.NEW_RECORD):
    """Create a journey on a draft edition's course; the code derives from the title."""
    if version.status != ProgrammeVersion.Status.DRAFT:
        raise PermissionDenied("Journeys can only be created in a draft edition.")
    if course.programme_version_id != version.pk:
        raise ValidationError({"course": "The course must belong to this programme version."})
    if start_mode not in PracticalJourney.StartMode.values:
        raise ValidationError({"start_mode": "Unknown start mode."})
    return PracticalJourney.objects.create(
        programme_version=version,
        course=course,
        code=_unique_journey_code(version, title),
        title=title,
        description=description,
        start_mode=start_mode,
        order=course.practical_journeys.count() + 1,
    )


def update_journey(journey, title, description, start_mode):
    _require_draft_version(journey)
    if start_mode not in PracticalJourney.StartMode.values:
        raise ValidationError({"start_mode": "Unknown start mode."})
    journey.title = title
    journey.description = description
    journey.start_mode = start_mode
    journey.save(update_fields=("title", "description", "start_mode"))
    return journey


def delete_journey(journey):
    """Delete an empty journey. Anything populated must be dismantled first, so
    a single action can never silently discard authored structure."""
    _require_draft_version(journey)
    if journey.step_assignments.exists() or journey.record_roles.exists() or journey.dependencies.exists():
        raise ValidationError("Remove the journey's steps, record roles and dependencies before deleting it.")
    journey.delete()


def _role_references(role):
    return {
        "associations": JourneyRecordAssociation.objects.filter(role=role).exists(),
        "dependencies": JourneyDependency.objects.filter(required_record_role=role).exists(),
        "condition bindings": JourneyConditionBinding.objects.filter(role=role).exists(),
    }


def create_record_role(journey, key, label, record_kind, required=True,
                       creation_mode=JourneyRecordRole.CreationMode.NEW):
    _require_draft_version(journey)
    if record_kind not in VERIFY_RECORDS:
        raise ValidationError({"record_kind": "Choose an approved simulator record kind."})
    if JourneyRecordRole.objects.filter(journey=journey, key=key).exists():
        raise ValidationError({"key": "A record role with this key already exists on this journey."})
    return JourneyRecordRole.objects.create(
        journey=journey, key=key, label=label, record_kind=record_kind,
        required=required, creation_mode=creation_mode,
        order=journey.record_roles.count() + 1,
    )


def update_record_role(role, changes):
    """Apply field changes to a record role. A role that is referenced by
    associations, dependencies, or condition bindings keeps its identity:
    its record kind and key are locked, because those references tie exact
    records and condition semantics to them. Label, required flag, creation
    mode and order always stay editable."""
    _require_draft_version(role.journey)
    referenced = any(_role_references(role).values())
    for field in ("record_kind", "key"):
        new_value = changes.get(field)
        if new_value and new_value != getattr(role, field):
            if referenced:
                raise ValidationError(
                    {field: "This role is in use, so its " + field + " can no longer change."}
                )
            setattr(role, field, new_value)
    if "label" in changes:
        role.label = changes["label"]
    if "required" in changes:
        role.required = changes["required"]
    if "creation_mode" in changes:
        role.creation_mode = changes["creation_mode"]
    role.full_clean()
    role.save()


def delete_record_role(role):
    _require_draft_version(role.journey)
    references = _role_references(role)
    blocked = [name for name, used in references.items() if used]
    if blocked:
        raise ValidationError(
            "This record role is still referenced by " + ", ".join(blocked) + "; remove those first."
        )
    role.delete()


def move_record_role(role, direction):
    """Swap a role with its neighbour in role order."""
    _require_draft_version(role.journey)
    roles = list(JourneyRecordRole.objects.filter(journey=role.journey).order_by("order", "id"))
    index = roles.index(role)
    swap = index - 1 if direction == "up" else index + 1
    if swap < 0 or swap >= len(roles):
        return
    neighbour = roles[swap]
    with transaction.atomic():
        # Lift the moving row clear of the unique (journey, order) constraint
        # before the two positions change places.
        JourneyRecordRole.objects.filter(pk=role.pk).update(order=role.order + 10000)
        JourneyRecordRole.objects.filter(pk=neighbour.pk).update(order=role.order)
        JourneyRecordRole.objects.filter(pk=role.pk).update(order=neighbour.order)


def remove_dependency(journey, dependency):
    _require_draft_version(journey)
    if dependency.journey_id != journey.pk:
        raise ValidationError({"journey": "The dependency belongs to a different journey."})
    dependency.delete()


def bind_condition(condition, role):
    """Bind a saved-record condition on an assigned journey step to one of the
    journey's record roles. Purely authoring-level: no runtime verification
    behaviour is introduced here."""
    journey = role.journey
    _require_draft_version(journey)
    if condition.kind != VerificationCondition.Kind.SAVED_RECORD:
        raise ValidationError("Only saved-record conditions can be bound to a record role.")
    if not JourneyStep.objects.filter(step_id=condition.step_id, journey=journey).exists():
        raise ValidationError("The condition's step must be assigned to this journey.")
    if role.record_kind != condition.record_kind:
        raise ValidationError("The record role must use the same record kind as the condition.")
    binding, _created = JourneyConditionBinding.objects.get_or_create(condition=condition, role=role)
    return binding


def unbind_condition(binding):
    _require_draft_version(binding.role.journey)
    binding.delete()


def unbound_condition_issues(journey):
    """Saved-record conditions on assigned steps that have no record role
    binding yet — surfaced by the organizer's readiness checklist."""
    issues = []
    for assignment in ordered_assignments(journey):
        for condition in assignment.step.conditions.filter(
            kind=VerificationCondition.Kind.SAVED_RECORD
        ):
            if not JourneyConditionBinding.objects.filter(condition=condition).exists():
                issues.append(
                    'Step ' + str(assignment.journey_order) + ' ("' + assignment.step.title + '"): '
                    "a saved-record condition is not bound to a record role."
                )
    return issues


# --- Journey attempt advancement (student runtime) ------------------------------


def journey_advance(attempt):
    """Advance ``current_journey_step`` to the next canonical step when the
    learner's evidence allows it, and evaluate journey completion on the POST
    that earned it.

    Progression ceiling: walking the canonical order from the entry point,
    the first unsatisfied step locks everything after it — so no step beyond
    the learner's demonstrated position can ever be reached. Dependency edges
    (step-completed, record-available) are enforced on the target step.
    """
    with transaction.atomic():
        locked = JourneyAttempt.objects.select_for_update().get(pk=attempt.pk)
        rows = journey_step_rows(locked)
        if not rows:
            return locked, False, "This journey has no assigned steps yet."

        current_index = 0
        if locked.current_journey_step_id:
            for index, row in enumerate(rows):
                if row["assignment"].pk == locked.current_journey_step_id:
                    current_index = index
                    break

        target = current_index + 1
        if target >= len(rows):
            return locked, False, "This is the final step of the journey."

        reachable = [True]
        for index in range(1, len(rows)):
            reachable.append(reachable[index - 1] and rows[index - 1]["satisfied"])
        if not reachable[target]:
            blocked = rows[target]["step"].title
            return locked, False, '"' + blocked + '" is locked until the earlier steps are complete.'

        for dependency in JourneyDependency.objects.filter(journey=locked.journey, dependent_step=rows[target]["assignment"]):
            if dependency.dependency_type == JourneyDependency.DependencyType.RECORD_AVAILABLE:
                role_ok, _message = role_satisfied(locked, dependency.required_record_role)
                if not role_ok:
                    blocked = rows[target]["step"].title
                    role_label = dependency.required_record_role.label
                    return locked, False, (
                        '"' + blocked + '" needs the record role "' + role_label + '" satisfied first.'
                    )
            else:
                predecessor_row = next(
                    (row for row in rows if row["assignment"].pk == dependency.predecessor_step_id), None,
                )
                if predecessor_row and not predecessor_row["satisfied"]:
                    blocked = predecessor_row["step"].title
                    return locked, False, (
                        '"' + blocked + '" must be completed first.'
                    )

        locked.current_journey_step = rows[target]["assignment"]
        locked.last_activity_at = timezone.now()
        locked.save(update_fields=("current_journey_step", "last_activity_at"))

    # Completion evaluation, on the POST that earned it.
    rows_now = journey_step_rows(locked)
    required_roles = JourneyRecordRole.objects.filter(journey=locked.journey, required=True)
    roles_ok = all(role_satisfied(locked, role)[0] for role in required_roles)
    lesson_rows = LessonAttempt.objects.filter(
        enrolment=locked.enrolment,
        lesson_id__in=[row["step"].lesson_id for row in rows_now],
    )
    lessons_complete = lesson_rows.count() == len(rows_now) and all(
        row.completed_at is not None and row.theory_acknowledged_at is not None
        for row in lesson_rows
    )
    if all(row["satisfied"] for row in rows_now) and roles_ok and lessons_complete:
        if locked.completed_at is None:
            locked.completed_at = timezone.now()
            locked.status = JourneyAttempt.Status.COMPLETED
            locked.save(update_fields=("completed_at", "status"))
    return locked, True, "Advanced to the next step."
