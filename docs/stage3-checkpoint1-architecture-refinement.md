# Stage 3, Checkpoint 1 — Architecture Refinement: Attributable Creation Provenance

Status: read-only analysis. No code, models, migrations, simulator files or
database changes. Builds on and supersedes the attribution mechanics of
`docs/stage3-checkpoint1-provenance-audit.md` (§3); its workflow inventory
(§1) and journey-engine findings (§2) remain valid and are not repeated.

---

## 1. The refinement problem, accepted

The original Approach C inferred journey attribution from owner + timestamp
+ active attempt. **[Fact]** The guided and standalone surfaces are the same
simulator views in the same browser session: the lesson workspace embeds the
simulator in an iframe (`templates/hybrid/workspace.html:117`,
`src="{{ frame_url }}"`) and offers the same URL in a new tab
(`workspace.html:114`, `target="_blank"`); the journey page reaches the
simulator only through the lesson workspace. **[Fact]** Creation POSTs from
either surface hit identical endpoints (`scenarios/urls.py`) with identical
session credentials (`simulator_access_required`, `scenarios/views.py:132-142`).

Therefore a `post_save` receiver that matches owner + record kind + open
attempt cannot distinguish:

1. a record created in the simulator surface launched from the journey, and
2. the same record created independently in another tab during the same
   window.

Both have identical ownership and timestamp characteristics. The receiver
would label independent simulator activity as journey creation evidence —
exactly what this refinement forbids. Approach C's automatic attribution is
retracted.

## 2. Can the server distinguish the initiating surface without touching
simulator endpoints or request handling?

**No — and this is a structural fact, not an implementation gap.**

- **Session context:** a session-level "active attempt" flag is shared by
  every tab of the user. The brief's warning applies verbatim: it proves the
  user has a journey open somewhere, never that *this* request came from it.
- **Request-scoped context:** the only request-carried signals are headers
  and the URL. `Referer`/`Sec-Fetch-*` could distinguish an iframe request
  from a top-level one, but they are client-controlled (spoofable by any
  scripted client), they distinguish *framing* rather than *intent* (the
  workspace itself offers "Open in new tab" for guided work), and reading
  them for authorisation would require modifying every creation view — the
  endpoint boundary the brief protects. Rejected.
- **Signed attempt-bound creation context (token):** reliable in principle —
  the server issues a token bound to (enrolment, attempt, step, role,
  expiry) when the step is opened, and the creation endpoint validates it
  and stamps provenance in-transaction. This is the only mechanism that
  proves intent at request time. It requires: the simulator creation forms
  or launch URLs to carry the token (frozen templates/JS), and every
  creation endpoint to validate it (frozen views), plus token
  expiry/replay/retry handling. **Rejected as a boundary violation for this
  stage; recorded as the strongest option if simulator integration is ever
  permitted (§6).**
- **Existing architecture:** no middleware, header convention, or route
  tagging in the codebase identifies the originating journey — verified
  (§1 facts); the simulator has no knowledge of journeys at all.

**Conclusion, stated explicitly:** both required guarantees — (A)
authoritative evidence that the student created the record, and (B)
reliable evidence that the creation belongs to the intended journey attempt
— cannot both be established purely server-side at creation time without
modifying simulator endpoints or their request handling. The smallest
necessary integration boundary that achieves both without touching any
simulator file is: **capture every creation as server-side evidence, and
let the student's explicit, server-validated attribution supply the journey
link** (creation-event capture with explicit subsequent attribution).

## 3. Revised design: creation ledger + explicit attribution

### 3.1 Capture — the creation ledger (no simulator changes)

A `post_save` receiver registered by the `hybrid` app records every INSERT
of the four registry models into a new ledger model
`SimulatorRecordCreation`:

- `record_kind` (from the sender model), `record_id`, `owner` (FK),
- `record_created_at` — copied from `instance.created_at`
  (`auto_now_add`, server-generated, never client-supplied),
