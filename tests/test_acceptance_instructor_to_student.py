"""Acceptance: instructor authoring → publication → a learner's real simulator work.

Every row here arrives through the product's own forms — the builder's programme,
course, module, lesson, step, condition and journey posts, the edition publish,
then the learner's own screen-by-screen journey. In particular the record that
satisfies the verification condition is created by posting the same payload the
simulator's Create UCR form sends, so no ORM shortcut stands between the learner's
keystrokes and the evidence that governs progression.
"""
import json

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from accounts.models import SimulatorCredential, User
from hybrid import journey_services
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyVerificationEvidence,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    SimulatorRecordCreation,
    VerificationCondition,
)
from hybrid.publishing import edition_blockers
from onboarding.models import (
    DisclaimerAcceptance,
    DisclaimerVersion,
    Enrolment,
    Programme,
    ProgrammeVersion,
)
from scenarios.models import UcrDeclaration


def _person(db, username, group_name):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.test", password="test-password",
    )
    user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _instructor(db):
    return _person(db, "acceptance-instructor", "Instructor")


def _learner(db, username="acceptance-learner"):
    """A student with a live simulator credential and a signed-in simulator session."""
    learner = _person(db, username, "Student")
    SimulatorCredential.objects.create(user=learner).issue()
    client = Client()
    client.force_login(learner)
    session = client.session
    session["simulator_user_id"] = str(learner.pk)
    session.save()
    return learner, client


def _ucr_payload(**overrides):
    """The Create UCR form's own save payload, with the exporter the lesson names."""
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "DCL001", "code": "SUP001", "name": "Supplier",
            "country": "GH", "address": "1 Supplier Way",
            "contact": "Supplier Contact", "phone": "0200000000",
            "email": "supplier@example.test",
        },
        "exporter": {
            "identity": "", "name": "ACME Trading", "country": "GH",
            "address": "1 Export Road", "phone": "0210000000",
            "contact": "Export Contact", "contact_no": "C-100",
            "designation": "Exports",
        },
        "importer": {
            "identity": "", "name": "ACME Imports", "country": "NL",
            "address": "1 Import Street", "phone": "0900000000",
            "contact": "Import Contact", "contact_no": "C-200",
            "designation": "Imports",
        },
        "consignment": {
            "mode": "30", "goods": "General merchandise",
            "origin": "GH", "destination": "NL", "reference": "REF-1", "email": "",
        },
        "documents": [],
    }
    payload.update(overrides)
    return payload


def _author(client):
    """One instructor's ordinary week: programme, course, module, lesson, journey, publish."""
    programme_version = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Clearance basics", "code": "acceptance-programme"},
    )
    assert programme_version.status_code == 302
    programme = Programme.objects.get(code="acceptance-programme")

    client.post(
        reverse("hybrid-builder"),
        {"programme": programme.pk, "title": "Cargo clearance", "description": ""},
    )
    course = HybridCourse.objects.get(title="Cargo clearance")

    client.post(
        reverse("hybrid-course-edit", args=[course.pk]),
        {"action": "create_module", "title": "First declaration", "description": ""},
    )
    module = HybridModule.objects.get(course=course, title="First declaration")

    client.post(
        reverse("hybrid-module-edit", args=[module.pk]),
        {"action": "create_lesson", "title": "Create a UCR", "summary": "Open the single window and save a draft."},
    )
    lesson = HybridLesson.objects.get(module=module, title="Create a UCR")
    editor = reverse("hybrid-lesson-edit", args=[lesson.pk])

    client.post(editor, {"action": "add_step", "active_tab": "journey"})
    step = PracticalStep.objects.get(lesson=lesson)
    saved = client.post(editor, {
        "title": lesson.title, "summary": lesson.summary, "active_tab": "journey",
        "form-body": "<p>The UCR declares the goods before anything moves.</p>",
        "steps-TOTAL_FORMS": "1", "steps-INITIAL_FORMS": "1",
        "steps-MIN_NUM_FORMS": "0", "steps-MAX_NUM_FORMS": "1000",
        "steps-0-id": str(step.pk),
        "steps-0-title": "Open the declaration form",
        "steps-0-instruction": "Create a UCR whose exporter is ACME Trading, then save the draft.",
        "steps-0-outcome": "A saved draft naming your exporter.",
        "steps-0-hint": "The exporter block is below the regime choice.",
        "steps-0-screen": "single-window-create-ucr",
    })
    assert saved.status_code == 302
    step.refresh_from_db()
    assert (step.instruction, step.outcome, step.screen) == (
        "Create a UCR whose exporter is ACME Trading, then save the draft.",
        "A saved draft naming your exporter.",
        "single-window-create-ucr",
    )

    client.post(editor, {"action": "add_condition", "step_id": step.pk, "kind": "saved_record"})
    condition = VerificationCondition.objects.get(step=step)
    client.post(editor, {
        "action": "save_condition", "condition_id": condition.pk,
        "kind": "saved_record", "record_status": "ucr:draft",
        "value_rows": "1", "check_0": "ucr:exporter_name", "value_0": "ACME Trading",
    })
    condition.refresh_from_db()
    assert condition.expected_fields == {"exporter_name": "ACME Trading"}

    client.post(
        reverse("hybrid-course-journeys", args=[course.pk]),
        {"title": "Clear one consignment", "description": "", "start_mode": "new_record"},
    )
    journey = PracticalJourney.objects.get(course=course)
    detail = reverse("hybrid-journey-detail", args=[journey.pk])
    client.post(detail, {"action": "assign_step", "step_id": step.pk})
    client.post(detail, {
        "action": "add_role", "key": "primary-ucr", "label": "Your UCR",
        "record_kind": "ucr", "required": "on", "creation_mode": "new",
    })
    role = JourneyRecordRole.objects.get(journey=journey, key="primary-ucr")
    client.post(detail, {"action": "bind_condition", "condition_id": condition.pk, "role_id": role.pk})

    version = course.programme_version
    assert edition_blockers(version) == []
    client.post(reverse("hybrid-builder"), {"action": "publish_edition", "version_id": version.pk})
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED

    return {
        "version": version, "lesson": lesson, "step": step,
        "condition": condition, "journey": journey, "role": role,
    }


