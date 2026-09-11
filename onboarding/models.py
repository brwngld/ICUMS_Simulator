import uuid

from django.conf import settings
from django.db import models


class Programme(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    code = models.SlugField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class ProgrammeVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        RETIRED = "retired", "Retired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("programme", "version"), name="unique_programme_version")]
        ordering = ("programme__name", "version")

    def __str__(self):
        return f"{self.programme.name} v{self.version}"


class Enrolment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        WITHDRAWN = "withdrawn", "Withdrawn"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="enrolments")
    enrolled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="enrolments_created",
    )
    programme_version = models.ForeignKey(ProgrammeVersion, on_delete=models.PROTECT, related_name="enrolments")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("student", "programme_version"), name="unique_student_programme_enrolment")]

    def __str__(self):
        return f"{self.student} — {self.programme_version}"


class DisclaimerVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=150)
    body = models.TextField()
    is_current = models.BooleanField(default=False)
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-version",)

    def __str__(self):
        return f"Disclaimer v{self.version}"


class DisclaimerAcceptance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="disclaimer_acceptances")
    disclaimer = models.ForeignKey(DisclaimerVersion, on_delete=models.PROTECT, related_name="acceptances")
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("user", "disclaimer"), name="unique_disclaimer_acceptance")]
