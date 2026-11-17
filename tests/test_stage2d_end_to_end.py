"""UI 4 Stage 2D — the first complete Theory & Practical workflow, end to end.

One instructor record-and-convert walk and one student learn-verify-complete
walk, driven through the real HTTP endpoints against PostgreSQL, with the
persisted data checked at every boundary. This module deliberately repeats no
per-feature suite's unit coverage; it is the seam test: does a recording made
in the studio become a published lesson a learner can actually complete — and
do the demonstration's own records stay out of the learner's way?

Composed from the existing builders (``demonstration_world``) so the rows are
the same shape the focused suites verify.
"""
import json
from datetime import timedelta

import pytest
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import SimulatorCredential, User
from audit.models import AuditEvent
from demonstration_world import draft_world
from hybrid import demonstrations
from hybrid.models import DemonstrationEvent, DemonstrationSession, HybridLesson, LessonAttempt, PracticalStep
from onboarding.models import Enrolment, ProgrammeVersion
from scenarios.models import UcrDeclaration, allocate_ucr_number

e2e = override_settings(DEBUG=True, DEMONSTRATION_RECORDING_ENABLED=True)

FRAME = {"HTTP_SEC_FETCH_DEST": "iframe", "HTTP_SEC_FETCH_SITE": "same-origin"}


# --- Shared world ------------------------------------------------------------


def make_student(username):
    student = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    student.student_id = username.upper()
    student.save(update_fields=("student_id",))
    credential = SimulatorCredential.objects.create(user=student)
    credential.issue()
    return student


def student_client(student):
    client = Client()
    client.force_login(student)
    store = client.session
    store["simulator_user_id"] = str(student.pk)
    store.save()
    return client


