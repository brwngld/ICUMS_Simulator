# Logistics & Supply Chain Management — Verified Frameworks Fact Sheet

**Last verified: 2026-10** (sources checked live this month; confidence marked per bullet).

Purpose: canonical reference for curriculum writers. Definitions are paraphrase-safe unless quoted. Recommended teaching wording is under "SAFE PHRASINGS" per topic.

---

## 1. Core definitions: logistics vs supply chain management

- CSCMP defines **logistics management** as "that part of supply chain management that plans, implements, and controls the efficient, effective forward and reverse flow and storage of goods, services, and related information between the point of origin and the point of consumption in order to meet customers' requirements." (source: CSCMP, https://cscmp.org/CSCMP/Educate/SCM_Definitions_and_Glossary_of_Terms.aspx) — high confidence.
- CSCMP defines **supply chain management (SCM)** as encompassing "the planning and management of all activities involved in sourcing and procurement, conversion, and all logistics management activities," including "coordination and collaboration with channel partners" (suppliers, intermediaries, third-party providers, customers); SCM "integrates supply and demand management within and across companies." (source: CSCMP, same URL) — high confidence.
- CSCMP's framing makes **logistics a subset of SCM** — teach this relationship. (source: CSCMP, same URL) — high confidence.
- CSCMP lists typical logistics activities: inbound/outbound transportation, fleet management, warehousing, materials handling, order fulfilment, network design, inventory management, supply/demand planning, and management of 3PL providers — plus, to varying degrees, sourcing, procurement, production planning, packaging/assembly, customer service. (source: CSCMP, same URL) — high confidence.
- **Inbound logistics** = supplier flows into a business; **outbound logistics** = finished goods flows to customers; **reverse logistics** = flows back toward origin (returns, repairs, recycling, disposal). CSCMP's definition explicitly covers "forward and reverse flow," so reverse logistics sits inside logistics management. (source: CSCMP, same URL; inbound/outbound phrasing from industry usage) — high confidence (umbrella); medium (inbound/outbound labels).
- **Third-party logistics (3PL)**: outsourcing of logistics functions — transport, warehousing, forwarding, pick-and-pack — to an external provider acting between seller and buyer. (source: Wikipedia "Third-party logistics", https://en.wikipedia.org/wiki/Third-party_logistics) — high confidence.
- **Fourth-party logistics (4PL)**: an asset-light integrator (lead logistics provider) owning no transport/warehouse capacity; it selects, manages and integrates multiple 3PLs and technology to run the client's supply chain. The term is widely attributed to Accenture. (source: Wikipedia "Third-party logistics", same URL; year of coinage conflicts across sources — teach no year) — medium confidence.
- **Freight forwarder**: intermediary arranging international shipment for shippers — booking carriage, consolidating cargo, preparing documentation — without usually operating the vessels/aircraft. (source: standard industry usage; secondary sources) — medium confidence (uncontroversial, no primary source).
- **Customs broker**: licensed agent clearing goods through customs for importers/exporters — declarations, classification, duties; licensing varies by country. (source: general usage, e.g., US CBP licence model) — medium confidence.
- **Green logistics**: reducing logistics' environmental impact (emissions, energy, waste) via cleaner modes, load optimisation, packaging reduction. **Cold-chain logistics**: temperature-controlled storage/transport for perishables and pharma with continuous monitoring. (labelled concepts; qualitative) — high confidence.

### SAFE PHRASINGS — Definitions
- "Logistics management plans, implements and controls the efficient forward and reverse flow and storage of goods, services and related information between origin and consumption, to meet customers' requirements. It is the part of supply chain management that does this."
- "SCM is broader than logistics: it adds sourcing, procurement and conversion, plus coordination with channel partners within and across companies."
- "A 3PL operates logistics for you; a 4PL integrates and manages the whole network — including the 3PLs — and typically owns few or no assets."
- "Reverse logistics moves goods backwards — customer to seller or recycler — and is part of logistics, not an exception to it."

---

## 2. The Seven Rights (7 Rs) of logistics

- Widely taught formulation: the **right product**, in the **right quantity**, in the **right condition**, at the **right place**, at the **right time**, to the **right customer**, at the **right price**. (source: textbook/industry convention — medium confidence: a convention, not a standard; no canonical author)
- Variants exist: the older "5 Rights" of purchasing (quality, quantity, time, place, price); some lists add "right documentation" or merge price into "right cost". Pick one list and use it consistently. (medium confidence)

### SAFE PHRASINGS — 7 Rs
- "Logistics succeeds when the right product reaches the right customer, in the right quantity and condition, at the right place and time, at the right price. Miss any one and the delivery is a service failure."
- "You may meet five-R or eight-R versions elsewhere; this course uses the seven-R list above."

---

## 3. Procurement and the order-to-receipt flow

- Standard flow: internal **purchase requisition** (approved) → **purchase order (PO)** to supplier → supplier ships, often with an **advance ship notice (ASN)** → buyer **goods receipt** (checked against PO) → supplier **invoice** → payment after matching. (source: general practice; consistent with EDI flows in IBM/vendor documentation) — high confidence.
- **Three-way match**: PO + goods receipt note + supplier invoice agree (quantities, prices) before payment is released; discrepancies investigated first. (source: standard accounting/procurement control) — high confidence (concept); tolerances vary by company (medium).
- The EDI mirror of the flow is 850 → 855 → 856 → 810 (section 9). — high confidence.

### SAFE PHRASINGS — Procurement
- "Requisition, then purchase order, then goods receipt, then invoice — and payment only when PO, receipt and invoice all agree. That check is the three-way match."

---

## 4. Warehousing

- Core functions: **receiving, put-away/storage, order picking, packing, dispatch**, plus **returns processing** and **value-added services** (labelling, kitting, light assembly). (source: standard warehouse practice; Wikipedia "Warehouse management system", https://en.wikipedia.org/wiki/Warehouse_management_system) — high confidence.
- Typical zones: **receiving dock, reserve storage, forward picking area, packing, dispatch/marshalling**, plus a returns/quarantine area. (source: standard design practice) — medium confidence (convention).
- Standard flow: **receiving → put-away → picking → packing → dispatch**; returns run as a separate reverse flow. (source: standard practice) — high confidence.
- **Picking methods**: **discrete** (one order per picker pass), **batch** (several orders per pass), **zone** (pickers in zones, orders passed on), **wave** (orders released in scheduled groups aligned to shipping/carrier cut-offs). (source: industry taxonomy) — medium confidence (standard, but batch/wave boundaries vary in practice).
- **Cross-docking**: goods move from receiving dock directly to shipping dock with little or no storage; the Material Handling Industry of America defines it as moving goods "from the receiving dock to shipping for shipping without placing it first into storage locations"; dwell typically under 24 hours. (source: Wikipedia "Cross-docking" quoting MHIA, https://en.wikipedia.org/wiki/Cross-docking) — high confidence.
- **WMS core function**: recording the arrival and departure of inventory, with supporting functions for location tracking, space use, task coordination, and analysis of capacity, stock and labour, and system integration (e.g., APIs). (source: Wikipedia "Warehouse management system") — high confidence (core); medium (extended list).

### SAFE PHRASINGS — Warehousing
- "A warehouse receives, stores, picks, packs and dispatches — and often also handles returns and value-added services."
- "Cross-docking takes goods from the inbound truck straight to the outbound truck, normally within 24 hours, skipping storage."
- "A WMS is the system of record for what enters, where it sits, and what leaves the warehouse."

---

## 5. Inventory management

- **FIFO**: oldest stock issued first — default physical policy, required for perishables. **FEFO**: earliest expiry date issued first — the correct rule where shelf life matters, even if arrival order differs. **LIFO**: newest first; as physical flow it suits few goods — teach it chiefly as an **accounting** cost-flow method associated with US GAAP, **not permitted under IFRS (IAS 2)**. (source: accounting convention; IAS 2 prohibition is standard accounting knowledge — medium confidence, re-check IFRS text if teaching in depth)
- **ABC analysis**: classifying items by value contribution — A (few items, most value), B (middle), C (many items, little value) — an application of the Pareto (80/20) principle; used to set control and count frequency. (source: Wikipedia "Cycle count" describing ABC as the most common counting approach using the Pareto principle, https://en.wikipedia.org/wiki/Cycle_count) — high confidence.
- **Safety stock**: buffer against demand and lead-time variability so service holds when actuals exceed expectations. (concept) — high confidence; statistical formulas vary by text — teach none as universal.
- **Reorder point**: inventory level that triggers replenishment; **ROP = expected demand during lead time + safety stock**; simplified: ROP = average daily usage × lead time in days. (source: Wikipedia "Reorder point", https://en.wikipedia.org/wiki/Reorder_point) — high confidence.
- **Economic order quantity (EOQ)**: classic model for order size minimising total ordering + holding cost: **Q* = sqrt(2DS/H)** — D = annual demand, S = fixed cost per order, H = annual holding cost per unit. Teach as the classic textbook model with strong simplifying assumptions: constant demand, full delivery at zero stock, fixed order cost, no quantity discounts or stockouts. (source: Wikipedia "Economic order quantity", https://en.wikipedia.org/wiki/Economic_order_quantity) — high confidence.
- **Service level**: target probability of no stockout (or share of demand met from stock — the two common definitions; pick one). Higher targets need disproportionately more safety stock. (concept) — high confidence.
- **Inventory turnover** = COGS ÷ average inventory. **Days of supply** = average inventory ÷ average daily usage (≈ 365 ÷ turns when usage aligns with COGS). (source: standard convention) — medium confidence (state the denominator used).
- **Cycle counting**: counting a subset of items on a continuous, rotating schedule (A-items most often, via ABC), instead of a full annual physical count; less disruptive, supports root-cause correction. (source: Wikipedia "Cycle count", https://en.wikipedia.org/wiki/Cycle_count) — high confidence.
- **Stock reconciliation**: compare system vs physical stock; investigate discrepancies (mis-picks, unrecorded moves, theft, unit-of-measure errors) before adjusting records. (standard practice) — high confidence (concept).

### SAFE PHRASINGS — Inventory
- "FIFO issues the oldest stock first; FEFO issues the stock that expires first; LIFO is an accounting method — under IFRS it is not allowed."
- "Reorder point = demand expected during the lead time + safety stock."
- "EOQ — square root of 2DS over H — is the classic textbook answer for order size; it assumes steady demand and fixed costs, so treat it as a model, not a law."
- "Inventory turnover is COGS over average inventory; days of supply divides average inventory by average daily usage."

---

## 6. Transport operations and economics

- **Cost trade-off**: total logistics cost balances transport cost against inventory cost — slower, cheaper modes raise in-transit and cycle inventory; faster modes cost more per unit but cut inventory and stockouts. (source: standard total-cost principle) — high confidence as principle; medium on any number.
- **Consolidation**: **FTL** dedicates a trailer to one shipper — faster, direct, less handling; **LTL** combines several shippers' freight in one trailer — cheaper per unit, more handling, longer transit; **groupage** is the European consolidation term. LTL carriers typically run hub-and-spoke terminal networks. (source: Wikipedia "Less than truckload shipping", https://en.wikipedia.org/wiki/Less_than_truckload_shipping) — high confidence.
- **Milk run**: fixed, repeated circular route with multiple pickup/drop-off stops, consolidating small loads (term from dairy collection routes). (source: Wikipedia "Milk run", https://en.wikipedia.org/wiki/Milk_run) — high confidence.
- **Hub-and-spoke vs point-to-point**: hub networks consolidate all flows through central hubs (fewer connections to operate, longer transit); point-to-point serves pairs directly (faster, needs volume per pair). (source: standard network-design convention) — high confidence as concept.
- **Route planning**: sequencing stops to minimise distance/time/fuel under capacity, time-window and driver-hours constraints (the vehicle-routing problem family). (concept) — high confidence.
- **Multimodal transport**: carriage by at least two modes **on the basis of a single multimodal transport contract**, one multimodal transport operator (MTO) responsible end-to-end even where sub-carriers haul. The 1980 UN Convention on International Multimodal Transport of Goods (Geneva, 24 May 1980) uses this definition — but the Convention never entered into force (6 ratifications vs 30 required as of 2019): teach the definition, not the Convention as live law. (source: Wikipedia "Multimodal transport", https://en.wikipedia.org/wiki/Multimodal_transport) — high confidence.
- **Intermodal transport**: goods travel in **one and the same loading unit** (container, swap body) across two or more modes without handling the goods. Common usage contrast: intermodal stresses the unchanged loading unit (often separate contract per leg); multimodal adds the single contract and end-to-end responsibility. Bodies (OECD/ECMT/UN) differ slightly — state the distinction as above, not as hard law. (source: Wikipedia "Intermodal freight transport", https://en.wikipedia.org/wiki/Intermodal_freight_transport) — medium-high confidence.
- **Empty running**: travelling without paying cargo — a major cost and emissions inefficiency; cut via backhaul matching and network design. **Backhaul**: the return leg, ideally carrying paying cargo. (concepts) — high confidence; no universal percentages (see DO NOT CLAIM).

### SAFE PHRASINGS — Transport
- "Multimodal = two or more modes, one contract, one operator responsible end to end. Intermodal = the goods stay in the same container across modes; each leg may have its own contract."
- "FTL rents the whole truck to one shipper; LTL and groupage share it — cheaper, but more handling."
- "A milk run is one vehicle on a fixed loop collecting from several suppliers — small loads consolidated into one route."

---

## 7. Performance measurement

- **OTIF (On-Time In-Full)**: percentage of orders delivered both on time (promised date/window) and in full (complete, correct); strict OTIF fails an order that is late *or* short. **OTIF % = (on-time-in-full deliveries ÷ total deliveries) × 100.** (source: MetricHQ, https://www.metrichq.org/supply-chain/on-time-in-full) — high confidence.
- **Perfect order rate**: extends OTIF with damage-free **and** correct documentation/invoicing; some conventions multiply component success rates. (source: industry usage, secondary sources) — medium confidence on exact components.
- **Order cycle time**: order receipt → delivery. **Dock-to-stock time**: arrival at receiving dock → stock pickable. (standard KPIs) — high confidence as concepts; medium on benchmarks.
- **Inventory accuracy %**: share of counted locations/SKUs matching the system record within tolerance — the output measure of cycle counting. (standard) — high confidence (concept).
- **Freight cost per unit / per tonne-km**: spend ÷ units shipped, or cost per tonne moved per kilometre — the standard mode/lane comparator. (standard) — high confidence (concept).
- **Capacity utilisation**: share of available vehicle/container/warehouse capacity actually used — core efficiency lever for cost and emissions. (standard) — high confidence (concept).
- **Claims/damage ratio**: damage/loss claims as share of shipments or freight spend. (standard usage) — medium confidence on any typical values.
- **Forecast accuracy**: **MAPE** = average of |actual − forecast| ÷ |actual| × 100 (fragile near zero actuals); **MAD** = average of |actual − forecast| in demand units. Standard textbook measures. (source: standard forecasting texts) — high confidence.
- **Lead time**: order (or trigger) to receipt; components include order processing, production/pick-pack, handling, transport, and customs clearance internationally. (standard) — high confidence (concept).

### SAFE PHRASINGS — Performance
- "OTIF counts only orders both on time and complete — early but short still fails."
- "The perfect order adds damage-free and correctly documented/invoiced to on-time and in-full."
- "MAPE expresses forecast error as an average percentage; MAD keeps it in demand units."
- "Lead time is not just transport — it includes order processing, preparation, transit and, across borders, customs."

---

## 8. Planning

- **Forecasting families**: qualitative — **market survey** (structured customer/channel expectations), **Delphi** (iterated anonymous expert panels); quantitative time series — **moving average** (mean of last n periods), **exponential smoothing** (weights recent data more), **regression/causal** (demand explained by driver variables). (source: standard forecasting texts) — high confidence as families; medium on comparative accuracy.
- **S&OP**: a cross-functional, typically monthly process combining demand forecasting with supply planning so sales, operations, inventory and finance work from one set of assumptions; product-family/aggregate level, horizon up to ~18 months; cycle of data review, demand plan, supply plan, pre-meeting, executive meeting. APICS defines it as setting overall output levels to satisfy planned sales while meeting profitability/productivity objectives; the modern process is generally attributed to Richard Ling (Oliver Wight), 1980s. (source: Wikipedia "Sales and operations planning", https://en.wikipedia.org/wiki/Sales_and_operations_planning) — high confidence.
- **Push vs pull**: push executes against forecasts; pull executes against actual demand. Real chains are usually hybrid (push to a decoupling stock point, pull after). (concept) — high confidence.
- **MRP**: time-phased orders for dependent-demand components from master schedule, bills of material, inventory records. **DRP**: same time-phased logic applied to replenishing distribution centres. (standard concepts) — high confidence.
- **Network design**: number/location of DCs is a cost-vs-service trade-off — more/deeper networks cut delivery time and outbound transport but add facility and inventory cost; centralised networks do the reverse. (concept) — high confidence.
- **Bullwhip effect**: order variability amplifies upstream — orders to suppliers swing more than sales to buyers. Lee, Padmanabhan and Whang (1997) established the standard four causes: **demand signal processing (forecast updating), order batching, price fluctuations, rationing/shortage gaming**. Countermeasures: information sharing (POS data), smaller/more frequent orders, vendor-managed inventory. (source: Wikipedia "Bullwhip effect", https://en.wikipedia.org/wiki/Bullwhip_effect) — high confidence.
- **Postponement (delayed differentiation)**: keep the product generic; defer final configuration (dyeing, labelling, local packaging, final assembly) until real demand is known — Benetton's late-dyed sweaters; in-store paint mixing. Suited to high demand uncertainty. (source: Wikipedia "Delayed differentiation", https://en.wikipedia.org/wiki/Delayed_differentiation) — high confidence.

### SAFE PHRASINGS — Planning
- "S&OP is the monthly meeting where sales, operations and finance agree one plan — one demand number, one supply answer, one financial view."
- "The bullwhip effect: small changes in customer demand become bigger swings in orders upstream — caused by forecast updating, order batching, promotions and shortage gaming."
- "Postponement means finish the product as late as possible, when you actually know who wants what."

---

## 9. Technology

- **WMS**: system of record for warehouse inventory movement (see section 4). (source: Wikipedia "Warehouse management system") — high confidence (core).
- **TMS**: plans and executes transport — mode/route selection, carrier selection and rating, tendering, tracking, freight audit/settlement, increasingly emissions reporting. (source: industry-standard scope; secondary sources) — medium confidence on any product's exact features.
- **ERP**: integrated transactional backbone across finance, procurement, sales, inventory, production; WMS/TMS either extend ERP modules or integrate with them. — high confidence (concept).
- **Yard management**: managing trailers/vehicles in the yard — gate check-in, parking positions, dock scheduling, move tracking (often a YMS linked to WMS/TMS). (industry usage) — medium confidence.
- **EDI**: "the computer-to-computer exchange of structured business documents in standardized electronic formats between organizations" (trading partners). (source: Wikipedia "Electronic data interchange", https://en.wikipedia.org/wiki/Electronic_data_interchange) — high confidence.
- **ANSI ASC X12** dominates North American EDI. Widely used sets: **850 Purchase Order**, 855 PO Acknowledgement, **856 Advance Ship Notice (ASN)** — confirmed in IBM's standards documentation — **810 Invoice**; the 850 → 855 → 856 → 810 sequence is the standard teaching example. (source: IBM docs, https://www.ibm.com/docs/en/b2bis?topic=standards-856-advance-shipment-notice; vendor guides) — high confidence.
- **UN/EDIFACT**: the international EDI standard developed for the UN, published by UNECE, approved as **ISO 9735** (1987), maintained by **UN/CEFACT**. Common messages: **ORDERS** (purchase order), **DESADV** (despatch advice — the ASN counterpart), **INVOIC** (invoice). (source: Wikipedia "EDIFACT", https://en.wikipedia.org/wiki/EDIFACT) — high confidence.
- **APIs**: the modern alternative/supplement to EDI — real-time, system-to-system integration (visibility platforms, e-commerce, carrier booking), easier to change than batch EDI. (qualitative) — high confidence as trend.
- **GS1 identification**: **GTIN (Global Trade Item Number)** identifies a trade item at any packaging level — it is the number *encoded in* barcodes, not the barcode itself. **SSCC (Serial Shipping Container Code)**: "an 18-digit number used to identify logistics units" (pallets, containers); structure: extension digit + GS1 company prefix + serial reference + check digit; encoded typically in GS1-128 or RFID; a key ASN data element. (source: Wikipedia "Serial shipping container code", https://en.wikipedia.org/wiki/Serial_shipping_container_code; GS1) — high confidence.
- **RFID**: contactless identification of tagged pallets/cartons/assets by radio, no line of sight needed; complements barcodes where bulk or portal reads add value. — high confidence (concept).
- **Track-and-trace**: seeing where a shipment is and what has happened to it via scan/status events. **IoT telematics and cold-chain sensors**: GPS position, fuel, driver behaviour, temperature/humidity in near-real time, enabling cold-chain excursion alerts. (qualitative) — high confidence (concepts).
- **e-AWB**: IATA's e-Air Waybill programme (with the multilateral e-AWB Agreement) removes the requirement for paper AWB issuance. Background: the AWB is the carrier's receipt and evidence of the contract of carriage and is **not a document of title** (non-negotiable), unlike an ocean bill of lading. (source: Wikipedia "Air waybill", https://en.wikipedia.org/wiki/Air_waybill) — high confidence.
- **MLETR**: **UNCITRAL Model Law on Electronic Transferable Records**, adopted 13 July 2017; enables legal use of electronic transferable records (e.g., electronic bills of lading) on three principles — non-discrimination of electronic means, functional equivalence with paper, technology neutrality; "control" is the electronic equivalent of possession. The key legal enabler cited for e-B/L; adoption counts change — point learners to UNCITRAL's status page. (source: UNCITRAL, https://uncitral.un.org/en/texts/ecommerce/modellaw/electronic_transferable_records) — high confidence.
- **Port Community Systems (PCS)**: neutral digital platforms where all public and private stakeholders in a port/airport community exchange shipment information through one trusted platform; promoted internationally by IPCSA. (source: IPCSA's published framing — medium confidence: site unreachable during verification)
- **National Single Window**: one national entry point where trade parties submit standardised information/documents once to satisfy all regulatory requirements; UN/CEFACT Recommendation No. 33 is the usual reference. (medium confidence)
- **Ghana anchor**: Ghana customs clearance runs on **ICUMS (Integrated Customs Management System)** — an end-to-end e-customs platform at all ports of entry and exit, implemented under the UNIPASS contract (Ghana Link Network Services), rolled out from 28 April 2020, replacing GCNet and West Blue; GRA describes it as coordinating cross-border trade, cutting stakeholder costs and supporting revenue. (source: Ghana Revenue Authority, https://gra.gov.gh/customs/icums; Imani Africa, April 2020) — high confidence.
- **AI/ML uses** (qualitative, no performance claims): demand forecasting, ETA prediction, document OCR/extraction, anomaly detection in track-and-trace. — high confidence as trend.
- **Blockchain in trade documentation** (qualitative, caution): promise — shared tamper-evident records for B/Ls and certificates; reality — MLETR-style legal reform and neutral platforms have mattered more so far; adoption is partial. Teach promise-vs-reality. (medium confidence)

### SAFE PHRASINGS — Technology
- "EDI is computers trading standard electronic documents — X12 in North America (850 order, 856 ship notice, 810 invoice), UN/EDIFACT internationally (ORDERS, DESADV, INVOIC)."
- "The GTIN identifies the product; the SSCC identifies the pallet or container it travels on — the item versus the logistics unit."
- "MLETR is the UNCITRAL model law (2017) letting an electronic bill of lading do what a paper one does — legal recognition, functional equivalence, technology neutrality."
- "A port community system is the port's shared digital post office: every party exchanges shipment data through one neutral platform."

---

## 10. Strategy and contracts

- **Make-vs-buy / outsourcing**: weigh cost, capability, control, demand variability, and strategic importance; 3PL/4PL (section 1) are the usual vehicles. (concept) — high confidence as framework.
- **3PL selection criteria** (typical): service scope fit, geographic coverage, track record/references, IT and visibility integration, cost model, compliance/insurance/security, scalability and cultural fit. (industry practice) — medium confidence (teach as checklist, not canon).
- **SLA components** (typical): scope of services; KPIs with targets (OTIF, dock-to-stock, inventory accuracy); measurement and reporting cadence; remedies/service credits; governance and review cycle; exit/transition terms. (industry practice) — medium confidence on any fixed structure; teach as components.
- **Spot vs contract rates**: spot = one-off price at current market; contract = agreed rates for committed volume/period (often indexed). Shippers typically blend both — core lanes on contract, peaks on spot. (standard freight-market usage) — high confidence (concepts).
- **Incoterms and service scope**: Incoterms 2020 (ICC; 11 rules — any mode: EXW, FCA, CPT, CIP, DPU, DAP, DDP; sea/inland waterway only: FAS, FOB, CFR, CIF) allocate tasks, costs and risk-transfer points between buyer and seller, determining who buys carriage, insurance and clearance. Incoterms do not transfer ownership, fix price, or themselves constitute a carriage contract; ICC trademark. (source: Wikipedia "Incoterms", https://en.wikipedia.org/wiki/Incoterms) — high confidence.

### SAFE PHRASINGS — Strategy
- "Outsource when the market can do it better or cheaper and it is not your strategic core."
- "An SLA says what service is bought, how it is measured, what happens when it is missed, and how either side exits."
- "The Incoterms rule in the sales contract decides who arranges and pays for transport, insurance and clearance — and where risk passes."

---

## 11. Risk and resilience

- **Risk management cycle**: identify → assess (likelihood × impact) → mitigate/treat → monitor and review, with communication throughout; mirrors the ISO 31000 process structure. (medium confidence on exact stage names; teach as a four-step loop)
- **Risk categories** (teaching taxonomy): supply-side, transport, customs/regulatory, financial, security, natural. (common taxonomy) — medium confidence; categories uncontroversial.
- **Business continuity planning (BCP)**: documented, tested plans for continuing/recovering operations after disruption — alternate suppliers, routes, sites, decision authority. (concept) — high confidence.
- **Resilience strategies** (standard set): dual/multi-sourcing, buffer stock, end-to-end visibility, flexibility (alternative modes/routes), supplier development. (resilience literature) — high confidence as a set.
- **Verified disruption examples** (use these exact facts):
  - **COVID-19 port congestion**: from early 2020 through roughly 2021–2022 — demand shifts, labour disruptions, vessel/container imbalances, record freight rates on major lanes. Keep timing broad; no single end date. — high confidence (qualitative); medium on magnitude.
  - **Ever Given / Suez Canal**: ran aground 23 March 2021, freed 29 March 2021 — canal blocked **six days and seven hours**; at least 369 vessels waiting by 28 March, over 400 by reopening. (source: Wikipedia "2021 Suez Canal obstruction", https://en.wikipedia.org/wiki/2021_Suez_Canal_obstruction) — high confidence.
  - **Red Sea disruptions**: from 19 October 2023 the Houthis (Ansar Allah) attacked shipping in the Red Sea/Gulf of Aden; from **December 2023** major container lines widely rerouted around the Cape of Good Hope, substantially lengthening Asia–Europe voyages. (source: Wikipedia "Red Sea crisis", https://en.wikipedia.org/wiki/Red_Sea_crisis) — high confidence on dates; medium on voyage-length percentages.

### SAFE PHRASINGS — Risk
- "Manage risk as a loop: identify what could go wrong, assess likelihood and impact, mitigate what matters, monitor — and repeat."
- "Three disruptions to remember: COVID-19 congestion 2020–2022; the Ever Given closing the Suez Canal for six days in March 2021; Red Sea attacks from late 2023 pushing mainline carriers around the Cape of Good Hope."

---

## 12. Sustainability

- **GHG Protocol** (developed by WRI and WBCSD): **Scope 1** = direct emissions from sources the company owns or controls (e.g., own vehicles); **Scope 2** = indirect emissions from purchased electricity, steam, heat, cooling; **Scope 3** = other indirect emissions across the value chain (e.g., purchased transport). (source: GHG Protocol Corporate Standard, https://ghgprotocol.org/corporate-standard) — high confidence.
- **Transport emissions intensity by mode — directional claim (verified)**: per tonne-km, **sea < rail < road < air**. Verified via energy intensity (emissions scale with fuel burned): ocean ≈ 0.09 MJ/t-km, rail ≈ 0.33, road ≈ 1.21, air ≈ 9.77 (Deutsche Bahn 2018, compiled in Wikipedia "Energy efficiency in transport", https://en.wikipedia.org/wiki/Energy_efficiency_in_transport); air roughly 30–100x sea in that dataset. — high confidence on the ordering; medium on numbers.
- **Levers** (concepts, all high confidence): **modal shift** to lower-intensity modes; **load factor improvement**; **empty-run reduction**; **packaging optimisation** (lighter, right-sized, reusable); **reverse logistics** for returns/refurbishment/recycling.
- Regional regulatory schemes (e.g., EU CSRD, ETS): name them only as clearly regional examples; never present as global requirements. (guidance)

### SAFE PHRASINGS — Sustainability
- "Scope 1 is what you burn yourself; Scope 2 is the energy you buy; Scope 3 is everyone else in your value chain — including freight you outsource."
- "Per tonne-kilometre, sea is lowest-emitting, then rail, then road, with air by far the highest — which is why modal shift matters."

---

## 13. Ethics and continuous improvement

- **Facilitation payments vs bribes**: a facilitation ("grease") payment expedites a routine, non-discretionary action whose outcome is already fixed — it changes timing, not the decision. The US FCPA treats payments for "routine governmental action" as a narrow exception; the **UK Bribery Act 2010 recognises no exemption** (they can be unlawful there). Many multinational codes nonetheless prohibit both bribes and facilitation payments. In freight and customs (clearance, inspections, permits) this is a core integrity risk — teach the distinction and the stricter company-policy standard. (source: Wikipedia "Facilitating payment", https://en.wikipedia.org/wiki/Facilitating_payment) — high confidence.
- **Incoterms/document fraud awareness** (qualitative): trade-document manipulation, false origin/value declarations, and misuse of delivery terms create fraud and compliance exposure — teach controls (document checks, three-way match, approved carrier/broker lists), not specific allegations. — high confidence as risk framing.
- **PDCA**: Plan–Do–Check–Act, the Deming/Shewhart cycle — plan a change, do it small-scale, check results, act to standardise or adjust, repeat. (standard quality management) — high confidence.
- **Lean thinking**: maximise customer value by systematically eliminating waste — overproduction, waiting, unnecessary transport, excess inventory, defects, over-processing, unused talent. (standard lean literature) — high confidence (concept).
- **5S**: workplace organisation in five steps — **Sort, Set in order, Shine, Standardize, Sustain** (seiri, seiton, seiso, seiketsu, shitsuke); developed in Japan, associated with just-in-time manufacturing (Osada; Hirano). (source: Wikipedia "5S (methodology)", https://en.wikipedia.org/wiki/5S_(methodology)) — high confidence.
- **Kaizen**: continuous incremental improvement involving everyone — small frequent changes, standardised when they work. (standard) — high confidence (concept).

### SAFE PHRASINGS — Ethics & CI
- "A facilitation payment speeds up something you are already entitled to; a bribe changes the decision. Many company codes ban both — and in some jurisdictions, like the UK, facilitation payments are unlawful too."
- "PDCA is the loop — plan, do, check, act; 5S gives every workplace a standard: sort, set in order, shine, standardize, sustain."

---

## DO NOT CLAIM

1. **Exact g-CO2 per tonne-km per mode as universal constants.** The ordering sea < rail < road < air is verified; precise factors vary by vehicle, load factor, fuel and methodology (tank-to-wheel vs well-to-wheel). Give the ordering and indicative magnitudes only.
2. **"Intermodal = single contract."** The classic reversal. Single contract + one responsible operator = multimodal; intermodal stresses the same loading unit across modes, often separate contracts.
3. **LIFO as standard warehouse practice.** It is an accounting cost-flow method (US GAAP association; not permitted under IFRS); physical goods run FIFO/FEFO.
4. **A year for the invention of 4PL.** Sources conflict; say only "widely attributed to Accenture".
5. **The 7 Rs as a formal standard.** It is a teaching convention with variants. Present one consistent list; cite no standards body.
6. **Ever Given trade-loss figures** (e.g., "$9.6 billion per day"). Widely quoted, not reliably verified. Verified: aground 23 March 2021, freed 29 March 2021, six days seven hours, 369+ vessels queued.
7. **A single end date for COVID-19 congestion, or precise pandemic rate multiples.** Keep it qualitative: 2020 through 2021–2022.
8. **One canonical percentage for Red Sea voyage/capacity changes.** Rerouting is verified; exact voyage-length increases vary by lane.
9. **Universal OTIF benchmarks or specific retailer OTIF policies** as teaching facts — program-specific and time-bound.
10. **ROI/savings percentages for WMS, TMS, AI, blockchain or IoT.** Vendor-dependent; teach functions, not returns.
11. **"The air waybill is a document of title."** False — the AWB is a receipt and evidence of contract of carriage, non-negotiable; the ocean bill of lading is the document of title.
12. **"Incoterms transfer ownership" or "are the contract of carriage."** They allocate tasks, costs and risk points; they do not transfer title, set price, or constitute carriage contracts.
13. **"GTIN is a barcode."** GTIN is the number; barcodes (GS1-128, EAN/UPC) are ways to encode it.
14. **"EDIFACT is obsolete" or "X12 is the global standard."** X12 dominates North America; EDIFACT (ISO 9735) remains wide internationally. Both coexist.
15. **Current counts of MLETR-adopting jurisdictions.** Verified: adopted by UNCITRAL 13 July 2017; for current counts, use UNCITRAL's status page.
16. **Bullwhip amplification magnitudes (e.g., "40%") as law.** Verified core is the four causes (Lee et al. 1997); magnitudes are context-specific.
17. **"Facilitation payments are legal everywhere" or "are bribes under all laws."** Both wrong: FCPA carves a narrow exception; UK Bribery Act bans them; many codes ban both.
18. **EOQ or safety-stock formulas as universally applicable recipes.** Teach the assumptions.

---

*Prepared for curriculum writing. Sources verified live October 2026; re-check primary sources at build time for legal status items (MLETR adoption, IFRS/LIFO, convention ratification).*
