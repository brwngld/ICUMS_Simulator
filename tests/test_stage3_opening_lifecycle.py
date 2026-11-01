"""Stage 3.3 Checkpoint 2D.1: transactional opening generations."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import IntegrityError, OperationalError, close_old_connections, transaction
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import journey_evidence, journey_services, verification
from hybrid.journey_evidence import CurrentVerification
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    JourneyVerificationEvidence,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration




def _world(db, seed="opening", *, with_evidence=False):
    programme = Programme.objects.create(
        name=seed, code=seed, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{seed}-course", title="Course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{seed}-module", title="Module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{seed}-lesson", title="Lesson", order=1, theory="<p>Theory</p>",
    )
    first = PracticalStep.objects.create(
        lesson=lesson, key="first", title="First", screen="single-window-overview", order=1,
    )
    second = PracticalStep.objects.create(
        lesson=lesson, key="second", title="Second", screen="single-window-overview", order=2,
    )
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code=f"{seed}-journey", title="Journey",
    )
    first_assignment = journey_services.assign_step(journey, first)
    second_assignment = journey_services.assign_step(journey, second)

    condition = role = association = record = None
    if with_evidence:
        condition = VerificationCondition.objects.create(
            step=first, kind=VerificationCondition.Kind.SAVED_RECORD,
            record_kind="ucr", required_status="draft",
            expected_fields={"exporter_name": "ACME Trading"}, order=1,
        )
        role = journey_services.create_record_role(
            journey, "declaration", "Declaration", "ucr",
            creation_mode=JourneyRecordRole.CreationMode.EXISTING,
        )
        journey_services.bind_condition(condition, role)

    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    student = User.objects.create_user(username=f"{seed}-student", password="x")
    enrolment = Enrolment.objects.create(student=student, programme_version=version)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    journey_attempt = journey_services.get_or_create_attempt(enrolment, journey)

    if with_evidence:
        record = UcrDeclaration.objects.create(
            owner=student, temp_no=f"{seed}-ucr", status="draft",
            exporter_name="ACME Trading", regime="CO",
        )
        association = journey_services.assign_record(
            journey_attempt, role, record.pk,
            JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
        )

    return {
        "student": student,
        "version": version,
        "lesson": lesson,
        "steps": (first, second),
        "assignments": (first_assignment, second_assignment),
        "lesson_attempt": lesson_attempt,
        "journey_attempt": journey_attempt,
        "condition": condition,
        "role": role,
        "association": association,
        "record": record,
    }


@pytest.mark.django_db
def test_first_journey_open_creates_one_stable_generation(db):
    world = _world(db, "opening-first")

    opened = verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert opened.generation is not None
    assert StepEvent.objects.filter(
        attempt=world["lesson_attempt"], step=world["steps"][0], kind=StepEvent.Kind.OPENED,
    ).count() == 1


@pytest.mark.django_db
def test_repeated_refresh_and_workspace_reentry_do_not_rotate_or_refresh(db):
    world = _world(db, "opening-repeat")
    first = verification.record_open(world["lesson_attempt"], world["steps"][0])
    original = (first.pk, first.generation, first.occurred_at)

    for _visit in range(3):
        reopened = verification.record_open(world["lesson_attempt"], world["steps"][0])
        assert (reopened.pk, reopened.generation, reopened.occurred_at) == original


@pytest.mark.django_db
def test_previous_and_next_navigation_preserve_each_opening(db):
    world = _world(db, "opening-navigation")
    first = verification.record_open(world["lesson_attempt"], world["steps"][0])
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        current_journey_step=world["assignments"][1],
    )
    second = verification.record_open(world["lesson_attempt"], world["steps"][1])

    previous = verification.record_open(world["lesson_attempt"], world["steps"][0])
    next_again = verification.record_open(world["lesson_attempt"], world["steps"][1])

    assert (previous.generation, previous.occurred_at) == (first.generation, first.occurred_at)
    assert (next_again.generation, next_again.occurred_at) == (second.generation, second.occurred_at)


@pytest.mark.django_db
def test_null_generation_is_adopted_without_refreshing_timestamp(db):
    world = _world(db, "opening-adopt")
    original_time = timezone.now() - timedelta(days=1)
    legacy = StepEvent.objects.create(
        attempt=world["lesson_attempt"], step=world["steps"][0],
        kind=StepEvent.Kind.OPENED, occurred_at=original_time, generation=None,
    )

    adopted = verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert adopted.pk == legacy.pk
    assert adopted.generation is not None
    assert adopted.occurred_at == original_time


@pytest.mark.django_db
def test_genuine_legacy_opening_still_refreshes_timestamp(db):
    world = _world(db, "opening-legacy")
    legacy_step = PracticalStep.objects.create(
        lesson=world["lesson"], key="legacy", title="Legacy", order=3,
    )
    old_time = timezone.now() - timedelta(days=1)
    event = StepEvent.objects.create(
        attempt=world["lesson_attempt"], step=legacy_step,
        kind=StepEvent.Kind.OPENED, occurred_at=old_time,
    )

    refreshed = verification.record_open(world["lesson_attempt"], legacy_step)

    assert refreshed.pk == event.pk
    assert refreshed.occurred_at > old_time
    assert refreshed.generation is None


@pytest.mark.django_db
def test_invalid_journey_context_refuses_instead_of_falling_back(db, client):
    world = _world(db, "opening-invalid")
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).delete()

    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(world["lesson_attempt"], world["steps"][0])
    assert excinfo.value.code == "attempt_missing"
    assert not StepEvent.objects.exists()

    client.force_login(world["student"])
    response = client.post(reverse("hybrid-step-open", args=(world["lesson_attempt"].pk, 0)))
    assert response.status_code == 403
    assert response.json()["code"] == "attempt_missing"


@pytest.mark.django_db
def test_completed_journey_allows_existing_navigation_but_no_new_generation(db):
    world = _world(db, "opening-completed")
    opened = verification.record_open(world["lesson_attempt"], world["steps"][0])
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED,
        completed_at=timezone.now(),
    )

    revisited = verification.record_open(world["lesson_attempt"], world["steps"][0])
    assert (revisited.generation, revisited.occurred_at) == (opened.generation, opened.occurred_at)
    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(world["lesson_attempt"], world["steps"][1])
    assert excinfo.value.code == "journey_completed"
    assert not StepEvent.objects.filter(step=world["steps"][1], kind=StepEvent.Kind.OPENED).exists()


@pytest.mark.django_db
def test_completed_journey_does_not_adopt_a_null_generation(db):
    world = _world(db, "opening-completed-null")
    original_time = timezone.now() - timedelta(days=1)
    legacy = StepEvent.objects.create(
        attempt=world["lesson_attempt"], step=world["steps"][0],
        kind=StepEvent.Kind.OPENED, occurred_at=original_time, generation=None,
    )
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED,
        completed_at=timezone.now(),
    )

    revisited = verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert revisited.pk == legacy.pk
    assert revisited.generation is None
    assert revisited.occurred_at == original_time


@pytest.mark.django_db
def test_repeated_opening_leaves_existing_evidence_current_and_unchanged(db):
    world = _world(db, "opening-evidence", with_evidence=True)
    opened = verification.record_open(world["lesson_attempt"], world["steps"][0])
    evidence = JourneyVerificationEvidence.objects.create(
        journey_attempt=world["journey_attempt"],
        lesson_attempt=world["lesson_attempt"],
        journey_step=world["assignments"][0],
        condition=world["condition"],
        condition_fingerprint=journey_evidence.condition_fingerprint(world["condition"]),
        role=world["role"],
        association=world["association"],
        record_kind="ucr",
        record_id=world["record"].pk,
        opening_generation=opened.generation,
        opening_occurred_at=opened.occurred_at,
    )

    verification.record_open(world["lesson_attempt"], world["steps"][0])
    evidence.refresh_from_db()
    current = journey_evidence.current_verification(
        world["student"], world["lesson_attempt"], world["steps"][0],
    )

    assert isinstance(current, CurrentVerification)
    assert current.evidence_ids == (evidence.pk,)
    assert evidence.opening_generation == opened.generation
    assert JourneyVerificationEvidence.objects.count() == 1


@pytest.mark.django_db
def test_opened_singleton_constraint_remains_the_concurrency_backstop(db):
    world = _world(db, "opening-singleton")
    verification.record_open(world["lesson_attempt"], world["steps"][0])

    with pytest.raises(IntegrityError), transaction.atomic():
        StepEvent.objects.create(
            attempt=world["lesson_attempt"], step=world["steps"][0],
            kind=StepEvent.Kind.OPENED, generation=uuid.uuid4(),
        )


def _threaded_open(attempt_id, step_id, barrier):
    """Use this thread's own Django connection for a simultaneous attempt."""
    close_old_connections()
    try:
        attempt = LessonAttempt.objects.get(pk=attempt_id)
        step = PracticalStep.objects.get(pk=step_id)
        barrier.wait(timeout=5)
        event = verification.record_open(attempt, step)
        return event.pk, event.generation, event.occurred_at
    finally:
        close_old_connections()


