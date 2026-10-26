# Curriculum Development — Progress Tracker

Owner: Bernard. Deliverable: 15 module Word documents covering 60 lessons
(5 courses × 3 modules × 4 lessons) of the Customs Training logistics
programme, PLUS one module assessment per module (12 questions, 3 per lesson,
covering all 4 lessons; platform range 10–15), each ready for manual entry —
lessons via the Theory Builder, assessments via Configure assessment.

Structure (confirmed in DB and instructor portal): every course = 3 modules;
every module = 4 lessons + 1 module assessment. Lesson requirements per the
portal: 5 fixed sections per lesson and at least 1 knowledge-check question
(we produce 3 per lesson). Platform supports module assessments (70% default
pass) and a programme-wide final exam (NOT requested — do not create one).

Status legend: [ ] todo · [~] in progress · [x] done

## Pipeline state

- [x] Lesson briefs dumped from DB → `curriculum/lesson_briefs/module-NN/lesson-N.M.md`
- [x] Writing specification → `curriculum/WRITING_SPEC.md`
- [~] Research fact sheets (3 background agents):
  - [~] `curriculum/research/ghana-trade-customs.md` (Ghana customs/ports/regulators) — still running
  - [x] `curriculum/research/trade-transport-standards.md` — DONE (~4,300 words, 12 sections + DO-NOT-CLAIM)
  - [~] `curriculum/research/logistics-scm-frameworks.md` (7Rs, warehousing, KPIs, tech, strategy) — still running
- [x] Course 1 drafts complete except 3.4 (failed twice on rate limits — TOP of queue)
- [x] Draft lessons through 7.3 — 7.2 trimmed to band by me inline (5,699→<5,500);
      ALL 32 drafted files pass `qa_drafts.py` (0 issues)
- [~] Modules 1-6 compiled to docx (6 of 15 review documents ready)
- Usage-limit note: provider 5-hour cap hit ~00:02 provider-time (=16:00 local);
  resets 17:10 local. Timer exec_10f86185 wakes the pipeline. Relaunch queue at
  reset: 7.4, then M8 lessons+assessment cadence through M15 (32 lessons, 9
  assessments remain), then fact-check pass, final compile, visual gate.
- [ ] Draft 15 module assessments (12 questions each, after the module's lessons)
- [ ] Fact-check + corrections pass (per module, lessons AND assessment)
- [ ] Compile 15 .docx into `curriculum/docx/` (lesson 1.1 content pulled from
      local_data/db.sqlite3; assessment section appended per module)
- [ ] Visual quality gate + delivery

## My spot-checks (fact-check ledger, verified by me 2026-10-22)

- ETLS e-certificate (lesson 6.3): VERIFIED — ECOWAS launched the electronic
  Certificate of Origin 25 Nov 2024; Ghana is one of six pilot states
  (ecowas.int). Fact-check pass may add "November 2024" to the draft if wanted.
- "Clearing agent" usage (lessons 2.4, 5.1): VERIFIED — GRA's own page uses
  "Customs House Agent (CHA)", interchangeably "Customs Broker"/"Customs
  Clearing Agent" for GRA-licensed intermediaries.
- Module 6 assessment: read in full by me; agent died post-write but the file
  is complete, spec-format, and derives solely from lesson content. APPROVED.
- Weekly sailing frequency + rollover (~1 week on weekly lanes) (lessons 5.2,
  7.1): VERIFIED — weekly is the liner benchmark; missed cut-off = rollover to
  next sailing, ~7 days (industry sources).
- China–Europe rail between sea and air on speed/cost (lesson 3.2): VERIFIED —
  rail ~12–20 days vs sea 50–60 vs air 3–7; ~50% cheaper than air (qualitative
  claim in draft is exactly right; no figures are quoted in the draft itself).

## Known data issues

- Module 11 lesson ordering CORRUPTED in DB: "Cargo Insurance and Risk
  Allocation" and "Dangerous Goods..." BOTH have order=2; nothing at order 1.
  Cargo Insurance belongs at position 1. Only module affected (checked all 15).
  Caused the missing 11.1 brief (dump overwrote it) — brief regenerated
  manually 2026-10-22. Reported to Bernard — HE fixes in admin. Do not edit DB.

- Module 4 Lesson 1 title+slug in DB are CORRUPTED: "It frightens me, and I
  definitely don't want to jump. I just experience the feeling." (slug
  `it-frightens-me-and-...`). Should be "Importing, Exporting, and Transit
  Trade". Summary/objectives/key terms intact. Reported to Bernard
  2026-10-22 — HE fixes in admin; drafts use the correct title. Do not edit DB.
