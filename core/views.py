from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from audit.models import AuditEvent
from assessments.models import Assessment
from learning.models import Module
from learning.services import module_summary
from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance
from progress.models import ProgrammeProgress
from reports.models import CompletionRecord
from accounts.models import SimulatorCredential


@login_required
def dashboard(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    role_names = set(request.user.groups.values_list("name", flat=True))
    enrolment = request.user.enrolments.filter(status="active").select_related("programme_version__programme").first()
    summaries = []
    if enrolment:
        modules = Module.objects.filter(programme_version=enrolment.programme_version, is_published=True)
        summaries = [module_summary(enrolment, module) for module in modules]
    final_assessment = Assessment.objects.filter(programme_version=enrolment.programme_version, assessment_type=Assessment.Type.FINAL_THEORY, is_published=True).first() if enrolment else None
    programme_progress = ProgrammeProgress.objects.filter(enrolment=enrolment).first() if enrolment else None
    completion_record = CompletionRecord.objects.filter(enrolment=enrolment).first() if enrolment else None
    simulator_credential = SimulatorCredential.objects.filter(user=request.user).first()
    return render(request, "core/dashboard.html", {"role_names": role_names, "enrolment": enrolment, "module_summaries": summaries, "programme_progress": programme_progress, "final_assessment": final_assessment, "completion_record": completion_record, "simulator_credential": simulator_credential})


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
