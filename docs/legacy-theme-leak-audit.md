# Legacy theme leak audit

Date: 14 October 2026  
Status: automated remediation applied 15 October 2026; re-swept 21 October 2026 — see the re-sweep section below for what closed and what remains open

## Remediation update — 15 October 2026

The approved source and deployment remediation has now been applied:

- rebuilt the verified `local_data/static_collected` directory with local-production settings;
- confirmed the manifest contains current hashes plus 26 Unfold assets;
- added `manage.py check_static_manifest` to reject missing, stale, or incomplete collected output;
- replaced the audited legacy accent literals in active CSS/templates with Unfold primary/base tokens;
- moved admin donut presentation colours out of Python and into semantic CSS classes;
- replaced purple HS-table striping with neutral base-surface tokens;
- made `theme.js` the sole theme-state controller and removed the duplicate writer from `app-shell.js`;
- moved both password-change pages into the shared Unfold shell; and
- added a regression test that rejects the known legacy literals and duplicate theme-state ownership.

Automated verification completed with 373 passing tests. A manual route-by-route screenshot and contrast review remains recommended before the next production deployment, particularly for simulator workflows in dark mode. The generated collected-static directory remains ignored build output and was not edited by hand.

## Re-sweep — 21 October 2026

Method for this pass: every class selector in `static/css/app.css` was tested for a full-token occurrence
across all 445 repository HTML/JS/Python files and all 1,472 installed Django/Unfold files, then against
every text column of a read-only copy of the development database (83 tables). Stored lesson prose cannot
hide a stylesheet hook: `learning/rich_text.py:24-30` allows no `class` attribute on any tag it keeps.

### Closed since the 15 October pass

| Finding | Outcome |
|---|---|
| Live legacy purple (`#5145cd` and its variants) | The seven remaining sites now consume `var(--color-primary-900, #2b2860)`, `var(--color-primary-50, #eef0fd)`, `var(--color-base-600, #475569)` or `color-mix(in srgb, var(--primary) N%, transparent)`. `tests/test_legacy_theme_guardrails.py:45` passes. |
| Guardrail blind spot | Three legacy colours had survived the 15 October hex sweep because they were written as `rgb()` triples, which a literal search cannot see. The guardrail now decodes every `rgb()`/`rgba()` triple in active theme sources and reports it as the forbidden hex, with file and line. |
| P3 font divergence | `static/css/app.css:11` is the only `:root` family declaration and consumes `var(--font-sans, …)`, matching `static/css/simulator-portal.css:14`. The competing `body { font-size: .9rem }` is gone, so the 14px body size is owned once at `app.css:20` and agrees with Unfold's own `text-sm`. Exactly two sans `font-family` declarations remain in application CSS, both on `var(--font-sans, …)`; the old `app.css` monospace rule left with the credential-card block, so the only deliberate monospace left is the simulated-document editor and the one-time-password field. |
| P2 `templates/base.html` | Deleted. It had no `{% extends %}`, no `template_name`, and both password pages had already moved to `core/base_student.html`. |
| Dead legacy CSS | 65 class hooks — 195 whole rules and 15 partial selector lists — removed from `app.css`, which went from 666 lines to 469. What left: the welcome banner, journey graphic, stats/role/badge blocks, the module-card sub-parts, the superseded `builder-*` / `outline-*` / `check-row` column layout, the lesson/panel/workflow blocks, the credential list, the auth panel/footnote blocks, `page-intro` / `section-heading` / `table-wrapper`, and `knowledge-check`. |
| Pre-Unfold shell CSS and its loader | Removed together in a second pass, `app.css` 469 → 322 lines: `.app-layout`, `.page-shell`, `.workspace-bar`, `.guest-layout`, `.brand-mark`, `.account-summary`, `.nav-search`, `.site-header`, `.top-nav`, `.brand`, `.user-avatar`, `.skip-link`, `.theme-menu`, `.theme-switch*`, `.sidebar-*`, `.navigation-*`, `.nav-group*`, `.breadcrumb-divider`, `.environment-badge`, `.training-notice`, `signout-form`. The first pass had scored these live only because `app-shell.js` mutates them; with `base.html` gone that script loads nowhere, so its references stopped counting. `static/js/app-shell.js` is deleted. `.ui-icon` survives the sheet because `templates/components/icon.html` renders it, so the four `.nav-search .ui-icon`-style descendant rules had to be tested per selector part, not per rule. |
| `static/js/app-shell.js` | Deleted. `tests/test_legacy_theme_guardrails.py:63` no longer reads it; the guard now scans every other file in `static/js/` and fails if anything but `theme.js` names `adminTheme` or `icums-theme`. |
| Off-palette lavender on the builder review cards | `.step-number` at `app.css:97` now reads `border: 1px solid var(--color-primary-100, #e0e3fb)` and `background: var(--color-primary-50, #eef0fd)`, matching its already-tokenised dark variant. Chrome computes `rgb(224,227,251)` / `rgb(238,240,253)` on `#4236b6` text in light mode and `rgb(56,48,147)` / `rgb(43,40,96)` on `#8a86de` in dark. |

