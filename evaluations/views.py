from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import PracticalEvaluation
from .services import add_feedback, revise_outcome


def _is_instructor(user):
    return user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()


@login_required
def evaluation_detail(request, evaluation_id):
    evaluation = get_object_or_404(
        PracticalEvaluation.objects.select_related("attempt__enrolment__student", "attempt__scenario_version__scenario", "rubric_version").prefetch_related(
            "criterion_results__criterion",
            "remediation_recommendations__resource",
            "remediation_recommendations__scenario_version__scenario",
            "revisions__instructor",
            "attempt__instructor_feedback__instructor",
        ),
        pk=evaluation_id,
    )
    if evaluation.attempt.enrolment.student_id != request.user.pk and not _is_instructor(request.user):
        raise PermissionDenied("You cannot view this evaluation.")
    instructor_view = _is_instructor(request.user)
    feedback = evaluation.attempt.instructor_feedback.all() if instructor_view else evaluation.attempt.instructor_feedback.filter(visible_to_student=True)
    return render(request, "evaluations/detail.html", {"evaluation": evaluation, "instructor_view": instructor_view, "feedback": feedback})


@login_required
@require_POST
def evaluation_override(request, evaluation_id):
    evaluation = get_object_or_404(PracticalEvaluation, pk=evaluation_id)
    try:
        revise_outcome(evaluation, request.user, request.POST.get("outcome", ""), request.POST.get("reason", ""), request.META.get("REMOTE_ADDR"))
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(request, "The revised outcome was recorded without changing the original system evaluation.")
    return redirect("practical-evaluation", evaluation_id=evaluation.pk)


@login_required
@require_POST
def evaluation_feedback(request, evaluation_id):
    evaluation = get_object_or_404(PracticalEvaluation.objects.select_related("attempt"), pk=evaluation_id)
    try:
        add_feedback(evaluation.attempt, request.user, request.POST.get("body", ""), request.POST.get("visible_to_student") == "yes")
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    else:
        messages.success(request, "Feedback recorded.")
    return redirect("practical-evaluation", evaluation_id=evaluation.pk)
