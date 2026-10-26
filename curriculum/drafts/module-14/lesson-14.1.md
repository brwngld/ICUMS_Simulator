# DRAFT — Lesson 14.1: Transport and Warehouse Management Systems

=== KEY CONCEPT ===
HEADING: Why logistics systems exist: the ceiling of manual coordination
BODY:
Learners of this programme have already run, by hand, the processes this lesson digitalises. Module 8 walked the warehouse chain — receiving, put-away, picking, packing, dispatch — as a manual discipline, and Modules 5 and 7 ran the transport desk by telephone, quotation, and paper shipment file. Those lessons taught the processes precisely because the processes come first. This lesson asks a different question: what happens when volumes grow and the paper stops keeping up?

Manual coordination works at small scale and fails predictably at scale. The failure has a recognisable shape.

1. Information lives in people, not in records. The put-away locations are remembered by the senior picker; the carrier's current tariff is known only by the transport clerk. When that person is absent or leaves the business, the operation loses its memory.
2. Records multiply and disagree. The warehouse notebook, the spreadsheet, and the office copy of the delivery note are each updated at different times, so every question about stock or shipments produces several answers.
3. Decisions run on stale data. A sales clerk confirms an order against a stock figure from yesterday's count and discovers the truth only when the picker finds an empty shelf.
4. Coordination depends on heroics. The operation meets its deadlines because two supervisors work through lunch and one clerk telephones the depot every hour. It works until the day it does not.

A logistics management system is the industry's answer: software that records each operational event as it happens and makes that record immediately available to everyone authorised to see it. The raw material of such systems is real-time data — information made available with sufficiently low delay to support immediate or near-immediate operational decisions. What the paper warehouse and the telephone transport desk achieved through memory and effort, the system achieves through one shared, current record. Systems substitute shared data for heroics.

=== KEY CONCEPT ===
HEADING: Defining the TMS and the WMS — and the system of record
BODY:
Two systems anchor this lesson, and both should be recognised from the processes they digitise.

A transportation management system, usually written TMS, is software used to plan, execute, monitor, and optimise transportation activities. It is the digital counterpart of the transport desk: the quotation comparisons and booking work of Lesson 5.2, Freight Quotations and Shipment Booking, the tracking of Lesson 5.4, Shipment Tracking and Customer Communication, and the route choices of Lesson 13.2 all reappear inside it as system functions.

A warehouse management system, usually written WMS, is software used to manage and control warehouse operations, inventory locations, and stock movements. It is the digital counterpart of the warehouse record-keeping of Module 8, with one decisive difference: the WMS does not merely record what happened. It directs the work while it happens and records each confirmation as the work is done.

Both systems share a deeper property: each acts as the system of record for its domain. A system of record is the single system holding the agreed, authoritative version of the truth for a part of the business. For the warehouse, a WMS is the system of record for what enters, where it sits, and what leaves. For transport, the TMS is the system of record for what was tendered, shipped, and delivered, and at what cost.

The idea formalises the records discipline of Lesson 8.4, Warehouse Documentation and Stock Reconciliation. There, accuracy depended on people keeping one set of records and reconciling them against physical reality. A system of record is that same discipline built into software: one record, shared by every department, updated by the transaction itself rather than by a clerk copying figures the next morning. When every department reads the same record, disputes about whose figure is correct end, because there is only one figure.

=== KEY CONCEPT ===
HEADING: WMS functions: directing the physical flow
BODY:
The surest way to understand a WMS is to walk the receiving-to-dispatch chain of Lesson 8.2, Receiving, Put-Away, Picking, and Dispatch, again and watch which steps the system takes over. The chain is unchanged; the coordination becomes electronic.

1. Receiving management. The system holds the expected deliveries, checks each arrival against the order, and has the receiving operator scan each item or carton. A barcode — a machine-readable representation of information used to identify and track items — turns the physical arrival into a record at the dock instead of a note typed into the office ledger later.
2. Directed put-away. Instead of a supervisor deciding where goods go, the system assigns each received item a storage location and instructs the operator where to place it, applying rules for size, demand velocity, temperature, and compatibility. The paper location list and the driver's memory are replaced by an instruction that is correct even for a new employee's first week.
3. Wave and batch pick planning. The system groups orders into batches that can be picked in one pass and releases them in waves — scheduled groups aligned to vehicle departures and carrier cut-offs — so picking effort matches the dispatch plan instead of competing with it. The clustering a good dispatcher did by instinct is computed, consistently, every time.
4. Task interleaving. The system sequences tasks so equipment and people travel loaded rather than empty: a forklift that has just put a pallet away in one aisle is sent next to pick in a neighbouring location instead of driving back across the warehouse. Travel that was invisible on paper becomes a planned and reduced quantity.
5. Packing and shipping confirmation. Each carton is scanned as it is packed and each load is confirmed at the vehicle, so the system knows exactly which cartons left on which carrier. The dispatch record exists the moment the doors close, with no paperwork chase afterwards.

