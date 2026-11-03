# Customs Curriculum Writing Specification

Binding contract for every lesson draft in `curriculum/customs/drafts/`.
Programme: **Customs Clearance and Compliance** (code `customs-clearance-and-compliance`),
5 courses × 3 modules × 4 lessons = 60 lessons, plus one module assessment per module.

This specification **inherits** `curriculum/WRITING_SPEC.md` (the Logistics contract) for
everything it does not override below. A drafting agent reads BOTH files, then this
lesson's brief, then the lesson's source anchors. Sections inherited unchanged:
§1 (file layout and block markers), §2 (how blocks render), §6 (MCQ shape), §7
(anti-repetition), §8 (prohibited items, except where overridden), §9 (spelling and usage),
§10 (deliverable and report), §11 (module assessments — 12 questions, 3 per lesson).

Sections **overridden** by this file: §3 (length and block counts), §4 (relatability),
§5 (fact-safety — reworked for a source-anchored curriculum). Bernard's instruction:
*"I don't need a lot of theories. I want them factual and relatable, both local and
international."*

## C1. What "factual, not theoretical" means in practice

Every Key Concept block must carry at least one **verifiable concrete**: a numbered
section of the Customs Act, a named document or form, a statutory time limit, a
defined term from the Act, an institution performing a named function, a tariff
row, an international instrument, or a real place. A block whose content is only
framing, background or conceptual scaffolding is a defect — merge it or cut it.

Target mix per lesson: roughly **two thirds operational fact, one third context**.
Context is the sentence or two that tells the learner why the fact matters at a
port or a border; it is not a section of its own.

Open a lesson with the thing itself, not with a preamble. Bad: "Customs plays a vital
role in the economic development of nations." Good: "Under section 4 of the Customs
Act, 2015 (Act 891), the Commissioner-General may designate an area as a
customs-controlled area. Goods that stay there more than fourteen days after being
entered, or after being sold at auction, are liable to forfeiture to the State."

## C2. Block counts and word bands (overrides §3)

- **5 to 7 Key Concept blocks**, each **120 to 250 words**.
- **2 to 3 Worked Example blocks**, each **200 to 400 words**.
- **1 to 2 Important Note blocks**, each **120 to 220 words**.
- Exactly **3 MCQs**, unchanged from §6.
- Lesson total (blocks only): **1,600 to 2,600 words.**

That is about half the Logistics length. It is deliberate: Customs content carries
statutes, documents and figures, so it does not need as much explanatory padding.

Block markers, headings, `POINTS: 1`, plain-text bodies, no markdown or HTML inside a
body — all exactly as Logistics §1. British spelling as §9.

## C3. Source anchors (new, and the core of this spec)

Each brief lists the lesson's anchors. **The anchor is the boundary of what you may
state as fact.** Available sources live in `output/docx/`:

| Anchor key | File | What it is |
|---|---|---|
| `ACT` | `Customs Act 2015 (2).pdf` | Act 891 of 2015, full text, ~200 sections |
| `PHA` | `Public-Health-Act-851 (1).pdf` | Public Health Act, 2009 (Act 851) |
| `CPC-LAW` | `CPC2026_Customs_Law.pdf` | GRA International Tax Office law deck |
| `CPC-TT` | `CPC2026_Shpping_and_INCOTERMS.pdf` | shipping, Incoterms |
| `CPC-GSA` / `GSA-NOTES` | `CPC2026_MDA - GSA(0).pdf`, `GSA NOTES.pdf` | standards, pattern approval, prohibitions |
| `CPC-FDA` | `CPC2026_MDA - FDA.pdf` | food and drugs controls |
| `CPC-RISK` | `CPC2026_Risk_Management.pdf`, `Risk Management.pdf` | risk management |
| `CPC-PORT` | `CPC2026_Role_of Port Operators (GPHA)-Sea.pdf` | port operators |
| `CPC-TRANSIT` | `Transit and Transhipment.pdf` | transit and transhipment (scanned) |
| `CPC-FZ` | `FREE ZONES (FZs).pdf` | free zones (scanned) |
| `CPC-DFS` | `DUTY-FREE SHOPS AND SHIP STORES.pdf` | duty-free and stores (scanned) |
| `TIMETABLE` | `CPC2026 COMPLETE TIMETABLE.pdf` | the 2026 proficiency programme's teaching topics |
| `TARIFF` | `output/docx/HSCODE/HS FINAL 2017-15-506.xlsx` | 5,886 Ghana TSN rows with CET, VAT and import-excision columns |
| `TARIFF-24` | `output/docx/HS CODE 2024 2.pdf` | the 2024 refresh, scanned |
| `AFU` | `body_gen-annex-and-specific-annexes.pdf` | African Union / continental agreement annexes |
| `SPECIMEN` | `output/docx/Auction-Allocation-Letter-SPECIMEN.pdf` | anonymised Form 80 allocation letter (training specimen) |

Text already extracted from the readable PDFs is in `.tmp/source-text/*.txt`; the six
scanned files must be read visually (render the page, read the image) or treated as
unavailable — say which you did in `FACTS & SOURCES`.

Where a lesson needs a fact that is **not** in its anchors, use `curriculum/customs/research/`
fact sheets, or verify with WebSearch against an authoritative source (official .gov.gh
site, WCO, WTO, IATA, ICC, UN/CEFACT). Failing both: write around it — describe the
function without naming the organisation, figure or deadline.

