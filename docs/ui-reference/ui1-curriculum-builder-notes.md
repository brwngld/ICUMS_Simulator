# UI 1 — Theory & Practical Curriculum Builder: prototype notes

Prototype: [`icums_instructor_curriculum_builder.html`](icums_instructor_curriculum_builder.html)
— one standalone file (inline CSS/JS, no dependencies, no network calls).
Open it directly in a browser; every interaction is simulated and nothing is
saved. This is a visual/interaction review artifact only — **no Django
template, model, view, route, form, migration, permission or test was touched,
and nothing is committed.**

## Layout

The page is the instructor's Theory & Practical landing inside the existing
Unfold shell, and it replaces the current form-heavy `builder_index` (whose
"New programme" and "New course" forms both sit on the landing page):

1. **Shell** — brand block, app search, role navigation with icon tiles
   (Dashboard / My Learning / Instructor groups, exactly the entries the
   portal sidebar renders today, with *Theory & Practical builder* active),
   user block, and the header bar with sidebar toggle, page title and the
   Training-environment badge.
2. **Page head** — the existing eyebrow ("Instructor · Theory & Practical"),
   the "Theory & Practical builder" title and its current lede copy, with one
   prominent **New programme** action on the right.
3. **Summary indicators** — four stat tiles (Programmes, Courses, Modules,
   Lessons) that recompute as data changes.
4. **Toolbar** — search by name or code, an All / Draft / Published segmented
   filter, and a "Showing X of Y programmes" count.
5. **Programme cards** — responsive card grid. Each card: name, programme
   code, one chip per edition (`v2 · Draft` amber / `v1 · Published` green),
   one row per edition with the draft/published edition accent bars from the
   current builder, course/module/lesson counts, and a **Manage programme**
   action. Course and module creation are *not* on this page — they move into
   the programme workspace this page leads to.

## Navigation

- The sidebar is a visual replica of the current portal navigation; items are
  simulated (no routing).
- The header toggle collapses the sidebar on desktop and opens a drawer with
  backdrop at tablet/mobile widths (Unfold's behaviour).
- **Manage programme** represents the entry point to a future dedicated
  programme workspace (editions, courses, modules, lessons). Clicking it shows
  a clearly-simulated message; no workspace is designed yet.
- Hierarchy is unchanged: Programme → Course → Module → Lesson. No new levels.

## Interaction states (all simulated)

| State | How to see it |
| --- | --- |
| Loading | On first paint (~0.7 s skeleton cards) or via "Preview state → Loading" |
| Create dialog | "New programme" — Name + Code with per-field validation: required, length, code format (`lowercase-with-hyphens`), duplicate code, ~0.75 s simulated save with spinner |
| Success | After creation: Django-style green message, new card highlighted, stats and count update |
| Load error | "Preview state → Load error" — error card with "Try again" that replays loading |
| Empty | "Preview state → No programmes yet" — full empty state with CTA (summary tiles hide) |
| No results | Search "zzz" or a filter with no matches — inline empty state with "Clear search and filters" |
| Dark mode | The header moon/sun toggle (uses the app's `adminTheme` localStorage convention, `html.dark` + `data-theme`) |
| Reset | "Reset sample data" restores the initial set |

Keyboard: the dialog closes on Esc, submits on Enter, and traps initial focus
to the name field; focus-visible rings follow the app's conventions.

## Data provenance

- **Test, Testing, Testing 1** mirror the live database (read-only query:
  the three active Theory & Practical programmes, all draft v1, with their
  real course/module/lesson counts).
- **Declaration Skills** is *sample content* — the live database has no
  published hybrid edition, so this card (published v1 + draft v2)
  demonstrates the published state, edition stacking and its chip/accent
  treatment. It is not real data.

## Fidelity

- Colours are the frozen UNFOLD palette (`base` slate, `primary` indigo from
  `config/settings/base.py`); no new hues. Warning/success accents reuse the
  builder's existing edition colours.
- Cards, buttons, chips, tables and empty states reuse the `authoring-*`
  design system (`instructor-theory-builder.css`, `hybrid-builder.css`);
  the dialog follows the existing `authoring-course-modal` conventions.
- Sidebar tiles and icons are copies of the app's own SVG set
  (`templates/components/icon.html`), stroke-consistent with the shell.
- Motion (card rise-in, hover lift) follows `app.css`; `prefers-reduced-motion`
  is respected.
- The approved Demonstration Studio is untouched, as is the student workspace.

## Responsive behaviour

| Width | Layout |
| --- | --- |
| ≥ 1440 (desktop) | 3-card rows, sidebar visible, stats in one row |
| ~1024–1366 (laptop) | 2–3 cards, unchanged chrome |
| ≤ 1024 (tablet) | Sidebar becomes a drawer; 2×2 stats; cards 1–2 columns |
| 390 (mobile) | Single column, full-width filter row, drawer sidebar, dialog at 92vw |

## Open design decisions for approval

1. **Summary-indicator scope.** The tiles currently count *all editions*
   (labelled "· all editions"). Alternatives: draft editions only, or the
   latest edition per programme. Draft-only is probably the honest "working
   curriculum" number; needs your ruling.
2. **Card action set.** Cards expose only **Manage programme**; publishing,
   "New draft from this edition" and course creation move into the programme
   workspace. The current page exposes publish inline — confirm the move.
3. **Sample card.** Drop "Declaration Skills" once real published data exists,
   or keep a seeded demo programme in development?
4. **Creation surface.** The prototype uses a centred dialog (matching the
   existing course modal). A focused full-page creation view is the
   alternative if you prefer more room for help text.
5. **Filter semantics.** Draft/Published matches a programme having *any*
   edition in that state. Could instead show only matching editions inside
   each card.
6. **Review aids, not proposals.** The header theme-toggle button and the
   "Preview state / Reset" banner are review conveniences; the real UI would
   keep the theme control in the user menu and drop the banner.

## Screenshots

`docs/ui-reference/screenshots/ui1-builder-*.png` — 1440×900, 1366×768,
768×1024, 390×844 in light and dark, plus interaction states (dialog light +
dark, validation, created-with-message, loading, error, empty, no-results).
