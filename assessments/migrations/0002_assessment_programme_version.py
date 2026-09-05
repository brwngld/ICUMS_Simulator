import django.db.models.deletion
from django.db import migrations, models


def populate_programme_version(apps, schema_editor):
    assessment_model = apps.get_model("assessments", "Assessment")
    for assessment in assessment_model.objects.select_related("module__programme_version"):
        if assessment.module_id:
            assessment.programme_version_id = assessment.module.programme_version_id
            assessment.save(update_fields=("programme_version",))


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0001_initial"),
        ("onboarding", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="assessment",
            name="programme_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessments",
                to="onboarding.programmeversion",
            ),
        ),
        migrations.RunPython(populate_programme_version, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="assessment",
            name="programme_version",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessments",
                to="onboarding.programmeversion",
            ),
        ),
    ]
