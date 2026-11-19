# Ghana Electronic Customs Systems — Verified Fact Sheet

Last verified: 2026-11-19

Purpose: a source-checked reference for curriculum writers on the named Ghanaian
systems — ICUMS and the single-window approach — at the level the sources support.
This is the fact sheet the Module 4.2 and Module 5 briefs anchor their
named-system claims to (spec C4.6: named systems appear as the anchors and fact
sheets describe them; never invent a screen, a menu, a field name or a status
code; Module 5 is additionally theory-only per C7). The GRA pages were re-verified
on 2026-11-19; the 2026-10 verification from the Logistics fact sheet is carried
forward where unchanged. Items that could not be confirmed are in the final
**DO NOT CLAIM** section.

---

## 1. ICUMS — the Integrated Customs Management System

Verified facts:

- ICUMS stands for the Integrated Customs Management System and is described by
  the Ghana Revenue Authority as a single-window e-Customs platform for Ghana's
  international trade. (source: Ghana Revenue Authority,
  https://gra.gov.gh/customs/icums/ — verified 2026-10 and re-verified 2026-11-19)
- The GRA page dates the rollout to June 2020: "In June 2020, the Government of
  Ghana, Customs Division of the GRA, UNIPASS-Ghana and other well-meaning
  agencies joined up" to usher Ghana's trade to a single window system. (source:
  https://gra.gov.gh/customs/icums/ — re-verified 2026-11-19; use "2020" or
  "mid-2020", not the "28 April 2020" go-live date some sources give)
- ICUMS "came as a direct successor of the former Pre-Arrival Assessment Report
  System (PAARS) and the Ghana Customs Management System (GCMS)", which were
  managed by GCNet Ltd and West Blue Consulting. The stated motivation: high port
  transaction costs, delayed clearance, revenue leakage, and the burden of
  multiple online platforms for valuation, classification, risk management and
  payment. (source: https://gra.gov.gh/customs/icums/ — re-verified 2026-11-19)
- UNIPASS-Ghana is identified on the GRA page as the partner behind ICUMS; the
  GRA page's ICUMS link points to unipassghana.com. The company name "Ghana Link
  Network Services" does not appear verbatim on the fetched pages — background
  knowledge, not a quotable fact. (source: https://gra.gov.gh/customs/icums/)
- ICUMS's described capabilities: "allows users to create Unique Consignment
  Reference (UCR), an exclusive number for easy identification and tracking of all
  cargo"; processing of documents and payments through a single window; valuation,
  classification, risk management and payment on one platform; "end-to-end
  tracking which does not allow operators to tamper with figures"; and a "stand-by
  human resource management model that identifies officers assigned to a
  consignment". (source: https://gra.gov.gh/customs/icums/ — re-verified
  2026-11-19)
- The GRA page's ICUMS-related links: "Pay Customs Declaration" (via
  ghana.gov.gh), a Used Vehicle Duty Calculator and a General Goods Duty
  Calculator (both hosted on unipassghana.com), and an ICUMS Manual PDF. The
  manual's contents were not read. (source: https://gra.gov.gh/customs/icums/)

SAFE PHRASINGS:

- "ICUMS — the Integrated Customs Management System — is Ghana's single-window
  e-customs platform, operated under the UNIPASS arrangement in partnership with
  GRA Customs."
- "ICUMS replaced the earlier GCMS and PAARS systems, which were run by GCNet and
  West Blue Consulting."
- "In ICUMS a consignment is classified, valued, assessed and paid for on one
  platform, and every consignment carries a Unique Consignment Reference (UCR) —
  an exclusive number for identification and tracking."

## 2. The import-procedure flow as GRA states it

Verified facts:

- Under current import procedure, "the customs declaration is submitted in ICUMS
  by the clearing agent"; ICUMS generates the tax bill (covering classification,
  valuation and approval stages) and the importer pays duties and taxes at
  participating banks against that bill. (source: Ghana Revenue Authority,
  https://gra.gov.gh/customs/import-procedures/ — verified 2026-10, carried
  forward)
