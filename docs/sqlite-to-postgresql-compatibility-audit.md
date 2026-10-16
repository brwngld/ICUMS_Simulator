# ICUMS Simulator — SQLite to PostgreSQL Compatibility Audit

**Audit date:** 2026-10-16  
**Scope:** Read-only review of Django models, migrations, transaction handling, progress and assessment flows, simulator records, practical verification, database configuration, and data transfer.

No application code, migrations, database records, settings, or dependencies were modified during this audit.

## Executive summary

The project uses Django's ORM consistently and already includes PostgreSQL production settings and the Psycopg driver. Most schema definitions should migrate cleanly. PostgreSQL's real row-level locking and concurrent request handling, however, expose correctness risks that SQLite testing cannot validate.

| Result | Count |
|---|---:|
| Confirmed incompatibilities/defects | 4 |
| High-risk PostgreSQL/concurrency concerns | 5 |
| Medium/low risks | 6 |
| Confirmed compatible areas | 8 |

The most important issues are:

1. UCR numbering can race under concurrent submissions.
2. MDA application numbering uses `MAX + 1`, which can race.
3. Lesson knowledge-check attempt numbering uses `MAX + 1` without locking.
4. Practical attempt limits are not fully protected by a database invariant.
5. Several submit endpoints do not lock records before transitioning them from draft to submitted.

These problems may be difficult to reproduce under SQLite but can appear under PostgreSQL with concurrent users or duplicate browser submissions.

## Confirmed defects

### Critical — UCR number allocation is concurrency-unsafe

**Location:** `scenarios/models.py:609-623`

The allocator reads existing UCR values, calculates the maximum numeric suffix in Python, and adds one. Although the operation uses `transaction.atomic()`, no stable shared sequence row is locked. Two PostgreSQL transactions can calculate the same next number. The unique constraint will reject one request with `IntegrityError`, potentially producing an HTTP 500 and losing a valid submission.

**Recommended correction:** Use a dedicated counter row locked with `select_for_update()`, a PostgreSQL sequence, or a bounded retry around the unique constraint.

**Required test:** Submit two UCRs simultaneously through separate PostgreSQL connections and verify that both succeed with distinct numbers and no unhandled exception.

### Critical — MDA application numbering uses unlocked `MAX + 1`

**Locations:** `scenarios/views.py:1417-1431`, `scenarios/views.py:1449-1465`, and `scenarios/views.py:1804-1813`

The next `monthly_sequence` is calculated from the current maximum plus one. An atomic block does not lock a stable sequence record, so concurrent transactions can select the same next value. The database unique constraint protects stored integrity but turns the race into a failed request.

**Recommended correction:** Introduce a counter keyed by sequence month and lock that counter while incrementing it, or use a PostgreSQL sequence with formatting handled separately.

**Required test:** Submit two MDA applications concurrently for the same month and verify distinct numbers and non-500 responses.

### High — Lesson knowledge-check attempt numbering races

**Locations:** `learning/views.py:524-525` and `assessments/models.py:167`

Attempt numbers use `MAX(attempt_number) + 1` without an attempt-specific transaction or row lock. A double click, browser retry, or two tabs can attempt to create the same number. The unique constraint can then raise `IntegrityError`.

**Recommended correction:** Lock a stable parent row, such as the enrolment or lesson-check record, before calculating the number. Make duplicate submissions idempotent.

**Required test:** Submit the same knowledge check concurrently through two PostgreSQL transactions.

### High — UCR submission transition is not locked

**Locations:** `scenarios/views.py:653` and `scenarios/views.py:705-707`

The code checks whether a UCR has already been submitted and later changes its status without locking the record across the check-and-write operation. Concurrent requests can both observe the draft state and execute submission-side effects.

**Recommended correction:** Wrap the complete transition in `transaction.atomic()`, retrieve the UCR using `select_for_update()`, and make resubmission idempotent.

**Required test:** Submit the same UCR twice concurrently and confirm that one logical submission, number, and set of dependent records is produced.

## PostgreSQL risks requiring isolated testing

### High — Practical attempt creation and maximum-attempt limits

**Locations:** `scenarios/services.py:27-51` and `scenarios/models.py:497`

The service locks the enrolment row before checking for an existing attempt and assigning the next number, which is a good serialization mechanism. Safety nevertheless depends on every attempt-creation path acquiring the same lock. There is no conditional database constraint limiting a learner to one in-progress attempt for the same scenario version.