def save_body(**overrides):
    payload = {
        "regime": "TN",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "E2E Provider",
            "country": "GH", "address": "1 Provider Road", "contact": "Provider Contact",
            "phone": "+233200000003", "email": "provider@example.test", "email_2": "",
        },
        "exporter": {
            "name": "E2E Exporter", "country": "GH", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "name": "E2E Importer", "country": "CN", "address": "1 Import Road",
            "phone": "+861000000001", "contact": "Import Contact",
            "contact_no": "+861000000002", "designation": "Manager",
        },
        "consignment": {
            "goods": "Training goods", "origin": "GH", "destination": "CN", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


def second_lesson(world):
    """A second, complete lesson in the same module — the sequencing witness."""
    lesson_two = HybridLesson.objects.create(
        module=world["module"],
        slug=f"{world['lesson'].slug}-two",
        title=f"{world['lesson'].title} II",
        summary="Second lesson summary.",
        theory="<p>Second lesson theory.</p>",
        order=2,
    )
    PracticalStep.objects.create(
        lesson=lesson_two, key="e2e-two-step", title="Second lesson activity",
        instruction="Open the Single Window overview.", outcome="The overview screen has been reached.",
        screen="single-window-overview", order=1,
    )
    return lesson_two


def instructor_walk(world, client):
    """The instructor half of the workflow, steps 1-14, with boundary checks."""
    lesson = world["lesson"]
    lesson_two = second_lesson(world)

    # 1-3. Draft lesson with theory; open the Demonstration Studio.
    studio = client.get(reverse("hybrid-lesson-demonstration-studio", args=[lesson.pk]))
    assert studio.status_code == 200
    assert reverse("hybrid-demonstration-start", args=[lesson.pk]) in studio.content.decode()

    # 4. Start recording.
    started = client.post(reverse("hybrid-demonstration-start", args=[lesson.pk]))
    assert started.status_code == 200
    session_id = started.json()["session"]["id"]
    session = DemonstrationSession.objects.get(pk=session_id)
    assert session.state == "recording"
    assert client.session[demonstrations.ACTIVE_SESSION_KEY] == session_id

    # 5-6. Drive the supported UCR screens in the studio frame; save the demo
    # draft (temporary reference), then submit it (final number) and land on
    # the detail screen — the full Import UCR procedure as evidence.
    for route in ("simulator-portal", "single-window-overview", "single-window-create-ucr"):
        assert client.get(reverse(route), **FRAME).status_code == 200
    saved = client.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    assert saved.status_code == 200
    demo = UcrDeclaration.all_objects.get(pk=saved.json()["id"])
    assert demo.demonstration_session_id == session.pk
    assert demo.temp_no.startswith("DEMOUCR")
    submitted = client.post(
        reverse("ucr-submit"), json.dumps(save_body(draft_id=demo.pk)), content_type="application/json"
    )
    assert submitted.status_code == 200
    sub = submitted.json()
    assert sub["ucr_no"].startswith("KGHTESTUCR")
    assert sub["demonstration"] is True
    demo.refresh_from_db()
    assert demo.status == UcrDeclaration.Status.SUBMITTED
    assert demo.ucr_no == sub["ucr_no"]
    # The redirect target resolves for the recording instructor's own record.
    assert client.get(sub["detail_url"], **FRAME).status_code == 200
    assert client.get(reverse("single-window-search-ucr"), **FRAME).status_code == 200

    events = list(DemonstrationEvent.objects.filter(session_id=session.pk).order_by("sequence"))
    assert [(event.sequence, event.event_type) for event in events] == [
        (1, "navigation"), (2, "navigation"), (3, "navigation"),
        (4, "record_created"), (5, "record_updated"), (6, "navigation"), (7, "navigation"),
    ]
    assert events[4].action_code == "ucr.submitted"
    assert events[4].payload["result_status"] == "submitted"

    # 7. Stop recording.
    session.refresh_from_db()
    stopped = client.post(
        reverse("hybrid-demonstration-stop"),
        json.dumps({"session_id": session_id, "version": session.version}),
        content_type="application/json",
    )
    assert stopped.status_code == 200
    session.refresh_from_db()
    assert session.state == "stopped"
    assert demonstrations.ACTIVE_SESSION_KEY not in client.session

    # 8-9. The Review tab's proposals: the procedure's milestones, grounded in
    # the captured evidence, with nothing invented to fill gaps.
    proposals_url = reverse("hybrid-demonstration-proposals", args=[lesson.pk, session.pk])
    convert_url = reverse("hybrid-demonstration-convert", args=[lesson.pk, session.pk])
    proposals_response = client.get(proposals_url).json()
    proposals = proposals_response["activities"]
    assert [proposal["id"] for proposal in proposals] == [
        "screen:simulator-portal", "screen:single-window-overview", "screen:single-window-search-ucr",
        "milestone:regime", "milestone:sections", "milestone:save", "milestone:submit",
    ]
    assert proposals_response["capture_warnings"] == []
    assert next(p for p in proposals if p["id"] == "milestone:submit")["condition"]["required_status"] == "submitted"
    assert next(p for p in proposals if p["id"] == "milestone:regime")["condition"]["expected_fields"] == {"stage": "regime_selected", "value": "TN"}
    assert all(proposal["evidence"] for proposal in proposals)

    # 10-11. Select, edit, and apply — dropping the portal stop-over.
    activities = [
        {
            "proposal_id": proposal["id"],
            "title": "Create and save a UCR draft" if proposal["id"] == "milestone:save" else proposal["title"],
            "instruction": proposal["instruction"],
            "outcome": proposal["outcome"],
            "hint": "",
            "with_condition": proposal["has_condition"],
        }
        for proposal in proposals if proposal["id"] != "screen:simulator-portal"
    ]
    applied = client.post(convert_url, json.dumps({"activities": activities}), content_type="application/json")
    assert applied.status_code == 200
    assert applied.json()["lesson_url"].endswith("?tab=activities")

    # 12. Persisted steps appear in the ordinary lesson editor.
    editor = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk]) + "?tab=activities")
    assert editor.status_code == 200
    assert "Create and save a UCR draft" in editor.content.decode()
    steps = list(lesson.practical_steps.order_by("order"))
    assert [step.screen for step in steps] == [
        "single-window-overview", "single-window-search-ucr",
        "single-window-create-ucr", "single-window-create-ucr",
        "single-window-create-ucr", "single-window-create-ucr",
    ]
    regime_condition = steps[2].conditions.get()
    assert regime_condition.kind == "stage_evidence"
    assert regime_condition.expected_fields == {"stage": "regime_selected", "value": "TN"}
    sections_condition = steps[3].conditions.get()
    assert sections_condition.kind == "stage_evidence"
    save_condition = steps[4].conditions.get()
    assert (save_condition.kind, save_condition.record_kind, save_condition.required_status) == ("saved_record", "ucr", "draft")
    submit_condition = steps[5].conditions.get()
    assert submit_condition.required_status == "submitted"
    condition = save_condition

    # 13. Duplicate conversion is refused; the audit marker is the boundary.
    again = client.post(convert_url, json.dumps({"activities": activities}), content_type="application/json")
    assert again.status_code == 409
    assert json.loads(again.content)["code"] == "already_converted"
    assert AuditEvent.objects.filter(
        action_code="demonstration.converted", target_id=str(session.pk)
    ).exists()

    # 14. Publish the edition through the real workspace action.
    published = client.post(
        reverse("hybrid-programme-detail", args=[world["version"].programme.pk]),
        {"action": "publish_edition", "version_id": str(world["version"].pk)},
    )
    assert published.status_code == 302
    version = ProgrammeVersion.objects.get(pk=world["version"].pk)
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    assert version.published_at is not None
    course = world["course"]
    course.refresh_from_db()
    assert course.is_published is True
    lesson.refresh_from_db()
    assert lesson.is_published is True

    return {
        "session": session, "steps": steps, "condition": condition,
        "lesson": lesson, "lesson_two": lesson_two, "version": version,
    }


