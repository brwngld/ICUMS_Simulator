# UI 1 — Backend Compatibility Assessment: Curriculum Builder landing page

Assessment only. No code, templates, migrations, tests, commits or pushes were
changed for this document. Approved reference:
[`icums_instructor_curriculum_builder.html`](icums_instructor_curriculum_builder.html)
(layout, components, typography and interaction patterns are frozen for
implementation). Companion notes: [`ui1-curriculum-builder-notes.md`](ui1-curriculum-builder-notes.md).

Baseline: branch `feat/theory-experience-faithful` at `a9397bd` (Stage 1 closed),
suite 1057 passing, real database 0 FK violations, hybrid 0001–0009 applied.

## 1. How the backend is organised today

Everything the landing needs already exists behind one view and one URL:

- **View** `builder_index` — [hybrid/instructor_views.py:288](../hybrid/instructor_views.py)
- **URL** `path("", builder_index, name="hybrid-builder")` — [hybrid/instructor_urls.py:7](../hybrid/instructor_urls.py) (served under `/instructor/hybrid/`)
- **POST actions** dispatched on `action`: `create_programme`, `publish_edition`,
  `new_draft`, and the default course-creation branch.
- **Forms** `ProgrammeCreateForm` (name ≤150, code SlugField ≤50 unique —
  [hybrid/forms.py:65](../hybrid/forms.py)) and `CourseCreateForm`.
- **Edition engine** `_draft_version` (reuse open draft, else create
  v(max+1) empty), `_ensure_draft_tracking`, `edition_blockers`,
  `publish_edition`, `clone_to_draft` ([hybrid/publishing.py](../hybrid/publishing.py)).
- **Editions** `ProgrammeVersion.Status = draft | published | retired`,
  unique `(programme, version)` ([onboarding/models.py:95](../onboarding/models.py)).
  The current template renders *all* statuses, retired included.
- **Gates** `login_required` + `_require_instructor` (Instructor/Administrator
  group or superuser) — every route; draft-scoping helpers 404 published
  content for editing.
- **Shell** `render_student_page` supplies the Unfold chrome, role sidebar
  (`Theory & Practical builder` is already a sidebar entry), breadcrumbs and
  the theme conventions.
- **Creation flow today** (what the dialog must slot into): valid
  `create_programme` → save, set `learning_track=HYBRID`, `_draft_version`,
  success message, redirect to `hybrid-builder`. Invalid → full page re-render
  with `status=400` and inline form errors
  (`test_a_programme_with_a_taken_code_is_rejected_without_creating`,
  `test_a_programme_post_does_not_validate_the_course_form`).

## 2. UI-to-backend compatibility matrix

