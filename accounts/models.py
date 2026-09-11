import hashlib
import hmac
import re
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


class User(AbstractUser):
    """Application user; defined before the first migration for long-term flexibility."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    student_id = models.CharField(max_length=14, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("username",)

    def __str__(self) -> str:
        return self.get_full_name() or self.username


class StudentIdSequence(models.Model):
    key = models.CharField(max_length=20, primary_key=True, default="students", editable=False)
    current_value = models.PositiveIntegerField(default=0)


def allocate_student_id(first_name):
    letters = re.sub(r"[^A-Za-z]", "", first_name or "").upper()[:4].ljust(4, "X")
    with transaction.atomic():
        sequence, _ = StudentIdSequence.objects.select_for_update().get_or_create(key="students")
        sequence.current_value += 1
        sequence.save(update_fields=("current_value",))
        return f"{letters}{sequence.current_value:05d}/{timezone.localdate():%y}"


class SimulatorCredential(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="simulator_credential")
    nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    issued_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    reset_requested_at = models.DateTimeField(blank=True, null=True)

    @property
    def is_current(self):
        return bool(self.issued_at and self.expires_at and self.expires_at > timezone.now())

    @property
    def generated_password(self):
        if not self.issued_at:
            return ""
        digest = hmac.new(settings.SECRET_KEY.encode(), f"{self.user_id}:{self.nonce}".encode(), hashlib.sha256).hexdigest()
        return f"Ic!{digest[:4].upper()}{digest[4:10]}"

    def issue(self):
        now = timezone.now()
        if not self.user.student_id:
            self.user.student_id = allocate_student_id(self.user.first_name or self.user.username)
            self.user.save(update_fields=("student_id",))
        self.nonce = uuid.uuid4()
        self.issued_at = now
        if now.month == 12:
            boundary = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            boundary = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.expires_at = boundary
        self.reset_requested_at = None
        self.save()

    def matches(self, value):
        return self.is_current and hmac.compare_digest(self.generated_password, value or "")
