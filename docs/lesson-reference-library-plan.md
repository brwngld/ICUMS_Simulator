# Cross-programme lesson references and the shared learning library

**Feasibility audit and implementation plan — 2026-11-02**

Status: **proposal only.** No source code, migration, template, stylesheet, or database record has been
changed for this feature. Nothing is committed or pushed. Implementation begins only after the decisions
in §10 are approved.

Answers the brief "ICUMS Simulator — Cross-Programme Learning References and Shared Learning Library",
deliverables §10.1–10.8. Out of scope per the brief and unchanged by this plan: student self-enrolment
(§7) and course-level assessments (§8, recorded in §11).

---

## 1. Verdict

**Feasible, and cheaper than the brief assumes: no new models, no migrations, no lesson duplication.**
The whole feature reduces to one architectural decision — **a reference is a separate read-only view over
the same `Lesson` / `ContentBlock` rows, and that view never resolves an enrolment.** Every isolation
requirement in the brief follows from that one choice, rather than from a list of guards.

Three facts make it cheaper than first estimated:

1. **A read-only, enrolment-free lesson renderer already exists.** The instructor preview
   (`lesson_preview`, `instructor_portal/views.py:1360-1413`) renders the student template
   `learning/lesson.html` from a shared enrolment-free helper (`_lesson_section_context`,
   `instructor_portal/views.py:1306-1355`), is `@require_GET`, and creates no progress rows. Its
   zero-side-effects contract is already tested
   (`tests/test_course_authoring_preview.py:118-148`). The reference reader is a third entrance
   to the same rendering idea, not a new renderer from scratch.
2. **The stable reference identifier already exists.** Every `Lesson` has a UUID primary key
   (`learning/models.py:84`), and a UUID-keyed preview route already proves the pattern
   (`instructor_portal/urls.py:45`). `/library/lesson/<uuid>/` survives slug renames, title edits,
   and module renumbering. No new identifier field.
3. **The authoring mechanism already works end to end.** The section editor's Link button accepts
   root-relative paths (`static/js/rich-text-editor.js:20` — `SAFE_URL` allows `/`, `./`, `../`),
   and the nh3 sanitizer passes scheme-less relative URLs through untouched (its `url_relative`
   default is `pass-through`; empirically proven by the surviving `/media/...` image fixture in
   `tests/test_rich_text_lesson_content.py:78-84`). A reference is an ordinary link in a block body.

The build is therefore: **one eligibility function, two views (reader + library), one or two templates,
and tests.** No `LessonReference` model, no `Resource` changes, no curriculum changes.

**The one prerequisite nobody can code around:** nothing is referenceable today. No `ProgrammeVersion`
in the dev database is `published` (§12), so Flows A and D are untestable until at least one programme
version is published — that is the sequencing fact that makes publishing Logistics v1 the first real
milestone.

---

## 2. Current-state findings (brief §4, the ten audit areas)

All findings verified against the working tree, 2026-11-02. All learning routes are mounted at
`/theory/` (`config/urls.py:40`).

### 2.1 Programme, course, module, lesson and publication models

- Hierarchy as the brief assumes: `Programme → ProgrammeVersion → Course → Module → Lesson`
  (`learning/models.py:10,46,83`; `onboarding/models.py`). Course, Module and Lesson all carry UUID
  PKs (`learning/models.py:17,47,84`).
- Publication states: `ProgrammeVersion.Status` = draft/published/retired
  (`onboarding/models.py:93-97`); `is_published` booleans on Course (:32), Module (:67), Lesson (:92).
  `retired` is already in use (xladder, experience-demo-a1, both GSA versions). There is **no
  lesson-level retired flag** — retiring one lesson means unpublishing it.
- `Programme.is_active` exists (`onboarding/models.py:32`) but is consumed **nowhere** at runtime —
  only in the admin (`onboarding/admin.py:11`) and the seed command. The eligibility rule in §4
  would be its first real consumer.
- Practical content is a separate table (`HybridLesson`, 3 rows) from theory `Lesson` (93 rows)
  (`hybrid/models.py:115`). Reference mode over `learning.Lesson` therefore excludes practicals by
  construction, not by filtering.