### Still open, and why

| Finding | Extent | Why it waits |
|---|---|---|
| Parallel dark neutral palette `#172033`, `#2b3950`, `#aab4ca` | 89 sites | Each substitution needs a dark-mode contrast check, done per file rather than in one sweep. |
| Hard-coded palette hexes | 592 of 712 six-digit hexes in `static/css/*.css`; the other 120 are correct `var(--token, #hex)` fallbacks | Concentrated in `simulator-portal.css` (199), `cargo-page.css` (148), `dash.css` (67), `app.css` (63), `instructor-theory-builder.css` (40). Mechanical, but wants the same per-file review. |
| `tools/build_admin_content_guide.py:25` | `PURPLE = colors.HexColor("#5145CD")` | The last legacy purple in the repository. It colours a generated PDF rather than a page, and sits outside the guardrail's source roots. Left alone deliberately. |

### Corrections to the 14 October method

- `\b` word boundaries are unsafe for hyphenated class names: `\bsection-heading\b` matches inside
  `course-section-heading`, and `auth-story` matches inside `auth-story-footer`. An earlier pass of this
  re-sweep reported nine classes as live for exactly that reason — they occur only as segments of the
  prefixed names the app actually renders (`dash-module-icon`, `lrn-content-block`, `quiz-progress-track`).
- A name appearing in prose is not usage. `knowledge-check` was found inside a sentence at
  `templates/instructor_portal/module_edit.html:159` and in manual copy at `tools/build_admin_manual.py:159`;
  `auth-story` was found only in `tests/test_login_redesign.py:45`, which asserts its absence.
- Repo-only searches under-report nothing here but must not over-report: `errorlist` looks dead in the
  repository yet is rendered by `django/forms/utils.py`, so it stays.
- Searching whole file text over-reports usage badly. A name in a template comment or a Python docstring
  is not a hook: `.top-nav` looked live because `templates/core/base_simulator.html:11` says "the legacy
  simulator shell (purple gradient header, fixed sidebar, top-nav) is gone", and `.brand` looked live on
  nine prose hits. The second pass therefore treated only `class="…"` attribute values and JS class APIs
  (`classList.add/remove/toggle`, `querySelector('.x')`, `className =`) as usage, scanning the repository
  plus 392 Django and Unfold template/script files. That is what turned the surviving shell block up.
- A rule is dead when **any** class in a selector part is dead, not only when all of them are.
  `.nav-search .ui-icon` cannot match once `.nav-search` is rendered nowhere, even though `.ui-icon` is
  live on its own through `templates/components/icon.html`. Testing per-rule rather than per-part is what
  left those four rules behind on the first attempt at this block.
- Per-part testing needs an accurate selector splitter, and two bugs were caught by it rather than by
  reading the output: a depth counter that started at 0 drove the nesting negative and swallowed whole
  regions of the sheet (470 lines to 68), and rejoining a mixed selector list without its commas produced
  `html[data-theme="dark"] .panel` / `html[data-theme="dark"] .reading-panel` on consecutive lines, which
  parses as a single descendant selector. Both survived only because the tool refused to write.

### Verification

`manage.py check` reports no issues. `tests/` runs 581 passed, 0 failed. `app.css?v=` is bumped to
`20261021-2` at `templates/core/base_student.html:16`, which is the only template that loads `app.css`.

