from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from evaluations.models import Rubric, RubricCriterion, RubricVersion
from learning.models import Resource
from scenarios.models import Scenario, ScenarioActionDefinition, ScenarioDocument, ScenarioState, ScenarioVersion


class Command(BaseCommand):
    help = "Load a clearly fictional guided Import scenario for engine demonstrations."

    @transaction.atomic
    def handle(self, *args, **options):
        scenario, _ = Scenario.objects.update_or_create(
            code="fictional-guided-import",
            defaults={"title": "Guided Fictional Import Clearance", "area": Scenario.Area.IMPORT},
        )
        version, _ = ScenarioVersion.objects.update_or_create(
            scenario=scenario,
            version=1,
            defaults={
                "status": ScenarioVersion.Status.PUBLISHED,
                "assistance_mode": ScenarioVersion.AssistanceMode.BEGINNER,
                "purpose": ScenarioVersion.Purpose.PRACTICE,
                "reference_status": ScenarioVersion.ReferenceStatus.CONCEPTUAL,
                "briefing": "Review a fictitious shipment, progress through the simulated office and field stages, and complete gate out. This workflow is illustrative and awaits subject-matter validation.",
                "learning_objective": "Demonstrate awareness of the major Import workflow stages, document consistency, prerequisites, and parallel shipping-line activity.",
                "initial_data": {
                    "document_mismatch_recorded": False,
                    "document_mismatch_resolved": False,
                    "boe_created": False,
                    "vessel_arrived": True,
                    "shipping_invoice_requested": False,
                    "shipping_invoice_paid": False,
                    "shipping_release_requested": False,
                    "field_clearance_complete": False,
                },
                "published_at": timezone.now(),
            },
        )
        state_specs = [
            ("document-review", "Document review", "Compare all displayed documents and identify inconsistencies.", True, False),
            ("resolve-mismatch", "Resolve document mismatch", "Record the discrepancy before resolving it.", False, False),
            ("create-ucr", "Create UCR", "The documents are ready for the next simulated stage.", False, False),
            ("create-emda", "Create EMDA", "Continue with the simulated declaration preparation.", False, False),
            ("create-boe", "Create BOE", "Create the simulated Bill of Entry.", False, False),
            ("boe-processing", "BOE processing", "Submit and monitor the simulated BOE.", False, False),
            ("assessment", "Assessment decision", "Review and accept the fictional assessment for this guided path.", False, False),
            ("tax-payment", "Tax payment", "Record the fictitious training payment.", False, False),
            ("field-clearance", "Field clearance", "Complete the simulated field-clearance activity.", False, False),
            ("gate-out", "Gate out", "The fictional training transaction is complete.", False, True),
        ]
        states = {}
        for order, (key, label, guidance, initial, terminal) in enumerate(state_specs, start=1):
            states[key], _ = ScenarioState.objects.update_or_create(
                scenario_version=version,
                key=key,
                defaults={"label": label, "guidance": guidance, "order": order, "is_initial": initial, "is_terminal": terminal},
            )

        linear_actions = [
            ("record-document-mismatch", "Record document discrepancy", "document-review", "resolve-mismatch", {"document_mismatch_recorded": True}, "The quantity mismatch has been recorded."),
            ("resolve-document-mismatch", "Resolve document discrepancy", "resolve-mismatch", "create-ucr", {"document_mismatch_resolved": True}, "The fictional documents are now consistent."),
            ("create-ucr", "Create UCR", "create-ucr", "create-emda", {}, "The simulated UCR has been created."),
            ("create-emda", "Create direct EMDA", "create-emda", "create-boe", {}, "The simulated EMDA has been created."),
            ("create-boe", "Create BOE", "create-boe", "boe-processing", {"boe_created": True}, "The simulated BOE has been created."),
            ("submit-boe", "Submit BOE", "boe-processing", "assessment", {}, "The fictional BOE is now under simulated assessment."),
            ("accept-assessment", "Accept assessment", "assessment", "tax-payment", {}, "The fictional assessment has been accepted."),
            ("record-tax-payment", "Record training tax payment", "tax-payment", "field-clearance", {}, "The fictitious tax payment has been recorded."),
            ("complete-field-clearance", "Complete field clearance", "field-clearance", "field-clearance", {"field_clearance_complete": True}, "The simulated field activity is complete."),
            ("gate-out", "Gate out", "field-clearance", "gate-out", {}, "The fictitious shipment has gated out."),
        ]
        for order, (code, label, source, target, effects, feedback) in enumerate(linear_actions, start=1):
            if code == "gate-out":
                conditions = {"shipping_release_requested": True, "field_clearance_complete": True}
            elif code == "complete-field-clearance":
                conditions = {"field_clearance_complete": False}
            else:
                conditions = {}
            ScenarioActionDefinition.objects.update_or_create(
                scenario_version=version,
                code=code,
                defaults={
                    "label": label,
                    "from_state": states[source],
                    "to_state": states[target],
                    "conditions": conditions,
                    "effects": effects,
                    "success_feedback": feedback,
                    "beginner_hint": f"The next guided action is: {label}.",
                    "order": order,
                },
            )
        parallel_actions = [
            ("request-shipping-invoice", "Request shipping-line invoice", {"vessel_arrived": True, "boe_created": True, "shipping_invoice_requested": False}, {"shipping_invoice_requested": True}),
            ("pay-shipping-invoice", "Pay fictional shipping-line invoice", {"shipping_invoice_requested": True, "shipping_invoice_paid": False}, {"shipping_invoice_paid": True}),
            ("request-shipping-release", "Request shipping-line release", {"shipping_invoice_paid": True, "shipping_release_requested": False}, {"shipping_release_requested": True}),
        ]
        for order, (code, label, conditions, effects) in enumerate(parallel_actions, start=50):
            ScenarioActionDefinition.objects.update_or_create(
                scenario_version=version,
                code=code,
                defaults={
                    "label": label,
                    "from_state": None,
                    "to_state": None,
                    "conditions": conditions,
                    "effects": effects,
                    "success_feedback": f"{label} completed in the training scenario.",
                    "beginner_hint": f"Shipping-line work can proceed in parallel when its conditions are satisfied: {label}.",
                    "order": order,
                },
            )
        documents = [
            ("Bill of Lading", "Fictional Bill of Lading", "FIC-BL-004821", {"Consignee": "Akwaaba Training Traders Ltd", "Quantity": "120 cartons", "Vessel status": "Arrived"}, {"expected_quantity": 120}),
            ("Commercial Invoice", "Fictional Commercial Invoice", "FIC-INV-2026-104", {"Consignee": "Akwaaba Training Traders Ltd", "Quantity": "120 cartons", "Value": "GHS 48,000 (training only)"}, {"expected_quantity": 120}),
            ("Packing List", "Fictional Packing List", "FIC-PL-2026-104", {"Consignee": "Akwaaba Training Traders Ltd", "Quantity": "102 cartons", "Gross weight": "2,400 kg"}, {"expected_quantity": 120, "issue": "quantity_mismatch"}),
        ]
        for order, (document_type, title, reference, learner_data, evaluator_data) in enumerate(documents, start=1):
            ScenarioDocument.objects.update_or_create(
                scenario_version=version,
                document_type=document_type,
                defaults={"title": title, "reference": reference, "learner_data": learner_data, "evaluator_data": evaluator_data, "order": order},
            )
        rubric, _ = Rubric.objects.update_or_create(
            code="fictional-import-demonstration",
            defaults={"title": "Fictional Import Demonstration Rubric"},
        )
        rubric_version, _ = RubricVersion.objects.update_or_create(
            rubric=rubric,
            version=1,
            defaults={
                "scenario_version": version,
                "status": RubricVersion.Status.PUBLISHED,
                "pass_percentage": 70,
                "is_demonstration": True,
                "published_at": timezone.now(),
            },
        )
        remediation_resource = Resource.objects.filter(title="Document consistency review").first()
        criteria = [
            {
                "code": "complete-workflow",
                "title": "Complete the simulated workflow",
                "dimension": RubricCriterion.Dimension.COMPLETION,
                "maximum_points": 20,
                "mandatory": True,
                "evaluation_rule": {"type": "completion"},
                "order": 1,
            },
            {
                "code": "document-review",
                "title": "Identify and resolve the document discrepancy",
                "dimension": RubricCriterion.Dimension.DOCUMENT_REVIEW,
                "maximum_points": 25,
                "mandatory": True,
                "evaluation_rule": {"type": "required_actions", "action_codes": ["record-document-mismatch", "resolve-document-mismatch"]},
                "remediation_resource": remediation_resource,
                "order": 2,
            },
            {
                "code": "main-procedure",
                "title": "Follow the main simulated procedure",
                "dimension": RubricCriterion.Dimension.PROCEDURE,
                "maximum_points": 35,
                "mandatory": True,
                "evaluation_rule": {"type": "required_actions", "action_codes": ["create-ucr", "create-emda", "create-boe", "submit-boe", "accept-assessment", "record-tax-payment", "complete-field-clearance", "gate-out"]},
                "order": 3,
            },
            {
                "code": "shipping-line-branch",
                "title": "Complete parallel shipping-line activity",
                "dimension": RubricCriterion.Dimension.DECISION_MAKING,
                "maximum_points": 10,
                "mandatory": True,
                "evaluation_rule": {"type": "state_flags", "equals": {"shipping_release_requested": True}},
                "order": 4,
            },
            {
                "code": "assistance-awareness",
                "title": "Work with limited assistance",
                "dimension": RubricCriterion.Dimension.ASSISTANCE,
                "maximum_points": 10,
                "mandatory": False,
                "evaluation_rule": {"type": "assistance_limit", "maximum_events": 2, "deduction_per_extra": 2},
                "order": 5,
            },
        ]
        for criterion_data in criteria:
            code = criterion_data.pop("code")
            RubricCriterion.objects.update_or_create(rubric_version=rubric_version, code=code, defaults=criterion_data)
        self.stdout.write(self.style.SUCCESS("Seeded the fictional guided Import scenario."))
