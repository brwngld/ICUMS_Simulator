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

    def test_lesson_is_created_as_a_draft_and_then_built_in_the_editor(self):
        self.client.post(reverse("course-create"), {"name": "Trade Theory"})
        version = ProgrammeVersion.objects.get(programme__name="Trade Theory")
        self.client.post(reverse("course-builder-module-create", args=[version.pk]), {"title": "CPC", "description": ""})
        module = Module.objects.get(programme_version=version)
        response = self.client.post(
            reverse("lesson-create", args=[module.pk]),
            {
                "title": "Understanding CPCs",
                "summary": "Recognise the structure and purpose of a CPC.",
                "objectives": "Read the first two digits of a CPC.",
                "key_terms": "CPC :: Customs Procedure Code.",
            },
        )
        lesson = Lesson.objects.get(module=module)
        # The popup creates the draft and returns to the module lessons list; the
        # tabbed editor is opened from there.
        self.assertRedirects(response, f'{reverse("module-edit", args=[module.pk])}?tab=lessons')
        self.assertEqual(lesson.blocks.count(), 0)
        self.assertEqual(lesson.knowledge_checks.count(), 0)

        self.client.post(reverse("lesson-section-add", args=[lesson.pk]), {"kind": "text"})
        block = lesson.blocks.get()
        self.client.post(
            reverse("lesson-edit", args=[lesson.pk]),
            {
                "title": "Understanding CPCs",
                "summary": "Recognise the structure and purpose of a CPC.",
                "objectives": "Read the first two digits of a CPC.",
                "key_terms": "CPC :: Customs Procedure Code.",
                "form-TOTAL_FORMS": "1",
                "form-INITIAL_FORMS": "1",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                "form-0-id": str(block.pk),
                "form-0-heading": "What a CPC means",
                "form-0-body": "The first two digits identify the requested regime.",
            },
        )
        block.refresh_from_db()
        self.assertEqual(block.body, "<p>The first two digits identify the requested regime.</p>")

        self.client.post(
            reverse("lesson-practice-add", args=[lesson.pk]),
            {
                "prompt": "What do the first two digits represent?",
                "points": "1",
                "explanation": "They identify the current requested regime.",
                "option_1": "The requested regime",
                "option_2": "The previous regime",
                "option_3": "The risk channel",
                "option_4": "The importer TIN",
                "correct_position": "1",
                "add_to_assessment": "on",
            },
        )
        lesson.refresh_from_db()
        self.assertEqual(lesson.blocks.count(), 1)
        check = lesson.knowledge_checks.get()
        self.assertEqual(check.after_block_id, lesson.blocks.get().pk)
        question_version = check.question_version
        self.assertEqual(question_version.prompt, "What do the first two digits represent?")
        self.assertEqual(question_version.options.count(), 4)
        self.assertEqual(question_version.options.filter(is_correct=True).count(), 1)
        self.assertEqual(question_version.options.get(is_correct=True).label, "The requested regime")
        assessment = Assessment.objects.get(module=module)
        self.assertEqual(assessment.items.count(), 1)
        self.assertEqual(assessment.items.get().question_version, question_version)
        self.assertFalse(lesson.is_published)
        self.assertFalse(question_version.is_published)
        self.assertFalse(assessment.is_published)

    def test_student_cannot_access_course_builder(self):
        student = get_user_model().objects.create_user(username="student", email="student@example.com", password="test-password")
        self.client.force_login(student)
        response = self.client.get(reverse("course-builder"))
        # The portal gate sends a student back to their own dashboard with a
        # warning instead of Django's bare 403 page; access is still refused.
        self.assertRedirects(response, reverse("dashboard"))
        response = self.client.get(reverse("course-builder"), follow=True)
        self.assertTrue(any("Instructor access is required." in str(message) for message in response.context["messages"]))

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
        self.test_lesson_is_created_as_a_draft_and_then_built_in_the_editor()
        version = ProgrammeVersion.objects.get(programme__name="Trade Theory")
        module = version.modules.get()
        self.client.post(
            reverse("final-exam-create", args=[version.pk]),
            {"title": "Trade Theory final examination", "pass_percentage": "70", "maximum_attempts": "3"},
        )
        final_exam = Assessment.objects.get(programme_version=version, assessment_type=Assessment.Type.FINAL_THEORY)
        self.client.post(
            reverse("assessment-question-add", args=[final_exam.pk]),
            {
                "prompt": "Which CPC digits record the requested regime?",
                "points": "1",
                "explanation": "The first two digits of a CPC record the requested regime.",
                "option_1": "The first two digits",
                "option_2": "The last two digits",
                "option_3": "The importer TIN",
                "option_4": "The border post code",
                "correct_position": "1",
            },
        )
        response = self.client.get(reverse("course-review", args=[version.pk]))
        self.assertContains(response, "Ready to publish")
        response = self.client.post(reverse("course-publish", args=[version.pk]))
        self.assertRedirects(response, reverse("instructor-dashboard"))
        version.refresh_from_db()
        self.assertEqual(version.status, ProgrammeVersion.Status.PUBLISHED)
        self.assertTrue(version.modules.get().is_published)
        self.assertTrue(version.modules.get().lessons.get().is_published)
        self.assertTrue(QuestionVersion.objects.get(prompt="What do the first two digits represent?").is_published)
        self.assertTrue(QuestionVersion.objects.get(prompt="Which CPC digits record the requested regime?").is_published)
        self.assertTrue(Assessment.objects.get(module=module).is_published)
        final_exam.refresh_from_db()
        self.assertTrue(final_exam.is_published)

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
        practical = ScenarioVersion.objects.get(module=module)
        self.assertRedirects(response, reverse("practical-edit", args=[practical.pk]))
        self.assertEqual(practical.status, ScenarioVersion.Status.DRAFT)
        self.assertEqual(practical.states.count(), 4)
        self.assertEqual(practical.action_definitions.count(), 3)
        self.assertTrue(practical.states.get(order=1).is_initial)
        self.assertTrue(practical.states.get(key="complete").is_terminal)
        self.assertEqual(practical.rubric_version.criteria.count(), 1)
