# DRAFT — Lesson 13.2: Transport Route and Network Optimisation

=== KEY CONCEPT ===
HEADING: Route decisions and network decisions are two different questions
BODY:
This lesson opens the optimisation layer of transportation planning. Module 3 taught how transport modes are chosen, and Lesson 3.2 defined the multimodal and intermodal arrangements this lesson revisits at planning level. Lesson 7.1 and 7.4 covered ocean operations and freight charges; Lesson 12.1, International Transport Corridors, followed goods along border-crossing routes. This lesson stands above those operational views and asks the planning questions: which way should this shipment travel, and what structure should the company build so that the shipments of the next five years travel well? Lesson 13.1, Demand Forecasting and Supply Planning, supplied the demand picture both answers depend on; the next lesson, 13.3, Inventory Optimisation and Service Levels, will optimise the stock the network holds.

Transportation planning is the process of organising transport resources, routes, schedules, and services to meet shipment requirements. Within it sit two decisions that differ in kind, and confusing them is the first mistake this lesson corrects.

1. Route optimisation is the process of identifying transportation routes that best satisfy specified cost, time, distance, and operational requirements. It answers the question: given the network as it exists, which way should this consignment go? Route decisions are made daily, at the dispatch desk, shipment by shipment.

2. Network optimisation is the improvement of facility locations, transportation links, and operational flows to achieve defined performance objectives. It answers a different question: what should the network itself look like? A logistics network is the system of facilities, transportation links, and operational relationships used to move and distribute goods — warehouses, hubs, ports, routes, and the services connecting them. Network decisions are investments: they cost capital, take months to implement, and are revisited rarely.

The clocks differ. A route can be changed next week at little cost beyond a change of mind; a distribution centre cannot. That difference in reversibility is why the two decisions need different data, different approvals, and different review cycles — and why this lesson keeps them separate throughout.

=== KEY CONCEPT ===
HEADING: What a route comparison actually weighs
BODY:
Route selection at planning level is a comparison of complete door-to-door options, not a scan of leg-by-leg prices. Lesson 7.4 taught the discipline of reading the whole charge build, and Lesson 10.1, Components of Total Logistics Cost, the total-cost lens; applied to a route, the lens asks what each option truly costs once everything it causes is counted. The comparison weighs six inputs.

1. Cost per leg. Each leg's linehaul, fuel, handling, and accessorial charges, built into a door-to-door figure — including the empty positioning legs vehicles run to reach their loading points.

2. Transit time. Door to door, including expected waiting at ports, terminals, and borders — not driving time alone; Lesson 12.1 showed how waiting clusters at a corridor's seams.

3. Reliability. How tightly transit times cluster around their average. Border friction, met in Lesson 12.1, turns a short routing into an unreliable one, and unreliability forces buffers of time and stock downstream.

4. Handling count. Every touch — a reload at a terminal, a transfer between vehicles, a cross-dock — adds delay risk and damage risk. This is Lesson 3.3's handling principle restated at planning level: the more a consignment is touched, the more can go wrong to it.

5. Constraints. A route constraint is a restriction affecting route selection, such as vehicle capacity, road access, time limits, or delivery requirements. Terminal cut-offs, vehicle size limits on certain roads, and equipment availability at the right place and date can disqualify an option before price is discussed.

6. The delivery window. A delivery window is a specified period during which goods are expected or permitted to be delivered. A routing arriving outside the window may be as useless as one arriving a day late; the buyer's receiving rhythm, not the map, sets the real deadline.

Route comparison also reopens the mode question of Lesson 3.2: a routing may differ from its rival by mode, not merely by road. Combining modes under one responsible operator is the multimodal arrangement; moving goods in one unchanged loading unit, such as a container, across modes is the intermodal arrangement. Both matter practically: each transfer between modes is a touch, and the contract structure decides who answers for the journey. A routing is finally chosen by weighing all six inputs together — never by picking the cheapest single leg.

=== KEY CONCEPT ===
HEADING: The components of a distribution network
BODY:
A distribution network is the arrangement of warehouses, distribution centres, transport routes, and delivery points used to supply customers. It is the network seen from the customer's end: the fixed structure through which every order must pass. Its components recur in every industry.

1. Origins. The factories, supplier sites, and import ports where stock enters the network. For an importing business the origin may be a gateway port such as Tema; for a manufacturer, the factory gate.

2. Storage and flow facilities. Central warehouses holding national stock, regional distribution centres holding stock close to demand, and cross-dock terminals, where goods move from the inbound vehicle to the outbound vehicle with little or no storage in between. The consolidation machinery of Lesson 5.3 and the inland depots of Lesson 9.2 live at this layer. Each facility is a place where stock rests and where handoffs happen.

3. Transportation links. The scheduled or ad hoc services joining the facilities: linehauls between warehouse and distribution centre, collection routes from suppliers, delivery rounds to customers.

4. Delivery points. The shops, sites, and households where goods leave the network. The final stage has its own name: last-mile delivery is the final transportation stage in which goods reach their intended recipient. Loads are small and stops are many, so each journey's cost is spread over little cargo and cost per unit delivered runs high — which is why the location of stock relative to customers matters.

