"""Real platform statistics for the admin dashboard (django-unfold).

Read-only: every call only runs count/list queries that mirror what the
admin changelists already expose. Nothing here mutates data or changes
any admin behaviour; it purely feeds templates/admin/index.html.
"""

from django.urls import reverse_lazy

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
    """The student/instructor navigation — an independent copy for the student
    portal. Editing this list never affects the administrator sidebar.

    Items and visibility mirror the original student sidebar exactly by
    reusing the same role context the old template relied on."""
    from accounts.context_processors import role_context
    from django.urls import reverse

    roles = role_context(request)
    groups = [
        {
            "title": "Overview",
            "items": [{"title": "Dashboard", "icon": "dashboard", "link": reverse("dashboard")}],
        },
    ]

    learning = []
    if roles["has_active_enrolment"]:
        learning.append({"title": "Theory", "icon": "menu_book", "link": reverse("roadmap")})
    if roles["can_access_practical"]:
        learning.append({"title": "Practical/Theory", "icon": "layers", "link": reverse("scenario-list")})
    if learning:
        groups.append({"title": "Learning", "items": learning})

    groups.append(
        {
            "title": "Simulator",
            "items": [
                {"title": "Simulator sandbox", "icon": "box", "link": reverse("simulator-portal")},
            ],
        }
    )

    if roles["can_access_instructor_portal"]:
        groups.append(
            {
                "title": "Instructor tools",
                "items": [
                    {"title": "Instructor", "icon": "users", "link": reverse("instructor-dashboard")},
                    {"title": "Theory builder", "icon": "edit_note", "link": reverse("course-builder") + "?path=theory"},
                    {"title": "Practical/Theory builder", "icon": "layers", "link": reverse("course-builder") + "?path=combined"},
                ],
            }
        )

    if request.user.is_staff:
        groups.append(
            {
                "title": "Administration",
                "items": [
                    {"title": "Advanced administration", "icon": "settings", "link": reverse("admin:index")},
                ],
            }
        )

    return groups


def sidebar_navigation(request):
    """Dispatch: superusers get the full admin navigation; instructors, staff
    and students all get the student copy (its own permission rules hide
    whatever a user may not see). The two lists are independent."""
    if request.user.is_superuser:
        return _admin_navigation()
    return _student_navigation(request)
