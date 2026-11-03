# PostgreSQL test run — verification and results

> **Superseded.** This is a dated snapshot of an intermediate run (729 of 1,223
> tests passing, all failures traced to test-environment causes). Those causes
> were corrected; the final gate passed 1,227 tests. Read
> `docs/postgresql-compatibility-review-2026-11-03.md` for the current state.

**2026-11-03 · resumed from the interrupted run (~23%) · no code, migration, data, or test files changed**

Settings module for all runs: `config.settings.vps` (PostgreSQL via `.env`), pytest override
`--ds config.settings.vps`, `--reuse-db` against the manually created `test_icums_simulator`.

## Pre-flight verification (the five checks)

| # | Check | Result |
|---|---|---|
| 1 | `test_icums_simulator` exists, empty, owned by `myproject_user` | **Exists ✓, owned by myproject_user ✓ — NOT empty.** It holds the interrupted run's full schema: 102 public tables, `django_migrations` stamped with all 123 migrations, sampled data tables at 0 rows. The seed rows a fresh `migrate` would create are missing (notably `auth_group` = 0 rows). This state is consistent with a schema-only restore, not a live migrated database. |
| 2 | Django targets `test_icums_simulator`, not `icums_simulator` | ✓ `config.settings.vps` → `NAME=icums_simulator`, no `TEST` override, so the runner derives `test_icums_simulator`. |
| 3 | Active backend is PostgreSQL | ✓ `django.db.backends.postgresql`, vendor `postgresql`, server *PostgreSQL 18.3 (Windows)* at 127.0.0.1:5432. The SQLite `config.settings.test` module was not used. |
| 4 | Runner can initialize/manage tables in the isolated DB | ✓ Probe table create/insert/drop as `myproject_user` succeeded; smoke run (`tests/test_foundation.py`) created and used rows in the isolated DB. |
| 5 | Application (migrated) database untouched | ✓ `icums_simulator` (owner `postgres`, 102 tables, 24 MB) was only read at the catalog level (`pg_database`, `information_schema`). No writes, no migrations, no data changes anywhere outside the disposable test DB. |

Also verified: `myproject_user` does **not** hold CREATEDB (`rolcreatedb = false`) — which is why
the test DB had to be created manually, and why the runner cannot rebuild it (`--create-db` would
drop the existing one and then fail). This ruled out self-healing the seed problem below without
your approval.

## Results

### Focused Demonstration Studio suite
(`test_demonstration_isolation.py`, `test_demonstration_recording.py`, `test_instructor_demonstration_studio.py`)

**105 passed, 9 failed — 3:17.** (The earlier paused run reported 98/8 on a slightly different
collection.)

### Complete suite

**729 passed, 218 failed, 276 errors — 1,223 collected, 30:21.**
The totals are reproducible: two consecutive runs produced identical counts
(33:00 and 30:21).

## Why things failed — three causes, cleanly separated

### A. Missing seed rows in the reused database (~208 failed + all 276 errors) — NOT PostgreSQL-specific
The reused `test_icums_simulator` has every migration *recorded* as applied but carries none of
the rows a real `migrate` creates. The clearest single symptom: `auth_group` has **0 rows**, while
`accounts/migrations/0002_create_roles` is stamped applied. Every test that puts a user in the
Student/Instructor/Administrator group therefore dies with
`Group.DoesNotExist` — at fixture setup (→ the 276 ERRORs: `test_theory_flow` 29, `test_practice_desk` 29,
`test_guide_panel` 25, `test_rich_text_lesson_content` 20, `test_course_authoring_*` 48 …) or
mid-test (→ most of the 218 FAILEDs: `test_multi_enrolment` 19, `test_stage3_opening_lifecycle` 19,
hybrid workspace suites, `test_course_hierarchy`, `test_security_hardening` …).
Six representative failures were re-run individually across four different files; **all showed
`Group.DoesNotExist`**. On a freshly created SQLite test database (the normal suite) these rows
exist because migrations actually run — this failure class is an artifact of the schema-only test
database, not of PostgreSQL.

### B. Genuine PostgreSQL-specific failures: the 8 lock-contention tests
`test_demonstration_recording.py` — `test_sqlite_lock_contention_is_retried_and_other_errors_are_not`,
`test_a_locked_statement_is_run_again_until_it_lands`, `test_contention_that_outlasts_the_budget_becomes_a_refusal`,
`test_a_lifecycle_transition_repeats_after_a_lock_and_applies_once`, `test_a_binding_read_reruns_after_a_lock`,
`test_a_database_too_busy_to_answer_keeps_the_lesson`, `test_an_endpoint_answers_a_lock_with_503_not_500`,
`test_the_studio_page_itself_still_persists_nothing` (this last one is cause C, actually — see below).

Seven tests fail because contention detection is **deliberately vendor-gated**
(`hybrid/demonstrations.py:215-229`): on SQLite it recognises the message
`"database is locked"`; on PostgreSQL it recognises **only SQLSTATE codes**
(`_POSTGRES_CONTENTION_CODES`, e.g. 40001/40P01/55P03). The tests fake SQLite-shaped
`OperationalError("database is locked")` errors, which PostgreSQL correctly refuses to treat as
contention, so the error propagates and the test fails. The product code has an explicit
PostgreSQL path; the tests simply never exercise it with PG-shaped errors (e.g. `pgcode=40001`).
Fixing this means changing the tests to fake vendor-appropriate errors — a test change, which the
brief forbids, so it is reported, not made.

### C. Environment staleness: the staticfiles manifest (2 failures)
`test_the_studio_page_itself_still_persists_nothing` and
`test_instructor_demonstration_studio.py::test_the_studio_persists_nothing` fail with
`ValueError: Missing staticfiles manifest entry for 'css/demonstration-studio.css'`.
Under `config.settings.vps` the manifest storage is active, and the existing manifest
(`local_data/static_collected/staticfiles.json`, 215 entries) predates the new studio stylesheet.
Running `collectstatic` under the VPS settings would regenerate it (writes only to
`local_data/static_collected/`). Not done — it changes workspace state and needs your OK.

## Remedies requiring your decision (none executed)

1. **Seed the test database properly.** Options, in order of cleanliness:
   a. Temporarily grant `CREATEDB` to `myproject_user`, run the suite **once** without
      `--reuse-db` (runner rebuilds the disposable DB and runs all 123 migrations for real,
      including `0002_create_roles`), then revoke the privilege; from then on `--reuse-db` is safe
      and stable. The disposable DB is dropped and rebuilt by the runner itself.
   b. Or insert the missing seed rows directly into `test_icums_simulator` (touches data in the
      disposable DB; works but leaves a hand-made state).
2. **Regenerate the staticfiles manifest** (`collectstatic` under VPS settings) to clear cause C.
3. **Decide the lock-test design**: have the contention tests fake vendor-appropriate failures per
   backend (SQLSTATE for PostgreSQL, message for SQLite), or split them by vendor. A test change —
   yours to approve.

## Bottom line

- The isolated `test_icums_simulator` works, is correctly owned, and Django/pytest target it
  exclusively; the application database was never touched.
- Of 1,223 tests, **729 pass on PostgreSQL**. Essentially all 494 failures/errors trace to the
  schema-only state of the reused test database (missing seed rows) and one stale staticfiles
  manifest — environment artifacts, not PostgreSQL incompatibilities.
- The only *genuine* PostgreSQL-specific signal in the suite is the vendor-gated contention
  handling: 7 demonstration-recording tests fake SQLite-shaped lock errors that the PostgreSQL
  path (correctly, by design) does not treat as contention.
