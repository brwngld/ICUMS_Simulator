import uuid
import re
import secrets
from django.conf import settings

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from .country_codes import COUNTRY_CODE_SET


class TrainingStakeholder(models.Model):
    """Fictional stakeholder available to the UCR TIN/NID lookup."""

    class TinType(models.TextChoices):
        INDIVIDUAL = "P00", "Individual / sole proprietor (P00)"
        COMPANY = "C00", "Company / partnership (C00)"
        GOVERNMENT = "G00", "Government agency (G00)"
        FOREIGN_MISSION = "Q00", "Foreign mission (Q00)"
        INSTITUTION = "V00", "Public institution / trust / co-operative (V00)"
        NID = "GHA", "National ID (GHA)"

    ROLE_CHOICES = (
        ("importer", "Importer"), ("exporter", "Exporter"),
        ("cha", "CHA / Declarant"), ("freight_forwarder", "Freight Forwarder"),
        ("other", "Other"),
    )

    tin_type = models.CharField(max_length=3, choices=TinType.choices, default=TinType.COMPANY)
    code = models.CharField(max_length=13, unique=True, blank=True, help_text="11-character TIN or 13-character GHA NID.")
    name = models.CharField(max_length=180)
    description = models.CharField(max_length=180, blank=True)
    address = models.TextField(blank=True)
    roles = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="merged_codes", help_text="Optional: this code resolves to the selected surviving TIN. The survivor's details take precedence.")

    class Meta:
        ordering = ("code", "name")
        constraints = [models.UniqueConstraint(Lower("code"), name="unique_training_tin_case_insensitive")]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        suffix_length = 10 if self.tin_type == self.TinType.NID else 8
        if not re.fullmatch(re.escape(self.tin_type) + rf"[A-Z0-9]{{{suffix_length}}}", self.code):
            raise ValidationError({"code": "Enter an 11-character TIN beginning P00, C00, G00, Q00 or V00, or a 13-character GHA NID."})
        self.name = self.name.strip()
        if self.pk:
            for alias in self.additional_names.filter(name__iexact=self.name):
                if set(alias.roles) & set(self.roles):
                    raise ValidationError({"name": "This name already has one or more of the selected roles under this TIN."})
        if self.merged_into_id:
            if self.pk == self.merged_into_id:
                raise ValidationError({"merged_into": "A TIN cannot merge into itself."})
            if self.merged_into.merged_into_id:
                raise ValidationError({"merged_into": "Choose the surviving TIN, not another merged code."})
            if self.pk and self.merged_into.merged_into_id == self.pk:
                raise ValidationError({"merged_into": "This would create a merge cycle."})
        allowed_roles = {key for key, _ in self.ROLE_CHOICES}
        if not isinstance(self.roles, list) or any(role not in allowed_roles for role in self.roles):
            raise ValidationError({"roles": "Select one or more listed stakeholder roles."})

    def __str__(self):
        return f"{self.code} · {self.name}"


class TrainingStakeholderName(models.Model):
    stakeholder = models.ForeignKey(TrainingStakeholder, on_delete=models.CASCADE, related_name="additional_names")
    name = models.CharField(max_length=180)
    address = models.TextField(blank=True)
    roles = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if self.stakeholder_id:
            if self.stakeholder.name.strip().casefold() == self.name.casefold() and set(self.stakeholder.roles) & set(self.roles):
                raise ValidationError({"name": "This name already has one or more of the selected roles under this TIN."})
            for alias in TrainingStakeholderName.objects.filter(stakeholder_id=self.stakeholder_id, name__iexact=self.name).exclude(pk=self.pk):
                if set(alias.roles) & set(self.roles):
                    raise ValidationError({"name": "This name already has one or more of the selected roles under this TIN."})
        allowed_roles = {key for key, _ in TrainingStakeholder.ROLE_CHOICES}
        if not isinstance(self.roles, list) or any(role not in allowed_roles for role in self.roles):
            raise ValidationError({"roles": "Select one or more listed stakeholder roles."})