- **Hole worth closing:** `Module.course` is nullable (`learning/models.py:49-56`), and
  `module_is_available` returns True for such a module (`learning/services.py:228-233`) — today it is
  simply unreachable to students; in a library query it would surface. The eligibility rule must
  require a published course.

### 2.2 Student enrolment and programme-selection mechanisms

- `enrolment_for_request` resolves `?programme=<code>` or falls back to the oldest active theory-track
  enrolment and raises `PermissionDenied` when none exists (`onboarding/services.py:55-63`).
- `active_enrolments` filters `Enrolment.Status.ACTIVE` (`onboarding/services.py:24-37`);
  multi-enrolment selection is covered by `tests/test_multi_enrolment.py` (20 tests).
- Lesson URLs carry `?programme=<code>` via `programme_href` for multi-enrolment learners
  (`onboarding/services.py:66-78`). The reference route is keyed by UUID and needs none of this —
  which is precisely why a normal lesson URL must not be reused as the reference URL (brief §4).

### 2.3 Lesson-detail routing and enrolment resolution

- Routes: `lesson-detail` / `lesson-section` / `lesson-part`, all slug-based and all pointing at one
  view (`learning/urls.py:9-11`).
- `lesson_detail` (`learning/views.py:510-702`): `@login_required`, then the gate chain —
  onboarding disclaimer guard (:523), `enrolment_for_request` (:525), published module in the
  *enrolment's* programme version (:526), prerequisite unlocked (:527-528), difficulty level reached
  (:529-530), published lesson (:531).
- **Writes on a plain GET:** `LessonProgress.objects.get_or_create` (:532) and
  `ModuleProgress.objects.get_or_create(..., status=IN_PROGRESS)` (:533); reading a paged part also
  saves `progress.last_part` (:650-654). POST handles practice answers (`LessonCheckResponse`,
  :593-613) and section completion (`action=continue`, :620-640, which stamps `completed_at`).
- Consequence: a normal lesson-detail URL **cannot** serve as a reference URL — opening it writes
  progress rows before any content renders.

### 2.4 Difficulty-ladder and prerequisite enforcement

- `module_is_unlocked` demands completed `ModuleProgress` *on the same enrolment*
  (`learning/services.py:22-29`) — a cross-programme prerequisite permanently locks the module.
  **A reference link is the right tool; a prerequisite is the wrong one.** (This function has no
  direct test today; the prerequisite field is exercised only by the authoring cycle guard,
  `tests/test_course_authoring_edit.py:147-158`.)
- `module_is_locked` / `course_is_available` enforce the difficulty ladder
  (`learning/services.py:236-241`, `:213-225`). The reference reader skips the entire ladder by never
  resolving an enrolment — reference reading is educational access, not progression.

### 2.5 Lesson rendering, content blocks and media

- Block kinds are exactly `text` / `example` / `notice` (`learning/models.py:103-106`) — there are no
  image, video or attachment block kinds. Bodies are sanitized at save time (`ContentBlock.save`,
  `learning/models.py:118-120`) and again at render (`rich_content` filter,
  `learning/templatetags/rich_text…:9-12`).
- **Video/embeds are impossible today:** the sanitizer strips `iframe/script/object/embed/svg` with
  their contents (`learning/rich_text.py:33,61`). Lesson media means uploaded images
  (`/media/lesson_rich_text/...`, site-absolute URLs) plus sidebar `Resource` external links.
- **Security note (pre-existing, not created by this feature):** `lesson_rich_text/` is listed in
  `PUBLIC_MEDIA_PREFIXES` and served without authentication (`core/views.py:201,218-222`), even
  though `learning/rich_text_images.py:4-6` claims the opposite — that docstring is stale. Reference
  readers see lesson images regardless of the reader page's own auth posture; flagged for the
  deferred security review, not silently inherited.
- Interactive content = practice knowledge checks only, rendered as POST forms
  (`templates/learning/lesson.html:133-150`). The read-only contract must ensure these never render
  as functional on a reference page (§6, R2).
- Section presentation diverges between the two existing renderers: the student route always shows a
  fixed five-section journey with progress states (`learning/views.py:82-89`); the instructor preview
  builds a content-driven list (`instructor_portal/views.py:1327-1339`). Which shape reference mode
  uses is a visible design decision (D1, prototype).