- The procedure requires permits "from any of the regulatory agencies, dependent
  on the type of goods", with the FDA and the GSA explicitly named. An Import
  Declaration Form (IDF) is obtained from the Ministry of Trade. (source:
  https://gra.gov.gh/customs/import-procedures/)
- GRA maintains a separate "Customs Tariffs and Levies" resource, confirming
  levies exist alongside duty; the individual levy names were not captured.
  (source: https://gra.gov.gh/customs/import-procedures/)

SAFE PHRASINGS:

- "The clearing agent lodges the declaration in ICUMS; ICUMS assesses and issues
  the tax bill; the importer pays at participating banks; permits from the
  regulatory agencies attach before release."

## 3. The single-window approach

Verified facts:

- GRA describes ICUMS as having moved Ghana's trade to "a single window system" —
  the single-window concept is now embodied in ICUMS. (source:
  https://gra.gov.gh/customs/icums/ — re-verified 2026-11-19)
- The Ghana Shippers' Authority is an active trade-facilitation stakeholder; its
  site links to regulatory agencies. (source: https://shippers.org.gh/ — verified
  2026-10)

Not verified: the "Ghana National Single Window" as a branded programme — its
introduction in 2015 and the reported ~2022 transfer of its operation to the
Ghana Shippers' Authority. The Shippers' Authority homepage fetched does not
mention the Single Window at all. Write "single window" as the lowercase concept
ICUMS embodies, not as a named programme with dates.

SAFE PHRASINGS:

- "Ghana operates a single-window approach to trade declarations: importers and
  agents lodge documents and payments through one system (ICUMS) rather than
  multiple platforms."

## 4. The UCR

Verified facts:

- "ICUMS … allows users to create Unique Consignment Reference (UCR), an
  exclusive number for easy identification and tracking of all cargo." (source:
  https://gra.gov.gh/customs/icums/ — re-verified 2026-11-19)
- The simulator's own modelling treats the UCR as the consignment's tracking
  identity from the Consignment Application onward (see section 6).

SAFE PHRASINGS:

- "Every consignment carries a Unique Consignment Reference (UCR) — ICUMS's
  exclusive number for identifying and tracking the cargo end to end."

## 5. What the sources do not describe (and Module 5 therefore may not teach)

The GRA pages describe ICUMS's capabilities at the function level. They do not
describe screens, menus, field names, role names, or workflow status codes. The
Module 5 briefs are bound by spec C7 (theory-only: no screens, menus, field
names) and C4.6 (named systems appear as the anchors and this sheet describe
them). The teachable content for Module 5 is:

- The Act's rules of the electronic environment: the electronic declaration, the
  electronic record and signature (s.151's definitions), the agent's
  written-authority duty (ss.43-44), the roles (declarant, agent, proper officer,
  Commissioner-General) by what each is legally entitled to do.
- The function-level facts this sheet verifies: one platform for valuation,
  classification, risk management and payment; the UCR as the tracking identity;
  the agent lodges; the tax bill is generated and paid at banks.
- The timetable deck's programme topics as the emphasis anchor.

## 6. As modelled in the owner's simulator

Accepted from the owner's own training simulator without external verification
(do not present as externally sourced facts):

- The clearance flow models a Consignment Application (the consignment's
  registration and UCR), a Bill of Entry (BOE) with annexed documents, an IDF
  document, and permit workflows for FDA, GSA and EPA.
- The simulator's dashboard, statuses and field names are the owner's design
  choices — useful for continuity between the curriculum's worked examples and the
  practical engine, but not evidence of how ICUMS itself works.

---

## DO NOT CLAIM

The following were NOT verified and must not appear in learner-facing material
without fresh sourcing:

- Any ICUMS screen, menu, button, field name, role name, or workflow status code.
  The GRA pages describe functions, not interfaces — and Module 5's C7 guard
  bans interface teaching regardless.
- The specific go-live date "28 April 2020" (the GRA page dates the rollout to
  June 2020; use "2020" or "mid-2020" only).
- "Ghana Link Network Services" as the verbatim operator name (only
  "UNIPASS-Ghana" was confirmed on GRA's page).
- The "Ghana National Single Window" as a branded programme: its 2015
  introduction, its reported 2022 transfer to the Ghana Shippers' Authority, or
  any other institutional history. Write "single window" as the concept.
- The ICUMS Manual's contents (the PDF exists on the GRA page; it was not read).
- The named line items of a duty assessment (VAT, NHIL, GETFund levy, ECOWAS
  levy, EXIM levy, AU import levy, special import levy, processing charges) —
  carried from the Logistics sheet's DO NOT CLAIM; the "Customs Tariffs and
  Levies" resource confirms levies exist, the names were not captured.
- Any duty, levy or fee rate; any payment deadline.
- The simulator's modelling presented as how ICUMS actually works.
