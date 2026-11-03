"""Instructor-facing builder for the Theory & Practical curriculum.

Creates and edits the same ``HybridCourse`` / ``HybridModule`` /
``HybridLesson`` / ``PracticalStep`` rows the Stage 2 student workspace
reads. Editing is confined to draft editions: published ProgrammeVersions
are shown in the index but every authoring route 404s for them, so published
content a learner is enrolled on can never be silently modified.
Publication itself (the draft→published sweep and clone-to-draft) is Stage 4.
"""
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.text import slugify

from core.admin_dashboard import render_student_page
from instructor_portal.ordering import _move
from instructor_portal.views import _require_instructor, _unique_slug
from learning.rich_text import plain_text
from onboarding.models import Programme, ProgrammeVersion
from scenarios.bindings import VERIFY_RECORDS

from . import demonstrations, journey_services
from .forms import (
    CourseCreateForm,
    CourseEditForm,
    LessonDetailsForm,
    ModuleForm,
    ProgrammeCreateForm,
    StepForm,
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
    course_blockers,
    edition_blockers,
    lesson_issues,
    publish_edition,
)

#: The lesson editor's four stages, in the order the instructor works through
#: them. The query/post parameter is still called ``tab`` because the shared
#: authoring tab script reads it.
STAGES = ("details", "theory", "activities", "review")

#: Index POSTs that target neither create form, so both stay unbound and an
#: error re-render never shows validation messages for the wrong form.
_CARD_ACTIONS = ("publish_edition", "new_draft", "create_programme")

#: Removing a lesson cascades to its demonstration session, its events and the
#: records scoped to it, so a lesson that is being recorded right now is not
#: removable — neither directly, nor through the module that contains it.
LESSON_RECORDING_IN_USE = (
    "This lesson cannot be deleted while a demonstration recording is active. "
    "Stop or discard the recording first."
)
MODULE_RECORDING_IN_USE = (
    "This module contains a lesson with an active demonstration recording. "
    "Stop or discard the recording before deleting the module."
)


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


def _lesson_stage(request):
    """Which stage the editor should show: the one a refused save came from,
    otherwise the one the page asked for."""
    name = (request.POST.get("active_tab") if request.method == "POST" else request.GET.get("tab")) or ""
    return name if name in STAGES else "details"


def _editor_url(lesson, stage):
    return f"{reverse('hybrid-lesson-edit', args=[lesson.pk])}?tab={stage}"


def _activity_card(step, post=None):
    """The one integrated card an activity gets in stage 3.

    Each form is prefixed with its own row id, so a card's POST saves that
    activity and its checks together and nothing else: no management form, no
    re-validation of the sibling cards, and an untouched row cannot be
    rewritten by a stale page. A row the posted page never carried — one added
    since the page was built — is rendered straight from the database and left
    alone, rather than refused for fields nobody was shown.

    The card also carries the journey side of the activity: the journey it
    runs inside, and for each saved-record check the record role it is bound
    to. That is read-only here — the controls below it post the organizer's own
    services, so the editor and the organizer can never disagree about a
    binding.
    """
    step_prefix = f"step-{step.pk}"
    assignment = JourneyStep.objects.filter(step=step).select_related("journey").first()
    checks = []
    for condition in step.conditions.order_by("order", "id"):
        prefix = f"cond-{condition.pk}"
        # A check is born before its record and status are chosen, and only a
        # registered record kind can be described or given a role.
        registered = condition.record_kind in VERIFY_RECORDS
        bindable = (
            assignment is not None
            and condition.kind == VerificationCondition.Kind.SAVED_RECORD
            and registered
        )
        checks.append({
            "condition": condition,
            "form": VerificationConditionForm(
                post if post is not None and f"{prefix}-kind" in post else None,
                instance=condition,
                prefix=prefix,
            ),
            "binding": JourneyConditionBinding.objects.filter(condition=condition).select_related("role").first(),
            "record_label": VERIFY_RECORDS[condition.record_kind][1] if registered else "",
            "summary": (
                condition.describe() if registered
                else "A saved record — choose the record and its status above."
            ),
            "roles": list(
                assignment.journey.record_roles.filter(record_kind=condition.record_kind).order_by("order", "id")
            ) if bindable else [],
        })
    return {
        "step": step,
        "form": StepForm(
            post if post is not None and f"{step_prefix}-title" in post else None,
            instance=step,
            prefix=step_prefix,
        ),
        "checks": checks,
        # The checks a record role can be bound to; navigation checks follow the
        # journey's step order on their own and never appear in that list.
        "record_checks": [
            entry for entry in checks if entry["condition"].kind == VerificationCondition.Kind.SAVED_RECORD
        ],
        "assignment": assignment,
        "journey": assignment.journey if assignment else None,
    }


