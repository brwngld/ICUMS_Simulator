from django.core.exceptions import PermissionDenied

from .models import DisclaimerAcceptance, DisclaimerVersion, Enrolment


def current_enrolment(user):
    """The single enrolment a student surface should read, or ``None``.

    A learner may hold several active enrolments but the portal has no way to
    choose between them yet, so every surface must resolve the same one:
    oldest first, with ``pk`` breaking ties because ``enrolled_at`` is not
    unique and an unordered query can disagree page to page.
    """
    return (
        Enrolment.objects.select_related("programme_version__programme")
        .filter(student=user, status=Enrolment.Status.ACTIVE)
        .order_by("enrolled_at", "pk")
        .first()
    )


def active_enrolment_for(user):
    enrolment = current_enrolment(user)
    if enrolment is None:
        raise PermissionDenied("No active programme enrolment was found.")
    return enrolment


def current_disclaimer():
    return DisclaimerVersion.objects.filter(is_current=True).order_by("-version").first()


def needs_disclaimer_acceptance(user):
    disclaimer = current_disclaimer()
    if disclaimer is None:
        return False
    return not DisclaimerAcceptance.objects.filter(user=user, disclaimer=disclaimer).exists()
