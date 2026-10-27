# Stage 3.3 — Verification Lifecycle Design Note

Status: review only. Checkpoint 1 does not implement any lifecycle, locking,
event, evaluator, attribution or replacement change.

## 1. Current VERIFIED constraint and reopening

`StepEvent` permits one `verified` row per `(LessonAttempt, PracticalStep)`.
`record_open()` refreshes the singleton opening time, but `is_verified()` and
journey progress currently test only whether the VERIFIED row exists. A later
opening can therefore make a record/role stale while the old VERIFIED row is
still treated as current. `mark_verified()` also uses `get_or_create()`, so a
successful retry after reopening cannot give that singleton a new generation.

## 2. Verification generations

An opening cycle is necessary for journey-bound steps. A verification is
current only for the opening generation against which it was earned. The
recommended durable design is an additive verification-run/evidence row that
records the opening timestamp (or opening-generation identifier), the exact
condition, role, association and record identity, and the result timestamp.
The existing VERIFIED `StepEvent` remains the compatibility checkpoint; it
must be considered current only when backed by evidence from the latest
opening cycle. Legacy non-journey lessons retain their current interpretation.

## 3. Historical versus current evidence

Do not delete or rewrite an older verification merely because a step is
reopened. Preserve it as historical evidence and derive current state from
the latest opening generation. A new successful check creates a new evidence
generation. Journey progression and completion read only the evidence tied to
the latest opening. This preserves an audit trail without allowing historical
success to satisfy current work.

## 4. Shared transaction and lock order

Verification and attribution replacement must acquire locks in one order:

1. `JourneyAttempt`
2. `LessonAttempt`
3. active `JourneyRecordAssociation` rows in deterministic role/id order
4. VERIFIED event/current verification evidence

Verification resolves and evaluates the exact records only after these locks
are held. Replacement takes the same `JourneyAttempt` lock first and then its
association row; it refuses replacement while current verification exists.
This prevents a record being replaced between selection, evaluation and the
verification write, and avoids PostgreSQL deadlocks caused by inverted lock
orders.

## 5. SQLite and PostgreSQL

PostgreSQL enforces the order with real row-level `SELECT FOR UPDATE` locks;
concurrency tests must cover verification versus replacement and duplicate
checks. SQLite ignores row-level locking and serializes writers at database
scope, so correctness also requires database uniqueness constraints and
transactional rechecks immediately before every write. SQLite tests can prove
state invariants and race-safe error handling, but PostgreSQL remains the
authoritative concurrency test environment.

No lifecycle behavior described here is implemented in Checkpoint 1.
