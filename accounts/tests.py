from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SimulatorCredential, User


class StudentRegistrationTests(TestCase):
    def test_registration_assigns_progressive_student_ids(self):
        payload = {"first_name": "Bernard", "last_name": "Learner", "email": "bernard@example.test", "password1": "LongTrainingPassword!47", "password2": "LongTrainingPassword!47"}
        response = self.client.post(reverse("register"), payload)
        self.assertRedirects(response, reverse("dashboard"))
        first = User.objects.get(email=payload["email"])
        self.assertEqual(first.student_id, "BERN00001/26")
        self.assertEqual(first.username, first.student_id)
        self.client.logout()
        payload.update(first_name="Alice", email="alice@example.test")
        self.client.post(reverse("register"), payload)
        self.assertEqual(User.objects.get(email=payload["email"]).student_id, "ALIC00002/26")


class SimulatorCredentialTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="BERN00001/26", student_id="BERN00001/26", first_name="Bernard", email="credential@example.test", password="MainAccountPassword!47")
        Group.objects.get_or_create(name="Student")[0].user_set.add(self.user)
        self.credential = SimulatorCredential.objects.create(user=self.user)
        self.credential.issue()

    def test_valid_generated_credential_opens_simulator(self):
        response = self.client.post(reverse("simulator-login"), {"student_id": self.user.student_id, "password": self.credential.generated_password})
        self.assertRedirects(response, reverse("simulator-portal"))
        self.assertEqual(self.client.session["simulator_user_id"], str(self.user.pk))

    def test_expired_credential_is_rejected_and_reset_can_be_requested(self):
        password = self.credential.generated_password
        SimulatorCredential.objects.filter(pk=self.credential.pk).update(expires_at=timezone.now())
        response = self.client.post(reverse("simulator-login"), {"student_id": self.user.student_id, "password": password})
        self.assertRedirects(response, reverse("simulator-portal"))
        self.assertNotIn("simulator_user_id", self.client.session)
        self.client.post(reverse("simulator-reset-request"), {"student_id": self.user.student_id})
        self.credential.refresh_from_db()
        self.assertIsNotNone(self.credential.reset_requested_at)

    def test_staff_simulator_sign_out_is_refused_with_clear_message(self):
        staff = User.objects.create_user(username="staff", password="StaffPassword!47", is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse("simulator-logout"), follow=True)
        self.assertContains(response, "Staff and administrators have permanent simulator access")
        self.assertContains(response, "simulator sign-out is unavailable")

    def test_student_simulator_sign_out_clears_secondary_session(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["simulator_user_id"] = str(self.user.pk)
        session.save()
        response = self.client.post(reverse("simulator-logout"), follow=True)
        self.assertNotIn("simulator_user_id", self.client.session)
        self.assertContains(response, "You have signed out of the simulator workspace")
