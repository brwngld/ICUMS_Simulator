from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from learning.models import Lesson, Module
from onboarding.models import Programme, ProgrammeVersion
from progress.models import LessonProgress


class ModuleLessonTabFlowTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name="Instructor")
        self.instructor = get_user_model().objects.create_user(username="lesson-tab-instructor", password="test-password")
        self.instructor.groups.add(group)
        self.client.force_login(self.instructor)
        programme = Programme.objects.create(name="Lesson tab course", code="lesson-tab-course")
        self.version = ProgrammeVersion.objects.create(programme=programme, version=1)
        self.module = Module.objects.create(
            programme_version=self.version, code="lesson-tab-module", title="Lesson tab module"
        )

    def test_module_lessons_tab_contains_inline_create_form(self):
        response = self.client.get(f'{reverse("module-edit", args=[self.module.pk])}?tab=lessons')
        self.assertContains(response, '<dialog id="add-lesson" class="authoring-course-modal">', html=False)
        self.assertContains(response, "data-close-lesson-modal")
        self.assertContains(response, reverse("lesson-create", args=[self.module.pk]))
        self.assertContains(response, reverse("course-builder-detail", args=[self.version.pk]))

    def test_created_lesson_returns_to_module_lessons_tab(self):
        response = self.client.post(reverse("lesson-create", args=[self.module.pk]), {
            "title": "A new lesson",
            "summary": "A short summary",
            "objectives": "Understand the flow",
            "key_terms": "Flow :: A sequence of steps",
        })
        self.assertRedirects(response, f'{reverse("module-edit", args=[self.module.pk])}?tab=lessons')
        self.assertTrue(Lesson.objects.filter(module=self.module, title="A new lesson").exists())

    def test_saved_lesson_stays_on_the_active_editor_tab(self):
        lesson = Lesson.objects.create(module=self.module, slug="editable", title="Editable lesson")
        response = self.client.post(reverse("lesson-edit", args=[lesson.pk]), {
            "title": "Updated lesson",
            "summary": "Updated summary",
            "objectives": "Updated objective",
            "key_terms": "Term :: Definition",
            "active_tab": "sections",
            "form-TOTAL_FORMS": "0",
            "form-INITIAL_FORMS": "0",
            "form-MIN_NUM_FORMS": "0",
            "form-MAX_NUM_FORMS": "1000",
        })
        self.assertRedirects(response, f'{reverse("lesson-edit", args=[lesson.pk])}?tab=sections')

    def test_draft_lesson_can_be_deleted_from_module_tab(self):
        lesson = Lesson.objects.create(module=self.module, slug="disposable", title="Disposable lesson")
        response = self.client.post(reverse("lesson-delete", args=[lesson.pk]))
        self.assertRedirects(response, f'{reverse("module-edit", args=[self.module.pk])}?tab=lessons')
        self.assertFalse(Lesson.objects.filter(pk=lesson.pk).exists())

    def test_lesson_with_student_progress_cannot_be_deleted(self):
        student = get_user_model().objects.create_user(username="lesson-student", password="test-password")
        enrolment = self.version.enrolments.create(student=student)
        lesson = Lesson.objects.create(module=self.module, slug="started", title="Started lesson")
        LessonProgress.objects.create(enrolment=enrolment, lesson=lesson)
        response = self.client.post(reverse("lesson-delete", args=[lesson.pk]), follow=True)
        self.assertContains(response, "cannot be deleted because it already has learner activity")
        self.assertTrue(Lesson.objects.filter(pk=lesson.pk).exists())
