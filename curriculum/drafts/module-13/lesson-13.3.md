# DRAFT — Lesson 13.3: Inventory Optimisation and Service Levels

=== KEY CONCEPT ===
HEADING: Inventory optimisation: the strategy above the mechanics
BODY:
Lesson 8.3, Inventory Control, FIFO, and FEFO, taught the working mechanics of stock: how to issue it (FIFO and FEFO), how to record it, when to reorder (the reorder point), how much to order (the economic order quantity), and how to rank items for control effort (ABC analysis). This lesson moves one level up, to the questions those mechanics exist to serve. What availability should the operation promise? How much of the organisation's money should sit on shelves to keep that promise? And which stock policies turn that money into service most efficiently? Answering them is the work of inventory optimisation, the process of determining inventory policies and quantities that balance cost, availability, and service requirements.

Three habits of mind define the optimiser.

1. Inventory is invested cash. Every unit on a shelf is working capital that cannot be spent elsewhere until the unit sells or is used. A distributor holding stock worth two million cedis is not merely storing goods; the business has placed two million cedis of its capital inside its own warehouses, and optimisation asks what service that placement buys.

2. The purpose is balance, not minimisation. The cheapest possible inventory policy is no inventory at all, and it is also a guarantee of stockouts, lost customers, and emergency purchases. The most generous policy inverts the failure. Optimisation rejects both extremes: it searches for the policy at which the total cost of holding stock and of failing to hold it is lowest.

3. Policies are set, not inherited. Reorder points, safety stocks, and order quantities are decisions somebody makes, explicitly or by default. The optimiser makes them explicitly, from demand, lead times, and costs, and revisits them when those inputs move.

The module has already assembled the inputs. Lesson 13.1 supplied the demand view, including forecast error; Lesson 13.2 supplied the network view, the number and location of stocking points. This lesson converts both into stock policy, and measures the result in service and in cash.

=== KEY CONCEPT ===
HEADING: Service level: a designed availability target, not an outcome
BODY:
The service level is a defined measure of the ability to satisfy customer demand or meet specified service expectations, and the single most important fact about it is that it is a policy choice. An organisation decides, in advance, the availability it will design its stock to deliver, in the same way an engineer decides the load a bridge is built to carry. Two readings of the term are common, and the professional habit is to be explicit about which one is in use.

1. Availability target. The cycle service level is the target probability of passing through a replenishment cycle without a stockout: a 95 per cent cycle service level means that 95 replenishment cycles in every 100 are designed to end with demand still covered when the next order arrives. This is a property the organisation designs into its safety stock.

2. Fulfilment measure. The fill rate is the proportion of demand fulfilled immediately from available inventory under a defined measurement method. It reports what actually happened to customers. Its stricter cousin, the on-time in-full measure examined in Lesson 13.4, Logistics Performance Indicators and KPIs, scores an order as a success only if it arrived both on time and complete; and when a promise slips despite the design, telling the customer honestly is its own discipline, met in Lesson 5.4, Shipment Tracking and Customer Communication.

The distinction matters because a designed target and a measured outcome are different kinds of statement. A target without measurement is a hope; a measurement without a target is an accident that has been scored. Optimisation uses both: the target to size the buffers, the fulfilment measures to check whether the design delivered.

Service levels also differ by product and by customer, and legitimately so. A hospital pharmacy and a confectionery wholesaler should not carry the same availability promise, and neither should a contracted key account and casual walk-in demand. The promise is differentiated, deliberately, and the next blocks give that differentiation its logic.

=== KEY CONCEPT ===
HEADING: The costs that compete: holding, ordering, and stockouts
BODY:
Optimisation begins with a complete cost picture, because every inventory policy is a choice among costs. Three families compete.

1. Inventory holding cost. The cost associated with maintaining stock over time: the capital tied up in the goods, the storage space they occupy, insurance, shrinkage and damage, and the risk of obsolescence as stock ages. Lesson 10.1, Components of Total Logistics Cost, made the uncomfortable point that carrying cost is real money even though no invoice names it; it surfaces as interest, rent, write-offs, and lost liquidity. Holding cost grows with the quantity held and the time it is held.

2. Ordering cost. The expense incurred in placing and processing replenishment orders: the paperwork and approval behind each purchase order, receiving and inspection at the warehouse, invoice matching, and the transport and administration that accompany every consignment. Its shape matters: much of it is charged per order rather than per unit, so frequent small orders cost more in total than fewer large ones for the same annual demand.

3. Stockout cost. A stockout is a situation in which an inventory item is unavailable when required, and its costs arrive from several directions at once: the margin on the sale that could not be made, the expediting cost of emergency replacements, the customer who quietly moves to a competitor, and the contractual or reputational damage of an unkept commitment. Lesson 10.1 grouped these with the costs of failure, the family nobody budgets but everybody eventually pays.

