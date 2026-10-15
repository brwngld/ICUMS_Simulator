# Deferred: learners enrolled on more than one programme

Status: **agreed direction, not implemented.** Drafted 2026-10-15 while the
course-hierarchy architecture was frozen, so that experience testing could
finish first. Nothing here is urgent except §"Fix regardless".

## What happens today

One enrolment is resolved per request and the learner is never asked which
programme they mean.

- `onboarding/services.py:6` `active_enrolment_for()` filters
  `student + status=active`, `order_by("enrolled_at")`, takes `.first()` — the
  **oldest active enrolment wins**. Used by every theory page, orientation,
  assessments and the practical portal.
- Everything downstream is scoped to that one `programme_version`, so the other
  programme is unreachable rather than merely hidden:
  - course → 404 (`learning/views.py:437`), module → 404 (`learning/views.py:188`),
    lesson → 404 (`learning/views.py:464`);
  - its assessments → `PermissionDenied` (`assessments/views.py:40`);
  - practical list → filtered to the chosen version (`scenarios/views.py:2851`).
- Attempt-owned pages (`assessments/views.py:90`, `scenarios/views.py:2882`)
  filter by `enrolment__student`, so history from the *other* programme does
  appear there — the learner sees records they cannot open.
- No UI anywhere lists a learner's own enrolments. The instructor dashboard
  (`instructor_portal/views.py:66`) is the only place multiple enrolments per
  student are visible at all.
- Nothing is lost: progress, attempts and completion records are all stored per
  enrolment. The model permits several (unique only on
  `student + programme_version`, `onboarding/models.py:109`), and admin creates
  them freely (`onboarding/admin.py:21`, `accounts/admin.py:13`).

Verified live on the sample learner `xl-learner` with a temporary second active
enrolment: `/theory/` rendered only the older programme, a course of the second
programme returned 404, and the first course returned 200.

## Fix regardless

The dashboard (`core/views.py:31`) and the student sidebar
(`core/admin_dashboard.py:252`) run their own
`filter(status="active").first()` **with no ordering**, while the roadmap uses
the ordered helper. SQLite happens to agree with the roadmap today; PostgreSQL
can return a different row, so the dashboard's "Continue your learning" card,
module counts and completion record could describe one programme while
`/theory/` shows another. Both call sites should use `active_enrolment_for()`
(or a shared ordered helper) whether or not the switcher work proceeds.

## Agreed direction

**"My courses" landing page on top of an explicit-enrolment resolver.**

1. Every student view resolves the enrolment from the request (a path or query
   parameter, validated against `student` + `status=active`) instead of guessing,
   falling back to the oldest active one so existing links keep working.
2. A page listing each active enrolment with its own progress, each linking into
   that programme's roadmap.
3. The roadmap, sidebar and dashboard follow the selected enrolment; the
   difficulty ladder stays per-programme, exactly as built.

Rejected for now: *one active enrolment at a time* (contradicts how instructors
actually use admin), and a session-based switcher without the listing page
(invisible state; a bookmarked link can disagree with the session).

Why this shape: it leaves the frozen single-programme roadmap intact, makes the
second programme genuinely reachable, and folds the ordering bug into the same
change instead of patching it separately.

## Not decided

- URL shape: `/theory/` becoming `/theory/<enrolment>/…` versus `?enrolment=`.
- Whether the dashboard shows one programme or a compact list of all.
- Practical/orientation gating across programmes — is orientation per programme
  or per learner? Today it is per enrolment (`scenarios/services.py:12`), which
  the listing page makes visible but does not resolve.
- New interface wording needs approval before any template is touched (theme
  lock, `AGENTS.md`).
