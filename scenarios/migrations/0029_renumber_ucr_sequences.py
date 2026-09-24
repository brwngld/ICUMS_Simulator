"""Renumber existing UCR/temp references into per-year sequences (KGHTESTUCR260000001, ...)."""

from django.db import migrations

PREFIX_BY_FIELD = {"temp_no": "TEMPUCR", "ucr_no": "KGHTESTUCR"}


def renumber_ucr_sequences(apps, schema_editor):
    UcrDeclaration = apps.get_model("scenarios", "UcrDeclaration")
    records = sorted(UcrDeclaration.objects.all(), key=lambda record: (record.created_at, record.pk))

    # Phase 1: park current values on unique placeholders so phase 2 never collides.
    for record in records:
        changed = False
        for field, prefix in PREFIX_BY_FIELD.items():
            if getattr(record, field).startswith(prefix):
                setattr(record, field, f"RENUM-{record.pk}-{field}")
                changed = True
        if changed:
            record.save()

    # Phase 2: assign the clean per-year sequence in creation order.
    counters = {}
    for record in records:
        year = record.created_at.strftime("%y")
        changed = False
        for field, prefix in PREFIX_BY_FIELD.items():
            if getattr(record, field) == f"RENUM-{record.pk}-{field}":
                key = (prefix, year)
                counters[key] = counters.get(key, 0) + 1
                setattr(record, field, f"{prefix}{year}{counters[key]:07d}")
                changed = True
        if changed:
            record.save()


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0028_ucrdeclaration_optional_ucr_no")]
    operations = [migrations.RunPython(renumber_ucr_sequences, migrations.RunPython.noop)]
