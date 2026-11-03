"""Server-side verification for hybrid practical steps.

The browser reports nothing here that the server trusts: a step's conditions
are evaluated against the learner's own saved simulator records and the
durable ``StepEvent`` ledger. Freshness follows the guided-practical engine's
rule — a qualifying record must show activity at or after the moment the
learner opened the step — so unrelated pre-existing records can never satisfy
a new task. Only a passing check writes a ``verified`` event, and the partial
unique constraint makes a second one impossible; the browser merely learns
the result.
"""
import uuid
import time

from django.db import IntegrityError, OperationalError, connection, transaction
from django.utils import timezone

from scenarios.bindings import VERIFY_RECORDS

from . import journey_evidence
from .models import (
    JourneyAttempt,
    JourneyDependency,
    JourneyStep,
    LessonAttempt,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)


OPENING_RETRY_LIMIT = 3
OPENING_RETRY_BASE_DELAY = 0.01

#: PostgreSQL SQLSTATEs meaning "collision — the statement may be re-run".
#: ``40001`` serialization failure, ``40P01`` deadlock detector, ``55P03`` the
#: caller gave up waiting on a lock. Everything else travels untouched, because
#: retrying a constraint violation or a syntax error only hides a defect.
_POSTGRES_CONTENTION_CODES = frozenset({"40001", "40P01", "55P03"})


