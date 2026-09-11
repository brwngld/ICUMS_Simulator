from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("learning", "0001_initial"), ("scenarios", "0003_scenarioversion_maximum_attempts_and_more")]

    operations = [
        migrations.AddField(
            model_name="scenarioversion",
            name="module",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="guided_practicals", to="learning.module"),
        ),
    ]
