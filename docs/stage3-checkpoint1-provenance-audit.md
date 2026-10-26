# Stage 3, Checkpoint 1 — Simulator Record-Creation Provenance: Architecture Audit

Status: inspection and planning only. No code, models, migrations, simulator
files or templates were modified for this checkpoint. Every claim marked
**[Fact]** carries a file:line reference verified in the working tree at
`7723eb450aac0c594332e744a8a9624a625abac6`; items marked **[Recommendation]**
are this document's proposals awaiting review.

---

## 1. Existing simulator creation architecture

### 1.1 The practical registry

**[Fact]** `scenarios/bindings.py:29-34` — the registry approves exactly four
record kinds: `ucr` → `UcrDeclaration`, `boe` → `BoeDeclaration`,
`consignment` → `ConsignmentApplication`, `mda` → `MdaConsignmentRequest`.
`hybrid.verification._verify_saved_record` and `JourneyRecordRole.clean`
read this registry; nothing else can be verified or role-typed.

**[Fact]** The guided-step routes an instructor may bind
(`bindings.py:17-26`) are the portal, the Single Window overview, UCR create
and search, BOE search, the clearance workspace, consignment-application
create and consignment search. MDA requests are created from buttons on the
consignment-document and consignment-application screens rather than a bound
route of their own.

### 1.2 Shared creation architecture (applies to all four models)

- **[Fact]** All four models carry a non-nullable `owner` FK to the user
  model, an implicit integer auto PK, `created_at auto_now_add`,
  `updated_at auto_now`, a nullable view-assigned `submitted_at`, and a
  status field defaulting to DRAFT (`scenarios/models.py:518-583` UCR,
  `:850-958` consignment, `:990-1037` MDA, `:1102-1141` BOE).
- **[Fact]** Every student-facing creation endpoint sets the owner
  server-side to `request.user` (UCR save `views.py:747`, UCR clone
  `views.py:1031`, BOE create `views.py:2275-2284`, consignment save
  `views.py:1711`) or to the consignment application's owner (MDA creation
  `views.py:1530`, `views.py:1884`). No creation path accepts an
  owner from client input.
- **[Fact]** All creation is synchronous request-scoped work. There is no
  Celery, threading or async anywhere in the project (grep over all `.py`).
- **[Fact]** `created_at` is `auto_now_add` on all four models: the creation
  timestamp is database-write-time, server-generated, and not
  client-controllable.
- **[Fact]** Transactions: there is no `ATOMIC_REQUESTS`
  (`config/settings/`). MDA creation wraps itself in `transaction.atomic()`
  (`views.py:1526-1542`, `:1881-1890`); the UCR and consignment save views
  commit the record save directly (implicit per-statement autocommit) with
  attachments saved separately; `allocate_job_number` uses
  `select_for_update` inside `atomic` (`models.py:1076-1086`) while
  `allocate_ucr_number`/`allocate_application_number` are max+1 scans
  relying on unique constraints as backstops (`models.py:608-626`,
  `:1040-1048`).
- **[Fact]** Access control: `simulator_access_required`
  (`scenarios/views.py:132-142`) requires staff/instructor status or a
  simulator-credential session; the Stage 2/3 verification engine additionally
  scopes every check to `attempt.enrolment.student`
  (`hybrid/verification.py:70`).
- **[Fact]** Review mode: staff review reads the reviewed student via
  `_effective_owner` and most write endpoints refuse writes under review via
  `_review_json_guard`/`_review_form_guard` (`views.py:82-92`). Two
  inconsistent endpoints are flagged in §6.3.
- **[Fact]** Submission is an update, not a creation: UCR submit
  (`views.py:757-784`), consignment submit (`views.py:1719-1737`), BOE submit
  (`views.py:2837-2873`) and MDA submit (`views.py:1350-1377`) set
  `status`/`submitted_at` on the **same row**; a resubmitted declaration
  requires cloning (UCR clone `views.py:1023-1040` creates a new row with
  `derivation="clone"` and `source_ucr` set).
- **[Fact]** Frontend-only screens persist nothing: cargo direct delivery and
  service request, the cargo reference pages, Simple Amendment / Post Entry,
  Master Application, Exporter Registration, Opt In/Out create/search/detail,
  and all Single Window reference pages are plain renders or in-page demos;
  the Practice Desk is GET-only by design. Verified per-template: no
  fetch/POST to any creation endpoint.