The strategic tension is now visible. Holding more stock attacks stockout costs and inflates holding costs. Ordering in larger, rarer quantities attacks ordering costs and inflates holding costs. No policy escapes all three; a good policy chooses deliberately among them.

=== KEY CONCEPT ===
HEADING: The optimisation problem: two costs pulled against each other
BODY:
State the problem honestly. Raising the service level requires more safety stock; more safety stock raises the holding cost. Cutting the holding cost means thinner buffers; thinner buffers raise the frequency and severity of stockouts, and stockouts cost money too. The optimisation problem is therefore not to minimise inventory and not to maximise availability, but to find the policy at which the sum of the two competing costs is smallest. In principle, the optimum sits where the money saved by one more step of availability equals the money that step costs to carry.

Everything depends on pricing the second cost honestly, so the optimiser estimates the cost of a stockout before choosing a target. The working approach is deliberately practical.

1. Size the event. For a typical stockout of the item, estimate how many units of demand would go unmet before the next replenishment arrives.

2. Price the margin at risk. Multiply those units by the gross margin each would have earned. This gross-margin-at-risk figure is the irreducible core of the stockout cost.

3. Add the consequences. Add the expediting cost of an emergency replacement and, conservatively, the value of harmed customer relationships or contractual penalties. Some consequences, such as patient harm from a missing medicine, cannot be honestly priced in money; the professional response is to treat the monetary estimate as a floor rather than a ceiling, and to let that item earn a higher protection level.

The estimation is rough by design, and that is acceptable: its job is to rank policies against each other, not to produce a figure for the annual report. A rough stockout cost that is written down and argued over is worth more than a precise silence, because the commonest and most expensive error in inventory management is simply pretending the cost is zero.

=== KEY CONCEPT ===
HEADING: Cycle stock and safety stock: two buffers, different jobs
BODY:
Average inventory answers two different questions, and the optimiser keeps the answers apart.

Cycle stock is inventory held to satisfy expected demand between replenishment orders. It exists because of ordering economics: ordering cost is charged per order, so an organisation orders in batches even though demand arrives continuously, and each batch drains away as customers buy. Cycle stock is a bet that demand will behave as expected, and its size is an order-quantity decision. The classic instrument is the economic order quantity taught in Lesson 8.3: a model that estimates an order quantity minimising the sum of ordering and holding cost under strong simplifying assumptions, including constant demand, full delivery at a single stroke, fixed order cost, and no quantity discounts or stockouts. The principles survive into advanced practice: order size is a balance between ordering cost and holding cost, and the assumptions are conditions to check, not decorations to ignore.

Safety stock is additional inventory maintained to reduce the risk of shortages caused by uncertainty in demand or replenishment. It exists because Lesson 13.1's forecasts are wrong by some amount and lead times wobble. Safety stock is not a bet on demand behaving; it is the price paid for demand being unsteady.

The reorder point is the inventory position at which a replenishment order should be initiated under a defined policy. It triggers on the inventory position, a measure of stock availability that commonly includes on-hand inventory plus outstanding orders, adjusted for backorders, so that goods already ordered and on their way are counted where they should be. Its construction is the one formula carried over from Lesson 8.3: expected demand during the replenishment lead time, plus safety stock.

Strategically: cycle stock is governed by order economics, safety stock by uncertainty, and the reorder point is where the two meet the calendar.

=== KEY CONCEPT ===
HEADING: What swells the buffer: demand variability and replenishment lead time
BODY:
Two forces determine how much protection an item needs, and both were met earlier in the programme; this block states their inventory consequences precisely.

1. Demand variability. The noisier the demand during the exposure window, the more safety stock the same service promise requires. An item selling a steady 30 units every day can be protected with a thin buffer, because a bad day is barely worse than an average one. An item selling 30 units on average but ranging from 5 to 90 needs a thick one, because the buffer must absorb the spread, not the average. This is why Lesson 13.1's work on forecast error matters twice: a better forecast improves the plan directly and shrinks the buffer every policy must carry.

2. Replenishment lead time. The period between initiating a replenishment order and receiving the goods. Its components, from the programme's earlier lessons, are order processing, preparation and pick-pack, transport and handling, and, across borders, customs clearance. A longer lead time extends the exposure window, so more expected demand must be covered and more can go wrong inside the window. A less reliable lead time is worse than a merely long one: variability in the lead time itself loads additional uncertainty onto the same buffer.

The consequence is the hinge of this lesson. The buffer is sized against what can go wrong during exposure. Shrink the exposure, in length or in variability, and the same service promise can be kept with a smaller buffer. That observation converts inventory optimisation from a choice between overstocking and understocking into a design discipline with levers, and the next blocks take up those levers in turn.