Two facts make the network the master decision of this lesson. First, stock lives in the network: where facilities sit decides how much inventory the company must hold and where. Second, handoffs happen in the network: every facility a consignment passes through is a touch, carrying the delay and damage risk established earlier. Change the network and you change the cost and service of every shipment that will ever run through it — which is why network decisions are taken deliberately and rarely, and route decisions daily within them.

=== KEY CONCEPT ===
HEADING: Direct delivery and hub-and-spoke distribution
BODY:
Two pure structures anchor every distribution network discussion.

Direct delivery is a distribution arrangement in which goods move directly from an origin to a destination without passing through an intermediate distribution facility. A hub-and-spoke network is a distribution structure in which shipments move through central hubs connecting multiple origins and destinations. Each structure wins under different flow conditions; knowing which hold is the whole skill.

1. Direct delivery wins where flows are large and regular. When one origin-destination pair generates enough volume to fill vehicles on its own, a direct line gives the shortest distance, fewest touches, fastest transit, and no hub cost or delay. A full-truckload shuttle between a factory and a major customer is the classic case.

2. Hub-and-spoke wins where many origins meet many destinations in small quantities. When no single pair generates a full load, direct lines run half empty or needlessly often; a hub collects many small consignments, sorts them, and dispatches each outbound vehicle full. This is the consolidation logic of Lesson 5.3 expressed as a network shape, and the standard design of part-load road networks, whose carriers combine several shippers' freight in one vehicle — cheaper per unit, more handling, longer transit — which is why they typically operate hub-and-spoke terminal networks.

The hub's price is paid in distance, touches, and time: every inter-town consignment travels via the hub, is handled there, and waits for the outbound departure. The direct line's price is paid in utilisation: vehicles run part full unless the flow justifies them.

Few real networks are pure. The working pattern is hybrid — direct lines where flows are dense, a hub-and-spoke layer where they are thin; worked example two puts numbers on the choice. The habit is to let the flow pattern, not fashion, decide which lanes hub and which run direct.

=== KEY CONCEPT ===
HEADING: Consolidation, vehicle capacity, and load factor
BODY:
Route and network choices are made real by vehicle choices, and vehicle economics rest on two measures.

Vehicle capacity is the maximum permitted or practical quantity, weight, or volume of cargo that a vehicle can transport. It is bounded from two sides: the practical side, how much the body holds, and the legal side, permitted weight limits enforced at weighbridges along major corridors. Load factor is a measure of the proportion of available transport capacity being utilised. A full vehicle runs at a high load factor; a vehicle carrying one pallet on a twelve-pallet body runs at a twelfth of its capacity.

Load factor is the quiet lever behind most freight economics and a major one behind transport emissions, because a moving vehicle burns fuel largely whether it is full or not; raising it spreads the same journey's cost, and the same emissions, over more cargo.

Consolidation is the deliberate raising of load factor, in recognisable forms.

1. Full-truckload movement dedicates a whole vehicle to one shipper's load: direct, fast, minimal handling, and the sensible choice where the flow fills the vehicle.

2. Shared part-load movement — less-than-truckload shipping, called groupage in freight forwarding — combines several consignments in one vehicle: cheaper per unit, more handling, longer transit, and normally organised through a hub network for the reasons just given.

3. Scheduled collection routes, of which the milk run in worked example three is the pattern: one vehicle on a fixed loop consolidating small loads from several points into one journey.

The link back to route planning is direct: vehicle capacity decides how many vehicles a day's demand requires and which routings are physically possible; load factor decides whether each chosen routing is economic. A comparison that ignores both compares fantasies — the cheapest quoted option is no bargain if it cannot legally or physically carry the load, and no routing is cheap running at a tenth of its capacity.

=== KEY CONCEPT ===
HEADING: Vehicle routing and delivery schedules
BODY:
Vehicle routing is the process of assigning delivery or collection locations to vehicles and determining their travel sequences. It is route optimisation at the finest grain: not which corridor or mode, but which vehicle visits which stops in which order. Efficient route planning matters because distance, fuel, driving hours, and missed windows are all decided at this grain: a poor sequence adds hours to a day's work without a single road closing, while a well-planned round cuts transport cost and delivery delays with the vehicles the company already owns — one of the few optimisations available every day at almost no capital cost.

Three realities shape every routing plan.

1. Vehicle capacity and stop count. A vehicle can serve only as many stops as its capacity and its working day allow. Overload the round and the plan fails at the third stop; underuse it and the round wastes capacity already paid for.

2. Delivery windows. Customer receiving hours, urban delivery restrictions at certain times, and port or terminal cut-offs carve the day into permitted slots. A sequence that ignores them produces arrivals nobody can receive — and a failed delivery is the most expensive stop of all, its cost paid twice, in the wasted journey and the re-run. A sequence built around windows looks longer on the map and finishes sooner in practice.

3. Sequencing under constraints. Stops are ordered to minimise distance and driving time while respecting windows, vehicle access limits, and load separation requirements. Driving and rest rules bound how far a vehicle and crew may legally travel in a period, which is why some journeys are planned as overnight stops rather than same-day runs.