#: The card's journey controls. They change journey structure, so they run
#: through the organizer's services and never touch the models directly.
_JOURNEY_ACTIONS = ("assign_journey", "unassign_journey", "bind_role", "unbind_role", "create_role_and_bind")


def _step_of(lesson, post):
    return get_object_or_404(PracticalStep, pk=post.get("step_id"), lesson=lesson)


def _condition_of(lesson, post):
    return get_object_or_404(
        VerificationCondition, pk=post.get("condition_id"), step__lesson=lesson,
    )


def _journey_action(request, lesson, action):
    """Run one of the card's journey controls and say what happened.

    The services own every guard — draft edition, same course, matching record
    kind, a step assigned before its check can bind — so a control here is
    exactly the organizer's own action, reached from the card instead of a
    second page.
    """
    post = request.POST
    if action == "assign_journey":
        step = _step_of(lesson, post)
        journey = get_object_or_404(
            PracticalJourney, pk=post.get("journey_id"), course=lesson.module.course,
        )
        journey_services.assign_step(journey, step)
        return f"“{step.title}” now runs inside {journey.title}."
    if action == "unassign_journey":
        step = _step_of(lesson, post)
        assignment = JourneyStep.objects.filter(step=step).select_related("journey").first()
        if assignment is None:
            raise ValidationError("That activity is not in a practical journey.")
        journey_services.unassign_step(assignment.journey, step)
        return f"“{step.title}” left {assignment.journey.title}."
    if action == "bind_role":
        condition = _condition_of(lesson, post)
        role = get_object_or_404(
            JourneyRecordRole, pk=post.get("role_id"), journey__course=lesson.module.course,
        )
        current = JourneyConditionBinding.objects.filter(condition=condition).first()
        if current and current.role_id != role.pk:
            # One check can name one record, so re-binding replaces the old
            # pairing rather than leaving a check pointing at two roles.
            journey_services.unbind_condition(current)
        journey_services.bind_condition(condition, role)
        return f"Check bound to the record role “{role.label}”."
    if action == "unbind_role":
        binding = get_object_or_404(
            JourneyConditionBinding, pk=post.get("binding_id"), condition__step__lesson=lesson,
        )
        journey_services.unbind_condition(binding)
        return "Check unbound — nothing certifies it until it is bound again."
    # create_role_and_bind: the instructor names the role, so nothing here is
    # guessed. Its record kind is the check's own; a journey that needs shared
    # or reused roles is configured in the organizer.
    condition = _condition_of(lesson, post)
    assignment = JourneyStep.objects.filter(step=condition.step).select_related("journey").first()
    if assignment is None:
        raise ValidationError("Put this activity in a practical journey first.")
    label = (post.get("label") or "").strip()
    if not label:
        raise ValidationError("Name the record role you are creating.")
    role = journey_services.create_record_role(
        assignment.journey,
        # A role's key is the longest thing a label can become, and the column
        # holds 60 characters, so the derived key is cut well inside that.
        key=_unique_slug(JourneyRecordRole, "key", slugify(label)[:40] or "role", journey=assignment.journey),
        label=label,
        record_kind=condition.record_kind,
    )
    journey_services.bind_condition(condition, role)
    return f"Record role “{label}” created and bound to the check."


