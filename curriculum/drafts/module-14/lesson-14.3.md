# DRAFT — Lesson 14.3: Shipment Visibility, Tracking, and Automation

=== KEY CONCEPT ===
HEADING: Shipment visibility defined: knowing in time to act
BODY:
Lesson 5.4, Shipment Tracking and Customer Communication, taught tracking as a customer-service discipline performed by hand. The clerk who received the question "where is my consignment?" telephoned the carrier, waited, verified the answer, and only then reassured the customer. This lesson digitalises that discipline and adds automation to it — but the definition of success is unchanged.

Shipment visibility is the ability to obtain timely information about the location, movement, and status of goods during transportation. Taught as an operational capability rather than a software feature, visibility means being able to answer three questions about every shipment and handling unit — where is it now, in what condition is it, and when will it arrive — with answers reliable enough, and early enough, to act on before the answer stops mattering. That final clause is the decisive one. An arrival time discovered after the receiving shift has gone home is history, not visibility.

The wider term is operational visibility: the ability to access relevant information about the current status of business activities. Shipment visibility is its transport-facing part; order status and stock position are its office- and warehouse-facing parts, met by the systems of Lesson 14.1, Transport and Warehouse Management Systems.

Visibility earns its cost through four uses that recur throughout this lesson: exception management, catching deviations early enough to correct them; customer communication, answering questions accurately before they are asked; operational planning, building today's work on today's positions rather than yesterday's assumptions; and service reliability, defending the delivery promises that the performance indicators of Lesson 13.4 measure.

=== KEY CONCEPT ===
HEADING: The visibility ladder: from asking, to knowing, to predicting
BODY:
Visibility is not a single state but a ladder of three rungs, and each rung changes who initiates the question and how much time remains to act.

1. Reactive tracking — ask and wait. This is the manual discipline of Lesson 5.4: visibility exists only while someone is asking for it. Every question costs a call or an email, the answer is only as good as the person on the other end, and the customer waits. A disciplined reactive operation succeeds — but each answer is expensive, and none arrives before the customer asks.

2. Event-driven visibility — the shipment reports itself. Milestone events flow into the system automatically from the physical actions that cause them: a scan at dispatch, a position report from the vehicle, a sensor reading from the cargo. The record is made once, at the source, at the moment of the event, and every authorised party reads the same event without a single telephone call. The questions do not disappear; they are answered before they are asked.

3. Predictive visibility — the system looks forward. Beyond the record of what has happened, the system estimates what will happen: an estimated arrival that updates itself from live conditions, so the receiving team hears about the two-hour delay from the data rather than from the driver's last call.

The rungs are cumulative, not alternatives. Prediction rests on clean events, and clean events rest on knowing exactly which physical thing each record describes — the identification backbone of the next block. An organisation cannot skip rungs: automate on top of unreliable events and the errors simply arrive faster.

=== KEY CONCEPT ===
HEADING: The identification backbone: the product, the logistics unit, and the label that ties them
BODY:
Every tracking event must answer two questions: what happened, and to what. The second question is answered by identification, and identification is only useful when every party in the chain names the same thing the same way. This is the identification backbone on which all visibility rests. The standard identifiers used across international logistics come from GS1, the international body behind the standard product and unit identification numbers used in supply chains. Two of its identifiers matter most here.

1. The GTIN, Global Trade Item Number, identifies a trade item — the product itself, at any packaging level: the individual unit, the inner pack, the carton. One teaching point deserves emphasis: the GTIN is a number, encoded in a barcode for machines to read. The barcode is the representation; the number is the identity.

2. The SSCC, Serial Shipping Container Code, is an 18-digit number that identifies a logistics unit — the pallet, the container, the stretch-wrapped load that travels and is handled as one physical unit. Each logistics unit can carry its own unique SSCC, and that one label ties the physical unit to its data: what it contains, which order it belongs to, and every event recorded against it. The SSCC is the number behind "pallet three" — except that, unlike "pallet three", it means the same thing in Rotterdam, Tema, and Accra.

Barcodes and RFID are the two common ways of reading these identifiers. A barcode is read optically, one label at a time, with the scanner's line of sight to the symbol. RFID — radio frequency identification — reads the identifier by radio, without line of sight, and can read many tagged units at once, for example through a portal as a loaded trailer passes. RFID complements the barcode where bulk reading adds value; it does not replace the discipline of recording.

Why standard identifiers matter follows directly. Lesson 3.3, Cargo Types, Packaging, and Handling, taught the marks and labels that let cargo be recognised; Lesson 8.2, Receiving, Put-Away, Picking, and Dispatch, taught the scan disciplines at receiving and dispatch; Lesson 12.3, Coordinating Carriers, Agents, and Regulatory Authorities, taught the coordination of parties who each hold their own papers. A standard identifier is what lets all of those parties read one label and mean the same unit — no relabelling, no private codes, no reconciliation of whose pallet is whose.

