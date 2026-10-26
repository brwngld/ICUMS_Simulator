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

Stage 2 adds an optional journey layer without changing those legacy rows.
Database constraints protect same-row invariants and concurrency boundaries.
Cross-row rules — canonical curriculum ordering, cycle detection, published
immutability, atomic association replacement and journey-aware verification —
remain service responsibilities for later checkpoints. Model clean methods
provide defensive validation for direct authoring, but no journey-aware
runtime behaviour is introduced here.
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


class PracticalJourney(models.Model):
    """A versioned practical workflow spanning lessons in one hybrid course."""

    class StartMode(models.TextChoices):
        NEW_RECORD = "new_record", "New record"
        EXISTING_RECORD = "existing_record", "Existing record"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(
        ProgrammeVersion,
        on_delete=models.PROTECT,
        related_name="practical_journeys",
    )
    course = models.ForeignKey(
        HybridCourse,
        on_delete=models.PROTECT,
        related_name="practical_journeys",
    )
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    start_mode = models.CharField(max_length=20, choices=StartMode.choices, default=StartMode.NEW_RECORD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("order", "title")
        constraints = [
            models.UniqueConstraint(
                fields=("programme_version", "code"),
                name="unique_journey_code_per_version",
            ),
            models.UniqueConstraint(
                fields=("course", "order"),
                name="unique_journey_order_per_course",
            ),
            models.CheckConstraint(condition=Q(order__gte=1), name="journey_order_positive"),
        ]

    def clean(self):
        if self.course_id and self.programme_version_id:
            course_version_id = (
                HybridCourse.objects.filter(pk=self.course_id)
                .values_list("programme_version_id", flat=True)
                .first()
            )
            if course_version_id != self.programme_version_id:
                raise ValidationError({"course": "The course must belong to the journey's programme version."})

    def __str__(self):
        return self.title


class JourneyStep(models.Model):
    """An existing practical step assigned to a cross-lesson journey."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(PracticalJourney, on_delete=models.CASCADE, related_name="step_assignments")
    step = models.OneToOneField(PracticalStep, on_delete=models.PROTECT, related_name="journey_assignment")
    journey_order = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("journey_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("journey", "journey_order"),
                name="unique_step_order_per_journey",
            ),
            models.CheckConstraint(condition=Q(journey_order__gte=1), name="journey_step_order_positive"),
        ]

    def clean(self):
        if not self.journey_id or not self.step_id:
            return
        step_scope = (
            PracticalStep.objects.filter(pk=self.step_id)
            .values_list("lesson__module__course_id", "lesson__module__course__programme_version_id")
            .first()
        )
        journey_scope = (
            PracticalJourney.objects.filter(pk=self.journey_id)
            .values_list("course_id", "programme_version_id")
            .first()
        )
        if step_scope and journey_scope and step_scope != journey_scope:
            raise ValidationError({"step": "The step must belong to the journey's course and programme version."})

    def __str__(self):
        return f"{self.journey.title} · {self.journey_order}. {self.step.title}"


class JourneyRecordRole(models.Model):
    """A stable role for one approved kind of simulator record."""

    class CreationMode(models.TextChoices):
        NEW = "new", "New"
        EXISTING = "existing", "Existing"
        EITHER = "either", "New or existing"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(PracticalJourney, on_delete=models.CASCADE, related_name="record_roles")
    key = models.SlugField(max_length=60)
    label = models.CharField(max_length=180)
    record_kind = models.CharField(max_length=20)
    required = models.BooleanField(default=True)
    creation_mode = models.CharField(max_length=12, choices=CreationMode.choices, default=CreationMode.NEW)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(fields=("journey", "key"), name="unique_record_role_key"),
            models.UniqueConstraint(fields=("journey", "order"), name="unique_record_role_order"),
            models.CheckConstraint(condition=Q(order__gte=1), name="journey_role_order_positive"),
        ]

    def clean(self):
        if self.record_kind not in VERIFY_RECORDS:
            raise ValidationError({"record_kind": "Choose an approved simulator record kind."})

    def __str__(self):
        return f"{self.journey.title} · {self.label}"


class JourneyDependency(models.Model):
    """An additional forward prerequisite between two journey steps."""

    class DependencyType(models.TextChoices):
        STEP_COMPLETED = "step_completed", "Step completed"
        RECORD_AVAILABLE = "record_available", "Record available"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey(PracticalJourney, on_delete=models.CASCADE, related_name="dependencies")
    predecessor_step = models.ForeignKey(
        JourneyStep,
        on_delete=models.CASCADE,
        related_name="dependent_links",
    )
    dependent_step = models.ForeignKey(
        JourneyStep,
        on_delete=models.CASCADE,
        related_name="prerequisite_links",
    )
    dependency_type = models.CharField(max_length=20, choices=DependencyType.choices)
    required_record_role = models.ForeignKey(
        JourneyRecordRole,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="dependencies",
    )
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("journey", "predecessor_step", "dependent_step", "dependency_type"),
                name="unique_journey_dependency",
            ),
            models.UniqueConstraint(fields=("journey", "order"), name="unique_journey_dependency_order"),
            models.CheckConstraint(
                condition=~Q(predecessor_step=models.F("dependent_step")),
                name="journey_dependency_not_self",
            ),
            models.CheckConstraint(condition=Q(order__gte=1), name="journey_dependency_order_positive"),
        ]

    def clean(self):
        errors = {}
        if self.predecessor_step_id and self.dependent_step_id:
            predecessor = JourneyStep.objects.filter(pk=self.predecessor_step_id).first()
            dependent = JourneyStep.objects.filter(pk=self.dependent_step_id).first()
            if predecessor and dependent:
                if predecessor.journey_id != self.journey_id or dependent.journey_id != self.journey_id:
                    errors["journey"] = "Both steps must belong to this journey."
                elif predecessor.journey_order >= dependent.journey_order:
                    errors["dependent_step"] = "The dependent step must come after its predecessor."
        if self.required_record_role_id:
            role_journey_id = (
                JourneyRecordRole.objects.filter(pk=self.required_record_role_id)
                .values_list("journey_id", flat=True)
                .first()
            )
            if role_journey_id != self.journey_id:
                errors["required_record_role"] = "The record role must belong to this journey."
            if self.dependency_type != self.DependencyType.RECORD_AVAILABLE:
                errors["required_record_role"] = "Only record-available dependencies may specify a record role."
        elif self.dependency_type == self.DependencyType.RECORD_AVAILABLE:
            errors["required_record_role"] = "A record-available dependency requires a record role."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.journey.title} · {self.predecessor_step} → {self.dependent_step}"


class JourneyAttempt(models.Model):
    """One enrolment's state within one published practical journey."""

    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    enrolment = models.ForeignKey(Enrolment, on_delete=models.PROTECT, related_name="journey_attempts")
    journey = models.ForeignKey(PracticalJourney, on_delete=models.PROTECT, related_name="attempts")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NOT_STARTED)
    current_journey_step = models.ForeignKey(
        JourneyStep,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-last_activity_at",)
        constraints = [
            models.UniqueConstraint(fields=("enrolment", "journey"), name="unique_enrolment_journey_attempt"),
        ]

    def clean(self):
        errors = {}
        if self.enrolment_id and self.journey_id:
            enrolment_version_id = (
                Enrolment.objects.filter(pk=self.enrolment_id)
                .values_list("programme_version_id", flat=True)
                .first()
            )
            journey_version_id = (
                PracticalJourney.objects.filter(pk=self.journey_id)
                .values_list("programme_version_id", flat=True)
                .first()
            )
            if enrolment_version_id != journey_version_id:
                errors["journey"] = "The journey must belong to the enrolment's programme version."
        if self.current_journey_step_id:
            current_journey_id = (
                JourneyStep.objects.filter(pk=self.current_journey_step_id)
                .values_list("journey_id", flat=True)
                .first()
            )
            if current_journey_id != self.journey_id:
                errors["current_journey_step"] = "The current step must belong to this journey."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.enrolment_id} · {self.journey.title}"


