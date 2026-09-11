from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0004_scenarioversion_module")]

    operations = [
        migrations.AddField(
            model_name="scenariodocument",
            name="pdf_layout",
            field=models.CharField(
                choices=[
                    ("generic", "General customs document"),
                    ("bill_of_lading", "Bill of Lading"),
                    ("commercial_invoice", "Commercial Invoice"),
                    ("packing_list", "Packing List"),
                ],
                default="generic",
                max_length=24,
            ),
        ),
    ]