### 2.6 Rich-text link handling and sanitization

- Editor: Link button uses a prompt validated against
  `SAFE_URL = /^(https?:|mailto:|\/|\.\/|\.\.\/|#)/i` (`static/js/rich-text-editor.js:20,617-636`),
  so an instructor can already type `/library/lesson/<uuid>/`. No `target`/`rel` is set client-side,
  and anything outside `A: ["href","title"]` is stripped on round-trip (:13-19,44-49).
- Sanitizer (`learning/rich_text.py`): tags/attrs allowlist (:17-30), schemes http/https/mailto (:31),
  `link_rel="noopener noreferrer"` auto-added (:64). nh3 0.3.7 is called without `url_relative`, whose
  default passes scheme-less relative URLs through — **relative reference hrefs survive**, confirmed
  by existing tests (`tests/test_rich_text_lesson_content.py:78-96`; `javascript:`/`data:` are
  stripped).
- Consequence: because `target` never survives sanitization, reference links open in the same tab and
  the student returns with the browser back button — exactly Flow A's "returns to the original
  Customs lesson" (D8: accept this, it is the current behaviour of every in-lesson link).

### 2.7 Existing resource/remediation links

- `Resource` (`learning/models.py:138-146`) is a shared external-document library: `URLField`
  validates absolute URLs only (relative paths rejected at form/admin validation — tested), M2M
  `lessons` exposed only via Django admin `filter_horizontal` (`learning/admin.py:46-49`), no
  instructor-portal CRUD. Course-copy shares Resource rows across editions
  (`instructor_portal/views.py:834-836`). `QuestionVersion.remediation_resource` points at it
  (seed usage). The dev DB holds **0 Resource rows and 0 M2M rows** — no behaviour to preserve.
- Student-facing rendering is sidebar links with `target="_blank" rel="noopener"`
  (`templates/learning/module_overview.html:47`, `roadmap.html:101-103`).
- Verdict: keep Resource for *external* documents and remediation links. Internal cross-references
  use the reference route, because `URLField` would force full `https://<host>/...` strings that
  break at the VPS cutover.

### 2.8 Instructor authoring interfaces

- Theory block bodies: `lesson_edit` (`instructor_portal/views.py:1605-1642`, draft editions only)
  with the rich editor wired per block (`templates/instructor_portal/lesson_edit.html:23,31`).
- Hybrid theory body: `hybrid` lesson editor saves a single sanitized `theory` field
  (`hybrid/instructor_views.py:939-962`, `hybrid/models.py:147`) — separate surface; reference mode
  does not read it.
- Django admin edits bodies as raw textareas (no rich editor loaded); sanitization still applies on
  save.
- **No permalink/copy-link UI exists anywhere.** Instructors see Preview links (UUID-keyed,
  instructor-only). Discovering the `/library/lesson/<uuid>/` URL to paste into another lesson is an
  authoring-ergonomics gap addressed as optional Stage 3 (§8).

### 2.9 Student dashboard and navigation (the chrome)

- Every student page renders through `render_student_page` (`core/admin_dashboard.py:599-634`),
  which builds the Unfold sidebar from `_student_navigation` (:241-354). That sidebar **reads** the
  viewer's own enrolment (fallback when `request.page_enrolment` is unset, :255) and their
  `ModuleProgress` for lock states; the global `role_context` processor also queries the user's
  enrolments on every authenticated request (`accounts/context_processors.py:6,11-15`).
- `request.page_enrolment` has exactly two setters, both in the practical app
  (`scenarios/views.py:2957,3020`), and one reader — the sidebar. Nothing in `learning/` sets it, and
  when absent the sidebar degrades gracefully to the viewer's own enrolment (or inert `#` links for a
  viewer with none). **The reference page therefore shows the student their own programme's
  navigation, never the referenced programme's** — the misleading-chrome risk is resolved by default.
  The reader must simply *not set* `page_enrolment`.
- Breadcrumbs are derived from the URL name (`core/admin_dashboard.py:586-596`); lesson routes map to
  a trail into the enrolled programme (:493-494, :401-410). **A new URL name gets an empty breadcrumb
  trail** — graceful, and arguably correct for context-free reading.
