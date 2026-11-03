# Customs Curriculum — Compound Plan and Progress Tracker

Owner: Bernard. Deliverable: **60 lessons + 15 module assessments** for the programme
*Customs Clearance and Compliance*, in the same form the Logistics curriculum shipped in
(`curriculum/drafts/module-NN/lesson-N.M.md` → fact-check → `curriculum/docx/`), ready for
Bernard to enter by hand through the Theory Builder and Configure assessment.

Nothing in this plan writes to the database. The programme
`customs-clearance-and-compliance` v1 is still a `draft` version with 0 courses, 0 modules
and 0 lessons, so **there is no DB content to dump briefs from** — unlike Logistics, the
briefs are authored here from the curriculum document plus the source files.

- Structure: Course 1–5 → 3 modules each (M1–M15) → 4 lessons each (N.1–N.4) → 3 MCQs
  per lesson → 1 module assessment of 12 questions per module.
- Lesson sections are the platform's five fixed steps: Introduction (objectives) →
  Key concepts → Worked example → Important note → Practice.
- Writing contract: `curriculum/customs/WRITING_SPEC.md` (inherits the Logistics spec,
  overrides length, fact-safety and relatability).
- Course titles, module titles and lesson titles are taken **verbatim** from
  `output/docx/Customs Clearance Curriculum - with Courses.docx`. Do not reword them.
- Difficulty lives on the Course: C1 beginner · C2 beginner-intermediate ·
  C3 intermediate · C4 intermediate-advanced · C5 advanced.

## Pipeline state

- [x] Course layer added to the curriculum document (2026-11-02)
- [x] Source inventory triaged: 12 of 18 PDFs have a text layer (`.tmp/source-text/`),
      6 are scans (`Transit and Transhipment`, `FREE ZONES`, `DUTY-FREE SHOPS`,
      `Risk Management`, `FULL DUTY CALCULATIONS - AKYA`, `HS CODE 2024 2`,
      `CamScanner 10-01-2026`)
- [x] `TARIFF` base validated: `HS FINAL 2017-15-506.xlsx`, 377 sheets, 5,886 TSN rows,
      97 chapters, columns Heading / TSN / Description / SU / CET ID / VAT / IE.
      `hscodesgh.pdf` is the ICUMS HS search printout and is **truncated at 8463.20 —
      chapters 85–98 are missing from it**.
- [x] Auction-allocation specimen (Form 80) produced and anonymised
- [ ] Research fact sheets (3 background sheets, same purpose as the Logistics ones)
      → `curriculum/customs/research/`
      - [ ] `ghana-customs-institutions.md` — GRA/Customs Division, GPHA, GPA, MPA, GTA,
            GSA, FDA, the CHA licensing route, which body does what (scanned from anchors,
            not memory) + a DO-NOT-CLAIM list
      - [ ] `customs-instruments-and-standards.md` — HS Convention structure, GRI wording,
            Revised Kyoto Convention, WTO Trade Facilitation Agreement, Incoterms 2020
            obligations table, ECOWAS CET and TSN construction, AfCFTA protocol status
      - [ ] `ghana-legal-anchors.md` — Act 891 section-by-section index with the fourteen
            day / record keeping / ruling / objection provisions quoted, the unapplied
            amendments listed, Public Health Act 851 provisions used by FDA/GSA controls,
            and the subsidiary regulations cited in the decks (LI 1541, LI 1586, LI 1932,
            NRCD 173) with what each actually says
- [ ] Lesson briefs, all 60 → `curriculum/customs/lesson_briefs/module-NN/lesson-N.M.md`
      (4 drafted as the calibration set; see below)
- [ ] Lesson drafts, 60 → `curriculum/customs/drafts/` — waves of one module at a time,
      each wave QA'd with `tools/qa_customs.py` before the next starts
- [ ] Module assessments, 15 → one per module after its four lessons
- [ ] Fact-check and errata pass per module
- [ ] Compile 15 docx + pdf → `curriculum/customs/docx/`
- [ ] Visual quality gate and delivery