=== KEY CONCEPT ===
HEADING: Not every product deserves the same promise: segmenting service levels
BODY:
A single service level applied to a whole assortment is quietly wasteful in both directions: it overspends on items whose stockouts hardly matter and under-protects the items whose stockouts are expensive or dangerous. The optimiser's alternative is segmentation, setting different availability targets for different products and customers, each justified by the balance at the heart of the definition of inventory optimisation introduced earlier: the cost of protection against the cost of failure.

The product dimension. A life-critical medicine and a convenience good pass through the same mechanics but face different consequences. When the medicine is missing, the cost of the stockout is extreme, and not only in money, so the organisation designs availability near the top of the practical range. When the multivitamin is missing, the customer buys another brand or returns next week, so a more modest target is the honest optimum. Neither product is being treated unfairly; each is priced according to what its absence costs.

The customer dimension. A contracted key account with a measured availability commitment and a casual walk-in buyer justify different policies for the same item, and the contract, not habit, should decide.

The instrument for doing this systematically is ABC analysis, which Lesson 8.3 taught as a classification that groups items according to their relative importance, commonly based on annual consumption value: a few A items carry most of the value, and a long tail of C items carries little. At the strategic layer, ABC becomes the skeleton of the whole stock policy: A items earn tight service targets, frequent review, and first claim on management attention, because that is where the money and the service concentrate; C items earn cheap, simple policies, because elaborate protection of trivial value is optimisation inverted. Classification supports stock management precisely by making differentiated treatment systematic instead of personal.

=== KEY CONCEPT ===
HEADING: Lever 1: shorten and stabilise the lead time
BODY:
The first optimisation lever does not touch the warehouse at all. Because the buffer is sized against what can go wrong during the replenishment lead time, anything that shortens or steadies that window shrinks the stock needed for the same promise.

Shortening works through speed. The programme's freight lessons, Lesson 7.1, Ocean Freight Operations and Vessel Schedules, and Lesson 7.2, Air Cargo Operations and Cargo Acceptance, showed the two speeds available on international lanes, and Lesson 10.1's air-versus-sea comparison showed the total-cost way to read them: air costs more per consignment and may cost less in total once the inventory it eliminates is priced. Moving a critical item from a six-week ocean pipeline to a shorter air one converts weeks of exposure into days, and weeks of exposure are precisely what the safety stock was bought to cover.

Stabilising works through reliability, and it is usually the cheaper half of the lever. Dependable supplier performance, prompt order processing, fewer customs surprises through accurate documentation, and carriers that keep their schedules all narrow the spread of the lead time without buying speed. Since the buffer must absorb the spread, narrowing it is service delivered by organisation rather than by stock.

The caution is the one Lesson 10.1 taught: freight savings and inventory savings live in different ledgers, so a mode change that looks expensive to transport can look cheap to the business, and one that looks cheap to transport can quietly hold its cost in safety stock on a shelf. The optimiser compares the whole, transport and inventory together, before declaring a lead-time change an improvement.

=== KEY CONCEPT ===
HEADING: Lever 2: reduce the variability you are exposed to
BODY:
The second lever attacks the other input to the buffer: variability itself. Three instruments do this work.

1. Better forecasting. Lesson 13.1 established that forecast error is measured and managed, and its inventory price is now visible: every unit of typical error must be carried as safety stock somewhere. Narrow the error, with better data, better methods, and the sales and operations planning conversation, and every buffer downstream can shrink at unchanged service.

2. Postponement. The technique of keeping the product generic and deferring final configuration, such as dyeing, labelling, local packaging, or final assembly, until real demand is known. Its inventory power is structural: uncertainty attaches to the small pool of generic stock rather than to the large family of finished variants, so the buffer is carried once instead of many times. It suits products whose final form can be decided late and whose demand is uncertain, and it is the same idea Lesson 13.1 met from the planning side as delayed differentiation.

3. Calmer demand signals. Lesson 13.1's bullwhip effect showed how order swings amplify upstream through forecast updating, order batching, price fluctuations, and shortage gaming. A stockholder who sees distorted orders is forced to buffer against phantoms; shared point-of-sale data, smaller and more frequent orders, and steady pricing shrink the swings and therefore the buffers built on them.

Under all three sits a floor: record discipline. Lesson 8.4, Warehouse Documentation and Stock Reconciliation, made the operational case for accurate stock records; the strategic case is that every parameter in this lesson, safety stock, reorder point, service target, is computed from records, and a policy computed on wrong records protects a fiction while the real stock quietly does something else.

=== KEY CONCEPT ===
HEADING: Lever 3: pool inventory across locations
BODY:
The third lever is geographic. When the same item is stocked at many locations, each location carries its own safety stock against its own local surprises, and the totals mount: five stores each hedging their own uncertainty hold five separate hedges. When the item is pooled into fewer locations, the same total demand is served with less total buffer, because local swings partly cancel: the week one region runs hot, another often runs cool, so the pooled demand is steadier than the sum of its parts. Pooling converts separate, larger hedges into one smaller hedge for the same coverage, and the worked example later in this lesson puts illustrative arithmetic on the effect.

