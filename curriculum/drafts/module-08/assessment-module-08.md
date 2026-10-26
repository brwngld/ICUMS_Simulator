# DRAFT — Module 8 Assessment: Warehousing and Inventory Management

Coverage map (one line per question):

Q1 | lesson 8.1 | layout choice driven by site shape: a single building frontage points to U-flow, because through-flow needs dock doors and yard access on two sides (design factors objective).
Q2 | lesson 8.1 | space utilisation is a balance, not a maximum: cramming destroys the flow the space exists to serve, and capacity is how much the building can flow while holding.
Q3 | lesson 8.1 | cross-dock versus put-away when the timing condition fails: a load whose outbound departure has gone reverts to storage and picking (flow reasoning).
Q4 | lesson 8.2 | the shortage discovered after a clean signature: record-then-sign versus signed-clean, and the correct response once the evidence was fixed at the dock.
Q5 | lesson 8.2 | picking-method choice on a new order profile: continuous order arrivals against fixed carrier cut-offs point to wave picking, the timing policy.
Q6 | lesson 8.2 | the third door at receiving: damaged goods and incomplete documentation go to quarantine, kept apart from available stock, until resolved.
Q7 | lesson 8.3 | FEFO applied to a fresh two-batch case in which arrival order and expiry order disagree, with the arithmetic of the slack the wrong rule leaves.
Q8 | lesson 8.3 | reorder-point arithmetic on new numbers: trigger = lead-time demand (45 x 3 = 135) plus safety stock (60) = 195, against the half-answer and doubled-buffer distractors.
Q9 | lesson 8.3 | inventory management versus inventory control: deciding well on records that do not match the shelf is deciding on fiction.
Q10 | lesson 8.4 | unit-of-measure confusion as the cause of a variance that refuses to trace: check the units before blaming the staff.
Q11 | lesson 8.4 | the three-way match applied fresh in the excess direction: payment is released only when the purchase order, the GRN and the invoice agree.
Q12 | lesson 8.4 | adjustment with root cause versus blind keying: recurring small variances are a signal to read, and the audit trail records the pattern of corrections.

=== ASSESSMENT Q1 | tests lesson 8.1 ===
QUESTION:
A distribution company is designing a new warehouse on a plot served by a single access road, so the yard and dock frontage can only sit along one side of the building. The operations manager insists on a through-flow layout, arguing that goods should always move in a straight line from one end of the building to the other.

Which statement best evaluates the manager's position?

POINTS: 1
OPTIONS:
1. Through-flow is always the more efficient layout, so the company should reconstruct the site at whatever cost to provide a second frontage.
2. The site points to a U-flow layout: with receiving and dispatch on the one dock face and the zones arranged so inbound and outbound traffic never cross, one frontage serves both flows, while through-flow would require dock doors and yard access on two sides.
3. A U-flow layout is impossible on a single-frontage site, because receiving and dispatch cannot share the same doors.
4. Whichever shape is chosen, formal zones are optional, because the flow of work itself keeps the goods in order.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The lesson's design factors put site and building shape first: the doors, the yard and the frontage decide between U-flow and through-flow before any other decision is made. Through-flow enters at one end and leaves at the opposite end, which demands dock doors on two sides with yard access at both and a building deep enough for the flow to spread out; this site, with a single access road and one possible frontage, cannot support that. U-flow is designed for exactly this constraint: receiving and dispatch share one dock face, the doors serve inbound traffic in the morning and outbound traffic in the afternoon, supervision is concentrated, and the zones across the bottom of the U keep the two flows from crossing.

Answer 1 treats a layout preference as a requirement to rebuild the site; the lesson teaches fitting the shape to the land, not the land to the shape. Answer 3 is simply false: sharing doors is the defining feature of U-flow, and its workable condition is zone arrangement, not impossibility. Answer 4 removes the discipline both shapes depend on; zones arranged in the order of the work are what make either shape flow.

The takeaway: the site chooses the shape, and the zoning makes the shape work.

=== ASSESSMENT Q2 | tests lesson 8.1 ===
QUESTION:
The warehouse of a consumer-goods distributor in Accra is completely full: every rack position is occupied, overflow cartons are stacked in the ends of the aisles, and reserve pallets have colonised the dispatch staging area. Receiving queues on the floor awaiting locations, and orders leave later every week. The manager cites the full racks as proof of efficient space utilisation and proposes densifying further by narrowing the aisles.

