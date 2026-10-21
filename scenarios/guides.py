"""The guide panel carried into the simulator by a guided-practice step.

Phase 2 of the guided-practice roadmap: the step used to live only on the
scenario workspace, so reading the task and pressing "Check my work" meant
leaving the simulator and coming back. The panel travels with the student
instead — it appears on the simulator page that the step's own binding points
at, and every control in it posts to the existing engine endpoints. It is a
second window onto the same state machine, never a second copy of its rules:
what the panel offers is whatever ``scenarios.services`` already permits, and
the engine re-decides on every request.

Two rules hold throughout. Nothing is taken from the request except a marker
saying the panel made the call — the page to return to is re-derived from the
attempt's binding through the registry, so a crafted form cannot aim the
redirect anywhere else. And a check result travels in the server-side session,
never in a query string or a form field, so the frontend cannot report a
verification that the database does not support.
"""

from dataclasses import dataclass

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse

from .bindings import SIMULATOR_BINDING_ROUTES
from .models import ScenarioAttempt
from .services import available_actions
from .verification import step_verified_at, step_verification_required

#: One-shot panel notice, held in the session and consumed by the next render
#: of the step it belongs to.
GUIDE_NOTICE_KEY = "guided_practice_notice"

#: Shown when a step asks for its task to be verified before it will move on.
VERIFICATION_PENDING = (
    "This step's simulator task has not been verified yet. Complete the task, "
    "then check your work to continue."
)

#: Assistance modes that show the step's explanation and offer a hint. Advanced
#: and competency students get the task and nothing else, exactly as on the
#: workspace page.
GUIDED_MODES = ("beginner", "intermediate")


@dataclass
class GuideNotice:
    """A check or hint result waiting to be read in the panel."""

    kind: str
    message: str
    passed: bool | None = None

    @property
    def tone(self):
        if self.passed is True:
            return "pass"
        if self.passed is False:
            return "fail"
        return "info" if self.kind else ""


@dataclass
class GuideStage:
    label: str
    is_current: bool
    is_visited: bool


@dataclass
class GuidePanel:
    """Everything the panel renders, resolved from the attempt rather than the page."""

    attempt: object
    state: object
    scenario_title: str
    area: str
    step_number: int
    step_total: int
    task: str
    guidance: str
    stages: list
    actions: list
    workspace_url: str
    check_url: str
    hint_url: str
    verification_pending: bool
    notice: GuideNotice | None = None

    @property
    def shows_hint(self):
        return self.attempt.assistance_mode in GUIDED_MODES

    @property
    def collapsed_summary(self):
        return f"Step {self.step_number} of {self.step_total} · {self.state.label}"


def _binding(attempt):
    binding = attempt.current_state.binding
    return binding if isinstance(binding, dict) else {}


def _current_url_name(request):
    return getattr(getattr(request, "resolver_match", None), "url_name", "")


def active_attempt(request):
    """The attempt whose current step points at the page being rendered.

    Matching on the page rather than on a parameter means a bookmarked or
    hand-typed simulator url still finds the right step, and a student with
    several attempts sees the one they are actually working on. Only a learner
    signed in to their own simulator session qualifies: staff review sessions
    and author previews carry no session of their own to match, so the panel
    never appears during ordinary sandbox use.
    """
    if hasattr(request, "_guided_attempt"):
        return request._guided_attempt
    request._guided_attempt = attempt_for_route(request, _current_url_name(request))
    return request._guided_attempt


def _session_student(request):
    """The learner whose own simulator session this request carries, else ``None``."""
    user = getattr(request, "user", None)
    session = getattr(request, "session", None)
    if user is None or not user.is_authenticated or session is None:
        return None
    if session.get("simulator_user_id") != str(user.pk):
        return None
    return user


def _own_attempts(user):
    return (
        ScenarioAttempt.objects.filter(
            enrolment__student=user,
            status=ScenarioAttempt.Status.IN_PROGRESS,
        )
        .select_related("current_state", "scenario_version__scenario")
        .order_by("-started_at", "id")
    )


def attempt_for_route(request, url_name):
    """The in-progress attempt standing on the step bound to ``url_name``."""
    if url_name not in SIMULATOR_BINDING_ROUTES:
        return None
    user = _session_student(request)
    if user is None:
        return None
    return _own_attempts(user).filter(current_state__binding__route=url_name).first()


