# Learners enrolled on more than one programme

Status: **implemented 2026-10-16.** The single resolver, the `?programme=<code>`
parameter and `/programmes/` are live. §"History" keeps what the behaviour was
before, and §"Still open" what it still does not do.

## How it works now

- `onboarding/services.py` owns the choice:
  - `active_enrolments(user)` — every active enrolment, oldest first, `pk`
    breaking ties because `enrolled_at` is not unique and an unordered query can
    pick a different row page to page;
  - `requested_enrolment(request)` — the enrolment `?programme=<code>` names, or
    the oldest when the parameter is absent, or `None`;
  - `enrolment_for_request(request)` — the same, raising `PermissionDenied` for a
    page that cannot render without one;
  - `programme_href(url, enrolment)` — puts the parameter back on a generated link.
- Every student surface reads the request, not a guess: the roadmap, course,
  module and lesson pages (`learning/views.py`), assessments
  (`assessments/views.py`), orientation and the dashboard (`core/views.py`), the
  practical portal (`scenarios/views.py`) and the student sidebar
  (`core/admin_dashboard.py`).
- Links generated inside those pages carry the parameter, so choosing a programme
  once keeps you in it through the roadmap, its courses, lessons, assessments and
  the trail back. Redirects (lesson section, module overview after a completion)
  re-attach it too.
- `/programmes/` (`core.views.my_programmes`) lists each active enrolment with its
  module progress, and the dashboard gains the same list as a compact panel. Both
  appear only when a learner actually has a choice: with one active enrolment the
  sidebar, the dashboard and every URL stay exactly as they were.

## History

Before this, one enrolment was resolved per request and the learner was never
asked which programme they meant — the oldest active one won, because
`active_enrolment_for()` took `.first()` off an ordered query. Everything else was
scoped to that one `programme_version`, so the other programme was unreachable
rather than merely hidden: its course, module and lesson pages 404'd
(`learning/views.py`), its assessments raised `PermissionDenied`
(`assessments/views.py`), and the practical list filtered down to the chosen
version (`scenarios/views.py`). Attempt-owned pages filtered by
`enrolment__student`, so history from the other programme did appear there — the
learner saw records they could not open. Nothing was ever lost: progress,
attempts and completion records are stored per enrolment, and the model allows
several (unique only on `student + programme_version`, `onboarding/models.py`).

Verified live on the sample learner `xl-learner` with a temporary second active
enrolment: `/theory/` rendered only the older programme, a course of the second
programme returned 404, and the first course returned 200.

The genuine bug in that list was the dashboard and the student sidebar running
their own `filter(status="active").first()` **with no ordering** while the roadmap
used the ordered helper. SQLite agreed with the roadmap; PostgreSQL can return a
different row, so the "Continue your learning" card could describe one programme
while `/theory/` showed another.

## Rejected

*One active enrolment at a time* — contradicts how instructors actually use admin,
which creates enrolments freely. A *session-based switcher without the listing
page* — invisible state, and a bookmarked link can disagree with the session.

## Still open

- **The parameter names a programme, not an enrolment.** Two active enrolments for
  the same programme (different versions — `brwngld`'s development account has GSA
  v1 and v2) produce two rows that both open the older version. A per-version key
  would fix it; the agreed URL shape was `?programme=<code>`.
- **The practical portal does not carry the parameter through its own pages.**
  `/practical/` honours `?programme=` when it arrives, and the dashboard's
  practical and orientation links set it, but links inside the scenario list do
  not, so a scenario opened from there resolves the oldest enrolment. Orientation
  remains per enrolment, as decided.
- **`PermissionDenied` strings are user-facing.** "You are not enrolled in that
  programme." reaches the learner as a warning toast through `handler403`.