Done well, routing is where optimisation visibly reduces transport costs and delivery delays: fewer kilometres, fuller vehicles, arrivals inside promised windows, fewer failed deliveries and re-runs. Done as an afterthought at the dispatch desk each morning, it quietly gives back everything the network design saved.

=== KEY CONCEPT ===
HEADING: Backhaul and the cost of running empty
BODY:
A backhaul is a return or subsequent transport movement that may be used to carry additional cargo rather than operating empty. Its opposite is empty running: a vehicle travelling without paying cargo. A truck sent from Accra to Kumasi that returns the same day carrying nothing costs its owner the return journey's fuel, driver time, and vehicle wear, and earns nothing against them; the price of the outbound load quietly carries the empty return inside it.

Empty running is a major cost and emissions inefficiency. The emissions point deserves to stand beside the money: an empty leg produces emissions with no freight to show for them, and reducing empty running counts among the recognised levers of greener transport, beside shifting to less emissive modes and improving load factors.

Why does empty running persist? Flows are unbalanced in space and time: goods move from production regions to consumption regions, and the return direction offers less cargo than the outbound. A network's geography therefore decides how hard backhauls are to find — making backhaul potential itself a network-design consideration.

Planning return loads is a transport-planning discipline, not a stroke of luck.

1. Match return cargo where the flows exist: a distribution run can backhaul supplier collections, empty pallets, or reusable packaging along the same corridor.

2. Trade capacity in both directions: carriers will generally price an outbound lane better where the shipper can offer them return traffic, relieving their own empty-running problem.

3. Accept the second-best backhaul where the perfect one does not exist; a part-load return still beats an empty one on both cost and emissions.

Worked example three shows the milk run as a structural answer to empty legs, and worked example one shows how positioning legs change a route comparison on a cross-border lane.

=== KEY CONCEPT ===
HEADING: Designing the network: the distribution-centre question
BODY:
The central network-design question is deceptively simple: how many distribution centres does the business need, and where should they sit? Beneath it lies the best-established trade-off in network design, and every network decision is a position on that trade-off.

More distribution centres mean each facility sits closer to its customers. Outbound delivery distances fall, delivery becomes faster and response to orders quicker, and the last mile shortens. But each additional facility brings fixed cost — premises, equipment, systems, staff — and, less obviously, it fragments the company's inventory: each site must hold its own buffer against its own local demand, so total stock rises for the same level of protection. A centralised network does the reverse: one pool of stock serves everyone at the lowest total inventory, but delivery distances, transit times, and last-mile costs grow.

The design questions that decide a sound position on the trade-off are the ones this module has assembled.

1. Which markets must be served, and where do they sit? Geography sets the delivery distances any structure must produce.

2. What is the service promise? A next-day promise forces stock close to customers; a slower promise lets a central pool serve widely.

3. What is the demand pattern? The forecast built in Lesson 13.1 tells the planner where volume concentrates and how it varies — the raw material of the fragmentation calculation in worked example four.

Network design also extends to how products travel through the structure. Postponement — keeping the product generic and deferring final configuration, such as labelling or final packing, until real demand is known — can matter as much as facility count where demand is uncertain and varied, because it lets one central stock serve many possible endings.

The headline: more distribution centres buy service with inventory and fixed cost; fewer buy inventory efficiency with distance and time. Neither pole is correct; the service promise and the demand pattern decide the price worth paying.

=== KEY CONCEPT ===
HEADING: Digital mapping and optimisation software in transportation planning
BODY:
None of this lesson's comparisons are new; software changes the scale at which they can be made and remade. Digital mapping supplies the geography — road networks, distances, travel times, access restrictions — that turns which way into a computable question. On that geography sit two families of tools.

1. Routing and scheduling tools work on the vehicle-routing problem family described earlier: given stops, quantities, windows, capacities, and driving-time limits, they propose vehicle assignments and stop sequences, and re-propose them when an order arrives or a window changes. Around those plans, a transport management system — the software class that plans and executes transport — typically adds carrier selection and rating, tendering, track-and-trace, and freight audit and settlement.

2. Network design tools take the longer view: given demand by region, facility costs, and transport rates, they compare candidate structures — two distribution centres against three, this region served from here or there — on total cost and service before capital is committed.

Two cautions belong in the same breath as the capability. First, these tools do not remove judgement; they rank options by the inputs given, and the next block takes up what happens when the inputs are wrong. Second, published claims about the savings such tools deliver are vendor-dependent and cannot be treated as facts; what can be taught is what the tools do — compute, compare, and re-compare at a scale and speed no manual planner can match, so that re-planning becomes cheap enough to do routinely rather than rarely. The professional standard is to know what question each tool answers and what data it needs. Such a tool earns its keep as a fast, consistent calculator of comparisons the planner defines — never as the planner's replacement.