| # | Approved UI element | Existing backend support | Verdict |
| --- | --- | --- | --- |
| 1 | Unfold shell, portal sidebar, theme | `render_student_page` + `_student_navigation`; `theme.js` conventions | **Reused as-is** — the prototype's sidebar was a replica of this |
| 2 | Page head (eyebrow, title, lede) | Existing `builder_index.html` copy | **Reused verbatim** (copy is frozen) |
| 3 | Prominent New programme action | POST `action=create_programme` on `hybrid-builder` | **Reused**; only presentation moves into the dialog |
| 4 | Creation dialog: name + code | `ProgrammeCreateForm` (unique SlugField, max lengths) | **Reused**; see §5 for the error round-trip |
| 5 | Validation states (required / format / duplicate) | ModelForm: required + `unique` enforced server-side; tests cover both | **Reused**; the prototype's format regex is *stricter* than `SlugField` (no underscores) — fine as UI guidance, backend unchanged (D7) |
| 6 | Simulated save latency + spinner | n/a (prototype affordance) | **Front-end only**; real submit is a normal POST |
| 7 | Success confirmation | `messages.success("Programme created in a new draft edition v1.")` | **Reused**; wording differs from the prototype's (copy decision, D5) |
| 8 | Summary tiles (4 totals) | **No support** — the page renders no totals | **New read-only context** in `builder_index`; definition must avoid double-counting (D1, §6) |
| 9 | Programme cards: name, code, state, editions, counts | Query already prefetches `versions__hybrid_courses`; course counts render today; draft/published status + `hyb-edition--*` accents exist | **Mostly reused**; per-edition **module/lesson counts are new** (view aggregation, no model change) |
| 10 | Edition chips `v2 · Draft` / `v1 · Published` | `ProgrammeVersion.Status` + existing edition styles | **Reused**; **retired editions** have no prototype representation (D4) |
| 11 | Manage programme → workspace | **No dedicated workspace exists.** Nearest: `builder_index?programme=<pk>` scoping; courses deep-link to `hybrid-course-edit` | **Routing gap** — new thin `programme_detail` view/template (D2); one redirect-back tweak in POST handlers |
| 12 | Publish edition / New draft (on cards) | POST `publish_edition` (blockers-checked) and `new_draft` (`clone_to_draft`) already exist and are tested | **Reused unchanged**; placement moves from the landing into the workspace |
| 13 | New course form | `CourseCreateForm` + `_ensure_draft_tracking` + forged-pk protection (`test_a_scoped_course_post_cannot_move_to_another_programme`) | **Reused unchanged** in the workspace |
| 14 | Search (name or code) | **No support** | **Small view change**: `?q=` → `Q(name__icontains) \| Q(code__icontains)` (D8) |
| 15 | Draft/Published filter | **No support** | **Small view change**: `?status=` → `versions__status=…`, `.distinct()` (D6) |
| 16 | "Showing X of Y programmes" | Trivially derived from the filtered queryset | **New template context** |
| 17 | Loading / load-error / no-results / empty states | Empty branch exists in the current template; form errors already render at status 400 | **Template work**; loading skeletons are front-end-only; "Try again" is a reload |
| 18 | CSRF on the dialog form | `{% csrf_token %}` convention on every POST form | **Reused** — the dialog form carries the token like any other |
| 19 | Authorization (instructor-only) | `login_required` + `_require_instructor` on `builder_index` | **Reused unchanged**; existing tests cover denial and login redirect |
| 20 | Accessibility (labels, helptext, error lists, focus) | Django field groups render label + helptext + `errorlist`; native `<dialog>` gives focus management and Esc | **Template work** following the prototype's aria pattern |
| 21 | Responsive + dark mode | Unfold chrome already responsive; page CSS from the prototype uses only frozen palette tokens | **New builder stylesheet** (prototype CSS adapted; no theme edits) |

**Models/migrations required: none.** Every gap is view-context, template or
routing work.

## 3. Existing functionality that can be reused

`builder_index` view + `hybrid-builder` URL and all four POST actions ·
`ProgrammeCreateForm` / `CourseCreateForm` · `_draft_version` /
`_ensure_draft_tracking` · `edition_blockers` / `publish_edition` /
`clone_to_draft` · `_require_instructor` + `render_student_page` · messages
framework · `hybrid-course-edit` deep links · `authoring-*` design system CSS
and the app icon set · Unfold sidebar/header/theme · the 57-test
`test_hybrid_builder.py` baseline.

## 4. Missing functionality and necessary adaptations

1. **Summary totals** (view computation + approved definition, §6).
2. **Per-edition module/lesson counts** on cards (view aggregation; keep it
   O(1)-ish with `Prefetch`/annotation — the real dataset is tiny but the
   pattern should not N+1).
3. **Search + status filter** as GET params on `hybrid-builder`.
4. **Programme workspace** page and **Manage programme** routing, incl.
   returning POST redirects to the workspace instead of the landing.
5. **Dialog presentation + error round-trip** (§5) and its no-JS fallback.
6. **Retired-edition representation** (D4).
7. **Two copy deviations** needing sign-off under the copy lock (D5).

## 5. How the New Programme dialog submits through the existing flow

No JSON endpoint is needed. The dialog wraps the same
`ProgrammeCreateForm` fields and POSTs `action=create_programme` to
`hybrid-builder` with `{% csrf_token %}`:

- **Valid** → the view already redirects to `hybrid-builder` with a success
  message; the landing re-renders including the new card. (Optionally the
  template highlights the new programme when `?created=<code>` is present —
  cosmetic.)