Which statement best diagnoses the situation?

POINTS: 1
OPTIONS:
1. The manager is right: full racks show the space is earning its keep, and narrowing the aisles will add capacity and improve performance further.
2. The constraint is equipment rather than layout; more forklifts will restore dispatch speed even through the crowded aisles and occupied staging areas.
3. Space utilisation is a balance, not a maximum: spare locations, clear aisles and staging space are part of the design, and cramming destroys the flow the space exists to serve, so the building's capacity is how much it can flow while holding.
4. No operating change can help a full warehouse; the only solution is immediate relocation to a larger building.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The lesson's important note is direct: every square metre must earn its keep, but cramming is the worse error. Space utilisation is the effective use of available space for storage and operational activities, and it is a balance rather than a maximum. When every rack position is full, received goods have nowhere to be put away and wait on the floor, exactly as this warehouse's receiving queue shows. When aisles lose their designed width, forklifts slow and scrape; when staging areas are colonised, dispatch queues in the walkways. Each friction taxes every order while the building looks impressively full. Well-run operations plan to run high but not absolute utilisation, keeping spare locations for the day's arrivals, and the lesson closes the thought: capacity is how much the warehouse can flow while holding, not how much it can hold at a squeeze.

Answer 1 embraces the misconception the note dismantles, and densifying by narrowing aisles deepens every one of the frictions described. Answer 2 adds power to congested routes; the problem is distance and blockage, not machine shortage. Answer 4 surrenders prematurely: re-slotting, clearing the aisles and protecting the staging areas routinely recover performance, as the Kumasi re-slotting example showed, before any capital question arises.

The takeaway: a full warehouse is not a productive one; manage utilisation as a balance that protects flow.

=== ASSESSMENT Q3 | tests lesson 8.1 ===
QUESTION:
A distribution centre near Tema plans to cross-dock a promotional load that arrives pre-allocated and labelled to individual retail stores, but the trailer reaches the receiving dock in the evening, after the outbound trailers serving those stores have already departed for their scheduled deliveries.

Which statement best describes the correct handling of the load?

POINTS: 1
OPTIONS:
1. Hold the pallets on the receiving dock overnight so they can be moved straight across to the next day's trailer, preserving the cross-dock and avoiding any storage handling.
2. Put the pallets away into reserve storage and pick them for the stores' next scheduled departure, because the timing condition on which cross-docking depends has failed and put-away is now the cheaper and more reliable path.
3. Load the pallets onto whichever outbound trailer departs next, whichever stores it serves, so the goods keep moving without entering storage.
4. Return the load to the supplier, because a missed departure voids the pre-allocation and the goods can no longer be delivered to the stores.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

Cross-docking moves goods from the receiving dock directly to the shipping dock with little or no storage, and the lesson's Rotterdam example is explicit that it lives on four conditions: pre-allocation and labelling, a schedule that holds, dock capacity and labour, and information that arrives before the goods. Here the allocation information is intact, but the timing condition has broken: the outbound trailers have gone. The lesson's rule for a broken condition is that the load reverts to ordinary warehousing. Put-away into reserve and a normal pick for the stores' next scheduled departure adds handling, but it is the controlled path; the goods are recorded, located and protected while they wait.

Answer 1 forces the cross-dock by camping on the dock: the pallets sit unrecorded as pickable stock, congest the receiving area and block the next delivery, and the goods still wait a day. Answer 3 keeps goods moving but sends them to the wrong stores, converting a timing miss into customer-facing misdelivery. Answer 4 discards a perfectly deliverable load; a missed evening is served by the next scheduled run, not by reversal.

The takeaway: cross-docking is earned in advance by timing and information, and when either slips, the disciplined answer is put-away, not improvisation.

=== ASSESSMENT Q4 | tests lesson 8.2 ===
QUESTION:
Under pressure from a queue of vehicles, a receiving officer at a branch in Takoradi signs the driver's manifest clean for 80 cartons of bottled water. At put-away the next morning, the storage team counting the goods confirms that only 74 cartons were actually delivered. All figures are illustrative for teaching purposes.

Which statement best describes the branch's position and the correct response?