Each function digitises a manual step the learner has already performed. Nothing here is a new logistics process; it is the same process made reliable, fast, and measurable.

=== KEY CONCEPT ===
HEADING: WMS functions: tracking stock and measuring the operation
BODY:
The second group of WMS functions concerns knowledge rather than movement: knowing where everything is, verifying that the knowledge is still true, and measuring how well the operation runs.

1. Inventory and location tracking. The WMS holds a quantity for every item at every location, which means every item has a "where". The question that once sent a picker walking the aisles — where are the forty cartons of this medicine? — becomes a query answered in seconds, and the answer names the aisle, row, and bin.
2. Cycle-count support. Counting a rotating subset of locations instead of shutting the warehouse for a full count was taught as the disciplined alternative to the annual stocktake. The WMS makes it routine: it generates count tasks for selected locations, compares each physical count against its own record, and routes any discrepancy into investigation before an adjustment is made. The reconciliation discipline of Lesson 8.4 stops being a monthly event and becomes a continuous background process.
3. Labour and space metrics. Because every task is confirmed in the system, the WMS can measure what manual supervision could only estimate: how long receipts take to reach pickable locations, how many picks each labour hour achieves, how full each storage zone runs. These are the warehouse indicators of Lesson 13.4, Logistics Performance Indicators and KPIs — dock-to-stock time, picking productivity, space utilisation — collected automatically instead of by stopwatch and sampling.

One property unites all three functions. None of them invents new work: tracking, counting, and measuring existed in every well-run manual warehouse. The WMS performs them completely, continuously, and without depending on anyone's memory. That completeness is also why the WMS can act as the warehouse's system of record, in the sense defined earlier: it does not merely support the record-keeping discipline — it is the record.

=== KEY CONCEPT ===
HEADING: TMS functions: planning and execution
BODY:
A TMS covers the transport lifecycle in two halves: deciding how shipments should move, and making them move.

The planning half answers the questions of Lesson 13.2, Transport Route and Network Optimisation, shipment by shipment and automatically.

1. Mode and route selection. The system compares the available modes and routes for each shipment against cost, transit time, and service rules, applying the trade-offs the learner studied as network strategy — now executed in seconds for every order rather than debated monthly for the whole network.
2. Load building. The system fits orders to vehicles by weight, volume, and compatibility, so a trailer is planned as a loaded unit rather than an empty box that dispatch fills by eye.
3. Consolidation. The system recognises part-loads travelling to the same region and combines them into full loads, applying the full-load and shared-load logic of Module 13 — full loads faster with less handling, shared loads cheaper per unit — consistently and without favouritism.

The execution half turns the plan into movements and records.

4. Booking and tendering. The system selects the carrier against the contracted rates, tenders the load electronically, and confirms acceptance — the quotation-and-booking work of Lesson 5.2 compressed into a transaction.
5. Track-and-trace. From pickup through delivery, the system records status events — loaded, in transit, arrived, delivered — so the shipment's progress is visible to everyone authorised to look, without a single telephone call. This is the visibility promised in Lesson 5.4, supplied as a by-product of execution rather than assembled by asking.

The caution belongs here as well. The system executes comparisons, and a comparison is only as good as the rules and rates loaded into it. That dependency — master data — has its own block later in this lesson.

=== KEY CONCEPT ===
HEADING: TMS functions: freight audit and performance analytics
BODY:
After the freight moves, two further TMS functions close the loop: checking what the movement cost, and learning what the movement achieved.

Freight audit and payment is the function of checking carrier invoices against contracted rates before any money moves. Lesson 7.4, Shipping Charges, Freight Rates, and Surcharges, taught the anatomy of a freight bill: base charge, surcharges, currencies, totals. Freight audit is that anatomy compared mechanically — the TMS reads each invoice line, matches it against the rate contract and against the shipments actually executed, and flags every variance for investigation before payment is released. A manual audit samples a few invoices a month; a system audit checks every line of every invoice, every time. Approved invoices then pass to finance for settlement, with the audit trail attached.

Performance analytics is the function of computing transport performance from the execution records the TMS already holds. The indicators of Lesson 13.4 — OTIF, meaning on-time in-full delivery; freight cost per unit shipped; cost per tonne-kilometre; vehicle capacity utilisation; claims ratios — are assembled automatically from tendering, tracking, and audit data instead of being collected monthly from paper shipment files. What a manual desk measured monthly, a systemised desk can review weekly or daily.

