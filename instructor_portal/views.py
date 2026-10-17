from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from uuid import uuid4

from core.admin_dashboard import render_student_page
from .ordering import (
    move_course as move_course_order,
    move_lesson as move_lesson_order,
    move_module as move_module_order,
)
from django.utils import timezone
from django.utils.text import slugify

from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Course, Lesson, Module
from learning.services import DIFFICULTY_LEVELS, part_window
from learning.rich_text import count_words, plain_text
from learning.rich_text_images import (
    clone_lesson_images,
    pixel_size as rich_image_size,
    prune_lesson as prune_rich_text_images,
    store_image as store_rich_text_image,
)
from learning.views import module_overview_context, roadmap_context
from scenarios.models import ScenarioVersion as ScenarioVersionModel
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress

from evaluations.models import Rubric, RubricCriterion, RubricVersion
from reports.models import CompletionPolicy
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioDocument, ScenarioState, ScenarioVersion
from accounts.models import SimulatorCredential

from .forms import (
    AssessmentQuestionForm,
    AssessmentSettingsForm,
    BlockFormSet,
    CourseCreateForm,
    CourseEditForm,
    LessonCheckEditForm,
    LessonEditForm,
    LessonPracticeQuestionForm,
    ModuleCreateForm,
    ModuleEditForm,
    PracticalCreateForm,
    PracticalEditForm,
    ProgrammeCourseForm,
    ScenarioDocumentFormSet,
    ScenarioStateFormSet,
)


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@login_required
def dashboard(request):
    _require_instructor(request.user)
    enrolments = _instructor_enrolments(request.user).select_related("student__simulator_credential").prefetch_related("lesson_progress", "theory_attempts")
    return render_student_page(request, "instructor_portal/dashboard.html", {"enrolments": enrolments})


@login_required
@transaction.atomic
def simulator_credential_issue(request, user_id):
    _require_instructor(request.user)
    if request.method != "POST":
        return redirect("instructor-dashboard")


    from accounts.models import User

    student = get_object_or_404(User, pk=user_id)
    credential, _ = SimulatorCredential.objects.get_or_create(user=student)
    raw_password = credential.issue()
    credential.mark_revealed()
    return render_student_page(request, "instructor_portal/credential_reveal.html", {
        "student": student,
        "credential": credential,
        "raw_password": raw_password,
    })


def _unique_slug(model, field, value, **scope):
    base = slugify(value) or "untitled"
    candidate = base
    number = 2
    while model.objects.filter(**scope, **{field: candidate}).exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


@login_required
def course_builder(request):
    _require_instructor(request.user)
    status_filter = request.GET.get("status", "all")
    if status_filter not in {"all", "draft", "published", "retired"}:
        status_filter = "all"
    qs = (
        ProgrammeVersion.objects.select_related("programme")
        .prefetch_related("modules__lessons")
        .annotate(module_total=Count("modules", distinct=True), lesson_total=Count("modules__lessons", distinct=True))
        .order_by("programme__name", "version")
    )
    if status_filter != "all":
        qs = qs.filter(status=status_filter)
    learning_path = request.GET.get("path", "all")
    if learning_path not in {"all", "theory", "combined"}:
        learning_path = "all"
    return render_student_page(request, "instructor_portal/course_builder.html", {
        "versions": qs,
        "form": CourseCreateForm(),
        "learning_path": learning_path,
        "status_filter": status_filter,
    })


@login_required
@transaction.atomic
def course_create(request):
    _require_instructor(request.user)
    if request.method != "POST":
        return redirect("course-builder")
    form = CourseCreateForm(request.POST)
    if not form.is_valid():
        versions = ProgrammeVersion.objects.select_related("programme").prefetch_related("modules__lessons").order_by("programme__name", "version")
        return render_student_page(request, "instructor_portal/course_builder.html", {
            "versions": versions,
            "form": form,
            "learning_path": "theory",
            "status_filter": "all",
        }, status=400)
    name = form.cleaned_data["name"]
    code = _unique_slug(Programme, "code", name)
    programme = Programme.objects.create(
        name=name,
        code=code,
        description=form.cleaned_data.get("description", ""),
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status="draft")
    messages.success(request, "Draft course created. Add its first module next.")
    return redirect("course-builder-detail", version_id=version.pk)


@login_required
@require_POST
@transaction.atomic
def course_delete(request, version_id):
    """Delete one unused draft and its authoring-only content tree."""
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_for_update().select_related("programme"),
        pk=version_id,
        status=ProgrammeVersion.Status.DRAFT,
    )
    if version.enrolments.exists():
        messages.error(request, "This draft cannot be deleted because it already has learner activity.")
        return redirect(f'{reverse("course-builder")}?path=theory')

    assessments = Assessment.objects.filter(programme_version=version)
    practicals = ScenarioVersion.objects.filter(module__programme_version=version)
    if assessments.filter(attempts__isnull=False).exists() or practicals.filter(attempts__isnull=False).exists():
        messages.error(request, "This draft cannot be deleted because it already has learner activity.")
        return redirect(f'{reverse("course-builder")}?path=theory')

    # Remove protected authoring descendants from the leaves upwards.
    from evaluations.models import RubricVersion
    from reports.models import CompletionPolicy

    CompletionPolicy.objects.filter(programme_version=version).delete()
    assessments.delete()
    RubricVersion.objects.filter(scenario_version__in=practicals).delete()
    # Actions must go first because ``to_state`` deliberately protects its
    # destination state, even though both records belong to the same draft.
    ScenarioActionDefinition.objects.filter(scenario_version__in=practicals).delete()
    practicals.delete()
    modules = Module.objects.filter(programme_version=version)
    modules.update(prerequisite=None)
    Lesson.objects.filter(module__in=modules).delete()
    modules.delete()
    Course.objects.filter(programme_version=version).delete()
    programme = version.programme
    name = programme.name
    version.delete()
    if not programme.versions.exists():
        programme.delete()
    messages.success(request, f'Draft course “{name}” deleted.')
    return redirect(f'{reverse("course-builder")}?path=theory')


@login_required
def course_builder_detail(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_related("programme").prefetch_related("modules__lessons", "modules__guided_practicals__scenario", "assessments__items"),
        pk=version_id,
        status=ProgrammeVersion.Status.DRAFT,
    )
    # Rendered through the shared shell: the raw render() call this page
    # used before skipped the admin chrome context, leaving its header —
    # sidebar toggle included — empty.
    final_exam = version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY).first()
    modules = list(
        version.modules.prefetch_related("lessons", "assessments", "guided_practicals__scenario").order_by("order", "title")
    )
    course_groups = [
        {"course": course, "modules": [item for item in modules if item.course_id == course.pk]}
        for course in version.courses.all()
    ]
    return render_student_page(
        request,
        "instructor_portal/course_builder_detail.html",
        {
            "version": version,
            "module_form": ModuleCreateForm(version),
            "course_form": ProgrammeCourseForm(),
            "course_groups": course_groups,
            "loose_modules": [item for item in modules if item.course_id is None],
            "final_exam": final_exam,
        },
    )


@login_required
@transaction.atomic
def programme_course_create(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion, pk=version_id, status="draft")
    if request.method != "POST":
        return redirect("course-builder-detail", version_id=version.pk)
    form = ProgrammeCourseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please correct the course form.")
        return redirect("course-builder-detail", version_id=version.pk)
    course = Course.objects.create(
        programme_version=version,
        code=_unique_slug(Course, "code", form.cleaned_data["title"], programme_version=version),
        title=form.cleaned_data["title"],
        description=form.cleaned_data["description"],
        difficulty=form.cleaned_data["difficulty"],
        is_required=form.cleaned_data["is_required"],
        order=version.courses.count() + 1,
    )
    messages.success(request, "Course added to the roadmap. Move a module into it next.")
    return redirect("programme-course-edit", course_id=course.pk)


