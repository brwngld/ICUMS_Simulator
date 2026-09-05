from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from assessments.models import AnswerOption, Assessment, AssessmentItem, LessonCheck, Question, QuestionVersion
from learning.models import ContentBlock, Lesson, Module, Resource
from onboarding.models import DisclaimerVersion, Enrolment, Programme, ProgrammeVersion


class Command(BaseCommand):
    help = "Load clearly labelled fictional theory content for development and demonstrations."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Optionally enrol an existing user in the demonstration programme.")

    @transaction.atomic
    def handle(self, *args, **options):
        DisclaimerVersion.objects.filter(is_current=True).update(is_current=False)
        DisclaimerVersion.objects.update_or_create(
            version=1,
            defaults={
                "title": "Training simulator notice",
                "body": (
                    "This application is an educational training simulator. It is not the official ICUMS system.\n\n"
                    "All transactions and documents used here are fictitious. Nothing entered or submitted here "
                    "creates a customs declaration, government transaction, payment, shipment instruction, or legal record."
                ),
                "is_current": True,
            },
        )
        programme, _ = Programme.objects.update_or_create(
            code="customs-foundations",
            defaults={"name": "Customs Clearance Foundations", "is_active": True},
        )
        programme_version, _ = ProgrammeVersion.objects.update_or_create(
            programme=programme,
            version=1,
            defaults={"status": ProgrammeVersion.Status.PUBLISHED, "published_at": timezone.now()},
        )
        module, _ = Module.objects.update_or_create(
            programme_version=programme_version,
            code="document-foundations",
            defaults={
                "title": "Document Review Foundations",
                "description": "Fictional demonstration content for testing the theory learning flow.",
                "order": 1,
                "is_published": True,
            },
        )
        lesson, _ = Lesson.objects.update_or_create(
            module=module,
            slug="document-consistency",
            defaults={
                "title": "Checking document consistency",
                "summary": "Learn how to identify a mismatch across fictional shipment documents.",
                "order": 1,
                "is_published": True,
            },
        )
        ContentBlock.objects.update_or_create(
            lesson=lesson,
            order=1,
            defaults={
                "kind": ContentBlock.Kind.NOTICE,
                "heading": "Fictional training example",
                "body": "The names, references, quantities, and events in this lesson are invented for simulator testing.",
            },
        )
        comparison_block, _ = ContentBlock.objects.update_or_create(
            lesson=lesson,
            order=2,
            defaults={
                "kind": ContentBlock.Kind.TEXT,
                "heading": "Compare the documents",
                "body": "Review the Bill of Lading, commercial invoice, and packing list. Compare parties, references, quantities, descriptions, weights, and dates before proceeding.",
            },
        )
        resource, _ = Resource.objects.update_or_create(
            title="Document consistency review",
            defaults={"description": "Return to this fictional lesson and review the comparison checklist."},
        )
        resource.lessons.add(lesson)
        question, _ = Question.objects.get_or_create(code="demo-document-mismatch")
        question_version, _ = QuestionVersion.objects.update_or_create(
            question=question,
            version=1,
            defaults={
                "prompt": "The invoice shows 120 cartons and the packing list shows 102. What should happen first?",
                "explanation": "A material inconsistency should be investigated and resolved before proceeding.",
                "points": 1,
                "is_published": True,
                "remediation_resource": resource,
            },
        )
        correct_option, _ = AnswerOption.objects.update_or_create(question_version=question_version, order=1, defaults={"label": "Investigate and resolve the inconsistency", "is_correct": True})
        AnswerOption.objects.update_or_create(question_version=question_version, order=2, defaults={"label": "Ignore the difference and continue", "is_correct": False})
        AnswerOption.objects.update_or_create(question_version=question_version, order=3, defaults={"label": "Submit immediately", "is_correct": False})
        assessment, _ = Assessment.objects.update_or_create(
            programme_version=programme_version,
            title="Document Review Foundations Assessment",
            defaults={"module": module, "assessment_type": Assessment.Type.MODULE, "pass_percentage": 70, "is_published": True},
        )
        AssessmentItem.objects.update_or_create(assessment=assessment, question_version=question_version, defaults={"order": 1})
        LessonCheck.objects.update_or_create(
            lesson=lesson,
            question_version=question_version,
            defaults={"after_block": comparison_block, "order": 1},
        )
        final_assessment, _ = Assessment.objects.update_or_create(
            programme_version=programme_version,
            title="Final Theory Demonstration Examination",
            defaults={"module": None, "assessment_type": Assessment.Type.FINAL_THEORY, "pass_percentage": 70, "is_published": True},
        )
        AssessmentItem.objects.update_or_create(assessment=final_assessment, question_version=question_version, defaults={"order": 1})

        username = options.get("username")
        if username:
            user_model = get_user_model()
            try:
                user = user_model.objects.get(username=username)
            except user_model.DoesNotExist as exc:
                raise CommandError(f"User '{username}' does not exist.") from exc
            user.groups.add(Group.objects.get(name="Student"))
            Enrolment.objects.get_or_create(student=user, programme_version=programme_version)
            self.stdout.write(self.style.SUCCESS(f"Seeded content and enrolled {username}. Correct option: {correct_option.label}"))
        else:
            self.stdout.write(self.style.SUCCESS("Seeded fictional demonstration content."))
