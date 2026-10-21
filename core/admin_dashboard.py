"""Real platform statistics for the admin dashboard (django-unfold).

Read-only: every call only runs count/list queries that mirror what the
admin changelists already expose. Nothing here mutates data or changes
any admin behaviour; it purely feeds templates/admin/index.html.
"""

from django.contrib import admin as admin_site
from django.shortcuts import render
from django.urls import reverse, reverse_lazy

from accounts.models import User
from assessments.models import Question, TheoryAttempt
from evaluations.models import PracticalEvaluation
from learning.models import Lesson, Module
from learning.services import module_is_locked
from onboarding.models import Enrolment, Programme
from onboarding.services import active_enrolments, programme_href, requested_enrolment
from reports.models import Certificate
from scenarios.models import (
    BoeDeclaration,
    ConsignmentApplication,
    Scenario,
    ScenarioAttempt,
    UcrDeclaration,
)

RECENT_USER_LIMIT = 6


def _model_perm(app_label, model_name):
    return lambda request: request.user.has_perm(f"{app_label}.view_{model_name}")


def _role_segments(students, staff, superusers):
    total = students + staff + superusers
    if total == 0:
        return []
    roles = [
        ("Students", students, "students"),
        ("Instructors", staff, "instructors"),
        ("Superusers", superusers, "superusers"),
    ]
    segments = []
    offset = 0
    for label, count, tone in roles:
        pct = round(count * 100 / total, 1)
        if pct <= 0:
            continue
        segments.append({
            "label": label,
            "count": count,
            "pct": pct,
            "dash_offset": round(offset - 25, 2),
            "tone": tone,
        })
        offset += pct
    return segments


def dashboard_callback(request, context):
    users_total = User.objects.count()
    students = User.objects.filter(is_staff=False).count()
    staff = User.objects.filter(is_staff=True, is_superuser=False).count()
    superusers = User.objects.filter(is_superuser=True).count()
    enrolments_total = Enrolment.objects.count()
    enrolments_active = Enrolment.objects.filter(status="active").count()

    content_counts = [
        {"label": "Programmes", "count": Programme.objects.count()},
        {"label": "Modules", "count": Module.objects.count()},
        {"label": "Lessons", "count": Lesson.objects.count()},
        {"label": "Questions", "count": Question.objects.count()},
    ]
    context["dash"] = {
        "cards": [
            {"icon": "people", "label": "Total users", "value": users_total, "sub": f"{students} students · {staff + superusers} staff"},
            {"icon": "how_to_reg", "label": "Active enrolments", "value": enrolments_active, "sub": f"of {enrolments_total} total"},
            {"icon": "local_shipping", "label": "Scenarios", "value": Scenario.objects.count(), "sub": "Practical training cases"},
            {"icon": "receipt_long", "label": "UCR declarations", "value": UcrDeclaration.objects.count(), "sub": f"{ConsignmentApplication.objects.count()} consignment applications"},
        ],
        "role_segments": _role_segments(students, staff, superusers),
        "role_total": users_total,
        "content": content_counts,
        "content_max": max((row["count"] for row in content_counts), default=1) or 1,
        "activity": [
            {"label": "Scenario attempts", "count": ScenarioAttempt.objects.count()},
            {"label": "Theory attempts", "count": TheoryAttempt.objects.count()},
            {"label": "Practical evaluations", "count": PracticalEvaluation.objects.count()},
            {"label": "Certificates issued", "count": Certificate.objects.count()},
        ],
        "recent_users": [
            {
                "name": user.get_full_name() or user.username,
                "username": user.username,
                "role": "Staff" if user.is_staff else "Student",
                "is_active": user.is_active,
                "joined": user.date_joined,
            }
            for user in User.objects.order_by("-date_joined")[:RECENT_USER_LIMIT]
        ],
        "attention": [
            {
                "label": "Inactive user accounts",
                "detail": "Cannot sign in until re-enabled",
                "count": User.objects.filter(is_active=False).count(),
                "url": "/admin/accounts/user/?is_active__exact=0",
            },
            {
                "label": "Users who never signed in",
                "detail": "Issued credentials not yet used",
                "count": User.objects.filter(last_login__isnull=True).count(),
                "url": "/admin/accounts/user/?last_login__isnull=1",
            },
            {
                "label": "Withdrawn enrolments",
                "detail": "Students pulled out of a programme",
                "count": Enrolment.objects.filter(status="withdrawn").count(),
                "url": "/admin/onboarding/enrolment/?status__exact=withdrawn",
            },
        ],
        "boe_total": BoeDeclaration.objects.count(),
    }
    return context