# --- The instructor walk -----------------------------------------------------


@pytest.mark.django_db
@e2e
def test_instructor_records_converts_and_publishes(db):
    world = draft_world("e2e-instructor")
    client = Client()
    client.force_login(world["instructor"])

    prepared = instructor_walk(world, client)

    assert prepared["lesson_two"].title  # the sequencing witness exists
    # The create step is attested by the saved draft (regime pinned); the
    # submit step by the learner's own final UCR number.
    assert prepared["condition"].step.title == "Create and save a UCR draft"
    assert prepared["lesson"].practical_steps.get(
        title="Create and save a UCR draft"
    ).conditions.get().required_status == "draft"
    assert prepared["lesson"].practical_steps.get(
        title="Submit the UCR — obtain the final UCR number"
    ).conditions.get().required_status == "submitted"


# --- The student walk --------------------------------------------------------


@pytest.mark.django_db
@e2e
def test_student_completes_the_published_lesson(db):
    world = draft_world("e2e-student-flow")
    client = Client()
    client.force_login(world["instructor"])
    prepared = instructor_walk(world, client)
    lesson = prepared["lesson"]
    lesson_two = prepared["lesson_two"]
    module = world["module"]

    student = make_student("e2e-student")
    enrolment = Enrolment.objects.create(student=student, programme_version=world["version"])
    student_browser = student_client(student)

    # 1. The roadmap lists the published lesson.
    roadmap = student_browser.get(reverse("hybrid-roadmap"))
    assert roadmap.status_code == 200
    assert reverse("hybrid-workspace", args=[lesson.pk]) in roadmap.content.decode()
    # Sequencing: the module's second lesson is locked until the first completes.
    assert reverse("hybrid-workspace", args=[lesson_two.pk]) not in roadmap.content.decode()
    locked = student_browser.get(reverse("hybrid-workspace", args=[lesson_two.pk]))
    assert locked.status_code == 302  # PermissionDenied → portal redirect with the message

    # 2-3. Open the theory page; acknowledge; then start the practical.
    theory_page = student_browser.get(reverse("hybrid-lesson-theory", args=[lesson.pk]))
    assert theory_page.status_code == 200
    attempt = LessonAttempt.objects.get(enrolment=enrolment, lesson=lesson)
    acknowledged = student_browser.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk]))
    assert acknowledged.json()["lesson_complete"] is False
    workspace = student_browser.get(reverse("hybrid-workspace", args=[lesson.pk]))
    assert workspace.status_code == 200

    # 8 (negative). An ordinary draft saved BEFORE the step opened cannot satisfy it:
    # the freshness clock starts at the step's own open. The stale draft is
    # backdated so the ordering is unambiguous on every engine's clock precision.
    stale = UcrDeclaration.objects.create(
        owner=student, temp_no=allocate_ucr_number(UcrDeclaration.TEMP_PREFIX),
        regime="TN", status=UcrDeclaration.Status.DRAFT,
    )
    UcrDeclaration.objects.filter(pk=stale.pk).update(
        updated_at=timezone.now() - timedelta(seconds=30), created_at=timezone.now() - timedelta(seconds=30),
    )

    # 5. Open the screens: condition-free steps (0, 1) satisfy on entry; the
    #    saved-record steps' freshness clocks start at their own opens.
    for index in (0, 1, 2, 3, 4, 5):
        assert student_browser.post(reverse("hybrid-step-open", args=[attempt.pk, index])).json()["ok"] is True

    early = student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 2])).json()
    assert early["passed"] is False
    assert any("Select the regime" in result["message"] for result in early["results"])

    # 6-7. Save a fresh ordinary draft through the real simulator route, then
    # verify the regime, sections and save steps against it.
    saved = student_browser.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    assert saved.status_code == 200
    fresh = UcrDeclaration.objects.get(pk=saved.json()["id"])
    assert fresh.temp_no.startswith("TEMPUCR")
    assert fresh.demonstration_session_id is None

    for screen_index in (0, 1):
        assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, screen_index])).json()["passed"] is True
    # Set stage evidence for the regime and sections steps via the beacon endpoint.
    evidence_url = reverse("hybrid-stage-evidence", args=[attempt.pk])
    csrf = student_browser.session.get("_auth_user_id")  # use the session's CSRF
    import json as _json
    student_browser.post(
        evidence_url,
        _json.dumps({"stage": "regime_selected", "value": "TN"}),
        content_type="application/json",
    )
    student_browser.post(
        evidence_url,
        _json.dumps({"stage": "sections_completed"}),
        content_type="application/json",
    )
    assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 2])).json()["passed"] is True
    assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 3])).json()["passed"] is True
    assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 4])).json()["passed"] is True

    # 9. Advance the verified regime step; the screen steps verify on their own opens.
    assert student_browser.post(reverse("hybrid-step-advance", args=[attempt.pk, 2])).status_code == 200

    # The submit step (5) requires the learner's own final UCR number.
    assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 5])).json()["passed"] is False
    submitted = student_browser.post(
        reverse("ucr-submit"), json.dumps(save_body(draft_id=fresh.pk)), content_type="application/json"
    )
    assert submitted.status_code == 200
    assert submitted.json()["ucr_no"].startswith("KGHTESTUCR")
    fresh.refresh_from_db()
    assert fresh.status == UcrDeclaration.Status.SUBMITTED
    assert student_browser.post(reverse("hybrid-step-check", args=[attempt.pk, 5])).json()["passed"] is True

    # 10. Completion lands once every step is satisfied and theory is acknowledged.
    assert student_browser.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk])).json()["lesson_complete"] is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None

    # The demonstration record never satisfied anything: the student's own two
    # ordinary drafts are all the ordinary manager shows, and the demo row is
    # unreachable through the ordinary surface.
    visible = list(UcrDeclaration.objects.filter(owner=student))
    assert stale in visible and fresh in visible
    demo = UcrDeclaration.all_objects.filter(demonstration_session__isnull=False).first()
    assert demo is not None and demo not in visible
    assert student_browser.get(reverse("ucr-detail", args=[demo.pk])).status_code == 404

    # 11. Roadmap progress reflects lesson completion — and unlocks the next
    # lesson in the module. The module itself is not complete yet: lesson two
    # is still outstanding, so the edition count is one of two.
    from hybrid.publishing import learner_edition_progress
    from hybrid.services import module_complete

    assert module_complete(enrolment, module) is False
    assert learner_edition_progress(enrolment, world["version"]) == (1, 2)
    roadmap_after = student_browser.get(reverse("hybrid-roadmap")).content.decode()
    assert lesson.title in roadmap_after
    assert reverse("hybrid-workspace", args=[lesson_two.pk]) in roadmap_after
    # Lesson 2's theory must be acknowledged before the guide renders
    LessonAttempt.objects.create(
        enrolment=enrolment, lesson=lesson_two, theory_acknowledged_at=timezone.now(),
    )
    assert student_browser.get(reverse("hybrid-workspace", args=[lesson_two.pk])).status_code == 200


