"""Integrated Practice Desk — a discardable prototype, not a feature.

One workspace that puts the lesson and the guided-practical step beside the real
simulator: theory and task in the left pane, the *existing* simulator page in the
right pane, shown in a same-origin frame so every field, validation rule and
script he edits in the playground shows up here without a second copy of
anything. Progression is untouched: the desk renders the same guide panel and
"Check my work" still runs ``verify_step`` against the attempt in the database.

The footprint is small on purpose, so the spike can be dropped in one revert:
``scenarios/desk.py``, ``templates/scenarios/practice_desk.html``,
``static/css/practice-desk.css``, ``static/js/practice-desk.js``, the two lines
in ``scenarios/urls.py``, the ``/test`` route in ``config/urls.py``, and the
framing gate in ``scenarios/views.py``. The theory side reads lesson content and
writes nothing — no progress row is created or moved here, so a desk visit
cannot complete a section; that stays on the lesson page. Reading a locked
section is equally harmless, because locking is enforced by the writes on that
page.

Everything is steered from the url, so no code change is needed to pair a page
with a lesson:
``/practical/practice-desk/?sim=<simulator page>&lesson=<module code>/<slug>&section=<slug>&programme=<code>``,
or ``/test`` for the same page with the first playground page and the first
lesson of the current programme filled in.
"""

from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from core.admin_dashboard import _simulator_navigation, render_student_page
from learning.models import Lesson, Module
from learning.views import _annotate_sections, _lesson_sections, _resolve_current_section
from onboarding.services import needs_disclaimer_acceptance, programme_href, requested_enrolment
from progress.models import LessonProgress

from . import guides
from .bindings import SIMULATOR_BINDING_ROUTES
from .models import ScenarioAttempt
from .views import _is_simulator_author

#: The playground areas whose own navigation supplies the desk's page switcher.
#: Options are read from that menu rather than copied into a list here, so a
#: simulator page added or renamed in the playground is the desk's too.
PLAYGROUND_AREAS = ("/practical/cargo", "/practical/clearance", "/practical/single-window")

#: Prefixes the frame may be pointed at. Framing is already refused by the
#: global ``DENY`` for anything outside the simulator views, so this only keeps
#: the desk from aiming its own frame at a page it should not show.
FRAMEABLE_PATHS = ("/practical/",)

#: Lesson sections readable beside the simulator. Answering practice questions
#: needs the lesson page's own POST flow, so the desk links out to that.
DESK_SECTIONS = ("objectives", "concepts", "example", "note")

#: Reading style per section, reusing the lesson page's own classes.
SECTION_COPY_CLASS = {
    "objectives": "lrn-introduction",
    "concepts": "lrn-copy",
    "example": "lrn-copy lrn-scenario",
    "note": "lrn-key",
}


def _playground_pages(request):
    """Every simulator page the playground navigation offers, area by area.

    ``_simulator_navigation`` builds one area's menu from the request path alone,
    so a bare path stand-in is enough to collect all three areas. A link that
    appears in more than one menu (the portal home) keeps its first label. Each
    page carries the desk url that shows it, so the template never has to build a
    query string.
    """
    pages = []
    seen = set()
    for path in ("/practical/portal", *PLAYGROUND_AREAS):
        for group in _simulator_navigation(SimpleNamespace(path=path)):
            for item in group["items"]:
                link = item.get("link") or ""
                if not link.startswith(FRAMEABLE_PATHS) or link in seen:
                    continue
                seen.add(link)
                pages.append({"url": link, "title": item["title"], "area": group["title"], "desk_url": _desk_href(request, sim=link)})
    return pages


def _page_groups(pages):
    """Menu sections in nav order, so the switcher reads like the playground menu.

    Consecutive pages of one section share an option group; pages the menu offers
    outside any section (the workspace home) come back with no title and are
    rendered ahead of the groups.
    """
    groups = []
    for page in pages:
        title = page["area"]
        if groups and groups[-1]["title"] == title:
            groups[-1]["pages"].append(page)
        else:
            groups.append({"title": title, "pages": [page]})
    return [group for group in groups if group["title"]]


