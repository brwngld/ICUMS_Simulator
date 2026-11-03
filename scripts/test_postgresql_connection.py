#!/usr/bin/env python3
"""Read-only verification of the PostgreSQL connection configured in .env."""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.vps")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.db.migrations.executor import MigrationExecutor  # noqa: E402


def main() -> int:
    connection.ensure_connection()
    if connection.vendor != "postgresql":
        print(f"ERROR: Django is using {connection.vendor!r}, not PostgreSQL.", file=sys.stderr)
        return 1

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user, version()")
        database_name, database_user, server_version = cursor.fetchone()

    migration_plan = MigrationExecutor(connection).migration_plan(
        MigrationExecutor(connection).loader.graph.leaf_nodes()
    )

    print("PostgreSQL connection successful.")
    print(f"Settings module: {os.environ['DJANGO_SETTINGS_MODULE']}")
    print(f"Database: {database_name}")
    print(f"User: {database_user}")
    print(f"Server: {server_version.split(',')[0]}")
    print(f"Pending Django migrations: {len(migration_plan)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
