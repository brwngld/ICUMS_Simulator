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
from onboarding.models import Enrolment, Programme
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
        ("Students", students, "#5145cd"),
        ("Instructors", staff, "#087f8c"),
        ("Superusers", superusers, "#d97706"),
    ]
    segments = []
    offset = 0
    for label, count, colour in roles:
        pct = round(count * 100 / total, 1)
        if pct <= 0:
            continue
        segments.append({
            "label": label,
            "count": count,
            "pct": pct,
            "dash_offset": round(offset - 25, 2),
            "colour": colour,
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
    sidebar. Theory and Practical are always listed so the portal reads the
    same for every student; the pages themselves still enforce enrolment,
    orientation and role access. Instructor tools appear only for users
    with instructor access."""
    from accounts.context_processors import role_context
    from django.urls import reverse

    roles = role_context(request)
    groups = [
        {
            "title": "",
            "items": [{"title": "Dashboard", "icon": "dashboard", "icon_template": "core/nav_icons/dashboard.html", "link": reverse("dashboard")}],
        },
        {
            "title": "Theory",
            "items": [{"title": "Theory", "icon": "menu_book", "icon_template": "core/nav_icons/theory.html", "link": reverse("roadmap")}],
        },
        {
            "title": "Practical",
            "items": [{"title": "Practical/Theory", "icon": "layers", "icon_template": "core/nav_icons/practical.html", "link": reverse("scenario-list")}],
        },
        {
            "title": "Simulator",
            "items": [
                {"title": "Simulator sandbox", "icon": "box", "icon_template": "core/nav_icons/sandbox.html", "link": reverse("simulator-portal")},
            ],
        },
    ]

    if roles["can_access_instructor_portal"]:
        groups.append(
            {
                "title": "Instructor",
                "items": [
                    {"title": "Instructor", "icon": "users", "icon_template": "core/nav_icons/instructor.html", "link": reverse("instructor-dashboard")},
                    {"title": "Theory builder", "icon": "edit_note", "icon_template": "core/nav_icons/theory_builder.html", "link": reverse("course-builder") + "?path=theory"},
                    {"title": "Practical/Theory builder", "icon": "layers", "icon_template": "core/nav_icons/practical_builder.html", "link": reverse("course-builder") + "?path=combined"},
                ],
            }
        )

    return groups


def _crumb(title, link=""):
    """One breadcrumb entry. An empty link renders as the current page."""
    return {"title": str(title), "link": link or ""}


def _instructor_crumb():
    return _crumb("Instructor", "/instructor/")


# Portal page hierarchy, keyed by URL name and built from the view's own
# context, so every trail reflects the real parent pages. Pages without an
# entry (the dashboards, the roadmap, the scenario list, orientation) are
# top-level and keep a plain title, like the admin overview.
_BREADCRUMB_BUILDERS = {
    "instructor-student-detail": lambda ctx: [
        _instructor_crumb(),
        _crumb(ctx["enrolment"].student),
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
        _crumb("Course builder", "/instructor/courses/"),
        _crumb(ctx["module"].programme_version.programme.name, f"/instructor/courses/{ctx['module'].programme_version_id}/"),
        _crumb("Create a guided practical"),
    ],
    "simulator-credential-issue": lambda ctx: [
        _instructor_crumb(),
        _crumb("One-time simulator password"),
    ],
    "lesson-detail": lambda ctx: [
        _crumb("Theory", "/theory/"),
        _crumb(ctx["module"].title),
        _crumb(ctx["lesson"].title),
    ],
    "assessment-take": lambda ctx: [
        _crumb("Theory", "/theory/"),
        _crumb(ctx["assessment"].title),
    ],
    "assessment-result": lambda ctx: [
        _crumb("Theory", "/theory/"),
        _crumb(ctx["attempt"].assessment.title),
    ],
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
    return render(request, template, context, status=status)


def sidebar_navigation(request):
    """Dispatch by interface: pages under /admin/ get the administrator
    navigation; portal pages get the student navigation. An administrator
    browsing the portal keeps their own session and sees the student
    navigation plus one extra "Advanced Admin" link back to the admin
    dashboard. Students and tutors never see that link. The two lists are
    independent — editing one never affects the other."""
    if request.path.startswith("/admin/"):
        return _admin_navigation()

    groups = _student_navigation(request)
    if request.user.is_superuser:
        # Portal preview for the administrator: their own session, the
        # student/tutor navigation, and one link back to the admin
        # dashboard. Instructors are staff but not administrators, so the
        # link is hidden from them.
        groups = list(groups) + [
            {
                "title": "Administration",
                "items": [
                    {"title": "Advanced Admin", "icon": "settings", "link": "/admin/"},
                ],
            },
        ]
    return groups
