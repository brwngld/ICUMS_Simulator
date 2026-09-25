from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from scenarios.models import ConsignmentApplication

from .models import Assessment
from .service import refresh_assessment


def _can_review(request, application) -> bool:
    return request.user.is_staff or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()


@login_required
def assessment_detail(request, application_id):
    application = get_object_or_404(ConsignmentApplication.objects.select_related("ucr"), pk=application_id)
    if application.owner_id != request.user.pk and not _can_review(request, application):
        raise PermissionDenied("This application belongs to another learner.")
    if application.status != ConsignmentApplication.Status.SUBMITTED and application.owner_id == request.user.pk:
        messages.info(request, "The assessment becomes final once the application is submitted; values shown are from the saved draft.")
    assessment = refresh_assessment(application)
    return render(request, "assessment/detail.html", {
        "application": application,
        "assessment": assessment,
        "review_mode": application.owner_id != request.user.pk,
    })
