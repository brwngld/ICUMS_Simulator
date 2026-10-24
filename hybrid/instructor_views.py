"""Instructor-facing builder for the Theory & Practical curriculum.

Creates and edits the same ``HybridCourse`` / ``HybridModule`` /
``HybridLesson`` / ``PracticalStep`` rows the Stage 2 student workspace
reads. Editing is confined to draft editions: published ProgrammeVersions
are shown in the index but every authoring route 404s for them, so published
content a learner is enrolled on can never be silently modified.
Publication itself (the draft→published sweep and clone-to-draft) is Stage 4.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from core.admin_dashboard import render_student_page
from instructor_portal.ordering import _move
from instructor_portal.views import _require_instructor, _unique_slug
from learning.rich_text import plain_text
from onboarding.models import Programme, ProgrammeVersion

from . import journey_services
from .forms import (
    CourseCreateForm,
    CourseEditForm,
    LessonDetailsForm,
    ModuleForm,
    StepFormSet,
    TheoryForm,
    VerificationConditionForm,
)
from .journey_forms import DependencyForm, JourneyCreateForm, JourneyEditForm, RecordRoleForm
from .models import (
    HybridCourse,
    HybridLesson,
    HybridModule,
    JourneyConditionBinding,
    JourneyDependency,
    JourneyRecordAssociation,
    JourneyRecordRole,
    JourneyStep,
    PracticalJourney,
    PracticalStep,
    VerificationCondition,
)
from .publishing import (
    clone_to_draft,
    edition_blockers,
    lesson_issues,
    publish_edition,
)

TABS = ("details", "theory", "journey", "simulator", "review")


def _draft_version(programme):
    """The programme's open draft edition, or a fresh empty one.

    A draft starts empty on purpose: cloning a published edition into a new
    draft is the publication workflow (Stage 4), not authoring.
    """
    version = programme.versions.filter(status=ProgrammeVersion.Status.DRAFT).first()
    if version is None:
        last = programme.versions.order_by("-version").first()
        version = ProgrammeVersion.objects.create(
            programme=programme,
            version=(last.version + 1) if last else 1,
            status=ProgrammeVersion.Status.DRAFT,
        )
    return version


def _lesson_issues(lesson):
    """Deprecated alias — readiness lives in ``hybrid.publishing`` now, so the
    publish sweep and the editor's Review tab can never disagree."""
    return lesson_issues(lesson)


def _renumber(queryset):
    """Compact order values back to 1..N after a removal."""
    for position, item in enumerate(queryset, start=1):
        if item.order != position:
            item.order = position
            item.save(update_fields=("order",))


def _course_row(course):
    return {
        "course": course,
        "module_count": course.hybrid_modules.count(),
        "lesson_count": HybridLesson.objects.filter(module__course=course).count(),
    }


@login_required
@transaction.atomic
def builder_index(request):
    """Every Theory & Practical programme, its editions and courses."""
    _require_instructor(request.user)
    programmes = (
        Programme.objects.filter(learning_track=Programme.Track.HYBRID, is_active=True)
        .prefetch_related("versions__hybrid_courses")
        .order_by("name")
    )
    form = CourseCreateForm(request.POST or None)
    if request.method == "POST":
        if request.POST.get("action") == "publish_edition":
            version = get_object_or_404(
                ProgrammeVersion,
                pk=request.POST.get("version_id"),
                programme__learning_track=Programme.Track.HYBRID,
                status=ProgrammeVersion.Status.DRAFT,
            )
            blockers = edition_blockers(version)
            if blockers:
                messages.error(request, "This edition is not ready to publish: " + " ".join(blockers))
            else:
                published, skipped = publish_edition(version)
                note = f" {len(skipped)} unfinished course(s) stayed unpublished." if skipped else ""
                messages.success(request, f"Edition v{version.version} published with {len(published)} course(s).{note}")
            return redirect("hybrid-builder")
        if request.POST.get("action") == "new_draft":
            version = get_object_or_404(
                ProgrammeVersion,
                pk=request.POST.get("version_id"),
                programme__learning_track=Programme.Track.HYBRID,
                status=ProgrammeVersion.Status.PUBLISHED,
            )
            draft = clone_to_draft(version)
            messages.success(
                request,
                f"New draft edition v{draft.version} created — the published edition keeps serving enrolled learners.",
            )
            return redirect("hybrid-builder")
        if form.is_valid():
            programme = form.cleaned_data["programme"]
            version, created = _ensure_draft_tracking(programme)
            course = HybridCourse.objects.create(
                programme_version=version,
                code=_unique_slug(HybridCourse, "code", form.cleaned_data["title"], programme_version=version),
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                order=version.hybrid_courses.count() + 1,
            )
            messages.success(request, "Course created." if not created else "Course created in a new draft edition.")
            return redirect("hybrid-course-edit", course_id=course.pk)
        return render_student_page(
            request, "hybrid/builder_index.html", {"programmes": programmes, "form": form}, status=400,
        )
    return render_student_page(request, "hybrid/builder_index.html", {"programmes": programmes, "form": form})