=== KEY CONCEPT ===
HEADING: GPS and telematics: tracking the vehicle
BODY:
The Global Positioning System, GPS, is a satellite-based navigation system used to determine position and support location tracking. A receiver on a vehicle, trailer, or container computes its position from satellite signals; when that position is timestamped and transmitted, tracking begins. This is the technology behind the vehicle icon moving across the dispatch screen.

The broader discipline is telematics: the use of telecommunications and information technologies to collect and transmit data from vehicles or equipment. A telematics stream typically carries more than position alone.

1. Position and movement. Where the vehicle is, when it stopped, and how long it stayed — the raw material of progress against plan.

2. Driving data. Speeding, harsh braking, and long idling bear directly on cargo safety and fuel use, and are properly used to coach safer driving rather than to ambush drivers — a boundary this lesson returns to in an important note.

3. Equipment status. For refrigerated equipment, the operating state of the cooling unit reported alongside the position — the machine and the journey together.

How does this support shipment monitoring in practice? The dispatcher watches a fleet instead of a fog: every vehicle's progress against its plan on one screen, a route deviation surfacing as a difference rather than a rumour, an unscheduled long stop visible within the reporting interval. Customers can be given facts — the vehicle is on the corridor north of Kumasi and should reach the depot by mid-afternoon — instead of reassurances.

One limitation belongs inside the definition itself. Position is not condition. A truck can be exactly on time while its cargo is being ruined by heat, because the vehicle is tracked and the cargo is not. Closing that gap needs sensors travelling with the load, which is the next block's subject.

=== KEY CONCEPT ===
HEADING: Tracking sensors and the Internet of Things: sensing the condition of cargo
BODY:
The Internet of Things, IoT, is a network of connected physical devices that collect and exchange information. In logistics, the most important members of that network are tracking sensors: devices used to monitor shipment conditions, location, movement, or other measurable characteristics — attached to the cargo or its packaging rather than only to the vehicle carrying it.

For most sensitive cargo, the decisive conditions are those the cargo itself experiences. A sensor travelling inside the load reports temperature and humidity as the cargo lives them, not as the dashboard of the refrigeration unit claims them. For the cold chain this is the difference between assuming and knowing. Lesson 11.2, Dangerous Goods and Special Cargo Handling, treated temperature-sensitive pharmaceuticals as cargo whose integrity depends on an unbroken temperature band, and Lesson 8.1, Warehouse Functions and Layout, showed the cold room holding that band inside the warehouse. Condition sensors extend the same control onto the journey: the band is now defended from the moment of packing to the moment of delivery.

The record matters as much as the alarm. A condition sensor produces a continuous log — a temperature reading every few minutes across the whole journey. That log is evidence: proof of the conditions the cargo actually experienced, usable to assure a customer, to settle a dispute, or to support a claim under the insurance arrangements of Lesson 11.1. A delivery receipt says the cartons arrived; the condition log says what they went through on the way.

With this block the visibility triple is complete: identity from the identification backbone, position from GPS and telematics, condition from sensors. What turns these streams into a usable picture is the discipline of recording events at defined points — milestones — which the next block organises.

=== KEY CONCEPT ===
HEADING: Milestones, event notifications, and geofenced checkpoints
BODY:
A shipment milestone is a significant event recorded during a shipment's movement or processing. Milestones are the skeleton of visibility: booking confirmed, cargo received at the depot, packed, loaded, departed, transhipped, arrived at the port, cleared, out for delivery, delivered, proof of delivery recorded. Read in order, the milestone stream is the shipment's electronic biography — the same statuses the Lesson 5.4 clerk collected one telephone call at a time, now recorded at the moment each one happens by the scan or system transaction that caused it, the scan-confirmed execution of Lesson 14.1, and carried between the parties in the structured electronic messages of Lesson 14.2, Electronic Data Interchange and Digital Documentation.

An event notification is an automated or manual message reporting a specified operational event or status change. The distinction matters: milestones accumulate in the system as the record; notifications are pushed outward to the people who need to know — the customer told of dispatch and delivery, the receiving warehouse told of a revised departure time.

Geofencing adds automatic checkpoints to the biography. Geofencing is the creation of a virtual geographic boundary used to detect when a tracked device enters or leaves a defined area. The practical uses are immediate.

1. Node arrival without typing. Draw fences around the port gate, the border post, the distribution centre. The vehicle's entry raises the arrival milestone automatically — no human has to remember to record it.

