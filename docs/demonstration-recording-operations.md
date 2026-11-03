# Demonstration recording — operations

Status: **Stage 1A foundation, the Stage 1A.1 hardening, the Stage 1B `ucr-save`
write and the Stage 1B.1 instructor-experience completion, built 2026-11-02/03
and not yet live.** The models, lifecycle service, endpoints, isolation, cleanup
and inactivity policy all exist and are tested, an authorized instructor with a
live recording can save a demonstration-scoped UCR through the existing Create
UCR screen (and reload it there afterwards), and the Demonstration Studio speaks
accurately about recording while the flag is on. `DEMONSTRATION_RECORDING_ENABLED`
is still `False` everywhere by default; nothing here is enabled in production.
The remaining simulator writes (`ucr-submit`, attachments, clone, amend, BOE,
MDA, consignment) are not built and not authorised.

## The flag

`config/settings/base.py:118` defines `DEMONSTRATION_RECORDING_ENABLED = False`.

- It is an **entry gate only**. Identity, lesson scope, session binding, lifecycle
  state and the route manifest are re-checked server-side after it, so turning it
  on widens no permission and no record scope. Every one of the six endpoints
  still refuses for a learner, for a bare `is_staff` account, for a stranger's
  session and for a published lesson with the flag on (see
  `tests/test_demonstration_recording.py`).
- To try it locally, set the value to `True` in `config/settings/local.py` (or
  temporarily in `base.py`) and restart the dev server. With the flag on, the
  Demonstration Studio's controls drive the real lifecycle endpoints, its
  timeline lists the recorded events, and a UCR saved from the simulator frame
  inside a live recording becomes a demonstration record on that session —
  never an ordinary one.
- It does **not** gate the read-only simulator iframe. That proof is separately
  dev-only: `hybrid/instructor_views.py` hands the studio a frame URL only when
  `settings.DEBUG`, and `scenarios/middleware.py:68` keeps the simulator
  `frame-ancestors 'self'`.
- Until Stage 1B is reviewed, leave it `False` in `production.py` and `vps.py`.
  There is no environment-variable override on purpose: an operator has to edit a
  settings file and deploy, which is the friction we want around a recorder that
  captures instructor actions.

## Lifecycle an operator should know

`hybrid/demonstrations.py` owns the states: `recording → paused → recording →
stopped`, plus `discarded`. A session is bound to the instructor's server-side
Django session (`ACTIVE_SESSION_KEY = "hybrid_demonstration_session_id"`); the
client never names a session it is acting on.

- **One live session per instructor**, enforced by a conditional unique constraint
  (`hybrid/models.py`, `one_live_demonstration_session_per_instructor`), not by a
  pre-check. A session left behind by a closed tab does not hold that slot forever:
  see §"Inactivity" below.
- **Inactivity**: a `recording` or `paused` session whose `last_activity_at` is 30
  minutes old is sealed (turned into a normal `stopped` session) by the first
  control the instructor presses, by the next `start` if they simply begin again,
  or by the cleanup command's first sweep. Sealing keeps the timeline and the
  demonstration records, starts the thirty-day retention clock, and releases the
  one-live-session slot. Nothing is deleted by a seal.
- **Only deliberate activity moves the deadline.** Pressing a control (a
  compare-and-set transition) and recording an event stamp `last_activity_at` in
  the same statement. Reads — resolving the binding, the studio's polling
  payload, the timeline — never touch it, so a page left open is not someone
  working. The seal itself is not activity either: the gap between
  `last_activity_at` and `stopped_at` is what distinguishes a lapsed recording
  from one the instructor stopped.
- **Stopping starts the clock.** `stop_recording` stamps
  `retention_expires_at = stopped_at + RETENTION_DAYS`, and expiry is judged
  against that stamp, never recomputed. Changing `RETENTION_DAYS` afterwards
  moves future sessions only.
- **Discarding deletes the data at once** — the session's events and its
  demonstration records (attachments cascade with the record). The session row
  itself survives as a tombstone carrying `discarded_at` and a
  `retention_expires_at` thirty days out, so a discarded session's metadata is
  collected by the same clock as a stopped one's data and nothing accumulates
  forever. Ordinary records and lesson content are unreachable from discard.
- **Sealed is terminal.** A `stopped` or `discarded` session cannot be resumed,
  restarted or reopened; the instructor starts a new recording, which is a new
  session with its own timeline.