def _ensure_draft_tracking(programme):
    """Reuse or open the programme's draft edition, reporting which happened."""
    existing = programme.versions.filter(status=ProgrammeVersion.Status.DRAFT).first()
    if existing:
        return existing, False
    return _draft_version(programme), True


def _draft_course(course_id):
    return get_object_or_404(
        HybridCourse.objects.select_related("programme_version__programme"),
        pk=course_id,
        programme_version__status=ProgrammeVersion.Status.DRAFT,
    )


def _draft_module(module_id):
    return get_object_or_404(
        HybridModule.objects.select_related("course__programme_version__programme"),
        pk=module_id,
        course__programme_version__status=ProgrammeVersion.Status.DRAFT,
    )


def _draft_lesson(lesson_id):
    return get_object_or_404(
        HybridLesson.objects.select_related("module__course__programme_version__programme"),
        pk=lesson_id,
        module__course__programme_version__status=ProgrammeVersion.Status.DRAFT,
    )


@login_required
@transaction.atomic
def course_edit(request, course_id):
    _require_instructor(request.user)
    course = _draft_course(course_id)
    modules = list(course.hybrid_modules.order_by("order", "title"))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_module":
            form = ModuleForm(request.POST)
            if form.is_valid():
                HybridModule.objects.create(
                    course=course,
                    code=_unique_slug(HybridModule, "code", form.cleaned_data["title"], course=course),
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    order=course.hybrid_modules.count() + 1,
                )
                messages.success(request, "Module created.")
                return redirect("hybrid-course-edit", course_id=course.pk)
            messages.error(request, "The module needs a title.")
            return redirect("hybrid-course-edit", course_id=course.pk)
        if action == "move_module":
            module = get_object_or_404(HybridModule, pk=request.POST.get("module_id"), course=course)
            _move(
                HybridModule.objects.filter(course=course).order_by("order", "title"),
                module,
                request.POST.get("direction"),
            )
            return redirect("hybrid-course-edit", course_id=course.pk)
        if action == "delete_module":
            module = get_object_or_404(HybridModule, pk=request.POST.get("module_id"), course=course)
            try:
                module.delete()
                messages.success(request, "Module removed.")
            except ProtectedError:
                messages.error(request, "This module still has lessons. Remove its lessons first.")
            return redirect("hybrid-course-edit", course_id=course.pk)

        form = CourseEditForm(request.POST)
        if form.is_valid():
            course.title = form.cleaned_data["title"]
            course.description = form.cleaned_data["description"]
            course.save(update_fields=("title", "description"))
            messages.success(request, "Course updated.")
            return redirect("hybrid-course-edit", course_id=course.pk)
    else:
        form = CourseEditForm(initial={"title": course.title, "description": course.description})

    return render_student_page(request, "hybrid/course_detail.html", {
        "course": course,
        "form": form,
        "modules": modules,
        "module_form": ModuleForm(),
        "journeys": [
            {
                "journey": journey,
                "issue_count": len(journey_services.structural_issues(journey))
                + len(journey_services.unbound_condition_issues(journey)),
            }
            for journey in course.practical_journeys.order_by("order", "title")
        ],
    })


@login_required
@transaction.atomic
def module_edit(request, module_id):
    _require_instructor(request.user)
    module = _draft_module(module_id)
    lessons = list(module.hybrid_lessons.order_by("order", "title"))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_lesson":
            form = LessonDetailsForm(request.POST)
            if form.is_valid():
                lesson = HybridLesson.objects.create(
                    module=module,
                    slug=_unique_slug(HybridLesson, "slug", form.cleaned_data["title"], module=module),
                    title=form.cleaned_data["title"],
                    summary=form.cleaned_data["summary"],
                    order=module.hybrid_lessons.count() + 1,
                )
                messages.success(request, "Lesson created — build it out in the editor.")
                return redirect("hybrid-lesson-edit", lesson_id=lesson.pk)
            messages.error(request, "The lesson needs a title.")
            return redirect("hybrid-module-edit", module_id=module.pk)
        if action == "move_lesson":
            lesson = get_object_or_404(HybridLesson, pk=request.POST.get("lesson_id"), module=module)
            _move(
                HybridLesson.objects.filter(module=module).order_by("order", "title"),
                lesson,
                request.POST.get("direction"),
            )
            return redirect("hybrid-module-edit", module_id=module.pk)
        if action == "delete_lesson":
            lesson = get_object_or_404(HybridLesson, pk=request.POST.get("lesson_id"), module=module)
            lesson.delete()
            messages.success(request, "Lesson removed.")
            return redirect("hybrid-module-edit", module_id=module.pk)

        form = ModuleForm(request.POST)
        if form.is_valid():
            module.title = form.cleaned_data["title"]
            module.description = form.cleaned_data["description"]
            module.save(update_fields=("title", "description"))
            messages.success(request, "Module updated.")
            return redirect("hybrid-module-edit", module_id=module.pk)
    else:
        form = ModuleForm(initial={"title": module.title, "description": module.description})

    return render_student_page(request, "hybrid/module_detail.html", {
        "module": module,
        "form": form,
        "lessons": lessons,
        "lesson_form": LessonDetailsForm(),
    })


