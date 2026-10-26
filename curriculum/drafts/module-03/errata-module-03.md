# ERRATA — Module 3 fact-check (lessons 3.1–3.4, assessment-module-03)

Fact-check run 2026-10-22 against `curriculum/research/trade-transport-standards.md`,
`curriculum/research/ghana-trade-customs.md`,
`curriculum/research/logistics-scm-frameworks.md`, `curriculum/WRITING_SPEC.md`
(rules 5–6, section 11), and the lesson briefs in
`curriculum/lesson_briefs/module-03/`. One WebSearch confirmation was used
(container pallet capacity, for change 1 below).

Verified clean, no change needed: every container figure in lesson 3.3 matches
the trade sheet exactly (20ft 5.898 x 2.352 x 2.393 m / 33 m3 / 30,480 kg max
gross / ~28,250 kg payload; 40ft ~12 m / 67.5 m3 / ~26,700 kg payload; high-cube
~2.7 m internal; TEU/FEU and the FEU = 2 TEU rule); the nine DG classes, UN 1950
/ UN 3480, and "classes 1, 2 and 7 have no packing groups"; the B/L three
functions with the "certain forms" title qualifier; the AWB always
non-negotiable / never a document of title; MAWB vs HAWB; VGM as a shipper duty
since 1 July 2016 (SOLAS VI/2) with no VGM = no loading; cargo and documentation
cut-offs; the multimodal (one contract, one operator) vs intermodal (same
loading unit, separate contracts) distinction — correctly stated, no
intermodal/multimodal reversal anywhere, including assessment Q5; CMR taught as
European with Ghana explicitly not a party; non-preferential vs preferential
certificates of origin with ETLS and AfCFTA; phyto/health certificates;
three-way match; free-time/charge language kept qualitative with no amounts.
Ghana content is sheet-backed or generic (ICUMS as national customs system,
channel/risk model, UCR, licensed clearing agent; Tema/Kotoka as geography
only; no unverified institutional claims — no GIFF, no MPS, no Terminal 3, no
MoFA directorate names, no border-post names). Cross-lesson references check
out ("earlier lesson" mentions of TEU, liner services, air waybill, and
consolidation all exist in modules 1–2 drafts; Module 6 and Module 11
forward-references match the curriculum structure). Marker syntax, block
counts, 3 MCQs per lesson, 12 assessment questions with matching CORRECT
openers, British spelling, no markdown in bodies, and no real company names:
all pass (`tools/qa_drafts.py` clean for all five files, before and after).

## CHANGES MADE (7)

### lesson-3.3.md

1. Worked Example "Packing a containerised export of shea butter products",
   Step 3 (Choosing the container).
   - Before: "Volume: 1,000 cartons at about 0.03 cubic metres come to about
     30 cubic metres, close to the roughly 33 cubic metres inside a
     twenty-foot container once pallet clearances are allowed for. Weight:
     1,000 cartons at 12 kilograms give 12,000 kilograms, comfortably below a
     twenty-foot container's payload of approximately 28,250 kilograms. The
     cargo is volume-bound rather than weight-bound, so a twenty-foot box is
     right; a forty-foot container would cost more while sailing half empty."
   - After: "Volume: 1,000 cartons at about 0.03 cubic metres come to about
     30 cubic metres before the pallets beneath them are counted, which
     already fills the roughly 33 cubic metres inside a twenty-foot container,
     and fifty pallets cannot be fitted into one. Weight: 1,000 cartons at
     12 kilograms give 12,000 kilograms, comfortably below a forty-foot
     container's payload of approximately 26,700 kilograms. The cargo is light
     for its volume, so a forty-foot box is right; the pallets travel in it
     double-stacked with room to spare, while a twenty-foot container would
     accept only part of the load."
   - Reason: the example's conclusion was physically impossible and
     self-contradictory. Step 2 creates 50 pallets (20 cartons each); a
     twenty-foot container holds roughly 9–11 standard pallets single-stacked
     (about 20–22 double-stacked), so 50 cannot fit — confirmed by industry
     sources (iContainers "How many pallets fit in a container") and by the
     sheet's own internal dimensions (floor 5.898 x 2.352 m, height 2.393 m).
     The pallets add roughly 9 m3 to the cartons' 30 m3, so the load exceeds
     33 m3 rather than fitting "once pallet clearances are allowed for". The
     corrected conclusion (palletised, light-for-volume cargo goes in the
     forty-foot) is exactly the lesson's own Key Concept rule ("heavy, dense
     cargo goes in twenty-foot containers, while light, bulky cargo suits
     forty-foot boxes") and the trade sheet's safe phrasing, so the example
     now demonstrates the rule instead of violating it. Step 5 ("the 50
     pallets are stuffed into the container") and the closing paragraphs
     needed no change; the sheet-listed container figures are untouched.

2. Worked Example "Dangerous goods under control: a consolidated shipment
   from Singapore", Step 1.
   - Before: "...and each is assigned a packing group according to its degree
     of danger."
   - After: "...and the flammable liquid is assigned a packing group according
     to its degree of danger; gases, being a class without packing groups, are
     not graded in this way."
   - Reason: the example's two dangerous products are Class 2 aerosols and a
     Class 3 flammable liquid; "each is assigned a packing group" attached a
     packing group to Class 2 gases, contradicting the same lesson's Key
     Concept ("Classes 1, 2, and 7 have no packing groups") and the trade
     sheet's DO NOT CLAIM 7 ("never attach PG I/II/III to explosives, gases or
     radioactive material"). Step 2's declaration-field list (which mentions
     packing groups generically) is correct as written and untouched.

