from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_owner(apps, schema_editor):
    """Every MDA request derives from a consignment application that has an
    owner; copy that owner. Rows without an application cannot exist (the FK
    is non-nullable), so the backfill is deterministic — but guard anyway and
    fail loudly rather than silently assigning an owner we cannot prove."""
    MdaConsignmentRequest = apps.get_model("scenarios", "MdaConsignmentRequest")
    updated = 0
    for request in MdaConsignmentRequest.objects.select_related("consignment_application__owner").only("pk", "consignment_application__owner"):
        owner = request.consignment_application.owner if request.consignment_application else None
        if owner is None:
            raise RuntimeError(
                f"MDA request {request.pk} has no consignment-application owner to backfill; "
                "refusing to guess ownership."
            )
        request.owner = owner
        request.save(update_fields=("owner",))
        updated += 1
    if updated:
        print(f"Backfilled owner on {updated} MDA consignment request(s).")


def unbackfill_owner(apps, schema_editor):
    # Reverse only re-nulls the column; the AlterField below must run first.
    MdaConsignmentRequest = apps.get_model("scenarios", "MdaConsignmentRequest")
    MdaConsignmentRequest.objects.update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        ("scenarios", "0047_scenariostate_binding"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="mdaconsignmentrequest",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="mda_consignment_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_owner, unbackfill_owner),
        migrations.AlterField(
            model_name="mdaconsignmentrequest",
            name="owner",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="mda_consignment_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="mdaconsignmentrequest",
            name="updated_at",
            field=models.DateTimeField(default=timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="mdaconsignmentrequest",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
