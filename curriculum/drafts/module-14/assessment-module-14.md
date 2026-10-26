# DRAFT — Module 14 Assessment: Digital Logistics and Technology

Coverage map (one line per question):

Q1 | lesson 14.1 | the functional boundaries of ERP, WMS and TMS read off one delivery: different figures for value, bin-and-task, and carrier-and-charges are each system answering its own question, not an integration failure (distinguishing TMS, WMS and ERP; system of record; one record, many viewers).
Q2 | lesson 14.1 | the truthful system of record: cartons missing from a bin are likelier a record-keeping failure than a system failure, so investigate before adjusting — adjustment-first, private records and blanket approvals each poison the record (data accuracy; access control; the system records what people record).
Q3 | lesson 14.1 | the freight-audit function defended against a bypass proposal: every line of every invoice compared against the rate contract and the executed shipments, payment held on variance — presumed-correct billing, sampling and silent correction each break the control (freight audit and payment).
Q4 | lesson 14.2 | EDI's definition applied to a mislabelled process: emailed PDFs re-typed by clerks are not computer-to-computer structured exchange in agreed standards, so the re-keying errors and delays EDI removes are all still present; interoperability comes from shared standards, not identical software (electronic data interchange; electronic data standard).
Q5 | lesson 14.2 | the ASN's defining property: it travels ahead of the goods, enabling pre-matching to the purchase order and scan-confirmed receipt against an expected-receipt list — not a duplicate packing list and not an invoice (advance shipping notice / DESADV / 856; the three-way match).
Q6 | lesson 14.2 | dematerialisation versus the transferable record applied fresh: the e-AWB was easy because air waybills are non-negotiable, while a negotiable bill of lading is a document of title — a scanned PDF can be neither possessed nor controlled, so an e-B/L needs control plus legal recognition on MLETR principles, varying by country (electronic bill of lading; document of title).
Q7 | lesson 14.3 | the visibility ladder diagnosed in an ask-and-wait operation: reactive tracking is the current rung and event-driven visibility the next, because prediction rests on clean events and cannot be jumped to (reactive, event-driven and predictive visibility; cumulative rungs).
Q8 | lesson 14.3 | GTIN versus SSCC on a fresh labelling decision: one SSCC per product line defeats serial identification — the GTIN names the trade item, the SSCC must be unique to each logistics unit (GS1 identification; the barcode is the representation, the number is the identity).
Q9 | lesson 14.3 | the alert-needs-a-response-process rule read from a failure: alerts without a named owner, authority and playbook, response window with escalation, and tuning train an organisation to ignore them — automation amplifies the absence of a designed process (exception alert; alert fatigue).
Q10 | lesson 14.4 | the analytics ladder climbed in order against a start-with-the-most-advanced proposal: descriptive, diagnostic, predictive, prescriptive — each rung inherits the quality of the one beneath, so prediction before description is guessing dressed in mathematics (the analytics ladder; sequencing).
Q11 | lesson 14.4 | the four-question evaluation frame applied to a robotics pitch: named problem, total cost, ecosystem readiness, bounded pilot with measures defined in advance — against competitor envy, demo-worship and permanent refusal (evaluating emerging technology; automation amplifies the process it is given).
Q12 | lesson 14.4 | blockchain's promise and caution separated: tamper-evident is not truth-creating — a ledger guarantees entries are unaltered after entry, not that they were true at entry, and value depends on counterparties, standards and legal recognition (blockchain; distributed ledger technology).

=== ASSESSMENT Q1 | tests lesson 14.1 ===
QUESTION:
Three months after going live, a distribution company in Accra runs an ERP, a WMS and a TMS. At the morning meeting, one customer delivery is discussed from three angles, and a new supervisor hears different figures for what looks like the same delivery: finance reports its value, the warehouse reports its bin locations and pick tasks, and the transport desk reports its carrier, load and charges. Alarmed by the differences, the supervisor reports an integration failure to management.

Which option best assesses the report?

