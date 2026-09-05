import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from learning.models import Resource
from scenarios.models import ScenarioAttempt, ScenarioVersion


class Rubric(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=180)

    def __str__(self):
        return self.title


class RubricVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rubric = models.ForeignKey(Rubric, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    scenario_version = models.OneToOneField(ScenarioVersion, on_delete=models.PROTECT, related_name="rubric_version")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=70)
    is_demonstration = models.BooleanField(default=True, help_text="Demonstration rubrics are not approved competency policy.")
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("rubric", "version"), name="unique_rubric_version")]

    def __str__(self):
        return f"{self.rubric.title} v{self.version}"


class RubricCriterion(models.Model):
    class Dimension(models.TextChoices):
        ACCURACY = "accuracy", "Accuracy"
        DOCUMENT_REVIEW = "document_review", "Document review"
        PROCEDURE = "procedure", "Procedure"
        DECISION_MAKING = "decision_making", "Decision-making"
        CORRECTION = "correction", "Problem correction"
        ASSISTANCE = "assistance", "Assistance required"
        COMPLETION = "completion", "Completion"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rubric_version = models.ForeignKey(RubricVersion, on_delete=models.CASCADE, related_name="criteria")
    code = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    dimension = models.CharField(max_length=24, choices=Dimension.choices)
    maximum_points = models.PositiveIntegerField()
    mandatory = models.BooleanField(default=False)
    evaluation_rule = models.JSONField(default=dict, help_text="Validated declarative evaluation rule.")
    remediation_resource = models.ForeignKey(Resource, blank=True, null=True, on_delete=models.SET_NULL, related_name="rubric_criteria")
    remediation_scenario = models.ForeignKey(ScenarioVersion, blank=True, null=True, on_delete=models.SET_NULL, related_name="remediation_criteria")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "title")
        constraints = [models.UniqueConstraint(fields=("rubric_version", "code"), name="unique_rubric_criterion_code")]

    def clean(self):
        super().clean()
        if not isinstance(self.evaluation_rule, dict):
            raise ValidationError({"evaluation_rule": "The evaluation rule must be a JSON object."})
        allowed_types = {"completion", "required_actions", "state_flags", "assistance_limit"}
        if self.evaluation_rule.get("type") not in allowed_types:
            raise ValidationError({"evaluation_rule": "The rule type is missing or unsupported."})

    def __str__(self):
        return self.title


class PracticalEvaluation(models.Model):
    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.OneToOneField(ScenarioAttempt, on_delete=models.PROTECT, related_name="evaluation")
    rubric_version = models.ForeignKey(RubricVersion, on_delete=models.PROTECT, related_name="evaluations")
    system_score = models.PositiveIntegerField(default=0)
    maximum_score = models.PositiveIntegerField(default=0)
    system_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    system_outcome = models.CharField(max_length=8, choices=Outcome.choices)
    elapsed_seconds = models.PositiveIntegerField(default=0, help_text="Informational only; never included in scoring.")
    evaluated_at = models.DateTimeField(auto_now_add=True)

    @property
    def effective_outcome(self):
        latest = self.revisions.order_by("-created_at").first()
        return latest.revised_outcome if latest else self.system_outcome


class CriterionResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(PracticalEvaluation, on_delete=models.CASCADE, related_name="criterion_results")
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.PROTECT, related_name="results")
    awarded_points = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    evidence = models.JSONField(default=dict, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        ordering = ("criterion__order", "criterion__title")
        constraints = [models.UniqueConstraint(fields=("evaluation", "criterion"), name="unique_evaluation_criterion_result")]


class RemediationRecommendation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(PracticalEvaluation, on_delete=models.CASCADE, related_name="remediation_recommendations")
    criterion_result = models.OneToOneField(CriterionResult, on_delete=models.CASCADE, related_name="remediation")
    resource = models.ForeignKey(Resource, blank=True, null=True, on_delete=models.SET_NULL, related_name="practical_recommendations")
    scenario_version = models.ForeignKey(ScenarioVersion, blank=True, null=True, on_delete=models.SET_NULL, related_name="practical_recommendations")
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class EvaluationRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    evaluation = models.ForeignKey(PracticalEvaluation, on_delete=models.PROTECT, related_name="revisions")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="evaluation_revisions")
    original_outcome = models.CharField(max_length=8, choices=PracticalEvaluation.Outcome.choices)
    revised_outcome = models.CharField(max_length=8, choices=PracticalEvaluation.Outcome.choices)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class InstructorFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(ScenarioAttempt, on_delete=models.PROTECT, related_name="instructor_feedback")
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="practical_feedback_authored")
    body = models.TextField()
    visible_to_student = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