def _unbound_record_checks(lesson):
    """The lesson's saved-record checks that a journey will refuse to evaluate
    because no record role answers for them.

    Review & Publish names each one and links back to the card that can bind it,
    because the publication gate now refuses the edition over it. A check on an
    activity that is in no journey is not listed: the lesson workspace verifies
    that one against the learner's own records without a role, so nothing is
    missing until the activity joins a journey.
    """
    journeys = {
        assignment.step_id: assignment.journey
        for assignment in JourneyStep.objects.filter(step__lesson=lesson).select_related("journey")
    }
    bound = set(
        JourneyConditionBinding.objects.filter(condition__step__lesson=lesson).values_list("condition_id", flat=True)
    )
    rows = []
    for step in lesson.practical_steps.order_by("order", "id"):
        journey = journeys.get(step.pk)
        if journey is None:
            continue
        for condition in step.conditions.filter(kind=VerificationCondition.Kind.SAVED_RECORD):
            # An unregistered record kind is already refused as an unverifiable
            # condition, and a check that has no record chosen yet is half-saved.
            if condition.pk in bound or condition.record_kind not in VERIFY_RECORDS:
                continue
            rows.append({"step": step, "condition": condition, "journey": journey})
    return rows


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
    """The Theory & Practical programme dashboard, or one programme's page.

    Without ``?programme=`` this is the approved landing (UI 1): summary
    statistics, search, a Draft/Published filter, programme cards and the
    New-programme dialog — the same ``ProgrammeCreateForm`` and
    ``create_programme`` action as before. ``?programme=<pk>`` renders the
    long-standing programme-scoped authoring page unchanged.
    """
    _require_instructor(request.user)
    programmes = (
        Programme.objects.filter(learning_track=Programme.Track.HYBRID, is_active=True)
        .prefetch_related("versions__hybrid_courses__hybrid_modules__hybrid_lessons")
        .order_by("name")
    )
    action = request.POST.get("action") if request.method == "POST" else None
    form = CourseCreateForm(request.POST if action not in _CARD_ACTIONS else None)
    programme_form = ProgrammeCreateForm(request.POST if action == "create_programme" else None)
    # A course created from an edition's row already knows its programme, so the
    # page carries that through the query string and the form stops asking again.
    # Scoping the field's queryset to the one programme is also the boundary: a
    # posted pk for any other programme fails validation instead of landing.
    context = {"programmes": programmes, "form": form, "programme_form": programme_form}
    selected = Programme.objects.filter(
        pk=request.GET.get("programme"), learning_track=Programme.Track.HYBRID,
    ).first()
    if selected is not None:
        # The hidden input must carry the contextual pk, so the unbound form is
        # initialised with it; the scoped queryset is what refuses a forged value.
        form.fields["programme"].queryset = Programme.objects.filter(pk=selected.pk)
        form.fields["programme"].initial = selected.pk
        context["selected_programme"] = selected
    template_name = "hybrid/builder_programme.html" if selected is not None else "hybrid/builder_index.html"
    # Landing context: search, status filter and summary statistics. The
    # statistics count each programme's current edition — the open draft if one
    # exists, otherwise its latest published edition — so a programme cloned
    # into a new draft is never counted twice and retired editions never count.
    query = (request.GET.get("q") or "").strip()
    status_filter = request.GET.get("status") or ""
    total_count = programmes.count()
    visible = programmes
    if query:
        visible = visible.filter(Q(name__icontains=query) | Q(code__icontains=query))
    if status_filter in {ProgrammeVersion.Status.DRAFT, ProgrammeVersion.Status.PUBLISHED}:
        visible = visible.filter(versions__status=status_filter).distinct()
    context.update(
        query=query,
        status_filter=status_filter,
        total_count=total_count,
        programme_rows=[_landing_row(p) for p in visible],
        landing_stats=_landing_stats(programmes),
    )
    if request.method == "POST":
        if action == "create_programme":
            if programme_form.is_valid():
                programme = programme_form.save()
                programme.learning_track = Programme.Track.HYBRID
                programme.save(update_fields=("learning_track",))
                version = _draft_version(programme)
                messages.success(request, f"Programme created in a new draft edition v{version.version}.")
                return redirect("hybrid-builder")
            return render_student_page(request, template_name, context, status=400)
        if action == "publish_edition":
            _publish_edition_action(request, request.POST.get("version_id"))
            return redirect("hybrid-builder")
        if action == "new_draft":
            _new_draft_action(request, request.POST.get("version_id"))
            return redirect("hybrid-builder")
        if form.is_valid():
            course, created = _create_course_in_open_draft(form.cleaned_data["programme"], form)
            messages.success(request, "Course created." if not created else "Course created in a new draft edition.")
            return redirect("hybrid-course-edit", course_id=course.pk)
        return render_student_page(request, template_name, context, status=400)
    return render_student_page(request, template_name, context)


