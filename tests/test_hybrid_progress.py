"""Stage 4: server-side verification, durable progress, publication and the
student learning flow.

Everything here is workflow-agnostic: the saved-record condition uses
UcrDeclaration only because it is one of the registered record kinds — the
engine never names a workflow.
"""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyDependency,
    JourneyRecordRole,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
    StepEvent,
    VerificationCondition,
)
from hybrid import journey_services, publishing
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def _user(db, username, group_name="Student"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _published_edition(code, lesson_count=2):
    """A published programme edition: one course, one module, N lessons.

    Lesson 1 carries the verification-heavy step; later lessons have one
    condition-free step each, so sequencing can be exercised.
    """
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    course = HybridCourse.objects.create(programme_version=version, code=f"{code}-c", title=f"{code} course", order=1, is_published=True)
    module = HybridModule.objects.create(course=course, code=f"{code}-m", title=f"{code} module", order=1, is_published=True)
    lessons = []
    for index in range(1, lesson_count + 1):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"{code}-lesson-{index}", title=f"{code} journey {index}",
            order=index, is_published=True, summary=f"Lesson {index} summary.", theory="<p>Theory.</p>",
        )
        PracticalStep.objects.create(
            lesson=lesson, key=f"step-{index}", title=f"Step of lesson {index}", order=1,
            instruction="Do it.", outcome="Done.", screen="single-window-overview",
        )
        lessons.append(lesson)
    step_one = lessons[0].practical_steps.get()
    VerificationCondition.objects.create(
        step=step_one, kind=VerificationCondition.Kind.SCREEN_OPENED, order=1,
    )
    VerificationCondition.objects.create(
        step=step_one, kind=VerificationCondition.Kind.SAVED_RECORD, order=2,
        record_kind="ucr", required_status="draft", expected_fields={"exporter_name": "ACME Trading"},
    )
    return programme, version, course, module, lessons


def _learner_enrolled(db, username, version):
    learner = _user(db, username)
    Enrolment.objects.create(student=learner, programme_version=version)
    return learner


def _attempt(learner, lesson):
    return LessonAttempt.objects.get(enrolment__student=learner, lesson=lesson)


def _post_step(client, attempt, index, action):
    return client.post(reverse(f"hybrid-step-{action}", args=[attempt.pk, index]))


# --- Attempts, verification, progress ------------------------------------------


@pytest.mark.django_db
def test_opening_the_workspace_creates_one_resumable_attempt(client, db):
    _, version, _, _, _ = _published_edition("resume")
    learner = _learner_enrolled(db, "resumer", version)
    lesson = HybridLesson.objects.filter(module__course__programme_version=version).first()
    client.force_login(learner)

    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = LessonAttempt.objects.get(enrolment__student=learner, lesson=lesson)
    assert attempt.current_step == lesson.practical_steps.order_by("order", "id").first()

    attempt.current_step = lesson.practical_steps.order_by("order", "id").last()
    attempt.save(update_fields=("current_step",))
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt.refresh_from_db()
    assert attempt.current_step == lesson.practical_steps.order_by("order", "id").last()