Both prunes were then checked against real rendered markup rather than source. Every URL resolvable
without arguments (179 pages) and then a second pass over 163 URLs including every single-argument
pattern filled from live primary keys were fetched through an in-process `Client` against a *copy* of the
development database (`local_data/db.scratchprune.sqlite3`, scratch settings module, both deleted
afterwards; the real DB was only ever read and its row counts are unchanged). Each response was searched
**inside `class="…"` attribute values only**, with a full-token delimiter match
(`(?<![A-Za-z0-9_-])name(?![A-Za-z0-9_-])`) — the same usage model used to classify the names, and the
reason the check is not fooled by a name appearing in prose. Result: **no removed class appears in any
rendered page.** `app.css` reaches 13 of the arg-free pages plus the practical builder and assessment
pages, and the pass confirms positively that those pages still render the hooks the sheet keeps —
`step-number`, `journey-panel` and `journey-step` on two `practical-edit` pages, `my-learning-group` on
13, and `app.css` linked on every assessment page fetched — so a clean result is not an artefact of never
reaching a styled page. Three blind spots were closed separately: the rich-text allow-list
(`learning/rich_text.py` permits no `class` attribute, so stored lesson prose cannot carry a stylesheet
hook), a read-only scan of all 83 database tables, and this end-to-end render.

The sheet was also parsed by a real CSS engine (headless Chrome, with Unfold's stylesheet in the same
document) and flattened to 168 selector contexts, which matched the file's own 168 non-at-rule selectors
one for one — nothing was silently dropped as a parse error. Computed styles were read for the component
whose colour changed: `.step-number` resolves to `rgb(224,227,251)` border on `rgb(238,240,253)` with
`rgb(66,54,182)` digits in light mode, and `rgb(56,48,147)` on `rgb(43,40,96)` with `rgb(138,134,222)`
under `html[data-theme="dark"]`, with `.panel` and `.eyebrow` still applying. What this still does **not**
prove is how every page looks: no page has been seen in a browser by eye, and the route-by-route
light/dark sweep remains open.

Restarting the local server is still required for the pruned sheet to appear. `start_local.py:36` runs
`collectstatic` on every start, so `local_data/static_collected` rebuilds itself and the stale manifest
needs no manual action; the reason it looks ignored is that `DEBUG = False` caches both templates and the
WhiteNoise manifest per process. The `?v=` bump is inert under manifest storage, which rewrites the URL
to a hashed name.

## Executive summary

The audit found real legacy-theme residue, but not every purple-looking value is a defect. The configured Django Unfold primary palette is itself indigo/purple (`config/settings/base.py:135-138`), with `primary-600` set to `#4236b6`. The safe objective is therefore not a blind hue replacement. It is to remove old, independently maintained palettes and make active components consume the existing Unfold/system tokens.

The highest-risk issue is the generated `local_data/static_collected` tree. Its manifest points at old, hashed CSS that predates the current source and appears to predate the Unfold static collection. Under `local_production.py` and `vps.py`, WhiteNoise serves this manifest, so a deployment that reuses this directory can display an old purple/teal simulator scheme even when source CSS is correct.

Active source also contains several independent accent systems:

- `static/css/app.css` still defines the old `#5145cd` accent and many hand-picked purple light/dark variants.
- `static/css/admin-dashboard.css` and `core/admin_dashboard.py` still use `#5145cd` directly.
- shared lesson, quiz, dashboard, and simulator CSS use off-palette dark accents such as `#9b8cff`, `#bdb3ff`, and `#3d3a7a` instead of Unfold variables.
- `static/css/cargo-page.css` has literal purple-tinted zebra striping (`rgba(120, 110, 220, ...)`).
- legacy shell selectors and a second theme controller remain in source even though the relevant pages now render inside Unfold.

No external font import or competing webfont was found. `Inter` matches Unfold's bundled font. The font concern is unnecessary global redeclaration/fallback divergence, not a different font family.

## How this audit was performed

Read-only searches covered:

- source CSS under `static/css` and `static/admin/css`;
- all templates, including inline styles and class names;
- JavaScript theme and shell controllers;
- Python settings and Python-generated chart colours;
- template-to-stylesheet relationships;
- the generated `local_data/static_collected` manifest and CSS;
- Git history for the palette migration intent.

