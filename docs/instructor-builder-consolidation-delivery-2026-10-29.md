# Instructor Builder Consolidation and Hybrid Learning Completion — delivery report

Delivered 2026-10-29 on `feat/theory-experience-faithful`, against the mission
document's Batches A–F. Baseline was `9c7d0d9` ("Connect exact-record journey
verification to the student workflow"); this report covers `a2e79e5`, `53f3d1c`,
`52c8745`, `002fff5`, `6b232b5` and the closing docstring fix in
[scenarios/views.py:113](../scenarios/views.py).

## 1. Baseline confirmed (§1)

| Item | State at the start of this batch |
| --- | --- |
| Branch / HEAD | `feat/theory-experience-faithful` / `9c7d0d9` |
| Working tree | clean; no work was reset, stashed, overwritten or discarded |
| Development database | `local_data/db.sqlite3` (SQLite), inspected read-only |
| Pending migrations | three in `hybrid` — see §5. **Not applied.** |
| Full suite before changes | `1 failed, 977 passed`; the failure is pre-existing (§6) |
| Production / VPS | untouched. Nothing was deployed, pushed or published. |

## 2. Delivered functionality (§3–§10)

### Two primary builders (§3, §4)

Instructor navigation now offers exactly the Theory builder and the Theory &
Practical builder. The old Practical/Theory entry left the sidebar
(`core/admin_dashboard.py`), the dashboard panel points at
`hybrid-builder`, and the course list's `?path=theory` / `?path=combined` tabs —
which never filtered anything — are gone. Nothing was deleted: builder B keeps
every URL, view, model and test it had.

### Ordinary course setup without Advanced Admin (§4)

The Theory & Practical builder can now create its own programme
(`create_programme`). The learning track is set by the view, so a builder
programme can never land in the theory system, each card's POST binds only its
own form, and no instructor permission was widened. The empty state reads
"create the first above" instead of telling instructors to ask an administrator.

### The five authoring stages (§5)

Details and objectives, theory blocks, journey steps, simulator screen selection,
expected outcomes, verification conditions, record roles, dependencies, preview
and publication readiness are all reachable from the builder. Two gaps in that
chain closed here:

- **Screen selection** is limited to the approved registry in
  `scenarios/bindings.py`, which now also answers "which record kinds can this
  screen verify, in which statuses, and which saved columns can be pinned to an
  exact value".
- **Expected values no longer need JSON.** The condition editor offers a
  "Saved value" column select grouped by record kind and one text/number/yes-no
  box per row. Columns that cannot be compared exactly (decimal, date, JSON, and
  the lifecycle columns `id`, `status`, `created_at`, `updated_at`,
  `submitted_at`) are not offered at all, so an instructor cannot type an
  expectation the engine could never honour. A mismatched kind or prose in a
  flag row is a readable server-side error.

### Publication gate aligned with the evidence model (§8) — decision to review

A required record role with creation mode "new" used to block its whole edition,
because the simulator carried no creation provenance. `hybrid/creation_ledger.py`
now writes immutable evidence inside each approved record's own creation
transaction and `journey_services.role_satisfied` reads it, so that blocker was
false: the flagship "the learner creates the declaration" journey could never
ship. It was removed, together with the matching optional-role warning. **The
runtime stays fail-closed** — a record with no ledger row still leaves its role
open and its step unsatisfied. No data changed, no migration, no permission
change, and no already-published content is affected. Flagged for review in §13.

### The student split-screen workspace (§6)

Left pane: theory reading (rendered through `rich_content`), the practical
journey progress list, one card per step with its instruction, expected outcome,
hint, verification feedback, and Previous / Hint / Check my work / Next step
controls. Right pane: an iframe of the **real** simulator screen the current step
points at — its own navigation, its own forms, its own authentication and
permission checks, no restricted functionality exposed and no duplicated or
fake simulator. The divider is draggable, keyboard-operable, `aria`-labelled,
persists per tab, and collapses to a single switchable pane below the responsive
breakpoint. The student performs the operation in the simulator; there is no
substitute form in the lesson pane.

### One verification system, reused (§7, §8)

