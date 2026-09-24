from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0022_trainingserviceprovider_declarant_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trainingserviceprovider",
            name="contact_name",
            field=models.CharField(blank=True, max_length=180),
        ),
        migrations.AlterField(
            model_name="trainingserviceprovider",
            name="phone",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AlterField(
            model_name="trainingserviceprovider",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
    ]