Searches included named hues, hex/RGB/HSL literals, gradients, CSS variables, font declarations/imports, theme state keys, and legacy shell classes. Findings were then traced to the templates that load each file.

Repository history is useful evidence: commit `992844d` is titled `fix: dash accent token moved to the chrome primary — no old purple left` and explicitly describes `#5145cd` as the old accent and `#4236b6` as the current chrome `primary-600`. This audit uses that stated migration intent when separating old literals from the configured palette.

## System baseline and replacement rule

The only authoritative palette located in application configuration is:

- neutral/base scale: `config/settings/base.py:130-133`;
- primary scale: `config/settings/base.py:135-138`;
- current interactive primary: `--color-primary-600` / `#4236b6`;
- current dark/light surface and text variables: Unfold's `--color-base-*` and `--color-font-*-*` variables.

Conservative replacement rule for later work:

1. Where a page is rendered by Unfold, use Unfold variables or Unfold utility classes, not a copied hex value.
2. Use the semantic shade appropriate to the state (`primary-600` for a normal active control, another configured primary shade only where the existing Unfold component uses it).
3. Use base/text variables for neutral backgrounds, borders, and text. Do not turn every purple literal into `primary-600`.
4. Preserve semantic success, warning, and error colours.
5. Do not invent or alter the `UNFOLD["COLORS"]` palette during remediation.
6. Never edit `local_data/static_collected` by hand; rebuild it from approved source.

## Prioritised findings

### P0 — stale collected static can serve an entirely old theme

**Evidence**

| Location | Current value/evidence | Likely impact | Confidence |
|---|---|---|---|
| `config/settings/base.py:97` | `STATIC_ROOT = LOCAL_DATA_DIR / "static_collected"` | Establishes the generated directory used by collection. | High |
| `config/settings/local_production.py:11` | `CompressedManifestStaticFilesStorage` | Local production serves manifest-hashed files from the collected tree. | High |
| `config/settings/vps.py:28` | `CompressedManifestStaticFilesStorage` | VPS mode has the same exposure. | High |
| `local_data/static_collected/staticfiles.json:1` | maps `css/app.css` to `css/app.7054348625db.css` and `css/simulator-portal.css` to `css/simulator-portal.1cebd8154600.css`; no `unfold/` entries were found | A reused manifest can serve CSS from before the Unfold migration and omit current Unfold assets. | High |
| `local_data/static_collected/css/simulator-portal.css:9-11` and `.../simulator-portal.1cebd8154600.css:9-11` | `--primary: #5a3fc0`, `--primary-dark: #412a9a`, `--teal: #087f8c` | Old purple-to-teal simulator presentation can appear in production. | High |
| `local_data/static_collected/css/simulator-portal.css:40,97` and hashed equivalent `:40,97` | legacy primary/purple/teal gradients | Old gradient bands on simulator headers and dialogs. | High |
| `local_data/static_collected/css/app.css:8` and `.../app.7054348625db.css:8` | `--accent: #176b50` | This collected app CSS is also older than current source, proving the tree is mixed/stale rather than an authoritative snapshot. | High |

**Recommended later approach**

Treat `local_data/static_collected` as disposable output. In a controlled deployment step, preserve any operationally required copy, clear only the verified `STATIC_ROOT`, run `collectstatic`, confirm the manifest contains Unfold assets and current hashes, then smoke-test local-production/VPS mode with cache disabled. Do not “fix” individual generated CSS files.

### P1 — the legacy `app.css` accent still loads on Unfold student/instructor pages

`templates/core/base_student.html:16` loads `static/css/app.css` before the shared dash stylesheet. The file also loads through `templates/base.html:10`, which is still used by `templates/registration/password_change_form.html:1` and `password_change_done.html:1`.

**Exact legacy palette findings**

