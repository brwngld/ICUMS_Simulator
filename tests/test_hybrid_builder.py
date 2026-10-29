"""Stage 3 smoke: the instructor builder authors the same rows the student
workspace renders, inside draft editions only."""
import pytest
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.urls import reverse

from accounts.models import User
from hybrid.models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyStep,
    PracticalJourney,
    PracticalStep,
    VerificationCondition,
)
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


def _user(db, username, group_name):
    user = User.objects.create_user(username=username, email=f"{username}@example.test", password="test-password")
    user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    DisclaimerAcceptance.objects.get_or_create(
        user=user,
        disclaimer=DisclaimerVersion.objects.get_or_create(
            version=1, defaults={"title": "Notice", "body": "Training only.", "is_current": True}
        )[0],
    )
    return user


def _instructor(db, username="builder"):
    return _user(db, username, "Instructor")


def _student(db, username="learner"):
    return _user(db, username, "Student")


def _hybrid_programme(code="build-prog"):
    programme = Programme.objects.create(name=f"Programme {code}", code=code, learning_track=Programme.Track.HYBRID)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    return programme, version


def _course(version, code="course-one"):
    return HybridCourse.objects.create(
        programme_version=version, code=code, title=f"{code} title", order=1,
    )


def _module(course, code="module-one"):
    return HybridModule.objects.create(course=course, code=code, title=f"{code} title", order=1)


def _lesson(module, slug="lesson-one"):
    return HybridLesson.objects.create(module=module, slug=slug, title=f"{slug} title", order=1)


def _lesson_post(title="Renamed lesson", summary="Fresh summary", theory_body="<p>Body copy</p>",
                 stage="details"):
    # The theory form keeps the "form" prefix on purpose (the shared
    # rich-text editor binds textarea ids like id_form-body).
    return {
        "action": "save_lesson", "active_tab": stage,
        "title": title, "summary": summary, "form-body": theory_body,
    }


def _card_post(step, title=None, instruction="Do the thing.", outcome="The thing is done.",
               hint="Look again.", screen="single-window-create-ucr"):
    """One activity card's own payload: that step's fields, prefixed with its id."""
    prefix = f"step-{step.pk}-"
    return {
        "action": "save_activity", "step_id": str(step.pk), "active_tab": "activities",
        f"{prefix}title": step.title if title is None else title,
        f"{prefix}instruction": instruction,
        f"{prefix}outcome": outcome,
        f"{prefix}hint": hint,
        f"{prefix}screen": screen,
    }


def _check_post(condition, rows=(), record_status="ucr:draft", kind="saved_record"):
    """The check block inside a card: its type, the record-and-status pair and
    one select/value pair per saved expectation, all under the check's prefix."""
    prefix = f"cond-{condition.pk}-"
    data = {
        f"{prefix}kind": kind,
        f"{prefix}record_status": record_status,
        f"{prefix}value_rows": str(len(rows)),
    }
    for index, (column, value) in enumerate(rows):
        data[f"{prefix}check_{index}"] = column
        data[f"{prefix}value_{index}"] = value
    return data


# --- Access -------------------------------------------------------------------


@pytest.mark.django_db
def test_only_instructors_open_the_builder(client, db):
    _student(db, "not-staff")
    client.force_login(User.objects.get(username="not-staff"))
    response = client.get(reverse("hybrid-builder"))
    assert response.status_code == 302
    assert response.url == reverse("dashboard")


@pytest.mark.django_db
def test_anonymous_visitors_are_sent_to_login(client, db):
    response = client.get(reverse("hybrid-builder"))
    assert response.status_code == 302
    assert reverse("login") in response.headers["location"]


@pytest.mark.django_db
def test_the_builder_lists_hybrid_programmes_and_their_editions(client, db):
    instructor = _instructor(db)
    programme, version = _hybrid_programme("listed")
    client.force_login(instructor)
    html = client.get(reverse("hybrid-builder")).content.decode()
    assert programme.name in html
    assert "Draft edition" in html


# --- Programme authoring -------------------------------------------------------


@pytest.mark.django_db
def test_the_builder_creates_a_hybrid_programme_with_a_draft_edition(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Coastal clearance", "code": "coastal-clearance"},
    )
    assert response.status_code == 302
    programme = Programme.objects.get(code="coastal-clearance")
    assert programme.learning_track == Programme.Track.HYBRID
    assert programme.is_active is True
    version = programme.versions.get()
    assert (version.version, version.status) == (1, ProgrammeVersion.Status.DRAFT)