**Recommendation:** Add a conditional uniqueness constraint for one in-progress attempt per enrolment and scenario version while retaining the enrolment lock.

**Test:** Start the same practical simultaneously through two PostgreSQL connections.

### Medium — Practical action-history sequence allocation

**Locations:** `scenarios/services.py:58-79` and `scenarios/models.py:515`

The attempt is locked before state mutation and action sequence allocation. This should serialize correctly on PostgreSQL, and a unique constraint prevents duplicate sequence values. Compatibility depends on all action creation continuing to pass through this locked service.

**Test:** Send two actions for one attempt concurrently and verify consecutive sequences and deterministic final state.

### Medium — Practical verification JSON mutation

**Location:** `scenarios/verification.py:54-58`

The attempt is locked before `state_data` is changed. JSON is nevertheless read and rewritten as a whole. Any alternate writer that does not acquire the same row lock could overwrite unrelated changes.

**Recommendation:** Ensure every `ScenarioAttempt.state_data` mutation goes through a row-locking service.

### High — Theory attempt submission locking

**Locations:** `assessments/services.py:33-46` and `assessments/services.py:57-98`

Attempt creation locks the enrolment and is substantially safer. Submission is atomic but does not visibly reacquire the attempt with `select_for_update()` before checking status and writing responses. Concurrent submissions could both observe `IN_PROGRESS`; uniqueness constraints may turn this into an unhandled conflict.

**Recommendation:** Lock the attempt at submission start and treat an already-submitted attempt as an idempotent success or controlled conflict.

**Test:** Submit the same theory attempt concurrently.

### High — BOE submission is not visibly serialized

**Locations:** `scenarios/views.py:2770-2795` and `scenarios/models.py:1137`

The endpoint checks for an already-submitted declaration and later assigns a declaration number without visibly locking the declaration. The unique constraint protects number uniqueness but does not ensure idempotent submission or prevent duplicated side effects.

**Test:** Submit the same BOE concurrently and verify one number and one set of stage events.

## Schema and query compatibility

### JSON fields — generally compatible

Representative locations include `audit/models.py:22`, `assessment/models.py:51`, `scenarios/models.py:490`, and `scenarios/models.py:1126`.

Django `JSONField` supports SQLite and PostgreSQL; PostgreSQL stores it as `jsonb`. PostgreSQL will strictly reject non-serializable values, and JSON comparisons remain type-sensitive (`"1"` is different from `1`). Whole-object updates also risk lost concurrent writes.

**Pre-migration check:** Validate every JSON value and confirm its expected top-level type: dictionary, list, or nullable value.

### Case-insensitive uniqueness — compatible, subject to clean data

Functional and conditional uniqueness is defined at `scenarios/models.py:42` and `scenarios/models.py:116-117`. PostgreSQL supports these constraints.

Existing SQLite data must be checked for case-folding collisions such as `ABC123` and `abc123`, especially records created before the constraints existed or inserted outside Django.

### Text comparisons — medium risk

The project uses `iexact` and `icontains` extensively, including `scenarios/views.py:723`, `scenarios/views.py:1107`, and `assessment/service.py:39`. These queries are portable through Django.

Plain exact comparisons remain collation dependent. PostgreSQL exact comparison is normally case-sensitive. Identifiers intended to be case-insensitive should consistently use `iexact`, `Lower()`, or normalized stored values. Non-ASCII case behaviour must also be tested.

### Boolean fields — compatible

Django Boolean fields migrate cleanly. Before import, verify that legacy SQLite values are limited to valid Boolean representations, particularly where data may have been inserted outside Django.

### Date and time handling — mostly compatible

Application paths generally use `timezone.now()` and `timezone.localtime()`. Historical migration `scenarios/migrations/0029_renumber_ucr_sequences.py:25` calls `strftime()` on stored timestamps and should be exercised against timezone-aware PostgreSQL values during a clean migration.

Confirm the production PostgreSQL timezone and Django `TIME_ZONE`/`USE_TZ` settings before import.

### Foreign keys and cascading behaviour — generally compatible

The project deliberately uses `PROTECT` for historical/published records, `CASCADE` for owned dependent data, and `SET_NULL` for optional historical actors or resources. PostgreSQL will enforce these relationships rigorously.