POINTS: 1
OPTIONS:
1. No discrepancy exists, because the signed manifest and the stock record both say 80 cartons; the branch received what its documents attest.
2. The branch should quietly reduce the stock record to 74 cartons and absorb the loss, because a clean signature cannot be contradicted and contacting the supplier would serve no purpose.
3. The branch should restate its stock record to the true count and report the shortage to the supplier immediately, with every piece of supporting evidence it can assemble, while recognising that the clean signature has already fixed the documentary evidence at 80 and the claim is therefore contested ground.
4. The branch should withhold payment for its entire next delivery from this supplier until the six missing cartons are delivered.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The lesson's worked example of the two branches makes the position plain: the delivery note signed at the dock is the record against which every later claim is judged, and signed-then-queried is signed-then-lost. The clean signature attests 80 cartons received, so the branch's claim now argues with a signed statement the supplier also holds. The correct response is still honesty and speed: make the stock record true, report the shortage to the supplier at once, and assemble what evidence exists, the put-away count, the unloading records, any photographs, and the driver's own records. Even weakened evidence promptly presented can succeed, as Branch B's supplier eventually engaging its dispatch records shows, but the branch has lost the leverage the dock annotation would have given it.

Answer 1 confuses internal consistency with truth; both documents agreeing merely repeats the same error. Answer 2 commits the second lesson's quiet keying habit: forcing the record down hides the loss, abandons any recovery, and leaves the cause invisible. Answer 4 is a disproportionate remedy unrelated to the lesson's discipline, penalising future orders for a documented failure to record at the dock.

The takeaway: record the discrepancy before the signature, because the signature is the moment the evidence is fixed; after it, the truth arrives late and unarmed.

=== ASSESSMENT Q5 | tests lesson 8.2 ===
QUESTION:
An online retailer's fulfilment warehouse in Accra receives customer orders continuously throughout the day. Its carrier vans depart at fixed times, 10:00, 13:00 and 16:00. The team picks each order discretely the moment it arrives, and although the shift's total picking hours are sufficient, the warehouse misses the 16:00 cut-off almost every day in a scramble of last-minute orders. All times are illustrative for teaching purposes.

Which picking approach best addresses this profile?

POINTS: 1
OPTIONS:
1. Batch picking: combining many orders into single passes along the pick path, because the missed cut-off is caused by pickers walking too far between orders.
2. Zone picking: assigning pickers to fixed zones so orders travel from zone to zone, because spreading the work across zones guarantees every order finishes before its van departs.
3. Hiring additional pickers to run more discrete passes, so that every order is begun and completed the moment it arrives.
4. Wave picking: releasing orders for picking in scheduled groups aligned to the 10:00, 13:00 and 16:00 departures, so picking work lands against each cut-off instead of colliding with it.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

The lesson defines wave picking as a timing policy rather than a route: orders are released in scheduled groups aligned to departure times, carrier cut-offs or workload peaks, so the warehouse is not picking at dawn what sails at dusk, nor drowning at the carrier cut-off. This profile is its exact case: total capacity is sufficient, but arrival-order picking lets work pile up against the afternoon departure. Releasing waves aligned to the three departures spreads the day's orders so that each van's orders are complete before its cut-off, converting the daily scramble into a planned rhythm.

Answer 1 reaches for the right family but the wrong tool: batch picking cuts walking when there are many small orders, yet it says nothing about when work is released, so the 16:00 pile-up survives. Answer 2 overclaims what zones do; zone picking organises travel in large buildings with long pick faces and adds handoff coordination, and no zone design guarantees completion against a clock. Answer 3 buys more labour to solve a scheduling problem, and arrival-order discrete picking would still bunch work against the final cut-off.

The takeaway: when the binding constraint is the departure schedule rather than travel or labour, wave the orders to the clock.

=== ASSESSMENT Q6 | tests lesson 8.2 ===
QUESTION:
A warehouse receives a delivery of 40 cartons of fruit juice. Six cartons are crushed and leaking, and the consignment has arrived without its delivery note, so the paperwork is incomplete. A supervisor wants to put the 34 sound cartons straight into stock so they can be sold. All figures are illustrative for teaching purposes.

Which statement best describes the correct disposition of the consignment?

