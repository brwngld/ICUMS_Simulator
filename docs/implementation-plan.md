# Implementation Plan

## Delivery strategy

Build one end-to-end vertical slice before expanding the curriculum. The first useful demonstration is one complete theory module followed by simulator orientation and one Beginner Import scenario. This tests the platform architecture without waiting for the final customs content.

Sample content must be conspicuously marked fictional and replaceable.

## Phase 0 — Planning approval

Deliverables:

- agreed product rules and V1 exclusions;
- architecture and database portability contract;
- conceptual data model;
- screen and navigation map;
- implementation phases and acceptance criteria;
- list of unresolved customs/content decisions.

Exit criterion: the product owner approves this planning baseline or records requested changes.

## Phase 1 — Application foundation

Deliverables:

- Django project with focused domain apps and environment-specific settings;
- configuration profiles for development, test, local production, and hosted production;
- custom Django user model, initial domain models, and Django migrations;
- SQLite foreign-key enforcement;
- user authentication, multiple roles, and authorization helpers;
- CSRF protection, secure password storage, error handling, and audit foundation;
- local production start procedure and backup/restore procedure;
- automated test and code-quality baseline.

Acceptance criteria:

- administrator, instructor, and student accounts can sign in and see only permitted areas;
- one account can hold both administrator and instructor roles;
- database can be created entirely by Django migrations;
- trusted administrators can use a secured Django Admin without exposing it as the student interface;
- tests use isolated temporary databases;
- disclaimer is visible on authenticated training pages.

## Phase 2 — Onboarding and theory vertical slice

Deliverables:

- enrolment, profile, versioned disclaimer acceptance, and roadmap;
- content models for modules, lessons, blocks, questions, and resources;
- seed/import mechanism for initial administrator/developer content;
- Django Admin configuration for initial modules, lessons, questions, resources, and publishing;
- lesson viewer, saved position, short questions, and feedback;
- module assessment and untimed final-exam capability;
- progress/unlock rules and result history;
- basic instructor content and student-progress views.

Acceptance criteria:

- a new student completes onboarding and the current disclaimer;
- the student completes one seeded theory module and its assessment;
- leaving a lesson and returning restores progress;
- failed criteria produce a targeted recommendation;
- another attempt is added without deleting the first;
- elapsed time is recorded but is absent from scoring logic.

## Phase 3 — Simulator orientation and scenario engine

Deliverables:

- orientation lesson and demonstration framework;
- versioned scenario definitions and structured validation;
- state-machine runtime with conditional available actions;
- document viewer for fictitious training documents;
- save, exit, resume, restart-policy, and action history;
- configurable Beginner/Intermediate/Advanced/Competency assistance policies;
- basic scenario administration/import tooling.
- Django Admin configuration for trusted scenario-definition management.
- reference-based practical layouts that preserve relevant ICUMS navigation and screen structure while using distinct simulator branding and colours;

Acceptance criteria:

- a student cannot enter practical training until configured theory prerequisites are met;
- one Beginner Import scenario can be completed end to end;
- action availability depends on scenario state and conditions;
- hints and checklist use are recorded;
- resuming restores the same transaction state;
- a published scenario version cannot silently change an attempt already in progress.
- each practical screen identifies its structural reference as verified, deliberately adapted, or still TBC.

## Phase 4 — Practical evaluation and remediation

Deliverables:

- criterion-level practical rubric;
- evaluation of actions, document review, decisions, errors, corrections, and assistance;
- practical result and evidence view;
- weakness-to-resource/scenario remediation rules;
- instructor feedback and basic result review;
- practical module assessment and competency mode.

Acceptance criteria:

- results explain strengths, weaknesses, and relevant evidence;
- practice assistance is reported according to policy;
- time is displayed only as informational evidence;
- failure recommends a lesson/resource and a different scenario targeting the same skill;
- evaluation data remains auditable and reproducible from the scenario version and action log.

## Phase 5 — Completion, certificate, and operational readiness

Deliverables:

- completion-policy service;
- basic competency report;
- automatically issued V1 certificate with unique identifier;
- configurable future `requires_instructor_approval` policy;
- administrator configuration and audit views;
- backup, restore, logging, deployment, and recovery documentation;
- accessibility, security, and browser checks;
- seeded demonstration dataset.

Acceptance criteria:

- only a qualifying completion record can issue a certificate;
- reloading or retrying certificate generation does not issue duplicates;
- certificate wording clearly describes simulator training;
- an administrator can back up and restore the complete local system;
- the full thin-slice user journey passes automated and manual acceptance tests.

## Phase 6 — PostgreSQL readiness gate

This gate is completed before public or institutional hosting, not necessarily before local V1 use.

Deliverables:

- PostgreSQL staging database;
- clean migration from zero using the same Django migration history;
- documented SQLite export/PostgreSQL import process;
- comparison report for migrated record counts and critical totals;
- automated test suite executed against PostgreSQL;
- concurrency and transaction review;
- hosted secrets, HTTPS, file storage, backups, and monitoring plan.

Exit criterion: the hosted application passes the same functional acceptance suite and migration reconciliation shows no unexplained differences.

## Recommended first demonstration

```text
Register/sign in
 -> Accept simulator disclaimer
 -> View roadmap
 -> Complete one fictional theory lesson
 -> Answer short questions
 -> Pass a module assessment
 -> Complete simulator orientation
 -> Perform one guided Beginner Import scenario
 -> Receive evidence-based feedback
 -> Leave and resume at least once
```

## Review checkpoints

1. Approve planning baseline.
2. Approve wireframes and visual direction before detailed UI work.
3. Approve the first theory-module content before treating assessment results as meaningful.
4. Validate the first Import scenario and consequences with a customs subject-matter expert.
5. Approve competency rubric and certificate wording before release to students.

## Content still required from the product owner or subject-matter expert

- first complete theory module and source references;
- first fictional Import transaction and document set;
- permitted reference screenshots, screen recordings, field lists, or walkthrough notes for the relevant real ICUMS screens;
- confirmed steps, statuses, rules, errors, and consequences for that scenario;
- assessment questions, accepted answers, pass thresholds, and attempt rules;
- practical competency criteria and mandatory failure conditions;
- final product name, logo, certificate wording, and signatory details.

Development can use clearly labelled placeholders until these are supplied, but placeholder customs rules must never be presented as authoritative.