def _ensure_generation_schema():
    """Repair migration-test ordering before opening separate connections."""
    # Migrate the hybrid app to its latest migration — what ``migrate hybrid``
    # does. Pinning an ancestor would roll newer migrations back out of the
    # shared test database, breaking every suite that runs afterwards.
    executor = MigrationExecutor(connection)
    executor.migrate([key for key in executor.loader.graph.leaf_nodes() if key[0] == "hybrid"])


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_opening_returns_the_one_persisted_generation(transactional_db):
    """Actual simultaneous SQLite requests; each worker owns its connection."""
    _ensure_generation_schema()
    world = _world(transactional_db, "opening-concurrent-first")
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _threaded_open,
                world["lesson_attempt"].pk,
                world["steps"][0].pk,
                barrier,
            )
            for _index in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]

    persisted = StepEvent.objects.get(
        attempt=world["lesson_attempt"], step=world["steps"][0], kind=StepEvent.Kind.OPENED,
    )
    assert StepEvent.objects.filter(
        attempt=world["lesson_attempt"], step=world["steps"][0], kind=StepEvent.Kind.OPENED,
    ).count() == 1
    assert {result[0] for result in results} == {persisted.pk}
    assert {result[1] for result in results} == {persisted.generation}
    assert {result[2] for result in results} == {persisted.occurred_at}


