from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hybrid", "0013_alter_lessonattempt_unique_constraint"),
    ]

    operations = [
        migrations.AlterField(
            model_name="demonstrationevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("navigation", "Navigation"),
                    ("record_created", "Record created"),
                    ("record_updated", "Record updated"),
                    ("interaction", "Interaction"),
                ],
                max_length=20,
            ),
        ),
    ]