Analytics then feeds planning. The measured cost and service of each carrier and lane become the inputs to the next mode, route, and carrier decisions: the planning cycle of Module 13 does not end when the shipment is delivered, because the TMS closes it by turning results into evidence.

The pattern across all the TMS functions deserves stating plainly: plan, execute, audit, analyse. The system does not decide the transport strategy — management does that, as Module 13 taught. The system executes that strategy on every shipment, checks the invoices against it, and reports the results of it.

=== KEY CONCEPT ===
HEADING: The OMS and the ERP backbone
BODY:
The TMS and WMS do not stand alone; they sit inside a wider landscape of business systems, and orders flow downhill through it.

At the front stands the order management system, or OMS: software used to receive, process, track, and manage customer orders. The OMS captures the sale, confirms availability, and hands each order to the systems that will fulfil it — the WMS for the goods, the TMS for the movement.

Behind them stands the enterprise resource planning system, or ERP: an integrated software system used to manage major organisational processes and business information. The ERP is the transactional backbone of the company — finance, purchasing, sales, and inventory in one system — carrying the commercial record from purchase order to supplier invoice and from customer order to payment.

The division of labour is best learned through the question each system answers.

1. The ERP answers: what do we own, owe, sell, and spend? Its stock figure is a value; its delivery is a line on an invoice.
2. The WMS answers: where is every item, and who moved it? Its stock figure is a quantity at a bin location, together with the tasks that touched it.
3. The TMS answers: how does each shipment move, and what does it cost? Its delivery is a load, a carrier, and a set of charges.

The same delivery is therefore a value in the ERP, a pick-and-pack task in the WMS, and a load with a tariff in the TMS. In practice the WMS and TMS either extend ERP modules or integrate with them, exchanging orders, confirmations, and charges so that each system keeps its own specialty while all of them read one truth.

One further system completes the physical picture: yard management — the check-in, parking, dock-door scheduling, and move tracking for trailers between gate and dock — often run by its own system linked to the WMS and TMS.

=== KEY CONCEPT ===
HEADING: System integration: making the systems talk
BODY:
When each system holds part of the truth, the parts must be connected. System integration is the process of connecting software applications so they can exchange data and support coordinated operations, and its absence has a price every manual desk already knows: re-keying. An order typed into one system, copied onto a picking list, and typed again into a carrier's portal is handled three times and can be wrong three times, and each re-keying creates a discrepancy that somebody must later reconcile.

Integration removes the copying. One entry propagates: a customer order confirmed in the OMS becomes a picking task in the WMS without retyping; the confirmed dispatch becomes a transport booking in the TMS; the delivery confirmation becomes the invoice basis in the ERP. The benefits follow directly.

1. Information accuracy. Data entered once cannot be mistyped twice, so the systems agree by construction rather than by reconciliation.
2. Speed. Confirmations travel between systems in seconds, so downstream departments start work earlier.
3. Coordination. Every department reads the same record, so a delay visible to the warehouse is visible at once to customer service — nobody has to be told, because nobody has to ask.
4. Traceability. Each event is stamped once, by the person and system that produced it, which is what makes later audit and investigation possible.

The connection itself is built in two main ways. The modern instrument is the application programming interface, or API: a defined interface that enables software applications to exchange information or invoke supported functions, typically in real time, system to system. The established instrument for exchanging structured business documents between organisations — orders, despatch advices, invoices — is electronic data interchange, which the next lesson treats in full. Integration between a company's own systems and integration between trading partners solve different problems, but they serve one purpose: the record moves with the goods, without being copied by hand.

=== KEY CONCEPT ===
HEADING: Visibility: one record, many viewers
BODY:
Integration exists to produce visibility. Shipment visibility means knowing where a shipment is and what has happened to it, built up from the scan and status events of execution. Inventory visibility is defined precisely: the ability to access timely information about inventory quantities, locations, and status. Both rest on the real-time record introduced at the start of this lesson, and both are only as current as the last recorded event.

The data that produces visibility falls into four familiar families, which together answer the question of what logistics systems record and process.

1. Master data: the standing reference records — items, locations, partners, rates — that describe the permanent structure of the operation.
2. Transaction data: the events of daily work — orders, receipts, put-aways, picks, packs, loads, deliveries.
3. Status and event data: the progress marks attached to transactions — scanned, in transit, delayed, delivered — the raw material of track-and-trace.
4. Reference and tariff data: contracted rates, surcharge tables, calendars, and rules against which planning and audit run.

