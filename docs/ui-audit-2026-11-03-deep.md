# Deep UI consistency audit — admin / instructor / student / simulator

**2026-11-03 · follow-up to [ui-audit-2026-11-03.md](ui-audit-2026-11-03.md) · dark theme · 1440×900**

You asked for the intensive pass: every little divergence between the four chrome worlds
(admin portal, instructor surfaces, student surfaces, simulator), especially the side panels,
pagination/page size, and popups. Everything below was measured live in the browser (computed
styles) and cross-checked against the stylesheets. **No code or styling was changed** — every fix
needs your approval under the theme lock.

---

## 0. Why everything is "a little bit different" — the root cause

Three structural facts produce almost every divergence below:

1. **Per-surface stylesheets re-define the same class names.** `.primary-button` is defined in
   **four** stylesheets (`app.css`, `dash.css`, `cargo-page.css`, `simulator-portal.css`) with
   different padding, radius and colors. Whichever stylesheet a page loads wins — so the *same
   class* looks different on every surface. Same pattern for `secondary-button`, `search-button`,
   `boe-lookup-btn`, `ucr-row-action`.
2. **One sidebar callback, three navigations, one shell.** `sidebar_navigation`
   (`core/admin_dashboard.py:855-882`) dispatches by path: `_admin_navigation` under `/admin/`,
   `_simulator_navigation` under simulator prefixes, `_student_navigation` everywhere else (the
   instructor items are bolted onto the student list). The shell is always Unfold's — *except* the
   simulator pages, which hand-roll their own sidebar in `base_simulator.html`.
3. **Five dialog styling families, four button systems, four message systems** (details below) —
   each surface brought its own instead of sharing one design system.

---

## 1. The left side panels, measured

All four chromes share the 288 px width and the `#0f172a` background, but:

| Property | Admin (`/admin/`) | Portal (student/instructor) | Simulator | 
|---|---|---|---|
| Search box ("Search apps and model…") | yes | yes | **absent** |
| Section headings | "Overview", "People"… — **no text-transform** | **"MY LEARNING" is uppercase**, but "Instructor" and "Administration" are not — mixed case *inside one sidebar* | no section headings |
| Nav link weight | 12 px / 600 | 12 px / 600 | **14 px / 400** (visibly lighter) |
| Collapse handle | yes | yes | yes (same shell) |
| Active-item logic | 1 item | **2 items active at once** (measured on `/instructor/`: "Dashboard" + "Instructor"; on course pages: Dashboard + Learning Roadmap + dead "Assessments") | n/a (student session also showed Login / Forgot Password? / Request Account all active-looking) |
| Brand header | logo + "ICUMS Simulator / Training administration" | same | same brand block + a second in-content brand bar (the sim header) — **two stacked brand bars** on sim pages |
| User chip | bottom | bottom | bottom |

Specific defects:

- **S1 — Mixed heading case in one sidebar.** "MY LEARNING" (uppercase, from the student nav
  markup) sits directly above "Instructor" / "Administration" (sentence case, from the generic
  group renderer). The admin sections are sentence case. One sidebar, two conventions.
- **S2 — Multi-active highlight.** The active logic matches several items simultaneously on every
  non-admin page measured, and the dead `#` Assessments link receives the active style (round 1,
  finding 5 — now quantified: 2–3 `a.active` at a time).
- **S3 — Simulator nav typography.** 14 px/400 links vs 12 px/600 everywhere else; no search box.
  If intentional (mimicking the real ICUMS portal), it still reads as a different product shell.
- **S4 — Simulator pages show two brand bars** (sidebar brand + the in-content
  "PRACTICAL TRAINING ENVIRONMENT / Cargo tracking dashboard" bar with its own logo chip).
- **S5 — Superuser lands on the learner dashboard.** `ui-audit-admin` opening `/` sees the student
  "Your training journey" page; the admin index is reachable only via the "Advanced Admin" link.
  Combined with the finding below, the admin's entry point is currently an error page.

## 2. Pagination and page size

| Surface | Mechanism | Controls shown | Wording |
|---|---|---|---|
| Admin changelists | server-side pagination | "Rows per page" select (10/20/50/100/200, default 100, `id="page-size"`) + numbered pagination + total count ("673 audit events") | — |
| Instructor roster (`/instructor/`) | **none** — all rows rendered, client-side JS filter | three filter inputs + live count | "Showing 5 of 5 students" (`dashboard.html:107`) |
| Theory & Practical builder landing | server-side `?q=` filter | search + Draft/Published segmented buttons | "Showing 4 of 4 programmes" (`builder_index.html:55`) |
| Theory course builder table | none | — | — |
| Every student list (roadmap, module, lessons) | none | — | — |

Defects:

- **P1 — The only real pagination lives in the admin.** The instructor roster will stop scaling
  (it renders every enrolment row and filters in JS; the roster count text even hardcodes
  "Showing {{ rows|length }} of {{ rows|length }}" server-side, then re-computes the same string
  in JS at `dashboard.html:163` — two implementations of one sentence).
- **P2 — No page-size choice anywhere outside the admin**, and the two "Showing X of Y" strings
  use different elements, styles and pluralization code paths (template `pluralize` filter vs JS
  ternary).
