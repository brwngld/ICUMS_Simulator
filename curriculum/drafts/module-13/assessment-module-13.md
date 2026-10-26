# DRAFT — Module 13 Assessment: Supply Chain Planning and Optimisation

Coverage map (one line per question):

Q1 | lesson 13.1 | forecasting method matched to the data available: a stable SKU with a long history versus a new product with none, evaluated against a one-method-for-all proposal (qualitative and quantitative forecasting methods).
Q2 | lesson 13.1 | a three-month moving average calculated on fresh figures and its error record diagnosed: one-directional misses are bias from a lagged trend, to be fixed in the forecast rather than buffered with stock (moving average; forecast error; bias versus noise).
Q3 | lesson 13.1 | a single bullwhip cause named from a fresh order pattern: a promotional surge and slump with steady consumer offtake is forward buying under price fluctuations, discriminated from shortage gaming, random variation, and real demand change (bullwhip effect; forecast demand versus actual demand).
Q4 | lesson 13.2 | route versus network as two different decisions: daily dispatch rescues read as symptoms of a structure that no longer fits the flows, to be escalated into a network review rather than incentivised or software-bought (route optimisation versus network optimisation; design the network first).
Q5 | lesson 13.2 | hub-and-spoke versus direct judged on a fresh flow pattern: thin, scattered flows between seven towns justify the hub's consolidation despite its distance, handling, and waiting (direct delivery; hub-and-spoke network).
Q6 | lesson 13.2 | backhaul economics on a fresh lane: a carrier's better outbound rate is funded by turning an empty return leg into an earning one, and the internal comparison must count the shuttle's own empty return (backhaul; empty running).
Q7 | lesson 13.3 | the service level as a policy choice with costs on both sides: a 90-to-95 per cent raise evaluated by reorder points, expected stockout cost, and extra carrying cost on fresh illustrative figures (cycle service level; safety stock; reorder point).
Q8 | lesson 13.3 | the pooling trade-off applied fresh and by item: slow-moving lines with independent regional swings pool well, while fast movers and instant-response items must sit near demand, so pooling is decided item by item, not blanket (risk pooling; ABC-style segmentation of service).
Q9 | lesson 13.3 | lead time as a driver of the buffer: a shorter, steadier pipeline shrinks the exposure window the safety stock covers, so the mode decision belongs to transport and inventory cost together (replenishment lead time; safety stock; the total-cost lens).
Q10 | lesson 13.4 | OTIF computed correctly on fresh numbers: overlapping late-and-short failures subtracted once, against the on-time-only, in-full-only, and averaging distractors (on-time in-full).
Q11 | lesson 13.4 | a tension pair read together: rising picking productivity alongside falling order accuracy is a transfer, not a gain, and the measure must be published with its counterweight (the behaviour rule; warehouse productivity with order accuracy).
Q12 | lesson 13.4 | targets versus actuals and the borrowed-benchmark warning: a 99 per cent promise made from a conference figure without a baseline, against the define, baseline, then target sequence (benchmarking; baseline first; performance target versus actual result).

=== ASSESSMENT Q1 | tests lesson 13.1 ===
QUESTION:
A supplier of industrial consumables plans next quarter's purchases for two items. Item A is an established cleaning chemical with four years of steady monthly sales records. Item B is a new hand-tool range launching next month, never sold in this market. At the planning meeting, a colleague proposes applying the same simple quantitative method to both items, because a single company-wide method is easier to administer.

Which option best evaluates the proposal?

POINTS: 1
OPTIONS:
1. The proposal is sound, because a consistent company-wide method reduces forecast error on both items regardless of the data available for each.
2. The proposal is sound for Item B but not for Item A: new products need quantitative methods as soon as decisions loom, while established items respond best to expert judgement.
3. The proposal should be amended: quantitative forecasting fits Item A, whose long, steady history lets a method learn the pattern, while Item B, with no sales history, must be forecast qualitatively through expert judgement, structured market surveys, or a Delphi-style expert panel.
4. The proposal should be amended in the opposite direction: expert judgement should carry Item A because experienced salespeople outperform formulas on mature products, and Item B should wait for six months of history before any forecast is attempted.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