- Reading minutes and progress percentages are computed values, derivable without enrolment
  (`learning/views.py:663,698`; `learning/services.py:252-261`). The preview's trick of passing an
  *unsaved* `LessonProgress(lesson=lesson)` instance satisfies the template's `progress.completed_at`
  reads without any DB write (`instructor_portal/views.py:1410`).

### 2.10 Permissions, audit logging and tests

- Student surfaces are `@login_required` throughout; the 403 convention is redirect-with-message
  (`tests/test_portal_403_redirect.py`). There is no read-audit logging on lesson views today;
  reference reads inherit that (D12).
- The no-side-effects test idiom already exists: assert zero rows across
  `LessonProgress, ModuleProgress, ProgrammeProgress, TheoryAttempt, ScenarioAttempt,
  PracticalEvaluation, CompletionRecord, Certificate` after exercising the route
  (`tests/test_course_authoring_preview.py:118-138`), plus POST → 405 + zero `LessonProgress`
  (:142-148) and anonymous → login redirect (:163-177).
- Relevant gaps: no combined eligibility function exists anywhere (the checks are scattered —
  §2.1/2.3/2.4); `Programme.is_active` unconsumed; retired-version learner behaviour untested
  (`tests/test_course_retire.py` covers instructors only); no learner-facing search tests; no
  reference/library anything (grep-verified absent).
- Conventions for the new suites: pytest + pytest-django, function-based, per-file fixtures or plain
  builder helpers (best theory-side examples: `tests/test_course_hierarchy.py:39-146`,
  `tests/test_theory_flow.py:24-43`), no conftest.py. Suggested files:
  `tests/test_reference_reader.py`, `tests/test_lesson_library.py`.

---

## 3. Gap analysis

| Capability | Today | Needs | New work |
|---|---|---|---|
| Stable reference identifier | Lesson UUID PKs; UUID preview route precedent | UUID-based reference route | Route + view only |
| Read-only lesson renderer | Instructor preview (GET-only, zero rows, tested) | Student-facing entrance with approved design | New view + template decision (D1) |
| Eligibility policy | Scattered publish checks; `module_is_available` returns True for courseless modules | One function, one place for the paywall hook | One queryset/predicate |
| Cross-lesson links in bodies | Editor accepts `/`-paths; sanitizer passes relative hrefs | Nothing mechanical; instructor pastes the URL | Optional picker/permalink (Stage 3) |
| Library browse/search | Absent (no `/library/` route, no icontains search over lessons) | One view + template; `icontains` v1, `SearchVector` after PostgreSQL cutover | One view + template + tests |
| Flow C safe message | 404/403 handling exists; no reference-specific copy | Eligibility-driven refusal with approved copy | Template + copy approval (D5) |
| Enrolled-student reference read (Flow D) | Their normal path writes progress | Reference mode never touches their rows | Same reader view; test |
| Chrome neutrality | Sidebar degrades to viewer's own enrolment; new URL name → no breadcrumbs | Do not set `page_enrolment` | Discipline + test |
| Progression isolation | `lesson_detail` writes on GET | Reference view is `@require_GET`, enrolment-free, no progress/assessment writes | The core new view |
| Instructor permalink discovery | No copy-link UI | Optional editor affordance | Stage 3, needs design approval |
| Retired/unpublished handling | `status`/`is_published` fields; retired keeps enrolled learners' access (`tests/test_course_retire.py`) | Eligibility excludes retired; Flow C copy | Policy decision (D5) |

---

## 4. Recommended data and permission architecture

### 4.1 No new models

References are ordinary sanitized links in block bodies; identity is the existing UUID PK. A
`LessonReference` table is deferred until a real question needs it ("what links to lesson X?", broken-link
reports). Until then, broken references are discovered at click time and answered by the Flow C
message — acceptable at v1 scale (60 lessons, 1,004 blocks in the largest programme).

### 4.2 The eligibility rule (single source of truth)

```
referenceable(lesson) =
    lesson.is_published
    and lesson.module.is_published
    and lesson.module.course is not None and course.is_published
    and lesson.module.programme_version.status == "published"
    and lesson.module.programme_version.programme.is_active
```

One function (a queryset for the library, a predicate for the reader), one place to add the paywall
condition when money arrives. Published-everywhere-by-default is the correct v1: programmes are free
today, and publishing *is* already the instructor's consent decision. Per-lesson opt-in would add a
field and a workflow for no current need (D3).