- Lesson 1.2 (`logistics-versus-supply-chain-manageme`): `key_terms` field in
  DB is corrupted — holds a duplicate of the objectives. Drafting agent will
  propose key terms in the draft (`=== PROPOSED KEY TERMS ===`) for Bernard
  to approve. Do not edit the DB ourselves. APPROVED by Bernard 2026-10-22.
- Module 1's existing "Introduction to Logistics Module Assessment" holds
  only 3 questions and is unpublished; it will be superseded by the new
  12-question assessment draft. Bernard enters it via Configure assessment.

## Module assessment status

| Module | Assessment draft (12 Qs) | Fact-check |
|---|---|---|
| 01–15 | pending (after that module's lessons) | |

## Lesson draft status (59 to draft)

| Module | Lessons | Drafts | Fact-check |
|---|---|---|---|
| 01 Introduction to Logistics | 01.1–01.4 | COMPLETE (1.1 from DB + drafts) | assessment DONE |
| 02 The Logistics Ecosystem | 02.1–02.4 | COMPLETE | assessment DONE |
| 03 Fundamentals of Goods Movement | 03.1–03.4 | COMPLETE | assessment DONE |
| 04 International Trade Fundamentals | 04.1–04.4 | COMPLETE (title bug in DB) | assessment DONE |
| 05 Freight Forwarding Fundamentals | 05.1–05.4 | COMPLETE | assessment DONE |
| 06 Logistics Documentation | 06.1–06.4 | COMPLETE | assessment DONE |
| 07 Transport and Shipping Operations | 07.1–07.4 | COMPLETE (7.2 trimmed by me) | assessment next slot |
| 08 Warehousing and Inventory Management | 08.1–08.4 | all 4 lessons drafting |  |
| 09 Port and Terminal Operations | 09.1–09.4 | queued |  |
| 10 Logistics Costing and Pricing | 10.1–10.4 | queued |  |
| 11 Logistics Risk and Compliance | 11.1–11.4 | queued |  |
| 12 Cross-Border Logistics and Coordination | 12.1–12.4 | queued |  |
| 13 Supply Chain Planning and Optimisation | 13.1–13.4 | queued |  |
| 14 Digital Logistics and Technology | 14.1–14.4 | queued |  |
| 15 Strategic Logistics Management | 15.1–15.4 | queued |  |

Compiled review docx so far: modules 01–04 in curriculum/docx/.
| 06 Logistics Documentation | 6.1–6.4 | pending | |
| 07 Transport and Shipping Operations | 7.1–7.4 | pending | |
| 08 Warehousing and Inventory Management | 8.1–8.4 | pending | |
| 09 Port and Terminal Operations | 9.1–9.4 | pending | |
| 10 Logistics Costing and Pricing | 10.1–10.4 | pending | |
| 11 Logistics Risk and Compliance | 11.1–11.4 | pending | |
| 12 Cross-Border Logistics and Coordination | 12.1–12.4 | pending | |
| 13 Supply Chain Planning and Optimisation | 13.1–13.4 | pending | |
| 14 Digital Logistics and Technology | 14.1–14.4 | pending | |
| 15 Strategic Logistics Management | 15.1–15.4 | pending | |

## Draft files land in

`curriculum/drafts/module-NN/lesson-N.M.md`

## Working agreements

- Spec at WRITING_SPEC.md is binding: 14–17 blocks (9–12 Key Concept,
  3–4 Worked Example, 2–3 Important Note), exactly 3 MCQs, fact-safety rules,
  plain-text bodies, British spelling, Ghana + international examples.
- Never state duty rates/fees/deadlines as fact; illustrative figures must be
  labelled. Institutional claims only from research sheets.
- Bernard reviews the docx per module before entering content into the
  Theory Builder himself. We do NOT write to the database.

## Fact-check ledger (final pass)

| Module | Verdict | Notes |
|---|---|---|
| 01 | PASS-WITH-CHANGES | 6 edits; aligns 1.2 with approved 1.1 wording |
| 02 | PASS-WITH-CHANGES | stale caveats updated; clearing-agent usage GRA-verified |
| 03 | PASS-WITH-CHANGES | 2 real fixes: impossible 50-pallet/20ft; PG on Class 2 |
| 04 | PASS-WITH-CHANGES | Incoterms clause-by-clause audit clean; 5 conservative edits |
| 05 | PASS-WITH-CHANGES | 1 spelling fix; TT Club/FIATA corroborations |
| 06 | PASS-WITH-CHANGES | 52 t in one container -> 24 t fixed; doc-law clean |
| 07 | PASS-WITH-CHANGES | 6 fixes incl. inverted quote-example arithmetic |
| 08 | PASS-WITH-CHANGES | GRN != title transfer fix; formulas recomputed; IAS 2 verified |
| 09 | PASS-WITH-CHANGES | creditors self-contradiction fixed; charges sheet-exact |
| 10 | PASS-WITH-CHANGES | all arithmetic recomputed; 1 assessment distractor fixed |
| 11 | PASS | zero edits |
| 12 | PASS-WITH-CHANGES | 9 edits; corridor framings softened to illustrative (J1 logged) |
| 13 | PASS-WITH-CHANGES | CRITICAL: wrong answer key on assessment Q12 fixed; 4 consistency fixes |
| 14 | PASS-WITH-CHANGES | 2 precision edits; standards sheet-exact, no hype |
| 15 | PASS-WITH-CHANGES | Tema-Rotterdam sea transit 5->3 weeks fixed; Aflao verified |


## FINAL STATUS — DELIVERED 2026-10-23

- 60 lessons (1.1 from DB + 59 drafted) + 15 module assessments: WRITTEN.
- Fact-check: 15/15 modules verified. 14 PASS-WITH-CHANGES, 1 clean PASS (M11).
  Real catches fixed: wrong answer key (M13 assessment Q12), 52 t in one
  container (6.1... lesson 6.2), 50 pallets in a 20 ft (3.3), PG on Class 2
  aerosols (3.3), inverted quote-comparison arithmetic (7.4), GRN-as-title
  overstatement (8.2), Tema-Rotterdam 5->3 weeks (15.4), plus spelling and
  label sweeps. Per-module errata files in curriculum/drafts/module-*/.
- Structural QA: 74/74 files pass (qa_drafts.py), incl. two block merges
  (11.3, 13.4) and word-band trims (1.3, 10.3, 13.1, 13.2, 15.2).
- Documents: 15 docx + 15 pdf in curriculum/docx/, rebuilt from verified
  drafts after all corrections. Visual gate: 60-page sample judged; the two
  flagged defects (orphaned KEY CONCEPT label; HTML in lesson 1.1's DB-sourced
  blocks) were fixed (keep-with-next; HTML-to-text converter) and re-passed.
- OWNER ACTION ITEMS (database, not touched by us):
  1. Module 4 Lesson 1 title/slug corrupted ("It frightens me...") -> restore
     "Importing, Exporting, and Transit Trade".
  2. Module 11 lesson order: Cargo Insurance at order 1 (currently 2, tied
     with Dangerous Goods).
  3. Lesson 1.2 key_terms field holds a duplicate of the objectives -> replace
     with the PROPOSED KEY TERMS in its draft (pending Bernard's approval).

## DB BUGS — FIXED 2026-10-23 (with Bernard's approval)

Backups: backups/db-before-curriculum-fixes-20261023-183728.sqlite3 and
backups/lesson-rows-before-fixes-20261023-183728.json (full row images).

1. M4/L1 title+slug restored: "Importing, Exporting, and Transit Trade" /
   importing-exporting-and-transit-trade. VERIFIED.
2. M11 order: Cargo Insurance now 1 (was tied at 2 with Dangerous Goods). VERIFIED.
3. M1/L2 title de-truncated: "Logistics versus Supply Chain Management"; slug
   -> logistics-versus-supply-chain-management. VERIFIED.
4. M1/L2 key_terms replaced with the draft's 7 proposed terms (preamble line
   excluded). VERIFIED.
Note: local_data/db.sqlite3 only — apply the same four fixes to any production
database. Compiler TITLE_FIXUPS left in place as harmless documentation.
  Optional: add "November 2024" to lesson 6.3's ETLS e-certificate sentence;
  genericise Aflao in 15.4 for uniformity with modules 12-13.