=== KEY CONCEPT ===
HEADING: The honesty of optimisation: models rank the inputs they are given
BODY:
Optimisation, whether performed in software or on the back of two quotations, has one non-negotiable property: it ranks options by the inputs given. Change the inputs and the ranking changes. The computing phrase for the failure mode is garbage in, garbage out: a model fed optimistic transit times, incomplete handling costs, and last year's fuel prices confidently returns an answer that is precisely wrong.

Three disciplines keep optimisation honest.

1. Feed it the whole cost. Service and risk are part of cost. A cheap fragile route is not cheap: the routing that saves money on linehaul but adds two handling touches carries damage and delay risk that belongs inside the comparison, as worked example one demonstrates. Reliability belongs in the cost figure too: the buffers a company holds against an unpredictable lane are real money spent because of that lane.

2. Optimise the total system, not the silo. Lesson 10.1's total-cost lens, applied at network scale, is the discipline here: the cheapest transport option is frequently the most expensive supply chain decision, because slow and unreliable transport raises inventory, expediting, and stockout costs elsewhere in the operation. The question is never only whether a leg is cheap, but what the choice costs the whole system.

3. Respect the model's simplifications. Every network model compares a simplified world: average demands, average rates, the scenarios someone chose to run. The output is a structured comparison of assumptions, not a prophecy. Read it by asking which assumption, if wrong, would most change the answer.

Held together, the three disciplines give optimisation its proper role: a rigorous, repeatable way to compare options the planner has framed well, with the planner — not the algorithm — accountable for the framing. That is the advanced standard this lesson sets: optimise deliberately, feed the comparison honestly, and judge the outputs as a professional judges any calculation.

=== WORKED EXAMPLE ===
HEADING: Choosing between two routings: a recurring Kumasi to Ouagadougou consignment
BODY:
A Ghanaian distributor of beverages and household goods ships a recurring weekly consignment — 24 pallets — from its Kumasi warehouse to a buyer in Ouagadougou, Burkina Faso. The buyer receives goods only within an agreed weekly delivery window. Two routings are on the table. All figures in this example are illustrative for teaching purposes.

Step 1: Describe the options.
Option A runs north from Kumasi on Ghana's paved axis toward the northern border crossing with Burkina Faso, then on to Ouagadougou. It crosses one international border, moves sealed under the regional transit arrangement met in Lesson 12.1 — one document, no reloading en route — and carries an all-in door-to-door quote of GHS 40,000. Typical transit is three days, and the trip record shows the delivery window missed once in the last ten trips.
Option B runs south-east to the coast, crosses at the coastal border into Togo, and runs north on the paved axis linking Lomé with Ouagadougou. It crosses two international borders and adds one intermediate handling: at a Togo terminal the consignment is transferred between carriers. Its quoted price is GHS 37,500. Typical transit is four days when both borders move well, six when they do not, and the delivery window has been missed on about half the trips.

Step 2: Price the differences.
The second border and the coastal detour add, on average, two extra driver-and-vehicle days per trip, at an illustrative GHS 1,500 per day: GHS 3,000. The terminal transfer adds a handling touch, with its damage and delay risk. Missed windows trigger an average penalty of GHS 6,000 per miss in discounts, waiting, and storage. Option A expects 0.1 x 6,000 = GHS 600 per trip; Option B expects 0.5 x 6,000 = GHS 3,000.

Step 3: Compare door to door.
Option A: 40,000 + 600 = GHS 40,600, reliably. Option B: 37,500 + 3,000 + 3,000 = GHS 43,500, variably. The lower quote is GHS 2,900 per trip dearer in practice — and less predictable besides, forcing the buyer to hold buffer stock against the bad case.

What does this example demonstrate?
The linehaul quote was one line of a seven-line comparison. The borders, the extra touch, the reliability record, and the delivery window decided the result, as the route-comparison inputs predict.

Key lesson
Compare routings door to door, on total expected cost including waiting, handling, and missed windows, weighted by the buyer's tolerance for unreliability. Different numbers could reverse the result: cheaper coastal rates and a dependable second border could make Option B win. The method, not this answer, is the lesson.

=== WORKED EXAMPLE ===
HEADING: Hub-and-spoke versus point-to-point: the arithmetic of five towns
BODY:
A European distributor operates a national distribution centre at Rotterdam and serves five regional towns. Flows between the towns are scattered: each pair exchanges, on average, one-fifth of a truckload per day. Management asks whether the towns should be linked by direct lines or through a regional hub. All figures in this example are illustrative for teaching purposes.

Step 1: Count the direct option.
Connecting every pair of towns by a direct line needs one route per pair: five towns, each paired with four others, counted once, give 5 x 4 / 2 = 10 routes. Each route carries only its own pair's one-fifth of a load, so every direct vehicle runs at roughly a 20 percent load factor. Ten mostly empty vehicles, ten mostly empty return legs, with the cost and emissions of both.

Step 2: Count the hub option.
Insert a hub between the towns. Each town now has a single spoke to the hub. Each spoke carries the town's combined traffic with the other four towns: 4 x one-fifth = four-fifths of a load inbound toward the hub, and the same outbound from it. Connections fall from 10 routes to 5 spokes, and each spoke movement runs at roughly an 80 percent load factor instead of 20. The price: every inter-town consignment now travels two legs, is handled at the hub, and waits for the outbound departure, while the hub facility itself costs money to run.

