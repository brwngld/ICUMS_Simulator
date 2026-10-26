# DRAFT — Lesson 13.4: Logistics Performance Indicators and KPIs

=== KEY CONCEPT ===
HEADING: From opinion to management: performance measurement and KPIs
BODY:
Module 13 has built the plans: Lesson 13.1, Demand Forecasting and Supply Planning, produced the forecast; Lesson 13.2, Transport Route and Network Optimisation, shaped the routes; Lesson 13.3, Inventory Optimisation and Service Levels, set the stock policies. This lesson closes the module with the discipline that decides whether those plans actually work: performance measurement, the systematic collection and analysis of information used to evaluate operational results.

The central instrument of performance measurement is the key performance indicator, usually written KPI. A KPI is a measurable indicator used to evaluate progress towards a defined operational or business objective. Two parts of that definition matter. A KPI is measurable, meaning it is computed from operational records by a stated formula; and it is tied to an objective, meaning somebody decided in advance what level represents success. Many things in a warehouse can be counted, but a count becomes a KPI only when it has a formula, a target, a data source, and an owner.

Monitoring matters because logistics work is dispersed, time-critical, and judged by customers who do not care about internal explanations. Performance monitoring serves five purposes.

1. It makes service visible. Without measurement, a business learns about late deliveries when customers complain; with measurement, it knows its delivery reliability before the customer tells it.
2. It exposes inefficiency. Costs, idle capacity, and errors hide inside daily routine until a number names them.
3. It enables targets. A target set against measured baseline is a commitment; a target set against a feeling is a wish.
4. It supports continuous improvement, the ongoing approach of identifying and implementing changes that improve processes and performance. You cannot improve what you never measure.
5. It turns argument into evidence. Meetings about whether service is good enough end quickly when both sides read the same number.

In short, measurement converts logistics from opinion into management.

=== KEY CONCEPT ===
HEADING: The behaviour rule: people optimise what you measure
BODY:
A familiar saying in management holds that what gets measured gets managed. The deeper truth is sharper: people optimise what you measure. Staff and managers adapt their behaviour to the indicators placed before them, rationally, because measurement is how their work is judged. The design question is therefore not whether to measure, but whether the chosen measures reward the right behaviour, or whether they reward cleverly wrong behaviour.

Consider three measures steering somewhere their designers never intended.

1. A transport fleet measured only on cost per load will learn to wait. Holding departures until every truck is full cuts the cost per load beautifully, and quietly destroys delivery reliability, because orders now wait for the truck rather than the reverse.
2. A warehouse measured only on picking speed will learn to rush. Lines picked per hour climbs, and order accuracy slides, because speed measured alone is speed purchased with errors.
3. A distribution team measured only on on-time delivery will learn to split orders. Delivering whatever is ready on time protects the number while customers receive half-deliveries.

In each case no dishonesty is required, only a badly aimed measure. The lesson for the KPI designer is to define, for every indicator, the behaviour it is supposed to encourage, and to check that no reasonable person could improve the number while damaging the business. Where such a loophole exists, pair the measure with its counterweight: speed with accuracy, cost with service, availability with cost of carrying stock. The behaviour rule also explains why a few well-chosen indicators outperform a dashboard of everything, as the hierarchy discussion below develops.

=== KEY CONCEPT ===
HEADING: Organising the KPI set: leading and lagging indicators, and the hierarchy
BODY:
Performance indicators differ in when they speak. A lagging indicator reports a result after the fact — last month's OTIF, last quarter's claims ratio, the freight cost per unit actually paid — and is indispensable for accountability: it records the score honestly. A leading indicator predicts a result before it arrives, by measuring the conditions that produce it. Inventory accuracy leads service: records that disagree with the shelf today become tomorrow's short deliveries. Dock-to-stock time, the elapsed time from a vehicle's arrival at the receiving dock until goods are put away and pickable, leads dispatch reliability. Forecast error, measured by the MAPE taught in Lesson 13.1, Demand Forecasting and Supply Planning, leads availability; capacity utilisation trends lead cost and service pressure, because a fleet filling towards its limits will soon miss service or pay overtime and spot rates. A balanced set holds both kinds: lagging indicators tell management the score, leading indicators forecast the score while there is still time to change it — a review built only on lagging numbers is an inquest, a review built on both is a steering instrument.

The second organising principle is the hierarchy of three levels, each feeding the one above. Strategic KPIs are a small set, usually fewer than ten, tied to the service promise and the business plan — OTIF, overall logistics cost trend, inventory days of supply — reviewed monthly to answer one question: are we keeping the promises the strategy makes? Operational KPIs are process measures reviewed weekly or monthly by the managers who run the operation — order cycle time, freight cost per tonne-kilometre, inventory accuracy, vehicle capacity utilisation. Task-level KPIs are daily or per-shift measures used by supervisors and teams, such as lines picked per labour hour and orders dispatched per vehicle. The hierarchy works through cascade: lines picked per hour feeds order cycle time, and order cycle time feeds OTIF. A task-level number that cannot be traced upward to any operational or strategic objective is measuring habit rather than purpose, and should be challenged.