Pooling is the inventory face of the decision Lesson 13.2, Transport Route and Network Optimisation, analysed from the transport side. The trade-off there is symmetric: more stocking points in the network cut delivery time and outbound transport cost but add facility and inventory cost, while a centralised network does the reverse. The optimiser reads the network decision as an inventory decision too: every stocking point added is another buffer purchased, and every one consolidated is buffer released.

The lever has honest limits, and optimisation respects them. Gains shrink when local demands rise and fall together, because swings that move together do not cancel. Pooling lengthens the response to distant customers, which is a service cost paid in delivery time rather than in stock. And some stock must sit close to demand regardless: fast movers, and items whose absence stops a customer's work within hours. The question is therefore not whether to centralise, but which items pool well and which must live near the customer, decided item by item along the ABC lines drawn earlier.

=== KEY CONCEPT ===
HEADING: Measuring inventory performance: turnover, days of supply, and the cash view
BODY:
A policy is not performing unless it can be scored, and inventory performance has two standard instruments.

1. Inventory turnover. A measure of how frequently inventory is sold or consumed and replaced during a specified period, computed as the cost of goods sold divided by average inventory for the period. A turnover of six says the operation sells and replaces its average stock six times a year: the same stock funds six buying seasons inside twelve months.

2. Days of supply. Average inventory divided by average daily usage, answering the plainer question: if demand continued as usual, how many days would today's shelves last? When usage aligns with the cost figure, days of supply approximates 365 divided by turnover, and the optimiser states which denominator is in use, because the two are reported differently in different businesses.

Both feed the working-capital lens this lesson has pressed throughout: inventory is cash on shelves. A reduction in days of supply at unchanged service is cash released, and it is one of the few improvements a finance director and a customer can applaud together.

The optimiser's red flag is aged and obsolete stock: items that no longer turn, expiry-dated goods approaching their dates, models superseded, spares for machines already retired. Aged stock is not merely expensive; it is diagnostic. Stock that nobody buys was ordered under a policy nobody revised, so the warehouse floor is where stale assumptions resurface as write-offs. Reviewing turnover and days of supply item by item finds the flag while it is still a flag.

One caution guards the whole block: turnover alone is not a verdict. A low figure can be negligence, or it can be a deliberate buffer for a critical spare with a long lead time, and the difference lies in the item's role, as the final worked example demonstrates.

=== KEY CONCEPT ===
HEADING: The review rhythm: optimisation is a cycle, not a project
BODY:
Every parameter this lesson has discussed, the service level targets, the safety stocks, the reorder points, was computed from assumptions: a demand rate and its variability, a lead time and its reliability, a set of costs. None of those assumptions holds still. Demand drifts and seasons shift, and Lesson 13.1's forecast error guarantees the plan will be wrong by some amount; suppliers change performance and lead times move; margins, freight rates, and the cost of capital all wander. An inventory policy that was optimal when set is silently drifting away from optimal ever after, which is why optimisation is a cycle, not a project.

The rhythm has three beats.

1. Set. Choose service level targets by segment, size safety stocks and reorder points from demand, lead-time, and cost data, and write the policies down so they can be examined.

2. Measure. Score the design against reality: stockout and fill-rate history against the targets, turnover and days of supply against intention, aged stock against a zero-tolerance line.

3. Revise. When measurement or changed assumptions show drift, recompute the parameters. A target that keeps missing, a buffer that never once triggered, an item whose lead time halved, each is a signal to reset, not a curiosity.

The cadence is part formal, part event-driven: scheduled reviews, often folded into the sales and operations planning cycle Lesson 13.1 described, plus immediate reviews when a supplier changes, a product launches or retires, or a disruption moves lead times. Lesson 8.3 closed on the note that the formulas are servants, not masters; the strategic version of that note is that the parameters are servants too. They serve the balance between cost and service, and they keep their jobs only while the balance holds.

=== WORKED EXAMPLE ===
HEADING: Two products, two promises: setting service levels at an Accra distributor
BODY:
A health-and-wellness distributor in Accra carries two items through the same warehouse and the same ordering routine: an essential injectable medicine supplied to hospitals, and a mass-market multivitamin supplement sold through pharmacies and shops. Both have annual demand of about 12,000 units, both are ordered in batches of 1,000, so both pass through about 12 replenishment cycles a year, and both face a lead time of 10 days, about 33 units of expected demand per day. All figures in this example are illustrative for teaching purposes.