class JourneyRecordAssociation(models.Model):
    """The exact simulator record occupying a role in a learner journey."""

    class AssignmentSource(models.TextChoices):
        CREATED_IN_JOURNEY = "created_in_journey", "Created in journey"
        AUTHORIZED_EXISTING = "authorized_existing", "Authorized existing record"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey_attempt = models.ForeignKey(
        JourneyAttempt,
        on_delete=models.CASCADE,
        related_name="record_associations",
    )
    role = models.ForeignKey(
        JourneyRecordRole,
        on_delete=models.PROTECT,
        related_name="record_associations",
    )
    enrolment = models.ForeignKey(
        Enrolment,
        on_delete=models.PROTECT,
        related_name="journey_record_associations",
    )
    programme_version = models.ForeignKey(
        ProgrammeVersion,
        on_delete=models.PROTECT,
        related_name="journey_record_associations",
    )
    record_kind = models.CharField(max_length=20)
    record_id = models.PositiveBigIntegerField()
    assignment_source = models.CharField(max_length=24, choices=AssignmentSource.choices)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="assigned_journey_records",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    replaced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-assigned_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("journey_attempt", "role"),
                condition=Q(is_active=True),
                name="unique_active_record_per_role",
            ),
            models.CheckConstraint(
                condition=(Q(is_active=True, replaced_at__isnull=True) | Q(is_active=False, replaced_at__isnull=False)),
                name="journey_record_active_state",
            ),
        ]
        indexes = [
            models.Index(fields=("record_kind", "record_id"), name="journey_record_lookup"),
            models.Index(fields=("enrolment", "programme_version"), name="journey_record_owner"),
        ]

    def clean(self):
        errors = {}
        attempt = JourneyAttempt.objects.filter(pk=self.journey_attempt_id).select_related("journey").first()
        role = JourneyRecordRole.objects.filter(pk=self.role_id).first()
        if attempt:
            if self.enrolment_id != attempt.enrolment_id:
                errors["enrolment"] = "The enrolment must match the journey attempt."
            if self.programme_version_id != attempt.journey.programme_version_id:
                errors["programme_version"] = "The programme version must match the journey attempt."
        if role:
            if attempt and role.journey_id != attempt.journey_id:
                errors["role"] = "The record role must belong to the attempted journey."
            if self.record_kind != role.record_kind:
                errors["record_kind"] = "The record kind must match the selected role."
        if self.record_kind not in VERIFY_RECORDS:
            errors["record_kind"] = "Choose an approved simulator record kind."
        elif self.record_id and self.enrolment_id:
            model = VERIFY_RECORDS[self.record_kind][0]
            owner_id = Enrolment.objects.filter(pk=self.enrolment_id).values_list("student_id", flat=True).first()
            if owner_id and not model.objects.filter(pk=self.record_id, owner_id=owner_id).exists():
                errors["record_id"] = "The record must exist and belong to the enrolled learner."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.journey_attempt_id} · {self.role.key} · {self.record_kind}:{self.record_id}"


