import uuid

from django.core.exceptions import ValidationError
from django.db import models

from learning.models import Module, Resource
from onboarding.models import Enrolment, ProgrammeVersion


class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80, unique=True)

    def __str__(self):
        return self.code


class QuestionVersion(models.Model):
    class Type(models.TextChoices):
        SINGLE = "single", "Single choice"
        TRUE_FALSE = "true_false", "True or false"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    question_type = models.CharField(max_length=16, choices=Type.choices, default=Type.SINGLE)
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
    remediation_resource = models.ForeignKey(Resource, blank=True, null=True, on_delete=models.SET_NULL, related_name="question_versions")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("question", "version"), name="unique_question_version")]

    def __str__(self):
        return f"{self.question.code} v{self.version}"


class AnswerOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_version = models.ForeignKey(QuestionVersion, on_delete=models.CASCADE, related_name="options")
    label = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")


class Assessment(models.Model):
    class Type(models.TextChoices):
        MODULE = "module", "Module assessment"
        FINAL_THEORY = "final_theory", "Final theory examination"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(ProgrammeVersion, on_delete=models.PROTECT, related_name="assessments")
    module = models.ForeignKey(Module, blank=True, null=True, on_delete=models.PROTECT, related_name="assessments")
    title = models.CharField(max_length=180)
    assessment_type = models.CharField(max_length=16, choices=Type.choices, default=Type.MODULE)
    pass_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=70)
    maximum_attempts = models.PositiveIntegerField(blank=True, null=True, help_text="Leave blank for unlimited attempts.")
    randomize_questions = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.module_id and self.programme_version_id and self.module.programme_version_id != self.programme_version_id:
            raise ValidationError({"module": "The module must belong to the selected programme version."})
        if self.assessment_type == self.Type.FINAL_THEORY and self.module_id:
            raise ValidationError({"module": "A final theory examination applies to the whole programme and cannot belong to one module."})


class AssessmentItem(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="items")
    question_version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="assessment_items")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=("assessment", "question_version"), name="unique_assessment_question")]


class TheoryAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"

    class Outcome(models.TextChoices):
        PASS = "pass", "Pass"
        FAIL = "fail", "Fail"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.PROTECT, related_name="theory_attempts")
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name="attempts")
    attempt_number = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.IN_PROGRESS)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(blank=True, null=True)
    score = models.PositiveIntegerField(default=0)
    maximum_score = models.PositiveIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    outcome = models.CharField(max_length=8, choices=Outcome.choices, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("enrolment", "assessment", "attempt_number"), name="unique_theory_attempt_number")]
        ordering = ("-started_at",)


class TheoryAttemptItem(models.Model):
    """Question snapshot selected when an attempt begins."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(TheoryAttempt, on_delete=models.CASCADE, related_name="items")
    question_version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="attempt_items")
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=("attempt", "question_version"), name="unique_attempt_question_item")]


class TheoryResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(TheoryAttempt, on_delete=models.CASCADE, related_name="responses")
    question_version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="responses")
    selected_option = models.ForeignKey(AnswerOption, blank=True, null=True, on_delete=models.PROTECT, related_name="responses")
    awarded_score = models.PositiveIntegerField(default=0)
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("attempt", "question_version"), name="unique_attempt_question_response")]


class LessonCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey("learning.Lesson", on_delete=models.CASCADE, related_name="knowledge_checks")
    after_block = models.ForeignKey("learning.ContentBlock", on_delete=models.CASCADE, related_name="knowledge_checks")
    question_version = models.ForeignKey(QuestionVersion, on_delete=models.PROTECT, related_name="lesson_checks")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")
        constraints = [models.UniqueConstraint(fields=("lesson", "question_version"), name="unique_lesson_knowledge_check")]

    def clean(self):
        super().clean()
        if self.lesson_id and self.after_block_id and self.after_block.lesson_id != self.lesson_id:
            raise ValidationError({"after_block": "The selected content block must belong to this lesson."})


class LessonCheckResponse(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="lesson_check_responses")
    lesson_check = models.ForeignKey(LessonCheck, on_delete=models.PROTECT, related_name="responses")
    attempt_number = models.PositiveIntegerField()
    selected_option = models.ForeignKey(AnswerOption, on_delete=models.PROTECT, related_name="lesson_check_responses")
    is_correct = models.BooleanField(default=False)
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-responded_at",)
        constraints = [models.UniqueConstraint(fields=("enrolment", "lesson_check", "attempt_number"), name="unique_lesson_check_attempt")]
