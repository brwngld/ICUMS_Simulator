# UI 4 Stage 1 — recording foundation and UCR isolation plan

Date: 2026-11-02

Status: design only; no recording model, migration or write path has been implemented.

## 1. Current-state verification

The approved same-origin iframe checkpoint remains present:

- Studio URL: `/instructor/hybrid/lessons/<lesson UUID>/demonstration-studio/`.
- Initial real simulator URL: `/practical/portal/` (`scenarios.views.simulator_portal`, `templates/scenarios/portal.html`).
- The studio template contains the real iframe; it contains no reconstructed simulator controls.
- `DemonstrationFrameSafetyMiddleware` still limits development instructor iframe traffic to approved route families and GET/HEAD.
- Approved responses retain `X-Frame-Options: SAMEORIGIN`, `Content-Security-Policy: frame-ancestors 'self'`, and `Cache-Control: no-store`.
- Global `X_FRAME_OPTIONS = "DENY"` is unchanged.
- The safety middleware remains conditional on `DEBUG`, instructor identity and `Sec-Fetch-Dest: iframe`; ordinary top-level requests and student requests do not enter it.
- Current verification: `tests/test_instructor_demonstration_studio.py` plus `tests/test_navigation_uniformity.py`: 30 passed. `manage.py check`: no issues.

### UI changes since the checkpoint

`templates/core/base_simulator.html` has a later uncommitted navigation restyle: smaller brand lockup, tab-style service navigation, stable overflow-arrow slots, and tab-by-tab scroll stepping. Because UI 4 embeds the shared shell, this changes the iframe appearance as intended. It does not change iframe routing, framing, permissions or write protection.

Other current modifications to hybrid course/journey/editor templates and tests are unrelated authoring/copy work. One unrelated change also exists in `hybrid/instructor_views.py` below the Demonstration Studio view. They must be preserved and are not prerequisites for recording.

No current pending change conflicts structurally with the recording foundation. The main integration risk is overlapping edits in `hybrid/instructor_views.py` and `templates/hybrid/demonstration_studio.html`; implementation must patch narrowly and retain the existing unrelated changes.

## 2. Recommended isolation design

### Decision

Use the existing `UcrDeclaration` table with a nullable, server-controlled `demonstration_session` foreign key. Do not create a second demonstration-UCR table.

This is the smallest maintainable option because the UCR currently has a large field set, shared payload validation, draft update behaviour, attachments, numbering, search/detail rendering and downstream relationships. A dedicated table would either duplicate all of that or require a polymorphic abstraction larger than Stage 1.

The earlier proposal is insufficient if implemented as “add a nullable FK and filter where remembered.” Isolation must be fail-closed:

1. `UcrDeclaration.objects` becomes an ordinary-record manager whose default queryset includes only `demonstration_session IS NULL`.
2. `UcrDeclaration.all_objects` is the unfiltered manager and is used only by the demonstration service, cleanup code and narrowly reviewed administration code.
3. Demonstration services always query by all of: session ID, instructor ID, lesson ID and record ID.
4. The client can never submit `demonstration_session`; middleware/service derives it from the authenticated server-side binding.
5. The creation-evidence receiver explicitly ignores any instance with `demonstration_session_id` even though the default manager also hides it.
6. Existing verification and journey code continues through the ordinary manager and therefore cannot see demonstration UCRs. Add explicit regression tests so this is not an implicit assumption.

Reverse owner relations inherit the default manager, so `user.ucr_declarations` also excludes demonstrations. The Django base manager remains unfiltered for internal FK resolution; application code must not use `_base_manager` for business queries.

### Why not dedicated demonstration tables

Dedicated tables provide a stronger physical boundary but would duplicate or fork:

- approximately forty UCR data fields and status rules;
- `_parse_ucr_payload`, `_apply_ucr_payload`, `_ucr_record_payload` and attachment handling;
- create/edit/search/detail templates and JavaScript;
- numbering, validation and future UCR schema changes.

That duplication conflicts with the requirement to preserve and reuse the actual simulator. It is not justified for the UCR-only rollout when a fail-closed manager plus exact session scope gives enforceable application isolation.

## 3. Minimum data model

### `hybrid.DemonstrationSession`