POINTS: 1
OPTIONS:
1. The report is correct: the three systems should quote identical figures for the same delivery, and any difference proves an interface fault that must be repaired before the implementation can be called complete.
2. The report mistakes design for defect: the ERP answers what the company owns, owes, sells and spends, so its figure is a value; the WMS answers where every item is and who moved it, so its figure is a quantity at a bin with the tasks that touched it; the TMS answers how each shipment moves and at what cost, so its figure is a load, a carrier and a set of charges — and integration means one truth shared across specialties, not three identical copies.
3. The report is partly right: only the ERP's figure can be trusted, because the ERP is the transactional backbone, and the WMS and TMS are display tools whose figures need not reconcile with anything.
4. The report has identified a real duplication: one of the three systems should be removed, because a well-run company needs a single system holding the value, the quantity and the load in one record.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The lesson's division of labour is learned through the question each system answers. The ERP is the transactional backbone — finance, purchasing, sales, inventory — so it answers what the company owns, owes, sells and spends, and its delivery is a value and an invoice line. The WMS answers where every item is and who moved it: a quantity at a bin location, together with the pick and put-away tasks that touched it. The TMS answers how each shipment moves and what it costs: a load, a carrier and a set of charges. Three different figures for one delivery are therefore the systems working as designed, each holding the authoritative version of the truth for its own domain — the system-of-record idea — and integration means every department reads the view it needs from one coordinated record, not that three copies agree to the decimal.

Answer 1 turns a design principle into a fault report and would send the company hunting for an interface defect that does not exist. Answer 3 collapses the specialties into the ERP, whose stock figure is a value and cannot say which bin or which task. Answer 4 removes a specialty the business needs; the systems are meant to keep their own fields of mastery while exchanging orders, confirmations and charges.

The takeaway: ask which question each system exists to answer, and expect the same delivery to be a value, a task and a load.

=== ASSESSMENT Q2 | tests lesson 14.1 ===
QUESTION:
A warehouse team cannot find eight cartons that the WMS says are in bin B-12. The shift supervisor proposes adjusting the record down by eight immediately, so that the figures balance before the morning report.

Which option best assesses the proposal?

POINTS: 1
OPTIONS:
1. The proposal is sound: the physical count is the truth, so correcting the record to match it at once is exactly what a system of record is for.
2. The discrepancy proves the WMS software is unreliable, and the team should keep a private paper list of true locations until the vendor repairs the product.
3. The proposal is sound provided a supervisor with adjustment rights enters the correction, because an approved adjustment is by definition a trustworthy one.
4. The proposal treats the symptom and destroys the evidence: the likeliest cause is an unrecorded movement — the system sees confirmations, not cartons — so the discipline is to investigate the bin's recent history, correct at source, and only then adjust, with the adjustment visible and attributable behind access control; most system errors in logistics are record-keeping errors wearing a system's name.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

A system of record is truthful only while every physical movement is recorded as it happens: the WMS does not see the cartons, it sees the confirmation transactions. Cartons missing from an honest bin usually mean an unrecorded move — stock shifted during congestion, or parked in an overflow corner without a scan — and the lesson's rule is that most system errors are record-keeping errors wearing a system's name. The discipline therefore runs: investigate the bin's recent transactions and the physical overflow areas, find the cause, correct it at source, and only then adjust the record — keeping the adjustment behind access control so that it is visible and attributable. This is the reconciliation discipline of the paper warehouse, unchanged in spirit, with the system now scheduling the counts and keeping the trail.

Answer 1 performs the adjustment-first shortcut the lesson warns against: figures forced into balance make the report look right while the cause survives to misdirect the next shift. Answer 2 reaches for the private notebook, which becomes the real system of record the moment it exists, demoting the software to decoration. Answer 3 confuses authorisation with accuracy: approval rights make an adjustment attributable, not correct.

The takeaway: when the screen disagrees with the shelf, ask which record failed and why — the adjustment is the last step, not the first.

=== ASSESSMENT Q3 | tests lesson 14.1 ===
QUESTION:
A finance manager reviewing accounts payable proposes a saving: carrier invoices arrive monthly, and since the transport rates were agreed in a signed contract, finance can pay each invoice directly against the carrier's own billing summary, releasing the TMS freight-audit step.

Which option best evaluates the proposal?

POINTS: 1
OPTIONS:
1. The proposal removes the control that pays the contract rather than the invoice: freight audit compares every line of every invoice against the rate contract and the shipments actually executed, flags variances — rates above contract, charges without an execution record — and holds payment until they are resolved, a completeness that reading the carrier's own summary cannot reproduce.
2. The proposal is sound, because a signed contract guarantees that invoices conform to it, and re-checking the invoice lines against the contract merely duplicates the carrier's own billing checks.
3. The proposal should be softened, not adopted: finance should sample a few invoices each month against the contract, since a sample gives the same assurance as a complete check at a fraction of the effort.
4. The proposal should be replaced by a stronger one: the TMS should silently correct any invoice line that differs from the contract and pay the corrected amount, sparing both parties the investigation.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

