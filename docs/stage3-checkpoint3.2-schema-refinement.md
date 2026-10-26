# Stage 3.2 — Attribution Schema Refinement (resolves the eight points)

Status: read-only design. Facts verified at `7723eb4` + the uncommitted
Checkpoint 3.1 work. Supersedes the §5 schema recommendation of
`stage3-checkpoint3.2-student-attribution.md` in one respect (point 1).

---

## 1. `SimulatorRecordCreation` stays an immutable creation-evidence ledger

**Decision: no `attributed_to`/`attributed_at` fields on the ledger.**

**[Fact]** `JourneyRecordAssociation` already references the exact simulator
record (`record_kind`, `record_id` — indexed pair, `models.py:634-637`), the
attempt, the enrolment, the programme version, the role and the claim source
(`models.py:579-664`). Attribution is fully representable as an association
row with `assignment_source = CREATED_IN_JOURNEY`; the ledger's only extra
data is timestamps, which the attribution service reads from the ledger row
without mutating it. Keeping the ledger append-only preserves its meaning as
immutable evidence: capture never learns about journeys.

**[Fact]** This is safe because a `CREATED_IN_JOURNEY` association is only
ever written by the new attribution service, and only after validating a
ledger row for the same (record_kind, record_id) owned by the student — the
ledger is the prerequisite, the association is the claim. Verified: no code
path today sets `CREATED_IN_JOURNEY` (grep — enum comparisons only).

## 2. Claim-uniqueness strategy on `JourneyRecordAssociation`

**[Fact]** Existing constraints (`models.py:621-637`):
`unique_active_record_per_role` — (journey_attempt, role) where active;
`journey_record_active_state` check; index on (record_kind, record_id);
index on (enrolment, programme_version).

**[Recommendation]** add to `JourneyRecordAssociation.Meta`:

```python
models.UniqueConstraint(
    fields=("record_kind", "record_id"),
    condition=Q(assignment_source="created_in_journey", is_active=True),
    name="unique_active_created_in_journey_claim",
)
```

Semantics: at most one **active** created-in-journey claim may exist for a
given simulator record, across all attempts, roles and students. The
condition excludes every `AUTHORIZED_EXISTING` row, so legitimate existing
and future associations are untouched and the migration adds a constraint
over a currently-empty population (verified: no code path sets
`CREATED_IN_JOURNEY` — no conflict, no backfill). If a claim is later
superseded (replacement history), the record becomes claimable again —
by its owner only (attribution requires ledger + record ownership by the
same student).

## 3. `select_for_update` is not a record-claim lock

**[Fact]** `JourneyAttempt.objects.select_for_update()` locks one attempt
row (`journey_services.py:445-447`, `:547`). Two concurrent attributions of
the **same record** to **different attempts** lock different rows — the row
locks do not serialise them.

- **PostgreSQL:** both transactions proceed; the second `INSERT` into
  `JourneyRecordAssociation` violates
  `unique_active_created_in_journey_claim` → `IntegrityError`.
- **SQLite:** the database-wide write lock serialises the transactions
  outright; the same constraint decides.

Design consequence: the attempt lock protects the *attempt's* state
(unsatisfied re-check, replacement bookkeeping); the **partial unique
constraint is the authoritative record-claim gate on both backends**. The
service additionally pre-checks "already claimed" to return a friendly 409
and treats the constraint violation as the race-safe backstop — the same
dual mechanism this codebase already documents
(`journey_services.py:8-19`). Verified against `models.py:624-633`
(constraint-over-savepoint precedent on SQLite).

## 4. Eligible-creation window — exact definition

A ledger row is **eligible** for (attempt, role) when ALL hold:

1. `record_kind == role.record_kind` and `owner == attempt.enrolment.student`
   (ledger columns).
2. Unattributed: no active `CREATED_IN_JOURNEY` association references the
   record.
3. `record_created_at >= attempt.started_at` — created during the attempt.
4. `record_created_at >= opened_at(attempt, bound_step)` — the freshness
   bound of the role's bound condition's step, exactly the rule
   Check-My-Work already applies (`verification.py:28-41`). If the role has
   no bound condition, the floor is `attempt.started_at`.

**Step reopening narrows the window**: `step_open` refreshes
`opened_at` (`verification.py:34-41`), so a record created between an
earlier opening and a re-open becomes ineligible after the re-open. This is
deterministic and identical to the engine's existing freshness semantics —
deliberate, so attribution eligibility and Check-My-Work freshness can never
disagree. **Retries** create fresh rows with later timestamps: always
eligible while the window is open. **The role does not need to be the
currently active step**: the window is anchored to the bound step's own
OPENED event, so a student who creates the record and advances is not
penalised; only the record's creation time is judged.

## 5. Validation sets (eligibility and `role_satisfied`)