Step 3: Find where each wins.
For the scattered flows the hub wins clearly — half the connections, four times the load factor, fuller vehicles, lower cost per unit carried. This is the arithmetic behind part-load networks, and why such carriers typically run hub-and-spoke terminal networks. But suppose two of the towns, an hour apart, begin exchanging two full truckloads every day. Hubbing that flow turns the two daily full loads into four spoke movements and adds two hub handlings per load to cargo that could travel direct, full, in one leg. The dense lane justifies its own direct line, and the hub keeps serving the thin flows around it.

What does this example demonstrate?
The arithmetic behind structure choice: count the flows. Many small flows between many points favour a hub-and-spoke network; dense, regular flows between a pair favour direct delivery. Volume per route, not preference, decides.

Key lesson
Direct delivery and hub-and-spoke are answers to different flow patterns; durable networks are hybrid, each lane running on the structure its volume supports, reviewed as volumes change.

=== WORKED EXAMPLE ===
HEADING: The milk-run: one loop replaces four collection trips
BODY:
A fruit-juice packer in Tema receives packaging materials daily from four suppliers around the industrial area — cartons, bottles, labels, and film — each supplier dispatching four pallets a day to the factory. All figures in this example are illustrative for teaching purposes.

Step 1: Describe the old arrangement.
The factory booked four dedicated collections a day. Each collection used a 12-pallet truck to carry 4 pallets — a one-third load factor — and each truck returned to its base empty. Four trips, four collection charges, and two-thirds of the capacity paid for sitting idle. The average charge was GHS 1,800 per collection: 4 x 1,800 = GHS 7,200 a day. Arrival times varied with each carrier's day, so the warehouse could not plan receiving staff around them, and late collections pushed the packing schedule back.

Step 2: Design the loop.
The packer moved the collections onto a milk run: one vehicle on a fixed, repeated circular route with multiple pickup stops. A single 16-pallet vehicle now runs a published loop each morning, visiting the four suppliers in a fixed sequence, collecting 16 pallets, and returning full. Load factor: 16 / 16 = 100 percent. One trip replaces four, and four empty return legs collapse into one loaded return. The loop contract costs GHS 3,500 a day (illustrative), a saving of GHS 3,700 a day over the four dedicated collections — and because the loop runs to a fixed timetable, material arrivals become predictable, which the packing line had never had.

Step 3: Build in the constraints that make it work.
The loop functions only because three disciplines hold. First, each supplier prepares its four pallets inside a fixed pickup window, so the vehicle never waits and the sequence never slips. Second, the total load of 16 pallets sits within the vehicle's capacity, and the full loop fits inside the driver's permitted working day. Third, because one vehicle carries four supply lines, the packer holds a contingency — a backup vehicle agreement and a rule to resequence or split the loop when the truck fails — so one breakdown cannot stop four production inputs at once.

What does this example demonstrate?
The milk run consolidates small loads into one scheduled route: fewer trips, higher load factor, lower cost, and more predictable arrivals than the ad hoc collections it replaced — consolidation, capacity planning, and scheduling in a single design.

Key lesson
Fixed loops trade flexibility for cost and reliability. They work when pickup windows are honoured, the load fits the vehicle, and a contingency exists for the loop's single point of failure.

=== WORKED EXAMPLE ===
HEADING: One warehouse or two: the distribution-centre question
BODY:
A pharmaceutical distributor in Accra supplies pharmacies and hospitals across Ghana from one national warehouse. Northern customers around Tamale are replenished by long road journeys from Accra, with lead times of days, and the service promise in the north is slipping as sales grow. The board considers a second distribution centre in Kumasi. All figures in this example are illustrative for teaching purposes.

Step 1: Quantify the stock effect.
Today the single warehouse holds a national buffer of 6,000 units of the fast-moving lines (illustrative). Two sites do not hold 3,000 each for the same protection. Each site must carry its own buffer against its own region's uncertain demand, even when the other region is quiet. The planner estimates 4,200 units in Accra plus 3,000 in Kumasi — 7,200 where one pool held 6,000, roughly a fifth more — and the two sites also hold separate working stock, so total inventory rises further (illustrative). This is inventory fragmentation: splitting one pool into sites multiplies the buffers, as the network-design trade-off predicts.

Step 2: Quantify the service effect.
From Kumasi, replenishments to the north shorten by roughly a day's drive; Kumasi-area customers move to same-day collection and delivery; and Tamale's lead time falls materially. Outbound transport cost per unit falls with the shorter distance. The second site also adds resilience: a disruption at either site no longer strands the whole country's supply.

Step 3: Weigh the trade-off.
Against the service gains stand the second facility's fixed costs — premises, staff, systems, management attention — and the extra fifth of inventory with its carrying cost. The decision turns on this lesson's questions. What service promise does the business actually sell — can northern customers be served in full and on time from Accra at all? What does Lesson 13.1's demand forecast show — is northern volume large and growing enough to feed a distribution centre? And what do the transport rates between the sites allow? If northern demand were thin and slow-moving, the same money might serve better as a scheduled delivery service from the central warehouse.

