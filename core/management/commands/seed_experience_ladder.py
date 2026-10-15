"""Seed a development-only sample programme that shows all five difficulty levels.

The published training programmes carry unlevelled compatibility courses, so
they cannot demonstrate the difficulty ladder. This command builds its own
programme, courses, modules, lessons, knowledge checks and assessments, plus a
learner and an instructor login, and never touches an existing programme,
enrolment or progress record. Safe to re-run: every row is keyed on the
programme code.

    .venv/Scripts/python.exe manage.py seed_experience_ladder --password <dev-password>
"""
import argparse

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Course, Lesson, Module
from onboarding.models import DisclaimerAcceptance, DisclaimerVersion, Enrolment, Programme, ProgrammeVersion

# (course code, title, difficulty, required, lesson titles)
COURSES = [
    ("foundations", "Customs foundations", "beginner", True,
     ["How a declaration travels", "Who does what in a clearance"]),
    ("trade-terms", "Trade terms basics", "beginner", False,
     ["Incoterms in plain language"]),
    ("documents", "Documentation and compliance", "beginner-intermediate", True,
     ["Documents behind a clearance"]),
    ("valuation", "Valuation and classification", "intermediate", True,
     ["Reading a tariff line"]),
    ("decisions", "Clearance decisions", "intermediate-advanced", True,
     ["Choosing a treatment"]),
    ("regimes", "Complex regimes", "advanced", True,
     ["Suspense and bonded processing"]),
]

BODY = (
    "This is fictional sample material for testing the learning experience. "
    "A shipment is presented, the parties involved are named, and the paperwork "
    "that would normally move alongside it is described step by step. Nothing "
    "here is official guidance, and no real tariff, fee or legal text is quoted. "
    "Read it the way you would read a short case note: what happened, who was "
    "responsible for it, and which document records it."
)