@pytest.mark.django_db
def test_a_check_fails_until_the_screen_was_opened(client, db):
    learner = _learner_enrolled(db, "opener", _published_edition("opener")[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="opener").first()
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = _attempt(learner, lesson)

    refused = _post_step(client, attempt, 0, "check")
    assert refused.json()["passed"] is False
    failed_labels = " | ".join(result["message"] for result in refused.json()["results"])
    assert "Open the step's simulator screen" in failed_labels

    _post_step(client, attempt, 0, "open")
    passed = _post_step(client, attempt, 0, "check")
    by_label = {result["label"]: result["passed"] for result in passed.json()["results"]}
    assert by_label["Open the step's simulator screen"] is True


@pytest.mark.django_db
def test_a_saved_record_condition_checks_owner_status_values_and_freshness(client, db):
    learner = _learner_enrolled(db, "declarant", _published_edition("records")[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="records").first()
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = _attempt(learner, lesson)
    _post_step(client, attempt, 0, "open")

    # A record with the wrong saved values fails with a dedicated message.
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="Someone else", temp_no="TEMPTEST1")
    wrong_values = _post_step(client, attempt, 0, "check").json()
    assert wrong_values["passed"] is False
    assert any("saved values do not match" in r["message"] for r in wrong_values["results"])

    # The right values pass.
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMPTEST2")
    passed = _post_step(client, attempt, 0, "check").json()
    assert passed["passed"] is True

    # Another learner's matching record never counts.
    other = _learner_enrolled(db, "other-declarant", _published_edition("other")[1])
    UcrDeclaration.objects.create(owner=other, status="draft", exporter_name="ACME Trading", temp_no="TEMPTEST3")
    assert _post_step(client, attempt, 0, "check").json()["passed"] is True


@pytest.mark.django_db
def test_a_stale_record_cannot_satisfy_the_step(client, db):
    learner = _learner_enrolled(db, "stale", _published_edition("stale")[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="stale").first()
    attempt = LessonAttempt.objects.create(enrolment=Enrolment.objects.get(student=learner), lesson=lesson)
    stale_stamp = timezone.now() - timezone.timedelta(hours=1)

    # The record predates the moment the learner opened the step.
    StepEvent.objects.create(attempt=attempt, step=lesson.practical_steps.get(), kind=StepEvent.Kind.OPENED, occurred_at=timezone.now())
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="ACME Trading")
    UcrDeclaration.objects.update(created_at=stale_stamp, updated_at=stale_stamp)

    client.force_login(learner)
    result = _post_step(client, attempt, 0, "check").json()
    assert result["passed"] is False
    assert any("predate this step" in r["message"] for r in result["results"])


@pytest.mark.django_db
def test_verification_is_idempotent_and_attempt_scoped(client, db):
    learner = _learner_enrolled(db, "idempotent", _published_edition("idem")[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="idem").first()
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = _attempt(learner, lesson)
    _post_step(client, attempt, 0, "open")
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMPTEST6")

    first = _post_step(client, attempt, 0, "check")
    second = _post_step(client, attempt, 0, "check")
    assert first.json()["passed"] and second.json()["passed"]
    assert StepEvent.objects.filter(attempt=attempt, kind=StepEvent.Kind.VERIFIED).count() == 1

    stranger = _user(db, "stranger")
    client.force_login(stranger)
    assert _post_step(client, stranger and attempt, 0, "check").status_code == 404


@pytest.mark.django_db
def test_advance_is_refused_while_the_step_is_unverified(client, db):
    learner = _learner_enrolled(db, "gated", _published_edition("gate", lesson_count=1)[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="gate").first()
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = _attempt(learner, lesson)

    refused = _post_step(client, attempt, 0, "advance")
    assert refused.status_code == 403
    attempt.refresh_from_db()
    assert attempt.current_step == lesson.practical_steps.get()

    _post_step(client, attempt, 0, "open")
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMPTEST4")
    _post_step(client, attempt, 0, "check")
    allowed = _post_step(client, attempt, 0, "advance")
    assert allowed.json()["allowed"] is True


@pytest.mark.django_db
def test_theory_acknowledgement_completes_the_lesson(client, db):
    learner = _learner_enrolled(db, "completer", _published_edition("completing", lesson_count=1)[1])
    lesson = HybridLesson.objects.filter(module__course__programme_version__programme__code="completing").first()
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = _attempt(learner, lesson)

    ack = client.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk]))
    assert ack.json()["lesson_complete"] is False  # the step is not verified yet

    _post_step(client, attempt, 0, "open")
    UcrDeclaration.objects.create(owner=learner, status="draft", exporter_name="ACME Trading", temp_no="TEMPTEST5")
    final = _post_step(client, attempt, 0, "check")
    assert final.json()["lesson_complete"] is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None


# --- Sequencing and the roadmap -------------------------------------------------