POINTS: 1
OPTIONS:
1. Record the arrival, move the consignment to the quarantine area, keep it physically and in the system apart from available stock, and resolve the damage assessment and the missing documentation before any of the goods become saleable stock.
2. Put the 34 sound cartons away into stock and quarantine only the 6 damaged ones, because damage to part of a delivery does not affect the acceptability of the rest.
3. Cross-dock the sound cartons directly to a waiting customer order, since goods that leave the same day never need to pass through quarantine.
4. Refuse the delivery and return all 40 cartons to the supplier without recording them, so the incomplete paperwork never enters the warehouse's records at all.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The lesson's three doors at the dock are put away, cross-docking and quarantine, and this consignment qualifies for the third door twice over: damaged items and deliveries with incomplete documentation both go to a separate quarantine area, kept apart physically and in the system, until the question is resolved. Quarantined stock is not available stock; mixing the two is how a warehouse sells goods it should have rejected, or ships goods whose status nobody has verified. Recording the arrival and holding the consignment preserves the evidence, keeps the receiving area moving, and lets the damage assessment and the paperwork query run their course before anything is accepted.

Answer 2 splits the consignment on a physical criterion alone, but the missing delivery note queries the whole delivery, not six cartons, and the lesson names incomplete documentation itself as a ground for quarantine. Answer 3 misapplies cross-docking, which suits goods already verified and pre-allocated, not an unaccepted delivery with a live condition query. Answer 4 destroys the record; the receiving discipline is to record what actually happened, and an unrecorded return surrenders the evidence the company needs for the claim.

The takeaway: goods that cannot yet be accepted are not rejected or rushed out; they are recorded, quarantined and resolved.

=== ASSESSMENT Q7 | tests lesson 8.3 ===
QUESTION:
The dispensary of a clinic in Tamale uses about 30 cartons of a common medicine in a typical month. In January it receives Batch P, 120 cartons, expiring in March of the following year. In February it receives Batch Q, 60 cartons bought at a discount from a short-dated clearance, expiring at the end of June this year. All figures are illustrative for teaching purposes. The storekeeper, following the arrival order, begins issuing Batch P.

Which statement best identifies the correct issue order and the risk in the storekeeper's approach?

POINTS: 1
OPTIONS:
1. The storekeeper is correct: for goods with expiry dates the first batch received must still be issued first, and arrival order is the standing rule whatever the dates say.
2. The dispensary should issue Batch Q first under the first-expired, first-out rule: at 30 cartons a month it is exhausted by the end of March, three months clear of its June expiry, whereas under arrival order it would wait until May and have exactly the two months of May and June to move 60 cartons, with no slack for a single soft month.
3. The dispensary should issue from Batch P first because it is the larger batch, and larger batches should always be cleared before smaller ones.
4. The order does not matter, because both batches are within date and neither will expire while in use.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The medicine carries expiry dates, so the first-expired, first-out rule governs and the arrival order is the wrong master. The arithmetic shows why the divergence matters here. Under FEFO, Batch Q is issued from February and its 60 cartons cover two months, finishing at the end of March, a full three months before its end-of-June expiry; Batch P then runs comfortably towards its far later date. Under the storekeeper's arrival order, Batch P's 120 cartons occupy January to April, and Batch Q is left with May and June, precisely 60 cartons of demand, to clear its 60 cartons: zero slack. One slow month of dispensing strands short-dated medicine on the shelf, which is the write-off, disposal and safety risk the lesson's FEFO rule and monthly expiry sweep exist to prevent.

Answer 1 states the misconception the lesson dismantles: arrival order governs only where no expiry date does. Answer 3 invents a quantity rule that no rotation discipline recognises; batch size says nothing about which units expire first. Answer 4 ignores that within-date is not enough, because the question is which batch is left exposed as its date approaches.

The takeaway: when goods carry dates, the expiry date orders the shelf, and the earlier arrival waits its turn.

=== ASSESSMENT Q8 | tests lesson 8.3 ===
QUESTION:
A trader in Cape Coast sells about 45 bags of sugar in a typical week. The supplier needs three weeks from the placing of an order to delivery. The trader has chosen a safety stock of 60 bags to protect against unusually heavy weeks and late trucks. All figures are illustrative for teaching purposes.

At which recorded stock level should the trader place the next order, and why?