Freight audit is the function that pays the contract, not the invoice. The TMS reads every line of the carrier's billing against two references — the rate contract and the shipments actually executed — and flags any variance: a base rate above the agreed figure, a surcharge outside the documented table, a charge for a load that was never tendered. Nothing is paid while a variance stands; the query goes to the carrier, the correction is re-checked in the system, and only then does the invoice pass to finance for settlement with its audit trail attached. The value of the control is its completeness — every line of every invoice, every time — which is precisely what the proposal abandons.

Answer 2 presumes what the audit exists to verify: the lesson's worked example found an entire month billed above contract because an outdated tariff was applied in good faith, plus one load invoiced twice with no matching execution record. Answer 3 accepts the manual sample as equivalent, but sampling is exactly the weakness that made the system audit worth building; the manual desk checked a few invoices a month, and the variances it missed were nobody's fault and everybody's cost. Answer 4 has the system silently altering another party's invoice; the audit compares, flags, holds and keeps the evidence — the carrier corrects its own billing.

The takeaway: pay the contract, not the invoice, and let no invoice pass unchecked.

=== ASSESSMENT Q4 | tests lesson 14.2 ===
QUESTION:
A customs brokerage in Accra advertises that it operates fully by electronic data interchange. On inspection, its process is this: clerks receive suppliers' emailed PDF invoices, open each one, read it, and re-type the details into the brokerage's declaration system.

Which option best assesses the advertisement?

POINTS: 1
OPTIONS:
1. The advertisement is accurate, because EDI means exchanging documents between organisations electronically, and emailed documents do exactly that.
2. The advertisement would be accurate if the PDFs were scanned from paper rather than created digitally, since scanned documents are the standard EDI format.
3. The advertisement is inaccurate: EDI is the computer-to-computer exchange of structured business documents in agreed standard formats, in which the receiving system reads and processes the message itself — an emailed PDF still needs a person to open, read and re-type it, so the re-keying errors and delays EDI exists to remove are all still present.
4. The advertisement is inaccurate because EDI requires both trading partners to run identical software, which the brokerage and its suppliers evidently do not.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

Electronic data interchange has three defining elements, and the brokerage's process fails all three. EDI is computer-to-computer: the message passes into the partner's system and the receiving software reads and processes it itself. It is structured: every piece of data sits in a defined place, so the receiving system knows exactly where the quantity, the price and the delivery date are. And it uses agreed standards, so a message composed by one side is interpreted identically by the other. An emailed PDF is none of these: a person must open it, read it and re-type it, which means every re-keying error and every hand-off delay that EDI exists to remove is still present — the transaction merely travels faster on its first step.

Answer 1 accepts the claim because documents move electronically, which is the exact misconception the computer-to-computer element dismantles. Answer 2 confuses the image of a document with a structured message: a scan is an image, however it was produced, and no format standard makes an image machine-readable as data. Answer 4 blames the wrong thing — partners never need identical software; interoperability between different systems is precisely what the published standards, UN/EDIFACT and ANSI X12, supply, which is why a buyer can trade with hundreds of suppliers running different programs.

The takeaway: EDI is judged by whether the receiving system reads the message without human hands, not by whether a document travelled.

=== ASSESSMENT Q5 | tests lesson 14.2 ===
QUESTION:
A warehouse manager at a Tema food distributor receives the advance shipping notice for tomorrow's truckload and files it with the other paperwork, remarking that the packing list already travels with the driver, so the notice adds nothing until the goods arrive.

Which option best assesses the remark?