Identification technologies feed the record. Barcodes, introduced with receiving, attach events to items cheaply and universally. Radio frequency identification, or RFID, is a technology that uses radio signals to identify and exchange information with tagged objects; unlike a barcode it needs no line of sight and can read many tagged pallets at once through a portal, which suits bulk identification points. Underneath both sits the discipline of standard identification: a trade item carries its own identifying number — encoded in the barcode, not the barcode itself — while the pallet or container it travels on carries a separate identifier for the logistics unit. A scan can therefore say not only what the goods are but which unit of handling they sit on.

Visibility, finally, is not a screen for one department. It is one shared record with many authorised viewers: the warehouse sees inbound arrivals due, the transport desk sees loads in progress, customer service sees the delivery status the customer will ask about, and management sees the indicators of Lesson 13.4 assembling themselves. Four views, one truth.

=== KEY CONCEPT ===
HEADING: Master data, data accuracy, and access control
BODY:
Every transaction in every system leans on master data — the shared reference records that describe the permanent structure of the operation: items with their codes, descriptions, units of measure, and weights; locations with their identifiers down to the bin; partners with their addresses, identifiers, and agreed terms; rates with their validity periods and conditions. Master data is the hidden foundation because it is installed once and used thousands of times a day, usually invisibly.

Systems obey a rule older than computing: garbage in, garbage out. A system processes whatever it is fed, without knowing whether the feed was true. A wrong unit of measure turns a receipt of ten cartons into a hundred pieces; a missing bin identifier turns directed put-away into guesswork; an outdated carrier tariff turns freight audit into a rubber stamp. The system amplifies errors exactly as efficiently as it amplifies good practice, which is why data accuracy is not an information-technology nicety but an operating condition.

The discipline of Lesson 8.4 therefore survives digitalisation unchanged in spirit. A system of record is kept truthful by comparing records against physical reality — cycle counts, reconciliation, investigation before adjustment — except that the WMS now schedules the comparisons and keeps the audit trail. Inventory accuracy, the share of counted locations matching the record within tolerance, becomes a managed indicator with a target and an owner, in the manner of Lesson 13.4.

The third element is access control: the mechanisms used to restrict system functions and information to authorised users. Its purpose is trust. Records that anyone can edit are records nobody can trust, so systems assign roles: a picker sees picking tasks, not rate tables; stock adjustments require a supervisor; only finance releases payments; and every change carries the identity of its maker. Access control keeps the record attributable, protects commercially sensitive information such as customer lists and contracted rates, and draws the boundary without which the system of record cannot be trusted at all.

=== KEY CONCEPT ===
HEADING: Choosing, implementing, and adopting a system
BODY:
Selecting a logistics system follows one principle above all others: define the process first, then fit the system to it — never buy the system and let it define the process. A requirements evaluation is therefore mostly process work, and it can be framed as four questions.

1. Processes. Which processes must the system support — receiving, directed put-away, wave picking, rating, tendering, freight audit?
2. Data. Which data must it hold, clean, and exchange — items, locations, partners, tariffs, orders, status events?
3. People. Who will use it, and what must each role see, remembering the case for access control?
4. Connections. How must it integrate with the ERP already in place and with trading partners?

System implementation is defined as the process of configuring, deploying, testing, and introducing a software system into operational use. Each word carries work: configuring the system to the chosen processes, testing it against realistic orders and exceptions, and cutting over deliberately rather than on a licence calendar.

The costs that decide success, however, are the ones after the contract: data migration, training, and change management. Data migration means cleaning and loading the master data described earlier in this lesson — years of item, location, and partner records that were never designed to be machine-read. Training means teaching every role to do its own work the new way, which is slower at first and therefore resented. Change management means expecting the pull of old habits: under pressure on a busy afternoon, a supervisor will keep the private paper list, and the moment that list becomes the real record, the system has already begun to die.

The industry's name for the outcome is shelfware: the best system unused is shelfware — licensed, installed, and not used to run the operation. Adoption, not installation, is the finish line, and it is won the same way the paper discipline of Lesson 8.2 was won: every step of the chain recorded as it happens, by everyone, every time.

=== WORKED EXAMPLE ===
HEADING: One order, two warehouses: the paper walk and the WMS walk
BODY:
Consider a pharmaceutical distributor in Accra that serves clinics across Ghana. A clinic in Kumasi orders 120 cartons of assorted medicines for delivery within two days; one line is 40 cartons of a single product. All timings and details are illustrative for teaching purposes. The same order is walked twice: once through the distributor's old paper warehouse, once through the same warehouse running a WMS.

The paper walk, run by hand as in Module 8.