2. Deviation detection. A fence drawn along the planned corridor makes a wrong turning visible as an alert within minutes, not as a next-day discovery.

A caution completes the block: a milestone is an event in a system, not the physical truth itself. Recorded late, recorded in advance, or never recorded when discipline fails, it drifts from reality — which is why data quality has its own block before this lesson ends.

=== KEY CONCEPT ===
HEADING: Estimated time of arrival and the predictive ETA
BODY:
An estimated time of arrival, ETA, is the anticipated time when a transport service or shipment will reach a specified destination. Every delivery promise contains an ETA whether it is managed well or not: the dispatch plan, the emailed delivery date, and the driver's "we will be there by three" are all ETAs of different quality.

A conventional ETA is computed once, at planning, from the schedule and an assumed transit time. It is honest at the moment of calculation and silent thereafter. It does not know about the traffic queue after the bridge, the queue at the border post, or the vessel that left port late — so it degrades quietly as the journey deviates, and the degradation is discovered by whoever depends on it.

A predictive ETA is an estimated arrival time calculated using current and historical information to anticipate shipment progress: the distance remaining, the progress made so far today, the time this class of vehicle usually takes over the next section, the delay this border crossing typically adds at the end of the week. The calculation is one of the established uses of machine learning in logistics — pattern-finding across large volumes of historical movement data — and this lesson treats it qualitatively; Lesson 14.4, Data Analytics and Emerging Logistics Technologies, develops the analytical ideas.

The operational value is timing, not precision for its own sake. A prediction refreshed while there is still time to act converts delay into replanning: the customer is notified with a revised window, the warehouse re-slots the expected receipt, the onward vehicle is rescheduled. Two honest cautions belong in the same breath: a prediction is only as good as the data behind it, and a prediction is a better estimate, not a guarantee — mature operations communicate a window and its updates rather than a false certainty, extending the honesty discipline of Lesson 5.4.

=== KEY CONCEPT ===
HEADING: From visibility to action: exception management
BODY:
Visibility is not the dashboard; it is the earlier decision. The operational purpose of everything this lesson has assembled — identity, position, condition, milestones, estimated arrivals — is to move the moment of discovery of a problem from delivery day to the moment the problem begins. That movement is exception management.

An exception alert is a notification generated when an operational event deviates from defined expectations or conditions: the temperature leaves its band; the estimated arrival slips beyond an agreed tolerance; a vehicle leaves its geofenced corridor; a milestone that was due does not arrive. The alert is raised by rule, not by luck — nobody has to be watching the screen at the moment of deviation.

The alert, however, is only the beginning. A managed exception follows a loop.

1. Detect. The rule compares each event against its expectation and raises the deviation.

2. Verify. Is it real? Sensors drift and fail, a geofence can be drawn wrongly, the plan itself can contain the error. Lesson 5.4 taught the clerk to verify before reassuring the customer; the same professional discipline now applies to machine data — check the trend, the second reading, the context — before acting and before dismissing.

3. Act. A named person issues the corrective instruction: call the driver, dispatch the technician, re-sequence the delivery.

4. Record and learn. The outcome is logged against the shipment, and recurring exceptions feed back into thresholds, routes, and process design.

Exception management also reorganises customer communication. Routine milestone notifications flow to customers automatically; the exception is precisely where a human being should speak — promptly, accurately, with the facts and the corrective plan at hand. Lesson 5.4's communication discipline survives automation; it is aimed instead at the cases that deserve it.

Without the loop, visibility is spectator sport: the operation watches its problems in high resolution and does nothing about them sooner.

=== KEY CONCEPT ===
HEADING: Logistics automation and the automation rule
BODY:
The second half of this lesson is automation. Logistics automation is the use of technology to perform operational tasks with reduced manual intervention, and it takes two forms: physical automation — machines moving, lifting, and picking goods — and administrative automation — software executing routine office work. Both share one heart. Workflow automation is the use of technology to execute or coordinate predefined operational tasks with reduced manual intervention: a sequence of work that fires when its conditions are met, without a clerk starting each step.

The working unit of workflow automation is the automation rule: a defined condition and an associated action used to control an automated process. "When the cargo temperature leaves its band for more than fifteen minutes, alert the duty officer." "When the dispatch scan is confirmed, send the customer the dispatch notification." "When an invoice matches its purchase order and its goods receipt, release it to the payment queue." Every rule is a piece of the organisation's process, written down precisely enough for a machine to execute.

That last phrase carries the lesson's central insight. What automation is: fast, tireless, consistent execution of defined rules, at volumes no clerk could sustain and at hours no clerk should have to work. What automation is not: judgement, negotiation, creativity, or process design. The machine cannot decide what should happen in a case the rules never anticipated — it can only stop and hand the case upward. The rule set is therefore the process made executable, and writing it exposes how well defined the process really is. Vagueness cannot be automated; it can only be routed to a human as a permanent stream of exceptions.

