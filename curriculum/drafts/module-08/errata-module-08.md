# ERRATA — Module 8 fact-check (lessons 8.1–8.4, assessment-module-08)

Fact-check run 2026-10-22 against `curriculum/research/logistics-scm-frameworks.md`
(sections 3, 4, 5, 7, 8, 13 and DO NOT CLAIM), `curriculum/research/trade-transport-standards.md`,
`curriculum/research/ghana-trade-customs.md`, and `curriculum/WRITING_SPEC.md`
(rules 5–6, section 11).

One WebSearch verification was spent, on the single claim the research sheet
flags as medium confidence (see VERIFIED item 9). All other checked claims are
covered by the sheets or are uncontentious general business knowledge. No duty
rates, statistics stated as fact, institutional claims, or container-spec
claims appear anywhere in the five files (grep-audited); all module-08 figures
are illustrative and labelled.

## CHANGES MADE (5 edits, 3 items)

### lesson-8.2.md

1. Key Concept "Recording Receipt: The Goods Received Note and Honest
   Paperwork", GRN job 1.
   - Before: "The warehouse officially owns the goods only from the moment the
     GRN is raised, so every later promise about availability rests on it."
   - After: "The goods enter official stock only from the moment the GRN is
     raised, so every later promise about availability rests on it."
   - Reason: legal ownership (title) passes per the sales contract and trade
     terms — often at shipment, before arrival — not upon GRN. The GRN creates
     the *stock record*, which is the point the block is making. Recast in
     records terms; teaching point unchanged.

2. Worked Example "One Order's Journey Through a Tema Distribution Centre",
   Step 3, closing sentence (same defect, narrative form).
   - Before: "The stock records now show 400 cartons owned by the warehouse."
   - After: "The stock records now show the warehouse holding 400 cartons."

### lesson-8.1.md

3. MCQ 2, option 4 and its explanation sentence.
   - Option 4 before: "...so that pickers need to visit the far racking more
     often." After: "...less often."
   - Explanation before: "Answer 4 fails because holding more stock does not
     shorten the walk; the picker still travels to the far racking on every
     order, and the extra stock adds holding cost." After: "...does not
     shorten the walk; the fast sellers still sit at the far end, so every
     order that needs them still pays the full distance, and the extra stock
     adds holding cost."
   - Reason: as drafted the distractor was self-contradictory (larger
     quantities causing *more* visits), and the explanation rebutted a
     different claim than the option made. It is now a coherent but wrong
     remedy (fewer replenishment trips do not shorten the per-order walk),
     which is what the explanation dismantles.

### assessment-module-08.md

4. Q6 stem.
   - Added: "All figures are illustrative for teaching purposes."
   - Reason: Q6 carries quantities (40/6/34 cartons) and was the only
     question of the twelve without the illustrative-figures label, while the
     assessment's FACTS & SOURCES states all figures "are labelled as such in
     the stems". Makes the file consistent with WRITING_SPEC rule 5.1 and
     with its own sourcing claim.

## VERIFIED — no change needed

1. **Formula audit — all arithmetic recomputed and correct.**
   - Lesson 8.3 cement retailer: lead-time demand 120 × 2 = 240; ROP = 240 +
     100 = 340; EOQ = sqrt(2 × 6,000 × 250 ÷ 12) = sqrt(250,000) = 500;
     6,000 ÷ 500 = 12 orders a year. All correct, and the EOQ statement
     (sqrt(2DS/H), D annual demand, S fixed cost per order, H annual holding
     cost per unit) matches the sheet exactly, with all four simplifying
     assumptions taught openly.
   - Lesson 8.3 pharmacy FEFO: Batch B (80) from April at 20/month = 4
     months, out end of July, two clear months before end-September expiry;
     FIFO counterfactual: Batch A (100) from January runs out end of May,
     leaving B exactly June–September (4 × 20 = 80, zero slack). Correct.
   - Lesson 8.3 ABC/turnover: 12 + 26 + 62 = 100 and 78 + 17 + 5 = 100 of
     per cent; 480 of 4,000 = 12%; turnover 6,000,000 ÷ 2,000,000 = 3;
     daily usage 6,000,000 ÷ 365 ≈ 16,400; days of supply 2,000,000 ÷
     16,400 ≈ 122 (= 365 ÷ 3). Correct and matches the sheet's formulas
     (turnover = COGS ÷ average inventory; days of supply = average
     inventory ÷ average daily usage).
   - Assessment Q7: FEFO — Batch Q (60) issued from February at 30/month,
     out end of March, three clear months before end-June; arrival order —
     Batch P (120) occupies January to end of April, leaving Q exactly May +
     June = 2 × 30 = 60, zero slack. Correct.
   - Assessment Q8: 45 × 3 = 135; 135 + 60 = 195; distractor 255 = 135 +
     2 × 60. Correct.
   - Assessment Q10: 30 × 24 = 720; overstatement 720 − 30 = 690 cartons.
     Correct.
   - Lesson 8.4 Kumasi reconciliation: expected 300 + 100 − 152 − 45 = 203;
     true transfer 48 gives B-07 = 200 (matches shelf); P-03 record
     20 + 45 − 30 = 35 vs shelf 20 + 48 − 30 = 38; totals 238 = 238. Fully
     consistent.
   - Lesson 8.4 unit-of-measure note: 60 × 24 = 1,440 bottles/pallet; MCQ 1
     variance 101 − 96 = 5; assessment Q4 80 − 74 = 6; Q6 40 − 6 = 34;
     Q11 excess 105 − 90 = 15; lesson 8.2 MCQ 1 shortage 60 − 54 = 6. All
     correct.
   - ROP statements in both files use trigger = lead-time demand + safety
     stock, matching the sheet; the weekly-usage simplified form is the
     sheet's daily form restated with a weekly period, which is sound.
