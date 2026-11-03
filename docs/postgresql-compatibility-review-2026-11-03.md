# PostgreSQL compatibility review — ICUMS Simulator

**2026-11-03 · `config.settings.vps` (PostgreSQL 18.3) · `--reuse-db` against the disposable `test_icums_simulator`**

Baseline full suite: **10 failed, 1215 passed** (36m10s). Every failure was
classified and corrected; none was an application defect masked by SQLite.
Targeted PostgreSQL gates then passed in full, followed by one final full-suite
gate (results at the end).

## Method

For each installed application: models and model managers, migrations
(including `RunPython` data migrations), ORM queries, transaction boundaries and
row locking, unique constraints and `IntegrityError` handling, concurrent write
paths, and database-dependent tests. Corrections were limited to confirmed
PostgreSQL incompatibilities and their tests; no UI, copy, theme or business
rule was changed.

Checks applied throughout:

- `select_for_update()` on queries that also join a nullable relation (PostgreSQL
  refuses `FOR UPDATE` on the nullable side of an outer join);
- every lock site inside an `atomic()` block;
- `IntegrityError` handlers that classify a collision — they must recognise
  PostgreSQL's constraint name, not only SQLite's message text;
- read-then-write allocations against a unique constraint;
- JSON path lookups, case-sensitive comparisons, date/time parts, raw SQL;
- backend-dependent test assumptions (static URLs under manifest storage,
  `varchar` lengths, per-table sequences, SQLite-only error text).

## Baseline failure taxonomy

| Class | Tests | Cause | Correction |
|---|---|---|---|
| Manifest static URLs asserted without hashing | 6 | `ManifestStaticFilesStorage` rewrites URLs to `name.<hash>.css` | assert through `django.templatetags.static.static()` |
| `varchar(20)` enforced | 1 | a 22-character `temp_no` fitted SQLite, not PostgreSQL | shortened the fixture value |
| SQLite-only contention injection | 2 | tests raised `OperationalError("database is locked")`, which PostgreSQL never emits | inject the running backend's contention shape |
| Wrong id used for a URL | 1 | `ucr-amend` was addressed with the MDA request's pk; it matched the UCR pk only because SQLite restarts per-table sequences in a fresh database | address the amend by the UCR's own pk |

## Coverage matrix

`SFX` = `select_for_update` sites, `atomic` = `transaction.atomic` uses,
`uniq` = field-level `unique` plus table-level unique rules, `integ` =
`except IntegrityError` handlers in the application's own code.

| Application | Models | Migrations (data) | SFX | atomic | JSONField | uniq | integ | Inspected | Corrections |
|---|---|---|---|---|---|---|---|---|---|
| accounts | 5 | 10 (2) | 1 | 2 | 0 | 10 | 0 | models, migrations, `StudentIdSequence` allocator (locked), credential admin | none |
| assessment | 2 | 2 (1) | 0 | 0 | 1 | 4 | 0 | tax-code seed, preview computation (Python `Decimal`) | none |
| assessments | 10 | 4 (1) | 2 | 3 | 0 | 18 | 0 | attempt numbering (Enrolment lock), snapshot items, `bulk_create` | none |
| audit | 1 | 1 (0) | 0 | 0 | 1 | 1 | 0 | model, queries | none |
| core | 0 | 0 | 0 | 3 | 0 | 0 | 0 | shared dashboard/throttle helpers (no DB surface) | none |
| evaluations | 8 | 1 (0) | 0 | 3 | 2 | 15 | 0 | revisions, ordering, queries | none |
| hybrid | 18 | 12 (2) | 16 | 31 | 2 | 42 | 4 | all journeys/evidence/demonstration models; every lock, retry and integrity classifier | 5 code, 2 new tests |
| instructor_portal | 0 | 0 | 5 | 17 | 1 | 0 | 0 | every lock site, course/lesson/module mutations, roster actions | 1 |
| learning | 6 | 9 (2) | 1 | 2 | 0 | 9 | 0 | lesson content, checks, rich-text media lifecycle | 2 |
| onboarding | 5 | 8 (0) | 0 | 1 | 0 | 10 | 0 | programmes, editions, enrolments | none |
| progress | 3 | 3 (0) | 0 | 0 | 0 | 6 | 0 | progress rows updated by the lesson view | none |
| reports | 3 | 1 (0) | 0 | 2 | 2 | 7 | 0 | report queries and aggregates | none |
| scenarios | 31 | 54 (13) | 5 | 12 | 17 | 61 | 1 | all simulator records, sequences, JSON payloads, search filters | 1 code, 1 new test |

Raw SQL: none in application code. JSON key lookups exist only in the UCR
search filters (`form_data__…__icontains`); date-part lookups: none.

## Code corrections

| Location | Defect | Correction |
|---|---|---|
| `hybrid/verification.py` | `record_open` locked `JourneyAttempt` while joining the nullable `current_journey_step` → `FOR UPDATE cannot be applied to the nullable side of an outer join` (56 test blocks) | `select_for_update(of=("self",))` |
| `hybrid/verification.py` | opening retries recognised SQLite contention only | centralised `is_database_contention()`: SQLite from the message, PostgreSQL from the SQLSTATE found through `__cause__` (Django rebuilds driver exceptions) |
| `hybrid/journey_verification.py` | verification retries recognised SQLite contention only | uses `verification.is_database_contention()` |
| `hybrid/demonstrations.py` | second copy of the contention classifier | imports the single implementation from `verification` |
| `hybrid/attribution.py` | any `IntegrityError` was reported as "already claimed" | `_is_claim_collision()` maps only `unique_created_in_journey_record_claim` / `unique_active_record_per_role` (PostgreSQL constraint name or SQLite message); everything else propagates |
| `hybrid/journey_services.py` | `assign_step` read the highest `journey_order` without a lock | locks the `PracticalJourney` row before reading and appending |
| `instructor_portal/views.py` | `enrolment_withdraw` locked while joining nullable `enrolled_by` | `select_for_update(of=("self",))` |
| `scenarios/views.py` | MDA monthly number was read-then-written with no arbiter (`unique_mda_monthly_sequence`, `application_no`) | savepoint + bounded re-allocation on a collision; generated-number uniqueness excluded from `full_clean` so a lost race retries instead of returning 400 |
| `learning/views.py` | lesson-check `attempt_number` was `Max + 1` outside a lock | computed and inserted under an `Enrolment` row lock inside `atomic()` |
| `learning/rich_text_images.py` | `body__contains` is case-sensitive on PostgreSQL but SQLite `LIKE` is not | `body__icontains` (keeps a file rather than deleting it on a case-only mismatch) |