Together the two principles enforce the few-well-chosen rule: each level and each family carries only what its audience can act on — a handful at the top, more detail operationally, the most granular at task level. A single flat dashboard of forty indicators serves nobody; a measure must earn its place by changing a decision, otherwise it is decoration with a formula.

=== KEY CONCEPT ===
HEADING: Service KPIs: measuring delivery reliability and order accuracy
BODY:
Service KPIs measure whether the promise made to the customer was kept. Three indicators carry most of the weight.

1. On-Time Delivery
On-time delivery, OTD, is the proportion of deliveries completed within the specified delivery time requirements. The usual formula is: OTD percentage equals deliveries completed on time, divided by total deliveries, multiplied by 100. It measures the time half of the promise. Its weakness is that a delivery counted as on time may still be incomplete.
2. On-Time In-Full
On-time in-full, OTIF, is the proportion of orders delivered within the agreed time and with the complete required quantity. The formula is: OTIF percentage equals orders delivered both on time and in full, divided by total orders delivered, multiplied by 100. OTIF is deliberately strict: an order fails if it is late or short, and an early but incomplete delivery still fails. One number, two conditions, no averaging.
3. Order Accuracy
Order accuracy is the degree to which fulfilled orders match customer requirements: the right product in the right quantity, verified when the order is prepared and again at receipt. It isolates the picking and packing quality that OTIF blends with transport performance.

The composite service measure is the perfect order rate, which extends OTIF with two further conditions: the goods arrived undamaged, and the documentation and invoice were correct. Because one order must clear all conditions at once, some conventions compute it by multiplying the component success rates. The product is punishing. Illustrative figures: four components of 95, 95, 99 and 98 per cent multiply to roughly 87.6 per cent, although every component looks strong. This multiplicative fragility is the perfect order's whole point: it prices every failure into one number.

=== KEY CONCEPT ===
HEADING: Speed KPIs: order cycle time and the parts of lead time
BODY:
Service KPIs say whether the promise was kept; speed KPIs explain the promise itself and diagnose why it is missed.

The central measure is order cycle time, the time between receipt of an order and completion of the defined fulfilment process, from order entry through picking and dispatch to completed delivery. It is measured per order and reported as an average, but the average alone misleads. An illustrative operation reports a two-day average order cycle time; the worst orders took five. The average hides the customers who suffered. Report the average and the spread, the worst cases and how often they occur, because the tail of the distribution is where broken promises live.

Order cycle time is the customer-facing sum of a set of components that sit inside the wider idea of lead time, the elapsed time from order or replenishment trigger to receipt of goods. Its components are worth separating, because each has a different owner and a different cure.

1. Order processing: entry, verification, credit and confirmation.
2. Preparation: picking, packing, and staging for dispatch, governed by warehouse process discipline as taught in Lesson 8.2, Receiving, Put-Away, Picking, and Dispatch.
3. Transport: the transit leg, governed by the route and network decisions of Lesson 13.2.
4. Crossing borders: order processing, preparation, transit and customs clearance all count internationally, which is why imported lines carry structurally longer and more variable lead times.

The diagnostic power of the split is simple. When order cycle time deteriorates, the component view shows which stage absorbed the time, and corrective effort goes where the time went rather than where anecdote points.

=== KEY CONCEPT ===
HEADING: Cost KPIs: freight cost, cost per shipment, and the cost of holding stock
BODY:
Cost KPIs answer a different question from service KPIs: are we buying this service efficiently? Three families matter.

1. Freight cost measures
Freight cost per unit divides total freight spend by units shipped, such as per pallet delivered. Freight cost per tonne-kilometre divides spend by tonnes moved multiplied by kilometres travelled, the standard comparator between lanes and modes because it normalises for both weight and distance. An illustrative shipment of 10 tonnes carried 200 kilometres at a total cost of 1,000 GHS has a cost of 0.5 GHS per tonne-kilometre. Figures of this kind are illustrative for teaching purposes.
2. Cost per shipment
Cost per shipment is the logistics cost allocated to an individual shipment under a defined costing method. The closing phrase carries the discipline: the allocation rule must be stated and kept identical month after month, because a trend in which fuel was included one month and excluded the next measures the accountant's mood, not the operation.
3. Cost of carrying stock
Inventory turnover and days of supply, taught in Lesson 8.3, Inventory Control, FIFO, and FEFO, and applied in Lesson 13.3, belong in every logistics cost review because stock is bought logistics capacity. Restated briefly: inventory turnover equals cost of goods sold divided by average inventory, and days of supply equals average inventory divided by average daily usage; state which denominator you used. Falling turnover means money standing on shelves.

