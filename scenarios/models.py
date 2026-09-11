import uuid

from django.core.exceptions import ValidationError
from django.db import models

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
