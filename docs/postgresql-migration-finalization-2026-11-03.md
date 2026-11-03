# PostgreSQL migration finalization — 2026-11-03

Completion report for the SQLite-to-PostgreSQL stabilization: data protection,
UUID reconciliation, credential reconciliation, verification and the final
baseline. Nothing was committed, pushed or deployed, and no schema or feature
was changed.

Target: `icums_simulator` on `127.0.0.1:5432`, user `myproject_user`,
PostgreSQL 18.3. Confirmed before any write: 16 users, 102 tables, 123 applied
migrations, 155 foreign keys, zero unvalidated constraints.

## 1. Protection

| Item | Result |
| --- | --- |
| Backup | `backups/pg-icums_simulator-pre-reconciliation-20261103T160310Z.dump` (custom format, 1,958,703 bytes) |
| Readability | `pg_restore --list` parsed the archive; 102 table-data sections |
| Restore verification | Restored into the disposable `test_icums_simulator` with `--exit-on-error`: all 102 tables present, row counts identical to the source in every table |
| Constraints after restore | 155 foreign keys, 0 unvalidated |
| Baseline | Key counts captured (16 users, 673 audit events, 123 admin-log rows, 3 credentials, 10 programmes, 11 versions, 6 courses, 643 questions, 32 UCRs, 9 MDA requests, 34 lesson-progress rows, 10 enrolments) |
| Content baseline | Per-table content fingerprints for all 102 tables |
| Concurrent writers | None. One idle pgAdmin browse connection, no open transaction, no application server listening |
| Isolation | The restored copy was reset and re-migrated afterwards, so the isolated test database carries no production data |

`myproject_user` still has no CREATEDB, so the disposable `test_icums_simulator`
was used as the restore target instead of creating a new database.

## 2. UUID reconciliation

The transfer had reassigned all 16 user UUIDs; audit targets and administrator
log entries are text columns and had kept the originals.

Applied with `scripts/reconcile_user_uuids.py --apply --allow-database
icums_simulator` after a full rehearsal on the disposable copy (apply,
idempotent re-run, rollback, re-apply — all passed).

| Item | Result |
| --- | --- |
| Users | 16 preserved, all now holding their original SQLite UUIDs |
| Foreign keys | 23 constraints to `accounts_user` re-pointed inside one transaction with `SET CONSTRAINTS ALL DEFERRED` |
| Audit events | 518 user-target events resolve again; target text was never rewritten |
| Administrator log | 15 of 15 entries resolve again |
| Row counts | Unchanged in all 102 tables |
| Unrelated content | 89 tables byte-identical; of the 13 changed tables, 12 differ only in user identifier columns (the user table itself and 11 tables that reference it), and `accounts_simulatorcredential` additionally carries the two repaired hashes |
| Transaction | Re-keying, credential repair and verification ran inside one transaction; a failed verification rolls everything back |
| Mapping | `backups/user-uuid-reconciliation-20261103T160600Z.json` (old and new id per user, plus backup path) |
| Rollback | Script supports `--rollback`; rehearsed successfully on the copy |
| Idempotency | Re-running reports 0 users to re-key and passes verification |

The 117 remaining unresolved user-target audit events point at accounts deleted
long before the transfer. They were left untouched — the repair changes
identities, not history.

## 3. Simulator credentials

Three credentials existed. None could be re-derived from the stored data under
the current `SECRET_KEY` (one revealed, two awaiting reveal), so no original
password was recovered and none is claimed.

| Username | State | Outcome |
| --- | --- | --- |
| demo-student | awaiting reveal | hash re-derived to the value the credential page shows; one-time reveal not consumed |
| panel-learner | awaiting reveal | hash re-derived to the value the credential page shows; one-time reveal not consumed |
| work | already revealed | hash left byte-identical; the password the learner was shown continues to validate against it; it cannot be recomputed, and the credential is expired until renewal |

No plaintext or hash was printed anywhere. `issued_at`, `expires_at`,
`revealed_at` and the reset fields are identical to the backup for all three
rows.

Workflow verification ran on the disposable copy (19/19 checks):

- the credential page reveals a value on first load that matches the stored hash
  and records `revealed_at`; a second load reveals nothing;
- the two pending credentials match their derivation and remain unrevealed on
  the live database;