- **Invalid** → the view already re-renders the page with `status=400` and
  field errors. Adaptation: the template marks the dialog
  (`<dialog ... open data-errors>`) when `programme_form.errors` is
  non-empty, so a few lines of JS reopen it and focus the first invalid
  field. No-JS fallback: the same markup renders the form expanded inline.
  This preserves both existing tests verbatim
  (`400` status; both "This field is required." messages present).

## 6. Summary tiles without double-counting

The hazard: after "New draft from this edition", a programme holds published
v1 **and** draft v2 whose content is a clone — counting every edition counts
the same curriculum twice, and historical numbers move as editions stack.

Proposed definition (**D1**): per programme, count its **open draft edition
if one exists, otherwise its latest published edition**; retired editions are
never counted; multiple drafts (possible in the schema, created one-at-a-time
by the flow) resolve the same way `_ensure_draft_tracking` does —
`.first()` under the existing ordering. Tiles then read as "the curriculum
being worked on, or what learners see when nothing is in flight". The
prototype's "· all editions" sub-label is replaced by this definition — an
approved-prototype deviation requiring sign-off. Real-data effect today: all
three hybrid programmes hold exactly one draft v1, so the numbers are
unchanged (4/8/9/18 includes the sample card; live data is 3/5/2/2).

## 7. Manage Programme navigation

- **Target (D2, recommended):** a new thin route
  `path("programmes/<uuid:programme_id>/", programme_detail, name="hybrid-programme-detail")`
  next to the existing builder routes. The template is the prototype's card
  content expanded into a page: edition rows (with Publish edition / New draft
  from this edition), the existing scoped New-course form, and the course list
  linking to `hybrid-course-edit`. The programme-detail view reuses
  `_require_instructor`, the same queryset gates (`learning_track=HYBRID`),
  and `_ensure_draft_tracking`; no new POST handlers — its forms POST the
  existing actions to `hybrid-builder`.
- **Adaptation:** those POST handlers currently `redirect("hybrid-builder")`.
  When the POST carries the workspace context (e.g. a `next` field), redirect
  back to `hybrid-programme-detail` instead — the one behavioural change to
  the view, preserving message semantics.
- **Interim option:** point Manage at the existing
  `builder_index?programme=<pk>` scoping (already tested) and ship Stage 2
  later; Stage 1 does not depend on it.

## 8. Authorization, CSRF, accessibility, responsive integration

- **Authorization:** unchanged; the page inherits `login_required` +
  `_require_instructor`. Students keep getting the login redirect / 403 as
  tested today. The workspace route gets the identical pair of decorators.
- **CSRF:** dialog and workspace forms carry `{% csrf_token %}` like every
  existing form; no exemptions.
- **Accessibility:** Django field groups provide label/helptext/errorlist;
  the dialog uses native `<dialog>` (focus trap, Esc) with
  `aria-labelledby`, `aria-invalid` and error lists as in the prototype;
  segmented filter buttons keep `aria-pressed`; the skeleton/empty/error
  regions get `aria-live` where the prototype has them.
- **Responsive/Unfold:** the real page inherits Unfold's sidebar/header
  behaviour; only the content column carries the prototype's responsive CSS
  (breakpoints ≈ 1024/68/40 rem as approved). Dark mode arrives through the
  shell's `html.dark` variables — the prototype CSS already maps them.

## 9. Conflicts between the approved prototype and existing behaviour

| Conflict | Resolution proposed |
| --- | --- |
| Prototype tiles count all editions ("· all editions") vs requirement to avoid double-counting | Adopt §6 definition; sub-label copy changes (D1) |
| Prototype has no retired-edition representation; the model and current template render retired editions | Show retired editions only in the workspace, muted (existing `--retired` styling); landing cards omit them (D4) |
| Prototype success/duplicate messages differ from the view's frozen copy | Keep existing view copy unless approved (D5) |
| Prototype filters/search run client-side; nothing server-side exists | Server-side GET params (D8), same visible behaviour |
| Prototype's state-preview banner, Reset and header theme toggle are review aids | Not shipped; the theme control stays in the user menu |
| Prototype code regex (lowercase + hyphens, no underscores) is stricter than `SlugField` | Keep as UI guidance; backend unchanged (D7) |
| Prototype cards expose only "Manage programme" while the view supports publish/new-draft/new-course POSTs | Keep the POSTs; they render in the workspace (D2) |

