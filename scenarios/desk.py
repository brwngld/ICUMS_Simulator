"""Integrated Practice Desk — a discardable prototype, not a feature.

One workspace that puts the lesson and the guided-practical step beside the real
simulator: theory and task in the left pane, the *existing* simulator page in the
right pane, shown in a same-origin frame so every field, validation rule and
script he edits in the playground shows up here without a second copy of
anything. Progression is untouched: the desk renders the same guide panel and
"Check my work" still runs ``verify_step`` against the attempt in the database.

The footprint is small on purpose, so the spike can be dropped in one revert:
``scenarios/desk.py``, ``templates/scenarios/practice_desk.html``,
``static/css/practice-desk.css``, ``static/js/practice-desk.js``, the two lines in
``scenarios/urls.py``, the ``/test`` route in ``config/urls.py``, and the framing
gate in ``scenarios/views.py``. ``practical_roadmap`` below, its template
``scenarios/practical_roadmap.html`` and its url line are the same kind of spike:
a redesign of the practical landing shown on its own path, ``?done=N`` previewing
how far the learner has got. The theory side reads lesson content and
writes nothing — no progress row is created or moved here, so a desk visit
cannot complete a section; that stays on the lesson page. Reading a locked
section is equally harmless, because locking is enforced by the writes on that
page.

Everything is steered from the url, so no code change is needed to pair a page
with a lesson:
``/practical/practice-desk/?sim=<simulator page>&lesson=<module code>/<slug>&section=<slug>&programme=<code>``,
or ``/test`` for the same page with the first playground page and the first
lesson of the current programme filled in. ``sim=none`` leaves the simulator out
altogether, for the reading and How To pages.
"""

from types import SimpleNamespace
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from accounts.models import SimulatorCredential
from core.admin_dashboard import _simulator_navigation, render_student_page
from learning.models import Lesson, Module
from learning.views import _annotate_sections, _lesson_sections, _resolve_current_section
from onboarding.services import needs_disclaimer_acceptance, programme_href, requested_enrolment
from progress.models import LessonProgress

from . import guides
from .bindings import SIMULATOR_BINDING_ROUTES
from .models import ScenarioAttempt, UcrDeclaration
from .services import practical_is_unlocked
from .views import _effective_owner, _enrolment_with_access, _is_simulator_author, simulator_access_required

REFERENCE_UCR = "KGHTESTUCR260000014"

#: The playground areas whose own navigation supplies the desk's page switcher.
#: Options are read from that menu rather than copied into a list here, so a
#: simulator page added or renamed in the playground is the desk's too.
PLAYGROUND_AREAS = ("/practical/cargo", "/practical/clearance", "/practical/single-window")

#: Prefixes the frame may be pointed at. Framing is already refused by the
#: global ``DENY`` for anything outside the simulator views, so this only keeps
#: the desk from aiming its own frame at a page it should not show.
FRAMEABLE_PATHS = ("/practical/",)

#: ``?sim=none`` runs the desk without a simulator beside it. The theory and How
#: To pages have no use for one; the step checks read the framed document, so
#: they are inert on this setting until a page is named again.
NO_FRAME = "none"

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

#: The theory shown beside the UCR practical: one page, no section machinery.
#: Body copy is Bernard's, dictated 2026-10-22; the two headings are his too.
#: Rendered with ``lesson.css``'s own ``.lrn-copy``, so nothing new is styled.
UCR_THEORY = {
    "title": "What is UCR and How to Create UCR",
    "lead": "UCR in ICUMS stands for Unique Consignment Reference.",
    "sections": [
        {
            "heading": "What It Is",
            "items": [
                {
                    "lead": "Definition",
                    "text": "An exclusive, globally unique reference number assigned to a shipment or cargo "
                    "movement within Ghana's Integrated Customs Management System (ICUMS).",
                },
                {
                    "lead": "Electronic Data Binder",
                    "text": "It acts as a digital file that tracks an international trade transaction from the "
                    "initial order all the way to final delivery.",
                },
                {
                    "lead": "Single Window Access",
                    "text": "Importers, exporters, or declarants create and manage it directly inside the ICUMS "
                    "platform without switching between different systems.",
                },
            ],
        },
        {
            "heading": "Key Uses in ICUMS",
            "items": [
                {
                    "lead": "Cargo Tracking & Identification",
                    "text": "Allows customs authorities and traders to easily identify, monitor, and trace goods.",
                },
                {
                    "lead": "Document Linking",
                    "text": "Serves as the primary reference key to attach and link trade documents\u2014such as "
                    "invoices, bills of lading, packing lists, and certificates of origin (COO)\u2014to a specific "
                    "consignment.",
                },
                {
                    "lead": "Audit & Reconciliation",
                    "text": "Used by enforcement and revenue agencies (like the Ghana Revenue Authority) for "
                    "auditing, compliance checks, and customs clearance reconciliation.",
                },
            ],
        },
    ],
}