class TrainingServiceProvider(models.Model):
    """Fictitious declarant details; a null owner denotes a shared administrator record."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="training_service_providers", verbose_name="Assigned to", help_text="Choose a student or your own account. Leave blank to make this record available to everyone in the training simulator.")
    declarant_prefix = models.CharField(max_length=2, default="CH", help_text="Two letters used when generating the declarant code, e.g. CH.")
    declarant_code = models.CharField(max_length=8, unique=True, blank=True, editable=False)
    code = models.CharField(max_length=13, help_text="The service provider's 11-character TIN or 13-character NID, not the declarant code.")
    name = models.CharField(max_length=180)
    country_code = models.CharField(max_length=2, default="GH")
    address = models.TextField()
    contact_name = models.CharField(max_length=180, blank=True)
    contact_designation = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    email_2 = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("declarant_code", "name")
        constraints = [
            models.UniqueConstraint(Lower("code"), "owner", condition=Q(owner__isnull=False), name="unique_training_provider_per_owner"),
            models.UniqueConstraint(Lower("code"), condition=Q(owner__isnull=True), name="unique_admin_training_provider_code"),
        ]

    def clean(self):
        super().clean()
        self.code = self.code.strip().upper()
        self.declarant_prefix = self.declarant_prefix.strip().upper()
        self.country_code = self.country_code.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", self.declarant_prefix):
            raise ValidationError({"declarant_prefix": "Enter exactly two letters."})
        if not re.fullmatch(r"(?:P00|C00|G00|Q00|V00)[A-Z0-9]{8}|GHA[A-Z0-9]{10}", self.code):
            raise ValidationError({"code": "Enter a valid 11-character TIN or 13-character GHA NID."})
        if len(self.country_code) != 2 or self.country_code not in COUNTRY_CODE_SET:
            raise ValidationError({"country_code": "Enter a known two-letter country code, or use the search button to pick one."})

    def __str__(self):
        return f"{self.declarant_code} · {self.code}, {self.name}"

    def save(self, *args, **kwargs):
        if not self.declarant_code:
            prefix = self.declarant_prefix.strip().upper()
            for _ in range(100):
                candidate = f"{prefix}{secrets.randbelow(1000000):06d}"
                if not type(self).objects.filter(declarant_code=candidate).exists():
                    self.declarant_code = candidate
                    break
            else:
                raise ValidationError("Could not allocate a unique declarant code. Please try again.")
        super().save(*args, **kwargs)

from onboarding.models import Enrolment
from learning.models import Module


class Scenario(models.Model):
    class Area(models.TextChoices):
        IMPORT = "import", "Import"
        EXPORT = "export", "Export"
        TRANSIT = "transit", "Transit"
        WAREHOUSE = "warehouse", "Warehouse"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=180)
    area = models.CharField(max_length=16, choices=Area.choices)

    def __str__(self):
        return self.title


class ScenarioVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    class AssistanceMode(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        COMPETENCY = "competency", "Competency assessment"

    class ReferenceStatus(models.TextChoices):
        CONCEPTUAL = "conceptual", "Conceptual placeholder"
        VERIFIED = "verified", "Reference verified"
        ADAPTED = "adapted", "Deliberately adapted"
        TBC = "tbc", "To be confirmed"

    class Purpose(models.TextChoices):
        PRACTICE = "practice", "Practice"
        MODULE_ASSESSMENT = "module_assessment", "Practical module assessment"
        COMPETENCY = "competency", "Practical competency assessment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="versions")
    module = models.ForeignKey(Module, blank=True, null=True, on_delete=models.PROTECT, related_name="guided_practicals")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    assistance_mode = models.CharField(max_length=16, choices=AssistanceMode.choices, default=AssistanceMode.BEGINNER)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.PRACTICE)
    maximum_attempts = models.PositiveIntegerField(blank=True, null=True, help_text="Leave blank for unlimited attempts.")
    reference_status = models.CharField(max_length=16, choices=ReferenceStatus.choices, default=ReferenceStatus.CONCEPTUAL)
    briefing = models.TextField()
    learning_objective = models.TextField()
    initial_data = models.JSONField(default=dict, blank=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("scenario", "version"), name="unique_scenario_version")]
        ordering = ("scenario__title", "version")

    def __str__(self):
        return f"{self.scenario.title} v{self.version}"

    def clean(self):
        super().clean()
        if not isinstance(self.initial_data, dict):
            raise ValidationError({"initial_data": "Initial data must be a JSON object."})
        if self.purpose == self.Purpose.COMPETENCY and self.assistance_mode != self.AssistanceMode.COMPETENCY:
            raise ValidationError({"assistance_mode": "A competency assessment must use Competency assistance mode."})


class ScenarioState(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="states")
    key = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    guidance = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    is_initial = models.BooleanField(default=False)
    is_terminal = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "label")
        constraints = [
            models.UniqueConstraint(fields=("scenario_version", "key"), name="unique_scenario_state_key"),
            models.UniqueConstraint(fields=("scenario_version",), condition=models.Q(is_initial=True), name="one_initial_state_per_scenario_version"),
        ]

    def __str__(self):
        return self.label


class ScenarioActionDefinition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="action_definitions")
    code = models.SlugField(max_length=80)
    label = models.CharField(max_length=180)
    from_state = models.ForeignKey(ScenarioState, blank=True, null=True, on_delete=models.CASCADE, related_name="outgoing_actions")
    to_state = models.ForeignKey(ScenarioState, blank=True, null=True, on_delete=models.PROTECT, related_name="incoming_actions")
    conditions = models.JSONField(default=dict, blank=True, help_text="Required state-data key/value pairs.")
    effects = models.JSONField(default=dict, blank=True, help_text="State-data key/value pairs applied after the action.")
    success_feedback = models.TextField(blank=True)
    beginner_hint = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "label")
        constraints = [models.UniqueConstraint(fields=("scenario_version", "code"), name="unique_scenario_action_code")]

    def clean(self):
        super().clean()
        for field_name in ("from_state", "to_state"):
            state = getattr(self, field_name)
            if state and state.scenario_version_id != self.scenario_version_id:
                raise ValidationError({field_name: "The state must belong to this scenario version."})
        if not isinstance(self.conditions, dict):
            raise ValidationError({"conditions": "Conditions must be a JSON object."})
        if not isinstance(self.effects, dict):
            raise ValidationError({"effects": "Effects must be a JSON object."})

    def __str__(self):
        return self.label


class ScenarioDocument(models.Model):
    class PdfLayout(models.TextChoices):
        GENERIC = "generic", "General customs document"
        BILL_OF_LADING = "bill_of_lading", "Bill of Lading"
        COMMERCIAL_INVOICE = "commercial_invoice", "Commercial Invoice"
        PACKING_LIST = "packing_list", "Packing List"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80)
    title = models.CharField(max_length=180)
    reference = models.CharField(max_length=100, blank=True)
    pdf_layout = models.CharField(max_length=24, choices=PdfLayout.choices, default=PdfLayout.GENERIC)
    learner_data = models.JSONField(default=dict, blank=True)
    evaluator_data = models.JSONField(default=dict, blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "title")

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if not isinstance(self.learner_data, dict):
            raise ValidationError({"learner_data": "Learner data must be a JSON object."})
        if not isinstance(self.evaluator_data, dict):
            raise ValidationError({"evaluator_data": "Evaluator data must be a JSON object."})


class BillOfLading(models.Model):
    class Template(models.TextChoices):
        CARRIER_GRID = "carrier_grid", "Carrier Grid BL"
        OCEAN_TRANSPORT = "ocean_transport", "Ocean Transport BL"
        MULTIMODAL = "multimodal", "Multimodal BL"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="bills_of_lading")
    title = models.CharField(max_length=180, default="Fictitious Bill of Lading")
    reference = models.CharField(max_length=100, unique=True)
    template = models.CharField(max_length=24, choices=Template.choices, default=Template.CARRIER_GRID)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    carrier = models.CharField(max_length=180)
    carrier_agent = models.TextField(blank=True)
    shipper = models.TextField()
    consignee = models.TextField()
    notify_party = models.TextField(blank=True)
    booking_reference = models.CharField(max_length=100, blank=True)
    shipper_reference = models.CharField(max_length=100, blank=True)
    original_status = models.CharField(max_length=80, default="Non-negotiable training copy")
    number_of_originals = models.PositiveSmallIntegerField(default=0)
    vessel = models.CharField(max_length=180)
    voyage_number = models.CharField(max_length=80)
    place_of_receipt = models.CharField(max_length=180, blank=True)
    port_of_loading = models.CharField(max_length=180)
    port_of_discharge = models.CharField(max_length=180)
    place_of_delivery = models.CharField(max_length=180, blank=True)
    freight_terms = models.CharField(max_length=180, blank=True)
    shippers_declared_value = models.CharField(max_length=100, blank=True, help_text="Optional BL declaration; this is not the commercial invoice total.")
    place_of_issue = models.CharField(max_length=180, blank=True)
    date_of_issue = models.DateField(blank=True, null=True)
    shipped_on_board_date = models.DateField(blank=True, null=True)
    additional_declarations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "title")
        verbose_name = "Bill of Lading"
        verbose_name_plural = "Bills of Lading"

    def __str__(self):
        return f"{self.reference} - {self.title}"


class BillOfLadingCargoItem(models.Model):
    class CargoType(models.TextChoices):
        VEHICLE = "vehicle", "Vehicle"
        GENERAL = "general", "General merchandise"
        PERSONAL_EFFECTS = "personal_effects", "Household or personal effects"
        MACHINERY = "machinery", "Machinery"
        OTHER = "other", "Other cargo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bill_of_lading = models.ForeignKey(BillOfLading, on_delete=models.CASCADE, related_name="cargo_items")
    order = models.PositiveIntegerField(default=1)
    cargo_type = models.CharField(max_length=24, choices=CargoType.choices, default=CargoType.GENERAL)
    container_number = models.CharField(max_length=30)
    seal_number = models.CharField(max_length=30, blank=True)
    container_type = models.CharField(max_length=80, blank=True)
    marks_and_numbers = models.TextField(blank=True)
    package_quantity = models.PositiveIntegerField(default=1)
    package_type = models.CharField(max_length=80, default="package")
    goods_description = models.TextField(blank=True)
    vehicle_year = models.PositiveSmallIntegerField("Year of manufacture", blank=True, null=True)
    vehicle_make = models.CharField("Make or manufacturer", max_length=80, blank=True)
    vehicle_model = models.CharField("Model", max_length=100, blank=True)
    vin_or_chassis = models.CharField("VIN, chassis or serial number", max_length=80, blank=True)
    hs_code = models.CharField(max_length=24, blank=True)
    gross_weight = models.DecimalField(max_digits=12, decimal_places=3)
    weight_unit = models.CharField(max_length=12, default="KGM")
    measurement = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    measurement_unit = models.CharField(max_length=12, default="MTQ")

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return f"{self.container_number}: {self.goods_description[:60]}"

    def clean(self):
        super().clean()
        if self.cargo_type == self.CargoType.VEHICLE:
            missing = [name for name in ("vehicle_year", "vehicle_make", "vehicle_model", "vin_or_chassis") if not getattr(self, name)]
            if missing:
                raise ValidationError({name: "This vehicle detail is required." for name in missing})
        elif self.cargo_type in (self.CargoType.GENERAL, self.CargoType.PERSONAL_EFFECTS, self.CargoType.MACHINERY, self.CargoType.OTHER) and not self.goods_description.strip():
            raise ValidationError({"goods_description": "Describe this cargo item."})


class CommercialDocument(models.Model):
    class DocumentType(models.TextChoices):
        INVOICE = "invoice", "Commercial invoice"
        PROFORMA_INVOICE = "proforma_invoice", "Proforma invoice"
        PACKING_LIST = "packing_list", "Packing list"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="commercial_documents")
    document_type = models.CharField(max_length=16, choices=DocumentType.choices, default=DocumentType.INVOICE)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    title = models.CharField(max_length=180, default="Fictitious commercial document")
    reference = models.CharField(max_length=100, unique=True)
    document_date = models.DateField(blank=True, null=True)
    exporter_name = models.CharField(max_length=180)
    exporter_address = models.TextField(blank=True)
    exporter_contact = models.CharField(max_length=180, blank=True)
    consignee_name = models.CharField(max_length=180)
    consignee_address = models.TextField(blank=True)
    currency = models.CharField(max_length=8, default="USD")
    container_reference = models.CharField(max_length=180, blank=True)
    payment_terms = models.CharField(max_length=180, blank=True)
    fob = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    freight = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    insurance = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at", "title")

    def __str__(self):
        return f"{self.reference} - {self.title}"

    def clean(self):
        super().clean()
        if self.document_type == self.DocumentType.PACKING_LIST:
            for name in ("fob", "freight", "insurance"):
                if getattr(self, name) not in (None, ""):
                    raise ValidationError({name: "Packing lists do not contain commercial totals."})


class CommercialDocumentLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(CommercialDocument, on_delete=models.CASCADE, related_name="line_items")
    order = models.PositiveIntegerField(default=1)
    description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    quantity_unit = models.CharField(max_length=32, default="pcs")
    package_count = models.PositiveIntegerField(blank=True, null=True)
    pieces_per_package = models.CharField(max_length=80, blank=True)
    net_weight = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    gross_weight = models.DecimalField(max_digits=12, decimal_places=3, blank=True, null=True)
    weight_unit = models.CharField(max_length=12, default="KGM")
    dimensions = models.CharField(max_length=120, blank=True)
    hs_code = models.CharField(max_length=24, blank=True)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)

    class Meta:
        ordering = ("order", "id")

    def __str__(self):
        return self.description[:80]

    def clean(self):
        super().clean()
        if self.document and self.document.document_type == CommercialDocument.DocumentType.PACKING_LIST and (self.unit_price is not None or self.amount is not None):
            raise ValidationError({"unit_price": "Packing lists do not contain prices."})


class ScenarioAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABANDONED = "abandoned", "Abandoned"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.PROTECT, related_name="scenario_attempts")
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.PROTECT, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    assistance_mode = models.CharField(max_length=16, choices=ScenarioVersion.AssistanceMode.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    current_state = models.ForeignKey(ScenarioState, on_delete=models.PROTECT, related_name="attempts")
    state_data = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    last_saved_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-started_at",)
        constraints = [models.UniqueConstraint(fields=("enrolment", "scenario_version", "attempt_number"), name="unique_scenario_attempt_number")]


class ScenarioAction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(ScenarioAttempt, on_delete=models.CASCADE, related_name="actions")
    sequence = models.PositiveIntegerField()
    action_definition = models.ForeignKey(ScenarioActionDefinition, on_delete=models.PROTECT, related_name="recorded_actions")
    action_code = models.CharField(max_length=80)
    state_before = models.CharField(max_length=80)
    state_after = models.CharField(max_length=80)
    input_data = models.JSONField(default=dict, blank=True)
    outcome_code = models.CharField(max_length=40, default="success")
    feedback_shown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sequence",)
        constraints = [models.UniqueConstraint(fields=("attempt", "sequence"), name="unique_scenario_action_sequence")]


class UcrDeclaration(models.Model):
    """Learner-authored UCR practice record; Save stores a draft (TEMPUCR…), Submit issues the final number."""

    TEMP_PREFIX = "TEMPUCR"
    UCR_PREFIX = "KGHTESTUCR"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ucr_declarations")
    source_ucr = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="derived_ucrs")
    derivation = models.CharField(max_length=8, blank=True, choices=(("clone", "Clone"), ("amend", "Amendment")))
    temp_no = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    ucr_no = models.CharField(max_length=20, blank=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    regime = models.CharField(max_length=2)
    show_provider = models.BooleanField(default=True)

    declarant_code = models.CharField(max_length=8, blank=True)
    provider_code = models.CharField(max_length=13, blank=True)
    provider_name = models.CharField(max_length=180, blank=True)
    provider_country = models.CharField(max_length=2, blank=True)
    provider_address = models.TextField(blank=True)
    provider_contact = models.CharField(max_length=180, blank=True)
    provider_phone = models.CharField(max_length=40, blank=True)
    provider_email = models.EmailField(blank=True)
    provider_email_2 = models.EmailField(blank=True)

    exporter_identity = models.CharField(max_length=13, blank=True)
    exporter_name = models.CharField(max_length=180, blank=True)
    exporter_country = models.CharField(max_length=2, blank=True)
    exporter_address = models.TextField(blank=True)
    exporter_phone = models.CharField(max_length=40, blank=True)
    exporter_fax = models.CharField(max_length=40, blank=True)
    exporter_contact = models.CharField(max_length=180, blank=True)
    exporter_contact_no = models.CharField(max_length=40, blank=True)
    exporter_designation = models.CharField(max_length=100, blank=True)

    importer_identity = models.CharField(max_length=180, blank=True)
    importer_name = models.CharField(max_length=180, blank=True)
    importer_country = models.CharField(max_length=2, blank=True)
    importer_address = models.TextField(blank=True)
    importer_phone = models.CharField(max_length=40, blank=True)
    importer_fax = models.CharField(max_length=40, blank=True)
    importer_contact = models.CharField(max_length=180, blank=True)
    importer_contact_no = models.CharField(max_length=40, blank=True)
    importer_designation = models.CharField(max_length=100, blank=True)

    goods_description = models.TextField(blank=True)
    origin_country = models.CharField(max_length=2, blank=True)
    destination_country = models.CharField(max_length=2, blank=True)
    transport_mode = models.CharField(max_length=40, blank=True)
    user_reference = models.CharField(max_length=100, blank=True)
    ucr_email = models.TextField(blank=True)
    documents = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [models.UniqueConstraint(fields=("ucr_no",), condition=Q(ucr_no__gt=""), name="unique_ucr_number_when_issued")]

    def __str__(self):
        return self.ucr_no or self.temp_no or f"UCR draft ({self.regime})"


class UcrDocumentAttachment(models.Model):
    ucr = models.ForeignKey(UcrDeclaration, on_delete=models.CASCADE, related_name="attachments")
    row_index = models.PositiveSmallIntegerField()
    file = models.FileField(upload_to="ucr_attachments/%Y/%m/")
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("row_index", "pk")


def purge_expired_ucr_drafts(max_age_days=7):
    """Delete TEMPUCR drafts that were never submitted within the retention window."""
    from datetime import timedelta

    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=max_age_days)
    deleted, _ = UcrDeclaration.objects.filter(status=UcrDeclaration.Status.DRAFT, updated_at__lt=cutoff).delete()
    return deleted


def allocate_ucr_number(prefix):
    """prefix + two-digit year + a 7-digit sequence, e.g. KGHTESTUCR260000001 then ...000002."""
    from django.db import transaction
    from django.utils import timezone

    year = timezone.localtime().strftime("%y")
    stem = f"{prefix}{year}"
    for _ in range(3):
        with transaction.atomic():
            issued = []
            for temp_no, ucr_no in UcrDeclaration.objects.filter(
                Q(temp_no__startswith=stem) | Q(ucr_no__startswith=stem)
            ).values_list("temp_no", "ucr_no"):
                issued.extend(number for number in (temp_no, ucr_no) if number.startswith(stem))
            sequences = [int(number[len(stem):]) for number in issued if number[len(stem):].isdigit()]
            candidate = f"{stem}{(max(sequences) + 1) if sequences else 1:07d}"
            if not UcrDeclaration.objects.filter(Q(temp_no=candidate) | Q(ucr_no=candidate)).exists():
                return candidate
    raise ValidationError("Could not allocate the next reference number. Please try again.")



class GhanaHSCode(models.Model):
    """Customs-approved Ghana HS tariff code imported from the supplied reference list."""

    code = models.CharField(max_length=10, unique=True, db_index=True)
    description = models.TextField()
    heading_code = models.CharField(max_length=4, blank=True, db_index=True)
    quantity_unit = models.CharField(max_length=120, blank=True)
    import_duty = models.CharField(max_length=24, blank=True)
    import_vat = models.CharField(max_length=24, blank=True)
    import_excise = models.CharField(max_length=24, blank=True)
    export_duty = models.CharField(max_length=24, blank=True)
    nhil_rate = models.CharField(max_length=24, blank=True)
    source_page = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "Ghana HS code"
        verbose_name_plural = "Ghana HS codes"

    def __str__(self):
        return f"{self.code} - {self.description}"


class CustomsRegime(models.Model):
    """Admin-managed customs regime used by BOE declaration lookups."""

    code = models.CharField(max_length=2, unique=True)
    name = models.CharField(max_length=240)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def clean(self):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}, {self.name}"


class CustomsProcedureCode(models.Model):
    """CPC linked to the customs regime under which it can be selected."""

    regime = models.ForeignKey(CustomsRegime, on_delete=models.CASCADE, related_name="procedure_codes")
    code = models.CharField(max_length=12, unique=True)
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def clean(self):
        self.code = self.code.strip().upper()
        self.description = self.description.strip()
        if self.regime_id and not self.code.startswith(self.regime.code):
            raise ValidationError({"code": "The CPC must start with its linked regime code."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.description}"


class PortCode(models.Model):
    """Admin-maintained port/city code used by the transport lookup."""

    code = models.CharField(max_length=12, unique=True, db_index=True)
    name = models.CharField(max_length=180, db_index=True)
    country_code = models.CharField(max_length=2, blank=True, db_index=True)
    country_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "Port code"
        verbose_name_plural = "Port codes"

    def clean(self):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()
        self.country_code = self.country_code.strip().upper()
        self.country_name = self.country_name.strip()
        if self.country_code and self.country_code not in COUNTRY_CODE_SET:
            raise ValidationError({"country_code": "Enter a valid two-letter country code."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.name}"


class MdaAgency(models.Model):
    """Regulatory agency available from the Confirmation application launcher."""

    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=180)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)
        verbose_name = "MDA"
        verbose_name_plural = "MDAs"

    def clean(self):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code}, {self.name}"


class MdaApplication(models.Model):
    """An application offered by one MDA; its processes are configured separately."""

    mda = models.ForeignKey(MdaAgency, on_delete=models.CASCADE, related_name="applications")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=180)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("mda__code", "code")
        constraints = [models.UniqueConstraint(fields=("mda", "code"), name="unique_application_code_per_mda")]

    def clean(self):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mda.code} · {self.code}, {self.name}"


class MdaProcess(models.Model):
    """One of the processes available for an MDA application."""

    application = models.ForeignKey(MdaApplication, on_delete=models.CASCADE, related_name="processes")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=180)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("application__mda__code", "application__code", "code")
        constraints = [models.UniqueConstraint(fields=("application", "code"), name="unique_process_code_per_mda_application")]

    def clean(self):
        self.code = self.code.strip().upper()
        self.name = self.name.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.application} · {self.code}, {self.name}"


class ConsignmentApplication(models.Model):
    """Consignment Document application built on top of an issued UCR; five tabs, one sequence number."""

    APPLICATION_PREFIX = "CD"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consignment_applications")
    ucr = models.ForeignKey(UcrDeclaration, on_delete=models.PROTECT, related_name="applications")
    application_no = models.CharField(max_length=24, blank=True, editable=False)
    version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    reference_info = models.TextField(blank=True)

    exporter_name = models.CharField(max_length=180, blank=True)
    exporter_physical_country = models.CharField(max_length=2, blank=True)
    exporter_physical_address = models.TextField(blank=True)
    exporter_postal_country = models.CharField(max_length=2, blank=True)
    exporter_tel = models.CharField(max_length=40, blank=True)
    exporter_fax = models.CharField(max_length=40, blank=True)
    exporter_email = models.EmailField(blank=True)
    exporter_postal_address = models.TextField(blank=True)
    exporter_mda_ref = models.CharField(max_length=60, blank=True)
    exporter_sector = models.CharField(max_length=80, blank=True)
    exporter_warehouse = models.CharField(max_length=180, blank=True)

    consignor_same = models.BooleanField(default=False)
    consignor_name = models.CharField(max_length=180, blank=True)
    consignor_physical_country = models.CharField(max_length=2, blank=True)
    consignor_physical_address = models.TextField(blank=True)
    consignor_postal_country = models.CharField(max_length=2, blank=True)
    consignor_tel = models.CharField(max_length=40, blank=True)
    consignor_fax = models.CharField(max_length=40, blank=True)
    consignor_email = models.EmailField(blank=True)
    consignor_postal_address = models.TextField(blank=True)
    consignor_mda_ref = models.CharField(max_length=60, blank=True)
    consignor_sector = models.CharField(max_length=80, blank=True)
    consignor_warehouse = models.CharField(max_length=180, blank=True)

    importer_code = models.CharField(max_length=180, blank=True)
    importer_physical_country = models.CharField(max_length=2, blank=True)
    importer_physical_address = models.TextField(blank=True)
    importer_postal_country = models.CharField(max_length=2, blank=True)
    importer_tel = models.CharField(max_length=40, blank=True)
    importer_fax = models.CharField(max_length=40, blank=True)
    importer_email = models.EmailField(blank=True)
    importer_postal_address = models.TextField(blank=True)
    importer_mda_ref = models.CharField(max_length=60, blank=True)
    importer_sector = models.CharField(max_length=80, blank=True)
    importer_warehouse = models.CharField(max_length=180, blank=True)

    consignee_same = models.BooleanField(default=False)
    consignee_code = models.CharField(max_length=180, blank=True)
    consignee_physical_country = models.CharField(max_length=2, blank=True)
    consignee_physical_address = models.TextField(blank=True)
    consignee_postal_country = models.CharField(max_length=2, blank=True)
    consignee_tel = models.CharField(max_length=40, blank=True)
    consignee_fax = models.CharField(max_length=40, blank=True)
    consignee_email = models.EmailField(blank=True)
    consignee_postal_address = models.TextField(blank=True)
    consignee_mda_ref = models.CharField(max_length=60, blank=True)
    consignee_sector = models.CharField(max_length=80, blank=True)
    consignee_warehouse = models.CharField(max_length=180, blank=True)

    means_of_transport = models.CharField(max_length=40, blank=True)
    vessel_name = models.CharField(max_length=180, blank=True)
    voyage_no = models.CharField(max_length=80, blank=True)
    shipment_date = models.DateField(blank=True, null=True)
    carrier = models.CharField(max_length=180, blank=True)
    manifest_no = models.CharField(max_length=80, blank=True)
    bl_awb_no = models.CharField(max_length=80, blank=True)
    marks_numbers = models.TextField(blank=True)
    port_arrival = models.CharField(max_length=80, blank=True)
    port_departure = models.CharField(max_length=80, blank=True)
    customs_office = models.CharField(max_length=80, blank=True)
    freight_station = models.CharField(max_length=120, blank=True)
    inland_transport_co = models.CharField(max_length=180, blank=True)
    inland_transport_ref = models.CharField(max_length=80, blank=True)
    cargo_type = models.CharField(max_length=60, blank=True)
    containers_up_to_20 = models.PositiveSmallIntegerField(default=0)
    containers_30_plus = models.PositiveSmallIntegerField(default=0)

    delivery_term = models.CharField(max_length=60, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    exchange_rate = models.DecimalField(max_digits=14, decimal_places=4, blank=True, null=True)
    fob_fcy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    fob_ncy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    freight_fcy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    freight_ncy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    insurance_fcy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    insurance_ncy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    other_costs_fcy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    other_costs_ncy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    customs_value_fcy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    customs_value_ncy = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)

    items = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [models.UniqueConstraint(fields=("application_no",), condition=Q(application_no__gt=""), name="unique_application_number_when_issued")]

    def __str__(self):
        return self.application_no or f"Application draft for {self.ucr}"


class MdaStatus(models.TextChoices):
    """MDA application statuses; shared with the clearance side.

    Every MDA passes through SU (Submitted). MOTI and GSA approve automatically
    from SU to AP. AD/AE (DTRD), AG (GCUS), and SC (2nd MDA Checking Officer,
    GCoO) belong to MDAs with multi-officer approval chains.
    """

    DRAFT = "DR", "DR, Draft"
    SUBMIT_PENDING_FEE = "PP", "PP, Submit - Pending Fee"
    SUBMITTED = "SU", "SU, Submitted"
    ON_HOLD = "OH", "OH, On-Hold"
    QUERY = "QY", "QY, Query"
    REJECTED = "RJ", "RJ, Rejected"
    APPROVAL_PENDING_FEE = "PD", "PD, Approval - Pending Fee"
    APPROVED_CHECKING_OFFICER = "AC", "AC, Approved Checking Officer"
    APPROVED_VALIDATION_OFFICER = "AV", "AV, Approved Validation Officer"
    APPROVED_MDA = "AM", "AM, Approved MDA"
    APPROVED_DTRD_CHECKING_OFFICER = "AD", "AD, Approved DTRD Checking Officer"
    APPROVED_DTRD_VALIDATION_OFFICER = "AE", "AE, Approved DTRD Validation Officer"
    APPROVED_GCUS_CHECKING_OFFICER = "AG", "AG, Approved GCUS Checking Officer"
    APPROVED = "AP", "AP, Approved"
    RE_SUBMIT = "RS", "RS, Re-Submit"
    APPEAL = "MA", "MA, Appeal"
    APPROVED_APPEAL = "MP", "MP, Approved Appeal"
    REJECTED_APPEAL = "MR", "MR, Rejected Appeal"
    APPROVED_SECOND_MDA_CHECKING_OFFICER = "SC", "SC, Approved 2nd MDA Checking Officer(GCoO)"


class MdaConsignmentRequest(models.Model):
    """MDA application launched from a Consignment Document confirmation tab."""

    class ConsignmentType(models.TextChoices):
        SUB = "SB", "Sub Consignment"
        SINGLE = "SG", "Single Consignment"
        NON_BL = "NB", "Non B/L"

    consignment_application = models.ForeignKey(
        ConsignmentApplication, on_delete=models.CASCADE, related_name="mda_requests"
    )
    mda = models.ForeignKey(MdaAgency, on_delete=models.PROTECT, related_name="consignment_requests")
    application = models.ForeignKey(MdaApplication, on_delete=models.PROTECT, related_name="consignment_requests")
    process = models.ForeignKey(MdaProcess, on_delete=models.PROTECT, related_name="consignment_requests")
    consignment_type = models.CharField(max_length=2, choices=ConsignmentType.choices)
    master_no = models.CharField(max_length=30, blank=True)
    application_no = models.CharField(max_length=25, unique=True, editable=False)
    sequence_month = models.CharField(max_length=6, blank=True, null=True, editable=False)
    monthly_sequence = models.PositiveIntegerField(blank=True, null=True, editable=False)
    form_data = models.JSONField(default=dict, blank=True)
    approval_terms = models.BooleanField(default=False)
    approval_purpose = models.TextField(blank=True)
    approval_remarks = models.TextField(blank=True)
    additional_parties = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=2, choices=MdaStatus.choices, default=MdaStatus.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        constraints = [
            models.UniqueConstraint(fields=("sequence_month", "monthly_sequence"), name="unique_mda_monthly_sequence")
        ]

    def clean(self):
        if self.application_id and self.mda_id and self.application.mda_id != self.mda_id:
            raise ValidationError({"application": "The selected application does not belong to this MDA."})
        if self.process_id and self.application_id and self.process.application_id != self.application_id:
            raise ValidationError({"process": "The selected process does not belong to this application."})
        if self.consignment_type == self.ConsignmentType.SUB and not self.master_no.strip():
            raise ValidationError({"master_no": "Master No. is required for a Sub Consignment."})
        if self.consignment_type != self.ConsignmentType.SUB:
            self.master_no = ""

    def __str__(self):
        return self.application_no


def allocate_application_number():
    """CD + creation date (YYYYMMDD) + a 6-digit sequence, e.g. CD20260919000001."""
    from django.utils import timezone

    stamp = timezone.localtime().strftime("%Y%m%d")
    stem = f"{ConsignmentApplication.APPLICATION_PREFIX}{stamp}"
    existing = ConsignmentApplication.objects.filter(application_no__startswith=stem).values_list("application_no", flat=True)
    sequences = [int(number[len(stem):]) for number in existing if number[len(stem):].isdigit()]
    return f"{stem}{(max(sequences) + 1) if sequences else 1:06d}"

class AssistanceEvent(models.Model):
    class Kind(models.TextChoices):
        HINT = "hint", "Hint"
        GUIDANCE = "guidance", "Guidance"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(ScenarioAttempt, on_delete=models.CASCADE, related_name="assistance_events")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    context_code = models.CharField(max_length=100)
    content_shown = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
