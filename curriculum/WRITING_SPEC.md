# Curriculum Writing Specification

This is the binding contract for every lesson draft in `curriculum/drafts/`.
Every drafting agent must read this file, the lesson's brief file, and the
relevant research sheets BEFORE writing. The project owner (Bernard) will
enter approved content into his Theory Builder by hand, so the draft must be
exact, complete, and format-faithful.

## 1. Files and format

- One markdown draft per lesson: `curriculum/drafts/module-NN/lesson-N.M.md`
- UTF-8, plain text in bodies. NO markdown syntax inside bodies (no `#`,
  `**`, backticks, links). The Theory Builder stores plain text; writers
  produce paragraphs, numbered sub-points (`1. Planning`), and dashes for
  lists — exactly the style of lesson 1.1.
- Block markers (one per line, exactly this shape, blank lines around them):

```
=== KEY CONCEPT ===
HEADING: Understanding Logistics in Everyday Life
BODY:
...paragraph text...

=== WORKED EXAMPLE ===
HEADING: ...
BODY:
...

=== IMPORTANT NOTE ===
HEADING: ...
BODY:
...

=== MCQ 1 ===
QUESTION:
A distributor has 200 bags of cement ready for delivery...
POINTS: 1
OPTIONS:
1. First option text.
2. Second option text.
3. Third option text.
4. Fourth option text.
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.
...why it is correct, why the main distractors fail, closing takeaway...

=== FACTS & SOURCES ===
- <factual claim used in the lesson> — <source: research sheet section / verified URL / general business knowledge>
```

- End every draft with the FACTS & SOURCES section. Any claim that is not
  general business knowledge must be listed there.

## 2. How the lesson renders (write blocks accordingly)

The learner experiences fixed sections in this order: Objectives → all Key
Concept blocks → all Worked Example blocks → all Important Note blocks → the
Practice multiple-choice questions. Blocks of the same type are read one at a
time in order. Therefore:

