"""The Theory & Practical curriculum tree.

A hybrid programme teaches theory reading and practical simulator work in one
lesson, so it gets its own content tree beside ``learning``'s: same shape,
separate rows, shared programme spine. Every content row reaches a
``ProgrammeVersion`` (through its course), never an enrolment — a learner's
enrolment pins the version, and the rows of another version are never
rewritten, which is what lets instructors publish draft revisions without
disturbing learners mid-way through a published edition.

The tree deliberately mirrors ``learning``'s field names and constraint style
(UUID primary keys, ``order``/``title`` ordering, one uniqueness constraint
per parentage level) so the two systems stay easy to compare. Unlike
``learning.Module``, a hybrid module always belongs to a course, so the
version is reached through exactly one path and no denormalised version FK
exists to drift out of sync.

Learner state lives beside the content tree, never inside it:
``LessonAttempt`` is one learner's run through one lesson (resumable, with
theory acknowledgement and completion), ``StepEvent`` is the durable per-step
evidence (opened / verified / hint), and ``VerificationCondition`` is
instructor-authored, developer-constrained config saying what a step must
prove. Conditions never touch the existing Practical Builder's binding
schema; they reuse only the ``scenarios.bindings`` registries, so any
approved ICUMS workflow can be verified without hybrid code naming one.

Future relationship (later stage): a stored hybrid ModuleProgress stamp, if
reporting needs one — module completion is currently computed from lesson
attempts at read time.
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from learning import rich_text
from onboarding.models import Enrolment, ProgrammeVersion
from scenarios.bindings import SIMULATOR_BINDING_ROUTES, VERIFY_RECORDS


class HybridCourse(models.Model):
    """A subject area inside a hybrid programme edition."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(
        ProgrammeVersion,
        on_delete=models.PROTECT,
        related_name="hybrid_courses",
        help_text="The programme edition this course belongs to. Draft revisions clone it; published editions are never rewritten.",
    )
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "title")
        constraints = [
            models.UniqueConstraint(fields=("programme_version", "code"), name="unique_hybrid_course_code_per_programme")
        ]

    def __str__(self):
        return self.title