The choice of forecasting method is a matter of fit between the method and the data. Quantitative forecasting learns from numerical history and assumes the pattern it finds continues into the future; Item A, with four years of steady monthly records, is exactly the case that rewards such methods, whether a moving average, exponential smoothing, or a causal model. Qualitative forecasting, built on expert judgement, structured market surveys, and Delphi-style panels that aggregate independent expert opinion in anonymous, iterated rounds, is the method of necessity where numbers do not exist. Item B has never sold in this market, so structured judgement is the only honest basis for the launch commitments that lead times force now.

Answer 2 inverts the logic, assigning quantitative methods to the item without history and judgement to the one with data. Answer 1 elevates administrative consistency over fit; a consistent method that ignores each item's data situation produces a predictable failure on the new range. Answer 4 inverts the assignment again and adds the waiting fallacy: postponing the forecast until history exists does not remove the purchasing and space decisions, it only strips them of a stated demand assumption.

The takeaway: match the method to the data, and when there is no history, structure judgement rather than pretend history exists.

=== ASSESSMENT Q2 | tests lesson 13.1 ===
QUESTION:
A distributor records monthly demand for a fast-moving SKU as 300, 310, 320, 330, 340, and 350 cartons for months 1 to 6. All figures are illustrative for teaching purposes. The company forecasts with a three-month moving average, so the forecasts made for months 4, 5, and 6 were 310, 320, and 330 cartons, and each month's replenishment was planned from that forecast. The warehouse reports recurring stockouts.

Which option best describes the month 7 forecast and what the error record shows?

POINTS: 1
OPTIONS:
1. Forecast 340 cartons; every forecast so far has fallen exactly 20 cartons below the actual that followed, a one-directional pattern that is bias from the rising trend an averaging method lags, so the remedy is a trend-aware method or market intelligence, not a larger safety stock.
2. Forecast 350 cartons; the most recent month is always the soundest estimate, and the moving average should be abandoned as unnecessarily complicated.
3. Forecast 340 cartons; the forecasts have tracked the series closely, so the method is accurate and the stockouts the warehouse reports must be unrelated to forecasting.
4. Forecast 325 cartons; the average of all six observed months is the most stable basis for the forecast, and the recurring misses are random noise that safety stock should buffer.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

The month 7 forecast is the average of months 4 to 6: 330 plus 340 plus 350, divided by three, which is 340 cartons. The error record matters more than the number. The forecasts for months 4, 5, and 6 were 310, 320, and 330, and the actuals that followed were 330, 340, and 350: every forecast missed low, by the same 20 cartons. Errors scattered on both sides of a sound centre are noise, to be buffered with safety stock; errors clustered in one direction are bias, and this series shows textbook bias — demand is rising steadily, and an averaging method lags a trend by construction. Because each reorder point is built from the forecast of demand during the lead time, a persistently low forecast starts every replenishment cycle from the wrong base, which is exactly why stockouts recur even though the buffer was sized correctly for scatter.

Answer 2 abandons the method for the last observation, which still chases the trend one period behind and carries no error discipline. Answer 3 reads close tracking as accuracy and ignores the direction of the misses, the exact confusion that lets bias survive. Answer 4 averages all six months, a figure no moving-average policy produces, and mislabels systematic error as noise — the mistake that leads planners to buy ever-larger buffers against a model that could simply be corrected.

The takeaway: compute the forecast, then read the errors — fix bias in the method, and buffer only noise with stock.

=== ASSESSMENT Q3 | tests lesson 13.1 ===
QUESTION:
A manufacturer of cooking oil sells through one wholesaler, whose monthly orders have historically tracked consumer offtake closely. The manufacturer then runs a deep one-month promotional discount. During the promotion month the wholesaler's orders roughly triple; the following month they fall well below their normal level; retail data show that what consumers actually bought barely moved. The sales manager proposes treating the surge as evidence of booming demand and expanding production.

Which option best names what the order pattern actually shows?

POINTS: 1
OPTIONS:
1. The pattern is a shift in consumer demand that the retail data have not yet captured, so expanding production now positions the manufacturer ahead of the market.
2. The pattern is shortage gaming: the wholesaler inflated orders to secure a larger allocation during a shortage and cancelled once the scare passed.
3. The pattern is random variation in the wholesale tier, and no management response is required beyond watching the next few months.
4. The pattern is forward buying driven by the price fluctuation: the wholesaler stocked up at the promotional price and will live off that stock, so upstream has read a phantom surge and slump; everyday stable pricing and sharing downstream sales data would flatten the swings.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

