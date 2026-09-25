from django.db import migrations


TAX_CODES = [
    ("01", "Import Duty", "cv", None, None, "all"),
    ("02", "Import VAT", "cv_duty", "15.000", None, "all"),
    ("05", "Processing Fee", "cv", "0.000", None, "all"),
    ("06", "ECOWAS Levy", "cv", "0.500", None, "all"),
    ("31", "Vehicle Examination Fee", "cv", "1.000", None, "vehicle"),
    ("32", "Network Charge", "fob", "0.400", None, "all"),
    ("33", "Network Charge VAT", "network", "15.000", None, "all"),
    ("45", "Ghana Shippers Authority SNF Fee", "flat", None, "12.00", "all"),
    ("47", "Import NHIL", "cv_duty", "2.500", None, "all"),
    ("48", "Network Charge NHIL", "network", "2.500", None, "all"),
    ("49", "Vehicle Overload Penalty", "cv", "5.000", None, "vehicle"),
    ("63", "GHS Disinfection Fee", "flat", None, "112.06", "all"),
    ("72", "MoTI e-IDF Fee", "flat", None, "5.00", "all"),
    ("78", "Special Import Levy (2%)", "cv", "2.000", None, "all"),
    ("87", "Ghana Export-Import Bank (EXIM) Levy", "cv", "0.750", None, "all"),
    ("88", "Ghana Education Trust (GET) Fund Import Levy", "cv_duty", "2.500", None, "all"),
    ("89", "Network Charge GET Fund Levy", "network", "2.500", None, "all"),
    ("98", "African Union Import Levy", "cv", "0.200", None, "all"),
]


def seed_tax_codes(apps, schema_editor):
    TaxCode = apps.get_model("assessment", "TaxCode")
    for code, name, base, rate, flat, applies_to in TAX_CODES:
        TaxCode.objects.update_or_create(
            code=code,
            defaults={"name": name, "base": base, "rate": rate, "flat_amount": flat, "applies_to": applies_to, "active": True},
        )


def remove_tax_codes(apps, schema_editor):
    TaxCode = apps.get_model("assessment", "TaxCode")
    TaxCode.objects.filter(code__in=[row[0] for row in TAX_CODES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_tax_codes, remove_tax_codes),
    ]
