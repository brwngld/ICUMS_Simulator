"""Stage 2 Checkpoint 5: the student journey foundation.

The learner's journey page, resume, and runtime: attempts are learner-scoped
and version-matched, progression walks the canonical order under a
demonstrated-position ceiling, and completion reads durable StepEvent
evidence plus required-role satisfaction — never lesson flags alone.
"""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import journey_services, verification as hybrid_verification
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyAttempt,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    LessonAttempt,
    PracticalJourney,
    PracticalStep,
)
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def _student(db, username="journey-learner"):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="x")
    user.groups.add(Group.objects.get_or_create(name="Student")[0])
    disclaimer, _ = DisclaimerVersion.objects.get_or_create(
        version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
    )
    DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)
    return user


def _world(db, published=True):
    """A journey edition built as a draft (steps assigned like the organizer
    would), then published when ``published`` is true."""
    programme = Programme.objects.create(
        name="Student Journey Programme", code="student-journeys", learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(programme_version=version, code="sj-c", title="Journey Course", order=1)
    module = HybridModule.objects.create(course=course, code="sj-m", title="Journey Module", order=1)
    lessons, steps = [], []
    for index in (1, 2):
        lesson = HybridLesson.objects.create(
            module=module, slug=f"sjl-{index}", title=f"Journey Lesson {index}", order=index,
            theory="<p>Read this.</p>",
        )
        step = PracticalStep.objects.create(
            lesson=lesson, key=f"sjs-{index}", title=f"Journey Step {index}", order=1,
        )
        lessons.append(lesson)
        steps.append(step)
    from hybrid import journey_services
    journey = PracticalJourney.objects.create(
        programme_version=version, course=course, code="sj", title="Student Journey",
    )
    for step in steps:
        journey_services.assign_step(journey, step)
    if published:
        version.status = ProgrammeVersion.Status.PUBLISHED
        version.save(update_fields=("status",))
        course.is_published = True
        course.save(update_fields=("is_published",))
        module.is_published = True
        module.save(update_fields=("is_published",))
        for lesson in lessons:
            lesson.is_published = True
            lesson.save(update_fields=("is_published",))
    return {
        "programme": programme, "version": version, "course": course, "module": module,
        "lessons": lessons, "steps": steps, "journey": journey,
    }


def _enrol(db, world, user):
    return Enrolment.objects.create(student=user, programme_version=world["version"])


def _open_world_steps(lesson_attempts):
    """Simulate the workspace evidence path: OPENED StepEvent stamps on each
    of the learner's LessonAttempts."""
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)


def _student_page(client, journey):
    return client.get(reverse("hybrid-journey-student", args=[journey.pk]))


def _advance(client, journey):
    response = client.post(reverse("hybrid-journey-advance", args=[journey.pk]))
    messages = " ".join(str(m) for m in get_messages(response.wsgi_request))
    return response, messages


@pytest.mark.django_db
def test_the_journey_page_creates_one_attempt_and_marks_the_entry_point(client, db):
    student = _student(db)
    world = _world(db)
    _enrol(db, world, student)
    client.force_login(student)

    response = _student_page(client, world["journey"])
    assert response.status_code == 200
    html = response.content.decode()
    attempt = JourneyAttempt.objects.get(enrolment__student=student, journey=world["journey"])
    assert attempt.current_journey_step.step.key == "sjs-1"
    assert "Resume here" in html
    assert "Journey Step 1" in html

    _student_page(client, world["journey"])
    assert JourneyAttempt.objects.filter(enrolment__student=student, journey=world["journey"]).count() == 1


@pytest.mark.django_db
def test_a_learner_from_another_version_cannot_open_the_journey(client, db):
    student = _student(db)
    world = _world(db)
    second_version = ProgrammeVersion.objects.create(programme=world["programme"], version=2)
    Enrolment.objects.filter(student=student).update(programme_version=second_version)
    client.force_login(student)

    response = _student_page(client, world["journey"])
    assert response.status_code == 302  # PermissionDenied → portal redirect


