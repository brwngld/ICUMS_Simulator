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
def lesson_detail(request, module_code, lesson_slug, section=None):
    """The staged lesson: every section is its own page.

    Sections follow the teaching order - Objectives, Key concepts,
    Worked example, Important note, Practice - and each has a dedicated
    route. Completing the Practice section (or its Continue control)
    completes the lesson; all module, assessment, and exam gates are
    unchanged and enforced server-side.
    """
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
    objectives = [line.strip() for line in (lesson.objectives or "").splitlines() if line.strip()]
    key_terms = []
    for line in (lesson.key_terms or "").splitlines():
        line = line.strip()
        if "::" in line:
            term, definition = line.split("::", 1)
            key_terms.append((term.strip(), definition.strip()))

    # The lesson's section list, in teaching order.
    sections = []
    concept_block = next((b for b in blocks if b.kind == "text"), None)
    example_block = next((b for b in blocks if b.kind == "example"), None)
    notice_block = next((b for b in blocks if b.kind == "notice"), None)
    if objectives:
        sections.append({"slug": "objectives", "title": "Objectives", "stage": "Orient"})
    if concept_block:
        sections.append({"slug": "concepts", "title": concept_block.heading or "Key concepts", "stage": "Learn"})
    if example_block:
        sections.append({"slug": "example", "title": example_block.heading or "Worked example", "stage": "Apply"})
    if notice_block:
        sections.append({"slug": "note", "title": notice_block.heading or "Important note", "stage": "Remember"})
    if check:
        sections.append({"slug": "practice", "title": "Practice", "stage": "Practise"})
    if not sections:
        sections.append({"slug": "concepts", "title": "Lesson", "stage": "Learn"})

    def section_url(slug):
        return reverse("lesson-section", args=(module.code, lesson.slug, slug))

    current_index = next((index for index, item in enumerate(sections) if item["slug"] == section), None)
    if current_index is None:
        # no/unknown section: resume at the first unvisited page (or Practice when done)
        resume_index = min(progress.last_position or 0, len(sections) - 1)
        if request.method == "GET":
            return redirect(section_url(sections[resume_index]["slug"]))
        current_index = resume_index

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
            return redirect(section_url("practice") + "#feedback")
        # continue: advance to the next section; the last section completes the lesson.
        if current_index < len(sections) - 1:
            progress.last_position = max(progress.last_position or 0, current_index + 1)
            progress.save(update_fields=("last_position", "updated_at"))
            return redirect(section_url(sections[current_index + 1]["slug"]))
        progress.last_position = len(sections) - 1
        progress.completed_at = progress.completed_at or timezone.now()
        progress.save(update_fields=("last_position", "completed_at", "updated_at"))
        lessons_in_module = list(module.lessons.filter(is_published=True).order_by("order", "title"))
        next_lesson = next((item for item in lessons_in_module if item.order > lesson.order), None)
        if next_lesson:
            return redirect("lesson-detail", module_code=module.code, lesson_slug=next_lesson.slug)
        assessment = module.assessments.filter(is_published=True).first()
        return redirect("assessment-take", assessment_id=assessment.pk) if assessment else redirect("roadmap")

    progress.last_position = max(progress.last_position or 0, current_index)
    progress.save(update_fields=("last_position", "updated_at"))
    for index, item in enumerate(sections):
        item["url"] = section_url(item["slug"])
        item["index"] = index
        item["state"] = "done" if index < current_index or progress.completed_at else ("current" if index == current_index else "todo")
    word_count = sum(len(block.body.split()) for block in blocks)
    module_assessment = module.assessments.filter(is_published=True).first()
    return render_student_page(
        request,
        "learning/lesson.html",
        {
            "enrolment": enrolment,
            "module": module,
            "lesson": lesson,
            "progress": progress,
            "sections": sections,
            "current_index": current_index,
            "current_section": sections[current_index],
            "prev_section": sections[current_index - 1] if current_index > 0 else None,
            "next_section": sections[current_index + 1] if current_index < len(sections) - 1 else None,
            "concept_block": concept_block,
            "example_block": example_block,
            "notice_block": notice_block,
            "check": check,
            "objectives": objectives,
            "key_terms": key_terms,
            "lessons_in_module": list(module.lessons.filter(is_published=True).order_by("order", "title")),
            "module_assessment": module_assessment,
            "reading_minutes": max(1, round(word_count / 200)),
        },
    )