POINTS: 1
OPTIONS:
1. The remark is correct: the advance shipping notice merely repeats the packing list electronically, so it is useful only as a replacement if the paper copy is lost.
2. The remark misses the notice's defining property — it travels ahead of the goods: matched against the purchase order at data level while the truck is still on the road, it lets the warehouse resolve discrepancies in advance and receive by scanning each pallet's SSCC label against a prepared expected-receipt list, turning receiving from a discovery into the verification of an announcement.
3. The remark is correct in practice: electronic data cannot be checked against the purchase order until the goods can be counted, so the notice becomes useful only on arrival at the dock.
4. The remark misses the message family: the notice is the invoice message, so filing it delays payment and the matching against the purchase order.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The advance shipping notice — DESADV in UN/EDIFACT, the 856 in ANSI X12 — is in effect the digital packing list, and its entire advantage is timing: it travels ahead of the goods. Received while the truck is still on the road, it is matched against the purchase order at data level, so a picking error or a quantity disagreement surfaces days before delivery, while the supplier can still correct it cheaply, and the warehouse can build its expected-receipt list. On arrival, each pallet is confirmed by scanning its SSCC label against that list, and the goods receipt assembles itself from the scans instead of from counting and keying. The paper packing list rode with or behind the cargo; the ASN arrives first — that is the whole difference, and it is what makes receiving prepared rather than paperless.

Answer 1 accepts the remark and demotes the notice to an insurance copy for lost paperwork. Answer 3 asserts the impossibility that the pre-matching flow disproves: the data can be checked precisely because the goods have not yet arrived. Answer 4 confuses the message families — the invoice is a separate message, INVOIC or the 810, matched afterwards in the three-way match of purchase order, goods receipt and invoice.

The takeaway: the value of the advance shipping notice lies entirely ahead of the truck.

=== ASSESSMENT Q6 | tests lesson 14.2 ===
QUESTION:
An exporter in Tema ships shea butter to Antwerp under a negotiable bill of lading, because the buyer may resell the goods while they are at sea. The exporter's other documents are already digital: its air-freight consignments moved to the electronic air waybill without difficulty, and its certificates of origin are issued electronically. On that strength, the forwarder proposes scanning the ocean bill of lading and emailing the PDF to the buyer's bank as the electronic original.

Which option best assesses the proposal?

POINTS: 1
OPTIONS:
1. The proposal is sound, because the electronic air waybill and the electronic bill of lading are the same kind of change — replacing paper with an electronic image — and what succeeded for one transport document succeeds for all.
2. The proposal is sound provided the scan is high-resolution and certified by the forwarder, after which the PDF can be endorsed from holder to holder like a paper original.
3. The proposal is unnecessary because negotiable bills of lading can never be replaced by electronic records in any trade, so paper originals must always be couriered.
4. The proposal fails on the dividing line between the two document families: the air waybill is non-negotiable — a receipt and evidence of contract conferring no control of the cargo — so its electronic form needed only procedure and agreement, while a negotiable bill is a document of title that works through possession and endorsement; a scanned PDF can be neither possessed nor controlled, so a valid electronic bill needs a system of control and a legal framework recognising the record, on MLETR principles, with the position varying by country.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

Documents do not digitalise equally because they do not carry equal legal weight. The exporter's easy experiences — the e-AWB and electronic certificates of origin — were non-negotiable documents: receipts and evidence of contract that name parties and record events but confer no control of the cargo, so their replacement required procedure and agreed standards, and it has succeeded at scale. A negotiable bill of lading is the hard case: a document of title, in which possession of the original, properly endorsed, is what controls the goods and transfers ownership mid-journey. A scanned PDF is a picture of that document — it cannot be possessed in the legal sense, endorsed from holder to holder, or controlled — so however crisp the image, it cannot do the bill's work. A genuine electronic bill of lading needs a system establishing who controls the record and a legal framework giving that control the force of possession, on the MLETR principles of legal recognition, functional equivalence and technology neutrality — and because MLETR is a template whose national adoption varies, the legal basis must be confirmed for the specific trade before committing.

Answer 1 generalises the easy case across the dividing line that defines it. Answer 2 upgrades the scan with certification, but endorsement requires possession and control, which no image supports. Answer 3 overcorrects into impossibility, which the e-B/L's existence where law and contract support it disproves.

The takeaway: scanning changes the medium; only law and control change what a record can do.

=== ASSESSMENT Q7 | tests lesson 14.3 ===
QUESTION:
A transport company in Kumasi answers every customer's where-is-my-load question by telephoning the driver, and the answer is only as good as whoever picks up. To improve, the operations manager proposes contracting a predictive-ETA service immediately, reasoning that the most advanced rung of visibility delivers the most value first.

Which option best evaluates the proposal?

