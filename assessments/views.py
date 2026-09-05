from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from learning.services import module_is_unlocked, module_lessons_completed, programme_theory_completed
from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance

from .models import Assessment, TheoryAttempt
from .services import get_or_start_attempt, submit_attempt


@login_required
@require_http_methods(["GET", "POST"])
def assessment_take(request, assessment_id):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = active_enrolment_for(request.user)
    assessment = get_object_or_404(Assessment.objects.prefetch_related("items__question_version__options"), pk=assessment_id, is_published=True)
    if assessment.programme_version_id != enrolment.programme_version_id:
        raise PermissionDenied("This assessment is not available.")
    if assessment.module and (
        not module_is_unlocked(enrolment, assessment.module)
        or not module_lessons_completed(enrolment, assessment.module)
    ):
        raise PermissionDenied("This assessment is not available.")
    if assessment.assessment_type == Assessment.Type.FINAL_THEORY and not programme_theory_completed(enrolment):
        raise PermissionDenied("Complete all theory modules before starting the final theory examination.")
    attempt = get_or_start_attempt(enrolment, assessment)
    if request.method == "POST":
        attempt = submit_attempt(attempt, request.POST)
        return redirect("assessment-result", attempt_id=attempt.pk)
    return render(request, "assessments/take.html", {"assessment": assessment, "attempt": attempt})


@login_required
def assessment_result(request, attempt_id):
    attempt = get_object_or_404(
        TheoryAttempt.objects.select_related("assessment", "enrolment").prefetch_related("responses__question_version__remediation_resource"),
        pk=attempt_id,
        enrolment__student=request.user,
    )
    return render(request, "assessments/result.html", {"attempt": attempt})
