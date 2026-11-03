# UI 4 Stage 1A.1 — acceptance audit and corrective pass record

Status: **audit complete, corrective pass applied, awaiting approval of one
migration (`hybrid.0012`).** Stage 1B not begun. Recording feature flag remains
`False` (`config/settings/base.py:118`); `ucr-save` remains `frozenset()` in
`DEMONSTRATION_ROUTE_PERMISSIONS`.

Recorded 2026-11-03. Read-only audit followed by the four authorized message
edits; nothing committed, pushed or deployed.

## D1–D8 audit verdict

All eight decisions verified against source (not the implementation report).
No functional blockers.

| Decision | Location | Verdict |
| --- | --- | --- |
| D1 scope column | `scenarios/models.py:566` (`editable=False`), `scenarios/admin.py` `exclude` | Holds; service assigns scope by attribute |
| D2 deletion guard | `hybrid/instructor_views.py` `delete_module`/`delete_lesson` via `demonstrations.lesson_is_recording()` | Holds for the live window; fails closed on DB contention |
| D3 `record_out_of_scope` | `scenarios/views.py` `_requested_ucr_draft` / `_addressed_demonstration_draft` | Holds; refusal precedes any write; other users' ids answer like unknown ids |
| D4 migration-test isolation | `tests/test_stage2_journey_migration.py` autouse leaf-restore fixture | Holds; inline Stage 3 repairs removed |
| D5 discard retention | `hybrid/demonstrations.py` `discard_recording`, `expire_demonstrations` | Holds; stopped **and** discarded collected on the 30-day stamp |
| D6 inactivity | `hybrid/demonstrations.py` `last_activity_at`, `_is_idle`, `seal_abandoned_session(s)`, `_refuse_if_idle`; migration `hybrid.0011` | Holds; deliberate activity only; both live states lapse alike |
| D7 join scoping | `scenarios/views.py` `ucr_attachment`, `core/views.py` `_may_see_private_media`, three admin `get_queryset` overrides | Holds; listing and search; upload to a demonstration draft refused before any attachment row |
| D8 contention | `_retry_on_contention` around every service entry point; endpoint last net | Holds on SQLite; **PostgreSQL unexecuted** (see below) |

## Deletion / cascade findings

- `DemonstrationSession.lesson` CASCADE; `DemonstrationEvent.session` CASCADE;
  `UcrDeclaration.demonstration_session` **CASCADE** (session expiry removes
  scoped records — not SET_NULL, so no leak into ordinary visibility).
- `DemonstrationSession.instructor` **PROTECT**: an instructor with any session
  row (including a terminal tombstone awaiting expiry) cannot be deleted until
  `expire_demonstrations` runs.
- `HybridLesson.module`, `HybridModule.course`, `HybridCourse.programme_version`
  all **PROTECT**. No hybrid course or programme-version delete route exists;
  no hybrid content or demonstration model is registered in the admin, so there
  is no admin bulk-delete path to a live session.
- The legacy `instructor_portal.views.course_delete` targets
  `learning.Course/Module/Lesson` (a different tree) and would raise
  ProtectedError while hybrid courses exist — pre-existing, fails safe, no data
  loss.
- Conclusion: an active recording cannot be deleted indirectly through any
  supported parent or administrative operation. The only cascade edge is lesson
  deletion, guarded by D2.

## Inactivity and retention findings

30-minute deadline from `last_activity_at` (`>=` boundary). Stamped by: start,
pause, resume, stop, event reservation (same statement as the counter), discard.
Not stamped by: `resolve_bound_session`, `session_payload`, `timeline` (passive
polling does not extend a recording). Paused lapses on the same predicate.
Sealed sessions are terminal (STOPPED), keep timeline and scoped records, and
release the one-live-slot partial unique index; `start_recording` seals a lapsed
held session before refusing. Stopped = `stopped_at + 30d`; discarded =
`discarded_at + 30d`; both stamped, never recomputed. Command
`expire_demonstrations` runs both sweeps, is idempotent, reports
`Sealed N abandoned, removed M expired.`, and is not self-scheduling.

Discrepancies found were cosmetic (test count, help text, cron comment) and are
fixed in the corrective pass below.

