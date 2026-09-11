import uuid

from django.conf import settings
from django.db import models

from evaluations.models import PracticalEvaluation
from onboarding.models import Enrolment, ProgrammeVersion


class CompletionPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.OneToOneField(ProgrammeVersion, on_delete=models.PROTECT, related_name="completion_policy")
    requires_instructor_approval = models.BooleanField(default=False)
    certificate_template_version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Completion policy — {self.programme_version}"


class CompletionRecord(models.Model):
    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Pending instructor approval"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.OneToOneField(Enrolment, on_delete=models.PROTECT, related_name="completion_record")
    qualifying_evaluation = models.ForeignKey(PracticalEvaluation, on_delete=models.PROTECT, related_name="completion_records")
    status = models.CharField(max_length=20, choices=Status.choices)
    evidence_snapshot = models.JSONField(default=dict)
    policy_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.PROTECT, related_name="completion_approvals")
    approved_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.enrolment} — {self.get_status_display()}"


class Certificate(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    completion_record = models.OneToOneField(CompletionRecord, on_delete=models.PROTECT, related_name="certificate")
    certificate_number = models.CharField(max_length=50, unique=True)
    template_version = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.TextField(blank=True)

    def __str__(self):
        return self.certificate_number
