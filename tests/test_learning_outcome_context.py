import pytest

from learning.models import Lesson, Module
from learning.views import roadmap_context
from onboarding.models import Programme, ProgrammeVersion


@pytest.mark.django_db
def test_learning_outcome_card_uses_matching_lesson_context():
    programme = Programme.objects.create(
        name="Context course",
        code="context-course",
        learning_outcomes="Explain demand forecasting methods.",
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    module = Module.objects.create(programme_version=version, code="planning", title="Supply Planning")
    Lesson.objects.create(
        module=module,
        slug="forecasting",
        title="Demand Forecasting",
        objectives="Explain qualitative and quantitative forecasting methods.",
    )

    card = roadmap_context(version, None)["learning_outcome_cards"][0]

    assert card["title"] == "Explain demand forecasting methods."
    assert "Demand Forecasting" in card["description"]
    assert "Supply Planning" in card["description"]


@pytest.mark.django_db
def test_learning_outcome_card_uses_real_coverage_when_no_match_exists():
    programme = Programme.objects.create(
        name="Coverage course",
        code="coverage-course",
        learning_outcomes="Apply professional judgement.",
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    module = Module.objects.create(programme_version=version, code="records", title="Trade Records")
    Lesson.objects.create(module=module, slug="documents", title="Documents")

    description = roadmap_context(version, None)["learning_outcome_cards"][0]["description"]

    assert description == "Supported across 1 module and 1 lesson in this course."