Step 1: Price a stockout for each item. A typical medicine stockout leaves roughly 150 units of hospital demand unmet. At a gross margin of GHS 20 per unit, the margin at risk is GHS 3,000; expediting a replacement costs about GHS 1,000; and harm to hospital relationships is valued conservatively at another GHS 1,000, since a missing essential medicine can also harm patients in ways money does not capture. The working estimate is GHS 5,000 per event, treated as a floor. A typical multivitamin stockout strands about 400 packs at a margin of GHS 3 each, GHS 1,200, and little else: customers substitute or return, and no expedited freight is justified.

Step 2: Compare a 90 per cent and a 99 per cent target for the medicine. At 90 per cent, each of the 12 annual cycles carries a 10 per cent chance of failure, so 1.2 stockout events are expected: 1.2 times GHS 5,000, or GHS 6,000 a year. At 99 per cent, expected events fall to 0.12, about GHS 600, but protection grows disproportionately: safety stock rises from 250 to 600 units, moving the reorder point from 330 plus 250 (580) to 330 plus 600 (930). The extra 350 units cost an assumed GHS 6 per unit-year, GHS 2,100, against about GHS 5,400 of expected stockout cost avoided; the raise pays for itself before counting the unpriced patient consequences.

Step 3: Run the same comparison for the multivitamin. At 90 per cent, expected stockout cost is 1.2 times GHS 1,200, or GHS 1,440 a year; at 99 per cent it falls to about GHS 144, saving roughly GHS 1,300. But the extra 400-pack buffer costs GHS 5 per pack-year, GHS 2,000, so the raise costs more than it saves: the lower target is not neglect but the honest optimum for this item.

What does this example demonstrate? The same mechanics produced opposite policies, because the two items price failure differently.

Key lesson: a service level is chosen item by item, weighing the cost of protection against the cost of failure; for a life-critical product, failure sets the policy.

=== WORKED EXAMPLE ===
HEADING: One store or two: the pooling effect between Tema and Kumasi
BODY:
A food wholesaler sells one steady line of tinned tomatoes through two regional stores, one in Tema serving the south and one in Kumasi serving the north. Each store averages 600 cartons of demand a month. Demand wobbles: a month can run some 200 cartons above or below average at either store, and the swings do not move together, because a strong month in the south is often a quiet month in the north. Each store therefore holds a safety stock of 200 cartons sized against its own swings, 400 cartons of buffer in total. All figures in this example are illustrative for teaching purposes.

A consultant proposes consolidating the buffer: hold this line's safety stock at a single central store in Tema serving both regions. The reasoning runs in four steps.

Step 1: Combine the exposure. The central store faces 1,200 cartons of average monthly demand, but not the swings of either single store. Because the two regions' good and bad months partly offset one another, the combined demand is steadier than either half: the pooled swing is smaller than the sum of the swings.

Step 2: Size the pooled buffer. The buffer exists to absorb variability, and pooled variability is proportionally smaller, so the same coverage can be designed with less total stock. In this illustrative design, 280 cartons at the central store replace the 400 held across the two sites.

Step 3: Bank the release. The 120 released cartons, at an illustrative value of GHS 150 each, return about GHS 18,000 of working capital at once, and they no longer cost the assumed GHS 7.50 per carton-year to carry, about GHS 900 a year saved, with designed availability unchanged.

Step 4: Pay the price of pooling, knowingly. Northern customers are now served from Tema, so their replenishment rides the Tema to Kumasi leg: delivery to the north becomes slower, or its outbound transport dearer, which is exactly the facility-and-inventory cost against delivery-time-and-transport-cost trade-off that Lesson 13.2 placed on the other side of the same decision. And the gains have conditions: if the two regions' demands rose and fell together, as they would under a shared promotion or a shared festive season, the swings would reinforce rather than cancel, and the pooled buffer would approach the sum it replaced.

What does this example demonstrate? Pooling serves the same total demand with a smaller total hedge, because independent variability partly cancels when demands share one pool.

Key lesson: the pooled buffer buys the same availability for less money, and the currency it pays in is delivery speed to the periphery.

=== WORKED EXAMPLE ===
HEADING: Two SKUs in Rotterdam: turnover, days of supply, and the role of the item
BODY:
A marine spare-parts distributor in Rotterdam supplies engine components to shipping companies. A finance review of its inventory produces two striking figures, and the skill this example teaches is reading them. All figures in this example are illustrative for teaching purposes.

Step 1: Measure SKU P, a fast-moving line of engine filters. Annual usage at cost is 480,000 US dollars, and average inventory is 40,000 US dollars. Inventory turnover is the cost of goods sold divided by average inventory: 480,000 divided by 40,000, which is 12 times a year. Days of supply is average inventory divided by average daily usage: daily usage at cost is 480,000 divided by 365, about 1,315 dollars a day, so the stock on hand represents 40,000 divided by about 1,315, or roughly 30 days. The line turns about monthly, tidy and disciplined.

