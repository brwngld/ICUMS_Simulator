#!/usr/bin/env python3
"""One-time, guarded transfer from the local SQLite database to PostgreSQL."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MANAGE_PY = PROJECT_ROOT / "manage.py"
SQLITE_DATABASE = PROJECT_ROOT / "local_data" / "db.sqlite3"
BACKUP_DIRECTORY = PROJECT_ROOT / "backups"
SOURCE_SETTINGS = "config.settings.local"
COUNT_MARKER = "ICUMS_MODEL_COUNTS="

load_dotenv(PROJECT_ROOT / ".env")


def manage(settings_module: str, *arguments: str, capture: bool = False) -> str:
    environment = os.environ.copy()
    environment["DJANGO_SETTINGS_MODULE"] = settings_module
    environment["PYTHONUTF8"] = "1"
    command = [sys.executable, str(MANAGE_PY), *arguments]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=capture,
    )
    return result.stdout if capture else ""


def database_identity(settings_module: str) -> tuple[str, str]:
    code = (
        "from django.db import connection; "
        "connection.ensure_connection(); "
        "print('ICUMS_DATABASE=' + connection.vendor + ':' + connection.settings_dict['NAME'])"
    )
    output = manage(settings_module, "shell", "-c", code, capture=True)
    line = next(line for line in output.splitlines() if line.startswith("ICUMS_DATABASE="))
    vendor, name = line.removeprefix("ICUMS_DATABASE=").split(":", 1)
    return vendor, name


def model_counts(settings_module: str) -> dict[str, int]:
    code = (
        "import json; from django.apps import apps; "
        "print('ICUMS_MODEL_COUNTS=' + json.dumps({"
        "m._meta.label: m.objects.count() for m in apps.get_models()"
        "}, sort_keys=True))"
    )
    output = manage(settings_module, "shell", "-c", code, capture=True)
    line = next(line for line in output.splitlines() if line.startswith(COUNT_MARKER))
    return json.loads(line.removeprefix(COUNT_MARKER))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back up SQLite and transfer all Django data into PostgreSQL."
    )
    parser.add_argument(
        "--target-settings",
        default=os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.vps"),
        help="PostgreSQL settings module (default: DJANGO_SETTINGS_MODULE or config.settings.vps).",
    )
    parser.add_argument(
        "--replace-target",
        metavar="DATABASE_NAME",
        help=(
            "Required confirmation. The value must exactly match the PostgreSQL database name; "
            "all existing rows in that database will be replaced."
        ),
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    if not SQLITE_DATABASE.is_file():
        print(f"ERROR: SQLite database not found: {SQLITE_DATABASE}", file=sys.stderr)
        return 1

    vendor, database_name = database_identity(arguments.target_settings)
    if vendor != "postgresql":
        print(f"ERROR: Target settings use {vendor!r}, not PostgreSQL.", file=sys.stderr)
        return 1
    if arguments.replace_target != database_name:
        print("Refusing to replace the PostgreSQL target without exact confirmation.", file=sys.stderr)
        print("After confirming the target is correct, run:", file=sys.stderr)
        print(
            f"  {sys.executable} scripts/{Path(__file__).name} --replace-target {database_name}",
            file=sys.stderr,
        )
        return 2

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIRECTORY / f"db-before-postgresql-{timestamp}.sqlite3"
    shutil.copy2(SQLITE_DATABASE, backup_path)
    print(f"SQLite backup created: {backup_path}")

    fixture_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="icums-sqlite-export-", suffix=".json", delete=False
        ) as fixture:
            fixture_path = Path(fixture.name)

        print("Updating the SQLite schema...")
        manage(SOURCE_SETTINGS, "migrate", "--noinput")

        print("Exporting SQLite data as UTF-8...")
        manage(
            SOURCE_SETTINGS,
            "dumpdata",
            "--natural-foreign",
            "--natural-primary",
            "--output",
            str(fixture_path),
        )
        source_counts = model_counts(SOURCE_SETTINGS)

        print("Applying the PostgreSQL schema...")
        manage(arguments.target_settings, "migrate", "--noinput")

        print(f"Replacing data in PostgreSQL database {database_name!r}...")
        manage(arguments.target_settings, "flush", "--noinput")
        manage(arguments.target_settings, "loaddata", str(fixture_path))

        target_counts = model_counts(arguments.target_settings)
        if source_counts != target_counts:
            differences = {
                label: {"sqlite": source_counts.get(label), "postgresql": target_counts.get(label)}
                for label in sorted(source_counts.keys() | target_counts.keys())
                if source_counts.get(label) != target_counts.get(label)
            }
            print("ERROR: Row-count verification failed:", file=sys.stderr)
            print(json.dumps(differences, indent=2), file=sys.stderr)
            print(f"SQLite backup retained at: {backup_path}", file=sys.stderr)
            return 1

        total_objects = sum(target_counts.values())
        print(f"Migration successful: {total_objects} objects verified across all models.")
        print(f"Rollback backup retained at: {backup_path}")
        return 0
    finally:
        if fixture_path is not None:
            fixture_path.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
