"""Practise Again — repeat attempts as disposable scratch runs.

Interactive Practical lessons are training, not examinations. A completed
attempt stays recorded and never relocks the lesson; a repeat ("practice
run") is a fresh attempt whose stage checks verify only what the run itself
produces: scratch records scoped to the attempt (PRCTUCR…), invisible to
every ordinary listing, excluded from the creation ledger, and thrown away
the moment the run completes. Progression truth is never touched by any of
it — repetition cannot lose, reset or inflate completion.
"""
import pytest
from django.urls import reverse
from django.utils import timezone

from hybrid import publishing, services, verification
from hybrid.models import LessonAttempt, StepEvent
from onboarding.models import Enrolment, ProgrammeVersion
from scenarios.models import UcrDeclaration

from tests.test_hybrid_progress import _acknowledge_theory, _learner_enrolled, _published_edition


def _ack_theory(client, learner, lesson):
    from hybrid.models import LessonAttempt
    from django.utils import timezone as _tz
    from onboarding.models import Enrolment
    enrolment = Enrolment.objects.get(student=learner)
    attempt = LessonAttempt.objects.filter(
        enrolment=enrolment, lesson=lesson,
    ).order_by("-started_at").first()
    if attempt is None:
        attempt = LessonAttempt.objects.create(enrolment=enrolment, lesson=lesson)
    attempt.theory_acknowledged_at = _tz.now()
    attempt.save(update_fields=("theory_acknowledged_at",))


def _complete_lesson(client, learner, lesson, temp_no):
    """Walk a one-step lesson to completion as the learner: open its step,
    satisfy a verification step with a fresh record, acknowledge theory.
    Condition-free steps satisfy on entry and take no check. On a practice
    attempt the workspace binds the browser, so the record the helper
    creates is the run's own scoped scratch record."""
    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    attempt = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()
    step = lesson.practical_steps.order_by("order", "id").first()
    assert client.post(reverse("hybrid-step-open", args=[attempt.pk, 0])).json()["ok"] is True
    if verification.step_requires_verification(step):
        create = UcrDeclaration.all_objects.create
        scoped = {"practice_attempt": attempt} if services.is_practice_attempt(attempt) else {}
        create(
            owner=learner, status="draft", exporter_name="ACME Trading",
            temp_no=temp_no, **scoped,
        )
        assert client.post(reverse("hybrid-step-check", args=[attempt.pk, 0])).json()["passed"] is True
    assert client.post(reverse("hybrid-acknowledge-theory", args=[attempt.pk])).json()["ok"] is True
    attempt.refresh_from_db()
    assert attempt.completed_at is not None
    return attempt


def _simulator_access(client, learner):
    """The learner's standalone simulator session (credential + signed-in simulator)."""
    from accounts.models import SimulatorCredential

    if not learner.student_id:
        learner.student_id = f"STU-{learner.username.upper()}"
        learner.save(update_fields=("student_id",))
    credential = SimulatorCredential.objects.filter(user=learner).first()
    if credential is None:
        credential = SimulatorCredential.objects.create(user=learner)
    credential.issue()
    session = client.session
    session["simulator_user_id"] = str(learner.pk)
    session.save()


