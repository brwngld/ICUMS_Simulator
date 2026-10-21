"""The Integrated Practice Desk spike: theory and guide beside the real simulator.

This is a prototype behind its own url, so these tests hold the two things that
make it safe to keep around while the rest of the app is untouched:

* framing is opened only for the simulator's own pages, only when the browser
  says the document is being loaded as a frame, and only to the same origin —
  the global ``DENY`` keeps guarding every other page and every other request;
* the desk shows the learner's live guided-practical step and their own lesson
  reading, and it never writes: no progress row, no completion, no attempt.
"""

from urllib.parse import urlencode, urlsplit

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import Programme, ProgrammeVersion
from progress.models import LessonProgress
from scenarios.desk import _playground_pages
from scenarios.models import ScenarioAttempt

from tests.test_guide_panel import _oriented, _scenario, _three_step
from tests.test_guided_simulator_binding import login_with_simulator_access


@pytest.fixture
def desk_learner(db):
    """A learner on a guided practical whose first step opens the Create UCR page."""
    user = User.objects.create_user(username="desk-student", email="desk@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    enrolment = _oriented(user, "desk")
    version = _scenario()
    _three_step(version)
    from scenarios.services import start_or_resume_attempt

    attempt, _created = start_or_resume_attempt(enrolment, version)
    module = Module.objects.create(
        programme_version=enrolment.programme_version, code="desk-m1", title="Single Window parties", is_published=True
    )
    lesson = Lesson.objects.create(
        module=module,
        slug="who-files-what",
        title="Who files what in the Single Window",
        summary="Three roles meet on one declaration.",
        objectives="Name the declarant.\nName the service provider.",
        is_published=True,
    )
    ContentBlock.objects.create(
        lesson=lesson, kind="text", heading="Why the country code matters",
        body="<p>A two-letter Common Code drives regime validation downstream.</p>", order=1,
    )
    return type("Desk", (), {
        "user": user,
        "enrolment": enrolment,
        "attempt": attempt,
        "module": module,
        "lesson": lesson,
        "desk_url": "{}?{}".format(reverse("practice-desk"), urlencode({"lesson": f"{module.code}/{lesson.slug}"})),
    })()


@pytest.fixture
def signed_in(client, desk_learner):
    login_with_simulator_access(client, desk_learner.user)
    return desk_learner


def _frame_source(body):
    start = body.index('data-desk-frame')
    return body[start:body.index('>', start)]


# --- who may be framed -------------------------------------------------------


@pytest.mark.django_db
def test_a_simulator_page_lets_the_desk_frame_it(client, signed_in):
    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")
    assert response["X-Frame-Options"] == "SAMEORIGIN"


@pytest.mark.django_db
def test_the_same_simulator_page_refuses_a_frame_it_was_not_asked_for(client, signed_in):
    assert client.get(reverse("single-window-create-ucr"))["X-Frame-Options"] == "DENY"


@pytest.mark.django_db
def test_another_kind_of_page_stays_unframeable(client, signed_in):
    response = client.get(reverse("dashboard"), HTTP_SEC_FETCH_DEST="iframe")
    assert response["X-Frame-Options"] == "DENY"


@pytest.mark.django_db
def test_a_refused_simulator_page_offers_no_frame(client, db):
    """The access gate still wins: a login redirect is never made frameable."""
    outsider = User.objects.create_user(username="desk-outsider", email="outsider@example.test", password="test-password")
    outsider.groups.add(Group.objects.get(name="Student"))
    client.force_login(outsider)
    response = client.get(reverse("single-window-create-ucr"), HTTP_SEC_FETCH_DEST="iframe")
    assert response.status_code == 302
    assert response["X-Frame-Options"] == "DENY"


# --- what the desk shows -------------------------------------------------------


@pytest.mark.django_db
def test_the_desk_pairs_the_live_step_with_the_page_it_belongs_to(client, signed_in):
    body = client.get(signed_in.desk_url).content.decode()
    assert "data-desk-guide" in body
    assert "Step 1 of 3" in body
    assert "Create and submit the importer UCR declaration" in body
    assert "Check my work" in body


@pytest.mark.django_db
def test_the_desk_frame_is_the_real_simulator_page(client, signed_in):
    """The right pane is the playground's own url, so an edit there shows here."""
    assert f'src="{reverse("single-window-create-ucr")}"' in _frame_source(client.get(signed_in.desk_url).content.decode())


@pytest.mark.django_db
def test_the_desk_opens_the_lesson_where_the_learner_stands(client, signed_in):
    body = client.get(signed_in.desk_url).content.decode()
    assert "Who files what in the Single Window" in body
    assert "Three roles meet on one declaration." in body
    assert "Name the service provider." in body
    assert not LessonProgress.objects.filter(enrolment=signed_in.enrolment, lesson=signed_in.lesson).exists()


@pytest.mark.django_db
def test_the_desk_reads_a_section_of_the_named_lesson(client, signed_in):
    body = client.get(f"{signed_in.desk_url}&section=concepts").content.decode()
    assert "A two-letter Common Code drives regime validation downstream." in body
    assert "Why the country code matters" in body
    assert not LessonProgress.objects.filter(enrolment=signed_in.enrolment, lesson=signed_in.lesson).exists()


@pytest.mark.django_db
def test_a_lesson_of_another_programme_is_not_shown(client, signed_in):
    """The same module code and lesson slug in a different programme stays out."""
    foreign = ProgrammeVersion.objects.create(
        programme=Programme.objects.create(name="Desk elsewhere", code="desk-elsewhere"), version=1
    )
    other = Module.objects.create(
        programme_version=foreign, code=signed_in.module.code, title="Elsewhere", is_published=True
    )
    Lesson.objects.create(
        module=other, slug=signed_in.lesson.slug, title="A lesson from elsewhere",
        summary="Not this learner's programme.", is_published=True,
    )
    body = client.get(signed_in.desk_url).content.decode()
    assert "A lesson from elsewhere" not in body
    assert "Not this learner's programme." not in body


@pytest.mark.django_db
def test_a_section_change_keeps_the_page_and_the_lesson(client, signed_in):
    body = client.get(f"{signed_in.desk_url}&section=note").content.decode()
    assert "This section has no published content for this lesson yet." in body
    assert f'src="{reverse("single-window-create-ucr")}"' in _frame_source(body)


# --- how the reading pane is laid out ----------------------------------------


@pytest.mark.django_db
def test_the_step_card_holds_the_step_and_its_buttons(client, signed_in):
    body = client.get(signed_in.desk_url).content.decode()
    assert "Guided practical · Step 1 of 3" in body
    assert "Declare the consignment" in body
    assert "Create and submit the importer UCR declaration" in body
    assert "Check my work" in body
    assert "Hint" in body


@pytest.mark.django_db
def test_the_step_stays_pinned_while_the_reading_scrolls(client, signed_in):
    """The step is the head of the pane; the theory and journey scroll under it."""
    body = client.get(signed_in.desk_url).content.decode()
    assert body.index("data-desk-guide") < body.index('class="desk-scroll"')
    assert "Check my work" in body[: body.index('class="desk-scroll"')]
    assert "Lesson journey" in body[body.index('class="desk-scroll"') :]


@pytest.mark.django_db
def test_an_unverified_step_offers_a_disabled_next_step(client, signed_in):
    """The gate is still the engine's: the card shows the lock, it does not hide it."""
    body = client.get(signed_in.desk_url).content.decode()
    assert "The next step unlocks after a successful check." in body
    assert "disabled" in body
    assert 'action="/practical/attempts/' in body  # the check still posts to the engine


@pytest.mark.django_db
def test_the_journey_card_and_workflow_line_trace_the_scenario(client, signed_in):
    body = client.get(signed_in.desk_url).content.decode()
    assert "0 of 3 completed" in body
    assert "Apply for the document" in body
    assert "Practical complete" in body
    assert "Workflow:" in body


@pytest.mark.django_db
def test_an_author_sees_the_step_card_on_the_desk(client, desk_learner, db):
    """The shared panel hides itself from an author; the desk shows them their own."""
    tutor = User.objects.create_user(username="desk-tutor", email="tutor@example.test", password="test-password")
    tutor.groups.add(Group.objects.get(name="Instructor"))
    enrolment = _oriented(tutor, "tutor")
    version = _scenario()
    _three_step(version)
    from scenarios.services import start_or_resume_attempt

    start_or_resume_attempt(enrolment, version)
    client.force_login(tutor)
    body = client.get(reverse("desk-test")).content.decode()
    assert "Guided practical · Step 1 of 3" in body
    assert "Lesson journey" in body


@pytest.mark.django_db
def test_the_desk_opens_the_page_the_learner_chooses(client, signed_in):
    search_ucr = reverse("single-window-search-ucr")
    body = client.get(f"{reverse('practice-desk')}?sim={search_ucr}").content.decode()
    assert f'src="{search_ucr}"' in _frame_source(body)


@pytest.mark.django_db
@pytest.mark.parametrize("refused", ["/admin/", "//example.test/practical/clearance/", "/practical/no-such-page/"])
def test_the_desk_refuses_to_point_its_frame_at_anything_else(client, signed_in, refused):
    """``?sim=`` only accepts a page the playground itself links to."""
    body = client.get(f"{reverse('practice-desk')}?sim={refused}").content.decode()
    assert f'src="{reverse("single-window-create-ucr")}"' in _frame_source(body)


@pytest.mark.django_db
def test_a_page_that_is_not_in_the_menu_falls_back_to_the_step(client, signed_in):
    response = client.get(f"{reverse('practice-desk')}?sim=/practical/no-such-page/")
    assert urlsplit(response.context["desk"]["frame_url"]).path == reverse("single-window-create-ucr")


@pytest.mark.django_db
def test_the_switcher_offers_the_playgrounds_own_pages(rf, signed_in):
    """Read from the simulator navigation, so the list cannot drift from it."""
    urls = {page["url"] for page in _playground_pages(rf.get(reverse("practice-desk")))}
    assert reverse("single-window-create-ucr") in urls
    assert reverse("search-boe-declaration") in urls
    assert not any(url.startswith("/admin/") for url in urls)


@pytest.mark.django_db
def test_without_a_simulator_session_the_desk_shows_no_guide(client, db):
    user = User.objects.create_user(username="desk-nocredential", email="nocred@example.test", password="test-password")
    user.groups.add(Group.objects.get(name="Student"))
    _oriented(user, "desk-nocred")
    client.force_login(user)
    assert "data-desk-guide" not in client.get(reverse("practice-desk")).content.decode()


@pytest.mark.django_db
def test_a_completed_attempt_leaves_the_guide_pane_empty(client, signed_in):
    ScenarioAttempt.objects.filter(pk=signed_in.attempt.pk).update(status=ScenarioAttempt.Status.COMPLETED)
    assert "Step 1 of 3" not in client.get(signed_in.desk_url).content.decode()


# --- the no-argument entry point ---------------------------------------------


@pytest.mark.django_db
def test_the_test_route_opens_the_desk_with_no_url_building(client, signed_in):
    """``/test`` is the same desk, its two parameters filled in from the learner."""
    body = client.get(reverse("desk-test")).content.decode()
    assert 'src="/practical/portal/"' in _frame_source(body)
    assert "Who files what in the Single Window" in body
    assert "Step 1 of 3" in body


@pytest.mark.django_db
def test_the_test_route_keeps_what_the_url_asks_for(client, signed_in):
    search_ucr = reverse("single-window-search-ucr")
    reference = f"{signed_in.module.code}/{signed_in.lesson.slug}"
    body = client.get(f"{reverse('desk-test')}?sim={search_ucr}&lesson={reference}").content.decode()
    assert f'src="{search_ucr}"' in _frame_source(body)
    assert "Who files what in the Single Window" in body
