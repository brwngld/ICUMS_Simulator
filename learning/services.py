from progress.models import LessonProgress, ModuleProgress


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


def programme_theory_completed(enrolment):
    modules = enrolment.programme_version.modules.filter(is_published=True)
    module_count = modules.count()
    return module_count > 0 and ModuleProgress.objects.filter(
        enrolment=enrolment,
        module__in=modules,
        status=ModuleProgress.Status.COMPLETED,
    ).count() == module_count
