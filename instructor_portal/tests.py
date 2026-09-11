from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from assessments.models import Assessment, QuestionVersion
from learning.models import Lesson, Module
from onboarding.models import ProgrammeVersion
from scenarios.models import ScenarioVersion


class CourseBuilderTests(TestCase):
    def setUp(self):
        instructor_group, _ = Group.objects.get_or_create(name="Instructor")
        self.user = get_user_model().objects.create_user(username="instructor", email="instructor@example.com", password="test-password")
        self.user.groups.add(instructor_group)
        self.client.force_login(self.user)

    def test_instructor_can_create_course_and_module_without_technical_fields(self):
        response = self.client.post(reverse("course-create"), {"name": "International Trade and Customs"})
        version = ProgrammeVersion.objects.get(programme__name="International Trade and Customs")
        self.assertRedirects(response, reverse("course-builder-detail", args=[version.pk]))
        self.assertEqual(version.status, ProgrammeVersion.Status.DRAFT)
        detail_response = self.client.get(reverse("course-builder-detail", args=[version.pk]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "International Trade and Customs")

        response = self.client.post(
            reverse("course-builder-module-create", args=[version.pk]),
            {"title": "Customs Procedure Codes", "description": "Understand CPC structure."},
        )
        self.assertRedirects(response, reverse("course-builder-detail", args=[version.pk]))
        module = Module.objects.get(programme_version=version)
        self.assertEqual(module.code, "customs-procedure-codes")
        self.assertFalse(module.is_published)

    def test_complete_lesson_form_creates_blocks_check_question_and_assessment(self):
        self.client.post(reverse("course-create"), {"name": "Trade Theory"})
        version = ProgrammeVersion.objects.get(programme__name="Trade Theory")
        self.client.post(reverse("course-builder-module-create", args=[version.pk]), {"title": "CPC", "description": ""})
        module = Module.objects.get(programme_version=version)
        response = self.client.post(
            reverse("lesson-create", args=[module.pk]),
            {
                "title": "Understanding CPCs",
                "summary": "Recognise the structure and purpose of a CPC.",
                "concept_heading": "What a CPC means",
                "concept_body": "The first two digits identify the requested regime.",
                "example_heading": "Example",
                "example_body": "70X00 is used for warehousing.",
                "notice_heading": "Why it matters",
                "notice_body": "The CPC affects duty and risk decisions.",
                "question_prompt": "What do the first two digits represent?",
                "correct_answer": "The requested regime",
                "incorrect_answer_1": "The previous regime",
                "incorrect_answer_2": "The risk channel",
                "incorrect_answer_3": "The importer TIN",
                "explanation": "They identify the current requested regime.",
                "add_to_assessment": "on",
            },
        )
        self.assertRedirects(response, reverse("course-builder-detail", args=[version.pk]))
        lesson = Lesson.objects.get(module=module)
        self.assertEqual(lesson.blocks.count(), 3)
        self.assertEqual(lesson.knowledge_checks.count(), 1)
        question_version = QuestionVersion.objects.get(question__code="cpc-understanding-cpcs")
        self.assertEqual(question_version.options.count(), 4)
        self.assertEqual(question_version.options.filter(is_correct=True).count(), 1)
        assessment = Assessment.objects.get(module=module)
        self.assertEqual(assessment.items.count(), 1)
        self.assertFalse(lesson.is_published)
        self.assertFalse(question_version.is_published)
        self.assertFalse(assessment.is_published)

    def test_student_cannot_access_course_builder(self):
        student = get_user_model().objects.create_user(username="student", email="student@example.com", password="test-password")
        self.client.force_login(student)
        response = self.client.get(reverse("course-builder"))
        self.assertEqual(response.status_code, 403)

    def test_instructor_dashboard_exposes_the_two_authoring_paths(self):
        response = self.client.get(reverse("instructor-dashboard"))
        self.assertContains(response, "Theory builder")
        self.assertContains(response, "Practical/Theory builder")

    def test_admin_without_student_enrolment_does_not_get_student_theory_link(self):
        self.user.is_staff = True
        self.user.save(update_fields=("is_staff",))
        response = self.client.get(reverse("instructor-dashboard"))
        self.assertNotContains(response, 'href="/theory/"')
        response = self.client.get(reverse("roadmap"))
        self.assertRedirects(response, f'{reverse("course-builder")}?path=theory')

    def test_complete_course_can_be_published_from_review(self):
        self.test_complete_lesson_form_creates_blocks_check_question_and_assessment()
        version = ProgrammeVersion.objects.get(programme__name="Trade Theory")
        response = self.client.get(reverse("course-review", args=[version.pk]))
        self.assertContains(response, "Ready to publish")
        response = self.client.post(reverse("course-publish", args=[version.pk]))
        self.assertRedirects(response, reverse("instructor-dashboard"))
        version.refresh_from_db()
        self.assertEqual(version.status, ProgrammeVersion.Status.PUBLISHED)
        self.assertTrue(version.modules.get().is_published)
        self.assertTrue(version.modules.get().lessons.get().is_published)
        self.assertTrue(QuestionVersion.objects.get(question__code="cpc-understanding-cpcs").is_published)
        self.assertTrue(Assessment.objects.get(module__programme_version=version).is_published)

    def test_guided_practical_builder_creates_an_isolated_linear_flow(self):
        self.client.post(reverse("course-create"), {"name": "Unified Customs Training"})
        version = ProgrammeVersion.objects.get(programme__name="Unified Customs Training")
        self.client.post(reverse("course-builder-module-create", args=[version.pk]), {"title": "Import Clearance", "description": ""})
        module = Module.objects.get(programme_version=version)
        response = self.client.post(
            reverse("practical-create", args=[module.pk]),
            {
                "title": "Guided BOE Creation",
                "area": "import",
                "briefing": "Create a fictional BOE using supplied training data.",
                "learning_objective": "Complete the correct declaration sequence.",
                "assistance_mode": "beginner",
                "maximum_attempts": "3",
                "steps": "Review the documents\nCreate the BOE\nSubmit the declaration",
            },
        )
        self.assertRedirects(response, reverse("course-builder-detail", args=[version.pk]))
        practical = ScenarioVersion.objects.get(module=module)
        self.assertEqual(practical.status, ScenarioVersion.Status.DRAFT)
        self.assertEqual(practical.states.count(), 4)
        self.assertEqual(practical.action_definitions.count(), 3)
        self.assertTrue(practical.states.get(order=1).is_initial)
        self.assertTrue(practical.states.get(key="complete").is_terminal)
        self.assertEqual(practical.rubric_version.criteria.count(), 1)
