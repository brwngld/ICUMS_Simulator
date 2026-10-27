"""MDA activity freshness: the journey and simulator verifiers decide whether a
record was worked during a visit from ``max(updated_at, submitted_at, created_at)``.

MDA draft edits and submissions are partial saves, so they must list
``updated_at`` explicitly or a learner's genuine work stays invisible to
verification. These tests pin that behaviour on the real endpoints and on the
evaluator that reads it.
"""
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from hybrid import verification
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    LessonAttempt,
    PracticalStep,
    VerificationCondition,
)
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import (
    ConsignmentApplication,
    MdaAgency,
    MdaApplication,
    MdaConsignmentRequest,
    MdaProcess,
    MdaStatus,
    UcrDeclaration,
)

HOUR = timedelta(hours=1)


def _owner(username):
    return User.objects.create_user(
        username=username, email=f"{username}@example.test", password="x", is_staff=True,
    )


def _mda_request(owner, application_no, mda_code="MOTI", app_code="IDF", documents=None):
    """The approved MDA chain: UCR → consignment application → MDA request."""
    agency = MdaAgency.objects.get_or_create(code=mda_code, defaults={"name": f"{mda_code} Authority"})[0]
    application = MdaApplication.objects.get_or_create(
        mda=agency, code=app_code, defaults={"name": f"{app_code} Application"},
    )[0]
    process = MdaProcess.objects.get_or_create(
        application=application, code="NEW", defaults={"name": "New Application"},
    )[0]
    ucr = UcrDeclaration.objects.create(
        owner=owner, regime="IM", goods_description="VEHICLE",
        origin_country="CN", destination_country="GH", transport_mode="10, Sea Transport",
        temp_no="TEMP" + application_no[-7:], ucr_no="UCR" + application_no[-7:],
        status=UcrDeclaration.Status.SUBMITTED, documents=list(documents or []),
    )
    consignment = ConsignmentApplication.objects.create(
        owner=owner, ucr=ucr, status=ConsignmentApplication.Status.SUBMITTED,
    )
    return MdaConsignmentRequest.objects.create(
        consignment_application=consignment, owner=owner,
        mda=agency, application=application, process=process,
        consignment_type="SG", application_no=application_no,
    )


def _backdate(record, moment):
    """Move the row's own timestamps without touching the auto_now field."""
    MdaConsignmentRequest.objects.filter(pk=record.pk).update(created_at=moment, updated_at=moment)
    record.refresh_from_db()
    return record


def _verification_step(owner, username):
    """One practical step whose only condition is a saved draft MDA request."""
    programme = Programme.objects.create(
        name=username, code=username, learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(
        programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT,
    )
    course = HybridCourse.objects.create(
        programme_version=version, code=f"{username}-c", title="Course", order=1,
    )
    module = HybridModule.objects.create(course=course, code=f"{username}-m", title="Module", order=1)
    lesson = HybridLesson.objects.create(
        module=module, slug=f"{username}-l", title="Lesson", order=1, theory="<p>Theory</p>",
    )
    step = PracticalStep.objects.create(
        lesson=lesson, key=f"{username}-s", title="Apply to the MDA", order=1,
        screen="single-window-overview",
    )
    VerificationCondition.objects.create(
        step=step, kind=VerificationCondition.Kind.SAVED_RECORD, record_kind="mda",
        required_status=MdaStatus.DRAFT, expected_fields={"consignment_type": "SG"}, order=1,
    )
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    enrolment = Enrolment.objects.create(student=owner, programme_version=version)
    lesson_attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    return step, lesson_attempt


@pytest.mark.django_db
def test_draft_save_advances_updated_at():
    owner = _owner("mdafresh-draft")
    record = _mda_request(owner, "CD202609MOTIIDF9000001")
    before = record.updated_at
    _backdate(record, timezone.now() - HOUR)
    stale_moment = record.updated_at

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"reference_info": "edited by the learner"}, content_type="application/json",
    )

    assert response.status_code == 200
    record.refresh_from_db()
    assert record.form_data["reference_info"] == "edited by the learner"
    assert record.updated_at > stale_moment
    assert record.status == MdaStatus.DRAFT