Step 2: Measure SKU Q, a specialised pump impeller for one family of engines. Annual usage at cost is 60,000 US dollars, and average inventory is 45,000. Turnover is 60,000 divided by 45,000, about 1.3 times a year. Daily usage at cost is about 164 dollars, so days of supply is 45,000 divided by about 164, roughly 274 days. On a turnover league table, SKU Q looks like a disaster: a part that sits on the shelf for the better part of a year.

Step 3: Read the figures against each item's role. SKU Q is a critical spare whose maker is sixteen weeks away by the replenishment lead time, and whose absence can hold a customer's vessel in port. The 274 days on the shelf are not drift; they are the policy, a buffer bought deliberately because the lead time is long and failure is expensive. Judged by turnover alone, the distributor would starve exactly the item its customers depend on. SKU P, by contrast, is replenished locally within days; if its days of supply crept from 30 toward 60, the review would rightly ask what cash was doing on those shelves.

Step 4: Keep the red flag in view. Role justifies SKU Q's buffer, but it does not freeze it: if the engine family is retired, or the maker opens a nearer depot, the policy must be recomputed. An impeller bought for engines no longer sailing is precisely the aged-stock flag this lesson warned about, surfacing eventually as a write-off.

What does this example demonstrate? Turnover and days of supply locate the questions; they do not answer them.

Key lesson: inventory measures are read against the item's role, its lead time, and its criticality, never against a universal league table.

=== IMPORTANT NOTE ===
HEADING: One hundred per cent service level is not a strategy
BODY:
The most seductive number in inventory management is 100 per cent, and the most expensive. Safety stock does not grow in neat steps as the target rises; protection grows disproportionately as the target approaches completeness, because the buffer must stretch to cover the increasingly extreme tail of what demand and lead time might do. A 90 per cent target protects against the plausible; a 99.9 per cent target protects against the freak; promising to cover every conceivable outcome means carrying worst-case stock on every item, every day. The carrying cost of that promise becomes crushing for practical purposes: cash converted into shelves, insurance, and, for dated goods, eventual write-offs.

It is also a promise no stock policy can keep. Suppliers fail, quality rejections happen, and the freak outcome the buffer never anticipated occasionally arrives anyway. The professional position is not the perfect number but the chosen number: a target set deliberately for each segment of the assortment, with its residual risk named and accepted by the people accountable for it. An organisation that announces 100 per cent has not made a policy decision; it has declined to make one, and it will discover its real target the first time the cash runs out or the warehouse fills.

=== IMPORTANT NOTE ===
HEADING: A service level without a stock policy is marketing
BODY:
Announcing a service level changes nothing by itself. A 99 per cent availability promise is delivered, or not, by the machinery beneath it: safety stock actually purchased, reorder points actually honoured, order quantities actually reviewed, lead times actually managed, records actually accurate. If the buffers were never resized to support the new number, the announcement has merely raised the standard against which the operation will now visibly fail. That is the first half of the warning: a service level without the stock policy to deliver it is marketing.

The second half is the mirror image. A stock policy without a stated service level drifts just as badly, because nobody can say what the buffers are for. Every stockout then looks like negligence, every surplus looks like prudence, and arguments about stock are settled by seniority instead of by the balance between cost and failure this lesson taught. The target and the parameters are two halves of one instrument, and the measurement discipline, fill-rate history, turnover, days of supply, is the third. Set the target, size the policy to it, measure the result, and revise: the cycle only works when all three are present, and an organisation holding any two of them is decorating a gap.

=== MCQ 1 ===
QUESTION:
The managing director of a distribution company tells the quarterly review: "From next month, we will hold a 100 per cent service level on every product. I want stockouts to become impossible."

Which statement best evaluates this instruction?
POINTS: 1
OPTIONS:
1. The instruction is sound provided the company enlarges its warehouses before raising the service levels.
2. The instruction mistakes a policy decision for its abolition: protection grows disproportionately as the target nears completeness, and covering every conceivable outcome carries carrying costs that soon exceed any stockout cost, so professional practice sets a chosen target for each segment with its residual risk named and accepted.
3. The instruction is achievable because service levels are controlled by the stock the company already holds, and existing buffers were sized generously enough.
4. The instruction will succeed because stockouts are caused mainly by suppliers, so a 100 per cent internal target removes them.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

A service level is a policy choice: the availability the stock system is designed to deliver, balanced against the cost of providing it. As the target approaches completeness, safety stock grows disproportionately, because the buffer must stretch over the increasingly extreme tail of what demand and lead time might do. Carrying worst-case stock on every item converts cash into shelves, insurance, and eventual write-offs, a cost that for practical purposes outgrows the stockout cost it prevents. The professional alternative is a target set deliberately for each segment of the assortment, with the residual risk named and accepted.