Above all three sits the cost-to-serve idea, which extends the total-cost lens of Lesson 10.1, Components of Total Logistics Cost, downwards to the individual customer or channel: the full cost of serving one customer, including order handling, picking, delivery frequency, and returns. Cost-to-serve explains a truth that flat cost averages conceal: two customers buying the same revenue can cost very different amounts to serve.

=== KEY CONCEPT ===
HEADING: Asset and quality KPIs: utilisation, accuracy, and damage
BODY:
The third cluster of indicators watches the assets the business owns and the quality of the work done with them.

1. Capacity and transport utilisation
Transport utilisation is the proportion of available transportation capacity used during operations, and the same utilisation logic applies to containers and warehouse space: used capacity divided by available capacity, multiplied by 100. Utilisation is the core efficiency lever for both cost and emissions, and its most visible failure is empty running, travelling without paying cargo.
2. Warehouse productivity
Warehouse productivity is a measure of warehouse output relative to resources such as labour hours or equipment time, for example lines picked per labour hour. Its standing warning comes from the behaviour rule: productivity measured alone invites errors, so it is always read alongside accuracy.
3. Inventory accuracy
Inventory accuracy is the extent to which recorded inventory information matches verified physical stock, usually expressed as counted locations matching the record within tolerance, divided by locations counted, multiplied by 100. It is the output measure of the cycle counting taught in Lesson 8.3, resting on the record discipline of Lesson 8.4, Warehouse Documentation and Stock Reconciliation.
4. Dock-to-stock time
The elapsed time from arrival at the receiving dock to goods being put away and pickable. It is a leading indicator for dispatch reliability and a test of receiving discipline.
5. Claims and damage ratio
The value or number of damage and loss claims expressed as a share of shipments or of freight spend. It is a quality signal with a direct cost tail, and sensitive trades such as cold-chain food or pharmaceuticals watch it more closely than almost any other measure.
6. Forecast MAPE
The mean absolute percentage error taught in Lesson 13.1 measures planning quality, feeding the safety stock and service-level decisions of Lesson 13.3.

Quality measures are frequently the leading indicators of service measures: accuracy and damage today predict OTIF next month.

=== KEY CONCEPT ===
HEADING: Targets and actuals: baseline first, then promise
BODY:
A performance target is a defined level of a defined indicator, to be achieved by a defined date. An actual result is what measurement reports. The difference between the two is not an accounting nicety; it is the working agenda of every review meeting, because the gap is where management attention belongs. Confusing the two is a common failure: reporting the target as if it were the result confuses a plan with an achievement.

How are sound targets set? Three steps, and the order matters.

1. Baseline first
Measure before you manage. Establish what the indicator actually is today, computed by the agreed formula from honest records, for at least one full normal period. A baseline month of clean data is worth more than any borrowed number, because it is the only figure that describes this operation.
2. Target from your own trend and your own promise
Set the target just beyond the baseline, in the direction the service promise requires, with a date. Illustrative: OTIF measured at 89 per cent becomes a target of 92 per cent for next quarter, then 95 per cent the quarter after. The size of the step should reflect what the operation can resource, not what a conference chart once showed.
3. State the definition with the number
An indicator published without its formula and data source is not comparable across months or companies, so the definition travels with every target and every actual.

The comparison of performance against internal targets, historical results, or relevant external standards is called benchmarking, and it is a legitimate discipline when used carefully: your own targets, your own history, and the practices of others all inform. What benchmarking must never become is target-shopping, the importation of impressive numbers achieved by other businesses under other conditions. The next sections give that warning its full weight.

=== KEY CONCEPT ===
HEADING: Reading KPIs together: tension, balance, and the road to customer satisfaction
BODY:
No operational KPI should be read alone, because indicators push against one another. Freight cost per unit can fall because consolidation stretched delivery times. Warehouse productivity can rise because picking accuracy fell. Vehicle utilisation can climb because orders waited for full loads. Each of those pairs, cost against service, speed against accuracy, asset use against responsiveness, is a tension, and a management report that shows one side of a tension without the other is an invitation to celebrate a transfer as though it were a gain.

The reading rule is therefore: publish tension pairs together and judge them together. Freight cost per unit falling while OTIF also falls is not a win; it is a purchase of cost savings paid for in service, and the purchase may or may not be sensible, but it must be a decision, not an accident. A small balanced set, one or two indicators from each family, service, speed, cost, asset, and quality, read side by side, will outperform a long list of solitary numbers every month.