@pytest.fixture
def world(db):
    instructor_client = Client()
    instructor_client.force_login(_instructor(db))
    return _author(instructor_client)


def _enter(client, learner, world):
    """The learner's way in, in the order the product offers it: the lesson
    workspace, then the journey that owns the step, then the step itself, then
    the theory reading. The journey page is what creates the journey attempt the
    opening is authorized against, so it comes before any step opens."""
    workspace = client.get(reverse("hybrid-workspace", args=[world["lesson"].pk]))
    assert workspace.status_code == 200
    client.get(reverse("hybrid-journey-student", args=[world["journey"].pk]))
    attempt = LessonAttempt.objects.get(enrolment__student=learner, lesson=world["lesson"])
    opened = client.post(reverse("hybrid-step-open", args=[attempt.pk, 0]))
    assert opened.status_code == 200, opened.json()
    client.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk]))
    return workspace, attempt


def _save_ucr(client, **overrides):
    """Post the Create UCR form's own payload to the simulator's save endpoint."""
    response = client.post(
        reverse("ucr-save"), data=json.dumps(_ucr_payload(**overrides)), content_type="application/json",
    )
    assert response.status_code == 200, response.content
    return UcrDeclaration.objects.get(pk=response.json()["id"])


def _attribute(client, world, record):
    """Claim the freshly created record for the journey role, from the journey's
    own page and through its own endpoint."""
    creation = SimulatorRecordCreation.objects.get(record_kind="ucr", record_id=record.pk)
    return client.post(
        reverse("hybrid-journey-role-attribute", args=[world["journey"].pk, world["role"].pk]),
        data=json.dumps({"creation_id": str(creation.pk)}), content_type="application/json",
    )


def _evidence(world):
    """The durable verification rows written for the lesson's one step."""
    return JourneyVerificationEvidence.objects.filter(journey_step__step=world["step"])


@pytest.mark.django_db
def test_the_authored_lesson_verifies_a_record_the_learner_really_saved(world, db):
    learner, client = _learner(db)
    Enrolment.objects.create(student=learner, programme_version=world["version"])

    workspace, attempt = _enter(client, learner, world)
    assert reverse("single-window-create-ucr") in workspace.content.decode()

    # The learner works in the simulator itself: the same JSON the form posts.
    record = _save_ucr(client)
    assert (record.owner, record.status, record.exporter_name) == (learner, "draft", "ACME Trading")

    # …and claims it for the journey role from the journey's own page.
    assert _attribute(client, world, record).json()["attributed"] is True
    assert JourneyRecordAssociation.objects.filter(
        journey_attempt__journey=world["journey"], record_kind="ucr", record_id=record.pk,
    ).exists()

    result = client.post(reverse("hybrid-step-check", args=[attempt.pk, 0])).json()
    assert result["passed"] is True, result
    assert result["lesson_complete"] is True
    assert len(JourneyVerificationEvidence.objects.filter(
        journey_attempt__journey=world["journey"], journey_step__step=world["step"],
    )) == 1

    attempt.refresh_from_db()
    assert attempt.completed_at is not None
    journey_attempt = JourneyAttempt.objects.get(enrolment__student=learner, journey=world["journey"])
    assert [row["satisfied"] for row in journey_services.journey_step_rows(journey_attempt)] == [True]


@pytest.mark.django_db
def test_an_unrelated_record_does_not_pass_and_the_step_stays_locked(world, db):
    learner, client = _learner(db, "wrong-learner")
    Enrolment.objects.create(student=learner, programme_version=world["version"])
    _, attempt = _enter(client, learner, world)

    record = _save_ucr(client, exporter={
        "identity": "", "name": "Someone Else", "country": "GH", "address": "1 Export Road",
        "phone": "0210000000", "contact": "Export Contact", "contact_no": "C-100",
        "designation": "Exports",
    })
    _attribute(client, world, record)

    checked = client.post(reverse("hybrid-step-check", args=[attempt.pk, 0])).json()
    assert checked["passed"] is False
    assert any(entry["passed"] is False for entry in checked["results"])

    advanced = client.post(reverse("hybrid-step-advance", args=[attempt.pk, 0]))
    assert advanced.status_code == 403
    assert advanced.json()["allowed"] is False

    attempt.refresh_from_db()
    assert attempt.completed_at is None
    assert _evidence(world).count() == 0


@pytest.mark.django_db
def test_checking_the_same_step_twice_reuses_one_evidence_row(world, db):
    learner, client = _learner(db, "twice-learner")
    Enrolment.objects.create(student=learner, programme_version=world["version"])
    _, attempt = _enter(client, learner, world)

    _attribute(client, world, _save_ucr(client))

    first = client.post(reverse("hybrid-step-check", args=[attempt.pk, 0])).json()
    second = client.post(reverse("hybrid-step-check", args=[attempt.pk, 0])).json()
    assert first["passed"] is second["passed"] is True
    assert _evidence(world).count() == 1
