import re
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.utils.crypto import get_random_string
from django.db import models, transaction
from django.utils import timezone


class User(AbstractUser):
    """Application user; defined before the first migration for long-term flexibility."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True, blank=True, null=True)
    student_id = models.CharField(max_length=14, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("username",)

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        # Empty emails are stored as NULL so the unique constraint tolerates
        # any number of users created without one (e.g. via the admin add screen).
        if self.email == "":
            self.email = None
        super().save(*args, **kwargs)


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
    """Monthly simulator login for a student.

    The password is generated randomly on issue(), stored only as a hash, and
    shown exactly once (revealed_at) — it can never be looked up again; a reset
    is the only way to get a new one.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="simulator_credential")
    password_hash = models.CharField(max_length=128, blank=True)
    revealed_at = models.DateTimeField(blank=True, null=True)
    issued_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    reset_requested_at = models.DateTimeField(blank=True, null=True)

    @property
    def is_current(self):
        return bool(self.issued_at and self.expires_at and self.expires_at > timezone.now())

    @property
    def password_state(self):
        if not self.password_hash:
            return "not_issued"
        return "revealed" if self.revealed_at else "awaiting_reveal"

    def issue(self):
        """Regenerate the password; returns the new plaintext for its single reveal."""
        now = timezone.now()
        if not self.user.student_id:
            self.user.student_id = allocate_student_id(self.user.first_name or self.user.username)
            self.user.save(update_fields=("student_id",))
        raw_password = f"Ic!{get_random_string(8)}"
        self.password_hash = make_password(raw_password)
        self.revealed_at = None
        self.issued_at = now
        if now.month == 12:
            boundary = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            boundary = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.expires_at = boundary
        self.reset_requested_at = None
        self.save()
        return raw_password

    def mark_revealed(self):
        self.revealed_at = timezone.now()
        self.save(update_fields=("revealed_at",))

    def matches(self, value):
        return self.is_current and bool(self.password_hash) and check_password(value or "", self.password_hash)