@pytest.mark.django_db(transaction=True)
def test_concurrent_null_generation_adoption_observes_one_persisted_uuid(transactional_db):
    """Actual simultaneous SQLite adoption; compare-and-set chooses one UUID."""
    _ensure_generation_schema()
    world = _world(transactional_db, "opening-concurrent-adopt")
    original_time = timezone.now() - timedelta(days=1)
    StepEvent.objects.create(
        attempt=world["lesson_attempt"], step=world["steps"][0],
        kind=StepEvent.Kind.OPENED, occurred_at=original_time, generation=None,
    )
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _threaded_open,
                world["lesson_attempt"].pk,
                world["steps"][0].pk,
                barrier,
            )
            for _index in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]

    persisted = StepEvent.objects.get(
        attempt=world["lesson_attempt"], step=world["steps"][0], kind=StepEvent.Kind.OPENED,
    )
    assert persisted.generation is not None
    assert persisted.occurred_at == original_time
    assert {result[1] for result in results} == {persisted.generation}
    assert {result[2] for result in results} == {original_time}


@pytest.mark.django_db
def test_singleton_uniqueness_collision_refetches_the_winning_row(db):
    """Deterministic collision recovery; not a concurrency simulation."""
    world = _world(db, "opening-collision")
    winner = verification.record_open(world["lesson_attempt"], world["steps"][0])

    recovered = verification._create_opened_event(
        world["lesson_attempt"], world["steps"][0], generation=uuid.uuid4(),
    )

    assert recovered.pk == winner.pk
    assert recovered.generation == winner.generation
    assert recovered.occurred_at == winner.occurred_at


@pytest.mark.django_db
def test_expected_sqlite_contention_retries_the_complete_operation(db, monkeypatch):
    """Deterministic fault injection for the bounded retry contract."""
    world = _world(db, "opening-retry")
    original = verification._record_open_once
    calls = []

    def contended(attempt_id, step_id):
        calls.append((attempt_id, step_id))
        if len(calls) < 3:
            raise OperationalError("database is locked")
        return original(attempt_id, step_id)

    monkeypatch.setattr(verification, "_record_open_once", contended)
    monkeypatch.setattr(verification.time, "sleep", lambda _delay: None)

    opened = verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert opened.generation is not None
    assert calls == [(world["lesson_attempt"].pk, world["steps"][0].pk)] * 3


@pytest.mark.django_db
def test_sqlite_contention_retry_exhaustion_is_a_controlled_refusal(db, monkeypatch):
    world = _world(db, "opening-retry-exhausted")
    calls = []

    def always_locked(attempt_id, step_id):
        calls.append((attempt_id, step_id))
        raise OperationalError("database table is locked")

    monkeypatch.setattr(verification, "_record_open_once", always_locked)
    monkeypatch.setattr(verification.time, "sleep", lambda _delay: None)

    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert excinfo.value.code == "opening_contention"
    assert len(calls) == verification.OPENING_RETRY_LIMIT


@pytest.mark.django_db
def test_unexpected_integrity_error_is_not_swallowed(db, monkeypatch):
    world = _world(db, "opening-integrity")

    def broken_create(**_kwargs):
        raise IntegrityError("FOREIGN KEY constraint failed")

    monkeypatch.setattr(StepEvent.objects, "create", broken_create)

    with pytest.raises(IntegrityError, match="FOREIGN KEY"):
        verification.record_open(world["lesson_attempt"], world["steps"][0])


@pytest.mark.django_db
def test_direct_post_cannot_open_another_learners_attempt(db, client):
    world = _world(db, "opening-post-owner")
    other = User.objects.create_user(username="opening-post-other", password="x")
    client.force_login(other)

    response = client.post(reverse("hybrid-step-open", args=(world["lesson_attempt"].pk, 0)))

    assert response.status_code == 404
    assert not StepEvent.objects.exists()


