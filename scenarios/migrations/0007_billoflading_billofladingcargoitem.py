import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0006_infer_training_document_layouts")]
    operations = [
        migrations.CreateModel(
            name="BillOfLading",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(default="Fictitious Bill of Lading", max_length=180)),
                ("reference", models.CharField(max_length=100, unique=True)),
                ("template", models.CharField(choices=[("carrier_grid", "Carrier Grid BL"), ("ocean_transport", "Ocean Transport BL"), ("multimodal", "Multimodal BL")], default="carrier_grid", max_length=24)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("published", "Published")], default="draft", max_length=12)),
                ("carrier", models.CharField(max_length=180)), ("carrier_agent", models.TextField(blank=True)), ("shipper", models.TextField()), ("consignee", models.TextField()), ("notify_party", models.TextField(blank=True)),
                ("booking_reference", models.CharField(blank=True, max_length=100)), ("shipper_reference", models.CharField(blank=True, max_length=100)), ("original_status", models.CharField(default="Non-negotiable training copy", max_length=80)), ("number_of_originals", models.PositiveSmallIntegerField(default=0)),
                ("vessel", models.CharField(max_length=180)), ("voyage_number", models.CharField(max_length=80)), ("place_of_receipt", models.CharField(blank=True, max_length=180)), ("port_of_loading", models.CharField(max_length=180)), ("port_of_discharge", models.CharField(max_length=180)), ("place_of_delivery", models.CharField(blank=True, max_length=180)),
                ("freight_terms", models.CharField(blank=True, max_length=180)), ("shippers_declared_value", models.CharField(blank=True, help_text="Optional BL declaration; this is not the commercial invoice total.", max_length=100)), ("place_of_issue", models.CharField(blank=True, max_length=180)), ("date_of_issue", models.DateField(blank=True, null=True)), ("shipped_on_board_date", models.DateField(blank=True, null=True)), ("additional_declarations", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("scenario_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bills_of_lading", to="scenarios.scenarioversion")),
            ],
            options={"verbose_name": "Bill of Lading", "verbose_name_plural": "Bills of Lading", "ordering": ("-updated_at", "title")},
        ),
        migrations.CreateModel(
            name="BillOfLadingCargoItem",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ("order", models.PositiveIntegerField(default=1)),
                ("cargo_type", models.CharField(choices=[("vehicle", "Vehicle"), ("general", "General merchandise"), ("personal_effects", "Household or personal effects"), ("machinery", "Machinery"), ("other", "Other cargo")], default="general", max_length=24)),
                ("container_number", models.CharField(max_length=30)), ("seal_number", models.CharField(blank=True, max_length=30)), ("container_type", models.CharField(blank=True, max_length=80)), ("marks_and_numbers", models.TextField(blank=True)),
                ("package_quantity", models.PositiveIntegerField(default=1)), ("package_type", models.CharField(default="package", max_length=80)), ("goods_description", models.TextField()),
                ("vehicle_year", models.PositiveSmallIntegerField(blank=True, null=True)), ("vehicle_make", models.CharField(blank=True, max_length=80)), ("vehicle_model", models.CharField(blank=True, max_length=100)), ("vin_or_chassis", models.CharField(blank=True, max_length=80)), ("hs_code", models.CharField(blank=True, max_length=24)),
                ("gross_weight", models.DecimalField(decimal_places=3, max_digits=12)), ("weight_unit", models.CharField(default="KGM", max_length=12)), ("measurement", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)), ("measurement_unit", models.CharField(default="MTQ", max_length=12)),
                ("bill_of_lading", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cargo_items", to="scenarios.billoflading")),
            ], options={"ordering": ("order", "id")},
        ),
    ]