The lesson's bullwhip block names four causes of upstream order amplification: demand-signal distortion, order batching, price fluctuations, and rationing or shortage gaming. The scenario isolates one of them. The trigger was the promotional discount; the wholesaler bought cheap and stocked up, then lived off that stock the following month; and consumer offtake — the actual demand — barely moved. The surge and slump in orders are therefore forward buying: phantom demand created by the price calendar, not by consumers. Expanding production against it would build capacity and stock for a wobble the manufacturer's own promotion manufactured. The countermeasures that attack this cause are everyday stable pricing in place of deep promotions, and sharing downstream sales data so every tier forecasts from consumption rather than from distorted orders.

Answer 2 names a real cause but the wrong one: shortage gaming requires supply to run short and sellers to ration by order size, and none of that appears in the scenario. Answer 1 mistakes the distorted order signal for the market — the misreading that leads upstream tiers to invest in phantom demand. Answer 3 dismisses a patterned, explicable swing as random variation, forfeiting both the diagnosis and the remedy.

The takeaway: when upstream orders swing while end demand holds steady, find which bullwhip cause the pattern bears, and remove the cause rather than forecast its echoes.

=== ASSESSMENT Q4 | tests lesson 13.2 ===
QUESTION:
At a distribution company, the dispatch desk re-sequences delivery rounds every morning, and several of its best people spend their days rescuing problem deliveries: stock regularly expedited from one region to another to cover shortages, a consolidation hub used on one lane because it exists rather than because the flows justify it, and direct runs invented overnight for lanes the network was never designed to serve. The operations manager proposes a new incentive scheme to make the dispatch team's daily rescues faster.

Which option best assesses that response?

POINTS: 1
OPTIONS:
1. The response is appropriate: sharper incentives will make the daily rescues faster, which is what the operation currently needs most.
2. The response misreads the signal: recurring exceptions are network data — daily routing is compensating for a structure that no longer fits the flows — so the pattern should be escalated into a network review, the structure redesigned, and the routes then left to run quietly inside it.
3. The response is unnecessary because route planning and network design are the same decision carried out at different times of day, so nothing needs to change beyond the daily schedule.
4. The response is premature: the operation should first buy a routing-software package, and only if the software cannot fix the daily patterns should the network be examined.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The lesson draws a hard line between two decisions of different kinds. Route optimisation chooses the way a consignment travels within the network as it exists; network optimisation changes the structure itself — facilities, links, and flows — and is an investment taken rarely and deliberately. The symptoms listed are not routing failures. Stock repeatedly expedited between regions, a hub used because it exists rather than because the flows justify it, and direct runs invented overnight are the recognisable signature of daily routing being asked to compensate for a network that no longer fits the flows inside it. The lesson's rule is that recurring exceptions are network data: escalate the pattern into the network review, fix the structure, and let the routes run quietly inside it.

Answer 1 professionalises the firefighting, rewarding the rescue of deliveries instead of improving the system that manufactures the rescues — precisely how firefighting becomes institutionalised among an operation's best people. Answer 3 dissolves a distinction the lesson insists on: the two decisions differ in kind, in cost, and in reversibility, which is why they need different data, approvals, and review cycles. Answer 4 reaches for software first, but tools rank the options they are given; a routing package will optimise the runs inside a misfit structure faster, not repair the structure.

The takeaway: design the network first, then run routes within it — recurring daily exceptions are evidence about the network, not about the dispatch desk.

=== ASSESSMENT Q5 | tests lesson 13.2 ===
QUESTION:
A part-load carrier serves seven market towns. Between every pair of towns a small trickle of consignments moves each week; no single pair generates anything close to a full vehicle. A newly appointed manager proposes abolishing the regional hub and running vehicles directly between every pair of towns, arguing that the hub adds distance, handling, and delay to every consignment.

Which option best evaluates the proposal?