The reason this discipline matters ultimately sits outside the company, with the customer. Operational KPIs and customer satisfaction are connected by a causal chain: inventory accuracy causes picking correctness; picking correctness and dock discipline cause OTIF; OTIF, order after order, becomes the customer's experience of reliability; experienced reliability becomes retention, and its absence becomes quiet defection that no single complaint ever announces. That is the practical meaning of the claim that logistics performance measurement protects revenue: it lets the business manage satisfaction before the survey instead of apologising after it. Surveys measure the end of the chain, after the fact; operational KPIs measure its causes, early enough to change the ending.

=== KEY CONCEPT ===
HEADING: Dashboards, reports, and the operating rhythm
BODY:
Measurement only pays when it is consumed on a rhythm: the dashboard, the report, and the meeting.

A performance dashboard is a visual display presenting selected performance indicators and operational information. A useful dashboard is small and disciplined: a handful of indicators, each shown against its target, each with a named owner, each displayed as a trend rather than a single snapshot, and flagged red, amber or green against thresholds agreed in advance. One page should be enough. A dashboard with forty tiles is not more informative than one with six; it is six informative signals drowned in thirty-four distractions.

The dashboard shows; the report explains. A monthly performance report adds commentary: why each red indicator is red, what the causes appear to be, what actions are under way, and what decisions management is asked to make: adding a vehicle, changing a carrier, raising safety stock. Dashboards and reports together support management decisions by replacing recollection and impression with a common, dated, defined set of facts.

Around the instruments runs the operating rhythm, the same five movements whether the operation is a single depot or a national network.

1. Define. Write down each KPI's formula, data source, owner, and review frequency.
2. Collect honestly. The records feeding the numbers follow the discipline of Lesson 8.4: posted at the time of the event, attributable, unadjusted without cause.
3. Review regularly. A weekly operational meeting for process indicators; a monthly management meeting for the strategic set.
4. Act. Every red indicator leaves the meeting with an owner, an action, and a date. A red number that leaves the meeting alone will be red again next week.
5. Audit the measure itself. Definitions drift, data quality decays, and behaviour adapts to the measure. Re-verify definitions and spot-check the data periodically.

This rhythm is continuous improvement made procedural, mirroring the classic plan, do, check, act cycle.

=== KEY CONCEPT ===
HEADING: Choosing KPIs for an operation
BODY:
The final skill of this lesson, and the capstone of the module, is recommending the right indicators for a specific operation. The method is short to state.

1. Start from the promise and the decisions
List what the operation has promised its customers, and the real management decisions it faces, carrier choice, delivery frequency, stock policy, staffing. KPIs exist to serve these; an indicator linked to neither a promise nor a decision is a candidate for deletion.
2. Cover the families
Build a starter set of roughly five indicators, one per family: service, such as OTIF; speed, such as order cycle time; cost, such as freight cost per unit or cost per shipment; asset use, such as vehicle capacity utilisation; and quality, such as inventory accuracy. A cold-chain food distributor would watch the claims and damage ratio closely from the start; a business living on imported lines would add a measure of clearance delays. Adjust the set to the operation, never to the template.
3. Define each completely
Formula, data source, owner, and review frequency, in writing, before the first number is produced.
4. Baseline before targets
Run the set for at least one normal period with no targets at all, then set trend targets from the baseline and the promise.
5. Review the set itself
Twice a year, ask which indicators changed a decision and which merely filled a page, and prune accordingly.

Two patterns fail repeatedly. The single-family dashboard, all cost or all service, steers the operation into the tensions described earlier. The exhaustive dashboard, every measure the systems can produce, dissolves attention. Five owned indicators, defined, baselined, and reviewed on a rhythm, will move an operation further than fifty unowned ones, and the worked examples that follow show it in practice.

=== WORKED EXAMPLE ===
HEADING: An OTIF month at a packaged-foods distributor in Tema
BODY:
A distributor of packaged foods based in Tema delivers to retail customers across Greater Accra. At the end of January, the logistics supervisor computes the month's service KPIs. All figures in this example are illustrative for teaching purposes.

Step 1: Gather the raw outcomes
During January the distributor completed 100 orders. Reviewing delivery notes and customer receipts, the supervisor records: 8 orders arrived later than the promised date; 5 orders were delivered short, meaning incomplete against the customer order; and 2 of the late orders were also short.

Step 2: Compute on-time delivery
Orders on time: 100 - 8 = 92. OTD = 92 ÷ 100 × 100 = 92 per cent.

Step 3: Compute the in-full rate
Orders delivered in full: 100 - 5 = 95. In-full rate = 95 per cent.

Step 4: Compute OTIF
OTIF counts only orders that were both on time and in full. Failures: 8 late + 5 short - 2 that failed both = 11 failed orders. OTIF = (100 - 11) ÷ 100 × 100 = 89 per cent. A tempting shortcut, averaging the 92 and the 95 per cent, gives 93.5 per cent, which is wrong, because it double-counts the 2 orders that failed on both counts.

