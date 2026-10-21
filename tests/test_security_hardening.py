"""The audit remediations (docs/security-audit-2026-10-17.md).

One test per fixed finding: private media is served only to its owner
(SEC-01/SEC-11), simulator credentials can only be issued to a student on the
instructor's own roster (SEC-02), assessment saves and submits re-read the
attempt under lock and refuse a finished one (SEC-05), attachments must match
their declared file type (SEC-07), and the public authentication endpoints
refuse bursts of failures (SEC-08).
"""

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse

from accounts.models import SimulatorCredential, User, allocate_student_id
from assessments.models import (
    AnswerOption,
    Assessment,
    AssessmentItem,
    Question,
    QuestionVersion,
    TheoryAttempt,
)
from assessments.services import get_or_start_attempt, save_attempt_answers, submit_attempt
from audit.models import AuditEvent
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from scenarios.models import UcrDeclaration, UcrDocumentAttachment
from scenarios.views import _content_matches_extension, _validate_ucr_attachments


def _user(username, group_name, **kwargs):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.test", password="test-password", **kwargs
    )
    user.student_id = allocate_student_id(username)
    user.groups.add(Group.objects.get(name=group_name))
    return user


@pytest.fixture
def programme_version(db):
    programme = Programme.objects.create(name="Audit Programme", difficulty="beginner")
    return ProgrammeVersion.objects.create(programme=programme, version=1, status="published")


@pytest.fixture
def students(db):
    owner = _user("media-owner", "Student", first_name="Owner")
    other = _user("media-other", "Student", first_name="Other")
    return owner, other


# --- SEC-01 / SEC-11: media serving -----------------------------------------


@pytest.fixture
def owned_attachment(db, students, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    owner, _ = students
    ucr = UcrDeclaration.objects.create(owner=owner, ucr_no="TEMPUCRMEDIA01", status="submitted", regime="10", declarant_code="MED001")
    attachment = UcrDocumentAttachment.objects.create(
        ucr=ucr, row_index=0, file=SimpleUploadedFile("report.pdf", b"%PDF-1.4 fictional"), original_name="report.pdf"
    )
    return attachment


def test_private_media_redirects_anonymous_visitors(client, owned_attachment):
    response = client.get(reverse("media", args=[owned_attachment.file.name]))
    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


def test_private_media_is_refused_to_other_students(client, owned_attachment, db, students):
    _, other = students
    client.force_login(other)
    response = client.get(reverse("media", args=[owned_attachment.file.name]))
    assert response.status_code == 404


def test_private_media_serves_the_owner_with_nosniff(client, owned_attachment, db):
    client.force_login(owned_attachment.ucr.owner)
    response = client.get(reverse("media", args=[owned_attachment.file.name]))
    assert response.status_code == 200
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("group_name", ["Instructor", "Administrator"])
def test_private_media_serves_reviewing_staff(client, owned_attachment, db, group_name):
    reviewer = _user(f"media-{group_name.lower()}", group_name, first_name="Reviewer")
    client.force_login(reviewer)
    response = client.get(reverse("media", args=[owned_attachment.file.name]))
    assert response.status_code == 200


def test_an_orphan_private_file_is_refused_even_when_signed_in(client, owned_attachment, db, students):
    _, other = students
    orphan_name = owned_attachment.file.storage.save("ucr_attachments/orphan.pdf", ContentFile(b"%PDF-1.4 orphan"))
    client.force_login(other)
    response = client.get(reverse("media", args=[orphan_name]))
    assert response.status_code == 404


def test_public_cover_artwork_stays_anonymous(client, settings, tmp_path, db):
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "course_covers").mkdir()
    (tmp_path / "course_covers" / "cover.jpg").write_bytes(b"\xff\xd8\xff cover")
    response = client.get(reverse("media", args=["course_covers/cover.jpg"]))
    assert response.status_code == 200


def test_a_media_path_that_escapes_media_root_is_refused(client, db):
    response = client.get("/media/../outside.pdf")
    assert response.status_code == 404


# --- SEC-02: credential issuance --------------------------------------------


