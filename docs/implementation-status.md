# Implementation Status

## Verified on 6 September 2026

The current implementation passes Django's system checks, has no ungenerated model changes, and passes 39 automated tests.

## Phase 1 foundation

- Django 5.2 LTS project on Python 3.12
- Custom UUID-based user model established in the first migration
- Student, Instructor, and Administrator groups created by data migration
- Multiple roles per user
- SQLite local configuration and PostgreSQL production configuration
- Separate local, test, and production settings
- Authentication, authorization baseline, CSRF protection, and security headers
- Persistent training-simulator notice
- Append-only audit-event model with login, logout, and disclaimer-acceptance events
- Secured Django Admin foundation
- Git repository and dependency records
- Local setup documentation

- Production-style same-computer serving through Waitress and WhiteNoise
- Loopback-only binding to prevent accidental network exposure

## Phase 2 theory vertical slice

- Versioned programmes and enrolments
- Versioned, auditable simulator disclaimer acceptance
- Ordered, published theory modules and lessons
- Structured lesson content blocks and linked remediation resources
- Student dashboard and learning roadmap
- Sequential prerequisite support
- Saved lesson completion
- Block-by-block lesson navigation and saved position
- Embedded knowledge checks with immediate explanatory feedback and append-only responses
- Versioned objective questions and answer options
- Untimed module and final-theory assessment types
- Programme-level assessment authorization
- Assessment locking until all published module lessons are complete
- Append-only numbered attempts and individual responses
- Question sets frozen when an assessment attempt begins
- Optional randomized question ordering retained in the frozen attempt
- Configurable maximum-attempt policy
- Elapsed-time recording that is excluded from scoring
- Automatic pass/fail evaluation and module completion
- Remediation-resource display for incorrect responses
- Final-theory examination locked until all published modules are complete
- Successful final-theory examination unlocks simulator orientation
- Recorded orientation completion
- Purpose-built instructor progress and attempt-review screens
- Published lesson, module, question-version, and assessment records protected from editing through Django Admin
- Django Admin content management
- Repeatable fictional demonstration-content command

## Phase 2 refinements still available

- Multiple-answer and manually reviewed short-response questions
- Rich instructor feedback and remediation-assignment forms
- Question-bank selection rules in addition to ordering randomization
- Additional publishing validation and a formal content-version duplication workflow
- More detailed student profile/onboarding fields once requirements are confirmed
- Product-owner-approved theory content replacing fictional placeholders

## Next recommended implementation increment

Review the complete fictional theory, guided practice, independent competency, and certificate journey in the browser. The next implementation gate is Phase 6 PostgreSQL and hosted-deployment readiness. Actual ICUMS-like practical layouts remain blocked on permitted reference material or subject-matter-expert walkthroughs.

## Phase 3 practical engine

- Versioned scenarios with draft, published, and retired states
- Beginner, Intermediate, Advanced, and Competency assistance modes
- Conceptual, verified, adapted, and TBC reference-status labels
- Declarative scenario states, conditions, effects, and actions without executable authored code
- Exactly one initial state per scenario version
- Fictitious structured documents with learner-visible and evaluator-only data separation
- Orientation-gated access to practical training
- Save/resume through persistent in-progress attempts
- Validated state transitions and rejection of out-of-sequence actions
- Conditional parallel actions alongside the main workflow
- Append-only action evidence with before/after states
- Recorded hint usage and mode-based hint restrictions
- Automatic completion on a terminal state
- Read-only attempt, action, and assistance evidence in Django Admin
- Practical-attempt visibility in the instructor student view
- Repeatable fictional guided Import scenario seed command
- End-to-end automated gate-out test including parallel shipping-line work
- First screenshot-informed practical workspace shell with deliberately different simulator branding and colours
- Responsive left navigation, tracking area, service shortcuts, reference panels, fictional rates, notices, and activity chart
- Frontend-only prototype access without programme/orientation gating or separate practical credentials during workflow discovery

## Phase 3 limitations

- The seeded Import workflow is illustrative, not an authoritative customs rule.
- The practical layout is conceptual and not yet structurally validated against real ICUMS references.
- Structured document displays are implemented; PDF/image document viewing comes later.
- Practical attempt limits are configurable; more detailed restart/abandonment policies remain future work.
- Practical screen structure remains conceptual.

## Phase 4 practical evaluation

- Versioned scenario-specific rubrics and ordered competency criteria
- Accuracy, document review, procedure, decision-making, correction, assistance, and completion dimensions
- Declarative completion, required-action, state-flag, and assistance-limit rules
- Configurable points, mandatory criteria, and pass threshold
- Automatic evaluation when a scenario reaches its terminal state
- Criterion-level evidence, score, result, and learner-facing feedback
- Strength/weakness presentation through passed and unmet criteria
- Informational elapsed time explicitly excluded from scoring
- Remediation links to theory resources and alternative scenario versions
- Demonstration-rubric warning to prevent provisional policy becoming official
- Instructor feedback with student-visible and private-note options
- Audited instructor pass/fail revisions that preserve the original system outcome
- Practical Practice, Module Assessment, and Competency Assessment classifications
- Competency-mode validation and configurable practical attempt limits
- Student result view and instructor evaluation access

## Phase 4 decisions still TBC

- Approved practical criteria, weights, pass percentage, and mandatory failures
- Whether particular uses of assistance affect a formal competency decision
- Approved remediation mappings
- Which practical assessments require instructor approval
- Exact competency-report language and sign-off requirements

## Phase 5 completion and operational readiness

- Browser-based student creation and enrolment through Django Admin
- Automatic Student-role assignment and recorded enrolling administrator
- Separate conceptual Import competency scenario that cannot show hints
- Programme-level completion policy with a future instructor-approval switch
- Completion gated by orientation, passed final theory, and passed competency practical
- Immutable theory/practical evidence and policy snapshots on the completion record
- Idempotent certificate generation with unique certificate numbers
- Clearly labelled simulator-training certificate and printable browser view
- Student dashboard link to the training record and certificate
- Instructor approval service, screen action, and audit event when policy requires it
- Read-only completion and certificate records in Django Admin
- Local SQLite database and uploaded-media ZIP backup command
- Explicit-confirmation restore command with a pre-restore database safety copy
- Production-style loopback serving through Waitress with collected static assets served by WhiteNoise
- Automated semantic checks for language, main landmark, one primary heading, labelled login controls, and a keyboard skip link
- Visible keyboard focus styling for links, buttons, inputs, selects, text areas, and programmatic focus targets

## Phase 5 decisions still TBC

- Final product name, visual identity, certificate wording, signatures, and verification method
- Whether instructor approval should be enabled for the first production cohort
- Retention, revocation, and re-issue policies
- Formal assisted-technology acceptance testing on deployment hardware
