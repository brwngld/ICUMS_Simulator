# Theory & Practical — Existing-System Capability and Integration Inventory

Read-only investigation of the repository as it stands. Nothing in this document changes code, templates, CSS, JavaScript, migrations, configuration or database records. The only file written for this report is this one.

Baseline: branch `feat/theory-experience-faithful`, HEAD `bf08419` ("Fix narrow dashboard overflow and landmarks"), working tree clean, 103 commits ahead of `main`. Date of investigation: 2026-10-29.

## Evidence conventions

Each claim carries one of these markers.

- ★ **author-verified** — read or executed by the author of this report during this investigation (source reads, read-only SQL, and the browser sessions described in §7.6).
- ○ **research-verified** — gathered by four read-only research passes over the source with file:line citations; the author spot-checked the load-bearing ones but not every line.
- **T** — asserted by a test in `tests/`, not independently re-run for this report.
- **B** — observed in a browser against a *copy* of the development database (`local_data/db_browser_check.sqlite3`, since deleted); not observed against `local_data/db.sqlite3`.
- **D** — a repository document's statement, not current code.
- **?** — inference from structure; flagged as an assumption.

Where code and an existing document disagree, the code is reported and the document is cited as **D**.

---

## 1. Executive summary

1. **The journey runtime has never run against the development database.** ★ Two of the tables the Stage-3 verification path depends on do not exist there — `hybrid_simulatorrecordcreation` and `hybrid_journeyverificationevidence` — because `hybrid/0006`, `hybrid/0007` and `hybrid/0008` are the only three of 97 repository migration files that are unapplied to `local_data/db.sqlite3`. Until those are applied, opening a journey-bound lesson on that database cannot attribute a record or write evidence.
2. **The hybrid content in that database is nearly empty.** ★ Read-only counts: 5 courses, 2 modules, 2 lessons, 2 practical steps, 3 verification conditions, 1 journey with **0** journey steps, 0 record roles, 0 lesson attempts, 0 step events, 0 record associations. The integrated builder is implemented and tested but effectively un-authored in the real local data.
3. **A complete older guided-practice engine exists, is populated, and is reachable.** ★ `scenarios/services.py:57` writes an ordered action sequence (`ScenarioAction`, `scenarios/models.py:500-515`) per attempt; the development database holds 12 action definitions, 3 attempts, 7 recorded actions and 6 assistance events, and the student sidebar's "Practical" entry points at `scenario-list` (`core/admin_dashboard.py:257`, `core/views.py:68`). It is a second, parallel answer to the same product problem the hybrid builder solves.
4. **Nothing in the repository captures a user's interaction with the simulator.** ○ No browser-side capture, no navigation tracking, no per-field logging, no recorder, no replay, no video. The only automatic capture is the record-creation ledger, and it fires on `post_save` of a record, not on an action.
5. **Verification can prove an outcome and one navigation fact — nothing finer.** ★ The engine supports exactly two condition kinds, `saved_record` and `screen_opened` (`hybrid/models.py:192-194`). `screen_opened` passes on the server's own opening row (`hybrid/journey_verification.py:414`); `saved_record` compares saved columns of an attributed record. No condition can currently distinguish "the learner chose IM, Import" from "the saved record's regime column reads IM".
6. **The proposed instructor-demonstration feature has no existing recorder to build on, but it does have four reusable pieces**: an ordered action-sequence table with an unused payload column, an approved-screen route registry, a per-field selector convention on one screen, and a server-side freshness stamp that already proves "this page was opened by this student at this moment".
7. **Students are not shown the instructor's expected values.** ★ `expected_fields` appears in no student template, and `VerificationCondition.describe()` (`hybrid/models.py:238-244`) deliberately emits only the required status label — the "A UCR declaration saved as "Draft"" line seen in the browser. There is no per-lesson or per-condition toggle; hiding is a property of `describe()`, which matters for the proposed "choose which expected values are hidden" capability.
8. **Attempts are pinned to an edition for life.** ★ `Enrolment.programme_version` is `PROTECT` (`onboarding/models.py:128`) and publishing a new edition copies no learner state (`hybrid/publishing.py:253-339`); a newly published edition never moves an in-flight attempt.
9. **Instructor access is one helper, and it is applied everywhere.** ○ `_require_instructor` (`instructor_portal/views.py:64-66`) is imported and called on every hybrid instructor route (`hybrid/instructor_views.py:289, 401, 489, 566, 700, 776, 817`); Django admin is separately superuser-gated (`core/middleware.py:6-24`). Enrolment creation and credential issue are the operations an ordinary instructor cannot do.
10. **The test suite is green against an in-memory database that does have those migrations.** ★ `.venv/Scripts/python.exe -m pytest tests -q` → 1 failed, 1035 passed (2026-10-29 run; `pytest.ini:2` pins `config.settings.test`, which uses `:memory:` SQLite and applies every migration from zero). The single failure is a copy/test wording mismatch, §2.7.

---

## 2. Current system architecture

### 2.1 Stack ○ ★

Python 3.12.10, Django 5.2.18 ★. Pinned dependencies: `nh3==0.3.7` (rich-text sanitizer, used at `learning/rich_text.py:14,57`), `reportlab`, `waitress`, `whitenoise`, `django-unfold==0.108.0` (`requirements.txt:1-6`; the only third-party UI app, `config/settings/base.py:25`). PostgreSQL driver is production-only (`requirements-production.txt:2`); tests use `pytest==9.1.1`, `pytest-django==4.14.0`.

Settings split: `base.py` (DEBUG False, `ALLOWED_HOSTS = []`, `config/settings/base.py:21-22`), `.local` (DEBUG True, localhost hosts, file SQLite with `timeout 20`, `local.py:5-15`; imported by default at `config/settings/__init__.py:3`), `.test` (hard-coded key, `:memory:` SQLite, MD5 hashers, DummyCache, `test.py:5-17`), `.local_production` and `.vps` (WhiteNoise/`STORAGES`; `vps.py:12` still inherits `.local`, so the live host is SQLite), `.production` (PostgreSQL from four required env vars, `production.py:18-32`).

### 2.2 Installed first-party apps and what they actually do (`config/settings/base.py:32-44`) ○

| App | Responsibility | State |
|---|---|---|
| `accounts` | custom `User` + `student_id`, `SimulatorCredential`, notifications, preferences | IMPLEMENTED |
| `audit` | `AuditEvent` append-only log | IMPLEMENTED, security events only |
| `core` | dashboards, sidebar, root pages, admin gate middleware; no models, 0 migrations | IMPLEMENTED |
| `onboarding` | Programme, ProgrammeVersion, Enrolment, disclaimers | IMPLEMENTED |
| `learning` | the legacy Theory builder and delivery — **this is the app mounted at `/theory/`**; there is no app named `theory` ★ | IMPLEMENTED, 93 lessons in dev DB ★ |
| `assessments` | questions, versions, assessments, theory attempts, lesson checks | IMPLEMENTED, 29 attempts ★ |
| `progress` | lesson/module/programme completion rows | IMPLEMENTED |
| `instructor_portal` | instructor roster + theory/practical authoring UI; no models | IMPLEMENTED |
| `scenarios` | the simulator: ~40 models, declarations and the older guided-scenario engine | IMPLEMENTED (engine partly LEGACY) |
| `evaluations` | rubrics and practical scoring, `/practical-results/` | IMPLEMENTED, bound to `ScenarioAttempt` |
| `reports` | completion records and certificates, `/records/` | IMPLEMENTED, bound to the theory path |
| `assessment` (singular) | one legacy consignment-application detail route + tax computation, `/practical/assessment/` | LEGACY, 1 route |
| `hybrid` | the Theory & Practical system: courses → lessons → journeys → verification | IMPLEMENTED, un-authored in dev data ★ |

### 2.3 URL structure ○ (`config/urls.py:28-52`)