POINTS: 1
OPTIONS:
1. The proposal is sound, because the shortest distance between two towns is always the cheapest way to move freight between them, whatever the volumes on the lane.
2. The proposal is sound for the thin flows but should exempt any pair of towns that generates a full vehicle of its own.
3. The proposal would multiply part-load journeys: with thin flows on every pair, direct lines would need far more connections and would run mostly empty, while the hub consolidates many small consignments into full outbound vehicles — the structure this flow pattern justifies, its price being distance, handling, and waiting at the hub.
4. The proposal should be adopted for half the towns as a trial, because hub and direct structures are interchangeable where flows are thin.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

Structure follows flow. A hub earns its place where many origins and destinations exchange small consignments: it collects many part-loads, sorts them, and dispatches each outbound vehicle full. With seven towns and thin flows on every pair, direct lines would need one route per pair — seven towns give twenty-one direct connections against seven spokes — and each direct vehicle would run at a small fraction of capacity, with the cost and emissions of mostly empty journeys repeated on every leg. The hub's price is real: every inter-town consignment travels two legs, is handled at the hub, and waits for the outbound departure. But where no pair generates a full vehicle, that price is lower than the direct alternative of running largely empty vehicles — which is why part-load and groupage carriers typically operate hub-and-spoke terminal networks.

Answer 1 states the shortest-distance fallacy: distance per journey falls, but the number of journeys and the emptiness of each rise, and emptiness is what decides cost per unit carried. Answer 2 offers the hybrid inverted — the working pattern is direct lines where flows are dense and a hub where they are thin, never the reverse. Answer 4 treats the structures as interchangeable, when the whole skill is reading which flow pattern each structure serves.

The takeaway: count the flows, and give each lane the structure its volume supports.

=== ASSESSMENT Q6 | tests lesson 13.2 ===
QUESTION:
A manufacturer ships finished goods weekly from its plant to a retail depot in the north of the country, and its own shuttle vehicles return to the plant empty every week. A contract carrier offers to carry the northbound loads at a better rate than the internal cost of the shuttle, provided the manufacturer takes back its suppliers' returnable packaging — empty pallets and reusable crates — on the same vehicles from a collection point near the northern depot.

Which option best explains why the carrier can offer the better rate, and what the manufacturer should count?

POINTS: 1
OPTIONS:
1. The better rate is possible because cargo on the return leg turns a pure-cost journey into an earning one: the carrier's vehicles would otherwise run empty, burning fuel, driver time, and vehicle life with no revenue, and by supplying return cargo the manufacturer relieves exactly that empty-running problem — while the internal comparison should count the shuttle's own empty return in its cost per delivered load.
2. The carrier is pricing aggressively to win the account and will raise the rate once the manufacturer is committed, so the offer should be refused whatever the return cargo.
3. The better rate reflects the carrier's newer vehicles, which burn less fuel per kilometre than the manufacturer's trucks, so the return cargo is incidental to the economics.
4. The return cargo benefits only the carrier, so the manufacturer should accept the rate but refuse to carry anything southbound.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

Empty running — a vehicle travelling without paying cargo — is a major cost and emissions inefficiency: the empty leg burns fuel, driver time, and vehicle life at the full rate while earning nothing, and produces emissions with no freight to show for them. Flows are unbalanced in space, so return cargo is scarce on many lanes, which is exactly why carriers will price an outbound lane better where a shipper can offer traffic for the return direction. The manufacturer's pallets and crates flowing south turn the carrier's pure-cost journey into an earning one, and the relief of the carrier's empty-running problem is what funds the better northbound rate. The manufacturer should count honestly on its own side too: the internal shuttle's true cost per delivered load includes the empty return leg, so the internal figure the offer is measured against is flattered.

Answer 2 reads the offer as a loss-leader trick, but the economics stand on their own: filling a return leg genuinely releases cost that can be shared. Answer 3 attributes the rate to vehicles, when the decisive line is cargo on the return leg. Answer 4 refuses the very cargo that sustains the saving, leaving the manufacturer's own packaging out of position and the carrier's leg empty again.

The takeaway: an empty kilometre is pure cost and pure emissions; structural backhauls make both sides of a lane cheaper.

=== ASSESSMENT Q7 | tests lesson 13.3 ===
QUESTION:
An importer stocks one critical spare part with an expected demand of 320 units during the replenishment lead time. All figures are illustrative for teaching purposes. At a 90 per cent cycle service level the safety stock is 80 units, giving a reorder point of 400. Raising the target to 95 per cent requires a safety stock of 140 units and a reorder point of 460, so 60 extra units are carried all year at an illustrative GHS 5 per unit per year. The item runs about 12 replenishment cycles a year; the raise halves expected failures from about 1.2 to about 0.6 a year, and a typical stockout costs an estimated GHS 800 in lost margin and expediting.

