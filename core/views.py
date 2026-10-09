from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from audit.models import AuditEvent
from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance
from progress.models import ProgrammeProgress
from accounts.models import SimulatorCredential
from .admin_dashboard import dashboard_callback


@login_required
def dashboard(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    context = {"role_names": set(request.user.groups.values_list("name", flat=True)), "simulator_credential": SimulatorCredential.objects.filter(user=request.user).first()}
    return render(request, "core/dashboard_unfold.html", admin.site.each_context(request) | context)


@login_required
@require_http_methods(["GET", "POST"])
def orientation(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = active_enrolment_for(request.user)
    programme_progress = ProgrammeProgress.objects.filter(enrolment=enrolment, orientation_unlocked_at__isnull=False).first()
    if programme_progress is None:
        raise PermissionDenied("Pass the final theory examination before starting orientation.")
    if request.method == "POST" and programme_progress.orientation_completed_at is None:
        with transaction.atomic():
            programme_progress.orientation_completed_at = timezone.now()
            programme_progress.save(update_fields=("orientation_completed_at", "updated_at"))
            AuditEvent.objects.create(
                actor=request.user,
                action_code="orientation.completed",
                target_type="enrolment",
                target_id=str(enrolment.pk),
                summary="Completed simulator orientation.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )
        return redirect("dashboard")
    return render(request, "core/orientation.html", {"programme_progress": programme_progress})
