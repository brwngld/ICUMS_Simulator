"""Milestone 1 of the UI-first full-programme prototype: instructor programme
and course authoring.

Every screen here renders from the in-memory mock below — nothing reads or
writes the database, and no prototype action posts to a production endpoint.
The mock hierarchy mirrors the real Theory & Practical chain (builder
landing → programme workspace → course workspace → module workspace) so the
navigation and Unfold chrome can be reviewed exactly where the production
builder puts them.
"""
from django.contrib.auth.decorators import login_required

from core.admin_dashboard import render_student_page

from .prototype_data import (
    DEFAULT_DEMO_EVENT_SCRIPT,
    DEMO_EVENT_SCRIPTS,
    MOCK_EDITIONS,
    MOCK_LESSONS,
    MOCK_MODULE,
    MOCK_PROGRAMME,
    MOCK_STATS,
    SIMULATOR_SCREENS,
)


@login_required
def landing(request):
    """Mock Curriculum Builder landing: programme cards, stats and filters."""
    return render_student_page(
        request,
        "hybrid/prototype/milestone1_landing.html",
        {
            "landing_stats": MOCK_STATS["landing"],
            "programme_rows": MOCK_PROGRAMME["landing_rows"],
            "total_count": MOCK_PROGRAMME["total_count"],
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


@login_required
def programme(request):
    """Mock programme workspace: editions, readiness and the course grid."""
    return render_student_page(
        request,
        "hybrid/prototype/milestone1_programme.html",
        {
            "programme": MOCK_PROGRAMME["detail"],
            "editions": MOCK_EDITIONS,
            "selected": MOCK_EDITIONS[0],
            "has_open_draft": True,
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


@login_required
def course(request):
    """Mock course workspace: modules, practical workflows and readiness."""
    return render_student_page(
        request,
        "hybrid/prototype/milestone1_course.html",
        {
            "course": MOCK_PROGRAMME["course"],
            "modules": MOCK_PROGRAMME["course"]["modules"],
            "journeys": MOCK_PROGRAMME["course"]["journeys"],
            "blockers": MOCK_PROGRAMME["course"]["blockers"],
            "lesson_count": MOCK_PROGRAMME["course"]["lesson_count"],
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


@login_required
def module(request):
    """Mock module workspace: the lesson list with theory/practical states."""
    return render_student_page(
        request,
        "hybrid/prototype/milestone1_module.html",
        {
            "module": MOCK_MODULE,
            "lesson_rows": MOCK_MODULE["lesson_rows"],
            "interactive_count": MOCK_MODULE["interactive_count"],
            "theory_count": MOCK_MODULE["theory_count"],
            "not_ready_count": MOCK_MODULE["not_ready_count"],
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


def _mock_lesson(request):
    """Resolve ?lesson=<slug> (&kind=) to a mock lesson dict, never a DB read."""
    slug = (request.GET.get("lesson") or "").strip()[:60]
    lesson = MOCK_LESSONS.get(slug)
    if lesson is None:
        kind = "guided" if (request.GET.get("kind") == "guided") else "interactive"
        lesson = {
            "slug": slug or "new-lesson",
            "kind": kind,
            "title": "Untitled prototype lesson",
            "summary": "",
            "objectives": [],
            "theory_html": "",
            "materials": [],
            "checks": [],
            "procedure": SIMULATOR_SCREENS[0] if kind == "interactive" else "",
            "steps": [],
        }
    return lesson


@login_required
def lesson_editor(request):
    """Milestone 2 mock lesson editor — one screen, both provisional lesson
    kinds. All authoring state lives in this browser tab (sessionStorage);
    nothing here reads or writes a HybridLesson."""
    lesson = _mock_lesson(request)
    return render_student_page(
        request,
        "hybrid/prototype/milestone2_lesson_editor.html",
        {
            "lesson": lesson,
            "simulator_screens": SIMULATOR_SCREENS,
            "module": MOCK_MODULE,
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


@login_required
def lesson_preview(request):
    """Milestone 2 mock instructor preview of a lesson — the student
    workspace shape with the resizable split, rendered from the browser-side
    lesson state (falling back to the seeded mock)."""
    lesson = _mock_lesson(request)
    return render_student_page(
        request,
        "hybrid/prototype/milestone2_lesson_preview.html",
        {
            "lesson": lesson,
            "module": MOCK_MODULE,
            "prototype_note": MOCK_PROGRAMME["prototype_note"],
        },
    )


@login_required
def demonstration_studio(request):
    """Milestone 3 mock Demonstration Studio — the production studio layout
    replaying a scripted sample capture. No recording endpoint is called and
    DEMONSTRATION_RECORDING_ENABLED stays untouched; the only store is the
    browser tab's sessionStorage."""
    lesson = _mock_lesson(request)
    script = DEMO_EVENT_SCRIPTS.get(lesson["slug"], DEFAULT_DEMO_EVENT_SCRIPT)
    return render_student_page(
        request,
        "hybrid/prototype/milestone3_studio.html",
        {
            "lesson": lesson,
            "demo_events": script,
            # Guided Material Study lessons have no simulator walkthrough, so
            # the Studio explains itself instead of opening an empty frame.
            "studio_available": lesson["kind"] == "interactive",
            "module": MOCK_MODULE,
            "prototype_note": (
                "UI prototype — Milestone 3 (Demonstration Studio, mock capture). "
                "No simulator action is recorded, no demonstration session exists, "
                "and nothing on this page reaches the database."
            ),
        },
    )


@login_required
def student_experience(request):
    """Milestone 3 mock student experience preview — the real workspace
    design (split, divider, step cards, Previous/Next/Hint) driven entirely
    by the browser-tab lesson state. Check-my-work is labelled mock; no
    attempt is opened and no verification runs."""
    lesson = _mock_lesson(request)
    return render_student_page(
        request,
        "hybrid/prototype/milestone3_student.html",
        {
            "lesson": lesson,
            "module": MOCK_MODULE,
            "prototype_note": (
                "UI prototype — Milestone 3 student preview. This is not a lesson "
                "attempt: no progress, acknowledgement or verification is recorded."
            ),
        },
    )