@pytest.mark.django_db
def test_a_programme_with_a_taken_code_is_rejected_without_creating(client, db):
    instructor = _instructor(db)
    programme, _ = _hybrid_programme("taken")
    client.force_login(instructor)
    response = client.post(
        reverse("hybrid-builder"),
        {"action": "create_programme", "name": "Lookalike", "code": programme.code},
    )
    assert response.status_code == 400
    assert not Programme.objects.filter(name="Lookalike").exists()


@pytest.mark.django_db
def test_a_programme_post_does_not_validate_the_course_form(client, db):
    """The two create cards are independent: a bare programme POST must not come
    back complaining about the course title it was never meant to carry."""
    _instructor(db)
    client.force_login(User.objects.get(username="builder"))
    response = client.post(reverse("hybrid-builder"), {"action": "create_programme", "name": "", "code": ""})
    assert response.status_code == 400
    html = response.content.decode()
    assert "This field is required." in html
    assert html.count("This field is required.") == 2  # programme name and code, nothing else


@pytest.mark.django_db
def test_instructor_navigation_offers_only_the_two_builders(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    html = client.get(reverse("dashboard")).content.decode()
    assert "Theory builder" in html
    assert "Theory & Practical builder" in html
    assert "Practical/Theory builder" not in html


@pytest.mark.django_db
def test_the_instructor_dashboard_opens_the_hybrid_builder(client, db):
    instructor = _instructor(db)
    client.force_login(instructor)
    html = client.get(reverse("instructor-dashboard")).content.decode()
    assert reverse("hybrid-builder") in html
    assert "path=combined" not in html


# --- Course and module authoring -----------------------------------------------


@pytest.mark.django_db
def test_creating_a_course_opens_or_reuses_a_draft_edition(client, db):
    instructor = _instructor(db)
    programme, version = _hybrid_programme("drafts")
    client.force_login(instructor)
    response = client.post(reverse("hybrid-builder"), {"programme": programme.pk, "title": "Cargo basics", "description": ""})
    assert response.status_code == 302
    course = HybridCourse.objects.get(title="Cargo basics")
    assert course.programme_version == version
    assert course.programme_version.status == ProgrammeVersion.Status.DRAFT


@pytest.mark.django_db
def test_a_course_cannot_be_created_on_a_theory_programme(client, db):
    instructor = _instructor(db)
    theory = Programme.objects.create(name="Theory only", code="theory-only", learning_track=Programme.Track.THEORY)
    client.force_login(instructor)
    response = client.post(reverse("hybrid-builder"), {"programme": theory.pk, "title": "Smuggled course", "description": ""})
    assert response.status_code == 400
    assert not HybridCourse.objects.filter(title="Smuggled course").exists()


@pytest.mark.django_db
def test_published_editions_are_not_editable(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("locked")
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.save(update_fields=("status",))
    course = _course(version)
    module = _module(course)
    lesson = _lesson(module)
    client.force_login(instructor)
    assert client.get(reverse("hybrid-course-edit", args=[course.pk])).status_code == 404
    assert client.get(reverse("hybrid-module-edit", args=[module.pk])).status_code == 404
    assert client.get(reverse("hybrid-lesson-edit", args=[lesson.pk])).status_code == 404


@pytest.mark.django_db
def test_modules_and_lessons_are_created_under_the_draft(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("crud")
    course = _course(version)
    client.force_login(instructor)

    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "create_module", "title": "Paperwork", "description": ""})
    module = HybridModule.objects.get(course=course, title="Paperwork")

    response = client.post(
        reverse("hybrid-module-edit", args=[module.pk]),
        {"action": "create_lesson", "title": "First journey", "summary": "About the journey."},
    )
    assert response.status_code == 302
    assert reverse("hybrid-lesson-edit", args=[HybridLesson.objects.get(module=module, title="First journey").pk]) in response.url
    lesson = HybridLesson.objects.get(module=module, title="First journey")
    assert lesson.slug == "first-journey"


@pytest.mark.django_db
def test_a_module_with_lessons_cannot_be_silently_deleted(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("protect")
    course = _course(version)
    module = _module(course)
    _lesson(module)
    client.force_login(instructor)
    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "delete_module", "module_id": module.pk})
    assert HybridModule.objects.filter(pk=module.pk).exists()


# --- The four-stage lesson editor -------------------------------------------------


