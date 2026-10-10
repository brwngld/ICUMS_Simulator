from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.admin_dashboard import render_student_page
from .ordering import move_lesson as move_lesson_order, move_module as move_module_order
from django.utils import timezone
from django.utils.text import slugify

from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from scenarios.models import ScenarioVersion as ScenarioVersionModel
from onboarding.models import Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress

from evaluations.models import Rubric, RubricCriterion, RubricVersion
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioState, ScenarioVersion
from accounts.models import SimulatorCredential

from .forms import (
    AssessmentQuestionForm,
    AssessmentSettingsForm,
    BlockFormSet,
    CourseCreateForm,
    CourseEditForm,
    LessonCheckEditForm,
    LessonCreateForm,
    LessonEditForm,
    ModuleCreateForm,
    ModuleEditForm,
    PracticalCreateForm,
    PracticalEditForm,
    ScenarioStateFormSet,
)


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@login_required
def dashboard(request):
    _require_instructor(request.user)
    enrolments = Enrolment.objects.select_related("student", "student__simulator_credential", "programme_version__programme").prefetch_related("lesson_progress", "theory_attempts")
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
    drafts = ProgrammeVersion.objects.filter(status=ProgrammeVersion.Status.DRAFT).select_related("programme").prefetch_related("modules__lessons")
    learning_path = request.GET.get("path", "all")
    if learning_path not in {"all", "theory", "combined"}:
        learning_path = "all"
    return render_student_page(request, "instructor_portal/course_builder.html", {"drafts": drafts, "form": CourseCreateForm(), "learning_path": learning_path})


@login_required
@transaction.atomic
def course_create(request):
    _require_instructor(request.user)
    if request.method != "POST":
        return redirect("course-builder")
    form = CourseCreateForm(request.POST)
    if not form.is_valid():
        drafts = ProgrammeVersion.objects.filter(status="draft").select_related("programme").prefetch_related("modules__lessons")
        return render_student_page(request, "instructor_portal/course_builder.html", {"drafts": drafts, "form": form}, status=400)
    name = form.cleaned_data["name"]
    code = _unique_slug(Programme, "code", name)
    programme = Programme.objects.create(name=name, code=code)
    version = ProgrammeVersion.objects.create(programme=programme, version=1, status="draft")
    messages.success(request, "Draft course created. Add its first module next.")
    return redirect("course-builder-detail", version_id=version.pk)


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
    return render_student_page(
        request,
        "instructor_portal/course_builder_detail.html",
        {"version": version, "module_form": ModuleCreateForm(), "final_exam": final_exam},
    )


def _course_issues(version):
    issues = []
    modules = version.modules.prefetch_related("lessons__blocks", "lessons__knowledge_checks__question_version__options", "assessments__items")
    if not modules.exists():
        issues.append("Add at least one module.")
    for module in modules:
        if not module.lessons.exists():
            issues.append(f'Add at least one lesson to “{module.title}”.')
        # A module is completed by passing its module assessment; without one
        # the module — and therefore the final exam, orientation, and every
        # practical — stays out of reach for its students.
        module_assessments = [a for a in module.assessments.all() if a.assessment_type == Assessment.Type.MODULE]
        if not module_assessments:
            issues.append(f'Add a module assessment to “{module.title}” — students complete a module by passing its assessment.')
        elif not any(assessment.items.exists() for assessment in module_assessments):
            issues.append(f'The module assessment for “{module.title}” must include at least one question.')
        for lesson in module.lessons.all():
            if not lesson.blocks.exists():
                issues.append(f'Add teaching content to “{lesson.title}”.')
            if not lesson.knowledge_checks.exists():
                issues.append(f'Add a knowledge check to “{lesson.title}”.')
            for check in lesson.knowledge_checks.all():
                if check.question_version.options.filter(is_correct=True).count() != 1:
                    issues.append(f'The knowledge check in “{lesson.title}” must have exactly one correct answer.')
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
            "assessments__items__question_version",
        ),
        pk=version_id,
        status="draft",
    )
    return render_student_page(request, "instructor_portal/course_review.html", {"version": version, "issues": _course_issues(version)})