- `id`: UUID primary key.
- `lesson`: FK to `HybridLesson`, `CASCADE`; only a draft lesson is eligible.
- `instructor`: FK to user, `PROTECT`.
- `state`: `recording`, `paused`, `stopped`, `discarded`.
- `started_at`, `paused_at`, `stopped_at`, `discarded_at`, `created_at`, `updated_at`.
- `next_sequence`: positive bigint, initially 1.
- `version`: positive bigint for optimistic lifecycle updates.
- optional `retention_expires_at` once retention is approved.

Database constraints:

- conditional unique constraint allowing at most one `recording`/`paused` session per instructor;
- check constraints requiring state-appropriate timestamps where portable;
- index on `(instructor, state)` and `(lesson, created_at)`.

Only the owning instructor may control the session in Stage 1. Administrator takeover, co-authoring and session reassignment remain out of scope pending approval.

### `hybrid.DemonstrationEvent`

- `id`: UUID primary key.
- `session`: FK with `CASCADE`.
- `sequence`: positive bigint.
- `event_type`: allowlisted enum (`navigation`, `record_created`, `record_updated`, with `selection` reserved but not enabled initially).
- `action_code`: allowlisted semantic code.
- `route_name`: approved Django route name or blank.
- `record_kind`: blank or `ucr`.
- `record_id`: nullable positive bigint, referring only to a record in the same session.
- `payload`: sanitized JSON object.
- `idempotency_key`: UUID supplied as an opaque retry key; never an authorization token.
- `created_at`: server timestamp.

Constraints:

- unique `(session, sequence)`;
- unique `(session, idempotency_key)`;
- indexes on `(session, sequence)` and `(session, event_type)`.

The payload schema is versioned in Python and rejects unknown keys. Initial payloads may contain only approved enum values such as `regime_code`, `transport_mode_code`, `result_status`, and `changed_fields` containing semantic field keys. It never stores names, addresses, descriptions, emails, phone numbers, document contents, passwords, cookies, CSRF/session tokens, headers or DOM snapshots.

### `scenarios.UcrDeclaration`

- nullable FK `demonstration_session` to `hybrid.DemonstrationSession`, `CASCADE`, indexed;
- ordinary default manager and explicit unfiltered manager as described above;
- optional database index `(demonstration_session, status, updated_at)`.

No demonstration field is added to `UcrDocumentAttachment`; it inherits scope through `ucr`. File uploads should be rejected for the initial rollout, avoiding a storage-retention expansion in Stage 1.

## 4. Lifecycle and server binding

### Start

`POST` to an instructor-only lifecycle endpoint validates the user, draft lesson and feature flag, creates a `recording` session, and stores only its UUID in the Django session under a dedicated key. A conditional unique constraint prevents two active sessions for one instructor. Starting while another session is recording/paused returns 409 rather than silently replacing it.

### Active binding

Every instructor iframe request is resolved server-side:

1. require authenticated instructor and `Sec-Fetch-Dest: iframe`;
2. read the session UUID from the server-side Django session;
3. load a `DemonstrationSession` matching UUID, instructor and allowed state;
4. verify its lesson remains in a draft programme version;
5. attach the resolved object to the request; never trust a form/query session ID.

Stage 1 intentionally supports one active recording per browser/Django session. Multi-tab independent recordings require a frame-scoped token propagation design and are a later decision.

### Pause and resume

- Pause is an authorized POST with an optimistic `version` check; state becomes `paused`.
- While paused, GET navigation remains available but no navigation event is appended and UCR save/update POSTs return 409.
- Resume changes the same session back to `recording`; sequence numbering continues.

### Stop

Stop seals the stream. State becomes `stopped`; later event appends and UCR writes return 409. Demonstration records remain available only to the owner for review until discard/expiry. Stop never creates `PracticalStep`, verification evidence or published content.

### Discard

Discard is an authorized, confirmed POST allowed from recording, paused or stopped. In one database transaction it marks the session discarded, deletes demonstration events and demonstration UCR rows, and clears the active Django-session binding. It does not touch ordinary records or already approved lesson content.

Initial rollout rejects file uploads. If uploads are approved later, discard must collect storage names before row deletion and delete blobs with `transaction.on_commit`; a reconciliation command must clean any orphan left by storage failure.

