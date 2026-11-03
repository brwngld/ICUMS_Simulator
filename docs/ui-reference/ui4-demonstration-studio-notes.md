# UI 4 — Demonstration Studio: functional assessment and design notes

Prototype: [`icums_instructor_demonstration_studio_ui4.html`](icums_instructor_demonstration_studio_ui4.html)
— standalone, sample data only, every capture and validation action labelled
simulated. The approved Studio (`demonstration_studio.html`, committed) is
**unchanged**; this is a concept for its evolution. Nothing is committed for
UI 4 and no Django code was touched.

2026-11-02 revision: the standalone prototype now demonstrates Start, Pause,
Resume, Stop, confirmed discard, status/count, timeline selection and explicit
conversion into editable lesson-step drafts. The simulator area is labelled a
standalone placeholder rather than a representative simulator. See
[`ui4-embedding-recording-feasibility.md`](ui4-embedding-recording-feasibility.md)
for the repository-backed iframe decision, recording architecture, isolation
requirements, stages, tests and approval questions.

## Part 1 — Functional assessment (what exists today)

**Implemented (reused as the foundation):**
- **Lesson-to-studio navigation** — two entry points, both committed:
  "Open Demonstration Studio" on the Module Workspace lesson cards and the
  activities tab link in the full editor
  (`hybrid-lesson-demonstration-studio`, `instructor_urls.py`).
- **Route, permissions and draft restriction** — `lesson_demonstration_studio`
  view: `login_required`, `_require_instructor`, `_draft_lesson` (published
  editions 404), GET-only (405 otherwise); six tests in
  `test_instructor_demonstration_studio.py` including "the studio persists
  nothing".
- **The approved mock UI** — three-tab layout (Demonstrate / Review steps /
  Student preview) with the client-side simulated capture timeline; explicitly
  labelled "recording is simulated client-side".
- **Practical activity authoring lives in the full editor** — the activities
  tab's per-step cards (`StepForm`: title, instruction, outcome, hint,
  screen) with per-card saves, add/move/remove, dependency assignment and
  per-card verification-condition authoring (`VerificationConditionForm`).
- **Expected-outcome configuration** — the step's `outcome` field plus
  server-verified checks: `screen_opened` and `saved_record` conditions whose
  record/status choices come from the shared registry
  (`scenarios/bindings.py`).
- **The real simulator** — the production target to embed: the scenarios app's
  routes (`SIMULATOR_BINDING_ROUTES`: 8 developer-approved screens from
  "Simulator portal" to "Search consignment applications"), which the full
  editor's screen select and the verification engine already reference.
- **Simulator state tracking and validation (runtime)** — the Stage 3 engine:
  `record_open`/step events, verification of `screen_opened` and
  `saved_record` conditions against the learner's own records, journey
  attempts with dependencies and completion checkpoints.

**Partially implemented:**
- **Demonstration capture** — only the client-side mock exists; no action
  model, no persistence, no link between a demonstration and authored steps.
- **Expected-outcome feedback during authoring** — the editor validates
  structurally (`lesson_issues`: instruction/outcome/screen per step) but
  shows nothing interactive beside a simulator while authoring.

**Missing (genuinely new work for a future stage):**
- Embedding the real simulator inside the studio surface.
- A demonstration-capture model (what the instructor did, scoped to the
  lesson, isolated from student data).
- Capture→step drafting (turning demonstrated actions into proposed
  activities), with the instructor editing everything before save.
- Any saving, resuming or editing of demonstrations (today the studio writes
  nothing, by design and by test).

## Part 2 — The UI 4 design

One screen, two zones, on the approved studio's visual foundation:

1. **Simulator zone (left, full visibility)** — a clearly labelled standalone
   placeholder in its own scroll pane (620px desktop / 480px laptop-column).
   The production target is the actual same-origin Django simulator, not this
   placeholder.
2. **Capture timeline (right)** — simulated Start/Pause/Resume/Stop/discard,
   status and count, allowlisted meaningful actions, instructor selection and
   explicit draft conversion, with the isolation principle restated.
3. **Practical activities zone (below)** — the lesson's steps as full
   activity cards: title, **screen select limited to the real 8-route
   registry**, instruction, expected outcome, hint; prev/next navigation
   between activities with step chips; **validation strip mirroring the real
   readiness rules** ("Not publish-ready — the activity has no instruction /
   no expected outcome / no simulator screen" → "✓ Ready").
4. **Capture→draft review** — selected simulated actions create one editable
   lesson-step draft. The existing "Prefill from simulated capture" remains a
   secondary prototype affordance; both are explicitly labelled simulated.
5. **Student preview tab** — unchanged from the approved studio.

## Backend mapping (what each prototype element binds to)

| Prototype element | Production binding |
| --- | --- |
| Simulator panel | The scenarios app routes (`SIMULATOR_BINDING_ROUTES`); embed mechanism is an open decision (D1) |
| Capture timeline | New demonstration-capture model — does **not** exist; requires authorization (D2) |
| Activity cards | Existing `StepForm` fields (`title`, `instruction`, `outcome`, `hint`, `screen`) — same POST path as the editor's cards |
| Screen select | `binding_route_choices()` — the identical registry the editor uses |
| Validation strip | `hybrid.publishing.lesson_issues` step rules (instruction/outcome/screen) |
| Prefill from capture | New capture→draft service — does not exist (D2) |
| Student preview | Existing lesson preview |

## Open decisions requiring approval

1. **D1 — Simulator embedding mechanism.** Repository inspection supports a
   same-origin iframe with per-response framing permission. Production work is
   gated on demonstration-data isolation and an approved route allowlist.
2. **D2 — Demonstration capture.** Whether to build a capture model at all
   (and its isolation rules), or keep the studio as an authoring workspace
   beside the simulator without capture. The prototype's capture timeline and
   prefill are only meaningful if D2 is approved.
3. **D3 — Authoring split.** Should the studio own activity creation
   (posting `StepForm` directly) or remain a companion surface that deep-links
   into the full editor's cards (current behaviour, zero new backend)?
4. **D4 — Validation depth.** Strip mirrors structural step rules only, or
   also surfaces verification-condition readiness (roles, bindings) from the
   review tab.

## Screenshots

`docs/ui-reference/screenshots/ui4-studio-*.png` — 1440×900, 1366×768,
768×1024, 390×844 in light and dark, plus capture-prefill and validation
states.

The 2026-11-02 recording revision adds `ui4-recording-idle.png`,
`ui4-recording-recording.png`, `ui4-recording-paused.png`,
`ui4-recording-stopped.png` and `ui4-recording-review.png`.
