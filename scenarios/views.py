from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance

from .models import ScenarioActionDefinition, ScenarioAttempt, ScenarioVersion
from .services import available_actions, perform_action, practical_is_unlocked, record_hint, start_or_resume_attempt


def _enrolment_with_access(request):
    if needs_disclaimer_acceptance(request.user):
        return None, redirect("disclaimer")
    enrolment = active_enrolment_for(request.user)
    if not practical_is_unlocked(enrolment):
        raise PermissionDenied("Complete simulator orientation before beginning practical training.")
    return enrolment, None


@login_required
def scenario_list(request):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    versions = ScenarioVersion.objects.filter(status=ScenarioVersion.Status.PUBLISHED).select_related("scenario")
    attempts = {attempt.scenario_version_id: attempt for attempt in ScenarioAttempt.objects.filter(enrolment=enrolment, status=ScenarioAttempt.Status.IN_PROGRESS)}
    return render(request, "scenarios/list.html", {"scenario_versions": versions, "attempts": attempts})


@login_required
def scenario_detail(request, version_id):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    version = get_object_or_404(ScenarioVersion.objects.select_related("scenario"), pk=version_id, status=ScenarioVersion.Status.PUBLISHED)
    active_attempt = ScenarioAttempt.objects.filter(enrolment=enrolment, scenario_version=version, status=ScenarioAttempt.Status.IN_PROGRESS).first()
    return render(request, "scenarios/detail.html", {"scenario_version": version, "active_attempt": active_attempt})


@login_required
@require_POST
def scenario_start(request, version_id):
    enrolment, response = _enrolment_with_access(request)
    if response:
        return response
    version = get_object_or_404(ScenarioVersion, pk=version_id, status=ScenarioVersion.Status.PUBLISHED)
    attempt, created = start_or_resume_attempt(enrolment, version)
    messages.success(request, "Scenario started." if created else "Your saved scenario has been resumed.")
    return redirect("scenario-workspace", attempt_id=attempt.pk)


@login_required
def scenario_workspace(request, attempt_id):
    attempt = get_object_or_404(
        ScenarioAttempt.objects.select_related("enrolment", "scenario_version__scenario", "current_state").prefetch_related("scenario_version__documents", "actions"),
        pk=attempt_id,
        enrolment__student=request.user,
    )
    return render(request, "scenarios/workspace.html", {"attempt": attempt, "available_actions": available_actions(attempt)})


@login_required
@require_POST
def scenario_action(request, attempt_id, action_id):
    attempt = get_object_or_404(ScenarioAttempt, pk=attempt_id, enrolment__student=request.user)
    action = get_object_or_404(ScenarioActionDefinition, pk=action_id)
    try:
        updated = perform_action(attempt, action)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scenario-workspace", attempt_id=attempt.pk)
    if action.success_feedback:
        messages.success(request, action.success_feedback)
    return redirect("scenario-workspace", attempt_id=updated.pk)


@login_required
@require_POST
def scenario_hint(request, attempt_id):
    attempt = get_object_or_404(ScenarioAttempt.objects.select_related("current_state", "scenario_version"), pk=attempt_id, enrolment__student=request.user)
    hint = record_hint(attempt)
    messages.info(request, hint)
    return redirect("scenario-workspace", attempt_id=attempt.pk)