The Stage 2/3 journey engine, exact-record selection, opening generations,
provenance checks and append-only `JourneyVerificationEvidence` are unchanged in
mechanism; this batch only removed the publication-time contradiction above and
fixed two presentation defects found by the walkthrough. Immutable evidence is
still evidence-authoritative for progression, old `VERIFIED` events still cannot
bypass current journey verification, and publishing new content does not
invalidate historical completed attempts.

### Acceptance through real forms (§9, §10)

`tests/test_acceptance_instructor_to_student.py` drives the whole path with HTTP
POSTs — programme, course, module, lesson, step, condition, role, binding,
publish — then enrols a learner, opens the workspace, saves a **real UCR through
the simulator's own `ucr-save` endpoint**, attributes it to the role, checks the
step, and advances. Three scenarios: a correct record passes and completes the
lesson; an unrelated record fails and `advance` is refused with 403; checking the
same step twice produces exactly one evidence row.

## 3. Authoritative builder and how legacy data is preserved (§3)

**Theory & Practical (`hybrid`, `/hybrid/builder/`) is the authoritative
builder** for new combined theory-and-practical content. The legacy
Practical/Theory builder is retired from instructor navigation only.

| Legacy asset | Where it lives | Still reachable |
| --- | --- | --- |
| Scenario authoring | `instructor_portal/urls.py:35-54` (`practical-builder-index`, `practical-builder`, `practical-edit`, `practical-preview`, `practical-create`) | yes, by URL; covered at `tests/test_course_authoring_edit.py:495` |
| Scenario runtime | `/practice-desk/`, `/roadmap/` (`scenarios/desk.py`) | yes, unchanged |
| Lesson ↔ module join | `ScenarioVersion.module` (`scenarios/models.py:192`) | unchanged; no migration touched it |
| Enrolments, attempts, progress | `onboarding`, `learning`, `hybrid` attempt tables | unchanged; still readable |

No lesson, enrolment, attempt or progress record was converted or deleted.
Lessons that cannot be migrated keep their own path rather than being silently
rewritten into the hybrid model.

## 4. Exact files modified

| Commit | Files |
| --- | --- |
| `a2e79e5` Consolidate instructor authoring onto two builders | `core/admin_dashboard.py`, `hybrid/forms.py`, `hybrid/instructor_views.py`, `templates/hybrid/builder_index.html`, `templates/instructor_portal/course_builder.html`, `templates/instructor_portal/dashboard.html`, `tests/test_hybrid_builder.py` |
| `53f3d1c` Author verification values without JSON | `hybrid/forms.py`, `scenarios/bindings.py`, `templates/hybrid/lesson_editor.html`, `tests/test_hybrid_builder.py`, `tests/test_hybrid_progress.py` |
| `52c8745` Publish journeys whose records the learner creates | `hybrid/creation_ledger.py`, `hybrid/publishing.py`, `tests/test_stage2_journey_publication.py` |
| `002fff5` Accept the instructor-to-student path through real forms | `tests/test_acceptance_instructor_to_student.py` (new) |
| `6b232b5` Render the workspace reading and size an unstarted journey | `hybrid/views.py`, `templates/hybrid/workspace.html`, `tests/test_hybrid_workspace.py`, `tests/test_stage2_journey_student.py` |
| this report | `docs/instructor-builder-consolidation-delivery-2026-10-29.md`, `scenarios/views.py` (docstring only) |

The two defects `6b232b5` fixed: the workspace escaped the theory blocks it was
supposed to render (it now pipes them through `rich_content`), and a journey with
no attempt yet reported `position_total` from the role count — an unrelated
number — instead of its assigned step count.

## 5. Migrations

Created earlier in this line of work, **still unapplied on the development
database** (verified with `showmigrations --list`, which reports nothing else
pending):

- `hybrid.0006_simulatorrecordcreation`
- `hybrid.0007_journeyrecordassociation_unique_active_created_in_journey_claim`
- `hybrid.0008_journey_verification_evidence`

No new migration was needed by this batch. All three applied cleanly to a copied
database and are SQLite/PostgreSQL portable as written. Per the mission they were
not applied to `local_data/db.sqlite3` — see §13.

## 6. Automated results

Full suite after the batch: **`1 failed, 977 passed`** (`python -m pytest tests
-q`, ~110 s).

