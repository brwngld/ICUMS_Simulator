"""Rich-text lesson content — storage, sanitisation and identical rendering.

Phase A of the content pipeline: every ``ContentBlock.body`` is normalised to
sanitised HTML, plain-text lessons keep their old ``linebreaks`` output, and the
learner page and the instructor preview render the same markup from the same template.
"""
import re

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import User
from assessments.models import LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from learning.rich_text import count_words, plain_text, to_safe_html
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion

RICH_BODY = (
    "<h3>Documents to check</h3>"
    "<p>A consignee submits <strong>two</strong> invoices.</p>"
    "<ul><li>Commercial invoice</li><li>Packing list</li></ul>"
    "<table><caption>Declaration routes</caption><thead><tr><th scope=\"col\">Case</th><th scope=\"col\">Route</th></tr></thead>"
    "<tbody><tr><td>Low value</td><td>Green</td></tr></tbody></table>"
    "<figure><img src=\"/media/lesson_rich_text/lesson/inspection.png\" alt=\"Inspection flow\" width=\"640\">"
    "<figcaption>Inspection flow</figcaption></figure>"
    "<p><a href=\"https://example.test/guide\" title=\"Guide\">Read the guide</a></p>"
)
UNSAFE_BODY = (
    "<p onclick=\"steal()\">Unsafe <script>alert(1)</script> content"
    "<iframe src=\"https://evil.test\"></iframe>"
    "<a href=\"javascript:alert(2)\">click</a>"
    "<img src=\"data:image/png;base64,AAAA\" alt=\"pixel\">"
    "<span class=\"big\" style=\"color:red\">styled</span></p>"
)


def _lesson_markup(html):
    return re.findall(r'<div class="lrn-copy[^"]*">(.*?)</div>', html, flags=re.S)


def _learner_on_concepts(client, course):
    """Sections unlock in order, so walk the learner from objectives to concepts."""
    client.force_login(course["learner"])
    objectives = reverse("lesson-section", args=[course["module"].code, course["lesson"].slug, "objectives"])
    client.get(objectives)
    return client.post(objectives, {"action": "continue"})


@pytest.fixture
def course(db):
    programme = Programme.objects.create(name="Rich Programme", code="rich-text")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.PUBLISHED)
    module = Module.objects.create(programme_version=version, code="rich-module", title="Rich Module", order=1, is_published=True)
    lesson = Lesson.objects.create(module=module, slug="rich-lesson", title="Rich Lesson", order=1, is_published=True)
    instructor = User.objects.create_user(username="rich-instructor", email="rich-i@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=instructor, disclaimer=DisclaimerVersion.objects.create(version=21, title="Rich notice", body="Training only.", is_current=True)
    )
    learner = User.objects.create_user(username="rich-learner", email="rich-l@example.test", password="test-password")
    learner.groups.add(Group.objects.get(name="Student"))
    Enrolment.objects.create(student=learner, programme_version=version, status="active")
    DisclaimerAcceptance.objects.get_or_create(
        user=learner, disclaimer=DisclaimerVersion.objects.create(version=22, title="Rich learner notice", body="Training only.", is_current=True)
    )
    return {"version": version, "module": module, "lesson": lesson, "instructor": instructor, "learner": learner}


def test_plain_text_body_keeps_linebreaks_paragraphs():
    assert to_safe_html("First line.\n\nSecond paragraph.") == "<p>First line.</p>\n\n<p>Second paragraph.</p>"
    assert to_safe_html("One\nTwo") == "<p>One<br>Two</p>"
    assert to_safe_html("") == "<p></p>"


def test_plain_text_markups_are_escaped_not_executed():
    assert to_safe_html("a < b and & sign") == "<p>a &lt; b and &amp; sign</p>"


def test_rich_body_survives_the_allowlist():
    cleaned = to_safe_html(RICH_BODY)
    for fragment in ["<h3>Documents to check</h3>", "<ul><li>Commercial invoice</li>", "<caption>Declaration routes</caption>",
                     '<th scope="col">Case', "<figcaption>Inspection flow</figcaption>", 'alt="Inspection flow"', 'title="Guide"']:
        assert fragment in cleaned, fragment


def test_unsafe_markup_and_protocols_are_removed():
    cleaned = to_safe_html(UNSAFE_BODY)
    for forbidden in ["onclick", "<script", "alert(", "<iframe", "javascript:", "data:image", "class=", "style="]:
        assert forbidden not in cleaned, forbidden
    assert "Unsafe" in cleaned and "styled" in cleaned


def test_to_safe_html_is_idempotent():
    once = to_safe_html(RICH_BODY)
    assert to_safe_html(once) == once


def test_word_counts_ignore_markup():
    assert count_words("<p>one <strong>two</strong></p><p>three</p>") == 3
    assert count_words("one\ntwo") == 2
    assert count_words("") == 0
    assert count_words("<p>Fictional lesson content.</p>") == count_words("Fictional lesson content.")


@pytest.mark.django_db
def test_saving_a_plain_block_stores_paragraph_html(course):
    block = ContentBlock.objects.create(lesson=course["lesson"], heading="Concept", body="Fictional lesson content.", order=1)
    assert block.body == "<p>Fictional lesson content.</p>"


@pytest.mark.django_db
def test_saving_a_rich_block_stores_sanitised_html(course):
    block = ContentBlock.objects.create(lesson=course["lesson"], heading="Concept", body=UNSAFE_BODY, order=1)
    assert "<script" not in block.body and "onclick" not in block.body