@pytest.mark.django_db
def test_submit_advances_updated_at():
    owner = _owner("mdafresh-submit")
    record = _mda_request(owner, "CD202609FDAIPF9000002", mda_code="FDA", app_code="IP")
    _backdate(record, timezone.now() - HOUR)
    stale_moment = record.updated_at

    client = Client()
    client.force_login(owner)
    response = client.post(reverse("mda-consignment-application-submit", args=(record.pk,)), {})

    assert response.status_code == 200
    record.refresh_from_db()
    assert record.status == MdaStatus.SUBMITTED
    assert record.submitted_at is not None
    assert record.updated_at > stale_moment


@pytest.mark.django_db
def test_a_post_opening_mda_edit_satisfies_the_freshness_bound():
    """The defect, observed through the evaluator: the learner opens the step,
    edits the draft, and Check-My-Work must see that work."""
    owner = _owner("mdafresh-evaluator")
    step, lesson_attempt = _verification_step(owner, "mdafresh-evaluator")
    record = _mda_request(owner, "CD202609MOTIIDF9000003")
    _backdate(record, timezone.now() - HOUR)

    verification.record_open(lesson_attempt, step)
    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"reference_info": "worked after entering the step"}, content_type="application/json",
    )
    assert response.status_code == 200

    record.refresh_from_db()
    bound = verification.opened_at(lesson_attempt, step)
    assert record.updated_at > bound
    assert verification.verify_step(lesson_attempt, step)["passed"] is True


@pytest.mark.django_db
def test_a_record_untouched_since_the_opening_stays_stale():
    """Re-entry authorizes nothing: work from before this visit is still too
    old, so the step keeps demanding it."""
    owner = _owner("mdafresh-stale")
    step, lesson_attempt = _verification_step(owner, "mdafresh-stale")
    record = _mda_request(owner, "CD202609MOTIIDF9000004")

    client = Client()
    client.force_login(owner)
    verification.record_open(lesson_attempt, step)
    client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"reference_info": "worked before re-entering"}, content_type="application/json",
    )
    # The edit is now a visit old: rewind it, then re-enter the step.
    _backdate(record, timezone.now() - HOUR)
    verification.record_open(lesson_attempt, step)

    assert verification.verify_step(lesson_attempt, step)["passed"] is False
    assert record.status == MdaStatus.DRAFT

    client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"reference_info": "worked again"}, content_type="application/json",
    )
    assert verification.verify_step(lesson_attempt, step)["passed"] is True


@pytest.mark.django_db
def test_a_refused_draft_save_does_not_advance_updated_at():
    """The Approval-tab document check returns before the save, so a refused
    write must not look like learner activity."""
    owner = _owner("mdafresh-refused")
    record = _mda_request(owner, "CD202609MOTIIDF9000005")
    _backdate(record, timezone.now() - HOUR)
    stale_moment = record.updated_at

    client = Client()
    client.force_login(owner)
    response = client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"approval_save": True}, content_type="application/json",
    )

    assert response.status_code == 400
    record.refresh_from_db()
    assert record.updated_at == stale_moment
    assert record.status == MdaStatus.DRAFT


@pytest.mark.django_db
def test_another_users_write_does_not_advance_updated_at():
    owner = _owner("mdafresh-foreign-owner")
    intruder = _owner("mdafresh-foreign-intruder")
    record = _mda_request(owner, "CD202609MOTIIDF9000006")
    _backdate(record, timezone.now() - HOUR)
    stale_moment = record.updated_at

    client = Client()
    client.force_login(intruder)
    response = client.post(
        reverse("mda-consignment-application-save", args=(record.pk,)),
        {"reference_info": "tampering"}, content_type="application/json",
    )

    assert response.status_code == 404
    record.refresh_from_db()
    assert record.updated_at == stale_moment
    assert record.form_data == {}
