"""Middleware for guided practice and the development studio frame proof."""

import logging

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotAllowed

from .guides import active_attempt
from .verification import record_step_open, step_opened_at

logger = logging.getLogger(__name__)


class GuidedStepOpenMiddleware:
    """Bound the verification window for a step the student walked straight into.

    The workspace stamped the moment a student clicked "Open simulator step",
    and a check without that stamp falls back to the attempt start — which lets
    a record made for an earlier step pass as new work. Now the panel is on the
    simulator page itself, arriving *is* opening the step, so the stamp is taken
    whenever the page renders for the student who owns the attempt.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == "GET" and response.status_code == 200 and "text/html" in response.get("Content-Type", ""):
            self._stamp(request)
        return response

    @staticmethod
    def _stamp(request):
        attempt = active_attempt(request)
        if attempt is None or step_opened_at(attempt, attempt.current_state) is not None:
            return
        record_step_open(attempt, attempt.current_state)


class DemonstrationFrameSafetyMiddleware:
    """Make instructor-owned simulator iframes read-only in development, and
    record the screens a live demonstration drives (Stage 1C).

    The read-only boundary is deliberately narrow: normal top-level simulator
    requests and every student request are untouched.  An authenticated
    instructor document loaded as an iframe may browse only the approved
    simulator route families and may issue only safe document reads.  On top of
    that boundary sits one best-effort side channel: when a 200 HTML document
    GET names a screen in ``DEMONSTRATION_NAVIGATION_ACTIONS`` and the browser
    holds a live recording, the screen is appended to that recording's
    timeline.  Capture is metadata about the demonstration, never a write to
    simulator content, and it can never alter the response — see
    :func:`_capture_frame_navigation`.
    """

    APPROVED_PATH_PREFIXES = (
        "/practical/portal/",
        "/practical/cargo/",
        "/practical/clearance/",
        "/practical/single-window/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not self._is_development_instructor_frame(request):
            return self.get_response(request)
        if not any(request.path.startswith(prefix) for prefix in self.APPROVED_PATH_PREFIXES):
            return HttpResponseForbidden("This simulator route is not approved for the Demonstration Studio frame.")
        if request.method not in ("GET", "HEAD"):
            return HttpResponseNotAllowed(("GET", "HEAD"))

        request.demonstration_frame_read_only = True
        response = self.get_response(request)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
        response.headers["Cache-Control"] = "no-store"
        _capture_frame_navigation(request, response)
        return response

    @staticmethod
    def _is_development_instructor_frame(request):
        if not settings.DEBUG or not request.path.startswith("/practical/"):
            return False
        if request.headers.get("Sec-Fetch-Dest", "") != "iframe":
            return False
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False
        return bool(
            user.is_staff
            or user.is_superuser
            or user.groups.filter(name__in=("Instructor", "Administrator")).exists()
        )


def _capture_frame_navigation(request, response):
    """Append one navigation event for the approved screen this frame opened.

    Stage 1C. The gate is narrow by construction, so nothing noisy can reach
    here: the frame safety middleware has already admitted only an instructor
    document navigation (``Sec-Fetch-Dest: iframe``) on an approved prefix —
    static assets, fetch lookups, the studio's own polling and top-level
    browsing are all shaped differently and never arrive. On top of that:

    - the response must be a rendered HTML page (a lookup's JSON, a 404 or a
      redirect is not a screen the demonstration visited);
    - the resolved route name must be in ``DEMONSTRATION_NAVIGATION_ACTIONS``
      (the manifest's page set — approved-but-non-page routes never record);
    - ``DEMONSTRATION_RECORDING_ENABLED`` must be on;
    - the browser's server-side binding must resolve to the request user's own
      ``recording`` session — the same resolution every control uses, so a
      paused recording records nothing, a stopped or discarded one has no
      binding left, and a forged binding resolves to nobody.

    The route the recording is already on is not recorded again, so a refresh
    or a double load stays one logical navigation. ``append_navigation_event``
    re-derives every authorization itself and stamps activity with the event's
    sequence reservation. Capture is best-effort by design: a refusal (paused,
    idle, seal) is simply no event, and any unexpected error is logged and
    swallowed — a recording side-channel must never fail a page the instructor
    is looking at.
    """
    if request.method != "GET" or response.status_code != 200:
        return
    if "text/html" not in response.get("Content-Type", ""):
        return
    match = getattr(request, "resolver_match", None)
    route = getattr(match, "url_name", None) if match is not None else None
    from hybrid import demonstrations

    if route not in demonstrations.DEMONSTRATION_NAVIGATION_ACTIONS:
        return
    if not demonstrations.recording_enabled():
        return
    try:
        session = demonstrations.resolve_bound_session(request)
        if session is None or demonstrations.navigation_is_current_screen(session, route):
            return
        demonstrations.append_navigation_event(request, route_name=route)
    except Exception:  # noqa: BLE001 - capture is a side channel, not the page's job
        logger.warning("Demonstration navigation capture skipped for route %s", route, exc_info=True)