def _publish_edition_action(request, version_id, programme=None):
    """The publish_edition POST action, shared by the landing and workspace.

    Refuses anything that is not an open draft of the programme's track (or of
    the given programme, when one is pinned), reports readiness blockers
    instead of publishing, and lets :func:`publishing.publish_edition` speak
    for the publication rules. Returns the version (draft even when refused).
    """
    guards = {"pk": version_id, "status": ProgrammeVersion.Status.DRAFT}
    if programme is not None:
        guards["programme"] = programme
    else:
        guards["programme__learning_track"] = Programme.Track.HYBRID
    version = get_object_or_404(ProgrammeVersion, **guards)
    blockers = edition_blockers(version)
    if blockers:
        messages.error(request, "This edition is not ready to publish: " + " ".join(blockers))
    else:
        published, skipped = publish_edition(version)
        note = f" {len(skipped)} unfinished course(s) stayed unpublished." if skipped else ""
        messages.success(request, f"Edition v{version.version} published with {len(published)} course(s).{note}")
    return version


def _new_draft_action(request, version_id, programme=None):
    """The new_draft POST action, shared by the landing and workspace.

    Clones a published edition into a fresh draft via
    :func:`publishing.clone_to_draft`; anything that is not a published
    edition of the track (or of the pinned programme) 404s. Returns the draft.
    """
    guards = {"pk": version_id, "status": ProgrammeVersion.Status.PUBLISHED}
    if programme is not None:
        guards["programme"] = programme
    else:
        guards["programme__learning_track"] = Programme.Track.HYBRID
    version = get_object_or_404(ProgrammeVersion, **guards)
    draft = clone_to_draft(version)
    messages.success(
        request,
        f"New draft edition v{draft.version} created — the published edition keeps serving enrolled learners.",
    )
    return draft


def _create_course_in_open_draft(programme, form):
    """Create the validated form's course in the programme's open draft.

    Reuses the draft when one is open, exactly like every other authoring
    entry point. Returns ``(course, created)`` where ``created`` says whether
    a new draft edition had to be opened for it.
    """
    version, created = _ensure_draft_tracking(programme)
    course = HybridCourse.objects.create(
        programme_version=version,
        code=_unique_slug(HybridCourse, "code", form.cleaned_data["title"], programme_version=version),
        title=form.cleaned_data["title"],
        description=form.cleaned_data["description"],
        order=version.hybrid_courses.count() + 1,
    )
    return course, created


@login_required
@transaction.atomic
def programme_detail(request, programme_id):
    """The instructor workspace for one Theory & Practical programme (UI 2).

    Reached from the landing's Manage programme action. Shows the programme's
    editions and the selected edition's courses and statistics; edition
    selection is read-only navigation, course creation reuses the landing's
    form and guards, and publish / new-draft reuse the exact actions the
    builder has always used — pinned to this programme.
    """
    _require_instructor(request.user)
    programme = get_object_or_404(
        Programme.objects.filter(learning_track=Programme.Track.HYBRID, is_active=True),
        pk=programme_id,
    )
    # The hidden input carries the workspace's programme; the scoped queryset
    # is the boundary: a posted pk for any other programme fails validation.
    form = CourseCreateForm()
    form.fields["programme"].queryset = Programme.objects.filter(pk=programme.pk)
    form.fields["programme"].initial = programme.pk
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_course":
            form = CourseCreateForm(request.POST)
            form.fields["programme"].queryset = Programme.objects.filter(pk=programme.pk)
            if form.is_valid():
                course, created = _create_course_in_open_draft(programme, form)
                messages.success(request, "Course created." if not created else "Course created in a new draft edition.")
                return redirect("hybrid-course-edit", course_id=course.pk)
            return render_student_page(
                request, "hybrid/programme_detail.html", _workspace_context(request, programme, form), status=400,
            )
        if action == "publish_edition":
            _publish_edition_action(request, request.POST.get("version_id"), programme=programme)
            return redirect("hybrid-programme-detail", programme_id=programme.pk)
        if action == "new_draft":
            _new_draft_action(request, request.POST.get("version_id"), programme=programme)
            return redirect("hybrid-programme-detail", programme_id=programme.pk)
        return redirect("hybrid-programme-detail", programme_id=programme.pk)
    return render_student_page(request, "hybrid/programme_detail.html", _workspace_context(request, programme, form))