Rules this deliberately encodes:

- **Retired or unpublished at any level ⇒ not referenceable.** Note the deliberate asymmetry with
  course retirement, where enrolled learners keep access (`tests/test_course_retire.py`): enrolled
  learners keep what they were promised; reference readers, who never enrolled, lose access when the
  source programme is retired (D5).
- **Courseless modules are never referenceable**, closing the `module_is_available` hole (§2.1).
- **Theory only, by construction**: the route resolves `learning.Lesson`; hybrid practicals live in a
  different table with a different route and cannot be granted through it.

### 4.3 Access policy

- **Authenticated by default** (`@login_required` on both reader and library). Anonymous access would
  hand the whole library to scrapers and cost the training-environment framing that
  `docs/product-rules.md:3-9` requires; the honest caveat is that lesson *images* are already public
  under `/media/lesson_rich_text/` (§2.5) — authentication of the pages is a meaningful but partial
  boundary either way (D4).
- **Read-only contract enforced in the view, not the template**: `@require_GET` (so form POSTs that
  follow the rendering URL get a 405, closing the template-forms-not-disarmed gap seen in preview
  mode, `templates/learning/lesson.html:133-150,185-190`), no enrolment resolution, no writes to any
  progress/assessment model, no `request.page_enrolment`, no messages on GET.
- **Search** is `icontains` across `Lesson.title/summary/objectives/key_terms` and
  `ContentBlock.heading/body`, filtered by programme/course; full-text `SearchVector` is deferred to
  the PostgreSQL cutover (v1 corpus: ≤1,100 blocks — honest and fast enough).

### 4.4 Reference architecture vs. the brief's §5 questions

| Brief question | Answer |
|---|---|
| Dedicated read-only route? | Yes — the core decision (§1). |
| Stable internal identifier? | Already exists (UUID PK); no new field. |
| Instructor reference picker? | Deferred (Stage 3, optional): pasting `/library/lesson/<uuid>/` works today; a picker is ergonomics, not architecture. |
| Shared library with search/filters? | Yes — one view, §4.3. |
| Reference-access eligibility policy? | §4.2, one function, paywall hook inside it. |
| Handling unpublished/archived/deleted/revised sources? | Eligibility refuses at read time; Flow C message; revision tracking out of scope (attempts retain content versions per `docs/product-rules.md:91`, but lesson content itself is edited in place — noting it, not solving it). |
| New models/migrations? | None. |

---

## 5. Proposed routes and UI entry points

Project-level mount (not under `/theory/`, which means *enrolled* theory):

```python
path("library/", include("learning.urls_library")),   # or inline in config/urls.py

# learning.urls_library
path("", views.lesson_library, name="lesson-library"),
path("lesson/<uuid:lesson_id>/", views.lesson_reference, name="lesson-reference"),
```

Entry points: (1) in-body reference links authored by instructors; (2) the library page. Where the
library is linked from the student chrome (sidebar item vs roadmap link) is new user-facing copy and
navigation → design approval (D2). The reader renders through the existing student chrome
(`render_student_page`) for theme consistency, sets no `page_enrolment`, and shows a small
source-attribution strip ("Read from: Programme › Course › Module") instead of enrolled-course
breadcrumbs — copy belongs to the D1 prototype.

Instructor surfaces change nothing in Stage 1–2; optional Stage 3 adds permalink discovery
(`lesson_edit` copy-link) and possibly a picker dialog.

---

