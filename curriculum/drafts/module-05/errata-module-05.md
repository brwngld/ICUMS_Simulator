# ERRATA — Module 5 (Freight Forwarding Fundamentals) fact-check

Fact-check date: 2026-10-22. Checker verified all five files
(lesson-5.1.md, lesson-5.2.md, lesson-5.3.md, lesson-5.4.md,
assessment-module-05.md) against curriculum/research/trade-transport-standards.md,
curriculum/research/ghana-trade-customs.md, curriculum/research/logistics-scm-frameworks.md,
curriculum/WRITING_SPEC.md, the lesson briefs in
curriculum/lesson_briefs/module-05/, and the owner's verified items in
curriculum/PROGRESS.md (weekly sailing frequency + ~1-week rollover; GRA
"clearing agent" terminology). WebSearch was used for the general-knowledge
claims the drafts flagged (cited below).

Verdict: PASS-WITH-CHANGES. One spelling-consistency fix applied; every
factual claim checks out against the sheets, the owner's ledger, or verified
industry sources. No factual corrections were needed.

## Changes made (safe fixes only)

1. lesson-5.1.md — 7 occurrences, "transhipment" → "transhipment"
   (responsibilities block; common-challenges block; Worked Example 2 Options
   A and B and the risk paragraph; MCQ 2 question; MCQ 2 explanation).
   REASON: British spelling (spec section 9) and module consistency —
   lesson-5.2, lesson-5.4, assessment-module-05, and lesson-7.1 all use
   "transhipment". Pure spelling change; no meaning touched. qa_drafts.py
   re-run after the edit: all five module-05 files still [OK].

## High-risk items — confirmed as taught

- lesson-5.1 export declaration in ICUMS: the hedge HELD. Body reads "The
  export declaration is lodged through Ghana's single-window customs system,
  ICUMS" — passive, no agent named, exactly as the FACTS entry promised.
  Supportable: UNECE Rec. 33 (via trade-transport-standards.md section 12)
  defines the single window as covering "import, export, and transit-related
  regulatory requirements", and ghana-trade-customs.md section 1 confirms
  ICUMS is Ghana's single window. Import-side statements elsewhere in 5.1,
  5.3, 5.4, and assessment Q3 correctly use the verified import-specific
  clearing-agent phrasing.
- lesson-5.2 rollover and weekly frequency: present and hedged as taught —
  "Container liner services on major trade lanes commonly sail on a weekly
  frequency" and "On a weekly service the rollover typically costs about a
  week of transit"; MCQ 3 says "roughly one weekly service". Matches the
  owner's 2026-10-22 verified ledger.
- lesson-5.3 "said to contain": hedged in body as "A common practice ..." and
  now externally verified — standard carrier qualification on sealed
  consolidated boxes: https://dhl-freight-connections.com/en/logistics-dictionary/said-to-contain-stc
  and https://www.dpworld.com/en/glossary/said-to-contain-stc
- lesson-5.3 LCL costs more per unit of volume than FCL: taught qualitatively
  with structural reasons (CFS handling both ends, build/break, weighing,
  per-customer documentation), no amounts — confirmed as standard industry
  practice; assessment Q9 handles the per-unit vs total-cost nuance correctly.
- lesson-5.3/5.4 master vs house B/L: verified — carrier issues the MBL to the
  forwarder/consolidator, forwarder issues an HBL per shipper:
  https://cargox.io/content-hub/master-bill-of-lading-vs-house-bill-of-lading
  The TT Club confirms the agent/principal teaching behind it (issuing an HBL
  puts the forwarder into a carrier-liability position):
  https://www.ttclub.com/news-and-resources/news/article/tt-talk-legal-eagle-when-should-a-freight-forwarder-issue-a-house-bill-of-lading
- lesson-5.4 milestone sequence: taught as "for a typical consolidated ocean
  import" (hedged) and matches the standard industry milestone flow (booking,
  gate-in/cargo received, loaded, departed, transhipment, arrived/discharged,
  customs cleared, released, delivered):
  https://www.kpler.com/blog/a-complete-guide-to-container-tracking and
  https://terminal49.com/glossary/container-milestones
