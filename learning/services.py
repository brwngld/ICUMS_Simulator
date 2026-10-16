from django.urls import reverse

from onboarding.models import Programme
from onboarding.services import active_enrolments, programme_href
from progress.models import LessonProgress, ModuleProgress

from .models import Lesson

# The five levels in teaching order, straight from the shared choices list.
DIFFICULTY_LEVELS = [value for value, _label in Programme.Difficulty.choices]
LEVEL_LABELS = dict(Programme.Difficulty.choices)
# The four words a learner sees on a difficulty level; every one already
# labels a progress or assessment state elsewhere in the product.
LEVEL_STATE_LABELS = {
    "completed": "Completed",
    "in_progress": "In progress",
    "available": "Available",
    "locked": "Locked",
}


def module_is_unlocked(enrolment, module):
    if module.prerequisite_id is None:
        return True
    return ModuleProgress.objects.filter(
        enrolment=enrolment,
        module_id=module.prerequisite_id,
        status=ModuleProgress.Status.COMPLETED,
    ).exists()


def module_summary(enrolment, module):
    lessons = module.lessons.filter(is_published=True)
    lesson_count = lessons.count()
    completed_count = LessonProgress.objects.filter(
        enrolment=enrolment,
        lesson__in=lessons,
        completed_at__isnull=False,
    ).count()
    return {
        "module": module,
        "unlocked": module_is_unlocked(enrolment, module),
        "lesson_count": lesson_count,
        "completed_count": completed_count,
        "percentage": round((completed_count / lesson_count) * 100) if lesson_count else 0,
        "first_lesson": lessons.first(),
    }


def module_lessons_completed(enrolment, module):
    lessons = module.lessons.filter(is_published=True)
    lesson_count = lessons.count()
    return lesson_count > 0 and LessonProgress.objects.filter(
        enrolment=enrolment,
        lesson__in=lessons,
        completed_at__isnull=False,
    ).count() == lesson_count


def module_completion(enrolment):
    """How many published modules this enrolment has, and how many are passed."""
    modules = enrolment.programme_version.modules.filter(is_published=True)
    total = modules.count()
    completed = ModuleProgress.objects.filter(
        enrolment=enrolment,
        module__in=modules,
        status=ModuleProgress.Status.COMPLETED,
    ).count()
    return {"completed_count": completed, "module_count": total}


def programme_rows(user):
    """One row per active enrolment: the programme, its progress and its roadmap.

    A row for a learner who holds several enrolments links to that programme by
    code, so choosing a row opens it rather than whichever enrolment is oldest.
    """
    rows = []
    for enrolment in active_enrolments(user):
        counts = module_completion(enrolment)
        rows.append({
            "enrolment": enrolment,
            "programme": enrolment.programme_version.programme,
            "version": enrolment.programme_version,
            **counts,
            "percentage": round(counts["completed_count"] / counts["module_count"] * 100) if counts["module_count"] else 0,
            "url": programme_href(reverse("roadmap"), enrolment),
        })
    return rows


def programme_theory_completed(enrolment):
    counts = module_completion(enrolment)
    return counts["module_count"] > 0 and counts["completed_count"] == counts["module_count"]


def course_modules(course, enrolment=None):
    """The modules a course offers. Without an enrolment, everything it holds.

    Instructor previews pass no enrolment, so drafts and unpublished modules
    appear and nothing is treated as locked.
    """
    modules = course.modules.all() if enrolment is None else course.modules.filter(is_published=True)
    return modules.order_by("order", "title")


def course_lesson_totals(course, enrolment):
    """Published and completed lesson counts for one course."""
    lessons = Lesson.objects.filter(module__in=course_modules(course, enrolment))
    if enrolment is not None:
        lessons = lessons.filter(is_published=True)
    total = lessons.count()
    completed = (
        0 if enrolment is None
        else LessonProgress.objects.filter(enrolment=enrolment, lesson__in=lessons, completed_at__isnull=False).count()
    )
    return total, completed


