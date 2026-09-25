from django.contrib import admin
from django import forms
from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html
from django.forms.models import BaseInlineFormSet
import json
import secrets

from .models import AssistanceEvent, BillOfLading, BillOfLadingCargoItem, ConsignmentApplication, CommercialDocument, CommercialDocumentLine, CustomsProcedureCode, CustomsRegime, GhanaHSCode, MdaAgency, MdaApplication, MdaConsignmentRequest, MdaProcess, PortCode, Scenario, ScenarioAction, ScenarioActionDefinition, ScenarioAttempt, ScenarioDocument, ScenarioState, ScenarioVersion, TrainingStakeholder, TrainingStakeholderName, TrainingServiceProvider, UcrDeclaration


@admin.register(GhanaHSCode)
class GhanaHSCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "heading_code", "quantity_unit", "import_duty", "import_vat")
    search_fields = ("code", "description", "heading_code")
    list_filter = ("heading_code",)
    ordering = ("code",)
    readonly_fields = ("source_page",)


class CustomsProcedureCodeAdminForm(forms.ModelForm):
    class Meta:
        model = CustomsProcedureCode
        fields = "__all__"
        widgets = {
            "code": forms.TextInput(attrs={"size": 12}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class CustomsProcedureCodeInline(admin.TabularInline):
    model = CustomsProcedureCode
    form = CustomsProcedureCodeAdminForm
    extra = 1
    fields = ("code", "description", "is_active")


@admin.register(CustomsRegime)
class CustomsRegimeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "cpc_count")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    inlines = (CustomsProcedureCodeInline,)

    class Media:
        css = {"all": ("admin/css/customs-procedure-code.css",)}

    @admin.display(description="CPCs")
    def cpc_count(self, obj):
        return obj.procedure_codes.count()


@admin.register(CustomsProcedureCode)
class CustomsProcedureCodeAdmin(admin.ModelAdmin):
    form = CustomsProcedureCodeAdminForm
    list_display = ("code", "description", "regime", "is_active")
    search_fields = ("code", "description", "regime__code", "regime__name")
    list_filter = ("is_active", "regime")
    autocomplete_fields = ("regime",)

    class Media:
        css = {"all": ("admin/css/customs-procedure-code.css",)}


@admin.register(PortCode)
class PortCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country_code", "country_name", "is_active")
    search_fields = ("code", "name", "country_code", "country_name")
    list_filter = ("is_active", "country_code")
    ordering = ("code",)
    fieldsets = (
        ("Port details", {"fields": (("code", "name"),)}),
        ("Country", {"fields": (("country_code", "country_name"),)}),
        ("Availability", {"fields": ("is_active",)}),
    )


class MdaApplicationInline(admin.TabularInline):
    model = MdaApplication
    extra = 1
    fields = ("code", "name", "is_active")


@admin.register(MdaAgency)
class MdaAgencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "application_count")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    inlines = (MdaApplicationInline,)

    @admin.display(description="Applications")
    def application_count(self, obj):
        return obj.applications.count()


class MdaProcessInline(admin.TabularInline):
    model = MdaProcess
    extra = 1
    fields = ("code", "name", "is_active")


@admin.register(MdaApplication)
class MdaApplicationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "mda", "is_active", "process_count")
    search_fields = ("code", "name", "mda__code", "mda__name")
    list_filter = ("is_active", "mda")
    autocomplete_fields = ("mda",)
    inlines = (MdaProcessInline,)

    @admin.display(description="Processes")
    def process_count(self, obj):
        return obj.processes.count()


@admin.register(MdaProcess)
class MdaProcessAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "application", "is_active")
    search_fields = ("code", "name", "application__code", "application__name", "application__mda__code")
    list_filter = ("is_active", "application__mda")
    autocomplete_fields = ("application",)


@admin.register(MdaConsignmentRequest)
class MdaConsignmentRequestAdmin(admin.ModelAdmin):
    list_display = ("application_no", "student", "mda", "application", "process", "consignment_type", "status", "created_at")
    search_fields = ("application_no", "mda__code", "application__code", "process__code", "consignment_application__ucr__ucr_no", "consignment_application__owner__student_id", "consignment_application__owner__first_name", "consignment_application__owner__last_name")
    list_filter = ("status", "consignment_type", "mda")
    readonly_fields = ("application_no", "created_at")
    autocomplete_fields = ("mda", "application", "process")
    raw_id_fields = ("consignment_application",)

    @admin.display(description="Student", ordering="consignment_application__owner__student_id")
    def student(self, obj):
        owner = obj.consignment_application.owner
        return f"{owner.get_full_name() or owner.username} ({owner.student_id or 'no ID'})"