| Location | Literal/current value | Component/pages affected | Likely visual impact | Confidence |
|---|---|---|---|---|
| `static/css/app.css:8` | `--accent: #5145cd` | All selectors that consume `--accent`; especially classic password-change pages, plus any student/instructor content not overridden by `.dash` | Old purple links, buttons, progress, callouts, and focus treatment. | High |
| `static/css/app.css:145` | brand background `#5145cd`, shadow `#5145cd26` | legacy `templates/base.html` shell | Old purple brand tile/shadow. | High |
| `static/css/app.css:161` | avatar `#6b49b8` on `#ede7fa` | legacy authenticated shell | Separate purple avatar palette. | High |
| `static/css/app.css:175-176` | shadows `#5145cd1a/#5145cd30`; hover `#4236b6` | `.primary-button`, including change-password submit | Mixed old literal shadow and current primary hover. | High |
| `static/css/app.css:177` | `#bbb3ee` on `#f8f7ff` | secondary-button hover | Pale purple hover unrelated to base tokens. | High |
| `static/css/app.css:183` | focus shadow `#5145cd17` | form fields | Old purple focus ring tint. | High |
| `static/css/app.css:202` | shadow `#5145cd18` | journey illustration | Subtle purple glow. | Medium |
| `static/css/app.css:238` | row hover `#faf9ff` | generic tables loaded under the student shell | Purple-tinted table hover can leak into unrelated tables. | High |
| `static/css/app.css:326-376` | dark accent `#9b8cff` plus `#27244c`, `#7468dc`, `#4b4485`, `#292650`, `#c2badf`, `#bdb3ff`, `#302b5e`, `#d5d0ff`, `#554c9a` | dark-mode app content and legacy password screens | A complete parallel dark-purple palette instead of Unfold dark tokens. | High |
| `static/css/app.css:391` | theme knob `#5b54d6` | legacy theme switch | Isolated non-system purple. | High |
| `static/css/app.css:445,449,493` | `#c7cdf7` hover borders | cards/account summary | This value is in the configured primary scale, but it is hard-coded and bypasses the system token. | Medium |

**Why this leaks despite the Unfold shell guards**

`templates/core/base_student.html:18-40` repairs a few global collisions (`body`, headings, links, header title, sidebar link colour), but it does not neutralise every unscoped rule in `app.css`. The file contains generic selectors for `body`, headings, links, buttons, inputs, tables, and named components. The comments at `static/css/dash.css:120-123` also acknowledge that shared dash rules “supersede the legacy app.css,” confirming both layers are active.

**Recommended later approach**

First decide whether the two password-change templates should join the Unfold shell. Then narrow `app.css` to any genuinely remaining classic surface or remove it from `base_student.html` after a page-by-page regression pass. For active Unfold pages, bridge component semantics to `--color-primary-*`, `--color-base-*`, and `--color-font-*`; do not merely replace `#5145cd` with another copied hex.

### P1 — admin overview retains the explicitly identified old accent

`templates/admin/index.html:12` loads `static/css/admin-dashboard.css`.

| Location | Literal/current value | Component/pages affected | Likely visual impact | Confidence |
|---|---|---|---|---|
| `static/css/admin-dashboard.css:12-13` | `--d-accent: #5145cd`; border `#c7cdf7` | admin overview cards, bars, icons, links, chart-adjacent content | Admin overview uses old accent while surrounding Unfold chrome uses primary-600. | High |
| `static/css/admin-dashboard.css:26-27` | dark `#9b8cff`; border `#4b4485` | admin overview in dark mode | Off-palette bright purple and border. | High |
| `core/admin_dashboard.py:38` | student donut segment `#5145cd` | “People by role” donut and legend in `templates/admin/index.html:37-54` | Old purple remains even if CSS tokens are corrected. | High |

**Recommended later approach**

Map the dashboard accent to Unfold primary variables in CSS. For the generated SVG segment, stop passing presentation hexes from Python if practical; pass a semantic class/key and colour it in CSS. If an inline SVG colour is unavoidable, derive it from the configured system palette in one place rather than duplicating the literal.

### P1 — active shared dark-mode accents are outside the configured primary scale

These files are active across the student, instructor, lesson, assessment, and simulator surfaces. The light primary `#4236b6` is the configured `primary-600` and is not itself evidence of an old scheme. The dark values below are not present in the configured Unfold palette.

