# ERRATA — Module 1 fact-check (lessons 1.2, 1.3, 1.4, assessment-module-01)

Fact-check run 2026-10-22 against `curriculum/research/logistics-scm-frameworks.md`,
`curriculum/research/trade-transport-standards.md`, `curriculum/research/ghana-trade-customs.md`,
`curriculum/WRITING_SPEC.md` (rules 5–6, section 11), and the production reference
`curriculum/reference/lesson-1.1-complete.md` (read-only, untouched).

No WebSearch verification was needed: every checked claim about named concepts
(CSCMP definitions, 7 Rs and their variants, 3PL/4PL, freight forwarder, customs
broker/clearing agent, milk run, bullwhip amplification, cold chain, five rights
of purchasing) is covered by the research sheets (verified live 2026-10), and
every remaining claim is uncontentious general business knowledge. No duty
rates, statistics, dates, or institutional claims appear anywhere in the four
files.

## CHANGES MADE (6)

### lesson-1.2.md

1. Key Concept "The relationship between logistics and supply chain management",
   first sentence.
   - Before: "The previous lesson defined logistics as the planning,
     implementation, and control of the movement and storage of goods, together
     with the related information, from a point of origin to a point of
     consumption, in order to meet customers' requirements."
   - After: "The previous lesson defined logistics as the planning,
     implementation, coordination, and control of the movement and storage of
     goods, together with the related information and resources, from a point
     of origin to a point of consumption or use."
   - Reason: the sentence misquotes lesson 1.1, which is in production and
     defines logistics with "coordination" and "resources" and ends "consumption
     or use"; the dropped-in CSCMP tail ("in order to meet customers'
     requirements") belongs to the next sentence's paraphrase, not to 1.1. The
     assessment's Q1 explanation already quotes the 1.1 wording, so the module
     is now internally consistent.

2. Key Concept "How logistics and supply chain management complement each
   other", final sentence.
   - Before: "The next lesson turns to the standards by which logistics work is
     judged: the seven rights of logistics."
   - After: "...turns to the criteria by which logistics work is judged..."
   - Reason: lesson 1.3's Important Note explicitly teaches that the seven
     rights are "a professional convention rather than an official standard";
     calling them "standards" set up a direct contradiction one lesson later.

3. Important Note "Goods also move back up the chain", closing sentence.
   - Before: "Reverse logistics receives fuller treatment in later modules; ..."
   - After: "Reverse logistics receives fuller treatment later in this course; ..."
   - Reason: the fuller treatment is lesson 1.4, in this same module; "later
     modules" is factually wrong about the curriculum's own structure.

### lesson-1.3.md

4. Worked Example "Walking a Rice Delivery Through the Seven Rights", first
   paragraph.
   - Added: "All figures in this example are illustrative for teaching
     purposes."
   - Reason: this was the only one of the nine worked examples across the three
     lessons whose body carried concrete quantities (400 bags) without the
     illustrative-figures label; all its siblings carry one. Cheap consistency
     fix, no visual or copy impact beyond the label sentence.

5. FACTS & SOURCES, Tema/Tamale bullet.
   - Before: "...connected by the national road network; no distances or journey
     times are stated — general geographical knowledge."
   - After: "...connected by the national road network; only an approximate
     distance (several hundred kilometres) is stated, and no journey times are
     given — general geographical knowledge."
   - Reason: the bullet was inaccurate about its own text — the rice example
     states "several hundred kilometres". (The claim itself is true: the Tema
     to Tamale road distance is on the order of 600 km.) Body text unchanged.

### lesson-1.4.md

6. Two recap lists of the seven rights, in the Key Concept "Outbound Logistics:
   Definition and Purpose" and the Important Note "Reverse Logistics Is Planned,
   Not a Failure".
   - Before: "...to the right customer, at the right price." (both places)
   - After: "...to the right customer, at the right cost." (both places)
   - Reason: lesson 1.3 fixes the course's canonical list as "product, quantity,
     condition, place, time, customer, and cost" and states "Within this course,
     one list is used consistently"; the assessment (Q9 option 4) uses the same.
     Lesson 1.4 was the only file still using the "right price" variant in the
     course-list position. (Mentions *about* the "right price" variant, as a
     variant, in 1.3 and the assessment, are correct and untouched.)

## ITEMS REVIEWED AND DECLINED (no change)

1. Lesson 1.2 has no title line before the first marker, while 1.3 and 1.4 open
   with a "DRAFT — ..." line. Cosmetic only; WRITING_SPEC.md does not require a
   title line, and lesson 1.1 was evidently entered without one. Owner's call.

2. Lesson 1.2's `=== PROPOSED KEY TERMS ===` section sits after
   `=== FACTS & SOURCES ===`. Spec section 1 says drafts "end with the FACTS &
   SOURCES section" but section 8 calls PROPOSED KEY TERMS the "final section";
   the two rules conflict and the current layout follows section 8. Left
   as-is; flag for the owner in case Theory Builder entry order matters.

3. Lesson 1.2 presents four direction-based categories (inbound, outbound,
   internal, reverse); lesson 1.4 presents three directions (inbound, outbound,
   reverse) plus 3PL, and never mentions "internal logistics". Not a
   contradiction — 1.2's internal logistics is movement within one premises,
   which is not a direction relative to suppliers or customers — but the owner
   may wish to harmonise the taxonomies across the two lessons.

4. Assessment Q8 (fresh fish, hotel): the scenario says the supplier "delivers
   60 boxes" but never states the ordered quantity, while the explanation
   asserts "the quantity ordered was the quantity delivered" to dismiss option
   3. The natural reading (full order delivered) supports it, so I left it; if
   the owner wants it airtight, add "the full order of 60 boxes" to the
   question stem.

5. Lesson 1.2's CSCMP-based paraphrase of logistics management omits
   "effective" and "forward and reverse" from the sheet's wording. This is a
   safe simplification: the dedicated Important Note on reverse flows carries
   the forward-and-reverse point explicitly, and the FACTS & SOURCES entry
   quotes the definition in full. No change.

6. Real place names (Accra, Tema, Kumasi, Takoradi, Tamale, Wa, Koforidua,
   Rotterdam, Shenzhen, Mumbai, Dubai) are all used generically and are within
   the spec's approved example locations; no real company is named anywhere
   (Adampa Provisions Ltd, Adjoa's Provisions and similar are fictional).
   Confirmed compliant; no change.

## VERDICT

PASS-WITH-CHANGES. Marker syntax, block counts (1.2: 10 KC + 3 WE + 3 IN + 3
MCQ; 1.3: 11 + 3 + 3 + 3; 1.4: 10 + 4 + 3 + 3), POINTS: 1, four options,
CORRECT/explanation-opener pairings, British spelling, no markdown in bodies,
the assessment's 12-question coverage map, and the lesson 1.2 PROPOSED KEY
TERMS exception all verified compliant. All factual content is sheet-backed or
uncontentious general knowledge; the six fixes above are consistency and
labelling corrections only, no thematic or copy impact beyond the quoted
sentences (the lesson 1.2 definition sentence should be checked by Bernard
against the theme/copy lock, though it aligns the draft with the already-
approved lesson 1.1 text rather than introducing new copy).
