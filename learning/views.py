import re

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from core.admin_dashboard import render_student_page
from onboarding.services import enrolment_for_request, needs_disclaimer_acceptance, programme_href
from progress.models import LessonProgress, ModuleProgress
from assessments.models import Assessment, LessonCheck, LessonCheckResponse, TheoryAttempt

from .models import Course, Lesson, Module
from .rich_text import count_words
from .services import (
    DIFFICULTY_LEVELS,
    course_is_available,
    course_is_completed,
    course_modules,
    level_states,
    locked_course_message,
    locked_module_message,
    module_is_available,
    module_is_locked,
    module_is_unlocked,
    programme_theory_completed,
)


_OUTCOME_STOP_WORDS = {
    "able", "about", "after", "also", "and", "are", "can", "course", "define",
    "describe", "explain", "for", "from", "how", "identify", "its", "name", "of",
    "the", "their", "this", "through", "to", "understand", "what", "why", "with",
}


def _outcome_cards(outcomes, module_cards):
    """Attach honest lesson/module evidence to authored course outcomes."""
    lesson_entries = [
        (item["lesson"], card["module"])
        for card in module_cards
        for item in card["lessons"]
    ]
    total_lessons = len(lesson_entries)
    cards = []
    for outcome in outcomes:
        terms = {
            token for token in re.findall(r"[a-z0-9]+", outcome.lower())
            if len(token) > 2 and token not in _OUTCOME_STOP_WORDS
        }
        matches = []
        for lesson, module in lesson_entries:
            searchable = " ".join((module.title, module.description, lesson.title, lesson.summary, lesson.objectives)).lower()
            score = sum(1 for term in terms if term in searchable)
            if score:
                matches.append((score, lesson, module))
        matches.sort(key=lambda item: (-item[0], item[2].order, item[1].order))
        if matches:
            best_score = matches[0][0]
            best = [item for item in matches if item[0] == best_score][:2]
            if len(best) == 1:
                description = f'Developed through “{best[0][1].title}” in {best[0][2].title}.'
            else:
                description = f'Developed through “{best[0][1].title}” and “{best[1][1].title}”.'
        else:
            description = f'Supported across {len(module_cards)} module{"s" if len(module_cards) != 1 else ""} and {total_lessons} lesson{"s" if total_lessons != 1 else ""} in this course.'
        cards.append({"title": outcome, "description": description})
    return cards


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


def _lesson_minutes(lesson):
    return max(1, round(sum(count_words(block.body) for block in lesson.blocks.all()) / 200))


def _lesson_url(module, lesson, preview, enrolment=None):
    url = (reverse("lesson-preview", args=[lesson.pk]) if preview
           else reverse("lesson-detail", args=[module.code, lesson.slug]))
    return programme_href(url, enrolment)


def _assessment_url(assessment, preview, enrolment=None):
    url = (reverse("assessment-preview", args=[assessment.pk]) if preview
           else reverse("assessment-take", args=[assessment.pk]))
    return programme_href(url, enrolment)


