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
