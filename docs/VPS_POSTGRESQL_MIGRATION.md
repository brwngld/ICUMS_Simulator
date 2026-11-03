# VPS SQLite to PostgreSQL migration

Run these commands from the ICUMS Simulator project directory on the VPS.

## 1. Confirm `.env`

The project `.env` file must contain:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.vps
DJANGO_SECRET_KEY=your-real-secret-key
DJANGO_ALLOWED_HOSTS=your-domain-or-vps-ip
DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain

POSTGRES_DB=icums_simulator
POSTGRES_USER=myproject_user
POSTGRES_PASSWORD=your-postgresql-password
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Do not commit `.env` to Git.

## 2. Update the application and dependencies

```bash
cd /path/to/Icums_Simulator
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Replace `/path/to/Icums_Simulator` with the real project path.

## 3. Test PostgreSQL without changing data

```bash
python scripts/test_postgresql_connection.py
```

Confirm that the output reports:

```text
PostgreSQL connection successful.
Database: icums_simulator
Pending Django migrations: 0
```

The number of pending migrations can be greater than zero before the one-time
transfer. The transfer script applies them.

## 4. Run the one-time data transfer

Stop the application service first so users cannot change SQLite data during
the transfer. Replace `icums-simulator` if the systemd service has another
name.

```bash
sudo systemctl stop icums-simulator
```

Run the transfer:

```bash
python scripts/migrate_sqlite_to_postgresql.py \
  --replace-target icums_simulator
```

Warning: this command replaces all existing rows in the PostgreSQL database
named `icums_simulator`. Run it only for the initial SQLite-to-PostgreSQL
transfer.

The script will:

1. Verify that the target is PostgreSQL.
2. Create a dated SQLite backup in `backups/`.
3. Update the SQLite schema.
4. Apply the PostgreSQL schema migrations.
5. Replace the PostgreSQL data with the SQLite records.
6. Compare every Django model's row count.
7. Remove the temporary data export.

Successful output ends with a message similar to:

```text
Migration successful: 15835 objects verified across all models.
Rollback backup retained at: ...
```

## 5. Verify and restart

```bash
python scripts/test_postgresql_connection.py
python manage.py check
sudo systemctl start icums-simulator
sudo systemctl status icums-simulator --no-pager
```

Sign in and check an existing student, course, assessment, simulator record,
and report.

If the service has a different name, use that name in the `systemctl`
commands.

## 6. Verify user identities (one-time, after the transfer)

`dumpdata --natural-primary` omits the primary key of models with a natural key.
For users that key is the username, so the transfer loads every user with a
fresh UUID while text references — `audit_auditevent.target_id` and
`django_admin_log.object_id` — keep the original ids. Simulator credential
hashes are derived from `SECRET_KEY`, the user id and `issued_at`, so they stop
matching too. Run the reconciliation once, after the transfer:

```bash
python scripts/reconcile_user_uuids.py            # dry run: prints the plan
python scripts/reconcile_user_uuids.py --apply --allow-database icums_simulator
```

It takes a `pg_dump` backup first, writes a mapping file under `backups/`,
re-keys the users and every foreign key in one transaction, re-hashes only
credentials whose one-time reveal has not happened yet, and verifies row counts,
audit resolution and credential state before committing. Re-running it is a
no-op; `--rollback MAPPING.json --allow-database icums_simulator` reverses it.

Never re-hash a credential that has already been revealed: its stored hash is
the only record of the password the learner holds.

## Future deployments

Do not run the SQLite transfer script again. For normal future deployments,
use:

```bash
cd /path/to/Icums_Simulator
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py check
sudo systemctl restart icums-simulator
```

Keep the dated SQLite backup until PostgreSQL has been operating successfully
and a PostgreSQL backup process has been verified.