@login_required
@transaction.atomic
def course_publish(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion, pk=version_id, status="draft")
    if request.method != "POST":
        return redirect("course-review", version_id=version.pk)
    issues = _course_issues(version)
    if issues:
        messages.error(request, "The course still has items to resolve before publishing.")
        return redirect("course-review", version_id=version.pk)
    lessons = Lesson.objects.filter(module__programme_version=version)
    question_versions = QuestionVersion.objects.filter(
        Q(lesson_checks__lesson__module__programme_version=version)
        | Q(assessment_items__assessment__programme_version=version)
    ).distinct()
    version.modules.update(is_published=True)
    lessons.update(is_published=True)
    question_versions.update(is_published=True)
    version.assessments.update(is_published=True)
    practicals = ScenarioVersion.objects.filter(module__programme_version=version)
    practicals.update(status=ScenarioVersion.Status.PUBLISHED, published_at=timezone.now())
    RubricVersion.objects.filter(scenario_version__in=practicals).update(status=RubricVersion.Status.PUBLISHED, published_at=timezone.now())
    version.status = ProgrammeVersion.Status.PUBLISHED
    version.published_at = timezone.now()
    version.save(update_fields=("status", "published_at"))
    messages.success(request, f'“{version.programme.name}” is now available to enrolled students.')
    return redirect("instructor-dashboard")