Lesson 14.1 stated the principle that this lesson now extends: technology serves the process. Automation removes the routine and amplifies whatever process it is given — a good process automated becomes good faster, and a broken process automated is broken faster.

=== KEY CONCEPT ===
HEADING: Where automation belongs: processes suited to the machine
BODY:
Automation opportunities are found by testing work against a short list of properties: high volume, repetitive, definable by rules, low in judgement, with errors that are detectable. Four families of logistics work pass the test repeatedly.

1. Document processing. Robotic process automation, RPA, is software that performs repetitive, rule-based office work in place of a person typing. Paired with OCR — optical character recognition, software that reads printed or scanned text into structured fields — it transforms document-heavy processes. The office example this lesson develops shortly is invoice matching: the three-way match of Lesson 8.4, Warehouse Documentation and Stock Reconciliation — purchase order, goods receipt, and invoice agreeing before payment — executed automatically, with people seeing only the mismatches.

2. Routine communication. Booking confirmations, dispatch notifications, delivery notices, and milestone updates are nearly identical every time they are sent: ideal rule-driven work, so that nobody has to remember to inform the customer.

3. Physical warehouse work. Warehouse robotics automates movement inside the facility. The characteristic concept is goods-to-picker: automated equipment brings the storage unit to a workstation where a person picks, instead of a picker walking the aisles taught in Lesson 8.2. The walking between locations — a large invisible cost of manual picking — is removed, while judgement over delicate or irregular items can remain human.

4. Pattern recognition at scale. The established uses of artificial intelligence and machine learning in logistics are qualitative and specific: demand forecasting, the discipline of Lesson 13.1 executed with machine assistance on large data; predictive ETA calculation, taught above; document OCR and extraction; and anomaly detection in track-and-trace data — odd patterns surfaced for human review.

The boundary of the list is as instructive as the list itself. Negotiating with a carrier, resolving a damaged-goods dispute, redesigning a picking layout: judgement, relationship, and design work, and they remain professional human work. Automation takes the routine so that professional time is spent where it earns.

=== KEY CONCEPT ===
HEADING: Benefits, limitations, and the data-quality reality
BODY:
Real-time visibility and automation pay four recurring benefits. Exceptions are caught early, while correction is still cheap. Communication stops depending on chasing: facts flow before questions are asked. Planning runs on current positions instead of yesterday's assumptions. And service reliability becomes defensible: the promises measured by Lesson 13.4's indicators — on-time and in-full delivery among them — are monitored, explained, and improved on evidence rather than anecdote.

The limitations deserve equal billing, because they shape how the capability must be built.

1. Events lag reality. The scan happens after the loading; the position report arrives at intervals; the sensor reads every few minutes. The honest term is near-real-time, and decisions should respect the lag.

2. Devices fail. Sensors drift, power runs out, coverage drops in valleys and border queues. Absence of data is not absence of trouble — and an operation that instruments only its critical lanes has made a sensible choice, not a failure.

3. Data quality decides the ceiling. A mislabelled unit is tracked flawlessly to the wrong truth; a stale address automates a misdelivery. Identification discipline, master-data hygiene, and the reconciliation habits of Lesson 8.4 set the maximum quality of any visibility the systems can display.

4. System reliability is part of visibility. When the platform is down, the operation must not be blind: fallback procedures — the telephone habits of Lesson 5.4, kept alive on paper — remain the professional insurance.

5. Precision costs. Instrumenting every carton on every lane is rarely justified; fit the tracking to the value and risk of the cargo, the same fit principle Lesson 14.1 applied to systems themselves.

These facts also give the evaluation discipline this lesson's final objective asks for: map the questions staff ask repeatedly and the exceptions that recur; measure the current baseline with Lesson 13.4's indicators; automate the stable, rule-defined work first; and keep human judgement on the exceptions. The deeper analytical uses of the data this produces belong to Lesson 14.4.

=== WORKED EXAMPLE ===
HEADING: A cold-chain excursion caught live — and the same journey without visibility
BODY:
A pharmaceutical distributor in Accra dispatches a refrigerated truck — a reefer, in industry shorthand — carrying 300 cartons of temperature-sensitive medicines from its cold rooms to its branch in Tamale. The agreed temperature band for the journey is between two and eight degrees Celsius. All figures in this example are illustrative for teaching purposes.

Each carton bears the product's GTIN in its barcode; the 12 pallets each carry their own SSCC label; the reefer reports position and cargo temperature through its telematics every ten minutes.