## Module 1 calibration set

Briefs written 2026-11-02 for M1 (4 lessons) so Bernard can approve the shape before the
remaining 56 are authored: `lesson_briefs/module-01/lesson-1.1.md` … `1.4.md`.

## The 60 lessons and their source anchors

Titles verbatim from the curriculum document. Anchor keys are defined in
`WRITING_SPEC.md` C3. `+L` marks a lesson that carries a Logistics cross-reference line.

### Course 1 — Customs Foundations, Documents and the Clearance Ecosystem (`beginner`)

**M1 Customs Foundations and the Legal Mandate**
| Lesson | Anchor |
|---|---|
| 1.1 Purpose, functions and mandate of Customs | `ACT` ss.1-13 · `CPC-LAW` · `TIMETABLE` |
| 1.2 Customs laws, regulations and international standards | `ACT` front matter + unapplied amendments · `CPC-LAW` · instruments sheet |
| 1.3 Customs controlled areas, ports, borders and approved routes | `ACT` ss.4, 5, 46, 47 · `CPC-PORT` |
| 1.4 The import, export and transit clearance lifecycle | `ACT` ss.14-29, 48-54, 6-13, 95-97 |

**M2 Trade, Shipping and Clearance Documents**
| Lesson | Anchor |
|---|---|
| 2.1 Modes of transport, vessel operations and cargo types | `CPC-TT` · `ACT` ss.15-21 +L |
| 2.2 Commercial invoice, packing list and supporting records | `ACT` ss.14, 101, 9 record keeping +L |
| 2.3 Bill of lading, air waybill and certificate of origin | `ACT` ss.15, 70 · `CPC-TT` +L |
| 2.4 Incoterms and the allocation of cost, risk and responsibility | `CPC-TT` · instruments sheet +L |

**M3 The Port and Border Clearance Ecosystem**
| Lesson | Anchor |
|---|---|
| 3.1 Customs, port authorities, terminal operators and shipping lines | `CPC-PORT` · institutions sheet |
| 3.2 Importers, exporters, customs house agents and freight forwarders | `ACT` ss.43, 44, 45 |
| 3.3 Cargo arrival, manifesting, discharge and terminal handling | `ACT` ss.16-21 · `CPC-PORT` |
| 3.4 Release, delivery, storage, demurrage and detention | `ACT` ss.6, 52, 53 · `CPC-PORT` +L |

### Course 2 — Customs Procedures, Electronic Declarations and Import Controls (`beginner-intermediate`)

**M4 Customs Regimes and Core Procedures**
| Lesson | Anchor |
|---|---|
| 4.1 Imports for home consumption and export procedures | `ACT` ss.74, 97 · `TIMETABLE` |
| 4.2 Customs Procedure Codes and declaration types | `ACT` ss.49, 50 · systems sheet |
| 4.3 Temporary importation, re-export and re-importation | `ACT` ss.75, 77, 78 · `TIMETABLE` |
| 4.4 Suspense procedures and movement under customs control | `ACT` ss.5(1)(d), 79-88 |

**M5 Electronic Customs Systems and Declarations** — theory only per C7; the practical
track owns screens, and this module is where the boundary is tested hardest.
| Lesson | Anchor |
|---|---|
| 5.1 Access, roles and navigation in the customs electronic system | systems sheet · `ACT` ss.43-44 |
| 5.2 Unique Consignment References and declaration preparation | systems sheet · `ACT` ss.49, 50 |
| 5.3 Manifests, attachments, permits and electronic supporting documents | `ACT` ss.16, 17 · `CPC-GSA` · `CPC-FDA` |
| 5.4 Workflow statuses, validation, payment, release and record keeping | `ACT` ss.6-9, 71-73 |

