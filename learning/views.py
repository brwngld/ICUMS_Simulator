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
from assessments.models import Assessment, LessonCheck, LessonCheckResponse, TheoryAttempt

from .models import Lesson, Module
from .services import module_is_unlocked, module_lessons_completed, programme_theory_completed


def _guard_onboarding(request):
    if needs_disclaimer_acceptance(request.user):
        return redirect("disclaimer")
    return None


def _lesson_sections():
    return [
        {"slug": "objectives", "title": "Introduction", "stage": "Start"},
        {"slug": "concepts", "title": "Key concepts", "stage": "Learn"},
        {"slug": "example", "title": "Worked example", "stage": "Apply"},
        {"slug": "note", "title": "Important note", "stage": "Remember"},
        {"slug": "practice", "title": "Practice", "stage": "Practise"},
    ]


def _resolve_current_section(sections, progress, requested_section):
    current_index = next((index for index, item in enumerate(sections) if item["slug"] == requested_section), None)
    if current_index is not None:
        furthest_available = len(sections) - 1 if progress.completed_at else min(progress.last_position, len(sections) - 1)
        return (furthest_available, True) if current_index > furthest_available else (current_index, False)

    resume_index = min(progress.last_position or 0, len(sections) - 1)
    return resume_index, True


def _annotate_sections(sections, section_url, progress, current_index):
    for index, item in enumerate(sections):
        item["url"] = section_url(item["slug"])
        item["index"] = index
        if progress.completed_at or index < progress.last_position:
            item["state"] = "done"
        elif index == current_index:
            item["state"] = "current"
        elif index == progress.last_position:
            item["state"] = "available"
        else:
            item["state"] = "locked"


@login_required
def module_overview(request, module_code):
    if response := _guard_onboarding(request):
        return response
    enrolment = active_enrolment_for(request.user)
    module = get_object_or_404(
        Module.objects.select_related("programme_version__programme").prefetch_related(
            "lessons__blocks", "lessons__resources", "assessments"
        ),
        programme_version=enrolment.programme_version,
        code=module_code,
        is_published=True,
    )
    if not module_is_unlocked(enrolment, module):
        raise PermissionDenied("Complete the prerequisite module first.")

    lessons = list(module.lessons.filter(is_published=True).order_by("order", "title"))
    progress_by_lesson = {
        item.lesson_id: item
        for item in LessonProgress.objects.filter(enrolment=enrolment, lesson__in=lessons)
    }
    lesson_items = []
    objectives = []
    resources = []
    resource_ids = set()
    next_lesson = None
    total_minutes = 0
    completed_count = 0
    for lesson in lessons:
        progress = progress_by_lesson.get(lesson.pk)
        status = "completed" if progress and progress.completed_at else "in_progress" if progress else "not_started"
        completed_count += status == "completed"
        words = sum(len(block.body.split()) for block in lesson.blocks.all())
        minutes = max(1, round(words / 200))
        total_minutes += minutes
        lesson_items.append({"lesson": lesson, "progress": progress, "status": status, "minutes": minutes})
        if next_lesson is None and status != "completed":
            next_lesson = lesson
        for line in (lesson.objectives or "").splitlines():
            value = line.strip()
            if value and value not in objectives:
                objectives.append(value)
        for resource in lesson.resources.all():
            if resource.pk not in resource_ids:
                resource_ids.add(resource.pk)
                resources.append(resource)

    assessment = module.assessments.filter(is_published=True).first()
    attempts = TheoryAttempt.objects.filter(
        enrolment=enrolment, assessment=assessment, status=TheoryAttempt.Status.SUBMITTED
    ).order_by("-percentage", "-submitted_at") if assessment else TheoryAttempt.objects.none()
    best_attempt = attempts.first()
    attempt_count = attempts.count()
    lessons_complete = bool(lessons) and completed_count == len(lessons)
    attempts_remaining = None
    if assessment and assessment.maximum_attempts is not None:
        attempts_remaining = max(assessment.maximum_attempts - attempt_count, 0)
    can_attempt = bool(assessment and lessons_complete and (attempts_remaining is None or attempts_remaining > 0))
    assessment_passed = bool(best_attempt and best_attempt.outcome == TheoryAttempt.Outcome.PASS)
    progress_percentage = round(completed_count / len(lessons) * 100) if lessons else 0

    return render_student_page(request, "learning/module_overview.html", {
        "enrolment": enrolment,
        "module": module,
        "lesson_items": lesson_items,
        "objectives": objectives,
        "resources": resources,
        "assessment": assessment,
        "best_attempt": best_attempt,
        "attempt_count": attempt_count,
        "attempts_remaining": attempts_remaining,
        "can_attempt": can_attempt,
        "assessment_passed": assessment_passed,
        "lessons_complete": lessons_complete,
        "next_lesson": next_lesson,
        "completed_count": completed_count,
        "progress_percentage": progress_percentage,
        "total_minutes": total_minutes,
    })


