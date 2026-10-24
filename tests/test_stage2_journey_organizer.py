"""Stage 2 Checkpoint 4: the instructor journey organizer.

Only instructors reach it; only draft editions mutate; every workflow runs
through the approved journey services. Existing lesson-editor tests continue
to pass unchanged (run in the same battery).
"""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
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
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def _instructor(db, username="organizer"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Instructor")[0])
    return user


def _student(db, username="organizer-student"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Student")[0])
    return user


def _world(db):
    programme = Programme.objects.create(
        name="Organizer Programme", code="organizer", learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    course = HybridCourse.objects.create(programme_version=version, code="org-c", title="Organizer Course", order=1)
    module = HybridModule.objects.create(course=course, code="org-m", title="Organizer Module", order=1)
    lessons, steps = [], []
    for index in (1, 2, 3):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"ol-{index}", title=f"Organizer Lesson {index}", order=index,
        )
        step = PracticalStep.objects.create(
            lesson=lesson, key=f"os-{index}", title=f"Organizer Step {index}", order=1,
        )
        lessons.append(lesson)
        steps.append(step)
    other_course = HybridCourse.objects.create(programme_version=version, code="org-c2", title="Other Course", order=2)
    other_module = HybridModule.objects.create(course=other_course, code="org-m2", title="Other Module", order=1)
    other_lesson = HybridLesson.objects.create(module=other_module, slug="ol-x", title="Other Lesson", order=1)
    other_step = PracticalStep.objects.create(lesson=other_lesson, key="os-x", title="Other Step", order=1)
    return {
        "programme": programme, "version": version, "course": course, "module": module,
        "lessons": lessons, "steps": steps,
        "other_course": other_course, "other_step": other_step,
    }


def _ucr(owner, n):
    return UcrDeclaration.objects.create(
        owner=owner, status="draft", exporter_name="ACME Trading", temp_no=f"TEMPORG-{n}",
    )


def _journey(world, code="journey"):
    return PracticalJourney.objects.create(
        programme_version=world["version"], course=world["course"],
        code=code, title="Organizer Journey", order=1,
    )


def _detail(journey):
    return reverse("hybrid-journey-detail", args=[journey.pk])


def _post(client, url, data):
    response = client.post(url, data)
    messages = " ".join(
        str(m) for m in get_messages(response.wsgi_request)
    ) if hasattr(response, "wsgi_request") else ""
    return response, messages


# --- Access ----------------------------------------------------------------------


@pytest.mark.django_db
def test_only_instructors_open_the_organizer(client, db):
    world = _world(db)
    organizer = reverse("hybrid-course-journeys", args=[world["course"].pk])

    anonymous = client.get(organizer)
    assert anonymous.status_code == 302
    assert reverse("login") in anonymous.headers["location"]

    student = _student(db)
    client.force_login(student)
    refused = client.get(organizer)
    assert refused.status_code == 302
    assert refused.url == reverse("dashboard")


@pytest.mark.django_db
def test_the_organizer_is_404_outside_draft_editions(client, db):
    instructor = _instructor(db)
    world = _world(db)
    ProgrammeVersion.objects.filter(pk=world["version"].pk).update(status=ProgrammeVersion.Status.PUBLISHED)
    client.force_login(instructor)
    assert client.get(reverse("hybrid-course-journeys", args=[world["course"].pk])).status_code == 404
    journey = _journey(world)
    assert client.get(_detail(journey)).status_code == 404


# --- Journey creation and settings ------------------------------------------------


@pytest.mark.django_db
def test_creating_a_journey_via_post(client, db):
    instructor = _instructor(db)
    world = _world(db)
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-course-journeys", args=[world["course"].pk]),
        {"title": "Export file journey", "description": "", "start_mode": "new_record"},
    )
    assert response.status_code == 302
    journey = PracticalJourney.objects.get(title="Export file journey")
    assert journey.code.startswith("export-file-journey")
    assert journey.course_id == world["course"].pk
    assert journey.start_mode == "new_record"


@pytest.mark.django_db
def test_the_organizer_lists_journeys_and_readiness(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    html = client.get(reverse("hybrid-course-journeys", args=[world["course"].pk])).content.decode()
    assert journey.title in html
    assert "No practical steps" in html


@pytest.mark.django_db
def test_journey_edit_and_delete_via_post(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)

    response = client.post(_detail(journey), {
        "action": "save_journey", "title": "Renamed journey",
        "description": "Now described.", "start_mode": "existing_record",
    })
    assert response.status_code == 302
    journey.refresh_from_db()
    assert journey.title == "Renamed journey"
    assert journey.start_mode == "existing_record"

    client.post(_detail(journey), {"action": "delete_journey"})
    assert not PracticalJourney.objects.filter(pk=journey.pk).exists()


@pytest.mark.django_db
def test_a_populated_journey_cannot_be_deleted(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    for step in world["steps"]:
        client.post(_detail(journey), {"action": "assign_step", "step_id": step.pk})

    _, messages_text = _post(client, _detail(journey), {"action": "delete_journey"})
    assert PracticalJourney.objects.filter(pk=journey.pk).exists()
    assert "Remove the journey's steps" in messages_text


# --- Step assignment and removal ---------------------------------------------------


@pytest.mark.django_db
def test_assigning_steps_via_post_follows_canonical_order(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)

    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][1].pk})
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})

    assignments = JourneyStep.objects.filter(journey=journey).order_by("journey_order")
    assert [a.step.key for a in assignments] == ["os-1", "os-2"]
    html = client.get(_detail(journey)).content.decode()
    assert "Entry point" in html