`/admin/` · `/accounts/` (7) · `/onboarding/disclaimer/` (1) · `/theory/` → learning (6) · `/assessments/` (2) · `/instructor/` → instructor_portal (51 + 1 include) · **`/instructor/hybrid/`** → hybrid instructor (7, mounted through `instructor_portal/urls.py:9`) · `/practical/` → scenarios (88) · `/practical/assessment/` → the legacy `assessment` app (1) · `/practical-results/` → evaluations (3) · `/records/` → reports (3) · `/hybrid/` → hybrid student (10) · `/` → core (3).

Two `practical/` includes exist at `config/urls.py:43-44` for different apps; list order plus disjoint converters (`scenarios/urls.py:94` takes `<uuid>`, the assessment app takes `assessment/<int>`) means both still resolve. No first-party `urls.py` declares `app_name`/namespace, so every route name is flat and global. ★ `/practical/` itself (`path("", scenario_list)`, `scenarios/urls.py:93`) is the legacy scenario list, not a simulator home page. There is also a deliberately throwaway spike at `/test` and `/test/` (`config/urls.py:34-35`, `scenarios/desk.py:431`).

### 2.4 Migration status: repository versus database ★

Read-only query (`sqlite3` on `file:local_data/db.sqlite3?mode=ro`, `SELECT app,name FROM django_migrations`) diffed against `*/migrations/0*.py`: 97 first-party files, 94 applied, exactly three unapplied —

```
hybrid 0006_simulatorrecordcreation
hybrid 0007_journeyrecordassociation_unique_active_created_in_journey_claim
hybrid 0008_journey_verification_evidence
```

and the corresponding tables are absent (`sqlite_master` check). `docs/instructor-builder-consolidation-delivery-2026-10-29.md:16` records the same gap **D**. Consequence: the creation ledger, the unique active-claim constraint and journey evidence rows exist in code only; the local runtime cannot serve those paths. A stray root-level `db.sqlite3` also sits beside the real `local_data/db.sqlite3` ★ (?).

The production/VPS database is not reachable from this machine: `production.py:18-32` reads four required env vars, none of which are set anywhere in the tree; `.env.example` points at `config.settings.vps` on `customsclearancepractice.com`, which still uses SQLite. No connection was attempted.

### 2.5 Data model relevant to training ○

- `onboarding`: Programme `:7`, ProgrammeVersion `:92` (unique programme+version `:106`), Enrolment `:113` (unique per student+version `:134`, `enrolled_by`), DisclaimerVersion `:140`, DisclaimerAcceptance `:155`.
- `accounts`: User `:13`, StudentIdSequence `:40`, SimulatorCredential `:62` (hash-only password, `is_current` `:79`, `password_state` `:84`), Notification `:137`, UserPreference `:168`; the Student/Instructor/Administrator groups are created by `accounts/migrations/0002_create_roles.py:10`.
- `hybrid`: HybridCourse `:48` → HybridModule `:74` → HybridLesson `:100` (all pinned to a ProgrammeVersion), PracticalStep `:133`, VerificationCondition `:182` (`expected_fields` JSON `:210`), LessonAttempt `:250`, StepEvent `:285`, PracticalJourney `:332`, JourneyStep `:386`, JourneyRecordRole `:425`, JourneyDependency `:458`, JourneyAttempt `:531`, JourneyRecordAssociation `:590`, JourneyConditionBinding `:683`, SimulatorRecordCreation `:720`, JourneyVerificationEvidence `:769`.
- `scenarios`: the engine (Scenario `:151`, ScenarioVersion `:167`, ScenarioState `:219` with `binding` JSON `:228`, ScenarioActionDefinition `:245`, ScenarioAttempt `:477` with `state_data` `:490`, ScenarioAction `:500`) plus the declarations the hybrid engine verifies (UcrDeclaration `:518`, ConsignmentApplication `:850`, MdaConsignmentRequest `:990`, BoeDeclaration `:1102`), reference data (HS codes, regimes, procedure codes, ports, offices, MDA agencies/applications/processes, stakeholders, providers), documents (BillOfLading `:308`, CommercialDocument `:402`, UcrDocumentAttachment) and `AssistanceEvent` `:1050`, `BoeStageEvent` `:1144`.
- `learning`: Course `:10`, Module `:46`, Lesson `:83`, ContentBlock `:102`, RichTextImage `:123`, Resource `:138`. `assessments`: Question/QuestionVersion/AnswerOption/Assessment/AssessmentItem/TheoryAttempt/TheoryAttemptItem/TheoryResponse/LessonCheck/LessonCheckResponse (`:10-170`). `evaluations`, `progress`, `reports`, `audit` as listed in §2.2.

### 2.6 `is_published` — a correction to a prior note ○ ★

`is_published` is *both* written by a publication sweep and read as a live visibility filter. The sweep flips course/module/lesson in one pass (`hybrid/publishing.py:238-245`) and the hard gate is edition-level journey integrity (`:224-231`), but student queries do filter on it (`hybrid/services.py:50,70`; `hybrid/views.py:181-183,203-218`; `assessments/views.py:41`; `core/views.py:40`). There is no single place where visibility is decided. **A stored project note claiming it is only a sweep marker is out of date for hybrid.**

### 2.7 Tests ○ ★

Layout: `pytest.ini:4` sets `testpaths = tests`; 82 files and 1024 `def test_` there, while app-level `tests.py` files are near-empty stubs (accounts 4, core 4, instructor_portal 7, scenarios 2, others 0). Command `.venv/Scripts/python.exe -m pytest tests -q`, ~120 s. Author's run on 2026-10-29: **1 failed, 1035 passed** ★. The failure is `tests/test_admin_enrolment.py::test_monthly_password_is_hashed_and_shown_once`, which asserts `b"shown once"` in the dashboard (`:101`) while the issuing path leaves the credential in `awaiting_reveal` (`accounts/models.py:93` sets `revealed_at = None`) and that branch renders "the student views it once on their credential page" (`templates/instructor_portal/dashboard.html:94`) — a wording mismatch, not a security regression ○. **T** Coverage relevant to this report: `test_hybrid_builder.py` 57, `test_stage2_journey_publication.py` 30, `test_stage3_attribution.py` 21, `test_stage3_creation_ledger.py` 17, `test_guided_simulator_binding.py` 21, `test_hybrid_record_confirmation.py` 24, `test_acceptance_instructor_to_student.py` 4. `docs/instructor-builder-consolidation-delivery-2026-10-29.md:17` still quotes "1 failed, 977 passed" **D** — stale.

---

## 3. Instructor workflow map

### 3.1 Programme, editions, publication, enrolment ○ ★

`Programme` is the stable container; `ProgrammeVersion` is the edition with status draft/published/retired (`onboarding/models.py:93-96`). Theory publication flips modules/lessons/questions/assessments/scenarios in one pass and holds back unready modules (`instructor_portal/views.py:634-673`); hybrid publication is partial at course level and all-or-nothing on journey integrity (`hybrid/publishing.py:204-250`). **Publishing touches no enrolment row**: `clone_to_draft` states "every existing enrolment keeps its pinned version" (`publishing.py:253-260`), and retiring a version does not revoke access because `active_enrolments` filters enrolment status only (`onboarding/services.py:28`).

Enrolment is **admin-created only**: `EnrolmentAdmin.save_model` sets `enrolled_by`, adds the Student group and audits (`onboarding/admin.py:28-41`), deletion is forbidden (`:43-44`); registration creates a user and group but no enrolment (`accounts/views.py:32-61`). Instructors may withdraw but not create (`instructor_portal/views.py:2132-2141`). Multi-programme enrolment is allowed and **two editions of one programme are allowed** (the unique constraint is per `programme_version`, `onboarding/models.py:134`); an ambiguous request resolves to the **oldest active enrolment on that track**, ordered `("enrolled_at","pk")`, with `?programme=<code>` overriding (`onboarding/services.py:28-52`) and `programme_href` adding the parameter only when more than one enrolment exists (`:66-102`).

