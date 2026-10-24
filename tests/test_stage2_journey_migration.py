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