- **P3 — /admin/ index itself 500s** (`no such column: scenarios_ucrdeclaration.demonstration_session_id`,
  raised in `unfold.sites.index`): the four pending migrations from round 1 break not just the
  desk but the admin dashboard. Until `manage.py migrate`, the admin's entry point is a Django
  error page.

## 3. Popups and dialogs — five families, plus native dialogs

### 3.1 The styled `<dialog>` families (measured)

| Family (file) | Width | Padding model | Radius | Backdrop | Dark-mode behaviour |
|---|---|---|---|---|---|
| `account-dialog` (`dash.css`) — credential & multi-programme dialogs | min(30rem, 92vw) | padding 0 + light card | .75rem | rgba(20,25,45,.55) | **card forces light** (`#fff`/`base-50`, dark text) → bright white popup on a dark page |
| `code-dialog` (`cargo-page.css`) — reference-data Help dialogs | min(**58rem**, 92vw) | padding 0 + light card | .75rem | rgba(20,25,45,.55) | **forced light** (`#fff` card) |
| `simulator-login-dialog` (`simulator-portal.css`) | min(31rem, …) | padding 0 | **none (square)** | **rgba(8,12,22,.76)** — darkest | **forced light** |
| `authoring-course-modal` + ws/hyb variants (`instructor-theory-builder.css`, `hybrid-*-workspace.css`) | min(92vw, 38rem) (confirm: 30rem) | padding 1rem directly | .75rem | #0f172a80 (lightest) | **theme-aware** (`--au-surface` → dark in dark mode) |
| Unfold admin dialogs | admin's own | admin's own | — | — | theme-aware |

So the same product shows popups that are wide/narrow, dark/light, square/rounded, with four
different backdrop darknesses. In dark mode an instructor gets a dark Add-course dialog while a
student's Help dialog is a bright white rectangle — the strongest "the popups look off" driver.

### 3.2 Native browser dialogs still in product flows (census)

