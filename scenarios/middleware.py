"""Middleware for guided practice and the development studio frame proof."""

from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponseNotAllowed

from .guides import active_attempt
from .verification import record_step_open, step_opened_at


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
    """Make instructor-owned simulator iframes read-only in development.

    This is deliberately not a recording implementation.  It is the narrow
    safety boundary for the UI 4 integration proof: normal top-level simulator
    requests and every student request are untouched.  An authenticated
    instructor document loaded as an iframe may browse only the approved
    simulator route families and may issue only safe document reads.
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
