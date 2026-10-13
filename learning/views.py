from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.admin_dashboard import render_student_page
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
    return render_student_page(request, "learning/roadmap.html", {"enrolment": enrolment, "module_summaries": [module_summary(enrolment, module) for module in modules], "theory_completed": programme_theory_completed(enrolment), "final_assessment": final_assessment})


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
    check = lesson.knowledge_checks.select_related("question_version").prefetch_related("question_version__options").first()
    lessons_in_module = [item for item in module.lessons.filter(is_published=True).order_by("order", "title")]

    if request.method == "POST":
        action = request.POST.get("action", "continue")
        if action == "answer_check" and check is not None:
            selected = check.question_version.options.filter(pk=request.POST.get("option")).first()
            if selected is None:
                messages.error(request, "Choose an answer before checking your response.")
            else:
                previous = LessonCheckResponse.objects.filter(enrolment=enrolment, lesson_check=check).aggregate(value=Max("attempt_number"))["value"] or 0
                LessonCheckResponse.objects.create(enrolment=enrolment, lesson_check=check, attempt_number=previous + 1, selected_option=selected, is_correct=selected.is_correct)
                messages.success(request, "Correct. " + check.question_version.explanation if selected.is_correct else "Review this point. " + check.question_version.explanation)
            return redirect(request.path + "#practice")
        # continue: the staged reader is one page, so advancing completes the lesson.
        progress.last_position = max(len(blocks) - 1, 0)
        progress.completed_at = progress.completed_at or timezone.now()
        progress.save(update_fields=("last_position", "completed_at", "updated_at"))
        next_lesson = next((item for item in lessons_in_module if item.order > lesson.order), None)
        if next_lesson:
            return redirect("lesson-detail", module_code=module.code, lesson_slug=next_lesson.slug)
        assessment = module.assessments.filter(is_published=True).first()
        return redirect("assessment-take", assessment_id=assessment.pk) if assessment else redirect("roadmap")

    objectives = [line.strip() for line in (lesson.objectives or "").splitlines() if line.strip()]
    key_terms = []
    for line in (lesson.key_terms or "").splitlines():
        line = line.strip()
        if "::" in line:
            term, definition = line.split("::", 1)
            key_terms.append((term.strip(), definition.strip()))
    word_count = sum(len(block.body.split()) for block in blocks)
    reading_minutes = max(1, round(word_count / 200))
    return render_student_page(
        request,
        "learning/lesson.html",
        {
            "enrolment": enrolment,
            "module": module,
            "lesson": lesson,
            "progress": progress,
            "blocks": blocks,
            "check": check,
            "objectives": objectives,
            "key_terms": key_terms,
            "lessons_in_module": lessons_in_module,
            "reading_minutes": reading_minutes,
            "section_count": len(blocks) + (2 if check else 1),
        },
    )

