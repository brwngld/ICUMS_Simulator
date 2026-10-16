from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied

from .models import DisclaimerAcceptance, DisclaimerVersion, Enrolment


def active_enrolments(user):
    """Every enrolment a learner may open, oldest first.

    ``pk`` breaks ties because ``enrolled_at`` is not unique and an unordered
    query can pick a different row page to page.
    """
    return (
        Enrolment.objects.select_related("programme_version__programme")
        .filter(student=user, status=Enrolment.Status.ACTIVE)
        .order_by("enrolled_at", "pk")
    )


def requested_enrolment(request):
    """The enrolment ``?programme=<code>`` selects, or ``None``.

    With no parameter it falls back to the oldest active enrolment, so every
    existing link and bookmark keeps working. Two enrolments for the same
    programme (different versions) resolve to the oldest, because the parameter
    names a programme.
    """
    code = request.GET.get("programme")
    if not code:
        return active_enrolments(request.user).first()
    return active_enrolments(request.user).filter(programme_version__programme__code=code).first()


def enrolment_for_request(request):
    """The enrolment a student page renders on, or a 403 for a page that needs one."""
    enrolment = requested_enrolment(request)
    if enrolment is None:
        raise PermissionDenied(
            "You are not enrolled in that programme." if request.GET.get("programme")
            else "No active programme enrolment was found."
        )
    return enrolment


def programme_href(url, enrolment):
    """Keep a generated link on the programme the learner is working through.

    The parameter only appears once a learner has more than one active
    enrolment to choose between, so a single-programme learner keeps the plain
    URLs the portal has always produced. The answer is cached on the enrolment
    instance because a page builds many links.
    """
    code = _switchable_programme_code(enrolment)
    if not code:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'programme': code})}"


def programme_param(enrolment):
    """The ``?programme=<code>`` suffix for a link a template builds itself.

    Practical pages write their hrefs with a url tag rather than in python, so
    they need the piece instead of a whole url. It is empty for a learner with
    nothing to choose between and only ever lands on paths that carry no query
    string of their own.
    """
    code = _switchable_programme_code(enrolment)
    return f"?{urlencode({'programme': code})}" if code else ""


def _switchable_programme_code(enrolment):
    if enrolment is None:
        return ""
    if not hasattr(enrolment, "_programme_switchable"):
        enrolment._programme_switchable = (
            Enrolment.objects.filter(
                student_id=enrolment.student_id, status=Enrolment.Status.ACTIVE
            ).count() > 1
        )
    return enrolment.programme_version.programme.code if enrolment._programme_switchable else ""


def current_disclaimer():
    return DisclaimerVersion.objects.filter(is_current=True).order_by("-version").first()


def needs_disclaimer_acceptance(user):
    disclaimer = current_disclaimer()
    if disclaimer is None:
        return False
    return not DisclaimerAcceptance.objects.filter(user=user, disclaimer=disclaimer).exists()
