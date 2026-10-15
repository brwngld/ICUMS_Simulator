import uuid

from django.db import migrations, models

import django.db.models.deletion

LEVEL_CODES = ["beginner", "beginner-intermediate", "intermediate", "intermediate-advanced", "advanced"]


def add_courses(apps, schema_editor):
    Programme = apps.get_model("onboarding", "Programme")
    ProgrammeVersion = apps.get_model("onboarding", "ProgrammeVersion")
    Course = apps.get_model("learning", "Course")
    Module = apps.get_model("learning", "Module")

    difficulties = {code: code for code in LEVEL_CODES}
    for version in ProgrammeVersion.objects.order_by("programme_id", "version"):
        orphans = Module.objects.filter(programme_version=version, course__isnull=True)
        if not orphans.exists():
            continue
        programme = Programme.objects.get(pk=version.programme_id)
        # Every module already carries a level, so a version whose modules
        # share one level becomes that level's course rather than a generic
        # container. Mixed or unset levels keep the legacy ordering untouched.
        levels = {module.difficulty for module in orphans if module.difficulty in difficulties}
        difficulty = levels.pop() if len(levels) == 1 else ""
        if Course.objects.filter(programme_version=version).exists():
            # A version can hold several courses once an instructor splits it;
            # the compatibility container takes the next free slot.
            position = Course.objects.filter(programme_version=version).count() + 1
            code = f"{programme.code}-v{version.version}-group-{position}"[:60]
            title = programme.name
        else:
            position = 1
            code = f"{programme.code}-v{version.version}"[:60]
            title = programme.get_difficulty_display() if difficulty else programme.name
        course = Course.objects.create(
            programme_version=version,
            code=code,
            title=title,
            difficulty=difficulty,
            order=position,
            is_published=version.status == "published",
        )
        # Module order and codes are the legacy sequence, so they stay as they are.
        orphans.update(course=course)


def drop_courses(apps, schema_editor):
    Course = apps.get_model("learning", "Course")
    Module = apps.get_model("learning", "Module")
    Module.objects.filter(course__isnull=False).update(course=None)
    Course.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0006_richtextimage"),
        ("onboarding", "0006_programme_overview_summary"),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=60)),
                ("title", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True, help_text="Shown on the learner roadmap under the course title.")),
                (
                    "difficulty",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("beginner", "Beginner"),
                            ("beginner-intermediate", "Beginner to Intermediate"),
                            ("intermediate", "Intermediate"),
                            ("intermediate-advanced", "Intermediate to Advanced"),
                            ("advanced", "Advanced"),
                        ],
                        help_text="One of the five levels. A level unlocks when every required course above it is complete; a course without a level stays available straight away.",
                        max_length=30,
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1)),
                ("is_published", models.BooleanField(default=False)),
                (
                    "is_required",
                    models.BooleanField(
                        default=True,
                        help_text="Required courses gate the next difficulty level. Turn this off for optional courses learners may skip.",
                    ),
                ),
                (
                    "programme_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="courses",
                        to="onboarding.programmeversion",
                    ),
                ),
            ],
            options={"ordering": ("order", "title")},
        ),
        migrations.AddField(
            model_name="module",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="The course this module belongs to. Modules without a course sit on the roadmap on their own.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="modules",
                to="learning.course",
            ),
        ),
        migrations.AddConstraint(
            model_name="course",
            constraint=models.UniqueConstraint(
                fields=("programme_version", "code"), name="unique_course_code_per_programme"
            ),
        ),
        migrations.RunPython(add_courses, drop_courses, elidable=True),
    ]
