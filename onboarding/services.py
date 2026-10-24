from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied

from .models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme


def active_enrolments(user, track=None):
    """Every enrolment a learner may open, oldest first.

    ``pk`` breaks ties because ``enrolled_at`` is not unique and an unordered
    query can pick a different row page to page. A reader without a learning
    account has none: ``student`` is keyed on the UUID primary key, so asking
    for an enrolment of ``AnonymousUser`` is a type error rather than an empty
    list, and the pages that answer before sign-in would fault instead of
    offering the way in.

    ``track`` narrows the answer to one learning track (a ``Programme.Track``
    value). Listing surfaces such as My Programmes leave it off so a learner
    sees every programme they are enrolled on; a page that belongs to one
    learning system passes its track so it can never resolve the other
    system's enrolment.
    """
    if not user.is_authenticated:
        return Enrolment.objects.none()
    enrolments = (
        Enrolment.objects.select_related("programme_version__programme")
        .filter(student=user, status=Enrolment.Status.ACTIVE)
        .order_by("enrolled_at", "pk")
    )
    if track is not None:
        enrolments = enrolments.filter(programme_version__programme__learning_track=track)
    return enrolments


def requested_enrolment(request, track=Programme.Track.THEORY):
    """The enrolment ``?programme=<code>`` selects, or ``None``.

    Routes default to the theory track because every route that existed before
    the hybrid system belongs to it; the hybrid app passes its own track
    explicitly. The fallback is the oldest active enrolment *on that track*, so
    a Theory & Practical enrolment can never hijack a theory page by being the
    older one, and the reverse holds for hybrid pages. With no parameter every
    existing link and bookmark keeps working. Two enrolments for the same
    programme (different versions) resolve to the oldest, because the parameter
    names a programme. A parameter naming a programme of the wrong track
    selects nothing, exactly like a programme the learner is not enrolled in.
    """
    code = request.GET.get("programme")
    if not code:
        return active_enrolments(request.user, track=track).first()
    return active_enrolments(request.user, track=track).filter(programme_version__programme__code=code).first()


def enrolment_for_request(request, track=Programme.Track.THEORY):
    """The enrolment a student page renders on, or a 403 for a page that needs one."""
    enrolment = requested_enrolment(request, track=track)
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