def _workspace_context(request, programme, form):
    """Everything the workspace template needs, edition-scoped.

    ``?edition=<version>`` selects which edition's courses and statistics are
    shown; without it the programme's current edition (its open draft, else
    its latest published edition, else the newest edition kept) is shown.
    """
    editions = []
    for version in reversed(list(programme.versions.all())):
        row = {
            "version": version, "version_number": version.version, "status": version.status,
            "published_at": version.published_at, **_edition_counts(version),
        }
        if version.status == ProgrammeVersion.Status.DRAFT:
            row["blockers"] = edition_blockers(version)
        editions.append(row)
    current = _current_edition(programme)
    if current is None and editions:
        current = editions[0]["version"]
    requested = request.GET.get("edition")
    selected = None
    if requested is not None:
        selected = next((row for row in editions if str(row["version_number"]) == requested), None)
    if selected is None:
        selected = next((row for row in editions if current is not None and row["version"] is current), editions[0] if editions else None)
    courses = []
    if selected is not None:
        for course in selected["version"].hybrid_courses.order_by("order", "title"):
            modules = list(course.hybrid_modules.order_by("order", "title"))
            courses.append({
                "course": course,
                "modules": len(modules),
                "lessons": sum(len(module.hybrid_lessons.all()) for module in modules),
                "blockers": course_blockers(course) if selected["status"] == ProgrammeVersion.Status.DRAFT else [],
            })
    return {
        "programme": programme,
        "form": form,
        "editions": editions,
        "has_open_draft": any(row["status"] == ProgrammeVersion.Status.DRAFT for row in editions),
        "selected": selected,
        "selected_is_draft": selected is not None and selected["status"] == ProgrammeVersion.Status.DRAFT,
        "courses": courses,
    }


def _edition_counts(version):
    """Course, module and lesson totals for one edition, from the prefetch."""
    courses = list(version.hybrid_courses.all())
    modules = sum(len(course.hybrid_modules.all()) for course in courses)
    lessons = sum(
        len(module.hybrid_lessons.all())
        for course in courses
        for module in course.hybrid_modules.all()
    )
    return {"courses": len(courses), "modules": modules, "lessons": lessons}


def _landing_row(programme):
    """One card's data: every non-retired edition, newest first, with counts."""
    editions = [
        {"version": version.version, "status": version.status, **_edition_counts(version)}
        for version in reversed(list(programme.versions.all()))
        if version.status != ProgrammeVersion.Status.RETIRED
    ]
    return {"programme": programme, "editions": editions}


def _current_edition(programme):
    """The edition the tiles count: the open draft, else the latest published.

    Picks the same draft ``_ensure_draft_tracking`` reuses (the first under the
    model's version ordering), so what the tiles count is what course creation
    lands in."""
    drafts = [v for v in programme.versions.all() if v.status == ProgrammeVersion.Status.DRAFT]
    if drafts:
        return drafts[0]
    published = [v for v in programme.versions.all() if v.status == ProgrammeVersion.Status.PUBLISHED]
    return max(published, key=lambda v: v.version) if published else None