@admin.register(UcrDeclaration)
class UcrDeclarationAdmin(admin.ModelAdmin):
    """Every learner's UCRs with their owner, so administrators can trace student work."""

    list_display = ("ucr_no", "temp_no", "student", "regime", "status", "created_at", "submitted_at")
    search_fields = ("ucr_no", "temp_no", "owner__student_id", "owner__first_name", "owner__last_name", "owner__username", "exporter_name", "importer_name")
    list_filter = ("status", "regime", "derivation")
    readonly_fields = ("temp_no", "ucr_no", "owner", "status", "created_at", "updated_at", "submitted_at")

    @admin.display(description="Student", ordering="owner__student_id")
    def student(self, obj):
        return f"{obj.owner.get_full_name() or obj.owner.username} ({obj.owner.student_id or 'no ID'})"


@admin.register(ConsignmentApplication)
class ConsignmentApplicationAdmin(admin.ModelAdmin):
    """Every learner's consignment applications with their owner."""

    list_display = ("application_no", "student", "ucr", "status", "created_at", "submitted_at")
    search_fields = ("application_no", "owner__student_id", "owner__first_name", "owner__last_name", "owner__username", "exporter_name", "importer_code")
    list_filter = ("status",)
    readonly_fields = ("application_no", "owner", "status", "created_at", "submitted_at")

    @admin.display(description="Student", ordering="owner__student_id")
    def student(self, obj):
        return f"{obj.owner.get_full_name() or obj.owner.username} ({obj.owner.student_id or 'no ID'})"


def declarant_capable_stakeholders():
    """Active stakeholders whose own or additional names carry the CHA / Declarant or Freight Forwarder role.

    Filtered in Python because JSONField's contains lookup is unsupported on SQLite.
    """
    declarant_roles = {"cha", "freight_forwarder"}
    qualifying = [
        stakeholder.pk
        for stakeholder in TrainingStakeholder.objects.filter(is_active=True).prefetch_related("additional_names")
        if declarant_roles.intersection(stakeholder.roles)
        or any(declarant_roles.intersection(alias.roles) for alias in stakeholder.additional_names.all())
    ]
    return TrainingStakeholder.objects.filter(pk__in=qualifying)


class StakeholderTinChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.code} · {obj.name}"


class TrainingServiceProviderForm(forms.ModelForm):
    stakeholder = StakeholderTinChoiceField(
        queryset=TrainingStakeholder.objects.none(),
        label="TIN",
        help_text="Select a registered stakeholder whose roles include CHA / Declarant or Freight Forwarder.",
    )

    class Meta:
        model = TrainingServiceProvider
        fields = ("declarant_prefix", "stakeholder", "name", "country_code", "address", "contact_name", "contact_designation", "phone", "email", "email_2", "is_active", "owner")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stakeholder"].queryset = declarant_capable_stakeholders()
        if self.instance and self.instance.pk:
            self.initial["stakeholder"] = TrainingStakeholder.objects.filter(code=self.instance.code).first()

    def clean(self):
        cleaned = super().clean()
        stakeholder = cleaned.get("stakeholder")
        if stakeholder:
            self.instance.code = stakeholder.code
            duplicate = TrainingServiceProvider.objects.filter(code__iexact=stakeholder.code)
            if self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            owner = cleaned.get("owner")
            duplicate = duplicate.filter(owner=owner) if owner else duplicate.filter(owner__isnull=True)
            if duplicate.exists():
                self.add_error("stakeholder", "A service provider for this TIN and assignment already exists.")
        return cleaned


@admin.register(TrainingServiceProvider)
class TrainingServiceProviderAdmin(admin.ModelAdmin):
    form = TrainingServiceProviderForm
    change_form_template = "admin/scenarios/trainingserviceprovider/change_form.html"
    list_display = ("declarant_code", "code", "name", "country_code", "owner", "is_active")
    list_filter = ("is_active", "country_code")
    search_fields = ("declarant_code", "code", "name", "owner__username", "owner__student_id")
    readonly_fields = ("declarant_code",)
    fields = ("declarant_prefix", "declarant_code", "stakeholder", "name", "country_code", "address", "contact_name", "contact_designation", "phone", "email", "email_2", "is_active", "owner")

    class Media:
        css = {"all": ("admin/css/training-service-provider.css",)}
        js = ("js/dialog-pagination.js", "admin/js/training-service-provider.js", "js/ucr-country-codes.js")

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        form = context["adminform"].form
        context["stakeholder_json"] = json.dumps({
            str(stakeholder.pk): {"name": stakeholder.name, "address": stakeholder.address}
            for stakeholder in form.fields["stakeholder"].queryset
        })
        return super().render_change_form(request, context, add=add, change=change, form_url=form_url, obj=obj)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields + (("declarant_prefix",) if obj else ())


