# ERRATA — Module 13 (Supply Chain Planning and Optimisation)

Fact-check of lessons 13.1–13.4 and assessment-module-13.md, 2026-10-22.
Every calculation in the module was recomputed independently. Verification
method: recomputation from the drafts' own stated inputs (no external facts
needed; zero WebSearch calls used), checked against
curriculum/research/logistics-scm-frameworks.md sections 5–8, 12–13 and its
DO NOT CLAIM list, curriculum/research/ghana-trade-customs.md section 8,
curriculum/research/trade-transport-standards.md (ISRT/transit), and
curriculum/WRITING_SPEC.md rules 5–6 and section 11.

## A. Errors found and corrected (via Edit)

1. **assessment-module-13.md, Q12 — wrong answer key (critical).**
   CORRECT was marked as option 1, "published figures from leading
   distributors are the most reliable available targets ... adopting them is
   what benchmarking is for" — precisely the borrowed-benchmark fallacy the
   lesson prohibits — while option 2 held the correct no-benchmark statement
   and the explanation itself said "Answer 1 mistakes target-shopping for
   benchmarking". Fix: swapped the texts of options 1 and 2 so the marked key
   (position 1) is the correct statement, and re-pointed the explanation's
   distractor reference from "Answer 1" to "Answer 2". The swap preserves the
   coverage note's claim that each correct-answer position is used exactly
   three times (3, 1, 4, 2, 3, 1, 2, 4, 3, 4, 2, 1).

2. **lesson-13.2.md, worked example 4 — fragmentation arithmetic contradicted
   the claim.** The split "3,500 in Accra plus 2,500 in Kumasi" sums to 6,000,
   exactly the single-site buffer, so the buffers were not multiplied at all
   and the stated "roughly a fifth" rise had no numerical support (it also
   inverted the lesson 13.3 pooling example, 400 to 280). Fix: split changed
   to 4,200 plus 3,000 = 7,200, stated as "7,200 where one pool held 6,000,
   roughly a fifth more" (exactly +20 per cent), with duplicated working stock
   raising total inventory further. Step 3's "extra fifth of inventory" now
   matches the buffers alone. No other block or question used the old numbers.

3. **lesson-13.2.md, worked example 2 — spoke-movement count.** "Hubbing that
   flow splits each full load into four spoke movements" is wrong: one load
   via a hub is two spoke movements (inbound + outbound), as the lesson's own
   MCQ 2 correctly states ("two spoke movements plus double handling"). The
   pair's two daily full loads give four movements in total. Fix: reworded to
   "turns the two daily full loads into four spoke movements and adds two hub
   handlings per load".

4. **lesson-13.2.md, worked example 1 — transit line inconsistent with the
   costing.** Option B at "three days when both borders move well, five when
   they do not" averages 4 days, i.e. only one extra day against Option A's
   three, but the comparison costs "two extra driver-and-vehicle days per
   trip" (GHS 3,000). Fix: Option B's typical transit changed to "four days
   when both borders move well, six when they do not" (average 5 = A's 3 + 2),
   which keeps every costing figure and the headline totals of GHS 40,600
   versus GHS 43,500 (dearer by GHS 2,900) intact.

5. **lesson-13.1.md, S&OP worked example, step 4 — unexplained December
   inflow.** Step 3 says "even a full December shipment" (5,000 cartons)
   leaves a pre-build need, yet step 4 uses a "December inflow of 4,000"
   without saying why — with a 5,000 inflow the plan would close exactly and
   there would be no gap to reconcile. All stated arithmetic (5,200 covered;
   6,500 less 5,500 = roughly 1,000 short; 1,200 x GHS 40 = GHS 48,000) was
   already correct. Fix: added one clause identifying the 4,000 as "the
   shipment already booked at the ordinary-month quantity and no longer
   enlargeable inside the eight-week lead time". No numbers changed; MCQ 2
   ("about 5,200 cartons") is unaffected.

## B. Recomputed and verified correct (no change)

- **13.1 moving average:** forecasts 210/220/230 for months 4–6; errors all
  exactly 20 cartons low. APEs 8.7 / 8.3 / 8.0 per cent; MAPE 8.34 = "about
  8.3 per cent". Correct.
- **13.1 exponential smoothing (alpha = 0.3, F1 = 200):** 200, 203, 208.1,
  214.7, 222.3 (unrounded 214.67, 222.269); errors 21.9 / 25.3 / 27.7; MAPE
  10.39 = "about 10.4 per cent". Correct under both rounded and unrounded
  chaining. Demand rise 50/200 = "25 per cent across the record". Correct.
