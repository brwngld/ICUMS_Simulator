from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from evaluations.models import Rubric, RubricCriterion, RubricVersion
from learning.models import Resource
from scenarios.models import BillOfLading, BillOfLadingCargoItem, CommercialDocument, CommercialDocumentLine, Scenario, ScenarioActionDefinition, ScenarioDocument, ScenarioState, ScenarioVersion


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
            ("Bill of Lading", "Fictional Bill of Lading", "FIC-BL-004821", {
                "carrier": "Atlantic Training Carrier Ltd",
                "bill_of_lading_number": "FIC-BL-004821",
                "shipper": "Savannah Demo Exporters Ltd, Valencia, Spain",
                "consignee": "Akwaaba Training Traders Ltd, Accra, Ghana",
                "notify_party": "Akwaaba Training Traders Ltd, Accra, Ghana",
                "carrier_agent": "Coastal Training Agency Ltd, Tema, Ghana",
                "booking_reference": "SIM-BKG-84017",
                "shipper_reference": "SIM-REF-2219",
                "vessel": "MV Learning Star",
                "voyage_number": "TRN-042",
                "port_of_loading": "Valencia, Spain",
                "port_of_discharge": "Tema, Ghana",
                "place_of_receipt": "Madrid, Spain",
                "place_of_delivery": "Accra, Ghana",
                "freight_terms": "Freight prepaid",
                "container_number": "SIMU 204817 3",
                "container_type": "40 ft high cube",
                "seal_number": "SIM-883104",
                "package_count": "120 cartons",
                "goods_description": "Fictitious household ceramic items for simulator training",
                "gross_weight": "2,400 kg",
                "measurement": "24.8 m3",
                "declared_value": "GHS 48,000 - training only",
                "place_and_date_of_issue": "Tema, Ghana - 10 September 2026",
                "shipped_on_board_date": "2 September 2026",
            }, {"expected_quantity": 120}),
            ("Commercial Invoice", "Fictional Commercial Invoice", "FIC-INV-2026-104", {"Consignee": "Akwaaba Training Traders Ltd", "Quantity": "120 cartons", "Value": "GHS 48,000 (training only)"}, {"expected_quantity": 120}),
            ("Packing List", "Fictional Packing List", "FIC-PL-2026-104", {"Consignee": "Akwaaba Training Traders Ltd", "Quantity": "102 cartons", "Gross weight": "2,400 kg"}, {"expected_quantity": 120, "issue": "quantity_mismatch"}),
        ]
        for order, (document_type, title, reference, learner_data, evaluator_data) in enumerate(documents, start=1):
            ScenarioDocument.objects.update_or_create(
                scenario_version=version,
                document_type=document_type,
                defaults={"title": title, "reference": reference, "pdf_layout": {"Bill of Lading": "bill_of_lading", "Commercial Invoice": "commercial_invoice", "Packing List": "packing_list"}[document_type], "learner_data": learner_data, "evaluator_data": evaluator_data, "order": order},
            )
        bill, _ = BillOfLading.objects.update_or_create(
            reference="SIM-BL-240091",
            defaults={
                "scenario_version": version, "title": "Structured Fictional Bill of Lading", "template": BillOfLading.Template.OCEAN_TRANSPORT, "status": BillOfLading.Status.PUBLISHED,
                "carrier": "Atlantic Training Carrier Ltd", "carrier_agent": "Coastal Training Agency Ltd, Tema, Ghana", "shipper": "Savannah Demo Exporters Ltd, Valencia, Spain",
                "consignee": "Akwaaba Training Traders Ltd, Accra, Ghana", "notify_party": "Akwaaba Training Traders Ltd, Accra, Ghana", "booking_reference": "SIM-BKG-84017", "shipper_reference": "SIM-REF-2219",
                "vessel": "MV Learning Star", "voyage_number": "TRN-042", "place_of_receipt": "Madrid, Spain", "port_of_loading": "Valencia, Spain", "port_of_discharge": "Tema, Ghana", "place_of_delivery": "Accra, Ghana",
                "freight_terms": "Freight prepaid", "place_of_issue": "Tema, Ghana", "shipped_on_board_date": timezone.localdate(), "additional_declarations": "Shipper's load, stow, weight and count. Fictitious non-hazardous cargo for training only.",
            },
        )
        BillOfLadingCargoItem.objects.update_or_create(
            bill_of_lading=bill, order=1,
            defaults={"cargo_type": BillOfLadingCargoItem.CargoType.VEHICLE, "container_number": "SIMU2048173", "seal_number": "SIM883104", "container_type": "40 ft high cube", "package_quantity": 1, "package_type": "vehicle", "goods_description": "Fictitious used passenger vehicle", "vehicle_year": 2022, "vehicle_make": "Example Motors", "vehicle_model": "Training SUV", "vin_or_chassis": "SIMVIN00000000001", "hs_code": "8703.23", "gross_weight": "1500.000", "weight_unit": "KGM"},
        )
        BillOfLadingCargoItem.objects.update_or_create(
            bill_of_lading=bill, order=2,
            defaults={"cargo_type": BillOfLadingCargoItem.CargoType.PERSONAL_EFFECTS, "container_number": "SIMU2048173", "seal_number": "SIM883104", "container_type": "40 ft high cube", "package_quantity": 4, "package_type": "packages", "goods_description": "Fictitious household and personal effects", "hs_code": "9905.00", "gross_weight": "900.000", "weight_unit": "KGM"},
        )
        invoice, _ = CommercialDocument.objects.update_or_create(
            reference="SIM-INV-240091",
            defaults={"scenario_version": version, "document_type": CommercialDocument.DocumentType.INVOICE, "status": CommercialDocument.Status.PUBLISHED, "title": "Structured Fictitious Commercial Invoice", "document_date": timezone.localdate(), "exporter_name": "Savannah Demo Exporters Ltd", "exporter_address": "14 Training Quay, Valencia, Spain", "exporter_contact": "+34 000 000 000", "consignee_name": "Akwaaba Training Traders Ltd", "consignee_address": "8 Simulator Avenue, Accra, Ghana", "currency": "USD", "container_reference": "SIMU2048173 / 40FT HC", "payment_terms": "Freight collect", "fob": "18400.00", "freight": "1250.00", "insurance": "180.00", "notes": "Fictitious invoice for training only."},
        )
        CommercialDocumentLine.objects.update_or_create(document=invoice, order=1, defaults={"description": "Fictitious training SUV, model year 2022", "quantity": 1, "quantity_unit": "unit", "package_count": 1, "pieces_per_package": "1 vehicle", "gross_weight": "1500.000", "net_weight": "1500.000", "weight_unit": "KGM", "hs_code": "8703.23", "unit_price": "18000.00", "amount": "18000.00"})
        CommercialDocumentLine.objects.update_or_create(document=invoice, order=2, defaults={"description": "Fictitious household effects", "quantity": 4, "quantity_unit": "pkgs", "package_count": 4, "pieces_per_package": "mixed cartons", "gross_weight": "900.000", "net_weight": "820.000", "weight_unit": "KGM", "hs_code": "9905.00", "unit_price": "100.00", "amount": "400.00"})
        packing, _ = CommercialDocument.objects.update_or_create(
            reference="SIM-PL-240091",
            defaults={"scenario_version": version, "document_type": CommercialDocument.DocumentType.PACKING_LIST, "status": CommercialDocument.Status.PUBLISHED, "title": "Structured Fictitious Packing List", "document_date": timezone.localdate(), "exporter_name": "Savannah Demo Exporters Ltd", "exporter_address": "14 Training Quay, Valencia, Spain", "exporter_contact": "+34 000 000 000", "consignee_name": "Akwaaba Training Traders Ltd", "consignee_address": "8 Simulator Avenue, Accra, Ghana", "currency": "USD", "container_reference": "SIMU2048173 / 40FT HC", "notes": "No prices are shown on a packing list. Fictitious training sample."},
        )
        CommercialDocumentLine.objects.update_or_create(document=packing, order=1, defaults={"description": "Fictitious training SUV, model year 2022", "quantity": 1, "quantity_unit": "unit", "package_count": 1, "pieces_per_package": "1 vehicle", "gross_weight": "1500.000", "net_weight": "1500.000", "weight_unit": "KGM", "hs_code": "8703.23"})
        CommercialDocumentLine.objects.update_or_create(document=packing, order=2, defaults={"description": "Fictitious household effects", "quantity": 4, "quantity_unit": "pkgs", "package_count": 4, "pieces_per_package": "5 pcs/carton", "gross_weight": "900.000", "net_weight": "820.000", "weight_unit": "KGM", "hs_code": "9905.00"})
        proforma, _ = CommercialDocument.objects.update_or_create(
            reference="SIM-PRO-240091",
            defaults={"scenario_version": version, "document_type": CommercialDocument.DocumentType.PROFORMA_INVOICE, "status": CommercialDocument.Status.PUBLISHED, "title": "Structured Fictitious Proforma Invoice", "document_date": timezone.localdate(), "exporter_name": "Savannah Demo Exporters Ltd", "exporter_address": "14 Training Quay, Valencia, Spain", "exporter_contact": "+34 000 000 000", "consignee_name": "Akwaaba Training Traders Ltd", "consignee_address": "8 Simulator Avenue, Accra, Ghana", "currency": "USD", "container_reference": "Proposed 40FT HC shipment", "payment_terms": "Quotation valid for 30 days", "fob": "18000.00", "freight": "1250.00", "insurance": "180.00", "notes": "Quotation only. Prices and shipping costs are provisional."},
        )
        CommercialDocumentLine.objects.update_or_create(document=proforma, order=1, defaults={"description": "Proposed purchase: fictitious training SUV, model year 2022", "quantity": 1, "quantity_unit": "unit", "gross_weight": "1500.000", "net_weight": "1500.000", "weight_unit": "KGM", "hs_code": "8703.23", "unit_price": "18000.00", "amount": "18000.00"})
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
        self._seed_competency_scenario(documents)
        self.stdout.write(self.style.SUCCESS("Seeded the fictional guided and competency Import scenarios."))

    def _seed_competency_scenario(self, documents):
        scenario, _ = Scenario.objects.update_or_create(
            code="fictional-import-competency",
            defaults={"title": "Fictional Import Competency Check", "area": Scenario.Area.IMPORT},
        )
        version, _ = ScenarioVersion.objects.update_or_create(
            scenario=scenario,
            version=1,
            defaults={
                "status": ScenarioVersion.Status.PUBLISHED,
                "assistance_mode": ScenarioVersion.AssistanceMode.COMPETENCY,
                "purpose": ScenarioVersion.Purpose.COMPETENCY,
                "reference_status": ScenarioVersion.ReferenceStatus.CONCEPTUAL,
                "briefing": "Independently process a fictitious import transaction. This workflow remains conceptual until approved reference material is supplied.",
                "learning_objective": "Demonstrate independent document review, processing, parallel shipping-line activity, and field clearance.",
                "initial_data": {"discrepancy_recorded": False, "processing_complete": False, "shipping_invoice_requested": False, "shipping_invoice_paid": False, "shipping_release_requested": False, "field_clearance_complete": False},
                "published_at": timezone.now(),
            },
        )
        states = {}
        specs = [
            ("independent-review", "Independent document review", True, False),
            ("declaration-processing", "Declaration processing", False, False),
            ("field-clearance", "Field clearance", False, False),
            ("competency-complete", "Competency check complete", False, True),
        ]
        for order, (key, label, initial, terminal) in enumerate(specs, start=1):
            states[key], _ = ScenarioState.objects.update_or_create(
                scenario_version=version,
                key=key,
                defaults={"label": label, "guidance": "Complete this stage independently.", "order": order, "is_initial": initial, "is_terminal": terminal},
            )
        actions = [
            ("identify-competency-discrepancy", "Record the document discrepancy", "independent-review", "declaration-processing", {}, {"discrepancy_recorded": True}),
            ("complete-competency-processing", "Complete declaration processing", "declaration-processing", "field-clearance", {"discrepancy_recorded": True}, {"processing_complete": True}),
            ("request-competency-shipping-invoice", "Request shipping-line invoice", None, None, {"processing_complete": True, "shipping_invoice_requested": False}, {"shipping_invoice_requested": True}),
            ("pay-competency-shipping-invoice", "Pay fictional shipping-line invoice", None, None, {"shipping_invoice_requested": True, "shipping_invoice_paid": False}, {"shipping_invoice_paid": True}),
            ("request-competency-shipping-release", "Request shipping-line release", None, None, {"shipping_invoice_paid": True, "shipping_release_requested": False}, {"shipping_release_requested": True}),
            ("complete-competency-clearance", "Complete field clearance", "field-clearance", "competency-complete", {"shipping_release_requested": True}, {"field_clearance_complete": True}),
        ]
        for order, (code, label, source, target, conditions, effects) in enumerate(actions, start=1):
            ScenarioActionDefinition.objects.update_or_create(
                scenario_version=version,
                code=code,
                defaults={"label": label, "from_state": states[source] if source else None, "to_state": states[target] if target else None, "conditions": conditions, "effects": effects, "success_feedback": f"{label} recorded.", "beginner_hint": "", "order": order},
            )
        for order, (document_type, title, reference, learner_data, evaluator_data) in enumerate(documents, start=1):
            ScenarioDocument.objects.update_or_create(
                scenario_version=version,
                document_type=document_type,
                defaults={"title": title, "reference": f"COMP-{reference}", "learner_data": learner_data, "evaluator_data": evaluator_data, "order": order},
            )
        rubric, _ = Rubric.objects.update_or_create(code="fictional-import-competency", defaults={"title": "Fictional Import Competency Rubric"})
        rubric_version, _ = RubricVersion.objects.update_or_create(
            rubric=rubric,
            version=1,
            defaults={"scenario_version": version, "status": RubricVersion.Status.PUBLISHED, "pass_percentage": 70, "is_demonstration": True, "published_at": timezone.now()},
        )
        criteria = [
            ("competency-completion", "Complete the competency workflow", RubricCriterion.Dimension.COMPLETION, 30, {"type": "completion"}),
            ("competency-actions", "Complete all required independent actions", RubricCriterion.Dimension.PROCEDURE, 50, {"type": "required_actions", "action_codes": [item[0] for item in actions]}),
            ("competency-release", "Secure the fictional shipping release", RubricCriterion.Dimension.DECISION_MAKING, 20, {"type": "state_flags", "equals": {"shipping_release_requested": True}}),
        ]
        for order, (code, title, dimension, points, rule) in enumerate(criteria, start=1):
            RubricCriterion.objects.update_or_create(
                rubric_version=rubric_version,
                code=code,
                defaults={"title": title, "dimension": dimension, "maximum_points": points, "mandatory": True, "evaluation_rule": rule, "order": order},
            )