- **[Fact]** Seeding never creates the four registry models
  (`seed_demo_scenario.py` touches only scenario-content rows; reference data
  comes from migrations/fixtures).

### 1.3 Per-workflow creation matrix

| Workflow | Model / pk | Creation view (file:line) | URL, method | Ownership set by | Transaction | Creation timestamp | Creates or updates | Synchronous |
|---|---|---|---|---|---|---|---|---|
| UCR draft save | `UcrDeclaration` / auto int id | `ucr_save_declaration` (`views.py:730-754`) | `ucr-save`, POST `/practical/single-window/ucr/save/` | `owner=request.user` (`:747`); existing drafts resolved owner-scoped (`:719-727`) | implicit autocommit (no outer atomic) | `created_at auto_now_add` (`models.py:574`) | Creates on first save; later saves update the same DRAFT row | Yes |
| UCR clone | `UcrDeclaration` | `ucr_clone` (`views.py:1023-1040`) | POST `ucr/<id>/clone/` | `owner=request.user` (`:1031`) | implicit | `created_at auto_now_add` | Creates a new row (`derivation="clone"`, `source_ucr` set) | Yes |
| BOE create | `BoeDeclaration` | `boe_create` (`views.py:2244-2285`) | POST `boe-create` `/practical/clearance/boe/create/` | `owner=request.user` (`:2275ff`) | `allocate_job_number` locks inside `atomic`; row create otherwise implicit | `created_at auto_now_add` (`models.py:1130`) | Always creates (one BOE per UCR, OneToOne `models.py:1121`) | Yes |
| Consignment save | `ConsignmentApplication` | `application_save_declaration` (`views.py:1695-1716`) | POST `application-save` | `owner=request.user` (`:1711`) | implicit; `allocate_application_number` unlocked (flagged §6.3) | `created_at auto_now_add` (`models.py:949`) | Creates on first save per UCR; later saves update the DRAFT | Yes |
| MDA request (dialog) | `MdaConsignmentRequest` | `application_mda_request_create` (`views.py:1512-1557`) | POST `application-mda-request-create` | `owner=consignment_application.owner` (`:1530`) | `transaction.atomic()` + `full_clean()` (`:1526-1542`) | `created_at auto_now_add` (`models.py:1017`) | Creates | Yes |
| MDA request (entry screen) | `MdaConsignmentRequest` (+ implicit parent application) | `consignment_application_mda_create` / `_copy` (`views.py:1894-1942`) via `_target_mda_request` (`:1868-1891`) | POST `consignment-application-mda-create` / `-copy` | `owner=application_record.owner` (`:1884`) | `transaction.atomic()` (`:1881-1890`) | `created_at auto_now_add` | Creates (and implicitly creates the parent DRAFT application if missing, `:1875-1880`) | Yes |

**[Fact]** Non-registry student-owned rows created during scenarios:
`ScenarioAttempt`, `ScenarioAction`, `AssistanceEvent`, `UcrDocumentAttachment`,
`BoeStageEvent`, and the per-application `Assessment` (`get_or_create` on
viewing the assessment page). None are in `VERIFY_RECORDS`; only
`UcrDocumentAttachment` hangs off a registry record.

### 1.4 Creation-vs-update boundary

**[Fact]** Creation = a new row (first save of a draft, clone, BOE create,
MDA request). Everything else — submit, amend, general-draft saves, MDA
re-save, assessment refresh — updates an existing row and moves
`updated_at`/`submitted_at`. This boundary is exactly what creation
provenance must capture and what the existing freshness check cannot
distinguish (§2.2).

## 2. Stage 2 provenance gap — why NEW roles fail closed

### 2.1 The deliberate fail-closed rule

**[Fact]** `journey_services.role_satisfied`
(`hybrid/journey_services.py:565-589`): if a role's active association
declares `assignment_source == CREATED_IN_JOURNEY`, the role is **never**
satisfied — the message says the system cannot yet verify that the record was
created within this journey. Authorized-existing roles satisfy normally.

