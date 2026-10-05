# Local Development

## Supported runtime

The project currently targets Python 3.12 and Django 5.2 LTS.

## Windows setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. Django Admin is available to trusted administrators at `http://127.0.0.1:8000/admin/`.

The development server must not be exposed to the internet.

## Production-style local server

After installing dependencies and applying migrations, start the application with Waitress and WhiteNoise:

```powershell
.\.venv\Scripts\python.exe start_local.py
```

Open `http://127.0.0.1:8000/`. The launcher performs a Django system check, collects static assets, binds only to a loopback address, and serves the application with four Waitress threads. Press `Ctrl+C` to stop it.

This mode is suitable for controlled use on the same computer. It deliberately refuses `0.0.0.0` or another network-facing bind address. A later hosted or local-network deployment requires the Phase 6 PostgreSQL, HTTPS, secrets, proxy, backup, and concurrency readiness work.

## Chosen hosting domain

`customsclearancepractice.com` has been set aside for the hosted deployment. When Phase 6 happens, point the DNS at the server, obtain the TLS certificate, and start the production server with:

```text
DJANGO_ALLOWED_HOSTS=customsclearancepractice.com,www.customsclearancepractice.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://customsclearancepractice.com
```

(the production settings already read these from the environment alongside the PostgreSQL and secret-key variables).

## Temporary VPS deployment (SQLite)

For short-lived training runs on an Ubuntu VPS, the SQLite database works as-is with Waitress bound externally. The `config/settings/vps.py` module exists for exactly this.

1. Copy the project to the VPS (git clone), create a virtualenv, and `pip install -r requirements.txt`.
2. Bring your current data: copy `local_data/db.sqlite3` (and `local_data/media/` if used) to the same paths — student accounts, passwords, and all records live there.
3. Serve with Waitress on an external interface:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.vps
export DJANGO_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DJANGO_ALLOWED_HOSTS="your.domain.or.vps.ip"
python manage.py migrate
python manage.py collectstatic --noinput
python -m waitress --listen=0.0.0.0:8000 config.wsgi:application
```

4. Open `http://<vps-ip>:8000/` (or the domain once DNS points at the VPS). Put nginx + certbot in front for HTTPS before real use — logins happen over this connection.

Notes:
- SQLite is fine for roughly ten concurrent trainees; heavy simultaneous saves can hit write locks briefly.
- Back up by copying `local_data/db.sqlite3` (the backup_local_system command also works).
- This module is temporary by design; the Phase 6 PostgreSQL gate supersedes it.

Day-2 operations under systemd: the `icums` service reads `.env` itself, but your interactive shell does not. `manage.py` defaults to the dev settings, which use plain static storage — running `collectstatic` that way quietly copies un-hashed files and writes no `staticfiles.json`, and the site then 500s on every page because the manifest-storaged `{% static %}` lookups fail. Source the environment first, every time:

```bash
cd ~/ICUMS_Simulator
set -a; source .env; set +a
.venv/bin/python manage.py collectstatic --noinput   # or migrate / shell / createsuperuser
sudo systemctl restart icums
```

Deploying new code always needs the same trio: `git pull`, `collectstatic` (as above) when static files changed, and `systemctl restart icums` when Python code changed — then a hard refresh in the browser, since pages and scripts may be cached.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
```

## Local data

The SQLite database, generated/uploaded media, collected static files, and test cache belong under `local_data/`. This directory is ignored by Git because it can contain private or machine-specific information.

## Backup and restore

Create a ZIP backup of the local SQLite database and uploaded media:

```powershell
.\.venv\Scripts\python.exe manage.py backup_local_system
```

The default destination is `backups/`. Copy important backups to a separate protected storage location.

To restore a verified archive, first stop the server. Then run:

```powershell
.\.venv\Scripts\python.exe manage.py restore_local_system backups\YOUR_BACKUP_FILE.zip --confirm
```

Restore replaces the active local database and merges archived media into the media directory. Before replacing the database, the command creates a timestamped safety copy beside the current database. Do not run restore while students are using the application.
