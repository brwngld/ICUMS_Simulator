"""Shared settings for every ICUMS Simulator environment."""

import os
from pathlib import Path

from django.templatetags.static import static
from django.urls import reverse_lazy


def _model_perm(app_label, model_name):
    """Sidebar permission gate mirroring the changelist's own access check."""
    return lambda request: request.user.has_perm(f"{app_label}.view_{model_name}")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOCAL_DATA_DIR = BASE_DIR / "local_data"

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "unsafe-development-key-change-before-hosting",
)
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "audit.apps.AuditConfig",
    "core.apps.CoreConfig",
    "onboarding.apps.OnboardingConfig",
    "learning.apps.LearningConfig",
    "assessments.apps.AssessmentsConfig",
    "progress.apps.ProgressConfig",
    "instructor_portal.apps.InstructorPortalConfig",
    "scenarios.apps.ScenariosConfig",
    "evaluations.apps.EvaluationsConfig",
    "reports.apps.ReportsConfig",
    "assessment.apps.AssessmentConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.role_context",
                "accounts.context_processors.simulator_review",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = LOCAL_DATA_DIR / "static_collected"
MEDIA_URL = "media/"
MEDIA_ROOT = LOCAL_DATA_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# Admin theme (django-unfold). Presentational only: groups the registered
# models for the sidebar and sets the admin brand. The links reuse the
# standard admin changelist URLs, so permissions and behaviour are unchanged.
UNFOLD = {
    "SITE_TITLE": "ICUMS Simulator admin",
    "SITE_HEADER": "ICUMS Simulator",
    "SITE_SUBHEADER": "Training administration",
    "SITE_URL": "/",
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/svg+xml", "href": lambda request: static("image/favicon.svg")},
        {"rel": "icon", "sizes": "96x96", "type": "image/png", "href": lambda request: static("image/favicon-96x96.png")},
    ],
    "ENVIRONMENT": lambda request: ["Training environment", "warning"],
    "DASHBOARD_CALLBACK": "core.admin_dashboard.dashboard_callback",
    "COLORS": {
        "base": {
            "50": "#f8fafc", "100": "#f1f5f9", "200": "#e2e8f0", "300": "#cbd5e1",
            "400": "#94a3b8", "500": "#64748b", "600": "#475569", "700": "#334155",
            "800": "#1e293b", "900": "#0f172a", "950": "#0a0f1e",
        },
        "primary": {
            "50": "#eef0fd", "100": "#e0e3fb", "200": "#c7cdf7", "300": "#a8aded",
            "400": "#8a86de", "500": "#5145cd", "600": "#4236b6", "700": "#383093",
            "800": "#302b76", "900": "#2b2860", "950": "#1b1940",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
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
        ],
    },
}