def _admin_navigation():
    """The administrator navigation (verbatim from the original UNFOLD config)."""
    return[
            {
                "title": "Overview",
                "items": [
                    {"title": "Dashboard", "icon": "dashboard", "link": reverse_lazy("admin:index")},
                ],
            },
            {
                "title": "People",
                "items": [
                    {"title": "Users", "icon": "people", "link": reverse_lazy("admin:accounts_user_changelist"), "permission": _model_perm("accounts", "user")},
                    {"title": "Simulator credentials", "icon": "key", "link": reverse_lazy("admin:accounts_simulatorcredential_changelist"), "permission": _model_perm("accounts", "simulatorcredential")},
                ],
            },
            {
                "title": "Programmes",
                "collapsible": True,
                "items": [
                    {"title": "Programmes", "icon": "school", "link": reverse_lazy("admin:onboarding_programme_changelist"), "permission": _model_perm("onboarding", "programme")},
                    {"title": "Programme versions", "link": reverse_lazy("admin:onboarding_programmeversion_changelist"), "permission": _model_perm("onboarding", "programmeversion")},
                    {"title": "Enrolments", "icon": "how_to_reg", "link": reverse_lazy("admin:onboarding_enrolment_changelist"), "permission": _model_perm("onboarding", "enrolment")},
                    {"title": "Disclaimer versions", "link": reverse_lazy("admin:onboarding_disclaimerversion_changelist"), "permission": _model_perm("onboarding", "disclaimerversion")},
                    {"title": "Disclaimer acceptances", "link": reverse_lazy("admin:onboarding_disclaimeracceptance_changelist"), "permission": _model_perm("onboarding", "disclaimeracceptance")},
                ],
            },
            {
                "title": "Learning content",
                "collapsible": True,
                "items": [
                    {"title": "Modules", "icon": "menu_book", "link": reverse_lazy("admin:learning_module_changelist"), "permission": _model_perm("learning", "module")},
                    {"title": "Lessons", "link": reverse_lazy("admin:learning_lesson_changelist"), "permission": _model_perm("learning", "lesson")},
                    {"title": "Resources", "link": reverse_lazy("admin:learning_resource_changelist"), "permission": _model_perm("learning", "resource")},
                ],
            },
            {
                "title": "Theory & progress",
                "collapsible": True,
                "items": [
                    {"title": "Questions", "icon": "quiz", "link": reverse_lazy("admin:assessments_question_changelist"), "permission": _model_perm("assessments", "question")},
                    {"title": "Question versions", "link": reverse_lazy("admin:assessments_questionversion_changelist"), "permission": _model_perm("assessments", "questionversion")},
                    {"title": "Assessments", "link": reverse_lazy("admin:assessments_assessment_changelist"), "permission": _model_perm("assessments", "assessment")},
                    {"title": "Theory attempts", "link": reverse_lazy("admin:assessments_theoryattempt_changelist"), "permission": _model_perm("assessments", "theoryattempt")},
                    {"title": "Theory responses", "link": reverse_lazy("admin:assessments_theoryresponse_changelist"), "permission": _model_perm("assessments", "theoryresponse")},
                    {"title": "Lesson check responses", "link": reverse_lazy("admin:assessments_lessoncheckresponse_changelist"), "permission": _model_perm("assessments", "lessoncheckresponse")},
                    {"title": "Lesson progress", "link": reverse_lazy("admin:progress_lessonprogress_changelist"), "permission": _model_perm("progress", "lessonprogress")},
                    {"title": "Module progress", "link": reverse_lazy("admin:progress_moduleprogress_changelist"), "permission": _model_perm("progress", "moduleprogress")},
                    {"title": "Programme progress", "link": reverse_lazy("admin:progress_programmeprogress_changelist"), "permission": _model_perm("progress", "programmeprogress")},
                ],
            },
            {
                "title": "Simulator",
                "collapsible": True,
                "items": [
                    {"title": "Scenarios", "icon": "local_shipping", "link": reverse_lazy("admin:scenarios_scenario_changelist"), "permission": _model_perm("scenarios", "scenario")},
                    {"title": "Scenario versions", "link": reverse_lazy("admin:scenarios_scenarioversion_changelist"), "permission": _model_perm("scenarios", "scenarioversion")},
                    {"title": "Scenario states", "link": reverse_lazy("admin:scenarios_scenariostate_changelist"), "permission": _model_perm("scenarios", "scenariostate")},
                    {"title": "Scenario actions", "link": reverse_lazy("admin:scenarios_scenarioaction_changelist"), "permission": _model_perm("scenarios", "scenarioaction")},
                    {"title": "Action definitions", "link": reverse_lazy("admin:scenarios_scenarioactiondefinition_changelist"), "permission": _model_perm("scenarios", "scenarioactiondefinition")},
                    {"title": "Scenario documents", "link": reverse_lazy("admin:scenarios_scenariodocument_changelist"), "permission": _model_perm("scenarios", "scenariodocument")},
                    {"title": "Scenario attempts", "link": reverse_lazy("admin:scenarios_scenarioattempt_changelist"), "permission": _model_perm("scenarios", "scenarioattempt")},
                    {"title": "Stakeholders", "link": reverse_lazy("admin:scenarios_trainingstakeholder_changelist"), "permission": _model_perm("scenarios", "trainingstakeholder")},
                    {"title": "Service providers", "link": reverse_lazy("admin:scenarios_trainingserviceprovider_changelist"), "permission": _model_perm("scenarios", "trainingserviceprovider")},
                ],
            },
            {
                "title": "Trade documents",
                "collapsible": True,
                "items": [
                    {"title": "UCR declarations", "icon": "receipt_long", "link": reverse_lazy("admin:scenarios_ucrdeclaration_changelist"), "permission": _model_perm("scenarios", "ucrdeclaration")},
                    {"title": "Consignment applications", "link": reverse_lazy("admin:scenarios_consignmentapplication_changelist"), "permission": _model_perm("scenarios", "consignmentapplication")},
                    {"title": "Bills of lading", "link": reverse_lazy("admin:scenarios_billoflading_changelist"), "permission": _model_perm("scenarios", "billoflading")},
                    {"title": "Commercial documents", "link": reverse_lazy("admin:scenarios_commercialdocument_changelist"), "permission": _model_perm("scenarios", "commercialdocument")},
                    {"title": "BOE declarations", "link": reverse_lazy("admin:scenarios_boedeclaration_changelist"), "permission": _model_perm("scenarios", "boedeclaration")},
                    {"title": "MDA applications", "link": reverse_lazy("admin:scenarios_mdaapplication_changelist"), "permission": _model_perm("scenarios", "mdaapplication")},
                    {"title": "MDA consignment requests", "link": reverse_lazy("admin:scenarios_mdaconsignmentrequest_changelist"), "permission": _model_perm("scenarios", "mdaconsignmentrequest")},
                ],
            },
            {
                "title": "Reference data",
                "collapsible": True,
                "items": [
                    {"title": "Customs regimes", "icon": "dataset", "link": reverse_lazy("admin:scenarios_customsregime_changelist"), "permission": _model_perm("scenarios", "customsregime")},
                    {"title": "Procedure codes", "link": reverse_lazy("admin:scenarios_customsprocedurecode_changelist"), "permission": _model_perm("scenarios", "customsprocedurecode")},
                    {"title": "HS codes", "link": reverse_lazy("admin:scenarios_ghanahscode_changelist"), "permission": _model_perm("scenarios", "ghanahscode")},
                    {"title": "Port codes", "link": reverse_lazy("admin:scenarios_portcode_changelist"), "permission": _model_perm("scenarios", "portcode")},
                    {"title": "Tax codes", "link": reverse_lazy("admin:assessment_taxcode_changelist"), "permission": _model_perm("assessment", "taxcode")},
                    {"title": "MDA agencies", "link": reverse_lazy("admin:scenarios_mdaagency_changelist"), "permission": _model_perm("scenarios", "mdaagency")},
                    {"title": "MDA processes", "link": reverse_lazy("admin:scenarios_mdaprocess_changelist"), "permission": _model_perm("scenarios", "mdaprocess")},
                    {"title": "Assistance events", "link": reverse_lazy("admin:scenarios_assistanceevent_changelist"), "permission": _model_perm("scenarios", "assistanceevent")},
                ],
            },
            {
                "title": "Evaluation & records",
                "collapsible": True,
                "items": [
                    {"title": "Rubrics", "icon": "fact_check", "link": reverse_lazy("admin:evaluations_rubric_changelist"), "permission": _model_perm("evaluations", "rubric")},
                    {"title": "Rubric versions", "link": reverse_lazy("admin:evaluations_rubricversion_changelist"), "permission": _model_perm("evaluations", "rubricversion")},
                    {"title": "Practical evaluations", "link": reverse_lazy("admin:evaluations_practicalevaluation_changelist"), "permission": _model_perm("evaluations", "practicalevaluation")},
                    {"title": "Criterion results", "link": reverse_lazy("admin:evaluations_criterionresult_changelist"), "permission": _model_perm("evaluations", "criterionresult")},
                    {"title": "Evaluation revisions", "link": reverse_lazy("admin:evaluations_evaluationrevision_changelist"), "permission": _model_perm("evaluations", "evaluationrevision")},
                    {"title": "Remediation recommendations", "link": reverse_lazy("admin:evaluations_remediationrecommendation_changelist"), "permission": _model_perm("evaluations", "remediationrecommendation")},
                    {"title": "Instructor feedback", "link": reverse_lazy("admin:evaluations_instructorfeedback_changelist"), "permission": _model_perm("evaluations", "instructorfeedback")},
                    {"title": "Practical assessments", "link": reverse_lazy("admin:assessment_assessment_changelist"), "permission": _model_perm("assessment", "assessment")},
                    {"title": "Certificates", "link": reverse_lazy("admin:reports_certificate_changelist"), "permission": _model_perm("reports", "certificate")},
                    {"title": "Completion records", "link": reverse_lazy("admin:reports_completionrecord_changelist"), "permission": _model_perm("reports", "completionrecord")},
                    {"title": "Completion policies", "link": reverse_lazy("admin:reports_completionpolicy_changelist"), "permission": _model_perm("reports", "completionpolicy")},
                    {"title": "Audit events", "link": reverse_lazy("admin:audit_auditevent_changelist"), "permission": _model_perm("audit", "auditevent")},
                ],
            },
        ]