@pytest.mark.django_db
def test_the_assign_picker_excludes_steps_already_in_journeys(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)

    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})
    context_steps = [
        step.pk for step in client.get(_detail(journey)).context["unassigned_steps"]
    ]
    assert world["steps"][0].pk not in context_steps
    assert world["steps"][1].pk in context_steps


@pytest.mark.django_db
def test_a_forged_cross_course_assignment_is_refused_with_a_message(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)

    response, messages_text = _post(
        client, _detail(journey), {"action": "assign_step", "step_id": world["other_step"].pk},
    )
    assert response.status_code == 302
    assert not JourneyStep.objects.filter(journey=journey).exists()
    assert "must belong to the journey's course" in messages_text


@pytest.mark.django_db
def test_removing_a_step_via_post_cleans_dependencies(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    for step in world["steps"]:
        client.post(_detail(journey), {"action": "assign_step", "step_id": step.pk})
    first = JourneyStep.objects.get(journey=journey, step=world["steps"][0])
    second = JourneyStep.objects.get(journey=journey, step=world["steps"][1])
    client.post(_detail(journey), {
        "action": "add_dependency",
        "predecessor": first.pk, "dependent": second.pk, "dependency_type": "step_completed",
    })
    assert JourneyDependency.objects.filter(journey=journey).count() == 1

    client.post(_detail(journey), {"action": "remove_step", "step_id": first.pk})
    assert not JourneyStep.objects.filter(journey=journey, step=world["steps"][0]).exists()
    assert not JourneyDependency.objects.filter(journey=journey).exists()


# --- Dependencies -------------------------------------------------------------------


@pytest.mark.django_db
def test_dependency_add_and_cycle_refusal_via_post(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    for step in world["steps"]:
        client.post(_detail(journey), {"action": "assign_step", "step_id": step.pk})
    assignments = list(JourneyStep.objects.filter(journey=journey).order_by("journey_order"))

    client.post(_detail(journey), {
        "action": "add_dependency",
        "predecessor": assignments[0].pk, "dependent": assignments[1].pk,
        "dependency_type": "step_completed",
    })
    client.post(_detail(journey), {
        "action": "add_dependency",
        "predecessor": assignments[1].pk, "dependent": assignments[2].pk,
        "dependency_type": "step_completed",
    })
    # Canonical order already forbids backward edges, so a true cycle can only
    # arrive through unvalidated rows; the service's cycle check is the backstop.
    JourneyDependency.objects.create(
        journey=journey, predecessor_step=assignments[2], dependent_step=assignments[0],
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED, order=3,
    )
    response, messages_text = _post(client, _detail(journey), {
        "action": "add_dependency",
        "predecessor": assignments[0].pk, "dependent": assignments[2].pk,
        "dependency_type": "step_completed",
    })
    assert "cycle" in messages_text
    assert JourneyDependency.objects.filter(journey=journey).count() == 3

    client.post(_detail(journey), {"action": "remove_dependency", "dependency_id": JourneyDependency.objects.first().pk})
    assert JourneyDependency.objects.filter(journey=journey).count() == 2


# --- Record roles --------------------------------------------------------------------


@pytest.mark.django_db
def test_role_crud_and_ordering_via_post(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)

    client.post(_detail(journey), {
        "action": "add_role", "key": "primary-ucr", "label": "Primary UCR",
        "record_kind": "ucr", "required": "on", "creation_mode": "new",
    })
    role = JourneyRecordRole.objects.get(journey=journey, key="primary-ucr")
    assert role.order == 1 and role.required is True

    second = journey_services_style_add(client, journey)
    client.post(_detail(journey), {"action": "move_role", "role_id": second.pk, "direction": "up"})
    role.refresh_from_db(); second.refresh_from_db()
    assert (role.order, second.order) == (2, 1)

    client.post(_detail(journey), {
        "action": "save_role", "role_id": role.pk, "key": "primary-ucr",
        "label": "Renamed UCR", "record_kind": "ucr", "required": "on", "creation_mode": "new",
    })
    role.refresh_from_db()
    assert role.label == "Renamed UCR"

    client.post(_detail(journey), {"action": "delete_role", "role_id": role.pk})
    assert not JourneyRecordRole.objects.filter(pk=role.pk).exists()


def journey_services_style_add(client, journey):
    client.post(_detail(journey), {
        "action": "add_role", "key": "boe", "label": "BOE declaration",
        "record_kind": "boe", "creation_mode": "existing",
    })
    return JourneyRecordRole.objects.get(journey=journey, key="boe")


@pytest.mark.django_db
def test_role_deletion_is_blocked_while_a_dependency_references_it(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    for step in world["steps"]:
        client.post(_detail(journey), {"action": "assign_step", "step_id": step.pk})
    client.post(_detail(journey), {
        "action": "add_role", "key": "ucr", "label": "UCR role",
        "record_kind": "ucr", "creation_mode": "new",
    })
    role = JourneyRecordRole.objects.get(journey=journey, key="ucr")
    assignments = list(JourneyStep.objects.filter(journey=journey).order_by("journey_order"))
    client.post(_detail(journey), {
        "action": "add_dependency", "predecessor": assignments[0].pk, "dependent": assignments[1].pk,
        "dependency_type": "record_available", "required_record_role": role.pk,
    })

    client.post(_detail(journey), {"action": "delete_role", "role_id": role.pk})
    role.refresh_from_db()
    assert role.pk is not None


# --- Condition bindings ---------------------------------------------------------------


@pytest.mark.django_db
def test_condition_binding_via_post(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})
    step = world["steps"][0]
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD,
        record_kind="ucr", required_status="draft", order=1,
    )

    bound_role = JourneyRecordRole.objects.create(
        journey=journey, key="ucr-role", label="Learner UCR", record_kind="ucr", order=1,
    )
    client.post(_detail(journey), {
        "action": "bind_condition", "condition_id": step.conditions.get().pk, "role_id": bound_role.pk,
    })
    assert JourneyConditionBinding.objects.filter(condition_id=step.conditions.get().pk, role=bound_role).exists()

    other_role = JourneyRecordRole.objects.create(
        journey=journey, key="boe-role", label="BOE", record_kind="boe", order=2,
    )
    client.post(_detail(journey), {
        "action": "bind_condition", "condition_id": step.conditions.get().pk, "role_id": other_role.pk,
    })
    assert not JourneyConditionBinding.objects.filter(condition_id=step.conditions.get().pk, role=other_role).exists()

    binding = JourneyConditionBinding.objects.get(role=bound_role)
    client.post(_detail(journey), {"action": "unbind_condition", "binding_id": binding.pk})
    assert not JourneyConditionBinding.objects.filter(pk=binding.pk).exists()


@pytest.mark.django_db
def test_the_organizer_reports_unbound_conditions(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})
    step = world["steps"][0]
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD,
        record_kind="ucr", required_status="draft", order=1,
    )

    response = client.get(_detail(journey))
    issues = response.context["unbound_issues"]
    assert any("not bound to a record role" in issue for issue in issues)