def _ucr_body(**overrides):
    """A valid Create-UCR payload, as the simulator page posts it."""
    payload = {
        "regime": "IM",
        "show_provider": True,
        "provider": {
            "declarant_code": "CH000869", "code": "C0029705992", "name": "Practice Provider",
            "country": "GH", "address": "1 Practice Road", "contact": "Practice Contact",
            "phone": "+233200000003", "email": "practice@example.test", "email_2": "",
        },
        "exporter": {
            "name": "Practice Exporter", "country": "CN", "address": "1 Export Road",
            "phone": "+233200000001", "contact": "Export Contact",
            "contact_no": "+233200000002", "designation": "Manager",
        },
        "importer": {
            "identity": "C0000000001", "name": "Practice Importer", "country": "GH",
            "address": "1 Import Road", "phone": "+233200000004", "contact": "Import Contact",
            "contact_no": "+233200000005", "designation": "Manager",
        },
        "consignment": {
            "goods": "Practice goods", "origin": "CN", "destination": "GH", "mode": "10, Sea Transport",
        },
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_practise_again_creates_a_fresh_attempt_and_preserves_history(client, db):
    _, version, _, _, lessons = _published_edition("repeat", lesson_count=1)
    learner = _learner_enrolled(db, "repeater", version)
    lesson = lessons[0]
    first = _complete_lesson(client, learner, lesson, "TEMPTESTR1")
    events_before = list(StepEvent.objects.filter(attempt=first).order_by("occurred_at"))

    response = client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    assert response.status_code == 302

    attempts = list(LessonAttempt.objects.filter(enrolment__student=learner, lesson=lesson).order_by("started_at"))
    assert len(attempts) == 2
    first.refresh_from_db()
    assert first.completed_at is not None  # history untouched
    assert list(StepEvent.objects.filter(attempt=first).order_by("occurred_at")) == events_before
    second = attempts[1]
    assert second.completed_at is None
    assert second.current_step == lesson.practical_steps.order_by("order", "id").first()


@pytest.mark.django_db
def test_a_practice_run_verifies_only_its_own_scoped_record(client, db):
    _, version, _, _, lessons = _published_edition("isolate", lesson_count=1)
    learner = _learner_enrolled(db, "isolated", version)
    lesson = lessons[0]
    _complete_lesson(client, learner, lesson, "TEMPTESTI1")

    client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    second = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()
    assert client.post(reverse("hybrid-step-open", args=[second.pk, 0])).json()["ok"] is True

    # Attempt 1's draft is not this run's evidence — the refusal names the
    # practice run and asks for a new record.
    stale = client.post(reverse("hybrid-step-check", args=[second.pk, 0])).json()
    assert stale["passed"] is False
    assert any("in this practice run" in r["message"] for r in stale["results"])

    # A record produced inside the run — scoped to it — satisfies the stage.
    UcrDeclaration.all_objects.create(
        owner=learner, status="draft", exporter_name="ACME Trading",
        practice_attempt=second, temp_no="TEMPTESTI2",
    )
    assert client.post(reverse("hybrid-step-check", args=[second.pk, 0])).json()["passed"] is True


@pytest.mark.django_db
def test_repeated_completions_do_not_inflate_progress(client, db):
    _, version, _, module, lessons = _published_edition("counted", lesson_count=2)
    learner = _learner_enrolled(db, "counted", version)
    lesson1, lesson2 = lessons
    enrolment = Enrolment.objects.get(student=learner)

    _complete_lesson(client, learner, lesson1, "TEMPTESTC1")
    client.post(reverse("hybrid-practise-again", args=[lesson1.pk]))
    _complete_lesson(client, learner, lesson1, "TEMPTESTC2")

    assert publishing.learner_edition_progress(enrolment, version) == (1, 2)
    assert services.module_complete(enrolment, module) is False

    _complete_lesson(client, learner, lesson2, "TEMPTESTC3")
    assert publishing.learner_edition_progress(enrolment, version) == (2, 2)
    assert services.module_complete(enrolment, module) is True


@pytest.mark.django_db
def test_a_completed_lesson_stays_open_and_offers_practise_again(client, db):
    _, version, _, _, lessons = _published_edition("reopen", lesson_count=2)
    learner = _learner_enrolled(db, "reopener", version)
    lesson1, _lesson2 = lessons
    _complete_lesson(client, learner, lesson1, "TEMPTESTO1")

    reopened = client.get(reverse("hybrid-workspace", args=[lesson1.pk]))
    assert reopened.status_code == 200
    assert "Practise again" in reopened.content.decode()

    html = client.get(reverse("hybrid-roadmap")).content.decode()
    assert reverse("hybrid-workspace", args=[lesson1.pk]) in html


@pytest.mark.django_db
def test_practise_again_is_refused_for_journey_bound_lessons(client, db):
    """Journey steps live in the journey's own lifecycle; the repeat action
    must refuse them instead of opening a second legacy attempt."""
    from hybrid import journey_services
    from hybrid.models import HybridCourse, PracticalJourney, PracticalStep

    _, version, _, _, lessons = _published_edition("jbound", lesson_count=1)
    learner = _learner_enrolled(db, "journeybound", version)
    lesson = lessons[0]
    journey = PracticalJourney.objects.create(
        programme_version=version,
        course=HybridCourse.objects.get(programme_version=version),
        code="jb", title="Bound workflow",
    )
    step = PracticalStep.objects.get(lesson=lesson)
    version.status = ProgrammeVersion.Status.DRAFT
    version.save(update_fields=("status",))
    journey_services.assign_step(journey, step)
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))

    response = client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    assert response.status_code == 302  # PermissionDenied → portal redirect
    assert LessonAttempt.objects.filter(enrolment__student=learner, lesson=lesson).count() == 0


