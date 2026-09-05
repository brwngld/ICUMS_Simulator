from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from audit.models import AuditEvent

from .models import DisclaimerAcceptance
from .services import current_disclaimer


@login_required
@require_http_methods(["GET", "POST"])
def disclaimer(request):
    active_disclaimer = current_disclaimer()
    if active_disclaimer is None:
        return redirect("dashboard")
    if DisclaimerAcceptance.objects.filter(user=request.user, disclaimer=active_disclaimer).exists():
        return redirect("dashboard")
    if request.method == "POST" and request.POST.get("accept") == "yes":
        with transaction.atomic():
            DisclaimerAcceptance.objects.get_or_create(user=request.user, disclaimer=active_disclaimer)
            AuditEvent.objects.create(
                actor=request.user,
                action_code="disclaimer.accepted",
                target_type="disclaimer",
                target_id=str(active_disclaimer.pk),
                summary=f"Accepted disclaimer version {active_disclaimer.version}.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        return redirect("dashboard")
    return render(request, "onboarding/disclaimer.html", {"disclaimer": active_disclaimer})