Step 5: Split the failures diagnostically
The 89 per cent is one number hiding two diseases. Of the 8 late orders, 5 ran on the same regional lane in the same week, following the breakdown of a dedicated vehicle with no backup arranged; the other 3 carried imported lines that cleared late at the port, echoing the delay pressures examined in Lesson 9.4, Demurrage, Detention, and Storage Charges. All 5 short deliveries traced to one product family: the system showed stock available, but picking against inaccurate records produced short despatches, a process failure of the kind Lesson 8.2 addresses.

Step 6: Assign owners and actions
The transport supervisor owns a backup-vehicle arrangement for the dedicated lane. The warehouse supervisor owns a cycle count of the affected product family, with scan confirmation at the picking location. The procurement lead owns a safety-stock review on the late-clearing import line, applying the logic of Lesson 13.3.

What does this example demonstrate?
The headline OTIF of 89 per cent is a score, not a diagnosis. The split of late against short separates two different failures with different owners, different causes, and different cures.

Key lesson
Measure first, then dissect: an undivided service number tells you that something is wrong, and only the split tells you what to fix.

=== WORKED EXAMPLE ===
HEADING: The consolidation that cost service: reading two KPIs together in Rotterdam
BODY:
A food distributor based in Rotterdam serves supermarkets across the Netherlands from one distribution centre. All figures in this example are illustrative for teaching purposes.

Step 1: The baseline
At the start of the initiative the operation measures OTIF at 96 per cent and freight cost per pallet delivered at 20 euros. Supermarket orders arrive daily and travel mostly as part-load groupage shipments, the consolidation arrangement introduced in Lesson 5.3, Shipping Instructions and Cargo Consolidation.

Step 2: The cost initiative
The transport manager consolidates. Daily part-load deliveries are combined into two full-truck regional loops per week per region. Freight cost per pallet delivered falls to 16 euros, a 20 per cent reduction, and the initiative is reported to management as a clear success.

Step 3: The service response
Over the following two months, OTIF slips to 88 per cent. Average order cycle time lengthens, because orders placed after a loop has departed wait for the next one. Two supermarket customers complain formally about stock gaps on promoted lines, and one raises the deterioration at its supplier review.

Step 4: Read the two KPIs together
Neither number alone tells the story. The cost KPI shows a genuine 4-euro saving per pallet; the service KPI shows 8 points of OTIF paid for it. Together they show a transfer: the saving was manufactured by spending delivery reliability, the dynamic this lesson's tension pairs predict. Had the dashboard carried only freight cost, the initiative would have been declared a success until the customer losses, the true cost, arrived unmeasured.

Step 5: The rebalanced decision
Management redesigns rather than reverses. Planned replenishment orders, which supermarkets place on a known weekly cycle, are consolidated onto the loops under an agreed two-to-three-day promise, keeping most of the saving. Short-notice and promotion orders return to next-day direct delivery, accepting a higher cost per pallet on that defined slice of volume. The rebalanced targets: freight cost per pallet held near 18 euros on the blended mix, OTIF restored to 95 per cent or better.

What does this example demonstrate?
Two KPIs in tension must be read as a pair, and the correct response to an unbalanced trade-off is usually a redesign that keeps part of each benefit, not a retreat to either extreme.

Key lesson
A cost KPI without its service twin congratulates half a decision; publish them together or the operation will sell one to buy the other in secret.

=== WORKED EXAMPLE ===
HEADING: A five-KPI rollout at a pharmaceutical distributor in Accra
BODY:
A pharmaceutical distributor in Accra supplies pharmacies and clinics from one warehouse and a small fleet. A newly appointed distribution manager introduces performance measurement in one quarter. All figures in this example are illustrative for teaching purposes.

Step 1: Choose five KPIs, one per family
Service: OTIF, from delivery dates and completed quantities against orders. Speed: order cycle time, from order receipt to completed delivery. Cost: freight cost per shipment, monthly delivery cost divided by shipments, under a stated costing method. Asset: vehicle capacity utilisation, load volume over available volume. Quality: inventory accuracy from the monthly cycle counts. Each receives a written definition, a data source, a named owner, and a weekly computation with monthly review.

Step 2: Baseline one month, no targets
The first month produces the baseline: OTIF 91 per cent; order cycle time averaging 2.4 days with a worst case of 6 days; freight cost per shipment 680 GHS; vehicle utilisation 68 per cent; inventory accuracy 94 per cent. No targets are announced this month, so the numbers describe normal operations rather than staged behaviour.

Step 3: Set trend targets from the baseline and the promise
Targets for the next quarter: OTIF from 91 to 94 per cent; inventory accuracy from 94 to 98 per cent; vehicle utilisation from 68 to 75 per cent; order cycle time from 2.4 to 2.0 days with the worst case held below 3 days; freight cost per shipment held within 5 per cent of baseline while service improves, because forcing cost down during a service repair would recreate the tension trap this lesson warns against.

