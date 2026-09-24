from django.db import migrations


CORE_MDAS = (
    ("EPA", "Environmental Protection Agency"),
    ("FDA", "Food and Drugs Authority"),
    ("GSA", "Ghana Standards Authority"),
)


def seed_core_mdas(apps, schema_editor):
    MdaAgency = apps.get_model("scenarios", "MdaAgency")
    for code, name in CORE_MDAS:
        MdaAgency.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})


def remove_core_mdas(apps, schema_editor):
    MdaAgency = apps.get_model("scenarios", "MdaAgency")
    MdaAgency.objects.filter(code__in=[code for code, _name in CORE_MDAS], applications__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0035_mdaagency_mdaapplication_mdaprocess_and_more")]

    operations = [migrations.RunPython(seed_core_mdas, remove_core_mdas)]