def _student_navigation(request):
    """The Student and Tutor/Instructor navigation — an independent copy for
    the student portal. Editing this list never affects the administrator
    sidebar. Learning destinations remain visible while the pages themselves
    enforce enrolment, orientation and role access. Instructor tools appear
    only for users with instructor access."""
    from accounts.context_processors import role_context
    from django.urls import reverse

    roles = role_context(request)
    assessment_items = []
    # A practical page knows which programme it is on even when its own url does
    # not say, and it records that on the request; everywhere else the request
    # decides.
    enrolment = getattr(request, "page_enrolment", None) or requested_enrolment(request)
    roadmap_url = programme_href(reverse("roadmap"), enrolment)
    practical_url = programme_href(reverse("scenario-list"), enrolment)
    if enrolment:
        # The roadmap page carries the module and lesson navigation itself, so the
        # sidebar only needs one entry here — individual courses, modules and
        # lessons must not populate the global sidebar.
        modules = list(
            enrolment.programme_version.modules.filter(is_published=True)
            .prefetch_related("assessments")
            .order_by("order", "title")
        )
        for index, module in enumerate(modules, start=1):
            # Skip anything the learner cannot open yet: a module inside a
            # draft course, or one still behind a difficulty level.
            if module_is_locked(enrolment, module):
                continue
            assessment = module.assessments.filter(is_published=True).first()
            if assessment:
                assessment_items.append(
                    {
                        "title": f"Module {index} assessment",
                        "link": programme_href(reverse("assessment-take", args=(assessment.pk,)), enrolment),
                    }
                )

    learning_items = [
        {
            "title": "Theoretical Training",
            "icon": "menu_book",
            "icon_template": "core/nav_icons/theory.html",
            "link": roadmap_url,
            "submenu": True,
            "active": request.path.startswith(("/theory/", "/assessments/")),
            "items": [{"title": "Learning Roadmap", "link": roadmap_url if enrolment else "#"}],
        },
        {
            "title": "Simulator",
            "icon": "box",
            "icon_template": "core/nav_icons/sandbox.html",
            "link": reverse("simulator-portal"),
            "submenu": True,
            "items": [{"title": "Simulator Sandbox", "link": reverse("simulator-portal")}],
        },
        {
            "title": "Practical",
            "icon": "layers",
            "icon_template": "core/nav_icons/practical.html",
            "link": practical_url,
            "submenu": True,
            "items": [{"title": "Theory & Practical", "link": practical_url}],
        },
        {
            "title": "Assessments",
            "icon": "assignment",
            "link": assessment_items[0]["link"] if assessment_items else (roadmap_url if enrolment else "#"),
            "submenu": bool(assessment_items),
            "items": assessment_items,
        },
    ]
    # A learner on one programme has nothing to switch between, so the entry
    # only appears once a second enrolment exists.
    if active_enrolments(request.user).count() > 1:
        learning_items.insert(1, {
            "title": "My programmes",
            "icon": "school",
            "link": reverse("my-programmes"),
            "active": request.path.startswith("/programmes/"),
        })

    groups = [
        {
            "title": "",
            "items": [{"title": "Dashboard", "icon": "dashboard", "icon_template": "core/nav_icons/dashboard.html", "link": reverse("dashboard")}],
        },
        {"title": "My Learning", "items": learning_items},
    ]

    if roles["can_access_instructor_portal"]:
        groups.append(
            {
                "title": "Instructor",
                "items": [
                    {"title": "Instructor", "icon": "users", "icon_template": "core/nav_icons/instructor.html", "link": reverse("instructor-dashboard")},
                    {"title": "Students", "icon": "group", "link": reverse("instructor-student-list")},
                    {"title": "Theory builder", "icon": "edit_note", "icon_template": "core/nav_icons/theory_builder.html", "link": reverse("course-builder") + "?path=theory"},
                    {"title": "Practical/Theory builder", "icon": "layers", "icon_template": "core/nav_icons/practical_builder.html", "link": reverse("practical-builder-index")},
                ],
            }
        )

    return groups