### Ordering and idempotency

Do not rely solely on `select_for_update`: PostgreSQL enforces it, while SQLite treats it as a no-op. Use a portable optimistic allocation:

1. within `transaction.atomic`, read expected `next_sequence` and `version`;
2. conditional `UPDATE` the same recording session where state/version/counter still match;
3. if one row changed, create the event with that sequence;
4. if zero rows changed, retry a bounded number of times;
5. unique constraints remain the final guard;
6. on SQLite `database is locked`, use the repository’s bounded contention-retry pattern; PostgreSQL uses row locking/conditional updates normally.

Successful UCR save/update and its event must commit in one transaction. Failed or rolled-back writes create no success event. An existing `(session, idempotency_key)` returns the existing result without a duplicate event or record mutation.

## 5. UCR-only rollout

### Approved frame routes

Replace path-prefix write decisions with an explicit route-name/method manifest:

| Route name | Method | Purpose | Recording behaviour |
|---|---:|---|---|
| `simulator-portal` | GET | Initial real dashboard | Navigation only |
| `single-window-overview` | GET | Open Single Window | Record allowlisted navigation |
| `single-window-create-ucr` | GET | New or `?draft=<id>` form | Record open/reopen navigation after scope validation |
| `ucr-service-provider-lookup` | GET | Existing form lookup | Read-only; no event payload |
| `ucr-stakeholder-lookup` | GET | Existing form lookup | Read-only; no event payload |
| `ucr-save` | POST | Create or update demonstration draft | Only write-enabled simulator action |
| `single-window-search-ucr` | GET | Find/reopen this session’s drafts | Demonstration-scoped results only |

`ucr-submit`, clone, amend, attachment upload/download, reference search for downstream applications, consignment, MDA, BOE, assessment and delete routes remain denied in demonstration mode.

### Exact action sequence

1. Parent observes an iframe load and sends a CSRF-protected navigation event POST to the instructor recording endpoint. The server resolves the URL to an approved route name; no GET request mutates data.
2. `single-window-overview` records `single_window.opened`.
3. `single-window-create-ucr` records `ucr.create_form_opened`.
4. `ucr-save` reuses existing payload parsing/application functions but resolves scope through a new demonstration service. On first save it creates `UcrDeclaration(owner=instructor, demonstration_session=active_session)` and event `ucr.draft_created`.
5. The event stores only safe enum metadata and the demonstration record ID, never UCR free text.
6. `single-window-search-ucr` uses the unfiltered manager constrained to the exact active session; ordinary instructor searches continue using the default ordinary manager.
7. Reopening uses the existing `?draft=<id>` form path, but the demonstration resolver requires that the draft belongs to the active session and instructor.
8. A later `ucr-save` updates only that scoped draft and records `ucr.draft_updated` with semantic changed-field keys, not values.
9. Stop displays the immutable ordered event sequence for review. Lesson-step conversion remains a later stage.

Use a separate demonstration temporary-number prefix/allocator so demonstrations do not consume or collide with ordinary `TEMPUCR` sequences. Submission/final UCR numbering is out of scope.

## 6. Query-path impact and required files

### Foundation and lifecycle

- `hybrid/models.py`: session/event models and constraints.
- `hybrid/migrations/<new>.py`: session/event tables.
- `hybrid/instructor_urls.py`: start/pause/resume/stop/discard/events/review endpoints.
- new `hybrid/demonstrations.py`: authorization, state transitions, binding, sequence allocation, event validation, discard/retention service.
- `hybrid/instructor_views.py`: thin lifecycle endpoints and studio context; preserve unrelated changes in this already-dirty file.
- `scenarios/middleware.py`: replace the proof’s blanket read-only decision with route-name manifest resolution; keep fail-closed GET/HEAD behaviour when no valid active recording exists.
- `config/settings/base.py`: feature flag default off and existing middleware; do not alter global framing settings.

### UCR model and writes

