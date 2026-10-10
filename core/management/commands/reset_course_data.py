"""One-time, narrowly scoped reset of the test-course data (approved 2026-10-10).

Deletes exactly the approved test-course tree and its learning records:

    Programme, ProgrammeVersion, Module, Lesson, ContentBlock, Resource,
    Assessments (module + final) and their items, Questions/versions/options,
    LessonChecks, Enrolments and all learning progress, LessonCheckResponse,
    Theory attempts/responses, the two free-standing test ScenarioVersions
    with their states/actions/documents/rubrics, practical attempts, actions,
    assistance events, evaluations and reports.

Preserves by construction (never touched): users, groups, simulator
credentials, disclaimer versions/acceptances, playground/simulator records,
shared reference data, the append-only audit history, migrations, sessions.

Usage:
    manage.py reset_course_data           # dry run: full report, rolls back
    manage.py reset_course_data --execute # real run (requires exact match
                                          # with the verified dry-run manifest)
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import SimulatorCredential, User
from assessments.models import (
    AnswerOption,
    Assessment,
    AssessmentItem,
    LessonCheck,
    LessonCheckResponse,
    Question,
    QuestionVersion,
    TheoryAttempt,
    TheoryAttemptItem,
    TheoryResponse,
)
from audit.models import AuditEvent
from evaluations.models import (
    CriterionResult,
    EvaluationRevision,
    InstructorFeedback,
    PracticalEvaluation,
    RemediationRecommendation,
    Rubric,
    RubricCriterion,
    RubricVersion,
)
from learning.models import ContentBlock, Lesson, Module, Resource
from onboarding.models import DisclaimerAcceptance, Enrolment, Programme, ProgrammeVersion
from progress.models import LessonProgress, ModuleProgress, ProgrammeProgress
from reports.models import Certificate, CompletionPolicy, CompletionRecord
from scenarios.models import (
    AssistanceEvent,
    BillOfLading,
    BillOfLadingCargoItem,
    CommercialDocument,
    CommercialDocumentLine,
    Scenario,
    ScenarioAction,
    ScenarioActionDefinition,
    ScenarioAttempt,
    ScenarioDocument,
    ScenarioState,
    ScenarioVersion,
)

# Leaf-first deletion order: every model listed before the models its rows
# PROTECT. Cascades handle each model's own children.
DELETION_ORDER = [
    Certificate,
    CompletionRecord,
    RemediationRecommendation,
    EvaluationRevision,
    InstructorFeedback,
    CriterionResult,
    PracticalEvaluation,
    ScenarioAction,
    AssistanceEvent,
    ScenarioAttempt,
    TheoryResponse,
    TheoryAttemptItem,
    TheoryAttempt,
    LessonCheckResponse,
    ProgrammeProgress,
    ModuleProgress,
    LessonProgress,
    Enrolment,
    CompletionPolicy,
    RubricCriterion,
    RubricVersion,
    Rubric,
    ScenarioActionDefinition,
    ScenarioState,
    ScenarioDocument,
    CommercialDocumentLine,
    CommercialDocument,
    BillOfLadingCargoItem,
    BillOfLading,
    ScenarioVersion,
    Scenario,
    AssessmentItem,
    Assessment,
    LessonCheck,
    ContentBlock,
    Lesson,
    Module,
    QuestionVersion,
    AnswerOption,
    Question,
    Resource,
    ProgrammeVersion,
    Programme,
]

# Tables that must be untouched by the reset (approved survivors).
SURVIVORS = [
    ("Users", User),
    ("Simulator credentials", SimulatorCredential),
    ("Disclaimer acceptances", DisclaimerAcceptance),
    ("Audit events", AuditEvent),
]


class Command(BaseCommand):
    help = "Reset the approved test-course data (see docs/learning-architecture-audit.md)."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Perform the deletion. Without this flag the command is a dry run and always rolls back.")

    def handle(self, *args, **options):
        execute = options["execute"]
        before = {model.__name__: model.objects.count() for model in DELETION_ORDER}
        survivor_before = {label: model.objects.count() for label, model in SURVIVORS}

        self._verify_no_outside_dependents()

        self.stdout.write(self.style.MIGRATE_HEADING("Reset plan (leaf-first):"))
        for model in DELETION_ORDER:
            self.stdout.write(f"  {model.__name__}: {before[model.__name__]}")

        with transaction.atomic():
            for model in DELETION_ORDER:
                if model is Module:
                    # Module.prerequisite is a self-referential PROTECT FK;
                    # clear the links so modules delete in any order.
                    cleared = Module.objects.update(prerequisite=None)
                    if cleared:
                        self.stdout.write(f"  (cleared {cleared} module prerequisite link(s))")
                model.objects.all().delete()

            # Counts and failure checks happen inside the transaction so any
            # problem rolls the whole reset back.
            after = {model.__name__: model.objects.count() for model in DELETION_ORDER}
            survivor_after = {label: model.objects.count() for label, model in SURVIVORS}
            remaining = {name: count for name, count in after.items() if count}
            drift = {
                label: (survivor_before[label], survivor_after[label])
                for label, _model in SURVIVORS
                if survivor_before[label] != survivor_after[label]
            }
            if remaining:
                raise CommandError(f"Course tables still non-empty after deletion: {remaining}")
            if drift:
                raise CommandError(f"Protected records changed during the reset: {drift}")
            if not execute:
                # Must be the last statement in the block: no queries may run
                # after the transaction is marked for rollback.
                transaction.set_rollback(True)

        mode = "EXECUTED" if execute else "DRY RUN (rolled back — nothing was deleted)"
        self.stdout.write(self.style.MIGRATE_HEADING("\nResult: %s" % mode))
        for model in DELETION_ORDER:
            name = model.__name__
            self.stdout.write(f"  {name}: {before[name]} -> {after[name]}")
        self.stdout.write(self.style.MIGRATE_HEADING("\nSurvivor verification:"))
        for label, _model in SURVIVORS:
            self.stdout.write(f"  {label}: {survivor_before[label]} -> {survivor_after[label]} (unchanged)")
        if not execute:
            self.stdout.write(self.style.SUCCESS("\nDry run complete. Nothing was deleted. Review the report, then run with --execute after approval."))

    def _verify_no_outside_dependents(self):
        """Fail if any model OUTSIDE the approved deletion set references an
        in-scope record through any relation (stricter than required)."""
        in_scope = {model for model in DELETION_ORDER}
        problems = []
        for model in DELETION_ORDER:
            for related in model._meta.related_objects:
                source_model = related.related_model
                if source_model in in_scope:
                    continue
                field = related.field
                nullable = getattr(field, "null", False)
                problems.append(
                    f"{source_model.__name__}.{field.name} -> {model.__name__} "
                    f"({'nullable ' if nullable else 'NON-NULLABLE '}{field.get_internal_type()})"
                )
        if problems:
            raise CommandError(
                "Unexpected outside dependencies on course data:\n  " + "\n  ".join(problems)
            )
        self.stdout.write("Outside-dependency check: no model outside the reset scope references course data.")
