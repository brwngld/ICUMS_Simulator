from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import AssistanceEvent, BillOfLading, BillOfLadingCargoItem, CommercialDocument, CommercialDocumentLine, Scenario, ScenarioAction, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument, ScenarioState, ScenarioVersion


class BillOfLadingCargoItemInline(admin.StackedInline):
    model = BillOfLadingCargoItem
    extra = 1
    fieldsets = (
        ("Container and packages", {"fields": (("order", "cargo_type"), ("container_number", "seal_number", "container_type"), ("package_quantity", "package_type"), "marks_and_numbers")}),
        ("Goods description", {"fields": ("goods_description", ("vehicle_year", "vehicle_make", "vehicle_model"), ("vin_or_chassis", "hs_code"), ("gross_weight", "weight_unit", "measurement", "measurement_unit"))}),
    )


@admin.register(BillOfLading)
class BillOfLadingAdmin(admin.ModelAdmin):
    change_form_template = "admin/scenarios/billoflading/change_form.html"
    list_display = ("reference", "title", "template", "status", "scenario_version", "updated_at")
    list_filter = ("template", "status", "scenario_version")
    search_fields = ("reference", "title", "shipper", "consignee", "vessel")
    inlines = (BillOfLadingCargoItemInline,)
    fieldsets = (
        ("Document setup", {"fields": (("scenario_version", "status"), ("title", "reference"), ("template", "original_status", "number_of_originals"))}),
        ("Parties", {"fields": ("carrier", "carrier_agent", "shipper", "consignee", "notify_party")}),
        ("References and route", {"fields": (("booking_reference", "shipper_reference"), ("vessel", "voyage_number"), ("place_of_receipt", "port_of_loading"), ("port_of_discharge", "place_of_delivery"))}),
        ("Issue and shipping information", {"fields": ("freight_terms", "shippers_declared_value", ("place_of_issue", "date_of_issue", "shipped_on_board_date"), "additional_declarations")}),
    )

    class Media:
        css = {"all": ("admin/css/bl-editor.css", "admin/css/bl-editor-fields-v2.css")}
        js = ("admin/js/bl-editor.js", "admin/js/bl-editor-fields-v2.js")


class CommercialDocumentLineInline(admin.StackedInline):
    model = CommercialDocumentLine
    extra = 1
    fieldsets = (
        ("Cargo and packages", {"fields": (("order", "description"), ("quantity", "quantity_unit", "package_count"), ("pieces_per_package", "hs_code"), ("dimensions", "net_weight", "gross_weight", "weight_unit"))}),
        ("Invoice pricing (hidden for packing lists)", {"fields": (("unit_price", "amount"),)}),
    )


@admin.register(CommercialDocument)
class CommercialDocumentAdmin(admin.ModelAdmin):
    change_form_template = "admin/scenarios/commercialdocument/change_form.html"
    list_display = ("reference", "title", "document_type", "status", "scenario_version", "updated_at")
    list_filter = ("document_type", "status", "scenario_version")
    search_fields = ("reference", "title", "exporter_name", "consignee_name")
    inlines = (CommercialDocumentLineInline,)
    fieldsets = (
        ("Document setup", {"fields": (("scenario_version", "document_type", "status"), ("title", "reference", "document_date"))}),
        ("Exporter / seller", {"fields": (("exporter_name", "exporter_contact"), "exporter_address")}),
        ("Consignee / buyer", {"fields": (("consignee_name",), "consignee_address")}),
        ("Shipment details", {"fields": (("currency", "container_reference"), "payment_terms")}),
        ("Invoice totals (not used on packing lists)", {"fields": (("fob", "freight", "insurance"),)}),
        ("Notes", {"fields": ("notes",)}),
    )

    class Media:
        css = {"all": ("admin/css/commercial-document-editor.css",)}
        js = ("admin/js/commercial-document-editor.js",)

    @admin.display(description="Generated training PDF")
    def pdf_preview(self, obj):
        if not obj or not obj.pk:
            return "Save this document to enable its PDF preview."
        return format_html('<a href="{}" target="_blank" rel="noopener">View generated PDF</a>', reverse("commercial-document-pdf", args=[obj.pk]))

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "area")
    list_filter = ("area",)
    prepopulated_fields = {"code": ("title",)}


@admin.register(ScenarioVersion)
class ScenarioVersionAdmin(admin.ModelAdmin):
    list_display = ("scenario", "module", "version", "status", "purpose", "assistance_mode", "reference_status")
    list_filter = ("status", "purpose", "assistance_mode", "reference_status")

    def has_change_permission(self, request, obj=None):
        return not obj or obj.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioState)
class ScenarioStateAdmin(admin.ModelAdmin):
    list_display = ("label", "scenario_version", "order", "is_initial", "is_terminal")
    list_filter = ("scenario_version", "is_initial", "is_terminal")

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioActionDefinition)
class ScenarioActionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("label", "scenario_version", "from_state", "to_state", "order")
    list_filter = ("scenario_version",)

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioDocument)
class ScenarioDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "pdf_layout", "document_type", "reference", "scenario_version", "order")
    list_filter = ("scenario_version", "pdf_layout", "document_type")
    readonly_fields = ("pdf_preview",)
    fieldsets = (
        ("Document identity", {"fields": ("scenario_version", "pdf_layout", "document_type", "title", "reference", "order")}),
        ("Fictitious learner content", {"fields": ("learner_data",), "description": "Enter fictional field/value pairs. For a Bill of Lading use: carrier, bill_of_lading_number, shipper, consignee, notify_party, carrier_agent, booking_reference, shipper_reference, vessel, voyage_number, port_of_loading, port_of_discharge, place_of_receipt, place_of_delivery, freight_terms, container_number, container_type, seal_number, package_count, goods_description, gross_weight, measurement, declared_value, place_and_date_of_issue, and shipped_on_board_date."}),
        ("Hidden evaluation data", {"fields": ("evaluator_data",), "description": "Answer-key data; never printed in the learner PDF."}),
        ("Preview", {"fields": ("pdf_preview",)}),
    )

    @admin.display(description="Generated training PDF")
    def pdf_preview(self, obj):
        if not obj or not obj.pk:
            return "Save this document to enable its PDF preview."
        url = reverse("scenario-document-pdf", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">View generated PDF</a>', url)

    def has_change_permission(self, request, obj=None):
        return not obj or obj.scenario_version.status == ScenarioVersion.Status.DRAFT

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)


@admin.register(ScenarioAttempt)
class ScenarioAttemptAdmin(admin.ModelAdmin):
    list_display = ("enrolment", "scenario_version", "attempt_number", "assistance_mode", "status", "current_state", "last_saved_at")
    list_filter = ("status", "assistance_mode", "scenario_version")
    readonly_fields = [field.name for field in ScenarioAttempt._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScenarioAction)
class ScenarioActionAdmin(admin.ModelAdmin):
    list_display = ("attempt", "sequence", "action_code", "state_before", "state_after", "created_at")
    readonly_fields = [field.name for field in ScenarioAction._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AssistanceEvent)
class AssistanceEventAdmin(admin.ModelAdmin):
    list_display = ("attempt", "kind", "context_code", "created_at")
    readonly_fields = [field.name for field in AssistanceEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