What does this example demonstrate?
More distribution centres buy service, shorter last-mile distance, and resilience — paid for in fixed cost and fragmented, larger total stock. Fewer buy inventory efficiency — paid for in distance and time. The right count follows the service promise and the demand pattern, not the real estate available.

Key lesson
Network design is a cost-versus-service decision made with demand data. Every added facility must be paid for in stock and fixed cost, and justified in service; the demand forecast, not the building catalogue, decides.

=== IMPORTANT NOTE ===
HEADING: Design the network first, then run routes within it
BODY:
The order of operations in this lesson is not stylistic; it is the difference between planning and firefighting. The service promise and the demand pattern should set the network — where stock sits, where hubs sit, which lanes run direct — and daily routes then run within that structure. A network is chosen for the shipments of coming years; a route for this week's consignment. When the order reverses, the symptoms are recognisable: stock regularly expedited from the wrong region to the right one; a hub used because it exists rather than because the flows justify it; direct runs invented overnight for lanes the structure cannot serve. Each rescue looks like dedication, and each is a signal that the daily routing is being asked to compensate for a network that no longer fits the flows inside it. This is how firefighting becomes institutionalised: permanently staffed by the operation's best people, who spend their skill rescuing deliveries instead of improving the system. The professional response is to treat recurring exceptions as network data — escalate the pattern into the network review, fix the structure, and let the routes run quietly inside it.

=== IMPORTANT NOTE ===
HEADING: Empty legs are real money and real emissions
BODY:
Every comparison in this lesson assumes vehicles earn their keep by carrying cargo. The empty leg breaks that assumption silently: it appears on no consignment file and carries no document, yet burns fuel, driver hours, and vehicle life at the full rate — and produces emissions with no freight to show for them. Backhaul planning is the discipline of making the return leg earn. Three habits cover most of it. Check the return direction before committing to any lane: what physically moves back, and how much of it is ours to carry — supplier collections, empty pallets, reusable packaging, equipment repositioning? Build structural answers where flows repeat: the milk run of worked example three, reciprocal arrangements with partners trading in both directions, and network structures that end the vehicle's day where its next load begins. And price the empty leg honestly in route comparisons: a routing whose vehicles travel far empty to reach their loading point is dearer than its linehaul quote suggests, which is why door-to-door comparisons include positioning legs. An empty kilometre is pure cost and pure emissions; planning it away is among the cheapest improvements a transport operation can make.

=== IMPORTANT NOTE ===
HEADING: A network designed for last year's demand is this year's constraint
BODY:
Network decisions are investments, and investments age. Demand shifts — Lesson 13.1 showed how far demand moves with seasons, trends, and events. Costs shift: fuel, haulage rates, wages, facility costs. Borders and corridors shift: Lesson 12.1 showed how procedures and infrastructure change the economics of whole regions. A structure that fitted the flows of three years ago can misfit today's: stock pooled where demand has thinned; a hub sitting on a lane that has grown dense enough to deserve direct lines; delivery radii stretched by customers the original design never imagined. The professional response is scheduled review, not crisis response. Watch the triggers: regional demand diverging materially from the pattern the network was designed around; transport or facility costs shifting the balance of the cost-versus-service trade-off; service performance degrading on particular lanes; border, corridor, or regulatory changes altering regional economics. Any one argues for re-running the network comparison with current data and with this lesson's total-cost honesty. Put the review triggers in the calendar as a matter of routine, the way audits are scheduled. Unexamined, a network does not stay neutral; it silently becomes the constraint the whole operation plans around.

=== MCQ 1 ===
QUESTION:
A planner must choose a routing for a recurring weekly consignment from Kumasi to a buyer in Ouagadougou. Routing A quotes GHS 40,000 door to door, crosses one border, and has arrived inside the buyer's delivery window in nine of the last ten trips. Routing B quotes GHS 37,500, crosses two borders, requires an intermediate transfer to a second carrier, and has missed the delivery window on about half its trips, with each miss triggering discount, waiting, and storage costs.

Which option best describes a sound choice?
POINTS: 1
OPTIONS:
1. Choose Routing B, because the lower quoted price is the only figure that actually appears in the transport budget.
2. Choose Routing A if its total expected door-to-door cost, including border waiting, handling risk, and the expected cost of missed windows, is lower, because reliability and handling are part of the route's real cost.
3. Choose Routing B, because a routing with more border crossings always offers better regional coverage and therefore better service.
4. Split the weekly consignment between both routings so that at least half of each shipment is guaranteed to arrive on time.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

The lesson's central discipline is to compare routings door to door on total expected cost, with reliability and handling inside the comparison rather than outside it. Routing B's GHS 2,500 price advantage is only one line of the comparison. Its second border adds waiting days, its intermediate transfer adds a handling touch with damage and delay risk, and a window missed on roughly half the trips reliably triggers discount, waiting, and storage costs. Adding those lines, as worked example one did with similar numbers, routinely reverses a quote-based choice — and even where the totals came out level, the unpredictable routing would force the buyer to hold buffer stock against the bad case, a cost Answer 1 never counts.

