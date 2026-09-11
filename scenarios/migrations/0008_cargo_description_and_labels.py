from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0007_billoflading_billofladingcargoitem")]
    operations = [
        migrations.AlterField(model_name="billofladingcargoitem", name="goods_description", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="billofladingcargoitem", name="vehicle_year", field=models.PositiveSmallIntegerField("Year of manufacture", blank=True, null=True)),
        migrations.AlterField(model_name="billofladingcargoitem", name="vehicle_make", field=models.CharField("Make or manufacturer", blank=True, max_length=80)),
        migrations.AlterField(model_name="billofladingcargoitem", name="vehicle_model", field=models.CharField("Model", blank=True, max_length=100)),
        migrations.AlterField(model_name="billofladingcargoitem", name="vin_or_chassis", field=models.CharField("VIN, chassis or serial number", blank=True, max_length=80)),
    ]
