"""Compile curriculum drafts into per-module Word documents.

Usage:  python curriculum/tools/build_docx.py 1 2 3 ...

Reads:
  curriculum/lesson_briefs/module-NN/lesson-N.M.md   (titles, summaries, objectives, key terms)
  curriculum/drafts/module-NN/lesson-N.M.md          (teaching blocks + MCQs)
  curriculum/drafts/module-NN/assessment-module-NN.md (module assessment, optional)
  curriculum/reference/lesson-1.1-complete.md        (lesson 1.1 from the live database)

Writes: curriculum/docx/Course C - Module NN - <Module Title>.docx
"""
from __future__ import annotations

import html as html_lib
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

_TAG_MARKUP = re.compile(r"<(/?)(ol|ul|li|p|h[1-6]|br|blockquote|div|strong|em)\b[^>]*/?>", re.I)
_ANY_TAG = re.compile(r"<[^>]+>")


def html_to_text(value: str) -> str:
    """Readable text of a rich-text body, preserving paragraphs and list numbering."""
    if "<" not in value:
        return value
    out, pos = [], 0
    ol_depth, item_no = [], 0
    for m in _TAG_MARKUP.finditer(value):
        seg = value[pos:m.start()]
        if seg.strip():
            prefix = f"{item_no}. " if ol_depth and item_no else ""
            out.append((prefix + seg.strip()) if prefix else seg.strip())
        closing, tag = m.group(1), m.group(2).lower()
        if tag == "ol" and not closing:
            ol_depth.append(True)
            item_no = 0
        elif tag == "ol":
            ol_depth and ol_depth.pop()
        elif tag == "li" and not closing:
            if ol_depth:
                item_no += 1
        if tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br", "div", "blockquote") and (
            closing or tag == "br"
        ):
            out.append("\n")
        pos = m.end()
    seg = value[pos:]
    if seg.strip():
        out.append(seg.strip())
    text = _ANY_TAG.sub("", "\n".join(out))
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "lesson_briefs"
DRAFTS = ROOT / "drafts"
REFERENCE = ROOT / "reference" / "lesson-1.1-complete.md"
OUT = ROOT / "docx"

MODULES = {
    1: ("Course 1 — Introduction to Logistics and Goods Movement", "Introduction to Logistics"),
    2: ("Course 1 — Introduction to Logistics and Goods Movement", "The Logistics Ecosystem"),
    3: ("Course 1 — Introduction to Logistics and Goods Movement", "Fundamentals of Goods Movement"),
    4: ("Course 2 — International Trade and Freight Forwarding Fundamentals", "International Trade Fundamentals"),
    5: ("Course 2 — International Trade and Freight Forwarding Fundamentals", "Freight Forwarding Fundamentals"),
    6: ("Course 2 — International Trade and Freight Forwarding Fundamentals", "Logistics Documentation"),
    7: ("Course 3 — Transport, Warehousing and Port Operations", "Transport and Shipping Operations"),
    8: ("Course 3 — Transport, Warehousing and Port Operations", "Warehousing and Inventory Management"),
    9: ("Course 3 — Transport, Warehousing and Port Operations", "Port and Terminal Operations"),
    10: ("Course 4 — Logistics Costing, Risk and Cross-Border Operations", "Logistics Costing and Pricing"),
    11: ("Course 4 — Logistics Costing, Risk and Cross-Border Operations", "Logistics Risk and Compliance"),
    12: ("Course 4 — Logistics Costing, Risk and Cross-Border Operations", "Cross-Border Logistics and Coordination"),
    13: ("Course 5 — Advanced Supply Chain and Strategic Logistics Management", "Supply Chain Planning and Optimisation"),
    14: ("Course 5 — Advanced Supply Chain and Strategic Logistics Management", "Digital Logistics and Technology"),
    15: ("Course 5 — Advanced Supply Chain and Strategic Logistics Management", "Strategic Logistics Management"),
}

# Bernard-approved corrections applied at compile time (DB bugs, see PROGRESS.md).
TITLE_FIXUPS = {
    (1, 2): "Logistics versus Supply Chain Management",
    (4, 1): "Importing, Exporting, and Transit Trade",
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
    return heading, html_to_text(body)


def parse_mcq(payload: str):
    """Return dict(question, points, options[list], correct, explanation)."""
    fields = {"question": "", "points": "1", "options": [], "correct": 0, "explanation": ""}
    section, buf = None, []

    def flush():
        if section == "QUESTION":
            fields["question"] = html_to_text("\n".join(buf).strip())
        elif section == "OPTIONS":
            opts = []
            for ln in buf:
                m = re.match(r"^(\d+)\.\s*(.*)$", ln.strip())
                if m:
                    opts.append(m.group(2).strip())
                elif opts:
                    opts[-1] += " " + ln.strip()
            fields["options"] = [html_to_text(o) for o in opts]
        elif section == "CORRECT":
            m = re.search(r"\d+", " ".join(buf))
            if m:
                fields["correct"] = int(m.group())
        elif section == "EXPLANATION":
            fields["explanation"] = html_to_text("\n".join(buf).strip())
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
    """Return dict(blocks=[(type, heading, body)], mcqs=[...], facts=[...], proposed_terms=[...], title=str|None)."""
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


def parse_brief(path: Path):
    text = path.read_text(encoding="utf-8")
    title = ""
    m = re.search(r"^#\s*LESSON BRIEF\s*([\d.]+)\s*[—-]\s*(.+)$", text, re.M)
    if m:
        title = m.group(2).strip()
    summary = section(text, "Summary (from curriculum)")
    objectives = section(text, "Learning Objectives (from curriculum)")
    key_terms = section(text, "Key Terms (from curriculum)")
    return title, summary, objectives, key_terms


def section(text: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


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

    h = doc.add_heading(f"{module_title}", 0)
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

    for lesson_idx in range(1, 5):
        lid = f"{n}.{lesson_idx}"
        brief_path = BRIEFS / mdir / f"lesson-{lid}.md"
        if not brief_path.exists():
            continue
        title, summary, objectives, key_terms = parse_brief(brief_path)
        title = TITLE_FIXUPS.get((n, lesson_idx), title)

        if (n, lesson_idx) == (1, 1):
            draft = parse_lesson_draft(REFERENCE)
        else:
            draft_path = DRAFTS / mdir / f"lesson-{lid}.md"
            if not draft_path.exists():
                continue
            draft = parse_lesson_draft(draft_path)

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
        counts = {}
        for btype, heading, body in draft["blocks"]:
            counts[btype] = counts.get(btype, 0) + 1
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
    fname = OUT / f"Course {n} placeholder.docx"
    course_no = course.split("—")[0].strip()
    fname = OUT / f"{course_no} - Module {n:02d} - {module_title}.docx"
    doc.save(fname)
    return fname, counts_total(draft), len(questions) if assess_path.exists() else 0


def counts_total(draft):
    return len(draft["blocks"]), len(draft["mcqs"])


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
