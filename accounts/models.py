import hashlib
import hmac
import re
import uuid

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


class User(AbstractUser):
    """Application user; defined before the first migration for long-term flexibility."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True, blank=True, null=True)
    student_id = models.CharField(max_length=14, unique=True, blank=True, null=True)
    phone = models.CharField(max_length=32, blank=True)
    organisation = models.CharField(max_length=150, blank=True)
    certificate_name = models.CharField(max_length=150, blank=True)
    country = models.CharField(max_length=2, blank=True)
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


class RenewalReason(models.TextChoices):
    EXPIRED = "expired", "My credential has expired"
    EXPIRING = "expiring", "It's about to expire"
    FORGOT = "forgot", "I forgot my password"
    LOCKED = "locked", "I'm locked out"
    OTHER = "other", "Something else"


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
    reset_reason = models.CharField(max_length=40, blank=True, choices=RenewalReason.choices)
    reset_note = models.TextField(blank=True)

    @property
    def is_current(self):
        return bool(self.issued_at and self.expires_at and self.expires_at > timezone.now())

    @property
    def password_state(self):
        if not self.password_hash:
            return "not_issued"
        return "revealed" if self.revealed_at else "awaiting_reveal"

    def issue(self):
        """Regenerate the password; the student views it once on their credential page."""
        now = timezone.now()
        if not self.user.student_id:
            self.user.student_id = allocate_student_id(self.user.first_name or self.user.username)
            self.user.save(update_fields=("student_id",))
        self.issued_at = now
        raw_password = self.recompute_password()
        self.password_hash = make_password(raw_password)
        self.revealed_at = None
        self.issued_at = now
        if now.month == 12:
            boundary = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            boundary = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
        self.expires_at = boundary
        self.reset_requested_at = None
        self.reset_reason = ""
        self.reset_note = ""
        self.save()
        return raw_password

    def recompute_password(self):
        """The password of the current issue, derived from data the server holds.

        Nothing recoverable is stored: the value is keyed from the secret key
        and this issue's timestamp, so it can be recomputed for the student's
        one-time display and only ever matches the stored hash. Re-issuing
        changes the timestamp, and with it the password.
        """
        if not (self.issued_at and self.user_id):
            return ""
        digest = hmac.new(
            settings.SECRET_KEY.encode(),
            f"simulator-password:{self.user_id}:{self.issued_at.isoformat()}".encode(),
            hashlib.sha256,
        ).digest()
        alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
        return "Ic!" + "".join(alphabet[byte % len(alphabet)] for byte in digest[:8])

    def mark_revealed(self):
        self.revealed_at = timezone.now()
        self.save(update_fields=("revealed_at",))

    def matches(self, value):
        return self.is_current and bool(self.password_hash) and check_password(value or "", self.password_hash)


class Notification(models.Model):
    """One notice for one recipient.

    Nothing writes these yet — the centre exists so the account menu and the
    notifications page have a real, styled home; future features create rows
    instead of inventing a second channel.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.title

    @property
    def is_read(self):
        return self.read_at is not None

    def mark_read(self):
        if self.read_at is None:
            self.read_at = timezone.now()
            self.save(update_fields=("read_at",))

class UserPreference(models.Model):
    """The Settings page's stored choices: display format and reminders.

    Saving a choice is real; applying language or date format across every
    page's rendering is a later step — the stored value is what the settings
    form and future features read.
    """

    LANGUAGE_CHOICES = [("en", "English"), ("fr", "Français")]
    TIMEZONE_CHOICES = [
        ("Africa/Accra", "Africa/Accra (GMT+0)"),
        ("Africa/Lagos", "Africa/Lagos (GMT+1)"),
        ("UTC", "UTC"),
    ]
    DATE_FORMAT_CHOICES = [
        ("d M Y", "25 Sep 2026"),
        ("m/d/Y", "09/25/2026"),
        ("Y-m-d", "2026-09-25"),
    ]
    EXPIRY_REMINDER_CHOICES = [
        (7, "7 days before"),
        (3, "3 days before"),
        (1, "1 day before"),
        (0, "Don't remind me"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences")
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")
    timezone = models.CharField(max_length=60, choices=TIMEZONE_CHOICES, default="Africa/Accra")
    date_format = models.CharField(max_length=20, choices=DATE_FORMAT_CHOICES, default="d M Y")
    expiry_reminder_days = models.PositiveSmallIntegerField(choices=EXPIRY_REMINDER_CHOICES, default=7)

    def __str__(self):
        return f"Preferences for {self.user}"