| Location | Literal/current value | Component/pages affected | Likely visual impact | Confidence |
|---|---|---|---|---|
| `static/css/dash.css:6` | `--d-accent: #9b8cff` | nearly all `.dash` student/instructor content; file loaded at `base_student.html:43` and `base_simulator.html:17` | Dark-mode links, buttons, pills, icons, and progress use a separate purple. | High |
| `static/css/dash.css:156,171,186` | `#bdb3ff`, `#3d3a7a` | builder active tab/progress links/module hover | Visible purple differences within instructor builders. | High |
| `static/css/lesson.css:4` | `--d-accent: #9b8cff` | lesson reader | Dark lesson progress, navigation, and controls diverge from Unfold. | High |
| `static/css/quiz.css:3` | `--d-accent: #9b8cff` | assessment take/result pages | Dark assessment controls and score use the off-palette accent. | High |
| `static/css/instructor-portal.css:29` | text `#bdb3ff` | dark “View mode” badge | One-off light purple badge text. | High |
| `templates/core/base_simulator.html:46,48` | `#bdb3ff`; backgrounds `#1b1940/#262254`; underline `#8a86de` | practical top-menu hover/current state | Inline template styles maintain another dark palette outside component CSS. | High |

**Recommended later approach**

Use the same Unfold primary and base variables already available in the Unfold shell. Where a component needs a dark-mode text shade, use the configured primary shade used by the equivalent Unfold interaction rather than maintaining `#9b8cff/#bdb3ff`. Verify contrast after substitution.

### P1 — simulator stylesheet is a second theme system with legacy shell residue

`templates/core/base_simulator.html:18` loads `static/css/simulator-portal.css` on practical pages.

| Location | Literal/current value | Component/pages affected | Likely visual impact | Confidence |
|---|---|---|---|---|
| `static/css/simulator-portal.css:1-14` | local `--ink`, `--canvas`, `--panel`, `--line`, `--primary`, `--primary-dark`, misleading `--teal`; hard-coded font stack | every practical/simulator page | Creates a parallel theme contract instead of consuming Unfold tokens. | High |
| `static/css/simulator-portal.css:28-66` and `202-241` | duplicate/overriding `.portal-shell`, `.portal-sidebar`, `.portal-brand`, `.portal-header`, `.portal-top-nav` rules | legacy simulator shell; `.portal-header/.portal-top-nav` are explicitly hidden by `base_simulator.html:34` | Dead or mostly dead pre-Unfold shell rules increase cascade risk and can reactivate if markup changes. | High for residue; Medium for current visibility |
| `static/css/simulator-portal.css:58,116` | gradients using local primary/dark/“teal” variables | old portal header and active dialog headers | Dialog headers can still show a local purple gradient; old page header is hidden. | High |
| `static/css/simulator-portal.css:358-370` | full local dark theme; `--primary: #9b8cff`, `--primary-dark: #8373ed`, `--teal: #bdb3ff` | every practical page in dark mode | Practical content diverges from Unfold chrome. | High |
| `static/css/simulator-portal.css:377-420,443,499` | repeated `#bdb3ff`, `#3d3a7a`, `#1b1940`, `#262254`, `#8a86de` | active links, badges, dialogs, quick actions, date buttons, plus dead shell controls | Purple leakage is spread across many component states. | High |
| `static/css/simulator-portal.css:438-453` | dark form text/background `#eef0fd/#262254` | all practical form controls | Direct primary-family colours are used as generic surfaces/text. | High |

**Recommended later approach**

Separate active practical-content styles from obsolete shell styles, remove dead shell selectors only after a rendered-page sweep, and translate the active local variables to aliases of Unfold system variables. Keep component-specific layout; retire the independent colour and font contract.

### P1 — literal purple table striping remains in the consignment workflow

| Location | Literal/current value | Component/pages affected | Likely visual impact | Confidence |
|---|---|---|---|---|
| `static/css/cargo-page.css:310` | `rgba(120, 110, 220, .05)` | alternating rows in `.app-hs-table` on consignment application flows | Subtle purple zebra band in light mode. | High |
| `static/css/cargo-page.css:312` | `rgba(120, 110, 220, .1)` | same table in dark mode | More visible purple zebra band. | High |
| `static/css/cargo-page.css:214` | `#bdb3ff` | dark clearance menu links | Off-palette purple text. | High |

The stylesheet is loaded by many practical templates, including `templates/scenarios/consignment_application.html:5`; the striped selector is specifically tied to the HS-code table used on that workflow.