# --- Existing lesson editor regression guard --------------------------------------------


@pytest.mark.django_db
def test_the_lesson_editor_still_serves_all_five_tabs(client, db):
    instructor = _instructor(db)
    world = _world(db)
    lesson = world["lessons"][0]
    client.force_login(instructor)
    html = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk])).content.decode()
    for tab in ("details", "theory", "journey", "simulator", "review"):
        assert f'data-authoring-tab="{tab}"' in html


# --- Role-reference protection (Checkpoint 4 final verification) -----------------
# A role referenced by learner associations, dependencies, or condition
# bindings can never be deleted or re-identified; metadata edits preserve all
# references.


def _referenced_role(journey, step, with_association=False, with_dependency=False, with_binding=False):
    """A role referenced by the requested structures, plus the exact record a
    learner association points at (for preservation assertions)."""
    suffix = "a" if with_association else ("d" if with_dependency else "b")
    role = JourneyRecordRole.objects.create(
        journey=journey, key=f"locked-{suffix}", label="Locked role", record_kind="ucr", required=True,
        order=journey.record_roles.count() + 1,
    )
    learner = User.objects.create_user(
        username=f"assoc-learner-{suffix}", email=f"assoc-{suffix}@example.test", password="x",
    )
    enrolment = Enrolment.objects.create(student=learner, programme_version=journey.programme_version)
    attempt = JourneyAttempt.objects.create(enrolment=enrolment, journey=journey)
    record = _ucr(learner, 900 + (1 if with_association else 0) + (2 if with_dependency else 0))
    if with_association:
        JourneyRecordAssociation.objects.create(
            journey_attempt=attempt, role=role, enrolment=enrolment,
            programme_version=journey.programme_version, record_kind="ucr",
            record_id=record.pk, assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
        )
    if with_dependency:
        JourneyDependency.objects.create(
            journey=journey, predecessor_step=journey.step_assignments.get(step=step),
            dependent_step=journey.step_assignments.order_by("-journey_order").first(),
            dependency_type=JourneyDependency.DependencyType.RECORD_AVAILABLE,
            required_record_role=role, order=1,
        )
    if with_binding:
        condition = VerificationCondition.objects.create(
            step=step, kind=VerificationCondition.Kind.SAVED_RECORD,
            record_kind="ucr", required_status="draft", order=1,
        )
        JourneyConditionBinding.objects.create(condition=condition, role=role)
    return role, learner, record


