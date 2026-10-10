from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0046_alter_boedeclaration_declaration_no_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariostate",
            name="binding",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Optional simulator task for this step: {'route': <registry route name>, 'task': <label>, 'verify': {'record': 'ucr|boe|consignment|mda', 'status': <record status>}}.",
            ),
        ),
    ]