- lesson-5.4 four-verb exception framework (identify, investigate,
  communicate, resolve): not merely general knowledge — it reproduces the DB
  key-term definition of Exception Management in lesson brief 5.4 verbatim.
  The investigate-before-communicate ordering is the lesson's own pedagogy,
  correctly flagged as such in FACTS.
- lesson-5.4 UCR claim ("the consignment carries the Unique Consignment
  Reference assigned in ICUMS, which supports end-to-end tracking") matches
  ghana-trade-customs.md section 1 and its SAFE PHRASING exactly.

## Reviewed and accepted (no change needed)

- lesson-5.2 GRI gloss "typically to manage capacity or restore profitability"
  vs the sheet's "contract seasons or capacity management" — uncontentious
  general-business gloss; the body explicitly attaches no figures.
- lesson-5.1 "the multimodal transport bill of lading administered by the
  international forwarders' federation FIATA" — generic descriptor, not
  FIATA's full name (International Federation of Freight Forwarders
  Associations); accurate as a description, sheet-backed (trade sheet
  section 4). Left as written.
- lesson-5.3 VGM phrasing "the party that packs the container must ensure its
  verified gross mass is obtained and declared" vs lesson-5.2's formal SOLAS
  framing ("the shipper must obtain and communicate"): complementary, not
  contradictory — 5.2 teaches the rule, 5.3 operationalises it for
  consolidated boxes. Both stay inside DO NOT CLAIM 11.
- Assessment Q3's "underlying duty to provide truthful and accurate
  information remains with the importer" — the lesson's own (uncontentious)
  principle that representation does not transfer accountability; consistent
  with 5.1's Important Note and the sheet's import-procedure facts.
- Worked-example arithmetic checked and correct: 5.2 WE1 (6 x 1.8 m3 = 10.8
  m3; lines sum to 3,370) and WE2 (830+250=1,080; 900+250+320+140+170=1,780;
  1,080+660=1,740); 5.3 WE1 (9+11+8=28 m3; 6,800+5,900+2,300=15,000 kg vs
  40ft 67.5 m3 / 26,700 kg payload from lesson 3.3 and trade sheet section 6).
- Destination cities beyond the spec's example list (London in 5.2, Dublin in
  assessment Q7) — general geography, uncontentious.
- All worked examples carry the "illustrative for teaching purposes" label;
  the assessment header covers all twelve scenarios and Q6's cut-off clock
  times are scoped to one illustrative booking confirmation (consistent with
  7.1's "never assume a cut-off" teaching).

## Spec compliance (verified mechanically)

- Block markers exact; qa_drafts.py [OK] on all five files (5.1: 10 KC/3 WE/3
  IN; 5.2: 11/3/3; 5.3: 11/3/3; 5.4: 10/3/3; all within 4,000-5,500 body
  words; assessment 12 questions).
- All 15 lesson MCQs and 12 assessment questions: POINTS: 1, exactly 4
  options, CORRECT matches the "The correct answer is Answer N." opener
  (checked programmatically).
- No markdown syntax in bodies. British spelling now consistent throughout
  (see change 1). No real companies named ("Adinkra Trading Company Ltd" in
  5.3 is a fictional illustrative name per spec section 4).
- Coverage map present in the assessment; 3 questions per lesson in lesson
  order; every question header names the lesson it tests.
- Cross-references verified against the drafts/briefs: lesson 2.2 title
  ("Freight Forwarders, Carriers, Shipping Lines, and Agents"), lesson 3.3
  title and the 40-ft figures first taught there, Module 4 Incoterms 2020
  handling, Module 11 lesson 11.4 ("Managing Shipment Delays, Damage, and
  Discrepancies"), and previous/next lesson titles per the briefs.

## Out-of-scope observation (for other fact-checkers / the owner)

- The American spelling "transhipment" also appears in
  drafts/module-02/lesson-2.3.md, drafts/module-07/lesson-7.1.md,
  drafts/module-07/lesson-7.4.md, and drafts/module-09/lesson-9.1.md (7.1
  mixes both spellings). Not touched here — those modules are outside this
  assignment — but whoever fact-checks those modules should normalise to
  "transhipment" for consistency.
- This errata file itself trips qa_drafts.py's lesson checks (as the module-01
  and module-02 errata files already do); that is known script noise, not a
  defect.