def _route_name(path):
    """The bound-step route name for a playground page url, or ``""``."""
    for name in SIMULATOR_BINDING_ROUTES:
        try:
            if reverse(name) == path:
                return name
        except NoReverseMatch:
            continue
    return ""


def _frame_path(request, pages):
    """The ``?sim=`` page to show, validated against the playground menu.

    Only a path the playground itself links to is accepted, so the desk can never
    be aimed at an arbitrary url. Anything else returns ``""`` and the caller
    falls back to the step's own page.
    """
    requested = (request.GET.get("sim") or "").strip()
    if not requested or not requested.startswith("/"):
        return ""
    if not url_has_allowed_host_and_scheme(requested, allowed_hosts=None):
        return ""
    path = requested.split("?")[0].split("#")[0]
    return path if path in {page["url"] for page in pages} else ""


def _bound_path(attempt):
    """The simulator page the learner's current step points at, or ``""``."""
    if attempt is None:
        return ""
    binding = attempt.current_state.binding
    route = str(binding.get("route") or "") if isinstance(binding, dict) else ""
    if route not in SIMULATOR_BINDING_ROUTES:
        return ""
    try:
        return reverse(route)
    except NoReverseMatch:
        return ""


def _desk_href(request, **changes):
    """This desk's url with parameters replaced, so switching a section keeps the
    page, lesson and programme the desk is already showing."""
    params = {key: value for key, value in request.GET.items() if value}
    for key, value in changes.items():
        if value:
            params[key] = value
        else:
            params.pop(key, None)
    return "{}?{}".format(reverse("practice-desk"), urlencode(params))


def _theory(request, enrolment):
    """The lesson reading pane, resolved read-only.

    With no progress row the learner stands at the first section, shown through
    an unsaved ``LessonProgress`` instance rather than a created one.
    """
    reference = (request.GET.get("lesson") or "").strip().strip("/")
    if enrolment is None or "/" not in reference:
        return {}
    module_code, _, lesson_slug = reference.partition("/")
    module = Module.objects.filter(
        programme_version=enrolment.programme_version, code=module_code, is_published=True
    ).first()
    if module is None:
        return {}
    lessons = Lesson.objects.filter(module=module, slug=lesson_slug)
    if not _is_simulator_author(request.user):
        lessons = lessons.filter(is_published=True)
    lesson = lessons.first()
    if lesson is None:
        return {}

    progress = LessonProgress.objects.filter(enrolment=enrolment, lesson=lesson).first() or LessonProgress()
    sections = _lesson_sections()
    requested_section = request.GET.get("section")
    if requested_section in DESK_SECTIONS:
        # A named section is read as asked: the desk writes nothing, so opening
        # ahead cannot unlock a step that the lesson page still holds shut.
        index = next(i for i, item in enumerate(sections) if item["slug"] == requested_section)
    else:
        index, _redirect = _resolve_current_section(sections, progress, None)
        if sections[index]["slug"] not in DESK_SECTIONS:
            # Practice belongs to the lesson page; read key concepts instead.
            index = next(i for i, item in enumerate(sections) if item["slug"] == "concepts")

    _annotate_sections(sections, lambda slug: _desk_href(request, section=slug), progress, index)
    current = sections[index]
    kind = {"concepts": "text", "example": "example", "note": "notice"}.get(current["slug"], "")
    section_args = [module.code, lesson.slug]
    module_lessons = list(module.lessons.order_by("order", "title").values_list("pk", flat=True))

    return {
        "theory": {
            "lesson": lesson,
            "module": module,
            "module_number": module.order,
            "lesson_number": module_lessons.index(lesson.pk) + 1,
            "lesson_total": len(module_lessons),
            "section_number": index + 1,
            "sections_total": len(sections),
            "sections_done": sum(1 for item in sections if item["state"] == "done"),
            "sections": sections,
            "current_section": current,
            "objectives": [line.strip() for line in (lesson.objectives or "").splitlines() if line.strip()],
            "summary": (lesson.summary or "").strip(),
            "blocks": [block for block in lesson.blocks.all() if block.kind == kind] if kind else [],
            "copy_class": SECTION_COPY_CLASS.get(current["slug"], "lrn-copy"),
            "empty_message": "This section has no published content for this lesson yet.",
            "lesson_url": programme_href(reverse("lesson-section", args=[*section_args, current["slug"]]), enrolment),
            "practice_url": programme_href(reverse("lesson-section", args=[*section_args, "practice"]), enrolment),
            "desk_section_urls": {item["slug"]: item["url"] for item in sections},
        }
    }