- `scenarios/models.py`: UCR session FK, default ordinary manager, unfiltered manager, demo index/allocator; keep ordinary draft expiry separate.
- `scenarios/migrations/<new>.py`: nullable FK, indexes and manager state if serialized.
- new `scenarios/demonstration_ucr.py` (recommended): exact-session create/update/search/reopen services so `scenarios/views.py` does not accumulate mode branches.
- `scenarios/views.py`: route handlers delegate to ordinary or demonstration service; affected current functions are `single_window_create_ucr`, `_requested_ucr_draft`, `ucr_save_declaration`, `_ucr_search_queryset`, and `single_window_search_ucr`. Explicitly deny demo access in submit/clone/amend/reference/dependent-record paths.
- `scenarios/urls.py`: retain existing UCR URLs; transaction wrapper still covers `ucr-save`.
- `static/js/ucr-create.js`: send an idempotency UUID with save; no content capture or cross-window messaging.
- `templates/scenarios/ucr_create.html` and `templates/scenarios/single_window_search_ucr.html`: preferably no structural change; only approved status/copy changes if required by the locked-copy process.

### Contamination prevention

- `hybrid/creation_ledger.py`: explicit early return for demonstration records. This is mandatory because post-save signals receive the instance directly and bypass manager filtering.
- `hybrid/verification.py`: ordinary manager already excludes demonstrations; add regression assertions and optionally an explicit `demonstration_session__isnull=True` defense.
- `hybrid/attribution.py`, `hybrid/journey_provenance.py`, `hybrid/journey_services.py`: default manager/absence of creation ledger should fail closed; add explicit isolation tests at eligible-list, claim, provenance and role-satisfaction layers.
- `hybrid/journey_evidence.py` and `hybrid/journey_verification.py`: verify no demonstration association/evidence can be created even with forged IDs.
- `scenarios/bindings.py`: no new record kind; UCR remains the same model whose default manager is ordinary-only.

### Search, admin, reports, audit and files

- `scenarios/views.py`: ordinary search/detail/reference/application/BOE lookup paths inherit the default manager. Demonstration search is a separate exact-session path through the service.
- `scenarios/admin.py`: existing UCR admin remains ordinary-only. Demonstration inspection, if approved, belongs under a read-only `DemonstrationSessionAdmin`, not mixed into student UCR lists.
- `core/admin_dashboard.py`: default manager makes counts ordinary-only; add a regression test.
- `core/views.py`: initial rollout has no demonstration uploads. Before enabling uploads, private-media authorization must require exact demonstration-session ownership instead of accepting all staff.
- `scenarios/models.py` and `scenarios/management/commands/expire_ucr_drafts.py`: ordinary expiry must not delete demonstration records; add a separate demonstration-retention command.
- `audit/signals.py`: currently audits login/logout only. Add lifecycle audit events only after retention/metadata policy approval; never include UCR field contents.
- `reports/*`: no current direct UCR query path; regression tests must prove demonstration activity cannot produce completion/evaluation/certificate records through journey verification.
- `assessment/views.py` and dependent consignment/BOE paths: no Stage 1 modification if their routes remain denied and ordinary UCR manager hides demonstrations; add denial tests.

## 7. Migration and rollback plan

### Forward migration

1. Add `DemonstrationSession` and `DemonstrationEvent` in a hybrid migration.
2. Add nullable `UcrDeclaration.demonstration_session` in a later scenarios migration depending on the new hybrid migration.
3. Add indexes/constraints. No data migration is required: every existing UCR receives NULL and remains ordinary.
4. Deploy with recording feature flag off and iframe writes still denied.
5. Run isolation/read-only tests on both SQLite and PostgreSQL before enabling UCR recording.

The dependency direction is safe if the hybrid session/event migration is created first and does not depend on the new scenarios migration; the scenarios FK migration then depends on it. Avoid introducing a circular migration dependency.

### Rollback

- Before schema rollback, disable the feature flag and stop lifecycle/capture endpoints.
- Delete or export demonstration sessions/events/records according to the approved retention policy.
- Reverse the scenarios FK migration before reversing the hybrid session tables.
- Ordinary UCR rows are unaffected because their FK is NULL.
- A code rollback while the nullable columns remain is safe; a database rollback while newer code is active is not.

SQLite table rebuilds for field/constraint changes require a backup and maintenance window even though local datasets are small. PostgreSQL FK/index additions should use the deployment’s normal transactional migration process; assess lock duration on the UCR table before production rollout.

## 8. Test plan