Which option best evaluates raising the target?

POINTS: 1
OPTIONS:
1. Raising the target costs nothing, because safety stock is insurance whose carrying cost is only an accounting entry rather than real money.
2. Raising the target is justified on the numbers: expected stockout cost falls from about GHS 960 to about GHS 480 a year, a saving of roughly GHS 480, against about GHS 300 of extra carrying cost for the 60 extra units — a gain of roughly GHS 180 a year before counting anything the estimate left out, and a gain that had to be bought with real carrying cost, because a service level is a policy choice with costs on both sides.
3. Raising the target is unjustified, because the reorder point rises to 460 and any increase in the reorder point means over-stocking by definition.
4. The two targets deliver the same availability, because the reorder point already contains safety stock at both levels, so the choice can be made on convenience.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

A service level is a policy choice, and the choice has costs on both sides. At 90 per cent, 12 cycles a year carry a 10 per cent failure chance each, about 1.2 expected stockouts; at 95 per cent the expectation falls to about 0.6. At an estimated GHS 800 per event, expected stockout cost falls from about GHS 960 to about GHS 480 a year — a saving of roughly GHS 480. The raise is not free: the reorder point moves from 400 to 460, the extra 60 units of safety stock are carried all year, and at GHS 5 per unit-year the additional carrying cost is about GHS 300. The comparison favours the raise by roughly GHS 180 a year before counting any stockout consequence the estimate left out — and the protection had to be purchased with genuine carrying cost, which is the whole discipline of setting the target deliberately.

Answer 1 treats carrying cost as an accounting fiction, but holding cost is real money in capital, space, insurance, and obsolescence whether or not an invoice names it. Answer 3 declares any higher reorder point over-stocking by definition, the league-table reflex; the question is whether the extra protection is worth its price, and here it is. Answer 4 denies that the targets differ, but the two reorder points are designed to buy different failure probabilities.

The takeaway: set the target deliberately, price both sides honestly, and let the comparison decide.

=== ASSESSMENT Q8 | tests lesson 13.3 ===
QUESTION:
A stationery wholesaler stocks some 2,000 items at four regional stores. A consolidation study splits the assortment into slow-moving specialist lines whose demand is uncertain and moves independently in each region, and fast-moving everyday lines that nearby schools and offices reorder within hours of running out. Management decides to pool the safety stock of the whole assortment into one central store, because pooling one product family in a trial had reduced total stock.

Which option best evaluates the decision?

POINTS: 1
OPTIONS:
1. The decision is sound and should be applied to the whole assortment as quickly as possible, because the more items are pooled, the larger the saving on every item.
2. The decision is unsound in principle, because pooling never reduces total stock, and the earlier trial's saving must have been measured incorrectly.
3. The decision should depend on unit value alone: the most expensive items should stay regional, and everything cheap should be pooled.
4. The decision overreaches: pooling pays best on the slow-moving lines whose regional swings partly cancel, while fast movers and items whose absence stops a customer's work within hours must live close to demand regardless, so the assortment should be pooled item by item along lines of importance and response need, as ABC-style classification supports.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

Pooling is real: when the same item is held at several sites, each site hedges its own local swings, and where those swings are independent they partly cancel under one pool, so the same availability can be designed with a smaller total buffer. But the lever has honest limits that a blanket decision ignores. The gains shrink when demands rise and fall together, and pooling must be paid for in response time to the periphery. The lesson's rule is to pool item by item: slow-moving lines with uncertain, independent regional demand are the natural candidates, while fast movers and items whose absence stops a customer's work within hours must sit close to demand regardless — exactly the split the study found in this assortment. ABC-style classification, grouping items by relative importance and pairing each class with the treatment it justifies, is the systematic instrument for drawing that line instead of leaving it to habit.

Answer 1 generalises from one successful family trial to the whole assortment, carrying pooling past the conditions that make it pay. Answer 2 denies the effect the trial demonstrated. Answer 3 substitutes unit value for the criteria that actually decide — variability, correlation, and response need — so the most expensive fast mover and the cheapest critical slow mover would both be misfiled.