Difficulty: `Programme.Difficulty` and `Module.Difficulty` are badge-only (`onboarding/models.py:67`; `learning/models.py:60-65`; rendered at `templates/learning/roadmap.html:18`). `Course.difficulty` is the real gate: `level_states` opens each level only when every required published course at the previous level is complete (`learning/services.py:136-225`), enforced at `learning/views.py:252-253,503-504,529-530` and `assessments/views.py:44-45`. `Module.prerequisite` (`learning/models.py:73`) is enforced by `module_is_unlocked` (`learning/services.py:22-29`). **Hybrid has no difficulty ladder and no cross-course lock** ★ (no `difficulty`/`level_states` hits in `hybrid/*.py`); its only sequencing is within a module — "Finish the previous lesson before opening this one" (`hybrid/services.py:43-65`, enforced at `hybrid/views.py:188-189`).

### 3.2 The authoring surfaces, and how many transitions each takes ○

| Surface | Route root | Purpose | Data written | Duplicates |
|---|---|---|---|---|
| Theory & Practical builder | `/instructor/hybrid/` (`hybrid/instructor_urls.py:11-17`, 7 routes) | Programme → course → module → lesson, four-stage editor, activity cards, roles, review & publish | HybridCourse/Module/Lesson/PracticalStep/VerificationCondition/roles/bindings | supersedes the older instructor theory builder for hybrid content |
| Instructor theory builder | `/instructor/` (51 routes) | legacy learning.Course/Module/Lesson/ContentBlock, questions, assessments, scenarios, publishing | learning + assessments + scenarios | separate hierarchy from hybrid |
| Journey Organizer | `/instructor/hybrid/journeys/<uuid>/` (`hybrid/instructor_views.py:700-776`) | course-wide step order, roles, dependencies, structural issues | JourneyStep/JourneyRecordRole/JourneyDependency | overlaps the activity card's bind/create-role action |
| Lesson preview | `/instructor/hybrid/lessons/<uuid>/preview/` (`hybrid/instructor_urls.py:12`) | the real workspace, draft content, no attempt, no writes | nothing | — |
| Django admin (superuser only) | `/admin/` | reference data, enrolments, scenario definitions, declarations | everything | — |

The current four-stage editor: `hybrid/instructor_views.py:566-680` renders `templates/hybrid/lesson_editor.html` with stages Lesson Details, Theory & Guidance, Practical Activities, Review & Publish (tabs at `:7`, deep link `?tab=activities#activity-<pk>` at `:172`). An activity card holds the step's instruction/outcome/hint/screen plus its verification conditions inline (`save_activity` at `:649-661` through `StepForm`/`VerificationConditionForm`, `hybrid/forms.py:197-301`), and binds a saved-record condition to a journey record role from its own card (`:226-234`, `create_role_and_bind`). Review & Publish lists blockers and links to the control that fixes them (`:478-479`). Publication refuses a journey whose bound check cannot attribute a record (`hybrid/publishing.py:224-231`).

Known authoring-copy defect: `templates/hybrid/lesson_editor.html:39` renders "2 activitys" (no pluralize) — inside the copy lock.

### 3.3 Instructor versus administrator ○

One predicate decides instructor access — `is_superuser` or membership in Instructor/Administrator (`instructor_portal/views.py:64-66`), mirrored for templates at `accounts/context_processors.py:9-10` and `core/views.py:235-237`; 403 handled by `core.views.permission_denied` (`config/urls.py:26`). Admin-only in practice: the whole `/admin/` site (`core/middleware.py:6-17`), enrolment creation and programme rows (`onboarding/admin.py`). Roster nuance: a plain Instructor sees only students they enrolled (`instructor_portal/views.py:2093-2097`), and credential issue is roster-scoped so one instructor cannot reset another's student (`:181-188`, audit SEC-02). **NOT FOUND:** any content-import capability; the only seeding is developer management commands (`seed_demo_content`, `seed_demo_scenario`, `seed_hybrid_demo`, `seed_experience_ladder`).

### 3.4 Navigation friction that exists today

Programme → course → module → lesson is four levels and each is its own page; the builder index now creates a course inside the already-selected programme without re-asking (`c524e08`, `hybrid/instructor_views.py:401-440`), and a journey can be created from the course page (`:413`), which removed the two largest detours. Remaining extra hops: role and dependency work still requires opening the Journey Organizer even though the activity card can create a role; publishing is reached from the builder index rather than the lesson; and there is no hybrid course or module detail route, so a learner cannot browse "the rest of this module" (`hybrid/urls.py:12-21` exposes roadmap, lesson, journey, attempt endpoints only) ★.

---

## 4. Simulator field/action inventory

### 4.1 Screens and the registry ★ ○

The simulator is `scenarios` mounted at `/practical/` with ~70 functional routes (`scenarios/urls.py:15-103`): portal and access (`:86-92`), Single Window (overview, UCR create/save/submit/search/detail/clone/amend/attachment, exporter registration, opt-in/out, preparation application, reference pages `:35-58,79-85`), consignment and MDA (`:59-78`), clearance/BOE (`:20-34`), cargo (`:17-19`) and the legacy scenario engine (`:93-103`).

The **approved-screen registry** is `SIMULATOR_BINDING_ROUTES` (`scenarios/bindings.py:22-31`) — 8 URL *names* with instructor labels, deliberately route names rather than URLs so a simulator redesign cannot break guided steps. `VERIFY_RECORDS` (`:34-39`) names the 4 verifiable record kinds; `checkable_fields`, `verify_field_choices`, `verify_status_choices` (`:56-126`) derive which saved columns and statuses may be pinned; `validate_binding` (`:129-171`) normalises a state binding `{route, task, verify{record,status,fields}}`. Consumers span both engines: `scenarios/views.py:45`, `verification.py:23`, `guides.py:26`, `desk.py:49` and 12 hybrid modules ★. Only 8 of ~70 screens are registable.

### 4.2 Forms and input controls ○

There are **no Django forms anywhere in the learner workflows** — `scenarios/forms.py` does not exist; only admin ModelForms (`scenarios/admin.py:24,234,292`). Every screen is hand-built HTML posted as JSON or FormData by JavaScript.

- **UCR** — `templates/scenarios/_ucr_form.html` + `static/js/ucr-create.js`; posts **multipart FormData** whose `payload` field is a JSON string, plus `file_<rowIndex>` attachments (`:352-362`) to `ucr-save`/`ucr-submit`. Controls: selects (`#ucr-regime`, `#ucr-mode`), checkboxes (`#ucr-show-provider`, `[data-same-declarant]`), text inputs incl. `data-country-code` maxlength-2 fields, textareas, `<dialog>` code lookups for country, TIN/NID party directory and document codes, and dynamic document rows (`#document-rows`).
- **BOE** — creation panel in `templates/scenarios/clearance_workspace.html:17-28` (regime/CPC/zone inputs, `reuse-document` radios IDF/EMDA/LOC/CANCELLED/NONE) posted by `static/js/clearance-boe-create.js:105-141`; the tabbed declaration posts **per-section** JSON to `boe-save-draft` (`section: "bl_awb"|"invoice"|"documents"|"item"…`) and `boe-submit`.
- **Consignment application** — entry screen `single_window_create_consignment_application.html` with cascading selects fed by `application-mda-options`; the 5-tab form is `consignment_application.html` + `static/js/application-form.js` (`collectPayload()` `:1090-1123`).
- **MDA** — real records are `MdaConsignmentRequest` via `application-mda-request-create`; `single_window_create_master_application.html:9-11` is a **frontend-only placeholder** with no write path.
- `templates/scenarios/single_window_create_ucr.html` is also frontend-only (its Save button alerts) ★ — the functional page is `ucr_create.html`.

### 4.3 Create-UCR field/action map ○ ★ (verified against the source; the author drove this form in a browser)

Server: `_parse_ucr_payload` (`scenarios/views.py:530-641`) → `_apply_ucr_payload` (`:644-667`) → `ucr_save_declaration` (`:733-755`) / `ucr_submit_declaration` (`:760-785`). Client: `collectUcrPayload()` (`static/js/ucr-create.js:289-336`).