@pytest.mark.django_db
def test_the_lesson_stage_saves_details_and_theory(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("editor")
    lesson = _lesson(_module(_course(version)))
    PracticalStep.objects.create(lesson=lesson, key="open", title="Old step", order=1, screen="single-window-overview")
    client.force_login(instructor)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        _lesson_post(title="Renamed lesson", summary="Fresh summary"),
    )
    assert response.status_code == 302

    lesson.refresh_from_db()
    assert lesson.title == "Renamed lesson"
    assert lesson.summary == "Fresh summary"
    assert "<p>Body copy</p>" in lesson.theory


@pytest.mark.django_db
def test_an_activity_card_saves_its_step(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("card-save")
    lesson = _lesson(_module(_course(version)))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Old step", order=1, screen="single-window-overview")
    client.force_login(instructor)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        _card_post(step, title="Renamed step"),
    )
    assert response.status_code == 302

    step.refresh_from_db()
    assert (step.title, step.instruction, step.outcome, step.screen) == (
        "Renamed step", "Do the thing.", "The thing is done.", "single-window-create-ucr",
    )


@pytest.mark.django_db
def test_saving_one_activity_leaves_its_siblings_alone(client, db):
    """The card is the unit of saving: the lesson's other activities keep their
    own text, keys and order whatever the posted card says."""
    instructor = _instructor(db)
    _, version = _hybrid_programme("card-siblings")
    lesson = _lesson(_module(_course(version)))
    first = PracticalStep.objects.create(
        lesson=lesson, key="first", title="First activity", instruction="Type one.",
        outcome="One done.", screen="single-window-overview", order=1,
    )
    second = PracticalStep.objects.create(lesson=lesson, key="second", title="Second activity", order=2)
    client.force_login(instructor)

    client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), _card_post(second, title="Edited second"))

    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.title, first.key, first.order, first.screen) == ("First activity", "first", 1, "single-window-overview")
    assert (second.title, second.key, second.order) == ("Edited second", "second", 2)


@pytest.mark.django_db
def test_a_step_screen_is_limited_to_the_approved_registry(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("registry")
    lesson = _lesson(_module(_course(version)))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Open", order=1, screen="single-window-overview")
    client.force_login(instructor)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        _card_post(step, screen="javascript:alert(1)"),
    )
    assert response.status_code == 400
    step.refresh_from_db()
    assert step.screen == "single-window-overview"


@pytest.mark.django_db
def test_steps_can_be_added_moved_and_removed(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("steps")
    lesson = _lesson(_module(_course(version)))
    first = PracticalStep.objects.create(lesson=lesson, key="first", title="First", order=1)
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[lesson.pk])

    client.post(editor, {"action": "add_step"})
    second = PracticalStep.objects.get(lesson=lesson, title="New activity")
    assert second.order == 2 and second.key.startswith("new-activity")

    client.post(editor, {"action": "move_step", "step_id": second.pk, "direction": "up"})
    first.refresh_from_db(); second.refresh_from_db()
    assert (first.order, second.order) == (2, 1)

    client.post(editor, {"action": "delete_step", "step_id": second.pk})
    assert not PracticalStep.objects.filter(pk=second.pk).exists()
    first.refresh_from_db()
    assert first.order == 1


@pytest.mark.django_db
def test_an_activity_in_a_journey_is_not_removed_from_the_lesson(client, db):
    """A journey step is protected, so removing it here must say so instead of
    taking the instructor down with a server error."""
    instructor = _instructor(db)
    _, version = _hybrid_programme("step-protected")
    course = _course(version)
    lesson = _lesson(_module(course))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Open", order=1)
    journey = PracticalJourney.objects.create(programme_version=version, course=course, code="j1", title="Journey one")
    JourneyStep.objects.create(journey=journey, step=step, journey_order=1)
    client.force_login(instructor)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        {"action": "delete_step", "step_id": step.pk},
        follow=True,
    )
    assert response.status_code == 200
    assert PracticalStep.objects.filter(pk=step.pk).exists()
    assert "belongs to a practical journey" in " ".join(m.message for m in response.context["messages"])


@pytest.mark.django_db
def test_the_review_tab_reports_what_is_missing(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("review")
    lesson = _lesson(_module(_course(version)))
    client.force_login(instructor)
    response = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk]))
    issues = " ".join(response.context["issues"])
    assert "No theory reading yet" in issues
    assert "No practical steps yet" in issues


# --- Authoring defects ------------------------------------------------------------