Step 1: Order taken. The order arrives by telephone and email; a clerk copies it onto a picking list and checks the ledger for availability — a ledger updated the previous evening.
Step 2: Search. Pickers work from memory: medicines are usually in rows three to five. One line was put away in the overflow area during last week's congestion and nobody recorded it. The search for the 40 cartons occupies most of an afternoon.
Step 3: Dispatch. Cartons are counted twice by hand, the delivery note is written out, and the transport clerk telephones three carriers before finding one with space for tomorrow.
Step 4: Records. The ledger is updated that night — by which time a second customer has been promised part of the same stock on yesterday's figures.

The WMS walk.

Step 1: Order captured. The order lands in the OMS and is confirmed against location-level stock in the WMS — current at the moment of confirmation.
Step 2: Directed work. The system releases pick tasks in a wave planned around tomorrow morning's Kumasi departure. Each picker is sent bin by bin; a scan of each barcode confirms the pick, and a mis-scan is refused at once.
Step 3: Exception handled. The overflow item? The system knows its location, because put-away was directed and scan-confirmed. No search occurs.
Step 4: Dispatch confirmed. Packing scans close each carton; the load is confirmed to a vehicle, and the TMS tenders the delivery to the contracted carrier against the tariff on file.
Step 5: Records current. Customer service answers the clinic's enquiry by reading the delivery status, and the evening cycle count of two locations confirms the system against the shelf.

What does this example demonstrate? The two walks contain the same steps — the WMS did not change the process of Lesson 8.2; it changed its reliability: fewer searches, no double-counting, a record current at each step, and promises made against true availability.

Key lesson: a WMS digitises the receiving-to-dispatch chain step by step, and its record stays truthful because every physical action is confirmed at the moment it happens.

=== WORKED EXAMPLE ===
HEADING: The freight-audit catch: an invoice against the contract
BODY:
A manufacturer based in Tema ships finished goods to Kumasi and Tamale with a road carrier under a contract: an agreed rate per trailer plus documented surcharges, exactly the freight-bill anatomy of Lesson 7.4. All figures in this example are illustrative for teaching purposes.

Step 1: Contract loaded. The agreed rate — say 4,200 GHS per trailer — and the surcharge table are loaded into the TMS as the rate contract, with a validity period.
Step 2: The month runs. During the month the TMS tenders fourteen loads; each is executed, tracked, and confirmed as delivered. Fourteen loads at 4,200 GHS give a base freight expectation of 58,800 GHS before surcharges.
Step 3: The invoice arrives. The carrier's monthly invoice lists fourteen base charges at 4,650 GHS each — 450 GHS above the contract on every line, 6,300 GHS in total — plus the expected fuel surcharge, and one further load invoiced twice.
Step 4: The audit compares. The TMS matches each invoice line against the rate contract and against the executed shipments. It flags the base-rate variance on all fourteen lines and the duplicate load, which has no matching execution record. Nothing is paid while the variances stand.
Step 5: Resolution. The query goes to the carrier, which confirms that an outdated tariff was applied and that the duplicate arose from a re-sent invoice. A corrected invoice arrives, is re-checked against the contract in the system, passes, and is released to finance for payment with the audit trail attached.

What does this example demonstrate? The manufacturer's accounts team did not discover the differences; the system did, by comparing every line of every invoice against the contract every time — the check that Lesson 7.4 performed manually, at sample scale, performed here at full scale. Note also what the audit did not do: it did not accuse, renegotiate, or decide. It compared, flagged, held, and kept the evidence, leaving the judgement to people.

Key lesson: freight audit pays the contract, not the invoice. The TMS makes that discipline complete — every invoice, every line — and turns the freight-bill anatomy into a mechanical control.

=== WORKED EXAMPLE ===
HEADING: A failed adoption: the post-mortem of a system that became shelfware
BODY:
Not every implementation ends like the Accra example. This post-mortem, generic and illustrative, follows a household-goods importer in Rotterdam that replaced its paper warehouse with a WMS. All details are illustrative for teaching purposes.

Step 1: The decision. Senior management selected a system in a vendor demonstration, impressed by features shown against the vendor's own scenarios. No process definition and no requirements document preceded the choice.
Step 2: The rush to go live. The go-live date was set to match the licence calendar. Item master data was loaded from years of spreadsheets containing duplicate codes and mixed units of measure — some goods tracked per pallet of forty-eight, some per carton of sixty, few labelled which. Storage locations were named during the go-live week itself. Training consisted of one demonstration to the whole staff five days before launch.
Step 3: The first weeks. Put-away confirmations landed on the wrong bins because the item codes were ambiguous and the operators, unschooled in the scanning discipline, confirmed placements they had not made. Pickers quietly returned to private notebooks of true locations. The notebooks were accurate; the system drifted.
Step 4: The collapse of trust. Stock records diverged from reality; availability promises began to fail; discrepancies were adjusted away to force the figures to balance rather than investigated — the shortcut Lesson 8.4 warned against. Management responded with more reports; staff responded with more paper.
Step 5: The outcome. Months later the operation ran on paper and the system was used only to produce invoices. The company owned shelfware.

