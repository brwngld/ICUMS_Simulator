import pytest

from learning.models import Lesson, Module
from learning.views import module_overview_context
from onboarding.models import Programme, ProgrammeVersion


@pytest.mark.django_db
def test_module_overview_previews_and_groups_learning_objectives():
    programme = Programme.objects.create(name="Logistics", code="logistics")
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    module = Module.objects.create(programme_version=version, code="planning", title="Planning")
    first = Lesson.objects.create(
        module=module,
        slug="forecasting",
        title="Demand Forecasting",
        objectives="\n".join(f"Forecasting objective {number}" for number in range(1, 6)),
    )
    second = Lesson.objects.create(
        module=module,
        slug="inventory",
        title="Inventory Planning",
        objectives="\n".join(f"Inventory objective {number}" for number in range(1, 5)),
    )

    context = module_overview_context(module)

    assert len(context["objective_preview"]) == 6
    assert context["objective_count"] == 9
    assert context["objective_groups"] == [
        {"lesson": first, "objectives": [f"Forecasting objective {number}" for number in range(1, 6)]},
        {"lesson": second, "objectives": [f"Inventory objective {number}" for number in range(1, 5)]},
    ]