def newest_attempt(request):
    """The learner's most recent in-progress attempt, whatever step it is on.

    Used by pages that are not themselves a bound simulator step and so cannot
    be matched by route; the attempt still comes from the same session check, so
    it is never someone else's work.
    """
    user = _session_student(request)
    if user is None:
        return None
    return _own_attempts(user).first()


def _stages(states, current, visited):
    return [GuideStage(label=state.label, is_current=state.pk == current.pk, is_visited=state.key in visited) for state in states]


def _step_number(states, current):
    for index, state in enumerate(states, start=1):
        if state.pk == current.pk:
            return index
    return 1


def build_panel(attempt, notice=None):
    states = list(attempt.scenario_version.states.all())
    visited = {attempt.current_state.key} | set(attempt.actions.values_list("state_after", flat=True))
    binding = _binding(attempt)
    return GuidePanel(
        attempt=attempt,
        state=attempt.current_state,
        scenario_title=attempt.scenario_version.scenario.title,
        area=attempt.scenario_version.scenario.get_area_display(),
        step_number=_step_number(states, attempt.current_state),
        step_total=len(states),
        task=str(binding.get("task") or "").strip(),
        guidance=str(attempt.current_state.guidance or "") if attempt.assistance_mode in GUIDED_MODES else "",
        stages=_stages(states, attempt.current_state, visited),
        actions=available_actions(attempt),
        workspace_url=reverse("scenario-workspace", args=[attempt.pk]),
        check_url=reverse("scenario-check-step", args=[attempt.pk]),
        hint_url=reverse("scenario-hint", args=[attempt.pk]),
        verification_pending=verification_outstanding(attempt),
        notice=notice,
    )


def guide_panel(request):
    """The panel context for this request, or ``{}`` when there is nothing to show."""
    attempt = active_attempt(request)
    if attempt is None:
        return {}
    return {"guide_panel": build_panel(attempt, notice=take_notice(request, attempt))}


def came_from_panel(request):
    """Whether this request was made by the panel rather than the workspace.

    A flag, not a destination: it only chooses between two server-side
    redirects, both of which are derived from the attempt.
    """
    return request.POST.get("guide") == "1"


def wants_fragment(request):
    return request.headers.get("X-Guide-Panel") == "1"


def return_url(attempt):
    """Where a panel request goes back to: the step's own simulator page."""
    route = _binding(attempt).get("route")
    if route in SIMULATOR_BINDING_ROUTES:
        try:
            return reverse(route)
        except NoReverseMatch:
            pass
    return reverse("scenario-workspace", args=[attempt.pk])


def store_notice(request, attempt, *, kind, message, passed=None):
    """Park a result in the session for the panel to read after a redirect."""
    request.session[GUIDE_NOTICE_KEY] = {
        "attempt": str(attempt.pk),
        "state": attempt.current_state.key,
        "kind": kind,
        "message": message,
        "passed": passed,
    }
    request.session.modified = True


def take_notice(request, attempt):
    """The pending notice for this exact step, consumed once."""
    pending = request.session.get(GUIDE_NOTICE_KEY)
    if not isinstance(pending, dict):
        return None
    if pending.get("attempt") != str(attempt.pk) or pending.get("state") != attempt.current_state.key:
        return None
    del request.session[GUIDE_NOTICE_KEY]
    request.session.modified = True
    return GuideNotice(kind=pending.get("kind", "check"), message=str(pending.get("message") or ""), passed=pending.get("passed"))


def verification_outstanding(attempt):
    """Whether this step declares a simulator task that has not been passed.

    Asked and answered on the server every time: the panel hides the step's
    actions while this is true, and the action endpoint refuses them, so
    collapsing a panel or editing the page cannot walk a student past the work.
    """
    return step_verification_required(attempt.current_state) and step_verified_at(attempt, attempt.current_state) is None


def fragment_response(request, attempt, notice):
    """The panel body on its own, for a check that must not reload the simulator.

    A student mid-declaration keeps their unsaved work: the page is untouched
    and only the panel is replaced.
    """
    panel = build_panel(attempt, notice=notice)
    return HttpResponse(render_to_string("scenarios/_guide_panel_body.html", {"panel": panel}, request=request))
