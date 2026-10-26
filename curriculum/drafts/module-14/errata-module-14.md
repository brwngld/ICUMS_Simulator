# ERRATA — Module 14 fact-check (lessons 14.1–14.4, assessment-module-14)

Fact-check run 2026-10-22 against `curriculum/research/logistics-scm-frameworks.md`
(section 9 anchor + DO NOT CLAIM), `curriculum/research/trade-transport-standards.md`
(sections 4, 5, 7, 12 + DO NOT CLAIM), `curriculum/research/ghana-trade-customs.md`
(ICUMS safe phrasings + DO NOT CLAIM), `curriculum/WRITING_SPEC.md` (rules 5–6,
section 11), and the four lesson briefs in `curriculum/lesson_briefs/module-14/`
(read-only, used to verify the key-term definitions the drafts attribute to them).

No WebSearch verification was needed (0 of 6 calls used): every institutional or
standards claim in the five files traces to the research sheets, which were
verified live 2026-10, and every remaining claim is uncontentious general
business knowledge.

## STANDARDS AUDIT — all sheet-exact (no changes needed)

- EDIFACT: expansion ("Electronic Data Interchange for Administration, Commerce
  and Transport"), UNECE publication, ISO 9735 approval, UN/CEFACT maintenance,
  ORDERS/DESADV/INVOIC meanings, and the coexistence framing ("X12 prevails in
  North America, EDIFACT remains widespread internationally, neither has
  displaced the other" — DO NOT CLAIM item 14 respected) — 14.2 only.
- X12: 850 purchase order, 855 purchase order acknowledgement, 856 advance ship
  notice, 810 invoice; the 850→855→856→810 teaching cycle with the three-way
  match — 14.2. Mis-assignments of message meaning appear only inside MCQ/assessment
  distractors (14.2 MCQ 1 option 2; assessment Q5 option 4), and each explanation
  states the correct mapping (856/DESADV vs 810/INVOIC).
- GS1: GTIN = trade-item identity at any packaging level, "the number encoded in
  a barcode, not the barcode itself"; SSCC = 18-digit logistics-unit identifier,
  key ASN data element — 14.2, 14.3, assessment Q8 (DO NOT CLAIM item 13
  respected; the 18-digit count is stated identically in all three places).
- MLETR: UNCITRAL Model Law on Electronic Transferable Records, adopted
  13 July 2017, three principles, control as the electronic equivalent of
  possession, "national adoption varies" with no adoption counts anywhere
  (DO NOT CLAIM item 15 respected) — 14.2 (twice), 14.4 (reference only),
  assessment Q6.
- e-AWB: IATA Resolution 672 (Multilateral e-AWB Agreement), default contract of
  carriage on enabled lanes since 1 January 2019, paper the exception; no
  adoption percentages anywhere — 14.2, assessment Q6 (both dates sheet-exact).
- AWB non-negotiable / ocean B/L document of title (DO NOT CLAIM item 11
  respected everywhere); sea waybill and telex release described per sheet.

## NO-HYPE SWEEP — clean

- Blockchain keeps the promise-vs-caution pairing in 14.4 ("tamper-evident
  rather than alteration-proof"; "a ledger guarantees that a record has not been
  altered since it was entered; it cannot guarantee that the entry was true in
  the first place") and again in assessment Q12. Adoption caution present
  ("legal recognition varies… neutral platforms have mattered more so far…
  adoption remains partial and uneven"), matching the sheet's qualitative frame.
- AI/ML stays qualitative in 14.3 and 14.4: forecasting, ETA prediction,
  OCR/extraction, anomaly detection — no performance, ROI or accuracy figures.
- No adoption statistics anywhere in the five files.
- Vendor/platform sweep: "Accenture", "SAP", "Oracle" absent; no commercial
  platform named. One change made (below). UNIPASS/ICUMS/GRA appear only in the
  sheet-sanctioned safe phrasings; IPCSA is not named for port community systems;
  no Ghana PCS claim; no ICUMS rollout dates, GCNet/West Blue mentions, single
  window 2015 date, or Shippers' Authority transfer claim (Ghana DO NOT CLAIM
  list respected in full).

## FUNCTION-BOUNDARY AUDIT — consistent

- ERP = value ("what do we own, owe, sell, and spend"), WMS = quantity at a bin
  with the tasks that touched it ("where is every item, and who moved it"),
  TMS = load, carrier, charges ("how does each shipment move, and what does it
  cost") — identical division in 14.1 and assessment Q1/Q2 explanations.
- Freight audit in 14.1 matches the lesson-7.4 anatomy it cites (base charge,
  surcharges, totals; pay the contract, not the invoice; approved invoices pass
  to finance for settlement with the audit trail) and the sheet's three-way
  match (§3) and TMS freight-audit/settlement scope (§9); assessment Q3 tests
  the same control with the same boundaries (compare, flag, hold — never
  silently correct or renegotiate).
- Key-term definitions in all four drafts verified verbatim against the
  corresponding lesson briefs (including OMS, which is absent from the research
  sheet but is a brief 14.1 key term — compliant via the brief).

## ASSESSMENT — verified

- 12 questions, exactly three per lesson, in lesson order; coverage map matches
  the questions; every question answerable from current lesson text (checked
  question by question, including quoted lesson phrases: "guessing dressed in
  mathematics", "a fiction formatted as a number", "the system sees
  confirmations, not cartons").
- Q6 (e-B/L case) checked word by word: stem, options and explanation align
  with 14.2's easy/hard dividing line — AWB non-negotiable receipt vs
  document of title held by possession and endorsement; scanned PDF can be
  neither possessed nor controlled; MLETR principles with varying national
  adoption. Locations/goods (Tema, Antwerp, shea butter) are on the spec's
  approved lists.
- Q10 (analytics-ladder case) checked word by word: option 2 reproduces the
  ladder order (descriptive → diagnostic → predictive → prescriptive), the
  inheritance rule, and the "model trained on history nobody has examined"
  consequence exactly as taught in 14.4.
- CORRECT positions run 2, 4, 1, 3, 2, 4, 3, 1, 4, 2, 1, 3 — each used exactly
  three times, as the coverage note claims; no negative-form stems; no
  "All of the above".

## CHANGES MADE (2)

### lesson-14.2.md

1. FACTS & SOURCES, X12 bullet.
   - Before: "...— source: research sheet logistics-scm-frameworks.md, section 9
     (citing IBM standards documentation)."
   - After: "...— source: research sheet logistics-scm-frameworks.md, section 9."
   - Reason: the no-vendor-names rule applies "anywhere"; the parenthetical was
     a second-hand provenance note duplicating the research sheet's own citation,
     so removing it loses nothing. FACTS is not learner-facing, but the sweep is
     cheapest this way. (The vendor name "IBM" appeared nowhere else in the
     module; no teaching content named any vendor before or after this change.)

2. Key Concept "The standard message families: UN/EDIFACT and ANSI X12", EDIFACT
   paragraph.
   - Before: "...it was approved as the international standard ISO 9735 and is
     maintained by UN/CEFACT, the UN centre for trade facilitation."
   - After: "...maintained by UN/CEFACT, the United Nations Centre for Trade
     Facilitation and Electronic Business."
   - Reason: the sentence reads as an expansion of the acronym; the partial
     expansion omitted the body's official remit ("...and Electronic Business").
     Full name is uncontroversial and matches the expansion style used in the
     same lesson for EDIFACT. Sheet-consistent ("maintained by UN/CEFACT").

## ITEMS REVIEWED AND DECLINED (no change)

1. "Descriptive analytics is the analysis of historical data to explain what has
   happened" (14.4). "Explain" could suggest diagnostic work, but it is the
   verbatim key-term definition in lesson brief 14.4, and the lesson immediately
   draws the what-vs-why line ("Descriptive tells you what. The second rung asks
   why"), on which MCQ 1 and assessment Q10 turn. Changing it would diverge from
   the curriculum database. Owner's call if the database definition itself is
   ever revisited.

2. "Possession of the original, properly endorsed... transfers ownership in
   transit" (14.2, and "transfers ownership mid-journey" in assessment Q6). The
   sheet says a duly endorsed B/L "controls the right to delivery, which is what
   makes it valuable... for selling goods in transit". The drafts' phrasing is
   the conventional commercial teaching of the same point and is used
   consistently; left unchanged.

3. Certificates of origin grouped with the easy-case (non-negotiable) documents
   in 14.2 and assessment Q6. Correct under the lesson's own criterion — they
   "name parties and record events; they do not confer control of the cargo" —
   and Q6's stem keeps the claim generic ("its certificates of origin are issued
   electronically"), not tied to the ECOWAS ETLS e-cert. No change.

4. Yard management (14.1) and the batch/wave picking boundary are taught as
   concepts without figures, matching the sheet's "medium confidence — teach the
   concept" handling; FACTS discloses both confidence caveats. No change.

5. Illustrative arithmetic audited: 14 × 4,200 = 58,800 and 14 × 450 = 6,300
   (14.1); 24 × 40 = 960 and 12 + 12 = 24 (14.2); 270 + 30 = 300 invoices
   (14.3); 40/310 ≈ "roughly one in eight" and 6/330 = "under one in fifty"
   (14.4). All internally consistent and labelled illustrative. No change.

6. 14.1's FACTS mentions the three-way match as "referenced conceptually"
   although the 14.1 body does not name it (the match is taught in 14.2 and the
   assessment). Over-disclosure, not error. No change.

7. 14.4's "an obvious attraction for bills of lading, certificates of origin and
   the chain of endorsements" — the endorsements belong to the bills of lading,
   not the certificates; the natural reading is the intended one. No change.

## VERDICT

PASS-WITH-CHANGES. Marker syntax, block counts (14.1: 10 KC + 3 WE + 3 IN + 3
MCQ; 14.2: 9 + 3 + 3 + 3; 14.3: 9 + 3 + 3 + 3; 14.4: 9 + 3 + 3 + 3), POINTS: 1,
four options per question, CORRECT/explanation-opener pairings, British
spelling, illustrative-figures labels on every quantified worked example, and
complete FACTS & SOURCES sections all verified compliant. The two edits are a
source-line cleanup and a standards-precision fix; neither touches theme,
headings, or teaching copy beyond the quoted sentence fragments.
