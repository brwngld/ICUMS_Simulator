import uuid

from django.db import models

from onboarding.models import Programme, ProgrammeVersion

from . import rich_text


class Course(models.Model):
    """A subject area inside a programme edition, placed at one difficulty level.

    Courses sit between the programme and its modules: a learner works through
    the courses of one difficulty level before the next level unlocks.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(ProgrammeVersion, on_delete=models.PROTECT, related_name="courses")
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(
        blank=True,
        help_text="Shown on the learner roadmap under the course title.",
    )
    difficulty = models.CharField(
        max_length=30,
        choices=Programme.Difficulty.choices,
        blank=True,
        help_text="One of the five levels. A level unlocks when every required course above it is complete; a course without a level stays available straight away.",
    )
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
    is_required = models.BooleanField(
        default=True,
        help_text="Required courses gate the next difficulty level. Turn this off for optional courses learners may skip.",
    )

    class Meta:
        ordering = ("order", "title")
        constraints = [models.UniqueConstraint(fields=("programme_version", "code"), name="unique_course_code_per_programme")]

    def __str__(self):
        return self.title


class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(ProgrammeVersion, on_delete=models.PROTECT, related_name="modules")
    course = models.ForeignKey(
        Course,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="modules",
        help_text="The course this module belongs to. Modules without a course sit on the roadmap on their own.",
    )
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=30,
        choices=Programme.Difficulty.choices,
        blank=True,
        help_text="Optional level for this module. Shown as a badge on the learner module and course overviews. Uses the same five levels as the course.",
    )
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
    cover_image = models.ImageField(
        upload_to="module_covers/",
        blank=True,
        help_text="Optional illustration for this module. Shown on the learner module overview and as a thumbnail on the course overview.",
    )
    prerequisite = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT, related_name="unlocks")

    class Meta:
        ordering = ("order", "title")
        constraints = [models.UniqueConstraint(fields=("programme_version", "code"), name="unique_module_code_per_programme")]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="lessons")
    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=180)
    summary = models.TextField(blank=True)
    objectives = models.TextField(blank=True, help_text="One learning objective per line; shown at the top of the lesson.")
    key_terms = models.TextField(blank=True, help_text="One per line as 'Term :: definition'; shown in the lesson sidebar.")
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ("order", "title")
        constraints = [models.UniqueConstraint(fields=("module", "slug"), name="unique_lesson_slug_per_module")]

    def __str__(self):
        return self.title


class ContentBlock(models.Model):
    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        EXAMPLE = "example", "Example"
        NOTICE = "notice", "Notice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="blocks")
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.TEXT)
    heading = models.CharField(max_length=180, blank=True)
    body = models.TextField()
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("order", "id")

    def save(self, *args, **kwargs):
        self.body = rich_text.to_safe_html(self.body)
        super().save(*args, **kwargs)


class RichTextImage(models.Model):
    """One image uploaded into a lesson section, so cleanup can tell owned files from orphans."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="rich_text_images")
    file = models.ImageField(upload_to="lesson_rich_text/")
    created_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="rich_text_images"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    lessons = models.ManyToManyField(Lesson, blank=True, related_name="resources")

    def __str__(self):
        return self.title