## C4. Numbers, rates and deadlines (overrides §5.1)

The Logistics rule "never state a rate or a deadline as fact" was right for a subject
with no source documents. It is wrong here: Bernard supplied the Act and the tariff,
and he wants factual content. So:

1. **Statutory time limits and thresholds may be stated** when taken from `ACT` or an
   agency deck, and must name the provision: "fourteen days … section 4(3) of Act 891".
2. **Duty, VAT and levy rates may be stated** only from `TARIFF` rows or a rate the
   lesson is explicitly working through, and each one must be labelled
   *illustrative of the structure, verify the rate in force* — because the supplied
   schedule is the 2024 refresh of a 2017 base and the two differ on excise lines.
   Never carry a rate from memory.
3. **Money in examples** is illustrative and the example says so, as in Logistics §5.1.
4. **Penalty and fine amounts**: Act 891 as supplied is "as at 18 May 2015" and its own
   front matter lists unapplied amendments (Act 923 of 2016, Act 949 of 2017, Act 957 of
   2017, Act 1014 of 2020, Act 1083 of 2022). Monetary penalties are exactly what such
   amendments move. State the offence and the mechanism; do **not** state a fine amount
   unless you verified the figure against the amending Act or the current schedule, and
   then cite which.
5. **Institutional facts** — who operates or regulates what — come only from an anchor,
   a fact sheet, or a verified authoritative source. Same rule as Logistics §5.2.
6. **Named Ghanaian systems** (ICUMS, the Ghana National Single Window) appear as the
   anchors and fact sheets describe them. Never invent a screen, a menu, a field name or
   a status code.
7. **Standards and instruments** (HS structure, GRI wording, Incoterms 2020 obligations,
   WCO frameworks) come from a fact sheet or the anchor deck, matched exactly, never
   paraphrased from memory.
8. **Distinguish** general international practice from Ghana-specific practice: write
   "in Ghana, …" only where an anchor supports it.
9. Do not invent statistics, dates, agreement names, case examples or quotations.
10. If a claim is not confident, verify it or cut it. A less specific example beats a
    plausible falsehood, and a cut claim beats a wrong one in a customs curriculum —
    because learners will repeat these numbers to clients.

Anything a learner might act on — a rate, a deadline, a form number, a licence
condition — must appear in `=== FACTS & SOURCES ===` as
`claim — anchor key + section/slide/row, or URL`.

## C5. Relatability (overrides §4)

- At least one Worked Example per lesson anchored in **Ghana practice**: Tema Port,
  Takoradi, Kotoka International Airport, Aflao, Paga, Elubo, the Tema oil jetties,
  a freight-forwarder's office in Accra, a CHA's desk at Tema. Use goods a Ghanaian
  trader actually clears — cement, frozen mackerel, rice, used vehicles, pharmaceuticals,
  cocoa, shea butter, timber, containerized FMCG, machinery and spare parts, LPG,
  poultry, second-hand clothing.
- At least one Worked Example or concrete reference per lesson that is **international
  and non-Ghanaian**: Rotterdam, Singapore, Jebel Ali, Antwerp, Hamburg, Shenzhen,
  Mombasa, Abidjan, Lagos, Durban, or a WCO/WTO instrument that applies everywhere.
  This is an international curriculum anchored in Ghana.
- Worked Examples are **step-by-step** (`Step 1`, `Step 2`, …) with real document names,
  real fields, real quantities, and the arithmetic shown, then close with
  "What does this example demonstrate?" and a one-line "Key lesson".
- Companies are generic or clearly illustrative ("Kwabena Trading Ltd", "a licensed
  customs house agent at Tema"). Never attach a factual claim to a real named company.
- Prefer the learner's point of view: what the person at the counter or the desk must
  have, do, check, or expect. Not what the state expects of them, unless the lesson is
  about enforcement.

## C6. Cross-references to the Logistics programme

Logistics explains **what a document is**; Customs explains **what the system must see
on it before it will proceed**. Do not re-teach the Logistics treatment. Where a Customs
lesson relies on it, the draft adds one line in the final Key Concept block in this shape
(the owner will create the link in the Theory Builder):

```
Reference: the packing list, the commercial invoice and the bill of lading are
introduced in the Logistics programme, module Logistics Documentation.
```

Write that line only where the brief's `Cross-reference` field says to.

## C7. Scope guard for Module 5 (Electronic Customs Systems and Declarations)

Module 5 is theory: the rules, the data and the reasons. The practical track owns the
screens. A Module 5 sentence that describes a click, a menu, a button or a field a learner
would type into has drifted into practical and must be rewritten as the underlying rule —
what the system requires, why, and what the consequence is.

## C8. Deliverable and report

Same as Logistics §10: write the file, self-review against the checklist (exact marker
syntax; block counts inside C2 bands; three MCQs whose `CORRECT:` numbers match their
explanation openers; every objective and key term from the brief taught; anchors cited
in `FACTS & SOURCES`; no prohibited content), then report **only** a short summary —
block counts, word count, one line per MCQ, and any claim a fact-checker should
scrutinise. Never paste lesson text into the report.

Structural QA after each module: `python curriculum/customs/tools/qa_customs.py`.
