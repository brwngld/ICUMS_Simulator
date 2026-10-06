# MDA × HS-code integration — agreed design (deferred)

Status: NOT YET IMPLEMENTED. Agreed with the product owner; implement after the
owner supplies the per-agency MDA lifecycle processes.

## 1. Deferred tweaks from the HS→MDA catalog (scenarios/views.py `HS_ANNEXED_REQUIREMENTS`)

- **Raw vs. processed food split** — chapter-level prefixes 02–03 currently call
  FDA for everything, including raw meat/fish that in practice may route to
  MoFA/PPRB instead of FDA. Fix: exclusion prefixes or finer sub-headings.
- **1704 → GSA** — kept from the original mapping (sugar confectionery is
  unusual for GSA); drop or move if the owner says so.

## 2. Where MDA requirements start — the Consignment Application (confirmed)

The Consignment Document application (`consignment_application.html`,
Confirmation tab, `{% if not mda_mode %}` block) renders a section titled
**MDA** with three GENERIC hardcoded rows — FDA, GSA, EPA — each with a
Create button (`data-mda-create`), regardless of the items' HS codes.
`static/js/application-form.js` (`makeMdaRow` / `showMdaRequest`) appends new
MDA rows at the BOTTOM of the table.

## 3. Agreed behavior once implemented

1. **HS-driven MDA rows.** The HS codes used in the application's items decide
   which MDA rows appear in that section (same prefix catalog as the BOE
   annexed documents — keep one shared source of truth). Generic rows go away:
   an agency appears only when an item's HS code calls for it; if no HS code
   calls for any agency, the section renders empty.
2. **New MDA rows on top.** When an MDA is added/created, its row moves to the
   TOP of the MDA table instead of the bottom.
3. **Keep the BOE annexed-document behavior as the safety net.** If the MDA
   that an HS code calls for was skipped at application stage, the BOE Item
   tab's annexed-document rule must still surface it (current behavior in
   `scenarios/views.py::_boe_annexed_documents` stays).
4. **BOE gating.** One of the major documents needed to create a BOE is the
   IDF. Even when an HS code calls for, say, GSA (and the IDF is MOTI), the
   learner can still CREATE the BOE — but cannot SUBMIT it until every
   HS-called MDA has been submitted, approved, and attached to the UCR
   (extend `boe_submit` / the Approval-save eDocument gate accordingly).

## 4. Open inputs from the product owner

- The process (status chain) each major MDA goes through — owner will supply
  later. IDF exists already (SU → auto-approve for MOTI/GSA) and will be
  polished later; FDA/EPA/GSA chains pending.
