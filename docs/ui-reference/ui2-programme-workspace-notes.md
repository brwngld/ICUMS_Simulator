# UI 2 — Instructor Programme Workspace: prototype notes

Prototype: [`icums_instructor_programme_workspace.html`](icums_instructor_programme_workspace.html)
— one standalone file (inline CSS/JS, no dependencies, no network calls).
Open it directly in a browser. It carries a clearly-labelled sample programme
("Declaration Skills") and every interaction is simulated — nothing is saved.
Design-only: **no Django view, URL, template, form, model, migration or record
was touched for UI 2**, and nothing is committed.

Visual language is identical to the approved UI 1 landing
([`icums_instructor_curriculum_builder.html`](icums_instructor_curriculum_builder.html))
and the shell conventions of the Unfold instructor interface. The approved
Demonstration Studio and the student workspace are untouched.

## Page structure

Top to bottom inside the existing Unfold shell (sidebar, header, environment badge):

1. **Breadcrumb + back link** — "← Curriculum Builder" above
   "Curriculum Builder → Declaration Skills". The instructor can always see
   where they are and step back one level.
2. **Programme identity header** — eyebrow "Theory & Practical · Programme",
   the programme name, its code, a one-line explanation of what is being
   managed, and a chip row: "Managing v3 · Draft" plus one chip per edition
   (v3 Draft amber / v2 Published green / v1 Retired muted).
3. **Overview tiles** — courses, modules and lessons of the edition currently
   being viewed (labelled "· edition v3"), plus "Editions kept". No other
   dashboard furniture.
4. **Editions & publishing panel** — one row per edition, newest first, with
   the existing draft/published/retired accent bars:
   - *Draft (current)* — counts, **Publish edition**, "Viewing courses" state.
     Attached beneath it, a **publication-readiness strip** ("Not ready to
     publish — 1 of 2 courses ready" with the blocking course named, or
     "Ready to publish — all courses ready").
   - *Published* — counts + publication date, a lock-icon **Read-only** note,
     and **View courses**. "New draft from this edition" appears here **only
     when no draft is open** — with the sample's draft open it is correctly
     absent.
   - *Retired* — visually muted, no actions except viewing.
5. **Courses panel** — the courses of the edition being viewed: title, code,
   module/lesson counts, per-course Draft/Published chip, a "Not
   publish-ready" marker where applicable, and **Manage course**. A prominent
   **Add course** action sits in the panel header (draft edition only).

## Navigation behaviour

- The intended journey — Curriculum Builder → Manage Programme → Manage
  Course → Manage Module → Create or Edit Lesson → Demonstration Studio — is
  made legible here: the breadcrumb anchors this page one level below the
  builder, and each course card's "Manage course" represents the next step.
- **Manage course** shows a clearly-simulated message ("…would open the …
  workspace (modules, lessons and the Demonstration Studio for its
  Interactive Practical lessons). Designed separately.") — course, module and
  lesson pages are intentionally **not** redesigned in UI 2.
- The sidebar, its active state and the header are the shell's own; the
  prototype replicates them for review.

## Edition-management design

- The editions panel is the single source of truth for lifecycle state. No
  new lifecycle is invented: draft → published → retired, exactly as the
  backend models them today.
- **Edition switching** is row-level: "View courses" re-renders the Courses
  panel and the overview tiles for that edition. Viewing a published edition
  shows a green read-only banner ("…publishing made this edition the
  learners' copy") with a "Back to the open draft" action; Manage course is
  disabled there and Add course disappears.
- **Publication readiness** mirrors the backend's all-or-nothing rule without
  changing it: the draft row reports how many courses are ready and names the
  blockers. The Publish action itself is simulated and says so.
- **Retired editions** render muted with no actions; they remain viewable for
  the record.

## Course-management interactions

- **Add course** opens a focused dialog (title + optional description) — no
  permanent creation form sits above the list. The dialog states which
  edition it targets ("created inside draft edition v3"). Validation is
  simulated (title required, ≤180 chars); submit shows a brief "Creating…"
  state, then a simulated message and a highlighted new card with 0 modules /
  0 lessons and "Not publish-ready" — mirroring what an empty course really
  is. The card is only added when viewing the open draft.
- The empty-programme preview (banner select → "Empty programme") shows a
  first-run programme: empty draft, readiness "the edition has no courses
  yet", and an Add-course CTA inside the empty state.
- All destructive-feeling actions (Publish edition, New draft) answer with
  messages that explicitly say "Simulated — nothing was changed."

## Responsive behaviour

- ≥ 1024: sidebar visible, 4 tiles in a row, course cards 2–3 up.
- ≤ 1024: sidebar becomes a drawer with backdrop; tiles 2×2; cards 1–2 up.
- 390: single column; edition rows stack their action buttons under the row;
  readiness strip aligns left; dialog at 92vw. Verified no page-level
  horizontal overflow at any size.

## Assumptions about backend capabilities

- Course/module/lesson counts per edition are computable by aggregation (the
  UI 1 landing already computes them).
- Readiness maps onto the existing `edition_blockers` / course-ready checks —
  presented as course-level bullets, no new rules.
- Courses carry their own Draft/Published state inside an edition (the
  publishing sweep publishes ready courses), so per-course chips are honest.
- "New draft from this edition" is only offered when no open draft exists —
  matching the backend's reuse-or-create behaviour.
- The dialog's fields mirror `CourseCreateForm` (title, description) with the
  programme implied by the workspace context, as the scoped flow does today.

## Open design decisions requiring approval

1. **Edition switching model** — row-level "View courses" (this prototype)
   vs. a persistent edition selector (tabs/dropdown) in the header.
2. **Readiness detail** — course-level bullets (shown) vs. a fuller checklist
   of every blocker message the backend can produce.
3. **Placement of Publish / New draft** — inside the editions panel (shown)
   vs. duplicated in the page header for one-click reach.
4. **Sample data** — "Declaration Skills" is illustrative (the live database's
   Theory & Practical programmes are throwaway "Test/Testing" entries with no
   published or retired editions). Confirm whether a seeded demo programme
   should exist in development for review purposes.
5. **Manage course transition** — until the course workspace is designed,
   Manage course would deep-link to the existing `hybrid-course-edit` page;
   confirm that interim target.
6. **Review aids** — the banner select and header theme toggle are prototype
   conveniences and would not ship.

## Screenshots

`docs/ui-reference/screenshots/ui2-workspace-*.png` — 1440×900, 1366×768,
768×1024, 390×844 in light and dark, plus states: Add-course dialog,
published-edition read-only view, empty programme.
