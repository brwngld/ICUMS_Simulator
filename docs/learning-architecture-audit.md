# ICUMS Simulator — Learning Architecture Audit

**Date:** 10 October 2026 · **Baseline:** commit `e4c6d92`, clean working tree, 202 tests passing, `manage.py check` clean.
**Scope:** audit only. No application code, templates, stylesheets, JavaScript, schemas, routes, or course content were modified. Nothing was committed. Verification accounts created for earlier tasks were already removed; no accounts were created or altered for this audit.

---

## Deliverable A — Current-state architecture map

### A.1 Django applications

| App | Purpose | Key models |
|---|---|---|
| `accounts` | UUID user model, groups (Student/Instructor/Administrator), simulator credentials | `User`, `SimulatorCredential` (monthly password, `is_current`, `reset_requested_at`) |
| `onboarding` | Programmes, versions, enrolments, disclaimer | `Programme`, `ProgrammeVersion` (draft/published), `Enrolment` (active/withdrawn/…), `DisclaimerVersion`, `DisclaimerAcceptance` |
| `learning` | Theory content | `Module` (order, `is_published`, `prerequisite` self-FK), `Lesson` (slug, order), `ContentBlock` (kind: text/example/notice, heading, body, order), `Resource` (M2M remediation links) |
| `assessments` | Knowledge checks and theory assessments | `Question`→`QuestionVersion`→`AnswerOption`, `Assessment` (MODULE/FINAL_THEORY, pass %, max attempts, randomize), `AssessmentItem`, `TheoryAttempt`/`TheoryAttemptItem`/`TheoryResponse`, `LessonCheck`/`LessonCheckResponse` |
| `progress` | Progress ledger | `LessonProgress` (last_position, completed_at), `ModuleProgress` (locked/available/in_progress/completed), `ProgrammeProgress` (theory_completed_at, orientation_unlocked_at, orientation_completed_at) |
| `scenarios` | Playground + guided practical engine + simulated trade records | `Scenario`, `ScenarioVersion` (module FK, assistance_mode ×4, purpose, briefing, objective, initial_data, max attempts), `ScenarioState`, `ScenarioActionDefinition` (from/to state, conditions JSON, effects JSON, success_feedback, beginner_hint), `ScenarioDocument`, `BillOfLading(+CargoItem)`, `CommercialDocument(+Line)`, `ScenarioAttempt` (current_state, state_data JSON, attempt_number unique), `ScenarioAction` (immutable per-step audit), `AssistanceEvent`, `UcrDeclaration`, `BoeDeclaration` (+`BoeSequence`/`JobSequence`), `ConsignmentApplication`, `MdaApplication/MdaProcess/MdaAgency/MdaConsignmentRequest`, `GhanaHSCode`, `CustomsRegime`, `CustomsProcedureCode`, `PortCode`, `TrainingStakeholder`, `TrainingServiceProvider` |
| `evaluations` | Practical rubrics and results | `Rubric`→`RubricVersion`→`RubricCriterion` (rule types: completion / required_actions / state_flags / assistance_limit; mandatory flag; remediation FKs), `PracticalEvaluation`, `CriterionResult`, `EvaluationRevision`, `InstructorFeedback`, `RemediationRecommendation` |
| `reports` | Completion and certificates | `CompletionPolicy`, `CompletionRecord`, `Certificate` |
| `audit` | Append-only trail | `AuditEvent` (login/logout/disclaimer/orientation/…) |
| `core` | Shared shell, dashboard, orientation, sidebar/breadcrumb dispatch | — |

### A.2 Route map (user-facing)

