"""Temporary VPS deployment settings: SQLite data, Waitress, external binding.

Intended for short-lived training runs on a single Ubuntu server. Not a
replacement for the Phase 6 hosted-deployment gate (PostgreSQL, HTTPS,
hardened secrets) — treat anything built on this module as temporary.
"""

import os

from django.core.exceptions import ImproperlyConfigured

from .local import *  # noqa: F403

DEBUG = False

if not os.environ.get("DJANGO_SECRET_KEY"):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set for VPS serving.")
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set for VPS serving (e.g. your domain or VPS IP).")

CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Nginx terminates TLS in front of Waitress and always sets X-Forwarded-Proto,
# so Django can trust that header to recognise https requests whatever the
# switches below decide (audit SEC-04).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Set DJANGO_HTTPS=1 once the certificate is installed and https:// works end
# to end: requests to http are redirected, and session and CSRF cookies stop
# travelling over plain http. HSTS needs DJANGO_HSTS=1 as well, so it can be
# turned on after https is verified rather than together with it.
_HTTPS_ON = {"1", "true", "yes"}
if os.environ.get("DJANGO_HTTPS", "").strip().lower() in _HTTPS_ON:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

if os.environ.get("DJANGO_HSTS", "").strip().lower() in _HTTPS_ON:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
