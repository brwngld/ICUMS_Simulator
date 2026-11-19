"""Compile the customs curriculum drafts into per-module Word documents.

Usage:  python curriculum/customs/tools/build_docx_customs.py 1 2 3 ...

Reads:
  curriculum/customs/lesson_briefs/module-NN/lesson-N.M.md   (titles, summaries, objectives, key terms)
  curriculum/customs/drafts/module-NN/lesson-N.M.md          (teaching blocks + MCQs)
  curriculum/customs/drafts/module-NN/assessment-module-NN.md (module assessment, optional)

Writes: curriculum/customs/docx/Course C - Module NN - <Module Title>.docx

Adapted from curriculum/tools/build_docx.py (the approved Logistics pipeline),
with the customs paths, module map and brief section names.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]  # curriculum/customs
BRIEFS = ROOT / "lesson_briefs"
DRAFTS = ROOT / "drafts"
OUT = ROOT / "docx"

MODULES = {
    1: ("Course 1 — Customs Foundations, Documents and the Clearance Ecosystem", "Customs Foundations and the Legal Mandate"),
    2: ("Course 1 — Customs Foundations, Documents and the Clearance Ecosystem", "Trade, Shipping and Clearance Documents"),
    3: ("Course 1 — Customs Foundations, Documents and the Clearance Ecosystem", "The Port and Border Clearance Ecosystem"),
    4: ("Course 2 — Customs Procedures, Electronic Declarations and Import Controls", "Customs Regimes and Core Procedures"),
    5: ("Course 2 — Customs Procedures, Electronic Declarations and Import Controls", "Electronic Customs Systems and Declarations"),
    6: ("Course 2 — Customs Procedures, Electronic Declarations and Import Controls", "MDA Requirements and Import Controls"),
    7: ("Course 3 — Classification, Valuation, Origin and Duty", "Harmonised System Classification"),
    8: ("Course 3 — Classification, Valuation, Origin and Duty", "Customs Valuation and Duty Calculation"),
    9: ("Course 3 — Classification, Valuation, Origin and Duty", "Rules of Origin and Trade Preferences"),
    10: ("Course 4 — Warehousing, Special Movements, Risk and Examination", "Warehousing, Reliefs and Revenue Adjustments"),
    11: ("Course 4 — Warehousing, Special Movements, Risk and Examination", "Transit, Transhipment and Free Zones"),
    12: ("Course 4 — Warehousing, Special Movements, Risk and Examination", "Customs Risk Management and Examination"),
    13: ("Course 5 — Advanced Border Controls, Compliance and Professional Practice", "Special Goods and Advanced Border Controls"),
    14: ("Course 5 — Advanced Border Controls, Compliance and Professional Practice", "Advanced Compliance and Case Management"),
    15: ("Course 5 — Advanced Border Controls, Compliance and Professional Practice", "Professional Customs Practice and Capstone"),
}

MARKER_RE = re.compile(r"^===\s*(.+?)\s*===\s*$")
BLOCK_TYPES = {
    "KEY CONCEPT": "Key Concept",
    "WORKED EXAMPLE": "Worked Example",
    "IMPORTANT NOTE": "Important Note",
}


def parse_blocks(text: str):
    """Split a draft into (kind, payload) chunks at === markers."""
    chunks, current, buf = [], None, []
    for line in text.splitlines():
        m = MARKER_RE.match(line)
        if m:
            if current is not None:
                chunks.append((current, "\n".join(buf).strip("\n")))
            current, buf = m.group(1).upper(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        chunks.append((current, "\n".join(buf).strip("\n")))
    return chunks


def parse_teaching_block(payload: str):
    heading, body = "", ""
    m = re.match(r"HEADING:\s*(.*?)\n(.*)$", payload, re.S)
    if m:
        heading, body = m.group(1).strip(), m.group(2).strip()
        body = re.sub(r"^BODY:\s*", "", body, count=1).strip()
    return heading, body


def parse_mcq(payload: str):
    """Return dict(question, points, options[list], correct, explanation)."""
    fields = {"question": "", "points": "1", "options": [], "correct": 0, "explanation": ""}
    section, buf = None, []

    def flush():
        if section == "QUESTION":
            fields["question"] = "\n".join(buf).strip()
        elif section == "OPTIONS":
            opts = []
            for ln in buf:
                m = re.match(r"^(\d+)\.\s*(.*)$", ln.strip())
                if m:
                    opts.append(m.group(2).strip())
                elif opts:
                    opts[-1] += " " + ln.strip()
            fields["options"] = opts
        elif section == "CORRECT":
            m = re.search(r"\d+", " ".join(buf))
            if m:
                fields["correct"] = int(m.group())
        elif section == "EXPLANATION":
            fields["explanation"] = "\n".join(buf).strip()
        elif section == "POINTS":
            m = re.search(r"\d+", " ".join(buf))
            if m:
                fields["points"] = m.group()

    for line in payload.splitlines():
        m = re.match(r"^(QUESTION|POINTS|OPTIONS|CORRECT|EXPLANATION):\s*(.*)$", line)
        if m:
            flush()
            section, buf = m.group(1), [m.group(2)] if m.group(2) else []
        elif section:
            buf.append(line)
    flush()
    return fields


def parse_lesson_draft(path: Path):
    chunks = parse_blocks(path.read_text(encoding="utf-8"))
    out = {"blocks": [], "mcqs": [], "facts": [], "proposed_terms": [], "title": None}
    for kind, payload in chunks:
        if kind in BLOCK_TYPES:
            heading, body = parse_teaching_block(payload)
            out["blocks"].append((BLOCK_TYPES[kind], heading, body))
        elif kind.startswith("MCQ") or kind.startswith("PRACTICE QUESTION") or kind.startswith("ASSESSMENT Q"):
            out["mcqs"].append(payload)
        elif kind.startswith("FACTS"):
            out["facts"] = [ln.strip().lstrip("- ").strip() for ln in payload.splitlines() if ln.strip().startswith("-")]
        elif "PROPOSED KEY TERMS" in kind:
            out["proposed_terms"] = [ln.strip() for ln in payload.splitlines() if "::" in ln]
    m = re.search(r"^#\s*(.+)$", path.read_text(encoding="utf-8"), re.M)
    if m:
        out["title"] = m.group(1).strip()
    return out


def parse_assessment(path: Path):
    text = path.read_text(encoding="utf-8")
    chunks = parse_blocks(text)
    intro = text.split("===")[0].strip() if "===" in text else text.strip()
    questions = []
    for kind, payload in chunks:
        if kind.startswith("ASSESSMENT Q"):
            m = re.search(r"tests lesson\s*([\d.]+)", kind, re.I)
            q = parse_mcq(payload)
            q["lesson"] = m.group(1) if m else "?"
            questions.append(q)
    return intro, questions


def section(text: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def parse_brief(path: Path):
    text = path.read_text(encoding="utf-8")
    title = ""
    m = re.search(r"^#\s*LESSON BRIEF\s*([\d.]+)\s*[—-]\s*(.+)$", text, re.M)
    if m:
        title = m.group(2).strip()
    summary = section(text, "Summary") or section(text, "Summary (from curriculum)")
    objectives = section(text, "Learning Objectives") or section(text, "Learning Objectives (from curriculum)")
    key_terms = section(text, "Key Terms") or section(text, "Key Terms (from curriculum)")
    return title, summary, objectives, key_terms


def add_body(doc, text: str, style=None):
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        p = doc.add_paragraph(style=style)
        for i, line in enumerate(para.splitlines()):
            if i:
                p.add_run().add_break()
            p.add_run(line.strip())
    return doc


def add_mcq(doc, idx: int, q: dict, label: str = "Practice Question"):
    if label:
        p = doc.add_paragraph()
        run = p.add_run(f"{label} {idx}")
        run.bold = True
    add_body(doc, q["question"])
    for i, opt in enumerate(q["options"], 1):
        marker = " ✓" if i == q.get("correct") else ""
        para = doc.add_paragraph(f"{i}. {opt}{marker}")
        para.paragraph_format.left_indent = Pt(18)
    cp = doc.add_paragraph()
    r = cp.add_run(f"Correct answer: Answer {q.get('correct', '?')}")
    r.bold = True
    ep = doc.add_paragraph()
    er = ep.add_run("Explanation")
    er.bold = True
    er.italic = True
    add_body(doc, q.get("explanation", ""))


def style_setup(doc):
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)


def build_module(n: int):
    course, module_title = MODULES[n]
    mdir = f"module-{n:02d}"
    doc = Document()
    style_setup(doc)

    doc.add_heading(f"{module_title}", 0)
    sub = doc.add_paragraph()
    r = sub.add_run(f"{course} · Module {n} · Teaching content for the Theory Builder")
    r.italic = True
    note = doc.add_paragraph()
    nr = note.add_run(
        "Review copy. Each lesson lists its blocks in entry order: enter each block's "
        "heading and body into the Theory Builder; enter practice questions as Lesson "
        "Checks; enter the module assessment via Configure assessment. Grey appendix "
        "sections are audit notes, not for entry."
    )
    nr.italic = True
    nr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

    counts_total = (0, 0)
    n_questions = 0
    for lesson_idx in range(1, 5):
        lid = f"{n}.{lesson_idx}"
        brief_path = BRIEFS / mdir / f"lesson-{lid}.md"
        if not brief_path.exists():
            continue
        title, summary, objectives, key_terms = parse_brief(brief_path)

        draft_path = DRAFTS / mdir / f"lesson-{lid}.md"
        if not draft_path.exists():
            continue
        draft = parse_lesson_draft(draft_path)
        counts_total = (counts_total[0] + len(draft["blocks"]), counts_total[1] + len(draft["mcqs"]))

        doc.add_heading(f"Lesson {lid} — {title}", 1)
        if summary:
            doc.add_heading("Summary", 2)
            add_body(doc, summary)
        if objectives:
            doc.add_heading("Learning objectives", 2)
            for ln in objectives.splitlines():
                if ln.strip():
                    doc.add_paragraph(ln.strip(), style="List Bullet")
        if key_terms and "::" in key_terms:
            doc.add_heading("Key terms", 2)
            for ln in key_terms.splitlines():
                if "::" in ln:
                    term, definition = ln.split("::", 1)
                    p = doc.add_paragraph()
                    p.add_run(term.strip() + " — ").bold = True
                    p.add_run(definition.strip())
        elif draft["proposed_terms"]:
            doc.add_heading("Key terms (PROPOSED — for your approval)", 2)
            for ln in draft["proposed_terms"]:
                term, definition = ln.split("::", 1)
                p = doc.add_paragraph()
                p.add_run(term.strip() + " — ").bold = True
                p.add_run(definition.strip())

        doc.add_heading("Teaching content", 2)
        for btype, heading, body in draft["blocks"]:
            lp = doc.add_paragraph()
            lr = lp.add_run(btype.upper())
            lr.bold = True
            lr.font.size = Pt(9)
            lr.font.color.rgb = RGBColor(0x2E, 0x4B, 0x8C)
            lp.paragraph_format.keep_with_next = True
            if heading:
                doc.add_heading(heading, 3)
            add_body(doc, body)

        if draft["mcqs"]:
            doc.add_heading("Practice questions (Lesson Checks)", 2)
            for i, payload in enumerate(draft["mcqs"], 1):
                add_mcq(doc, i, parse_mcq(payload))

        if draft["facts"]:
            doc.add_heading("Fact-check appendix (audit notes — not for entry)", 3)
            for f in draft["facts"]:
                p = doc.add_paragraph()
                run = p.add_run(f)
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

    assess_path = DRAFTS / mdir / f"assessment-module-{n:02d}.md"
    if assess_path.exists():
        intro, questions = parse_assessment(assess_path)
        n_questions = len(questions)
        doc.add_heading(f"Module {n} Assessment — {len(questions)} questions", 1)
        lead = doc.add_paragraph()
        lr = lead.add_run("Enter via the instructor portal's Configure assessment step. "
                          "Green ticks mark correct answers — do not enter them; enter options as-is.")
        lr.italic = True
        if intro and not intro.startswith("#"):
            add_body(doc, intro)
        for i, q in enumerate(questions, 1):
            p = doc.add_paragraph()
            r = p.add_run(f"Question {i} (tests lesson {q.get('lesson', '?')})")
            r.bold = True
            add_mcq(doc, i, q, label="")

    OUT.mkdir(exist_ok=True)
    course_no = course.split("—")[0].strip()
    fname = OUT / f"{course_no} - Module {n:02d} - {module_title}.docx"
    doc.save(fname)
    return fname, counts_total, n_questions


def main():
    mods = [int(a) for a in sys.argv[1:]] or sorted(MODULES)
    for n in mods:
        try:
            fname, (blocks, mcqs), aqs = build_module(n)
            print(f"Module {n:02d}: wrote {fname.name} ({blocks} blocks, {mcqs} lesson MCQs, {aqs} assessment questions)")
        except Exception as e:
            print(f"Module {n:02d}: FAILED — {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
