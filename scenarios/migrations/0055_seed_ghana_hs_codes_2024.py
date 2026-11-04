import json

from django.conf import settings
from django.db import migrations

#: The last tariff line the 2017 schedule carried into the first seed.
CUTOFF = "8463200000"


def new_rows() -> list[dict]:
    source = settings.BASE_DIR / "scenarios" / "data" / "ghana_hs_codes.json"
    rows = json.loads(source.read_text(encoding="utf-8"))
    return [row for row in rows if row["code"] > CUTOFF]


def add_hs_codes(apps, schema_editor):
    GhanaHSCode = apps.get_model("scenarios", "GhanaHSCode")
    GhanaHSCode.objects.bulk_create(
        [GhanaHSCode(**row) for row in new_rows()],
        batch_size=500,
        ignore_conflicts=True,
    )


def remove_hs_codes(apps, schema_editor):
    apps.get_model("scenarios", "GhanaHSCode").objects.filter(code__gt=CUTOFF).delete()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0054_alter_ucrdeclaration_exporter_identity_and_more")]
    operations = [migrations.RunPython(add_hs_codes, remove_hs_codes)]
