# Guided-Practice Checkpoint — Project State and Pause Record

**Checkpoint date:** 10 October 2026 · **Baseline commit:** `d5e0ca3` (Phase 1 integration)
**Status of the guided-practice engine roadmap: PAUSED — resume after the simulator UI redesign.**

This document preserves the state of the ICUMS Simulator and the guided-practice
roadmap so work can resume safely later. It complements `docs/implementation-status.md`
and `docs/deferred-security-review.md`.

## 1. Purpose and current state

The ICUMS Simulator is a local-first educational web application for learning
customs-clearance theory and practising simulated customs workflows. It is a
training simulator, not the official ICUMS platform: no real declarations,
payments, or connections. Theory, assessments, practical scenarios, playground
records (UCR/BOE/consignment/MDA), instructor authoring, completion records and
certificates are all operational; the simulator UI is mid-redesign onto the
Unfold-based design system used by the admin and student portals.

## 2. Phase 1 guided-practice integration (complete)

Final commit: **`d5e0ca3`** — "feat: Phase 1 guided-practice simulator
integration (link-out + server-side verification)". 16 files, +876/−8.
Verified at commit time: **278 tests passing**, Django system check clean,
no pending model changes, migrations `0047`/`0048` applied.

What it delivered:

- `ScenarioState.binding` JSON field (migration `0047`) storing an approved
  **route name** (not a URL) from the registry in `scenarios/bindings.py`;
  paths resolve through `reverse()` so future simulator URL redesigns survive.
- The guided workspace (an authorized shell page) renders a "Simulator task"
  callout with an **Open simulator step** link-out (separate tab) and an
  explicit **Check my work** action. Verification never advances the state
  machine; progression rules are unchanged.
- `scenarios/verification.py`: action-level, owner-scoped verification against
  real UCR/BOE/consignment/MDA records, bounded by the recorded step-open
  moment (falling back to attempt start) so pre-existing records cannot
  satisfy a new task.
- The simulator access gate stashes a validated internal `/practical/` path
  and `simulator_login` returns the student there after re-authentication;
  unsafe destinations are rejected (no open redirect).
- `MdaConsignmentRequest` gained `owner` + `updated_at` (migration `0048`,
  unambiguous backfill from each request's consignment application — verified
  before running: all 9 existing rows had an application, every application an
  owner; the migration fails loudly rather than guessing). Owner is set on all
  create paths and the MDA search filters by the direct owner.
- The practical editor authors per-stage bindings (registry route, task label,
  verified record + status) with validation; 20 new regression tests in
  `tests/test_guided_simulator_binding.py`.

Known limitations (accepted at approval):

- Correlation is owner + step-open time-window, not a hard attempt↔record
  link. A pre-existing record the student deliberately re-saves during the
  task can therefore satisfy it. Tightening this (record-level correlation or
  value-level checks) is future work under decision E3.
- Verification is display-independent by design (server-side records), so the
  simulator UI redesign does not affect it.

## 3. Architecture in place

See `docs/architecture.md` and `docs/data-model.md`. Summary: Django 5.2,
custom UUID users with Student/Instructor/Administrator groups (`accounts`),
versioned programmes/enrolments/disclaimer (`onboarding`), theory content
(`learning`), knowledge checks + module/final assessments with frozen question
sets (`assessments`), progress ledger (`progress`), declarative guided
scenario engine with immutable action ledger (`scenarios`), rubric evaluation
with instructor revisions (`evaluations`), completion + certificates
(`reports`), append-only audit events (`audit`), and the shared shell /
dashboard / orientation (`core`). The playground is DB-backed and per-user:
UCR declarations, BOE declarations, consignment applications, MDA requests,
seeded Ghana HS tariff, regimes/CPCs, ports, training stakeholders. Simulator
access uses monthly `SimulatorCredential`s; staff review mode is view-only
(see §7 for known gaps).

## 4. Roadmap history and the two work streams

The learning-architecture audit (10 Oct 2026, baseline `e4c6d92`) produced a
staged roadmap. **Course-authoring work — complete:** Stage 0 guard-rails
(publish requires module assessments + a final exam with questions; both
attempt starters serialize on the enrolment row) and Stage 1 builder usability
(edit flows, reorder, prerequisites, instructor previews, standalone
assessment management) landed in commits `76e4a3e`/`afd21fc` with 56 new
tests. **Guided-practice engine work — Phase 1 complete (above), remainder
paused:** the demonstration-and-practice engine over the real playground
(audit Stage 2), student-portal redesign (Stage 3), and broader regression
passes wait until the simulator UI redesign is done.