class HybridModule(models.Model):
    """One module of a hybrid course, taken in ``order``."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        HybridCourse,
        on_delete=models.PROTECT,
        related_name="hybrid_modules",
        help_text="The course this module belongs to. The programme version is reached through it.",
    )
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "title")
        constraints = [
            models.UniqueConstraint(fields=("course", "code"), name="unique_hybrid_module_code_per_course")
        ]

    def __str__(self):
        return self.title


class HybridLesson(models.Model):
    """One lesson: theory reading plus a practical journey, in module order."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(
        HybridModule,
        on_delete=models.PROTECT,
        related_name="hybrid_lessons",
    )
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    summary = models.TextField(blank=True)
    theory = models.TextField(
        blank=True,
        help_text="One continuous rich-text reading for the lesson's theory panel. Sanitised on save.",
    )
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "title")
        constraints = [
            models.UniqueConstraint(fields=("module", "slug"), name="unique_hybrid_lesson_slug_per_module")
        ]

    def save(self, *args, **kwargs):
        self.theory = rich_text.to_safe_html(self.theory)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class PracticalStep(models.Model):
    """One numbered step of a lesson's practical journey in the simulator.

    ``screen`` holds a route *name* from ``scenarios.bindings``' approved
    registry — never a raw URL — so a step survives a simulator URL redesign
    and can only ever target a developer-approved screen of any supported
    workflow. A blank screen keeps whatever screen the lesson is already
    showing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        HybridLesson,
        on_delete=models.CASCADE,
        related_name="practical_steps",
        help_text="The lesson this step belongs to. Steps run in order.",
    )
    key = models.SlugField(
        max_length=60,
        help_text="Stable identifier within the lesson, used by future attempt tracking.",
    )
    title = models.CharField(max_length=180)
    instruction = models.TextField(blank=True, help_text="What the learner does on this step's screen.")
    outcome = models.TextField(blank=True, help_text="What the learner should see when the step is done.")
    hint = models.TextField(blank=True, help_text="Shown only when the learner asks for it.")
    screen = models.CharField(
        max_length=100,
        blank=True,
        help_text="An approved simulator screen route name; blank keeps the current screen.",
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(fields=("lesson", "key"), name="unique_hybrid_step_key_per_lesson")
        ]

    def clean(self):
        if self.screen and self.screen not in SIMULATOR_BINDING_ROUTES:
            raise ValidationError({"screen": "Choose a simulator screen from the approved registry."})

    def screen_label(self):
        return SIMULATOR_BINDING_ROUTES.get(self.screen, "")

    def __str__(self):
        return self.title


class VerificationCondition(models.Model):
    """One server-verified requirement attached to a practical step.

    Two kinds exist in v1: ``saved_record`` — the learner owns a record of an
    approved kind in a required workflow status with exact saved values, and
    it was touched at or after the step was opened — and ``screen_opened`` —
    the learner actually passed through this step's screen. Both are checked
    entirely server-side; a browser can never certify them.
    """

    class Kind(models.TextChoices):
        SAVED_RECORD = "saved_record", "Saved record"
        SCREEN_OPENED = "screen_opened", "Screen opened"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step = models.ForeignKey(
        PracticalStep,
        on_delete=models.CASCADE,
        related_name="conditions",
        help_text="The step this condition gates.",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    record_kind = models.CharField(
        max_length=20,
        blank=True,
        help_text="saved_record only: which approved record kind must exist.",
    )
    required_status = models.CharField(max_length=30, blank=True, help_text="saved_record only.")
    expected_fields = models.JSONField(default=dict, blank=True, help_text="saved_record only: exact saved values.")
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")

    def clean(self):
        if self.kind == self.Kind.SAVED_RECORD:
            if self.record_kind not in VERIFY_RECORDS:
                raise ValidationError({"record_kind": "Choose an approved record kind."})
            model = VERIFY_RECORDS[self.record_kind][0]
            valid_statuses = {value for value, _display in model._meta.get_field("status").choices}
            if self.required_status not in valid_statuses:
                raise ValidationError({"required_status": "Choose a valid status for the record."})
            allowed = {
                field.name for field in model._meta.fields
                if not field.is_relation and field.name not in {"id", "status", "created_at", "updated_at", "submitted_at"}
            }
            unknown = sorted(set(self.expected_fields or {}) - allowed)
            if unknown:
                raise ValidationError({"expected_fields": "Unknown saved-value field(s): " + ", ".join(unknown) + "."})
            if any(isinstance(value, (dict, list)) for value in (self.expected_fields or {}).values()):
                raise ValidationError({"expected_fields": "Expected saved values must be text, numbers, booleans, or null."})
        else:
            self.record_kind = ""
            self.required_status = ""
            self.expected_fields = {}

    def describe(self):
        """A short learner-facing label for feedback lists."""
        if self.kind == self.Kind.SCREEN_OPENED:
            return "Open the step's simulator screen"
        model, model_label = VERIFY_RECORDS[self.record_kind]
        choices = dict(model._meta.get_field("status").choices)
        return f"A {model_label} saved as “{choices.get(self.required_status, self.required_status)}”"

    def __str__(self):
        return f"{self.step.title} · {self.describe()}"


class LessonAttempt(models.Model):
    """One learner's run through one hybrid lesson.

    The attempt is the progress ledger: its ``current_step`` resumes an
    interrupted journey, ``theory_acknowledged_at`` records D5's explicit
    theory acknowledgement, and ``completed_at`` is written only when every
    step is satisfied and the theory is acknowledged. Attempts belong to the
    enrolment, so they are pinned to the enrolled edition forever.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.CASCADE, related_name="hybrid_attempts")
    lesson = models.ForeignKey(HybridLesson, on_delete=models.PROTECT, related_name="attempts")
    current_step = models.ForeignKey(
        PracticalStep,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Where the learner stands; the workspace reopens here.",
    )
    theory_acknowledged_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("enrolment", "lesson"), name="unique_hybrid_attempt_per_lesson")
        ]
        ordering = ("started_at",)

    def __str__(self):
        return f"{self.enrolment_id} · {self.lesson.title}"


class StepEvent(models.Model):
    """Durable evidence for one step of one attempt.

    ``opened`` rows carry the moment the learner last entered the step — the
    freshness bound every saved-record condition is judged against, so
    pre-existing records can never satisfy a new task. ``verified`` rows are
    written only by the server after every condition passes, and the partial
    unique constraint makes duplicate checkpoint completion impossible at the
    database level.
    """

    class Kind(models.TextChoices):
        OPENED = "opened", "Opened"
        VERIFIED = "verified", "Verified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attempt = models.ForeignKey(LessonAttempt, on_delete=models.CASCADE, related_name="step_events")
    step = models.ForeignKey(PracticalStep, on_delete=models.PROTECT, related_name="events")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            # Kind.VERIFIED's value; a class-body name is not resolvable here.
            models.UniqueConstraint(
                fields=("attempt", "step"),
                condition=Q(kind="verified"),
                name="unique_hybrid_step_verified",
            ),
        ]
        indexes = [models.Index(fields=("attempt", "step", "kind"))]

    def __str__(self):
        return f"{self.attempt_id} · {self.step.title} · {self.kind}"
