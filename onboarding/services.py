from django.core.exceptions import PermissionDenied

from .models import DisclaimerAcceptance, DisclaimerVersion, Enrolment


def active_enrolment_for(user):
    enrolment = (
        Enrolment.objects.select_related("programme_version__programme")
        .filter(student=user, status=Enrolment.Status.ACTIVE)
        .order_by("enrolled_at")
        .first()
    )
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