@pytest.mark.django_db
def test_a_repeat_attempt_is_practice_and_the_first_pass_is_not(client, db):
    _, version, _, _, lessons = _published_edition("pmode", lesson_count=1)
    learner = _learner_enrolled(db, "practiser", version)
    lesson = lessons[0]

    client.force_login(learner)
    _ack_theory(client, learner, lesson)
    first_html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert '"practice": false' in first_html
    first = LessonAttempt.objects.filter(enrolment__student=learner, lesson=lesson).order_by("started_at").first()
    assert services.is_practice_attempt(first) is False

    _complete_lesson(client, learner, lesson, "TEMPTESTP1")
    client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    second = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()
    assert services.is_practice_attempt(second) is True

    second_html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert '"practice": true' in second_html


@pytest.mark.django_db
def test_a_practice_attempt_is_gated_exactly_like_the_first_pass(client, db):
    """Practice mode is the first-pass experience replayed on a fresh slate:
    the guided sequence gates every attempt, so an uncompleted step refuses
    advancement and tells the learner plainly. The repeat only differs in
    what the system remembers — earlier attempts stay preserved."""
    _, version, _, _, lessons = _published_edition("pwalk", lesson_count=1)
    learner = _learner_enrolled(db, "walker", version)
    lesson = lessons[0]

    client.force_login(learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    first = LessonAttempt.objects.filter(enrolment__student=learner, lesson=lesson).order_by("started_at").first()
    if verification.step_requires_verification(lesson.practical_steps.first()):
        refused = client.post(reverse("hybrid-step-advance", args=[first.pk, 0]))
        assert refused.status_code == 403
        assert refused.json()["allowed"] is False

    _complete_lesson(client, learner, lesson, "TEMPTESTP2")
    client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    second = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()

    client.post(reverse("hybrid-step-open", args=[second.pk, 0]))
    gated = client.post(reverse("hybrid-step-advance", args=[second.pk, 0]))
    assert gated.status_code == 403
    assert gated.json()["allowed"] is False


@pytest.mark.django_db
def test_a_practice_run_saves_scoped_records_and_throws_them_away_on_completion(client, db):
    """The retry loop end to end through the real save route: a practice
    browser's saves become PRCTUCR scratch scoped to the attempt — invisible
    to every ordinary listing, absent from the creation ledger — the stage
    check verifies them, and completion throws the whole set away while the
    verified history and the earlier attempt stay put."""
    _, version, _, _, lessons = _published_edition("scratch", lesson_count=1)
    learner = _learner_enrolled(db, "scratcher", version)
    lesson = lessons[0]
    first = _complete_lesson(client, learner, lesson, "TEMPTESTS1")

    client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    second = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()
    _simulator_access(client, learner)
    # The redirect lands on the workspace, whose GET binds the browser to the
    # open practice run.
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    assert client.session["hybrid_practice_attempt_id"] == str(second.pk)

    body = _ucr_body()
    body["exporter"]["name"] = "ACME Trading"  # the step condition pins this value
    saved = client.post(reverse("ucr-save"), body, content_type="application/json")
    assert saved.status_code == 200
    data = saved.json()
    assert data["temp_no"].startswith("PRCTUCR")
    record = UcrDeclaration.all_objects.get(pk=data["id"])
    assert record.practice_attempt_id == second.pk
    # Invisible to every ordinary surface; never learner evidence.
    assert UcrDeclaration.objects.filter(pk=record.pk).exists() is False

    client.post(reverse("hybrid-step-open", args=[second.pk, 0]))
    assert client.post(reverse("hybrid-step-check", args=[second.pk, 0])).json()["passed"] is True
    assert client.post(reverse("hybrid-acknowledge-theory", args=[second.pk])).json()["lesson_complete"] is True

    # Completion threw the scratch away; the run's history and the earlier
    # attempt stay preserved; the binding is gone.
    assert UcrDeclaration.all_objects.filter(practice_attempt=second).count() == 0
    assert "hybrid_practice_attempt_id" not in client.session
    second.refresh_from_db()
    assert second.completed_at is not None
    assert StepEvent.objects.filter(attempt=second, kind=StepEvent.Kind.VERIFIED).exists()
    first.refresh_from_db()
    assert first.completed_at is not None


@pytest.mark.django_db
def test_a_practice_submit_issues_a_final_number_that_is_also_thrown_away(client, db):
    _, version, _, _, lessons = _published_edition("psubmit", lesson_count=1)
    learner = _learner_enrolled(db, "submitter", version)
    lesson = lessons[0]
    _complete_lesson(client, learner, lesson, "TEMPTESTS2")

    client.post(reverse("hybrid-practise-again", args=[lesson.pk]))
    second = LessonAttempt.objects.filter(
        enrolment__student=learner, lesson=lesson, completed_at__isnull=True,
    ).order_by("-started_at").first()
    _simulator_access(client, learner)
    client.get(reverse("hybrid-workspace", args=[lesson.pk]))
    _ack_theory(client, learner, lesson)
    body = _ucr_body()
    saved = client.post(reverse("ucr-save"), body, content_type="application/json").json()
    body["draft_id"] = saved["id"]
    submitted = client.post(reverse("ucr-submit"), body, content_type="application/json").json()
    assert submitted["ucr_no"].startswith("KGHTESTUCR")

    # The redirect target resolves read-only for the run's own record.
    assert client.get(submitted["detail_url"]).status_code == 200

    _complete_lesson(client, learner, lesson, "TEMPTESTS3")
    # The run completed: its scratch — draft and final number alike — is gone.
    assert UcrDeclaration.all_objects.filter(practice_attempt=second).count() == 0
    assert client.get(submitted["detail_url"]).status_code == 404


@pytest.mark.django_db
def test_a_stale_practice_binding_never_writes_an_ordinary_row(client, db):
    """A browser that believes it is practising with a dead binding is
    refused — never silently written as an ordinary learner record."""
    _, version, _, _, lessons = _published_edition("pstale", lesson_count=1)
    learner = _learner_enrolled(db, "staler", version)
    lesson = lessons[0]
    _complete_lesson(client, learner, lesson, "TEMPTESTS4")

    _simulator_access(client, learner)
    from scenarios.practice_ucr import PRACTICE_ACTIVE_KEY

    session = client.session
    session[PRACTICE_ACTIVE_KEY] = "00000000-0000-0000-0000-000000000000"
    session.save()

    response = client.post(reverse("ucr-save"), _ucr_body(), content_type="application/json")
    assert response.status_code == 409
    assert response.json()["code"] == "practice_not_active"
    # The refused write produced no ordinary record (the first attempt's own
    # TEMPTESTS4 record is the only ordinary row the learner has).
    assert UcrDeclaration.objects.filter(owner=learner, temp_no__startswith="TEMPUCR").count() == 0
