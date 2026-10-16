from django.template.loader import render_to_string


def test_lesson_objectives_show_four_item_preview_and_expand_the_remainder():
    objectives = [f"Objective {number}" for number in range(1, 11)]

    html = render_to_string("learning/_lesson_objective_list.html", {"objectives": objectives})

    preview = html.split('class="lrn-objective-list lrn-objective-preview"', 1)[1].split("</div>\n", 1)[0]
    remainder = html.split('class="lrn-objective-list lrn-objective-more"', 1)[1]
    assert preview.count('class="lrn-objective"') == 4
    assert remainder.count('class="lrn-objective"') == 6
    assert "View all 10 learning objectives" in html


def test_lesson_objectives_do_not_show_accordion_for_four_items():
    html = render_to_string(
        "learning/_lesson_objective_list.html",
        {"objectives": [f"Objective {number}" for number in range(1, 5)]},
    )

    assert html.count('class="lrn-objective"') == 4
    assert "lrn-objective-details" not in html
