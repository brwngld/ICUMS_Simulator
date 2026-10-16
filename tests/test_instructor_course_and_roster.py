from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from learning.models import Module
from onboarding.models import Enrolment, ProgrammeVersion
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioState, ScenarioVersion


class InstructorCourseAndRosterTests(TestCase):
    def setUp(self):
        group, _ = Group.objects.get_or_create(name="Instructor")
        self.instructor = get_user_model().objects.create_user(
            username="roster-instructor", email="instructor@example.com", password="test-password"
        )
        self.instructor.groups.add(group)
        self.client.force_login(self.instructor)

    def create_version(self, name):
        self.client.post(reverse("course-create"), {"name": name})
        return ProgrammeVersion.objects.get(programme__name=name)

    def test_course_create_form_is_presented_in_modal(self):
        response = self.client.get(f'{reverse("course-builder")}?path=theory')
        self.assertContains(response, '<dialog class="authoring-course-modal" id="create-course"', html=False)
        self.assertContains(response, "data-close-course-modal")
        self.assertNotContains(response, '<details class="authoring-card authoring-create"', html=False)

    def test_instructor_can_delete_unused_draft_course_tree(self):
        version = self.create_version("Disposable Draft")
        programme_id = version.programme_id
        self.client.post(reverse("course-builder-module-create", args=[version.pk]), {"title": "Draft Module", "description": ""})
        module = Module.objects.get(programme_version=version)
        scenario = Scenario.objects.create(code="disposable-flow", title="Disposable flow", area=Scenario.Area.IMPORT)
        practical = ScenarioVersion.objects.create(
            scenario=scenario, module=module, version=1, briefing="Draft briefing", learning_objective="Draft objective"
        )
        start = ScenarioState.objects.create(scenario_version=practical, key="start", label="Start", is_initial=True)
        finish = ScenarioState.objects.create(scenario_version=practical, key="finish", label="Finish", is_terminal=True, order=2)
        ScenarioActionDefinition.objects.create(
            scenario_version=practical, code="continue", label="Continue", from_state=start, to_state=finish
        )
        response = self.client.post(reverse("course-delete", args=[version.pk]))
        self.assertRedirects(response, f'{reverse("course-builder")}?path=theory')
        self.assertFalse(ProgrammeVersion.objects.filter(pk=version.pk).exists())
        self.assertFalse(ProgrammeVersion.objects.filter(programme_id=programme_id).exists())

    def test_course_delete_refuses_draft_with_learner_activity(self):
        version = self.create_version("Active Draft")
        student = get_user_model().objects.create_user(username="active-student", email="active@example.com", password="test-password")
        Enrolment.objects.create(student=student, programme_version=version)
        response = self.client.post(reverse("course-delete", args=[version.pk]), follow=True)
        self.assertContains(response, "cannot be deleted because it already has learner activity")
        self.assertTrue(ProgrammeVersion.objects.filter(pk=version.pk).exists())

    def test_roster_is_scoped_to_enrolments_created_by_instructor(self):
        version = self.create_version("Roster Course")
        own_student = get_user_model().objects.create_user(username="own-student", email="own@example.com", password="test-password")
        other_student = get_user_model().objects.create_user(username="other-student", email="other@example.com", password="test-password")
        other_instructor = get_user_model().objects.create_user(username="other-instructor", email="other-instructor@example.com", password="test-password")
        Enrolment.objects.create(student=own_student, programme_version=version, enrolled_by=self.instructor)
        hidden = Enrolment.objects.create(student=other_student, programme_version=version, enrolled_by=other_instructor)
        response = self.client.get(reverse("instructor-student-list"))
        self.assertContains(response, "own-student")
        self.assertNotContains(response, "other-student")
        self.assertEqual(self.client.get(reverse("instructor-student-profile", args=[other_student.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("instructor-student-detail", args=[hidden.pk])).status_code, 404)

    def test_unenrol_withdraws_without_deleting_history(self):
        version = self.create_version("Withdrawal Course")
        student = get_user_model().objects.create_user(username="withdraw-student", email="withdraw@example.com", password="test-password")
        enrolment = Enrolment.objects.create(student=student, programme_version=version, enrolled_by=self.instructor)
        response = self.client.post(reverse("instructor-enrolment-withdraw", args=[enrolment.pk]))
        self.assertRedirects(response, reverse("instructor-student-profile", args=[student.pk]))
        enrolment.refresh_from_db()
        self.assertEqual(enrolment.status, Enrolment.Status.WITHDRAWN)
        self.assertTrue(Enrolment.objects.filter(pk=enrolment.pk).exists())