class TrainingStakeholderForm(forms.ModelForm):
    generation_mode = forms.ChoiceField(choices=(("manual", "Enter code manually"), ("auto", "Generate code automatically")), initial="manual", help_text="Choose how this TIN or NID is assigned.")
    code = forms.CharField(required=False, max_length=13, label="TIN / NID code")
    roles = forms.MultipleChoiceField(choices=TrainingStakeholder.ROLE_CHOICES, widget=forms.CheckboxSelectMultiple, required=True)

    class Meta:
        model = TrainingStakeholder
        fields = ("tin_type", "code", "name", "address", "roles", "is_active", "merged_into")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].initial = self.instance.roles if self.instance.pk else []
        self.fields["merged_into"].queryset = TrainingStakeholder.objects.filter(merged_into__isnull=True, is_active=True).exclude(pk=self.instance.pk)

    def clean(self):
        cleaned = super().clean()
        tin_type = cleaned.get("tin_type")
        code = (cleaned.get("code") or "").strip().upper()
        if cleaned.get("generation_mode") == "auto":
            width = 10 if tin_type == TrainingStakeholder.TinType.NID else 8
            for _ in range(20):
                candidate = f"{tin_type}{secrets.randbelow(10 ** width):0{width}d}"
                if not TrainingStakeholder.objects.filter(code=candidate).exists():
                    code = candidate
                    break
            else:
                raise forms.ValidationError("Could not generate an unused code. Please try again.")
        elif not code:
            self.add_error("code", "Enter a TIN / NID or choose automatic generation.")
        cleaned["code"] = code
        return cleaned


class TrainingStakeholderNameForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(choices=TrainingStakeholder.ROLE_CHOICES, widget=forms.CheckboxSelectMultiple, required=False)

    class Meta:
        model = TrainingStakeholderName
        fields = ("name", "address", "roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].initial = self.instance.roles if self.instance.pk else []

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("name") and not cleaned.get("roles") and not cleaned.get("DELETE"):
            self.add_error("roles", "Choose at least one role for this name.")
        return cleaned


class TrainingStakeholderNameFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = {self.instance.name.strip().casefold(): set(self.instance.roles)} if self.instance.name else {}
        for form in self.forms:
            cleaned = form.cleaned_data
            if not cleaned or cleaned.get("DELETE") or not cleaned.get("name"):
                continue
            key = cleaned["name"].strip().casefold()
            roles = set(cleaned.get("roles") or [])
            if seen.get(key, set()) & roles:
                form.add_error("name", "This name already has one or more of the selected roles under this TIN.")
            seen.setdefault(key, set()).update(roles)


class TrainingStakeholderNameInline(admin.TabularInline):
    model = TrainingStakeholderName
    form = TrainingStakeholderNameForm
    formset = TrainingStakeholderNameFormSet
    extra = 1
    verbose_name = "Additional name"
    verbose_name_plural = "Additional names (one primary name is required above)"


@admin.register(TrainingStakeholder)
class TrainingStakeholderAdmin(admin.ModelAdmin):
    form = TrainingStakeholderForm
    inlines = (TrainingStakeholderNameInline,)
    list_display = ("code", "name", "tin_type", "stakeholder_roles", "merged_into", "is_active")
    list_filter = ("tin_type", "is_active")
    search_fields = ("code", "name", "description", "additional_names__name")
    fieldsets = (
        ("TIN / NID setup", {"fields": ("tin_type", "generation_mode", "code")}),
        ("Primary name (required)", {"fields": ("name", "address", "roles")}),
        ("Advanced", {"classes": ("collapse",), "fields": ("is_active", "merged_into")}),
    )
    autocomplete_fields = ("merged_into",)

    class Media:
        js = ("admin/js/training-stakeholder.js",)

    @admin.display(description="Roles")
    def stakeholder_roles(self, obj):
        labels = dict(TrainingStakeholder.ROLE_CHOICES)
        return ", ".join(labels.get(role, role) for role in obj.roles)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        if obj.merged_into_id:
            target = obj.merged_into
            def copy_distinct_roles(name, address, roles):
                used = set(target.roles) if name.casefold() == target.name.casefold() else set()
                for existing in target.additional_names.filter(name__iexact=name):
                    used.update(existing.roles)
                remaining = [role for role in roles if role not in used]
                if remaining:
                    TrainingStakeholderName.objects.create(stakeholder=target, name=name, address=address, roles=remaining)

            copy_distinct_roles(obj.name, obj.address, obj.roles)
            for alias in obj.additional_names.all():
                copy_distinct_roles(alias.name, alias.address, alias.roles)
            obj.is_active = False
            obj.save(update_fields=("is_active",))
            self.message_user(request, f"{obj.code} now resolves to {target.code}. The surviving TIN's details take precedence.", messages.SUCCESS)


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