def _landing_stats(programmes):
    """Programme, course, module and lesson totals across current editions."""
    totals = {"programmes": 0, "courses": 0, "modules": 0, "lessons": 0}
    for programme in programmes:
        totals["programmes"] += 1
        edition = _current_edition(programme)
        if edition is not None:
            for key, value in _edition_counts(edition).items():
                totals[key] += value
    return totals


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
    form = CourseEditForm(initial={"title": course.title, "description": course.description})
    module_form = ModuleForm()
    journey_form = JourneyCreateForm()

    def _render(status=200):
        return render_student_page(request, "hybrid/course_detail.html", {
            "course": course,
            "form": form,
            "modules": modules,
            "module_form": module_form,
            "journey_form": journey_form,
            "journeys": [
                {
                    "journey": journey,
                    "issue_count": len(journey_services.structural_issues(journey))
                    + len(journey_services.unbound_condition_issues(journey)),
                }
                for journey in course.practical_journeys.order_by("order", "title")
            ],
            "lesson_count": sum(module.hybrid_lessons.count() for module in modules),
            "blockers": course_blockers(course),
            # ?confirm=module-<pk> opens that module's removal confirmation
            # without JavaScript; with JavaScript the Remove control opens the
            # same dialog directly.
            "confirm_module": next(
                (module for module in modules if request.GET.get("confirm") == f"module-{module.pk}"), None,
            ),
        }, status=status)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_journey":
            # The same form and service the journey organizer uses, so the
            # course page is a shortcut to the workflow rather than a second one.
            journey_form = JourneyCreateForm(request.POST)
            if journey_form.is_valid():
                try:
                    journey = journey_services.create_journey(
                        course.programme_version,
                        course,
                        title=journey_form.cleaned_data["title"],
                        description=journey_form.cleaned_data["description"],
                        start_mode=journey_form.cleaned_data["start_mode"],
                    )
                except (PermissionDenied, ValidationError) as error:
                    messages.error(request, _error_text(error))
                else:
                    messages.success(request, "Journey created.")
                    return redirect("hybrid-journey-detail", journey_id=journey.pk)
            else:
                messages.error(request, "The journey needs a title.")
            return redirect("hybrid-course-edit", course_id=course.pk)
        if action == "create_module":
            module_form = ModuleForm(request.POST)
            if module_form.is_valid():
                HybridModule.objects.create(
                    course=course,
                    code=_unique_slug(HybridModule, "code", module_form.cleaned_data["title"], course=course),
                    title=module_form.cleaned_data["title"],
                    description=module_form.cleaned_data["description"],
                    order=course.hybrid_modules.count() + 1,
                )
                messages.success(request, "Module created.")
                return redirect("hybrid-course-edit", course_id=course.pk)
            # The Add-module dialog reopens with the errors and entered values.
            return _render(status=400)
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
            if demonstrations.lesson_is_recording(module.hybrid_lessons.values_list("id", flat=True)):
                messages.error(request, MODULE_RECORDING_IN_USE)
                return redirect("hybrid-course-edit", course_id=course.pk)
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

    return _render()


@login_required
@transaction.atomic
def module_edit(request, module_id):
    _require_instructor(request.user)
    module = _draft_module(module_id)
    lessons = list(module.hybrid_lessons.order_by("order", "title"))
    # The lesson list describes what each lesson holds: its type, whether the
    # theory has been written, and — for Interactive Practical lessons — the
    # step count and what publication still wants from it, since those are
    # what open in the Demonstration Studio.
    lesson_rows = [
        {
            "lesson": lesson,
            "is_interactive": lesson.kind == HybridLesson.Kind.INTERACTIVE_PRACTICAL,
            "kind_label": lesson.get_kind_display(),
            "step_count": lesson.practical_steps.count(),
            "has_theory": bool(plain_text(lesson.theory).strip()),
            "issues": lesson_issues(lesson)
            if lesson.kind == HybridLesson.Kind.INTERACTIVE_PRACTICAL
            else [],
        }
        for lesson in lessons
    ]
    form = ModuleForm(initial={"title": module.title, "description": module.description})
    lesson_form = LessonDetailsForm()

    def _render(status=200):
        return render_student_page(request, "hybrid/module_detail.html", {
            "module": module,
            "form": form,
            "lessons": lessons,
            "lesson_rows": lesson_rows,
            "lesson_form": lesson_form,
            "interactive_count": sum(1 for row in lesson_rows if row["is_interactive"]),
            "theory_count": sum(1 for row in lesson_rows if row["has_theory"]),
            "not_ready_count": sum(1 for row in lesson_rows if row["issues"]),
            # ?confirm=lesson-<pk> opens that lesson's removal confirmation
            # without JavaScript; with JavaScript the Remove control opens the
            # same dialog directly.
            "confirm_lesson": next(
                (row["lesson"] for row in lesson_rows if request.GET.get("confirm") == f"lesson-{row['lesson'].pk}"),
                None,
            ),
        }, status=status)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_lesson":
            lesson_form = LessonDetailsForm(request.POST)
            if lesson_form.is_valid():
                # A POST from before the type existed (or with the select
                # blank) means Interactive Practical — the only type the
                # builder has ever created.
                kind = lesson_form.cleaned_data["kind"] or HybridLesson.Kind.INTERACTIVE_PRACTICAL
                if kind == HybridLesson.Kind.GUIDED_MATERIAL_STUDY:
                    # The type is stored on the model, but its Material Studio
                    # does not exist yet — refuse even a posted (disabled)
                    # option so no incomplete authoring path can start.
                    messages.error(
                        request,
                        "Guided Material Study is not available yet — the Material Studio is still to come.",
                    )
                    return redirect("hybrid-module-edit", module_id=module.pk)
                lesson = HybridLesson.objects.create(
                    module=module,
                    slug=_unique_slug(HybridLesson, "slug", lesson_form.cleaned_data["title"], module=module),
                    title=lesson_form.cleaned_data["title"],
                    summary=lesson_form.cleaned_data["summary"],
                    kind=kind,
                    order=module.hybrid_lessons.count() + 1,
                )
                messages.success(request, "Interactive Practical lesson created — continue in the Demonstration Studio.")
                return redirect("hybrid-lesson-demonstration-studio", lesson_id=lesson.pk)
            # The Add-lesson dialog reopens with the errors and entered values.
            return _render(status=400)
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
            if demonstrations.lesson_is_recording([lesson.pk]):
                messages.error(request, LESSON_RECORDING_IN_USE)
                return redirect("hybrid-module-edit", module_id=module.pk)
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

    return _render()