Answer 1 accepts the instruction and answers only the storage question, missing that the cost problem lies in the stock itself. Answer 3 is wrong on both counts: existing buffers were sized to the old targets, and no realistic buffer makes stockouts impossible, since suppliers fail and extreme outcomes arrive. Answer 4 blames suppliers alone, but internal buffer sizing is exactly what determines whether a supplier's delay turns into a customer-facing stockout.

The takeaway: 100 per cent is not a strategy; it is a refusal to balance costs, and the balance is the strategy.

=== MCQ 2 ===
QUESTION:
A wholesaler serves the north of the country from a Kumasi store and the south from a Tema store. Each store holds its own safety stock against its own local demand swings, and the swings at the two sites do not move together. A consultant proposes holding this line's safety stock in one central store at Tema instead.

Which statement best describes the inventory effect of the proposal?
POINTS: 1
OPTIONS:
1. The central store must hold the sum of the two regional safety stocks, because total demand is unchanged, so no stock is released.
2. The pooled safety stock can be smaller than the combined regional buffers, because independent local swings partly cancel when demands share one pool, though replenishment to the more distant region becomes slower or costlier to transport.
3. Pooling eliminates stockouts entirely, because one large store cannot run short when two smaller stores could.
4. Pooling has no effect on total stock, because safety stock depends only on the item's unit value and not on where it is held.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

Safety stock exists to absorb variability, and pooled demand is steadier than the sum of its parts: when the two regions' good and bad months partly offset, the combined swing is smaller than the swings added together, so the same designed availability can be achieved with a smaller total buffer. The lesson's worked example put illustrative arithmetic on exactly this effect. The price of pooling is paid in service to the periphery: distant customers now wait for the longer delivery leg, the same facility-and-inventory against delivery-time-and-transport trade-off the network lesson placed on the other side of the decision.

Answer 1 commits the commonest pooling error: adding the buffers as if variability added too, when the cancelling of swings is the entire source of the gain. Answer 3 overclaims: pooling shrinks the expected shortage, but no stock level eliminates it, and correlated swings such as a shared festive season erode the gain. Answer 4 denies the effect altogether; safety stock is sized against variability and lead time, both of which change when stock is pooled.

The takeaway: pooling buys the same availability with less total hedge and pays in delivery speed.

=== MCQ 3 ===
QUESTION:
A distributor's stock review shows two items. A consumable filter turns over 12 times a year, about 30 days of supply. A specialised pump impeller for one engine family turns over about 1.3 times a year, about 274 days of supply, and is ordered from a maker sixteen weeks away. A manager proposes cutting the impeller stock until its turnover matches the filter's.

Which statement best evaluates the proposal?
POINTS: 1
OPTIONS:
1. The proposal is sound, because a higher turnover is always better and any item with low turnover is over-stocked by definition.
2. The proposal is unsound, because the impeller's high days of supply is a deliberate buffer against a long lead time and expensive failure; the measures locate questions rather than answer them, and judgement depends on the item's role, lead time, and criticality.
3. The proposal is unsound because turnover cannot be measured for spare parts, only for consumables.
4. The proposal is sound, because both items are selling steadily and therefore their stock positions must be equally healthy.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

Inventory turnover, the cost of goods sold divided by average inventory, and days of supply, average inventory divided by average daily usage, are diagnostic instruments: they show where stock sits and how fast it moves, but the verdict requires the item's role. The impeller's 274 days are the policy, not an accident: a critical spare with a sixteen-week replenishment lead time, whose absence can hold a customer's vessel, justifies a buffer that a locally replenished consumable never would. Cutting it to match the filter's 30 days would disarm exactly the protection the customers depend on. The review should instead watch the buffer's assumptions: if the engine family retires or the maker opens a nearer depot, the policy must be recomputed, or the buffer ages into the obsolete-stock flag.

Answer 1 applies a league-table rule the lesson explicitly dismantled; low turnover can be negligence or deliberate protection, and only the item's role distinguishes them. Answer 3 invents a false limitation: turnover is computable for any item with usage and stock records. Answer 4 reads both figures as equally healthy, ignoring that one policy is matched to its supply reality while the other is only assumed to be.

The takeaway: the measures flag; the item's role interprets.

