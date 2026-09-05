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

The development server is not the eventual packaged local server and must not be exposed to the internet.

## Tests and checks

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
```

## Local data

The SQLite database, generated/uploaded media, collected static files, test cache, and future backups belong under `local_data/`. This directory is ignored by Git because it can contain private or machine-specific information.

Backups are not implemented yet. Before students use the system, Phase 1 must add and test a command that backs up both the SQLite database and private media.