Answer 3 invents a service benefit of extra borders that the lesson dismantled: every border is friction, waiting, and another document, not a feature. Answer 4 sounds cautious but is operationally incoherent: splitting a consignment across two arrival patterns means part of every shipment misses the window while both cost structures are paid in full.

The takeaway: the cheapest quote is a claim; the cheapest route is a total, and the total includes time, touches, and reliability.

=== MCQ 2 ===
QUESTION:
A distributor serves six regional towns through a central hub. Flows between the towns are small and scattered, but one pair of towns an hour apart now exchanges two full truckloads of goods every day — all of it travelling into the hub, being unloaded and reloaded, and travelling back out to its destination.

Which statement best describes the sound network adjustment?
POINTS: 1
OPTIONS:
1. Route the dense lane's cargo direct between the two towns, while the hub continues to serve the thin, scattered flows that consolidate well.
2. Keep the dense lane on the hub, because moving all flows through one place is always the cheapest arrangement regardless of volume.
3. Close the hub entirely and switch every flow to direct lines, because the dense lane has proved that direct delivery is always the superior structure.
4. Divide every consignment on the dense lane in half, so that the hub and a new direct line each carry part of the flow.
CORRECT: 1
EXPLANATION:
The correct answer is Answer 1.

Structure follows flow. Thin, scattered flows between many towns consolidate efficiently through a hub — that is why the hub earned its place, and worked example two showed the arithmetic. But a dense lane filling two complete trucks a day needs no consolidation: hubbing that cargo buys the worst of both structures, two spoke movements plus double handling where one full direct leg would do. The working pattern is hybrid — direct lines where flows are dense, hub-and-spoke where they are thin — with each lane reviewed as volumes change.

Answer 2 states the hub-always fallacy that the arithmetic disproves: a hub creates value by consolidating small flows into full vehicles, and a full load cannot be consolidated further, only detoured, delayed, and handled. Answer 3 overcorrects in the opposite direction; the other towns' thin flows still need the hub to fill their vehicles, and abandoning it would multiply part-load journeys. Answer 4 splits the flow for no operational reason, adding hub handling to half the cargo while paying for a direct line anyway.

The takeaway: review lanes by their actual flows and give each lane the structure its volume supports.

=== MCQ 3 ===
QUESTION:
To shorten deliveries, a company replaces its single national warehouse with four regional distribution centres. A year later, total inventory is higher, some regions hold slow-moving stock while others stock out, and facility costs have risen.

Which option best explains what happened?
POINTS: 1
OPTIONS:
1. The company's demand forecasts must have been wrong, because the number of warehouses has no effect on inventory levels.
2. Fragmenting the network multiplied the buffers: each regional centre holds its own stock against its own region's demand, so total stock and fixed costs rise even as delivery distances fall — the cost-versus-service trade-off that network design must weigh.
3. The regional centres are simply being managed badly, and centralising all inventory again would restore the previous performance without any other change.
4. The stockouts prove that regional distribution centres cannot work anywhere, and every network must remain fully centralised.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.

This is the cost-versus-service trade-off of network design working exactly as the model predicts. More distribution centres shorten delivery distances and speed up response, but each added site fragments the company's inventory: every regional centre must hold its own buffer against its own region's uncertain demand, so the same nationwide protection now requires more total stock. Fragmented buffers also explain the mixed symptoms — regions holding slow stock while others stock out — because stock in one region cannot serve demand in another. Fixed costs rise with the site count, since premises, staff, and systems come in sets.

Answer 1 is wrong on the mechanism: forecast quality matters, but the inventory rise is structural and would appear at any level of forecast accuracy. Answers 3 and 4 commit the mirror-image error the lesson warns against — treating one pole of the trade-off as universally correct. Centralising everything would cut inventory and fixed cost while lengthening every delivery; neither pole is correct. The design questions — the service promise, the market geography, the demand pattern — decide how many facilities the business should carry.

The takeaway: network structure sets inventory and cost behaviour, so change it only with the trade-off in view.