@pytest.fixture
def roster(db, programme_version):
    instructor_a = _user("roster-instructor-a", "Instructor", first_name="Alpha")
    instructor_b = _user("roster-instructor-b", "Instructor", first_name="Beta")
    student = _user("roster-student", "Student", first_name="Student")
    Enrolment.objects.create(student=student, programme_version=programme_version, enrolled_by=instructor_a)
    return instructor_a, instructor_b, student


def _issue(client, instructor, student):
    client.force_login(instructor)
    return client.post(reverse("simulator-credential-issue", args=[student.pk]))


def test_an_instructor_cannot_issue_for_another_instructors_student(client, roster, db):
    instructor_a, instructor_b, student = roster
    response = _issue(client, instructor_b, student)
    assert response.status_code == 404


def test_an_instructor_cannot_issue_for_a_staff_account(client, roster, db):
    instructor_a, _, _ = roster
    response = _issue(client, instructor_a, instructor_a)
    assert response.status_code == 404


def test_the_assigning_instructor_issues_and_the_event_is_audited(client, roster, db):
    instructor_a, _, student = roster
    response = _issue(client, instructor_a, student)
    assert response.status_code == 200
    credential = SimulatorCredential.objects.get(user=student)
    assert credential.issued_at is not None
    assert AuditEvent.objects.filter(
        actor=instructor_a, action_code="simulator.credential_issued", target_id=str(student.pk)
    ).exists()


def test_a_get_request_still_returns_to_the_roster(client, roster, db):
    instructor_a, _, student = roster
    client.force_login(instructor_a)
    response = client.get(reverse("simulator-credential-issue", args=[student.pk]))
    assert response.status_code == 302
    assert response.url == reverse("instructor-dashboard")


# --- SEC-05: attempt locking -------------------------------------------------


@pytest.fixture
def theory_assessment(db, programme_version):
    assessment = Assessment.objects.create(programme_version=programme_version, title="Audit assessment", is_published=True)
    question = Question.objects.create(code="audit-q1")
    version = QuestionVersion.objects.create(question=question, version=1)
    correct = AnswerOption.objects.create(question_version=version, label="Right", is_correct=True, order=1)
    AnswerOption.objects.create(question_version=version, label="Wrong", is_correct=False, order=2)
    AssessmentItem.objects.create(assessment=assessment, question_version=version, order=1)
    return assessment, version, correct


def _enrolled_student(programme_version):
    return _user(f"attempt-{str(programme_version.pk)[:8]}", "Student", first_name="Attempt")


def test_a_submitted_attempt_refuses_save_and_resubmit(db, programme_version, theory_assessment):
    assessment, version, correct = theory_assessment
    student = _enrolled_student(programme_version)
    enrolment = Enrolment.objects.create(student=student, programme_version=programme_version)
    attempt = get_or_start_attempt(enrolment, assessment)
    submit_attempt(attempt, {str(version.pk): correct.pk})
    with pytest.raises(ValueError):
        save_attempt_answers(attempt, {})
    with pytest.raises(ValueError):
        submit_attempt(attempt, {str(version.pk): correct.pk})


def test_save_then_submit_scores_the_posted_answer(db, programme_version, theory_assessment):
    # Submitting scores the answers the form posts back (the saved selections
    # only prefill it), so the posted answer is what must be scored.
    assessment, version, correct = theory_assessment
    student = _enrolled_student(programme_version)
    enrolment = Enrolment.objects.create(student=student, programme_version=programme_version)
    attempt = get_or_start_attempt(enrolment, assessment)
    save_attempt_answers(attempt, {str(version.pk): correct.pk})
    finished = submit_attempt(attempt, {str(version.pk): correct.pk})
    assert finished.score == 1
    assert finished.outcome == TheoryAttempt.Outcome.PASS


# --- SEC-07: upload content checks ------------------------------------------


def test_an_upload_whose_content_does_not_match_its_extension_is_refused():
    impostor = SimpleUploadedFile("innocent.png", b"<script>alert(1)</script>")
    assert _content_matches_extension(impostor) is False


