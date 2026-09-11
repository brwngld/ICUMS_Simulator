from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module
from onboarding.models import Enrolment, Programme, ProgrammeVersion

from evaluations.models import Rubric, RubricCriterion, RubricVersion
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioState, ScenarioVersion
from accounts.models import SimulatorCredential

from .forms import CourseCreateForm, LessonCreateForm, ModuleCreateForm, PracticalCreateForm


def _require_instructor(user):
    if not (user.is_superuser or user.groups.filter(name__in=("Instructor", "Administrator")).exists()):
        raise PermissionDenied("Instructor access is required.")


@login_required
def dashboard(request):
    _require_instructor(request.user)
    enrolments = Enrolment.objects.select_related("student", "student__simulator_credential", "programme_version__programme").prefetch_related("lesson_progress", "theory_attempts")
    return render(request, "instructor_portal/dashboard.html", {"enrolments": enrolments})


@login_required
@transaction.atomic
def simulator_credential_issue(request, user_id):
    _require_instructor(request.user)
    if request.method != "POST":
        return redirect("instructor-dashboard")
    from accounts.models import User
    student = get_object_or_404(User, pk=user_id)
    credential, _ = SimulatorCredential.objects.get_or_create(user=student)
    credential.issue()
    messages.success(request, f"Simulator credentials reset for {student}. They expire at the end of the month.")
    return redirect("instructor-dashboard")


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
    return render(request, "instructor_portal/course_builder.html", {"drafts": drafts, "form": CourseCreateForm(), "learning_path": learning_path})


@login_required
@transaction.atomic
def course_create(request):
    _require_instructor(request.user)
    if request.method != "POST":
        return redirect("course-builder")
    form = CourseCreateForm(request.POST)
    if not form.is_valid():
        drafts = ProgrammeVersion.objects.filter(status="draft").select_related("programme").prefetch_related("modules__lessons")
        return render(request, "instructor_portal/course_builder.html", {"drafts": drafts, "form": form}, status=400)
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
    return render(
        request,
        "instructor_portal/course_builder_detail.html",
        {"version": version, "module_form": ModuleCreateForm()},
    )


def _course_issues(version):
    issues = []
    modules = version.modules.prefetch_related("lessons__blocks", "lessons__knowledge_checks__question_version__options")
    if not modules.exists():
        issues.append("Add at least one module.")
    for module in modules:
        if not module.lessons.exists():
            issues.append(f'Add at least one lesson to “{module.title}”.')
        for lesson in module.lessons.all():
            if not lesson.blocks.exists():
                issues.append(f'Add teaching content to “{lesson.title}”.')
            if not lesson.knowledge_checks.exists():
                issues.append(f'Add a knowledge check to “{lesson.title}”.')
            for check in lesson.knowledge_checks.all():
                if check.question_version.options.filter(is_correct=True).count() != 1:
                    issues.append(f'The knowledge check in “{lesson.title}” must have exactly one correct answer.')
        for practical in module.guided_practicals.all():
            if practical.states.count() < 2 or not practical.action_definitions.exists():
                issues.append(f'Complete the simulated flow for “{practical.scenario.title}”.')
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
    return render(request, "instructor_portal/course_review.html", {"version": version, "issues": _course_issues(version)})


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
    question_versions = QuestionVersion.objects.filter(lesson_checks__lesson__module__programme_version=version).distinct()
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
    return render(request, "instructor_portal/lesson_builder.html", {"module": module, "form": LessonCreateForm()})


@login_required
@transaction.atomic
def lesson_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    if request.method != "POST":
        return redirect("lesson-builder", module_id=module.pk)
    form = LessonCreateForm(request.POST)
    if not form.is_valid():
        return render(request, "instructor_portal/lesson_builder.html", {"module": module, "form": form}, status=400)

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
    return render(request, "instructor_portal/practical_builder.html", {"module": module, "form": PracticalCreateForm()})


@login_required
@transaction.atomic
def practical_create(request, module_id):
    _require_instructor(request.user)
    module = get_object_or_404(Module.objects.select_related("programme_version__programme"), pk=module_id, programme_version__status="draft")
    if request.method != "POST":
        return redirect("practical-builder", module_id=module.pk)
    form = PracticalCreateForm(request.POST)
    if not form.is_valid():
        return render(request, "instructor_portal/practical_builder.html", {"module": module, "form": form}, status=400)
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
    return render(request, "instructor_portal/student_detail.html", {"enrolment": enrolment})