#: The How To page shown after the theory: what to have ready before a UCR is
#: started. Bernard dictates this list; add an item and it shows on the page.
UCR_HOWTO = {
    "label": "Things needed before one can work on UCR",
    "items": [
        "You need BL, Invoice and Packing List.",
        "You need the importer's TIN.",
        "You need scanned copies of the documents.",
        "You need to check the importer's details against that of the TIN. If the names match, "
        "then you are good to go, but if not, kindly draw the attention of the one who gave you "
        "the work, probably your boss.",
    ],
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
    no_frame = (request.GET.get("sim") or "").strip().lower() == NO_FRAME

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
    if not frame_path and not no_frame:
        frame_path = _bound_path(attempt) or (pages[0]["url"] if pages else "")

    # The page the frame shows decides which programme its links resolve on: an
    # attempt's own enrolment beats whichever enrolment the request happens to
    # pick, so the pane cannot disagree with the work in it.
    frame_enrolment = attempt.enrolment if attempt is not None else enrolment
    panel = guides.build_panel(attempt, notice=guides.take_notice(request, attempt)) if attempt else None
    reference_guide = getattr(request, "_show_reference_ucr_guide", False) and _reference_ucr_guide(request)
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
        "reference_guide": reference_guide,
        "ucr_theory": UCR_THEORY if reference_guide else None,
        "ucr_howto": UCR_HOWTO if reference_guide else None,
        "enrolment": enrolment,
        "parts": {"paged": False},
    }
    context.update(_theory(request, enrolment))
    return render_student_page(request, "scenarios/practice_desk.html", context)


def _reference_ucr_guide(request):
    """Small, read-only exercise generated from an actual learner-owned UCR."""
    record = UcrDeclaration.objects.filter(owner=_effective_owner(request), ucr_no=REFERENCE_UCR).first()
    if record is None:
        return None
    documents = [
        {"code": str(item.get("code") or ""), "name": str(item.get("name") or ""), "reference": str(item.get("reference") or "")}
        for item in (record.documents or [])
    ]
    def party(identity, name):
        return identity if identity and identity == name else ", ".join(value for value in (identity, name) if value)

    return {
        "ucr": record.ucr_no,
        "detail_path": reverse("ucr-detail", args=[record.pk]),
        "search_path": reverse("single-window-search-ucr"),
        "create_path": reverse("single-window-create-ucr"),
        "status": record.get_status_display(),
        "regime": record.regime,
        "declarant": record.declarant_code,
        "exporter": party(record.exporter_identity, record.exporter_name),
        "exporter_name": record.exporter_name or record.exporter_identity,
        "exporter_country": record.exporter_country,
        "exporter_phone": record.exporter_phone,
        "exporter_contact": record.exporter_contact,
        "exporter_designation": record.exporter_designation,
        "importer": party(record.importer_identity, record.importer_name),
        "importer_tin": record.importer_identity,
        "importer_name": record.importer_name,
        "importer_country": record.importer_country,
        "importer_address": record.importer_address,
        "importer_phone": record.importer_phone,
        "importer_contact": record.importer_contact,
        "importer_contact_no": record.importer_contact_no,
        "importer_designation": record.importer_designation,
        "goods": record.goods_description,
        "origin": record.origin_country,
        "destination": record.destination_country,
        "transport": record.transport_mode,
        "documents": documents,
    }


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
    request._show_reference_ucr_guide = True
    return practice_desk(request)


#: Provisional copy for the roadmap spike. Bernard dictates the wording; these
#: strings are the only place it lives so a pass over them is one edit.
ROADMAP_COPY = {
    "title": "Guided simulator practice",
    "description": "Work through the same transactions a clearing agent works through in ICUMS, one checked step at a time, with the live page open beside you.",
    "doing": "Re-enter a real UCR in the Single Window form, step by step, and save it as a draft.",
    "skills": [
        "Read a consignment from its source documents",
        "Key importer and exporter records accurately",
        "Keep a clean draft for the next session",
    ],
}

CREDENTIAL_LABELS = {"active": "Active", "expiring": "Expiring soon", "expired": "Expired", "none": "Not issued"}