Step 4: Install the instruments
A one-page dashboard carries the five indicators, each against target with a twelve-week trend and red, amber or green flags. A thirty-minute review meeting runs every Monday morning: warehouse supervisor, transport supervisor, procurement lead, and the manager.

Step 5: Run the first reviews
In week two, inventory accuracy is flagged red at 93 per cent. Investigation traces the slippage to returned goods restocked without returns notes, breaching the documentation discipline of Lesson 8.4. Action: no return re-enters stock without a returns note; owner, the warehouse supervisor. In week three, OTIF is flagged red after an inbound shipment cleared late at the port. Action: raise safety stock on the five fastest-moving imported lines, applying Lesson 13.3's logic; owner, the procurement lead.

What does this example demonstrate?
Five defined, owned, baselined indicators on a fixed rhythm converted measurement into management within a quarter; every red flag left its meeting with a name and an action attached.

Key lesson
A small, owned, well-defined set of KPIs beats a dashboard of everything; the review meeting, not the spreadsheet, is where performance is actually managed.

=== IMPORTANT NOTE ===
HEADING: What gets measured badly gets gamed
BODY:
The behaviour rule has a dark twin: what gets measured gets managed, and what gets measured badly gets gamed. Gaming is the adjustment of behaviour to flatter the number rather than to improve the business, and it requires no fraud, only pressure and a poorly designed measure.

Familiar patterns: Drivers learned that a delivery before the promised window counted against them, so trucks waited at the gate until the window opened, on-time statistics perfect, customers waiting at the gate with them. Warehouse teams recorded picking complete to satisfy a speed measure before the goods were physically staged. A branch redefined late from the promised delivery date to the dispatch date, and lateness vanished from the report while remaining untouched in the yard.

Two defences exist, and both are management work rather than technology.

1. Fix the definition in writing. A KPI's formula, data source, and counting rules are changed only deliberately, with the change dated and announced. Most gaming begins as definition drift, a small reinterpretation that makes the number kinder without anyone deciding anything.
2. Audit the measure itself. Periodically spot-check the data behind the indicator against physical reality: recheck a delivery date at the customer, recount a counted location. This is the discipline of Lesson 8.4, Warehouse Documentation and Stock Reconciliation, applied one level up: a KPI stands on records, and records that can be bent will be bent where the pressure to look good is greatest.

A measure that cannot survive an audit is not reporting performance; it is reporting the pressure its audience is under.

=== IMPORTANT NOTE ===
HEADING: Borrowed benchmarks mislead: baseline and trend are your truth
BODY:
The logistics world is full of impressive numbers: service levels that other companies report, cost ratios quoted at conferences, benchmark tables published by consultancies. On borrowed numbers this lesson's rule is blunt: there are no universal benchmark values for OTIF, inventory accuracy, utilisation, or any other KPI, and a text that quotes world-class percentages as targets is selling certainty it does not possess.

The reasons are structural. Two operations reporting the same KPI name may measure different things, because one counts an order on time when it arrives within the promised week and the other counts to the promised hour. They face different product mixes, different order profiles, different distances, different network shapes, and different promises made to different customers. A number produced by all of that history is not comparable to a number produced by different history, and setting your target at someone else's result commits your operation to a level whose conditions you cannot see and cannot copy.

Used correctly, external reference points still have a place. Benchmarking against published practice can tell you which indicators your industry considers worth measuring, and your own history, the internal benchmark, is genuinely comparable because it shares your definitions and your conditions.

The practical rule follows. Baseline first, target from your own trend and your own service promise, and treat every borrowed number as a curiosity until you have verified its definition. Baseline and trend are your truth; everything else is somebody else's story.

=== IMPORTANT NOTE ===
HEADING: A KPI without an owner is decoration
BODY:
The most common way measurement programmes die is not bad mathematics. It is orphaned indicators: numbers published, discussed, admired, and owned by nobody, which decay into wallpaper within a quarter.

An owner is a named person answerable for a specific indicator, with the authority to act on its causes and the duty to report on it at the review meeting. The definition matters in all three parts. Named, because a KPI belonging to the logistics department belongs to nobody. Answerable, because the owner is expected to explain the number, not merely produce it. Authorised to act, because holding a person responsible for a number whose causes they cannot touch is not accountability, it is scapegoating, and staff learn to defend themselves with explanations instead of improvements.

Three symptoms reveal an orphaned KPI set. First, review meetings that end without actions, because nobody present has the standing to commit to one. Second, indicators that stay red for months without consequence, which teaches the whole organisation that the dashboard is theatre. Third, a number whose definition nobody in the room can state when asked, which means the number can be reinterpreted by whoever finds it convenient.