POINTS: 1
OPTIONS:
1. The proposal is right: a predictive ETA makes the intermediate steps unnecessary, because a good forecast of arrival answers every question the customer could ask.
2. The proposal is wrong because predictive ETA is unreliable technology that no operation should adopt; the company should instead employ more telephonists to answer customers faster.
3. The proposal skips rungs: the company sits on the reactive rung — visibility exists only while someone is asking — and the next step is event-driven visibility, milestones recorded at source by scans, position reports and sensors so the shipment reports itself; prediction rests on clean events and cannot usefully be automated on top of an ask-and-wait operation.
4. The proposal is unnecessary because the company already enjoys event-driven visibility: the drivers answer promptly when called, which shows events are already flowing into a shared record.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

Visibility is a ladder of three cumulative rungs, and the scenario names the bottom one: every answer requires a telephone call, visibility exists only while someone is asking, and the customer waits — reactive tracking, the manual discipline performed by hand. The next rung is event-driven visibility, in which the shipment reports itself: milestone events recorded once, at source, at the moment they happen — dispatch scans, position reports, sensor readings — flowing to every authorised party without a call. Predictive visibility sits on top, estimating arrival from live conditions so delays are known in time to replan. The rungs cannot be skipped: prediction rests on clean events, and automating on top of an ask-and-wait operation simply delivers absent or wrong answers faster.

Answer 1 endorses the skip and assumes a forecast can substitute for the record it must be computed from. Answer 2 dismisses the technology wholesale and answers a capability gap with headcount, restoring the cost per question that reactive tracking charges — and no number of telephonists makes an answer arrive before the customer asks. Answer 4 misreads prompt human answers as an event stream: however quick the driver is to answer, the record still begins with a request, and no shared event history accumulates.

The takeaway: climb the ladder in order — let the shipment report itself before asking the system to predict.

=== ASSESSMENT Q8 | tests lesson 14.3 ===
QUESTION:
A bottling company in Accra prepares export pallets. A warehouse clerk proposes printing a single SSCC barcode for each product line and fixing identical labels to every pallet of that product, to save label stock: the system, he argues, will recognise the product from any of the labels.

Which option best assesses the proposal?

POINTS: 1
OPTIONS:
1. The proposal confuses the two identifiers: the product is identified by its GTIN — the number encoded in the item's barcode, shared by every unit of that item — while the SSCC is an 18-digit serial that must be unique to each logistics unit, so every pallet needs its own SSCC label to tie that physical pallet to its own contents, order and event history.
2. The proposal is sound, because the SSCC identifies the product inside the pallets, so one label per product is the economical design.
3. The proposal is sound provided the labels are RFID tags rather than printed barcodes, since RFID identification does not require the number to be unique.
4. The proposal is wrong for a different reason: the SSCC should replace the GTIN altogether, because a label on a pallet can carry only one identity at a time.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The proposal collapses the distinction between the two identities the lesson separates. The GTIN, the Global Trade Item Number, identifies the trade item — the product at any packaging level — and it is deliberately shared: every carton of the same product carries the same GTIN, which is how any party in any country recognises the item. The SSCC, the Serial Shipping Container Code, is an 18-digit number identifying a logistics unit — one pallet, container or wrapped load handled as a single physical unit — and its serial nature is the point: each unit built receives its own number, which ties that physical pallet to its contents, its order, and every event scanned against it from packing to receipt. Identical SSCC labels across all pallets of a product would destroy the serial, leaving the system unable to say which pallet is which — no meaningful receipt scanning, no event trail, no custody record when a unit goes missing.

Answer 2 assigns the SSCC the GTIN's job, identifying the product rather than the unit. Answer 3 confuses the reading technology with the identity: RFID is a way of reading a number by radio instead of optics, and the number itself must still be unique. Answer 4 offers the wrong cure — replacing the GTIN — when the two identifiers answer different questions and travel together, the item and the unit it rides on.

The takeaway: the GTIN names the item, the SSCC names the unit, and a serial identity must never repeat.

=== ASSESSMENT Q9 | tests lesson 14.3 ===
QUESTION:
A distributor installs condition sensors on its refrigerated fleet and configures exception alerts to arrive in a shared group mailbox. Months later a consignment of medicines is lost to an undetected temperature excursion: dozens of alerts had arrived in the days before the loss, but nobody reads the mailbox closely, and most past alerts had been sensor faults that never led to any action.

Which option best explains the failure?