## 10. Proposed implementation stages

**Stage 1 — Landing page (drop-in, no URL or view-signature change).**
Rework `templates/hybrid/builder_index.html` into the approved layout; add
stats + per-edition counts + `?q=&status=` to `builder_index`; dialog with
error round-trip and no-JS fallback; new stylesheet built from the approved
prototype CSS; Manage programme → `builder_index?programme=` (interim) or
Stage 2 if already merged. Update the landing tests whose assertions reference
the old markup; add tests for stats, filter/search, dialog error re-render.

**Stage 2 — Programme workspace.** `programme_detail` view + template +
`hybrid-programme-detail` route; POST redirect-back adaptation; Manage
programme links to it; retired editions visible here. Tests: workspace access
control, edition actions from the workspace, redirect-back, forged-programme
protection still holding.

**Stage 3 — QA pass.** Screenshot parity against the approved prototype at
1440×900 / 1366×768 / 768×1024 / 390×844 in both themes; keyboard and
focus-visible pass; `prefers-reduced-motion`; N+1 sanity; full suite.

## 11. Risks

- **Copy lock:** the new template and any message wording changes need the
  approvals in D5; everything else reuses frozen copy verbatim.
- **Test churn:** `test_the_builder_lists_hybrid_programmes_and_their_editions`,
  `test_a_programme_post_does_not_validate_the_course_form` (error-count
  assertion), `test_a_selected_programme_is_carried_instead_of_asked_again`
  and the scoped-course tests reference current markup/flows — expect
  assertion updates, no behavioural weakening.
- **Multiple drafts** resolve via `.first()` exactly like
  `_ensure_draft_tracking`; document rather than "fix".
- **Stats definition** changes displayed numbers vs the approved screenshots
  once any programme has two editions (D1 sign-off).
- **Two templates rendering programmes** (landing + workspace) must share one
  context-building helper to avoid drift.
- Review-aid elements must not leak into the real template.

## 12. Test requirements and acceptance criteria

**Tests:** update the landing tests above; add —
stats definition (programme with published v1 + draft v2 counts once;
retired excluded); `?q=` matches name and code, `?status=draft/published`
incl. a programme holding both; dialog invalid POST returns 400 with both
required errors visible in the reopened dialog; duplicate code creates no
row; Manage programme navigation + permission denial; workspace publish /
new draft redirect back to the workspace; full `pytest -q` green.

**Acceptance criteria (by stage):**
1. Landing renders the approved layout in the Unfold shell at all four
   approved sizes in both themes; all four POST actions still work
   (`create_programme` invalid → 400 with dialog reopened; valid → 302 +
   message + card visible); search/filter behave as approved; suite green.
2. Manage programme opens the workspace showing the programme's editions and
   courses; publish/new-draft/new-course work from it and return to it;
   published editions stay read-only; suite green.
3. Screenshot parity with the approved prototype; no accessibility
   regressions (focus, labels, contrast unchanged); `manage.py check` and
   `makemigrations --check` clean; zero migrations added.

## 13. Decisions requiring approval

- **D1 — Stats definition:** draft-if-present-else-latest-published, retired
  excluded; tile sub-label copy changes accordingly.
- **D2 — Workspace:** new `hybrid-programme-detail` page (recommended) vs
  interim `builder_index?programme=` scoping.
- **D3 — Dialog errors:** server re-render + auto-opened dialog (no JSON
  endpoint, no-JS fallback kept).
- **D4 — Retired editions:** workspace-only, muted; omitted from landing cards.
- **D5 — Copy:** keep the existing view messages ("Programme created in a new
  draft edition v1.", Django's duplicate-code wording) or adopt the
  prototype's phrasings — your call under the copy lock.
- **D6 — Filter semantics:** a programme matches Draft/Published when *any*
  edition holds that status.
- **D7 — Code format guidance:** prototype's stricter lowercase-hyphen rule
  as UI help text only; `SlugField` unchanged.
- **D8 — Search/filter** server-side via GET params (shareable URLs).