@login_required
def programme_course_edit(request, course_id):
    _require_instructor(request.user)
    course = get_object_or_404(
        Course.objects.select_related("programme_version__programme"),
        pk=course_id,
        programme_version__status="draft",
    )
    form = ProgrammeCourseForm(request.POST or None, course=course)
    if request.method == "POST" and form.is_valid():
        course.title = form.cleaned_data["title"]
        course.description = form.cleaned_data["description"]
        course.difficulty = form.cleaned_data["difficulty"]
        course.is_required = form.cleaned_data["is_required"]
        course.save(update_fields=("title", "description", "difficulty", "is_required"))
        messages.success(request, "Course updated.")
        return redirect("course-builder-detail", version_id=course.programme_version_id)
    return render_student_page(
        request,
        "instructor_portal/programme_course_edit.html",
        {
            "course": course,
            "form": form,
            "modules": course.modules.order_by("order", "title"),
            "issues": _programme_course_issues(course),
        },
    )


@login_required
@require_POST
def programme_course_delete(request, course_id):
    _require_instructor(request.user)
    course = get_object_or_404(Course, pk=course_id, programme_version__status="draft")
    version_id = course.programme_version_id
    if course.modules.exists():
        messages.error(request, "Move its modules to another course before removing it.")
    else:
        course.delete()
        messages.success(request, "Course removed.")
    return redirect("course-builder-detail", version_id=version_id)


@login_required
@require_POST
def programme_course_move(request, course_id):
    _require_instructor(request.user)
    course = get_object_or_404(Course, pk=course_id, programme_version__status="draft")
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        messages.error(request, "Unknown move direction.")
    elif move_course_order(course, direction):
        messages.success(request, "Course order updated.")
    return redirect("course-builder-detail", version_id=course.programme_version_id)


@login_required
@require_GET
def course_content_preview(request, course_id):
    """One course exactly as an enrolled student sees it, draft included."""
    _require_instructor(request.user)
    course = get_object_or_404(
        Course.objects.select_related("programme_version__programme"), pk=course_id
    )
    return render_student_page(request, "learning/roadmap.html", {
        **roadmap_context(course.programme_version, None, course=course),
        "preview_mode": True,
    })


def _lesson_issues(lesson):
    """What a single lesson still needs before a learner can study it."""
    issues = []
    blocks = list(lesson.blocks.all())
    # A section with an empty body still publishes as a blank panel, so a lesson
    # is only ready when every one of its sections carries text.
    if not blocks or any(not plain_text(block.body) for block in blocks):
        issues.append(f'Add teaching content to “{lesson.title}”.')
    if not lesson.knowledge_checks.exists():
        issues.append(f'Add a knowledge check to “{lesson.title}”.')
    for check in lesson.knowledge_checks.all():
        options = check.question_version.options.all()
        # is_published is the publish sweep's own marker, never a precondition:
        # a draft lesson is ready as soon as its question could be published safely.
        if options.count() < 2:
            issues.append(f'A knowledge check in “{lesson.title}” needs at least two answer options.')
        if options.filter(is_correct=True).count() != 1:
            issues.append(f'The knowledge check in “{lesson.title}” must have exactly one correct answer.')
    return issues


def _module_blockers(module):
    """Module-level requirements — without these the module cannot be published at all."""
    issues = []
    # A module is completed by passing its module assessment; without one
    # the module — and therefore the final exam, orientation, and every
    # practical — stays out of reach for its students.
    module_assessments = [a for a in module.assessments.all() if a.assessment_type == Assessment.Type.MODULE]
    if not module_assessments:
        issues.append(f'Add a module assessment to “{module.title}” — students complete a module by passing its assessment.')
    elif not any(assessment.items.exists() for assessment in module_assessments):
        issues.append(f'The module assessment for “{module.title}” must include at least one question.')
    for assessment in module_assessments:
        for item in assessment.items.select_related("question_version"):
            options = item.question_version.options.all()
            if options.count() < 2:
                issues.append(f'A question in the module assessment for “{module.title}” needs at least two answer options.')
            if options.filter(is_correct=True).count() != 1:
                issues.append(f'A question in the module assessment for “{module.title}” must have exactly one correct answer.')
    for practical in module.guided_practicals.all():
        if practical.states.count() < 2 or not practical.action_definitions.exists():
            issues.append(f'Complete the simulated flow for “{practical.scenario.title}”.')
    return issues


def _module_issues(module):
    """Everything still outstanding on one module, finished lessons included."""
    issues = []
    if not module.lessons.exists():
        issues.append(f'Add at least one lesson to “{module.title}”.')
    issues.extend(_module_blockers(module))
    for lesson in module.lessons.all():
        issues.extend(_lesson_issues(lesson))
    return issues


def _publishable_modules(version):
    """Modules whose own requirements are met, mapped to their finished lessons."""
    modules = version.modules.prefetch_related(
        "lessons__blocks",
        "lessons__knowledge_checks__question_version__options",
        "assessments__items__question_version__options",
        "guided_practicals__states",
        "guided_practicals__action_definitions",
    )
    ready = {}
    for module in modules:
        blockers = _module_blockers(module)
        lessons = [lesson for lesson in module.lessons.all() if not _lesson_issues(lesson)]
        if lessons and not blockers:
            ready[module] = lessons
    return ready


def _final_exam_issues(version):
    issues = []
    # Passing the final theory examination is what unlocks orientation and
    # every practical; a course without a valid final exam strands its
    # students after the modules.
    final_exams = [
        assessment for assessment in version.assessments.all()
        if assessment.assessment_type == Assessment.Type.FINAL_THEORY
    ]
    if not final_exams:
        issues.append("Add a final theory examination — passing it unlocks simulator orientation and practical training.")
    elif not any(assessment.items.exists() for assessment in final_exams):
        issues.append("The final theory examination must include at least one question.")
    for assessment in final_exams:
        for item in assessment.items.select_related("question_version"):
            options = item.question_version.options.all()
            if options.count() < 2:
                issues.append("A question in the final theory examination needs at least two answer options.")
            if options.filter(is_correct=True).count() != 1:
                issues.append("A question in the final theory examination must have exactly one correct answer.")
    return issues


def _programme_course_issues(course):
    """What one course still needs before learners follow it on the roadmap."""
    issues = []
    modules = list(course.modules.all())
    if not modules:
        issues.append(f'Add at least one module to “{course.title}”.')
    elif not any(not _module_blockers(module) and module.lessons.exists() for module in modules):
        issues.append(f'Finish a module in “{course.title}” so learners have something to start with.')
    if not course.difficulty:
        issues.append(f'Set a difficulty level for “{course.title}” to place it on the roadmap ladder.')
    return issues


def _programme_course_blockers(version, publishable):
    """Courses cannot hold up publication unless they exist and are empty.

    An unclassified course is only a warning: it stays open to learners and
    gates nothing, so a legacy course container never strands a published
    programme.
    """
    blockers = []
    ready_modules = set(publishable)
    for course in version.courses.all():
        modules = list(course.modules.all())
        if not modules:
            blockers.append(f'“{course.title}” has no modules. Move a module into it or remove the course.')
        elif not any(module in ready_modules for module in modules):
            blockers.append(f'“{course.title}” has no module ready for learners yet.')
    return blockers


def _course_issues(version):
    issues = []
    modules = version.modules.prefetch_related("lessons__blocks", "lessons__knowledge_checks__question_version__options", "assessments__items")
    if not modules.exists():
        issues.append("Add at least one module.")
    for module in modules:
        issues.extend(_module_issues(module))
    for course in version.courses.all():
        issues.extend(_programme_course_issues(course))
    if version.courses.exists():
        for module in version.modules.filter(course__isnull=True):
            issues.append(f'Move “{module.title}” into a course so learners meet it on the roadmap.')
    issues.extend(_final_exam_issues(version))
    return issues


@login_required
def course_review(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_related("programme").prefetch_related(
            "modules__lessons__blocks",
            "modules__lessons__knowledge_checks__question_version__options",
            "modules__guided_practicals__scenario",
            "modules__guided_practicals__states",
            "modules__guided_practicals__action_definitions",
            "modules__assessments__items__question_version",
            "assessments__items__question_version",
        ),
        pk=version_id,
        status="draft",
    )
    publishable = _publishable_modules(version)
    return render_student_page(request, "instructor_portal/course_review.html", {
        "version": version,
        "final_exam": version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY).first(),
        "issues": _course_issues(version),
        "publishable_modules": publishable,
        "pending_modules": [(module, _module_issues(module)) for module in version.modules.all() if module not in publishable],
        "publish_blockers": _publish_blockers(version, publishable),
    })


