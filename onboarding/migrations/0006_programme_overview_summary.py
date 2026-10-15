from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0005_programme_overview_cards"),
    ]

    operations = [
        migrations.AddField(
            model_name="programme",
            name="overview_summary",
            field=models.TextField(
                blank=True,
                help_text="A concise summary shown in the What you’ll learn course overview card.",
            ),
        ),
    ]