The takeaway: pooling buys availability with a smaller total hedge, pays in delivery speed, and is decided item by item.

=== ASSESSMENT Q9 | tests lesson 13.3 ===
QUESTION:
A service company imports one critical component through an ocean pipeline of about six weeks — illustrative figures for teaching purposes — and holds a large safety stock against six weeks of demand variability and occasional port delays. A freight forwarder offers an air routing that delivers in about five days at a higher cost per consignment. The finance manager objects that the air rate is more than double the ocean rate per shipment and should be refused.

Which option best evaluates the objection?

POINTS: 1
OPTIONS:
1. The objection is correct, because freight cost per consignment is the measure that should decide between competing routings.
2. The objection is correct, because switching to air would force the company to hold more safety stock, since air shipments are smaller than ocean consignments.
3. The objection compares only one line of the total: the shorter, steadier pipeline shrinks the exposure window the safety stock exists to cover, so the same service can be kept with a much smaller buffer, and the mode choice should be made on transport and inventory cost together, as the total-cost lens requires.
4. The objection is wrong because safety stock depends only on the item's unit cost, not on how the item is shipped.
CORRECT: 3
EXPLANATION:
The correct answer is Answer 3.

Safety stock is sized against what can go wrong during the replenishment lead time — the exposure window. A six-week ocean pipeline exposes the operation to six weeks of demand variability plus occasional port delay; a five-day air routing shrinks the window to days and, typically, steadies it. The same service promise can therefore be kept with a much smaller buffer, and the released stock is a genuine inventory saving. This is the total-cost discipline: freight savings and inventory savings live in different ledgers, so a mode that looks dearer per consignment can be cheaper to the business once the stock it eliminates is priced — and the decision must compare transport and inventory together rather than one line at a time.

Answer 1 lets a single line, cost per consignment, decide a system question — precisely the silo comparison the total-cost lens exists to correct. Answer 2 inverts the mechanism: the shorter pipeline reduces the exposure, and with it the buffer, not the reverse. Answer 4 denies the link between lead time and safety stock altogether; the buffer exists because demand and supply vary during the wait, so the length and the reliability of the wait are what set its size.

The takeaway: shrink the exposure and the buffer shrinks with it — judge the mode on transport and inventory cost together, never on the freight line alone.

=== ASSESSMENT Q10 | tests lesson 13.4 ===
QUESTION:
A distributor of household goods completed 150 orders in April. Checking delivery notes against customer orders — all figures illustrative for teaching purposes — the supervisor finds that 12 orders arrived after the promised date, 9 orders were delivered short of the ordered quantity, and 3 of the late orders were also short.

Which figure is the distributor's correct OTIF for April?

POINTS: 1
OPTIONS:
1. 92 per cent, the proportion of orders that arrived on time.
2. 94 per cent, the proportion of orders delivered in full.
3. 93 per cent, the average of the on-time rate and the in-full rate.
4. 88 per cent, the proportion of orders that were both on time and in full.
CORRECT: 4
EXPLANATION:
The correct answer is Answer 4.

OTIF counts only orders that clear both conditions at once: delivered within the agreed time and complete in quantity. The failures are the 12 late orders plus the 9 short orders minus the 3 that appear in both lists, which is 18 failed orders, leaving 132 of 150 orders delivered both on time and in full. That is 132 divided by 150, multiplied by 100 — 88 per cent.

Answer 1 is the on-time delivery rate, 138 of 150, which is exactly the weakness OTIF exists to correct: an order counted on time may still be short. Answer 2 is the in-full rate alone, 141 of 150, which ignores the time condition entirely. Answer 3 falls into the averaging trap: averaging 92 and 94 per cent gives 93 per cent, but the average double-counts the 3 orders that failed on both counts and flatters the true result. OTIF is deliberately strict — an order that is late or short has failed — and overlapping failures are subtracted once, never twice.

The takeaway: compute OTIF from the overlap-corrected failure count, then split the failures diagnostically, because the single number hides two different diseases — lateness and shortage — with different causes and different owners.