@pytest.mark.django_db
def test_a_lesson_is_locked_until_its_predecessor_completes(client, db):
    learner = _learner_enrolled(db, "sequential", _published_edition("sequence", lesson_count=2)[1])
    lesson1, lesson2 = list(HybridLesson.objects.filter(module__course__programme_version__programme__code="sequence").order_by("order"))
    client.force_login(learner)

    locked = client.get(reverse("hybrid-workspace", args=[lesson2.pk]))
    assert locked.status_code == 302  # PermissionDenied → portal redirect
    followed = client.get(locked.url)
    assert "Finish the previous lesson" in " ".join(str(m) for m in followed.context["messages"])

    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert reverse("hybrid-workspace", args=[lesson1.pk]) in html
    assert "locked" in html and reverse("hybrid-workspace", args=[lesson2.pk]) not in html

    # Completing lesson 1 unlocks lesson 2 — completion never resets.
    client.get(reverse("hybrid-workspace", args=[lesson1.pk]))
    attempt = _attempt(learner, lesson1)
    attempt.theory_acknowledged_at = timezone.now()
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=("theory_acknowledged_at", "completed_at"))

    assert client.get(reverse("hybrid-workspace", args=[lesson2.pk])).status_code == 200
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert reverse("hybrid-workspace", args=[lesson2.pk]) in html


@pytest.mark.django_db
def test_the_roadmap_reports_module_and_edition_progress(client, db):
    learner = _learner_enrolled(db, "progress", _published_edition("progress", lesson_count=2)[1])
    lesson1 = HybridLesson.objects.filter(module__course__programme_version__programme__code="progress").order_by("order").first()
    LessonAttempt.objects.create(
        enrolment=Enrolment.objects.get(student=learner), lesson=lesson1,
        theory_acknowledged_at=timezone.now(), completed_at=timezone.now(),
    )
    client.force_login(learner)
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert "1 of 2 lessons complete" in html
    assert "Module complete" not in html

    HybridLesson.objects.exclude(pk=lesson1.pk).update()
    lesson2 = HybridLesson.objects.filter(module__course__programme_version__programme__code="progress").exclude(pk=lesson1.pk).first()
    LessonAttempt.objects.create(
        enrolment=Enrolment.objects.get(student=learner), lesson=lesson2,
        theory_acknowledged_at=timezone.now(), completed_at=timezone.now(),
    )
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert "2 of 2 lessons complete" in html
    assert "Module complete" in html


@pytest.mark.django_db
def test_the_sidebar_points_students_at_the_hybrid_roadmap(client, db):
    learner = _learner_enrolled(db, "nav-learner", _published_edition("nav")[1])
    client.force_login(learner)
    html = client.get(reverse("dashboard")).content.decode()
    assert reverse("hybrid-roadmap") in html
    assert "Practical Scenarios" in html


# --- Publication, cloning and version preservation -------------------------------


@pytest.mark.django_db
def test_publishing_flips_ready_courses_and_leaves_unfinished_ones(db):
    _, version, *_rest = _published_edition("publishing", lesson_count=1)
    version.status = ProgrammeVersion.Status.DRAFT
    version.save(update_fields=("status",))
    draft_course = HybridCourse.objects.create(programme_version=version, code="empty-course", title="Empty", order=2)

    published, skipped, warnings = publishing.publish_edition(version)
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    assert version.published_at is not None
    assert [course.pk for course in published] != [] and skipped == [draft_course]
    draft_course.refresh_from_db()
    assert draft_course.is_published is False


@pytest.mark.django_db
def test_cloning_a_published_edition_copies_everything_including_conditions(db):
    _, version, course, module, lessons = _published_edition("cloning", lesson_count=1)
    draft = publishing.clone_to_draft(version)
    assert draft.status == ProgrammeVersion.Status.DRAFT
    assert draft.version == version.version + 1
    course_copy = HybridCourse.objects.get(programme_version=draft, code=course.code)
    assert course_copy.pk != course.pk
    lesson_copy = HybridLesson.objects.get(module__course=course_copy)
    step_copy = PracticalStep.objects.get(lesson=lesson_copy)
    assert step_copy.conditions.count() == 2
    assert VerificationCondition.objects.filter(step=step_copy, record_kind="ucr").exists()