def _crumb(title, link=""):
    """One breadcrumb entry. An empty link renders as the current page."""
    return {"title": str(title), "link": link or ""}


def _crumb_enrolment(ctx):
    """The enrolment a page's context knows about, if any."""
    return ctx.get("enrolment") or getattr(ctx.get("attempt"), "enrolment", None)


def _theory_href(ctx, url="/theory/"):
    """Keep a learner's trail on the programme they are actually reading.

    A bare `/theory/` resolves to the oldest active enrolment, so a learner on
    two programmes would be bounced back to the wrong one by any crumb.
    """
    return programme_href(url, _crumb_enrolment(ctx))


def _instructor_crumb():
    return _crumb("Instructor", "/instructor/")


def _course_crumb(ctx):
    """The course a module belongs to, when the learner reaches it through the
    roadmap. Modules with no course, draft-only courses and the compatibility
    containers that legacy programmes were wrapped in (no difficulty level, so
    they duplicate the programme name) keep the existing two-level trail."""
    module = ctx.get("module")
    course = getattr(module, "course", None)
    if course is None:
        return None
    if not (course.is_published or ctx.get("preview_mode")):
        return None
    if not course.difficulty and not ctx.get("preview_mode"):
        return None
    link = (
        f"/instructor/learner-courses/{course.pk}/student-view/"
        if ctx.get("preview_mode")
        else _theory_href(ctx, f"/theory/courses/{course.code}/")
    )
    return _crumb(course.title, link)


def _lesson_crumbs(ctx):
    crumbs = [_crumb("Home", "/"), _crumb("Theoretical Training", _theory_href(ctx))]
    course = _course_crumb(ctx)
    if course:
        crumbs.append(course)
    crumbs += [
        _crumb(f"Module {ctx['module'].order}", _theory_href(ctx, reverse("module-overview", args=(ctx["module"].code,)))),
        _crumb(f"Lesson {ctx.get('lesson_position', 1)}"),
    ]
    return crumbs


def _module_crumbs(ctx):
    crumbs = [_crumb("Home", "/"), _crumb("Theoretical Training", _theory_href(ctx))]
    course = _course_crumb(ctx)
    if course:
        crumbs.append(course)
    crumbs.append(_crumb(f"Module {ctx['module'].order}"))
    return crumbs


def _assessment_crumbs(ctx):
    assessment = ctx.get("assessment") or ctx["attempt"].assessment
    crumbs = [_crumb("Home", "/"), _crumb("Theoretical Training", _theory_href(ctx))]
    if assessment.module_id:
        crumbs.append(_crumb(f"Module {assessment.module.order}", _theory_href(ctx)))
    crumbs.append(_crumb("Assessment"))
    return crumbs


# Portal page hierarchy, keyed by URL name and built from the view's own
# context, so every trail reflects the real parent pages. Pages without an
# entry (the dashboards, the roadmap, the scenario list, orientation) are
# top-level and keep a plain title, like the admin overview.
_BREADCRUMB_BUILDERS = {
    "roadmap": lambda ctx: [
        _crumb("Home", "/"),
        _crumb("Theoretical Training", _theory_href(ctx)),
        _crumb("Course Overview"),
    ],
    "module-overview": _module_crumbs,
    "course-overview": lambda ctx: [
        _crumb("Home", "/"),
        _crumb("Theoretical Training", _theory_href(ctx)),
        _crumb("Course Overview", _theory_href(ctx)),
        _crumb(ctx["course"].title),
    ],
    "instructor-student-detail": lambda ctx: [
        _instructor_crumb(),
        _crumb(ctx["enrolment"].student),
    ],
    "instructor-student-list": lambda ctx: [_instructor_crumb(), _crumb("Students")],
    "instructor-student-profile": lambda ctx: [
        _instructor_crumb(),
        _crumb("Students", "/instructor/students/"),
        _crumb(ctx["student"]),
    ],
    "course-builder": lambda ctx: [
        _instructor_crumb(),
        _crumb({"theory": "Theory builder", "combined": "Practical/Theory builder"}.get(ctx.get("learning_path"), "Course builder")),
    ],
    "course-builder-detail": lambda ctx: [
        _instructor_crumb(),
        _crumb("Course builder", "/instructor/courses/"),
        _crumb(ctx["version"].programme.name),
    ],
    "course-review": lambda ctx: [
        _instructor_crumb(),
        _crumb("Course builder", "/instructor/courses/"),
        _crumb(ctx["version"].programme.name, f"/instructor/courses/{ctx['version'].pk}/"),
        _crumb("Review"),
    ],
    "lesson-builder": lambda ctx: [
        _instructor_crumb(),
        _crumb("Course builder", "/instructor/courses/"),
        _crumb(ctx["module"].programme_version.programme.name, f"/instructor/courses/{ctx['module'].programme_version_id}/"),
        _crumb("Create a lesson"),
    ],
    "practical-builder": lambda ctx: [
        _instructor_crumb(),
        _crumb("Practical/Theory builder", "/instructor/practicals/"),
        _crumb(ctx["module"].programme_version.programme.name, f"/instructor/courses/{ctx['module'].programme_version_id}/"),
        _crumb("Create a guided practical"),
    ],
    "practical-builder-index": lambda ctx: [
        _instructor_crumb(),
        _crumb("Practical/Theory builder"),
    ],
    "simulator-credential-issue": lambda ctx: [
        _instructor_crumb(),
        _crumb("One-time simulator password"),
    ],
    "lesson-detail": _lesson_crumbs,
    "lesson-section": _lesson_crumbs,
    "assessment-take": _assessment_crumbs,
    "assessment-result": _assessment_crumbs,
    "scenario-detail": lambda ctx: [
        _crumb("Practical/Theory", "/practical/"),
        _crumb(ctx["scenario_version"].scenario.title),
    ],
    "scenario-workspace": lambda ctx: [
        _crumb("Practical/Theory", "/practical/"),
        _crumb(ctx["attempt"].scenario_version.scenario.title, f"/practical/{ctx['attempt'].scenario_version_id}/"),
        _crumb("Workspace"),
    ],
    "practical-evaluation": lambda ctx: [
        _crumb("Dashboard", "/"),
        _crumb(ctx["evaluation"].attempt.scenario_version.scenario.title),
    ],
    "completion-detail": lambda ctx: [
        _crumb("Dashboard", "/"),
        _crumb("Training completion record"),
    ],
    "certificate-detail": lambda ctx: [
        _crumb("Dashboard", "/"),
        _crumb("Training completion record", f"/records/completion/{ctx['certificate'].completion_record_id}/"),
        _crumb("Certificate"),
    ],
}