=== ASSESSMENT Q11 | tests lesson 13.4 ===
QUESTION:
A distribution centre introduces picking-speed targets. Lines picked per labour hour rise sharply, orders still leave on time, and the centre's manager reports the productivity gain to head office as a clear improvement. Over the same weeks, customer complaints about wrong items in delivered orders increase, and returns caused by picking errors climb.

Which option best describes how head office should read the report?

POINTS: 1
OPTIONS:
1. The report is reliable, because a rise in lines picked per labour hour is direct evidence that the picking process has improved.
2. The report shows a tension transfer: productivity measured alone invites errors, and speed purchased with accuracy damage is not an improvement, so the productivity measure must be published with its counterweight — order accuracy — and the two read together before any gain is declared.
3. The report shows that the complaints are coincidental, because picking speed and picking accuracy are independent measures produced by different processes.
4. The report shows that the targets have failed and should be scrapped, with the centre returning to whatever picking pace it used before.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

People optimise what they are measured on, and productivity measured alone is one of the standard traps: lines picked per labour hour can be raised by rushing, and speed purchased with errors is not improvement. The behaviour rule requires the designer to state what behaviour each measure should encourage and to pair every measure with its counterweight — speed with accuracy, cost with service. Head office should therefore read the productivity number beside order accuracy, and the rising complaints and picking-error returns are the accuracy twin already speaking: part of the reported gain is a transfer from quality to speed, and the pair must be judged together before any improvement is declared.

Answer 1 celebrates a single-family reading, exactly how a tension transfer gets reported as victory. Answer 3 asserts independence, but the lesson's causal chain runs the other way: picking correctness feeds the customer's experience of reliability, so speed and accuracy are linked by construction, not coincidence. Answer 4 overcorrects; the remedy is not abandoning speed targets but defining them alongside their counterweight, so that improvements are real rather than purchased with defects.

The takeaway: publish tension pairs together and judge them together, or the operation will quietly sell one to buy the other.

=== ASSESSMENT Q12 | tests lesson 13.4 ===
QUESTION:
A newly appointed logistics manager finds that her company has never measured its delivery reliability. At a trade conference she hears that leading distributors report on-time in-full results of 99 per cent, and she announces to customers that the company will match 99 per cent from the following month.

Which option best assesses the announcement?

POINTS: 1
OPTIONS:
1. The announcement promises a number the operation has never measured, produced under definitions and conditions it cannot see: no universal benchmark values exist for OTIF or any other KPI, so the sound sequence is to define the measure, baseline it for at least one full normal period, and set the target from the company's own trend and its own service promise.
2. The announcement is sound practice, because published figures from leading distributors are the most reliable available targets, and adopting them is what benchmarking is for.
3. The announcement is sound provided the manager raises the promise to 100 per cent, which removes any risk of disappointing customers.
4. The announcement should be implemented by reporting 99 per cent as achieved from the first month, since the target now defines the result the company is committed to.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

There are no universal benchmark values for OTIF, inventory accuracy, utilisation, or any other KPI. A number reported by another operation was produced under its definitions, product mix, order profile, distances, network shape, and promises — conditions this company cannot see and cannot copy, starting with how tightly on time was even counted. The lesson's sequence is explicit: define the measure completely, baseline it for at least one full normal period, then set the target just beyond the baseline, in the direction the service promise requires, with a date. A target set against a measured baseline is a commitment; one set against a conference figure is a wish announced to customers. Benchmarking has a legitimate use — learning which indicators an industry considers worth measuring — and the internal benchmark, the company's own history, is the comparison that shares its definitions and conditions.

Answer 2 mistakes target-shopping for benchmarking, which is exactly the importation of impressive numbers the lesson prohibits. Answer 3 doubles the error and collides with the inventory lesson's finding that 100 per cent is not a strategy but a refusal to choose a target. Answer 4 reports the target as the result, confusing a plan with an achievement.

The takeaway: baseline first, then target from your own trend and your own promise — baseline and trend are your truth; everything else is somebody else's story.