POINTS: 1
OPTIONS:
1. The technology failed: condition sensors cannot detect genuine temperature excursions, so the loss was unavoidable.
2. The threshold was set too high, and lowering it so that every reading outside the band raised an alert would have prevented the loss.
3. The failure was distribution, not process: the alerts should also have been sent to every employee's individual mailbox, so that somebody is bound to see each one.
4. The alerts were raised but no response process existed behind them: an alert needs a named owner on every shift, the authority and a written playbook to act, a response window with escalation, and tuning to retire the alerts that never lead to action — without these, an alert that reaches everybody reaches in effect nobody, and constant noise trains the organisation to ignore the channel.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

The lesson's rule is that an alert is the beginning of a response, not the response itself, and four things must be decided before the first alert fires: a named owner staffed on every shift the cargo moves; the authority to act, with the corrective instructions written down in advance as a playbook; a response window with escalation if acknowledgement or action does not happen; and tuning, because every alert costs attention and attention is finite. The scenario fails all four: alerts arrived in an unowned mailbox, nobody held authority, and sensor-fault alerts that never led to action had taught everybody to dismiss the channel — alert fatigue, the standard failure mode of visible operations. The deeper principle is the one this module keeps repeating: automation amplifies the process it is given, so an alert system layered on an absent response process amplifies the absence.

Answer 1 blames the sensors, but the technology raised correct alerts — the loss lies in what never answered them. Answer 2 would deepen the fatigue, because thresholds firing on every reading teach dismissal fastest. Answer 3 adds mailboxes without adding ownership; distribution was never the defect, and wider copying only multiplies the noise.

The takeaway: design who verifies, who acts and who escalates before the technology fires — an alert without a responder is noise.

=== ASSESSMENT Q10 | tests lesson 14.4 ===
QUESTION:
A depot in Takoradi suffers recurring stockouts on a subset of its product range. The depot keeps no organised delivery and stock reports, and its history has never been examined as a whole. The area manager proposes starting with a machine-learning replenishment system, arguing that beginning with the most advanced analytics gives the quickest improvement.

Which option best evaluates the proposal?

POINTS: 1
OPTIONS:
1. The proposal is premature but for a different reason: the depot should first buy a business-intelligence platform, because dashboards must exist before any question can be asked of the data.
2. The proposal inverts the ladder: analytics climbs in order — descriptive reports first, built on history recorded completely and consistently; then diagnostic grouping to find why the stockouts concentrate; then prediction, then prescription — and each rung inherits the quality of the one beneath, so a model trained on history nobody has examined will faithfully reproduce errors nobody has corrected.
3. The proposal is sound, because advanced methods can infer patterns from incomplete records and will clean the stock data as a by-product of learning from it.
4. The ladder should be climbed in reverse: prescriptive replenishment comes first because it acts, and the descriptive reports are produced afterwards to justify the decisions.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The analytics ladder ranks analytics by the question it answers — what happened, why did it happen, what will happen, what should be done — and it is climbed in that order. Descriptive reports come first because they are built from history recorded completely and consistently, and they establish what the operation actually does; diagnostic grouping comes second, concentrating the stockouts by product, supplier, day or order quantity until a cause shows; prediction and prescription come last, and each stage inherits the quality of the one beneath it. A model trained on history nobody has examined will faithfully reproduce errors nobody has corrected — the lesson's phrase is that prediction without description is guessing dressed in mathematics, and a confident forecast built on unreliable records is a fiction formatted as a number.

Answer 1 buys the tool before the question, the tools-first thinking the lesson names as the second standard failure; dashboards serve questions, they do not precede them. Answer 3 credits advanced methods with powers the lesson denies them: a model repeats the pattern it is fed and never cleans it. Answer 4 reverses the ladder entirely, recommending actions against a future nobody has estimated and a history nobody has read.

The takeaway: reports first, diagnosis second, prediction third, prescription last — each rung earns the right to the next.

=== ASSESSMENT Q11 | tests lesson 14.4 ===
QUESTION:
At a demonstration day, a robotics vendor shows autonomous mobile robots gliding through a model warehouse and urges a Tema third-party logistics provider to sign for a full fleet while a discount lasts. The provider's own facility has a congested, disorganised layout, its picking productivity has never been measured, and no problem has been formally defined.

Which option best describes the professionally sound response?