**M6 MDA Requirements and Import Controls**
| Lesson | Anchor |
|---|---|
| 6.1 Regulatory coordination and electronic permit applications | `CPC-GSA` · `CPC-FDA` · institutions sheet |
| 6.2 Ghana Standards Authority import requirements and inspection | `CPC-GSA` · `GSA-NOTES` · legal sheet (LI 1541, LI 1586, LI 1932, NRCD 173) |
| 6.3 Food and Drugs Authority permits, inspection and release | `CPC-FDA` · `PHA` |
| 6.4 Managing multi-agency approvals, holds and discrepancies | `ACT` ss.37, 99 · `CPC-FDA` · `CPC-GSA` |

### Course 3 — Classification, Valuation, Origin and Duty (`intermediate`)

**M7 Harmonised System Classification**
| Lesson | Anchor |
|---|---|
| 7.1 Structure of the Harmonised System and the Ghana tariff | `TARIFF` · instruments sheet |
| 7.2 General Rules for Interpretation and legal notes | instruments sheet (verbatim GRI) |
| 7.3 Classification workflow, product descriptions and advance rulings | `ACT` s.12 · `TARIFF` |
| 7.4 Practical classification and resolving classification disputes | `TARIFF` · `TARIFF-24` (note the truncation caveat) |

**M8 Customs Valuation and Duty Calculation**
| Lesson | Anchor |
|---|---|
| 8.1 Transaction value and the hierarchy of valuation methods | `ACT` ss.67, 68 · `FULL DUTY CALCULATIONS - AKYA` (scan) |
| 8.2 CIF, FOB, assists, additions, deductions and exchange rates | `ACT` s.69 · `CPC-TT` |
| 8.3 Import duty, VAT, levies, fees and their tax bases | `ACT` ss.1, 2, 71, 72 · `TARIFF` columns |
| 8.4 Worked customs value and full-duty calculations | `FULL DUTY CALCULATIONS - AKYA` · `TARIFF` |

**M9 Rules of Origin and Trade Preferences**
| Lesson | Anchor |
|---|---|
| 9.1 Origin concepts, wholly obtained goods and substantial transformation | `ACT` s.70 · instruments sheet |
| 9.2 Preferential and non-preferential rules of origin | `AFU` · instruments sheet |
| 9.3 Certificates of origin and documentary evidence | `AFU` · `CPC-TT` |
| 9.4 Verification, denial of preference and origin disputes | `ACT` ss.7, 13 · `AFU` |

### Course 4 — Warehousing, Special Movements, Risk and Examination (`intermediate-advanced`)

**M10 Warehousing, Reliefs and Revenue Adjustments**
| Lesson | Anchor |
|---|---|
| 10.1 Customs warehousing, bonds, entries and removals | `ACT` ss.79-88 |
| 10.2 State warehouse, forfeiture, auction and allocation procedures | `ACT` ss.53, 93, 124-126 · `SPECIMEN` |
| 10.3 Exemptions, abatements, refunds and drawback | `ACT` ss.2, 104, 105, 106 |
| 10.4 Reconciliation, acquittal and control of duty relief | `ACT` ss.7, 9, 80 · securities ss.108-111 |

**M11 Transit, Transhipment and Free Zones**
| Lesson | Anchor |
|---|---|
| 11.1 Transit and transhipment concepts, routes and documentation | `ACT` ss.95, 96 · `CPC-TRANSIT` (scan) |
| 11.2 Guarantees, tracking, sealing, diversion risk and acquittal | `ACT` ss.108-111, 95 |
| 11.3 Free-zone legal framework, territoriality and approved operations | `ACT` s.94 · `CPC-FZ` (scan) |
| 11.4 Movements between free zones, the customs territory and foreign markets | `ACT` ss.94-96 · `CPC-FZ` (scan) |

