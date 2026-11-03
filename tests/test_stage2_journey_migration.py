"""Forward/reverse safety for the additive Stage 2 journey migration."""

import pytest
from django.db import connection
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor

from hybrid.models import HybridCourse, PracticalJourney
from onboarding.models import Programme, ProgrammeVersion


MIGRATION_0004 = ("hybrid", "0004_lessonattempt_stepevent_verificationcondition_and_more")
MIGRATION_0005 = ("hybrid", "0005_journey_foundation")
PROTECTED_TABLES = (
    "hybrid_practicalstep",
    "hybrid_verificationcondition",
    "hybrid_lessonattempt",
    "hybrid_stepevent",
    "onboarding_programmeversion",
    "onboarding_enrolment",
)


def protected_counts():
    with connection.cursor() as cursor:
        return {
            table: cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in PROTECTED_TABLES
        }


@pytest.fixture(autouse=True)
def _schema_back_at_the_leaves(transactional_db):
    """Put the schema back where the rest of the suite expects to find it.

    The tests below migrate *backwards* on purpose. A target is the whole desired
    state, so when they finish the database sits at hybrid 0005 and every later
    migration — in this app and in any app that depends on it — is unapplied. The
    test that did it never notices, but a later test opening its own connection
    does, which is why Stage 3 carried an inline repair. Forwarding to every app's
    leaf in teardown removes the ordering rule instead of compensating for it.
    """
    yield
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_empty_journey_tables_reverse_and_reapply_without_touching_legacy_rows():
    before = protected_counts()
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATION_0004])
    assert protected_counts() == before

    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATION_0005])
    assert protected_counts() == before
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
    assert "hybrid_practicaljourney" in tables
    assert "hybrid_journeyrecordassociation" in tables


@pytest.mark.django_db(transaction=True)
def test_populated_journey_tables_refuse_destructive_reverse_migration():
    programme = Programme.objects.create(
        name="Migration protection",
        code="migration-protection",
        learning_track=Programme.Track.HYBRID,
    )
    version = ProgrammeVersion.objects.create(programme=programme, version=1)
    course = HybridCourse.objects.create(programme_version=version, code="course", title="Course")
    PracticalJourney.objects.create(
        programme_version=version,
        course=course,
        code="protected",
        title="Protected",
    )

    with pytest.raises(IrreversibleError, match="populated Stage 2 journey tables"):
        MigrationExecutor(connection).migrate([MIGRATION_0004])

    assert PracticalJourney.objects.filter(code="protected").exists()


@pytest.mark.django_db
def test_the_schema_is_left_at_every_leaf_for_the_rest_of_the_suite():
    """The teardown above is the fix: no later test has to repair the schema."""
    executor = MigrationExecutor(connection)
    applied = set(executor.loader.applied_migrations)
    assert set(executor.loader.graph.leaf_nodes()) <= applied