POINTS: 1
OPTIONS:
1. At 135 bags, because that covers the demand expected during the three-week lead time.
2. At 255 bags, because the safety stock must be added to the lead-time demand twice, once for demand risk and once for supply delay.
3. At 195 bags, because that is the 135 bags of expected lead-time demand, 45 a week for three weeks, plus the 60-bag safety stock chosen for the service level.
4. At 60 bags, because the safety stock alone is the level at which the shelf can no longer protect the business.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The reorder point is the expected demand during the lead time plus the safety stock. The lead-time demand is 45 bags a week across the three-week lead time, which is 135 bags, and adding the chosen 60-bag buffer gives a trigger of 195 bags. When the recorded stock falls to that level the order is placed, so the shelf, buffer included, carries the trader through the three weeks even if a week runs warm or the truck runs late. Ordering earlier than 195 piles stock that is not needed; ordering later gambles the buffer on nothing going wrong.

Answer 1 is the attractive half-answer: 135 bags covers only the average lead-time demand, so the first heavy week or delayed delivery stocks the trader out, which is precisely the failure safety stock exists to prevent. Answer 2 doubles the buffer without a decision to raise the service level; the lesson teaches that the buffer is chosen once, deliberately, and added once, and that pushing protection higher costs disproportionately more. Answer 4 orders at the buffer line itself, which would exhaust even the safety stock before the delivery arrives.

The takeaway: the trigger fires at lead-time demand plus the chosen buffer, once, and both inputs are reviewed when demand, lead times or service ambitions move.

=== ASSESSMENT Q9 | tests lesson 8.3 ===
QUESTION:
At a year-end review, the owner of a distribution business reports that the company buys well: order quantities and timing decisions have matched demand closely all year. Yet the sales team has repeatedly confirmed orders the warehouse could not fill, and several shortages surfaced only when the annual count was taken months after they began.

Which statement best diagnoses the business in the lesson's terms?

POINTS: 1
OPTIONS:
1. The company's inventory management is sound but its inventory control is weak: management decides how much to hold and when to buy, while control is the tracking, safeguarding and record-accuracy discipline, and decisions that rest on records which do not match the shelf are decisions on fiction.
2. Management and control are the same discipline, so both have failed together and the purchasing judgement is as weak as the records.
3. The company's real problem is overstocking, because goods that cannot be found on the shelf are proof that too much stock is held.
4. The weakness is that only one stocktake is taken per year; hiring counters to run the annual count more than once will keep the records true.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The lesson opens by separating two terms beginners merge. Inventory management is the planning, monitoring and control of inventory to maintain availability and minimise cost: the managerial questions of how much, how much to buy, and when. Inventory control is the procedures and systems used to track, safeguard and maintain accurate records of stock: the operational discipline of counting what arrives, recording what leaves and keeping book and shelf in agreement. This business answers the managerial questions well and neglects the discipline that makes those answers stand on anything. Promises are made against records that overstate the shelf, so the company sells goods it does not have, and discrepancies grow silently between counts, which is why the losses surfaced cold at the annual count.

Answer 2 erases the distinction the lesson exists to teach; strong purchasing judgement with weak control is exactly the combination the lesson describes as deciding on fiction. Answer 3 misreads the symptom: stock that cannot be found or promised is a record and control failure, not evidence of excess quantity. Answer 4 treats control as a counting event; counting tests the records, but control is built from the documents and movements made every day between counts.

The takeaway: management decides, control makes the records true enough for the decisions to stand on, and the business needs both.

=== ASSESSMENT Q10 | tests lesson 8.4 ===
QUESTION:
A wholesaler's stock record for a bottled product is kept in cartons, and one carton holds 24 bottles. A delivery of 30 cartons arrives, and the receiving clerk, counting in bottles, keys 720 into the record. Issues continue to be posted in cartons. Weeks later a count finds the shelf holding far less than the record claims, and the variance cannot be traced to any movement. All figures are illustrative for teaching purposes.

Which statement best identifies the cause and the discipline that prevents it?

POINTS: 1
OPTIONS:
1. Pilferage: stock has been leaving without a document, which is why the shelf holds less than the record.
2. Unrecorded internal transfers: pallets have been walked between locations without transfer notes, so the stock exists but the system is looking in the wrong place.
3. A counting error at the stocktake, since the record kept perfect arithmetic and the shelf is the only figure that could be wrong.
4. Unit-of-measure confusion: the record kept perfect arithmetic while the units underneath it were mixed, so the units, not the staff, must be checked first, with one agreed unit per record, the unit stated on every document, and conversions printed for receiving.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