**M12 Customs Risk Management and Examination**
| Lesson | Anchor |
|---|---|
| 12.1 Risk-management foundations, mandate and objectives | `ACT` s.3 · `CPC-RISK` |
| 12.2 Risk identification, analysis, evaluation and risk registers | `CPC-RISK` |
| 12.3 Risk profiles, indicators, intelligence and targeting | `CPC-RISK` |
| 12.4 Treatment decisions, physical examination and post-clearance follow-up | `ACT` ss.7, 101, 112-120 · `CPC-RISK` |

### Course 5 — Advanced Border Controls, Compliance and Professional Practice (`advanced`)

**M13 Special Goods and Advanced Border Controls**
| Lesson | Anchor |
|---|---|
| 13.1 Prohibited, restricted and conditionally permitted goods | `ACT` ss.37, 98, 99, 100 · legal sheet |
| 13.2 Public-health, standards and high-risk product controls | `PHA` · `CPC-FDA` · `CPC-GSA` |
| 13.3 Motor vehicles, used goods and specialised valuation issues | `ACT` ss.55-61 · `TIMETABLE` |
| 13.4 Duty-free shops, ship stores and controlled consumption | `ACT` ss.24, 90 · `CPC-DFS` (scan) |

**M14 Advanced Compliance and Case Management**
| Lesson | Anchor |
|---|---|
| 14.1 Records, audit trails and post-clearance audit | `ACT` ss.7, 9, 11 |
| 14.2 Amendments, cancellations, offences and administrative penalties | `ACT` ss.121-143 — **penalty amounts are amendment-sensitive, see C4.4** |
| 14.3 Advance rulings, objections, appeals and dispute management | `ACT` ss.12, 13 |
| 14.4 Complex multi-agency clearance and enforcement cases | `ACT` ss.124-127 · `CPC-RISK` · `CPC-FDA` |

**M15 Professional Customs Practice and Capstone**
| Lesson | Anchor |
|---|---|
| 15.1 Ethics, code of conduct and customs house agent management | `ACT` ss.43, 44 · `TIMETABLE` · legal sheet |
| 15.2 Client due diligence, advisory work and evidence management | `ACT` ss.9, 11, 14 |
| 15.3 Compliance programmes, intelligence use and continuous improvement | `ACT` ss.3, 8 |
| 15.4 End-to-end customs clearance capstone case | every anchor above, no new facts |

## Decisions Bernard must take before the waves run

1. **Length.** C2 sets 1,600–2,600 words and 5–7 concept blocks, about half the Logistics
   size. Confirm, or set a different band. This number multiplies by 60.
2. **Rates and deadlines.** C4 allows statutory deadlines and tariff rates to be stated
   as fact when they come from the supplied Act or tariff, each labelled for
   verification. The Logistics spec banned them outright. Confirm the relaxation — and
   whether penalty amounts stay banned (my recommendation: yes, banned, because
   Act 891 as supplied has five unapplied amendments).
3. **Scanned sources.** Six of the eighteen source files have no text layer. They can be
   read visually page by page, which is slow and costs a lot per lesson. Options: read
   them per lesson as needed, skip them and use the Act alone, or install Tesseract and
   batch-convert. Tell me which and I will not spend the budget guessing.
4. **Tariff edition.** The usable schedule is the 2017 base with the 2024 rate refresh
   differing on excise lines. Every duty figure in the curriculum inherits that
   uncertainty. Recommend: teach the structure and the arithmetic, cite one chapter
   (say 24 or an FMCG head) as the worked reference, and mark all figures
   "illustrative of the 2024 schedule".
5. **Module 5.** Kept in Course 2, written as theory per C7. Confirm you want it kept —
   removing it changes the shape to 14 modules and 56 lessons.

## Working agreements

- Titles are never reworded. Objectives and key terms are authored in the brief, then
  frozen: a drafting agent teaches them, it does not rewrite them.
- `FACTS & SOURCES` is mandatory in every draft, with an anchor key per claim.
- No database writes. Bernard enters approved content himself through the Theory Builder.
- One module per wave, QA clean before the next wave starts. Errata files per module,
  as in Logistics.
