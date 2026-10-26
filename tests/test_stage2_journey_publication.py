"""Stage 2 Checkpoint 6: journey-aware publication and clone-to-draft.

Publication validates every practical journey in the edition — its structure,
its dependencies, and whether its record roles can be satisfied by the runtime
at all. Clone-to-draft copies journey structure onto the new edition with every
step, role, condition and dependency reference remapped, and never copies what
a learner has done: attempts, step events and record associations stay on the
edition the learner is enrolled on.
"""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import journey_services, publishing
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration

SCREEN = "single-window-overview"
CONDITIONAL_STEP = 1


def _instructor(db, username="journey-publisher"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def _learner(db, username):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Student")[0])
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _edition(code, courses=1, lessons=2):
    """An edition of complete, publishable lessons.

    Returns the edition with its courses and every practical step in curriculum
    order, so a journey can be built on top of finished lesson content.
    """
    programme = Programme.objects.create(
        name=f"Publication {code}", code=code, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    world = {"programme": programme, "version": version, "courses": [], "steps": []}
    for course_index in range(1, courses + 1):
        course = HybridCourse.objects.create(
            programme_version=version, code=f"{code}-course-{course_index}",
            title=f"{code} course {course_index}", order=course_index,
        )
        world["courses"].append(course)
        module = HybridModule.objects.create(
            course=course, code=f"{code}-module-{course_index}", title=f"{code} module", order=1,
        )
        for lesson_index in range(1, lessons + 1):
            lesson = HybridLesson.objects.create(
                module=module, slug=f"{code}-lesson-{course_index}-{lesson_index}",
                title=f"{code} lesson {course_index}.{lesson_index}", order=lesson_index,
                summary="What the lesson covers.", theory="<p>Theory reading.</p>",
            )
            step = PracticalStep.objects.create(
                lesson=lesson, key=f"step-{lesson_index}", title=f"Step {course_index}.{lesson_index}",
                instruction="Do the thing.", outcome="The record is saved.", screen=SCREEN, order=1,
            )
            if lesson_index == CONDITIONAL_STEP:
                VerificationCondition.objects.create(
                    step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="ucr",
                    required_status="draft", expected_fields={"exporter_name": "ACME Trading"}, order=1,
                )
            world["steps"].append(step)
    return world


def _course_steps(world, course):
    return [step for step in world["steps"] if step.lesson.module.course_id == course.pk]


def _journey(world, course_index=1, title="Declaration journey", steps=True, role=True, dependency=True,
             binding=True, start_mode=PracticalJourney.StartMode.EXISTING_RECORD):
    """A structurally complete journey: the course's steps in canonical order, a
    step-completed dependency between them, an existing-record role, and a
    saved-record condition bound to that role.

    Each part can be left out, so a test builds exactly the incomplete shape it
    means to name.
    """
    course = world["courses"][course_index - 1]
    journey = journey_services.create_journey(world["version"], course, title=title, start_mode=start_mode)
    owned = _course_steps(world, course)
    assignments = [journey_services.assign_step(journey, step) for step in owned] if steps else []
    role_row = None
    if role:
        role_row = journey_services.create_record_role(
            journey, "declaration", "Export declaration", "ucr",
            creation_mode=JourneyRecordRole.CreationMode.EXISTING,
        )
    if dependency and len(assignments) > 1:
        journey_services.add_dependency(
            journey, assignments[0], assignments[1], JourneyDependency.DependencyType.STEP_COMPLETED,
        )
    if binding and role_row is not None:
        condition = owned[0].conditions.filter(kind=VerificationCondition.Kind.SAVED_RECORD).first()
        if condition is not None:
            journey_services.bind_condition(condition, role_row)
    return journey


def _authored_rows(version_id):
    """Every journey-structure row of one edition, keyed by its own identity
    fields rather than its primary key, so a clone can be compared with its
    source and a mutation of the source can be detected."""
    return {
        "assignments": sorted(
            JourneyStep.objects.filter(journey__programme_version_id=version_id).values_list(
                "journey__code", "step__key", "journey_order",
            )
        ),
        "roles": sorted(
            JourneyRecordRole.objects.filter(journey__programme_version_id=version_id).values_list(
                "journey__code", "key", "label", "record_kind", "required", "creation_mode", "order",
            )
        ),
        "dependencies": sorted(
            JourneyDependency.objects.filter(journey__programme_version_id=version_id).values_list(
                "journey__code", "predecessor_step__step__key", "dependent_step__step__key",
                "dependency_type", "required_record_role__key", "order",
            )
        ),
        "bindings": sorted(
            JourneyConditionBinding.objects.filter(role__journey__programme_version_id=version_id).values_list(
                "role__journey__code", "role__key", "condition__step__key",
            )
        ),
    }


# --- Cloning ----------------------------------------------------------------------


@pytest.mark.django_db
def test_complete_journeys_clone_onto_the_new_edition(db):
    """A journey in every course of the edition is copied once, whole."""
    world = _edition("clonejourney", courses=2)
    first = _journey(world, 1, title="First course journey")
    second = _journey(world, 2, title="Second course journey")
    published, skipped, warnings = publishing.publish_edition(world["version"])
    assert (skipped, warnings) == ([], [])
    assert len(published) == 2

    draft = publishing.clone_to_draft(world["version"])
    copied = {journey.code: journey for journey in PracticalJourney.objects.filter(programme_version=draft)}
    assert set(copied) == {first.code, second.code}

    journey = copied[first.code]
    assert journey.title == first.title
    assert journey.description == first.description
    assert journey.order == first.order
    assert journey.start_mode == first.start_mode
    assert journey.course.programme_version_id == draft.pk
    assert journey.course.code == first.course.code
    assert [assignment.journey_order for assignment in journey.step_assignments.order_by("journey_order")] == [1, 2]
    assert [
        assignment.step.key for assignment in journey.step_assignments.order_by("journey_order")
    ] == [assignment.step.key for assignment in first.step_assignments.order_by("journey_order")]
    assert [
        (role.key, role.label, role.record_kind, role.required, role.creation_mode, role.order)
        for role in journey.record_roles.order_by("order")
    ] == [
        (role.key, role.label, role.record_kind, role.required, role.creation_mode, role.order)
        for role in first.record_roles.order_by("order")
    ]
    dependency = journey.dependencies.get()
    source_dependency = first.dependencies.get()
    assert dependency.dependency_type == source_dependency.dependency_type
    assert dependency.order == source_dependency.order
    assert dependency.predecessor_step_id != source_dependency.predecessor_step_id
    assert JourneyConditionBinding.objects.filter(role__journey=journey).count() == 1
    assert not HybridCourse.objects.filter(programme_version=draft, is_published=True).exists()


@pytest.mark.django_db
def test_every_cloned_reference_points_into_the_new_edition(db):
    world = _edition("remap", courses=2)
    _journey(world, 1, title="One")
    _journey(world, 2, title="Two")
    publishing.publish_edition(world["version"])
    source = world["version"]
    draft = publishing.clone_to_draft(source)
    source_steps = set(
        PracticalStep.objects.filter(lesson__module__course__programme_version=source).values_list("pk", flat=True)
    )

    journeys = list(PracticalJourney.objects.filter(programme_version=draft))
    assert len(journeys) == 2
    for journey in journeys:
        assignments = list(journey.step_assignments.all())
        assert assignments, "the cloned journey lost its steps"
        assert journey.course.programme_version_id == draft.pk
        for assignment in assignments:
            assert assignment.step_id not in source_steps
            assert assignment.step.lesson.module.course.programme_version_id == draft.pk
        for dependency in journey.dependencies.all():
            assert dependency.predecessor_step_id in {row.pk for row in assignments}
            assert dependency.dependent_step_id in {row.pk for row in assignments}
            if dependency.required_record_role_id:
                assert dependency.required_record_role.journey_id == journey.pk
        for binding in JourneyConditionBinding.objects.filter(role__journey=journey):
            assert binding.role.journey_id == journey.pk
            assert binding.condition.step_id not in source_steps
            assert binding.condition.step.journey_assignment.journey_id == journey.pk


@pytest.mark.django_db
def test_a_failed_clone_leaves_no_partial_edition(db, monkeypatch):
    world = _edition("cloneatomic")
    _journey(world)
    publishing.publish_edition(world["version"])
    source = world["version"]
    before = {
        "versions": ProgrammeVersion.objects.count(),
        "courses": HybridCourse.objects.count(),
        "lessons": HybridLesson.objects.count(),
        "steps": PracticalStep.objects.count(),
        "journeys": PracticalJourney.objects.count(),
    }
    original = publishing.clone_journeys

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("clone interrupted on purpose")

    monkeypatch.setattr(publishing, "clone_journeys", interrupted)
    with pytest.raises(RuntimeError):
        publishing.clone_to_draft(source)

    assert ProgrammeVersion.objects.count() == before["versions"]
    assert HybridCourse.objects.count() == before["courses"]
    assert HybridLesson.objects.count() == before["lessons"]
    assert PracticalStep.objects.count() == before["steps"]
    assert PracticalJourney.objects.count() == before["journeys"]


@pytest.mark.django_db
def test_cloning_copies_no_learner_state(db):
    world = _edition("nostate")
    journey = _journey(world)
    publishing.publish_edition(world["version"])
    source = world["version"]
    learner = _learner(db, "journey-learner")
    enrolment = Enrolment.objects.create(student=learner, programme_version=source)
    assignment = journey.step_assignments.order_by("journey_order").first()
    attempt = journey_services.get_or_create_attempt(enrolment, journey)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=assignment.step.lesson)
    StepEvent.objects.create(attempt=lesson_attempt, step=assignment.step, kind=StepEvent.Kind.OPENED)
    record = UcrDeclaration.objects.create(
        owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMP-CLONE-1",
    )
    journey_services.assign_record(
        attempt, journey.record_roles.get(), record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    before = {
        "journey_attempts": JourneyAttempt.objects.count(),
        "associations": JourneyRecordAssociation.objects.count(),
        "lesson_attempts": LessonAttempt.objects.count(),
        "events": StepEvent.objects.count(),
    }

    draft = publishing.clone_to_draft(source)

    assert JourneyAttempt.objects.count() == before["journey_attempts"]
    assert JourneyRecordAssociation.objects.count() == before["associations"]
    assert LessonAttempt.objects.count() == before["lesson_attempts"]
    assert StepEvent.objects.count() == before["events"]
    assert not JourneyAttempt.objects.filter(journey__programme_version=draft).exists()
    assert not JourneyRecordAssociation.objects.filter(programme_version=draft).exists()
    assert not LessonAttempt.objects.filter(lesson__module__course__programme_version=draft).exists()
    assert not StepEvent.objects.filter(attempt__lesson__module__course__programme_version=draft).exists()
    attempt.refresh_from_db()
    assert attempt.journey_id == journey.pk
    assert JourneyRecordAssociation.objects.get(journey_attempt=attempt).role.journey_id == journey.pk


@pytest.mark.django_db
def test_the_source_edition_is_unchanged_by_cloning(db):
    world = _edition("sourceintact")
    _journey(world)
    publishing.publish_edition(world["version"])
    source = world["version"]
    journey = PracticalJourney.objects.get(programme_version=source)
    journey_fields = (journey.title, journey.description, journey.order, journey.start_mode, journey.updated_at)
    rows_before = _authored_rows(source.pk)

    clone = publishing.clone_to_draft(source)

    journey.refresh_from_db()
    assert (journey.title, journey.description, journey.order, journey.start_mode, journey.updated_at) == journey_fields
    assert _authored_rows(source.pk) == rows_before
    # The clone carries the same structure under different identities.
    assert _authored_rows(clone.pk) == {
        key: [tuple(row) for row in value] for key, value in rows_before.items()
    }


# --- Publication gates --------------------------------------------------------------


@pytest.mark.django_db
def test_an_empty_journey_blocks_publication(db):
    world = _edition("emptyjourney")
    journey = _journey(world, steps=False, dependency=False, binding=False, role=False)
    blockers = publishing.edition_blockers(world["version"])

    assert len(blockers) == 1
    assert blockers[0].startswith(f"Course “{world['courses'][0].title}”: ")
    assert "Journey “Declaration journey”:" in blockers[0]
    assert "No practical steps are assigned to this journey." in blockers[0]
    assert publishing.course_blockers(journey.course) == [
        "Journey “Declaration journey”: No practical steps are assigned to this journey."
    ]


@pytest.mark.django_db
def test_a_journey_without_record_roles_blocks_publication(db):
    world = _edition("noroles")
    _journey(world, role=False, binding=False)
    assert publishing.edition_blockers(world["version"]) == [
        'Course “noroles course 1”: Journey “Declaration journey”: '
        "No record roles are defined for this journey."
    ]


@pytest.mark.django_db
def test_an_inconsistent_dependency_blocks_publication(db):
    """A backward edge — only writable around the service — blocks publication,
    because the runtime can never walk it."""
    world = _edition("backwards")
    journey = _journey(world)
    assignments = list(journey.step_assignments.order_by("journey_order"))
    JourneyDependency.objects.create(
        journey=journey,
        predecessor_step=assignments[1],
        dependent_step=assignments[0],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
        order=journey.dependencies.count() + 1,
    )
    blockers = publishing.edition_blockers(world["version"])
    assert len(blockers) == 1
    assert "does not follow the journey order" in blockers[0]


@pytest.mark.django_db
def test_a_journey_outside_the_editions_courses_blocks_publication(db):
    """Publication validates every journey of the edition, including one whose
    course was pointed at another edition — both editions name the mismatch,
    the one carrying the journey through its course and the one it was authored
    on."""
    world = _edition("orphanjourney")
    journey = _journey(world)
    other_version = ProgrammeVersion.objects.create(
        programme=world["programme"], version=2, status=ProgrammeVersion.Status.DRAFT,
    )
    other = HybridCourse.objects.create(
        programme_version=other_version, code="elsewhere", title="Elsewhere course", order=1,
    )
    journey.course_id = other.pk
    journey.save(update_fields=("course",))

    blockers = publishing.edition_blockers(world["version"])
    assert len(blockers) == 1
    assert "its course belongs to another edition." in blockers[0]
    assert "Journey “Declaration journey”: its course belongs to another edition." in publishing.course_blockers(other)
    assert publishing.journey_scope_issues(journey) == ["its course belongs to another edition."]

    journey.course_id = world["courses"][0].pk
    journey.save(update_fields=("course",))
    assert publishing.journey_scope_issues(journey) == []
    assert publishing.edition_blockers(world["version"]) == []
    assert journey.programme_version_id == world["courses"][0].programme_version_id


@pytest.mark.django_db
def test_a_required_new_record_role_blocks_publication(db):
    world = _edition("requirednew")
    journey = _journey(world)
    journey_services.create_record_role(
        journey, "fresh", "Freshly created declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    blockers = publishing.edition_blockers(world["version"])
    assert len(blockers) == 1
    assert 'required record role “Freshly created declaration” cannot be satisfied' in blockers[0]
    assert "cannot yet verify that a record was created within a journey." in blockers[0]


@pytest.mark.django_db
def test_a_journey_on_a_module_less_course_still_blocks_publication(db):
    """A course with no modules is not ready, and its journeys are readied with
    it rather than skipped: the module report used to short-circuit them."""
    world = _edition("nomodules")
    course = HybridCourse.objects.create(
        programme_version=world["version"], code="bare", title="Bare course", order=2,
    )
    journey = journey_services.create_journey(world["version"], course, title="Bare journey")
    journey_services.create_record_role(
        journey, "fresh", "Fresh declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )

    blockers = publishing.course_blockers(course)
    assert blockers == [
        "Add at least one module.",
        "Journey “Bare journey”: No practical steps are assigned to this journey.",
        'Journey “Bare journey”: required record role “Fresh declaration” cannot be satisfied: '
        "the system cannot yet verify that a record was created within a journey.",
    ]
    assert publishing.edition_blockers(world["version"]) == [
        f"Course “{course.title}”: " + " ".join(blockers),
    ]

    # Close the module gap and give the journey its step: it publishes with the
    # course instead of being skipped alongside it.
    module = HybridModule.objects.create(course=course, code="bare-module", title="Bare module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug="bare-lesson", title="Bare lesson", order=1,
        summary="What the lesson covers.", theory="<p>Theory reading.</p>",
    )
    step = PracticalStep.objects.create(
        lesson=lesson, key="bare-step", title="Bare step", instruction="Do the thing.",
        outcome="The record is saved.", screen=SCREEN, order=1,
    )
    journey_services.assign_step(journey, step)
    journey_services.update_record_role(journey.record_roles.get(), {"creation_mode": "existing"})
    assert publishing.edition_blockers(world["version"]) == []

    published, skipped, warnings = publishing.publish_edition(world["version"])
    assert course in published and skipped == [] and warnings == []
    for row in (course, module, lesson):
        row.refresh_from_db()
    assert course.is_published and lesson.is_published and module.is_published


@pytest.mark.django_db
def test_journey_publication_blockers_name_structure_then_roles(db):
    """The per-journey blocker list the edition gate and the organizer both
    read: structural issues first, then the roles the runtime cannot satisfy."""
    world = _edition("blockerlist")
    journey = _journey(world)
    journey_services.create_record_role(
        journey, "fresh", "Fresh declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    assert publishing.journey_publication_blockers(journey) == [
        'required record role “Fresh declaration” cannot be satisfied: the system '
        "cannot yet verify that a record was created within a journey."
    ]

    assignments = list(journey.step_assignments.order_by("journey_order"))
    JourneyDependency.objects.create(
        journey=journey,
        predecessor_step=assignments[1],
        dependent_step=assignments[0],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
        order=journey.dependencies.count() + 1,
    )
    blockers = publishing.journey_publication_blockers(journey)
    assert len(blockers) == 3
    assert "does not follow the journey order" in blockers[0]
    assert "The dependency graph contains a cycle." in blockers[1]
    assert "Fresh declaration" in blockers[2]


@pytest.mark.django_db
def test_an_optional_new_record_role_warns_without_blocking(db):
    world = _edition("optionalnew")
    journey = _journey(world)
    journey_services.create_record_role(
        journey, "spare", "Spare declaration", "ucr",
        required=False, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    assert publishing.edition_blockers(world["version"]) == []

    published, skipped, warnings = publishing.publish_edition(world["version"])
    assert [course.pk for course in published] == [journey.course.pk]
    assert skipped == []
    assert len(warnings) == 1
    assert 'optional record role “Spare declaration” cannot currently be satisfied' in warnings[0]


@pytest.mark.django_db
def test_an_unbound_saved_record_condition_warns_because_it_is_still_verifiable(db):
    """The verification engine checks a saved-record condition by record kind,
    status and saved values, so an unbound one is a note, not a blocker."""
    world = _edition("unbound")
    journey = _journey(world, binding=False)
    assert publishing.journey_publication_blockers(journey) == []
    warnings = publishing.journey_publication_warnings(journey)
    assert len(warnings) == 1
    assert "not bound to a record role" in warnings[0]

    condition = _course_steps(world, journey.course)[0].conditions.get()
    journey_services.bind_condition(condition, journey.record_roles.get())
    assert publishing.journey_publication_warnings(journey) == []


@pytest.mark.django_db
def test_a_condition_on_an_unregistered_record_kind_blocks_publication(db):
    """An unbound condition only warns while the verification engine can still
    check it; a record kind outside the registry can never be checked, so the
    step could never clear and publication is blocked."""
    world = _edition("unregistered")
    journey = _journey(world, binding=False)
    step = _course_steps(world, journey.course)[1]
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="manifest",
        required_status="draft", order=1,
    )
    blockers = publishing.edition_blockers(world["version"])
    assert len(blockers) == 1
    assert f'step “{step.title}” has a saved-record condition on “manifest”' in blockers[0]
    assert "not an approved simulator record" in blockers[0]
    assert publishing.journey_publication_warnings(journey) == []


@pytest.mark.django_db
def test_an_existing_record_journey_publishes(db):
    world = _edition("existingrecord")
    journey = _journey(world, start_mode=PracticalJourney.StartMode.EXISTING_RECORD)
    assert publishing.edition_blockers(world["version"]) == []

    published, skipped, warnings = publishing.publish_edition(world["version"])
    assert [course.pk for course in published] == [journey.course.pk]
    assert (skipped, warnings) == ([], [])
    assert all(lesson.is_published for lesson in HybridLesson.objects.filter(module__course=journey.course))
    assert ProgrammeVersion.objects.get(pk=world["version"].pk).status == ProgrammeVersion.Status.PUBLISHED


# --- Immutability and student continuity ----------------------------------------------


@pytest.mark.django_db
def test_a_published_edition_refuses_journey_and_lesson_edits(db):
    world = _edition("immutable")
    journey = _journey(world)
    publishing.publish_edition(world["version"])
    step = _course_steps(world, journey.course)[1]

    with pytest.raises(PermissionDenied):
        journey_services.assign_step(journey, step)
    with pytest.raises(PermissionDenied):
        journey_services.update_record_role(journey.record_roles.get(), {"label": "Renamed role"})

    instructor = _instructor(db)
    client = Client()
    client.force_login(instructor)
    lesson = journey.step_assignments.order_by("journey_order").first().step.lesson
    assert client.get(reverse("hybrid-lesson-edit", args=[lesson.pk])).status_code == 404
    assert client.get(reverse("hybrid-journey-detail", args=[journey.pk])).status_code == 404

    draft = publishing.clone_to_draft(world["version"])
    draft_journey = PracticalJourney.objects.get(programme_version=draft, code=journey.code)
    assert client.get(reverse("hybrid-journey-detail", args=[draft_journey.pk])).status_code == 200


@pytest.mark.django_db
def test_republishing_a_published_edition_changes_nothing(db):
    world = _edition("republish")
    journey = _journey(world)
    first = publishing.publish_edition(world["version"])
    published_at = ProgrammeVersion.objects.get(pk=world["version"].pk).published_at
    rows_before = _authored_rows(world["version"].pk)

    second = publishing.publish_edition(world["version"])

    assert [course.pk for course in second[0]] == [course.pk for course in first[0]]
    assert second[1] == [] and second[2] == []
    assert ProgrammeVersion.objects.get(pk=world["version"].pk).published_at == published_at
    assert _authored_rows(world["version"].pk) == rows_before
    assert PracticalJourney.objects.filter(programme_version=world["version"]).count() == 1


@pytest.mark.django_db
def test_learners_keep_their_edition_and_progress_through_publication_and_cloning(db):
    world = _edition("continuity")
    journey = _journey(world)
    publishing.publish_edition(world["version"])
    source = world["version"]
    learner = _learner(db, "continuity-learner")
    enrolment = Enrolment.objects.create(student=learner, programme_version=source)
    assignment = journey.step_assignments.order_by("journey_order").first()
    attempt = journey_services.get_or_create_attempt(enrolment, journey)
    lesson_attempt = LessonAttempt.objects.create(
        enrolment=enrolment, lesson=assignment.step.lesson, completed_at=timezone.now(),
    )
    event = StepEvent.objects.create(attempt=lesson_attempt, step=assignment.step, kind=StepEvent.Kind.OPENED)
    record = UcrDeclaration.objects.create(
        owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMP-CONTINUITY-1",
    )
    association = journey_services.assign_record(
        attempt, journey.record_roles.get(), record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    draft = publishing.clone_to_draft(source)
    publishing.publish_edition(draft)

    enrolment.refresh_from_db()
    attempt.refresh_from_db()
    assert enrolment.programme_version_id == source.pk
    assert attempt.journey_id == journey.pk
    assert attempt.current_journey_step_id == assignment.pk
    assert LessonAttempt.objects.get(pk=lesson_attempt.pk).lesson_id == assignment.step.lesson_id
    assert StepEvent.objects.get(pk=event.pk).attempt_id == lesson_attempt.pk
    assert JourneyRecordAssociation.objects.get(pk=association.pk).journey_attempt_id == attempt.pk
    assert ProgrammeVersion.objects.get(pk=draft.pk).status == ProgrammeVersion.Status.PUBLISHED
    assert ProgrammeVersion.objects.filter(programme=source.programme).count() == 2

    client = Client()
    client.force_login(learner)
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert world["courses"][0].title in html


# --- What the instructor is told ---------------------------------------------------------


@pytest.mark.django_db
def test_the_publish_action_names_the_blocking_journey(client, db):
    instructor = _instructor(db)
    world = _edition("actionblockers")
    journey = _journey(world)
    journey_services.create_record_role(
        journey, "fresh", "Freshly created declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"), {"action": "publish_edition", "version_id": world["version"].pk},
    )
    messages = " ".join(str(message) for message in get_messages(response.wsgi_request))

    assert "not ready to publish" in messages
    assert "Declaration journey" in messages
    assert "Freshly created declaration" in messages
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.DRAFT
    assert not HybridCourse.objects.filter(programme_version=world["version"], is_published=True).exists()


@pytest.mark.django_db
def test_the_publish_action_carries_the_journey_warnings_of_a_published_edition(client, db):
    instructor = _instructor(db)
    world = _edition("actionwarnings")
    journey = _journey(world, binding=False)
    journey_services.create_record_role(
        journey, "spare", "Spare declaration", "ucr",
        required=False, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"), {"action": "publish_edition", "version_id": world["version"].pk},
    )
    messages = [
        (message.level, str(message)) for message in get_messages(response.wsgi_request)
    ]

    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.PUBLISHED
    assert any("published with 1 course" in text for _level, text in messages)
    journey_texts = [text for _level, text in messages if "Spare declaration" in text or "not bound" in text]
    assert len(journey_texts) == 2


# --- Checkpoint 6 corrections: direct service calls cannot bypass the gates ------------


@pytest.mark.django_db
def test_a_direct_service_publish_refuses_a_required_new_record_role(db):
    """publish_edition itself — not just the organizer's gate — refuses while a
    required NEW record role cannot be satisfied."""
    world = _edition("directnew")
    journey = _journey(world)
    journey_services.create_record_role(
        journey, "fresh", "Freshly created declaration", "ucr",
        required=True, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )

    with pytest.raises(ValidationError) as excinfo:
        publishing.publish_edition(world["version"])

    assert "Freshly created declaration" in str(excinfo.value)
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.DRAFT
    assert not HybridCourse.objects.filter(programme_version=world["version"], is_published=True).exists()


@pytest.mark.django_db
def test_a_direct_service_publish_refuses_a_journey_outside_the_edition(db):
    world = _edition("directscope")
    journey = _journey(world)
    other_version = ProgrammeVersion.objects.create(
        programme=world["programme"], version=2, status=ProgrammeVersion.Status.DRAFT,
    )
    other = HybridCourse.objects.create(
        programme_version=other_version, code="directelsewhere", title="Elsewhere course", order=1,
    )
    journey.course_id = other.pk
    journey.save(update_fields=("course",))

    with pytest.raises(ValidationError) as excinfo:
        publishing.publish_edition(world["version"])

    assert "its course belongs to another edition" in str(excinfo.value)
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.DRAFT
    assert not HybridCourse.objects.filter(programme_version=world["version"], is_published=True).exists()


@pytest.mark.django_db
def test_a_direct_service_publish_refuses_an_unverifiable_condition(db):
    world = _edition("directunverifiable")
    journey = _journey(world, binding=False)
    step = _course_steps(world, journey.course)[1]
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="manifest",
        required_status="draft", order=1,
    )

    with pytest.raises(ValidationError) as excinfo:
        publishing.publish_edition(world["version"])

    assert "not an approved simulator record" in str(excinfo.value)
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_a_direct_service_publish_refuses_a_structurally_invalid_journey(db):
    world = _edition("directbackwards")
    journey = _journey(world)
    assignments = list(journey.step_assignments.order_by("journey_order"))
    JourneyDependency.objects.create(
        journey=journey,
        predecessor_step=assignments[1],
        dependent_step=assignments[0],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
        order=journey.dependencies.count() + 1,
    )

    with pytest.raises(ValidationError) as excinfo:
        publishing.publish_edition(world["version"])

    assert "does not follow the journey order" in str(excinfo.value)
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.DRAFT
    assert not HybridLesson.objects.filter(
        module__course__programme_version=world["version"], is_published=True,
    ).exists()


@pytest.mark.django_db
def test_the_service_preserves_the_partial_publication_contract(db):
    """The safeguard only adds the journey gate. Lesson-completeness blockers
    keep the documented skip path: ready courses publish around an unfinished
    one, and the edition becomes the live edition."""
    world = _edition("partialkeep", courses=2)
    _journey(world, 1)
    ready, unfinished = world["courses"]
    HybridLesson.objects.create(
        module=HybridModule.objects.get(course=unfinished), slug="partialkeep-gap",
        title="Unfinished lesson", order=99, summary="", theory="",
    )

    published, skipped, warnings = publishing.publish_edition(world["version"])

    assert [course.pk for course in published] == [ready.pk]
    assert [course.pk for course in skipped] == [unfinished.pk]
    assert warnings == []
    world["version"].refresh_from_db()
    assert world["version"].status == ProgrammeVersion.Status.PUBLISHED
    unfinished.refresh_from_db()
    assert unfinished.is_published is False


# --- Checkpoint 6 corrections: cloning validation --------------------------------------


@pytest.mark.django_db
def test_clone_rejects_a_journey_whose_course_is_in_another_edition(db):
    world = _edition("cloneforeigncourse")
    journey = _journey(world)
    other_version = ProgrammeVersion.objects.create(
        programme=world["programme"], version=2, status=ProgrammeVersion.Status.DRAFT,
    )
    other = HybridCourse.objects.create(
        programme_version=other_version, code="clonewhere", title="Elsewhere course", order=1,
    )
    journey.course_id = other.pk
    journey.save(update_fields=("course",))
    before = ProgrammeVersion.objects.count()

    with pytest.raises(ValidationError) as excinfo:
        publishing.clone_to_draft(world["version"])

    message = str(excinfo.value)
    assert "Declaration journey" in message
    assert "is not part of the source edition" in message
    assert ProgrammeVersion.objects.count() == before
    assert not ProgrammeVersion.objects.filter(version=3).exists()


@pytest.mark.django_db
def test_clone_rejects_a_step_reference_from_another_edition(db):
    """A JourneyStep written around the service, pointing at another edition's
    step, is named by the validation instead of dying in a KeyError — and the
    failed clone leaves no draft behind."""
    world = _edition("cloneforeignstep")
    journey = _journey(world)
    other_version = ProgrammeVersion.objects.create(
        programme=world["programme"], version=2, status=ProgrammeVersion.Status.DRAFT,
    )
    other_course = HybridCourse.objects.create(
        programme_version=other_version, code="clonestepper", title="Stepper course", order=1,
    )
    other_module = HybridModule.objects.create(course=other_course, code="clonestepper-m", title="Stepper module", order=1)
    foreign_lesson = HybridLesson.objects.create(
        module=other_module, slug="clonestepper-lesson", title="Foreign lesson", order=1,
        summary="Summary.", theory="<p>Theory.</p>",
    )
    foreign_step = PracticalStep.objects.create(
        lesson=foreign_lesson, key="foreign-step", title="Foreign step",
        instruction="Do it.", outcome="Done.", screen=SCREEN, order=1,
    )
    JourneyStep.objects.create(journey=journey, step=foreign_step, journey_order=99)
    before = {
        "versions": ProgrammeVersion.objects.count(),
        "courses": HybridCourse.objects.count(),
        "steps": PracticalStep.objects.count(),
    }

    with pytest.raises(ValidationError) as excinfo:
        publishing.clone_to_draft(world["version"])

    message = str(excinfo.value)
    assert "Declaration journey" in message
    assert "Foreign step" in message
    assert "is not part of the source edition" in message
    assert ProgrammeVersion.objects.count() == before["versions"]
    assert not ProgrammeVersion.objects.filter(version=3).exists()
    assert HybridCourse.objects.count() == before["courses"]
    assert PracticalStep.objects.count() == before["steps"]


@pytest.mark.django_db
def test_clone_rejects_a_dependency_reaching_outside_its_journey(db):
    world = _edition("clonedep", courses=2)
    first = _journey(world, 1, title="First")
    second = _journey(world, 2, title="Second")
    first_assignments = list(first.step_assignments.order_by("journey_order"))
    foreign_assignment = second.step_assignments.order_by("journey_order").first()
    JourneyDependency.objects.create(
        journey=first,
        predecessor_step=first_assignments[0],
        dependent_step=foreign_assignment,
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
        order=99,
    )
    before = ProgrammeVersion.objects.count()

    with pytest.raises(ValidationError) as excinfo:
        publishing.clone_to_draft(world["version"])

    message = str(excinfo.value)
    assert "First" in message
    assert "does not belong to this journey" in message
    assert ProgrammeVersion.objects.count() == before
    assert not ProgrammeVersion.objects.filter(version=3).exists()


@pytest.mark.django_db
def test_clone_rejects_a_condition_binding_from_another_journey(db):
    """A condition binding written around the service, tying one journey's
    condition to another journey's role, is named by the validation instead of
    silently cloning a cross-journey edge — and the failed clone leaves no
    draft behind."""
    world = _edition("clonebinding", courses=2)
    first = _journey(world, 1, title="First", binding=False)
    second = _journey(world, 2, title="Second")
    condition = first.step_assignments.order_by("journey_order").first().step.conditions.get()
    JourneyConditionBinding.objects.create(condition=condition, role=second.record_roles.get())
    before = ProgrammeVersion.objects.count()

    with pytest.raises(ValidationError) as excinfo:
        publishing.clone_to_draft(world["version"])

    message = str(excinfo.value)
    assert "First" in message
    assert "Export declaration" in message
    assert "belongs to another journey" in message
    assert ProgrammeVersion.objects.count() == before
    assert not ProgrammeVersion.objects.filter(version=3).exists()