=== FACTS & SOURCES ===
- Definitions of Inventory Optimisation, Service Level, Safety Stock, Cycle Stock, Reorder Point, Economic Order Quantity (EOQ), ABC Analysis, Inventory Holding Cost, Ordering Cost, Stockout, Fill Rate, Inventory Turnover, Replenishment Lead Time, and Inventory Position follow the lesson brief's key terms, defined at first use and used naturally in the blocks. — source: curriculum/lesson_briefs/module-13/lesson-13.3.md key terms.
- Service level taught with its two common definitions, cycle service level as the target probability of no stockout and fill rate as the share of demand met from stock, with the organisation explicit about which is in use; higher targets need disproportionately more safety stock; no statistical safety-stock formula is presented. — source: research sheet logistics-scm-frameworks.md section 5; DO NOT CLAIM item 18.
- Reorder point taught as expected demand during the lead time plus safety stock, carried over from Lesson 8.3's mechanics. — source: research sheet logistics-scm-frameworks.md section 5; curriculum/drafts/module-08/lesson-8.3.md.
- EOQ taught only as principles: a classic model estimating an order quantity that minimises the sum of ordering and holding cost under strong simplifying assumptions (constant demand, full delivery at zero stock, fixed order cost, no quantity discounts or stockouts), treated as a model rather than a law; no formula is presented as a universal recipe. — source: research sheet logistics-scm-frameworks.md section 5 and DO NOT CLAIM item 18.
- ABC analysis taught as a classification grouping items by relative importance, commonly annual consumption value, applied here to segment service levels and review intensity. — source: research sheet logistics-scm-frameworks.md section 5.
- Inventory turnover taught as COGS divided by average inventory; days of supply as average inventory divided by average daily usage, approximately 365 divided by turnover when usage aligns with the cost figure; the lesson states the denominator in use. — source: research sheet logistics-scm-frameworks.md section 5.
- Postponement (delayed differentiation) taught as keeping the product generic and deferring final configuration (dyeing, labelling, local packaging, final assembly) until real demand is known; suited to high demand uncertainty. — source: research sheet logistics-scm-frameworks.md section 8.
- Network design trade-off taught symmetrically: more stocking points cut delivery time and outbound transport cost but add facility and inventory cost; centralised networks do the reverse. Pooling (risk pooling across stocking points) taught as a concept with expressly illustrative arithmetic; no square-root-law or other formula is claimed as universal; the correlated-demand limit is stated. — source: research sheet logistics-scm-frameworks.md section 8 (network design) and general supply chain knowledge.
- Lead time components (order processing, preparation/pick-pack, transport and handling, customs clearance internationally) and OTIF as the strict on-time-and-in-full fulfilment measure, referenced as upcoming in Lesson 13.4. — source: research sheet logistics-scm-frameworks.md section 7.
- Bullwhip causes (forecast updating/demand signal processing, order batching, price fluctuations, rationing/shortage gaming) referenced only as already taught in Lesson 13.1; no amplification magnitudes claimed. — source: research sheet logistics-scm-frameworks.md section 8; curriculum/drafts/module-13/lesson-13.1.md.
- Holding-cost and failure-cost families (capital, space, insurance, shrinkage, obsolescence; lost margin, expediting, lost customers, contractual damage) are general business knowledge consistent with Lesson 10.1's cost families; no benchmark percentages or return figures are claimed anywhere in the lesson. — source: general business knowledge; curriculum/drafts/module-10/lesson-10.1.md.
- All arithmetic (reorder points 580 and 930 from 330 units of expected lead-time demand plus 250 or 600 units of safety stock; expected stockout costs GHS 6,000, GHS 600, GHS 1,440, and GHS 144 from 1.2 or 0.12 expected events; extra carrying costs GHS 2,100 and GHS 2,000; pooling release of 120 cartons, GHS 18,000 of working capital and GHS 900 a year; turnover of 12 and about 1.3; days of supply of about 30 and about 274 from daily usage of about 1,315 and about 164 dollars) is computed from expressly illustrative teaching figures labelled as such in each worked example; no real-company data is used. — source: WRITING_SPEC.md fact-safety rule 5.1.
- Companies in examples are generic (a health-and-wellness distributor in Accra, a food wholesaler with stores in Tema and Kumasi, a marine spare-parts distributor in Rotterdam); no factual claims are attached to real named firms; the Ghana settings (Accra, Tema, Kumasi) and the international setting (Rotterdam) satisfy the example-placement rule. — source: WRITING_SPEC.md section 4.
- Cross-references by name, no re-teaching: Lesson 5.4 Shipment Tracking and Customer Communication (communicating when promises slip); Lesson 7.1 Ocean Freight Operations and Vessel Schedules and Lesson 7.2 Air Cargo Operations and Cargo Acceptance (transit speeds on international lanes); Lesson 8.3 Inventory Control, FIFO, and FEFO (FIFO/FEFO, ABC analysis, reorder point, EOQ, the formulas-are-servants note); Lesson 8.4 Warehouse Documentation and Stock Reconciliation (record discipline); Lesson 10.1 Components of Total Logistics Cost (carrying cost, costs of failure, air-versus-sea total-cost reading); Lesson 13.1 Demand Forecasting and Supply Planning (forecast error, S&OP cycle, bullwhip, postponement from the planning side); Lesson 13.2 Transport Route and Network Optimisation (stocking-point trade-off); forward reference Lesson 13.4 Logistics Performance Indicators and KPIs (OTIF and fulfilment measures). — source: WRITING_SPEC.md section 7; lesson briefs for modules 5, 7, 8, 10, and 13.