- Each Key Concept must stand on its own as a teaching beat.
- Worked Examples come after the concepts; refer to concepts by name ("the
  definition of logistics introduced earlier"), never by block position.
- Important Notes are read near the end; use them for misconceptions,
  distinctions, warnings, and exceptions that consolidate the lesson.
- The `order` you list blocks in controls reading order WITHIN each type.

## 3. Content requirements per lesson

- 14–17 teaching blocks: 9–12 Key Concepts, 3–4 Worked Examples, 2–3
  Important Notes. Plus exactly 3 MCQs. (Lesson 1.1 has 16 blocks + 3 MCQs —
  that is the calibration.)
- Key Concept body: 150–400 words. Worked Example: 200–450 words. Important
  Note: 150–300 words. Lesson total (blocks only): 4,000–5,500 words.
- Cover EVERY learning objective in the brief. Every key term in the brief
  must be taught in the body (defined at first use and used naturally).
- Follow the brief's summary as the promise of the lesson. Do not rewrite
  titles, summaries, or objectives.
- Professional training-textbook voice: complete sentences, concrete
  operational detail, no filler. Progress from familiar to complex.
- Difficulty ladder: Modules 1–3 beginner (start from everyday experience,
  define everything); 4–6 beginner-to-intermediate; 7–9 intermediate
  (operational and terminal detail); 10–12 intermediate-to-advanced
  (costing arithmetic, risk allocation); 13–15 advanced (assume all prior
  lessons; strategy, optimisation, technology).
- Use numbered sub-points with a leading term where lesson 1.1 did
  (e.g. `1. Transportation` then explanation paragraphs).

## 4. Examples and relatability

- At least one Worked Example per lesson set in Ghana (Accra, Tema, Kumasi,
  Takoradi, Tamale, Cape Coast, Tema Port, Kotoka International Airport,
  Aflao/Paga/Elubo borders; goods such as cocoa, cement, frozen fish, shea
  butter, timber, pharmaceuticals, FMCG, machinery).
- At least one international, non-Ghana example per lesson (Rotterdam,
  Singapore, Hamburg, Shenzhen, Dubai, Mumbai, Antwerp) — this is an
  international curriculum anchored in Ghana, not a Ghana-only text.
- Worked Examples are step-by-step (Step 1, Step 2 ...) with concrete
  quantities and routes, then close with "What does this example
  demonstrate?" and a short "Key lesson" or "Lessons from the example"
  takeaway, matching the lesson 1.1 pattern.
- Companies in examples are generic or clearly illustrative ("a
  pharmaceutical distributor in Accra", "Kwabena Trading Ltd"). Never attach
  factual claims (contracts, volumes, capabilities) to real named companies.

## 5. Fact-safety rules (highest priority — no hallucination)

1. NEVER state specific duty rates, tax percentages, levies, fee amounts,
   statutory deadlines, or free-time periods as fact. Where a calculation
   needs numbers, use round illustrative figures and state: "All figures in
   this example are illustrative for teaching purposes."
2. Institutional facts (which organisation operates or regulates what) may
   be used ONLY from `curriculum/research/*.md` fact sheets. If a claim is
   not in a fact sheet and you cannot verify it with WebSearch from an
   authoritative source (official site, port authority, revenue authority,
   WCO, IATA, ICC), write around it — describe the function generically
   without naming an organisation.
3. Named Ghanaian systems (ICUMS, the Ghana National Single Window) are
   mentioned only where pedagogically needed and only as described in the
   research sheets.
4. Incoterms are always cited as "Incoterms 2020" and obligation allocations
   must match the research sheet exactly. Never paraphrase an Incoterm rule
   from memory.
5. Standards facts (ISO container dimensions, dangerous-goods classes 1–9,
   HS structure to six digits) come from the research sheets, not memory.
6. Distinguish general international practice from Ghana-specific practice.
   Write "in Ghana, ..." only when the research sheet or a verified source
   supports it; otherwise present the concept generally.
7. Do not invent statistics, dates, agreements, or quotes.
8. If you are not confident a claim is true, either verify it with WebSearch
   or remove it. An example that is slightly less specific is always better
   than a plausible falsehood.

## 6. Practice MCQs (exactly 3 per lesson)

- Scenario-based, mirroring the style of lesson 1.1's checks: a short
  realistic situation, then "Which option best explains ... / Which statement
  best describes ...".
- Exactly 4 options, exactly 1 correct, POINTS: 1.
- Distractors are the misconceptions the lesson's Important Notes dismantle.
  Options are full statements of similar length; never "All of the above".
- Explanation opens "The correct answer is Answer N.", explains the
  reasoning with reference to the lesson's concept, briefly says why the
  attractive distractor fails, and closes with the takeaway. 150–300 words.
- At most one negative-form question ("which is NOT...") per lesson.

## 7. Anti-repetition

- The brief lists the previous and next lesson. Do not deeply re-teach them;
  refer instead ("the previous lesson introduced the seven rights").
- Stay inside your lesson's scope; the detailed treatment of a topic belongs
  to the lesson titled for it (e.g. demurrage detail belongs to Module 9,
  not Module 3).
- Each lesson must still be teachable on its own: define any term you rely
  on that earlier lessons have not covered.

## 8. Prohibited

- Lesson agents produce no assessments or exams beyond the 3 MCQs. Module
  assessments are a separate deliverable (section 11) drafted after the
  module's four lessons exist.
- No changes to lesson titles, summaries, or objectives.
- No HTML or markdown inside BODY text.
- No meta commentary ("as an AI", "in this document") in learner-facing text.
- Never copy text from lesson 1.1; it is the style model, not source material.
- Exception for lesson 1.2 only: its Key Terms field in the database was
  corrupted (it holds a copy of the objectives). Add a final section
  `=== PROPOSED KEY TERMS ===` listing 5–7 terms in `Term :: definition`
  format, clearly for the owner's approval. Do not treat the corrupted field
  as the lesson's key terms.

## 9. Spelling and usage

- British spelling (organisation, prioritise, behaviour) as in lesson 1.1's
  body text. Objectives copied from the database keep their original wording
  regardless.
- Sentence case for headings. Numbers below 10 in words where natural.
- Currency amounts only as illustrative figures (rule 5.1); write "GHS" or
  "US dollars" rather than symbols in body text.

## 10. Agent deliverable and report

Write the draft file, then self-review against this checklist before
reporting: correct file name; marker syntax exact; block counts in range; 3
MCQs with matching CORRECT numbers; all objectives and key terms covered; no
prohibited content; FACTS & SOURCES complete. The agent's final response is a
SHORT report only (block counts, word count, MCQ one-line summaries, and any
claims the fact-checker should scrutinise) — never the lesson text itself.

## 11. Module assessments (separate deliverable, one per module)

Each of the 15 modules ends with a module assessment entered by the owner via
the instructor portal's Configure assessment step. The platform default is a
70% pass mark; questions are the same single-choice format as lesson checks.

- File: `curriculum/drafts/module-NN/assessment-module-NN.md`, drafted ONLY
  after the module's four lesson drafts are complete, by an agent that reads
  all four drafts plus the briefs.
- Exactly 12 questions (acceptable range 10–15), arranged so that the four
  lessons are covered evenly: 3 questions per lesson unless the owner's
  instruction says otherwise. Every question header names the lesson it
  tests:

```
=== ASSESSMENT Q1 | tests lesson N.M ===
QUESTION:
...
POINTS: 1
OPTIONS:
1. ...
2. ...
3. ...
4. ...
CORRECT: 2
EXPLANATION:
The correct answer is Answer 2.
...
```

- Slightly harder than lesson knowledge checks: application and
  discrimination across concepts, still answerable by a learner who studied
  the module. At least one scenario question per lesson. Same fact-safety
  rules (section 5), same explanation style (section 6).
- Open each file with a coverage map: one line per question naming the
  lesson and the objective/term it tests, so the owner can see balance at a
  glance.
- Do not write a final/programme examination unless the owner asks.