def module_overview_context(module, enrolment=None):
    """Everything the learner module overview shows.

    Passing no `enrolment` produces the instructor's preview of a draft:
    unpublished lessons and assessments are included, nothing is marked
    complete, and every link points at a read-only preview page.
    """
    preview = enrolment is None
    lessons = list(module.lessons.all() if preview else module.lessons.filter(is_published=True))
    lessons.sort(key=lambda lesson: (lesson.order, lesson.title))
    progress_by_lesson = (
        {} if preview
        else {item.lesson_id: item for item in LessonProgress.objects.filter(enrolment=enrolment, lesson__in=lessons)}
    )
    lesson_items = []
    objectives = []
    objective_groups = []
    resources = []
    resource_ids = set()
    next_lesson = None
    next_lesson_url = None
    total_minutes = 0
    completed_count = 0
    for lesson in lessons:
        progress = progress_by_lesson.get(lesson.pk)
        status = "completed" if progress and progress.completed_at else "in_progress" if progress else "not_started"
        completed_count += status == "completed"
        minutes = _lesson_minutes(lesson)
        total_minutes += minutes
        lesson_url = _lesson_url(module, lesson, preview, enrolment)
        lesson_items.append({
            "lesson": lesson,
            "progress": progress,
            "status": status,
            "minutes": minutes,
            "url": lesson_url,
        })
        if next_lesson is None and status != "completed":
            next_lesson, next_lesson_url = lesson, lesson_url
        lesson_objectives = [line.strip() for line in (lesson.objectives or "").splitlines() if line.strip()]
        if lesson_objectives:
            objective_groups.append({"lesson": lesson, "objectives": lesson_objectives})
        for value in lesson_objectives:
            if value and value not in objectives:
                objectives.append(value)
        for resource in lesson.resources.all():
            if resource.pk not in resource_ids:
                resource_ids.add(resource.pk)
                resources.append(resource)

    assessment = module.assessments.all().first() if preview else module.assessments.filter(is_published=True).first()
    attempts = TheoryAttempt.objects.filter(
        enrolment=enrolment, assessment=assessment, status=TheoryAttempt.Status.SUBMITTED
    ).order_by("-percentage", "-submitted_at") if assessment and enrolment else TheoryAttempt.objects.none()
    best_attempt = attempts.first()
    attempt_count = attempts.count()
    lessons_complete = bool(lessons) and completed_count == len(lessons)
    attempts_remaining = None
    if assessment and assessment.maximum_attempts is not None:
        attempts_remaining = max(assessment.maximum_attempts - attempt_count, 0)
    can_attempt = bool(assessment and (lessons_complete if enrolment else True) and (attempts_remaining is None or attempts_remaining > 0))
    assessment_passed = bool(best_attempt and best_attempt.outcome == TheoryAttempt.Outcome.PASS)
    progress_percentage = round(completed_count / len(lessons) * 100) if lessons else 0
    module_course = module.course
    course_page = module_course if module_course and (preview or module_course.is_published) else None
    course_url = None
    if course_page:
        url = (reverse("course-content-preview", args=[course_page.pk]) if preview
               else reverse("course-overview", args=[course_page.code]))
        course_url = programme_href(url, enrolment)

    return {
        "enrolment": enrolment,
        "module": module,
        "version": module.programme_version,
        "lesson_items": lesson_items,
        "objectives": objectives,
        "objective_preview": objectives[:6],
        "objective_groups": objective_groups,
        "objective_count": sum(len(group["objectives"]) for group in objective_groups),
        "resources": resources,
        "assessment": assessment,
        "best_attempt": best_attempt,
        "attempt_count": attempt_count,
        "attempts_remaining": attempts_remaining,
        "can_attempt": can_attempt,
        "assessment_passed": assessment_passed,
        "lessons_complete": lessons_complete,
        "next_lesson": next_lesson,
        "next_lesson_url": next_lesson_url,
        "completed_count": completed_count,
        "progress_percentage": progress_percentage,
        "total_minutes": total_minutes,
        "course": course_page,
        "course_url": course_url,
        "back_url": course_url or (
            reverse("course-preview", args=[module.programme_version_id]) if preview
            else programme_href(reverse("roadmap"), enrolment)
        ),
        "assessment_take_url": _assessment_url(assessment, preview, enrolment) if assessment else None,
        "assessment_result_url": None if preview else (
            reverse("assessment-result", args=[best_attempt.pk]) if best_attempt else None),
    }


@login_required
def module_overview(request, module_code):
    if response := _guard_onboarding(request):
        return response
    enrolment = enrolment_for_request(request)
    module = get_object_or_404(
        Module.objects.select_related("programme_version__programme", "course").prefetch_related(
            "lessons__blocks", "lessons__resources", "assessments"
        ),
        programme_version=enrolment.programme_version,
        code=module_code,
        is_published=True,
    )
    if not module_is_unlocked(enrolment, module):
        raise PermissionDenied("Complete the prerequisite module first.")
    if module_is_locked(enrolment, module):
        raise PermissionDenied(locked_module_message(module))

    return render_student_page(request, "learning/module_overview.html", module_overview_context(module, enrolment))


def _is_levelled(module):
    """Whether a module belongs to a course that sits at a difficulty level."""
    course = module.course
    return bool(course and course.is_published and course.difficulty in DIFFICULTY_LEVELS)