| Section | Control (id) | Payload key | Model field (`scenarios/models.py:518-574`) | Server rule |
|---|---|---|---|---|
| Regime Type | `select#ucr-regime` (`_ucr_form.html:18`) | `regime` | `regime` `:534` | must be in `{EX,IM,TN,TR,FI,FO}` (`views.py:505,541-543`); regime also chooses whether a party is identified by TIN or name (`UCR_PARTY_RULES` `:507-511`, mirrored `ucr-create.js:7-11`) |
| Temp. No. | `#ucr-temp` readonly | — | `temp_no` `:531` | allocated server-side on first save, `TEMPUCR…` (`views.py:750-751`) |
| Display Service Provider | `input#ucr-show-provider` | `show_provider` | `show_provider` `:535` | if true, the provider block is validated (`:546-571`) |
| Declarant / provider | `#ucr-declarant`, `#ucr-provider-code` (readonly "TIN, name", auto-filled from `ucr-service-provider-lookup`), `#ucr-provider-country/-address/-contact/-phone/-email/-email-2` | `provider.*` | `declarant_code`, `provider_code`, `provider_name`, `provider_country`, `provider_address`, `provider_contact`, `provider_phone`, `provider_email`, `provider_email_2` | the readonly code field is **split on comma** into code+name (`ucr-create.js:291-292`); country must be in `COUNTRY_CODE_SET`; email 1 required and `validate_email` |
| Exporter / Importer | `#ucr-{role}-identity`, `-name`, `-country`, `-address`, `-phone`, `-fax`, `-contact`, `-contact-no`, `-designation`; `[data-same-declarant]` checkbox | `exporter{}` / `importer{}` | `exporter_*` `:547-555`, `importer_*` `:557-565` | TIN regimes need identity ≥ 11 chars + name; address/phone/contact/contact_no/designation required (`views.py:588-597`). **"Same as Declarant" is client-side fill only — it has no payload key** (`ucr-create.js:182-203`). In name-mode regimes the visible name is typed into `-identity` and `-name` is hidden (`updateRegime` `:11-21`, fallback `value(-name) or value(-identity)` `:295`) |
| Consignment Details | `#ucr-goods`, `#ucr-origin`, `#ucr-destination`, `select#ucr-mode` (options carry no `value`, e.g. "30, Road Transport" — author-observed ★), `#ucr-reference`, `#ucr-email` | `consignment.{mode,goods,origin,destination,reference,email}` | `goods_description`, `origin_country`, `destination_country`, `transport_mode`, `user_reference`, `ucr_email` | mode prefix must be 10/30/40 (`views.py:600-602`); countries code-checked |
| eDocuments | `#add-document` rows: `[data-document-code]`, readonly `[data-document-name]`, reference input, `input[type=file]`; document-code dialog | `documents[]` of `{code,name,reference}` | `documents` JSONField `:573`; files → `UcrDocumentAttachment` | code requires reference, both client (`:339-351`) and server (`:621-622`); ≤50 rows; files ≤10 MB, extension **and magic-byte** checks (`:677-694`) |
| Save | `button#ucr-save` | `draft_id` (locator, not a column) | — | creates/updates the draft, returns `{id, temp_no, status, attachments}`; URL gains `?draft=` |
| Submit | `button#ucr-submit` (disabled until a draft exists) | — | `ucr_no` `:532`, `status` `:533`, `submitted_at` `:576` | requires an existing draft (`:775-776`); issues `KGHTESTUCR…` |
| List | link to `single-window-search-ucr` | — | — | exact-match search (`:788-808`) |

### 4.4 Lifecycle, ownership, permissions ○ ★

Statuses: UCR draft → submitted (`models.py:524-533`); ConsignmentApplication draft → submitted keeping its `CD<date><seq>` number (`views.py:1714-1736`); BoeDeclaration draft/submitted/assessed/accepted with `job_no` at creation and `declaration_no` at submit (`models.py:1105-1109`, `views.py:2284,2869-2870`) — submit is blocked until required MDAs are approved (`:2850-2866`); MdaConsignmentRequest has 19 statuses (`models.py:961-987`) with MOTI/GSA auto-approval on submit (`views.py:1353-1366`). Unsubmitted UCR drafts are purged from search after 7 days (`models.py:597-605`). Clone and amend create **new linked drafts** (`source_ucr`, `derivation`, `models.py:529-530`); submitted UCRs are immutable. **NOT FOUND:** a UCR delete route; BOE drafts are the only deletable record (`views.py:2879-2895`).

Ownership: every record has an `owner` FK; writes pin `owner=request.user` (`views.py:725,748,1712,2277,2294,2885`), reads/searches use `_effective_owner = _review_target or request.user` (`:78-79`) so a staff review session browses a student's records. Simulator entry requires `_has_simulator_access` — authenticated, session `simulator_user_id` matching the user, **and** a current `SimulatorCredential` (`:55-61`, `accounts/models.py:79-81`); the credential password is derived from `SECRET_KEY` + issue timestamp, stored hashed, shown once and expiring at the next month boundary (`accounts/models.py:89-127`). Review sessions are write-blocked by `_review_json_guard`/`_review_form_guard` (`:82-92`).

### 4.5 What the server can prove about an action ○ ★

| | Claim | Verdict | Evidence |
|---|---|---|---|
| A | a page was opened | **PARTIAL** | only inside a guided attempt: `GuidedStepOpenMiddleware` stamps the moment on any 200 HTML GET ★ (`scenarios/middleware.py:13-35`, registered `config/settings/base.py:56`) writing into `ScenarioAttempt.state_data`; hybrid writes a durable `StepEvent(opened)` only when the workspace POSTs `/open/<i>/` (`hybrid/views.py:283-296`). Standalone browsing: no |
| B | a navigation item was clicked | **NO** | NOT FOUND: any nav-click writer |
| C | a field was focused/edited | **NO** | client listeners only re-validate (`ucr-create.js:220-228`) |
| D | a dropdown option was selected | **NO** as an action | only the final submitted value survives |
| E | a checkbox/radio was selected | **NO** | "Same as Declarant" never leaves the browser |
| F | a field received a value | **YES, outcome-only** | `_apply_ucr_payload` `:644-667` |
| G | a form was submitted | **YES, true action** | the POST itself, under session auth |
| H | a record was created | **YES, strong** | `post_save` receivers write immutable `SimulatorRecordCreation` rows inside the same transaction (`hybrid/creation_ledger.py:45-81`, `scenarios/urls.py:7-11`) |
| I | a record was updated | **PARTIAL, outcome-only** | `updated_at auto_now` (`models.py:575`); no edit history |
| J | a saved record has a status/field value | **YES** | registry-limited columns, freshness-bounded (`scenarios/verification.py:99-146`; `hybrid/journey_verification.py:404-454`) |
| K | which user did it | **YES** | session, `owner` FK, `BoeStageEvent.created_by` (`models.py:1149`), ledger `owner`; login/logout audited with IP (`audit/signals.py:13-34`) |
| L | order and timing | **PARTIAL** | creation order provable (`SimulatorRecordCreation.captured_at`, unique per record); `ScenarioAction.sequence` and `BoeStageEvent` ordered — but only for the legacy engine's pre-declared buttons; per-field edits inside a form are invisible |

The distinction the brief asks for: **F/J/I are final-state readings, G/H/K(+L for creations) are actor-specific action evidence.** `updated_at` proves a record changed, never which control the learner used.

---

## 5. Demonstration-recording capability assessment

