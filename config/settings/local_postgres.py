"""Local development against PostgreSQL; the SQLite setup stays in local.py.

serve with:  python manage.py runserver --settings=config.settings.local_postgres
"""

import os

from .local import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "icums_simulator"),
        "USER": os.environ.get("POSTGRES_USER", "myproject_user"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Demonstration recording is enabled for local PostgreSQL development only:
# base.py keeps the default False, and production/vps never inherit this
# module. The functional Demonstration Studio (recording, navigation capture,
# lesson conversion) is part of the local development workflow.
DEMONSTRATION_RECORDING_ENABLED = True
