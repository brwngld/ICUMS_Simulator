"""Throwaway verification settings — fresh SQLite DB and media dir, never the
real PostgreSQL data. Delete this module after the browser check."""
from .local import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "local_data" / "db.guided_verify.sqlite3",
    }
}
MEDIA_ROOT = BASE_DIR / "local_data" / "media_guided_verify"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]