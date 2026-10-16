"""Middleware for the guided-practice flow."""

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
