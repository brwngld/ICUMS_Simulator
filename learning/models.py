import uuid

from django.db import models

from onboarding.models import ProgrammeVersion


class Module(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    programme_version = models.ForeignKey(ProgrammeVersion, on_delete=models.PROTECT, related_name="modules")
    code = models.SlugField(max_length=60)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=False)
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


class Resource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    url = models.URLField(blank=True)
    lessons = models.ManyToManyField(Lesson, blank=True, related_name="resources")

    def __str__(self):
        return self.title