## 5. Decision register (E1–E6)

Seven E1 decisions approved 10 October 2026 (recorded in the E1 decision
report; working notes under gitignored `qa/`):

1. Phase 1 approach: link-out + server-side verification, no frozen-file or
   security-header changes. **Implemented.**
2. Binding storage: dedicated `ScenarioState.binding` JSON field + migration. **Implemented.**
3. Verification depth: action-level (record exists, owned, required status). **Implemented.** Value-level (E3) remains open.
4. Verification trigger: explicit "Check my work". **Implemented.**
5. Future iframe: deferred; reassess after the simulator UI redesign. **Open.**
6. Simulator login redirect: safe validated internal `?next`. **Implemented.**
7. MDA ownership: `owner` + `updated_at` added with backfill. **Implemented.**

Other audit decisions still open: **E2** content lifecycle for published
courses (builder edits stay draft-only; no controlled published-edit flow),
**E3** verification depth beyond action-level, **E4** resolved (module
assessments required at publish; no legacy data fix was needed — the database
held no published courses at the time), **E5** frozen-boundary hooks for any
future in-page embedding/highlighting, **E6** resolved (attempt-start races
fixed in Stage 0).

## 6. Frozen-file boundaries and approvals

Per `AGENTS.md` (theme and copy locked 2026-10-09) and the standing working
agreements: no changes to the visual theme or user-facing text without
Bernard's explicit approval of the outcome. Frozen: `templates/scenarios/*`
(except the authorized list/detail/workspace shell pages extending the base
student template), `templates/assessment/detail.html`,
`static/css/simulator-portal.css`, `static/css/cargo-page.css`,
`static/css/ucr-create.css`, simulator JavaScript, and `static/js/app-shell.js`
(separate explicit approval required). Authentication, session, CSRF and
security-header configuration changes require explicit approval; no iframe
embedding or `X_FRAME_OPTIONS` weakening without approval.

## 7. Deferred review-mode and ownership issues

Documented during the October 2026 bug hunts (working reports under
gitignored `qa/`; summary also in `docs/deferred-security-review.md`):
`boe_create` and the MDA-request-create endpoint lack review-mode write
guards (a reviewing staff member POSTing mutates the student's record); the
IDF lookup is not owner-scoped (a student can use another's IDF number);
BOE declaration pages 404 under staff review mode (`owner=request.user`
instead of `_effective_owner`). None blocks the paused roadmap, but all three
belong on the pre-launch hardening list. Phase 1 explicitly did not bundle
them.

## 8. Outstanding guided-practice work (paused)

- Demonstration mode over the playground (highlight, playback, per-step
  failure/retry paths) — audit Stage 2 remainder; depends on E5 if embedded.
- Stricter attempt↔record correlation (optional; see §2 limitations).
- Student-portal redesign items (audit Stage 3 / Deliverable D): progress
  rail/two-pane lessons, illustration block kind, profile/settings page.
- Possible `?next`-style deepening of step links (e.g. prefilled `?draft=`
  entry points) once the simulator UI settles.

## 9. Last verified state

- Tests: **278 passed** at `d5e0ca3` (configured suite, `testpaths = tests`).
  Note: `accounts/tests.py` is outside the configured suite and contains two
  failing tests tied to the known blank "Generated password" dashboard bug —
  tracked on the hardening list, not part of this pause.
- Database: local dev SQLite; migrations through `0048` applied; MDA owner
  backfill ran over 9 rows. No production data exists; the VPS deployment
  templates remain staged in `deploy/` unexercised.
- Unresolved risks: the deferred security items (§7); `config/settings/vps.py`
  raises `NameError` instead of a clean error when `DJANGO_SECRET_KEY` is
  unset (flag before any VPS work); simulator credential expiry is enforced
  per-request (acceptable) with no proactive invalidation job.

## 10. How to resume safely

1. Re-verify baseline: clean tree, full suite green, `makemigrations --check`
   clean, and confirm the frozen-file boundaries still match `AGENTS.md`.
2. Read this checkpoint plus `docs/implementation-status.md` and the E1
   decision register (§5); re-confirm which decisions remain open.
3. For engine work, extend from `scenarios/bindings.py`,
   `scenarios/verification.py`, and the existing test patterns in
   `tests/test_guided_simulator_binding.py`; keep bindings route-name-based.
4. For any simulator-UI integration beyond the approved shell pages, obtain
   explicit per-file approval first (E5 process).
5. The simulator UI redesign is the active work stream; the guided-practice
   engine remains **PAUSED — resume after the simulator UI redesign**.