class JourneyConditionBinding(models.Model):
    """Binds a saved-record condition to a journey's exact record role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    condition = models.OneToOneField(
        VerificationCondition,
        on_delete=models.CASCADE,
        related_name="journey_binding",
    )
    role = models.ForeignKey(
        JourneyRecordRole,
        on_delete=models.PROTECT,
        related_name="condition_bindings",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        errors = {}
        condition = VerificationCondition.objects.filter(pk=self.condition_id).select_related("step").first()
        role = JourneyRecordRole.objects.filter(pk=self.role_id).first()
        if condition:
            if condition.kind != VerificationCondition.Kind.SAVED_RECORD:
                errors["condition"] = "Only saved-record conditions can be bound to a journey record role."
            assignment = JourneyStep.objects.filter(step_id=condition.step_id).first()
            if not assignment:
                errors["condition"] = "The condition's step must be assigned to a journey."
            elif role and assignment.journey_id != role.journey_id:
                errors["role"] = "The condition and role must belong to the same journey."
            if role and condition.record_kind != role.record_kind:
                errors["role"] = "The condition and role must use the same record kind."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.condition_id} · {self.role.key}"


class SimulatorRecordCreation(models.Model):
    """Authoritative server-side evidence that one registry record was created.

    One row per created simulator record of an approved kind, written by the
    capture receiver in ``hybrid.creation_ledger`` inside the same database
    transaction as the record's INSERT. Every value is server-generated: the
    owner comes from the creating view, the timestamp from ``auto_now_add`` —
    nothing here is client-supplied.

    The ledger is evidence only. It carries no journey, role or attempt
    reference, and nothing in the journey engine reads it, so it cannot by
    itself claim a role, satisfy a dependency or complete a journey.
    Attribution (linking a ledger row to a journey attempt) is a separate,
    later checkpoint. ``owner`` uses ``PROTECT`` so evidence outlives user
    cleanup; ``record_id`` is kept as a plain integer reference — the ledger
    is historical evidence and deliberately does not follow record deletion.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record_kind = models.CharField(max_length=20)
    record_id = models.PositiveBigIntegerField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="simulator_creation_evidence",
    )
    record_created_at = models.DateTimeField()
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("record_created_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("record_kind", "record_id"),
                name="unique_creation_evidence_per_record",
            ),
        ]
        indexes = [
            models.Index(fields=("owner", "record_kind"), name="creation_evidence_owner_kind"),
        ]

    def clean(self):
        if self.record_kind not in VERIFY_RECORDS:
            raise ValidationError({"record_kind": "Choose an approved simulator record kind."})

    def __str__(self):
        return f"{self.record_kind}:{self.record_id} · {self.owner_id}"