=== FACTS & SOURCES ===
- Definitions of Route Optimisation, Logistics Network, Distribution Network, Direct Delivery, Hub-and-Spoke Network, Vehicle Routing, Vehicle Capacity, Load Factor, Delivery Window, Route Constraint, Network Optimisation, Transportation Planning, Backhaul, and Last-Mile Delivery follow the lesson brief's key terms, defined at first use and used naturally in the blocks. — source: curriculum/lesson_briefs/module-13/lesson-13.2.md key terms.
- Route planning as sequencing stops to minimise distance/time/fuel under capacity, time-window, and driver-hours constraints (the vehicle-routing problem family); constraints taught in Key Concept on routing. — source: research sheet logistics-scm-frameworks.md section 6.
- Cost trade-off between transport and inventory (slower cheaper modes raise inventory and stockout costs; total-cost principle); taught as the total-system discipline. — source: research sheet logistics-scm-frameworks.md section 6.
- Consolidation concepts: FTL dedicates a vehicle to one shipper (faster, direct, less handling); LTL combines several shippers' freight in one vehicle (cheaper per unit, more handling, longer transit); groupage is the consolidation term in freight forwarding; LTL carriers typically run hub-and-spoke terminal networks. — source: research sheet logistics-scm-frameworks.md section 6.
- Milk run: fixed, repeated circular route with multiple pickup/drop-off stops, consolidating small loads. — source: research sheet logistics-scm-frameworks.md section 6.
- Hub-and-spoke consolidates flows through central hubs (fewer connections, longer transit) versus point-to-point (faster, needs volume per pair): standard network-design convention. — source: research sheet logistics-scm-frameworks.md section 6.
- Multimodal (at least two modes, single contract, one operator responsible end to end) versus intermodal (goods in one and the same loading unit across modes, often separate contracts): taught per the sheet's distinction; no claim that intermodal means single contract. — source: research sheet logistics-scm-frameworks.md section 6 and DO NOT CLAIM item 2.
- Empty running (travelling without paying cargo) is a major cost and emissions inefficiency, cut via backhaul matching and network design; backhaul is the return leg. Taught qualitatively; no percentages claimed. — source: research sheet logistics-scm-frameworks.md section 6 and DO NOT CLAIM list.
- Load-factor improvement and empty-run reduction as recognised emissions levers; capacity utilisation as a core efficiency lever for cost and emissions; a moving vehicle burns fuel regardless of fullness (qualitative). — source: research sheet logistics-scm-frameworks.md sections 6, 7, and 12.
- Network design: number/location of distribution centres is a cost-versus-service trade-off — more/deeper networks cut delivery time and outbound transport but add facility and inventory cost; centralised networks do the reverse; inventory fragmentation (each site holding its own buffer) taught from this trade-off. — source: research sheet logistics-scm-frameworks.md section 8.
- Postponement (delayed differentiation): keep the product generic and defer final configuration until real demand is known; suited to high demand uncertainty. — source: research sheet logistics-scm-frameworks.md section 8.
- Cross-docking: goods move from receiving dock to shipping dock with little or no storage. — source: research sheet logistics-scm-frameworks.md section 4.
- TMS scope: plans and executes transport — mode/route selection, carrier selection and rating, tendering, tracking, freight audit/settlement. No vendor names, no ROI or savings percentages anywhere in the lesson. — source: research sheet logistics-scm-frameworks.md section 9 and DO NOT CLAIM item 10.
- Routing/scheduling software and network-design tools taught as computing and comparing options on the inputs given (garbage in, garbage out); software claims limited to functions. — source: research sheet logistics-scm-frameworks.md sections 6 and 9.
- Resilience via alternative sites/structures (a second distribution centre adding resilience) taught as a concept. — source: research sheet logistics-scm-frameworks.md section 11 (resilience strategies).
- Geography of worked example one: Ouagadougou is connected by paved highways to Accra and to Lomé (paved Accra–Ouagadougou axis exists); Burkina Faso is landlocked and reaches the sea through coastal neighbours' gateways. Border crossings are described generically ("the northern border crossing with Burkina Faso", "the coastal border into Togo"): Aflao, Paga, and Elubo are marked Not Verified as named border posts in the research sheet, so no border post is named anywhere in the lesson. — source: research sheet ghana-trade-customs.md section 8 including its Not Verified note; consistent with the draft of lesson 12.1.
- The West African regional road transit arrangement (one document, seal, guarantee; sealed loads not reloading en route) is referenced only as "the regional transit arrangement met in Lesson 12.1" with no operational specifics re-taught. — source: research sheet trade-transport-standards.md section 12; draft lesson-12.1.
- Vehicle weight limits and weighbridges taught generically as the legal side of vehicle capacity; no country-specific limits stated. — source: general business knowledge; corridor control points per draft lesson-12.1, WRITING_SPEC.md rule 5.6.
- All figures in all four worked examples (quotes, penalties, pallet counts, load factors, buffer stocks, daily costs) are round illustrative teaching numbers, labelled as such in each example; no duty rates, fees, or statutory periods are stated anywhere. — source: WRITING_SPEC.md rule 5.1.
- Cross-references by name and number, no re-teaching: Lesson 3.2 Modes of Transport: Sea, Air, Road, Rail, and Multimodal (mode choice, multimodal/intermodal); Lesson 3.3 Cargo Types, Packaging, and Handling (handling risk); Lesson 5.3 Shipping Instructions and Cargo Consolidation (consolidation); Lesson 7.4 Shipping Charges, Freight Rates, and Surcharges (charge-build scope); Lesson 9.2 (inland depots); Lesson 10.1 Components of Total Logistics Cost (total-cost lens); Lesson 12.1 International Transport Corridors (border friction, corridors, transit); Lesson 13.1 Demand Forecasting and Supply Planning (previous lesson, demand pattern); Lesson 13.3 Inventory Optimisation and Service Levels (next lesson, forward reference). — source: WRITING_SPEC.md section 7; lesson briefs for modules 3, 5, 7, 9, 10, 12, and 13.