=== FACTS & SOURCES ===
- All twelve questions and their explanations derive solely from the content of the four module 13 lesson drafts (curriculum/drafts/module-13/lesson-13.1.md, lesson-13.2.md, lesson-13.3.md, lesson-13.4.md) and the key terms and learning objectives in the module 13 lesson briefs (curriculum/lesson_briefs/module-13/). No external facts, organisations, vendors, platforms, statistics, duty rates, fee amounts, or benchmark percentages asserted as fact are introduced anywhere in the assessment; there are no exceptions. The 99 per cent figure in Q12 is a fictional scenario claim put in a speaker's mouth and dismantled by the correct answer, mirroring the lesson's own treatment of borrowed numbers.
- All figures used in question stems are round illustrative teaching numbers labelled as such in their stems, per WRITING_SPEC.md rule 5.1: Q2 carton series 300 to 350; Q7 lead-time demand 320, safety stocks 80 and 140, reorder points 400 and 460, GHS 5 per unit-year, 12 cycles, GHS 800 per stockout; Q9 six weeks ocean and five days air; Q10 order counts 150, 12 late, 9 short, 3 overlapping. The remaining stems use no amounts requiring labelling.
- Arithmetic verified: Q2 — month 7 moving average (330+340+350)/3 = 340; forecasts 310, 320, 330 versus actuals 330, 340, 350, each 20 low; six-month average 1950/6 = 325. Q5 — seven towns give 7x6/2 = 21 direct connections against 7 spokes. Q7 — reorder points 320+80 = 400 and 320+140 = 460; extra 60 units at GHS 5 = GHS 300; expected failures 12x0.10 = 1.2 and 12x0.05 = 0.6; stockout cost 1.2x800 = GHS 960 and 0.6x800 = GHS 480; saving GHS 480; net gain GHS 180. Q10 — failures 12+9-3 = 18; OTIF 132/150 = 88 per cent; OTD 138/150 = 92 per cent; in-full 141/150 = 94 per cent; averaging trap (92+94)/2 = 93 per cent.
- Q1 to Q3 are as taught in lesson 13.1. Q1 extends the lesson's new-product MCQ into a two-item discrimination, adding the stable-SKU side of the method-fit rule. Q2 uses a fresh rising series (not the lesson's 200-to-250 example) and merges the calculation objective with the bias-versus-noise diagnosis, which the lesson's own MCQs did not test. Q3 isolates the price-fluctuations cause of the bullwhip effect, where the lesson's MCQ tested the full cause-and-remedy package; the promotion trigger discriminates the scenario against the shortage-gaming distractor.
- Q4 to Q6 are as taught in lesson 13.2. Q4 tests the design-first Important Note (recurring exceptions as network data; firefighting institutionalised), untested by the lesson's own MCQs, with a software-first distractor drawn from the lesson's tools caution. Q5 inverts the lesson's dense-lane MCQ: thin scattered flows justify keeping the hub, with fresh geography and an inverted-hybrid distractor. Q6 applies the empty-running and backhaul block, which no lesson MCQ covered; the returnable-packaging backhaul is fresh.
- Q7 to Q9 are as taught in lesson 13.3. Q7 re-angles the service-level-as-policy-choice target from the lesson's 100-per-cent critique to a 90-to-95 raise priced on both sides with fresh reorder-point arithmetic; no reuse of the lesson's 580/930 or medicine/multivitamin figures. Q8 tests the pooling limits — correlated demand, response time, fast movers — as an item-by-item decision, where the lesson's MCQ tested the basic pooling effect; the Tema-Kumasi two-store numbers are not reused. Q9 tests the lead-time lever and the transport-versus-inventory total-cost reading, which the lesson's MCQs did not cover.
- Q10 to Q12 are as taught in lesson 13.4. Q10 computes OTIF on fresh numbers (150/12/9/3 giving 88 per cent), deliberately distinct from the lesson's 80/6/4/2 giving 90 per cent and its 100/8/5/2 worked example giving 89 per cent; the distractors are the lesson's own named traps. Q11 applies the behaviour rule's picking-speed example and the tension-pair reading rule, untested by the lesson's MCQs (which used the consolidation pair). Q12 tests the borrowed-benchmarks note and the target-versus-actual distinction directly, where the lesson's MCQ addressed benchmarks only as one distractor.
- Coverage note: each lesson contributes exactly three questions, in lesson order, and every question is scenario-based with at least one application question per lesson. The CORRECT positions run 3, 1, 4, 2, 3, 1, 2, 4, 3, 4, 2, 1 across the twelve questions — each position used exactly three times. No question uses negative form ("which is NOT") and no option list includes "All of the above".