def _publish_blockers(version, publishable=None):
    """Issues that stop the course from going live at all.

    An unfinished module is no longer a blocker on its own — it simply stays
    hidden — but the course needs at least one module learners can complete and
    a valid final examination to unlock the practical side.
    """
    ready = _publishable_modules(version) if publishable is None else publishable
    blockers = []
    if not ready:
        blockers.append("Finish at least one module — no module is ready for learners yet.")
    blockers.extend(_programme_course_blockers(version, ready))
    blockers.extend(_final_exam_issues(version))
    return blockers


@login_required
@transaction.atomic
def course_publish(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion, pk=version_id, status="draft")
    if request.method != "POST":
        return redirect("course-review", version_id=version.pk)
    publishable = _publishable_modules(version)
    blockers = _publish_blockers(version, publishable)
    if blockers:
        messages.error(request, blockers[0] if len(blockers) == 1 else "The course still has items to resolve before publishing.")
        return redirect("course-review", version_id=version.pk)
    ready_modules = list(publishable)
    ready_lessons = [lesson for lessons in publishable.values() for lesson in lessons]
    Module.objects.filter(pk__in=[module.pk for module in ready_modules]).update(is_published=True)
    ready_ids = {module.pk for module in ready_modules}
    live_courses = [
        course.pk for course in version.courses.all()
        if any(module.pk in ready_ids for module in course.modules.all())
    ]
    Course.objects.filter(pk__in=live_courses).update(is_published=True)
    Lesson.objects.filter(pk__in=[lesson.pk for lesson in ready_lessons]).update(is_published=True)
    assessments = Assessment.objects.filter(
        Q(module__in=ready_modules) | Q(module__isnull=True, assessment_type=Assessment.Type.FINAL_THEORY)
    )
    QuestionVersion.objects.filter(
        Q(lesson_checks__lesson__in=ready_lessons) | Q(assessment_items__assessment__in=assessments)
    ).distinct().update(is_published=True)
    assessments.update(is_published=True)
    practicals = ScenarioVersion.objects.filter(module__in=ready_modules)
    practicals.update(status=ScenarioVersion.Status.PUBLISHED, published_at=timezone.now())
    RubricVersion.objects.filter(scenario_version__in=practicals).update(status=RubricVersion.Status.PUBLISHED, published_at=timezone.now())
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.save(update_fields=("status", "published_at"))
    held_back = version.modules.count() - len(ready_modules)
    summary = f'“{version.programme.name}” is now available to enrolled students.'
    if held_back:
        summary += f" {held_back} module{' is' if held_back == 1 else 's are'} still in draft and hidden from learners."
    messages.success(request, summary)
    return redirect("instructor-dashboard")


@login_required
def course_view_published(request, version_id):
    """Read-only instructor view of a published or retired course."""
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_related("programme").prefetch_related(
            "modules__lessons__blocks",
            "modules__assessments__items",
            "assessments__items",
        ),
        pk=version_id,
    )
    if version.status == ProgrammeVersion.Status.DRAFT:
        return redirect("course-builder-detail", version_id=version.pk)
    final_exam = version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY).first()
    enrolment_count = version.enrolments.count()
    return render_student_page(request, "instructor_portal/course_view_published.html", {
        "version": version,
        "final_exam": final_exam,
        "enrolment_count": enrolment_count,
    })


class _CopiedRows:
    """Which new row stands in for which source row while a draft is copied.

    Keyed by model and key because one row can be reachable through two parents
    — a knowledge check belongs to a lesson and follows one of its sections —
    and each row may only be copied once.
    """

    def __init__(self):
        self._targets = {}

    def remember(self, source, target):
        self._targets[(type(source), source.pk)] = target.pk

    def target(self, model, source_pk):
        if source_pk is None:
            return None
        return self._targets.get((model, source_pk))


def _repoint(instance, copies):
    """Move `instance`'s foreign keys onto their copied parents; reports whether anything moved."""
    changed = False
    for field in instance._meta.concrete_fields:
        # A one-to-one field is also a single foreign key column, but Django does
        # not flag it as many-to-one.
        if field.many_to_one or field.one_to_one:
            replacement = copies.target(field.related_model, getattr(instance, field.attname))
            if replacement is not None and replacement != getattr(instance, field.attname):
                setattr(instance, field.attname, replacement)
                changed = True
    return changed


def _copy_row(instance, copies, **overrides):
    """An unsaved copy of `instance`, hanging off the copies of its parents."""
    values = {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
        if not field.primary_key
    }
    copy = instance._meta.model(**values)
    _repoint(copy, copies)
    for name, value in overrides.items():
        setattr(copy, name, value)
    return copy


def _next_version_number(model, **filters):
    return (model.objects.filter(**filters).aggregate(highest=Max("version"))["highest"] or 0) + 1


def _clone_cascade_rows(source, target, copies):
    """Copy everything Django would delete together with `source`.

    Following CASCADE alone keeps learner attempts and other shared rows out of
    the draft and picks up child models as they are added. All children are
    saved before any is re-pointed because one can refer to a sibling.
    """
    copies.remember(source, target)
    pairs = []
    for link in source._meta.related_objects:
        if not (link.one_to_many and link.on_delete is models.CASCADE and link.get_accessor_name()):
            continue
        for child in getattr(source, link.get_accessor_name()).all():
            if copies.target(type(child), child.pk) is not None:
                continue
            child_copy = _copy_row(child, copies)
            child_copy.save()
            copies.remember(child, child_copy)
            pairs.append((child, child_copy))
    for child, child_copy in pairs:
        if _repoint(child_copy, copies):
            child_copy.save()
    for child, child_copy in pairs:
        _clone_cascade_rows(child, child_copy, copies)


def _clone_question_versions(source_version, copies):
    """Give the draft its own questions, so editing it cannot change the live course."""
    for question_version in QuestionVersion.objects.filter(
        Q(lesson_checks__lesson__module__programme_version=source_version)
        | Q(assessment_items__assessment__programme_version=source_version)
    ).distinct():
        question = Question.objects.create(code=f"{question_version.question.code[:60]}-{uuid4().hex[:8]}")
        copy = _copy_row(question_version, copies, question=question, version=1, is_published=False)
        copy.save()
        copies.remember(question_version, copy)
        _clone_cascade_rows(question_version, copy, copies)


def _carry_completion_policy(source_version, new_version):
    """Keep the edition's completion settings for the new draft.

    Only Django admin sets these, and a version without a policy quietly stops
    recording completions and issuing certificates.
    """
    policy = getattr(source_version, "completion_policy", None)
    if policy is None:
        return
    CompletionPolicy.objects.create(
        programme_version=new_version,
        requires_instructor_approval=policy.requires_instructor_approval,
        certificate_template_version=policy.certificate_template_version,
        is_active=policy.is_active,
    )


def _clone_course_content(source_version, new_version):
    """Carry a course's authoring content into a fresh draft version."""
    copies = _CopiedRows()
    copies.remember(source_version, new_version)
    _clone_question_versions(source_version, copies)
    _carry_completion_policy(source_version, new_version)

    # Courses are copied before modules so each module lands in the draft's own
    # copy of its course.
    for course in source_version.courses.all():
        copy = _copy_row(course, copies, is_published=False)
        copy.save()
        copies.remember(course, copy)

    modules = []
    for module in source_version.modules.all():
        copy = _copy_row(module, copies, prerequisite=None, is_published=False)
        if module.cover_image:
            # The file is copied rather than shared: removing the draft's cover
            # must not take the published course's with it.
            copy.cover_image = ContentFile(
                module.cover_image.read(), name=module.cover_image.name.rsplit("/", 1)[-1]
            )
        copy.save()
        copies.remember(module, copy)
        modules.append((module, copy))
        for lesson in module.lessons.all():
            lesson_copy = _copy_row(lesson, copies, is_published=False)
            lesson_copy.save()
            # Resources are a shared library, so only the links to them are copied.
            lesson_copy.resources.set(lesson.resources.all())
            _clone_cascade_rows(lesson, lesson_copy, copies)
            # Uploaded images are copied and re-linked, so deleting them from the
            # published edition cannot blank a picture in the new draft.
            clone_lesson_images(lesson, lesson_copy, copies)
        for assessment in module.assessments.all():
            assessment_copy = _copy_row(assessment, copies, is_published=False)
            assessment_copy.save()
            _clone_cascade_rows(assessment, assessment_copy, copies)
        for practical in module.guided_practicals.all():
            _clone_scenario_version(practical, copies)

    # A module can depend on one copied after it, so prerequisites link in a second pass.
    for module, copy in modules:
        if module.prerequisite_id:
            copy.prerequisite_id = copies.target(Module, module.prerequisite_id)
            copy.save(update_fields=("prerequisite",))

    for assessment in source_version.assessments.filter(module__isnull=True):
        assessment_copy = _copy_row(assessment, copies, is_published=False)
        assessment_copy.save()
        _clone_cascade_rows(assessment, assessment_copy, copies)


