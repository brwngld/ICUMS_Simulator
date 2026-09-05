from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditEvent


def _client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user,
        action_code="account.login",
        target_type="user",
        target_id=str(user.pk),
        summary="User signed in.",
        ip_address=_client_ip(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs):
    AuditEvent.objects.create(
        actor=user if getattr(user, "is_authenticated", False) else None,
        action_code="account.logout",
        target_type="user" if user else "",
        target_id=str(user.pk) if user else "",
        summary="User signed out.",
        ip_address=_client_ip(request),
    )
