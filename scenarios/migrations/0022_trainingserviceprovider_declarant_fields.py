from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0021_trainingserviceprovider_contact_designation"),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingserviceprovider",
            name="declarant_prefix",
            field=models.CharField(default="CH", help_text="Two letters used when generating the declarant code, e.g. CH.", max_length=2),
        ),
        migrations.AddField(
            model_name="trainingserviceprovider",
            name="declarant_code",
            field=models.CharField(blank=True, editable=False, max_length=8, unique=True),
        ),
        migrations.AddField(
            model_name="trainingserviceprovider",
            name="email_2",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AlterField(
            model_name="trainingserviceprovider",
            name="code",
            field=models.CharField(help_text="The service provider's 11-character TIN or 13-character NID, not the declarant code.", max_length=13),
        ),
        migrations.AlterField(
            model_name="trainingserviceprovider",
            name="owner",
            field=models.ForeignKey(blank=True, help_text="Choose a student or your own account. Leave blank to make this record available to everyone in the training simulator.", null=True, on_delete=django.db.models.deletion.CASCADE, related_name="training_service_providers", to=settings.AUTH_USER_MODEL, verbose_name="Assigned to"),
        ),
        migrations.AlterModelOptions(
            name="trainingserviceprovider",
            options={"ordering": ("declarant_code", "name")},
        ),
    ]