- **Portal shell:** `/` dashboard, `/orientation/`, `/onboarding/disclaimer/`
- **Theory route:** `/theory/` (roadmap), `/theory/<module>/<lesson>/` (stepped lesson)
- **Assessments:** `/assessments/<id>/` (take), `/assessments/attempts/<id>/` (result)
- **Practical route:** `/practical/` (scenario list), `/practical/<version>/` (detail), `/practical/<version>/start/`, `/practical/attempts/<id>/` (workspace), `…/actions/<id>/` (perform step), `…/hint/`, document/BoL/commercial PDF endpoints
- **Playground (free play):** `/practical/portal/` (simulator home + login), 81 `scenarios/urls.py` routes across Cargo (`/practical/cargo/…`), Clearance incl. BOE (`/practical/clearance/…`), Single Window incl. UCR, consignment, opt-in/out, MDA (`/practical/single-window/…`), plus access endpoints (`access/login|logout|request-reset|review…`)
- **Practical assessment:** `/practical/assessment/<application>/`
- **Results/records:** `/practical-results/<evaluation>/` (+override/feedback for instructors), `/records/completion/<id>/` (+approve), `/records/certificates/<id>/`
- **Instructor builder:** `/instructor/` (dashboard), `/instructor/courses/` (path=theory|combined), `courses/create`, `courses/<v>/` (outline), `courses/<v>/review/`, `courses/<v>/publish/`, `courses/<v>/modules/create/`, `modules/<m>/lessons/new|create`, `modules/<m>/practicals/new|create`, `students/<e>/`, credential issue
- **Auth:** `/accounts/login|logout|register|password-change`

### A.3 Delivery chain (verified in code)

`active enrolment` → disclaimer gate → roadmap (`learning/views.py:26`) → lesson steps with knowledge checks (`learning/views.py:41`, `LessonProgress.last_position`, `LessonCheckResponse`) → lesson `completed_at` → module assessment (gated on prerequisite module + all module lessons complete; pass ≥ `pass_percentage` → `ModuleProgress.COMPLETED`, `assessments/services.py:67`) → all modules complete unlocks final theory exam (`programme_theory_completed`) → pass sets `ProgrammeProgress.theory_completed_at` + `orientation_unlocked_at` (`assessments/services.py:72`) → orientation POST sets `orientation_completed_at` (`core/views.py`) → practical unlocked (`scenarios/services.py:11`) → guided attempt → terminal state → `evaluate_attempt` (`evaluations/services.py:38`) → completion record/certificate (`reports`).

### A.4 Guided practical engine (state machine)