| # | Capability | Status | Evidence |
|---|---|---|---|
| 1 | DOM event listeners that capture interaction | **NOT IMPLEMENTED** | every `addEventListener` in `static/js/*` is local UI; the only client→server writers are deliberate commands (`hybrid-workspace.js:55-67`, `hybrid-attribution.js:29`, `quiz.js:56`). NOT FOUND: `sendBeacon`, `MutationObserver`, recorder module |
| 2 | Navigation event tracking | **PARTIAL, journey-scoped** | `hybrid.StepEvent(opened)` and `scenarios/verification.record_step_open`; no page-view counter or history table |
| 3 | Form-field interaction logging | **NOT IMPLEMENTED** | values live only as record columns or whole-form `form_data` snapshots (`models.py:1010,1126`, written `views.py:1321,1540,2283`) — state, not edits |
| 4 | Server-side activity ledgers | **IMPLEMENTED, four shapes** | `ScenarioAction` (the only ordered **action** sequence, `models.py:500-515`); `hybrid.SimulatorRecordCreation` (the only automatic capture); `hybrid.JourneyVerificationEvidence` (append-only proof per passed condition); `audit.AuditEvent` (generic shape, security writers only). Plus `StepEvent` (one row per step+kind — a state ledger), `AssistanceEvent`, `BoeStageEvent` |
| 5 | Action sequence or timeline models | **IMPLEMENTED for the legacy engine only** | `ScenarioAction` with `sequence`, `state_before/after`, `input_data`, `outcome_code`; ordered by unique `(attempt, sequence)` ★ |
| 6 | Instructor demonstration mode | **NOT IMPLEMENTED** | `docs/learning-architecture-audit.md:92,115` records it as absent **D**; the nearest thing is the staff review session, which is deliberately write-blocking (`scenarios/views.py:166-199`) |
| 7 | Record/replay | **NOT IMPLEMENTED** | `hybrid/journey_verification._completed_replay` (`:525-551`) re-answers "Check my work" on a finished journey — not playback |
| 8 | Automatic steps from recorded actions | **NOT IMPLEMENTED** | the only writers of `PracticalStep`/`VerificationCondition` are instructor POSTs (`hybrid/instructor_views.py:588,615,649-661`), edition cloning (`publishing.py:297,309`) and dev seeds (`seed_hybrid_demo.py:63`) |
| 9 | Video / screen recording | **NOT IMPLEMENTED** | no `<video>`, no video model or upload path; only aspirational mentions in `docs/implementation-plan.md:173` **D**. Reusable storage exists (§10) |
| 10 | Field selectors / stable identifiers | **PARTIAL, one screen** | `data-app-field` (75 uses) + `data-item-field` (23) in `consignment_application.html`, consumed by `application-form.js:10-12,54,102,117`; the UCR form has only `id="ucr-<role>-<key>"`; the frontend-only screens have bare inputs |
| 11 | Simulator screen registry and route mapping | **IMPLEMENTED but thin** | 8 allow-listed route names in `bindings.py:22-31` against ~70 real routes; resolution happens at render (`reverse()` in `hybrid/views.py:141`); no path→key reverse lookup a recorder could use |
| 12 | Event → verification mapping | **IMPLEMENTED for 2 kinds** | `hybrid/models.py:192-194`, evaluated twice in parallel engines (`hybrid/verification.py:320-370`, `hybrid/journey_verification.py:404-454`) plus the guided engine's own copy (`scenarios/verification.py:99-146`) |

Half-finished work worth knowing about: `ScenarioAction.input_data` (`models.py:508`) is **stored but never populated in production** — the one caller passes no payload (`scenarios/views.py:3091` → `perform_action(attempt, action)`, `services.py:76-86`) ★. `audit.AuditEvent.metadata` is a ready append-only event sink with no simulator producer. The `/test` desk and `practical_roadmap` are self-declared discardable spikes (`scenarios/desk.py:10-17`).

---

## 6. Journey and verification capability map

### 6.1 The chain ○ ★

`PracticalStep` (lesson-scoped, `hybrid/models.py:133`) → `VerificationCondition` (`:182`) → `JourneyStep` (`:386`, journey-scoped assignment of a step) → `JourneyRecordRole` (`:425`, NEW_RECORD/EXISTING_RECORD creation mode) → `JourneyConditionBinding` (`:683`, condition ↔ role) → `JourneyDependency` (`:458`) → `JourneyAttempt` (`:531`) → `JourneyRecordAssociation` (`:590`, one active per role, `assignment_source`, superseded rows kept) → `SimulatorRecordCreation` (`:720`) → `JourneyVerificationEvidence` (`:769`).

Ownership split that any redesign must respect: **steps belong to lessons, journeys belong to the course/edition and only *assign* a lesson's step** (`journey_services.assign_step`). A lesson with no journey-assigned step keeps the simpler legacy engine and never creates a `JourneyAttempt` ★ (T: `test_hybrid_record_confirmation.py`, "a lesson whose steps no journey claimed stays a plain lesson").

### 6.2 Every supported condition

| Kind | What it checks | Evidence | When evaluated | Proves | Instructor configures | Student sees |
|---|---|---|---|---|---|---|
| `saved_record` | an attributed record of the registry kind, owned through the association, at `required_status`, with `expected_fields` matching saved columns | `JourneyRecordAssociation` → exact `record_id`, plus `SimulatorRecordCreation` for NEW claims; `JourneyVerificationEvidence` per passed condition | on `Check my work` (`step_check`) and again authoritatively at `step_advance` | **an outcome**, never an action | record kind + status + paired `check_N`/`value_N` dropdowns built from `verify_field_choices()` (`hybrid/forms.py:220-234`), validated against registry columns (`hybrid/models.py:224-232`) | the status label only, via `describe()` (`hybrid/models.py:238-244`); on value mismatch: "A required saved value does not match." with no field name (`hybrid/journey_verification.py:441-446`) ★ |
| `screen_opened` | that a persisted `StepEvent(opened)` with a generation token exists for this attempt+step | `StepEvent` `:285-329` | same two endpoints | **one navigation fact** — that the learner entered the step, judged from the server's own record, never a client event | step's `screen` route name, validated against the registry (`hybrid/models.py:172`) | "Open the step's simulator screen" |

Unknown kinds fail closed with `invalid_condition` (`hybrid/journey_verification.py:405`). Decimal/date/JSON columns are deliberately unverifiable (`scenarios/bindings.py:59-72`).

### 6.3 Freshness, provenance, progression, completion ★

`_resolve_selection` refuses `binding_missing` / `association_missing` / `record_stale` (`hybrid/journey_verification.py:181-242`), where the floor is `max(attempt.started_at, verification.opened_at(lesson_attempt, step))` and record activity is `verification.record_activity()` = the newest of `updated_at`/`submitted_at`/`created_at` (`hybrid/verification.py:60-70`) — the same function the picker uses, so a row the picker calls fresh cannot be refused as stale by the check after it.

Progression: `step_check` writes evidence only; `step_advance` gates on satisfaction and, for a journey-assigned step, advances the journey and reports it (`hybrid/views.py` follow-up `5aaee42`); a step whose conditions are unsatisfied refuses the next one (`hybrid/views.py:361-365`). A condition-free step is satisfied by being opened (`verification.step_satisfied` `:373-389`) — documented at `hybrid/views.py:293`. Satisfaction is **recomputed**, so a replaced record or edited condition stops a step counting even though its historical VERIFIED stamp remains (`hybrid/journey_services.py:171-179`).

Completion: `refresh_completion` needs the theory acknowledged and every step satisfied (`hybrid/verification.py:399-410`); `refresh_journey_completion` needs all steps satisfied, all required roles satisfied and every journey lesson's attempt both completed and theory-acknowledged (`hybrid/journey_services.py:430-448,385-405`). **No assessment participates in hybrid completion** ★ (no `assessment` reference in `hybrid/models.py`).

### 6.4 What it would take to verify an action such as choosing "IM, Import"

Not an implementation proposal — a statement of what is missing today. The value survives only as the saved column `UcrDeclaration.regime`, so the current engine can check the outcome ("regime is IM") and attribute it to a record, but cannot show that the learner operated that control. What does not exist: any per-interaction event (row 1/3 of §5), any stable field identifier on the UCR form beyond `id="ucr-exporter-*"`, any route-level mapping back from a URL to a registry screen key, and any condition kind whose evidence is an interaction rather than a state. The pieces that would carry such a design already exist in other places: `ScenarioAction`'s sequence+payload shape (unused payload), `data-app-field`'s dotted-path convention, `GuidedStepOpenMiddleware`'s arrival-equals-opening trick, and `JourneyVerificationEvidence`'s append-only proof pattern.

---

## 7. Student workflow map

### 7.1 Path ○ ★