@pytest.mark.parametrize(
    "name,head",
    [
        ("doc.pdf", b"%PDF-1.7 tail"),
        ("shot.png", b"\x89PNG\r\n\x1a\nrest"),
        ("scan.jpg", b"\xff\xd8\xff\xe0rest"),
        ("letter.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest"),
        ("sheet.docx", b"PK\x03\x04rest"),
    ],
)
def test_genuine_leading_signatures_are_accepted(name, head):
    genuine = SimpleUploadedFile(name, head)
    assert _content_matches_extension(genuine) is True


def test_the_save_validator_rejects_a_renamed_script(db):
    request = RequestFactory().post("/upload/", data={"file_0": SimpleUploadedFile("evil.png", b"#!/bin/sh")})
    with pytest.raises(ValidationError):
        _validate_ucr_attachments([{}], request)


def test_the_save_validator_accepts_a_real_image(db):
    request = RequestFactory().post(
        "/upload/", data={"file_0": SimpleUploadedFile("real.png", b"\x89PNG\r\n\x1a\nimage")}
    )
    _validate_ucr_attachments([{}], request)


# --- SEC-08: authentication rate limits -------------------------------------


LOC_MEMORY = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.fixture
def counted_cache():
    cache.clear()
    with override_settings(CACHES=LOC_MEMORY):
        yield cache
    cache.clear()


@pytest.mark.django_db
def test_repeated_login_failures_lock_the_account_even_for_the_right_password(client, counted_cache, db):
    _user("throttle-student", "Student", first_name="Throttle")
    wrong = {"username": "throttle-student", "password": "not-the-password"}
    for _ in range(5):
        assert client.post(reverse("login"), wrong).status_code == 200
    right = {"username": "throttle-student", "password": "test-password"}
    response = client.post(reverse("login"), right)
    assert response.status_code == 200
    assert "Too many failed sign-in attempts" in response.content.decode()


@pytest.mark.django_db
def test_a_different_account_is_not_blocked_by_anothers_failures(client, counted_cache, db):
    _user("throttle-one", "Student", first_name="One")
    second = _user("throttle-two", "Student", first_name="Two")
    wrong = {"username": "throttle-one", "password": "not-the-password"}
    for _ in range(5):
        client.post(reverse("login"), wrong)
    response = client.post(reverse("login"), {"username": "throttle-two", "password": "test-password"})
    assert response.status_code == 302


@pytest.mark.django_db
def test_a_successful_sign_in_clears_the_failure_count(client, counted_cache, db):
    _user("throttle-recover", "Student", first_name="Recover")
    wrong = {"username": "throttle-recover", "password": "not-the-password"}
    for _ in range(4):
        client.post(reverse("login"), wrong)
    assert client.post(reverse("login"), {"username": "throttle-recover", "password": "test-password"}).status_code == 302
    client.post(reverse("login"), wrong)  # a single typo afterwards must not lock the account
    response = client.post(reverse("login"), {"username": "throttle-recover", "password": "test-password"})
    assert response.status_code == 302


@pytest.mark.django_db
def test_repeated_simulator_failures_lock_the_student_id(client, counted_cache, db):
    student = _user("throttle-sim", "Student", first_name="Sim")
    credential, _ = SimulatorCredential.objects.get_or_create(user=student)
    raw_password = credential.issue()
    url = reverse("simulator-login")
    for _ in range(5):
        client.post(url, {"student_id": student.student_id, "password": "wrong"})
    response = client.post(url, {"student_id": student.student_id, "password": raw_password}, follow=True)
    assert "Too many failed simulator sign-in attempts" in response.content.decode()


@pytest.mark.django_db
def test_repeated_registrations_are_refused_after_the_limit(counted_cache, db):
    # Each success signs the client in, so every attempt needs a fresh client;
    # the limit is per address and follows across clients.
    def registration(number):
        return {
            "first_name": "Reg", "last_name": f"Number{number}", "email": f"reg{number}@example.test",
            "password1": "sV#9pL2$qW!7", "password2": "sV#9pL2$qW!7", "terms_accepted": "on",
        }

    for number in range(10):
        assert Client().post(reverse("register"), registration(number)).status_code == 302
    blocked = Client().post(reverse("register"), registration(11))
    assert blocked.status_code == 200
    assert User.objects.filter(email__startswith="reg").count() == 10