@pytest.mark.django_db
def test_the_module_page_describes_theory_instead_of_counting_deleted_blocks(client, db):
    """The block model is long gone; the row still has to say something true."""
    instructor = _instructor(db)
    _, version = _hybrid_programme("module-copy")
    module = _module(_course(version))
    written = _lesson(module, slug="written")
    written.theory = "<p>Reading</p>"
    written.save(update_fields=("theory",))
    _lesson(module, slug="blank")
    client.force_login(instructor)

    html = client.get(reverse("hybrid-module-edit", args=[module.pk])).content.decode()
    assert "theory block" not in html
    assert "theory written" in html
    assert "theory not written yet" in html


@pytest.mark.django_db
def test_a_step_has_one_simulator_screen_control(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("one-screen")
    lesson = _lesson(_module(_course(version)))
    step = PracticalStep.objects.create(lesson=lesson, key="open", title="Open", order=1)
    client.force_login(instructor)

    html = client.get(reverse("hybrid-lesson-edit", args=[lesson.pk])).content.decode()
    assert html.count(f'name="step-{step.pk}-screen"') == 1


@pytest.mark.django_db
def test_an_activity_card_carries_its_own_checks(client, db):
    """Stage 3 is one integrated card: the activity's text, its screen and the
    checks hanging off it are all on the same page, in the same form."""
    instructor = _instructor(db)
    step = _condition_step(db, "card-checks")
    client.force_login(instructor)
    condition = _add_condition(client, step)

    html = client.get(f"{reverse('hybrid-lesson-edit', args=[step.lesson.pk])}?tab=activities").content.decode()
    assert f'name="step-{step.pk}-instruction"' in html
    assert f'name="cond-{condition.pk}-record_status"' in html


@pytest.mark.django_db
def test_a_new_check_is_created_as_the_type_the_instructor_chose(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "check-kinds")
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[step.lesson.pk])

    client.post(editor, {"action": "add_condition", "step_id": step.pk, "kind": "saved_record"})
    client.post(editor, {"action": "add_condition", "step_id": step.pk, "kind": "screen_opened"})

    kinds = list(VerificationCondition.objects.filter(step=step).order_by("order").values_list("kind", flat=True))
    assert kinds == [VerificationCondition.Kind.SAVED_RECORD, VerificationCondition.Kind.SCREEN_OPENED]


@pytest.mark.django_db
def test_an_unrecognised_check_type_creates_no_row(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "bad-check-kind")
    client.force_login(instructor)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        {"action": "add_condition", "step_id": step.pk, "kind": "manifest"},
    )
    assert response.status_code == 302
    assert not VerificationCondition.objects.filter(step=step).exists()


# --- Verification conditions -----------------------------------------------------


def _condition_step(db, code="conditions"):
    """A draft lesson's step with no conditions of its own yet."""
    _, version = _hybrid_programme(code)
    lesson = _lesson(_module(_course(version)))
    return PracticalStep.objects.create(
        lesson=lesson, key="check", title="File the declaration", order=1, screen="single-window-create-ucr",
    )


def _add_condition(client, step, kind="saved_record"):
    client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        {"action": "add_condition", "step_id": step.pk, "kind": kind},
    )
    return VerificationCondition.objects.filter(step=step).order_by("-order").first()


@pytest.mark.django_db
def test_a_saved_value_is_chosen_from_the_record_not_written_as_json(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-editor")
    client.force_login(instructor)
    condition = _add_condition(client, step)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(step, title="File the declaration") | _check_post(
            condition, [("ucr:exporter_name", "ACME Trading"), ("", "")],
        ),
    )
    assert response.status_code == 302
    condition.refresh_from_db()
    assert condition.expected_fields == {"exporter_name": "ACME Trading"}

    html = client.get(f"{reverse('hybrid-lesson-edit', args=[step.lesson.pk])}?tab=activities").content.decode()
    assert 'name="expected_fields"' not in html
    assert 'value="ucr:exporter_name" selected' in html
    assert "ACME Trading" in html


@pytest.mark.django_db
def test_a_check_and_its_activity_are_configured_in_one_save(client, db):
    """Batch 3's core flow: the instructor types the instruction, picks the
    screen and pins the saved record without leaving the card."""
    instructor = _instructor(db)
    step = _condition_step(db, "cond-together")
    client.force_login(instructor)
    condition = _add_condition(client, step)

    response = client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(
            step,
            instruction="Create a UCR whose exporter is ACME Trading, then save the draft.",
            outcome="A saved draft naming your exporter.",
            screen="single-window-create-ucr",
        ) | _check_post(condition, [("ucr:exporter_name", "ACME Trading")]),
    )
    assert response.status_code == 302

    step.refresh_from_db()
    condition.refresh_from_db()
    assert step.instruction == "Create a UCR whose exporter is ACME Trading, then save the draft."
    assert (condition.kind, condition.record_kind, condition.required_status) == (
        VerificationCondition.Kind.SAVED_RECORD, "ucr", "draft",
    )
    assert condition.expected_fields == {"exporter_name": "ACME Trading"}


