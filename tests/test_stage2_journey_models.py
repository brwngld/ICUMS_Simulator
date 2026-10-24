"""Stage 2 Checkpoint 2: additive Practical Journey model safeguards."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

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
    PracticalJourney,
    PracticalStep,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration


def curriculum(code, version_number=1):
    programme = Programme.objects.create(
        name=f"Programme {code}",
        code=code,
        learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme,
        version=version_number,
        status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(programme_version=version, code="course", title="Course")
    module = HybridModule.objects.create(course=course, code="module", title="Module")
    lesson = HybridLesson.objects.create(module=module, slug="lesson", title="Lesson")
    step = PracticalStep.objects.create(lesson=lesson, key="step", title="Step")
    return programme, version, course, module, lesson, step


def journey_for(version, course, code="journey", order=1):
    return PracticalJourney.objects.create(
        programme_version=version,
        course=course,
        code=code,
        title=f"Journey {code}",
        order=order,
    )


@pytest.mark.django_db
def test_existing_steps_and_conditions_need_no_journey_assignment():
    _programme, _version, _course, _module, _lesson, step = curriculum("legacy-compatible")
    condition = VerificationCondition.objects.create(
        step=step,
        kind=VerificationCondition.Kind.SCREEN_OPENED,
    )

    assert not JourneyStep.objects.filter(step=step).exists()
    assert not JourneyConditionBinding.objects.filter(condition=condition).exists()
    assert PracticalStep.objects.filter(pk=step.pk).exists()
    assert VerificationCondition.objects.filter(pk=condition.pk).exists()


@pytest.mark.django_db
def test_journey_rejects_a_course_from_another_programme_version():
    _p1, version1, _course1, *_ = curriculum("journey-version-a")
    _p2, _version2, course2, *_ = curriculum("journey-version-b")
    journey = PracticalJourney(
        programme_version=version1,
        course=course2,
        code="wrong-course",
        title="Wrong course",
    )

    with pytest.raises(ValidationError, match="programme version"):
        journey.full_clean()


@pytest.mark.django_db
def test_journey_step_rejects_cross_course_assignment():
    _p1, version1, course1, *_ = curriculum("step-scope-a")
    _p2, _version2, _course2, _module2, _lesson2, step2 = curriculum("step-scope-b")
    journey = journey_for(version1, course1)
    assignment = JourneyStep(journey=journey, step=step2, journey_order=1)

    with pytest.raises(ValidationError, match="course and programme version"):
        assignment.full_clean()


@pytest.mark.django_db
def test_one_practical_step_can_belong_to_only_one_journey():
    _p, version, course, _module, _lesson, step = curriculum("one-assignment")
    first = journey_for(version, course, "first")
    second = journey_for(version, course, "second", order=2)
    JourneyStep.objects.create(journey=first, step=step, journey_order=1)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyStep.objects.create(journey=second, step=step, journey_order=1)


@pytest.mark.django_db
def test_dependency_requires_forward_steps_in_the_same_journey():
    _p, version, course, module, _lesson, first_step = curriculum("dependency")
    second_lesson = HybridLesson.objects.create(module=module, slug="second", title="Second", order=2)
    second_step = PracticalStep.objects.create(lesson=second_lesson, key="second", title="Second")
    journey = journey_for(version, course)
    first = JourneyStep.objects.create(journey=journey, step=first_step, journey_order=1)
    second = JourneyStep.objects.create(journey=journey, step=second_step, journey_order=2)

    valid = JourneyDependency(
        journey=journey,
        predecessor_step=first,
        dependent_step=second,
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    valid.full_clean()

    backward = JourneyDependency(
        journey=journey,
        predecessor_step=second,
        dependent_step=first,
        dependency_type=JourneyDependency.DependencyType.STEP_COMPLETED,
    )
    with pytest.raises(ValidationError, match="after its predecessor"):
        backward.full_clean()


@pytest.mark.django_db
def test_record_role_accepts_only_approved_record_kinds():
    _p, version, course, *_ = curriculum("role-kind")
    journey = journey_for(version, course)
    role = JourneyRecordRole(journey=journey, key="unknown", label="Unknown", record_kind="unknown")

    with pytest.raises(ValidationError, match="approved simulator record"):
        role.full_clean()


@pytest.mark.django_db
def test_journey_attempt_rejects_cross_version_enrolment_and_current_step():
    owner = User.objects.create_user(username="attempt-owner")
    _p1, version1, course1, _module1, _lesson1, step1 = curriculum("attempt-a")
    _p2, version2, course2, _module2, _lesson2, step2 = curriculum("attempt-b")
    enrolment = Enrolment.objects.create(student=owner, programme_version=version1)
    journey1 = journey_for(version1, course1)
    journey2 = journey_for(version2, course2)
    assignment2 = JourneyStep.objects.create(journey=journey2, step=step2, journey_order=1)

    wrong_version = JourneyAttempt(enrolment=enrolment, journey=journey2)
    with pytest.raises(ValidationError, match="programme version"):
        wrong_version.full_clean()

    wrong_step = JourneyAttempt(
        enrolment=enrolment,
        journey=journey1,
        current_journey_step=assignment2,
    )
    with pytest.raises(ValidationError, match="current step"):
        wrong_step.full_clean()


@pytest.mark.django_db
def test_database_prevents_duplicate_journey_attempts():
    owner = User.objects.create_user(username="duplicate-attempt")
    _p, version, course, *_ = curriculum("duplicate-attempt")
    enrolment = Enrolment.objects.create(student=owner, programme_version=version)
    journey = journey_for(version, course)
    JourneyAttempt.objects.create(enrolment=enrolment, journey=journey)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyAttempt.objects.create(enrolment=enrolment, journey=journey)


@pytest.mark.django_db
def test_exact_record_association_checks_owner_role_and_version():
    owner = User.objects.create_user(username="record-owner")
    other = User.objects.create_user(username="other-owner")
    _p, version, course, *_ = curriculum("record-association")
    enrolment = Enrolment.objects.create(student=owner, programme_version=version)
    journey = journey_for(version, course)
    role = JourneyRecordRole.objects.create(
        journey=journey,
        key="primary-ucr",
        label="Primary UCR",
        record_kind="ucr",
    )
    attempt = JourneyAttempt.objects.create(enrolment=enrolment, journey=journey)
    owned_record = UcrDeclaration.objects.create(owner=owner, regime="IM", temp_no="TEMPUCR000000000001")
    unrelated_record = UcrDeclaration.objects.create(owner=other, regime="IM", temp_no="TEMPUCR000000000002")

    valid = JourneyRecordAssociation(
        journey_attempt=attempt,
        role=role,
        enrolment=enrolment,
        programme_version=version,
        record_kind="ucr",
        record_id=owned_record.pk,
        assignment_source=JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    )
    valid.full_clean()

    invalid = JourneyRecordAssociation(
        journey_attempt=attempt,
        role=role,
        enrolment=enrolment,
        programme_version=version,
        record_kind="ucr",
        record_id=unrelated_record.pk,
        assignment_source=JourneyRecordAssociation.AssignmentSource.AUTHORIZED_EXISTING,
    )
    with pytest.raises(ValidationError, match="enrolled learner"):
        invalid.full_clean()


@pytest.mark.django_db
def test_sqlite_constraint_allows_history_but_only_one_active_record_per_role():
    owner = User.objects.create_user(username="record-history")
    _p, version, course, *_ = curriculum("record-history")
    enrolment = Enrolment.objects.create(student=owner, programme_version=version)
    journey = journey_for(version, course)
    role = JourneyRecordRole.objects.create(
        journey=journey,
        key="primary-ucr",
        label="Primary UCR",
        record_kind="ucr",
    )
    attempt = JourneyAttempt.objects.create(enrolment=enrolment, journey=journey)
    records = [
        UcrDeclaration.objects.create(owner=owner, regime="IM", temp_no=f"TEMPUCR00000000000{index}")
        for index in range(1, 4)
    ]
    common = {
        "journey_attempt": attempt,
        "role": role,
        "enrolment": enrolment,
        "programme_version": version,
        "record_kind": "ucr",
        "assignment_source": JourneyRecordAssociation.AssignmentSource.CREATED_IN_JOURNEY,
    }
    JourneyRecordAssociation.objects.create(record_id=records[0].pk, **common)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            JourneyRecordAssociation.objects.create(record_id=records[1].pk, **common)

    first = JourneyRecordAssociation.objects.get(record_id=records[0].pk)
    first.is_active = False
    first.replaced_at = timezone.now()
    first.save(update_fields=("is_active", "replaced_at"))
    JourneyRecordAssociation.objects.create(record_id=records[2].pk, **common)
    assert JourneyRecordAssociation.objects.filter(journey_attempt=attempt, role=role, is_active=True).count() == 1
    assert JourneyRecordAssociation.objects.filter(journey_attempt=attempt, role=role, is_active=False).count() == 1


@pytest.mark.django_db
def test_condition_binding_requires_same_journey_and_record_kind():
    _p, version, course, _module, _lesson, step = curriculum("condition-binding")
    journey = journey_for(version, course)
    JourneyStep.objects.create(journey=journey, step=step, journey_order=1)
    role = JourneyRecordRole.objects.create(
        journey=journey,
        key="primary-ucr",
        label="Primary UCR",
        record_kind="ucr",
    )
    condition = VerificationCondition.objects.create(
        step=step,
        kind=VerificationCondition.Kind.SAVED_RECORD,
        record_kind="ucr",
        required_status=UcrDeclaration.Status.DRAFT,
    )

    JourneyConditionBinding(condition=condition, role=role).full_clean()

    condition.kind = VerificationCondition.Kind.SCREEN_OPENED
    condition.save(update_fields=("kind",))
    with pytest.raises(ValidationError, match="saved-record"):
        JourneyConditionBinding(condition=condition, role=role).full_clean()