- **13.1 bullwhip example:** consumer range 100 units to factory range 1,000
  units = "ten times the variation"; all ranges internally consistent and
  expressly illustrative (DO NOT CLAIM 16 respected). Correct.
- **13.2 routing:** A = 40,000 + 0.1 x 6,000 = 40,600; B = 37,500 + 2 x 1,500
  + 0.5 x 6,000 = 43,500; B dearer by 2,900; MCQ quote advantage 2,500. All
  correct. Geography per ghana-trade-customs.md section 8 (paved Accra and
  Lome axes to Ouagadougou); no border post named, per the sheet's Not
  Verified list. Regional transit referenced generically per lesson 12.1 and
  the ISRT entry in trade-transport-standards.md. Compliant.
- **13.2 hub arithmetic:** 5 x 4 / 2 = 10 routes versus 5 spokes; per-route
  20 per cent versus per-spoke 80 per cent (4 x one-fifth). Correct.
  (Assessment Q5's 7 x 6 / 2 = 21 versus 7 spokes also correct.)
- **13.2 milk run:** 4 x 1,800 = 7,200; old load factor 4/12 = one-third;
  16/16 = 100 per cent; saving 7,200 - 3,500 = 3,700; two-thirds idle.
  Correct.
- **13.3 service-level example:** 12 cycles; 12,000/365 = about 33 units a
  day, lead-time demand 330; medicine 150 x 20 + 1,000 + 1,000 = 5,000;
  expected events 1.2 and 0.12; costs 6,000 / 600 / 1,440 / 144; saving
  "roughly 1,300" (1,296); ROP 330+250 = 580 and 330+600 = 930; extra 350 x 6
  = 2,100 against 5,400 avoided; multivitamin 400 x 5 = 2,000 against 1,296
  saved, so the lower target wins. All correct.
- **13.3 pooling:** 400 - 280 = 120 released; 120 x 150 = 18,000; 120 x 7.50
  = 900 a year. Correct.
- **13.3 Rotterdam:** 480,000/40,000 = 12 turns; 480,000/365 = about 1,315;
  40,000/1,315 = about 30 days; 60,000/45,000 = 1.33 ("about 1.3");
  60,000/365 = about 164; 45,000/164 = about 274 days. Correct. Turnover =
  COGS / average inventory and days of supply = average inventory / average
  daily usage are sheet-exact (section 5).
- **13.4 OTIF example:** failures 8 + 5 - 2 = 11; OTIF 89 per cent; OTD 92;
  in-full 95; averaging trap 93.5. Correct, and the OTIF formula matches the
  sheet exactly (strict: late or short fails; early-but-short still fails).
- **13.4 perfect order:** 0.95 x 0.95 x 0.99 x 0.98 = 87.56 = "roughly 87.6",
  taught with the sheet's "some conventions" qualifier. Correct.
- **13.4 Rotterdam tension example:** 20 to 16 euros = 20 per cent; 8 OTIF
  points; 4-euro saving. Correct. Tonne-kilometre: 1,000 / (10 x 200) = 0.5
  GHS. Correct.
- **13.4 MCQ 1:** failures 6 + 4 - 2 = 8; OTIF 72/80 = 90; distractors 92.5
  (74/80), 95 (76/80), 93.75 (average). All correct.
- **Assessment Q2:** month 7 forecast (330+340+350)/3 = 340; forecasts
  310/320/330 versus actuals 330/340/350, each 20 low; six-month average
  1,950/6 = 325. Correct.
- **Assessment Q7:** ROP 320+80 = 400 and 320+140 = 460; extra 60 x 5 = 300;
  expected failures 1.2 and 0.6; stockout cost 960 and 480; saving 480; net
  gain 180. Correct. (Note for the coordinator's brief: the assessment
  contains no "195 ROP"; the only "195" is inside "1,950/6 = 325" in the
  arithmetic-verified source line.)
- **Assessment Q10:** failures 12 + 9 - 3 = 18; OTIF 132/150 = 88; OTD
  138/150 = 92; in-full 141/150 = 94; averaging trap 93. Correct.
- **Formulas:** OTIF (orders both on time and in full / total orders
  delivered x 100), MAPE (mean of |actual - forecast| / |actual| x 100,
  fragile near zero actuals), MAD, ROP = lead-time demand + safety stock,
  turnover, days of supply, cycle service level vs fill rate, perfect order
  with its qualifier — all sheet-exact.
- **Bullwhip:** four causes attributed to Lee, Padmanabhan, and Whang (1997)
  and taught per the sheet; countermeasures (POS sharing, smaller and more
  frequent orders, everyday stable pricing, VMI) per the sheet; no
  amplification magnitude claimed as fact anywhere.
- **No-benchmark rule:** no "world-class" or universal targets stated as fact
  anywhere; 13.4 explicitly denies universal benchmarks; assessment Q12 uses
  the 99 per cent figure only as a fictional claim that the correct answer
  dismantles.
- **Fact-safety spot checks:** no duty rates, fees, or statutory periods; all
  computation figures labelled illustrative; no vendor or company claims;
  Ghana/international example placement per WRITING_SPEC section 4.

## C. Debatable items considered and declined (no edit)

1. **13.1, "six times out of six"** (bias step of worked example 1): reads
   ambiguously until one connects it to step 3's common months 4–6 window,
   where both methods are scored — 3 moving-average errors plus 3
   exponential-smoothing errors, all low. Defensible as written; an edit
   risked more confusion than it removed.
2. **13.3, safety-stock levels 250 (90 per cent) and 600 (99 per cent)** and
   the linear expected-events arithmetic: the service-level-to-stock mapping
   is an illustrative design input, not a claimed formula; the expected-events
   arithmetic given those inputs is exact, and the sheet forbids presenting
   any statistical safety-stock formula as universal (respected). Left as is.
3. **13.1, bullwhip ranges (950–1,050 up to 900–1,900):** expressly
   illustrative and internally consistent; magnitudes per DO NOT CLAIM item 16
   stay illustrative. Left as is.
4. **Cross-references to lessons not yet drafted** (1.2, 3.2, 3.3, 5.3, 5.4,
   7.2, 7.4, 8.2, 8.3, 8.4, 9.2): names follow the module lesson briefs cited
   in each FACTS & SOURCES section and could not be checked against drafts
   that do not exist yet. Titles that do exist as drafts were verified (7.1,
   9.4, 10.1, 12.1).

## D. Flagged for the owner (not a factual error; no edit made)

1. **lesson-13.4.md block count:** 12 Key Concepts + 3 Worked Examples + 3
   Important Notes = 18 teaching blocks, one above WRITING_SPEC section 3's
   14–17 range (the other three lessons are in range: 13.1 = 17, 13.2 = 17,
   13.3 = 17). Removing a block is a content decision, so it is left to the
   owner (candidates: merge "Dashboards, reports, and the operating rhythm"
   with "Choosing KPIs for an operation", or fold one Important Note into a
   Key Concept).

## E. Review-driven clarifications (2026-10-23)

An external content review was checked against the drafts. Two of its
clarifications were accepted and applied; its three "corrections" were
checked and declined, because the source already carries them.

1. **Applied — 13.1, forecast accuracy measures:** RMSE added to the
   MAPE/MAD paragraph (KEY CONCEPT "Forecast error and forecast accuracy:
   bias versus noise"), defined as the square root of the mean squared error
   and described as weighting a few very large misses far more than many
   small ones. Scoped to respect the DO NOT CLAIM list: no accuracy
   benchmarks or "good MAPE" thresholds added, and the FACTS & SOURCES
   inventory updated to match.
2. **Declined — "bias metrics are missing":** 13.1 already teaches the
   bias/noise distinction with sign-of-error analysis ("bias is the cheapest
   error to fix and the most expensive to ignore").
3. **Declined — "postponement always reduces risk":** the lesson never makes
   that claim; 13.1 already carries the trade-off paragraph ("Postponement
   is not free. It requires a configuration capability close to the
   customer…").
4. **Word-band trims to pay for the RMSE addition:** three rhetorical
   duplicates removed — the bullwhip block's "snap of the wrist" figure, the
   inventory-policy block's "Both ingredients trace back" signpost, and the
   forecasting-importance block's second restatement of its own closing
   sentence. No facts changed.

## Verdict

PASS-WITH-CHANGES: five corrections applied (one answer-key error, two
arithmetic inconsistencies, one costing/transit inconsistency, one
unexplained input); all other recomputed figures, formulas, attributions, and
fact-safety rules verified correct.