The post-mortem found no defect in the software. It found unclean master data fed into the system, training treated as an event instead of a programme, processes never defined before configuration, and no named owner of adoption.

What does this example demonstrate? Implementation is a change of working habits, and the habits decide. The system amplifies whatever is fed into it: clean data and trained users, or duplicates and workarounds.

Lessons from the example: clean and structure master data before go-live, not after; train each role on its own tasks and support users at the shoulder in the first weeks; define the process first and configure the system to it; put supervisors to work inside the system themselves, because staff follow what management does; and measure adoption — if confirmations are late or missing, the record is already drifting.

=== IMPORTANT NOTE ===
HEADING: Technology serves the process — systems execute strategy
BODY:
The single most expensive misconception in logistics technology is that a system will fix a process that does not work. The relationship runs the other way: technology serves the process, never the reverse, and a system executes whatever way of working it is given — faithfully and at speed.

A WMS installed in a badly laid-out warehouse, of the kind Lesson 8.1, Warehouse Functions and Layout, taught learners to avoid, does not repair the layout; it automates the badness. Directed put-away will fill the congested aisle faster and more often, task interleaving will chase travel paths that the layout makes long, and the metrics will report precisely how much the badness costs — every day, with confidence. A TMS given mistaken service targets optimises the shipments towards the wrong promise just as energetically. Automation multiplies: good process multiplied is good; bad process multiplied is bad.

The practical test follows. If a process does not work on paper, it will not work in a system — the failure merely hides inside a database until it surfaces as a larger discrepancy. This is why the requirements work of this lesson begins with defining the process, and why the manual teaching of the previous modules is not a memory to discard but the very specification the system must encode. Management decides the strategy — the layout, the picking methods, the service promise — and the system executes it. That division of labour is the whole content of this lesson in one sentence: systems execute strategy; they do not write it.

=== IMPORTANT NOTE ===
HEADING: The system records what people record
BODY:
A second misconception sits close to the first: that if the screen says twelve, there are twelve. A system of record is truthful only while every physical movement is recorded as it happens. The WMS does not see the pallet; it sees the confirmation transaction. When an operator moves stock without scanning, to save a walk, the physical warehouse and the recorded warehouse begin to diverge in that instant, and no screen will warn anybody, because the system believes its last confirmation.

Three workarounds deserve naming, because all three are common and all three poison the record.

1. Unrecorded moves. Stock shifted to reach a picker faster, or parked in an overflow corner during congestion, without a transaction. The system now points to a bin that is honestly empty.
2. Adjustment instead of investigation. Figures forced back into balance so that the reports look right — the reconciliation shortcut Lesson 8.4 warned against, now performed with a keyboard instead of an eraser.
3. Private records. The supervisor's notebook that is more current than the system. For as long as it exists, it is the real system of record, and everything else is decoration.

The defence is the same discipline as ever, digitised: scan at the moment of the move, count continuously, investigate before adjusting, and keep adjustments behind access control so they are visible and attributable. When a report looks wrong, distinguish the two possible causes before acting: the system failing, which is rare, and the data failing — an unrecorded or mistyped event — which is common. Most system errors in logistics are record-keeping errors wearing a system's name.

=== IMPORTANT NOTE ===
HEADING: Match the system to the organisation — fit, not maximum
BODY:
A final caution completes the evaluation guidance of this lesson: the aim is fit, not maximum technology. A single-site operation with a few hundred item codes and one carrier may run excellently on an ERP's basic inventory functions and a simple transport planner; a multi-site, multi-temperature, multi-client distribution business justifies a specialised WMS and TMS. Both answers can be correct, because requirements — process complexity, data volumes, numbers of users and roles, integration needs — differ, and the system must be fitted to the requirements, not the requirements to a brochure.

Over-buying has a cost the demonstration does not show: capability the organisation cannot feed with clean master data or staff with trained users becomes expense without control. Under-buying has the mirror cost: an operation that outgrows its basic tool must re-run the entire implementation later, with volumes already too large for a gentle transition.

Two evaluation habits keep the choice honest. First, write the process and data requirements before the first demonstration, and make every vendor demonstrate against the organisation's own scenarios — its order profiles, its exception cases — rather than the vendor's. Second, count the total cost of adoption, not the licence: data migration, integration work, training, and the permanent effort of keeping master data current all continue long after the purchase, and they are where the Rotterdam post-mortem was lost.