**Recommended later approach**

Use a base surface/row-hover system token for zebra striping, not a primary hue. Use a system primary text token only for truly interactive link emphasis.

### P2 — system-palette literals are copied instead of referenced

The following are not necessarily visually wrong today because their values appear in `UNFOLD["COLORS"]`, but they are drift risks and make later theme changes leak unevenly:

- `static/css/simulator-portal.css`: repeated `#4236b6`, `#383093`, `#eef0fd`, `#c7cdf7`, `#8a86de`, `#2b2860`, and `#1b1940` throughout lines `10-12`, `25`, `32-53`, `86-116`, `198-259`, `355-381`, and `438-507`.
- `static/css/dash.css:4,60,112,116,137,139,147,154-159,166,185`.
- `static/css/lesson.css:3` and `static/css/quiz.css:2`.
- `static/css/instructor-portal.css:28`.
- `static/css/ucr-create.css:101-106,123-135`.
- `templates/core/base_simulator.html:45-48`.

**Recommended later approach**

Replace copies with system variables in Unfold-rendered pages. This is a maintainability pass after the confirmed old palette and stale collected output are addressed; it should not be mixed with a palette redesign.

### P2 — duplicate legacy theme controller and dead shell branches remain

| Location | Current behaviour | Likely impact | Confidence |
|---|---|---|---|
| `static/js/theme.js:8-9,62-75` | canonical controller reads `adminTheme` and migrates legacy `icums-theme` | Migration compatibility is intentional; not itself a colour leak. | High |
| `static/js/app-shell.js:3-6,89-96` | a second controller reads/writes `icums-theme`; guarded by `window.ICUMSThemeReady` | `theme.js` never sets `window.ICUMSThemeReady`, so classic pages can attach two theme-toggle handlers and maintain two conventions. | High |
| `static/js/app-shell.js:9,17-45,111-152` | searches for `.portal-sidebar` and mutates legacy portal brand/sidebar/header | No current template contains `.portal-sidebar`; these are dead pre-Unfold branches. | High |
| `templates/base.html:13-71` | retains the complete `.app-layout/.site-header/.top-nav` pre-Unfold shell | Currently reached by password-change templates; retains old theme surface and navigation model. | High |

**Recommended later approach**

After the password-change shell decision, converge on one theme controller and remove only demonstrably dead legacy portal branches. Preserve the `icums-theme` read/migration path long enough to carry existing user preference into `adminTheme`.

### P3 — font audit: no competing font, but global declarations bypass inheritance

| Location | Declaration | Assessment | Confidence |
|---|---|---|---|
| `static/css/app.css:11,131` | `Inter, ["Segoe UI"], system-ui, sans-serif` | Same leading family as Unfold, but global `:root/body` declarations bypass `var(--font-sans)` and have different fallback order. | High |
| `static/css/simulator-portal.css:14` | `Inter, "Segoe UI", system-ui, sans-serif` | Same issue on practical pages. | High |
| `static/css/app.css:433` | `ui-monospace, SFMono-Regular, Consolas, monospace` | Appropriate semantic monospace for credentials/code. Exclude. | High |
| `templates/instructor_portal/credential_reveal.html:17` | `font-family: monospace` | Appropriate for a one-time password. Exclude. | High |
| `static/admin/css/bl-editor.css:4` | `"Courier New"` and `Arial` | Deliberate simulated document-template typography/watermark, not application chrome. Exclude unless document fidelity requirements change. | High |

Unfold bundles Inter locally; no Google Fonts import, remote font import, or alternate product font was found.

**Recommended later approach**

On Unfold-rendered surfaces, inherit Unfold's font or use `var(--font-sans)`. Keep semantic monospace and simulated-document fonts scoped to their content.

## False positives and exclusions