POINTS: 1
OPTIONS:
1. Apply the four questions before any commitment: name the specific, measurable problem the robots would solve; count the total cost beyond the subscription — integration, training, process change, maintenance; check the readiness conditions the equipment depends on; and run a bounded pilot — one zone, with success measures defined in advance — scaling only what the measures support.
2. Sign for the full fleet but skip the pilot, because a working demonstration is stronger evidence than a small in-house trial, and the discount rewards speed.
3. Decline permanently, because robotics cannot be justified in any facility whose layout is imperfect, and no facility's layout is ever perfect.
4. Sign for the full fleet, because a competitor in the same market recently adopted similar robots, and matching a competitor's technology protects market position whatever the provider's own situation.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The four questions convert enthusiasm into evidence, in order. What problem does it solve: the provider must name a specific, measurable problem first, because technology adopted without a named problem buys an answer and then goes hunting for a question. What does it really cost: the subscription is the opening bid, and integration, training, process change and maintenance frequently exceed the visible fee. Is the ecosystem ready: which systems must the robots work with, and can the facility maintain the equipment. What would a pilot prove: a bounded trial — one zone, one shift pattern — with success measures defined before it begins, scaled only if the measures are met. The frame also disciplines fit: the same machines dropped into a disorganised layout simply automate the disorganisation, because automation amplifies whatever process it is given — and an unmeasured picking operation cannot even say what improvement would count as success.

Answer 2 worships the demonstration, which is precisely the curated performance the lesson's absolute rule prohibits: never buy the demo — pilot, measure, then scale; a vendor's model warehouse is not the provider's facility. Answer 3 refuses without questions, but an honest evaluation can end in a bounded pilot, and one genuine bottleneck automated may serve a small operation well. Answer 4 answers a strategy question as a fashion question.

The takeaway: name the problem, count the whole cost, check readiness, pilot with measures — then decide.

=== ASSESSMENT Q12 | tests lesson 14.4 ===
QUESTION:
A trade-finance manager proposes that the company join a blockchain platform for certificates of origin, arguing: an entry on a blockchain ledger cannot be altered, so whatever the ledger records is thereby proven true.

Which option best assesses the argument?

POINTS: 1
OPTIONS:
1. The argument is sound, because tamper-evidence and truth are the same property, which is precisely why a shared ledger can replace verification of the certificates themselves.
2. The argument proves too little: a blockchain allows records to be rewritten freely by its administrators, so certificates on it are less trustworthy than paper originals in a filing cabinet.
3. The argument overstates the technology: a distributed ledger is tamper-evident — entries cannot be quietly changed after entry — but it cannot guarantee that an entry was true in the first place; the promise for trade documents is one shared record among parties who do not fully trust each other, and the platform delivers value only where counterparties, banks and authorities actually use it and the law recognises the record.
4. The argument is sound for certificates of origin but not for bills of lading, because certificates of origin are documents of title and bills of lading are not.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The lesson teaches the promise and the caution in one breath. The promise: a distributed ledger gives parties who do not fully trust one another — exporter, importer, bank, customs — one shared record whose entries cannot be quietly altered, an obvious attraction for certificates of origin and the bill-of-lading chain, and one way to establish who controls an electronic record. The caution is structural: a ledger guarantees that an entry has not been altered since it was entered; it cannot guarantee that the entry was true in the first place. A mistaken or forged certificate recorded on the platform is preserved with perfect integrity, so the manager's argument mistakes tamper-evidence for truth. The second caution is adoption: the platform delivers value only once the counterparties, banks and authorities who must actually use the record are on it, and legal recognition of electronic trade documents varies by country — the questions the four-question evaluation frame exists to ask before joining.

Answer 1 equates the two properties the lesson separates. Answer 2 inverts the finding: the ledger is not less trustworthy than private copies — it removes their quiet divergence — but it is simply not a truth machine. Answer 4 misstates document law: the bill of lading is the document of title; certificates of origin are not.

The takeaway: a shared ledger secures the record after entry; the truth at entry still depends on the discipline of whoever supplies it.