## UCR isolation findings

Ordinary manager covers search, detail, clone, amend and lookups. Attachments are
scoped at both doors (route and `/media/`), because both start on the attachment
and traverse to the UCR through the unfiltered base manager. Admin joins for BOE,
MDA and consignment exclude demonstration-linked rows in listing and search.
Ledger capture, attribution and verification read through the ordinary manager.

**Residual (theoretical, correctly gated):** student-facing BOE / consignment /
MDA listings filter by owner on their own model and join to the UCR without a
scope predicate. Unreachable today because no demonstration write path exists
and every creation path resolves its UCR through the ordinary manager with
`status=submitted`. If a later stage enables demonstration submit, those joins
need the same predicate. Recorded as a Stage 1B entry condition.

## Concurrency / PostgreSQL readiness

SQLite evidence only. **Zero tests have run on PostgreSQL** — the environment has
no driver installed. The classifier (`40001`, `40P01`, `55P03`) and the
`IntegrityError` name-matching helpers are unit-tested with monkeypatched
vendors, not against a real driver.

Pre-Stage-1B PostgreSQL gate (needs approval to install a driver and stand up a
server; nothing was installed during this audit):

1. Dedicated settings module with a Postgres database; run `migrate` forward and
   reverse for `hybrid.0011`/`0012` and `scenarios.0053`.
2. Demonstrate suites pass: `test_demonstration_recording.py` (77),
   `test_demonstration_isolation.py` (29), `test_hybrid_course_module_workspace.py`.
3. Same-instant start race: one winner, loser gets `session_active`, no 500.
4. Simultaneous appends: distinct, contiguous sequences; `next_sequence` = n+1.
5. Forced lock (`lock_timeout`) on a session row: 503 `session_busy` or a
   successful retry, never a 500.
6. Duplicate idempotency key concurrently: one event, both callers receive it.
7. `makemigrations --check` clean.

Open design item already documented: Stage 1B's save service must allocate and
insert in a savepoint per attempt, re-run the allocator on a `temp_no` unique
violation, and end in a controlled refusal — no `select_for_update` on the scan.

## Corrective pass (authorized)

Message strings now match the approved wording:

- `IDLE_MESSAGE` — "Recording stopped automatically after 30 minutes of
  inactivity. Your recorded activity has been preserved."
- `LESSON_RECORDING_IN_USE` — "This lesson cannot be deleted while a
  demonstration recording is active. Stop or discard the recording first."
- `MODULE_RECORDING_IN_USE` — "This module contains a lesson with an active
  demonstration recording. Stop or discard the recording before deleting the
  module."
- `record_out_of_scope` — "This declaration is not available for this
  operation."

Tests updated: the two wording assertions in
`tests/test_hybrid_course_module_workspace.py`; behavioural assertions unchanged.
Documentation updated: test count 76 → 77; inactivity sweep required whenever the
flag is enabled, including development/test environments.

## Pending (not done, awaiting approval)

- **`hybrid.0012_alter_demonstrationsession_retention_expires_at.py`** — required
  by the corrected `retention_expires_at` help text (help text only; no schema
  change). Not created. Until it exists,
  `test_hybrid_foundation.py::test_no_pending_model_changes_were_left_unmigrated`
  fails by design (it runs `makemigrations --check`).

## Verification at record time

- Focused demonstration + workspace suites: 128 passed.
- Full suite: 1222 passed, 1 failed — the drift guard above, caused solely by the
  unapproved migration.
- `manage.py check`: no issues.
- Disposable-database forward/reverse for `hybrid.0011` and `scenarios.0053`:
  passed (SQLite).
- `makemigrations --check --dry-run`: reports `hybrid.0012` (expected, pending).

## Pre-existing defects (not fixed, not regressions)

1. `ucr-save` with `show_provider: false` raises `KeyError: 'declarant_code'` in
   `_apply_ucr_payload` → 500. Pre-existing at commit 3a2f824; untouched by
   Stage 1A/1A.1.
2. `test_concurrent_first_opening_returns_the_one_persisted_generation`
   intermittently exhausts its 3-attempt opening budget. Proven pre-existing on
   clean HEAD in a throwaway worktree.