**[Fact]** `journey_services.assign_record` (`:526-562`) enforces mode
compatibility: a NEW role accepts only `source=CREATED_IN_JOURNEY`, an
EXISTING role only `AUTHORIZED_EXISTING`. Ownership is enforced server-side
(`:534-538`: the record must exist and belong to the attempt's student;
another learner's record raises `PermissionDenied`).

**[Fact]** `hybrid/publishing.py:84-106` (`journey_publication_blockers`) and
Checkpoint 6's guard in `publish_edition` make a required NEW role block
publication of the whole edition, because the simulator schema carries no
authoritative creation provenance.

### 2.2 The precise gap

**[Fact]** The pieces that already exist: `JourneyRecordAssociation` has a
`CREATED_IN_JOURNEY` assignment source (`hybrid/models.py:582-584`), full
ownership/edition validation in `clean()` (`:639-661`), a partial unique
constraint `unique_active_record_per_role` (`:623-628`), and enrolment/
programme-version FKs matching the attempt (`:644-647`). No code path ever
sets `CREATED_IN_JOURNEY`, and no simulator signal or service links a row's
creation to an attempt.

**[Fact]** The existing SAVED_RECORD verification
(`hybrid/verification.py:66-95`) proves ownership (server-side
`owner=attempt.enrolment.student` filter), status/field match, and
freshness (`_latest_activity >= opened_at(attempt, step)`, `:56-63`,
`:77`). It cannot prove **creation**: a record that merely existed and was
edited after opening the step passes the freshness check, because
`updated_at` is indistinguishable from creation. `updated_at auto_now` fires
on every save, so "created during the attempt" is not derivable from the
current schema.

**[Fact]** Conclusion: the gap is not authentication, ownership, or
freshness — those exist and are server-side. The gap is a durable,
authoritative link **record-row creation → (student, journey attempt)** that
is written at creation time by server code, not derived later.

### 2.3 Ownership and version checks that must remain intact

- **[Fact]** Attempt ownership: `attempt_for_user` resolves attempts only via
  `enrolment__student=user` (`journey_services.py:347-355`); verification is
  owner-scoped (`verification.py:70`).
- **[Fact]** Version matching: attempts require
  `enrolment.programme_version == journey.programme_version`
  (`models.py:549-573`; `journey_services.py:325-326`, `:342-344`); view
  entry re-checks it (`hybrid/views.py:244-246`, `:263-265`).
- **[Fact]** Association integrity: enrolment and programme version must
  match the attempt, role must belong to the attempted journey, record kind
  must match the role, and the record must exist and belong to the enrolled
  learner (`models.py:639-661`).
- **[Fact]** Single active record per role (`models.py:623-628`), published
  edition immutability (`_require_draft_version`, `journey_services.py:98-102`),
  and draft-only structure mutation are all load-bearing and unchanged by this
  design.

## 3. Recommended provenance design

**[Recommendation] Approach C — inferred association from authoritative
server-side creation evidence**, with three components:

1. **A post-save provenance receiver** registered by the `hybrid` app config
   on the four registry models. Django signals are synchronous and run inside
   the creating view's transaction/connection, and `post_save` carries
   `created=True` only on genuine INSERTs. The receiver reads
   `instance.owner` (server-set, §1.2) and `instance.created_at`
   (auto_now_add, server-set) — no client-supplied value is involved — and
   attempts an automatic claim: find the owner's single eligible
   (attempt, required NEW role, record_kind) and create the
   `JourneyRecordAssociation` with `source=CREATED_IN_JOURNEY` and a copied
   `record_created_at`.
2. **An idempotent reconciliation service**
   `hybrid.provenance.reconcile_creation_associations(attempt)` that re-runs
   the same match as a scan (owner + record_kind + `created_at >=`
   eligibility moment + not already claimed by any CREATED_IN_JOURNEY
   association), called on the POST paths that evaluate progress
   (`journey_advance`, completion refresh) so a failed or missed signal-time
   claim heals without user-visible action.
3. **The eligibility rule** that makes inference safe: a record claims a role
   only when (a) the owner's `JourneyAttempt` is IN_PROGRESS, (b) the role is
   required (or optional — recommended deferred, §10), `creation_mode=NEW`,
   `record_kind` matches the model, (c) the role has no active association,
   (d) `record.created_at >= attempt.started_at`, and (e) no other
   `CREATED_IN_JOURNEY` association already references that record row. When
   zero or multiple attempts/roles are eligible, nothing is claimed and the
   journey page surfaces the open requirement; a future explicit-claim UI can
   disambiguate (deferred).

Why this satisfies every design guarantee:

| Guarantee | Mechanism |
|---|---|
| Bound to the authenticated student | `owner` is set server-side by every creation view (§1.2 [Fact]); the receiver never reads client input |
| Associated with the correct active attempt | eligibility requires IN_PROGRESS + edition match + kind match + unclaimed role |
| Genuinely created during that attempt | `post_save created=True` is the INSERT moment; `record_created_at` is copied from `auto_now_add` and checked `>= attempt.started_at` |
| Pre-existing records can't be claimed | receiver fires only on INSERT; the reconciler scan bounds `created_at >= eligibility` and skips any record already referenced by a `CREATED_IN_JOURNEY` association |
| Another student's records can't be claimed | owner equality is the join key; `assign_record` already raises PermissionDenied on cross-owner records (`journey_services.py:537`) |
| No forged identifiers, timestamps or ownership claims | no client-supplied record id, timestamp or owner enters the path; the association is written by server code from server values; the only external trigger is the student's own authenticated creation POST |
| No cross-enrolment / cross-edition contamination | association `clean()` enforces enrolment/programme-version/role/kind match (`models.py:639-661`); eligibility runs per attempt of the owner's own enrolment |
| Duplicate submissions and retries | submit endpoints update the same row (no new INSERT → no duplicate provenance); duplicate drafts create extra rows but only the first claim wins (`unique_active_record_per_role` + the new per-record claim uniqueness); retry after failure is healed idempotently by the reconciler |
| Create vs update distinction | only INSERT emits provenance; updates move `updated_at` and never touch provenance |
| SQLite/PostgreSQL compatibility | plain ORM operations plus one partial unique constraint — the project already uses conditional `UniqueConstraint`s on SQLite (`models.py:623-633`) |

**[Recommendation] Hardening:** forbid `CREATED_IN_JOURNEY` through the
public `assign_record` (reserve it for the provenance service) so a future
caller cannot forge a created-in-journey claim through the service API.

## 4. Data flow from journey launch to verified record creation

1. Learner opens the journey page (`hybrid/views.py:228-275`): entry creates/
   resumes the single attempt (`get_or_create_attempt`), `current_journey_step`
   is seeded at the entry point.
2. Learner advances to the step whose condition is bound to the NEW role and
   opens the simulator: `step_open` records the OPENED `StepEvent`
   (`verification.py:34-41`) — the freshness bound — and the workspace frames
   `screen_url = reverse(step.screen)` (`hybrid/views.py:42`).
3. Learner completes the simulator form and POSTs the existing creation
   endpoint (e.g. `ucr-save`). The view authenticates, sets `owner` and lets
   `auto_now_add` stamp `created_at`; the row INSERT fires the provenance
   receiver.
4. The receiver matches the eligibility rule (§3) and writes
   `JourneyRecordAssociation(source=CREATED_IN_JOURNEY, record_created_at=...)`,
   replacing no one (role unclaimed) under the attempt row lock semantics
   already used by `assign_record`.
5. Learner returns to the journey and POSTs advance/refresh; the reconciler
   re-checks, `role_satisfied` now lifts (provenance present), dependencies
   of type RECORD_AVAILABLE release, and `refresh_journey_completion` marks
   the attempt COMPLETED when all gates pass.
6. The instructor's readiness gate and Checkpoint 6's direct-service guard
   are unchanged at runtime; the publishing-time required-NEW blocker is
   retired in the final implementation checkpoint once provenance is live.

## 5. Exact integration points and files

**New files**
- `hybrid/provenance.py` — eligibility matcher, claim service, reconciler,
  post_save receivers.
- `tests/test_stage3_record_provenance.py` — the acceptance tests of §8.11.

**Modified files (hybrid only)**
- `hybrid/apps.py` — register the receivers in `ready()`.
- `hybrid/journey_services.py` — `role_satisfied` provenance lift; reconciler
  invoked on the POST evaluation paths; `assign_record` hardened to refuse
  `CREATED_IN_JOURNEY` from external callers.
- `hybrid/models.py` + one new migration — `JourneyRecordAssociation` gains
  `record_created_at` (nullable DateTimeField) and the partial unique
  constraint "a record is created-in-journey at most once".
- `hybrid/publishing.py` — retire the required-NEW publication blocker
  (final checkpoint only, after provenance tests prove the chain).

**Simulator files: none.** No scenario view, URL, form, model, template,
JavaScript or CSS file changes. The frozen simulator templates, the
practice-desk JavaScript and all simulator CSS are untouched; simulator
navigation and visual design are unchanged because the provenance path is
entirely server-side observation of existing INSERTs.

## 6. Database and migration requirements

**[Recommendation]** One migration on `hybrid`:
- `JourneyRecordAssociation.record_created_at` — nullable
  `DateTimeField(null=True)`; set once at claim time from the record's
  `created_at` (never client-supplied).
- `UniqueConstraint(fields=("record_kind", "record_id"),
  condition=Q(assignment_source="created_in_journey"),
  name="unique_created_in_journey_claim")` — a record can be claimed as
  created-in-journey by at most one attempt, forever.
- SQLite compatibility: conditional unique constraints of exactly this shape
  already exist on this model (`models.py:623-633`) and run on the SQLite dev
  database; PostgreSQL supports partial unique indexes natively. No data
  migration is needed (no legacy rows carry `CREATED_IN_JOURNEY` — verified:
  no code path ever set it).

## 7. Security and ownership safeguards

- Owner: server-assigned in every creation view (§1.2 [Fact]); the receiver
  trusts only `instance.owner`/`instance.created_at`, never request data.
- Claim uniqueness: per-record partial unique constraint; per-role
  `unique_active_record_per_role` already in place.
- Edition integrity: association `clean()` requires
  enrolment/programme-version/role/kind coherence with the attempt.
- No new endpoints: there is nothing to authenticate differently; the
  existing `simulator_access_required` and journey view authentication are
  untouched.
- Forgery surface: removed, not added — `assign_record` will refuse
  `CREATED_IN_JOURNEY` from external callers, so the only writer is the
  server-side receiver/reconciler.
- Review mode: staff reviewing a student read student-owned records
  (`_effective_owner`); records created by staff in review gaps are
  staff-owned and can never match a student attempt (owner inequality).
- Known simulator-side review-mode inconsistencies (BOE endpoints use
  `request.user` instead of `_effective_owner`;
  `application_mda_request_create` lacks the review guard) were flagged in
  §6.3 of the fact sheet. **[Recommendation]** fix them in a simulator
  hygiene pass before or alongside Stage 3 implementation; the provenance
  design does not depend on them, because owner inequality still prevents
  false claims.

## 8. SQLite/PostgreSQL compatibility

- The receiver and reconciler use plain ORM `filter`/`create` calls inside
  `transaction.atomic()` where write-ordering matters — both backends.
- The `select_for_update` attempt-lock pattern already used by
  `assign_record`/`journey_advance` is retained for claim replacement; on
  SQLite the database write lock serialises (documented in
  `journey_services.py:8-19`), on PostgreSQL the row lock operates.
- The new partial unique constraint is supported on both backends
  (precedent: `models.py:624-628`).
- `auto_now_add` timestamps are timezone-aware (`USE_TZ`); comparisons against
  `attempt.started_at` are same-aware.

## 9. Failure-handling rules

1. **No active journey attempt** — the receiver finds no IN_PROGRESS attempt
   with an eligible unsatisfied NEW role: no association is written; the
   record remains an ordinary simulator record; the simulator response is
   unchanged. Independent simulator use outside a journey is unaffected by
   design.
2. **Multiple active attempts** — if exactly one attempt has an eligible
   unsatisfied required-NEW role of that kind, it claims. If several do, v1
   claims nothing and every affected journey page keeps showing the open
   requirement; the student resolves it by creating the record while only
   that journey is open, or (deferred) by an explicit claim control.
   Documented limitation, safe by construction (no wrong attribution).
3. **Invalid or expired creation context** — Approach C has no context token
   to expire; eligibility is evaluated from durable state at claim time. An
   attempt that is completed, retired or version-mismatched is simply not
   eligible.
4. **Record created, provenance write fails** — the simulator record still
   exists (provenance never blocks creation; receiver failures are contained
   so they cannot fail the student's save). The reconciler re-claims on the
   next advance/refresh POST; idempotency makes repeated runs harmless.
5. **Record later deleted or invalidated** — `role_satisfied` already fails
   closed ("the assigned record no longer exists for this learner",
   `journey_services.py:582-583`); journey completion stays blocked. Creating
   a replacement record claims the role again through the normal path (the
   replace-with-history semantics of `assign_record` apply).
6. **Student resumes a journey** — attempts are durable and unique per
   (enrolment, journey); resume re-evaluates everything; the reconciler is
   idempotent, so nothing double-claims.
7. **Retry of a previously submitted form** — submit is an update of the same
   row (no INSERT, no new provenance); a fresh declaration means a new row,
   which claims only if a role is still open, else remains an unclaimed
   ordinary record.
8. **Instructor/administrator review** — review mode is read-only for the
   guarded write endpoints; instructor reviews read the student's
   associations and evidence. Staff-owned records can never satisfy a
   student's role (owner inequality).
9. **Simulator use outside a guided journey** — fully supported and unchanged:
   without an eligible attempt the receiver is a no-op; nothing about the
   simulator's standalone behaviour changes.

## 10. Implementation checkpoints in dependency order

1. **Migration + model fields** — `record_created_at` and the per-record
   claim uniqueness (no behaviour change yet).
2. **`hybrid/provenance.py`** — eligibility matcher, claim service,
   reconciler; unit-tested in isolation.
3. **Receiver registration** (`hybrid/apps.py`) + reconciler calls on the
   POST evaluation paths — acceptance tests for the full
   create → claim → satisfy chain.
4. **`role_satisfied` lift + completion issue text updates** — NEW roles
   become satisfiable; completion flows light up.
5. **`assign_record` hardening** — refuse external `CREATED_IN_JOURNEY`.
6. **Retire the publishing required-NEW blocker** (`hybrid/publishing.py`) and
   update the Checkpoint 6 tests that assert it
   (`test_a_required_new_record_role_blocks_publication`,
   `test_a_journey_on_a_module_less_course_still_blocks_publication`,
   `test_a_direct_service_publish_refuses_a_required_new_record_role`,
   `test_journey_publication_blockers_name_structure_then_roles`) — this is
   the deliberate, reviewed un-fail-closing of the Stage 2 rule.
7. **Deferred (explicitly out of scope now):** explicit claim UI for
   multi-attempt ambiguity, optional-NEW-role claiming, Recording Studio,
   journey-aware Check My Work, simulator-side review-mode hygiene fixes.

## 11. Automated test plan and acceptance criteria

New file `tests/test_stage3_record_provenance.py`; acceptance = all pass.

1. Creating a UCR while a required-NEW ucr role is open auto-claims it:
   association exists, `source=created_in_journey`, `record_created_at ==
   record.created_at`, role satisfies, journey completes.
2. Same for boe, consignment, mda (parametrized over the registry kinds,
   using each kind's real creation endpoint where practical).
3. Pre-existing record (created before the attempt started) does not claim —
   the role stays open with the existing freshness message.
4. Another student's record never claims (owner isolation).
5. A record is claimed by at most one attempt (second attempt/role stays
   open; the partial unique constraint backs the race).
6. Resubmit/submit does not create duplicate provenance (same row updated).
7. Provenance-write failure heals: suppress the receiver, create the record,
   run the reconciler, role claims (idempotent — running twice makes no
   second association).
8. Record deleted after claim: role fails closed; a replacement record
   re-claims.
9. Multiple eligible attempts: nothing auto-claims; both journeys show the
   open requirement (documented limitation test).
10. Journey-less creation: no association, simulator behaves identically.
11. `assign_record` refuses `CREATED_IN_JOURNEY` from external callers.
12. Publishing: a required-NEW role no longer blocks once the provenance path
    exists (Checkpoint 6 blocker tests updated accordingly).

## 12. Risks, blockers and deferred functionality

- **Auto-claim ambiguity** (multiple open NEW roles of one kind across
  attempts): safe-by-default (no claim) but a UX limitation; explicit claim
  UI deferred.
- **Clone semantics**: a cloned UCR is a genuine INSERT by the student and
  will claim a NEW role. If reviewers want clones excluded, the receiver can
  skip `derivation == "clone"` rows — decision required at implementation
  review. **[Recommendation]** allow clones (they are new records created by
  the student; `source_ucr` preserves the lineage).
- **Receiver ordering vs attachment saves**: provenance fires on the record
  INSERT, before attachments in the UCR save path; a condition could also
  assert attachment existence — out of scope (conditions verify record
  status/fields only, per `bindings.validate_binding`).
- **Signal invisibility to bulk operations**: rows created via
  `bulk_create` or raw SQL would not fire `post_save`. Verified: no such
  path exists for the four models today; the reconciler covers future ones
  within the eligibility window.
- **Stage 2 dependency**: retiring the publishing blocker (checkpoint 6)
  must come after the acceptance tests of checkpoint 5 prove the chain —
  otherwise the fail-closed rule would be lifted without a working
  replacement. Sequencing in §10 enforces this.
- **Simulator hygiene flags** (review-mode guard gaps, unlocked application
  numbering, `ucr_amend` docstring drift): recorded in the fact sheet;
  unrelated to provenance correctness, recommended as a separate simulator
  hygiene pass.