def _course_cards(courses, cards_by_module, enrolment):
    """Course cards for the roadmap: title, description, module count and progress."""
    cards = []
    for course in courses:
        owned = [cards_by_module[module.pk] for module in course.modules.all() if module.pk in cards_by_module]
        lesson_count = sum(item["lesson_count"] for item in owned)
        completed_count = sum(item["completed_count"] for item in owned)
        cards.append({
            "course": course,
            "title": course.title,
            "description": course.description,
            "difficulty": course.difficulty,
            "module_count": len(owned),
            "lesson_count": lesson_count,
            "completed_count": completed_count,
            "percentage": round(completed_count / lesson_count * 100) if lesson_count else 0,
            "minutes": sum(item["minutes"] for item in owned),
            "completed": enrolment is not None and course_is_completed(enrolment, course),
            "locked": enrolment is not None and not course_is_available(enrolment, course),
            "url": (
                reverse("course-content-preview", args=[course.pk])
                if enrolment is None
                else programme_href(reverse("course-overview", args=[course.code]), enrolment)
            ),
        })
    return cards


def roadmap_context(version, enrolment, course=None):
    """Everything the learner roadmap and a course page show.

    With no `course` the context covers the whole programme edition: modules
    that belong to a difficulty level are grouped into course cards, and the
    rest stay listed on the page. Passing no `enrolment` produces the
    instructor's preview of a draft: unpublished modules, lessons and
    assessments are included, nothing is marked complete, and every link
    points at a read-only preview page.
    """
    preview = enrolment is None
    module_source = (
        course_modules(course, enrolment)
        if course is not None
        else (version.modules.all() if preview else version.modules.filter(is_published=True))
    )
    modules = list(
        module_source.select_related("course").prefetch_related(
            "lessons__blocks", "lessons__resources", "assessments"
        ).order_by("order", "title")
    )
    final_assessment = (
        version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY)
        if preview else
        version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY, is_published=True)
    ).first()
    progress_by_lesson = (
        {} if preview else
        {item.lesson_id: item for item in LessonProgress.objects.filter(enrolment=enrolment, lesson__module__in=modules)}
    )
    best_attempts = {}
    if not preview:
        for attempt in (
            TheoryAttempt.objects.filter(enrolment=enrolment, status=TheoryAttempt.Status.SUBMITTED, assessment__module__in=modules)
            .select_related("assessment")
            .order_by("assessment_id", "-percentage")
        ):
            best_attempts.setdefault(attempt.assessment_id, attempt)

    module_cards = []
    counts = {"completed": 0, "in_progress": 0, "not_started": 0}
    next_lesson = None
    next_lesson_url = None
    total_minutes = 0
    outcomes = []
    resources = []
    resource_ids = set()
    for module in modules:
        lessons = list((module.lessons.all() if preview else module.lessons.filter(is_published=True)).order_by("order", "title"))
        unlocked = (
            module_is_unlocked(enrolment, module) and not module_is_locked(enrolment, module)
            if enrolment else True
        )
        lesson_cards = []
        completed = 0
        module_minutes = 0
        for lesson in lessons:
            progress = progress_by_lesson.get(lesson.pk)
            status = "completed" if progress and progress.completed_at else "in_progress" if progress else "not_started"
            counts[status] += 1
            completed += status == "completed"
            minutes = _lesson_minutes(lesson)
            module_minutes += minutes
            lesson_url = _lesson_url(module, lesson, preview, enrolment)
            lesson_cards.append({"lesson": lesson, "status": status, "minutes": minutes, "url": lesson_url})
            if next_lesson is None and unlocked and status != "completed":
                next_lesson, next_lesson_url = lesson, lesson_url
            for line in (lesson.objectives or "").splitlines():
                value = line.strip()
                if value and value not in outcomes:
                    outcomes.append(value)
            for resource in lesson.resources.all():
                if resource.pk not in resource_ids:
                    resource_ids.add(resource.pk)
                    resources.append(resource)
        assessment = (module.assessments.all() if preview else module.assessments.filter(is_published=True)).first()
        best = best_attempts.get(assessment.pk) if assessment else None
        lessons_complete = bool(lessons) and completed == len(lessons)
        assessment_state = (
            "locked" if not assessment or not unlocked or not lessons_complete
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
            "inline": course is not None or (
                not _is_levelled(module) and module_is_available(enrolment, module)
            ),
            "completed_count": completed,
            "lesson_count": len(lessons),
            "percentage": round(completed / len(lessons) * 100) if lessons else 0,
            "minutes": module_minutes,
            "assessment": assessment,
            "assessment_url": _assessment_url(assessment, preview, enrolment) if assessment else None,
            "assessment_state": assessment_state,
            "best_attempt": best,
            "url": programme_href(
                reverse("module-preview", args=[module.pk]) if preview
                else reverse("module-overview", args=[module.code]),
                enrolment,
            ),
        })
    total_lessons = sum(counts.values())
    course_percentage = round(counts["completed"] / total_lessons * 100) if total_lessons else 0
    # An assessment behind a locked difficulty level is never the next action,
    # even when its lessons were completed before the content was levelled.
    next_assessment = next(
        (item["assessment"] for item in module_cards if item["unlocked"] and item["assessment_state"] in ("available", "attempted")),
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

    # Difficulty levels only structure the page once a course sits at one;
    # until then every module stays listed here, exactly as before.
    levels = [] if course is not None else level_states(version, enrolment)
    show_levels = any(item["courses"] for item in levels)
    roadmap_levels = []
    if show_levels:
        cards_by_module = {item["module"].pk: item for item in module_cards}
        current_index = next(
            (index for index, item in enumerate(levels) if item["state"] in ("available", "in_progress")),
            len(levels) - 1,
        )
        for index, item in enumerate(levels):
            roadmap_levels.append({
                **item,
                "courses": _course_cards(item["courses"], cards_by_module, enrolment),
                "expanded": index == current_index,
            })
    # Everything a learner can be shown: published modules inside a published
    # course, including those still behind a difficulty level. The dashboard
    # and the roadmap's counters work from this list, because a programme whose
    # modules all sit on courses has no inline cards at all.
    visible_modules = [
        item for item in module_cards if module_is_available(enrolment, item["module"])
    ]
    learning_outcomes = version.programme.get_outcomes_list() or outcomes[:8]
    return {
        "enrolment": enrolment,
        "version": version,
        "course": course,
        "levels": roadmap_levels,
        "show_levels": show_levels,
        "roadmap_url": programme_href(reverse("roadmap"), enrolment),
        "module_summaries": [item for item in module_cards if item["inline"]],
        "visible_modules": visible_modules,
        "module_total": len(visible_modules),
        "theory_completed": programme_theory_completed(enrolment) if enrolment else False,
        "final_assessment": final_assessment,
        "final_assessment_url": _assessment_url(final_assessment, preview, enrolment) if final_assessment else None,
        "lesson_counts": counts,
        "total_lessons": total_lessons,
        "course_percentage": course_percentage,
        "total_minutes": total_minutes,
        "next_lesson": next_lesson,
        "next_lesson_url": next_lesson_url,
        "next_assessment": next_assessment,
        "next_assessment_url": _assessment_url(next_assessment, preview, enrolment) if next_assessment else None,
        "current_module": current_module,
        # Prefer course-level outcomes set by the instructor; fall back to
        # outcomes aggregated from published lesson objectives.
        "learning_outcomes": learning_outcomes,
        "learning_outcome_cards": _outcome_cards(learning_outcomes, module_cards),
        "course_resources": resources[:4],
        "resource_categories": resource_categories,
        # Pass programme metadata so the learner overview can display them.
        "programme": version.programme,
    }


@login_required
def roadmap(request):
    if response := _guard_onboarding(request):
        return response
    if not request.user.enrolments.filter(status="active").exists() and (
        request.user.is_superuser or request.user.groups.filter(name__in=("Instructor", "Administrator")).exists()
    ):
        return redirect(f'{reverse("course-builder")}?path=theory')
    enrolment = enrolment_for_request(request)
    return render_student_page(request, "learning/roadmap.html", roadmap_context(enrolment.programme_version, enrolment))


@login_required
def course_overview(request, course_code):
    """One course: its overview, outcomes, modules, assessments and resources."""
    if response := _guard_onboarding(request):
        return response
    enrolment = enrolment_for_request(request)
    course = get_object_or_404(
        Course.objects.select_related("programme_version__programme"),
        programme_version=enrolment.programme_version,
        code=course_code,
        is_published=True,
    )
    if not course_is_available(enrolment, course):
        raise PermissionDenied(locked_course_message(course))
    return render_student_page(
        request, "learning/roadmap.html", roadmap_context(enrolment.programme_version, enrolment, course=course)
    )


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
    enrolment = enrolment_for_request(request)
    module = get_object_or_404(Module, programme_version=enrolment.programme_version, code=module_code, is_published=True)
    if not module_is_unlocked(enrolment, module):
        raise PermissionDenied("Complete the prerequisite module first.")
    if module_is_locked(enrolment, module):
        raise PermissionDenied(locked_module_message(module))
    lesson = get_object_or_404(Lesson, module=module, slug=lesson_slug, is_published=True)
    progress, _ = LessonProgress.objects.get_or_create(enrolment=enrolment, lesson=lesson)
    ModuleProgress.objects.get_or_create(enrolment=enrolment, module=module, defaults={"status": ModuleProgress.Status.IN_PROGRESS})
    blocks = list(lesson.blocks.all())
    checks = list(
        lesson.knowledge_checks.select_related("question_version")
        .prefetch_related("question_version__options")
        .order_by("order", "id")
    )
    objectives = [line.strip() for line in (lesson.objectives or "").splitlines() if line.strip()]
    key_terms = []
    for line in (lesson.key_terms or "").splitlines():
        line = line.strip()
        if "::" in line:
            term, definition = line.split("::", 1)
            key_terms.append((term.strip(), definition.strip()))

    # The lesson's section list, in teaching order.
    concept_blocks = [b for b in blocks if b.kind == "text"]
    example_blocks = [b for b in blocks if b.kind == "example"]
    notice_blocks = [b for b in blocks if b.kind == "notice"]
    concept_block = concept_blocks[0] if concept_blocks else None
    example_block = example_blocks[0] if example_blocks else None
    notice_block = notice_blocks[0] if notice_blocks else None
    sections = _lesson_sections()

    def section_url(slug):
        return programme_href(reverse("lesson-section", args=(module.code, lesson.slug, slug)), enrolment)

    overview_mode = False
    current_index, should_redirect = _resolve_current_section(sections, progress, section)
    if should_redirect and request.method == "GET":
        # Resume at the authoritative first unfinished section. Direct links
        # cannot bypass sequential completion.
        return redirect(section_url(sections[current_index]["slug"]))

    if request.method == "POST":
        action = request.POST.get("action", "continue")
        if action == "answer_check":
            check = next((item for item in checks if str(item.pk) == request.POST.get("check_id")), None)
            if check is None:
                messages.error(request, "This practice question is no longer available.")
                return redirect(section_url("practice") + "#feedback")
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
        return redirect(programme_href(reverse("module-overview", args=[module.code]), enrolment))

    _annotate_sections(sections, section_url, progress, current_index)
    word_count = sum(count_words(block.body) for block in blocks)
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
            "concepts_url": section_url("concepts"),
            "overview_mode": overview_mode,
            "prev_section": sections[current_index - 1] if current_index > 0 else None,
            "next_section": sections[current_index + 1] if current_index < len(sections) - 1 else None,
            "concept_block": concept_block,
            "example_block": example_block,
            "notice_block": notice_block,
            "concept_blocks": concept_blocks,
            "example_blocks": example_blocks,
            "notice_blocks": notice_blocks,
            "checks": checks,
            "objectives": objectives,
            "key_terms": key_terms,
            "lessons_in_module": lessons_in_module,
            "lesson_position": lesson_position,
            "reading_minutes": max(1, round(word_count / 200)),
            "completed_section_count": len(sections) if progress.completed_at else min(progress.last_position, len(sections)),
            "section_progress_percentage": 100 if progress.completed_at else round(min(progress.last_position, len(sections)) / len(sections) * 100),
        },
    )