The single failure is pre-existing and unrelated to anything here:
`tests/test_admin_enrolment.py::test_monthly_password_is_hashed_and_shown_once`
(fails identically at the `9c7d0d9` baseline). Everything else in §10 is green,
including the new acceptance file, `tests/test_hybrid_builder.py` (25 tests),
`tests/test_stage2_journey_publication.py`, `tests/test_hybrid_workspace.py` and
`tests/test_stage2_journey_student.py`.

## 7. Browser acceptance results

Run against a **copied** development database (`local_data/db.hybd.sqlite3`,
scratch settings, served on `localhost` so it could not share a session with the
running dev server), then torn down; the real database was re-checked read-only
afterwards and shows no stray users, no stray ledger rows and the same four
hybrid courses.

Verified by hand as a learner: simulator sign-in inside the frame (the login POST
returned to the requested screen), the real UCR form producing `TEMPUCR260000018`
after three required fields were completed, attribution showing
"Current record: #59 · Created in journey", live **Check my work** answering
"✓ A UCR declaration saved as “Draft” — Verified.", **Next step** enabling and the
frame swapping to `/practical/single-window/overview/`, one evidence row written,
and the lesson attempt completing.

**Not verified in a browser:** the wide two-pane split and the divider drag — the
embedded browser viewport is fixed at 531×553 (`window.resizeTo` is blocked), so
only the responsive single-pane branch was exercised. The desktop layout needs
one look in a real browser. Code paths and CSS for the drag are covered by the
unit tests only.

## 8. Activity verification — what is proven, and what is not (§7)

**Proven with trustworthy evidence, and claimed:**

- *Record creation is actor-bound.* `hybrid/creation_ledger.py` connects
  `post_save` for all four verifiable record models and writes a
  `SimulatorRecordCreation(record_kind, record_id, owner_id, record_created_at)`
  row inside the creating request's own transaction, taking `owner_id` from
  `request.user`. `role_satisfied` will not accept a "created in journey"
  association without that row, and refuses a row older than the attempt's start.
- *Opening a step is actor-bound.* The opening record carries a generation UUID,
  an owner-scoped lesson attempt, and a server-side authorization check;
  verification freshness is measured from it.
- *Attribution is a deliberate act.* A record is bound to a role through the
  student's own POST to the role-attribution endpoint, not inferred.
- *Writes are owner-scoped.* Simulator writes filter by `owner=request.user`
  (`scenarios/views.py:_requested_ucr_draft`) and review sessions are
  write-refused, so an owner id in the ledger means the authenticated holder of
  the simulator credential issued by `SimulatorCredential.issue()`.

**Deliberately not claimed:** that a learner performed a particular edit, click
or field change. `_record_activity` reads `max(updated_at, submitted_at,
created_at)` only as a **freshness bound** — the record must be no older than the
opening — and never as evidence of who changed what. There is no per-action
attribution, so the product does not assert one. Outcome verification ("the
record the learner selected has these saved values, in this status, and is no
older than this opening") is what the workflow completes on; that experience is
fully delivered and tested.

**Smallest necessary design, if action verification is ever wanted:** one
append-only ledger row per state-changing simulator action, mirroring
`hybrid/creation_ledger.py` exactly — written by an explicit call inside each
route's existing transaction, with `(owner_id, record_kind, record_id, action,
journey/step context, timestamp)`. No general event bus, no request middleware
that logs every write, no second parallel activity system, and no change to the
evidence model. It needs one decision from Bernard before it is built: **which
routes are student-writable enough to be worth an action row.** No lifecycle
coding was authorized, and none was written.

## 9. Known limitations

1. The three `hybrid` migrations are unapplied on the development database, so
   the creation ledger, the claim-uniqueness constraint and the evidence table do
   not exist there yet; the flagship journey cannot run against it until they are
   applied (approval needed).
2. Desktop-width split screen and divider drag are untested in a real browser (§7).
3. Legacy builder B remains fully reachable by URL; retiring it from navigation
   is a soft retirement, not a migration. Nothing was mapped into the hybrid model.
4. `?path=theory` / `?path=combined` are still accepted by
   `instructor_portal/views.py:234` and have no UI to set them; the value only
   round-trips to the template. Left alone deliberately, as the underlying content
   is still reachable through the tabs' absence.
5. Actor attribution stops at record creation (§8) — by design, not by omission.
6. `simulator-portal` is the frame for a hybrid lesson whose journey has no steps
   yet; that lesson cannot complete until an instructor assigns them.
7. The pre-existing password test failure (§6) is untouched.

## 10. How to test locally

```bash
# 1. Environment
.venv/Scripts/python.exe -m pytest tests -q          # expect 1 failed, 977 passed