class JourneyOpeningError(Exception):
    """Controlled refusal for an invalid journey-bound step opening."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def step_conditions(step):
    return list(step.conditions.order_by("order", "id"))


def step_requires_verification(step):
    """A step with no conditions asks for nothing and never blocks progress."""
    return step.conditions.exists()


def opened_at(attempt, step):
    """The freshness bound: when the learner last entered this step."""
    event = StepEvent.objects.filter(attempt=attempt, step=step, kind=StepEvent.Kind.OPENED).first()
    return event.occurred_at if event else attempt.started_at


def record_activity(record):
    """The moment a record was last worked: its newest of update, submission or
    creation. The verification engines and the learner's record picker read
    freshness from here, so a row the picker calls fresh can never be refused as
    stale by the check that follows it."""
    moments = [
        getattr(record, "updated_at", None),
        getattr(record, "submitted_at", None),
        getattr(record, "created_at", None),
    ]
    return max((moment for moment in moments if moment is not None), default=None)


def _opening_fail(message, code):
    raise JourneyOpeningError(message, code)


def _journey_opening_context(attempt, step):
    """Discover optional journey context without taking locks.

    A missing assignment is the only legacy signal. Once a step is assigned,
    every missing or incoherent journey row is a controlled refusal and must
    never fall through to timestamp-refresh behavior.
    """
    assignment = (
        JourneyStep.objects.filter(step=step)
        .select_related("journey__course", "step__lesson__module__course")
        .first()
    )
    if assignment is None:
        return None
    enrolment = attempt.enrolment
    journey = assignment.journey
    if step.lesson_id != attempt.lesson_id:
        _opening_fail("The step does not belong to this lesson attempt.", "step_mismatch")
    if (
        journey.programme_version_id != enrolment.programme_version_id
        or journey.course.programme_version_id != enrolment.programme_version_id
        or step.lesson.module.course_id != journey.course_id
    ):
        _opening_fail("This journey does not match the learner's enrolment.", "programme_mismatch")
    journey_attempt = JourneyAttempt.objects.filter(enrolment=enrolment, journey=journey).first()
    if journey_attempt is None:
        _opening_fail("No journey attempt is available for this learner.", "attempt_missing")
    return assignment, journey_attempt


def _require_openable(journey_attempt, assignment, opening_exists):
    """Revalidate navigation authority while the journey attempt is locked."""
    from . import journey_services

    if journey_attempt.status == JourneyAttempt.Status.COMPLETED:
        if opening_exists:
            return
        _opening_fail("This journey step is not currently available.", "journey_completed")
    if journey_attempt.status != JourneyAttempt.Status.IN_PROGRESS:
        _opening_fail("The journey attempt is not in progress.", "attempt_not_in_progress")

    current = journey_attempt.current_journey_step
    if current is None or current.journey_id != journey_attempt.journey_id:
        _opening_fail("This journey step is not currently available.", "step_not_current")
    if assignment.journey_order > current.journey_order:
        _opening_fail("This journey step is not currently available.", "step_not_current")
    if assignment.pk != current.pk:
        if opening_exists:
            return
        _opening_fail("This journey step is not currently available.", "step_not_current")

    rows = journey_services.journey_step_rows(journey_attempt)
    target_index = next(
        (index for index, row in enumerate(rows) if row["assignment"].pk == assignment.pk),
        None,
    )
    if target_index is None:
        _opening_fail("This step is not assigned to the journey.", "step_not_assigned")
    if any(not row["satisfied"] for row in rows[:target_index]):
        _opening_fail("This journey step is locked by earlier work.", "progression_blocked")

    dependencies = JourneyDependency.objects.filter(
        journey=journey_attempt.journey,
        dependent_step=assignment,
    ).select_related("predecessor_step", "required_record_role")
    row_by_assignment = {row["assignment"].pk: row for row in rows}
    for dependency in dependencies:
        if dependency.dependency_type == JourneyDependency.DependencyType.RECORD_AVAILABLE:
            role = dependency.required_record_role
            if role is None or role.journey_id != journey_attempt.journey_id:
                _opening_fail("This journey dependency is invalid.", "dependency_invalid")
            if not journey_services.role_satisfied(journey_attempt, role)[0]:
                _opening_fail("This journey step is waiting for a required record.", "dependency_blocked")
        else:
            predecessor = row_by_assignment.get(dependency.predecessor_step_id)
            if predecessor is None or not predecessor["satisfied"]:
                _opening_fail("This journey step is waiting for an earlier step.", "dependency_blocked")


def _is_opened_singleton_collision(exc):
    constraint_name = getattr(getattr(exc, "__cause__", None), "diag", None)
    if constraint_name is not None:
        return constraint_name.constraint_name == "unique_hybrid_step_opened"
    message = str(exc).lower()
    return (
        "unique constraint failed" in message
        and "hybrid_stepevent.attempt_id" in message
        and "hybrid_stepevent.step_id" in message
    )


def is_sqlite_contention(exc):
    if connection.vendor != "sqlite":
        return False
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def _sqlstate(error):
    """The driver's own error code, under either name the drivers use.

    Django rebuilds driver exceptions (``django/db/utils.py``) and hangs the
    original off ``__cause__``; only the cause carries ``pgcode``/``sqlstate``.
    Reading the top-level exception alone would never see a real PostgreSQL
    collision.
    """
    for _ in range(5):
        if error is None:
            return None
        code = getattr(error, "pgcode", None) or getattr(error, "sqlstate", None)
        if code:
            return code
        error = error.__cause__
    return None


#: Public form of ``_sqlstate`` for the scoped save service
#: (``scenarios.demonstration_ucr``), which classifies a lost reference race by
#: the driver's own code rather than by an engine's wording.
driver_sqlstate = _sqlstate


def is_database_contention(error):
    """Would re-running this statement be honest?

    The two engines report a collision differently: SQLite only in the message,
    PostgreSQL only in the SQLSTATE. A driver that reports neither is never
    treated as contended, so an unexpected error cannot be swallowed by a retry.
    """
    if connection.vendor == "sqlite":
        return is_sqlite_contention(error)
    if connection.vendor == "postgresql":
        return _sqlstate(error) in _POSTGRES_CONTENTION_CODES
    return False


def _create_opened_event(locked_attempt, step, *, generation):
    """Create the singleton, or return the row that won its exact race.

    The nested atomic block is a savepoint. An expected uniqueness collision
    rolls back there, leaving the surrounding transaction usable for the
    recovery read. Other integrity failures retain their original exception.
    """
    try:
        with transaction.atomic():
            return StepEvent.objects.create(
                attempt=locked_attempt,
                step=step,
                kind=StepEvent.Kind.OPENED,
                occurred_at=timezone.now(),
                generation=generation,
            )
    except IntegrityError as exc:
        if not _is_opened_singleton_collision(exc):
            raise
        winner = StepEvent.objects.filter(
            attempt=locked_attempt,
            step=step,
            kind=StepEvent.Kind.OPENED,
        ).first()
        if winner is None:
            raise
        return winner


def _record_legacy_open(attempt, step):
    """Preserve the original timestamp-refresh behavior under row locks."""
    with transaction.atomic():
        locked_attempt = LessonAttempt.objects.select_for_update().get(pk=attempt.pk)
        event = StepEvent.objects.select_for_update().filter(
            attempt=locked_attempt, step=step, kind=StepEvent.Kind.OPENED,
        ).first()
        if event is None:
            return _create_opened_event(locked_attempt, step, generation=None)
        event.occurred_at = timezone.now()
        event.save(update_fields=("occurred_at",))
        return event


def _record_open_once(attempt_id, step_id):
    """Run one complete, freshly resolved opening transaction."""
    attempt = LessonAttempt.objects.select_related(
        "enrolment", "lesson__module__course",
    ).get(pk=attempt_id)
    step = PracticalStep.objects.select_related("lesson__module__course").get(pk=step_id)
    discovered = _journey_opening_context(attempt, step)
    if discovered is None:
        return _record_legacy_open(attempt, step)

    discovered_assignment, discovered_journey_attempt = discovered
    with transaction.atomic():
        # current_journey_step is nullable, and PostgreSQL refuses FOR UPDATE on
        # the nullable side of an outer join; only the attempt row needs the lock.
        journey_attempt = (
            JourneyAttempt.objects.select_for_update(of=("self",))
            .select_related("journey", "current_journey_step", "enrolment")
            .get(pk=discovered_journey_attempt.pk)
        )
        locked_attempt = (
            LessonAttempt.objects.select_for_update()
            .select_related("enrolment", "lesson__module__course")
            .get(pk=attempt.pk)
        )
        assignment = (
            JourneyStep.objects.select_related("journey__course", "step__lesson__module__course")
            .filter(pk=discovered_assignment.pk, step=step)
            .first()
        )
        if assignment is None:
            _opening_fail("This step is not assigned to the journey.", "step_not_assigned")
        if step.lesson_id != locked_attempt.lesson_id:
            _opening_fail("The step does not belong to this lesson attempt.", "step_mismatch")
        if (
            journey_attempt.enrolment_id != locked_attempt.enrolment_id
            or journey_attempt.journey_id != assignment.journey_id
            or assignment.journey.programme_version_id != locked_attempt.enrolment.programme_version_id
            or assignment.journey.course_id != locked_attempt.lesson.module.course_id
        ):
            _opening_fail("This journey does not match the learner's enrolment.", "programme_mismatch")

        event = StepEvent.objects.select_for_update().filter(
            attempt=locked_attempt, step=step, kind=StepEvent.Kind.OPENED,
        ).first()
        _require_openable(journey_attempt, assignment, event is not None)
        if journey_attempt.status == JourneyAttempt.Status.COMPLETED:
            return event
        if event is None:
            return _create_opened_event(locked_attempt, step, generation=uuid.uuid4())
        if event.generation is None:
            candidate = uuid.uuid4()
            StepEvent.objects.filter(pk=event.pk, generation__isnull=True).update(
                generation=candidate,
            )
            event.refresh_from_db(fields=("generation", "occurred_at"))
        return event


def record_open(attempt, step):
    """Record a legacy visit or return a journey step's stable generation.

    Journey context is discovered before the transaction and then resolved
    again after locking JourneyAttempt -> LessonAttempt -> StepEvent. Ordinary
    navigation never rotates a journey opening or refreshes its timestamp.
    Database contention retries the complete operation from scalar IDs, so
    every attempt reloads and reauthorizes current database state.
    """
    attempt_id, step_id = attempt.pk, step.pk
    for retry_index in range(OPENING_RETRY_LIMIT):
        try:
            return _record_open_once(attempt_id, step_id)
        except OperationalError as exc:
            if not is_database_contention(exc):
                raise
            if retry_index + 1 == OPENING_RETRY_LIMIT:
                _opening_fail(
                    "This journey step is not currently available.",
                    "opening_contention",
                )
            time.sleep(OPENING_RETRY_BASE_DELAY * (retry_index + 1))


def is_verified(attempt, step):
    return StepEvent.objects.filter(attempt=attempt, step=step, kind=StepEvent.Kind.VERIFIED).exists()


def mark_verified(attempt, step):
    """Stamp the checkpoint once; repeats are absorbed by the constraint."""
    event, _created = StepEvent.objects.get_or_create(
        attempt=attempt, step=step, kind=StepEvent.Kind.VERIFIED, defaults={"occurred_at": timezone.now()},
    )
    return event


def _latest_activity(record):
    moments = [
        getattr(record, "updated_at", None),
        getattr(record, "submitted_at", None),
        getattr(record, "created_at", None),
    ]
    moments = [moment for moment in moments if moment is not None]
    return max(moments) if moments else None


def _verify_saved_record(attempt, condition):
    model, model_label = VERIFY_RECORDS[condition.record_kind]
    owner = attempt.enrolment.student
    bound = opened_at(attempt, condition.step)
    owned = model.objects.filter(owner=owner)
    if not owned.exists():
        return False, f"No {model_label} records exist for your account yet. Complete the task in the simulator, then check again."

    expected = condition.expected_fields if isinstance(condition.expected_fields, dict) else {}
    matching = owned.filter(status=condition.required_status, **expected)
    if matching.exists():
        if any((_latest_activity(record) or record.created_at) >= bound for record in matching):
            return True, "Verified."
        return False, (
            f"Your {model_label} records with the required status all predate this step. "
            "Complete the task now, then check again."
        )
    if expected and owned.filter(status=condition.required_status).exists():
        return False, (
            f"Your {model_label} has the required status, but the saved values do not match. "
            "Correct the record, then check again."
        )
    latest = owned.order_by("-created_at").first()
    latest_display = latest.get_status_display() if latest else "unknown"
    choices = dict(model._meta.get_field("status").choices)
    required_display = choices.get(condition.required_status, condition.required_status)
    return False, (
        f"Your latest {model_label} is “{latest_display}” — this step requires “{required_display}”. "
        "Complete the task in the simulator, then check again."
    )


def _verify_screen_opened(attempt, condition):
    if StepEvent.objects.filter(attempt=attempt, step=condition.step, kind=StepEvent.Kind.OPENED).exists():
        return True, "Verified."
    return False, "Open the step's simulator screen first, then check again."


def verify_step(attempt, step):
    """Evaluate every condition; return a JSON-safe result dictionary."""
    results = []
    for condition in step_conditions(step):
        if condition.kind == VerificationCondition.Kind.SAVED_RECORD:
            passed, message = _verify_saved_record(attempt, condition)
        else:
            passed, message = _verify_screen_opened(attempt, condition)
        results.append({"label": condition.describe(), "passed": passed, "message": message})
    passed = bool(results) and all(result["passed"] for result in results)
    if passed:
        mark_verified(attempt, step)
    return {"passed": passed, "results": results}


def step_satisfied(attempt, step):
    """Whether this attempt currently satisfies one practical step.

    A condition-free step asks for nothing. A step assigned to a journey is
    judged by its current journey verification evidence, so a historical
    ``VERIFIED`` stamp never authorizes progression once the record, the
    condition or the opening it was earned under has changed. A step outside
    every journey keeps the legacy ``VERIFIED`` rule unchanged.
    """
    if not step_requires_verification(step):
        return True
    if JourneyStep.objects.filter(step=step).exists():
        return isinstance(
            journey_evidence.current_verification(attempt.enrolment.student, attempt, step),
            journey_evidence.CurrentVerification,
        )
    return is_verified(attempt, step)


def satisfied_steps(attempt):
    """Which of the lesson's steps are satisfied (verified or condition-free)."""
    return {
        step.pk for step in attempt.lesson.practical_steps.all() if step_satisfied(attempt, step)
    }


