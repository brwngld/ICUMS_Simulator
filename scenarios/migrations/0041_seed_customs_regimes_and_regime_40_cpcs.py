import json
from pathlib import Path

from django.db import migrations


REGIMES = (
    ("00", "Reserved"), ("10", "Direct Export"),
    ("19", "Export of petroleum products following Petroleum Operations / Other Transactions"),
    ("20", "Direct Temporary Export"), ("27", "Temporary Export Following Warehousing"),
    ("30", "Direct Re-export for Goods landed but not entered"),
    ("34", "Re-export following home consumption"), ("35", "Re-export following temporary Admission"),
    ("37", "Re-export following warehousing"), ("39", "Other Re-export"),
    ("40", "Import into home consumption (Direct Import)"),
    ("45", "Import into home consumption following temporary admission"),
    ("47", "Import into home Consumption following warehousing"),
    ("48", "Home Consumption following coast-wise Transhipment/Transit"),
    ("49", "Import into home consumption following Free Zone / Duty Free Stores"),
    ("50", "Temporary Admission"), ("57", "Temporary Admission following warehouse"),
    ("59", "Temporary Admission Following Free Zone"), ("61", "Re-import following Direct Export"),
    ("62", "Re-import following Temporary Export"), ("70", "Direct entry into bonded warehouse"),
    ("72", "Warehousing Following Temporary Export"), ("75", "Warehousing Following Temporary Import"),
    ("77", "Bond To Bond (Warehousing)"), ("79", "Other Bond Operations"),
    ("80", "Transit / Transhipment / CoastWise Removal"),
    ("88", "Transit / Transhipment following Transit / Transhipment"),
    ("89", "Transit of petroleum products from Bond"),
    ("90", "Direct Entry into Free Zones / Ships Stores / Duty Free Stores"),
    ("94", "Entry into Free Zones / Ships Stores / Duty Free Stores from Domestic Market"),
    ("95", "Entry into Free Zones / Ships Stores / Duty Free Following Temporary Import"),
    ("97", "Entry into Free Zones / Ships Stores / Duty Free Following Warehouse"),
    ("99", "Other Operations"), ("24", "Temporary Export following Import into Home Use"),
)


def seed_codes(apps, schema_editor):
    CustomsRegime = apps.get_model("scenarios", "CustomsRegime")
    CustomsProcedureCode = apps.get_model("scenarios", "CustomsProcedureCode")
    regimes = {}
    for code, name in REGIMES:
        regime, _created = CustomsRegime.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})
        regimes[code] = regime
    data_path = Path(__file__).resolve().parents[1] / "data" / "regime_40_cpcs.json"
    for item in json.loads(data_path.read_text(encoding="utf-8")):
        CustomsProcedureCode.objects.update_or_create(
            code=item["code"],
            defaults={"regime": regimes["40"], "description": item["description"], "is_active": True},
        )


def remove_codes(apps, schema_editor):
    CustomsProcedureCode = apps.get_model("scenarios", "CustomsProcedureCode")
    CustomsRegime = apps.get_model("scenarios", "CustomsRegime")
    CustomsProcedureCode.objects.filter(regime__code="40").delete()
    CustomsRegime.objects.filter(code__in=[code for code, _name in REGIMES]).delete()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0040_customsregime_customsprocedurecode")]

    operations = [migrations.RunPython(seed_codes, remove_codes)]