@login_required
@require_GET
def practice_desk(request):
    """Theory and guide on the left, the real simulator on the right."""
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = requested_enrolment(request)
    pages = _playground_pages(request)
    frame_path = _frame_path(request, pages)

    attempt = None
    if frame_path:
        route = _route_name(frame_path)
        if route:
            attempt = guides.attempt_for_route(request, route)
    if attempt is None:
        attempt = guides.newest_attempt(request)
    if attempt is None and _is_simulator_author(request.user):
        # Desk-only affordance: the shared panel logic hides the step panel from
        # an author browsing the sandbox, which leaves nothing to review here.
        # Their own in-progress attempt is used instead, and only on this page.
        attempt = ScenarioAttempt.objects.filter(
            enrolment__student=request.user, status=ScenarioAttempt.Status.IN_PROGRESS
        ).select_related("current_state", "scenario_version", "enrolment").order_by("-started_at", "id").first()
    if not frame_path:
        frame_path = _bound_path(attempt) or (pages[0]["url"] if pages else "")

    # The page the frame shows decides which programme its links resolve on: an
    # attempt's own enrolment beats whichever enrolment the request happens to
    # pick, so the pane cannot disagree with the work in it.
    frame_enrolment = attempt.enrolment if attempt is not None else enrolment
    panel = guides.build_panel(attempt, notice=guides.take_notice(request, attempt)) if attempt else None
    context = {
        "desk": {
            "pages": pages,
            "page_groups": _page_groups(pages),
            "loose_pages": [page for page in pages if not page["area"]],
            "frame_path": frame_path,
            "frame_url": programme_href(frame_path, frame_enrolment) if frame_path else "",
            "steps_done": sum(1 for stage in panel.stages if stage.is_visited and not stage.is_current) if panel else 0,
        },
        "guide": panel,
        "enrolment": enrolment,
        "parts": {"paged": False},
    }
    context.update(_theory(request, enrolment))
    return render_student_page(request, "scenarios/practice_desk.html", context)


def _default_lesson(enrolment):
    """The first published lesson of this learner's programme, as a ``lesson=`` value."""
    if enrolment is None:
        return ""
    lesson = Lesson.objects.filter(
        module__programme_version=enrolment.programme_version,
        module__is_published=True,
        is_published=True,
    ).select_related("module").order_by("module__order", "order", "title").first()
    return f"{lesson.module.code}/{lesson.slug}" if lesson else ""


def test_desk(request):
    """The desk at ``/test`` with no url building required.

    Fills in the two parameters the desk reads - the framed simulator page and
    the lesson beside it - and then hands the request to the same view, so what
    is on screen is the desk itself rather than a second copy of it. Anything
    still typed into the url wins, and the page switcher changes ``sim`` live.
    """
    params = request.GET.copy()
    pages = _playground_pages(request)
    if not params.get("sim") and pages:
        params["sim"] = pages[0]["url"]
    if not params.get("lesson"):
        params["lesson"] = _default_lesson(requested_enrolment(request))
    request.GET = params
    return practice_desk(request)