## Test corrections

- Static asset claims now go through `static()`: `test_admin_portal_uniform_ui.py`
  (5 tests), `test_module_cover_image.py` (4 assertions), plus the seven files
  corrected earlier (`test_hybrid_record_confirmation`, `test_login_redesign`,
  `test_register_redesign`, `test_navigation_uniformity`, `test_mda_uniform_ui`,
  `test_local_serving_accessibility`, `test_ucr_lookup`).
- `temp_no` fixtures trimmed to the model's 20 characters:
  `test_stage3_evidence_primitives`, `test_stage3_journey_check_foundation`,
  `test_stage3_opening_lifecycle`, `test_stage3_journey_verification_flow`.
- `test_stage3_opening_lifecycle.py` injects the running backend's contention
  exception instead of SQLite's message.
- `test_demonstration_recording.py` / `test_demonstration_isolation.py`: the
  real-thread race helpers accept any backend's contention, not only SQLite's.
- `test_ucr_uniform_ui.py`: the amend page is addressed by the UCR's pk.
- New: `test_claim_collision_classifier_matches_only_the_claim_constraints`
  (PostgreSQL diag shape, SQLite message, foreign-key failure) and
  `test_mda_dialog_route_reallocates_after_a_monthly_sequence_collision`
  (a stale number is refused by the database, the route re-allocates and
  returns 201).

## Test-database initialisation (repeatable)

`conftest.py` overrides pytest-django's session setup. When a **reused**
PostgreSQL database whose name starts with `test_` no longer contains the
reference rows its migrations created (proxy: roles, port codes, customs
offices, HS codes, MDAs, regimes/procedures, training stakeholders, tax codes),
it drops that database's `public` schema and re-runs `migrate`.

Why it is needed: pytest-django orders non-transactional database tests last,
and each one's teardown is a database-wide `flush`. The flush empties every
table — including migration-seeded reference data — while `django_migrations`
stays stamped, so the next `--reuse-db` session would start migrated but empty.

Guarantees: nothing is seeded by hand, no data is written to `icums_simulator`,
test isolation is unchanged, and a healthy reused database is left untouched
(one canary query per session). It is skipped for SQLite, for `--no-migrations`,
and when the database is created fresh (`--create-db`).

## Targeted PostgreSQL runs

| Gate | Tests | Result |
|---|---|---|
| Hybrid: attribution, opening lifecycle, demonstrations, journey services/flow, evidence | 248 | **248 passed** (8m30s) |
| Scenarios / learning / shared UI: creation ledger, UCR (incl. amend), MDA, cover images, admin portal, rich text | 165 | **165 passed** (4m49s) |
| Cross-application integration: acceptance, enrolment, theory, assessments, dashboards, scenario engine, guided binding, security, migration order, authoring | 205 | **205 passed** (8m39s) |

The hybrid gate includes the real PostgreSQL lock test (a second psycopg
connection holding `ACCESS EXCLUSIVE`, `NOWAIT` → SQLSTATE `55P03`) and the
threaded first-opening / sequence races. The test-database repair was exercised
twice: the hybrid and final gates each started from a flushed database and
rebuilt it before the first test.

## Final full-suite gate

See "Final result" below.

## Remaining risks

1. `instructor_portal._next_version_number` is still a read-then-write counter;
   a concurrent "new draft" for the same programme could collide. In practice
   the existing-draft check serialises the action; no failure was observed.
2. Section and knowledge-check `order` counters use `Max + 1` with no unique
   constraint, so they have no database backstop (ordering only, no data loss).
3. `ManifestStaticFilesStorage` still requires `collectstatic` after asset
   changes; this is a deployment step, not a code defect.
4. Rebuilding a reused test database needs the database to exist
   (`myproject_user` has no CREATEDB); the repair reuses the existing one.
5. The PostgreSQL lock tests depend on local PostgreSQL 18.3 behaviour.

## Restrictions honoured

No write, migration or data change to `icums_simulator` **during this review**;
nothing was committed, pushed or deployed; Stage 1B was not started; the
Demonstration Studio recording flag remains off; no theme, styling or
user-facing copy was changed.

The UUID/credential reconciliation was executed afterwards, on 2026-11-03, under
separate approval; see `docs/postgresql-migration-finalization-2026-11-03.md`.

## Final result

- Baseline: **10 failed, 1215 passed** (36m10s) — every failure in the taxonomy above.
- Final gate (`--reuse-db`, `config.settings.vps`, single run): **1227 passed, 0 failed**
  (35m24s). The two additional tests are the new claim-collision classifier and
  MDA sequence-collision regression tests.
- The gate started from a flushed, migrated-but-empty database and the
  `conftest.py` repair rebuilt it before the first test, so the run also
  re-verified Phase 4 end to end.
