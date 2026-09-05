"""Local development and single-computer V1 settings."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

LOCAL_DATA_DIR.mkdir(exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": LOCAL_DATA_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}
