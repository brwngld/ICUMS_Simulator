"""Keep a reused test database consistent with its own migration history.

pytest-django runs non-transactional database tests last, and each one's
teardown is a database-wide ``flush``. That empties every table — including the
reference rows data migrations seeded (roles, port codes, customs offices, HS
codes, MDAs, customs regimes and procedures, training stakeholders, tax codes)
— while ``django_migrations`` stays stamped. With ``--reuse-db`` the next
session would then start against a migrated but empty database, and a suite can
fail wholesale after one such run.

So a reused test database is checked before the session's first database test:
if reference data its migrations are supposed to have created is gone, the
schema is dropped and migrations run again. Only a PostgreSQL database whose
name starts with ``test_`` is ever touched, nothing is seeded by hand, and the
session still starts from exactly what the migrations produce.
"""
import pytest

#: (app_label, model, filter, minimum rows) — one canary per data migration that
#: seeds reference data. Absence means the database was flushed.
_SEED_CANARIES = (
    ("auth", "Group", {"name__in": ("Student", "Instructor", "Administrator")}, 3),
    ("scenarios", "PortCode", {}, 1),
    ("scenarios", "CustomsOfficeCode", {}, 1),
    ("scenarios", "GhanaHSCode", {}, 1),
    ("scenarios", "MdaAgency", {}, 1),
    ("scenarios", "CustomsRegime", {}, 1),
    ("scenarios", "CustomsProcedureCode", {}, 1),
    ("scenarios", "TrainingStakeholder", {}, 1),
    ("assessment", "TaxCode", {}, 1),
)


def _missing_reference_data():
    from django.apps import apps

    missing = []
    for app_label, model_name, filters, minimum in _SEED_CANARIES:
        model = apps.get_model(app_label, model_name)
        if model.objects.filter(**filters).count() < minimum:
            missing.append(model_name)
    return missing


def _reset_schema_and_migrate():
    from django.core.management import call_command
    from django.db import connection

    connection.close()
    with connection.cursor() as cursor:
        cursor.execute("DROP SCHEMA public CASCADE")
        cursor.execute("CREATE SCHEMA public")
    call_command("migrate", verbosity=0, interactive=False, database=connection.alias)


def _repair_reused_test_database(request, *, keepdb, migrations_enabled):
    if not keepdb or not migrations_enabled:
        return
    from django.db import connection

    if connection.vendor != "postgresql":
        return
    if not str(connection.settings_dict.get("NAME") or "").startswith("test_"):
        return
    missing = _missing_reference_data()
    if not missing:
        return
    request.config.get_terminal_writer().line(
        f"Reused test database is missing reference data ({', '.join(missing)}); "
        "rebuilding its schema from migrations."
    )
    _reset_schema_and_migrate()


@pytest.fixture(scope="session")
def django_db_setup(
    request,
    django_test_environment,
    django_db_blocker,
    django_db_use_migrations,
    django_db_keepdb,
    django_db_createdb,
    django_db_modify_db_settings,
):
    """pytest-django's session setup, with a repair pass before the first test.

    The body mirrors ``pytest_django.fixtures.django_db_setup`` (4.14) because
    the repair has to run between database setup and the first test; a fixture
    cannot be chained into another fixture's arity.
    """
    from django.test.utils import setup_databases, teardown_databases
    from pytest_django.fixtures import _disable_migrations, _get_databases_for_setup

    setup_databases_args = {}
    if not django_db_use_migrations:
        _disable_migrations()
    if django_db_keepdb and not django_db_createdb:
        setup_databases_args["keepdb"] = True
    aliases, serialized_aliases = _get_databases_for_setup(request.session.items)

    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            aliases=aliases,
            serialized_aliases=serialized_aliases,
            **setup_databases_args,
        )
        _repair_reused_test_database(
            request,
            keepdb=django_db_keepdb and not django_db_createdb,
            migrations_enabled=django_db_use_migrations,
        )

    yield

    if not django_db_keepdb:
        with django_db_blocker.unblock():
            try:
                teardown_databases(db_cfg, verbosity=request.config.option.verbose)
            except Exception as exc:  # noqa: BLE001
                request.node.warn(pytest.PytestWarning(f"Error when trying to teardown test databases: {exc!r}"))