Step 1: The alert. At 01:40 the duty officer's phone raises an exception alert: cargo temperature has read above the band for three consecutive readings, currently 11 degrees. The automation rule behind it — temperature outside the band for more than fifteen minutes — fired by itself.

Step 2: The verification. Before waking anyone, the officer applies Lesson 5.4's discipline to machine data: is it real? The trend shows a steady climb over thirty minutes, not a single false reading; the last door-open event was hours earlier; the refrigeration unit reports running. The excursion looks genuine.

Step 3: The corrective instruction. The officer telephones the driver with a verification script: check the unit's display and the door seals. The driver finds a rear door seal working loose and reports the unit struggling to hold temperature. The instruction: continue at reduced speed, keep the doors closed, watch the unit, report every thirty minutes. A service technician is arranged to meet the truck at a depot en route.

Step 4: The record. Temperature returns into the band by 03:20. The condition log, the alert, the calls, and the technician's report are attached to the shipment record. At delivery in Tamale the receiver scans each pallet's SSCC, sees an unbroken band since the repair, and accepts the cargo on evidence rather than hope.

The alternative ending needs no new technology, only its absence. The same seal fails on an unmonitored truck. The driver, unaware, delivers on time; the Tamale receiver's spot check finds warm cartons at 09:00; the consignment is quarantined in full; and with no condition log, the dispute over where the loss occurred has no evidence to rest on.

What does this example demonstrate? Visibility moved discovery from delivery morning to forty minutes after the excursion began, at a cost of one alert and two telephone calls. The technology raised the alarm; the named officer, the verification habit, and the corrective instruction saved the cargo.

Lessons from the example: the alert is only the trigger — the designed response is the cure. Condition data is evidence as well as alarm. And without instrumentation, the same failure is discovered by the customer.

=== WORKED EXAMPLE ===
HEADING: One pallet label, three scans: an SSCC handover from Rotterdam to Tema
BODY:
A beverage exporter near Rotterdam consolidates a customer order into 24 pallets for ocean shipment to Tema. Each carton carries the product's GTIN; each pallet, once built and stretch-wrapped, carries one SSCC label. All arrangements and figures in this example are illustrative for teaching purposes.

Step 1: At packing. As each pallet is completed in the Rotterdam distribution centre, its SSCC is scanned and the cartons on that pallet are recorded against it. The scan creates the first milestone — packed — and feeds the electronic despatch advice, the advance-notice message of Lesson 14.2, whose key data element is precisely this list of SSCCs. The importer in Tema knows, before the vessel sails, exactly which 24 units to expect.

Step 2: At loading. The 24 pallets travel to the terminal and the container is stuffed. A scan at stuffing creates the loaded milestone against each SSCC; a further scan at the terminal confirms receipt of the container. Nobody writes "24 pallets gone" on a note — each unit reports itself.

Step 3: At receipt. Weeks later the container is devanned at the importer's Tema warehouse — the receiving discipline of Lesson 8.2 in its electronic form. Each pallet's SSCC is scanned at the dock; the system matches it against the despatch advice, retrieves the contents, and records received — pallet by pallet, not by guess. Twenty-three pallets match within minutes. The twenty-fourth shows as received in the carrier's records but not in the warehouse.

Step 4: The reconstruction. Because each pallet has carried one identity since Rotterdam, the event trail answers the dispute question without a telephone call: packed — recorded; stuffed — recorded; received at the terminal — recorded; discharged — recorded; devanned — no scan. The unit went missing in the devanning and receiving stage, and the parties can go straight to the right yard, the right shift, and the right record. Custody — who held the unit, and when — has been reconstructed from event data alone, in the spirit of the cargo-integrity discipline of Lesson 11.3, Supply Chain Security and Cargo Integrity.

What does this example demonstrate? A standard identifier turns a pallet from "one of twenty-four, hopefully" into an addressable unit whose biography any authorised party can read: one identity, many readers, no reconciliation meetings.

Lessons from the example: the SSCC ties the physical unit to its data for the whole journey. Scans at handover points build the custody record automatically. And the gaps in an event trail are as informative as its entries — they say where to look.

=== WORKED EXAMPLE ===
HEADING: Document automation in the office: the three-way match, automated
BODY:
Kwabena Trading Ltd, an importer and distributor in Accra, processes around 300 supplier and carrier invoices a month — machinery parts, packaging materials, and freight. All figures in this example are illustrative for teaching purposes.

Before automation, the process ran by eye. A clerk received each invoice — on paper or as a scanned image — typed its lines into a spreadsheet, found the matching purchase order and the goods receipt note, and compared quantities and prices line by line. Matched invoices went to the manager for payment approval with a handwritten tick; mismatches went into a folder of disputes. The work was accurate on a good day, slow every day, and hostage to the clerk's absence.