@pytest.mark.django_db
def test_learner_sees_the_rich_markup_as_html(client, course):
    ContentBlock.objects.create(lesson=course["lesson"], heading="Concept", body=RICH_BODY, order=1)
    _learner_on_concepts(client, course)
    response = client.get(reverse("lesson-section", args=[course["module"].code, course["lesson"].slug, "concepts"]))
    assert response.status_code == 200
    markup = "".join(_lesson_markup(response.content.decode()))
    assert "<caption>Declaration routes</caption>" in markup
    assert "<figcaption>Inspection flow</figcaption>" in markup
    assert "&lt;caption&gt;" not in markup


@pytest.mark.django_db
def test_preview_and_learner_page_render_the_same_markup(client, course):
    ContentBlock.objects.create(lesson=course["lesson"], heading="Concept", body=RICH_BODY, order=1)
    _learner_on_concepts(client, course)
    learner_html = client.get(reverse("lesson-section", args=[course["module"].code, course["lesson"].slug, "concepts"])).content.decode()
    client.force_login(course["instructor"])
    preview_html = client.get(reverse("lesson-preview", args=[course["lesson"].pk]), {"section": "concepts"}).content.decode()
    assert _lesson_markup(learner_html) == _lesson_markup(preview_html)
    assert _lesson_markup(learner_html), "the concepts section should render a content block"


@pytest.mark.django_db
def test_normalise_migration_wraps_legacy_bodies_without_changing_the_text(course):
    import importlib
    from django.apps import apps as global_apps

    migration = importlib.import_module("learning.migrations.0005_normalise_content_bodies")
    block = ContentBlock(lesson=course["lesson"], heading="Legacy", body="First line.\n\nSecond paragraph.", order=1)
    block.save()
    # A row written before the pipeline existed, straight into the column.
    ContentBlock.objects.filter(pk=block.pk).update(body="First line.\n\nSecond paragraph.")

    migration.normalise_bodies(global_apps, None)

    block.refresh_from_db()
    assert block.body == "<p>First line.</p>\n\n<p>Second paragraph.</p>"
    assert plain_text(block.body) == "First line. Second paragraph."
    assert count_words(block.body) == count_words("First line.\n\nSecond paragraph.")


@pytest.mark.django_db
def test_reading_time_is_the_same_for_plain_and_normalised_bodies(course):
    from learning.views import _lesson_minutes

    block = ContentBlock(lesson=course["lesson"], heading="Legacy", body=" ".join(f"word{index}" for index in range(200)), order=1)
    block.save()
    normalised = _lesson_minutes(course["lesson"])
    ContentBlock.objects.filter(pk=block.pk).update(body=block.body.removeprefix("<p>").removesuffix("</p>"))
    assert _lesson_minutes(course["lesson"]) == normalised == 1


@pytest.fixture
def draft_lesson(db):
    """A draft course with one lesson whose section can be left empty."""
    instructor = User.objects.create_user(username="guard-instructor", email="guard-i@example.test", password="test-password")
    instructor.groups.add(Group.objects.get(name="Instructor"))
    DisclaimerAcceptance.objects.get_or_create(
        user=instructor, disclaimer=DisclaimerVersion.objects.create(version=23, title="Guard notice", body="Training only.", is_current=True)
    )
    programme = Programme.objects.create(name="Guard Programme", code="guard-text")
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status=ProgrammeVersion.Status.DRAFT)
    module = Module.objects.create(programme_version=version, code="guard-module", title="Guard Module", order=1)
    lesson = Lesson.objects.create(module=module, slug="guard-lesson", title="Guard Lesson", summary="Draft.", order=1)
    block = ContentBlock.objects.create(lesson=lesson, heading="Concept", body="", order=1)
    return {"instructor": instructor, "version": version, "lesson": lesson, "block": block}


@pytest.mark.django_db
def test_an_empty_section_is_saved_but_blocks_publishing(client, draft_lesson):
    client.force_login(draft_lesson["instructor"])
    response = client.post(
        reverse("lesson-edit", args=[draft_lesson["lesson"].pk]),
        {
            "csrfmiddlewaretoken": "test",
            "title": "Guard Lesson",
            "summary": "Draft.",
            "objectives": "",
            "key_terms": "",
            "form-TOTAL_FORMS": "1", "form-INITIAL_FORMS": "1", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000",
            "form-0-id": str(draft_lesson["block"].pk), "form-0-heading": "Concept", "form-0-body": "",
        },
    )
    assert response.status_code == 302, "an unfinished draft section must still save"
    draft_lesson["block"].refresh_from_db()
    assert draft_lesson["block"].body == "<p></p>"

    review = client.get(reverse("course-review", args=[draft_lesson["version"].pk])).content.decode()
    assert "Not ready to publish" in review
    assert "Add teaching content to" in review


@pytest.mark.django_db
def test_a_written_section_clears_the_teaching_content_blocker(client, draft_lesson):
    draft_lesson["block"].body = "<p>Conformity assessment is evaluated against a checklist.</p>"
    draft_lesson["block"].save()
    LessonCheck.objects.create(
        lesson=draft_lesson["lesson"],
        after_block=draft_lesson["block"],
        question_version=QuestionVersion.objects.create(
            question=Question.objects.create(code="guard-check"), version=1, prompt="Check?", explanation="Because.", points=1
        ),
        order=1,
    )
    client.force_login(draft_lesson["instructor"])
    review = client.get(reverse("course-review", args=[draft_lesson["version"].pk])).content.decode()
    assert "Add teaching content to" not in review


def test_ordered_lists_are_preserved_for_learner_rendering():
    from learning.rich_text import to_safe_html

    rendered = to_safe_html("<ol><li>Planning</li><li>Implementation</li></ol>")

    assert rendered == "<ol><li>Planning</li><li>Implementation</li></ol>"

