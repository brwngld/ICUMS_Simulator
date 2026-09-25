from django.db import models


class TaxCode(models.Model):
    """Configurable tax/levy applied during an import assessment.

    base selects which amount the rate applies to (the ICUMS "TBC" code);
    rate is a percentage, except Import Duty (code 01) whose rate always comes
    from the item's HS code. Flat levies use base=flat with flat_amount.
    """

    class Base(models.TextChoices):
        CUSTOMS_VALUE = "cv", "Customs Value"
        CV_PLUS_DUTY = "cv_duty", "Customs Value + Import Duty"
        FOB_NCY = "fob", "FOB Ncy"
        NETWORK_CHARGE = "network", "Network Charge"
        FLAT = "flat", "Flat amount"

    class AppliesTo(models.TextChoices):
        ALL = "all", "All goods"
        VEHICLES = "vehicle", "Vehicles only"

    code = models.CharField("tax code", max_length=4, unique=True)
    name = models.CharField(max_length=120)
    base = models.CharField(max_length=12, choices=Base.choices, default=Base.CUSTOMS_VALUE)
    rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, help_text="Percent. Leave empty only for Import Duty (01): it uses the HS code duty rate.")
    flat_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, help_text="Used when base is flat.")
    applies_to = models.CharField(max_length=8, choices=AppliesTo.choices, default=AppliesTo.ALL)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"


class Assessment(models.Model):
    """Stored duty assessment snapshot for a consignment application."""

    application = models.OneToOneField("scenarios.ConsignmentApplication", on_delete=models.CASCADE, related_name="assessment")
    exchange_rate = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    fob_ncy = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    freight_ncy = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    insurance_ncy = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    customs_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    import_duty = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    duty_hs_code = models.CharField(max_length=10, blank=True)
    is_vehicle = models.BooleanField(default=False)
    total = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rows = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        return f"Assessment for {self.application.application_no or self.application.pk}"
