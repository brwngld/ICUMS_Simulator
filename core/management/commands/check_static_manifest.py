import json
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand, CommandError


REQUIRED_ASSETS = (
    "css/app.css",
    "css/dash.css",
    "css/admin-dashboard.css",
    "css/simulator-portal.css",
    "css/cargo-page.css",
    "js/theme.js",
)


class Command(BaseCommand):
    help = "Verify that the production static manifest contains current application and Unfold assets."

    def handle(self, *args, **options):
        static_root = Path(settings.STATIC_ROOT).resolve()
        manifest_path = static_root / "staticfiles.json"
        if not manifest_path.is_file():
            raise CommandError(f"Static manifest not found: {manifest_path}. Run collectstatic first.")

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            paths = manifest["paths"]
        except (OSError, ValueError, KeyError) as error:
            raise CommandError(f"Static manifest is unreadable: {error}") from error

        problems = []
        if not any(name.startswith("unfold/") for name in paths):
            problems.append("manifest contains no Unfold assets")

        for name in REQUIRED_ASSETS:
            hashed_name = paths.get(name)
            if not hashed_name:
                problems.append(f"missing manifest entry: {name}")
                continue
            if not (static_root / hashed_name).is_file():
                problems.append(f"missing hashed file: {hashed_name}")
            source = finders.find(name)
            collected = static_root / name
            if not source or not collected.is_file():
                problems.append(f"cannot compare source and collected asset: {name}")
            elif Path(source).read_bytes() != collected.read_bytes():
                problems.append(f"collected source is stale: {name}")

        if problems:
            raise CommandError("Static manifest check failed:\n- " + "\n- ".join(problems))

        unfold_count = sum(1 for name in paths if name.startswith("unfold/"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Static manifest is current: {len(REQUIRED_ASSETS)} application assets and {unfold_count} Unfold assets verified."
            )
        )
