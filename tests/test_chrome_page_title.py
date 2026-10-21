"""Regression guard: the chrome header names the page, never the admin greeting.

Unfold builds the header title (unfold/helpers/welcomemsg.html -> the
`header_title` tag) from the `content_title` block, and when a page gives it
nothing the tag falls back to "Welcome <username>". Every page in the student
shell therefore declares `workspace_name`, which core/base_student.html bridges
into that block. Simulator-shell pages name themselves through
core.admin_dashboard._SIMULATOR_PAGE_HEADS, which fills the `simulator_page`
header, or through their own `sim_title` block.
"""

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = PROJECT_ROOT / "templates"
SHELL = TEMPLATE_ROOT / "core" / "base_student.html"
SIMULATOR_SHELL = TEMPLATE_ROOT / "core" / "base_simulator.html"
#: The Practice Desk spike is discardable in one revert and its own copy is
#: still unapproved, so it is not held to the rule the shipped pages follow.
EXEMPT = {TEMPLATE_ROOT / "scenarios" / "practice_desk.html"}
#: Screens whose view passes the page name as `title`, which the chrome reads
#: directly: they are one template behind many records, so no fixed head entry.
TITLE_CONTEXT_SIMULATOR_PAGES = {
    TEMPLATE_ROOT / "scenarios" / "cargo_reference_page.html",
    TEMPLATE_ROOT / "scenarios" / "clearance_reference_page.html",
    TEMPLATE_ROOT / "scenarios" / "single_window_reference_page.html",
}


def _student_pages():
    for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
        if path == SHELL or path in EXEMPT:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if "core/base_student.html" in body and "{% extends" in body:
            yield path, body


def test_every_student_shell_page_declares_its_chrome_title():
    untitled = [
        str(path.relative_to(PROJECT_ROOT))
        for path, body in _student_pages()
        if "{% block workspace_name %}" not in body
    ]
    assert untitled == [], "Pages that would fall back to the admin greeting:\n" + "\n".join(untitled)


def test_the_simulator_pages_all_name_themselves_in_the_chrome():
    from core.admin_dashboard import _SIMULATOR_PAGE_HEADS

    untitled = []
    for path in sorted(TEMPLATE_ROOT.rglob("*.html")):
        if path == SIMULATOR_SHELL or path in EXEMPT or path in TITLE_CONTEXT_SIMULATOR_PAGES:
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if "core/base_simulator.html" not in body or "{% extends" not in body:
            continue
        if path.relative_to(TEMPLATE_ROOT).as_posix() not in _SIMULATOR_PAGE_HEADS:
            if "{% block sim_title %}" not in body:
                untitled.append(str(path.relative_to(PROJECT_ROOT)))
    assert untitled == [], "Simulator pages that would fall back to the admin greeting:\n" + "\n".join(untitled)


def test_the_shell_bridges_workspace_name_into_the_chrome_title():
    shell = SHELL.read_text(encoding="utf-8")
    bridge = re.search(
        r"\{% *block content_title *%\}\s*\{% *block workspace_name *%\}.*?\{% *endblock *%\}\s*\{% *endblock *%\}",
        shell,
    )
    assert bridge, "core/base_student.html no longer feeds workspace_name to the chrome header"


def test_the_chrome_header_reads_the_page_name(client, django_user_model):
    user = django_user_model.objects.create_user(username="chrome-reader", password="x", first_name="Chrome")
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    chrome = html[html.index('id="header-inner"') :][:1200]
    assert "Dashboard" in chrome
    assert "Welcome" not in chrome
