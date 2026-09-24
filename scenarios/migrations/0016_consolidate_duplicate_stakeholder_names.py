from django.db import migrations


def consolidate(apps, schema_editor):
    Stakeholder = apps.get_model("scenarios", "TrainingStakeholder")
    for stakeholder in Stakeholder.objects.all():
        seen = {stakeholder.name.strip().casefold(): stakeholder}
        for alias in stakeholder.additional_names.all().order_by("pk"):
            key = alias.name.strip().casefold()
            kept = seen.get(key)
            if kept is None:
                seen[key] = alias
                continue
            kept.roles = list(dict.fromkeys([*kept.roles, *alias.roles]))
            updates = ["roles"]
            if not kept.address and alias.address:
                kept.address = alias.address
                updates.append("address")
            kept.save(update_fields=updates)
            alias.delete()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0015_backfill_training_name_roles")]
    operations = [migrations.RunPython(consolidate, migrations.RunPython.noop)]
