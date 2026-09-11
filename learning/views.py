from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from onboarding.services import active_enrolment_for, needs_disclaimer_acceptance
from progress.models import LessonProgress, ModuleProgress
from assessments.models import Assessment, LessonCheck, LessonCheckResponse

from .models import Lesson, Module
from .services import module_is_unlocked, module_summary, programme_theory_completed


def _guard_onboarding(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    return None


@login_required
def roadmap(request):
    if response := _guard_onboarding(request):
        return response
    if not request.user.enrolments.filter(status="active").exists() and (
        request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    ):
        return redirect(f'{reverse("course-builder")}?path=theory')
    enrolment = active_enrolment_for(request.user)
    modules = Module.objects.filter(programme_version=enrolment.programme_version, is_published=True)
    final_assessment = Assessment.objects.filter(programme_version=enrolment.programme_version, assessment_type=Assessment.Type.FINAL_THEORY, is_published=True).first()
    return render(request, "learning/roadmap.html", {"enrolment": enrolment, "module_summaries": [module_summary(enrolment, module) for module in modules], "theory_completed": programme_theory_completed(enrolment), "final_assessment": final_assessment})


@login_required
@require_http_methods(["GET", "POST"])
def lesson_detail(request, module_code, lesson_slug):
    if response := _guard_onboarding(request):
        return response
    enrolment = active_enrolment_for(request.user)
    module = get_object_or_404(Module, programme_version=enrolment.programme_version, code=module_code, is_published=True)
    if not module_is_unlocked(enrolment, module):
        raise PermissionDenied("Complete the prerequisite module first.")
    lesson = get_object_or_404(Lesson, module=module, slug=lesson_slug, is_published=True)
    progress, _ = LessonProgress.objects.get_or_create(enrolment=enrolment, lesson=lesson)
    ModuleProgress.objects.get_or_create(enrolment=enrolment, module=module, defaults={"status": ModuleProgress.Status.IN_PROGRESS})
    blocks = list(lesson.blocks.all())
    requested_position = request.GET.get("step")
    try:
        position = int(requested_position) if requested_position is not None else progress.last_position
    except (TypeError, ValueError):
        position = progress.last_position
    position = min(max(position, 0), max(len(blocks) - 1, 0))
    current_block = blocks[position] if blocks else None
    if request.method == "POST":
        action = request.POST.get("action", "continue")
        try:
            posted_position = int(request.POST.get("position", position))
        except (TypeError, ValueError):
            posted_position = position
        posted_position = min(max(posted_position, 0), max(len(blocks) - 1, 0))
        if action == "answer_check":
            lesson_check = get_object_or_404(LessonCheck, pk=request.POST.get("check_id"), lesson=lesson)
            selected = lesson_check.question_version.options.filter(pk=request.POST.get("option")).first()
            if selected is None:
                messages.error(request, "Choose an answer before checking your response.")
            else:
                previous = LessonCheckResponse.objects.filter(enrolment=enrolment, lesson_check=lesson_check).aggregate(value=Max("attempt_number"))["value"] or 0
                LessonCheckResponse.objects.create(enrolment=enrolment, lesson_check=lesson_check, attempt_number=previous + 1, selected_option=selected, is_correct=selected.is_correct)
                messages.success(request, "Correct. " + lesson_check.question_version.explanation if selected.is_correct else "Review this point. " + lesson_check.question_version.explanation)
            return redirect(f"{request.path}?step={posted_position}")
        progress.last_position = max(progress.last_position, posted_position)
        if blocks and posted_position < len(blocks) - 1:
            progress.save(update_fields=("last_position", "updated_at"))
            return redirect(f"{request.path}?step={posted_position + 1}")
        progress.last_position = max(len(blocks) - 1, 0)
        progress.completed_at = progress.completed_at or timezone.now()
        progress.save(update_fields=("last_position", "completed_at", "updated_at"))
        next_lesson = module.lessons.filter(is_published=True, order__gt=lesson.order).first()
        if next_lesson:
            return redirect("lesson-detail", module_code=module.code, lesson_slug=next_lesson.slug)
        assessment = module.assessments.filter(is_published=True).first()
        return redirect("assessment-take", assessment_id=assessment.pk) if assessment else redirect("roadmap")
    checks = current_block.knowledge_checks.select_related("question_version").prefetch_related("question_version__options") if current_block else []
    return render(request, "learning/lesson.html", {"enrolment": enrolment, "module": module, "lesson": lesson, "progress": progress, "current_block": current_block, "position": position, "step_number": position + 1, "step_count": len(blocks), "checks": checks})
