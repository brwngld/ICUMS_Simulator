# Data Model

## Modelling principles

- Use relational tables for identity, enrolment, progression, attempts, and audit history.
- Version learning and scenario content so historical attempts remain interpretable.
- Append attempts and actions; never replace prior history.
- Separate definitions (what should happen) from attempts (what a learner did).
- Store a stable machine code and a user-facing label for states and competency criteria.
- Do not encode unfinished customs knowledge as permanent database constraints.

## Core relationship map

```text
User --< UserRole >-- Role
User --< Enrolment >-- ProgrammeVersion
ProgrammeVersion --< CurriculumModule --< Lesson --< ContentBlock
CurriculumModule --< ModuleAssessment --< AssessmentQuestion
Question --< QuestionVersion

User --< TheoryAttempt --< TheoryResponse
User --< ScenarioAttempt --< ScenarioAction
Scenario --< ScenarioVersion --< ScenarioDocument
ScenarioVersion --< ScenarioRule
ScenarioVersion --< EvaluationCriterion

Enrolment --< ProgressRecord
Attempt --< AssistanceEvent
Attempt -- Evaluation --< CriterionResult
Evaluation --< EvaluationRevision
Evaluation --< RemediationRecommendation

Enrolment -- CompletionRecord -- Certificate
User --< AuditEvent
```

## Identity and enrolment

### `users`

`id`, `email`, `password_hash`, `display_name`, `status`, `created_at`, `updated_at`, `last_login_at`

### Django Groups, permissions, and memberships

Role groups begin with `student`, `instructor`, and `admin`. Django's group membership supports combined Admin + Instructor accounts. The application still enforces domain-specific access, such as which students an instructor may view; broad group membership alone is not sufficient authorization.

### `programmes`, `programme_versions`, and `enrolments`

A programme version freezes the curriculum structure used by an enrolment. Enrolment stores learner, programme version, status, enrolled/completed timestamps, and certificate policy.

### `disclaimer_acceptances`

Stores user, disclaimer version, accepted timestamp, and relevant session/client metadata. A new material disclaimer version can require renewed acknowledgement.

## Learning content

### `curriculum_modules`

Programme version, code, title, description, theory/practical category, display order, publication state, and prerequisite policy.

### `lessons` and `content_blocks`

Lessons belong to modules. Ordered content blocks support text, images, examples, document references, and embedded short questions without hard-coding a curriculum into templates.

### `resources` and `content_resource_links`

Metadata and private file/external-link references. Links associate resources with lessons, scenarios, competency criteria, or remediation rules.

### `questions`, `question_versions`, and `answer_options`

Questions have stable identities and immutable published versions. V1 should initially support single choice, multiple choice, true/false, and short response. Short responses may require instructor review unless a deliberately narrow automatic rubric is configured.

## Theory assessments

### `assessments` and `assessment_items`

Definition, assessment type, module/programme relationship, published version, selection/order rules, configurable pass threshold, and attempt policy.

### `theory_attempts`

Learner, assessment version, attempt number, practice/formal classification, status, started/submitted timestamps, recorded duration, raw score, maximum score, percentage, and outcome.

### `theory_responses`

Attempt, question version, selected/written response, awarded score, automatic result, feedback snapshot, and instructor-review state.

## Practical scenarios

### `scenarios` and `scenario_versions`

Stable scenario identity plus immutable published definitions. Fields include practical area, objective, assistance mode, briefing, initial state, fictional-data marker, publication state, and definition version.

### `scenario_documents`

Scenario version, document type, private file reference, display metadata, and structured fictional values used for validation. Conditional documents are related to scenario conditions rather than fixed columns.

### `scenario_rules`

Validated declarative rules for prerequisites, available actions, transitions, warnings, mismatches, blocking conditions, corrections, and status changes. Rules use a constrained schema, not executable code.

### `scenario_attempts`

Learner, scenario version, attempt number, practice/formal classification, assistance mode, status, current state, started/last-saved/submitted timestamps, recorded duration, and resumable state payload.

### `scenario_actions`

Append-only event sequence: attempt, sequence number, action code, state before/after, input snapshot, outcome code, feedback shown, and timestamp.

### `assistance_events`

Records hint, explanation, checklist, or instructor assistance usage and its context. This provides evidence for competency evaluation without making assistance automatically punitive in practice modes.

## Evaluation, remediation, and review

### `evaluation_criteria`

Versioned rubric criteria such as accuracy, document review, procedure, decision-making, problem identification, correction, and assistance. Weight and pass rules remain configurable.

### `evaluations` and `criterion_results`

Preserve overall outcome and criterion-level evidence. Time is included as informational evidence but excluded from score calculation in V1.

### `evaluation_revisions`

Future-ready append-only instructor changes storing original/revised values, reason, actor, and timestamp. V1 may expose this only to administrators or leave the UI deferred.

### `remediation_rules`, `recommendations`, and `assignments`

Map weakness codes to a lesson, resource, or same-skill alternative scenario. A recommendation does not modify the official score. Instructor assignments remain supplementary unless a later policy explicitly changes this.

## Progress and completion

### `progress_records`

Enrolment, content/scenario entity, state, unlocked/completed timestamps, best qualifying attempt reference, and optional audited override reference.

### `completion_records`

Immutable programme completion decision, qualifying results, policy version, completion timestamp, and whether approval was required. V1 policy sets approval required to false.

### `certificates`

Completion record, unique certificate identifier, template version, issued timestamp, status, and generated-file reference. Revocation, if later required, is a status change with an audit event rather than deletion.

## Administration and auditing

### `feedback`

Instructor feedback tied to an enrolment, attempt, response, or criterion, with visibility and timestamps.

### `audit_events`

Actor, action code, target type/id, before/after summaries where appropriate, reason, timestamp, and request correlation data. Passwords, secret values, and full sensitive documents must never be copied into audit payloads.

## Decisions deferred to content approval

- Exact Import stages, states, field requirements, and validation rules
- Theory module and lesson structure
- Question banks and final-examination composition
- Passing thresholds and attempt limits
- Competency weights and mandatory criteria
- Detailed remediation mappings
- Certificate wording and signatory

These are configuration/content decisions, not reasons to redesign the core schema.
