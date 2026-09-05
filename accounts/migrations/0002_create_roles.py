from django.db import migrations


ROLE_NAMES = ("Student", "Instructor", "Administrator")


def create_roles(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    for role_name in ROLE_NAMES:
        group_model.objects.get_or_create(name=role_name)


def remove_roles(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    group_model.objects.filter(name__in=ROLE_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(create_roles, remove_roles)]