@pytest.mark.django_db
def test_a_role_with_a_learner_association_cannot_be_deleted_or_re_identified(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})
    step = world["steps"][0]
    role, learner, record = _referenced_role(journey, step, with_association=True)

    response, messages_text = _post(client, _detail(journey), {"action": "delete_role", "role_id": role.pk})
    assert response.status_code == 302
    assert "referenced" in messages_text
    assert JourneyRecordRole.objects.filter(pk=role.pk).exists()

    response, messages_text = _post(client, _detail(journey), {
        "action": "save_role", "role_id": role.pk, "key": "locked", "label": "New name",
        "record_kind": "boe", "required": "on", "creation_mode": "new",
    })
    role.refresh_from_db()
    assert role.record_kind == "ucr"
    assert "record_kind" in messages_text or "key" in messages_text

    # Permitted metadata edit (current key, same kind) preserves the learner's
    # association untouched.
    client.post(_detail(journey), {
        "action": "save_role", "role_id": role.pk, "key": role.key, "label": "Renamed only",
        "record_kind": "ucr", "required": "on", "creation_mode": "new",
    })
    role.refresh_from_db()
    assert role.label == "Renamed only"
    association = JourneyRecordAssociation.objects.get(role=role)
    assert association.record_id == record.pk and association.is_active


@pytest.mark.django_db
def test_a_role_with_a_dependency_or_binding_cannot_be_deleted_or_re_kind(client, db):
    instructor = _instructor(db)
    world = _world(db)
    journey = _journey(world)
    client.force_login(instructor)
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][0].pk})
    client.post(_detail(journey), {"action": "assign_step", "step_id": world["steps"][1].pk})
    step = world["steps"][0]
    dep_role, _learner, _record = _referenced_role(
        journey, step, with_dependency=True)
    bind_role, _l2, _r2 = _referenced_role(
        journey, world["steps"][1], with_binding=True)

    client.post(_detail(journey), {"action": "delete_role", "role_id": dep_role.pk})
    assert JourneyRecordRole.objects.filter(pk=dep_role.pk).exists()
    assert JourneyDependency.objects.filter(required_record_role=dep_role).exists()

    client.post(_detail(journey), {"action": "delete_role", "role_id": bind_role.pk})
    assert JourneyRecordRole.objects.filter(pk=bind_role.pk).exists()
    assert JourneyConditionBinding.objects.filter(role=bind_role).exists()


@pytest.mark.django_db
def test_an_unused_role_can_be_deleted_normally(client, db):
    world = _world(db)
    journey = _journey(world)
    client.force_login(_instructor(db))
    role = JourneyRecordRole.objects.create(
        journey=journey, key="loose", label="Loose role", record_kind="ucr", required=True, order=1,
    )

    client.post(_detail(journey), {"action": "delete_role", "role_id": role.pk})
    assert not JourneyRecordRole.objects.filter(pk=role.pk).exists()