2. **LIFO teaching (special duty 2).** Lesson 8.3 teaches LIFO as an
   accounting cost-flow convention ("the accounts may run last in, first
   out; the shelves do not"), never as a physical warehouse method; it
   states that as a physical method it suits almost no goods, and MCQ 3
   tests exactly that distinction. Matches the sheet's section 5 and DO NOT
   CLAIM item 3.
3. **LIFO/IFRS claim (the sheet's flagged medium-confidence item).**
   WebSearch-verified 2026-10-22: IAS 2 permits only FIFO and weighted
   average cost for interchangeable items; LIFO is not permitted under
   IFRS, while US GAAP allows it (ifrs.org IAS 2 page; Deloitte IAS Plus;
   KPMG IFRS-vs-US-GAAP comparison). Lesson 8.3's one-sentence treatment —
   "associated chiefly with United States accounting practice and is not
   permitted as a cost-flow method under international financial reporting
   standards" — is accurate as written and stands.
4. **FIFO/FEFO consistency (special duty 3).** Lesson 8.3's choice rule
   ("goods with expiry dates run FEFO; goods without them run FIFO as the
   general default") is applied identically in its worked example, MCQ 1,
   assessment Q7, and lesson 8.4's cycle-counting references. No
   contradictions found.
5. **Cross-docking (special duty 4).** Definition in 8.1 and 8.2 matches
   the sheet (receiving dock to shipping dock, little or no storage), and
   the dwell claim keeps the hedge in both places: "normally within
   twenty-four hours and often within the same shift" (8.1), "normally
   within about twenty-four hours" (8.2). Assessment Q3 makes no dwell-time
   claim. The MHIA attribution appears only in FACTS & SOURCES, not in
   learner-facing text.
6. **Three-way match.** 8.2 and 8.4 and assessment Q11 all state PO + GRN +
   invoice agreed before payment, discrepancies investigated first — exact
   match to sheet section 3. The receiving three-way comparison (PO,
   delivery note, goods) is kept distinct from the payment three-way match;
   no conflation.
7. **KPI statements.** Dock-to-stock time and inventory accuracy in 8.2/8.4
   match sheet section 7 definitions; no numeric benchmarks claimed
   anywhere, as the lessons' own FACTS & SOURCES assert.
8. **Sheet coverage.** Warehouse functions/zones/flow/picking methods/
   postponement/lean-waste/cold-chain/3PL/reverse logistics/WMS (8.1, 8.2),
   ABC, cycle counting, safety stock, service level, stockout/overstock
   (8.3, 8.4) all track the sheet's wording and confidence marks; the
   medium-confidence zone list is taught qualitatively. Ghana settings
   (Tema, Accra, Kumasi, Takoradi, Tamale, Cape Coast, Madina) are generic
   place names; the bonded-warehouse line is a single generic sentence with
   customs depth deferred, per the sheets' safe-phrasing discipline. All
   cross-referenced lesson titles (1.1, 1.3, 1.4, 2.3, 3.3, 5.3, 6.4)
   verified to exist in the curriculum.
9. **WRITING_SPEC compliance spot-check.** Assessment has 12 questions, 3
   per lesson, coverage map present, explanations open "The correct answer
   is Answer N."; every worked example across the four lessons carries the
   illustrative-figures label (after change 4).

## DECLINED / accepted as drafted (debatable items)

- Lesson 8.3 cement example: "Annual demand is roughly 6,000 bags" against
  120/week × 52 = 6,240. Accepted: the hedge "roughly" is present, the
  figure equals 120 × 50 weeks, and every downstream number (EOQ 500, 12
  orders) is internally consistent with 6,000. Illustrative example; no
  edit.
- Lesson 8.2: scheduling and dock allocation "guarantees that staff and
  equipment are free when the truck arrives". Rhetorical overstatement (a
  missed appointment breaks it) but harmless teaching voice in context;
  left.
- Lesson 8.4: "A signed delivery note is also a legal record" and "a
  signature... transfers responsibility". Stated as evidence/custody
  practice, not as a doctrine of title transfer; consistent with general
  warehouse practice. Left.
- Lesson 8.1: "travel... usually takes the largest share of a picker's
  time" — hedged, no benchmark percentages, matching its FACTS & SOURCES
  declaration. Left.
- Assessment Q3 explanation: pallets held on the dock "sit unrecorded as
  pickable stock" — means not recorded as *pickable* stock (received but
  not put away), consistent with lesson 8.2's teaching. Left.

## VERDICT

PASS-WITH-CHANGES. Five conservative edits across three files; all formula
arithmetic and every sheet-bound claim verified; the one externally flagged
claim (LIFO under IFRS) confirmed by live search. No owner decisions
required.
