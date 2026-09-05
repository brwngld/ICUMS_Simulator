import uuid

from django.core.exceptions import ValidationError
from django.db import models

from onboarding.models import Enrolment


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario = models.ForeignKey(Scenario, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    assistance_mode = models.CharField(max_length=16, choices=AssistanceMode.choices, default=AssistanceMode.BEGINNER)
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scenario_version = models.ForeignKey(ScenarioVersion, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=80)
    title = models.CharField(max_length=180)
    reference = models.CharField(max_length=100, blank=True)
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