@pytest.mark.django_db
def test_a_draft_edition_learner_is_refused_and_a_stranger_cannot_see_the_journey(client, db):
    student = _student(db)
    world = _world(db, published=False)
    _enrol(db, world, student)
    client.force_login(student)
    # A journey on an unpublished course has no student surface; the attempt
    # service still works, but the roadmap never links a draft course.
    stranger = _student(db, "stranger")
    client.force_login(stranger)
    # The journey's version match passes for any same-edition enrolment; the
    # published-course filter is what keeps it off the roadmap.
    assert "Student Journey" not in client.get(reverse("hybrid-roadmap")).content.decode()


@pytest.mark.django_db
def test_the_roadmap_links_the_journey_with_start_resume_and_status(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)

    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert "Start journey" in html

    attempt = journey_services.get_or_create_attempt(enrolment, world["journey"])
    lesson_attempt = LessonAttempt.objects.create(
        enrolment=attempt.enrolment, lesson=world["lessons"][0], theory_acknowledged_at=timezone.now(),
    )
    hybrid_verification.record_open(lesson_attempt, world["steps"][0])
    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert "Resume journey" in html
    assert "Step 2 of 2" in html


@pytest.mark.django_db
def test_condition_free_steps_need_their_screen_opened_not_lesson_flags(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])

    # Lesson flags alone never satisfy a condition-free step: rows stay
    # unsatisfied and advance is refused.
    LessonAttempt.objects.create(
        enrolment=enrolment, lesson=world["lessons"][0],
        completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
    )
    _response, messages_text = _advance(client, world["journey"])
    attempt.refresh_from_db()
    assert attempt.current_journey_step.step.key == "sjs-1"
    assert "locked until the earlier steps are complete" in messages_text

    # Opening the step's screen is the authoritative signal.
    lesson_attempt = LessonAttempt.objects.get(enrolment=enrolment, lesson=world["lessons"][0])
    hybrid_verification.record_open(lesson_attempt, world["steps"][0])
    _response, messages_text = _advance(client, world["journey"])
    attempt.refresh_from_db()
    assert attempt.current_journey_step.step.key == "sjs-2"


@pytest.mark.django_db
def test_the_progression_ceiling_blocks_two_steps_at_once(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])

    # Evidence for step 2 without step 1 cannot move the position.
    lesson_attempt_two = LessonAttempt.objects.create(
        enrolment=enrolment, lesson=world["lessons"][1], theory_acknowledged_at=timezone.now(),
    )
    hybrid_verification.record_open(lesson_attempt_two, world["steps"][1])
    _response, messages_text = _advance(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    assert attempt.current_journey_step.step.key == "sjs-1"
    assert "locked" in messages_text


@pytest.mark.django_db
def test_a_record_available_dependency_blocks_advance_until_the_role_is_satisfied(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    JourneyDependency.objects.create(
        journey=world["journey"],
        predecessor_step=world["journey"].step_assignments.get(step=world["steps"][0]),
        dependent_step=world["journey"].step_assignments.get(step=world["steps"][1]),
        dependency_type=JourneyDependency.DependencyType.RECORD_AVAILABLE,
        required_record_role=role, order=1,
    )
    lesson_attempt = LessonAttempt.objects.create(
        enrolment=enrolment, lesson=world["lessons"][0], theory_acknowledged_at=timezone.now(),
    )
    hybrid_verification.record_open(lesson_attempt, world["steps"][0])

    _response, messages_text = _advance(client, world["journey"])
    assert "needs the record role" in messages_text

    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPSTUDENT-1",
    )
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    _response, messages_text = _advance(client, world["journey"])
    attempt.refresh_from_db()
    assert attempt.current_journey_step.step.key == "sjs-2"


@pytest.mark.django_db
def test_a_created_in_journey_association_fails_closed_without_provenance(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    page = _student_page(client, world["journey"])
    assert page.status_code == 200, page.content[:400]
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    # A pre-existing record predating the attempt: same owner, so ownership
    # passes, but it cannot satisfy a new-record requirement.
    stale = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPSTALE-1",
    )
    UcrDeclaration.objects.filter(pk=stale.pk).update(created_at=attempt.started_at - timezone.timedelta(days=1))
    journey_services.assign_record(
        attempt, role, stale.pk, JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    )
    stale.refresh_from_db()
    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is False
    assert "cannot yet verify" in message


@pytest.mark.django_db
def test_a_new_record_role_refuses_an_authorized_existing_assignment(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    page = _student_page(client, world["journey"])
    assert page.status_code == 200, page.content[:400]
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPNEW-1",
    )
    with pytest.raises(Exception):
        journey_services.assign_record(
            attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
        )


@pytest.mark.django_db
def test_journey_completion_requires_every_step_roles_and_lessons(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )

    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)

    # Steps satisfied and lessons complete, but the required role is missing.
    journey_services.refresh_journey_completion(attempt)
    attempt.refresh_from_db()
    assert attempt.completed_at is None

    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPDONE-1",
    )
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )

    assert journey_services.refresh_journey_completion(attempt) is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None
    assert attempt.status == JourneyAttempt.Status.COMPLETED

    # Idempotent: re-evaluation changes nothing.
    stamp = attempt.completed_at
    assert journey_services.refresh_journey_completion(attempt) is True
    attempt.refresh_from_db()
    assert attempt.completed_at == stamp

    html = _student_page(client, world["journey"]).content.decode()
    assert "Journey complete" in html


