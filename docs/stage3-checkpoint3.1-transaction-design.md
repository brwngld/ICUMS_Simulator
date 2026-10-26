# Stage 3, Checkpoint 3.1 — Final Transaction Design: One Transaction per Creation

Status: design checkpoint. No code changed for this deliverable; the
currently uncommitted Checkpoint 3.1 implementation stays in the working
tree and its receiver will be simplified as specified here once this design
is approved. Verified facts carry file:line references; everything else is
recommendation.

---

## 1. Exact creation endpoints and their current transaction state

**[Fact]** Verified creation endpoints for the four registry models
(`scenarios/views.py`, `scenarios/urls.py`):

| # | Route name | View | Outer transaction today | Verdict |
|---|---|---|---|---|
| 1 | `ucr-save` | `ucr_save_declaration` (`views.py:730-754`) | none — `record.save()` + attachments run in autocommit | needs wrapping |
| 2 | `ucr-clone` | `ucr_clone` (`views.py:1023-1040`) | none — row create + attachments in autocommit | needs wrapping |
| 3 | `boe-create` | `boe_create` (`views.py:2244-2285`) | none for the row itself (`allocate_job_number` has an internal atomic that exits before the create) | needs wrapping |
| 4 | `application-save` | `application_save_declaration` (`views.py:1695-1716`) | none (`allocate_application_number` is unlocked, `models.py:1040-1048`) | needs wrapping |
| 5 | `application-mda-request-create` | `application_mda_request_create` (`views.py:1512-1557`) | `transaction.atomic()` wraps the creation (`:1526-1542`) | already suitable |
| 6 | `consignment-application-mda-create` / `-copy` | `consignment_application_mda_create` / `_copy` (`views.py:1894-1942`) | `transaction.atomic()` wraps creation incl. the implicit parent application (`:1881-1890`) | already suitable |

**[Fact]** Why the four unwrapped endpoints break mandatory provenance
(Django 5.2.18, `django/db/models/base.py:999` and `:1023`): `save_base`
uses `mark_for_rollback_on_error` (no transaction opened, no commit) for
parentless models, and `post_save` fires after that block exits. Under
autocommit the record INSERT commits before the signal fires, so the
receiver's evidence insert is a separate transaction — an evidence failure
there cannot roll the record back, which is why compensation existed.

## 2. Option comparison

**Option 1 — explicit `transaction.atomic()` inside each creation view.**
Wrap the persistence statements of views 1-4 in `with transaction.atomic():`
and add a `try/except` that returns each view's existing JSON error shape.
- Pros: controlled JSON failure responses (finally satisfying the earlier
  "controlled failure response where possible" clause); tightest transaction
  scope (validation and payload parsing stay outside the transaction).
- Cons: edits four view bodies; future creation endpoints must remember the
  wrapper and the error mapping.

**Option 2 — narrow route-specific transactional wrapping, no view-body
changes.** A one-line decorator (`transaction.atomic` bound at import) is
applied to exactly the four creation routes in `scenarios/urls.py`
(`path(..., atomic_wrap(views.ucr_save_declaration), name="ucr-save")`).
- Pros: smallest possible diff (a decorator definition plus four route
  lines); zero view-body changes — the views are observed, not edited;
  guarantee is structural (the route IS the transaction), so it cannot be
  forgotten inside future refactorings of a view body; rollback is total —
  record, evidence and any partial attachments all roll back together.
- Cons: the transaction spans the view's parsing/validation (fine at
  training-scale traffic, single-digit milliseconds); failure responses stay
  as they are today (propagated 500) unless Option 1's try/except is added
  later.

**Status-quo (compensation) — rejected.** Post-commit deletion cannot
restore the pre-commit state: the record is visible and claimable in the
window between commit and compensation, and a compensation failure leaves
the evidence-less record permanently. Superseded by this design.

**Recommendation: Option 2**, with Option 1's try/except noted as an
optional follow-up if a controlled JSON error response is wanted. It is the
smallest maintainable change that structurally guarantees atomicity: the
route boundary is the transaction, the capture receiver inserts inside it
and any failure rolls both back. No compensation code remains — the
receiver's capture becomes a straight `create()` again (removing the
compensation logic from `hybrid/creation_ledger.py` is part of the
implementation checkpoint).