`scenarios/services.py` — `available_actions` (actions whose `from_state` matches the attempt's current state, filtered by `conditions` against `state_data`), `start_or_resume_attempt` (orientation gate, resume-in-place, sequential attempt numbers, `maximum_attempts`), `perform_action` (`select_for_update`, ownership/scenario validation, applies `effects`, advances state, completes at terminal state, writes an immutable `ScenarioAction`, triggers evaluation), `record_hint` (assistance-mode gating, `AssistanceEvent` audit).

### A.5 Playground access model

`scenarios/views.py:48` `_has_simulator_access`: authors (staff/superuser/Instructor group) pass; students need a simulator session (`simulator_user_id`) matching a **current** `SimulatorCredential`. Login simulation: `portal.html` dialog (Student ID + monthly password) → `simulator_login` (`scenarios/views.py:139`); logout semantics by session type (`simulator_logout`); reset requests flag `SimulatorCredential.reset_requested_at` for the instructor dashboard. **Staff review mode** (`simulator_review_login/exit`, `_review_target`, `_effective_owner`, `_review_json_guard/_review_form_guard`): staff browse one student's simulator records strictly view-only.

### A.6 Simulator state

All playground records are DB-backed and per-user: `UcrDeclaration.owner` (TEMPUCR→KGHTESTUCR numbering), `BoeDeclaration.owner` (+ sequences, stages via `BoeStageEvent`), `ConsignmentApplication.owner`, MDA applications. A small amount of client-side state lives in `localStorage` (e.g. `icumsSimulatorOptRecord` in `single_window_search_opt_in_out.html`). Simulator JS lives in `static/js/` (`ucr-create.js`, `clearance-boe-create.js`, `opt-in-out*.js`, `dialog-pagination.js`, `application-form.js`, `ucr-search.js`, …). Simulator-specific CSS: `simulator-portal.css`, `cargo-page.css`, `ucr-create.css` (frozen per working agreement).

### A.7 Project documentation

`docs/` carries `architecture.md`, `data-model.md`, `screen-map.md`, `wireframes.md`, `product-rules.md`, `implementation-plan.md`, `implementation-status.md`, `practical-reference-log.md`, `mda-hs-integration-notes.md`, `security-notes.md`, `deferred-security-review.md`, `how-to-review.md`, and Word/PDF user/administrator manuals. `docs/product-rules.md` already codifies the intended content model (course / module / theory lesson / guided practical / combined module), the four assistance modes, assessment rules, and the authoring workflow — it matches this audit's terms of reference. `docs/practical-reference-log.md` records that simulator screens derive from **product-owner-supplied screenshots**, deliberately adapted — compliant with the government-website restrictions.

### A.8 Frozen boundaries (observed, respected)

Per the 2026-10-09 working agreement: theme/copy locked (AGENTS.md); simulator-owned files treated as frozen: `templates/scenarios/*` (except the three shell-based student pages `list.html`, `detail.html`, `workspace.html`, which extend `core/base_student.html`), `templates/assessment/detail.html`, `static/css/simulator-portal.css`, `static/css/cargo-page.css`, `static/css/ucr-create.css`, and the simulator JS files. `static/js/app-shell.js` is shared (also loads on simulator pages) and was previously changed only with explicit authorization.

---

## Deliverable B — Requirements comparison matrix

Status scale: **Verified** (implemented and evidenced), **Partial**, **Missing**, **Unverified**, **N/A**.

### B.1 Theory learning (`/theory/`)

| # | Requirement | Current implementation | Evidence | Status | Gap | Recommendation | Dependencies | Risk |
|---|---|---|---|---|---|---|---|---|
| T1 | Courses, modules, lessons, topics | Programme/ProgrammeVersion → Module → Lesson → ContentBlock steps | `learning/models.py`, `learning/views.py:41` | Verified | "Topics" exist as ContentBlock steps; concept exists but only 3 block kinds | Keep blocks as topics; extend kinds later | Redesign (D) | Low |
| T2 | Written explanations | ContentBlock text/example/notice bodies rendered stepwise | `lesson_detail`, `templates/learning/lesson.html` | Verified | Plain text only | Add rich text/media at redesign | — | Low |
| T3 | Instructor examples and illustrations | `example` block kind exists; **no image/diagram support anywhere** (no ImageField/media in `learning`) | `learning/models.py:43-58`, `instructor_portal/forms.py LessonCreateForm` | Partial | Illustrations cannot be uploaded or embedded | Introduce an illustration/image block kind + media handling in redesign | Media storage decision | Low |
| T4 | Knowledge checks | `LessonCheck` + `LessonCheckResponse` per block; builder creates exactly one per lesson | `assessments/models.py:139`, `instructor_portal/views.py:241` | Verified | Builder supports one check per lesson; model supports many; no editing | Allow multiple checks and editing | Builder work | Low |
| T5 | Module assessments | `Assessment(type=MODULE)`; auto-created when a lesson is saved with "add to assessment" | `instructor_portal/views.py:243-250` | Partial | No standalone "create/edit module assessment" UI; cannot add questions later except by adding lessons with the checkbox | Add assessment management to builder | Builder work | Medium |
| T6 | Lesson/module completion tracking | `LessonProgress.completed_at`; module completion **only** via passing the module assessment | `learning/views.py:80-82`, `assessments/services.py:67` | Verified | Modules without an assessment can never complete | Require/automate a module assessment at publish (see F2) | — | **High** |
| T7 | Sequential progression where configured | `Module.prerequisite` enforced in `module_is_unlocked` and at assessment time | `learning/services.py:4`, `assessments/views.py:26-29` | Partial | `prerequisite` has **no builder UI** — configurable only in Django admin | Expose prerequisite selection in builder | Builder work | Low |
| T8 | Student progress display | Roadmap module summaries (completed/lesson count, %), dashboards | `learning/services.py:13`, `roadmap.html` | Verified | Coarse (per module); no lesson-level map on one screen | Redesign opportunity (D) | — | Low |
| T9 | Drafts vs published | Version stays `draft`; publish flips modules/lessons/questions/assessments/practicals+rubrics atomically | `instructor_portal/views.py:147-173` | Verified | Publish is one-way; **no editing of published content via builder** (draft-only lookups) | Decide: content-fix flow for published versions (new version vs controlled edit) | Decision E2 | Medium |
| T10 | Resume learning | `LessonProgress.last_position` restores step; `?step=` deep links | `learning/views.py:52-57` | Verified | Steps can be skipped out of order via `?step=`; checks not required to advance | Enforce sequential stepping if configured | — | Low |
| T11 | Theory builder separated from practical model | Separate `lesson-builder` (theory) and `practical-builder` forms | `instructor_portal/views.py:197-309` | Verified | Lesson form has a fixed 3-section structure | Expand at rebuild | — | Low |
| T12 | Builder clarity | Dedicated builder at `/instructor/courses/` with theory/practical tabs, outline, review, publish | `course_builder*` views/templates | Verified | Create-only: **no edit views for lessons/modules/practicals**; no reorder UI (order = count+1); no lesson/practical preview for instructors; `prerequisite` admin-only | Builder rebuild (Roadmap stage 2) | — | Medium |
| T13 | Trace: create → publish → student completion | Verified by reading the chain and by `tests/test_theory_flow.py` (locks, foreign-programme denial, attempt limits, instructor gate) | `tests/test_theory_flow.py` | Verified | — | — | — | — |

### B.2 Practical/Theory learning (`/practical/`)

| # | Requirement | Current implementation | Evidence | Status | Gap | Recommendation | Dependencies | Risk |
|---|---|---|---|---|---|---|---|---|
| P1 | Dedicated builder page, no admin navigation | `/instructor/courses/` with `?path=theory|combined`; outline/review/publish without touching `/admin/` | `instructor_portal/urls.py`, `course_builder.html` | Verified | The original usability problem (building through advanced administration) **is solved**; remaining friction is create-only authoring, no preview | Rebuild authoring (stage 2) | — | — |
| P2 | Courses/modules/lessons/steps representation | ScenarioVersion `states` = ordered steps (+ terminal), `action_definitions` = the step transitions | `scenarios/models.py:219-270` | Verified | Steps are abstract labels; no mapping to playground screens | Guided engine v2 (stage 3) | Playground integration | High |
| P3 | Mix explanations with practical activities | `briefing` + `learning_objective` + per-state `guidance` text; theory lessons live alongside in the same module | `practical_create`, `workspace.html` | Partial | Explanation is static text in the workspace panel; cannot interleave rich content per step | Per-step instruction content in engine v2 | — | Medium |
| P4 | Demonstration mode (show the task in the playground, highlight, playback) | **Absent.** No highlighting, no demonstration playback, no pause/continue/replay | `workspace.html` (buttons only) | Missing | Whole capability missing | Build demonstration layer reusing playground pages (stage 3) | Playground integration; frozen-file permissions | High |
| P5 | Instructor specifies the action a student must perform | Text line per step → one `ScenarioActionDefinition` labelled with that line | `practical_create` `instructor_portal/views.py:287-304` | Verified | The "action" is pressing a button named after the step; not performing it in the simulator | Map step actions to real playground interactions | Playground integration | High |
| P6 | Instructor defines expected outcome | `effects={f"step_{n}_completed": True}` only; rubric rule = completion | `practical_create` | Partial | No expected values/outcomes beyond step completion; richer rules (required_actions/state_flags) exist in the model but no builder UI | Expose outcome authoring | Builder + engine | Medium |
| P7 | Automatic verification of student actions | `perform_action` validates against the state machine server-side; rubric evaluates completion/required_actions/state_flags/assistance_limit | `scenarios/services.py:50-85`, `evaluations/services.py:8-38` | **Verified (state machine only)** | Verification is of button steps, **not** of real playground form values/submissions/navigation | Extend verification to playground events | Playground integration | High |
| P8 | Retries, hints, error messages | Attempt numbering + maximum_attempts; hints by assistance mode with `AssistanceEvent`; server feedback strings; gates now redirect with messages | `scenarios/services.py:27-47,88-94`, handler403 | Verified | No wrong-answer path inside a step (an unavailable action is simply not shown) | Model failed attempts per step | Engine v2 | Medium |
| P9 | Advance to next step | Terminal-state completion; next steps become available as states advance | `available_actions`, `perform_action` | Verified | Linear only in builder-generated flows (model supports branching) | Keep model; add authoring later | — | Low |
| P10 | Instructor preview/test of a lesson | **None.** `lesson_detail`/`scenario_detail` require an active student enrolment; instructors without one cannot view their own lessons; no preview route exists | `learning/views.py:33`, `scenarios/views.py:2797-2800` | Missing | Instructors cannot see what students see | Build preview mode (impersonation-style view-only like simulator review) | — | Medium |
| P11 | Drafts editable safely | Draft-only lookups (`status="draft"`) in builder views; drafts invisible to students | `practical_create/lesson_create` lookups | Verified | No editing of existing drafts either (create-only) | Add edit flows | Builder work | Medium |
| P12 | Workflow: create → publish a practical course | courses → create draft → add module → add theory lesson(s) and/or practical(s) → review (validation issues listed) → publish (atomic flip) | `_course_issues`, `course_publish` | Verified | Publish issues don't require module assessments (see F2) | Add assessment requirement to issues | — | **High** |

### B.3 Playground

| # | Requirement | Current implementation | Evidence | Status | Gap |
|---|---|---|---|---|---|
| G1 | Simulated pages/workflows | 81 routes: Cargo (tracking-style portal home, direct delivery, service request, reference pages), Clearance (workspace, CPC search, BOE IDF lookup → create → declaration tabs → draft/submit/tax compute, searches ×3, simple-amendment, post-entry), Single Window (workspace/overview, exporter registration, preparation application, UCR create/save/submit/search/detail/clone/amend + lookups, consignment application create/search, master application, opt-in/out create/search/detail, MDA submission) | `scenarios/urls.py`, `templates/scenarios/*` | Verified | — |
| G2 | Login simulation | Dedicated simulator login (Student ID + monthly password) dialog + logout + reset request; separate from the learning-account session | `portal.html:76-79`, `simulator_login` | Verified | Deliberately "general function of the real system" ✓ |
| G3 | Authenticated vs unauthenticated states | Simulator session (`simulator_user_id`) + `is_current` credential; authors bypass | `_has_simulator_access` | Verified | — |
| G4 | Navigation between pages | Per-area sidebars (`_cargo_sidebar`, `_clearance_sidebar`, `_single_window_sidebar`) + `_portal_top_nav` | templates | Verified | — |
| G5 | Actions/forms/state changes | Real POST endpoints persist per-user records (UCR save/submit with TEMPUCR/KGHTESTUCR numbering, BOE draft/submit/tax, consignment + MDA submission with status flow, opt-in/out, service providers with owner assignment, stakeholder lookup) | `scenarios/views.py`, models with `owner` FK | Verified | Some screens remain deliberately conceptual (`reference_status`) |
| G6 | Verifiable tasks | Guided engine verifies state-machine steps; playground records (UCR/BOE/MDA) are queryable per user | services + models | Partial | Playground records are **not** wired into guided verification |
| G7 | Clean resets between attempts | Guided attempts: new attempt numbers, isolated `state_data` ✓; playground records: logout + monthly credential expiry only — **no per-user playground state reset** | `start_or_resume_attempt`, credential flow | Partial | Add instructor-triggered reset/archive of a student's playground records if needed |
| G8 | Guided lessons open playground at a defined state | **Absent** — the workspace is a separate portal page; `initial_data` exists on ScenarioVersion but seeds only abstract `state_data` | models | Missing | Core of engine v2 |
| G9 | Multiple lessons reusing pages without interference | Playground pages are stateless templates over per-user records; attempts are isolated per scenario version | models | Verified (at the records level) | — |
| G10 | Student practice vs instructor demonstration separation | Simulator staff **review mode** is view-only with write guards | `_review_target/_effective_owner/_review_*_guard` | Verified | Demonstration mode itself doesn't exist |

### B.4 Guided engine capability classification (spec §7 scale)

| Capability | Status |
|---|---|
| Demonstration: open correct simulator page | Not implemented |
| Demonstration: highlight field/control | Not implemented |
| Demonstration: step-specific instructions | Implemented and verified (state `guidance` text in workspace; not over the playground) |
| Demonstration: action sequence playback / expected result / pause-replay | Not implemented |
| Practice: reset/prepare simulator for attempt | Partial (attempt isolation yes; playground state no) |
| Practice: student performs real actions | Partial (abstract action buttons, not playground interactions) |
| Practice: demo actions don't count as student completion | N/A today (no demo actions exist) |
| Practice: stay in lesson context | Verified (workspace is self-contained) |
| Verification: check real simulator state | Partial (`state_data` JSON is engine-internal; real playground records not consulted) |
| Verification: validate form values/submissions | Not implemented (builder flows carry no expected values) |
| Verification: navigation/status checks | Partial (`state_flags` rubric rule exists; only builder sets trivial flags) |
| Verification: multi-action tasks | Verified (required_actions rubric rule + sequential state machine) |
| Verification: incorrect attempts/retries | Partial (attempt limits yes; no per-step failure path) |
| Verification: prevent premature progress | Verified (`select_for_update`, availability check, action-scenario ownership, POST-only) |
| Progression: record steps / unlock next | Verified (ScenarioAction ledger; next actions from current state) |
| Progression: resume | Verified (`start_or_resume_attempt`, "saved scenario has been resumed") |
| Progression: completion recorded reliably | Verified (terminal state → `completed_at` → evaluation, atomic) |
| Progression: opening ≠ completing | Verified (opening the workspace awards nothing; only terminal actions complete) |

### B.5 Cross-cutting

| # | Requirement | Status | Evidence / notes |
|---|---|---|---|
| C1 | Enrolment links progress to course/module/lesson/steps | Verified | All progress models FK to `Enrolment`; attempt rows FK enrolment + version |
| C2 | URL bypass of required steps | Partial — lesson steps skippable via `?step=` (position clamps, `last_position=max`), knowledge checks not required correct; **module, final-exam, orientation and practical gates hold** | `learning/views.py:52-87`, `assessments/views.py` |
| C3 | Duplicate/inconsistent records | Verified-safe at the schema level (unique constraints on attempts, action sequences, progress rows). Minor: `get_or_start_attempt` (theory) and `start_or_resume_attempt` (scenario) don't `select_for_update`; a simultaneous double-submit could raise a 500 via the unique constraint instead of returning the existing attempt | `assessments/services.py:11-31`, `scenarios/services.py:27` |
| C4 | Course edits vs students in progress | Verified-safe by restriction: published versions are immutable through the builder (draft-only lookups); consequently there is also **no way to fix published content** without admin | `course_builder_detail/lesson_create/...` |
| C5 | Progress recovery | Verified — lesson position and attempts resume | — |
| C6 | Completion logic trustworthy | Verified with two caveats: (F1) lesson steps/checks skippable; (F2) assessment-less module blocks the chain (below) | — |
| C7 | Roles/permissions | Verified — re-checked after the recent separation work: staff/superuser admin gated by `AdminSuperuserGateMiddleware`; instructor portal via `_require_instructor` + Instructor group; simulator credentials + review mode view-only; gates now message+redirect via `handler403` (`core/views.py`); tests `test_admin_portal_separation.py`, `test_portal_403_redirect.py` | — |
| C8 | Government-website restrictions | Verified-compliant — simulator screens derive from product-owner-supplied material, deliberately adapted (`docs/practical-reference-log.md`); no scraping/automation anywhere; fictional data throughout | — |
| C9 | Credentials/data handling | Verified — simulator passwords hashed on `SimulatorCredential` (`matches()`), one-time reveal, monthly expiry, reset requests; no secrets in repo | `accounts/models.py` |

### C6-F2 (cross-reference) **Progression dead-end:** `_course_issues` (`instructor_portal/views.py:105-125`) does not require a module assessment, and the only code path that sets `ModuleProgress.Status.COMPLETED` is passing a module assessment (`assessments/services.py:65-68`). A published module with no assessment (instructor unchecks "add to assessment", or adds no assessment) leaves `programme_theory_completed` permanently false → the final exam, orientation and **all practicals** are unreachable for that cohort. This is the single most important functional gap found.

### B.6 Tests

202 tests / 21 files, all passing at baseline. Coverage map: theory journey + gates (`test_theory_flow.py`, 10), guided engine (attempts, hints, assistance modes, completion — `test_scenario_engine.py`), playground records (UCR `test_ucr_lookup.py`, BOE `test_boe_*.py` ×4, MDA/consignment `test_mda_submit.py`, `test_consignment_application_mda.py`), completion/certificates (`test_completion_records.py`), assessment rules (`test_assessment.py`), admin enrolment (`test_admin_enrolment.py`), portal chrome/uniformity (`test_admin_portal_uniform_ui.py`, `test_mda_uniform_ui.py`, `test_ucr_uniform_ui.py`, `test_navigation_uniformity.py`, `test_admin_portal_separation.py`, `test_portal_403_redirect.py`, `test_changelist_page_size.py`), local serving/accessibility (`test_local_serving_accessibility.py`, `test_foundation.py`).

**Gaps:** no tests exercise the **builder form flows** (`lesson_create`, `practical_create` — content generation, question/state generation, publish issue list); no tests for the `?step=` skip behaviour; no demonstration/integration tests (capability absent); playground JS behaviour (client-side) is untested by design (backend endpoints are covered).

---

## Deliverable C — Prioritized implementation roadmap

**Stage 0 — Guard-rails for the existing chain (essential, small)**
1. Make `_course_issues` require each module to have a module assessment (or auto-create one at publish), and surface a clear review warning (fixes F2).
2. Add `select_for_update`/`get_or_create`-style safety to both attempt starters (prevents rare duplicate-attempt 500s).
3. Optionally enforce in-order lesson stepping when a module is marked sequential.
*These are small, testable, and remove a cohort-blocking trap before any redesign.*

**Stage 1 — Course-builder usability (essential)**
4. Edit flows for lessons, knowledge checks, modules, and draft practicals (currently create-only).
5. Reorder controls (modules/lessons) and prerequisite selection (moves admin-only configuration into the builder).
6. Instructor preview of lessons and guided practicals (view-only, reuse the simulator review pattern).
7. Standalone module-assessment management (add questions without re-creating lessons).

**Stage 2 — Guided demonstration-and-practice engine (the major build, depends on decisions E1–E3)**
8. Define a step-to-playground binding model (screen + control + expected value/submission), reusing existing playground routes and per-user records as the verification substrate.
9. Demonstration mode over the real playground pages (highlight, step instructions, playback), student-practice mode with isolated attempt state, and verification of real form values/submissions against `ScenarioActionDefinition` conditions/effects (the existing state machine, rubric rules, attempt ledger, and assistance modes are reused unchanged).
10. Per-step failure/retry path and feedback.

**Stage 3 — Student-portal redesign (per Deliverable D; after or alongside Stage 2 for the practical workspace)**

**Stage 4 — Regression and verification**
11. New tests for builder flows and engine-playground integration; re-run the frozen-simulator suites; accessibility and responsive passes at 1440/768/390/320.

Essential vs optional: items 1–2, 4, 8–9 are essential to the stated vision; 3, 5–7, 10 are high-value enhancements; branching scenario authoring and conceptual-to-validated screen upgrades are optional later phases.

---

## Deliverable D — Student-portal redesign proposal (design only)

**D.1 Page inventory (current).** Dashboard `/`; disclaimer; orientation; roadmap `/theory/`; lesson stepper; assessment take/result; scenario list/detail/workspace; simulator portal + 20+ playground screens; results `/practical-results/<id>/`; records `/records/…`; certificate; profile-equivalent (account links only — **no profile/settings page exists**). Empty states exist (dash-empty); there are no loading or error-state patterns beyond the message banner.

**D.2 Navigation structure (proposed).** Keep the three destinations the sidebar now always shows — **Theory**, **Practical/Theory**, **Simulator sandbox** — as first-class sections with distinct landing pages: Theory = module map with progress rings and resume affordance; Practical = course-scenario cards with attempt state and assistance mode; Sandbox = the existing playground portal unchanged. Add a persistent "Continue where you left off" card on the dashboard (lesson step or attempt already supports resume). Keep breadcrumbs (recently added) and the disclosure-based mobile drawer.

**D.3 Visual system (proposed).** Evolve the existing `.dash` token set (already the shared student/instructor vocabulary, light+dark tokens defined) rather than introducing a new framework: one card/panel language, one type scale (Unfold's `--text-*`), the locked indigo accent for primary actions, semantic pills for status (is-ok/is-warn/is-info already exist), consistent 0.75rem-radius surfaces. Light mode gets its own elevation treatment (borders + subtle shadow + tinted page background) so it is not "dark mode minus colour". Dark mode tokens already mirror the admin reference and stay as-is.

**D.4 Theory lesson layout (proposed).** Two-pane reading view on desktop: content column (block-stepped as today, with the knowledge check inline at its block) + a slim progress rail (blocks as ticks, checks as answered/correct icons). Footer = Back / Check / Continue with explicit completion semantics ("Mark complete" on the last step). Illustrations get a real block kind with figure/caption styling.

**D.5 Practical/Theory lesson layout (proposed).** Keep the proven three-pane workspace (workflow list | instruction+action pane | documents) but make the instruction pane step-scoped (briefing → current step explanation → expected outcome), reserve a dedicated **simulator frame** region into which guided steps will open the existing playground pages (Stage 2), and surface hints/feedback inline. Status, attempt number, and assistance mode remain visible in the head.

**D.6 Playground integration (proposed).** Guided steps link/embed the existing playground routes in a constrained context (banner "Guided lesson — step 3 of 6", exit-to-workspace); completion is still granted only by the server-side state machine, so free play remains untouched and unrestricted.

**D.7 Responsive behaviour.** Breakpoints already in the shell (60rem workspace collapse, 40rem stacking) carried through; the three-pane workspace collapses to an accordion (workflow / instructions+actions / documents); all tables scroll locally within their panels (already the pattern in `dash-table` panels); simulator screens keep their own responsive rules (frozen). Verify at 1440/768/390/320.

**D.8 Reusable components.** `.dash-*` system (panels, cards, pills, tables, steps, actions, callouts), unfold header/sidebar chrome, breadcrumbs registry, message banner, icon set (`components/icon.html`), mobile drawer. New components needed: progress ring/rail, step timeline, simulator frame wrapper, empty/error state cards, media/figure block.

**D.9 Files likely to require modification (implementation phase, not now).** `templates/core/base_student.html` (design tokens), the eleven dash templates, `static/css/app.css` (portal-only sections), possibly a new `static/css/portal.css`; no simulator-owned files; no builder templates except where Stage 1/2 work touches them.

---

## Deliverable E — Risks and decisions requiring approval

1. **E1 (architecture):** How should guided steps bind to playground interactions — embed playground pages in the lesson (iframe/fragment) vs. open-in-context with return? This decision shapes the engine build, the frozen-file boundary (simulator templates may need additive hooks), and verification design. *Recommend embedding-lite (link-out with constrained banner first, deepen later).*
2. **E2 (content lifecycle):** Published courses are currently immutable via the builder. Approve either (a) versioned supersession (new draft version, progress mapped by content IDs) or (b) controlled edits to published content with an audit event. Affects Stage 1.
3. **E3 (verification depth):** Should step completion ever require exact form values from the playground (strict verification), or is action/submission-level verification sufficient for V2? Affects data model (`conditions`/`effects` already support values).
4. **E4 (progression rule):** Confirm the intended rule that a module assessment is **required** for module completion (Stage 0 item 1 makes it mandatory at publish). Existing courses in the DB may need a data fix.
5. **E5 (frozen boundary):** Stage 2 will require additive hooks inside simulator-owned templates/JS for highlighting and step context. Per the standing rule, no such change happens without explicit sign-off of the exact files and approach.
6. **E6 (minor, noted):** `get_or_start_attempt`/`start_or_resume_attempt` race (double-submit → rare 500 via unique constraint). Small fix, listed in Stage 0; no decision needed, flagged for completeness.

No other unresolved decisions were found that materially affect architecture, security, or usability; where the implementation already establishes a valid pattern (separate builders, state-machine verification, assistance modes, simulator credential model, review-mode view-only), this audit recommends preserving it.

---

## Completion check

This audit establishes: what the application does today (A); how both learning routes actually work, end to end (A.3, B.1–B.2); that the dedicated builder does solve the original "authoring through advanced administration" problem while leaving create-only authoring, no preview, and admin-only sequencing as the remaining friction (B.2/P1, P10, T7, T12); that the playground already provides the screens, login simulation, per-user state, and view-only review the guided engine needs (B.3); exactly which guided capabilities are missing — demonstration over the playground and real-interaction verification — versus the parts that are genuinely solid (state machine, attempts, rubrics, assistance); how progress and completion are verified, including the one cohort-blocking gap (F2) and the minor bypass/race caveats (B.5); what must be preserved (frozen simulator surfaces, permission model, separate builders, assistance modes); how the student portal should be redesigned (D); and the order of implementation (C) pending the five decisions in (E).