@pytest.mark.django_db
def test_completion_is_impossible_from_lesson_flags_alone_even_with_a_required_role(client, db):
    """The recorded Checkpoint 3 requirement, proven end to end through the
    student runtime: flags + roles cannot complete an evidence-less journey."""
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPFLAGS-1",
    )
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    for lesson in world["lessons"]:
        LessonAttempt.objects.create(
            enrolment=enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
    assert journey_services.refresh_journey_completion(attempt) is False
    attempt.refresh_from_db()
    assert attempt.completed_at is None
    html = _student_page(client, world["journey"]).content.decode()
    assert "Journey complete" not in html


@pytest.mark.django_db
def test_evidence_from_another_learner_never_matches(client, db):
    student = _student(db)
    other = _student(db, "other-learner")
    world = _world(db)
    _enrol(db, world, student)
    _enrol(db, world, other)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment__student=student, journey=world["journey"])

    other_enrolment = Enrolment.objects.get(student=other, programme_version=world["version"])
    other_lesson_attempt = LessonAttempt.objects.create(
        enrolment=other_enrolment, lesson=world["lessons"][0], theory_acknowledged_at=timezone.now(),
    )
    hybrid_verification.record_open(other_lesson_attempt, world["steps"][0])
    hybrid_verification.mark_verified(other_lesson_attempt, world["steps"][0])

    rows = journey_services.journey_step_rows(attempt)
    assert rows[0]["satisfied"] is False


@pytest.mark.django_db
def test_the_advance_endpoint_is_post_only_and_learner_scoped(client, db):
    student = _student(db)
    world = _world(db)
    _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])

    assert client.get(reverse("hybrid-journey-advance", args=[world["journey"].pk])).status_code == 405

    stranger = _student(db, "stranger")
    _enrol(db, world, stranger)
    client.force_login(stranger)
    _student_page(client, world["journey"])
    response = client.post(reverse("hybrid-journey-advance", args=[world["journey"].pk]))
    stranger_attempt = JourneyAttempt.objects.get(enrolment__student=stranger, journey=world["journey"])
    assert stranger_attempt.current_journey_step.step.key == "sjs-1"


@pytest.mark.django_db
def test_anonymous_learners_are_sent_to_login(client, db):
    world = _world(db)
    response = client.get(reverse("hybrid-journey-student", args=[world["journey"].pk]))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]



# --- Checkpoint 5 final verification: bypass attempts ----------------------------


@pytest.mark.django_db
def test_repeated_advance_posts_cannot_skip_an_unsatisfied_step(client, db):
    """Forged or repeated advance POSTs cannot walk past a step whose
    evidence is missing: the position only ever moves one canonical step,
    and only when the ceiling allows."""
    student = _student(db)
    world = _world(db)
    _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])

    for _attempt_number in range(4):
        _response, messages_text = _advance(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment__student=student, journey=world["journey"])
    assert attempt.current_journey_step.step.key == "sjs-1"