The company then automated the routine.

Step 1: Capture and reading. Invoices arrive at one electronic address. OCR reads each document — supplier name, invoice number, dates, and every line's description, quantity, and price — into structured fields, without retyping.

Step 2: The automated match. A workflow automation applies the three-way match of Lesson 8.4 as rules: each invoice's lines against the purchase order's lines against the goods receipt recorded in the warehouse system of Lesson 14.1. The comparison is complete — every line of every invoice, not a sample.

Step 3: Split by outcome. Of the 300 invoices in a typical month, around 270 match within tolerance and flow to the payment queue with their evidence attached. Around 30 fail — a price variance, a receipt without an invoice, an invoice without an order reference. Each failure routes to a clerk's exception queue, both documents displayed side by side, with the mismatch named.

Step 4: The human work that remains. The clerk investigates only the exceptions: queries the supplier, checks the delivery, obtains the missing reference — the reconciliation judgement of Lesson 8.4, applied where judgement is actually needed. The manager approves genuine exceptions only. The same rule engine sends routine status notifications to customers and suppliers as a by-product of the milestone events arriving from the transport operation.

What does this example demonstrate? Automation did not automate the office; it automated the routine of the office. The typing disappeared, the comparison became complete, and the people moved from transcription to judgement.

Lessons from the example: automate the routine; keep the exception human. A complete automated match is more reliable than a sampled manual one. And the volumes here are illustrative — what matters is the new split of work, not the numbers.

=== IMPORTANT NOTE ===
HEADING: Visibility is not surveillance
BODY:
A visibility system watches cargo; it must never become an instrument for watching people. The distinction deserves precision, because the same data streams serve both temptations. Telematics records where a driver is and how the vehicle is driven; condition sensors record what happens inside a load; milestone records show who scanned what, and when. All of it exists to protect the cargo, keep the delivery promise, and improve the process — those are the only purposes this lesson justifies.

Three boundaries keep the capability honest.

1. Data serves the operation. Driving data is for safety coaching and service reliability, not for building a culture of ambush. When tracking is experienced purely as suspicion, the response is predictable — devices unplugged, workarounds invented, records degraded. The data-quality reality of this lesson is partly a trust question.

2. Commercial confidentiality. A customer's shipment data reveals trading patterns, volumes, and counterparties — commercially sensitive information. Visibility data is shared with the parties who need it for the movement, under the security and compliance disciplines of Lesson 14.2, not more widely because it happens to be convenient.

3. Evidence before blame. The condition log and the event trail exist to establish what happened and to fix the process. A management habit that reaches for the nearest individual before examining the process teaches the organisation to hide events, not to record them — and hidden events are lost visibility.

Remember: visibility is a service to the operation. The moment it is experienced primarily as watching, it stops producing honest data — and honest data is the entire product.

=== IMPORTANT NOTE ===
HEADING: An alert without a response process is noise
BODY:
The most common way visibility disappoints is not bad technology; it is alerts with no answer to the question: who acts? An exception alert that reaches nobody, or reaches somebody without authority, or reaches everybody, reaches — in effect — nobody. Worse, it teaches the organisation to ignore alerts.

A functioning alert needs four things decided before the first alert fires.

1. A named owner. A duty officer, a shift supervisor, a transport controller — one role, staffed on every shift the cargo moves, that receives the alert and owns the response.

2. Authority and a playbook. The owner must be able to act without assembling a meeting. The corrective instructions for the foreseeable exceptions — reefer excursion, corridor deviation, missed milestone — are written down in advance. The cold-chain worked example succeeded because the officer already knew the script.

3. A response window and escalation. A defined time to acknowledge, a defined time to act, and a defined escalation if neither happens — otherwise an alert at two in the morning is decoration.

4. Tuning. Every alert costs attention, and attention is finite. Thresholds that fire constantly train people to dismiss them; alert fatigue is the standard failure mode of visible operations. Review which alerts led to action, and retire or retune the ones that never do.

The design order matters: first the process — who verifies, who acts, who informs the customer, in the Lesson 5.4 tradition — then the technology that triggers it. An alert is the beginning of a response, not the response itself.

=== IMPORTANT NOTE ===
HEADING: Automation rewards the disciplined
BODY:
Automation executes whatever it is given, at machine speed and without fatigue — including mistakes. This closing note joins Lesson 14.1's principle to the practice of this lesson: technology serves the process, and automation amplifies the process it is served.

The practical consequence is a sequence, and the sequence is the discipline.

1. Stabilise the process first. If invoice matching is chaotic by hand, automation will produce chaos with complete audit trails, faster. Define the process, write it down, and make it work manually — the manual disciplines of Lessons 5.4 and 8.4 are the specification the automation will encode.