def _clone_scenario_version(practical, copies):
    """Copy a guided practical and its rubric onto their own draft version."""
    copy = _copy_row(
        practical,
        copies,
        version=_next_version_number(ScenarioVersion, scenario=practical.scenario),
        status=ScenarioVersion.Status.DRAFT,
        published_at=None,
    )
    copy.save()
    copies.remember(practical, copy)
    _clone_cascade_rows(practical, copy, copies)

    rubric_version = getattr(practical, "rubric_version", None)
    if rubric_version is not None:
        rubric_copy = _copy_row(
            rubric_version,
            copies,
            version=_next_version_number(RubricVersion, rubric=rubric_version.rubric),
            status=RubricVersion.Status.DRAFT,
            published_at=None,
        )
        rubric_copy.save()
        _clone_cascade_rows(rubric_version, rubric_copy, copies)


@login_required
@require_POST
@transaction.atomic
def course_revert_to_draft(request, version_id):
    """Create a new editable draft from a published/retired course."""
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_related("programme"),
        pk=version_id,
    )
    if version.status == ProgrammeVersion.Status.DRAFT:
        messages.info(request, "This course is already a draft.")
        return redirect("course-builder-detail", version_id=version.pk)
    next_ver = (
        ProgrammeVersion.objects.filter(programme=version.programme)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or 0
    ) + 1
    new_version = ProgrammeVersion.objects.create(
        programme=version.programme,
        version=next_ver,
        status=ProgrammeVersion.Status.DRAFT,
    )
    _clone_course_content(version, new_version)
    messages.success(
        request,
        "Draft v" + str(new_version.version) + ' of "' + version.programme.name + '" created with a copy of its modules, lessons and assessments. '
        "The published version remains active for enrolled students.",
    )
    return redirect("course-builder-detail", version_id=new_version.pk)


@login_required
@transaction.atomic
def module_create(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion, pk=version_id, status="draft")
    if request.method != "POST":
        return redirect("course-builder-detail", version_id=version.pk)
    form = ModuleCreateForm(version, request.POST)
    if form.is_valid():
        Module.objects.create(
            programme_version=version,
            course=form.cleaned_data.get("course"),
            code=_unique_slug(Module, "code", form.cleaned_data["title"], programme_version=version),
            title=form.cleaned_data["title"],
            description=form.cleaned_data["description"],
            order=version.modules.count() + 1,
        )
        messages.success(request, "Module added. You can now build its first lesson.")
    else:
        messages.error(request, "Please correct the module form.")
    return redirect("course-builder-detail", version_id=version.pk)