@pytest.mark.django_db
def test_programme_enrolment_mismatch_refuses_without_writing(db):
    world = _world(db, "opening-programme")
    other_version = ProgrammeVersion.objects.create(
        programme=world["version"].programme, version=2,
    )
    Enrolment.objects.filter(pk=world["lesson_attempt"].enrolment_id).update(
        programme_version=other_version,
    )
    world["lesson_attempt"].refresh_from_db()

    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(world["lesson_attempt"], world["steps"][0])

    assert excinfo.value.code == "programme_mismatch"
    assert not StepEvent.objects.exists()


@pytest.mark.django_db
def test_dependency_blocked_first_opening_writes_nothing(db):
    world = _world(db, "opening-dependency")
    verification.record_open(world["lesson_attempt"], world["steps"][0])
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        current_journey_step=world["assignments"][1],
    )
    role = JourneyRecordRole.objects.create(
        journey=world["journey_attempt"].journey,
        key="required", label="Required", record_kind="ucr",
        creation_mode=JourneyRecordRole.CreationMode.EXISTING, order=1,
    )
    from hybrid.models import JourneyDependency
    JourneyDependency.objects.create(
        journey=world["journey_attempt"].journey,
        predecessor_step=world["assignments"][0],
        dependent_step=world["assignments"][1],
        dependency_type=JourneyDependency.DependencyType.RECORD_AVAILABLE,
        required_record_role=role,
        order=1,
    )

    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(world["lesson_attempt"], world["steps"][1])

    assert excinfo.value.code == "dependency_blocked"
    assert not StepEvent.objects.filter(step=world["steps"][1], kind=StepEvent.Kind.OPENED).exists()


@pytest.mark.django_db
def test_locked_lesson_attempt_relationship_is_revalidated(db, monkeypatch):
    world = _world(db, "opening-locked-lesson")
    other_lesson = HybridLesson.objects.create(
        module=world["lesson"].module,
        slug="opening-locked-other", title="Other lesson", order=2, theory="<p>Theory</p>",
    )
    wrong_attempt = LessonAttempt.objects.create(
        enrolment=world["lesson_attempt"].enrolment,
        lesson=other_lesson,
    )
    assignment = world["assignments"][0]
    journey_attempt = world["journey_attempt"]
    monkeypatch.setattr(
        verification,
        "_journey_opening_context",
        lambda _attempt, _step: (assignment, journey_attempt),
    )

    with pytest.raises(verification.JourneyOpeningError) as excinfo:
        verification.record_open(wrong_attempt, world["steps"][0])

    assert excinfo.value.code == "step_mismatch"
    assert not StepEvent.objects.exists()


def _completed_post_world(db, seed, generation_marker):
    world = _world(db, seed)
    opening = None
    if generation_marker != "missing":
        opening = StepEvent.objects.create(
            attempt=world["lesson_attempt"], step=world["steps"][0],
            kind=StepEvent.Kind.OPENED,
            generation=(uuid.uuid4() if generation_marker == "uuid" else None),
        )
    JourneyAttempt.objects.filter(pk=world["journey_attempt"].pk).update(
        status=JourneyAttempt.Status.COMPLETED,
        completed_at=timezone.now(),
    )
    return world, opening


@pytest.mark.django_db
def test_completed_journey_post_preserves_existing_uuid(db, client):
    world, opening = _completed_post_world(db, "opening-post-complete", "uuid")
    client.force_login(world["student"])

    response = client.post(reverse("hybrid-step-open", args=(world["lesson_attempt"].pk, 0)))

    assert response.status_code == 200
    opening.refresh_from_db()
    assert opening.generation is not None


@pytest.mark.django_db
def test_completed_journey_post_does_not_adopt_null_uuid(db, client):
    world, opening = _completed_post_world(db, "opening-post-complete-null", "null")
    original_time = opening.occurred_at
    client.force_login(world["student"])

    response = client.post(reverse("hybrid-step-open", args=(world["lesson_attempt"].pk, 0)))

    assert response.status_code == 200
    opening.refresh_from_db()
    assert opening.generation is None
    assert opening.occurred_at == original_time


@pytest.mark.django_db
def test_completed_journey_post_without_opening_is_refused(db, client):
    world, _opening = _completed_post_world(db, "opening-post-complete-missing", "missing")
    client.force_login(world["student"])

    response = client.post(reverse("hybrid-step-open", args=(world["lesson_attempt"].pk, 0)))

    assert response.status_code == 403
    assert response.json()["code"] == "journey_completed"
    assert not StepEvent.objects.exists()
