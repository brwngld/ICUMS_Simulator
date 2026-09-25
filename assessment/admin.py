from django.contrib import admin

from .models import Assessment, TaxCode


@admin.register(TaxCode)
class TaxCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "base", "rate", "flat_amount", "applies_to", "active")
    list_filter = ("active", "applies_to", "base")
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("application", "customs_value", "import_duty", "total", "is_vehicle", "updated_at")
    search_fields = ("application__application_no", "application__ucr__ucr_no")
    readonly_fields = ("application", "exchange_rate", "fob_ncy", "freight_ncy", "insurance_ncy", "customs_value", "import_duty", "duty_hs_code", "is_vehicle", "total", "rows", "created_at", "updated_at")