Both validate the same authoritative set, server-side only:
- the **ledger row**: exists for (record_kind, record_id), `owner ==
  enrolment.student`, unattributed (for eligibility) / `attributed_to ==
  attempt.pk` (for satisfaction);
- the **record**: still exists in the registry model, `owner ==
  enrolment.student` (`models.py:655-659`);
- the **association**: attempt, role, kind coherence (`models.py:639-654`).

**[Fact]** The client supplies only the ledger row pk. Source
(`CREATED_IN_JOURNEY`) and every timestamp are server values; `role_satisfied`
re-derives the lift from durable rows at every evaluation
(`journey_services.py:581-589` lifted per §6 below) — a forged or stale
claim cannot persist.

## 6. Replace / release / reuse policy (this checkpoint)

- **Replace:** while the attempt is IN_PROGRESS, the student may attribute a
  different eligible record to the same role. The existing replacement
  semantics apply — the superseded association is kept as history
  (`is_active=False`, `replaced_at`) and the previous record's claim is
  released (it becomes eligible again for its owner elsewhere).
- **Release to "no record":** not supported. A role is satisfied or not;
  a deleted record fails it closed (`journey_services.py:581-583`), and the
  remedy is replacement, not release.
- **Reuse:** a record with an active claim cannot be claimed elsewhere
  (constraint). After replacement, its claim is released and it becomes
  eligible again for its owner's other journeys — rare and harmless (same
  owner).

## 7. Check My Work — journey-awareness explicitly deferred

**[Fact]** `hybrid/verification.py:_verify_saved_record` (`:66-95`) is
owner-scoped and freshness-bound but **not journey-aware**: it verifies that
the learner has *some* owned record of that kind matching the required
status and fields with fresh activity. It does not — yet — verify **the
attributed record** named by the role. **[Decision]** journey-aware
Check-My-Work (the condition evaluates the attributed record named by the
role binding) remains a declared future dependency
(`journey_services.py:32-37` already lists it as deliberately out of
scope). End-to-end practical verification — "the attributed record is the
record the condition verifies" — is therefore NOT claimed as available in
this checkpoint; attribution satisfies the **role gate** only, and step
verification remains the existing owner-scoped check.

## 8. Migration 0007 — required, exact contents

**[Fact]** Required: without a database constraint, two concurrent
attributions of one record to different attempts can both succeed (§3) —
Python-level checks cannot close that race.

**[Fact]** 0006 is untouched. 0007 contains exactly one operation:

```python
migrations.AddConstraint(
    "journey_record_association",
    models.UniqueConstraint(
        fields=("record_kind", "record_id"),
        condition=models.Q(assignment_source="created_in_journey", is_active=True),
        name="unique_active_created_in_journey_claim",
    ),
)
```

No ledger fields, no data migration, no conflict with existing rows
(none carry the source). SQLite/PostgreSQL: conditional unique constraints
of this shape already exist in this app (`models.py:624-633`).

## 9. Files, tests, limitations

**Files (implementation checkpoint):** NEW `hybrid/attribution.py`
(eligibility query, `attribute_record(attempt, role, ledger_row, student)`
service with the §5 validation chain, §3 locking); `hybrid/models.py`
(+1 constraint); migration 0008; `hybrid/views.py` + `hybrid/urls.py`
(GET eligible-list, POST attribute — journey-scoped, POST-only, CSRF);
`templates/hybrid/journey_student.html` (eligible-record selector on each
unsatisfied NEW role — plain form, no JS); `hybrid/journey_services.py`
(`role_satisfied` lift); NEW `tests/test_stage3_attribution.py`.
`SimulatorRecordCreation`, migration 0006, `creation_ledger.py`: unchanged.

**Test cases:** eligibility window boundaries (created before attempt start
→ ineligible; before step re-open → ineligible after re-open); ownership
isolation (other student's ledger rows never listed/claimable); claim
uniqueness under concurrency (second attribution → 409 via constraint);
replacement releases the old claim; completed-attempt refusal; deleted
record → `role_satisfied` fails closed; attribution writes no VERIFIED
`StepEvent` (step still demands Check-My-Work); journey completes only
when steps + roles + lessons all pass; idempotent repeat → 409; CSRF/POST
enforcement.

**Unresolved limitations (declared):**
1. Journey-aware Check-My-Work deferred (point 7) — the condition check
   remains owner-scoped, so the strict "the attributed record is the
   verified record" link awaits that future checkpoint.
2. Intent is the student's attestation, bounded by the server-verified
   window (inherent; accepted in the Checkpoint 3.1 refinement).
3. A capture failure (Checkpoint 3.1) leaves no ledger row, so that record
   can never be attributed — by design; the student retries the creation.
4. Multiple simultaneous NEW roles of the same kind across different
   journeys: the student attributes explicitly per journey; no ambiguity
   resolution logic is needed because nothing is auto-claimed.

---

Stopping here for review. Read-only: no implementation, migration,
commit, push, reset or stash; all unrelated work preserved.