@login_required
def roadmap(request):
    if response := _guard_onboarding(request):
        return response
    if not request.user.enrolments.filter(status="active").exists() and (
        request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    ):
        return redirect(f'{reverse("course-builder")}?path=theory')
    enrolment = active_enrolment_for(request.user)
    modules = list(
        Module.objects.filter(programme_version=enrolment.programme_version, is_published=True)
        .prefetch_related("lessons__blocks", "lessons__resources", "assessments")
        .order_by("order", "title")
    )
    final_assessment = Assessment.objects.filter(programme_version=enrolment.programme_version, assessment_type=Assessment.Type.FINAL_THEORY, is_published=True).first()
    progress_by_lesson = {
        item.lesson_id: item
        for item in LessonProgress.objects.filter(enrolment=enrolment, lesson__module__in=modules)
    }
    best_attempts = {}
    for attempt in (
        TheoryAttempt.objects.filter(enrolment=enrolment, status=TheoryAttempt.Status.SUBMITTED, assessment__module__in=modules)
        .select_related("assessment")
        .order_by("assessment_id", "-percentage")
    ):
        best_attempts.setdefault(attempt.assessment_id, attempt)

    module_cards = []
    counts = {"completed": 0, "in_progress": 0, "not_started": 0}
    next_lesson = None
    total_minutes = 0
    outcomes = []
    resources = []
    resource_ids = set()
    for module in modules:
        lessons = list(module.lessons.filter(is_published=True).order_by("order", "title"))
        unlocked = module_is_unlocked(enrolment, module)
        lesson_cards = []
        completed = 0
        module_minutes = 0
        for lesson in lessons:
            progress = progress_by_lesson.get(lesson.pk)
            status = "completed" if progress and progress.completed_at else "in_progress" if progress else "not_started"
            counts[status] += 1
            completed += status == "completed"
            words = sum(len(block.body.split()) for block in lesson.blocks.all())
            minutes = max(1, round(words / 200))
            module_minutes += minutes
            lesson_cards.append({"lesson": lesson, "status": status, "minutes": minutes})
            if next_lesson is None and unlocked and status != "completed":
                next_lesson = lesson
            for line in (lesson.objectives or "").splitlines():
                value = line.strip()
                if value and value not in outcomes:
                    outcomes.append(value)
            for resource in lesson.resources.all():
                if resource.pk not in resource_ids:
                    resource_ids.add(resource.pk)
                    resources.append(resource)
        assessment = module.assessments.filter(is_published=True).first()
        best = best_attempts.get(assessment.pk) if assessment else None
        assessment_state = (
            "locked" if not assessment or not module_lessons_completed(enrolment, module)
            else "passed" if best and best.outcome == TheoryAttempt.Outcome.PASS
            else "attempted" if best
            else "available"
        )
        total_minutes += module_minutes
        module_cards.append({
            "module": module,
            "lessons": lesson_cards,
            "first_lesson": lessons[0] if lessons else None,
            "unlocked": unlocked,
            "completed_count": completed,
            "lesson_count": len(lessons),
            "percentage": round(completed / len(lessons) * 100) if lessons else 0,
            "minutes": module_minutes,
            "assessment": assessment,
            "assessment_state": assessment_state,
            "best_attempt": best,
        })
    total_lessons = sum(counts.values())
    course_percentage = round(counts["completed"] / total_lessons * 100) if total_lessons else 0
    next_assessment = next(
        (item["assessment"] for item in module_cards if item["assessment_state"] in ("available", "attempted")),
        None,
    )
    current_module = next(
        (item for item in module_cards if item["unlocked"] and item["assessment_state"] != "passed"),
        module_cards[-1] if module_cards else None,
    )
    resource_categories = {"documents": [], "glossary": [], "reading": []}
    for resource in resources:
        resource_text = f"{resource.title} {resource.description}".lower()
        if "glossary" in resource_text or "key term" in resource_text:
            resource_categories["glossary"].append(resource)
        elif "reading" in resource_text or "reference" in resource_text:
            resource_categories["reading"].append(resource)
        else:
            resource_categories["documents"].append(resource)
    return render_student_page(request, "learning/roadmap.html", {
        "enrolment": enrolment,
        "module_summaries": module_cards,
        "theory_completed": programme_theory_completed(enrolment),
        "final_assessment": final_assessment,
        "lesson_counts": counts,
        "total_lessons": total_lessons,
        "course_percentage": course_percentage,
        "total_minutes": total_minutes,
        "next_lesson": next_lesson,
        "next_assessment": next_assessment,
        "current_module": current_module,
        "learning_outcomes": outcomes[:4],
        "course_resources": resources[:4],
        "resource_categories": resource_categories,
    })


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
    concept_block = next((b for b in blocks if b.kind == "text"), None)
    example_block = next((b for b in blocks if b.kind == "example"), None)
    notice_block = next((b for b in blocks if b.kind == "notice"), None)
    sections = _lesson_sections()

    def section_url(slug):
        return reverse("lesson-section", args=(module.code, lesson.slug, slug))

    overview_mode = False
    current_index, should_redirect = _resolve_current_section(sections, progress, section)
    if should_redirect and request.method == "GET":
        # Resume at the authoritative first unfinished section. Direct links
        # cannot bypass sequential completion.
        return redirect(section_url(sections[current_index]["slug"]))

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
        # Explicit, idempotent completion. Revisiting and continuing from an
        # already completed section never advances the persisted frontier.
        if current_index < len(sections) - 1:
            if current_index == progress.last_position:
                progress.last_position = current_index + 1
                progress.save(update_fields=("last_position", "updated_at"))
            next_index = min(current_index + 1, progress.last_position)
            return redirect(section_url(sections[next_index]["slug"]))
        progress.last_position = len(sections)
        progress.completed_at = progress.completed_at or timezone.now()
        progress.save(update_fields=("last_position", "completed_at", "updated_at"))
        return redirect("module-overview", module_code=module.code)

    _annotate_sections(sections, section_url, progress, current_index)
    word_count = sum(len(block.body.split()) for block in blocks)
    module_assessment = module.assessments.filter(is_published=True).first()
    module_lessons_complete = module_lessons_completed(enrolment, module)
    lessons_in_module = list(module.lessons.filter(is_published=True).order_by("order", "title"))
    lesson_position = next((index + 1 for index, item in enumerate(lessons_in_module) if item.pk == lesson.pk), 1)
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
            "overview_mode": overview_mode,
            "prev_section": sections[current_index - 1] if current_index > 0 else None,
            "next_section": sections[current_index + 1] if current_index < len(sections) - 1 else None,
            "concept_block": concept_block,
            "example_block": example_block,
            "notice_block": notice_block,
            "check": check,
            "objectives": objectives,
            "key_terms": key_terms,
            "lessons_in_module": lessons_in_module,
            "lesson_position": lesson_position,
            "module_assessment": module_assessment,
            "module_lessons_complete": module_lessons_complete,
            "reading_minutes": max(1, round(word_count / 200)),
            "completed_section_count": len(sections) if progress.completed_at else min(progress.last_position, len(sections)),
            "section_progress_percentage": 100 if progress.completed_at else round(min(progress.last_position, len(sections)) / len(sections) * 100),
        },
    )
