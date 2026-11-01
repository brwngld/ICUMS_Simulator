# Database integrity and test baseline — checkpoint findings

Date: 2026-10-30. Read-only against `local_data/db.sqlite3`; every write landed
on a disposable copy under `.tmp/checkpoint/`. Nothing is committed, nothing is
migrated on the real database, no audit row was deleted.

Evidence marks: ★ = verified by me directly in this session · T = test run ·
**?** = inference from evidence, stated as inference.

## 1. Real database was not modified by this checkpoint ★

| Check | Before | After |
| --- | --- | --- |
| `sha256(local_data/db.sqlite3)` | `909fc728…b528` | `909fc728…b528` (unchanged) |
| File mtime | 2026-10-30 14:29:26 | 2026-10-30 14:29:26 |
| `count(django_migrations)` | 112 | 112 |
| `PRAGMA foreign_key_check` | 6 violations | 6 violations |
| `hybrid_hybridlesson.kind` | absent | absent |

Every connection to the real database used `sqlite3.connect("file:…?mode=ro", uri=True)`.

## 2. Task A — the six foreign-key violations ★

`PRAGMA foreign_key_check` returns exactly six rows. `rowid` is SQLite's implicit
row id; the primary keys below were resolved from it.

| # | Table | Primary key | Missing parent | Record detail |
| --- | --- | --- | --- | --- |
| 1 | `accounts_user_groups` | `id=47` | `accounts_user.id = 83aee2a213e241f982458c4650688cf9` | `group_id=2` (Instructor) |
| 2 | `onboarding_programmeversion` | `a585dca03b83493190e7b055f0c0b729` | `onboarding_programme.id = 9b0d4b2eaeb54aba8c524848d7ae6807` | `version=1`, `status=draft`, created 2026-10-30 14:24:49 |
| 3 | `audit_auditevent` | `5615c70adc21451bb6a3b17046f9c4d4` | same deleted user | `account.login`, ip `127.0.0.1`, 2026-10-30 14:25:54 |
| 4 | `audit_auditevent` | `31014ec62205452fb56fd499cb6b08bc` | same deleted user | `account.login`, 14:25:56 |
| 5 | `audit_auditevent` | `6d08c47af3f2420586769695520b1659` | same deleted user | `account.login`, 14:26:02 |
| 6 | `audit_auditevent` | `1d2f5426b90b4782a831b249010862cd` | same deleted user | `account.login`, 14:26:04 |

### Two parents, both deleted today

Everything traces to two deletions made **today between 14:24 and 14:29**, the
window in which `local_data/db.sqlite3` was last written:

* one instructor **user** `83aee2a2…` — four logins at 14:25:54–14:26:04, then the user row removed;
* one **programme** `9b0d4b2e…` — its programme version (14:24:49) and the whole course chain beneath it survived.