Run orphan checks before export because SQLite can contain orphaned records if foreign-key enforcement was disabled during manual or external writes.

## Migration audit

### Confirmed positive findings

- No application raw SQL or backend-specific SQL was identified.
- Migrations primarily use portable Django schema and data operations.
- PostgreSQL supports the conditional and expression-based unique constraints in use.
- Psycopg is included at `requirements-production.txt:2`.
- Production settings already select `django.db.backends.postgresql`.

### Migrations requiring a clean PostgreSQL rehearsal

**Severity:** Medium

Run the entire migration history on an empty PostgreSQL database, paying special attention to:

- `scenarios/migrations/0016_consolidate_duplicate_stakeholder_names.py`
- `scenarios/migrations/0017_trainingstakeholder_unique_training_tin_case_insensitive_and_more.py`
- `scenarios/migrations/0019_restore_distinct_aster_roles.py`
- `scenarios/migrations/0029_renumber_ucr_sequences.py`
- reference-data seed migrations
- `scenarios/migrations/0006_infer_training_document_layouts.py`

A successful SQLite migration history does not prove compatibility with PostgreSQL collation, constraint timing, stricter typing, or locking.

## Database configuration

PostgreSQL production configuration exists at `config/settings/production.py:25-35`. It requires `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and optionally `POSTGRES_PORT`. Connection health checks and a 60-second persistent connection age are enabled.

Before production, verify:

- SSL configuration;
- statement and lock timeouts;
- connection limits relative to worker count;
- PgBouncer transaction-pooling compatibility if applicable;
- server timezone;
- automated backup and tested restore procedures.

## Safe SQLite-to-PostgreSQL migration strategy

1. Freeze application writes and take a verified SQLite backup.
2. Record the exact Git revision and Django migration state.
3. Run `manage.py check` and `showmigrations`.
4. Audit duplicates, orphaned foreign keys, invalid Booleans, oversized strings, malformed JSON, and inconsistent timestamps.
5. Create a new disposable PostgreSQL database.
6. Run all migrations from zero on PostgreSQL.
7. Run the complete automated suite against PostgreSQL.
8. Export SQLite data in dependency order or through controlled Django serialization.
9. Avoid blindly importing framework-generated content types and permissions; recreate or map them deliberately.
10. Import inside a controlled transaction.
11. Reset all PostgreSQL sequences for explicit integer/auto-increment primary keys.
12. Validate table row counts and relationship counts.
13. Validate case-insensitive uniqueness before enabling traffic.
14. Reconcile application counters including student IDs, BOE numbers, job numbers, UCR numbers, and future MDA sequence counters.
15. Run application smoke tests and all concurrency tests.
16. Rehearse backup and restore into a second disposable database.
17. Only then schedule the production cutover.

After importing explicit primary keys, use Django's generated sequence-reset SQL for installed apps. Application-managed counter rows such as `StudentIdSequence`, `BoeSequence`, and `JobSequence` must also be checked against the highest imported issued value.

## Required PostgreSQL test matrix

1. Clean migration from zero.
2. SQLite export to PostgreSQL import rehearsal.
3. Concurrent UCR submission.
4. Concurrent MDA application creation.
5. Concurrent BOE submission.
6. Concurrent theory-attempt creation.
7. Duplicate theory submission.
8. Concurrent lesson-check submission.
9. Concurrent practical-attempt creation.
10. Concurrent practical action application.
11. Practical maximum-attempt enforcement.
12. Progress completion from two browser sessions.
13. Case-insensitive stakeholder/provider duplicates.
14. JSON lookup and type validation.
15. Foreign-key deletion behaviour.
16. Transaction rollback after mid-submission failure.
17. Sequence reset after explicit-ID imports.
18. Unicode and case-comparison behaviour.

## Conclusion

The schema is broadly PostgreSQL-capable, and production configuration already targets PostgreSQL. No raw SQLite-specific SQL was found.

The application should not yet be declared PostgreSQL-ready because several identifier and attempt allocators rely on application-side `MAX + 1` logic or unlocked state transitions. PostgreSQL concurrency makes these paths more exposed than normal SQLite testing does.

The required next step is an isolated PostgreSQL migration and concurrency test run, followed by correction of the Critical and High findings before production data is transferred.