- `captured_at` (auto_now_add),
- `attributed_attempt` / `attributed_at` — null until a claim is accepted.

**[Fact]** The receiver reads only server-set values; fires only on genuine
INSERTs (`created=True`); and because Django signals run synchronously in
the creating request's connection, a rolled-back creation rolls its ledger
row back with it.

The ledger is evidence, not attribution: an unattributed ledger row says
"this student created this record at this server-recorded time" and nothing
else. Independent simulator activity lands here and stays unattributed —
it is never labelled as journey work.

### 3.2 Attribution — the explicit journey link

From the journey page, the student attributes one of their captured
creations to a specific role of the attempt. The attribution view (hybrid
app, POST-only, `attempt_for_user`-scoped) validates:

1. the ledger row exists, is unattributed, and belongs to the requesting
   student (ledger `owner == request.user` — session sharing cannot
   attribute another user's record);
2. the record still exists and is owned by the student (model lookup);
3. the window: `record_created_at >= opened_at(attempt, step)` of the bound
   step, and `>= attempt.started_at` — reusing the engine's freshness bound
   (`hybrid/verification.py:28-31`);
4. the role is a required-NEW role of the attempt's journey, matching
   `record_kind`, with no active association;
5. the claim uniqueness: no other `CREATED_IN_JOURNEY` association or
   attribution references this record (per-record claim uniqueness, §5).

On success: `JourneyRecordAssociation(source=CREATED_IN_JOURNEY,
record_created_at=record_created_at)` is created via the existing replacement
semantics, and the ledger row is marked attributed.

### 3.3 Why the meaning of CREATED_IN_JOURNEY is strengthened, not weakened

**[Fact]** Today the state is unsatisfiable by construction — no code sets
it. The refinement gives it a precise, auditable definition: *"this record
was inserted during this attempt's open window by the enrolled student, who
explicitly attributed it to this role; the server verified ownership,
existence, timing and uniqueness at attribution time."* Nothing is labelled
automatically; nothing independent is claimed; every attribution is a
logged student action tied to a server-verified creation. Content
correctness remains enforced separately by the bound SAVED_RECORD condition
at Check-My-Work (status + expected fields on the exact record).

**Residual limitation, stated plainly:** the server cannot read intent. A
student could attribute a record they created independently within the
window. That is an attestation about their own work — auditable (ledger +
attribution rows), bounded by the freshness window, and content-checked by
the condition. This is the same trust level every practical-training system
must accept for student-submitted work, and it is strictly stronger than
any inference the server can make without endpoint changes.

## 4. Required analyses (brief §"Evaluate")

- **Server-side session context — rejected.** Cannot identify the
  initiating tab (§1); also degrades to the same inference the refinement
  rejects.
- **Signed attempt-bound creation context — correct but out of boundary.**
  Kept as the recorded future option if simulator integration is later
  authorised (would need: token issuance on `step_open`, token acceptance in
  the four creation endpoints, and form/JS wiring — all frozen today).
- **Request-scoped context — rejected.** Same endpoint, same session, no
  trustworthy distinguishing signal; middleware inspection would require
  endpoint changes to be meaningful and would still be spoofable.
- **Creation-event capture with explicit subsequent attribution —
  RECOMMENDED** (§3). Zero simulator changes; both guarantees met with an
  honest, documented trust boundary.

## 5. Edge cases

- **Multiple tabs:** each tab's creations are separate ledger rows; the
  student attributes whichever record they intend, per journey. No
  mislabelling by the system.
- **Simultaneous attempts:** attribution names one attempt and role
  explicitly; per-record claim uniqueness prevents the same record serving
  two journeys; windows are evaluated per attempt.
- **Stale contexts:** no token exists; eligibility is computed from durable
  state (`opened_at`, attempt status) at attribution time, so there is
  nothing to go stale.
- **Retries:** a submit updates the same row (no new ledger row); a new
  draft creates a new ledger row; a refused/duplicate attribution can be
  retried (uniqueness makes repeats no-ops or rejections, never corruption).
- **Session sharing:** the ledger and attribution are owner-keyed and the
  attribution view authenticates the Django user; a shared simulator
  credential cannot attribute another user's record (owner equality is
  checked at capture, attribution and association layers — `models.py:655-659`).