def course_is_completed(enrolment, course):
    """A course is finished when every published module in it has been passed.

    Lesson views alone do not complete a module; only a passed module
    assessment writes the completion, so this respects the passing rules.
    """
    modules = course.modules.filter(is_published=True)
    if not modules.exists():
        return False
    return ModuleProgress.objects.filter(
        enrolment=enrolment,
        module__in=modules,
        status=ModuleProgress.Status.COMPLETED,
    ).count() == modules.count()


def required_courses(version, difficulty):
    """Published courses that gate progress at one difficulty level."""
    return list(
        version.courses.filter(
            difficulty=difficulty, is_published=True, is_required=True
        ).order_by("order", "title")
    )


def level_is_complete(version, difficulty, enrolment):
    courses = required_courses(version, difficulty)
    # A level with nothing to finish cannot be finished, so it never opens the
    # level above it.
    return bool(courses) and all(course_is_completed(enrolment, course) for course in courses)


def _level_lessons(version, difficulty):
    return Lesson.objects.filter(
        module__course__programme_version=version,
        module__course__difficulty=difficulty,
        module__is_published=True,
        is_published=True,
    )


def level_is_started(version, difficulty, enrolment):
    return LessonProgress.objects.filter(
        enrolment=enrolment, lesson__in=_level_lessons(version, difficulty), completed_at__isnull=False
    ).exists()


def level_states(version, enrolment):
    """State of each difficulty level for one learner, in teaching order.

    Beginner is always open. Each later level opens only when every required
    course at the level before it is complete. A course with no difficulty is
    outside the gates and stays open, which keeps legacy content reachable.
    """
    states = []
    open_level = True
    for index, difficulty in enumerate(DIFFICULTY_LEVELS):
        courses = list(version.courses.filter(difficulty=difficulty, is_published=True).order_by("order", "title"))
        gating = [course for course in courses if course.is_required]
        if enrolment is None:
            # A draft preview shows the shape of the roadmap, not any learner's place in it.
            state = "available" if index == 0 else "locked"
            completed = 0
        else:
            completed = sum(1 for course in gating if course_is_completed(enrolment, course))
            if not open_level:
                state = "locked"
            elif gating and completed == len(gating):
                state = "completed"
            elif courses and level_is_started(version, difficulty, enrolment):
                state = "in_progress"
            else:
                state = "available"
        states.append({
            "difficulty": difficulty,
            "label": LEVEL_LABELS[difficulty],
            "state_label": LEVEL_STATE_LABELS[state],
            "courses": courses,
            "state": state,
            "completed_count": completed,
            "required_count": len(gating),
            "locked": state == "locked",
            "first": index == 0,
        })
        # The chain only continues while each level has required courses and all of them are finished.
        open_level = open_level and bool(gating) and completed == len(gating)
    return states


def unlocked_difficulties(version, enrolment):
    return {item["difficulty"] for item in level_states(version, enrolment) if item["state"] != "locked"}


def course_is_available(enrolment, course):
    """Backend gate: may this learner open this course right now?

    Previews pass no enrolment and are never gated. A course with no
    difficulty sits outside the level chain, so it stays open.
    """
    if enrolment is None:
        return True
    if not course.is_published:
        return False
    if course.difficulty not in DIFFICULTY_LEVELS:
        return True
    return course.difficulty in unlocked_difficulties(course.programme_version, enrolment)


def module_is_available(enrolment, module):
    """Whether a learner should see this module listed at all."""
    if enrolment is None:
        return True
    course = module.course
    return course is None or course.is_published


def module_is_locked(enrolment, module):
    """True when the module's course is at a level this learner has not reached."""
    course = module.course
    if course is None or enrolment is None:
        return False
    return not course_is_available(enrolment, course)


def locked_course_message(course):
    return f"Finish the {LEVEL_LABELS.get(course.difficulty, course.title)} level to open “{course.title}”."


def locked_module_message(module):
    return locked_course_message(module.course)
