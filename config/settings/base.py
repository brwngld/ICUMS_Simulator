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
    "core.middleware.AdminSuperuserGateMiddleware",
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
        "navigation": "core.admin_dashboard.sidebar_navigation",
    },
}