The remedy costs nothing and is non-negotiable. No KPI enters the dashboard without a name beside it, and no red KPI leaves the review meeting without an action, a date, and the owner's agreement. Five owned indicators will outperform fifty orphaned ones, because measurement changes behaviour only at the point where a specific person decides that this number, on their watch, must move.

=== MCQ 1 ===
QUESTION:
A distributor in Kumasi delivered 80 orders during March. Reviewing the records, the logistics supervisor finds that 6 orders arrived later than the promised date, 4 orders were delivered short, and 2 of the late orders were also short.

Which figure is the distributor's correct OTIF for March?

POINTS: 1
OPTIONS:
1. 92.5 per cent, the proportion of orders that arrived on time.
2. 95 per cent, the proportion of orders delivered in full.
3. 90 per cent, the proportion of orders that were both on time and in full.
4. 93.75 per cent, the average of the on-time rate and the in-full rate.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

OTIF counts only orders that clear both conditions at once: delivered within the agreed time and complete in quantity. The failures are the 6 late orders plus the 4 short orders minus the 2 counted in both lists, which gives 8 failed orders, leaving 72 of 80 orders both on time and in full. That is 72 ÷ 80 × 100 = 90 per cent.

Answer 1 is the on-time delivery rate, which is exactly the weakness OTIF exists to correct: an order counted on time may still be short. Answer 2 is the in-full rate alone, which ignores the time condition entirely. Answer 4 falls into the averaging trap from the Tema worked example: averaging 92.5 and 95 per cent double-counts the 2 orders that failed on both counts and flatters the true result.

The takeaway: OTIF is strict by design, late or short means failed, and overlapping failures must be subtracted once, not counted twice.

=== MCQ 2 ===
QUESTION:
A distribution business consolidates its daily part-load deliveries into two full-truck regional loops per week. Freight cost per pallet falls by 20 per cent, but over the same two months OTIF slips from 96 to 88 per cent and two retail customers complain about stock gaps.

Which statement best describes how management should read these results?

POINTS: 1
OPTIONS:
1. The results confirm a successful initiative, because freight cost is the KPI the project targeted and it improved substantially.
2. The two results are unrelated, because cost performance and delivery reliability are measured by different departments from different data.
3. Service is the only KPI that matters, so the consolidation must be cancelled completely and every delivery returned to the daily schedule.
4. The results show a transfer from service to cost, and management must read the KPI pair together and rebalance, keeping part of the saving while restoring the service promise.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

Cost and service KPIs sit in tension: freight cost per unit can be cut by consolidating loads precisely because orders then wait for the truck, which is how OTIF falls. Read together, the two numbers describe a transfer, a genuine saving purchased with 8 points of delivery reliability, and the correct management response is the rebalanced decision shown in the Rotterdam worked example: consolidate planned replenishment orders that can carry a longer promise, keep direct delivery for short-notice orders, and set fresh targets for both indicators.

Answer 1 celebrates half a decision; a cost KPI without its service twin congratulates the transfer while the customer, the true cost, arrives unmeasured. Answer 2 is wrong because the indicators are causally linked, not merely adjacent on a dashboard. Answer 3 overcorrects to the other extreme; the rebalanced design kept most of the saving, and cancelling everything would surrender it unnecessarily.

The takeaway: no cost result should be reported without its service twin, because the operation will otherwise quietly sell one to buy the other.

=== MCQ 3 ===
QUESTION:
A new distribution manager at a frozen-food distributor in Tema must choose the company's first set of logistics KPIs. Senior colleagues offer four different recommendations.

Which option best describes the soundest starting set?

POINTS: 1
OPTIONS:
1. A full dashboard of every indicator the systems can produce, so that management can later select the ones that turn out to matter.
2. Freight cost measures only, because cost is the one result management can directly control and the figures are already reliable.
3. Published world-class benchmark values for OTIF, inventory accuracy and utilisation, adopted as the company's targets from the first month.
4. About five indicators covering service, speed, cost, asset use and quality, such as OTIF, order cycle time, freight cost per shipment, vehicle utilisation and inventory accuracy, each with a formula, an owner, a baselining month, and targets set from the company's own trend.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

The lesson's recommendation method starts from the service promise, covers the KPI families so that no tension trades in the dark, defines each indicator completely, baselines before targeting, and sets targets from the company's own trend and promise. For a cold-chain operation the claims and damage ratio would soon join the set, but the five-family starter structure is the sound foundation, and the Accra pharmaceutical rollout showed it working end to end.

Answer 1 is the dashboard of everything, which dissolves finite attention across dozens of unowned numbers; nothing earns its place by changing a decision. Answer 2 is the single-family dashboard, which steers the operation into the cost-versus-service tension and invites exactly the consolidation trap of the Rotterdam example. Answer 3 imports borrowed benchmarks as targets, contradicting the fact-safety rule that no universal benchmark values exist: other businesses' results were produced under other definitions, mixes, distances and promises, and cannot be copied.