- **No administrator takeover.** The Studio admin does not register
  `DemonstrationSession` or `DemonstrationEvent`, and every lifecycle entry point
  re-derives the session from `instructor=request.user`. An administrator cannot
  pause, resume, stop or discard another instructor's recording through any
  surface built in Stage 1A. Read-only administrative inspection is not built;
  see §"Open risks".
- Every transition is a compare-and-set on `(state, version)`, so a stale tab
  gets `stale_session` rather than silently driving an older row.

## Inactivity

`INACTIVITY_TIMEOUT = 30 minutes` in `hybrid/demonstrations.py`. The window is
deliberately short: it bounds how long a forgotten tab can capture a draft
lesson, and how long an instructor waits before their one live slot comes back.

| Where | What it does |
| --- | --- |
| `_refuse_if_idle` (called by `require_bound_session`) | The instructor pressed a control after the window: seal the session, drop the browser binding, answer `409 session_idle`. |
| `start_recording` | Defers to the seal: if the instructor's held session is idle, it is sealed and the new recording takes the freed slot; if it is still current, the start is refused with `session_active` as before. |
| `seal_abandoned_sessions()` | The sweep the command runs. Selects every live session past the window, oldest first, and seals each with a compare-and-set. A session a control moved first simply is not sealed. |

Both live states use one predicate, so `paused` lapses exactly like `recording`.
Sealing and stopping are the same state change internally; the only difference is
that a seal does not move `last_activity_at`. A late click and a polled page
receive the same message (`IDLE_MESSAGE`) and the same code (`session_idle`).

The sweep and the lazy seal are both idempotent: running either twice seals
nothing the second time, and running the command while a tab is open changes
nothing about that tab until it next acts — at which point it is refused and
told to start again.

## Cleanup: two commands, neither self-scheduling

Ordinary UCR draft expiry and demonstration expiry are deliberately separate,
because the ordinary manager cannot see demonstration rows:

| Command | Removes | Window | Sees demonstration rows? |
| --- | --- | --- | --- |
| `python manage.py expire_ucr_drafts [--days N]` | unsubmitted `TEMPUCR`/`KGHTESTUCR` learner drafts | default 7 days, recomputed each run | **No** — `scenarios.models.OrdinaryUcrDeclarationManager` filters them out |
| `python manage.py expire_demonstrations` | **sweep 1**: seals live sessions idle for 30 minutes; **sweep 2**: deletes `stopped` and `discarded` sessions past their stamped deadline, with their events and demonstration records | 30 minutes of inactivity; then `RETENTION_DAYS = 30` per session | Yes, and only those |

`expire_demonstrations` takes no arguments on purpose — the deadline was stamped
when the session closed, so a cron line cannot accidentally re-window it. It
prints `Sealed N abandoned, removed M expired.` and is idempotent: a session is
sealed once, collected once, and the next run reports zero for both counts.

Both sweeps matter. Without the first, an abandoned recording holds its
instructor's slot until they start something new. Without the second, a stopped
or discarded session's rows sit in the table forever — invisible to every
ordinary surface, but still there.

A session the database will not release does not abort the run: a lock that
outlasts the retry budget is logged and left for the next sweep.

Neither command is wired to a timer inside the application, exactly as
`expire_ucr_drafts` is not. Add both to the deployment crontab. The inactivity
sweep must run **more often than the window it enforces** — a session sealed at
the next run, not the next day:

```cron
# UCR draft expiry — ordinary learner drafts (already scheduled where learners use drafts)
15 3 * * * www-data cd /srv/icums-simulator && .venv/bin/python manage.py expire_ucr_drafts >> /var/log/icums-expire.log 2>&1
# Demonstration inactivity sweep — seals recordings idle for 30 minutes, then expires sealed ones
*/15 * * * * www-data cd /srv/icums-simulator && .venv/bin/python manage.py expire_demonstrations >> /var/log/icums-expire.log 2>&1
```

The demonstration line runs every fifteen minutes because it also runs the
expiry sweep; that is cheap (two indexed filters and, normally, no rows) and it
keeps the worst case for a forgotten recording at 30–45 minutes rather than a
day.

The inactivity sweep is required **whenever demonstration recording is enabled**
— not only in production. In development and test environments where the flag
has been turned on, an abandoned live session holds its instructor's one-live
slot until the sweep runs (or the instructor starts a new recording, which seals
the old one); run the command by hand there, or accept that a forgotten tab
blocks the next start until then. The expiry sweep matters the same way in any
environment where stopped or discarded sessions accumulate.