@pytest.mark.django_db
def test_a_published_editions_journeys_come_along_with_the_clone(db):
    """The clone test above covers lesson content; a published edition's
    journeys must ride along too, or the new draft has no practical side."""
    programme = Programme.objects.create(
        name="Journey clone", code="journeyclone", learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    course = HybridCourse.objects.create(programme_version=version, code="jc-c", title="JC course", order=1)
    module = HybridModule.objects.create(course=course, code="jc-m", title="JC module", order=1)
    steps = []
    for index in (1, 2):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"jc-lesson-{index}", title=f"JC lesson {index}", order=index,
            summary="Lesson summary.", theory="<p>Theory.</p>",
        )
        steps.append(PracticalStep.objects.create(
            lesson=lesson, key=f"jc-step-{index}", title=f"JC step {index}", order=1,
            instruction="Do it.", outcome="Done.", screen="single-window-overview",
        ))
    journey = journey_services.create_journey(version, course, title="JC journey")
    assignments = [journey_services.assign_step(journey, step) for step in steps]
    journey_services.create_record_role(
        journey, "declaration", "Export declaration", "ucr",
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    journey_services.add_dependency(
        journey, assignments[0], assignments[1], JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    published, skipped, warnings = publishing.publish_edition(version)
    assert (skipped, warnings) == ([], [])

    draft = publishing.clone_to_draft(version)
    copied = PracticalJourney.objects.get(programme_version=draft, code=journey.code)
    assert [row.step.key for row in copied.step_assignments.order_by("journey_order")] == ["jc-step-1", "jc-step-2"]
    assert copied.record_roles.get().key == "declaration"
    assert copied.dependencies.get().predecessor_step.journey_id == copied.pk
    assert copied.course.hybrid_modules.get().title == module.title


@pytest.mark.django_db
def test_learners_keep_their_pinned_edition_when_a_new_draft_is_built(client, db):
    learner = _learner_enrolled(db, "pinned", _published_edition("pinning", lesson_count=1)[1])
    version = ProgrammeVersion.objects.get(programme__code="pinning")
    old_title = HybridLesson.objects.filter(module__course__programme_version=version).first().title

    draft = publishing.clone_to_draft(version)
    draft_lesson = HybridLesson.objects.filter(module__course__programme_version=draft).first()
    draft_lesson.title = "Rewritten in the draft"
    draft_lesson.save(update_fields=("title",))

    client.force_login(learner)
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert old_title in html
    assert "Rewritten in the draft" not in html


@pytest.mark.django_db
def test_the_builder_button_clones_a_published_edition_into_a_new_draft(client, db):
    instructor = _user(db, "publisher", "Instructor")
    _, version, *_rest = _published_edition("cloner", lesson_count=1)
    client.force_login(instructor)
    response = client.post(reverse("hybrid-builder"), {"action": "new_draft", "version_id": version.pk})
    assert response.status_code == 302
    assert ProgrammeVersion.objects.filter(programme=version.programme, status=ProgrammeVersion.Status.DRAFT).exists()


# --- Preview and condition integrity ---------------------------------------------


@pytest.mark.django_db
def test_the_instructor_preview_writes_no_attempt(client, db):
    instructor = _user(db, "previewer", "Instructor")
    _, version, *_rest = _published_edition("previewing", lesson_count=1)
    lesson = HybridLesson.objects.filter(module__course__programme_version=version).first()
    client.force_login(instructor)
    assert client.get(reverse("hybrid-lesson-preview", args=[lesson.pk])).status_code == 200
    assert LessonAttempt.objects.count() == 0


@pytest.mark.django_db
def test_condition_validation_refuses_unapproved_targets(db):
    _, version, *_rest = _published_edition("condcheck", lesson_count=1)
    step = PracticalStep.objects.filter(lesson__module__course__programme_version=version).first()
    with pytest.raises(Exception):
        VerificationCondition(step=step, kind="saved_record", record_kind="made-up", required_status="draft").full_clean()
    with pytest.raises(Exception):
        VerificationCondition(
            step=step, kind="saved_record", record_kind="ucr", required_status="draft",
            expected_fields={"documents": {"nested": True}},
        ).full_clean()
    ok = VerificationCondition(step=step, kind="saved_record", record_kind="ucr", required_status="draft", expected_fields={"exporter_name": "x"})
    ok.full_clean()


# --- Stage 4 close-out: condition authoring, publish action, programme banner ---


@pytest.mark.django_db
def test_conditions_can_be_authored_in_the_editor(client, db):
    instructor = _user(db, "author", "Instructor")
    _, version, *_rest = _published_edition("authoring", lesson_count=1)
    version.status = ProgrammeVersion.Status.DRAFT
    version.save(update_fields=("status",))
    lesson = HybridLesson.objects.filter(module__course__programme_version=version).first()
    # A pristine step without the fixture's pre-seeded conditions.
    step = PracticalStep.objects.create(
        lesson=lesson, key="author-me", title="Authored step", order=2, screen="single-window-search-ucr",
    )
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[lesson.pk])

    # A condition is born as screen-opened evidence, then rewritten as a saved-record check.
    client.post(editor, {"action": "add_condition", "step_id": step.pk})
    condition = VerificationCondition.objects.get(step=step)
    assert condition.kind == VerificationCondition.Kind.SCREEN_OPENED

    saved = client.post(editor, {
        "action": "save_condition", "condition_id": condition.pk,
        "kind": "saved_record", "record_status": "ucr:draft",
        "expected_fields": '{"exporter_name": "ACME Trading"}',
    })
    assert saved.status_code == 302
    condition.refresh_from_db()
    assert condition.record_kind == "ucr"
    assert condition.required_status == "draft"
    assert condition.expected_fields == {"exporter_name": "ACME Trading"}

    # An unapproved status is refused by the registries and nothing changes.
    client.post(editor, {
        "action": "save_condition", "condition_id": condition.pk,
        "kind": "saved_record", "record_status": "ucr:nonexistent", "expected_fields": "{}",
    })
    condition.refresh_from_db()
    assert condition.required_status == "draft"

    # Ordering and removal.
    other = VerificationCondition.objects.create(step=step, kind=VerificationCondition.Kind.SCREEN_OPENED, order=2)
    client.post(editor, {"action": "move_condition", "condition_id": condition.pk, "direction": "down"})
    condition.refresh_from_db(); other.refresh_from_db()
    assert (condition.order, other.order) == (2, 1)
    client.post(editor, {"action": "delete_condition", "condition_id": condition.pk})
    assert not VerificationCondition.objects.filter(pk=condition.pk).exists()
    other.refresh_from_db()
    assert other.order == 1


@pytest.mark.django_db
def test_the_publish_action_refuses_incomplete_and_publishes_ready(client, db):
    instructor = _user(db, "publish-instructor", "Instructor")
    _, version, course, module, lessons = _published_edition("publish-action", lesson_count=1)
    lesson = lessons[0]
    version.status = ProgrammeVersion.Status.DRAFT
    version.save(update_fields=("status",))
    HybridCourse.objects.filter(pk=course.pk).update(is_published=False)
    HybridModule.objects.filter(pk=module.pk).update(is_published=False)
    HybridLesson.objects.filter(module_id=module.pk).update(is_published=False)
    client.force_login(instructor)

    # A step without a screen blocks publication.
    step = lesson.practical_steps.get()
    step.screen = ""
    step.save(update_fields=("screen",))
    client.post(reverse("hybrid-builder"), {"action": "publish_edition", "version_id": version.pk})
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.DRAFT

    step.screen = "single-window-overview"
    step.save(update_fields=("screen",))
    client.post(reverse("hybrid-builder"), {"action": "publish_edition", "version_id": version.pk})
    version.refresh_from_db()
    assert version.status == ProgrammeVersion.Status.PUBLISHED
    assert version.published_at is not None
    course.refresh_from_db()
    assert course.is_published is True


@pytest.mark.django_db
def test_the_roadmap_announces_programme_completion(client, db):
    learner = _learner_enrolled(db, "graduate", _published_edition("graduating", lesson_count=2)[1])
    for lesson in HybridLesson.objects.filter(module__course__programme_version__programme__code="graduating"):
        LessonAttempt.objects.create(
            enrolment=Enrolment.objects.get(student=learner), lesson=lesson,
            theory_acknowledged_at=timezone.now(), completed_at=timezone.now(),
        )
    client.force_login(learner)
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert "Programme complete" in html


@pytest.mark.django_db
def test_the_review_tab_carries_course_readiness(client, db):
    instructor = _user(db, "reviewer", "Instructor")
    _, version, course, module, lessons = _published_edition("reviewing", lesson_count=1)
    version.status = ProgrammeVersion.Status.DRAFT
    version.save(update_fields=("status",))
    # The lesson is fine, but a sibling course is empty: that blocker surfaces.
    HybridCourse.objects.create(programme_version=version, code="hollow", title="Hollow course", order=2)
    lesson = lessons[0]
    client.force_login(instructor)
    response = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk]))
    assert response.context["course_blockers_list"]
    assert "Add at least one module." in response.context["course_blockers_list"][0]
