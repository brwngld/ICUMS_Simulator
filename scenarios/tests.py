from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Scenario, ScenarioDocument, ScenarioVersion


class ScenarioDocumentPdfTests(TestCase):
    def test_staff_can_preview_a_generated_fictitious_pdf(self):
        user = get_user_model().objects.create_user(username="admin-preview", email="admin-preview@example.com", password="test", is_staff=True)
        scenario = Scenario.objects.create(code="pdf-preview", title="PDF preview", area="import")
        version = ScenarioVersion.objects.create(scenario=scenario, version=1, briefing="Training", learning_objective="Review")
        document = ScenarioDocument.objects.create(
            scenario_version=version,
            pdf_layout=ScenarioDocument.PdfLayout.COMMERCIAL_INVOICE,
            document_type="Invoice",
            title="Fictitious commercial invoice",
            reference="INV-SIM-001",
            learner_data={"seller": "Example Exporter Ltd", "amount": "USD 1,250.00"},
        )
        self.client.force_login(user)
        response = self.client.get(reverse("scenario-document-pdf", args=[document.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_unrelated_user_cannot_open_a_training_document(self):
        user = get_user_model().objects.create_user(username="outsider", email="outsider@example.com", password="test")
        scenario = Scenario.objects.create(code="private-pdf", title="Private PDF", area="import")
        version = ScenarioVersion.objects.create(scenario=scenario, version=1, briefing="Training", learning_objective="Review")
        document = ScenarioDocument.objects.create(scenario_version=version, document_type="Invoice", title="Sample")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("scenario-document-pdf", args=[document.pk])).status_code, 403)