### Permissions and binding

- anonymous/student cannot create or control a session;
- instructor can act only on own draft lesson and own session;
- published/retired lesson rejects start and continued writes;
- forged session UUID, stale Django-session binding and mismatched lesson fail closed;
- one-active-session constraint survives concurrent starts;
- top-level instructor simulator traffic does not inherit demonstration writes.

### Lifecycle

- valid transitions: recording→paused→recording→stopped and any live/stopped state→discarded;
- invalid/repeated transitions return stable 409 responses and do not change timestamps/version;
- paused/stopped/discarded sessions reject UCR writes and event append;
- stop seals order; discard clears server binding and scoped data.

### UCR isolation

- ordinary managers, owner reverse relations, search, detail, reference lookup, admin list and dashboard counts exclude demo UCRs;
- exact-session service sees only its own demonstrations;
- instructor A cannot read/update/discard instructor B’s UCR or session;
- ordinary UCR cannot be converted to demo scope by payload; demo UCR cannot be detached to ordinary scope;
- submitted/clone/amend/consignment/MDA/BOE routes reject demo records;
- ordinary draft expiry ignores demonstrations; demonstration cleanup ignores ordinary drafts.

### Attribution and verification

- demonstration UCR creation writes no `SimulatorRecordCreation`;
- it never appears in `eligible_creations` or existing-record pickers;
- forged attribution/association IDs fail provenance;
- saved-record verification ignores it even when owner/status/field values would otherwise match;
- no `JourneyVerificationEvidence`, verified `StepEvent`, lesson completion, practical evaluation, completion record or certificate results from it.

### Events and idempotency

- exact monotonic sequence under normal and concurrent append;
- same idempotency key returns the original result and creates no duplicate UCR/event;
- different keys create distinct ordered events;
- unknown event/action/payload keys are rejected;
- failed validation/rolled-back UCR save produces no success event;
- free-text and secrets never appear in event payload, logs or audit metadata.

### Cleanup

- discard deletes only records/events in the exact session;
- session expiry follows approved retention and is idempotent;
- future attachment cleanup deletes rows and blobs after commit and tolerates missing blobs/storage failure;
- lesson deletion cascade cannot leave demonstration records or files.

### Database matrix

- SQLite: run lifecycle, conditional-unique, optimistic counter, lock retry and discard suites against file-backed SQLite as well as the in-memory test database.
- PostgreSQL: run the same suite, plus `select_for_update`/concurrent transaction tests using separate connections and the production isolation level.
- Assert the same public outcomes rather than assuming identical lock exceptions.

## 9. Acceptance criteria

Stage 1 foundation is acceptable only when:

1. Existing real iframe/navigation and global framing protection tests still pass.
2. Feature flag off preserves the current read-only proof exactly.
3. Only the explicit UCR manifest can write when a valid owned recording is active.
4. Ordinary/student queries cannot retrieve demonstration UCRs by list, search, direct ID, reverse relation or downstream reference.
5. Demonstration creation produces no learner creation ledger, attribution, verification, completion, evaluation or report evidence.
6. Pause/stop/discard are enforced server-side under concurrency.
7. Event order and idempotency are database-enforced on SQLite and PostgreSQL.
8. Discard/retention removes scoped data without touching ordinary records.
9. No passwords, tokens or free-text UCR contents enter the event stream.
10. No simulator UI is duplicated and existing student behaviour remains unchanged.

## 10. Decisions requiring approval

1. Approve the fail-closed nullable-FK/default-manager design over dedicated demonstration-UCR tables.
2. Approve the one-active-recording-per-instructor/browser-session limitation for Stage 1.
3. Approve the UCR route manifest above and confirm that submit, clone, amend, attachments and downstream applications remain excluded.
4. Approve a separate demonstration temp-number namespace.
5. Approve retention: recommended default is immediate record/event deletion on discard, stopped-session retention for 30 days, then deletion; retain only a minimal lifecycle audit tombstone if policy requires it.
6. Decide whether Administrators may inspect sessions but not control them in Stage 1 (recommended), or may take over.
7. Approve file uploads remaining disabled until storage cleanup and private-media scoping are implemented.
8. Approve any future production copy/template/CSS changes under the theme/copy lock before implementation.