The same fit principle governs integration: connect where data flows repeatedly and decisions depend on it. Connecting everything to everything is not a virtue; integration serves the coordinated operation, in the words of this lesson's definition — not the other way round.

=== MCQ 1 ===
QUESTION:
A building-materials warehouse in Takoradi has a recurring problem: pickers spend long periods searching for stock that the records say is available, and the search usually ends in an overflow corner that nobody updated in the ledger.

Which option best explains how a warehouse management system addresses this problem?
POINTS: 1
OPTIONS:
1. It rearranges the physical warehouse layout automatically so that fast-moving items end up in the most convenient locations without human decisions.
2. It keeps a recorded location for every item, directs put-away to assigned bins with scan confirmation, and points picking to the recorded location, so record and reality stay aligned.
3. It removes the need for cycle counting and stock reconciliation, because a computerised record cannot drift from physical reality.
4. It values the stock for the finance department, replacing the accountant's ledger with a system-calculated stock figure.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The WMS attacks exactly the failure described in the scenario: stock physically somewhere other than its record. By directing put-away to assigned locations, confirming every placement and pick with a scan, and holding a quantity per location, it makes the answer to where is this stock a query rather than a search — and an overflow-corner placement would have been recorded at the moment it happened.

Answer 1 fails on the lesson's first warning: a system executes the layout it is given; it does not redesign the warehouse. Answer 3 contradicts the second warning, because the record drifts precisely when people stop recording, which is why cycle counting and reconciliation continue inside a WMS rather than disappearing. Answer 4 confuses the WMS with the ERP, whose stock figure is a value for finance; the WMS figure is a quantity at a bin location for operations.

The takeaway: a WMS replaces searching with directing, and its accuracy depends on disciplined recording, not on the absence of counting.

=== MCQ 2 ===
QUESTION:
A carrier's monthly invoice reaches a Tema manufacturer: every base-rate line is billed 450 GHS above the rate contract loaded in the TMS, and one load has been invoiced that was never executed.

Which statement best describes what the TMS freight-audit function does with this invoice?
POINTS: 1
OPTIONS:
1. It pays the invoice automatically to protect the carrier relationship, since the carrier's own billing is presumed correct.
2. It adjusts the invoice lines silently to match the contract and pays the corrected amount without informing the carrier.
3. It compares each invoice line against the contracted rates and the executed shipments, flags the variances, and holds payment until the differences are investigated and resolved.
4. It renegotiates the rate contract with the carrier for the next period, since the carrier has demonstrated that the current rates are out of date.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

Freight audit was taught as the function that pays the contract, not the invoice: the TMS reads each line against the rate contract and against the shipments actually executed, flags every variance, and holds payment while the differences are investigated. The two catches in the scenario — the rate above contract and the load without an execution record — are exactly the variances the audit exists to find, and the Tema worked example showed the full sequence: compare, flag, hold, query, resolve, then pay with the evidence attached.

Answer 1 surrenders the control entirely and rewards the error. Answer 2 is wrong in procedure as well as in partnership: the audit flags and holds, it does not silently alter another party's invoice — the carrier corrects its own billing, as the worked example showed. Answer 4 confuses audit with negotiation: the rate contract is a commercial agreement between people, and the system's task is to check billing against it, not to change it.

The takeaway: the audit function is a comparison control, complete because it checks every line of every invoice, and its power lies in paying nothing while a variance stands.

=== MCQ 3 ===
QUESTION:
Six months after going live with a new WMS, a distribution company finds that staff keep paper notebooks of true stock locations, supervisors adjust records to make reports balance, and management has concluded that the software was simply a bad product.

Which statement best explains what actually went wrong?
POINTS: 1
OPTIONS:
1. The implementation failed on its foundations — unclean master data, thin training, and no ownership of adoption — so people built workarounds that turned paper back into the real record; the remedy is data quality and training, not necessarily a different product.
2. The system cleans its own master data within the first months of operation, so the discrepancies should have disappeared without management action.
3. Paper notebooks and system records can safely coexist permanently, since the notebooks provide a useful secondary record whenever the system is slow.
4. Access control is the cause of the problem, and granting every employee the right to adjust any record would restore trust in the system.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The scenario reproduces the Rotterdam post-mortem almost line for line: master data loaded uncleaned, training delivered as a single event, no process definition, and no owner of adoption. The symptoms — private notebooks, adjustments instead of investigations, management blaming the product — are the standard biography of shelfware, and the remedy follows the foundations: clean the master data, train each role on its own tasks, put managers to work inside the system, and measure adoption.