## 6. Security and progression-isolation risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | Accidental reuse of `lesson_detail` re-introduces GET writes | Separate view, `@require_GET`, tests asserting zero rows (idiom of `tests/test_course_authoring_preview.py:118-138`) |
| R2 | `learning/lesson.html` renders POST forms that follow the rendering URL — a reader URL would silently receive them | `@require_GET` → 405; prototype decides between a `reference_mode` template variant that hides forms and a dedicated template (D1) |
| R3 | Draft/unpublished leakage through search or library | The single eligibility queryset is the only content source for both pages; tested with draft programmes |
| R4 | Courseless modules surfacing in the library | Eligibility requires `course is not None and course.is_published` |
| R5 | Foreign programme appearing in chrome / misleading the student | Reader never sets `page_enrolment`; sidebar falls back to the viewer's own enrolment (`core/admin_dashboard.py:255`); breadcrumbs empty for the new URL name |
| R6 | Lesson images already public under `/media/lesson_rich_text/` (`core/views.py:201`) | Pre-existing exposure, flagged to the deferred security review; not widened by this feature |
| R7 | UUID enumeration | UUID PKs are unguessable; authenticated default (D4) further reduces |
| R8 | Injection via authored links | Sanitizer allowlist (http/https/mailto schemes; `javascript:`/`data:` stripped; `rel="noopener noreferrer"` auto-added) — already tested |
| R9 | Assessment side effects through knowledge checks | Reader renders no functional answer forms; any POST → 405; `LessonCheckResponse` untouched (tested) |
| R10 | No read-audit trail for reference reads (none exists for normal lessons either) | Accept for v1; revisit if the library becomes paywalled (D12) |

---

## 7. Flow walkthroughs (brief §6)

**Flow A — Cross-programme reference.** Student reads a Customs lesson containing
`<a href="/library/lesson/<uuid>/">What is a packing list?</a>`. Click opens the reference reader
(same tab — sanitizer strips `target`, §2.6); the page renders the Logistics lesson with no enrolment
resolution and zero progress writes; browser-back returns to the Customs lesson, whose own progress
is untouched (their rows were written when they originally opened it via `/theory/`). Prerequisite:
both programmes published. Today `referenceable()` matches **zero lessons** (§12) — Flow A is
untestable until publishing.

**Flow B — Shared learning library.** Student opens `/library/`, types "packing list", filters by
programme/course; results are eligibility-filtered published lessons only; opening one is Flow A's
reader.

**Flow C — Restricted reference.** The source lesson is later unpublished, its module/course
unpublished, or its programme version retired. The reference URL now refuses via the same eligibility
predicate and renders the safe message ("this reference is no longer available") — no content, no
existence leak beyond the UUID's presence. Copy requires approval (D5).

**Flow D — Enrolled student.** A student enrolled in the referenced programme opens the reference URL:
the reader still renders reference mode and writes nothing — their normal completion path remains
`/theory/<module>/<lesson>/`. The reader does not silently swap to the enrolled view (predictability;
D9). A later, optional "continue this lesson in my programme" link can be added with approved copy.

---

## 8. Incremental implementation plan with approval checkpoints

**Stage 0 — Approvals (this document + prototype).** Bernard rules on D1–D12 (§10). A static HTML
prototype of the reference reader and library pages (theme-faithful, following the
`docs/ui-reference/` mock pattern) is produced for approval before any template code. No code.

**Stage 1 — Eligibility + reference reader.** `referenceable` function in `learning/services.py`;
`lesson_reference` view (`@login_required`, `@require_GET`, enrolment-free, unsaved-`LessonProgress`
pattern from the preview); approved template; Flow C refusal page. Tests
(`tests/test_reference_reader.py`): zero-side-effects sweep across all eight models (Flow A/D),
draft/retired/courseless refusals, anonymous redirect, student `lesson_detail` regression unchanged,
sanitizer parity for relative hrefs. No DB changes, no migrations.

**Stage 2 — Library and search.** `lesson_library` view + approved template: eligibility queryset,
`icontains` search, programme/course filters. Tests (`tests/test_lesson_library.py`): eligibility
filtering, search hits across block bodies, empty state, pagination behaviour.

**Stage 3 — Authoring ergonomics (optional, separately approved).** Permalink discovery in
`lesson_edit` (copy-link affordance); optionally a reference-picker dialog. Touches instructor UI →
design approval first. No `Resource` involvement.

**Stage 4 — Optional unification.** Refactor the instructor preview and the reference reader onto one
shared renderer (two entrances, different eligibility: preview sees drafts, the library does not).
Recommended eventually, not required for launch; kept separate so Stage 1 stays small.

Checkpoint after every stage: review, explicit approval, then proceed.

---

## 9. Regression and acceptance-test requirements

