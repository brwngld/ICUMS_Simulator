from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("onboarding", "0004_programme_cover_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="programme",
            name="target_audience",
            field=models.TextField(
                blank=True,
                help_text="Who this course is designed for. Shown on the learner course overview.",
            ),
        ),
        migrations.AddField(
            model_name="programme",
            name="learning_approach",
            field=models.TextField(
                blank=True,
                help_text="One learning method per line. Shown in the How you’ll learn overview card.",
            ),
        ),
    ]