## 3. Required implementation boundaries (exactly)

**Simulator Python changes (narrow, authorized by this design):**
- `scenarios/urls.py` — define or import a one-line
  `creation_transaction = transaction.atomic` decorator and wrap routes
  1-4 (`ucr-save`, `ucr-clone`, `boe-create`, `application-save`). Routes 5-6
  already own their atomics; wrapping them again would be harmless
  (savepoints) but is not required.
- Alternatively the same decorator applied inside the four view functions
  (`@transaction.atomic` above each) — equivalent guarantee, marginally
  larger diff, tighter scope (excludes payload parsing from the
  transaction). Either placement is acceptable; the urls.py placement is the
  smaller diff.

**Hybrid changes (already implemented in the working tree, with one
simplification at implementation time):**
- `hybrid/creation_ledger.py` — the capture receiver's compensation
  try/except and nested atomic are REMOVED; the receiver becomes a straight
  `SimulatorRecordCreation.objects.create(...)` that may raise. Raising is
  now safe and required: it triggers the route's rollback.
- `hybrid/apps.py`, `hybrid/models.py`, migration `0006` — unchanged from
  the current working tree.

**Templates, JavaScript, CSS, navigation: none.**

## 4. Coverage of non-request and helper paths

- **Cloning:** `ucr-clone` is route 2 — wrapped.
- **Creation helpers:** `allocate_ucr_number`, `allocate_job_number`,
  `allocate_application_number`, `_allocate_mda_application_number` allocate
  numbers only; they create no registry rows and need no coverage. Their
  internal locking is unchanged.
- **Implicit parent creation:** the consignment application created inside
  `_target_mda_request` sits inside route 6's existing atomic.
- **Non-HTTP creation paths:** verified none exist — no management command,
  fixture or seed creates registry rows (audit §1.4). Future ones should run
  inside `transaction.atomic` to inherit capture, noted in the registry
  docstring at implementation time.
- **Admin:** creating registry rows through Django admin remains
  impractical (unique `editable=False` numbers); out of scope unchanged.

## 5. Behaviour after implementation

- **Normal creation:** view runs inside the route transaction; INSERT fires
  the capture receiver; evidence INSERT joins the same transaction; the
  block exits and both commit together. Single visible change: none.
- **Evidence failure (forced fault):** the exception propagates out of the
  view; the route transaction rolls back — record, evidence, attachments and
  any parent rows all disappear; the client receives a 500 and can retry.
  No compensation code exists or is needed.
- **Standalone simulator use outside journeys:** identical — the ledger
  records evidence passively; no journey lookups occur.
- **Multiple tabs / parallel journeys:** unchanged from the accepted
  refinement (attribution is a later checkpoint).

## 6. Required regression tests (implementation checkpoint)

1. Per wrapped route (1-4): force the evidence create to fail
   (monkeypatch); POST the route; assert the failure response AND that no
   registry row, ledger row or attachment row persisted. This is the test
   that makes the route wrapper mandatory and keeps it mandatory.
2. Per wrapped route: happy-path POST persists the record AND the evidence.
3. Routes 5-6 (MDA): capture-failure test asserted against their existing
   atomics (record + implicit parent absent after failure).
4. `ucr-clone` wrapped: cloned row + evidence both present on success; both
   absent on forced failure.
5. Existing suites: full focused regression (stage2/hybrid/partial-publish)
   stays green with the route transactions active.

Acceptance: a deliberate fault in evidence capture can never leave a
registry row behind, on every supported creation path, under both SQLite
and PostgreSQL.

## 7. Risks

- Longer transactions on the four routes (parse + validate inside the
  transaction under the urls.py placement): negligible at training scale;
  the view-internal placement removes even this.
- A future sixth creation route without the wrapper: guarded by the per-route
  forced-failure regression test — a missing wrapper fails that route's test.
- 500-on-evidence-failure: identical to today's behaviour for any unexpected
  view exception; controlled JSON responses remain an optional follow-up
  (Option 1's try/except).

---

Stopping here for review. The working tree keeps the current uncommitted
Checkpoint 3.1 implementation (compensating receiver), which this design
supersedes: the implementation checkpoint will apply the route wrappers,
simplify the receiver to a straight create, update the tests, and only then
present the whole of Checkpoint 3.1 for commit review.