- **Journey-less creation:** captured as evidence, never attributed, never
  shown in any journey; simulator behaviour identical.

## 6. Exact integration boundary and files

**Simulator files: none.** No creation endpoint, URL, model, template,
JavaScript or CSS file in `scenarios/`, `templates/scenarios/`,
`static/js/practice-desk.js` or simulator CSS is modified. The four creation
views keep their current signatures and behaviour; they are observed, not
changed.

**Hybrid-side changes (all within the Stage 3 boundary):**
- NEW `hybrid/provenance.py` — ledger capture receivers, eligibility windows
  (reusing `verification.opened_at`), attribution service.
- NEW `hybrid/models.py` additions + one migration —
  `SimulatorRecordCreation` ledger, `JourneyRecordAssociation.record_created_at`,
  and the per-record claim uniqueness constraint (partial unique on
  `CREATED_IN_JOURNEY` associations; SQLite/PostgreSQL compatible —
  precedent `models.py:623-633`).
- `hybrid/apps.py` — receiver registration in `ready()`.
- `hybrid/views.py` + `hybrid/urls.py` — journey-scoped attribution POST and
  unattributed-ledger listing (hybrid routes, not simulator routes).
- `templates/hybrid/journey_student.html` — attribution control and
  unattributed-record list. This is a Stage 2 hybrid template, **not** a
  frozen simulator template; the change is a new control on the journey
  page, with no simulator navigation or visual impact.
- `hybrid/journey_services.py` — `role_satisfied` lifts when the attributed
  provenance exists; `assign_record` hardened to refuse externally supplied
  `CREATED_IN_JOURNEY`.
- `hybrid/publishing.py` — the required-NEW publication blocker is retired
  in the final implementation checkpoint (Checkpoint 6 tests updated then).
- NEW `tests/test_stage3_record_provenance.py`.

## 7. Implementation sequence (dependency order)

1. Migration + ledger model + `record_created_at` field + claim uniqueness.
2. `hybrid/provenance.py`: capture receiver, attribution service (windows,
   uniqueness, ownership).
3. Receiver registration; attribution view + URL; journey page control.
4. `role_satisfied` lift; completion-issue text updates.
5. `assign_record` hardening (no external `CREATED_IN_JOURNEY`).
6. Tests (test plan of the audit §8.11, adjusted: "attribution" replaces
   "auto-claim"; plus negative tests — attributing another student's ledger
   row, attributing a pre-window record, double attribution).
7. Final checkpoint: retire the `publishing.py` required-NEW blocker and
   update the Checkpoint 6 tests that assert it.

## 8. Security guarantees (revised)

- **(A) Authoritative creation evidence:** ledger rows are written by server
  code at INSERT time with `auto_now_add` timestamps and the server-assigned
  owner; nothing client-supplied is trusted.
- **(B) Journey-attempt linkage:** attribution is an explicit, logged
  student action, validated server-side against ownership, existence,
  freshness windows, role/kind match and per-record claim uniqueness.
- **Residual (inherent) limitation:** attribution carries the student's
  assertion of intent; the server verifies feasibility, not intent. This
  limitation is unavoidable without simulator-endpoint integration (§2) and
  is now explicit in the meaning of `CREATED_IN_JOURNEY` rather than hidden
  in an inference.
- All Stage 2 ownership, edition and immutability checks remain intact
  unchanged (audit §2.3).

---

Stopping here for review. No implementation, no models or migrations, no
simulator changes, no commits; all uncommitted work preserved.