@login_required
@transaction.atomic
def lesson_edit(request, lesson_id):
    """The five-tab lesson editor: Details, Theory, Practical Journey,
    Simulator & Verification, Review.

    One wrapping form saves the lesson details, the theory formset and the
    step formset together, exactly like the theory builder's editor; the
    add/move/remove buttons around the editor post their own small actions
    and come straight back to the same tab.
    """
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    lesson_form = LessonDetailsForm(request.POST or None, initial={"title": lesson.title, "summary": lesson.summary})
    theory_form = TheoryForm(request.POST or None, body=lesson.theory)
    steps = list(lesson.practical_steps.order_by("order", "id"))
    steps_formset = StepFormSet(request.POST or None, queryset=lesson.practical_steps.order_by("order", "id"))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_condition":
            step = get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson)
            VerificationCondition.objects.create(
                step=step,
                kind=VerificationCondition.Kind.SCREEN_OPENED,
                order=step.conditions.count() + 1,
            )
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=simulator")
        if action == "save_condition":
            condition = get_object_or_404(
                VerificationCondition, pk=request.POST.get("condition_id"), step__lesson=lesson,
            )
            condition_form = VerificationConditionForm(request.POST, instance=condition)
            if condition_form.is_valid():
                condition_form.save()
                messages.success(request, "Condition updated.")
            else:
                messages.error(request, "The condition was not saved — check its type, record and expected values.")
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=simulator")
        if action == "delete_condition":
            condition = get_object_or_404(
                VerificationCondition, pk=request.POST.get("condition_id"), step__lesson=lesson,
            )
            step = condition.step
            condition.delete()
            _renumber(VerificationCondition.objects.filter(step=step).order_by("order", "id"))
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=simulator")
        if action == "move_condition":
            condition = get_object_or_404(
                VerificationCondition, pk=request.POST.get("condition_id"), step__lesson=lesson,
            )
            _move(
                VerificationCondition.objects.filter(step=condition.step).order_by("order", "id"),
                condition,
                request.POST.get("direction"),
            )
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=simulator")
        if action == "add_step":
            # A step is born as an editable placeholder, like the theory
            # builder's sections; the instructor fills it in on the row.
            PracticalStep.objects.create(
                lesson=lesson,
                key=_unique_slug(PracticalStep, "key", "New step", lesson=lesson),
                title="New step",
                order=lesson.practical_steps.count() + 1,
            )
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=journey")
        if action == "delete_step":
            get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson).delete()
            _renumber(PracticalStep.objects.filter(lesson=lesson).order_by("order", "id"))
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=journey")
        if action == "move_step":
            _move(
                PracticalStep.objects.filter(lesson=lesson).order_by("order", "id"),
                get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson),
                request.POST.get("direction"),
            )
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab=journey")

        if lesson_form.is_valid() and theory_form.is_valid() and steps_formset.is_valid():
            lesson.title = lesson_form.cleaned_data["title"]
            lesson.summary = lesson_form.cleaned_data["summary"]
            lesson.theory = theory_form.cleaned_data["body"]
            lesson.save(update_fields=("title", "summary", "theory"))
            steps_formset.save()
            messages.success(request, "Lesson updated.")
            active_tab = request.POST.get("active_tab", "details")
            if active_tab not in TABS:
                active_tab = "details"
            return redirect(f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab={active_tab}")
        messages.error(request, "Check the highlighted fields — nothing was saved.")
        active_tab = request.POST.get("active_tab", "details")
        if active_tab not in TABS:
            active_tab = "details"
        status = 400
    else:
        active_tab = request.GET.get("tab", "details")
        if active_tab not in TABS:
            active_tab = "details"
        status = 200

    step_forms = list(steps_formset)
    step_rows = [
        {
            "step": step,
            "form": form,
            "conditions": [
                {"condition": condition, "form": VerificationConditionForm(instance=condition)}
                for condition in step.conditions.order_by("order", "id")
            ],
        }
        for step, form in zip(steps, step_forms)
    ]
    return render_student_page(request, "hybrid/lesson_editor.html", {
        "lesson": lesson,
        "lesson_form": lesson_form,
        "theory_form": theory_form,
        "steps_formset": steps_formset,
        "step_rows": step_rows,
        "step_count": len(steps),
        "has_theory": bool(plain_text(lesson.theory).strip()),
        "issues": lesson_issues(lesson),
        "course_blockers_list": edition_blockers(lesson.module.course.programme_version),
        "active_tab": active_tab,
    }, status=status)


@login_required
def lesson_preview(request, lesson_id):
    """A draft lesson in the real student workspace, writing nothing.

    Reuses the Stage 2 workspace rendering — which creates no progress of
    any kind — against the draft content. Students can never reach it.
    """
    _require_instructor(request.user)
    from .views import lesson_workspace_context

    lesson = get_object_or_404(
        HybridLesson.objects.select_related("module__course__programme_version__programme"),
        pk=lesson_id,
    )
    context = lesson_workspace_context(lesson)
    context["preview_mode"] = True
    return render_student_page(request, "hybrid/workspace.html", context)


# --- Journey organizer (course-level, draft editions only) ----------------------


def _draft_journey(journey_id):
    return get_object_or_404(
        PracticalJourney.objects.select_related("course__programme_version__programme"),
        pk=journey_id,
        course__programme_version__status=ProgrammeVersion.Status.DRAFT,
    )


def _error_text(error):
    if hasattr(error, "message_dict"):
        return " ".join(" ".join(items) for items in error.message_dict.values())
    if hasattr(error, "messages"):
        return " ".join(error.messages)
    return str(error)


def _journey_organizer_context(journey):
    assignments = journey_services.ordered_assignments(journey)
    bindings = {
        binding.condition_id: binding
        for binding in JourneyConditionBinding.objects.filter(
            condition__step__journey_assignment__journey=journey
        )
    }
    condition_rows = []
    for assignment in assignments:
        condition_rows.append({
            "assignment": assignment,
            "conditions": [
                {"condition": condition, "binding": bindings.get(condition.pk)}
                for condition in assignment.step.conditions.order_by("order", "id")
            ],
        })
    unassigned = PracticalStep.objects.filter(
        lesson__module__course=journey.course, journey_assignment__isnull=True,
    ).select_related("lesson")
    return {
        "journey": journey,
        "assignments": assignments,
        "entry_point": journey_services.entry_point(journey),
        "condition_rows": condition_rows,
        "unassigned_steps": list(unassigned),
        "issues": journey_services.structural_issues(journey),
        "unbound_issues": journey_services.unbound_condition_issues(journey),
        "dependency_form": DependencyForm(journey),
        "role_form": RecordRoleForm(),
        "journey_form": JourneyEditForm(
            initial={
                "title": journey.title,
                "description": journey.description,
                "start_mode": journey.start_mode,
            }
        ),
        "course": journey.course,
    }


@login_required
def course_journeys(request, course_id):
    """Organizer index: the draft course's journeys, their structural readiness
    and unbound conditions, and the create-journey form."""
    _require_instructor(request.user)
    course = _draft_course(course_id)
    journeys = [
        {
            "journey": journey,
            "issues": journey_services.structural_issues(journey)
            + journey_services.unbound_condition_issues(journey),
        }
        for journey in course.practical_journeys.order_by("order", "title")
    ]
    form = JourneyCreateForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                journey = journey_services.create_journey(
                    course.programme_version,
                    course,
                    title=form.cleaned_data["title"],
                    description=form.cleaned_data["description"],
                    start_mode=form.cleaned_data["start_mode"],
                )
            except (PermissionDenied, ValidationError) as error:
                messages.error(request, _error_text(error))
            else:
                messages.success(request, "Journey created.")
                return redirect("hybrid-journey-detail", journey_id=journey.pk)
            return redirect("hybrid-course-journeys", course_id=course.pk)
        messages.error(request, "The journey needs a title.")
        return redirect("hybrid-course-journeys", course_id=course.pk)
    return render_student_page(request, "hybrid/journey_organizer.html", {
        "title": f"Practical journeys · {course.title}",
        "course": course,
        "journeys": journeys,
        "form": form,
    })


@login_required
def journey_detail(request, journey_id):
    """The journey organizer: canonical step order, roles, dependencies,
    condition bindings, and structural readiness — draft editions only."""
    _require_instructor(request.user)
    journey = _draft_journey(journey_id)
    context = _journey_organizer_context(journey)

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "save_journey":
                form = JourneyEditForm(request.POST)
                if form.is_valid():
                    journey_services.update_journey(
                        journey,
                        form.cleaned_data["title"],
                        form.cleaned_data["description"],
                        form.cleaned_data["start_mode"],
                    )
                    messages.success(request, "Journey updated.")
                else:
                    messages.error(request, "The journey needs a title.")
            elif action == "delete_journey":
                journey_services.delete_journey(journey)
                messages.success(request, "Journey deleted.")
                return redirect("hybrid-course-journeys", course_id=journey.course_id)
            elif action == "assign_step":
                # Look the step up by id alone: a step from another course is
                # refused by the service with a visible message, not a 404.
                step = get_object_or_404(PracticalStep, pk=request.POST.get("step_id"))
                journey_services.assign_step(journey, step)
                messages.success(request, "Step assigned to the journey.")
            elif action == "remove_step":
                assignment = get_object_or_404(JourneyStep, journey=journey, pk=request.POST.get("step_id"))
                journey_services.unassign_step(journey, assignment.step)
                messages.success(request, "Step removed from the journey.")
            elif action == "add_dependency":
                form = DependencyForm(journey, request.POST)
                if form.is_valid():
                    journey_services.add_dependency(
                        journey,
                        form.cleaned_data["predecessor"],
                        form.cleaned_data["dependent"],
                        form.cleaned_data["dependency_type"],
                        required_record_role=form.cleaned_data["required_record_role"],
                    )
                    messages.success(request, "Dependency added.")
                else:
                    messages.error(request, "The dependency was not added — check the selected steps.")
            elif action == "remove_dependency":
                dependency = get_object_or_404(
                    JourneyDependency, journey=journey, pk=request.POST.get("dependency_id"),
                )
                journey_services.remove_dependency(journey, dependency)
                messages.success(request, "Dependency removed.")
            elif action == "add_role":
                data = request.POST.copy()
                if not data.get("key") and data.get("label"):
                    data["key"] = _unique_slug(JourneyRecordRole, "key", data["label"], journey=journey)
                role_form = RecordRoleForm(data)
                if role_form.is_valid():
                    journey_services.create_record_role(
                        journey,
                        key=role_form.cleaned_data["key"],
                        label=role_form.cleaned_data["label"],
                        record_kind=role_form.cleaned_data["record_kind"],
                        required=role_form.cleaned_data["required"],
                        creation_mode=role_form.cleaned_data["creation_mode"],
                    )
                    messages.success(request, "Record role added.")
                else:
                    messages.error(request, "The record role needs a key and a shown name.")
            elif action == "save_role":
                role = get_object_or_404(JourneyRecordRole, journey=journey, pk=request.POST.get("role_id"))
                journey_services.update_record_role(role, {
                    "key": request.POST.get("key", ""),
                    "label": request.POST.get("label", ""),
                    "record_kind": request.POST.get("record_kind", ""),
                    "required": request.POST.get("required") == "on",
                    "creation_mode": request.POST.get("creation_mode", ""),
                })
                messages.success(request, "Record role updated.")
            elif action == "delete_role":
                role = get_object_or_404(JourneyRecordRole, journey=journey, pk=request.POST.get("role_id"))
                journey_services.delete_record_role(role)
                messages.success(request, "Record role removed.")
            elif action == "move_role":
                role = get_object_or_404(JourneyRecordRole, journey=journey, pk=request.POST.get("role_id"))
                journey_services.move_record_role(role, request.POST.get("direction"))
            elif action == "bind_condition":
                condition = get_object_or_404(
                    VerificationCondition,
                    pk=request.POST.get("condition_id"),
                    step__journey_assignment__journey=journey,
                )
                role = get_object_or_404(JourneyRecordRole, journey=journey, pk=request.POST.get("role_id"))
                journey_services.bind_condition(condition, role)
                messages.success(request, "Condition bound to the record role.")
            elif action == "unbind_condition":
                binding = get_object_or_404(
                    JourneyConditionBinding, pk=request.POST.get("binding_id"), role__journey=journey,
                )
                journey_services.unbind_condition(binding)
                messages.success(request, "Condition unbound.")
        except (PermissionDenied, ValidationError) as error:
            messages.error(request, _error_text(error))
        return redirect("hybrid-journey-detail", journey_id=journey.pk)

    return render_student_page(request, "hybrid/journey_detail.html", context)