The lesson's important note calls unit-of-measure confusion the quietest way to lose stock, and this is its exact signature. Records count numbers while shelves hold things, and the unit of measure is the translation between them. Keying 720 bottles into a record kept in cartons overstated the receipt by 690 cartons on paper, and because every later issue was posted correctly in cartons, the arithmetic stayed internally perfect while the units underneath remained mixed. The result is a loss or surplus far larger than any physical event, which traces to nothing, which is why the lesson's rule is to check the units before blaming the staff: a mixed unit is a record-keeping fault, found in the documents, not on the shelf. The prevention is the note's rule set: one agreed unit per stock record, the unit stated beside every quantity on the GRN, transfer notes, pick lists and count sheets, and conversions printed so receiving counts in the unit the record expects.

Answer 1 invents a culprit the pattern does not support; theft leaves no paper surplus of this scale. Answer 2 mislocates stock rather than overstatement, and the variance here is in total, not between locations. Answer 3 reasons from the record's neatness, but neat arithmetic is precisely the trap.

The takeaway: when a variance refuses to trace, interrogate the units before the people.

=== ASSESSMENT Q11 | tests lesson 8.4 ===
QUESTION:
A wholesaler issues a purchase order for 90 cartons of detergent. The supplier delivers 105 cartons; the delivery note says 105, the dock counts 105 and notes the excess, and the goods received note is raised for 105. A week later the supplier's invoice arrives for 105 cartons. All figures are illustrative for teaching purposes.

Which statement best describes what should happen?

POINTS: 1
OPTIONS:
1. The invoice should be paid in full for 105, because the goods received note and the invoice agree on the quantity actually delivered and counted.
2. Payment should be held while the difference is investigated with the supplier, because the three-way match requires the purchase order, the goods received note and the invoice to agree, and the documents must be brought into agreement, by amending the order or resolving the excess, before payment is released.
3. The invoice should be quietly paid for 90 cartons and the extra 15 cartons kept without documentation, because the purchase order caps what the company owes.
4. The entire consignment should be returned unopened, because a delivery larger than the order is unacceptable in any circumstance.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The lesson's reconciliation block states the payment gate: before a company pays a supplier's invoice, careful practice matches three documents, the purchase order, the goods received note and the invoice, and payment is released only when they agree, with discrepancies investigated first. Here the match fails on quantity from the excess side: the order says 90, the receipt and invoice say 105. The dock did its part by counting and recording the true figure; the accounts team's part is to hold payment, not refuse it, and query the difference with the supplier's dispatch records to establish whether the excess was intended. If the goods are kept, the documents are brought into agreement, by amending the order or raising the proper additional authorisation, and the match completes before payment. The warehouse paperwork is the company's evidence in exactly the way the Accra cooking-oil example showed.

Answer 1 pays against two of three documents; the purchase order is the third leg of the match, not an optional witness. Answer 3 reaches the order quantity by the wrong road: keeping 15 undocumented cartons creates an unexplained paper surplus in stock and an unpaid obligation, which is how excesses become the discrepancies the lesson warns about. Answer 4 destroys value and relationship over a resolvable difference; over-delivery is investigated, not auto-rejected.

The takeaway: the three documents must agree before money moves, and the discrepancy is resolved, never absorbed.

=== ASSESSMENT Q12 | tests lesson 8.4 ===
QUESTION:
A warehouse supervisor reports that stock reconciliation at his site is under control: whenever the month-end count differs from the record, the balance is keyed to match the shelf and the month is closed. Over the past six months the same two locations holding one high-value item have counted slightly short every month, and each variance has been adjusted away without investigation.

Which statement best evaluates this practice?