def _page_title(ctx):
    """A page's own `page_title`, used as a head title or crumb label."""
    return ctx["page_title"]


# Simulator page heads: the title and breadcrumb trail each playground
# page shows in the chrome header. Extracted from the pages' former
# in-content heads; labels are the originals, verbatim. A title or crumb
# label may instead be a callable of the page's render context, for the
# pages whose name comes from the view (or from the record being shown)
# rather than from a fixed screen.
_SIMULATOR_PAGE_HEADS = {key.removeprefix("templates/"): value for key, value in {
    "templates/scenarios/cargo_direct_delivery.html": {"title": 'Direct Delivery', "crumbs": [('Cargo', 'simulator-portal'), ('Sea Import', None), ('Discharge', None), ('Direct Delivery', None)]},
    "templates/scenarios/cargo_service_request.html": {"title": 'Service Request', "crumbs": [('Cargo', 'simulator-portal'), ('Sea Import', None), ('Service Request', None)]},
    "templates/scenarios/clearance_workspace.html": {"title": 'Create BOE Declaration', "crumbs": [('Clearance', 'clearance-workspace'), ('Declaration', None), ('Register Declaration', None), ('Create BOE Declaration', None)]},
    "templates/scenarios/consignment_application.html": {"title": 'Search Application', "crumbs": [('Workspace', 'simulator-portal'), ('Application', None), ('Preparation Application', None), ('Consignment Document', None)]},
    "templates/scenarios/declaration_create.html": {"title": _page_title, "crumbs": [('Clearance', 'clearance-workspace'), ('Declaration', None), ('Register Declaration', None), (_page_title, None)]},
    "templates/scenarios/declaration_search.html": {"title": _page_title, "crumbs": [('Clearance', 'clearance-workspace'), ('Declaration', None), ('Register Declaration', None), (_page_title, None)]},
    "templates/scenarios/single_window_create_consignment_application.html": {"title": 'Create Application', "crumbs": [('Single Window', 'single-window-workspace'), ('Application', None), ('Create Application', 'single-window-create-consignment-application'), ('Search Application', 'single-window-search-consignment-application'), ('Create Application', None)]},
    "templates/scenarios/single_window_create_master_application.html": {"title": 'Create Application', "crumbs": [('Single Window', 'single-window-workspace'), ('Application', None), ('Create Application', 'single-window-create-master-application'), ('Search Application', 'single-window-search-master-application'), ('Create Application', None)]},
    "templates/scenarios/single_window_create_opt_in_out.html": {"title": 'Create Opt In/Out', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Opt In/Out Request', None), ('Create Opt In/Out', None)]},
    "templates/scenarios/single_window_create_ucr.html": {"title": 'Create UCR', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Unique Consignment Reference', None), ('Create UCR', None)]},
    "templates/scenarios/single_window_exporter_registration.html": {"title": _page_title, "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Exporter Registration', None), (_page_title, None)]},
    "templates/scenarios/single_window_opt_in_out_detail.html": {"title": 'Submitted Opt In/Out', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Opt In/Out Request', None), ('Submitted Opt In/Out', None)]},
    "templates/scenarios/single_window_preparation_application.html": {"title": _page_title, "crumbs": [('Single Window', 'single-window-workspace'), ('Application', None), ('Create Application', 'single-window-create-preparation-application'), ('Search Application', 'single-window-search-preparation-application'), (_page_title, None)]},
    "templates/scenarios/single_window_search_consignment_application.html": {"title": 'Search Application', "crumbs": [('Single Window', 'single-window-workspace'), ('Application', None), ('Create Application', 'single-window-create-consignment-application'), ('Search Application', 'single-window-search-consignment-application'), ('Search Application', None)]},
    "templates/scenarios/single_window_search_opt_in_out.html": {"title": 'Search Opt In/Out', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Search Opt In/Out', None)]},
    "templates/scenarios/single_window_search_ucr.html": {"title": 'Search UCR', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Unique Consignment Reference', None), ('Search UCR', None)]},
    "templates/scenarios/single_window_workspace.html": {"title": 'Unique Consignment Reference', "crumbs": [('Single Window', 'simulator-portal'), ('Registration', None), ('Unique Consignment Reference', None)]},
    "templates/scenarios/ucr_amend.html": {"title": 'Amend UCR', "crumbs": [('Single Window', 'single-window-workspace'), ('Registration', None), ('Unique Consignment Reference', None), ('Amend UCR', None)]},
    "templates/scenarios/ucr_create.html": {"title": 'Create UCR', "crumbs": [('Workspace', 'simulator-portal'), ('Registration', None), ('Create UCR', None)]},
    "templates/scenarios/ucr_detail.html": {"title": 'Create UCR', "crumbs": [('Workspace', 'simulator-portal'), ('Create UCR', None)]},
    "templates/scenarios/boe_declaration.html": {"title": lambda ctx: f"BOE Declaration {ctx['declaration'].job_no}", "crumbs": [('Clearance', 'clearance-workspace'), ('Declaration', None), ('Register Declaration', None), (lambda ctx: f"BOE Declaration {ctx['declaration'].job_no}", None)]},
    "templates/assessment/detail.html": {"title": 'Duty Assessment', "crumbs": [('Workspace', 'simulator-portal'), ('Clearance', None), ('Duty Assessment', None)]},
}.items()}


def _simulator_page_head(template, context):
    """Resolve a template's head entry into renderable crumbs."""
    from django.urls import reverse

    head = _SIMULATOR_PAGE_HEADS.get(template)
    if not head:
        return None

    def resolve(value):
        return str(value(context) if callable(value) else value)

    def link(url_name):
        try:
            return reverse(url_name) if url_name else ""
        except Exception:
            return ""

    try:
        title = resolve(head["title"])
        crumbs = [{"title": resolve(label), "link": link(url_name)} for label, url_name in head["crumbs"]]
    except (KeyError, AttributeError, TypeError):
        # A dynamic head references context this render does not carry;
        # leave the chrome to its own fallback rather than half-rendering.
        return None
    return {"title": title, "crumbs": crumbs} if title else None


def _portal_breadcrumbs(request, context):
    url_name = getattr(getattr(request, "resolver_match", None), "url_name", "")
    builder = _BREADCRUMB_BUILDERS.get(url_name)
    if builder is None:
        return []
    try:
        return builder(context)
    except KeyError:
        # A builder references context this particular render does not
        # carry; show no trail rather than a broken one.
        return []


def render_student_page(request, template, context=None, status=200):
    """Render a student/tutor page in the shared Unfold shell.

    Supplies the admin chrome context and the role-appropriate sidebar
    navigation as presentation context only — this does not touch Django
    Admin's has_permission authorization boundary.
    """
    from django.contrib.auth import get_user_model

    context = dict(context or {})
    context.update(admin_site.site.each_context(request))
    # The chrome title stays empty on these pages (the page carries the
    # primary heading); the welcomemsg override renders it without an <h1>
    # so pages keep exactly one primary heading.
    context["hide_chrome_h1"] = True
    if request.user.is_authenticated:
        context["sidebar_navigation"] = admin_site.site.get_sidebar_list(request)
    else:
        context["sidebar_navigation"] = []
    # Unfold gates the whole header (title, sidebar toggle, environment
    # badge) behind Django admin's has_permission, which is false for
    # anyone who is not Django staff — leaving tutors in the Instructor
    # group and ordinary students with an empty header bar. On portal
    # pages the gate is purely presentational: every view here is
    # login_required with its own role checks, so any authenticated user
    # may see the chrome. Admin access itself is untouched.
    context["has_permission"] = request.user.is_authenticated
    context["breadcrumbs"] = _portal_breadcrumbs(request, context)
    if request.path.startswith(SIMULATOR_PATH_PREFIXES):
        from scenarios.views import _has_simulator_access

        # The brand bar's service areas are only navigable with simulator
        # access, so the shell needs to know whether to offer them.
        context.setdefault("simulator_access", _has_simulator_access(request))
        context["simulator_page"] = _simulator_page_head(template, context)
    return render(request, template, context, status=status)


def _simulator_navigation(request):
    """The simulator playground navigation as Unfold sidebar groups,
    restored per area: like the original in-page sidebars, each area's
    pages see only their own menu tree. The workspace home carries no area
    tree at all — its service areas are entered from the brand bar — and
    leads with the simulator login block while the visitor still lacks
    access. The former three-level trees (area > section > leaf) map to
    Unfold's two levels as collapsible sections with the original section
    and leaf labels, verbatim."""
    from django.urls import reverse

    def cargo_ref(key):
        return reverse("cargo-reference-page", args=[key])

    def clearance_ref(key):
        return reverse("clearance-reference-page", args=[key])

    def previous(key):
        return reverse("single-window-previous-data", args=[key])

    def leaf(title, link, icon="chevron_right"):
        return {"title": title, "icon": icon, "link": link}

    def section(title, items):
        return {"title": title, "collapsible": True, "items": items}

    cargo = [
        section("Sea Import", [
            leaf("Direct Delivery", reverse("cargo-direct-delivery"), "local_shipping"),
            leaf("Service Request", reverse("cargo-service-request"), "local_shipping"),
        ]),
        section("Sea Export", [
            leaf("Export Sea Manifest BOE Matching", cargo_ref("export-sea-manifest-boe-matching")),
        ]),
        section("Air Import", [
            leaf("Service Request", cargo_ref("air-service-request"), "flight"),
        ]),
        section("Road Manifest", [
            leaf("Road Consignment List", cargo_ref("road-consignment-list")),
            leaf("Road Consignment Amend List", cargo_ref("road-consignment-amend-list")),
            leaf("Vehicle List", cargo_ref("vehicle-list")),
            leaf("Vehicle Amend", cargo_ref("vehicle-amend")),
        ]),
        section("Transportation", [
            leaf("BT Declaration", cargo_ref("bt-declaration")),
            leaf("BT Amendment Declaration", cargo_ref("bt-amendment-declaration")),
            leaf("Holding Area Transfer", cargo_ref("holding-area-transfer"), "swap_horiz"),
            leaf("List of non-exited BT", cargo_ref("non-exited-bt-report")),
            leaf("SIGMAT Route Amend", cargo_ref("sigmat-route-amend")),
            leaf("WeighBridge List", cargo_ref("weighbridge-list"), "monitor"),
        ]),
        section("Customs Area", [
            leaf("Dummy BL List", cargo_ref("dummy-bl-list")),
            leaf("Dummy BL Restoration List", cargo_ref("dummy-bl-restoration-list"), "restore"),
            leaf("Merge BL List", cargo_ref("merge-bl-list"), "call_merge"),
            leaf("Merge BL Restoration List", cargo_ref("merge-bl-restoration-list"), "restore"),
            leaf("UCL Release", cargo_ref("ucl-release"), "lock_open"),
            leaf("Temporary Importation", cargo_ref("temporary-importation"), "schedule"),
            leaf("Temporary Importation Closure", cargo_ref("temporary-importation-closure"), "task_alt"),
            leaf("Release of Blocking", cargo_ref("release-of-blocking"), "lock_open"),
        ]),
        section("Tracking", [
            leaf("Cargo Tracking", reverse("simulator-portal"), "search"),
        ]),
    ]
    clearance = [
        section("Declaration", [
            leaf("Create BOE Declaration", reverse("clearance-workspace"), "add"),
            leaf("Search BOE Declaration", reverse("search-boe-declaration"), "search"),
            leaf("Create Simple Amendment", reverse("create-simple-amendment"), "add"),
            leaf("Search Simple Amendment", reverse("search-simple-amendment"), "search"),
            leaf("Create Post Entry Declaration", reverse("create-post-entry-declaration"), "add"),
            leaf("Search Post Entry Declaration", reverse("search-post-entry-declaration"), "search"),
            leaf("Search Cancellation Request", clearance_ref("search-cancellation-request"), "search"),
            leaf("Create Release Prior to BOE", clearance_ref("create-release-prior-to-boe"), "add"),
            leaf("Search Release Prior to BOE", clearance_ref("search-release-prior-to-boe"), "search"),
            leaf("Export Booking Schedule Update", clearance_ref("export-booking-schedule-update")),
            leaf("Reply to Appeal Correction Query", clearance_ref("reply-to-appeal-correction-query"), "reply"),
            leaf("Request for BOE Suspension", clearance_ref("request-for-boe-suspension"), "pending"),
            leaf("Request Physical Inspection by CHA", clearance_ref("request-physical-inspection-by-cha"), "search"),
            leaf("Request for NBD Allow (Direct Import)", clearance_ref("request-for-nbd-allow-direct-import"), "pending"),
            leaf("Request BOE Release in Lab Analysis incomplete", clearance_ref("request-boe-release-in-lab-analysis-incomplete"), "pending"),
            leaf("Request for release of BOE Blocking", clearance_ref("request-for-release-of-boe-blocking"), "lock_open"),
            leaf("Request to change BL No before Manifest Matching", clearance_ref("request-to-change-bl-no-before-manifest-matching")),
            leaf("Request to enable BL No Swap", clearance_ref("request-to-enable-bl-no-swap"), "swap_horiz"),
            leaf("Request BOE Release without MDA Approval", clearance_ref("request-boe-release-without-mda-approval"), "pending"),
            leaf("Request to allow for Importer Name matching", clearance_ref("request-to-allow-for-importer-name-matching"), "pending"),
            leaf("BOE Annexed Document Registration", clearance_ref("boe-annexed-document-registration")),
            leaf("Request UCL Check Skip before Manifest Matching", clearance_ref("request-ucl-check-skip-before-manifest-matching"), "pending"),
            leaf("Transit Conversion Request", clearance_ref("transit-conversion-request"), "swap_horiz"),
            leaf("Exception Request for Chassis No. Restriction", clearance_ref("exception-request-for-chassis-no-restriction"), "pending"),
            leaf("Request to use PMD CL Plan", clearance_ref("request-to-use-pmd-cl-plan"), "pending"),
            leaf("Request to allow Post Entry after BOE Exited", clearance_ref("request-to-allow-post-entry-after-boe-exited"), "pending"),
            leaf("Bill Auto regeneration Stop List", clearance_ref("bill-auto-regeneration-stop-list"), "block"),
        ]),
        section("Declaration Report", [
            leaf("List of Declaration per Importer", clearance_ref("list-of-declaration-per-importer")),
            leaf("List of Declaration per Exporter", clearance_ref("list-of-declaration-per-exporter")),
            leaf("Warehouse BOE Report", clearance_ref("warehouse-boe-report")),
            leaf("ExWarehouse BOE Report", clearance_ref("exwarehouse-boe-report")),
            leaf("Declaration Tax Report", clearance_ref("declaration-tax-report")),
            leaf("Stock Balance (Ex)Warehouse Report", clearance_ref("stock-balance-ex-warehouse-report")),
            leaf("List of non-exited BOE", clearance_ref("list-of-non-exited-boe")),
            leaf("BOE Items Report", clearance_ref("boe-items-report")),
        ]),
        section("Additional Information", [
            leaf("Declaration Notice", clearance_ref("declaration-notice"), "info"),
            leaf("Declaration Tracking", clearance_ref("declaration-tracking"), "search"),
            leaf("Find User ID of Job No", clearance_ref("find-user-id-of-job-no"), "search"),
        ]),
        section("Petroleum Management", [
            leaf("Petroleum Lifting Summary", clearance_ref("petroleum-lifting-summary")),
            leaf("Petroleum Unpaid Order", clearance_ref("petroleum-unpaid-order")),
            leaf("Petroleum Depot Transfer", clearance_ref("petroleum-depot-transfer-list"), "swap_horiz"),
            leaf("Petroleum Inventory List", clearance_ref("petroleum-inventory-list")),
            leaf("Petroleum Period Extension Request", clearance_ref("petroleum-period-extension-request"), "schedule"),
            leaf("Petroleum Stock BOE Non-Reflection List", clearance_ref("petroleum-stock-boe-non-reflection-list")),
            leaf("Petroleum Stock Transfer Non-Reflection List", clearance_ref("petroleum-stock-transfer-non-reflection-list")),
            leaf("Petroleum Stock Order Non-Reflection List", clearance_ref("petroleum-stock-order-non-reflection-list")),
        ]),
    ]
    single_window = [
        section("Registration", [
            leaf("Create UCR", reverse("single-window-create-ucr"), "add"),
            leaf("Search UCR", reverse("single-window-search-ucr"), "search"),
            leaf("Transfer UCR", reverse("single-window-transfer-ucr"), "swap_horiz"),
            leaf("Received UCR", reverse("single-window-received-ucr"), "inbox"),
            leaf("Create Exporter Registration", reverse("single-window-create-exporter"), "how_to_reg"),
            leaf("Search Exporter Registration", reverse("single-window-search-exporter"), "search"),
            leaf("Create Opt In/Out", reverse("single-window-create-opt-in-out"), "add"),
            leaf("Search Opt In/Out", reverse("single-window-search-opt-in-out"), "search"),
            leaf("Create FCIE Registration", reverse("single-window-create-fcie"), "how_to_reg"),
            leaf("Search FCIE Registration", reverse("single-window-search-fcie"), "search"),
        ]),
        section("Application", [
            leaf("Create Application", reverse("single-window-create-preparation-application"), "add"),
            leaf("Search Application", reverse("single-window-search-preparation-application"), "search"),
            leaf("Create Master Application", reverse("single-window-create-master-application"), "add"),
            leaf("Search Master Application", reverse("single-window-search-master-application"), "search"),
            leaf("Create Consignment Application", reverse("single-window-create-consignment-application"), "add"),
            leaf("Search Consignment Application", reverse("single-window-search-consignment-application"), "search"),
        ]),
        section("Letter of Commitment", [
            leaf("Create Bank Pre-Registration", reverse("single-window-create-bank-registration"), "add"),
            leaf("Search Bank Pre-Registration", reverse("single-window-search-bank-registration"), "search"),
            leaf("Create Letter of Commitment", reverse("single-window-create-letter-commitment"), "add"),
            leaf("Search Letter of Commitment", reverse("single-window-search-letter-commitment"), "search"),
        ]),
        section("Previous Data", [
            leaf("Search Application", previous("application"), "history"),
            leaf("Search Exporter Registration", previous("exporter"), "history"),
            leaf("Search Letter of Commitment", previous("letter"), "history"),
            leaf("Search Pre Bank Registration", previous("bank"), "history"),
            leaf("Search Opt In", previous("opt-in"), "history"),
        ]),
    ]

    path = request.path
    is_home = path.startswith("/practical/portal")
    if is_home or path.startswith("/practical/more-information"):
        # The workspace home is a launcher, not an area: its service areas are
        # entered from the brand bar, so the Cargo menu belongs to the Cargo
        # pages and not here. The logged-out explainer is not a Cargo page
        # either — offering its reader the gated trees would only be a page of
        # bounces.
        area_sections = []
    elif path.startswith("/practical/clearance"):
        area_sections = clearance
    elif path.startswith("/practical/single-window"):
        area_sections = single_window
    else:
        # Cargo pages and the access endpoints carry the Cargo menu.
        area_sections = cargo

    groups = [
        {
            "title": "",
            "items": [
                {"title": "Student dashboard", "icon": "dashboard", "icon_template": "core/nav_icons/dashboard.html", "link": reverse("dashboard")},
                {"title": "Workspace home", "icon": "grid", "icon_template": "core/nav_icons/sandbox.html", "link": reverse("simulator-portal")},
            ],
        },
        *area_sections,
    ]

    from scenarios.views import _has_simulator_access

    if is_home and hasattr(request, "user") and not _has_simulator_access(request):
        # Simulator access is what opens every service area, so on the home
        # page the panel leads with the way in. Login and Forgot Password?
        # both open the existing dialog; ?login=1 is the hook that page
        # already honours and &reset=1 expands the reset form inside it.
        # The practice desk enumerates the menus from a bare path stand-in, so
        # the block that speaks for one reader is only offered to a request
        # carrying a reader at all.
        portal = reverse("simulator-portal")
        groups.insert(0, {
            "title": "",
            "items": [
                {"title": "Login", "icon": "login", "link": f"{portal}?login=1"},
                {"title": "Forgot Password?", "icon": "key", "link": f"{portal}?login=1&reset=1"},
                {"title": "Request Account", "icon": "person_add", "link": reverse("register")},
            ],
        })

    return groups


SIMULATOR_PATH_PREFIXES = (
    "/practical/portal",
    "/practical/cargo",
    "/practical/clearance",
    "/practical/single-window",
    "/practical/access",
    "/practical/assessment",
)


def sidebar_navigation(request):
    """Dispatch by interface: pages under /admin/ get the administrator
    navigation; simulator playground pages get the three area menus;
    other portal pages get the student navigation. An administrator
    browsing keeps their own session and sees one extra "Advanced Admin"
    link back to the admin dashboard. The lists are independent — editing
    one never affects the others."""
    if request.path.startswith("/admin/"):
        return _admin_navigation()

    if request.path.startswith(SIMULATOR_PATH_PREFIXES):
        groups = _simulator_navigation(request)
    else:
        groups = _student_navigation(request)
    if request.user.is_superuser:
        # Portal preview for the administrator: their own session, the
        # page's navigation, and one link back to the admin dashboard.
        # Instructors are staff but not administrators, so the link is
        # hidden from them.
        groups = list(groups) + [
            {
                "title": "Administration",
                "items": [
                    {"title": "Advanced Admin", "icon": "settings", "link": "/admin/"},
                ],
            },
        ]
    return groups
