from django.db import migrations


def seed_training_stakeholders(apps, schema_editor):
    Stakeholder = apps.get_model("scenarios", "TrainingStakeholder")
    names = [
        "Aster Training Traders Ltd", "Baobab Practice Imports Ltd", "Cedar Simulator Logistics Ltd",
        "Dawn Fictional Exports Ltd", "Eclipse Training Freight Ltd", "Falcon Practice Motors Ltd",
        "Golden Sample Goods Ltd", "Harbour Training Services Ltd", "Ivory Demo Machinery Ltd",
        "Jade Practice Ventures Ltd", "Kite Fictional Enterprise Ltd", "Lagoon Sample Trading Ltd",
        "Meridian Training Cargo Ltd", "Nimbus Practice Holdings Ltd", "Orchid Fictional Supply Ltd",
        "Palm Sample Distributors Ltd", "Quartz Training Agency Ltd", "River Practice Company Ltd",
        "Sunrise Fictional Merchants Ltd", "Tamarind Sample Freight Ltd",
    ]
    for index, name in enumerate(names, 1):
        code = f"C00{index:08d}"
        Stakeholder.objects.get_or_create(
            code=code, name=name,
            defaults={"description": "Fictional training company", "address": "" if index % 4 == 0 else f"Fictional training address {index}, Ghana"},
        )


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0011_trainingstakeholder")]
    operations = [migrations.RunPython(seed_training_stakeholders, migrations.RunPython.noop)]