class Command(BaseCommand):
    help = "Create a dev-only five-level sample programme with two logins."

    def add_arguments(self, parser):
        parser.add_argument("--code", default="xladder", help="Programme code to seed under.")
        parser.add_argument("--student", default="xl-learner", help="Username of the dev learner.")
        parser.add_argument("--instructor", default="xl-instructor", help="Username of the dev instructor.")
        parser.add_argument("--password", required=True, type=self._password)

    @staticmethod
    def _password(value):
        if len(value) < 10:
            raise argparse.ArgumentTypeError("Use at least 10 characters for the dev logins.")
        return value

    def handle(self, *args, **options):
        code = options["code"]
        with transaction.atomic():
            version = self._programme(code)
            self._content(version, code)
            self._final_exam(version, code)
            learners = self._people(options)
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {version.programme.name} v{version.version}: "
            f"{version.courses.count()} courses, {version.modules.count()} modules, "
            f"{Lesson.objects.filter(module__programme_version=version).count()} lessons, "
            f"{version.assessments.count()} assessments including the final examination."
        ))
        for label, user in learners:
            self.stdout.write(f"{label}: {user.username}")
        self.stdout.write("Existing programmes untouched: "
                          f"{', '.join(Programme.objects.exclude(code=code).values_list('code', flat=True))}")

    def _programme(self, code):
        programme, _ = Programme.objects.get_or_create(
            code=code,
            defaults={
                "name": "Experience Ladder (sample)",
                "description": "Fictional sample programme used to walk the five difficulty levels.",
                "overview_summary": "A short fictional course set that shows one level unlocking after the level before it is finished.",
                "target_audience": "Development testing only.",
                "learning_approach": "Read structured lessons\nAnswer knowledge checks\nTake module assessments",
                "learning_outcomes": "Follow a clearance from start to finish\nName the document that records each step",
            },
        )
        version, _ = ProgrammeVersion.objects.get_or_create(
            programme=programme, version=1, defaults={"status": ProgrammeVersion.Status.PUBLISHED}
        )
        if version.status != ProgrammeVersion.Status.PUBLISHED:
            version.status = ProgrammeVersion.Status.PUBLISHED
            version.save(update_fields=("status",))
        return version

    def _content(self, version, code):
        for course_index, (slug, title, difficulty, required, topics) in enumerate(COURSES, start=1):
            course, _ = Course.objects.get_or_create(
                programme_version=version, code=slug,
                defaults={
                    "title": title, "difficulty": difficulty, "is_required": required,
                    "is_published": True, "order": course_index,
                    "description": f"Sample {difficulty} course with {len(topics)} module(s).",
                },
            )
            for module_index, topic in enumerate(topics, start=1):
                module, _ = Module.objects.get_or_create(
                    programme_version=version, code=f"{code}-{slug}-{module_index}",
                    defaults={
                        "course": course, "title": topic, "order": module_index, "is_published": True,
                        "description": "Fictional modules, lessons and checks for experience testing.",
                    },
                )
                for lesson_index, lesson_title in enumerate((topic, f"{topic} in practice"), start=1):
                    lesson_key = f"{code}-{slug}-{module_index}-{lesson_index}"
                    lesson = self._lesson(module, f"lesson-{lesson_index}", lesson_title, lesson_index)
                    self._knowledge_check(lesson, lesson_key)
                self._assessment(version, module, f"{code}-{slug}-{module_index}")

    def _final_exam(self, version, code):
        """The examination that still gates orientation and practical training."""
        assessment, created = Assessment.objects.get_or_create(
            programme_version=version, title="Experience Ladder final examination",
            defaults={"assessment_type": Assessment.Type.FINAL_THEORY, "pass_percentage": 70, "is_published": True},
        )
        if created or not assessment.items.exists():
            for number in (1, 2):
                question_version, _correct = self._question(
                    f"{code}-final-q{number}", f"Which record closes the sample clearance? ({number})"
                )
                AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=number)

    def _lesson(self, module, slug, title, order):
        lesson, created = Lesson.objects.get_or_create(
            module=module, slug=slug,
            defaults={
                "title": title, "order": order, "is_published": True,
                "summary": "A short fictional lesson for walking the five-stage reader.",
                "objectives": f"Describe {title.lower()} in your own words\nName the record that supports it",
                "key_terms": f"{title} :: the fictional case used in this lesson",
            },
        )
        if created or not lesson.blocks.exists():
            for block_index, (kind, heading) in enumerate(
                [("text", "What happens"), ("example", "Worked example"), ("notice", "Watch out")], start=1
            ):
                ContentBlock.objects.create(lesson=lesson, kind=kind, heading=heading, body=BODY, order=block_index)
        return lesson

    def _question(self, code, prompt):
        question = Question.objects.create(code=code)
        version = QuestionVersion.objects.create(
            question=question, version=1, prompt=prompt, explanation="Sample material names this as the record.",
            points=1, is_published=True,
        )
        correct = AnswerOption.objects.create(question_version=version, label="The case record", is_correct=True, order=1)
        AnswerOption.objects.create(question_version=version, label="An unrelated form", is_correct=False, order=2)
        return version, correct

    def _assessment(self, version, module, key):
        assessment, created = Assessment.objects.get_or_create(
            programme_version=version, module=module, title=f"{module.title} assessment",
            defaults={"assessment_type": Assessment.Type.MODULE, "pass_percentage": 70, "is_published": True},
        )
        if created or not assessment.items.exists():
            for number in (1, 2):
                question_version, _correct = self._question(
                    f"{key}-q{number}", f"Which document records this step of {module.title.lower()}? ({number})"
                )
                AssessmentItem.objects.create(assessment=assessment, question_version=question_version, order=number)
        return assessment

    def _knowledge_check(self, lesson, key):
        notice_block = lesson.blocks.filter(kind=ContentBlock.Kind.NOTICE).first()
        if notice_block is None or lesson.knowledge_checks.exists():
            return
        question_version, _correct = self._question(f"{key}-check", "After the watch-out note, which record follows?")
        LessonCheck.objects.create(lesson=lesson, after_block=notice_block, question_version=question_version, order=1)

    def _people(self, options):
        user_model = get_user_model()
        disclaimers = DisclaimerVersion.objects.filter(is_current=True)
        created = []
        for label, username, group_name in (
            ("Learner", options["student"], "Student"),
            ("Instructor", options["instructor"], "Instructor"),
        ):
            user = user_model.objects.filter(username=username).first()
            if user is None:
                user = user_model.objects.create_user(
                    username=username, email=f"{username}@example.test", password=options["password"],
                )
            user.groups.add(Group.objects.get(name=group_name))
            for disclaimer in disclaimers:
                DisclaimerAcceptance.objects.get_or_create(user=user, disclaimer=disclaimer)
            created.append((label, user))
        learner = created[0][1]
        if not Enrolment.objects.filter(student=learner, programme_version__programme__code=options["code"]).exists():
            Enrolment.objects.create(
                student=learner,
                programme_version=ProgrammeVersion.objects.get(programme__code=options["code"], version=1),
            )
        else:
            Enrolment.objects.filter(student=learner, programme_version__programme__code=options["code"]).update(status="active")
        return created