- **Isolation sweep (Flows A, C, D):** after every reader/library interaction, assert zero rows in
  `LessonProgress, ModuleProgress, ProgrammeProgress, LessonCheckResponse, TheoryAttempt,
  ScenarioAttempt, PracticalEvaluation, CompletionRecord, Certificate` — the established idiom
  (`tests/test_course_authoring_preview.py:118-148`).
- **POST rejection:** any POST to `/library/lesson/<uuid>/` → 405, no rows.
- **Anonymous:** reader and library redirect to login; no content bytes leaked.
- **Eligibility matrix:** unpublished at each level (lesson/module/course/programme-version), retired
  version, courseless module, inactive programme — all refuse with the Flow C message.
- **Renderer parity:** block kinds text/example/notice, images, key terms, objectives render
  identically to the student view (extend the parity pattern of
  `tests/test_rich_text_lesson_content.py:119-138`).
- **Existing-path regressions:** student `lesson_detail` still writes exactly its expected rows
  (`test_course_authoring_preview.py:190-207` unchanged); instructor preview still zero-row; sanitizer
  tests unchanged.
- **Search acceptance:** a "packing list" query finds a lesson whose *block body* contains it, not
  only its title.

---

## 10. Decisions requiring approval

| # | Decision | Recommendation |
|---|---|---|
| D1 | Reader/library page design (theme lock): prototype before any template code | Prototype in Stage 0; reader shows a source-attribution strip, content-driven sections (preview style), no progress UI, no forms |
| D2 | Library entry point in the student chrome (new sidebar item = new copy) | Decide with the prototype; roadmap link is the lower-churn option |
| D3 | Eligibility default | Published-everywhere ⇒ referenceable (no per-lesson opt-in field) |
| D4 | Authentication | `@login_required` on reader and library |
| D5 | Retired/unpublished policy + Flow C message copy | Not referenceable at any unpublished/retired level; copy approved with the prototype |
| D6 | Route prefix | `/library/…` at project level, outside `/theory/` |
| D7 | Unify instructor preview and reference reader eventually (one renderer, two entrances) | Yes at Stage 4; not a Stage 1 dependency |
| D8 | Reference links open in the same tab (sanitizer strips `target`) | Accept — consistent with every existing in-lesson link |
| D9 | Enrolled students always get reference mode on reference URLs (no silent swap; optional future "continue in my programme" link) | Accept |
| D10 | Courseless modules are never referenceable | Accept — closes the `module_is_available` gap |
| D11 | `docs/product-rules.md:39` says "a course is the complete programme" while the models (and this brief) say Programme → Course → Module → Lesson | Needs an independent ruling; docs fix only |
| D12 | Read-audit logging for reference reads | None for v1, consistent with lessons today |

---

## 11. Recorded concerns (per brief §7–§8, no work done)

- **Course-level assessment gap:** the assessment architecture has module assessments and a final
  theory exam but no course-level assessment. Recorded as a separate architectural concern; this
  feature neither depends on it nor changes it.
- **Self-enrolment compatibility:** the reference architecture creates no enrolments and no dual-
  enrolment expectations, so future self-enrolment lands without conflicts. The library's
  programme/course facets can later double as the browse surface for self-enrolment, but nothing in
  this design assumes it.

## 12. Database state observed (read-only, 2026-11-02)

- `ProgrammeVersion` statuses: every version is `draft` or `retired` — **zero published**. Draft:
  `customs-clearance-and-compliance` v1, `icums` v1 ("Customs Training"), plus test programmes.
  Retired: `xladder` v1, `experience-demo-a1` v1, `gsa-requirements-for-customs-business` v1–v2.
- `icums` (display name "Customs Training" — the Logistics-style content): 5 courses, 15 modules,
  60 lessons, 1,004 content blocks — **all unpublished at every level**.
- `customs-clearance-and-compliance` v1 (draft) exists but is **empty** (0 courses/modules/lessons).
- `Resource`: 0 rows; `learning_resource_lessons`: 0 rows. `HybridLesson`: 3 rows. `Lesson`: 93 rows
  total, 32 with `is_published=True` — every one inside a draft version, so `referenceable()` matches
  zero lessons today.
- Consequence: the first real milestone is Bernard publishing v1 of the relevant programme; until
  then the feature can only be demonstrated with explicitly approved demo data (the audit brief's
  "do not seed" restriction stands for this task).