2. Clean the data before the rules. Duplicate item codes, stale addresses, unit numbers reused between shipments: each is a small error by hand and a systematic error automated. The identification backbone of this lesson — GTIN and SSCC, one label read identically by every party — is as much a data-hygiene project as a technology project.

3. Then automate, and watch the exception queue. The exceptions are the honest report on the process: every recurring mismatch names a defect in data, documents, or design. Fixing causes rather than adjusting records — Lesson 8.4's rule — is what turns an exception rate downward.

The encouraging truth is that the organisations most ready for automation are often the least impatient for it: those already running disciplined processes find automation almost unexciting, because it simply does what they already do, faster. And the professional skill that survives every round of automation is the one this lesson has returned to throughout — reading an exception, judging it, and acting on it. The machine supplies the alarm; the professional supplies the answer.

=== MCQ 1 ===
QUESTION:
At 01:00, a distributor's duty officer receives an exception alert: a reefer trailer carrying medicines from Accra to Tamale reports cargo temperature of 11 degrees Celsius, above the agreed band, sustained for twenty minutes.

Which statement best describes what must happen for the visibility system to have value in this situation?
POINTS: 1
OPTIONS:
1. The alert should be acknowledged in the system, so that the record shows the notification was received and read.
2. A named duty officer should verify whether the reading reflects a genuine excursion, issue a corrective instruction, and record the outcome, because the alert is only the trigger for a designed human response.
3. The system should be left to correct the temperature automatically, since sensor data is more reliable than human intervention.
4. The distributor should take no action until delivery and then inspect the cartons at the receiving warehouse, because sensor readings taken at night are unreliable.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

An exception alert is a trigger, not a response. The lesson's exception-management loop runs detect, verify, act, record: the officer first applies the verify-before-acting discipline of Lesson 5.4 to the machine data — checking the trend, the second reading, and the context to separate a genuine excursion from a sensor fault — then issues a corrective instruction to a named person, and records the outcome against the shipment. The cold-chain worked example showed exactly this sequence saving the cargo.

Answer 1 confuses acknowledgement with action: a record of receipt cures nothing. Answer 3 misstates the technology — the system raises the alarm, but inspection, instruction, and repair remain physical, human work. Answer 4 repeats the precise failure demonstrated in the unmonitored ending of the worked example: waiting for delivery converts a small correctable excursion into a quarantined consignment with no evidence.

The takeaway: an alert is worth only as much as the designed response behind it, and an alert without a responder is noise.

=== MCQ 2 ===
QUESTION:
At a Tema warehouse, a receiver scans the single label on a stretch-wrapped pallet. The system immediately shows which order the pallet belongs to, which cartons it contains, when it was packed abroad, and when it was stuffed into the container.

Which statement best describes what the SSCC on that label did?
POINTS: 1
OPTIONS:
1. It identified each individual product inside the cartons, replacing the need for product-level item numbers.
2. It is the barcode symbol printed on the label, and any barcode scanned anywhere returns the same information.
3. It is an 18-digit number that uniquely identifies the logistics unit itself, tying the physical pallet to its data so that every party reading the same number means the same pallet.
4. It transferred custody and ownership of the pallet to the receiver at the moment of scanning.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The SSCC, the Serial Shipping Container Code, is an 18-digit identifier of the logistics unit — the pallet or container handled as one physical unit. Because every party reads the same number from the same label, the physical pallet and its data — contents, order, and the milestone trail from packing to receipt — remain tied together across the whole journey, which is exactly what the custody reconstruction in the Rotterdam-to-Tema worked example relied upon.

Answer 1 confuses the SSCC with the GTIN: the product is identified by the GTIN, the logistics unit by the SSCC — the item and the unit are different identities answering different questions. Answer 2 makes the twin error of treating the barcode, the printed symbol, as the identity; the barcode is only one way of encoding the number. Answer 4 confuses identification with ownership: a scan records an event and evidence of custody, but title depends on the contract and the transport documents, not on the label.

The takeaway: one standard identifier, read identically by every party, is what allows a shipment to report itself.

=== MCQ 3 ===
QUESTION:
A logistics manager in Accra lists the office's daily frustrations: retyping supplier invoice lines for matching, copying delivery updates to customers by hand, and re-keying dispatch details between two systems.

