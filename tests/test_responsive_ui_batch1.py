from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_dash_grid_can_shrink_below_its_preferred_card_width():
    css = source("static/css/dash.css")
    assert "minmax(min(100%, 20rem), 1fr)" in css
    assert ".dash-panel { min-width: 0;" in css


def test_admin_dash_grid_can_shrink_below_its_preferred_card_width():
    css = source("static/css/admin-dashboard.css")
    assert "minmax(min(100%, 21rem), 1fr)" in css
    assert ".dash-panel { min-width: 0;" in css


def test_instructor_roster_owns_its_horizontal_scroll():
    template = source("templates/instructor_portal/dashboard.html")
    css = source("static/css/dash.css")
    assert 'class="dash-grid roster-filters"' in template
    assert 'class="roster-table-wrap" role="region"' in template
    assert 'aria-label="Student progress roster" tabindex="0"' in template
    assert ".roster-table-wrap { max-width: 100%; overflow-x: auto; }" in css
    assert ".roster-filters { grid-template-columns: 1fr; }" in css


def test_account_navigation_is_a_bounded_internal_scroller():
    css = source("static/css/dash.css")
    account_nav_rule = css.split(".account-nav {", 1)[1].split("}", 1)[0]
    assert "max-width: 100%" in account_nav_rule
    assert "overflow-x: auto" in account_nav_rule
    assert "overflow-x: hidden" not in source("templates/accounts/settings.html")


def test_affected_pages_have_one_labelled_main_landmark():
    expectations = {
        "templates/instructor_portal/dashboard.html": ("instructor-dashboard-title", "Student progress"),
        "templates/accounts/settings.html": ("account-settings-title", "Settings"),
    }
    for path, (heading_id, heading) in expectations.items():
        template = source(path)
        assert template.count('role="main"') == 1
        assert f'aria-labelledby="{heading_id}"' in template
        assert template.count(f'id="{heading_id}"') == 1
        assert f">{heading}</h1>" in template

    admin = source("templates/admin/index.html")
    assert admin.count('role="main"') == 1
    assert 'aria-labelledby="admin-overview-title"' in admin
    assert '<h2 id="admin-overview-title">Overview</h2>' in admin


def test_unfold_shell_has_a_functional_skip_link_target():
    template = source("templates/admin/base.html")
    assert 'href="#content"' in template
    assert ">Skip to main content</a>" in template
    assert template.count('id="content"') == 1