@login_required
def lesson_builder(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    return render_student_page(request, "instructor_portal/lesson_create.html", {"module": module, "form": LessonEditForm()})


@login_required
@transaction.atomic
def lesson_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    if request.method != "POST":
        return redirect("lesson-builder", module_id=module.pk)
    form = LessonEditForm(request.POST)
    if not form.is_valid():
        return render_student_page(request, "instructor_portal/lesson_create.html", {"module": module, "form": form}, status=400)

    data = form.cleaned_data
    lesson = Lesson.objects.create(
        module=module,
        slug=_unique_slug(Lesson, "slug", data["title"], module=module),
        title=data["title"],
        summary=data["summary"],
        objectives=data.get("objectives", ""),
        key_terms=data.get("key_terms", ""),
        order=module.lessons.count() + 1,
    )
    messages.success(request, "Lesson created.")
    return redirect(f'{reverse("module-edit", args=[module.pk])}?tab=lessons')


@login_required
@require_POST
@transaction.atomic
def lesson_delete(request, lesson_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_for_update().select_related("module__programme_version"),
        pk=lesson_id,
        module__programme_version__status=ProgrammeVersion.Status.DRAFT,
    )
    checks = lesson.knowledge_checks.all()
    if lesson.progress_records.exists() or checks.filter(responses__isnull=False).exists():
        messages.error(request, "This lesson cannot be deleted because it already has learner activity.")
        return redirect(f'{reverse("module-edit", args=[lesson.module_id])}?tab=lessons')

    question_versions = list(QuestionVersion.objects.filter(lesson_checks__lesson=lesson).select_related("question").distinct())
    AssessmentItem.objects.filter(question_version__in=question_versions).delete()
    checks.delete()
    module_id = lesson.module_id
    title = lesson.title
    lesson.delete()
    for question_version in question_versions:
        if not (
            question_version.assessment_items.exists()
            or question_version.attempt_items.exists()
            or question_version.responses.exists()
            or question_version.lesson_checks.exists()
        ):
            question = question_version.question
            question_version.delete()
            if not question.versions.exists():
                question.delete()
    messages.success(request, f'Lesson “{title}” deleted.')
    return redirect(f'{reverse("module-edit", args=[module_id])}?tab=lessons')


@login_required
def practical_builder(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    return render_student_page(request, "instructor_portal/practical_builder.html", {"module": module, "form": PracticalCreateForm()})


@login_required
def practical_builder_index(request):
    _require_instructor(request.user)
    practicals = ScenarioVersion.objects.select_related(
        "scenario", "module__programme_version__programme"
    ).prefetch_related("states", "documents").order_by("-module__programme_version__version", "scenario__title")
    draft_modules = Module.objects.select_related("programme_version__programme").filter(
        programme_version__status=ProgrammeVersion.Status.DRAFT
    ).order_by("programme_version__programme__name", "order", "title")
    return render_student_page(request, "instructor_portal/practical_builder_index.html", {
        "practicals": practicals,
        "draft_modules": draft_modules,
        "draft_count": practicals.filter(status=ScenarioVersion.Status.DRAFT).count(),
        "published_count": practicals.filter(status=ScenarioVersion.Status.PUBLISHED).count(),
    })


@login_required
@transaction.atomic
def practical_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    if request.method != "POST":
        return redirect("practical-builder", module_id=module.pk)
    form = PracticalCreateForm(request.POST)
    if not form.is_valid():
        return render_student_page(request, "instructor_portal/practical_builder.html", {"module": module, "form": form}, status=400)
    data = form.cleaned_data
    scenario = Scenario.objects.create(code=_unique_slug(Scenario, "code", data["title"]), title=data["title"], area=data["area"])
    practical = ScenarioVersion.objects.create(
        scenario=scenario,
        module=module,
        version=1,
        assistance_mode=data["assistance_mode"],
        purpose=ScenarioVersion.Purpose.PRACTICE,
        reference_status=ScenarioVersion.ReferenceStatus.CONCEPTUAL,
        maximum_attempts=data["maximum_attempts"],
        briefing=data["briefing"],
        learning_objective=data["learning_objective"],
        initial_data={},
    )
    states = []
    for order, label in enumerate(data["steps"], start=1):
        states.append(ScenarioState.objects.create(scenario_version=practical, key=f"step-{order}", label=label, guidance=f"Complete this training step: {label}.", order=order, is_initial=order == 1))
    terminal = ScenarioState.objects.create(scenario_version=practical, key="complete", label="Practical complete", guidance="The guided flow is complete.", order=len(states) + 1, is_terminal=True)
    for order, state in enumerate(states, start=1):
        target = states[order] if order < len(states) else terminal
        label = data["steps"][order - 1]
        ScenarioActionDefinition.objects.create(
            scenario_version=practical,
            code=f"complete-step-{order}",
            label=label,
            from_state=state,
            to_state=target,
            effects={f"step_{order}_completed": True},
            success_feedback=f"{label} completed in the training flow.",
            beginner_hint=f"The next guided action is: {label}.",
            order=order,
        )
    rubric = Rubric.objects.create(code=_unique_slug(Rubric, "code", f"{scenario.code}-rubric"), title=f"{scenario.title} Completion Rubric")
    rubric_version = RubricVersion.objects.create(rubric=rubric, version=1, scenario_version=practical, pass_percentage=70, is_demonstration=True)
    RubricCriterion.objects.create(rubric_version=rubric_version, code="complete-flow", title="Complete the guided practical flow", dimension=RubricCriterion.Dimension.COMPLETION, maximum_points=100, mandatory=True, evaluation_rule={"type": "completion"}, order=1)
    messages.success(request, "Guided practical flow created as a draft. Configure its stages and validation next.")
    return redirect("practical-edit", scenario_version_id=practical.pk)


@login_required
@require_POST
def module_move(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version"), pk=module_id, programme_version__status="draft")
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        messages.error(request, "Unknown move direction.")
    elif move_module_order(module, direction):
        messages.success(request, "Module order updated.")
    return redirect("course-builder-detail", version_id=module.programme_version_id)


@login_required
@require_POST
def lesson_move(request, lesson_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson.objects.select_related("module__programme_version"), pk=lesson_id, module__programme_version__status="draft")
    direction = request.POST.get("direction")
    if direction not in ("up", "down"):
        messages.error(request, "Unknown move direction.")
    elif move_lesson_order(lesson, direction):
        messages.success(request, "Lesson order updated.")
    return redirect("course-builder-detail", version_id=lesson.module.programme_version_id)


def _draft_assessment(assessment_id):
    return get_object_or_404(
        Assessment.objects.select_related("programme_version", "module"),
        pk=assessment_id,
        programme_version__status="draft",
    )


@login_required
def module_assessment_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version"), pk=module_id, programme_version__status="draft")
    existing = module.assessments.filter(assessment_type=Assessment.Type.MODULE).first()
    if existing:
        messages.info(request, "This module already has an assessment — edit it instead.")
        return redirect("assessment-edit", assessment_id=existing.pk)
    form = AssessmentSettingsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assessment = Assessment.objects.create(
            programme_version=module.programme_version,
            module=module,
            title=form.cleaned_data["title"],
            assessment_type=Assessment.Type.MODULE,
            pass_percentage=form.cleaned_data["pass_percentage"],
            maximum_attempts=form.cleaned_data["maximum_attempts"],
            randomize_questions=form.cleaned_data["randomize_questions"],
        )
        messages.success(request, "Module assessment created. Add its first question.")
        return redirect("assessment-edit", assessment_id=assessment.pk)
    return render_student_page(
        request,
        "instructor_portal/assessment_create.html",
        {"form": form, "heading": "Create the module assessment for the module", "module": module, "back_url": reverse("course-builder-detail", args=[module.programme_version_id])},
    )


@login_required
def final_exam_create(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion.objects.select_related("programme"), pk=version_id, status="draft")
    existing = version.assessments.filter(assessment_type=Assessment.Type.FINAL_THEORY).first()
    if existing:
        messages.info(request, "This course already has a final theory examination — edit it instead.")
        return redirect("assessment-edit", assessment_id=existing.pk)
    form = AssessmentSettingsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assessment = Assessment.objects.create(
            programme_version=version,
            title=form.cleaned_data["title"],
            assessment_type=Assessment.Type.FINAL_THEORY,
            pass_percentage=form.cleaned_data["pass_percentage"],
            maximum_attempts=form.cleaned_data["maximum_attempts"],
            randomize_questions=form.cleaned_data["randomize_questions"],
        )
        messages.success(request, "Final theory examination created. Add its first question.")
        return redirect("assessment-edit", assessment_id=assessment.pk)
    return render_student_page(
        request,
        "instructor_portal/assessment_create.html",
        {"form": form, "heading": "Create the final theory examination", "back_url": reverse("course-builder-detail", args=[version.pk])},
    )


@login_required
def assessment_edit(request, assessment_id):
    _require_instructor(request.user)
    assessment = _draft_assessment(assessment_id)
    form = AssessmentSettingsForm(
        request.POST or None,
        initial={
            "title": assessment.title,
            "pass_percentage": assessment.pass_percentage,
            "maximum_attempts": assessment.maximum_attempts,
            "randomize_questions": assessment.randomize_questions,
        },
    )
    if request.method == "POST" and form.is_valid():
        assessment.title = form.cleaned_data["title"]
        assessment.pass_percentage = form.cleaned_data["pass_percentage"]
        assessment.maximum_attempts = form.cleaned_data["maximum_attempts"]
        assessment.randomize_questions = form.cleaned_data["randomize_questions"]
        assessment.save(update_fields=("title", "pass_percentage", "maximum_attempts", "randomize_questions"))
        messages.success(request, "Assessment updated.")
        return redirect("assessment-edit", assessment_id=assessment.pk)
    questions = assessment.items.select_related("question_version").order_by("order", "id")
    return render_student_page(request, "instructor_portal/assessment_edit.html", {"assessment": assessment, "form": form, "questions": questions})


@login_required
def assessment_question_add(request, assessment_id):
    _require_instructor(request.user)
    assessment = _draft_assessment(assessment_id)
    form = AssessmentQuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save(assessment)
        messages.success(request, "Question added.")
        return redirect("assessment-edit", assessment_id=assessment.pk)
    return render_student_page(
        request,
        "instructor_portal/assessment_question_form.html",
        {"assessment": assessment, "form": form, "heading": "Add a question", "back_url": reverse("assessment-edit", args=[assessment.pk])},
    )


@login_required
def assessment_question_edit(request, assessment_id, question_version_id):
    assessment = _draft_assessment(assessment_id)
    question_version = get_object_or_404(QuestionVersion, pk=question_version_id, assessment_items__assessment=assessment)
    options = list(question_version.options.order_by("order"))
    initial = {"prompt": question_version.prompt, "points": question_version.points, "explanation": question_version.explanation}
    for index, option in enumerate(options, start=1):
        initial[f"option_{index}"] = option.label
    correct = next((option for option in options if option.is_correct), None)
    if correct:
        initial["correct_position"] = str(options.index(correct) + 1)
    form = AssessmentQuestionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save(assessment, question_version)
        messages.success(request, "Question updated.")
        return redirect("assessment-edit", assessment_id=assessment.pk)
    return render_student_page(
        request,
        "instructor_portal/assessment_question_form.html",
        {
            "assessment": assessment,
            "form": form,
            "heading": "Edit question",
            "question_version": question_version,
            "back_url": reverse("assessment-edit", args=[assessment.pk]),
        },
    )


@login_required
@require_POST
def assessment_question_delete(request, assessment_id, question_version_id):
    assessment = _draft_assessment(assessment_id)
    item = get_object_or_404(AssessmentItem, assessment=assessment, question_version_id=question_version_id)
    question_version = item.question_version
    item.delete()
    question_version.delete()  # draft-only: nothing references a draft question version
    messages.success(request, "Question removed.")
    return redirect("assessment-edit", assessment_id=assessment.pk)


def _lesson_section_context(lesson):
    """Shared section layout for the student delivery view and preview."""
    blocks = list(lesson.blocks.order_by("order", "id"))
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
    concept_blocks = [b for b in blocks if b.kind == "text"]
    example_blocks = [b for b in blocks if b.kind == "example"]
    notice_blocks = [b for b in blocks if b.kind == "notice"]
    concept_block = concept_blocks[0] if concept_blocks else None
    example_block = example_blocks[0] if example_blocks else None
    notice_block = notice_blocks[0] if notice_blocks else None
    sections = []
    if objectives:
        sections.append({"slug": "objectives", "title": "Objectives", "stage": "Orient"})
    if concept_block:
        sections.append({"slug": "concepts", "title": concept_block.heading or "Key concepts", "stage": "Learn"})
    if example_block:
        sections.append({"slug": "example", "title": example_block.heading or "Worked example", "stage": "Apply"})
    if notice_block:
        sections.append({"slug": "note", "title": notice_block.heading or "Important note", "stage": "Remember"})
    if checks:
        sections.append({"slug": "practice", "title": "Practice", "stage": "Practise"})
    if not sections:
        sections.append({"slug": "concepts", "title": "Lesson", "stage": "Learn"})
    word_count = sum(count_words(block.body) for block in blocks)
    return {
        "blocks": blocks,
        "checks": checks,
        "objectives": objectives,
        "key_terms": key_terms,
        "concept_block": concept_block,
        "example_block": example_block,
        "notice_block": notice_block,
        "concept_blocks": concept_blocks,
        "example_blocks": example_blocks,
        "notice_blocks": notice_blocks,
        "sections": sections,
        "lessons_in_module": list(lesson.module.lessons.order_by("order", "title")),
        "reading_minutes": max(1, round(word_count / 200)),
    }


@login_required
@require_GET
def lesson_preview(request, lesson_id):
    """Read-only instructor preview of the lesson's first section in the
    student presentation. No progress rows are created and the view answers
    GET only, so the lesson forms can never mutate anything."""
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson.objects.select_related("module__programme_version__programme"), pk=lesson_id)
    context = _lesson_section_context(lesson)
    sections = context["sections"]
    requested = request.GET.get("section")
    index = next((i for i, item in enumerate(sections) if item["slug"] == requested), 0)
    for i, item in enumerate(sections):
        item["url"] = reverse("lesson-preview", args=[lesson.pk]) + f"?section={item['slug']}"
        item["index"] = i
        item["state"] = "done" if i < index else ("current" if i == index else "todo")
    step_slug = sections[index]["slug"]
    step_blocks = {
        "concepts": context["concept_blocks"],
        "example": context["example_blocks"],
        "note": context["notice_blocks"],
        "practice": context["checks"],
    }.get(step_slug, [])
    try:
        requested_part = int(request.GET.get("part", 1))
    except (TypeError, ValueError):
        requested_part = 1
    parts = part_window(len(step_blocks), requested_part)
    preview_base = reverse("lesson-preview", args=[lesson.pk])

    def preview_part_url(number):
        return f"{preview_base}?section={step_slug}&part={number}"

    if requested_part != parts["index"]:
        # The preview answers a bad part number the same way the learner route
        # does: it shows the part that exists.
        return redirect((preview_base + f"?section={step_slug}") if parts["index"] == 1 else preview_part_url(parts["index"]))

    context.update(
        {
            "lesson": lesson,
            "module": lesson.module,
            "preview_mode": True,
            "current_index": index,
            "current_section": sections[index],
            "concepts_url": next((item["url"] for item in sections if item["slug"] == "concepts"), ""),
            "prev_section": sections[index - 1] if index > 0 else None,
            "next_section": sections[index + 1] if index < len(sections) - 1 else None,
            "parts": parts,
            "part_units": [step_blocks[parts["index"] - 1]] if parts["paged"] else step_blocks,
            "prev_part_url": preview_part_url(parts["index"] - 1) if parts["paged"] and parts["index"] > 1 else None,
            "next_part_url": preview_part_url(parts["index"] + 1) if parts["paged"] and parts["index"] < parts["total"] else None,
            "progress": LessonProgress(lesson=lesson),
        }
    )
    return render_student_page(request, "learning/lesson.html", context)


@login_required
@require_GET
def assessment_preview(request, assessment_id):
    """Read-only instructor preview of a draft or published assessment.
    No TheoryAttempt is created and nothing is scored."""
    _require_instructor(request.user)
    assessment = get_object_or_404(Assessment.objects.select_related("programme_version", "module"), pk=assessment_id)
    items = assessment.items.select_related("question_version").prefetch_related("question_version__options").order_by("order", "id")
    return render_student_page(
        request,
        "assessments/assessment_preview.html",
        {"assessment": assessment, "items": items, "preview_mode": True},
    )


@login_required
@require_GET
def practical_preview(request, scenario_version_id):
    """Read-only instructor preview of a guided practical: briefing, stages,
    and reference documents. No attempt exists and none is created."""
    _require_instructor(request.user)
    practical = get_object_or_404(
        ScenarioVersion.objects.select_related("scenario", "module__programme_version__programme"),
        pk=scenario_version_id,
    )
    return render_student_page(
        request,
        "scenarios/practical_preview.html",
        {
            "practical": practical,
            "preview_mode": True,
            "states": practical.states.order_by("order"),
            "bills_of_lading": practical.bills_of_lading.all(),
            "commercial_documents": practical.commercial_documents.all(),
            "documents": practical.documents.all(),
        },
    )


@login_required
@require_GET
def course_preview(request, version_id):
    """The course overview exactly as an enrolled student sees it.

    Draft content is included and no enrolment is consulted, so nothing here
    can be completed, scored or recorded.
    """
    _require_instructor(request.user)
    version = get_object_or_404(
        ProgrammeVersion.objects.select_related("programme").prefetch_related(
            "modules__lessons__blocks", "modules__lessons__resources", "modules__assessments"
        ),
        pk=version_id,
    )
    return render_student_page(request, "learning/roadmap.html", {
        **roadmap_context(version, None),
        "preview_mode": True,
    })


@login_required
@require_GET
def module_preview(request, module_id):
    """A single module overview as an enrolled student sees it, draft included."""
    _require_instructor(request.user)
    module = get_object_or_404(
        Module.objects.select_related("programme_version__programme").prefetch_related(
            "lessons__blocks", "lessons__resources", "assessments"
        ),
        pk=module_id,
    )
    return render_student_page(request, "learning/module_overview.html", {
        **module_overview_context(module, None),
        "preview_mode": True,
    })


def _apply_cover(instance, form):
    """Assign or clear a cover image; returns the name of a replaced file."""
    previous = instance.cover_image.name if instance.cover_image else ""
    if form.cleaned_data.get("clear_cover_image") and previous:
        instance.cover_image.delete(save=False)
        instance.cover_image = None
        return ""
    elif form.cleaned_data.get("cover_image"):
        instance.cover_image = form.cleaned_data["cover_image"]
    return previous if previous and previous != instance.cover_image.name else ""


def _delete_replaced_cover(instance, replaced_name):
    # The new file is only written on save(), so the old one goes afterwards.
    if replaced_name:
        instance.cover_image.storage.delete(replaced_name)


@login_required
def course_edit(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion.objects.select_related("programme"), pk=version_id, status="draft")
    programme = version.programme
    form = CourseEditForm(
        request.POST or None,
        request.FILES or None,
        initial={
            "name": programme.name,
            "description": programme.description,
            "overview_summary": programme.overview_summary,
            "target_audience": programme.target_audience,
            "learning_approach": programme.learning_approach,
            "learning_outcomes": programme.learning_outcomes,
            "difficulty": programme.difficulty,
            "estimated_weeks": programme.estimated_weeks,
        },
    )
    if request.method == "POST" and form.is_valid():
        tab = request.POST.get("tab", "basic")
        if tab == "basic":
            programme.name = form.cleaned_data["name"]
            programme.description = form.cleaned_data.get("description", "")
            replaced = _apply_cover(programme, form)
            programme.save(update_fields=("name", "description", "cover_image"))
            _delete_replaced_cover(programme, replaced)
            messages.success(request, "Basic information saved.")
        elif tab == "overview":
            programme.overview_summary = form.cleaned_data.get("overview_summary", "")
            programme.target_audience = form.cleaned_data.get("target_audience", "")
            programme.learning_outcomes = form.cleaned_data.get("learning_outcomes", "")
            programme.learning_approach = form.cleaned_data.get("learning_approach", "")
            programme.save(update_fields=("overview_summary", "target_audience", "learning_outcomes", "learning_approach"))
            messages.success(request, "Course overview saved.")
        elif tab == "settings":
            programme.difficulty = form.cleaned_data.get("difficulty", "")
            programme.estimated_weeks = form.cleaned_data.get("estimated_weeks") or None
            programme.save(update_fields=("difficulty", "estimated_weeks"))
            messages.success(request, "Course settings saved.")
        return redirect(f'{reverse("course-edit", args=[version.pk])}?tab={tab}')
    return render_student_page(
        request,
        "instructor_portal/course_edit.html",
        {
            "version": version,
            "form": form,
            "skill_count": len([line for line in (form["learning_outcomes"].value() or "").splitlines() if line.strip()]),
            "method_count": len([line for line in (form["learning_approach"].value() or "").splitlines() if line.strip()]),
        },
    )


@login_required
def module_edit(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    form = ModuleEditForm(module, request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        module.title = form.cleaned_data["title"]
        module.description = form.cleaned_data["description"]
        if "course" in request.POST:
            # A form that does not offer the choice must not detach the module
            # from its course.
            module.course = form.cleaned_data["course"]
        module.difficulty = form.cleaned_data["difficulty"]
        module.prerequisite = form.cleaned_data["prerequisite"]
        replaced = _apply_cover(module, form)
        module.save(update_fields=("title", "description", "course", "difficulty", "prerequisite", "cover_image"))
        _delete_replaced_cover(module, replaced)
        messages.success(request, "Module updated.")
        return redirect("course-builder-detail", version_id=module.programme_version_id)
    return render_student_page(request, "instructor_portal/module_edit.html", {
        "module": module,
        "form": form,
        "lesson_form": LessonEditForm(),
    })


def _annotate_section_numbers(block_formset):
    """Give each section form its number within its own kind (Key concept 1, 2…).

    The learner meets sections in one list, but authors think in kinds; the
    per-kind number is what makes "move these two key concepts together"
    legible on the page.
    """
    seen = {}
    for block_form in block_formset:
        kind = block_form.instance.kind
        seen[kind] = seen.get(kind, 0) + 1
        block_form.kind_index = seen[kind]


@login_required
def lesson_edit(request, lesson_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson.objects.select_related("module__programme_version"), pk=lesson_id, module__programme_version__status="draft")
    lesson_form = LessonEditForm(request.POST or None, initial={"title": lesson.title, "summary": lesson.summary, "objectives": lesson.objectives, "key_terms": lesson.key_terms})
    block_formset = BlockFormSet(request.POST or None, queryset=lesson.blocks.order_by("order"))
    _annotate_section_numbers(block_formset)
    checks = list(lesson.knowledge_checks.select_related("question_version").order_by("order", "id"))
    check = checks[0] if checks else None
    check_form = LessonCheckEditForm(check.question_version, request.POST or None) if check else None
    if request.method == "POST" and lesson_form.is_valid() and block_formset.is_valid() and (check_form is None or check_form.is_valid()):
        lesson.title = lesson_form.cleaned_data["title"]
        lesson.summary = lesson_form.cleaned_data["summary"]
        lesson.objectives = lesson_form.cleaned_data["objectives"]
        lesson.key_terms = lesson_form.cleaned_data["key_terms"]
        lesson.save(update_fields=("title", "summary", "objectives", "key_terms"))
        block_formset.save()
        prune_rich_text_images(lesson)
        if check_form:
            check_form.save()
        messages.success(request, "Lesson updated.")
        active_tab = request.POST.get("active_tab", "details")
        if active_tab not in {"details", "sections", "practice", "review"}:
            active_tab = "details"
        return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab={active_tab}')
    return render_student_page(
        request,
        "instructor_portal/lesson_edit.html",
        {
            "lesson": lesson,
            "lesson_form": lesson_form,
            "block_formset": block_formset,
            "check_form": check_form,
            "checks": checks,
            "block_count": lesson.blocks.count(),
            "objective_count": len([line for line in (lesson_form["objectives"].value() or "").splitlines() if line.strip()]),
            "key_term_count": len([line for line in (lesson_form["key_terms"].value() or "").splitlines() if line.strip()]),
        },
    )


def _draft_lesson(lesson_id):
    return get_object_or_404(
        Lesson.objects.select_related("module__programme_version"),
        pk=lesson_id,
        module__programme_version__status="draft",
    )


@login_required
@require_POST
def lesson_section_add(request, lesson_id):
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    kind = request.POST.get("kind")
    headings = {
        ContentBlock.Kind.TEXT: "Key concept",
        ContentBlock.Kind.EXAMPLE: "Worked example",
        ContentBlock.Kind.NOTICE: "Important note",
    }
    if kind not in headings:
        messages.error(request, "Choose a valid lesson section type.")
        return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=sections')
    next_order = (lesson.blocks.aggregate(value=Max("order"))["value"] or 0) + 1
    ContentBlock.objects.create(lesson=lesson, kind=kind, heading=headings[kind], body="", order=next_order)
    messages.success(request, "Lesson section added.")
    return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=sections')


@login_required
@require_POST
@transaction.atomic
def lesson_section_move(request, lesson_id, block_id):
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    block = get_object_or_404(ContentBlock, pk=block_id, lesson=lesson)
    direction = request.POST.get("direction")
    # Siblings are every section of the lesson, in the exact order the learner
    # meets them: moving swaps with the adjacent section, so several sections
    # of one kind can be gathered together instead of leaping past other kinds.
    siblings = list(lesson.blocks.order_by("order", "id"))
    index = next(i for i, item in enumerate(siblings) if item.pk == block.pk)
    neighbour_index = index - 1 if direction == "up" else index + 1 if direction == "down" else None
    if neighbour_index is not None and 0 <= neighbour_index < len(siblings):
        neighbour = siblings[neighbour_index]
        block.order, neighbour.order = neighbour.order, block.order
        block.save(update_fields=("order",))
        neighbour.save(update_fields=("order",))
        messages.success(request, "Lesson section moved.")
    return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=sections')


@login_required
@require_POST
@transaction.atomic
def lesson_section_delete(request, lesson_id, block_id):
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    block = get_object_or_404(ContentBlock, pk=block_id, lesson=lesson)
    replacement = lesson.blocks.exclude(pk=block.pk).order_by("order", "id").first()
    if replacement is None:
        messages.error(request, "A lesson must retain at least one content section.")
    else:
        block.knowledge_checks.update(after_block=replacement)
        block.delete()
        prune_rich_text_images(lesson)
        messages.success(request, "Lesson section removed.")
    return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=sections')


@login_required
@require_POST
def lesson_rich_image_upload(request, lesson_id):
    """Store an image pasted into the section editor and return where to show it.

    The lesson's sections are the only place these files appear, and they stay
    behind the login gate because ``lesson_rich_text/`` is not a public prefix.
    """
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "Choose an image file."}, status=400)
    try:
        image = store_rich_text_image(lesson, upload, created_by=request.user)
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    alt = (request.POST.get("alt") or "").strip()[:180]
    width, height = rich_image_size(image)
    return JsonResponse({"url": image.file.url, "alt": alt, "width": width, "height": height})


@login_required
@transaction.atomic
def lesson_practice_add(request, lesson_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__programme_version"),
        pk=lesson_id,
        module__programme_version__status="draft",
    )
    form = LessonPracticeQuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        after_block = lesson.blocks.order_by("order", "id").first()
        if after_block is None:
            form.add_error(None, "Add a lesson content section before adding a practice question.")
            return render_student_page(
                request,
                "instructor_portal/lesson_practice_question_form.html",
                {"lesson": lesson, "form": form, "heading": "Add practice question"},
                status=400,
            )
        data = form.cleaned_data
        question = Question.objects.create(code=_unique_slug(Question, "code", data["prompt"][:60]))
        question_version = QuestionVersion.objects.create(
            question=question,
            version=1,
            prompt=data["prompt"],
            explanation=data.get("explanation", ""),
            points=data["points"],
        )
        for order, (position, label) in enumerate(data["completed_options"], start=1):
            AnswerOption.objects.create(
                question_version=question_version,
                label=label,
                is_correct=str(position) == data["correct_position"],
                order=order,
            )
        next_order = (lesson.knowledge_checks.aggregate(value=Max("order"))["value"] or 0) + 1
        LessonCheck.objects.create(
            lesson=lesson,
            after_block=after_block,
            question_version=question_version,
            order=next_order,
        )
        if data.get("add_to_assessment"):
            module = lesson.module
            assessment, _ = Assessment.objects.get_or_create(
                programme_version=module.programme_version,
                module=module,
                assessment_type=Assessment.Type.MODULE,
                defaults={"title": f"{module.title} Module Assessment", "pass_percentage": 70, "maximum_attempts": 3},
            )
            AssessmentItem.objects.get_or_create(
                assessment=assessment,
                question_version=question_version,
                defaults={"order": assessment.items.count() + 1},
            )
        messages.success(request, "Practice question added.")
        return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=practice')
    return render_student_page(
        request,
        "instructor_portal/lesson_practice_question_form.html",
        {"lesson": lesson, "form": form, "heading": "Add practice question"},
    )


@login_required
@transaction.atomic
def lesson_practice_edit(request, lesson_id, check_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson, pk=lesson_id, module__programme_version__status="draft")
    check = get_object_or_404(
        LessonCheck.objects.select_related("question_version").prefetch_related("question_version__options"),
        pk=check_id,
        lesson=lesson,
    )
    form = LessonCheckEditForm(check.question_version, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Practice question updated.")
        return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=practice')
    return render_student_page(
        request,
        "instructor_portal/lesson_practice_question_form.html",
        {"lesson": lesson, "form": form, "heading": "Edit practice question", "check": check},
    )


@login_required
@require_POST
def lesson_practice_delete(request, lesson_id, check_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson, pk=lesson_id, module__programme_version__status="draft")
    check = get_object_or_404(LessonCheck, pk=check_id, lesson=lesson)
    check.delete()
    messages.success(request, "Practice question removed.")
    return redirect(f'{reverse("lesson-edit", args=[lesson.pk])}?tab=practice')


@login_required
def practical_edit(request, scenario_version_id):
    _require_instructor(request.user)
    practical = get_object_or_404(
        ScenarioVersionModel.objects.select_related("module__programme_version", "scenario"),
        pk=scenario_version_id,
        module__programme_version__status="draft",
    )
    practical_form = PracticalEditForm(
        request.POST or None,
        initial={
            "title": practical.scenario.title,
            "area": practical.scenario.area,
            "briefing": practical.briefing,
            "learning_objective": practical.learning_objective,
            "assistance_mode": practical.assistance_mode,
            "maximum_attempts": practical.maximum_attempts,
            "purpose": practical.purpose,
            "reference_status": practical.reference_status,
        },
    )
    state_formset = ScenarioStateFormSet(
        request.POST or None,
        queryset=practical.states.filter(is_terminal=False).order_by("order"),
    )
    documents_submitted = request.method == "POST" and "documents-TOTAL_FORMS" in request.POST
    document_formset = ScenarioDocumentFormSet(
        request.POST if documents_submitted else None,
        queryset=practical.documents.order_by("order", "title"),
        prefix="documents",
    )
    forms_valid = practical_form.is_valid() and state_formset.is_valid() and (
        document_formset.is_valid() if documents_submitted else True
    )
    remaining_states = [
        form for form in state_formset.forms
        if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("label")
    ] if state_formset.is_valid() else []
    if request.method == "POST" and forms_valid and not remaining_states:
        state_formset._non_form_errors = state_formset.error_class(["Add at least one practical stage."])
        forms_valid = False
    if request.method == "POST" and forms_valid:
        practical.scenario.title = practical_form.cleaned_data.get("title") or practical.scenario.title
        practical.scenario.area = practical_form.cleaned_data.get("area") or practical.scenario.area
        practical.scenario.save(update_fields=("title", "area"))
        practical.briefing = practical_form.cleaned_data["briefing"]
        practical.learning_objective = practical_form.cleaned_data["learning_objective"]
        practical.assistance_mode = practical_form.cleaned_data["assistance_mode"]
        practical.maximum_attempts = practical_form.cleaned_data["maximum_attempts"]
        practical.purpose = practical_form.cleaned_data.get("purpose") or practical.purpose
        practical.reference_status = practical_form.cleaned_data.get("reference_status") or practical.reference_status
        practical.save(update_fields=("briefing", "learning_objective", "assistance_mode", "maximum_attempts", "purpose", "reference_status"))

        # Rebuild the linear transition graph after stage additions, removals,
        # or reordering so the learner always follows the instructor's order.
        practical.action_definitions.all().delete()
        state_formset.save(commit=False)
        for deleted in state_formset.deleted_objects:
            deleted.delete()
        ordered_states = []
        for form in sorted(remaining_states, key=lambda item: item.cleaned_data.get("ORDER") or 9999):
            state = form.save(commit=False)
            state.scenario_version = practical
            state.order = len(ordered_states) + 1
            state.is_initial = state.order == 1
            state.is_terminal = False
            if not state.key:
                state.key = f"step-{uuid4().hex[:10]}"
            state.save()
            ordered_states.append(state)
        practical.states.filter(is_terminal=False).exclude(pk__in=[state.pk for state in ordered_states]).delete()
        terminal = practical.states.filter(is_terminal=True).first()
        if terminal is None:
            terminal = ScenarioState.objects.create(
                scenario_version=practical, key="complete", label="Practical complete",
                guidance="The guided flow is complete.", is_terminal=True,
            )
        terminal.order = len(ordered_states) + 1
        terminal.save(update_fields=("order",))
        for order, state in enumerate(ordered_states, start=1):
            target = ordered_states[order] if order < len(ordered_states) else terminal
            ScenarioActionDefinition.objects.create(
                scenario_version=practical,
                code=f"complete-step-{order}",
                label=state.label,
                from_state=state,
                to_state=target,
                effects={f"step_{order}_completed": True},
                success_feedback=f"{state.label} completed in the training flow.",
                beginner_hint=f"The next guided action is: {state.label}.",
                order=order,
            )

        if documents_submitted:
            documents = document_formset.save(commit=False)
            for deleted in document_formset.deleted_objects:
                deleted.delete()
            for document in documents:
                document.scenario_version = practical
                document.order = document.pk and document.order or practical.documents.count() + 1
                document.save()
        messages.success(request, "Guided practical updated.")
        return redirect("practical-edit", scenario_version_id=practical.pk)
    return render_student_page(
        request,
        "instructor_portal/practical_edit.html",
        {
            "practical": practical,
            "practical_form": practical_form,
            "state_formset": state_formset,
            "document_formset": document_formset,
            "state_count": practical.states.filter(is_terminal=False).count(),
        },
    )


@login_required
def student_detail(request, enrolment_id):
    _require_instructor(request.user)
    enrolment = get_object_or_404(
        _instructor_enrolments(request.user).prefetch_related(
            "lesson_progress__lesson__module",
            "module_progress__module",
            "theory_attempts__assessment",
            "scenario_attempts__scenario_version__scenario",
        ),
        pk=enrolment_id,
    )
    return render_student_page(request, "instructor_portal/student_detail.html", {"enrolment": enrolment})


def _instructor_enrolments(user):
    queryset = Enrolment.objects.select_related("student", "programme_version__programme", "enrolled_by")
    if user.is_superuser or user.groups.filter(name="Administrator").exists():
        return queryset
    return queryset.filter(enrolled_by=user)


@login_required
def student_list(request):
    _require_instructor(request.user)
    enrolments = list(_instructor_enrolments(request.user).order_by("student__first_name", "student__last_name", "-enrolled_at"))
    students = {}
    for enrolment in enrolments:
        item = students.setdefault(enrolment.student_id, {"student": enrolment.student, "enrolments": []})
        item["enrolments"].append(enrolment)
    return render_student_page(request, "instructor_portal/student_list.html", {
        "students": list(students.values()),
        "enrolment_count": len(enrolments),
    })


@login_required
def student_profile(request, user_id):
    _require_instructor(request.user)
    enrolments = _instructor_enrolments(request.user).filter(student_id=user_id).prefetch_related(
        "lesson_progress", "module_progress", "theory_attempts", "scenario_attempts"
    ).order_by("-enrolled_at")
    enrolments = list(enrolments)
    if not enrolments:
        raise PermissionDenied("This student is not assigned to you.")
    return render_student_page(request, "instructor_portal/student_profile.html", {
        "student": enrolments[0].student,
        "enrolments": enrolments,
    })


@login_required
@require_POST
@transaction.atomic
def enrolment_withdraw(request, enrolment_id):
    _require_instructor(request.user)
    enrolment = get_object_or_404(_instructor_enrolments(request.user).select_for_update(), pk=enrolment_id)
    if enrolment.status == Enrolment.Status.ACTIVE:
        enrolment.status = Enrolment.Status.WITHDRAWN
        enrolment.save(update_fields=("status",))
        messages.success(request, f"{enrolment.student} has been unenrolled from {enrolment.programme_version.programme.name}.")
    else:
        messages.info(request, "This enrolment is no longer active.")
    return redirect("instructor-student-profile", user_id=enrolment.student_id)