Which statement best describes which of these activities suit workflow automation, and what remains for people?
POINTS: 1
OPTIONS:
1. High-volume, repetitive, rule-definable activities suit automation, and the staff's work shifts to handling the exceptions and improving the process.
2. Any activity performed slowly enough by staff can be automated once the software is sufficiently advanced, leaving no logistics staff in the office process.
3. Only physical tasks such as warehouse picking can be automated; office paperwork must always remain manual because documents need human reading.
4. Automating an error-prone process will repair it, because software does not repeat the mistakes that people make.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The suitability test taught in this lesson has four properties: high volume, repetitive, definable by rules, and low in judgement. Retyping invoice lines — particularly with OCR reading the document into structured fields — sending routine status notifications, and re-keying data between systems all pass it. The office worked example showed the three-way match automated with people handling only the mismatches. What remains for people is precisely the judgement work: investigating exceptions, resolving disputes, and improving the process that the rules encode.

Answer 2 overstates the reach of automation: judgement, negotiation, and design cannot be automated — only the routine. Answer 3 reverses the lesson: document processing was the first family of automation taught, while physical work such as picking is a separate family, and both can be automated where volume and rule-definition justify it. Answer 4 repeats the misconception Lesson 14.1 dismantled: a broken process automated is broken faster, because automation amplifies whatever it is given.

The takeaway: automation takes the routine and rewards the disciplined; the exception remains the professional's work.

=== FACTS & SOURCES ===
- Definitions of shipment visibility, GPS, telematics, shipment milestone, event notification, geofencing, workflow automation, exception alert, ETA, predictive ETA, IoT, tracking sensor, automation rule and operational visibility follow the lesson brief 14.3 key terms. — source: lesson brief 14.3, Key Terms (curriculum database).
- GS1 identification: the GTIN identifies a trade item at any packaging level and is the number encoded in barcodes, not the barcode itself; the SSCC is an 18-digit number used to identify logistics units (pallets, containers) and is a key advance-ship-note data element. — source: research sheet logistics-scm-frameworks.md, section 9.
- RFID identifies tagged objects by radio without line of sight and complements barcodes where bulk or portal reads add value. — source: research sheet logistics-scm-frameworks.md, section 9.
- Track-and-trace is seeing where a shipment is and what has happened to it via scan and status events; IoT telematics and cold-chain sensors provide GPS position, driving behaviour, and temperature and humidity in near-real time, enabling cold-chain excursion alerts. — source: research sheet logistics-scm-frameworks.md, section 9 (qualitative concepts).
- AI/ML uses are taught qualitatively with no performance claims: demand forecasting, ETA prediction, document OCR and extraction, and anomaly detection in track-and-trace. — source: research sheet logistics-scm-frameworks.md, section 9.
- Warehouse robotics (goods-to-picker concept) and RPA for repetitive document processing are taught qualitatively as automation concepts without vendor names or performance claims. — source: research sheet logistics-scm-frameworks.md, section 9 (automation, qualitative) and general business knowledge.
- The three-way match — purchase order, goods receipt and supplier invoice agreed on quantities and prices before payment, with discrepancies investigated first — is the standard invoice-checking control automated in this lesson. — source: research sheet logistics-scm-frameworks.md, section 3.
- The advance ship notice / despatch advice (EDI 856 / DESADV) is the electronic notice of the units that will arrive, and EDI and APIs are the transmission channels for milestone events between parties, treated fully in lesson 14.2. — source: research sheet logistics-scm-frameworks.md, section 9.
- Cross-lesson references: the verify-before-reassuring and customer-communication discipline from Lesson 5.4; scan discipline at receiving and dispatch from Lesson 8.2; reconciliation and investigate-before-adjusting from Lesson 8.4; cold rooms from Lesson 8.1; temperature-sensitive pharmaceuticals from Lesson 11.2; cargo integrity and custody from Lesson 11.3; cargo marks and labels from Lesson 3.3; multi-party coordination from Lesson 12.3; demand forecasting from Lesson 13.1; OTIF and service indicators from Lesson 13.4. — source: lesson briefs and drafts of the referenced lessons (curriculum).
- No vendor names, no IoT hardware specifications, no ROI or savings claims, and no adoption statistics are used anywhere in the lesson; technologies are taught by function. — source: WRITING_SPEC.md rule 5.1 and research sheet logistics-scm-frameworks.md, DO NOT CLAIM item 10.
- All quantities, temperatures, times, volumes and company situations in the worked examples and inline illustrations (the Accra distributor's 300-carton consignment on 12 pallets with an illustrative two-to-eight-degree band; the Rotterdam exporter's 24 pallets; Kwabena Trading Ltd's roughly 300 monthly invoices with around 270 matching) are illustrative for teaching purposes. — source: WRITING_SPEC.md rule 5.1.
- The visibility ladder (reactive, event-driven, predictive), the exception-management loop (detect, verify, act, record), alert ownership and tuning against alert fatigue, the near-real-time qualifier, and the goods-to-picker description are general business knowledge presented without attribution. — source: general business knowledge.