The takeaway: few, owned, well-defined indicators, baselined and trended, beat exhaustive, orphaned, or borrowed measurement every time.

=== FACTS & SOURCES ===
- Definitions of key performance indicator, performance measurement, on-time delivery, on-time in-full, order accuracy, inventory accuracy, warehouse productivity, transport utilisation, cost per shipment, order cycle time, benchmarking, performance dashboard and continuous improvement follow the lesson brief 13.4 key terms. — source: lesson brief 13.4, Key Terms (curriculum database).
- OTIF percentage equals on-time-in-full deliveries divided by total deliveries, multiplied by 100; strict OTIF fails an order that is late or short, and an early but incomplete delivery still fails. — source: research sheet logistics-scm-frameworks.md, section 7 (OTIF, MetricHQ).
- The perfect order rate extends OTIF with damage-free condition and correct documentation/invoicing, and some conventions compute it by multiplying component success rates. — source: research sheet logistics-scm-frameworks.md, section 7 (perfect order rate; medium confidence on exact components, taught with the some-conventions qualifier).
- Order cycle time is measured from order receipt to delivery; dock-to-stock time is measured from arrival at the receiving dock to stock being pickable. — source: research sheet logistics-scm-frameworks.md, section 7.
- Inventory accuracy is the share of counted locations or SKUs matching the system record within tolerance, the output measure of cycle counting. — source: research sheet logistics-scm-frameworks.md, section 7.
- Freight cost per unit divides spend by units shipped, and freight cost per tonne-kilometre divides cost by tonnes moved per kilometre; it is the standard mode and lane comparator. — source: research sheet logistics-scm-frameworks.md, section 7.
- Capacity utilisation is the share of available vehicle, container or warehouse capacity actually used; it is a core efficiency lever for cost and emissions, and empty running is travelling without paying cargo. — source: research sheet logistics-scm-frameworks.md, sections 7 and 6.
- Claims and damage ratio expresses damage or loss claims as a share of shipments or freight spend. — source: research sheet logistics-scm-frameworks.md, section 7 (medium confidence on typical values; no values quoted in the lesson).
- MAPE equals the average of the absolute difference between actual and forecast divided by the absolute actual, multiplied by 100, and is fragile near zero actuals. — source: research sheet logistics-scm-frameworks.md, section 7 (forecast accuracy).
- Lead time runs from order or trigger to receipt, and its components include order processing, production or pick-pack, handling, transport and, internationally, customs clearance. — source: research sheet logistics-scm-frameworks.md, section 7.
- Inventory turnover equals cost of goods sold divided by average inventory; days of supply equals average inventory divided by average daily usage, with the denominator stated. — source: research sheet logistics-scm-frameworks.md, section 5 (taught in Lessons 8.3 and 13.3; restated here only).
- FTL dedicates a vehicle to one shipper while LTL and groupage combine several shippers' freight, cheaper per unit but with more handling; consolidation trades cost against transit and handling. — source: research sheet logistics-scm-frameworks.md, section 6.
- PDCA, plan, do, check, act, is the Deming/Shewhart continuous improvement cycle. — source: research sheet logistics-scm-frameworks.md, section 13.
- No universal OTIF benchmarks or specific retailer OTIF policies are claimed; benchmark figures are program-specific and time-bound, so the lesson teaches baseline-and-trend target setting. — source: research sheet logistics-scm-frameworks.md, DO NOT CLAIM item 9, and WRITING_SPEC.md rule 5.1.
- Lead time is not just transport: order processing, preparation, transit and, across borders, customs all count; and cold-chain logistics is temperature-controlled storage and transport with continuous monitoring. — source: research sheet logistics-scm-frameworks.md, sections 7 and 1.
- Leading versus lagging indicators, the strategic-to-task KPI hierarchy, the cost-to-serve lens, dashboard design practice (targets, owners, thresholds, trends), the define-collect-review-act-audit operating rhythm, and the sayings that what gets measured gets managed and that a KPI without an owner is decoration are general business knowledge, presented without attribution to any specific author. — source: general business knowledge.
- All quantities, percentages, currency amounts, dates and company situations in the worked examples and inline illustrations (100 orders with 8 late, 5 short and 2 overlapping; 80 orders with 6 late, 4 short and 2 overlapping; 95/95/99/98 per cent perfect-order components; 20 to 16 euros per pallet; 680 GHS per shipment; 91/94/98 per cent and 68 to 75 per cent targets; 10 tonnes over 200 kilometres at 1,000 GHS) are illustrative for teaching purposes. — source: WRITING_SPEC.md rule 5.1.