They were removed **outside the ORM** ★. Evidence: `AuditEvent.actor` is
`ForeignKey(…, null=True, on_delete=SET_NULL)` ([audit/models.py:12](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/audit/models.py#L12)), so an
ORM delete would have set `actor_id = NULL` instead of leaving a dangling id; the
`accounts_user_groups` join row would have been deleted by the many-to-many
collector; and `ProgrammeVersion.programme` is `on_delete=PROTECT`
([onboarding/models.py:99](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/onboarding/models.py#L99)), so an ORM delete of the programme would
have raised `ProtectedError`. SQLite does not enforce foreign keys by default,
so a raw `DELETE` silently leaves children behind.

**This is not pre-existing old garbage.** The previous delivery report called
these "pre-existing" rows that "have been sitting in the dev DB"; they are
same-day residue. The lesson-type session (screenshots at 15:16) genuinely did
work against a copy — the real DB mtime never moved past 14:29 — but an earlier
run today did write into the real database.

### Which rows belong to the throwaway Theory & Practical drafts ★

The orphaned programme version is the parent of exactly one course, and that
course is the studio-screenshot fixture:

```text
onboarding_programmeversion  a585dca0…  (orphan, created 14:24:49 today)
└── hybrid_hybridcourse      b531e14f…  code "studioshots-c"  "Customs Clearance"
    └── hybrid_hybridmodule  448d6213…  code "studioshots-m"  "Clearance module"
        └── hybrid_hybridlesson 8f49c103… slug "studioshots-ucr" "What is UCR"
            └── hybrid_practicalstep 073e0b70… key "ss-step" "Create UCR"
                └── (no verification conditions, no journey, no attempts)
```

Its lesson duplicates the real one beside it — real content is
`hui` → module `UCR` → lesson `what-is-ucr` "What is UCR" → step `new-step`
"Open Single Window" with two `screen_opened` conditions. The fixture has **zero**
`hybrid_verificationcondition`, **zero** journey rows and **zero** attempts, and
no other table references any of the five ids ★.

Everything else in the database belongs to other applications or to your real
drafts: 6 courses total (5 real + 1 fixture), 3 lessons (2 real + 1 fixture),
2 practical journeys (`hi` on `hui`, created today 11:54, still 0 journey steps),
all journey runtime tables empty (`hybrid_journeyattempt`, `hybrid_journeystep`,
`hybrid_stepevent`, `hybrid_journeyrecordassociation` = 0 rows) ★.

### Classification ★

| Records | Class | Reasoning |
| --- | --- | --- |
| `accounts_user_groups` id 47 | **Disposable test data** | Stale membership join row of the deleted screenshot instructor. No other table references that user. |
| `onboarding_programmeversion` a585dca0 + the 5-row course chain beneath it | **Disposable test data** | Fixture created today 14:24 for a screenshot run; duplicates the real UCR lesson; carries no learner or authoring value. |
| `audit_auditevent` 666–669 (4 rows) | **Audit / security data — special handling** | Append-only sign-in history. `accounts/models.py` describes `AuditEvent` as "Append-only record of security- and assessment-sensitive activity". Must not be auto-deleted. |
| Nothing else | — | No orphan touches `learning_*`, `assessments_*`, `progress_*`, `scenarios_*`, `evaluations_*`, `reports_*` ★ |

### Can a parent be restored instead of touching the children? ★

Not truthfully. The deleted parents are **not recoverable from any backup**:

| Backup searched | Contains programme `9b0d4b2e…`? | Contains user `83aee2a2…`? |
| --- | --- | --- |
| `backups/db-before-curriculum-fixes-20261023-183728.sqlite3` | no | no (latest user row 2026-10-16) |
| `db_backups/db_before_stage2_20261024_135915.sqlite3` | no | no (latest user row 2026-10-16) |
| `local_data/db.before_hybrid_migration.sqlite3` | predates the `learning_track` column, older still | — |
| `local_data/db.sqlite3.bak-2026101{5,6}-*` | predates | — |

Restoring would mean **inventing** a programme row and a user row to adopt the
orphans. For the audit rows there is a better option that invents nothing —
see R1.

## 3. Task A — minimum corrective actions proposed (not applied) ★

Smallest change per class, in the order that keeps every constraint satisfied.
Each is exactly what the ORM would have done on its own.

**R1 — audit rows: drop the dead pointer, keep every row.**

```sql
UPDATE "audit_auditevent" SET "actor_id" = NULL
 WHERE "id" IN ('5615c70adc21451bb6a3b17046f9c4d4','31014ec62205452fb56fd499cb6b08bc',
                '6d08c47af3f2420586769695520b1659','1d2f5426b90b4782a831b249010862cd');
```

`actor_id` is nullable precisely because the log outlives the actor
(`on_delete=SET_NULL`). The event, timestamp, IP and `target_id`
(`83aee2a2-13e2-41f9-8245-8c4650688cf9`, the same user in dashed form) all
survive, so nothing about *what happened* is lost. Zero rows deleted.

**R2 — stale group membership: one row.**

```sql
DELETE FROM "accounts_user_groups" WHERE "id" = 47 AND "user_id" = '83aee2a213e241f982458c4650688cf9';
```

The ORM deletes many-to-many join rows when a user is deleted; this finishes
that step.

**R3 — the fixture chain: five rows, children first.**

```sql
DELETE FROM "hybrid_practicalstep"        WHERE "id" = '073e0b70c96a47599961daf19e744f7a';
DELETE FROM "hybrid_hybridlesson"         WHERE "id" = '8f49c10305564cfb8b3c0f8f87609dbb';
DELETE FROM "hybrid_hybridmodule"         WHERE "id" = '448d621335b3425ca98f9fc99fbdf7f0';
DELETE FROM "hybrid_hybridcourse"         WHERE "id" = 'b531e14fb82245daa78d4f4167510f82';
DELETE FROM "onboarding_programmeversion" WHERE "id" = 'a585dca03b83493190e7b055f0c0b729';
```

Alternative if you would rather keep "Customs Clearance" as a course: `INSERT`
a fresh `onboarding_programme` and re-point `a585dca0…` at it — one invented
parent instead of five deleted rows. Workable, but it keeps a fixture whose
codes (`studioshots-c`, `ss-step`) are not real curriculum. **Recommend R3 as
deletion.** Your call; nothing here is applied without it.

Total footprint of R1+R2+R3: **10 rows touched, 6 deleted, 0 audit rows deleted.**

**R4 — the cause, not the symptom (needs your approval, code change).** Any
future raw delete of a parent will re-create this class of breakage. The narrow
option is a documented cleanup helper that deletes through the ORM (so
`PROTECT`/`SET_NULL`/m2m cascade behave) instead of `DELETE FROM`. Not
implemented; listed only so the decision is on the record.

## 4. Task A — hybrid 0006–0009 dependency map ★

| Migration | Depends on | Operations |
| --- | --- | --- |
| `0006_simulatorrecordcreation` | `hybrid/0005_journey_foundation`, swappable `AUTH_USER_MODEL` | CreateModel `SimulatorRecordCreation` + index `creation_evidence_owner_kind` + unique `unique_creation_evidence_per_record` |
| `0007_journeyrecordassociation_…claim` | `hybrid/0006`, **`onboarding/0008_programme_learning_track`** (already applied ★), swappable user | AddConstraint partial unique `unique_created_in_journey_record_claim` (`assignment_source='created_in_journey'`) |
| `0008_journey_verification_evidence` | `hybrid/0007` | CreateModel `JourneyVerificationEvidence`; AddField `stepevent.generation`; AddConstraint `unique_hybrid_step_opened`; 6 FK AddFields; 3 AddIndex; AddConstraint `unique_evidence_identity` |
| `0009_hybridlesson_kind` | `hybrid/0008` | AddField `hybridlesson.kind` (default `interactive_practical`) |

Strictly linear; `onboarding/0008` is the only cross-app edge and it is already
applied ★. So the whole pending set is exactly these four, and 0009 cannot be
applied without 0006–0008.

### Why the orphans block the migration — the real mechanism ★

It is not a "post-migrate sweep". The SQLite schema editor disables foreign-key
checking on entry and calls `check_constraints()` on **every** exit:

```python
# .venv/Lib/site-packages/django/db/backends/sqlite3/schema.py:38-42
def __exit__(self, exc_type, exc_value, traceback):
    self.connection.check_constraints()
    ...
```

and `check_constraints()` runs a **global** `PRAGMA foreign_key_check` and
raises on the first violation
([sqlite3/base.py:263-304](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/.venv/Lib/site-packages/django/db/backends/sqlite3/base.py#L263)).
Consequence: an orphan in *any* table — here `accounts_user_groups`, which has
nothing to do with hybrid — stops `migrate hybrid 0006` before it starts. It
also means only the **first** violation is reported, so fixing one row and
retrying reveals the next; all six must go before a single attempt succeeds ★
(reproduced exactly this way).

Note for the PostgreSQL cutover: that check is SQLite-specific; the same orphans
would ride straight through into Postgres, where the constraints are real ★.

## 5. Task B — `test_monthly_password_is_hashed_and_shown_once` ★ T

**Verdict: a stale assertion broken on 2026-10-21 by `59eb2d6` "Rebuild the
instructor training record page", 9 days ago. Not a regression from this week,
and the dashboard is not a "bare shell".**

Bisect evidence (single test, throwaway worktrees, HEAD untouched):

| Revision | Result |
| --- | --- |
| `7dc7108` (2026-10-21, before the credential self-serve work) | FAILED |
| `bddd076` (2026-10-21, self-serve credential management) | PASSED |
| `59eb2d6` (2026-10-21, roster rebuilt) → HEAD `bf08419` | FAILED |

`59eb2d6` even records it in its own message: *"Known state: the roster renders
an empty shell for an instructor with no enrolments
(test_monthly_password_is_hashed_and_shown_once)"* — that description is wrong.
Rebuilding the exact test scenario and dumping the HTML ★ shows the roster row
**is** rendered:

```text
password_state: awaiting_reveal | revealed_at: None | is_current: True
roster: 1 student
Simulator-access cell: "Login issued — Password issued — the student views it
   once on their credential page · Expires 1 Nov 2026, 00:00"
has 'shown once': False | has 'views it once': True
```

The assertion `assert b"shown once" in dashboard.content`
([tests/test_admin_enrolment.py:101](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/tests/test_admin_enrolment.py#L101)) can only pass through the
**revealed** branch of [templates/instructor_portal/dashboard.html:94](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/templates/instructor_portal/dashboard.html#L94)
("Password viewed by the student — shown once …"). The scenario never reveals:
`mark_revealed()` is called only from the student's own credential page
([accounts/views.py:208](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/accounts/views.py#L208)), and signing in at `simulator-login` does not
reveal. So the dashboard correctly shows the awaiting-reveal copy, whose wording
moved on 2026-10-21 to "views it once".

Proposed fix — test only, no template, no copy, no theme:

* **B1a (recommended, 1 line):** change the assertion to the copy that the
  awaiting-reveal state actually renders, e.g.
  `assert b"views it once" in dashboard.content`, keeping
  `assert raw_password.encode() not in dashboard.content` unchanged. The test
  still proves the password is never re-displayed to the instructor.
* **B1b (optional, slightly larger):** add a step where the student visits the
  credential page (`accounts/views.py:208`) and *then* assert `"shown once"` on
  the roster — this covers the revealed branch that currently has no assertion.
  No product change either way.

Either edit needs your approval because it changes a test's expectation.

## 6. Task B — the Stage 3 opening-lifecycle concurrency test ★ T

**Verdict: not reproducible, and the earlier symptom is fully explained by the
now-fixed migration helper. I found no defect left to fix.**

What I ran:

* `tests/test_stage3_opening_lifecycle.py` alone — **23 passed**, four
  consecutive runs (13.2s, 13.2s, 12.9s, 13.6s) ★
* full battery `pytest -q` — **twice**, each **1 failed, 1056 passed** (§7), the
  single failure being §5 above; the concurrency tests passed both times ★
* no random ordering plugin is installed (`pytest 9.1.1`, `pytest-django 4.14.0`,
  `addopts = -p no:cacheprovider`) ★ — so collection order is deterministic and
  "order-randomised flakiness" is not the explanation.

The mechanism that *was* there is real and worth stating: passing an
**already-applied** migration as a target puts the executor in backwards mode —

```python
# .venv/Lib/site-packages/django/db/migrations/executor.py:124-140
elif target in applied:
    next_in_app = sorted(n for n in …node_map[target].children if n[0] == target[0])
    for node in next_in_app:
        for migration in self.loader.graph.backwards_plan(node):
            if migration in applied:
                plan.append((…, True))     # ← unapply
```

so the old helper line `migrate([("hybrid", "0008_journey_verification_evidence")])`
**unapplied 0009** (its only same-app child) and dropped `kind` from the shared
test database; everything downstream then failed with "missing column" and, once
the same trick hit a table-creating migration, "missing table". Their first fix,
`("hybrid", None)`, was worse — that branch means *unmigrate the whole app*.
The shipped helper,

```python
executor.migrate([key for key in executor.loader.graph.leaf_nodes() if key[0] == "hybrid"])
```

is correct and future-safe: for an already-applied leaf, `next_in_app` is empty,
so the plan is empty and nothing is rolled back ★. **Endorse it.**

One cosmetic note: deleting the constant left two blank lines in a row at
[tests/test_stage3_opening_lifecycle.py:35](file:///C:/Users/Bernard/Desktop/learning/Icums_Simulator/tests/test_stage3_opening_lifecycle.py#L35).

If the flake reappears, the narrow way to catch it is to record the actual
exception (the threads swallow into a result list), not to add sleeps. I am not
proposing a change now, because there is nothing to fix.

## 7. Task C — migration rehearsal on disposable copies ★

Both copies are byte-identical to the real database at `sha256 909fc728…b528`
before use. Scripts live in `.tmp/checkpoint/` and refuse any path that is not
under that directory.

### Copy A — unrepaired, migration attempted

```text
migrate hybrid  →  django.db.utils.IntegrityError: The row in table
'accounts_user_groups' with primary key '47' has an invalid foreign key:
accounts_user_groups.user_id contains a value '83aee2a2…' that does not have a
corresponding value in accounts_user.id.
```

Post-failure state of copy A ★: hybrid applied still 0001–0005; no
`hybrid_simulatorrecordcreation`, no `hybrid_journeyverificationevidence`, no
`kind` column; still 6 violations. **The failure rolled back cleanly — no
partial schema.** That is useful: a blocked migrate on the real database is
recoverable by definition.

### Copy B — R1+R2+R3 applied, then migrated

```text
R1 audit_auditevent: actor_id set to NULL on 4 rows (0 rows deleted)
R2 accounts_user_groups: 1 row deleted (id=47)
R3 step/lesson/module/course/programmeversion: 1 row each, children first
violations before 6 → after 0
migrate hybrid → 0006, 0007, 0008, 0009 all applied (applied 15:48:38 → 15:48:40)
FK violations after migrate: 0
```

Schema fidelity checked in `sqlite_master` ★:

| Object | How it landed on SQLite |
| --- | --- |
| `unique_creation_evidence_per_record` | inlined as `CONSTRAINT … UNIQUE ("record_kind","record_id")` in `CREATE TABLE hybrid_simulatorrecordcreation` |
| `unique_evidence_identity` | same, in `CREATE TABLE hybrid_journeyverificationevidence` |
| `unique_created_in_journey_record_claim` | `CREATE UNIQUE INDEX … WHERE "assignment_source" = 'created_in_journey'` |
| `unique_hybrid_step_opened` | `CREATE UNIQUE INDEX … WHERE "kind" = 'opened'` |
| `stepevent.generation`, `hybridlesson.kind` | both columns present |
| `hybrid_journeyverificationevidence` FKs | all six `REFERENCES … DEFERRABLE INITIALLY DEFERRED` |

Nothing was faked or force-applied; no `--fake`, no `--reset`.

Row-count delta, real database → migrated copy ★ (nothing unexplained appears):

| Table | Real | Copy B | Cause |
| --- | --- | --- | --- |
| `django_migrations` | 112 | 116 | the four applied migrations |
| `django_content_type` | 93 | 95 | 2 new models |
| `auth_permission` | 372 | 380 | post-migrate permission sync |
| `accounts_user_groups` | 7 | 6 | R2 |
| `onboarding_programmeversion` | 10 | 9 | R3 |
| `hybrid_hybridcourse` / `…module` / `…lesson` / `…practicalstep` | 6 / 3 / 3 / 3 | 5 / 2 / 2 / 2 | R3 |
| `audit_auditevent` | 655 | 657 | R1 nulls 4 pointers, deletes none; **+2 rows are `account.login` events written at 15:49 by my own render check** (also `accounts_user.last_login` and 2 `django_session` rows) |
| new tables | — | `hybrid_simulatorrecordcreation`, `hybrid_journeyverificationevidence` (both 0 rows) | 0006, 0008 |

Every **other** table is content-identical, verified by hashing each table's full
row set except the new columns ★: `learning_*`, `assessments_*`, `progress_*`,
`scenarios_*`, `evaluations_*`, `reports_*`, `accounts_*` (bar the last_login
noted), `onboarding_*` (bar R3) — no differences.

Your real Theory & Practical content on copy B ★:

```text
module 'ucr' 'UCR'        course 'hui'  → lesson ('what-is-ucr', 'interactive_practical')  HTTP 200
module 'try' 'try'        course 'hi'   → lesson ('lesson-1',      'interactive_practical')  HTTP 200
```

Both `kind` values backfilled to the default, both module pages render
(`Lesson type`, `Open Demonstration Studio`, `Full editor`, the disabled
`guided_material_study` option all present), and both the new studio route and
the four-stage editor return 200 for an instructor ★. **The rehearsal therefore
also proves the current blocker clears:** with the working tree checked out
against the *unmigrated* real database, any `HybridLesson` query dies with
`sqlite3.OperationalError: no such column: hybrid_hybridlesson.kind` ★, so the
instructor module page cannot render at all until 0006→0009 are applied.

### Test battery

| Run | Result |
| --- | --- |
| `pytest -q` (run 1) | 1 failed, 1056 passed in 133.78s ★ |
| `pytest -q` (run 2) | 1 failed, 1056 passed in 129.64s — identical single failure, concurrency tests green again ★ |
| `manage.py check` | 0 issues ★ |
| `makemigrations --check --dry-run` | "No changes detected" ★ |
| failing test re-run at clean `bf08419` | fails there too ★ |

## 8. What was not done

_Superseded for the real database by §10, which records the repairs and migration
you authorized afterwards. The following describes the read-only checkpoint phase._

Real database untouched (§1); no audit row deleted; no migration applied,
faked, squashed or reset anywhere; nothing committed, pushed or deployed —
`git status` still shows the lesson-type work uncommitted plus my untracked
`docs/theory-practical-existing-system-inventory.md` and this file; no Stage 2
recording code written; no template, stylesheet or copy edited; the throwaway
worktrees used for the bisect were removed and the main tree was never reset or
stashed.

## 9. For your approval

1. **R1** — null the four `audit_auditevent.actor_id` pointers (keeps all rows). Yes / no.
2. **R2** — delete `accounts_user_groups` id 47. Yes / no.
3. **R3** — delete the 5-row `studioshots-*` fixture chain, **or** invent a parent
   programme and keep "Customs Clearance". Which one.
4. **Migrate** the real `local_data/db.sqlite3` from 0005 → 0009 afterwards, in
   that order, with a fresh `db.sqlite3.bak-<date>-pre-journey-migrations` copy
   first, per your existing backup convention. Yes / no.
5. **B1a or B1b** for the credential assertion — test-only change. Which one.
6. **No change** proposed for the concurrency suites beyond the helper fix that
   is already in the tree; I could not reproduce a failure. Accept that finding,
   or ask for a targeted repeat run.
7. **R4** (optional, later) — a documented ORM-based cleanup helper so future
   fixture teardowns cannot leave orphans again.

## 10. Executed under authorization — 2026-10-30 16:09 → 16:35 ★

Authorization: *ICUMS Simulator — Database Repair and Migration Authorization*
§1–§5. R1–R3 and the four migrations were applied to
`local_data/db.sqlite3`; §9 items 1–5 were approved, item 6 was accepted with
"report any recurrence", item 7 (R4) stays unexecuted. Nothing is committed,
pushed or deployed, and no recording code was written.

### 10.1 Preflight (§1) ★

| Check | Live value before touching anything | Matched the investigation |
| --- | --- | --- |
| Path resolved by `config.settings` → `.local` | `…\Icums_Simulator\local_data\db.sqlite3` | yes |
| `sha256` / mtime / size | `909fc728…b528` / 14:29:26.777220 / 9,302,016 B | identical to §1 |
| `integrity_check` / journal | `ok` / `delete`, page 4096, schema_version 832, no `-wal`/`-shm`/`-journal` | — |
| Migrations | 112 rows; hybrid 0001–0005 applied, 0006–0009 pending; `kind` absent | identical |
| `PRAGMA foreign_key_check` | exactly 6 rows: `accounts_user_groups` id 47 → `accounts_user` `83aee2a2…`; `onboarding_programmeversion` `a585dca0…` → `onboarding_programme` `9b0d4b2e…`; `audit_auditevent` rowids 666–669 → the same deleted user | identical, same UUIDs and timestamps |
| Fixture provenance | `studioshots-c` / `studioshots-m` / `studioshots-ucr` / `ss-step` all present; both parents still absent; `group_id=2` = `Instructor` | identical |
| Baseline census | 99 tables / 15,924 rows → `.tmp/checkpoint/census_before.json` | — |

**No drift** — the "stop and report differences" branch did not trigger. The only
line my checker flagged was its own notation (`'47'` vs `47` for an integer column),
not a database change.

`tasklist` + `Win32_Process` showed three live `manage.py runserver` processes
(PIDs 13064, 13900 on `127.0.0.1:8765 --noreload`, 21508), so the database was
treated as potentially active and **no raw file copy was used**.

### 10.2 Backup (§1) ★

```text
path     local_data/db.sqlite3.bak-20261030-160944-pre-hybrid-0006-0009
method   sqlite3.Connection.backup() — sqlite3_backup, 64 pages per step, source opened mode=ro
sha256   3918910d95e5253281fe40b1f39a938c9efb6e562694c5df44d61e752d74c1d9
size     9,302,016 bytes   timestamp 2026-10-30 16:09:44.195470
source   sha256 unchanged by the backup (909fc728…b528)
```

Verification of the backup itself: opens read-only, `integrity_check ok`, 99
tables / 15,924 rows with **zero** table or row-count differences against the
preflight census, 112 migrations with hybrid at 0005 and no `kind` column, all 6
pre-repair violations still present, the fixture course and all four audit rows
still present, and both real lessons (`what-is-ucr`, `lesson-1`) intact.

### 10.3 Repairs R1–R3 (§2) ★

Executed by `.tmp/checkpoint/repair_real.py`: `BEGIN IMMEDIATE` (fails fast if
another writer holds the lock) with `PRAGMA foreign_keys = ON`, every
precondition re-checked inside the transaction, and any mismatch — including an
unexpected inbound reference to a chain row — aborting with `ROLLBACK`. It was
first run against a scratch copy of the backup (`sha256 3918910d…`, identical)
and produced the same output there before touching the real database.

| | Statement | Rows | Effect |
| --- | --- | --- | --- |
| R1 | `UPDATE audit_auditevent SET actor_id = NULL WHERE id IN (5615c70a…, 31014ec6…, 6d08c47a…, 1d2f5426…)` | 4 updated | all four sign-in records preserved; table stays at 655 rows. Only the dangling FK pointer is removed — `target_id`, `summary`, `ip_address`, `created_at` still identify who signed in. |
| R2 | `DELETE FROM accounts_user_groups WHERE id = 47 AND user_id = '83aee2a2…'` | 1 deleted | 7 → 6; the `Instructor` group row itself is untouched. |
| R3 | children first: `hybrid_practicalstep` `073e0b70…` → `hybrid_hybridlesson` `8f49c103…` → `hybrid_hybridmodule` `448d6213…` → `hybrid_hybridcourse` `b531e14f…` → `onboarding_programmeversion` `a585dca0…` | 5 deleted | the `studioshots-*` fixture chain only. |

Pre-conditions confirmed inside the transaction: the four audit rows still keyed
to the absent user with `action_code='account.login'`; group row 47 still pointed
at the absent user; the version still pointed at the absent programme (so no
parent could be adopted, and none was invented); every chain row still carried its
fixture `code`/`slug`/`key`; and **no table outside the chain referenced any of the
five ids**.

Verified before `COMMIT`: `PRAGMA foreign_key_check` = **0 rows**; audit count
still 655 with all four ids present; both real lessons present; journey count
still 2. Then committed.

**Totals: 10 records touched — 4 preserved with a nulled pointer, 6 deleted, 0
parents invented, 0 audit rows removed.** Database `sha256` moved
`909fc728…b528` → `95bef282a8e856f08bc463daa247110d18868cea467910dd1ee7b040a50121c8`.

### 10.4 Migration (§3) ★

`--plan` first: 4 operations, all forward, **no unapply steps**. Then
`manage.py migrate hybrid 0009_hybridlesson_kind` — `0006_simulatorrecordcreation`,
`0007_journeyrecordassociation_…`, `0008_journey_verification_evidence`,
`0009_hybridlesson_kind`, each `OK`. No `--fake`, no `--fake-initial`, no reset,
no recreate, no additional data repair.

| Post-migration check | Result |
| --- | --- |
| hybrid applied | 0001–0009, in order |
| `django_migrations` | 112 → 116 |
| `HybridLesson.kind` | `varchar(30) NOT NULL`, cid 8 |
| existing lessons | `lesson-1` and `what-is-ucr` both `interactive_practical` — their expected type |
| new tables | `hybrid_simulatorrecordcreation`, `hybrid_journeyverificationevidence` — both 0 rows |
| unique indexes | `unique_active_record_per_role`, `unique_created_in_journey_record_claim`, `unique_hybrid_step_opened`, `unique_hybrid_step_verified` |
| `PRAGMA foreign_key_check` | 0 rows |
| `PRAGMA integrity_check` | `ok` |
| `manage.py check` | 0 issues |
| `makemigrations --check --dry-run` | "No changes detected" |
| `showmigrations` | 0 pending rows across every app |

Census deltas against preflight are confined to the six repair tables,
`django_migrations` (+4) and the two new empty tables, **plus**
`django_content_type` 93 → 95 and `auth_permission` 372 → 380. Those two are the
standard `migrate` post-processing: verified to be exactly the content types for
`hybrid.simulatorrecordcreation` and `hybrid.journeyverificationevidence` and
their four `add`/`change`/`delete`/`view` permissions each. Total rows
15,924 → 15,932.

### 10.5 Theory content preserved ★

| Table | Before | After | |
| --- | --- | --- | --- |
| `onboarding_programme` | 8 | 8 | unchanged |
| `onboarding_programmeversion` | 10 | 9 | −1 = the fixture version |
| `hybrid_hybridcourse` | 6 | 5 | −1 = `studioshots-c` |
| `hybrid_hybridmodule` / `hybrid_hybridlesson` / `hybrid_practicalstep` | 3 / 3 / 3 | 2 / 2 / 2 | −1 each = the fixture chain |
| `hybrid_verificationcondition` | 3 | 3 | unchanged |
| `hybrid_practicaljourney` | 2 | 2 | unchanged, same course/version ids |
| `accounts_user` | 13 | 13 | unchanged |
| `audit_auditevent` | 655 | 655 | unchanged; `actor_id NULL` moved 124 → 128, i.e. exactly the four R1 rows and nothing else |

Your real drafts, read back from the migrated database:

```text
hui · "Creation of UCR" → module ucr "UCR"      → lesson what-is-ucr "What is UCR"  kind=interactive_practical  theory set  1 step "Open Single Window"
hi  · "Hi"              → module try "try"     → lesson lesson-1     "lesson 1"     kind=interactive_practical  theory set  1 step "Create a UCR Draft"
```

Rendering proof — taken against a snapshot of the migrated database copied to
`.tmp/checkpoint/copy_C_migrated.sqlite3` (`8bc4954a…`, `integrity_check ok`, 0
violations), never against the real file: both module pages HTTP 200 containing
`Lesson type`, `Open Demonstration Studio`, `Full editor` and the disabled
`guided_material_study` option; the Demonstration Studio and the four-stage editor
both HTTP 200. `Material Studio coming soon` correctly does **not** appear, since
neither lesson is a Guided Material Study. This is also the check that was
impossible before — against the unmigrated database every lesson query died with
`no such column: hybrid_hybridlesson.kind`.

### 10.6 B1a — the dashboard credential test (§4) ★

`tests/test_admin_enrolment.py` only; no change to the reveal lifecycle, to
`accounts/views.py`, to the model or to any template. The stale
`assert b"shown once" in dashboard.content` is replaced by assertions on the
actual `awaiting_reveal` state and the wording that state renders
("Password issued — the student views it once on their credential page"), plus a
negative assertion that the revealed-state wording ("Password viewed by the
student") is absent, and a re-read of the credential proving that signing in
through the simulator does not reveal it.

`tests/test_admin_enrolment.py` — **4 passed**. The test passes in every battery
below; the §5 dashboard failure from the earlier checkpoint is gone.

## 11. Suite results (§4, §5) ★

| Run | Result | Failures |
| --- | --- | --- |
| `pytest tests/test_admin_enrolment.py` | 4 passed | — |
| battery 1 (after B1a) | 1 failed, 1056 passed in 109.31s | `test_stage3_shared_role.py::test_creation_provenance_and_step_freshness_are_separate_bounds` |
| battery 2 | 2 failed, 1055 passed in 105.29s | the same, plus `test_stage3_opening_lifecycle.py::test_concurrent_first_opening_returns_the_one_persisted_generation` |
| battery 3 | 2 failed, 1055 passed in 102.08s | `test_mda_activity_freshness.py::test_a_post_opening_mda_edit_satisfies_the_freshness_bound`, `test_student_dashboard.py::test_the_journey_stage_follows_the_learner` |
| battery 4 (loaded: my probe ran alongside) | 3 failed, 1054 passed in 167.21s | MDA freshness **and** shared-role provenance ties again, **plus** the opening-lifecycle concurrency test — its full traceback is in §12 instance 4 |
| battery 5 (final, unloaded) | **1057 passed in 124.53s — zero failures** | the whole suite green against the migrated real schema |
| stage3 group (4 files) | 1 failed, 68 passed | the shared-role provenance test |
| `manage.py check` / `makemigrations --check` | clean / no changes | — |

**No deterministic failure remains.** Batteries 1–4 each failed a *different* set of
tests and every one of them passes when run alone; battery 5, run last and without
my probe competing for the CPU, passed all 1057. That is the signature of a timing
dependency, not of broken code — a busy run produces more clock-tick collisions.
Root causes in §12; none of them is in code I touched, and the dashboard credential
test that §4 authorized has not failed in any run since B1a.

## 12. Recurrence report (§5) — four instances, two causes ★

The concurrency suite did recur — twice, in batteries 2 and 4 — and battery 4
kept the traceback, so it is root-caused below. Three of the four failures trace
to one underlying cause, a clock-tick tie; the fourth is a separate, genuinely
concurrency-related limit. Together they also explain the flake the previous
session reported.

**Mechanism.** This machine's `timezone.now()` is quantized to the Windows
system-clock tick, ~15.6 ms. Actions a test performs back-to-back therefore
frequently receive **identical** timestamps, and any production or test
comparison that is *strict* (`<`, `>`) or that breaks ties by "oldest" is then
indeterminate. Measurement in one warm process, repeating the failing scenario
40 times: **26 of 40 iterations (65%) produced an exact tie**, the remainder
landing one tick apart — deltas of `15.6ms, 0.0ms, 15.6ms, 0.0ms, 0.0ms, …`.

Evidence per instance:

1. `test_creation_provenance_and_step_freshness_are_separate_bounds` — the probe
   captured, in the failing configuration, `record_created_at`, `updated_at` and
   `attempt.started_at` **all equal to `16:24:20.201003`**, so
   `journey_provenance.py:107` `evidence.record_created_at < attempt.started_at`
   cannot be true and the resolver returns normally: `DID NOT RAISE`.
2. `test_a_post_opening_mda_edit_satisfies_the_freshness_bound` — pytest printed
   the assertion itself with both operands equal to
   `16:31:36.711610`: `assert record.updated_at > bound` where `bound` is
   `verification.opened_at(...)`. Same tie; it recurred in battery 4 with both
   operands equal to `18:37:26.682412` instead.
3. `test_the_journey_stage_follows_the_learner` — a variant: `Enrolment.id` is a
   **`uuid4`** primary key and `onboarding/services.py:29` orders
   `("enrolled_at", "pk")`. The fixture enrols the learner on three programmes in
   one tick, so `enrolled_at` ties and the "oldest" is decided by a random UUID
   order — the dashboard then renders a different enrolment than the one the test
   wrote progress to. (`ProgrammeProgress` is `OneToOneField`, so this is not a
   duplicate-row problem, and there is no cache in the view path.)
4. `test_concurrent_first_opening_returns_the_one_persisted_generation` —
   recurred in batteries 2 and 4, and battery 4 kept the traceback:

   ```text
   hybrid/verification.py:184  in _create_opened_event   (StepEvent.objects.create)
   django.db.utils.OperationalError: database table is locked: hybrid_stepevent

   hybrid/verification.py:291  in record_open  → _opening_fail
   hybrid.verification.JourneyOpeningError: This journey step is not currently available.
   ```

   Root cause, and it is **not** a timestamp tie — it is the SQLite retry budget.
   `record_open` (verification.py:284-295) catches `OperationalError` when
   `is_sqlite_contention` recognises "database is locked" or **"database table is
   locked"** (verification.py:168-172), retries up to `OPENING_RETRY_LIMIT = 3`
   with `OPENING_RETRY_BASE_DELAY = 0.01` s growth — a total backoff of about
   **30 ms**, roughly two clock ticks — and then converts the contention into the
   controlled refusal at line 291. When the battery is under load, the sibling
   writer holds the `hybrid_stepevent` lock longer than 30 ms, the budget is
   exhausted, and the thread raises `JourneyOpeningError` instead of returning the
   persisted generation, which is exactly what the test asserts. The
   `_create_opened_event` frame at line 184 is the same event's original
   `OperationalError`, kept as the exception chain. So this test's real dependency
   is SQLite's single-writer behaviour against a 30 ms retry budget; on Postgres
   `is_sqlite_contention` returns `False` at the first line and ordinary row locks
   serialise the two writers instead.

**Why the application is fine.** Real learner actions are seconds apart; a tie is
legitimate data, and the production rules are deliberately *inclusive* — a record
created no earlier than the journey start satisfies provenance
(`attribution.py:78` uses `record_created_at__gte`). It is the **tests** that
compress distinct steps into a single tick and then demand a strict inequality.

**Proposed narrowly scoped fixes — not applied, none authorized:**

- **C1** (shared-role test): stop relying on two successive `now()` reads
  differing — after `_attribute`, push the evidence into the past
  (`SimulatorRecordCreation.objects.filter(...).update(record_created_at=timezone.now() - timedelta(minutes=5))`)
  so the record predates the journey by a real margin while its activity stays
  fresh, which is exactly what the test claims to separate.
- **C2** (MDA freshness test): backdate the step-opening `StepEvent` by a second
  before the edit `POST`, instead of asserting the edit landed on a later tick.
- **C3** (student dashboard test): name the enrolment under test via the
  supported `?programme=<code>` parameter, or give the fixture distinct
  `enrolled_at` values, so a UUID tie-break cannot change which programme the
  dashboard renders.
- **C4** (optional, broader): a small shared test helper that guarantees strictly
  increasing timestamps — e.g. `monotonic_now()` backed by a per-process clock that
  never returns the same value twice — so this family cannot recur silently. This
  touches `tests/` only, never application code.
- **C5** (instance 4, and it is a different family): the retry budget is the
  constraint, not the clock. Three options, in increasing blast radius —
  (a) in `tests/test_stage3_opening_lifecycle.py`, raise the contention budget for
  that one test only via `django.test.override_settings` on a settings knob, or
  assert the *contract* instead of the happy path: exactly one thread may see a
  persisted generation, and a controlled `JourneyOpeningError` from the other is
  an acceptable SQLite outcome; (b) mark the test `skipif` on the SQLite backend
  and keep it running against Postgres, where row locks serialise the writers;
  (c) widen `OPENING_RETRY_LIMIT` / `OPENING_RETRY_BASE_DELAY` in
  `hybrid/verification.py:284-295`, which is **application behaviour** and changes
  what a real learner experiences under lock pressure, so it needs its own
  authorization. (a) or (b) is the narrower fix.

## 13. Complete changed-file inventory (§6.7) ★

**Repository files changed by me in this authorization — one:**

| File | Change |
| --- | --- |
| `tests/test_admin_enrolment.py` | B1a only: the credential-state assertions at the end of `test_monthly_password_is_hashed_and_shown_once` (+8 / −2). Test-only; no application behaviour, template, stylesheet or copy touched. |
| `docs/db-integrity-and-test-baseline-checkpoint.md` | this file — §8 pointer plus §10–§14 written after execution |

**Database files (all under gitignored `local_data/`):**

| Path | Status |
| --- | --- |
| `local_data/db.sqlite3` | repaired (R1–R3) and migrated 0005 → 0009. `909fc728…` → `95bef282…` → `a36db6e8…` (current) |
| `local_data/db.sqlite3.bak-20261030-160944-pre-hybrid-0006-0009` | **new** backup, `3918910d…`, verified in §10.2 |
| earlier backups (`…-20261015-course`, `…-20261016-*`, `db.before_hybrid_migration.sqlite3`) | untouched |

**Scratch, all under gitignored `.tmp/checkpoint/`** (nothing here reaches the repo):
`preflight.py`, `backup.py`, `repair_real.py`, `verify_real.py`,
`render_check.py` (reused), `test_zz_probe.py`, `test_zz_tie.py`,
`final_proof.py`, `census_before.json`, `dry_run.sqlite3`,
`copy_C_migrated.sqlite3`, `copy_A_untouched.sqlite3`, `copy_B_repaired.sqlite3`,
`stage3_group.log`, `battery_full.log`, `battery_run4.log`.

**Uncommitted work already in the tree, not written by me** — the provisionally
accepted lesson-type foundation plus the mock studio, unchanged since §10 began:
`hybrid/models.py`, `hybrid/forms.py`, `hybrid/instructor_views.py`,
`hybrid/instructor_urls.py`, `hybrid/publishing.py`,
`hybrid/migrations/0009_hybridlesson_kind.py`,
`templates/hybrid/module_detail.html`, `templates/hybrid/lesson_editor.html`,
`templates/hybrid/demonstration_studio.html`, `static/css/demonstration-studio.css`,
`tests/test_hybrid_lesson_types.py`, `tests/test_instructor_demonstration_studio.py`,
`tests/test_hybrid_builder.py`, `tests/test_stage3_opening_lifecycle.py`,
`tests/test_stage3_journey_verification_flow.py`, `docs/ui-reference/` (screenshots),
`docs/theory-practical-existing-system-inventory.md`.

`git status` shows exactly those plus my two files; `HEAD` remains `bf08419`. No
commit, no push, no deploy.

## 14. Still open ★

- **C1–C5** (§12): your ruling on which, if any, to apply. C1–C4 are test-side
  only; C5 option (c) would change application behaviour and needs its own
  authorization.
- **R4** (§9 item 7): the ORM-based fixture cleanup helper — not started.
- The `--noreload` dev server on `127.0.0.1:8765` was started before the
  lesson-type code landed, so it still serves the older modules; it needs a
  restart from you to show the new authoring surfaces. The database itself no
  longer blocks anything.
- Nothing is committed: `HEAD` is still `bf08419`, with the lesson-type
  foundation plus my one test change in the working tree.