def refresh_completion(attempt):
    """Write lesson completion when theory is acknowledged and all steps are
    satisfied; returns True when the attempt is (or just became) complete."""
    if attempt.completed_at:
        return True
    if attempt.theory_acknowledged_at is None:
        return False
    if satisfied_steps(attempt) != {step.pk for step in attempt.lesson.practical_steps.all()}:
        return False
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=("completed_at",))
    return True


def attempt_snapshot(attempt):
    """The JSON the workspace embeds so the browser can resume exactly where
    the server says the learner stands."""
    steps = list(attempt.lesson.practical_steps.order_by("order", "id"))
    satisfied = satisfied_steps(attempt)
    current_index = 0
    if attempt.current_step and attempt.current_step in steps:
        current_index = steps.index(attempt.current_step)
    return {
        "id": str(attempt.pk),
        "current_index": current_index,
        "satisfied": [steps.index(step) for step in steps if step.pk in satisfied],
        "theory_acknowledged": attempt.theory_acknowledged_at is not None,
        "lesson_complete": attempt.completed_at is not None,
        "requires": {
            str(step.pk): [
                {"kind": condition.kind, "label": condition.describe()}
                for condition in step_conditions(step)
            ]
            for step in steps
        },
    }


def attempt_for(request_user, attempt_id):
    """The user's own attempt, or None — never another learner's."""
    return LessonAttempt.objects.filter(pk=attempt_id, enrolment__student=request_user).first()