Answer 2 contradicts the lesson's rule that systems amplify whatever is fed into them; no system cleans garbage in by itself. Answer 3 names the exact failure mode as though it were a stable arrangement: while the notebook is more truthful than the system, the notebook is the real system of record and the software is decoration. Answer 4 inverts the purpose of access control, which exists to keep adjustments visible and attributable; open adjustment rights would accelerate the drift, not repair it.

The takeaway: adoption, not installation, is the finish line, and it is built on clean data, trained users, and owned discipline.

=== FACTS & SOURCES ===
- Definitions of transportation management system, warehouse management system, enterprise resource planning, order management system, system integration, inventory visibility, barcode, radio frequency identification, application programming interface, real-time data, access control and system implementation follow the lesson brief 14.1 key terms. — source: lesson brief 14.1, Key Terms (curriculum database).
- A TMS plans and executes transport: mode and route selection, carrier selection and rating, tendering, tracking, freight audit and settlement, and increasingly emissions reporting. — source: research sheet logistics-scm-frameworks.md, section 9 (industry-standard scope).
- A WMS is the system of record for what enters, where it sits, and what leaves the warehouse; it records the arrival and departure of inventory with supporting functions for location tracking, space use, task coordination, analysis of capacity, stock and labour, and system integration through APIs. — source: research sheet logistics-scm-frameworks.md, sections 4 and 9.
- The ERP is an integrated transactional backbone across finance, procurement, sales, inventory and production; WMS and TMS either extend ERP modules or integrate with them. — source: research sheet logistics-scm-frameworks.md, section 9.
- The warehouse core flow is receiving, put-away, picking, packing, dispatch; wave picking releases orders in scheduled groups aligned to shipping or carrier cut-offs; batch picking combines several orders per pass. — source: research sheet logistics-scm-frameworks.md, section 4 (picking taxonomy; medium confidence on the batch/wave boundary, taught as general practice).
- Directed put-away, task interleaving, scan-confirmed receiving and shipping, and labour and space metrics as WMS functions are standard industry practice; yard management covers gate check-in, parking positions, dock scheduling and move tracking, often via a system linked to the WMS and TMS. — source: research sheet logistics-scm-frameworks.md, section 9 (yard management, medium confidence) and general business knowledge.
- Cycle counting counts a rotating subset of locations on a continuous schedule instead of a full annual count; inventory accuracy is the share of counted locations or SKUs matching the system record within tolerance. — source: research sheet logistics-scm-frameworks.md, sections 5 and 7.
- Freight audit checks carrier invoices against contracted rates before payment, and approved invoices pass to finance for settlement; the three-way match — purchase order, goods receipt and invoice agreed before payment — is the standard invoice-checking control referenced conceptually. — source: research sheet logistics-scm-frameworks.md, sections 9 and 3.
- APIs are the modern, typically real-time, system-to-system integration instrument; EDI is the computer-to-computer exchange of structured business documents in standardised electronic formats between organisations, treated fully in lesson 14.2 and mentioned only in passing here. — source: research sheet logistics-scm-frameworks.md, section 9.
- RFID identifies tagged objects by radio without line of sight and complements barcodes where bulk or portal reads add value. — source: research sheet logistics-scm-frameworks.md, section 9.
- The trade item is identified by a number encoded in the barcode (the number is not the barcode itself), and the pallet or container travels under a separate logistics-unit identifier (SSCC). — source: research sheet logistics-scm-frameworks.md, section 9 (GTIN and SSCC; DO NOT CLAIM item 13 respected).
- OTIF, freight cost per unit and per tonne-kilometre, capacity utilisation, claims ratio and dock-to-stock time are the standard indicators referenced from Lesson 13.4; FTL dedicates a vehicle to one shipper while LTL combines several shippers' freight, cheaper per unit with more handling. — source: research sheet logistics-scm-frameworks.md, sections 6 and 7.
- No vendor names, no savings or ROI percentages and no adoption statistics are used anywhere in the lesson; systems are taught by function. — source: WRITING_SPEC.md rule 5.1 and research sheet logistics-scm-frameworks.md, DO NOT CLAIM item 10.
- All quantities, currency amounts, timings, percentages and company situations in the worked examples and inline illustrations (the Accra pharmaceutical distributor and its 120-carton order with a 40-carton line; the Tema manufacturer at 4,200 and 4,650 GHS per trailer, 58,800 GHS expected and 6,300 GHS variance over fourteen loads; the Rotterdam household-goods importer; searches and delays described only qualitatively) are illustrative for teaching purposes. — source: WRITING_SPEC.md rule 5.1.
- The requirements-first approach, process before technology, data migration, training, change management, shelfware, the garbage-in-garbage-out rule and the four-family data taxonomy are general business knowledge presented without attribution. — source: general business knowledge.
