import json

from django.conf import settings
from django.db import migrations


def seed_hs_codes(apps, schema_editor):
    GhanaHSCode = apps.get_model("scenarios", "GhanaHSCode")
    source = settings.BASE_DIR / "scenarios" / "data" / "ghana_hs_codes.json"
    rows = json.loads(source.read_text(encoding="utf-8"))
    GhanaHSCode.objects.bulk_create(
        [GhanaHSCode(**row) for row in rows],
        batch_size=500,
        ignore_conflicts=True,
    )


def remove_hs_codes(apps, schema_editor):
    apps.get_model("scenarios", "GhanaHSCode").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0032_ghanahscode")]
    operations = [migrations.RunPython(seed_hs_codes, remove_hs_codes)]
