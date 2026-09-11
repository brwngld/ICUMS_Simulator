import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Restore a local backup after making a safety copy of the current SQLite database."

    def add_arguments(self, parser):
        parser.add_argument("archive", help="Path to a backup ZIP created by backup_local_system.")
        parser.add_argument("--confirm", action="store_true", help="Required acknowledgement that current local data will be replaced.")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Restore replaces current local data. Re-run with --confirm after verifying the archive path.")
        database = settings.DATABASES["default"]
        if database["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("This command is only for the local SQLite deployment.")
        archive = Path(options["archive"]).resolve()
        if not archive.is_file():
            raise CommandError(f"Backup archive not found: {archive}")
        db_path = Path(database["NAME"]).resolve()
        media_root = Path(settings.MEDIA_ROOT).resolve()
        with zipfile.ZipFile(archive) as bundle:
            names = set(bundle.namelist())
            if not {"manifest.json", "database.sqlite3"}.issubset(names):
                raise CommandError("The archive is not a valid simulator backup.")
            manifest = json.loads(bundle.read("manifest.json"))
            if manifest.get("format") != 1 or manifest.get("database_engine") != "sqlite3":
                raise CommandError("The backup format is unsupported.")
            unsafe = [name for name in names if Path(name).is_absolute() or ".." in Path(name).parts]
            if unsafe:
                raise CommandError("The backup contains unsafe paths and was not restored.")
            with tempfile.TemporaryDirectory(prefix="icums-restore-") as temp_dir:
                temp_path = Path(temp_dir)
                bundle.extractall(temp_path)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                safety_copy = db_path.with_name(f"{db_path.name}.before-restore-{stamp}")
                connections.close_all()
                if db_path.exists():
                    shutil.copy2(db_path, safety_copy)
                db_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(temp_path / "database.sqlite3", db_path)
                restored_media = temp_path / "media"
                if restored_media.is_dir():
                    media_root.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(restored_media, media_root, dirs_exist_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Restored {archive}. Previous database safety copy: {safety_copy}"))