Login → dashboard (`core/views.py:27-31`) → disclaimer gate if unaccepted (`onboarding/services.py:109-113`, enforced `hybrid/views.py:197-198`) → credential page (`accounts/urls.py:9`) → sidebar entries Theoretical Training `/theory/`, Simulator `/practical/portal/`, **Practical `/practical/`** (the legacy scenario list), Theory & Practical `/hybrid/` (`core/admin_dashboard.py:281-331`); "My programmes" appears only with more than one enrolment (`:325-331`).

`/hybrid/` roadmap (`hybrid/urls.py:12` → `hybrid.views.roadmap`) lists journeys then courses→modules→lessons of the **pinned edition only**, published-only (`hybrid/views.py:202-219`); header progress "N of M" comes from `learner_edition_progress` (`hybrid/publishing.py:439-451`); journey cards show `current_position = satisfied+1` clamped to the step count, or the step count when no attempt exists (`hybrid/views.py:232-235`); locked lessons render as non-links (`templates/hybrid/roadmap.html:49-58`).

### 7.2 What is automatic, what needs a click ★

Opening `/hybrid/lessons/<uuid>/` **automatically** creates the `LessonAttempt` with `current_step` at the first step (`hybrid/services.py:32-40`) and, for a journey-bearing lesson, the `JourneyAttempt` (`hybrid/views.py:125-129`). No `StepEvent` is written on load — the opened row comes from the workspace's POST `/open/<i>/` fired by `show()` (`hybrid-workspace.js:271-273`, `hybrid/views.py:282-296`). Card 0 is the only unhidden card server-side, then `show(current_index)` resumes.

Requires a click: theory acknowledgement (`workspace.html:57` → POST `acknowledge_theory`), Hint (reveals the pre-rendered hidden `.hyb-hint`, else "No hint for this step."), the record picker (`data-record-select`), **Check my work** (POST `/check/<i>/`, retries an `opening_pending` refusal twice at 250 ms, `hybrid-workspace.js:311-319`), **Next step** (POST `/advance/`), pane switch on narrow screens. The divider is pointer-drag + ArrowLeft/Right/Home + double-click reset with 320/352 px floors persisted per tab in `sessionStorage` (`hybrid-workspace.js:109-139`); inside the same-origin iframe the parent injects CSS and hides the simulator's own sidebar/header/scrollbars (`:145-188`) without touching simulator templates.

### 7.3 Record selection and attribution ★

The step card lists, for the roles bound to that step's conditions, the learner's own candidates: NEW-mode rows from the creation ledger, EXISTING-mode rows from owned records, newest activity first, each outside the window marked "Changed before this step."; confirming POSTs `{creation_id}` or `{record_id}` to `hybrid-journey-role-attribute`, which funnels through one service (`hybrid/attribution.attribute_record`) so one active association per role holds and the superseded row survives as history. The journey page offers the same rows from the same builder (`hybrid/views._role_rows`), and both surfaces share one picker script.

### 7.4 Hints, expected values, completion notices ★

Instructor-written `step.instruction` ("What to do") and `step.outcome` ("Expected outcome") render unconditionally (`workspace.html:80-85`); `step.hint` renders hidden and is shown on demand. **Students never see `expected_fields`** — zero occurrences in `templates/hybrid` and `templates/learning`; the only leak is the required **status** label through `describe()`, which reaches `attempt_snapshot`'s `requires` map, the check results and the feedback line. On a journey check a wrong value says "A required saved value does not match." naming neither field nor value (`hybrid/journey_verification.py:441-446`). This is a property of `describe()`, not a configurable control — there is no per-condition or per-lesson hide/show switch.

Completion notices: the JS appends `.hyb-done-note` "Lesson complete — every step is verified and the theory is acknowledged." (`hybrid-workspace.js:331-339`); roadmap and journey pages have their own lines (`templates/hybrid/roadmap.html:22-23`, `journey_student.html:24-25`). Note a real wording/measurement mismatch: the roadmap's "every required lesson in this edition is done" is driven by edition-wide published-lesson counts, while `module_complete` is per module (`hybrid/services.py:68-76`) ★.

### 7.5 Attempts, persistence, preview, review ★

Persistence: `LessonAttempt.current_step/theory_acknowledged_at/completed_at/started_at` + `StepEvent` opened/verified rows (unique per attempt+step); `JourneyAttempt.status/current_journey_step/started_at/last_activity_at/completed_at` + `JourneyRecordAssociation` + immutable evidence rows. Resume comes from `attempt_snapshot` (`hybrid/verification.py:413-434`) → `current_index`, `satisfied`, `theory_acknowledged`, `lesson_complete`. **Feedback strings are request-scoped and not persisted.** Edition changes never move attempts (§1.8).

Instructor preview (`hybrid/instructor_urls.py:12` → `lesson_preview`, `instructor_views.py:693-709`) passes **no attempt**, so no JourneyAttempt is created, `data-attempt-base` is absent, the JS is write-free and Check answers "Verification is not connected in this preview." Staff review enters by POST `simulator-review-login` (exact single-match, `scenarios/views.py:166-190`) setting `simulator_review_user_id`; `review_mode` then suppresses eligible-record choices and `can_attribute`, skips attempt creation and renders "Instructor review is view-only." with endpoint-level refusals (`hybrid/views.py:463-464,484-485`). Theory-side previews exist for lesson/assessment/practical/course/module.

### 7.6 Browser-observed (against a copied database, since deleted) **B ★**

At 1440, 1758 and 531×553: the instructor editor's four stages render with no clipped controls and zero horizontal overflow and Review & Publish shows its blockers; the student picker sits beside the simulator pane, a confirmation persists across reload, an EXISTING-mode world lists both owned records newest-first with the aged one marked, choosing the aged record makes Check my work refuse and Next stay disabled, and replacing it passes. In a two-step published world driven end to end — sign into the simulator through the portal's own credential form, fill the real Create-UCR page, save (`TEMPUCR260000095`), confirm the fresh record, Check my work "✓ A UCR declaration saved as "Draft" — Verified.", Next step — the lesson showed step 2, the workspace header read "Step 2 of 2", and the roadmap read "Step 2 of 2"; in the copied database `current_journey_step` moved, one active association existed and `completed_at` stayed null. No browser session was run against `local_data/db.sqlite3`, and none reached the tables §1.1 says are missing.

### 7.7 Assessment and legacy practical paths ○

`assessments` is theory-only: `QuestionVersion`, `Assessment` (module or `final_theory`, `pass_percentage` default 70, nullable `maximum_attempts` = unlimited), `TheoryAttempt` with `select_for_update` concurrency; **no timeout enforcement** — `duration_seconds` is recorded after submit (`assessments/services.py:98`). A theory module completes only on a passed module assessment; a passed final exam unlocks orientation, and orientation gates every scenario attempt (`scenarios/services.py:34-35`). The three practical surfaces outside hybrid — the scenario engine, `/practical/roadmap/` (whose percent progress comes from **`?done=` in the URL**, i.e. self-reported, `scenarios/desk.py:497`) and the Practice Desk/`/test` spike — are separate from hybrid: hybrid routes resolve only hybrid-track enrolments and a hybrid learner never touches `ScenarioAttempt`; the desk resolves enrolment on the **theory-default** track so a hybrid-only learner gets `enrolment=None` there.

---

## 8. Instructor-to-student trace: "create a UCR declaration as a draft"

