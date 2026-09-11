import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Create a portable ZIP backup of the local SQLite database and uploaded media."

    def add_arguments(self, parser):
        parser.add_argument("--output-dir", default="backups", help="Directory in which the backup ZIP is created.")

    def handle(self, *args, **options):
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("This command is only for the local SQLite deployment.")
        db_path = Path(database["NAME"]).resolve()
        if not db_path.is_file():
            raise CommandError(f"SQLite database not found: {db_path}")
        output_dir = Path(options["output_dir"]).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = output_dir / f"icums-simulator-backup-{stamp}.zip"
        connections.close_all()
        manifest = {"format": 1, "created_at_utc": stamp, "database_engine": "sqlite3", "database_file": "database.sqlite3"}
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(db_path, "database.sqlite3")
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.is_dir():
                for path in media_root.rglob("*"):
                    if path.is_file():
                        bundle.write(path, Path("media") / path.relative_to(media_root))
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2))
        self.stdout.write(self.style.SUCCESS(str(archive)))

