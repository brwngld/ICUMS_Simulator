"""Seed port codes extracted from the ICUMS port-code reference PDFs (batch 1,
pages 1-200 of the Common Code list: 4,000 ports). Future batches append a new
fixture plus a migration of their own, so re-running stays idempotent."""

import json
from pathlib import Path

from django.db import migrations

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "port_codes_batch1.json"


def seed(apps, schema_editor):
    PortCode = apps.get_model("scenarios", "PortCode")
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = [
        PortCode(
            code=row["fields"]["code"],
            name=row["fields"]["name"],
            country_code=row["fields"]["country_code"],
            country_name=row["fields"]["country_name"],
            is_active=True,
        )
        for row in rows
    ]
    # ignore_conflicts keeps admin-maintained rows (e.g. GHTEM) untouched.
    PortCode.objects.bulk_create(records, ignore_conflicts=True, batch_size=500)


def unseed(apps, schema_editor):
    PortCode = apps.get_model("scenarios", "PortCode")
    codes = [row["fields"]["code"] for row in json.loads(FIXTURE.read_text(encoding="utf-8"))]
    PortCode.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0048_mdaconsignmentrequest_owner_updated_at"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
