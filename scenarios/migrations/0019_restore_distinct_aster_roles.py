from django.db import migrations


def restore(apps, schema_editor):
    Stakeholder = apps.get_model("scenarios", "TrainingStakeholder")
    Alias = apps.get_model("scenarios", "TrainingStakeholderName")
    stakeholder = Stakeholder.objects.filter(code="C0025673301", name="Aster Training Traders Ltd").first()
    if not stakeholder:
        return
    combined_roles = {"importer", "exporter", "cha", "freight_forwarder"}
    if set(stakeholder.roles) != combined_roles:
        return
    if Alias.objects.filter(stakeholder=stakeholder, name__iexact=stakeholder.name).exists():
        return
    stakeholder.roles = ["importer", "exporter"]
    stakeholder.save(update_fields=("roles",))
    Alias.objects.create(
        stakeholder=stakeholder,
        name="Aster Training Traders Ltd",
        address="Fictional training address 1, Ghana",
        roles=["cha", "freight_forwarder"],
    )


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0018_remove_trainingstakeholdername_unique_stakeholder_additional_name_and_more")]
    operations = [migrations.RunPython(restore, migrations.RunPython.noop)]
