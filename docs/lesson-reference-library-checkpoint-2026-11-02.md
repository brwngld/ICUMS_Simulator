# Lesson reference library — checkpoint, 2026-11-02

Workstream state at the point we switch to other work. **Nothing was implemented,
nothing was committed or pushed, and no database record was changed** — per the brief's
restrictions this task stopped after the feasibility audit and implementation proposal.

## What exists on disk

- **Full deliverable:** [lesson-reference-library-plan.md](lesson-reference-library-plan.md)
  (2026-11-02). Contains: current-state findings for all ten audit areas from brief §4 with
  file:line references, the gap matrix, the recommended architecture, proposed routes,
  the security/progression-isolation risk register (R1–R10), Flow A–D walkthroughs, the
  incremental plan with approval checkpoints (Stages 0–4), regression/acceptance test
  requirements, and the twelve decisions awaiting product-owner ruling (D1–D12, §10).

## Verdict in one line

Feasible with **no new models, no migrations, no lesson duplication**: a dedicated
read-only reference view over the existing `Lesson`/`ContentBlock` rows that never
resolves an enrolment; identity is the existing UUID PK; references are ordinary
sanitized links in block bodies. The instructor preview
(`instructor_portal/views.py:1360-1413`) already proves the read-only renderer pattern,
including its tested zero-side-effects contract.

## Decisions pending (blocks all implementation)

§10 of the plan: prototype-first for the reader/library pages (theme lock, D1/D2),
published-everywhere ⇒ referenceable (D3), authenticated-only (D4), retired/unpublished
policy and Flow C copy (D5), `/library/` route prefix (D6), preview-unification timing
(D7), same-tab links (D8), enrolled-student behaviour (D9), courseless-module exclusion
(D10), the `docs/product-rules.md:39` "course" terminology ruling (D11), read-audit
logging (D12).

## Next actions once approved

1. Stage 0: static HTML prototype of the reference reader and library pages for approval.
2. Prerequisite for any real testing: publish v1 of a programme — as of 2026-11-02 **zero
   `ProgrammeVersion` rows are `published`**, so `referenceable()` matches zero lessons
   (plan §12 has the full DB snapshot, including the new empty
   `customs-clearance-and-compliance` draft programme).

## Workspace note

The working tree on branch `feat/theory-experience-faithful` carries unrelated uncommitted
work (Instructor Portal / Demonstration Studio / Stage 1A.1). This task added exactly one
file — the plan document — and left everything else untouched.