def _roadmap_plan(reference):
    """The six UCR steps, mirrored from the ``ucrSteps`` array in
    ``static/js/practice-desk.js``. That text lives in the browser today, so this
    page cannot list it from a model - one of the two has to become the source.
    """
    def value(key):
        return str((reference or {}).get(key) or "—")

    return [
        {"title": "Open Single Window", "short": "Open Single Window", "instruction": "Select Single Window in the simulator navigation.", "checks": ["Single Window UCR form is open"]},
        {"title": "Select the regime", "short": "Select Import", "instruction": "Select Import as the Regime Type.", "checks": ["Regime Type is IM, Import"]},
        {"title": "Enter the exporter details", "short": "Exporter details", "instruction": "Scroll to Exporter and enter the values from the source UCR.", "checks": [f"Exporter name: {value('exporter_name')}", f"Country: {value('exporter_country')}", f"Tel. No.: {value('exporter_phone')}", f"Contact Person: {value('exporter_contact')}", f"Contact Designation: {value('exporter_designation')}"]},
        {"title": "Enter the importer details", "short": "Importer details", "instruction": "Enter the importer TIN and use its search button. In the pop-up, select either the TIN or name to populate the name and address. If the address is blank, enter it manually.", "checks": [f"TIN: {value('importer_tin')}", f"Name: {value('importer_name')}", f"Country: {value('importer_country')}", f"Address: {value('importer_address')}", f"Tel. No.: {value('importer_phone')}", f"Contact Person: {value('importer_contact')}", f"Contact No.: {value('importer_contact_no')}", f"Contact Designation: {value('importer_designation')}"]},
        {"title": "Enter the consignment details", "short": "Consignment details", "instruction": "Scroll to Consignment Details and enter the values from the source UCR.", "checks": [f"Goods description: {value('goods')}", f"Country of Origin: {value('origin')}", f"Country of Destination: {value('destination')}", f"Transport Mode: {value('transport')}"]},
        {"title": "Save as draft", "short": "Save as draft", "instruction": "Select Save to store the UCR as a draft and finish this practical.", "checks": ["Draft saved with a TEMPUCR number"]},
    ]


def _credential_summary(user):
    """The learner's simulator credential, stated the way the account page states it."""
    credential = SimulatorCredential.objects.filter(user=user).first()
    state = "none"
    if credential and credential.expires_at:
        remaining = (credential.expires_at - timezone.now()).total_seconds()
        state = "expired" if remaining <= 0 else ("expiring" if remaining <= 7 * 86400 else "active")
    expires = credential.expires_at if credential else None
    return {
        "state": state,
        "state_label": CREDENTIAL_LABELS[state],
        "expires_label": timezone.localdate(expires).strftime("%d %b %Y").lstrip("0") if expires else "—",
        "url": reverse("account-credential"),
    }


@login_required
@simulator_access_required
def practical_roadmap(request):
    """The practical landing in the theory roadmap frame, filled from this desk."""
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    reference = _reference_ucr_guide(request)
    pages = _playground_pages(request)
    plan = _roadmap_plan(reference)
    try:
        current = max(0, min(len(plan), int(request.GET.get("done") or 0)))
    except ValueError:
        current = 0
    create_path = (reference or {}).get("create_path") or (pages[0]["url"] if pages else reverse("scenario-list"))
    desk_url = programme_href(
        "{}?{}".format(reverse("practice-desk"), urlencode({"sim": create_path})), enrolment
    )
    steps = []
    for index, step in enumerate(plan):
        state = "done" if index < current else ("current" if index == current else "locked")
        steps.append({**step, "state": state, "clickable": state in ("done", "current"), "url": desk_url,
                      "check_count": len(step["checks"])})
    practicals = [{
        "title": "Create a UCR in Single Window",
        "area": "Single Window",
        "objective": "{} supplies every value this practical re-enters.".format((reference or {}).get("ucr") or "A source UCR"),
        "steps": steps,
        "step_count": len(steps),
        "done_count": current,
    }]
    return render_student_page(request, "scenarios/practical_roadmap.html", {
        "proto": {
            **ROADMAP_COPY,
            "practicals": practicals,
            "step_total": len(steps),
            "done_count": current,
            "locked_count": max(len(steps) - current - 1, 0),
            "check_total": sum(len(step["checks"]) for step in plan),
            "percentage": round(current / len(steps) * 100) if steps else 0,
            "pages": pages,
            "page_groups": _page_groups(pages),
            "howto_items": UCR_HOWTO["items"],
            "theory_sections": [
                {"heading": group["heading"], "summary": " · ".join(item["lead"] for item in group["items"])}
                for group in UCR_THEORY["sections"]
            ],
            "source_fields": [
                {"label": "UCR No.", "value": (reference or {}).get("ucr", "Not available on this account")},
                {"label": "Status", "value": (reference or {}).get("status", "—")},
                {"label": "Regime", "value": (reference or {}).get("regime", "—")},
                {"label": "Declarant", "value": (reference or {}).get("declarant", "—")},
                {"label": "Importer TIN", "value": (reference or {}).get("importer_tin", "—")},
                {"label": "Exporter", "value": (reference or {}).get("exporter", "—")},
            ],
            "credential": _credential_summary(request.user),
            "unlocked": practical_is_unlocked(enrolment) if enrolment else False,
            "lock_note": "Complete simulator orientation to unlock practical training.",
            "resume": None if not steps or current >= len(steps) else {
                "practical": practicals[0]["title"],
                "title": steps[current]["title"],
                "instruction": steps[current]["instruction"],
                "url": desk_url,
            },
        }
    })
