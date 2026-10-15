from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from django.views.decorators.http import require_http_methods

from core.admin_dashboard import render_student_page

from learning.services import (
    locked_module_message,
    module_is_locked,
    module_is_unlocked,
    module_lessons_completed,
    programme_theory_completed,
)
from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance

from .models import Assessment, TheoryAttempt
from progress.models import LessonProgress
from .services import get_or_start_attempt, save_attempt_answers, submit_attempt


def _safe_return_to(request):
    value = request.POST.get("return_to") or request.GET.get("return_to")
    if value and url_has_allowed_host_and_scheme(value, {request.get_host()}, require_https=request.is_secure()):
        return value
    return reverse("roadmap")


@login_required
@require_http_methods(["GET", "POST"])
def assessment_take(request, assessment_id):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    enrolment = active_enrolment_for(request.user)
    assessment = get_object_or_404(Assessment.objects.prefetch_related("items__question_version__options"), pk=assessment_id, is_published=True)
    if assessment.programme_version_id != enrolment.programme_version_id:
        raise PermissionDenied("This assessment is not available.")
    if assessment.module and module_is_locked(enrolment, assessment.module):
        raise PermissionDenied(locked_module_message(assessment.module))
    if assessment.module and (
        not module_is_unlocked(enrolment, assessment.module)
        or not module_lessons_completed(enrolment, assessment.module)
    ):
        raise PermissionDenied("This assessment is not available.")
    if assessment.assessment_type == Assessment.Type.FINAL_THEORY and not programme_theory_completed(enrolment):
        raise PermissionDenied("Complete all theory modules before starting the final theory examination.")
    attempt = get_or_start_attempt(enrolment, assessment)
    return_to = _safe_return_to(request)
    remaining_attempts = (
        max(assessment.maximum_attempts - attempt.attempt_number, 0)
        if assessment.maximum_attempts is not None else None
    )
    assessment_description = (
        assessment.module.description
        if assessment.module and assessment.module.description
        else "Use this assessment to demonstrate your understanding of the module content."
    )
    if request.method == "POST":
        if request.POST.get("action") == "save_progress":
            save_attempt_answers(attempt, request.POST)
            return HttpResponse(status=204)
        attempt = submit_attempt(attempt, request.POST)
        result_url = reverse("assessment-result", args=(attempt.pk,))
        return redirect(f"{result_url}?{urlencode({'return_to': return_to})}")
    saved_answers = {
        response.question_version_id: response.selected_option_id
        for response in attempt.responses.filter(selected_option__isnull=False)
    }
    for item in attempt.items.all():
        item.saved_option_id = saved_answers.get(item.question_version_id)
    return render_student_page(
        request,
        "assessments/take.html",
        {
            "assessment": assessment,
            "attempt": attempt,
            "return_to": return_to,
            "saved_answers": saved_answers,
            "remaining_attempts": remaining_attempts,
            "attempts_limited": assessment.maximum_attempts is not None,
            "assessment_description": assessment_description,
        },
    )


@login_required
def assessment_result(request, attempt_id):
    attempt = get_object_or_404(
        TheoryAttempt.objects.select_related("assessment", "enrolment__programme_version", "enrolment").prefetch_related("responses__question_version__remediation_resource", "items__question_version__options"),
        pk=attempt_id,
        enrolment__student=request.user,
    )
    assessment = attempt.assessment
    passed = attempt.outcome == TheoryAttempt.Outcome.PASS
    retake_allowed = assessment.maximum_attempts is None or attempt.attempt_number < assessment.maximum_attempts
    remaining_attempts = (
        max(assessment.maximum_attempts - attempt.attempt_number, 0)
        if assessment.maximum_attempts is not None else None
    )
    return_to = _safe_return_to(request)

    # Where "continue" goes after a pass: the next unfinished lesson, the
    # module's later content, orientation after the final exam, or the roadmap.
    continue_url = reverse("roadmap")
    continue_label = "Return to roadmap"
    if passed:
        enrolment = attempt.enrolment
        if assessment.assessment_type == Assessment.Type.FINAL_THEORY:
            continue_url = reverse("orientation")
            continue_label = "Continue to simulator orientation"
        elif assessment.module:
            module = assessment.module
            lessons = list(module.lessons.filter(is_published=True).order_by("order", "title"))
            next_lesson = next((lesson for lesson in lessons if not LessonProgress.objects.filter(enrolment=enrolment, lesson=lesson, completed_at__isnull=False).exists()), None)
            if next_lesson:
                continue_url = reverse("lesson-detail", args=(module.code, next_lesson.slug))
                continue_label = "Continue to the next lesson"

    # Per-question review aligned with the attempt's frozen question order.
    responses_by_question = {response.question_version_id: response for response in attempt.responses.all()}
    review = []
    for item in attempt.items.select_related("question_version").order_by("order", "id"):
        response = responses_by_question.get(item.question_version_id)
        review.append({
            "question": item.question_version,
            "response": response,
            "chosen": response.selected_option if response else None,
            "correct": item.question_version.options.filter(is_correct=True).first(),
        })
    return render_student_page(
        request,
        "assessments/result.html",
        {
            "attempt": attempt,
            "passed": passed,
            "pass_mark": assessment.pass_percentage,
            "retake_allowed": retake_allowed,
            "continue_url": continue_url,
            "continue_label": continue_label,
            "return_to": return_to,
            "remaining_attempts": remaining_attempts,
            "attempts_limited": assessment.maximum_attempts is not None,
            "review": review,
        },
    )