| # | From → To | Route / function | Data read / written | Permission | Gate | Known limitation |
|---|---|---|---|---|---|---|
| 1 | Builder index → programme | POST `hybrid-builder` `action=create_programme` (`instructor_views.py:401`) | Programme + ProgrammeVersion(draft) | `_require_instructor` | — | version status is the only publication state |
| 2 | → course | POST builder index `action=create_course` | HybridCourse pinned to the version | same | — | fixed in `c524e08` to stop re-asking for the programme |
| 3 | → module, lesson | `module_detail` / lesson create (`:489,566`) | HybridModule, HybridLesson | same | — | four page levels before content exists |
| 4 | Lesson editor → activity | `save_activity` (`:649-661`) → StepForm | PracticalStep(+screen, instruction, outcome, hint) | same | screen must be in the registry (`models.py:172`) | only 8 registable screens |
| 5 | → check | POST add condition (`:588`) | VerificationCondition(kind=saved_record, record_kind, required_status, expected_fields) | same | `_LIFECYCLE_COLUMNS` validation | Decimal/date/JSON unverifiable |
| 6 | → role + binding | card action `create_role_and_bind` (`:226-234`) | JourneyRecordRole + JourneyConditionBinding | same | — | the activity card and the Journey Organizer can both do this |
| 7 | → journey steps | `journey_services.assign_step` (`:189`) | JourneyStep | same | — | **the step's own lesson does not know it is journey-bound until published** |
| 8 | → publish | `hybrid/publishing.publish_edition` | flips `is_published` course/module/lesson, edition → published | same | journey integrity (`publishing.py:224-231`) | partial at course level, all-or-nothing on journeys |
| 9 | Student enrolment | `EnrolmentAdmin.save_model` (`onboarding/admin.py:28-41`) | Enrolment + Student group + audit | **admin/superuser** | — | instructors cannot enrol |
| 10 | Credential | `credential.issue()` via `instructor_portal/views.py:189-202` | SimulatorCredential (hash, expires) | roster-scoped instructor | — | the learner cannot enter the simulator before this happens |
| 11 | Roadmap → lesson | GET `/hybrid/lessons/<uuid>/` (`views.py:247-267`) | reads the pinned edition; **writes** LessonAttempt + JourneyAttempt | hybrid enrolment, published, unlocked | `lesson_is_unlocked` | every visit is journey activity |
| 12 | Step open | POST `/open/<i>/` (`:283-296`) | StepEvent(opened)+generation | attempt owner | — | nothing stamps the simulator page itself in hybrid |
| 13 | Create in simulator | GET `/practical/single-window/ucr/create/` → POST `ucr-save` | `UcrDeclaration` + `UcrDocumentAttachment` + `SimulatorRecordCreation` | `_has_simulator_access` | server-side validation (§4.3) | the frame is same-origin but un-instrumented |
| 14 | Confirm the record | POST `/hybrid/journeys/<j>/roles/<r>/attribute/` | JourneyRecordAssociation (1 active) | attempt owner, not review mode | one active per role, history kept | NEW-mode role whose creation is claimed shows "No eligible records…" |
| 15 | Check my work | POST `/check/<i>/` → `verify_journey_step` | JourneyVerificationEvidence | attempt owner | binding/association/freshness/status/values | outcome-only proof |
| 16 | Advance | POST `/advance/<i>/` | LessonAttempt.current_step, JourneyAttempt.current_journey_step | attempt owner | earlier steps satisfied | journey position and lesson position now move together |
| 17 | Journey completes | `refresh_journey_completion` | JourneyAttempt.completed_at, status | — | all steps + required roles + every lesson attempt completed & theory acknowledged | no assessment participates |

**Missing connections (both halves exist, the wire does not):**
- No browser-side observation connects a simulator interaction to a step: the parent workspace already reaches `frame.contentDocument` for CSS injection (`hybrid-workspace.js:140-190`) yet installs no listeners, and **`postMessage` appears nowhere in the repository** ○ ★. So "the learner opened Single Window" is provable, "the learner used the Create UCR screen for this step" is not — the hybrid step-open is the workspace POST, not the page visit.
- `ScenarioAction` (an ordered action sequence) and `PracticalStep`/`VerificationCondition` (the hybrid step model) share no vocabulary; the legacy engine's state `binding.verify` maps to record kinds while the hybrid condition table maps to roles, and no code converts one to the other ○.
- Instructor review can browse a student's records but cannot pre-attribute a role; the picker is learner-only by design.
- The student sidebar's "Practical" entry and the hybrid "Theory & Practical" entry lead to two different practical systems with different attempt tables ★.
- A learner's own creations are the only automatic capture, and it is a `post_save` effect, not an authored action; nothing records *which screen* the record was made on.

---

## 9. Existing versus proposed capability matrix

| Desired capability | Existing implementation | Status | Evidence | Actual gap | Reusable components |
|---|---|---|---|---|---|
| Create a T&P lesson inside the existing hierarchy | four-stage editor | **IMPLEMENTED** ★ | `hybrid/instructor_views.py:566-680`, `lesson_editor.html`, T `test_hybrid_builder.py` (57) | none for authoring | edition-scoped models, `StepForm` |
| Choose interactive demonstration recording **or** manual authoring | manual only | **PARTIAL** | manual path above | no second mode; nothing to switch between | `preview_mode`/`review_mode` context-flag pattern |
| Instructor performs the task in the real simulator | staff review session exists but is write-blocking | **PARTIAL** | `scenarios/views.py:166-199`, `_review_*_guard` `:82-92` | an instructor cannot *do* the task as themselves in a capture context | `_effective_owner`, `simulator_review_user_id`, `SimulatorCredential` gate |
| Capture navigation, field interactions, selections, submissions | form submissions and record creation only | **NOT IMPLEMENTED** | §5 rows 1-3, §4.5 B/C/D/E | no interaction events at all | `GuidedStepOpenMiddleware`, `StepEvent`, creation ledger, `AuditEvent.metadata` |
| Convert captured actions into editable steps | none | **NOT IMPLEMENTED** | only POSTs and seeds create steps (§5 row 8) | the whole conversion layer | `PracticalStep`/`VerificationCondition` forms, `ScenarioAction` sequence shape |
| Choose which expected values are hidden from students | hard-coded: always hidden | **PARTIAL** | `describe()` `models.py:238-244`, zero template hits ★ | no per-condition/per-lesson control | `describe()` is the single choke point |
| Theory guidance | lesson theory rich text + acknowledgement | **IMPLEMENTED** | `models.py:112-115`, `workspace.html:40-57`, `learning/rich_text.py` | hybrid theory is one continuous field, unlike learning's blocks | nh3 pipeline, `ContentBlock` kinds for the other app |
| Optional demonstration video | nothing | **NOT IMPLEMENTED** | no video model/tag/path ★ | entire feature | `MEDIA_ROOT`/`MEDIA_URL`, `upload_to` prefixes, ACL gate `core/views.py:205-237`, `RichTextImage` precedent |
| Review, preview, publish through existing workflows | blockers, preview, edition publish | **IMPLEMENTED** ★ | `publishing.py:204-250`, `lesson_preview` | two blocker lines for an unregistered record kind | `structural_issues`, `unbound_condition_issues` |
| Student opens a guided workspace beside the full simulator | split pane, iframe, divider, resume | **IMPLEMENTED** **B** ★ | `workspace.html:39-172`, `hybrid-workspace.js` | screen registry covers 8 of ~70 screens | `bindings.py` registry, `data-screen-url` switching |
| Perform the task independently | real simulator forms reachable in-frame | **IMPLEMENTED** **B** | §7.6 | no in-frame instrumentation, no guided stamps on the simulator side | route-name bindings |
| Hints appropriate to the learning level | one static hint per step | **PARTIAL** ★ | `step.hint`, `workspace.html:86-88` | no beginner→competency assistance modes despite the product rule **D** (`docs/product-rules.md:59-68`) | `StepEvent` can already count hint display if a row were written |
| Have supported actions **and** outcomes verified | outcomes + one navigation fact | **PARTIAL** ★ | §6.2 | actions are unverifiable (§6.4) | evidence pattern, freshness floor |
| Progress only when requirements are satisfied | evidence-gated advance | **IMPLEMENTED** ★ | `hybrid/views.py:361-365`, T `test_hybrid_record_confirmation` | condition-free steps are satisfied by opening | `step_satisfied`, `role_satisfied` |
| Complete without receiving the completed form | expected values never shown | **IMPLEMENTED** ★ | §7.4 | instructor text ("Expected outcome") may still describe values | `describe()` |

---

## 10. Reusable components (no implementation proposed)