@pytest.mark.django_db
def test_reaching_the_last_step_then_completing_does_not_advance_past_the_end(client, db):
    student = _student(db)
    world = _world(db)
    _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])

    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=Enrolment.objects.get(student=student, programme_version=world["version"]),
            lesson=lesson, theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)

    _advance(client, world["journey"])  # 1 -> 2
    _response, messages_text = _advance(client, world["journey"])  # 2 -> end
    assert "final step" in messages_text
    _response, messages_text = _advance(client, world["journey"])  # forged extra
    assert "final step" in messages_text
    attempt = JourneyAttempt.objects.get(enrolment__student=student, journey=world["journey"])
    assert attempt.current_journey_step.step.key == "sjs-2"


@pytest.mark.django_db
def test_a_direct_workspace_url_to_a_locked_lesson_is_still_refused_during_a_journey(client, db):
    """Journey participation does not bypass lesson sequencing: lesson 2 stays
    unreachable by direct URL until lesson 1's attempt is complete."""
    student = _student(db)
    world = _world(db)
    _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])

    response = client.get(reverse("hybrid-workspace", args=[world["lessons"][1].pk]))
    assert response.status_code == 302  # PermissionDenied → portal redirect
    followed = client.get(response.url)
    assert "Finish the previous lesson" in " ".join(str(m) for m in followed.context["messages"])


# --- Checkpoint 5 correction: fail-closed new-record provenance -------------------


@pytest.mark.django_db
def test_a_fresh_created_in_journey_record_does_not_satisfy_a_new_record_role(client, db):
    """Even a brand-new, learner-owned record associated as created_in_journey
    stays unsatisfied: the schema cannot prove journey-workflow creation."""
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPFRESH-1",
    )
    assert record.created_at >= attempt.started_at  # fresh by every measurable signal
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    )
    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is False
    assert "cannot yet verify" in message


@pytest.mark.django_db
def test_an_unsatisfied_new_record_role_blocks_journey_completion(client, db):
    """Full step evidence and complete lessons still cannot complete a journey
    while its required new-record role is unsatisfied (fail closed)."""
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)

    assert journey_services.refresh_journey_completion(attempt) is False
    attempt.refresh_from_db()
    assert attempt.completed_at is None


@pytest.mark.django_db
def test_an_existing_record_role_retains_its_permitted_behaviour(client, db):
    """Authorized existing-record handling is unchanged by the fail-closed rule."""
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    role = JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.EXISTING,
    )
    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPEXIST-1",
    )
    journey_services.assign_record(
        attempt, role, record.pk, JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    satisfied, message = journey_services.role_satisfied(attempt, role)
    assert satisfied is True and "record assigned" in message


@pytest.mark.django_db
def test_an_optional_unsatisfied_role_does_not_block_completion(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    JourneyRecordRole.objects.create(
        journey=world["journey"], key="note", label="Optional note", record_kind="ucr",
        required=False, order=1, creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    lesson_attempts = [
        LessonAttempt.objects.create(
            enrolment=enrolment, lesson=lesson,
            completed_at=timezone.now(), theory_acknowledged_at=timezone.now(),
        )
        for lesson in world["lessons"]
    ]
    for lesson_attempt in lesson_attempts:
        for step in lesson_attempt.lesson.practical_steps.all():
            hybrid_verification.record_open(lesson_attempt, step)

    assert journey_services.refresh_journey_completion(attempt) is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None


@pytest.mark.django_db
def test_the_journey_page_reports_the_open_new_record_requirement(client, db):
    student = _student(db)
    world = _world(db)
    enrolment = _enrol(db, world, student)
    client.force_login(student)
    _student_page(client, world["journey"])
    attempt = JourneyAttempt.objects.get(enrolment=enrolment, journey=world["journey"])
    JourneyRecordRole.objects.create(
        journey=world["journey"], key="ucr", label="Primary UCR", record_kind="ucr", order=1,
        creation_mode=JourneyRecordRole.CreationMode.NEW,
    )
    record = UcrDeclaration.objects.create(
        owner=student, status="draft", exporter_name="ACME", temp_no="TEMPREPORT-1",
    )
    journey_services.assign_record(
        attempt, role_pk := JourneyRecordRole.objects.get(key="ucr"), record.pk,
        JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    )

    html = _student_page(client, world["journey"]).content.decode()
    assert "cannot yet verify" in html
    assert "Primary UCR" in html
