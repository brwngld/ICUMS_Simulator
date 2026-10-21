"""Production-style settings for serving the local V1 on one computer."""

import os

from django.core.exceptions import ImproperlyConfigured

from .local import *  # noqa: F403

DEBUG = False

# Serving with DEBUG off means real sessions and real student records; the
# repository's development fallback key must not protect them (audit SEC-10).
if not os.environ.get("DJANGO_SECRET_KEY"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set when serving with local_production settings."
    )

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