- renewing a credential produces a current password that the simulator login
  endpoint accepts, binding the simulator session to the student;
- the revealed credential's hash and reveal timestamp are unchanged;
- `simulator.credential_issued` audit events still exist and resolve.

## 4. Data integrity after reconciliation

| Check | Result |
| --- | --- |
| Unvalidated constraints | 0 |
| Foreign keys checked for orphans | 155 checked, none |
| Users compared to backup, all columns | 16 users; only the `id` column differs |
| Programme / course / module / lesson | Identical to backup |
| Assessments (questions, attempts, lesson checks) | Identical to backup |
| Simulator records (UCR, MDA, UCR owner links) | Row counts identical; only user-key columns differ |
| Progress, reports, evaluations | Byte-identical |
| Applied migrations | 123, unchanged; `migrate --check` clean |
| Django system check | No issues |

## 5. Focused PostgreSQL tests

Run only against the isolated `test_icums_simulator` (`config.settings.vps`,
`--reuse-db`), covering credentials, account settings, enrolment, audit/security
hardening, instructor-to-student acceptance, simulator binding, UCR lookup and
ownership, completion records and the scenario engine:

**187 passed in 6m41s.**

## 6. Remaining blockers and risks

1. The `work` credential is expired and cannot be re-derived. Its stored hash is
   intact, so the previously revealed password still validates; the server
   cannot show it again. A renewal through the instructor screen issues a fresh,
   derivable password. This is expected behaviour, not a defect.
2. Two credentials were re-hashed in place. If a learner had kept an old
   unrevealed derivation from a script rather than the page, only the page's
   value is now valid — by design, since the page had never shown either one.
3. The two repaired credentials are expired (October issue dates), so simulator
   sign-in still requires a renewal; the repair fixes the reveal, not the
   calendar.
4. Re-running the reconciliation is safe and rolled back on failure, but
   `--rollback` reverses identities only; credential hashes stay repaired.
5. The backup retention decision is yours; the pre-reconciliation dump and the
   script's own pre-write dump are both in `backups/`.

## 7. Changed files

Application and test changes from the PostgreSQL compatibility review (still
uncommitted):

- `conftest.py` (new) — reused test-database repair
- `hybrid/attribution.py`, `hybrid/journey_services.py`,
  `hybrid/journey_verification.py`, `hybrid/verification.py`
- `instructor_portal/views.py` (nullable-join lock only)
- `learning/views.py`, `learning/rich_text_images.py`
- `scenarios/views.py` (MDA allocation only; the file also carries unrelated
  uncommitted demonstration work)
- `tests/test_admin_portal_uniform_ui.py`, `tests/test_module_cover_image.py`,
  `tests/test_stage3_attribution.py`, `tests/test_stage3_creation_ledger.py`,
  `tests/test_stage3_journey_verification_flow.py`,
  `tests/test_stage3_opening_lifecycle.py`, `tests/test_ucr_uniform_ui.py`,
  plus untracked demonstration tests that already contained the backend-neutral
  contention helper
- `docs/postgresql-compatibility-review-2026-11-03.md`

Reconciliation changes:

- `scripts/reconcile_user_uuids.py` (untracked): credential repair restricted to
  credentials that have not been revealed, revealed hashes verified unchanged,
  repair and verification moved inside the transaction, post-repair audit and
  admin-log resolution counts added

Database artifacts (not source):

- `backups/pg-icums_simulator-pre-reconciliation-20261103T160310Z.dump`
- `backups/pg-icums_simulator-before-uuid-restore-20261103T160601Z.dump`
- `backups/user-uuid-reconciliation-20261103T160600Z.json`
- `local_data/reconciliation/` — read-only inspectors and captured evidence

## 8. Recommendation

Sign off the PostgreSQL migration. The application database holds its original
identities again, every foreign key and validation constraint is satisfied,
historical audit and administrator-log references resolve, no unrelated row
changed, and the focused PostgreSQL suite is green. Before normal development
resumes, take a routine post-finalization backup (done — see §9) and treat the
two dump files as the rollback points for this change.

## 9. Final backup

After the reconciliation, with the schema unchanged and all verification
complete:

- `backups/pg-icums_simulator-post-reconciliation-20261103T161806Z.dump`
  (custom format, 1,957,240 bytes, 102 table-data sections).
