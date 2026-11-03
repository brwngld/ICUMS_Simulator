#!/usr/bin/env python3
"""Restore the user UUIDs that the SQLite-to-PostgreSQL transfer reassigned.

``dumpdata --natural-primary`` omits the primary key of every model with a
natural key, and ``AbstractBaseUser.natural_key`` is the username. The transfer
therefore loaded all 16 users with fresh uuid4 values, while the rows written
before the transfer kept the original ids:

* ``audit_auditevent.target_id`` still holds the original UUID for every
  user-target event (the column is text, not a foreign key);
* ``SimulatorCredential`` hashes are derived from
  ``SECRET_KEY + user_id + issued_at``, so they no longer match the value the
  credential page recomputes.

Re-keying the users back restores both without rewriting audit history and
without reissuing any credential. A credential still awaiting its one-time
reveal is re-hashed to the value the credential page derives when its original
hash was made under a secret this installation no longer holds, so the reveal
it is about to make is honest; a credential already revealed keeps its hash. Foreign keys are updated in the same
transaction; Django's PostgreSQL constraints are ``DEFERRABLE INITIALLY
DEFERRED``, so ``SET CONSTRAINTS ALL DEFERRED`` lets the parent change after its
children.

Dry run by default. ``--apply`` needs ``--allow-database`` to name the target
database exactly, and takes a pg_dump backup first. ``--rollback MAPPING.json``
reverses a saved run. Re-running either direction is a verified no-op.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIRECTORY = PROJECT_ROOT / "backups"
DEFAULT_SQLITE = PROJECT_ROOT / "local_data" / "db.sqlite3"
USER_TABLE = "accounts_user"
#: Text columns that hold a user UUID without a foreign key. Rewritten only when
#: they contain one of the ids the repair is replacing; today that is nothing.
TEXT_REFERENCES = (("audit_auditevent", "target_id"), ("django_admin_log", "object_id"))

load_dotenv(PROJECT_ROOT / ".env")


def canonical(value):
    """The dashed form Django stores for a UUID."""
    return str(uuid.UUID(str(value)))


def sqlite_users(path):
    if not Path(path).is_file():
        raise SystemExit(f"ERROR: SQLite database not found: {path}")
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("select username, id from accounts_user").fetchall()
    finally:
        connection.close()
    return {username: canonical(pk) for username, pk in rows}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-sqlite", default=str(DEFAULT_SQLITE), help="SQLite database holding the original ids.")
    parser.add_argument(
        "--target-settings",
        default=os.environ.get("DJANGO_SETTINGS_MODULE", "config.settings.vps"),
        help="Django settings module for the PostgreSQL target.",
    )
    parser.add_argument("--mapping", help="Mapping file to write (apply) or read (rollback).")
    parser.add_argument("--apply", action="store_true", help="Perform the repair. Dry run without it.")
    parser.add_argument("--rollback", metavar="MAPPING.json", help="Undo a previously applied mapping.")
    parser.add_argument(
        "--allow-database",
        metavar="DATABASE_NAME",
        help="Required for --apply/--rollback: must exactly match the connected database name.",
    )
    parser.add_argument("--backup-dir", default=str(BACKUP_DIRECTORY), help="Directory for pg_dump backups.")
    parser.add_argument("--pg-dump", help="Path to pg_dump when it is not on PATH.")
    return parser.parse_args()


def configure_django(settings_module):
    os.environ["DJANGO_SETTINGS_MODULE"] = settings_module
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    import django

    django.setup()
    from django.db import connection

    return connection


def database_name(connection):
    return connection.settings_dict["NAME"]


def fetch_users(cursor):
    cursor.execute(f'select id, username from "{USER_TABLE}"')
    return {username: str(pk) for pk, username in cursor.fetchall()}


def foreign_keys(cursor):
    cursor.execute(
        """
        select c.relname, con.conname,
               array_agg(att.attname order by att.attnum)::text[]
        from pg_constraint con
        join pg_class c on c.oid = con.conrelid
        join pg_namespace n on n.oid = c.relnamespace
        join pg_attribute att
          on att.attrelid = con.conrelid and att.attnum = any(con.conkey)
        where con.contype = 'f' and con.confrelid = %s::regclass and n.nspname = 'public'
        group by 1, 2
        order by 1, 2
        """,
        (USER_TABLE,),
    )
    found = []
    for table, name, columns in cursor.fetchall():
        if len(columns) != 1:
            raise SystemExit(f"ERROR: composite key {table}.{name} is not handled; stop and review.")
        found.append((table, name, columns[0]))
    return found


def table_counts(cursor):
    cursor.execute(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE' order by 1"
    )
    counts = {}
    for (table,) in cursor.fetchall():
        cursor.execute(f'select count(*) from "{table}"')
        counts[table] = cursor.fetchone()[0]
    return counts


def build_plan(old_ids, current_ids, new_ids=None, reverse=False):
    """One entry per user: the id it holds now and the id this direction wants.

    Forward, the transferred id is whatever the row holds today. Rollback reads
    both ids from the saved mapping and refuses a third value.
    """
    plan = []
    mismatched = []
    for username in sorted(old_ids):
        old = old_ids[username]
        current = current_ids.get(username)
        if current is None:
            mismatched.append(f"{username}: missing from PostgreSQL")
            continue
        if reverse:
            new = new_ids[username]
            if current not in (old, new):
                mismatched.append(f"{username}: id {current} is neither the original nor the recorded one")
                continue
            source, destination = current, new
        else:
            new = current
            source, destination = current, old
        plan.append({"username": username, "old": old, "new": new,
                     "source": source, "destination": destination})
    if set(current_ids) - set(old_ids):
        mismatched.append("PostgreSQL has users absent from SQLite: " + ", ".join(sorted(set(current_ids) - set(old_ids))))
    if mismatched:
        raise SystemExit("ERROR: mapping cannot be built:\n  " + "\n  ".join(mismatched))
    return plan


def locate_pg_dump(explicit):
    if explicit:
        return explicit
    found = shutil.which("pg_dump")
    if found:
        return found
    for candidate in (
        Path("C:/Program Files/PostgreSQL/18/bin/pg_dump.exe"),
        Path("C:/Program Files/PostgreSQL/17/bin/pg_dump.exe"),
        Path("C:/Program Files/PostgreSQL/16/bin/pg_dump.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("ERROR: pg_dump not found. Pass --pg-dump.")


def take_backup(connection, directory, pg_dump):
    settings_dict = connection.settings_dict
    target = Path(directory) / (
        f"pg-{settings_dict['NAME']}-before-uuid-restore-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.dump"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    if settings_dict.get("PASSWORD"):
        environment["PGPASSWORD"] = settings_dict["PASSWORD"]
    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--host", str(settings_dict["HOST"] or "127.0.0.1"),
        "--port", str(settings_dict["PORT"] or "5432"),
        "--username", settings_dict["USER"],
        "--dbname", settings_dict["NAME"],
        "--file", str(target),
    ]
    result = subprocess.run(command, env=environment, text=True, capture_output=True)
    if result.returncode != 0:
        raise SystemExit(f"ERROR: pg_dump failed; nothing was changed.\n{result.stderr.strip()}")
    print(f"Backup: {target}")
    return target


def write_mapping(path, mapping):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print(f"Mapping: {path}")


def apply_plan(cursor, plan, keys):
    """Move every id in one transaction; constraints re-check at commit."""
    pending = [entry for entry in plan if entry["source"] != entry["destination"]]
    if not pending:
        print("Nothing to change: every user already holds its target id.")
        return 0
    pairs = [(entry["source"], entry["destination"]) for entry in pending]
    cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    for table, name, column in keys:
        for source, destination in pairs:
            cursor.execute(
                f'update "{table}" set "{column}" = %s where "{column}" = %s',
                (destination, source),
            )
    for table, column in TEXT_REFERENCES:
        for source, destination in pairs:
            cursor.execute(
                f'update "{table}" set "{column}" = %s where "{column}" = %s',
                (destination, source),
            )
    for source, destination in pairs:
        cursor.execute(f'update "{USER_TABLE}" set id = %s where id = %s', (destination, source))
    print(f"Re-keyed {len(pending)} user(s); foreign keys and text references followed.")
    return len(pending)


def repair_credentials():
    """Re-hash the derived password where the one-time reveal has not happened.

    Restoring the UUID makes a credential derivable again only when it was
    issued under the secret this installation still holds. A credential whose
    password was already shown keeps its stored hash untouched: that hash is
    the only remaining record of the password the learner holds, and re-hashing
    it would silently revoke a working credential. One still awaiting its
    reveal is re-hashed to the value the credential page derives, so the reveal
    it is about to make is honest. ``issued_at``, ``expires_at`` and
    ``revealed_at`` are untouched, and no value is ever printed.
    """
    from django.contrib.auth.hashers import check_password, make_password

    from accounts.models import SimulatorCredential

    repaired = []
    preserved = []
    for credential in SimulatorCredential.objects.select_related("user").order_by("user__username"):
        derived = credential.recompute_password()
        if derived and check_password(derived, credential.password_hash):
            continue
        if credential.revealed_at:
            preserved.append(credential.user.username)
            continue
        credential.password_hash = make_password(derived)
        credential.save(update_fields=["password_hash"])
        repaired.append(credential.user.username)
    return repaired, preserved


def credential_report():
    from django.contrib.auth.hashers import check_password

    from accounts.models import SimulatorCredential

    report = []
    for credential in SimulatorCredential.objects.select_related("user").order_by("user__username"):
        # The derived value never leaves this frame; only the comparison does.
        derived = credential.recompute_password()
        report.append(
            {
                "username": credential.user.username,
                "revealed": bool(credential.revealed_at),
                "derivation_matches_hash": bool(derived) and check_password(derived, credential.password_hash),
            }
        )
    return report


def verify(cursor, plan, expected_key, before_counts, expect_credentials=True, preserved_hashes=None):
    problems = []
    after_counts = table_counts(cursor)
    if after_counts != before_counts:
        changed = {name: (before_counts.get(name), after_counts.get(name))
                   for name in before_counts.keys() | after_counts.keys()
                   if before_counts.get(name) != after_counts.get(name)}
        problems.append(f"row counts changed: {changed}")
    cursor.execute(f'select id, username from "{USER_TABLE}"')
    current = {str(pk): username for pk, username in cursor.fetchall()}
    for entry in plan:
        expected = entry[expected_key]
        if current.get(expected) != entry["username"]:
            problems.append(f"{entry['username']}: expected {expected}, found {current.get(entry['username'])}")
    old_ids = [entry["old"] for entry in plan]
    cursor.execute(
        "select count(*) from audit_auditevent where target_type='user' and target_id = any(%s)",
        (old_ids,),
    )
    resolved = cursor.fetchone()[0]
    cursor.execute(
        "select count(*) from audit_auditevent where target_type='user' and target_id = any(%s)",
        ([entry["new"] for entry in plan],),
    )
    stale = cursor.fetchone()[0]
    if expected_key == "old" and stale:
        problems.append(f"{stale} audit event(s) still point at a transferred UUID")
    if expected_key == "new":
        # A rollback deliberately returns to the broken state; the counts are
        # reported so the operator can see that, not treated as a failure.
        print("Rollback in place: audit history points at the transferred ids again, as before the repair.")
    credentials = credential_report() if expect_credentials else []
    if expect_credentials and expected_key == "old":
        broken = [row["username"] for row in credentials
                  if not row["revealed"] and not row["derivation_matches_hash"]]
        if broken:
            problems.append("pending credentials whose password no longer matches their hash: " + ", ".join(broken))
        if preserved_hashes:
            from accounts.models import SimulatorCredential

            live = dict(SimulatorCredential.objects.values_list("user__username", "password_hash"))
            changed = [name for name, value in preserved_hashes.items() if live.get(name) != value]
            if changed:
                problems.append("revealed credential hashes changed: " + ", ".join(changed))
        cursor.execute(
            "select count(*) from audit_auditevent e join accounts_user u on u.id::text = e.target_id "
            "where e.target_type='user'"
        )
        audit_resolved = cursor.fetchone()[0]
        cursor.execute(
            "select count(*) from django_admin_log l join accounts_user u on u.id::text = l.object_id "
            "where l.content_type_id = (select id from django_content_type "
            "where app_label='accounts' and model='user')"
        )
        admin_resolved = cursor.fetchone()[0]
        print(f"After repair: audit events resolving to a user: {audit_resolved}; "
              f"admin-log entries resolving to a user: {admin_resolved}")
    print(f"Users checked: {len(plan)}; audit events on original ids: {resolved}; on transferred ids: {stale}")
    for row in credentials:
        print(f"  credential {row['username']}: revealed={row['revealed']} "
              f"hash_matches_derivation={row['derivation_matches_hash']}")
    if problems:
        raise SystemExit("VERIFICATION FAILED:\n  " + "\n  ".join(problems))
    print("Verification passed.")


def main():
    arguments = parse_arguments()
    if arguments.apply and arguments.rollback:
        raise SystemExit("ERROR: choose --apply or --rollback, not both.")
    if (arguments.apply or arguments.rollback) and not arguments.allow_database:
        raise SystemExit("ERROR: --apply/--rollback require --allow-database <exact database name>.")

    connection = configure_django(arguments.target_settings)
    name = database_name(connection)
    if (arguments.apply or arguments.rollback) and arguments.allow_database != name:
        raise SystemExit(
            f"ERROR: connected database is {name!r}, not {arguments.allow_database!r}; refusing to write."
        )

    sqlite_ids = sqlite_users(arguments.source_sqlite)
    if arguments.rollback:
        mapping = json.loads(Path(arguments.rollback).read_text(encoding="utf-8"))
        plan = build_plan(
            {entry["username"]: entry["old"] for entry in mapping["users"]},
            fetch_users(connection.cursor()),
            new_ids={entry["username"]: entry["new"] for entry in mapping["users"]},
            reverse=True,
        )
        expect_credentials = False
        expected_key = "new"
        mapping_path = Path(arguments.rollback)
    else:
        current_ids = fetch_users(connection.cursor())
        plan = build_plan(sqlite_ids, current_ids, reverse=False)
        expect_credentials = True
        expected_key = "old"
        mapping_path = Path(arguments.mapping) if arguments.mapping else (
            BACKUP_DIRECTORY / f"user-uuid-reconciliation-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
        )
        if mapping_path.exists():
            # A rerun after a completed repair no longer sees the transferred id
            # in the database; the saved mapping still knows it, and a rollback
            # needs it.
            recorded = {entry["username"]: entry["new"] for entry in
                        json.loads(mapping_path.read_text(encoding="utf-8"))["users"]}
            for entry in plan:
                if entry["new"] == entry["old"] and recorded.get(entry["username"], entry["old"]) != entry["old"]:
                    entry["new"] = recorded[entry["username"]]

    pending = [entry for entry in plan if entry["source"] != entry["destination"]]
    print(f"Database: {name} ({connection.vendor})")
    print(f"Users: {len(plan)}; to re-key: {len(pending)}")
    for entry in plan:
        state = "already correct" if entry["source"] == entry["destination"] else f"{entry['source']} -> {entry['destination']}"
        print(f"  {entry['username']}: {state}")

    with connection.cursor() as cursor:
        keys = foreign_keys(cursor)
        print(f"Foreign keys to {USER_TABLE}: {len(keys)}")
        before_counts = table_counts(cursor)

    if not arguments.apply and not arguments.rollback:
        print("Dry run: no changes written. Re-run with --apply --allow-database "
              f"{name} to repair.")
        return 0

    if arguments.apply:
        backup = take_backup(connection, arguments.backup_dir, locate_pg_dump(arguments.pg_dump))
        mapping = {
            "generated_at": datetime.now(UTC).isoformat(),
            "database": name,
            "source_sqlite": str(Path(arguments.source_sqlite).resolve()),
            "backup": str(backup),
            "users": [{"username": entry["username"], "old": entry["old"], "new": entry["new"]} for entry in plan],
            "foreign_keys": [{"table": table, "constraint": constraint, "column": column}
                             for table, constraint, column in keys],
        }
        if pending or not mapping_path.exists():
            write_mapping(mapping_path, mapping)
        else:
            print(f"Mapping kept: {mapping_path}")

    from django.db import transaction

    preserved_hashes = {}
    if arguments.apply:
        from accounts.models import SimulatorCredential

        preserved_hashes = dict(
            SimulatorCredential.objects.filter(revealed_at__isnull=False)
            .values_list("user__username", "password_hash")
        )

    with transaction.atomic():
        with connection.cursor() as cursor:
            apply_plan(cursor, plan, keys)
        if arguments.apply:
            repaired, preserved = repair_credentials()
            print("Credential hashes re-derived: " + (", ".join(repaired) if repaired else "none (all already match)"))
            if preserved:
                print("Revealed credential hashes preserved: " + ", ".join(preserved))
        with connection.cursor() as cursor:
            verify(cursor, plan, expected_key, before_counts, expect_credentials=expect_credentials,
                   preserved_hashes=preserved_hashes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