@login_required
@transaction.atomic
def module_create(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion, pk=version_id, status="draft")
    if request.method != "POST":
        return redirect("course-builder-detail", version_id=version.pk)
    form = ModuleCreateForm(request.POST)
    if form.is_valid():
        Module.objects.create(
            programme_version=version,
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
    return render_student_page(request, "instructor_portal/lesson_builder.html", {"module": module, "form": LessonCreateForm()})


@login_required
@transaction.atomic
def lesson_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    if request.method != "POST":
        return redirect("lesson-builder", module_id=module.pk)
    form = LessonCreateForm(request.POST)
    if not form.is_valid():
        return render_student_page(request, "instructor_portal/lesson_builder.html", {"module": module, "form": form}, status=400)

    data = form.cleaned_data
    lesson = Lesson.objects.create(
        module=module,
        slug=_unique_slug(Lesson, "slug", data["title"], module=module),
        title=data["title"],
        summary=data["summary"],
        order=module.lessons.count() + 1,
    )
    blocks = [ContentBlock.objects.create(lesson=lesson, kind="text", heading=data["concept_heading"], body=data["concept_body"], order=1)]
    if data["example_body"]:
        blocks.append(ContentBlock.objects.create(lesson=lesson, kind="example", heading=data["example_heading"], body=data["example_body"], order=len(blocks) + 1))
    if data["notice_body"]:
        blocks.append(ContentBlock.objects.create(lesson=lesson, kind="notice", heading=data["notice_heading"], body=data["notice_body"], order=len(blocks) + 1))

    question_code = _unique_slug(Question, "code", f"{module.code}-{lesson.slug}")
    question = Question.objects.create(code=question_code)
    question_version = QuestionVersion.objects.create(
        question=question,
        version=1,
        prompt=data["question_prompt"],
        explanation=data["explanation"],
        points=1,
    )
    answers = [data["correct_answer"], data["incorrect_answer_1"], data["incorrect_answer_2"], data["incorrect_answer_3"]]
    for order, answer in enumerate((answer for answer in answers if answer), start=1):
        AnswerOption.objects.create(question_version=question_version, label=answer, is_correct=order == 1, order=order)
    LessonCheck.objects.create(lesson=lesson, after_block=blocks[0], question_version=question_version, order=1)

    if data["add_to_assessment"]:
        assessment, _ = Assessment.objects.get_or_create(
            programme_version=module.programme_version,
            module=module,
            assessment_type=Assessment.Type.MODULE,
            defaults={"title": f"{module.title} Module Assessment", "pass_percentage": 70, "maximum_attempts": 3},
        )
        AssessmentItem.objects.get_or_create(assessment=assessment, question_version=question_version, defaults={"order": assessment.items.count() + 1})

    messages.success(request, "Lesson, knowledge check, and assessment link created as drafts.")
    return redirect("course-builder-detail", version_id=module.programme_version_id)


@login_required
def practical_builder(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    return render_student_page(request, "instructor_portal/practical_builder.html", {"module": module, "form": PracticalCreateForm()})


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
    messages.success(request, "Guided practical flow created as a draft.")
    return redirect("course-builder-detail", version_id=module.programme_version_id)


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


@login_required
@require_GET
def lesson_preview(request, lesson_id):
    """Read-only instructor preview of a lesson in the student presentation.

    Renders the student template without touching progress: no LessonProgress
    or ModuleProgress rows are created, and the view answers GET requests
    only, so the lesson forms can never mutate anything."""
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson.objects.select_related("module__programme_version__programme"), pk=lesson_id)
    blocks = list(lesson.blocks.order_by("order", "id"))
    checks = blocks[0].knowledge_checks.select_related("question_version").prefetch_related("question_version__options") if blocks else []
    return render_student_page(
        request,
        "learning/lesson.html",
        {
            "lesson": lesson,
            "module": lesson.module,
            "preview_mode": True,
            "current_block": blocks[0] if blocks else None,
            "checks": checks,
            "position": 0,
            "step_number": 1,
            "step_count": len(blocks),
            "progress": LessonProgress(lesson=lesson),
        },
    )


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
def course_edit(request, version_id):
    _require_instructor(request.user)
    version = get_object_or_404(ProgrammeVersion.objects.select_related("programme"), pk=version_id, status="draft")
    form = CourseEditForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        version.programme.name = form.cleaned_data["name"]
        version.programme.save(update_fields=("name",))
        messages.success(request, "Course name updated.")
        return redirect("course-builder-detail", version_id=version.pk)
    return render_student_page(request, "instructor_portal/course_edit.html", {"version": version, "form": form})


@login_required
def module_edit(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    form = ModuleEditForm(module, request.POST or None)
    if request.method == "POST" and form.is_valid():
        module.title = form.cleaned_data["title"]
        module.description = form.cleaned_data["description"]
        module.prerequisite = form.cleaned_data["prerequisite"]
        module.save(update_fields=("title", "description", "prerequisite"))
        messages.success(request, "Module updated.")
        return redirect("course-builder-detail", version_id=module.programme_version_id)
    return render_student_page(request, "instructor_portal/module_edit.html", {"module": module, "form": form})


@login_required
def lesson_edit(request, lesson_id):
    _require_instructor(request.user)
    lesson = get_object_or_404(Lesson.objects.select_related("module__programme_version"), pk=lesson_id, module__programme_version__status="draft")
    lesson_form = LessonEditForm(request.POST or None, initial={"title": lesson.title, "summary": lesson.summary})
    block_formset = BlockFormSet(request.POST or None, queryset=lesson.blocks.order_by("order"))
    check = lesson.knowledge_checks.select_related("question_version").first()
    check_form = LessonCheckEditForm(check.question_version, request.POST or None) if check else None
    if request.method == "POST" and lesson_form.is_valid() and block_formset.is_valid() and (check_form is None or check_form.is_valid()):
        lesson.title = lesson_form.cleaned_data["title"]
        lesson.summary = lesson_form.cleaned_data["summary"]
        lesson.save(update_fields=("title", "summary"))
        block_formset.save()
        if check_form:
            check_form.save()
        messages.success(request, "Lesson updated.")
        return redirect("course-builder-detail", version_id=lesson.module.programme_version_id)
    return render_student_page(
        request,
        "instructor_portal/lesson_edit.html",
        {"lesson": lesson, "lesson_form": lesson_form, "block_formset": block_formset, "check_form": check_form, "block_count": lesson.blocks.count()},
    )


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
            "briefing": practical.briefing,
            "learning_objective": practical.learning_objective,
            "assistance_mode": practical.assistance_mode,
            "maximum_attempts": practical.maximum_attempts,
        },
    )
    state_formset = ScenarioStateFormSet(request.POST or None, queryset=practical.states.order_by("order"))
    if request.method == "POST" and practical_form.is_valid() and state_formset.is_valid():
        practical.briefing = practical_form.cleaned_data["briefing"]
        practical.learning_objective = practical_form.cleaned_data["learning_objective"]
        practical.assistance_mode = practical_form.cleaned_data["assistance_mode"]
        practical.maximum_attempts = practical_form.cleaned_data["maximum_attempts"]
        practical.save(update_fields=("briefing", "learning_objective", "assistance_mode", "maximum_attempts"))
        state_formset.save()
        messages.success(request, "Guided practical updated.")
        return redirect("course-builder-detail", version_id=practical.module.programme_version_id)
    return render_student_page(
        request,
        "instructor_portal/practical_edit.html",
        {"practical": practical, "practical_form": practical_form, "state_formset": state_formset, "state_count": practical.states.count()},
    )


@login_required
def student_detail(request, enrolment_id):
    _require_instructor(request.user)
    enrolment = get_object_or_404(
        Enrolment.objects.select_related("student", "programme_version__programme").prefetch_related(
            "lesson_progress__lesson__module",
            "module_progress__module",
            "theory_attempts__assessment",
            "scenario_attempts__scenario_version__scenario",
        ),
        pk=enrolment_id,
    )
    return render_student_page(request, "instructor_portal/student_detail.html", {"enrolment": enrolment})