POINTS: 1
OPTIONS:
1. The practice is sound, because small regular variances on an item are ordinary shrinkage that any well-run warehouse absorbs without investigation.
2. The pattern proves that the staff on that shift are stealing, and the correct response is to identify and dismiss those responsible.
3. The practice is the damaging habit the lesson warns against: recurring small variances at the same locations are a signal of an uncorrected process fault to be recounted, traced and fixed, while repeated unexplained keying hides the cause, dissolves genuine losses into an untraceable pool, and leaves an audit trail that testifies against the warehouse.
4. The variances will be resolved by the annual wall-to-wall stocktake, which will investigate six months of differences at once and reset the records to a counted truth.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The lesson's important note names forcing records to agree as the most damaging habit in warehouse recordkeeping, and the supervisor's report is its portrait: an adjustment is the conclusion of an investigation, never a shortcut around one. Three consequences follow. The real cause survives and will produce the next variance, and the next. Genuine losses, theft and damage included, dissolve into a general pool where no pattern can be seen and nobody is accountable. And the audit trail, a chronological record of who changed what and when, shows a balance corrected repeatedly, without recorded reasons, around each month-end, the exact pattern the lesson says changes the question from why this stock is short to who is hiding what. The reconciliation procedure is compare, recount, trace the movements through their documents, adjust with a stated reason and an authoriser's approval, and fix the cause; the note adds that small recurring variances deserve as much attention as one large one, precisely because nobody investigates what looks trivial.

Answer 1 accepts the tolerance myth the lesson dismantles. Answer 2 leaps to punishment without investigation, inverting the counting-as-diagnosis discipline; the Rotterdam bearing example found a process fault, not thieves. Answer 4 postpones a traceable pattern until its trail has gone cold, the exact weakness cycle counting exists to remove.

The takeaway: a variance is a question, not a verdict, and a repeated small question at the same location is the loudest signal in the building.

=== FACTS & SOURCES ===
- All twelve questions and their explanations derive solely from the content of the four module 8 lesson drafts (lesson-8.1.md, lesson-8.2.md, lesson-8.3.md, lesson-8.4.md) and the key terms in the module 8 lesson briefs (curriculum/lesson_briefs/module-08/). No external facts, organisations, statistics, benchmarks or market figures are introduced; there are no exceptions.
- The U-flow and through-flow characteristics in Q1, the space-utilisation and cramming teaching in Q2, and the cross-docking conditions and failure behaviour in Q3 are as taught in lesson 8.1 (layout, zoning, slotting, and the Rotterdam cross-docking worked example), whose stated sources are the lesson brief 8.1 and research sheet logistics-scm-frameworks.md section 4.
- The signed-clean consequence and correct shortage response in Q4, the four picking methods in Q5, and the three doors at the dock including quarantine in Q6 are as taught in lesson 8.2 (the two-branch shortage worked example, the picking-methods block, and the three-doors block).
- The FEFO rule, expiry-sweep reasoning and the slack arithmetic in Q7, the reorder-point formula in Q8, and the inventory-management-versus-control distinction in Q9 are as taught in lesson 8.3 (the Kumasi pharmacy FEFO example, the reorder-point block, and the opening definitions block).
- The unit-of-measure teaching in Q10, the three-way match in Q11, and the adjustment-with-root-cause, audit-trail and recurring-variance teaching in Q12 are as taught in lesson 8.4 (the unit-of-measure important note, the reconciliation block's payment-gate passage, and the adjustment important note and Kumasi reconciliation example).
- All quantities, dates, times and money-free figures in the question stems (80 and 74 cartons; 40, 34 and 6 cartons; 120, 60 and 30 cartons a month with the January, February, March and June dates; 45 bags a week, three weeks, 135, 60, 195 and 255 bags; one carton equals 24 bottles, 30 cartons, 720 bottles; 90, 105 and 15 cartons; the 10:00, 13:00 and 16:00 departures) are illustrative for teaching purposes and are labelled as such in the stems — WRITING_SPEC.md rule 5.1.
- Settings and goods (Accra, Tema, Takoradi, Tamale, Cape Coast; bottled water, fruit juice, medicine, sugar, detergent, a bottled product, promotional retail stock) are generic; no real company is named or attributed any fact — WRITING_SPEC.md section 4.
- Q7's arithmetic: FEFO exhausts Batch Q (60 cartons at 30 per month) by the end of March; arrival order holds Batch P (120 cartons at 30 per month) from January to the end of April, leaving Batch Q exactly the two months of May and June. Q8's arithmetic: 45 x 3 = 135; 135 + 60 = 195; 135 + 120 = 255. Q10's arithmetic: 30 cartons x 24 = 720; 720 - 30 = 690. All verified against the lesson-taught formulas.