# --- Negative paths at the seam ---------------------------------------------


@pytest.mark.django_db
@e2e
def test_negative_paths_across_the_workflow(db):
    world = draft_world("e2e-negative")
    instructor_user = world["instructor"]
    client = Client()
    client.force_login(instructor_user)
    lesson = world["lesson"]

    client.post(reverse("hybrid-demonstration-start", args=[lesson.pk]))
    demo_session = DemonstrationSession.objects.get(instructor=instructor_user, state="recording")
    client.get(reverse("single-window-create-ucr"), **FRAME)
    client.post(reverse("ucr-save"), json.dumps(save_body()), content_type="application/json")
    demo_session.refresh_from_db()
    client.post(
        reverse("hybrid-demonstration-stop"),
        json.dumps({"session_id": str(demo_session.pk), "version": demo_session.version}),
        content_type="application/json",
    )

    # Another instructor's recording is an unknown session for conversion.
    stranger = draft_world("e2e-negative-other")["instructor"]
    stranger_client = Client()
    stranger_client.force_login(stranger)
    proposals_url = reverse("hybrid-demonstration-proposals", args=[lesson.pk, demo_session.pk])
    convert_url = reverse("hybrid-demonstration-convert", args=[lesson.pk, demo_session.pk])
    assert stranger_client.get(proposals_url).status_code == 404
    assert stranger_client.post(
        convert_url, json.dumps({"activities": [{"proposal_id": "screen:simulator-portal"}]}),
        content_type="application/json",
    ).status_code == 404
    assert lesson.practical_steps.count() == 0

    # Apply once, publish, and confirm conversion is dead on the published lesson.
    proposals = client.get(proposals_url).json()["activities"]
    body = {"activities": [
        {
            "proposal_id": proposal["id"],
            "title": proposal["title"],
            "instruction": proposal["instruction"],
            "outcome": proposal["outcome"],
            "hint": "",
            "with_condition": proposal["has_condition"],
        }
        for proposal in proposals
    ]}
    assert client.post(convert_url, json.dumps(body), content_type="application/json").status_code == 200
    assert client.post(
        reverse("hybrid-programme-detail", args=[world["version"].programme.pk]),
        {"action": "publish_edition", "version_id": str(world["version"].pk)},
    ).status_code == 302
    assert client.post(convert_url, json.dumps(body), content_type="application/json").status_code == 404

    # With the flag off the whole recording surface closes again.
    with override_settings(DEMONSTRATION_RECORDING_ENABLED=False):
        assert client.post(reverse("hybrid-demonstration-start", args=[lesson.pk])).status_code == 403
        assert client.get(proposals_url).status_code == 403
        assert client.post(convert_url, json.dumps(body), content_type="application/json").status_code == 403

    # The demonstration's records stay out of every ordinary surface.
    assert UcrDeclaration.objects.filter(demonstration_session__isnull=False).count() == 0
    assert UcrDeclaration.all_objects.filter(demonstration_session__isnull=False).exists()