Skipping `expire_demonstrations` is a data-retention problem, not a correctness
one: a stopped or discarded session keeps its rows until the sweep runs, and
demonstration rows are invisible to every ordinary listing while they sit there.
Running it only occasionally is a usability problem: instructors wait for their
slot to come back.

## Isolation invariants

These hold with the flag on or off and are what makes a demonstration record safe
to create later. Proven one by one in `tests/test_demonstration_isolation.py`.

- `UcrDeclaration.objects` hides every row with a `demonstration_session`;
  `UcrDeclaration.all_objects` is the only way to see them, and
  `scenarios/demonstration_ucr.py` is the only code allowed to use it, always
  filtered by session and re-checked against `owner=session.instructor`.
- `Meta.base_manager_name = "all_objects"` keeps foreign keys, existence checks
  and `CASCADE` working on the unfiltered manager. The four things a manager
  cannot guard — joins/`select_related`, `_base_manager` traversal, `post_save`
  receivers and reverse-to-many accessors — are named in the docstring of
  `OrdinaryUcrDeclarationManager` (`scenarios/models.py:518`).
- **`session.ucr_declarations` is inert by construction.** A reverse-to-many
  manager is built from the related model's *default* manager, which is the
  filtered one, so it always returns nothing. Use
  `demonstration_ucrs(session)`. A test asserts this so nobody rediscovers it as a
  silent empty list.
- `SimulatorRecordCreation` is not written for a demonstration row at all
  (`hybrid/creation_ledger.py`), so a demonstration cannot become learner
  evidence, attribution material, a satisfied step, a completion or a dashboard
  number.
- `ordinary_ucr_scope_predicate()` is the explicit `Q(ucr__demonstration_session__isnull=True)`
  for any query that starts on another model and reads through to a UCR.
- Number allocation scans `all_objects`, so `DEMOUCR{yy}#######` and
  `TEMPUCR{yy}#######` draw from table-wide truth and cannot collide with each
  other or with an existing `ucr_no`.
- **The scope column cannot be edited.** `UcrDeclaration.demonstration_session`
  is `editable=False` and explicitly `exclude`d from `UcrDeclarationAdmin`, so no
  ModelForm — administrative or otherwise — renders a widget for it and an
  administrative save cannot clear a record's scope. The service assigns it on
  creation by ordinary field assignment.
- **Attachments are scoped at both doors.** `ucr-attachment` filters on
  `ucr__owner` *and* `ucr__demonstration_session__isnull=True`, and `_may_see_private_media`
  (`core/views.py`, the `/media/` path) starts its lookup on the attachment with
  the same join. A demonstration file is not served to its owner, to staff, or to
  an Instructor-group reviewer; demonstration attachments cannot be created
  because the save endpoint refuses before the upload is written.
- **Administrative joins name the scope.** BOE declarations, MDA consignment
  requests and consignment applications reach a UCR by join, so each admin
  overrides `get_queryset` to exclude rows whose UCR belongs to a demonstration.
  Both the changelist and its search run through that queryset.
- **The ordinary save and submit endpoints refuse a demonstration id.** Ordering
  matters: the ordinary manager cannot see the demo row, so addressing one would
  otherwise silently *create an ordinary draft in its place*. Both handlers
  answer `403 record_out_of_scope`. A demonstration draft belonging to someone
  else is answered exactly like an unknown id, so the refusal never confirms that
  another user's row exists.
