# Stage 3, Checkpoint 3.2 — Secure Student Attribution: Architecture Report

Status: planning only. No implementation, migration, commit or database
change. Facts carry file:line references verified at
`7723eb4` + the uncommitted Checkpoint 3.1 work.

---

## 1. Three separate operations, three separate rows

| Operation | Durable row | Written by |
|---|---|---|
| 1. Creation evidence | `SimulatorRecordCreation` (3.1 ledger) | capture receiver, inside the creation transaction (CP 3.1) |
| 2. Student attribution | `JourneyRecordAssociation` with `source=created_in_journey` | NEW attribution service (this checkpoint's design) |
| 3. Requirement verification | `StepEvent(kind=verified)` + `role_satisfied` lift | existing engines only (`hybrid/verification.py:104-116`, `journey_services.py:584-589`) |

Nothing in this design merges them: the ledger never attributes; the
association never proves creation by itself (it must reference a ledger
row); verification engines read both but are written by neither.

## 2. Student workflow (mapped to existing code)

1. Student opens the journey page (`hybrid/views.py:228-275`): entry creates/
   resumes the single attempt (`journey_services.py:323-334`); unsatisfied
   required NEW roles render in the existing role panel
   (`templates/hybrid/journey_student.html:56-66`).
2. Student advances to the bound step and opens the simulator:
   `step_open` records the OPENED `StepEvent` — the freshness bound
   (`hybrid/views.py:161-168`, `verification.py:28-41`).
3. Student creates the record through any simulator surface (wrapped route or
   standalone); the 3.1 ledger captures it server-side.
4. Back on the journey page, the role panel offers a server-generated list of
   that student's eligible, unattributed creations of the role's kind
   (NEW endpoint, §4).
5. Student selects one and POSTs attribution (NEW endpoint, §4).
6. Server validates the full chain (§5) and writes the association inside
   `transaction.atomic` with attempt-row locking (the exact pattern of
   `assign_record`, `journey_services.py:546-561`).
7. Verification engines evaluate separately: the step's bound
   SAVED_RECORD condition still needs Check-My-Work to write its VERIFIED
   `StepEvent`; `role_satisfied` lifts only for a ledger-backed attributed
   record. Attribution alone completes neither.

## 3. Why a record created during the attempt is eligible — and why
explicit attribution is still required

**[Fact]** The ledger proves identity, ownership and creation time
(`hybrid/models.py`, `SimulatorRecordCreation`; capture receiver in
`hybrid/creation_ledger.py` — all values server-generated). **[Fact]** It
cannot prove intent: a creation in an independent simulator tab during the
same window is indistinguishable at INSERT time (Checkpoint 3.1 refinement,
accepted). The student's explicit attribution is therefore the intent
signal — always student-initiated, always server-validated against
objective windows, and always auditable (ledger row + association row). The
system never auto-attributes (Checkpoint 3.1 refinement, §3.3).

## 4. Endpoints

**Discovery (GET):** `journeys/<uuid:journey_id>/roles/<uuid:role_id>/eligible/`
- Auth: `attempt_for_user` ownership + edition match (existing pattern,
  `journey_services.py:347-355`).
- Returns JSON: the student's `SimulatorRecordCreation` rows where
  `record_kind == role.record_kind`, not yet attributed to any attempt
  (no CREATED_IN_JOURNEY association references the record — partial unique
  constraint makes this a cheap index lookup), and
  `record_created_at >= max(attempt.started_at, opened_at(attempt, bound_step))`
  (reusing `verification.opened_at`). Ordered newest-first. No client
  identifiers accepted.

**Attribution (POST):** `journeys/<uuid:journey_id>/roles/<uuid:role_id>/attribute/`
- JSON body: `{"record_id": <ledger pk>}`. POST-only, CSRF-protected
  (`require_POST`; the app's existing convention), resolved through
  `attempt_for_user`.
- Server-side validation chain (all server data, in order):
  1. Attempt IN_PROGRESS, edition/enrolment match (existing checks).
  2. Role belongs to the journey, `creation_mode == NEW`, `record_kind`
     matches the ledger row's kind, role currently unsatisfied.
  3. Ledger row exists, `owner == enrolment.student`, unattributed.
  4. Window: `record_created_at >= attempt.started_at` and
     `>= opened_at(attempt, bound step)`.
  5. Record still exists and is owned by the student
     (`models.py:655-659` unchanged).
- Writes, inside `transaction.atomic` with
  `JourneyAttempt.objects.select_for_update()` (the established
  `assign_record` locking pattern): re-check role unsatisfied under the
  lock; mark the ledger row attributed; create the association with
  `source=CREATED_IN_JOURNEY`, `assigned_by=student`.
- Failure responses: JSON `{"error": ...}` with 400/403/409 — never silent.

**Roll/re-assignment:** attributing over an existing association uses the
existing replace-with-history path (`is_active=False, replaced_at`) —
`unique_active_record_per_role` stays the concurrency backstop.

## 5. Database changes (one migration, 0007)

- **[Fact]** `JourneyRecordAssociation` already carries everything needed
  for the attribution itself: attempt, role, enrolment, programme_version,
  kind, `record_id`, `source`, `assigned_by`, active/replaced history
  (`hybrid/models.py:579-664`). No new fields on it.
- **[Recommendation]** `SimulatorRecordCreation` gains
  `attributed_to = FK(JourneyAttempt, null=True, PROTECT)` and
  `attributed_at = DateTimeField(null=True)`, plus
  `UniqueConstraint(fields=("record_kind", "record_id"),
  condition=Q(attributed_to__isnull=False),
  name="unique_created_record_claim")` — one creation can be attributed to
  at most one attempt, enforced by the database. This is the only schema
  change; it is additive and composes with unapplied 0006 (0007 depends on
  it; deployment applies both in one `migrate hybrid`).

## 6. Role satisfaction and step completion stay separate

**[Recommendation]** `role_satisfied` (`journey_services.py:584-589`) lifts
for a `CREATED_IN_JOURNEY` association only when the referenced ledger row
exists, is owned by the student, and carries `attributed_to ==
attempt.pk` — provenance + attribution together, re-checked from durable
rows, never from the association's say-so.

**[Fact]** Step completion is untouched by design: a condition-bearing step
satisfies only via a VERIFIED `StepEvent` written by Check-My-Work
(`verification.py:104-116`); the partial unique constraint keeps it
single-shot (`models.py:306-320`). Attribution writes no StepEvent, so it
can never complete a practical step — the existing separation is the
answer to the brief's requirement, not a new mechanism.

## 7. Security requirements coverage

| Requirement | Mechanism (all existing unless noted) |
|---|---|
| Authenticated student / enrolment ownership | `attempt_for_user` + `enrolment__student` scoping (`journey_services.py:347-355`) |
| Exact attempt/step association | association `clean()`: enrolment, programme_version, role, journey coherence (`models.py:639-661`) |
| Record ownership + kind validation | ledger owner check + `models.py:653-659` record owner check |
| Authoritative creation evidence | ledger row is mandatory for NEW-role attribution; association without ledger backing fails `role_satisfied` (fail-closed retained) |
| Creation timestamp vs step opening | window check `>= opened_at(attempt, bound step)` (reuse `verification.opened_at`) |
| Reuse across attempts/roles | `unique_created_record_claim` (one attribution per creation) + `unique_active_record_per_role` |
| Multiple tabs / simultaneous attempts | attempts are unique per (enrolment, journey); each attribution names its attempt; a record claimed by one stays unclaimed for the other |
| Concurrent attribution | attempt-row `select_for_update` + both unique constraints (the Checkpoint 3 pattern, `journey_services.py:8-19`) |
| Duplicates / idempotency | repeat POST with the same record returns the existing association (409 or 200-idempotent — recommend 409-with-current-state) |
| Expired/completed/ineligible attempts | IN_PROGRESS required; completed/retired editions refused by existing gates |
| Stale/deleted records | record-existence check at attribution; `role_satisfied` re-checks at every evaluation (`journey_services.py:581-583`) |
| Instructor review mode | attribution resolves the student's own attempt only; staff have no override path (assigned_by records the student) |
| CSRF / POST-only | `require_POST` + Django CSRF middleware (app convention, `hybrid/views.py:161-277`) |
| No trust of client ids/timestamps | record identity comes from the ledger row pk; timestamps only from server columns |

## 8. Files (implementation checkpoint scope)

- NEW `hybrid/attribution.py` — eligibility query, attribution service.
- `hybrid/models.py` + migration `0007` — ledger attribution fields + claim uniqueness.
- `hybrid/views.py`, `hybrid/urls.py` — two endpoints (GET discovery, POST attribute).
- `templates/hybrid/journey_student.html` — eligible-record selector per unsatisfied NEW role (server-rendered list + one button; no JS required — plain form POST).
- `hybrid/journey_services.py` — `role_satisfied` provenance lift (ledger-backed).
- `tests/test_stage3_attribution.py` (new).

Simulator files: none. Frozen templates/JS/CSS: none. `publishing.py`
required-NEW blocker: still retired LAST, in its own later checkpoint after
3.2 acceptance.

## 9. Migration-0006 accounting

0006 remains unapplied on the development database. Checkpoint 3.2's
migration 0007 depends on it; nothing needs the tables until the attribution
endpoint runs. Implementation/testing plan: Django's test runner applies
0006+0007 to the throwaway test database automatically, so development and
CI are unaffected; the dev database receives both in a single
`manage.py migrate hybrid` at acceptance. No data migration is required
(no pre-existing ledger rows outside tests).

## 10. Implementation checkpoints

1. 0007 migration (ledger attribution fields + claim uniqueness).
2. `hybrid/attribution.py`: eligibility query + `attribute_record` service
   (validation chain §4, locking, idempotency) + unit tests.
3. Discovery + attribution endpoints (GET/POST, JSON) + URL routes.
4. `journey_student.html` role-panel control + journey view context
   (eligible lists per role).
5. `role_satisfied` ledger-backed lift + completion-issue text updates.
6. Route-level forced-failure and cross-student negative tests.
7. (Later, own checkpoint) retire `publishing.py` required-NEW blocker and
   update the Checkpoint 6 tests that assert it.

## 11. Acceptance criteria

1. A student who creates a UCR while a NEW ucr role's step is open sees it
   in the eligible list and, after attribution, the role satisfies and the
   journey completes (with all other gates green).
2. A record created before the step was opened never appears in the
   eligible list.
3. A record attributed to one journey can never be attributed to another
   (claim uniqueness), and a second attribution attempt returns 409.
4. Another student's creation never appears in any eligible list.
5. Concurrent attribution of one record to two roles/attempts yields
   exactly one success (constraint-proven).
6. Completed-attempt attribution is refused.
7. Attribution does not write VERIFIED StepEvents; the step still demands
   Check-My-Work.
8. Deleted record after attribution: role fails closed with the existing
   message.
9. All POSTs are CSRF-protected; GET mutates nothing.
10. Full existing suite stays green.

---

Stopping here for review. Read-only checkpoint respected: no implementation,
migration, commit, push, reset or stash; all unrelated uncommitted work
preserved.