@pytest.mark.django_db
def test_an_unsupported_record_status_is_refused_and_changes_nothing(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-bad-status")
    client.force_login(instructor)
    condition = _add_condition(client, step)
    data = _card_post(step) | _check_post(condition, [("ucr:exporter_name", "ACME Trading")])
    client.post(reverse("hybrid-lesson-edit", args=[step.lesson.pk]), data)
    condition.refresh_from_db()
    assert condition.required_status == "draft"

    response = client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(step, title="Rewritten anyway") | _check_post(
            condition, [("ucr:exporter_name", "ACME Trading")], record_status="ucr:nonexistent",
        ),
    )
    assert response.status_code == 400
    condition.refresh_from_db()
    step.refresh_from_db()
    assert condition.required_status == "draft"
    # Nothing in the refused card is written, not even the activity's own text.
    assert step.title == "File the declaration"


@pytest.mark.django_db
def test_a_card_leaves_a_check_it_was_never_shown_alone(client, db):
    """A page built before a check was added cannot rewrite or refuse it: the
    check the POST never carried stays exactly as it is."""
    instructor = _instructor(db)
    step = _condition_step(db, "cond-stale")
    client.force_login(instructor)
    shown = _add_condition(client, step)
    data = _card_post(step, title="Edited from the old page") | _check_post(shown, [("ucr:exporter_name", "ACME Trading")])
    hidden = _add_condition(client, step, kind="screen_opened")

    client.post(reverse("hybrid-lesson-edit", args=[step.lesson.pk]), data)

    hidden.refresh_from_db()
    assert hidden.kind == VerificationCondition.Kind.SCREEN_OPENED
    assert hidden.expected_fields == {}
    shown.refresh_from_db()
    assert shown.expected_fields == {"exporter_name": "ACME Trading"}


@pytest.mark.django_db
def test_a_number_and_a_flag_are_stored_as_the_record_holds_them(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-types")
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[step.lesson.pk])

    flag = _add_condition(client, step)
    number = _add_condition(client, step)
    client.post(
        editor,
        _card_post(step)
        | _check_post(flag, [("ucr:show_provider", "yes")])
        | _check_post(number, [], record_status="mda:DR"),
    )
    flag.refresh_from_db()
    assert flag.expected_fields == {"show_provider": True}

    client.post(
        editor,
        _card_post(step)
        | _check_post(flag, [])
        | _check_post(number, [("mda:monthly_sequence", "7")], record_status="mda:DR"),
    )
    number.refresh_from_db()
    assert number.expected_fields == {"monthly_sequence": 7}


@pytest.mark.django_db
def test_a_flag_answered_with_prose_is_refused(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-flag-word")
    client.force_login(instructor)
    condition = _add_condition(client, step)
    client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(step) | _check_post(condition, [("ucr:show_provider", "probably")]),
    )
    condition.refresh_from_db()
    assert condition.expected_fields == {}


@pytest.mark.django_db
def test_a_value_belongs_to_the_record_the_condition_checks(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-mismatch")
    client.force_login(instructor)
    condition = _add_condition(client, step)
    client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(step) | _check_post(condition, [("boe:declaration_no", "BOE-1")]),
    )
    condition.refresh_from_db()
    assert (condition.record_kind, condition.expected_fields) == ("", {})