@login_required
@transaction.atomic
def lesson_demonstration_studio(request, lesson_id):
    """Stage 1 Instructor Demonstration Studio for one draft lesson.

    Renders the approved client-side demonstration prototype scoped to this
    lesson. Recording is simulated in the browser only: nothing here writes
    demonstrations, captured actions or any backend state. Draft-scoped like
    the rest of the instructor builder."""
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    if request.method != "GET":
        return HttpResponse(status=405)
    context = {
        "title": f"Demonstration Studio · {lesson.title}",
        "lesson": lesson,
        "step_count": lesson.practical_steps.count(),
        "course_title": lesson.module.course.title,
        # Development-only UI 4 proof.  The frame safety middleware makes
        # instructor iframe traffic read-only and route-allowlisted before a
        # simulator view can run.  Production receives no frame URL.
        "simulator_frame_url": reverse("simulator-portal") if settings.DEBUG else "",
        # Stage 1B: when the flag is on, the studio's controls drive the real
        # lifecycle endpoints and the timeline lists the recorded events. Off,
        # the page keeps its original client-side behaviour untouched.
        "demonstration_recording": demonstrations.recording_enabled(),
    }
    return render_student_page(request, "hybrid/demonstration_studio.html", context)


def lesson_edit(request, lesson_id):
    """The four-stage lesson editor: Lesson Details, Theory & Guidance,
    Practical Activities, Review & Publish.

    Stages 1 and 2 are the lesson's own record and save together. Stage 3 is
    one integrated card per ``PracticalStep``: the activity's instructions,
    screen and every check hanging off it are saved by that card's own POST, so
    editing one activity never validates or rewrites its siblings. Structural
    actions (add, move, remove, and the check bookkeeping around a card) post
    their own small forms and come straight back to the stage they belong to.
    """
    _require_instructor(request.user)
    lesson = _draft_lesson(lesson_id)
    steps = list(lesson.practical_steps.order_by("order", "id"))
    action = request.POST.get("action") if request.method == "POST" else None
    # Only a lesson POST carries the lesson's own fields; binding the details
    # and theory forms to any other action would light up errors nobody typed.
    lesson_data = request.POST if action == "save_lesson" else None
    lesson_form = LessonDetailsForm(lesson_data, initial={"title": lesson.title, "summary": lesson.summary})
    theory_form = TheoryForm(lesson_data, body=lesson.theory)
    cards = {step.pk: _activity_card(step) for step in steps}
    status = 200

    if request.method == "POST":
        if action == "add_condition":
            step = get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson)
            # The instructor says which check they mean, so a record check is
            # born as one instead of arriving as a navigation placeholder that
            # has to be re-typed before it can be saved.
            kind = request.POST.get("kind", "")
            if kind not in VerificationCondition.Kind.values:
                messages.error(request, "Choose the type of check to add.")
                return redirect(_editor_url(lesson, "activities"))
            VerificationCondition.objects.create(
                step=step,
                kind=kind,
                order=step.conditions.count() + 1,
            )
            return redirect(_editor_url(lesson, "activities"))
        if action == "delete_condition":
            condition = get_object_or_404(
                VerificationCondition, pk=request.POST.get("condition_id"), step__lesson=lesson,
            )
            step = condition.step
            condition.delete()
            _renumber(VerificationCondition.objects.filter(step=step).order_by("order", "id"))
            return redirect(_editor_url(lesson, "activities"))
        if action == "move_condition":
            condition = get_object_or_404(
                VerificationCondition, pk=request.POST.get("condition_id"), step__lesson=lesson,
            )
            _move(
                VerificationCondition.objects.filter(step=condition.step).order_by("order", "id"),
                condition,
                request.POST.get("direction"),
            )
            return redirect(_editor_url(lesson, "activities"))
        if action == "add_step":
            # An activity is born as an editable card, like the theory
            # builder's sections; the instructor fills it in on the row.
            PracticalStep.objects.create(
                lesson=lesson,
                key=_unique_slug(PracticalStep, "key", "New activity", lesson=lesson),
                title="New activity",
                order=lesson.practical_steps.count() + 1,
            )
            return redirect(_editor_url(lesson, "activities"))
        if action == "delete_step":
            step = get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson)
            try:
                step.delete()
            except ProtectedError:
                messages.error(
                    request,
                    f'“{step.title}” belongs to a Practical Workflow — remove it from the workflow first.',
                )
            else:
                _renumber(PracticalStep.objects.filter(lesson=lesson).order_by("order", "id"))
            return redirect(_editor_url(lesson, "activities"))
        if action == "move_step":
            _move(
                PracticalStep.objects.filter(lesson=lesson).order_by("order", "id"),
                get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson),
                request.POST.get("direction"),
            )
            return redirect(_editor_url(lesson, "activities"))
        if action in _JOURNEY_ACTIONS:
            try:
                outcome = _journey_action(request, lesson, action)
            except (PermissionDenied, ValidationError) as error:
                messages.error(request, _error_text(error))
            else:
                messages.success(request, outcome)
            return redirect(_editor_url(lesson, "activities"))
        if action == "save_activity":
            step = get_object_or_404(PracticalStep, pk=request.POST.get("step_id"), lesson=lesson)
            card = _activity_card(step, request.POST)
            # Only the forms this page actually carried are validated and saved:
            # a check added since the page was built is neither rewritten by its
            # absence nor refused for fields nobody was shown.
            shown = [entry["form"] for entry in card["checks"] if entry["form"].is_bound]
            if card["form"].is_valid() and all(form.is_valid() for form in shown):
                card["form"].save()
                for form in shown:
                    form.save()
                messages.success(request, "Activity updated.")
                return redirect(_editor_url(lesson, "activities"))
            # The refused card is re-rendered carrying its own errors; every
            # other card keeps whatever the page was built with.
            cards[step.pk] = card
            messages.error(request, f'“{step.title}” was not saved — check the highlighted fields.')
            status = 400
        if action == "save_lesson":
            if lesson_form.is_valid() and theory_form.is_valid():
                lesson.title = lesson_form.cleaned_data["title"]
                lesson.summary = lesson_form.cleaned_data["summary"]
                lesson.theory = theory_form.cleaned_data["body"]
                lesson.save(update_fields=("title", "summary", "theory"))
                messages.success(request, "Lesson updated.")
                return redirect(_editor_url(lesson, _lesson_stage(request)))
            messages.error(request, "Check the highlighted fields — nothing was saved.")
            status = 400

    return render_student_page(request, "hybrid/lesson_editor.html", {
        "lesson": lesson,
        "lesson_form": lesson_form,
        "theory_form": theory_form,
        "activity_cards": [cards[step.pk] for step in steps],
        "step_count": len(steps),
        "course_journeys": list(lesson.module.course.practical_journeys.order_by("order", "title")),
        "has_theory": bool(plain_text(lesson.theory).strip()),
        "issues": lesson_issues(lesson),
        "binding_rows": _unbound_record_checks(lesson),
        "course_blockers_list": edition_blockers(lesson.module.course.programme_version),
        "active_tab": _lesson_stage(request),
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
