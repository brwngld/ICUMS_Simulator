# UI 3 — Course, Module and Lesson Management: prototype notes and assessment

Prototype: [`icums_instructor_course_workspace.html`](icums_instructor_course_workspace.html)
— one standalone file, sample data only, every interaction simulated and
labelled. Design-only: **no Django view, URL, template, form, model or record
was changed for UI 3**, and nothing is committed.

Visual language is identical to the approved UI 1 landing and UI 2 workspace.
The Demonstration Studio, the student workspace and publishing rules are
untouched.

## Part 1 — Existing functionality assessment (Task B)

Inspected: `course_edit` (course details, modules CRUD, journeys),
`module_edit` (lesson rows, creation, ordering), `lesson_edit` (four-stage
editor with per-activity cards and checks), the journey organizer, and their
templates — all draft-scoped and instructor-gated, covered by ~60 tests in
`test_hybrid_builder.py`.

**Works and is reused unchanged in UI 3's design:**
- Course details form (title/description); module create / move up-down /
  remove (with the real `ProtectedError` guard — a module with lessons refuses
  to die); journey creation (title, description, start mode) and organizer links.
- Lesson creation with the type select (Guided Material Study visible but
  disabled), redirect into the Demonstration Studio for Interactive Practical.
- Lesson rows carrying type, step count and theory-written state; lesson
  move/reorder; the four-stage lesson editor and Student preview; the journey
  organizer with roles/dependencies/checkpoints.
- Permissions and draft-only editing (`_draft_course/_draft_module/_draft_lesson`
  404 published content).

**Needs improvement (addressed by the UI 3 design):**
1. **Back-navigation is stale after UI 2** — the course page's "All courses"
   link still targets the landing; with the workspace in place the chain
   should read Programme workspace → Course → Module → Lesson.
2. **Creation forms are permanent inline forms** above each list (module,
   journey, lesson) — the approved pattern is focused dialogs.
3. **No course-level readiness** — readiness exists per lesson (review tab)
   and per edition (workspace); the course page shows journey issue counts
   but not "what is left to publish" for the course.
4. **No per-lesson readiness markers** on the module page (only
   "theory written").
5. **Destructive actions have no confirmation step** (module/lesson remove).
6. **No sibling context** — a course page doesn't show the other courses in
   the edition, nor link back to the workspace.

**Critical functional gaps:** none — every workflow above functions
end-to-end and is tested. The gaps are coherence and workflow quality, not
broken features.

## Part 2 — The UI 3 design

### Page structure (two simulated pages, one hierarchy)

**Course workspace** (opens from Manage course in the Programme Workspace):
1. Back link + breadcrumb: Programme workspace → Course.
2. Identity header: course name, code, "draft edition v3", Draft chip.
3. Overview tiles: modules, lessons, practical journeys, items to resolve.
4. **Publication readiness** — course-level, from the same backend blockers
   (`course_blockers`): "Not ready to publish — N items to resolve" with an
   expandable list naming each module/lesson/journey issue; "Ready to
   publish" when clear.
5. **Modules panel** — cards with title, code, lesson count, Draft chip, a
   "No lessons yet" marker, move up/down, and **Open module**; **Add module**
   dialog (title + optional description).
6. **Practical journeys panel** — existing organizer links and the journey's
   outstanding-requirement count; New journey opens the existing form flow.

**Module workspace** (opens from Open module):
1. Back link + breadcrumb: Programme workspace → Course → Module.
2. Identity header: module name/code, **Add lesson** action.
3. **Lessons panel** — type-aware cards: title, code, kind chip (Interactive
   Practical / Guided Material Study), step count, theory-written state,
   "Material Studio coming soon" for Guided Material Study, move up/down, and
   per-lesson actions exactly as they work today: **Open Demonstration
   Studio** and **Full editor** (Interactive Practical only — Guided Material
   Study's editor stays disabled until the Material Studio exists).
4. **Add lesson dialog** — title, type select (Guided Material Study
   disabled), summary; the created Interactive Practical lesson announces it
   would open in the Demonstration Studio, exactly as the current flow does.

### Navigation behaviour

- The full chain is visible: Curriculum Builder → Programme workspace →
  Course workspace → Module workspace → Lesson editor / Demonstration Studio.
  Course and Module pages carry back links and breadcrumbs; the lesson editor
  keeps its existing "Back to module".
- **Manage course** in the Programme Workspace and **Open module** here are
  the two new links; everything deeper is the existing, unchanged pages.
- Draft-only editing is preserved: these workspaces exist for draft editions
  (published content 404s today, as tested).

### Course-management interactions

- Move up/down simulates the existing `_move` ordering with a "Simulated —
  module order saved." message; reorderable lists include real disabled
  states at the ends.
- Add module validates (required, ≤180 chars) and flashes the new card —
  an empty module immediately shows "No lessons yet" and contributes a real
  blocker ("Module … has no lessons.") to the readiness panel.
- The readiness list is recomputed from the same rule shapes the backend
  uses (module without lessons, Interactive Practical lesson without steps,
  journey requirements).

### Assumptions about backend capabilities

- Per-course blockers: `publishing.course_blockers(course)` already exists
  and produces exactly the items shown.
- Counts: aggregation as in UI 1/UI 2.
- Dialogs map to the existing `ModuleForm` (title/description) and
  `LessonDetailsForm` (title/kind/summary) — no new forms needed.
- Ordering reuses the existing `_move` helper and hidden-form POST pattern.

## Responsive behaviour

- ≥ 1024: sidebar visible, tiles in a row, cards 2–3 up.
- ≤ 1024: drawer sidebar, 2×2 tiles, cards 1–2 up.
- 390: single column; move buttons join the footer row; dialogs at 92vw;
  no horizontal overflow at any size.

## Open design decisions requiring approval

1. **Two pages vs one** — the prototype splits Course (modules + journeys)
   and Module (lessons) into two pages, matching today's URLs. A combined
   single-page "course + its modules' lessons" accordion is possible but
   denser; not recommended.
2. **Readiness placement** — a dedicated panel at the top of the course page
   (shown) vs. a compact chip in the header only.
3. **Destructive-action confirmations** (module/lesson remove) — the current
   pages have none; adding a confirm dialog is a behaviour change that needs
   your sign-off.
4. **Sample data** — "Registering a UCR in the Single Window" is illustrative;
   the live database's courses are throwaway entries.
5. **Review aids** — the header theme toggle is a prototype convenience and
   would not ship.