- `config/settings/base.py:135-138` is the approved system primary palette. Those values are not legacy merely because they look indigo/purple.
- `#4236b6` is current `primary-600` according to configuration and repository migration history. A hard-coded occurrence is a tokenisation concern, not proof of the old theme.
- Status colours (red error, green success, amber warning), Ghana/ICUMS document colours, focus-yellow accessibility outlines, and neutral slate colours were not classified as purple leakage.
- `static/admin/css/bl-editor.css` and `commercial-document-editor.css` intentionally simulate document layouts. Their specialised colours/fonts should not be normalised to application chrome without a separate fidelity review.
- The word “purple” in comments such as `static/css/ucr-create.css:121` and `templates/core/base_simulator.html:11` is descriptive evidence, not a rendered colour.
- Unfold's installed/vendor CSS and fonts are upstream system assets, not application leakage.
- Binary favicons, PNGs, DOCX files, and PDFs were not colour-sampled. They are not CSS/theme sources; a separate brand-asset visual review would be needed if they are in scope.
- `local_data/static_collected` is generated output and appears stale. It is evidence and a deployment risk, not a source-edit target.

## Staged remediation checklist for later

No item below should be performed without explicit approval because theme, styling, templates, theme scripts, and user-facing copy are locked.

### Stage 0 — capture and verify

- [ ] Record screenshots of light and dark modes for admin overview, student dashboard, one lesson, one quiz, instructor builder, simulator portal, consignment HS table, UCR form, and both password-change pages.
- [ ] Confirm which deployment mode is currently used and whether it serves `local_data/static_collected`.
- [ ] Confirm the intended Unfold primary/system tokens; do not change `UNFOLD["COLORS"]`.

### Stage 1 — deployment/static hygiene

- [ ] Rebuild `STATIC_ROOT` from source with the configured environment.
- [ ] Confirm `staticfiles.json` includes Unfold CSS/fonts/scripts and current application hashes.
- [ ] Verify WhiteNoise serves the new hashes in local-production/VPS mode.
- [ ] Purge or invalidate upstream/browser caches only as required by the deployment.

### Stage 2 — eliminate the explicitly old accent

- [ ] Replace the active `#5145cd` accent contract in `app.css` with system-token consumption or remove `app.css` from Unfold pages after regression testing.
- [ ] Move `admin-dashboard.css` from `#5145cd/#9b8cff` to Unfold variables.
- [ ] Remove presentation colours from `core/admin_dashboard.py` or centralise their source.
- [ ] Retest charts, buttons, links, focus states, and both themes.

### Stage 3 — align active dark-mode components

- [ ] Replace `#9b8cff`, `#bdb3ff`, `#3d3a7a`, and related hand-picked purple surfaces in `dash.css`, `lesson.css`, `quiz.css`, `instructor-portal.css`, `simulator-portal.css`, `cargo-page.css`, and `base_simulator.html` with the equivalent system tokens.
- [ ] Replace the HS-table purple zebra stripe with a neutral base surface token.
- [ ] Run contrast checks for every interactive state after token substitution.

### Stage 4 — retire old shells and duplicated theme logic

- [ ] Decide whether password-change pages move to the shared Unfold shell.
- [ ] Remove only verified-dead portal shell CSS/JS branches.
- [ ] Consolidate theme state handling while retaining a one-way migration from `icums-theme` to `adminTheme`.
- [ ] Stop global `app.css`/simulator element rules from reaching Unfold chrome.

### Stage 5 — verification and guardrails

- [ ] Perform a route-level visual sweep in light, dark, and system modes.
- [ ] Test authenticated roles separately: student, instructor, superuser, and simulator-review mode.
- [ ] Add a read-only lint/check that rejects the known old literals (`#5145cd`, `#5a3fc0`, `#412a9a`, `#9b8cff`, `#bdb3ff`, and `rgba(120, 110, 220, ...)`) outside documented exceptions.
- [ ] Add a deployment check that fails if the collected manifest lacks Unfold assets or does not match current source.
- [ ] Keep semantic status colours and document-preview styling on an explicit allow-list.

## Suggested review order

1. Static collection/deployment correctness.
2. `admin-dashboard.css` and Python donut colours (small, isolated surface).
3. Password-change/`templates/base.html` shell decision.
4. Shared `dash.css`, lesson, and quiz dark tokens.
5. Simulator/practical stylesheet decomposition.
6. Cargo/UCR detail tokenisation and final visual sweep.

This order reduces the chance of “fixing” source while a stale manifest continues to serve an older theme, and it avoids broad changes to the locked visual system before the remaining legacy surfaces are clearly bounded.