- **The demonstration save never falls through to an ordinary write.** While the
  flag is on and the browser holds a binding, `ucr-save` POST belongs to the
  demonstration entirely (`scenarios.demonstration_ucr.demonstration_save_applies`).
  A binding that no longer resolves — stopped, discarded, sealed, published
  lesson — is refused with `409`, not answered with an ordinary draft: a browser
  that believes it is demonstrating must never quietly produce an ordinary
  record. Addressing an ordinary draft (one's own included), another session's
  record or an unknown id is the same `403 record_out_of_scope` as the ordinary
  route's refusal. No binding at all means the request is ordinary traffic and
  the ordinary route behaves exactly as before — including its `record_out_of_scope`
  refusals.
- **The Create UCR screen resolves through one scope at a time (Stage 1B.1).**
  After a save the page re-opens with `?draft=<id>`, and for a demonstration
  record the ordinary manager cannot see it. A bound browser therefore resolves
  `single-window-create-ucr` through its session scope only
  (`scenarios.demonstration_ucr.demonstration_create_draft`): its own draft
  reloads into the form, while an ordinary row (its own included), another
  session's record, an unknown id or a binding that no longer resolves renders
  an empty screen — never a leak, never a redirect, never an ordinary fallback.
  `recording` and `paused` both load (GET navigation stays available while
  paused); without a binding the screen keeps its ordinary behaviour, which is
  blind to demonstration rows by construction.
- **The page's own copy and affordances match the mode.** A demonstration save
  answers with `"demonstration": true`; the Create UCR script then reports a
  save-only confirmation and leaves Submit disabled — submission does not exist
  inside a recording. The Demonstration Studio's placeholder wording
  ("simulated", "not implemented") renders only while the flag is off; with it
  on, the page describes the recording that actually runs.
- **Lesson and module deletion stops while a recording is live.** Both builder
  delete views ask `lesson_is_recording()` first and refuse with a message that
  names the recording, never the instructor. A lesson whose recording has
  stopped or been discarded deletes normally (its rows cascade with the lesson).

## PostgreSQL: READ COMMITTED assumptions and contention handling

**Stage 1A / 1A.1 ran no test on PostgreSQL.** At that time the suite was
in-memory SQLite (`config/settings/test.py`) and the virtualenv had no
PostgreSQL driver installed. That is no longer the state: `psycopg` 3 is
installed, `config.settings.vps` runs the suite against PostgreSQL 18.3, and the
2026-11-03 compatibility review recorded **1,227 passing tests** — including a
real lock test that sees SQLSTATE `55P03`. The design notes below are kept as
written; the execution evidence now exists (see
`docs/postgresql-compatibility-review-2026-11-03.md`).

### What the code assumes

- **Isolation level `READ COMMITTED`** (PostgreSQL's default). Nothing here
  relies on repeatable read or serializable.
- **A conditional `UPDATE` is an atomic arbiter.** Two transactions updating the
  same row with `WHERE state=… AND version=…`: the second blocks until the first
  commits, then re-evaluates its `WHERE` against the committed row. Its version
  no longer matches, so it updates zero rows and the service raises
  `stale_session` — the *intended* outcome of a lost race, not an error.
- **A conditional unique constraint is the final arbiter.** Partial unique
  indexes (the one-live-session rule, `(session, sequence)`,
  `(session, idempotency_key)`) are enforced by the index; two concurrent
  winners collapse to one row and one `IntegrityError`, which the service
  classifies.
- **A plain `SELECT` is never blocked by a row lock.** Reads under READ
  COMMITTED take no locks and do not wait, so `timeline`, the payload counts and
  the owner-scoped attachment lookups have no separate contention path. On
  SQLite a read can still meet a writer's lock, which is why those calls are
  inside the endpoint's last-net refusal.
- **A lock error aborts its transaction.** Every retry attempt therefore opens
  its own `transaction.atomic()`. Retrying inside a caller's atomic block would
  only re-raise (`current transaction is aborted`) on PostgreSQL.

### Contention classification

`verification.is_database_contention()` is vendor-gated (the demonstrations
service imports it):

- SQLite: `verification.is_sqlite_contention()` — "database is locked" and
  "database table is locked" only.
- PostgreSQL: SQLSTATE `40001` (serialization failure), `40P01` (deadlock
  detected), `55P03` (lock not available). Everything else — `23505` unique
  violation, `23503` foreign key, `22001` value too long — is *not* contention
  and travels untouched.
- Any other vendor: never contention.

`_retry_on_contention(operation, attempts=4)` re-runs the whole operation and
ends in `503 session_busy`. It wraps every lifecycle transition, `start_recording`,
`discard_recording`, the binding read (`resolve_bound_session`), the
`live_session_for` read, and each per-session delete in the expiry sweep.
`hybrid/demonstration_views.py` adds a last net: a contention-shaped driver error
raised anywhere else in a request — including the read-only payload and timeline
— becomes the same 503, and any other database error is re-raised rather than
swallowed. The service tests prove the refusals with a monkeypatched vendor and
driver-shaped exceptions, and the PostgreSQL branch is now exercised for real
(`tests/test_stage3_opening_lifecycle.py`, `tests/test_demonstration_isolation.py`):
a second connection holds `ACCESS EXCLUSIVE`, and the retry sees SQLSTATE
`55P03` rather than a SQLite message.

### The event sequence (unchanged by the engine)

`(session, sequence)` is reserved with a compare-and-set on `next_sequence`, and
the event insert commits in the same savepoint. A sequence collision — which
should be structurally impossible — is classified as a retryable
`sequence_contention` and, after the budget, becomes a controlled 409, never a
bare `IntegrityError` 500.

### The reference allocator: Stage 1B retry design (implemented)

`scenarios.models.allocate_ucr_number(prefix)` is a read-then-write scan: it
selects the highest issued number for the stem from `all_objects`, adds one, and
checks the candidate is free, inside a short transaction loop. It never inserts.
Under READ COMMITTED two callers can both be handed the same candidate, and the
loser only finds out when its `INSERT` hits the table-wide unique `temp_no`.

The demonstration save (`scenarios.demonstration_ucr._insert_scoped_record`)
implements the Stage 1B design as written:

1. Allocate and insert inside one **savepoint per attempt**
   (`with transaction.atomic():` nested in the save's transaction), so a `23505`
   on `temp_no` rolls back only that attempt and the outer transaction survives.
2. On `IntegrityError` naming the `temp_no`/`ucr_no` unique index — classified
   by the driver's SQLSTATE (`23505`) first, with SQLite's message wording as
   the fallback (`_is_reference_conflict`) — **re-run the allocator** rather
   than reuse the candidate, bounded by five attempts with a small backoff.
   `test_a_lost_reference_race_is_retried_with_a_fresh_allocation` proves a
   caller recovers correctly; `test_concurrent_allocation_cannot_persist_the_same_reference_twice`
   still proves the table can never hold one reference twice.
3. Exhaustion is a controlled refusal (`503 reference_busy`, message wording
   shared with the allocator's own) — never a raw integrity error and never a
   silently re-generated reference.
4. **No `select_for_update` on the scan**, exactly as designed: a new row has no
   existing row to lock, and locking `UcrDeclaration` rows would contend with
   the lifecycle transitions for no protection the unique index does not
   already give.

Beyond the allocator, the save as a whole re-runs on contention
(`demonstrations.retry_on_contention`), like every lifecycle control: an
attempt a lock aborted committed nothing, so the retry re-derives the session,
the idempotency pre-check and the allocation against table truth. After the
budget the request is the controlled `503 session_busy`, and any other database
error is re-raised rather than swallowed.

### Stage 1B verification on PostgreSQL (2026-11-03)

Run with `--ds=config.settings.vps --reuse-db` against PostgreSQL 18.3,
`tests/test_demonstration_recording.py tests/test_demonstration_isolation.py
tests/test_demonstration_ucr_save.py tests/test_instructor_demonstration_studio.py
tests/test_hybrid_course_module_workspace.py`: **173 passed** (SQLite: 172
passed, 1 skipped — the real-lock test). On the list below:

1. The same-instant start race — covered by the existing
   `test_two_browsers_cannot_open_two_live_sessions` (`UniqueViolation` →
   `session_active`), passing on PostgreSQL.
2. The partial unique index — covered by the existing lifecycle tests, passing.
3. The allocator race with a real caller — done: both Stage 1B race tests
   (`test_two_concurrent_saves_allocate_distinct_references_and_sequences`,
   `test_concurrent_saves_with_one_key_persist_one_record`) run through the
   real service with two connections and pass repeatedly.
4. Migrations — no new migrations were needed for Stage 1B; the existing
   `hybrid.0010`/`0011` and `scenarios.0052`/`0053` remain verified from the
   Stage 1A.1 PostgreSQL run.
5. The endpoint last net — covered by `test_an_endpoint_answers_a_lock_with_503_not_500`,
   and the save route now maps a contention-shaped error to the same 503
   (`save_demonstration_ucr`).

## Test map

```bash
.venv/Scripts/python.exe -m pytest tests/test_demonstration_recording.py tests/test_demonstration_isolation.py \
    tests/test_demonstration_ucr_save.py tests/test_instructor_demonstration_studio.py \
    tests/test_hybrid_course_module_workspace.py -q
```

- `tests/test_demonstration_recording.py` (77 tests) — flag refusal,
  authorization, CSRF, server-side binding, forged/cross-instructor session ids,
  lifecycle and transitions, sequencing, idempotency (including malformed keys),
  the route manifest (since Stage 1B: `ucr-save` carries exactly one method,
  `POST`), payload shape, discard, retention, the inactivity policy,
  and the contention classifier.
- `tests/test_demonstration_isolation.py` (29 tests) — every ordinary surface
  that must not see a demonstration row: search, detail, owner reverse relation,
  admin changelist and dashboard, the BOE/MDA/consignment admin joins,
  attribution, journey verification, completion, attachment routes and `/media/`,
  the ordinary save/submit refusal, plus expiry and allocation.
- `tests/test_demonstration_ucr_save.py` (41 tests) — the Stage 1B write: when
  the save branch applies (flag + binding), the full authorization chain
  (student, cross-instructor, paused/stopped/discarded, sealed, published
  lesson, forged bindings), the flag-off and unbound-browser ordinary route,
  CSRF, draft addressing (own ordinary/foreign/unknown), the hidden-provider
  normalization, field-error shape, attachment refusal, idempotency (replay and
  malformed keys), reference-allocation recovery and exhaustion, event-failure
  rollback, two concurrency races through the real service, isolation after the
  save, the studio timeline, and the conflict classifier. Stage 1B.1 adds the
  `demonstration` response marker, the conditional studio copy gate, and the
  Create-screen reload (own session, paused, foreign/unknown/ordinary ids,
  stale binding, unbound blindness).
- `tests/test_instructor_demonstration_studio.py` — instructor gating,
  draft-lesson scoping, the flag-off Stage 1A markers (asserted unchanged), and
  since Stage 1B.1 the flag-on wording swap with the placeholders' absence.
- `tests/test_hybrid_course_module_workspace.py` — includes the lesson/module
  deletion guards for a live recording.
- `tests/demonstration_world.py` — the shared builders. `draft_world()` returns a
  world with **no** live session (use it when the test itself calls
  `start_recording`); `recording()` returns one that is already live.

Note for anyone adding migration-ordering tests: `MigrationExecutor.migrate(targets)`
treats the argument as the *whole desired state*. The Stage 2 migration test now
restores every app to its leaf after each test through an autouse fixture
(`executor.migrate(executor.loader.graph.leaf_nodes())`), rather than the Stage 3
tests repairing the schema inline. Naming only hybrid's newest migration rolls
`scenarios.0052` (which depends on `hybrid.0010`) back out of the shared test
database.

## Open risks

- **No administrative read-only inspection of demonstration sessions exists.**
  Decision D6 allowed it; building an admin surface was not approved in scope, so
  it is deferred. The models stay unregistered, which is also why no administrator
  can take over or discard another instructor's recording.
- The inactivity sweep is not self-scheduling. Until the cron line above is
  deployed, an abandoned recording holds its instructor's slot until the
  instructor starts a new one (which seals it) — the slot is no longer lost
  forever, but it can be lost until then.
- The route manifest authorizes reads, navigation and exactly one write
  (`DEMONSTRATION_ROUTE_PERMISSIONS`, with `ucr-save: {"POST"}`, served by
  `scenarios.demonstration_ucr.save_demonstration_ucr`). `ucr-submit`,
  `ucr-attachment`, clone, amend, BOE, MDA and consignment stay denied and are
  covered by manifest tests.
- **Navigation is not captured.** `append_navigation_event` exists and its
  routes are manifest-approved, but no view calls it yet — a recording's
  timeline currently holds only the UCR save events. Wiring screen-entry
  capture (probably at the frame boundary) is the next, separate decision.
- Demonstration UCR records now exist. `MEDIA` uploads stay out of scope: the
  demonstration save refuses any posted file (`400 attachment_denied`) before
  anything is written, so discard still has no stored files to collect. An
  upload path would need its own cleanup on discard first.
- The Studio's flag-on wording (banner, pill, status lines, scope note, discard
  confirm) and the save-only instruction on the Create UCR screen were approved
  as Stage 1B.1 and render only while the flag is on; the flag-off rendering is
  the original Stage 1A text, asserted unchanged by the studio tests.
- `_may_see_private_media` admits staff and Instructor-group members to any
  *ordinary* attachment path. That is a pre-existing media-breadth question,
  worth resolving before uploads are recorded. Demonstration attachments are now
  excluded from it entirely.
- A pre-existing defect was found while writing the D3 tests and is **not
  fixed** (out of scope): posting `show_provider: false` to the *ordinary*
  `ucr-save` raises `KeyError: 'declarant_code'` in `_apply_ucr_payload` and
  returns a 500. The demonstration save normalizes the same shape to blank
  provider columns (`_apply_payload`) rather than inheriting it; the ordinary
  route keeps its existing behaviour.
