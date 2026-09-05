import uuid

from django.db import models

from learning.models import Lesson, Module
from onboarding.models import Enrolment


class LessonProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name="progress_records")
    last_position = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("enrolment", "lesson"), name="unique_lesson_progress")]


class ModuleProgress(models.Model):
    class Status(models.TextChoices):
        LOCKED = "locked", "Locked"
        AVAILABLE = "available", "Available"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="module_progress")
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="progress_records")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("enrolment", "module"), name="unique_module_progress")]


class ProgrammeProgress(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.OneToOneField(Enrolment, on_delete=models.CASCADE, related_name="programme_progress")
    theory_completed_at = models.DateTimeField(blank=True, null=True)
    orientation_unlocked_at = models.DateTimeField(blank=True, null=True)
    orientation_completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