@pytest.mark.django_db
def test_clearing_a_row_stops_checking_that_saved_value(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-clear")
    client.force_login(instructor)
    editor = reverse("hybrid-lesson-edit", args=[step.lesson.pk])
    condition = _add_condition(client, step)
    client.post(editor, _card_post(step) | _check_post(condition, [("ucr:exporter_name", "ACME Trading")]))
    condition.refresh_from_db()
    assert condition.expected_fields == {"exporter_name": "ACME Trading"}

    client.post(editor, _card_post(step) | _check_post(condition, [("", "")]))
    condition.refresh_from_db()
    assert condition.expected_fields == {}


@pytest.mark.django_db
def test_a_navigation_check_stays_a_navigation_check(client, db):
    """Saving the card re-posts the check exactly as it was rendered, so the
    activity text can change without a check quietly becoming a different type."""
    instructor = _instructor(db)
    step = _condition_step(db, "cond-kind-stable")
    client.force_login(instructor)
    condition = _add_condition(client, step, kind="screen_opened")

    client.post(
        reverse("hybrid-lesson-edit", args=[step.lesson.pk]),
        _card_post(step, title="Renamed activity") | _check_post(
            condition, [], kind=VerificationCondition.Kind.SCREEN_OPENED,
        ),
    )

    condition.refresh_from_db()
    step.refresh_from_db()
    assert condition.kind == VerificationCondition.Kind.SCREEN_OPENED
    assert step.title == "Renamed activity"


@pytest.mark.django_db
def test_columns_that_cannot_be_pinned_exactly_are_not_offered(client, db):
    instructor = _instructor(db)
    step = _condition_step(db, "cond-columns")
    client.force_login(instructor)
    _add_condition(client, step)
    html = client.get(f"{reverse('hybrid-lesson-edit', args=[step.lesson.pk])}?tab=activities").content.decode()
    for column in ("ucr:documents", "consignment:shipment_date", "consignment:exchange_rate", "boe:form_data"):
        assert f'value="{column}"' not in html


# --- Preview --------------------------------------------------------------------


@pytest.mark.django_db
def test_the_preview_renders_draft_content_for_instructors_only(client, db):
    instructor = _instructor(db)
    _, version = _hybrid_programme("preview")
    lesson = _lesson(_module(_course(version)))
    PracticalStep.objects.create(
        lesson=lesson, key="open", title="Open the overview", order=1,
        instruction="Open it.", screen="single-window-overview",
    )
    client.force_login(instructor)
    html = client.get(reverse("hybrid-lesson-preview", args=[lesson.pk])).content.decode()
    assert lesson.title in html
    assert "Open the overview" in html
    assert "Instructor preview" in html

    student = _student(db, "peeking")
    client.force_login(student)
    assert client.get(reverse("hybrid-lesson-preview", args=[lesson.pk])).status_code == 302


# --- The milestone: builder-authored content drives the student workspace --------


@pytest.mark.django_db
def test_an_instructor_authored_lesson_renders_in_the_student_workspace(client, db):
    """The whole point of Stage 3: an instructor authors a lesson through the
    builder alone, and the Stage 2 workspace renders it with no code changes.
    Publishing the edition is Stage 4, so the test flips the flags directly."""
    instructor = _instructor(db)
    programme, version = _hybrid_programme("milestone")
    client.force_login(instructor)

    client.post(reverse("hybrid-builder"), {"programme": programme.pk, "title": "Milestone course", "description": ""})
    course = HybridCourse.objects.get(title="Milestone course")
    client.post(reverse("hybrid-course-edit", args=[course.pk]), {"action": "create_module", "title": "Milestone module", "description": ""})
    module = HybridModule.objects.get(course=course)
    client.post(reverse("hybrid-module-edit", args=[module.pk]), {"action": "create_lesson", "title": "Milestone journey", "summary": ""})
    lesson = HybridLesson.objects.get(module=module)

    client.post(reverse("hybrid-lesson-edit", args=[lesson.pk]), {"action": "add_step"})
    step = PracticalStep.objects.get(lesson=lesson)

    client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        _lesson_post(
            title="Milestone journey",
            summary="Authored entirely in the builder.",
            theory_body="<p>Authored theory.</p>",
            stage="activities",
        ),
    )
    client.post(
        reverse("hybrid-lesson-edit", args=[lesson.pk]),
        _card_post(step, title="Open the single window"),
    )

    # Stand-in for the Stage 4 publication sweep: publish the draft edition.
    ProgrammeVersion.objects.filter(pk=version.pk).update(status=ProgrammeVersion.Status.PUBLISHED)
    HybridCourse.objects.filter(pk=course.pk).update(is_published=True)
    HybridModule.objects.filter(pk=module.pk).update(is_published=True)
    HybridLesson.objects.filter(pk=lesson.pk).update(is_published=True)

    student = _student(db, "milestone-learner")
    Enrolment.objects.create(student=student, programme_version=ProgrammeVersion.objects.get(pk=version.pk))
    client.force_login(student)

    html = client.get(reverse("hybrid-workspace", args=[lesson.pk])).content.decode()
    assert "Milestone journey" in html
    assert "Authored entirely in the builder." in html
    assert "Authored theory." in html
    assert "Open the single window" in html
    assert reverse("single-window-create-ucr") in html