# 2. Bring the development database up to the evidence schema
#    (needs Bernard's approval first — it writes to local_data/db.sqlite3)
.venv/Scripts/python.exe manage.py migrate hybrid
.venv/Scripts/python.exe manage.py runserver         # 127.0.0.1:8000 / localhost:8000

# 3. Authoring path, as an instructor
#    /hybrid/builder/  -> create programme -> course -> module -> lesson
#    lesson editor: theory blocks, steps (screen from the approved list),
#    condition with "Saved value" + "Expected saved value", journey + role,
#    preview, then publish (the review tab names any remaining blocker)

# 4. Student path, as an enrolled learner
#    /theory/ roadmap -> Practical journeys card -> lesson workspace
#    read theory, open the step, perform it in the simulator iframe,
#    attribute the record, Check my work, Next step

# 5. One-command acceptance of the whole chain
.venv/Scripts/python.exe -m pytest tests/test_acceptance_instructor_to_student.py -q
```

To repeat the browser walkthrough safely, copy the database and run a scratch
settings module against the copy — never against `local_data/db.sqlite3`.

## 11. Remaining VPS / deployment blockers

- **PostgreSQL cutover is not done.** Development is SQLite; production is
  intended to be PostgreSQL on the VPS. The scoped import has not been written,
  and no SQLite concurrency result here should be read as Postgres proof.
- The three `hybrid` migrations must run against the production database as part
  of that cutover (they were written portably and applied cleanly to a copy).
- `static_collected` is deploy output and must not be hand-edited; nothing here
  changed it.
- Nothing has been deployed, pushed or published, and no paid third-party service
  was introduced.

## 12. Classification of remaining work

- **Blocking product functionality:** apply `hybrid` 0006–0008 to the development
  database (§13); confirm the desktop-width split screen and divider drag in a
  real browser.
- **Security or data integrity:** none open from this batch. Creation provenance,
  fail-closed roles, evidence-authoritative progression and owner-scoped writes
  all hold. Action-level attribution is a scope question, not a hole (§8).
- **Deployment requirements:** the SQLite → PostgreSQL cutover and its scoped
  import; production migration run; static collection on the VPS.
- **Optional enhancements:** retire builder B's URLs once no content depends on
  them; drop the dead `learning_path` parameter; add the per-action ledger if
  action verification is ever required; rename `_frame_for_practice_desk` now
  that the shipped workspace depends on it.

Nothing unfinished is being reported as complete: the authoring chain, the
publication gate, the workspace and the verification chain are delivered and
tested; the desktop-width browser check, the development-database migration and
the Postgres cutover are not.

## 13. Awaiting Bernard's approval

1. **Applying `hybrid` 0006, 0007 and 0008 to `local_data/db.sqlite3`.** The
   creation ledger, the unique active claim constraint and the evidence table do
   not exist on that database yet, so the learner-creates-the-record journey
   cannot run there.
2. **The publication-gate relaxation** in §2 — removing the required-"new"
   role blocker and its optional-role warning — as a deliberate decision rather
   than an incidental fix.
3. **New user-facing copy** written under the theme/copy lock, none of it yet
   approved: "New programme", "Programme name", "Programme code", "Create
   programme", the builder empty state "No Theory & Practical programmes yet —
   create the first above.", the builder header lead, the dashboard panel title
   "Theory & Practical builder", "Saved value", "Expected saved value",
   "Exactly what the simulator must have saved.", the "— None —" help text, and
   the validation messages ("Answer yes or no for this flag.", "Enter a whole
   number for this value.", "Choose which saved value this row checks.",
   "Choose a value saved on the same kind of record as this condition.", "Enter
   the value this saved column must have.", "Unknown saved value field(s): …").
4. **A browser look at the workspace at desktop width** (§7), since the embedded
   browser could only exercise the narrow layout.