=== FACTS & SOURCES ===
- All twelve questions and their explanations derive solely from the content of the four module 14 lesson drafts (curriculum/drafts/module-14/lesson-14.1.md, lesson-14.2.md, lesson-14.3.md, lesson-14.4.md) and the key terms and learning objectives in the module 14 lesson briefs (curriculum/lesson_briefs/module-14/). No external facts, vendors, platforms, statistics, duty rates, fee amounts or benchmark percentages asserted as fact are introduced anywhere in the assessment; there are no exceptions.
- Institutional facts used within stems and explanations come from the lessons, which source them from the research sheets: the e-AWB as the proven easy case and the negotiable ocean bill of lading as a document of title transferred by possession and endorsement; MLETR (the UNCITRAL Model Law on Electronic Transferable Records) with its three principles and varying national adoption; UN/EDIFACT and ANSI X12 as the two standard families; DESADV/856 as the advance shipping notice and INVOIC/810 as the invoice in the order-to-invoice cycle; the GTIN as the shared trade-item identity and the SSCC as an 18-digit serial identifier of logistics units; the three-way match of purchase order, goods receipt and invoice.
- No question states adoption statistics, savings percentages, ROI claims or vendor names. Technology is judged by function throughout, per WRITING_SPEC.md rule 5.1 and the lessons' DO NOT CLAIM discipline.
- Quantities and references in stems (the eight cartons in bin B-12 in Q2; the dozens of accumulated alerts in Q9) are illustrative scenario details in round terms, requiring no calculation; no stem uses currency, rates, percentages or periods.
- Q1 to Q3 are as taught in lesson 14.1. Q1 applies the which-system-answers-which-question division of labour (ERP value, WMS quantity at bin, TMS load and charges) as a misdiagnosed integration failure, an angle the lesson taught as fact but its own MCQs did not test. Q2 tests the second Important Note — the system sees confirmations, not goods — through a single-bin discrepancy and an adjustment-first proposal, where the lesson's own MCQ3 tested the six-month shelfware post-mortem instead. Q3 extends the freight-audit function from the lesson's what-does-the-audit-do MCQ to a bypass proposal aimed at removing the control, with the sampling and silent-correction misconceptions as distractors.
- Q4 to Q6 are as taught in lesson 14.2. Q4 discriminates EDI's three defining elements against an emailed-PDF process that is electronic but not EDI, complementing the lesson's private-format MCQ rather than repeating it; the identical-software distractor is answered by the standards-based interoperability rule. Q5 evaluates a dismissal of the ASN as a duplicate packing list, centring the ahead-of-the-goods property, the SSCC scan at receipt and the message-family distinction (856 versus 810), where the lesson's own MCQ1 tested what the notice enables. Q6 applies the dematerialisation-versus-transferable-record distinction fresh: the scenario is new (a Tema shea-butter exporter citing its e-AWB success as precedent), and the discriminating centre is the easy-case/hard-case dividing line between non-negotiable receipts and documents of title, with MLETR's varying adoption answering the universal-validity distractor; the lesson's own MCQ3 centred on the scanned-PDF claim alone in a Hamburg scenario.
- Q7 to Q9 are as taught in lesson 14.3. Q7 diagnoses the bottom rung of the visibility ladder (reactive ask-and-wait) and the cannot-skip-rungs rule against a jump-straight-to-prediction proposal, untested by the lesson's own MCQs. Q8 inverts the lesson's SSCC scan MCQ into a labelling design decision: one serial per product line would destroy per-unit identification; the GTIN/SSCC division, the 18-digit serial and the barcode-as-representation rule are the discriminating content. Q9 tests the design side of the alert-needs-a-response-process note — named owner, authority and playbook, response window with escalation, tuning against alert fatigue — through a failure post-mortem, where the lesson's own MCQ1 tested the officer's execution of the response loop; the amplification principle is applied in the explanation.
- Q10 to Q12 are as taught in lesson 14.4. Q10 tests the ladder's ordering and the inheritance rule (each stage inherits the quality of the one beneath; prediction without description is guessing dressed in mathematics) against a start-with-the-most-advanced proposal, where the lesson's MCQ1 tested naming a single rung and its MCQ2 tested the vendor-purchase judgement. Q11 applies the four-question evaluation frame to a robotics pitch, extending the frame with the robotics-specific judgement that machines dropped into a disorganised layout automate the disorganisation; the never-buy-the-demo rule and the fit principle supply the distractors. Q12 tests the blockchain promise/caution pairing — tamper-evident is not truth-creating, and value depends on ecosystem and legal recognition — which no lesson MCQ covered; the document-of-title inversion in distractor 4 reinforces lesson 14.2's distinction.
- Coverage note: each lesson contributes exactly three questions, in lesson order, and every question is scenario-based with at least one application or discrimination question per lesson. The CORRECT positions run 2, 4, 1, 3, 2, 4, 3, 1, 4, 2, 1, 3 across the twelve questions — each position used exactly three times. No question uses negative form ("which is NOT") and no option list includes "All of the above".
