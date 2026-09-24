from django.db import migrations


def backfill(apps, schema_editor):
    Stakeholder = apps.get_model("scenarios", "TrainingStakeholder")
    Alias = apps.get_model("scenarios", "TrainingStakeholderName")
    for stakeholder in Stakeholder.objects.filter(roles=[]):
        stakeholder.roles = ["importer", "exporter"] if stakeholder.code.startswith("C00") else ["other"]
        stakeholder.save(update_fields=("roles",))
    for alias in Alias.objects.all():
        updates = []
        if not alias.roles:
            alias.roles = alias.stakeholder.roles
            updates.append("roles")
        if not alias.address:
            alias.address = alias.stakeholder.address
            updates.append("address")
        if updates:
            alias.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0014_trainingstakeholdername_address_and_more")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