3. Worked Example "Dangerous goods under control..." — added the missing
   illustrative-figures sentence: "All figures in this example are
   illustrative for teaching purposes."
   - Reason: the example quotes concrete quantities (60 cartons, 40 drums,
     200 cartons) without the rule 5.1 label; its two siblings in the lesson
     both carry one.

### lesson-3.4.md

4. Worked Example "An air shipment: spare parts from Singapore to Rotterdam"
   — added "All figures in this example are illustrative for teaching
   purposes." to the opening paragraph.
   - Reason: the example quotes a concrete weight (85 kilograms) without the
     rule 5.1 label; example 1 in the same lesson carries one.

5. Worked Example "A domestic delivery and a five-carton shortage" — added
   the same label to the opening paragraph.
   - Reason: the example quotes concrete quantities (240/235 cartons) without
     the label; the lesson's FACTS section already claimed every worked
     example carried it.

### lesson-3.1.md

6. Key Concept "The participants who carry out the journey": "the factory
   despatching cartons" changed to "the factory dispatching cartons".
   - Reason: spelling consistency only — the module otherwise uses "dispatch"
     exclusively (lesson 3.1 itself at "stage the goods for dispatch" and
     "dispatcher"; lesson 3.4 throughout; assessment), and the two forms
     appeared in one sentence. Both are acceptable British variants, but not
     mixed in one text.

7. FACTS & SOURCES, ICUMS entry: citation "trade-transport-standards.md
   sections 9 and 12" changed to "trade-transport-standards.md section 12
   (Ghana's single window operates through ICUMS) and
   logistics-scm-frameworks.md section 9 (Ghana anchor: end-to-end e-customs
   platform at all ports of entry and exit)".
   - Reason: metadata only — the trade sheet's section 9 is Dangerous Goods,
     not the source of this claim; the "ports of entry and exit" phrasing
     comes from the logistics sheet's Ghana anchor. The lesson body's claim
     itself was sheet-backed and unchanged.

## CONSIDERED AND DECLINED

- Lesson 3.3 Key Concept teaches 30,480 kg max gross without the ISO
  668:2016/2020 36,000 kg plating-tested amendment or the road-weight-limit
  caveat (trade sheet DO NOT CLAIM 6). Declined: the lesson follows the
  sheet's own SAFE PHRASINGS for containers verbatim, beginner-level
  difficulty ladder applies, and the sheet says to teach 30,480 kg as the
  traditional design max gross. The VGM discussion in lesson 3.1 already
  teaches the verified-actual-weight idea, and road-limit capping appears
  qualitatively in lesson 3.2's FACTS. No learner-facing falsehood.
- Lesson 3.4 Worked Example 1 states unconditionally that the B/L issued for
  the shrimp container "is ... the document of title", where the Key Concept
  says "certain forms" of the document are. Declined: in the usual export
  case (order B/L, as here — the example says the document "controls who may
  claim the container in Amsterdam") the statement is correct, both MCQ 2 and
  assessment Q11 state the "certain forms" qualifier precisely, and tightening
  the narrative would add no teaching value.
- Lesson 3.1 Worked Example 1: 18 pallets in one refrigerated container.
  Within real-world range for a 20ft reefer with Euro-footprint pallets
  double-stacked, explicitly labelled illustrative ("all quantities and times
  are illustrative"), and no arithmetic conclusion depends on it. Left alone.
- Lesson 3.1 Worked Example 2: 20 pallets of tomato paste stuffed at the
  Italian factory. No pallet-count-to-container claim is made (the container
  size is unstated), so nothing to correct.
- Lesson 3.3 Worked Example 2: 1,200 sacks x 60 kg = 72 tonnes on three
  truckloads (24 t each) — plausible for articulated trucks and explicitly
  illustrative; cocoa in ~60 kg jute sacks matches industry practice. Left.
- Lesson 3.2 Worked Example 3 (cement distribution) has no concrete figures,
  only "a few dozen bags to a part-load", so rule 5.1's label is not
  triggered. No change.
- Lesson 3.2 KC 1 lists "Multimodal transport" with a loose one-line
  description before the precise single-contract definition later in the
  lesson. Declined: the precise definition (brief-verbatim) is taught twice
  in full; the list line is a preview, not a competing definition.
- Assessment Q4 relies on overland rail existing between the
  Shenzhen–Hamburg lane — already recorded as VERIFIED in
  `curriculum/PROGRESS.md` spot-checks (qualitative claim only; no figures).
- Word-count headroom note for the owner: lesson 3.1 sits at 5,499 of the
  5,500-word band; any future addition there will need a compensating trim.