- **BOE desk (`templates/scenarios/boe_declaration.html`): ~20 `window.alert`/`window.confirm`
  calls** carrying real workflow ("Submit this declaration? …", "Saved as draft. … Click OK to
  continue…"). OS-styled, and inconsistent with the desk's own `boe-dialog`/`code-dialog`.
- Lesson editor (`rich-text-editor.js:618,640`): `window.prompt` for Link and Image (round 1).
- Instructor `module_edit.html:120` and `student_profile.html:10`: inline `onsubmit="return confirm(…)"`
  for destructive actions.
- Demonstration Studio (`demonstration_studio.html:63`): `window.confirm` for discard.
- Disclaimer checkbox: native HTML5 validation bubble (round 1).
- **Behavioural hazard:** native dialogs silently no-op inside embedded webviews (demonstrated in
  round 1), so the desk's alert-driven flows are the ones most at risk in the Demonstration Studio
  iframe.

### 3.3 What popups get right
The hybrid workspaces' dialogs (Add course/module, confirm dialogs) are the best-built family:
theme-aware, Esc/×/Cancel, focus lands inside. They are the model to converge on.

## 4. Buttons — four shapes for "the primary action"

Measured live:

| Realm | Class | Shape | Color | Type |
|---|---|---|---|---|
| Admin | Unfold default + "Filters" | radius **6 px**, 14 px/500, padding 8/12 | neutral dark | — |
| Portal dashboards | `student-ghost-action` (roster "Issue login") | **pill, radius 99 px**, 12.48 px/700, border 1.3 px | **transparent ghost** | primary action rendered as a ghost pill |
| Settings (student) | save button | **pill, radius 99 px**, 14 px/700 | light purple `#8a86de` filled | — |
| Authoring | `authoring-primary` | radius **8.8 px**, 11.2 px/**750**, min-height 37.6 px | deep purple `#5145cd` filled | — |
| Simulator | `search-button` | radius 8.8 px, 12.48 px/600 | light purple `#8a86de` | — |
| Desk | `boe-lookup-btn`, `ucr-row-action`, `document-add-button`… | their own | their own | — |

Defects:
- **B1 — Two different purples for "primary"**: authoring `#5145cd` vs settings/simulator
  `#8a86de`. Side by side (e.g. an authoring card next to a settings button) they visibly clash.
- **B2 — Radiuses run 6 px → 8.8 px → 99 px** across the product for the same role.
- **B3 — The roster's primary action ("Issue login") is a ghost pill**, weaker-looking than
  secondary buttons elsewhere; destructive "Delete" styling also varies (red outline in course
  builder vs `authoring-danger` vs plain text link).
- **B4 — Same-class divergence**: `.primary-button` padding/radius differ per stylesheet
  (§0.1), so the class cannot be trusted anywhere.

## 5. Text inputs, labels, help text

| Realm | Input font | Radius | Background | Border | Label |
|---|---|---|---|---|---|
| Admin changelist search | 14 px | 6 px | base-900 | admin | — |
| Portal roster + Settings | **13.6 px** | 8 px | `rgb(23,32,51)` | `rgb(43,57,80)` | 11.52 px/600 |
| Authoring dialogs/forms | **12 px** | 8 px | base-900 `rgb(15,23,42)` | `rgb(51,65,85)` | 11.2 px/**700** |
| Simulator portal | 13.6 px | 8 px | **purple `rgb(43,40,96)`** | `rgb(71,85,105)` | — |

- **I1 — Three input font sizes (12 / 13.6 / 14 px) and two background tones** for the same
  control, by surface.
- **I2 — The purple-filled cargo search input** (round 1) — only accent-filled input in the app.
- **I3 — Focus remains a three-way split** (round 1 §P3): nothing on mouse focus for
  chrome pages; 3 px translucent ring on authoring pages (overlapping helper text in dialogs);
  yellow `:focus-visible` keyboard ring from `app.css:13` that the other realms don't share.
- **I4 — Label conventions**: authoring labels render as **"Course title:"** (bold + colon),
  settings as "First name" (600, no colon) — two label languages.

## 6. Tables

| Realm | Header treatment | Density | Notes |
|---|---|---|---|
| Admin changelist | sentence case, bold, sort icons | comfortable | full toolbar (search, rows-per-page, filters) |
| Instructor roster (`dash-table`) | **uppercase**, small, grey | tight; horizontal scroll wrapper | client-side filter row above |
| Course builder table | uppercase | tight | **headers wrap letter-by-letter** ("MO DUL ES", round 1) |
| Authoring tables (`authoring-table`) | uppercase micro-headers | tight | used across builder pages |

- **T1 — Header case differs between admin (sentence) and everything else (uppercase).**
- **T2 — The course-builder column wrap** (round 1, finding 7) remains the worst table defect.

## 7. Page titles and typography

- **H1 scale**: authoring pages 32 px/750 + purple uppercase eyebrow ("THEORY & PRACTICAL ·
  PROGRAMME") + breadcrumb row — a three-element header stack; student Settings 23.2 px/700 with
  no eyebrow; admin uses Unfold breadcrumbs ("Audit › Audit events"); simulator pages use the
  two-line brand bar instead of a page title.
- **H2 — Four different page-header patterns** across the four chromes; the authoring header
  stack is the most developed, the simulator's is the least (the page title lives in the brand
  bar, e.g. "Cargo tracking dashboard").

## 8. Flash messages — four systems

| System | Where | Look |
|---|---|---|
| Unfold admin message | admin + **hybrid workspaces** (the "Course created." green bar) | full-width tinted banner at top of content |
| `.portal-messages` (`simulator-portal.css:25`) | simulator | **fixed top-right toast**, white card + colored left border — **forced light in dark mode** |
| `.lrn-feedback` (`lesson.css:20`) | lesson pages | small inline tinted pill |
| `.message` (`app.css:32,89,136`) | misc | left-accent panel |

- **M1 — Same event, four presentations** (e.g. a save success shows a green bar in the builder
  but would be a white toast in the simulator).
- **M2 — The simulator toast is light-styled in dark mode** (same forced-light problem as the
  dialogs).

## 9. Pills, badges and status colors

- Status pills exist as `dash-pill` (is-ok/is-warn/is-muted), `authoring-status` (accent tint),
  settings pills (green tint, radius 99 px), sim pills, admin badges — **at least five pill
  systems** with different radii/padding/tints.
- **R1 — "Draft" is inconsistent**: amber pill in hybrid workspaces, plain grey text in the
  journey organizer ("Draft" above "Journey title:", unstyled), admin badges differ again.

## 10. Empty states

- **E1 — Two qualities**: styled empty states exist (workspace "No modules yet" with icon, text
  and action button) next to bare text rows ("No enrolments are available." inside a table cell,
  dashboard roster) — same product, two grades of empty state.

## 11. Round-1 items — status check

All round-1 findings remain open (no fixes applied). Two upgraded: the pending migrations now
also break **/admin/** (P3 above), and the purple search input + focus split are subsumed by
§5/I2–I3. New this round: S1–S5, P1–P3, B1–B4, H2, M1–M2, R1, E1, plus the dialog-family table.

---

## Suggested convergence targets (for your approval, not implemented)

If you want one recommendation: adopt **three shared systems and delete the per-surface copies** —
1. one dialog style (the hybrid `authoring-course-modal` family: theme-aware, backdrop #0f172a80,
   .75rem radius) with one close-button treatment;
2. one primary/secondary button pair (the `authoring-primary/secondary` pair is the most complete:
   hover/focus/disabled/danger variants exist);
3. one message component (choose banner vs toast; the simulator toast is the outlier that must
   change either way because it is forced light);
plus: one sidebar heading convention, one input style, uppercase-to-sentence-case decision for
table headers, and server-side pagination (or at least a shared count component) for the roster
once it grows. Each of these touches locked styling/copy, so they proceed only with your explicit
yes, in whatever order you choose.

## Audit footprint (disclosure)

New artifacts: `ui-audit-admin` superuser (password `UiAudit-2026`), two disclaimer acceptances
and audit-log rows created by the walkthrough. The browser session exercised read-only pages
except the four logins/logouts and the earlier round's disclosed writes. Nothing committed.