- **Ordered action ledger shape** — `ScenarioAction` (`scenarios/models.py:500-515`): `sequence` unique per attempt, `action_code`, `state_before/after`, `input_data` JSON (**currently always empty in production** ★), `feedback_shown`, `created_at`; writer `scenarios/services.py:76-86`.
- **Automatic capture precedent** — `hybrid/creation_ledger.py:45-81` post_save receivers inside the creation transaction (`scenarios/urls.py:7-11`), with T for bypasses and rollback (`test_stage3_creation_ledger.py`, 17).
- **Arrival-equals-opening** — `GuidedStepOpenMiddleware` (`scenarios/middleware.py:13-35`, registered `config/settings/base.py:56`) resolves an active attempt from the request and stamps the moment once ★.
- **Append-only proof rows** — `JourneyVerificationEvidence` + `_record_evidence` (`hybrid/journey_verification.py:476-502`).
- **Approved-screen registry with verification metadata** — `bindings.py:22-171`: labels, verifiable kinds, checkable columns, status choices, binding validation.
- **Freshness rule shared by UI and engine** — `verification.record_activity` (`hybrid/verification.py:60-70`) used by both the picker and the checker ★.
- **Stable dotted field identity** — `data-app-field` / `data-item-field` in `consignment_application.html` + `application-form.js:10-12,54,102,117`; payload paths already match model column names, and `expected_fields` already stores model column names (`bindings.py:93-112`, `hybrid/forms.py:220-234`).
- **Actor/session plumbing** — `_effective_owner`, `_review_target`, `_has_simulator_access`, `_review_*_guard` (`scenarios/views.py:52-95`); `AuditEvent` (`audit/models.py:7-30`).
- **Private-media storage + ACL** — `MEDIA_*` (`base.py:102-103`), `upload_to` conventions (`onboarding/models.py:74`, `learning/models.py:68,128`, `scenarios/models.py:589`), prefix-gated serving (`core/views.py:201-237`), orphan-tracking precedent `RichTextImage`.
- **UI conventions** — Unfold + `dash-*`/`hyb-*`/`lrn-*`/`cargo-*`/`boe-*`/`ucr-*` namespaces, manual `?v=YYYYMMDD-n` cache tokens, single theme controller `static/js/theme.js`.

---

## 11. Confirmed gaps and integration constraints

### 11.1 Gaps

1. **Three unapplied hybrid migrations, two missing tables in the development database** ★ (§1.1, §2.4). Everything Stage-3 (creation ledger, association unique-claim, journey evidence) is unrunnable there.
2. **The hybrid journey system is un-authored in real data** ★: 1 journey with 0 steps and 0 roles, 2 practical steps total, no attempts.
3. **Two live practical systems** ★: the legacy scenario engine (populated, sidebar-linked, state machine, action sequence, rubric evaluations) and hybrid journeys (tested, empty, the newer design). `evaluations`, `reports` and the orientation unlock chain are wired to the **legacy** one.
4. **No interaction capture** (§5 rows 1-3, §4.5 B-E).
5. **Screen registry covers 8 of ~70 screens** (§4.1); an unregistered kind produces duplicated blockers in Review & Publish ★.
6. **Only two condition kinds**; no per-action verification (§6.4).
7. **NEW-mode role whose only creation is claimed shows "No eligible records are available…"** even though the learner owns records ★.
8. **Every visit to a journey-bound lesson creates a durable JourneyAttempt** ★ (ruling accepted 2026-10-29) — journey activity now counts browsing.
9. **Assistance modes are a documented rule with no implementation** **D** (`docs/product-rules.md:59-68`) ★.
10. Copy defects: "2 activitys" (`lesson_editor.html:39`); the roadmap's "every required lesson" line measures edition-wide counts while `module_complete` is per module ★ (§7.4).
11. Three known review-mode write gaps (`boe_create`, MDA-request create, IDF lookup ownership) **D** `docs/learning-architecture-audit.md`, `docs/guided-practice-checkpoint.md:7-16`.
12. No self-service enrolment, no content import, no analytics on hint usage.

### 11.2 Constraints any redesign must respect

- **Data and versions.** Attempts are edition-pinned for life (`onboarding/models.py:128`; `publishing.py:253-339`); published content must not be rewritten; superseded associations and evidence rows are history and must not be deleted.
- **Ownership boundaries.** Lessons own steps; the journey/course owns ordering, roles and dependencies; the edition owns publication.
- **Fail-closed verification.** Unknown condition kinds, unapproved record kinds, unapproved route names and out-of-window records all refuse rather than pass (`hybrid/journey_verification.py:181-242,405`; `models.py:172,224-232`).
- **Simulator fidelity.** Route *names* are bound, never URLs (`bindings.py:1-14`); the training-only banner and fictional-data rules apply (`docs/product-rules.md`).
- **Security and privacy of recording.** Students are shown no expected values today (§7.4); an interaction recorder would capture what a learner typed, in a training product whose policy is minimal personal data (`docs/architecture.md:91-99` **D**). Review sessions are strictly view-only and endpoint-enforced. Credential material never appears in the schema and `issue()` derives passwords from `SECRET_KEY` (`accounts/models.py:113-127`) — anything new must not widen that exposure.
- **Theme and copy lock (AGENTS.md, 2026-10-09).** Colours, fonts, spacing, dark/light palettes and all user-facing text are frozen; changes require Bernard's explicit prior approval. Two strings are approved for this feature area: "Changed before this step." and "Required records".
- **No new models/migrations without approval; no `migrate` against `local_data/db.sqlite3`; no VPS changes; no push/deploy.**
- **Database portability.** Pervasive `JSONField` becomes `jsonb`; partial unique constraints and `Lower()` folding need a pre-import collision check; `select_for_update` semantics differ across engines; one admin filter already runs in Python because SQLite lacks JSON `contains` (`scenarios/admin.py:217`); `allocate_application_number` (`models.py:1040-1049`) is an unlocked `max()+1`, unlike the other allocators ★; no raw SQLite SQL in app code, backup/restore commands guard the engine (**D** `docs/sqlite-to-postgresql-compatibility-audit.md:238`).
- **Test and style conventions.** `tests/` is the suite; in-memory SQLite applies all migrations, so a migration gap is invisible to it ★; no `app_name` namespaces; manual cache-busting tokens must be re-numbered per change; templates extend one of three bases (`admin/base.html`, `core/base_student.html`, `core/base_simulator.html`).
- **A second agent commits into this branch** — HEAD moved from `5aaee42` to `bf08419` during this session ★; re-diff against HEAD before staging.

---

## 12. Open questions requiring product decisions

1. Which practical system is the product? The legacy scenario engine has content, action sequences, rubrics and a sidebar entry; hybrid journeys have the new builder, the evidence model and the tests. Maintaining both doubles verification, and any recorder design inherits the choice.
2. Will the three unapplied hybrid migrations be applied to the development database, and who runs them? Nothing Stage-3 works locally until they are, and the instruction on record forbids applying them without approval.
3. Is action-level verification actually wanted, given the product rule that students must not receive the completed form? Capturing per-field interaction is the only way to prove "the learner chose IM", and it means storing what learners type.
4. Where would captured evidence sit relative to the freshness rule — a new event table, `AuditEvent`, or the unused `ScenarioAction.input_data`? Each has different retention and privacy consequences.
5. What is the intended screen registry size? 8 allow-listed names against ~70 real routes currently bounds both authoring and any capture; expanding it is a product-scope decision, not a technical one.
6. Should assistance modes (`product-rules.md:59-68`) be implemented at all, and if so does hint usage become evidence for or against completion?
7. What is the rule for condition-free steps being satisfied by opening (`hybrid/views.py:293`) — acceptable convenience or a hole in "progress only when requirements are satisfied"?
8. Is a durable JourneyAttempt on every lesson visit the intended semantics, or should browsing be distinguished from working?
9. Should an instructor be able to pre-attribute a role for a student, or is learner confirmation a deliberate product stance?
10. What becomes of the roadmap's "every required lesson" line, given its number is edition-wide while the phrase reads per module?
11. Does demonstration video enter scope at all, and if so under which private-media prefix and with which ACL rules?
12. What is the retention policy for any captured action data once a journey is complete, given the append-only evidence pattern already in place?
