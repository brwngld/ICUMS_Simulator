"""Structural QA sweep over customs curriculum drafts (no model calls).

Mirrors `curriculum/tools/qa_drafts.py` (the Logistics sweep) with the bands
overridden by `curriculum/customs/WRITING_SPEC.md` C2: 5-7 Key Concept blocks of
120-250 words, 2-3 Worked Example blocks of 200-400 words, 1-2 Important Note
blocks of 120-220 words, exactly 3 MCQs, lesson total 1,600-2,600 block words.
Everything the customs spec inherits unchanged (marker syntax, MCQ shape, body
hygiene, FACTS & SOURCES presence, 12-question assessments) is checked the same
way. Run:

    python curriculum/customs/tools/qa_customs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "drafts"

BANDS = {"KEY CONCEPT": (120, 250), "WORKED EXAMPLE": (200, 400), "IMPORTANT NOTE": (120, 220)}
COUNTS = {"KEY CONCEPT": (5, 7), "WORKED EXAMPLE": (2, 3), "IMPORTANT NOTE": (1, 2)}
MARKER_RE = re.compile(r"^===\s*(.+?)\s*===\s*$")


def words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def parse(text: str):
    chunks, cur, buf = [], None, []
    for line in text.splitlines():
        m = MARKER_RE.match(line)
        if m:
            if cur:
                chunks.append((cur, "\n".join(buf).strip("\n")))
            cur, buf = m.group(1).upper(), []
        elif cur:
            buf.append(line)
    if cur:
        chunks.append((cur, "\n".join(buf).strip("\n")))
    return chunks


def body_problems(body: str, label: str, problems: list):
    if re.search(r"^\s*#", body, re.M):
        problems.append(f"{label}: markdown heading in body")
    if "**" in body or "`" in body:
        problems.append(f"{label}: markdown emphasis/code in body")
    if re.search(r"<[a-zA-Z/][^>]*>", body):
        problems.append(f"{label}: HTML tag in body")


def check_mcq(payload: str, where: str, problems: list, tag: str):
    q = re.search(r"^QUESTION:\s*\n(.*?)(?=^POINTS:)", payload, re.S | re.M)
    pts = re.search(r"^POINTS:\s*(\d+)", payload, re.M)
    opts = re.findall(r"^(\d+)\.\s+", payload, re.M)
    corr = re.search(r"^CORRECT:\s*(\d+)", payload, re.M)
    expl = re.search(r"^EXPLANATION:\s*\n(.*?)(?=^===|\Z)", payload, re.S | re.M)
    if not (q and pts and corr and expl):
        problems.append(f"{where}/{tag}: missing QUESTION/POINTS/CORRECT/EXPLANATION")
        return
    if pts.group(1) != "1":
        problems.append(f"{where}/{tag}: POINTS {pts.group(1)} != 1")
    if sorted(opts) != ["1", "2", "3", "4"]:
        problems.append(f"{where}/{tag}: options are {opts}")
    c = int(corr.group(1))
    if not 1 <= c <= 4:
        problems.append(f"{where}/{tag}: CORRECT {c} out of range")
    opener = f"The correct answer is Answer {c}"
    if not expl.group(1).strip().startswith(opener):
        problems.append(f"{where}/{tag}: explanation does not open with '{opener}'")
    # The customs spec inherits the Logistics MCQ shape unchanged, including the
    # explanation band; QA keeps the Logistics tolerance (~150-300).
    w = words(expl.group(1))
    if not 120 <= w <= 320:
        problems.append(f"{where}/{tag}: explanation {w} words (band ~150-300)")


def check_lesson(path: Path):
    text = path.read_text(encoding="utf-8")
    problems = []
    chunks = parse(text)
    counts = {k: 0 for k in COUNTS}
    total = 0
    mcq_n = 0
    has_facts = any(c.startswith("FACTS") for c, _ in chunks)
    for kind, payload in chunks:
        if kind in BANDS:
            counts[kind] += 1
            m = re.match(r"HEADING:\s*(.*)", payload)
            if not m or not m.group(1).strip():
                problems.append(f"{kind}#{counts[kind]}: missing HEADING")
            body = re.sub(r"^HEADING:.*?\nBODY:\s*\n?", "", payload, count=1, flags=re.S)
            w = words(body.strip())
            total += w
            lo, hi = BANDS[kind]
            if not lo <= w <= hi:
                problems.append(f"{kind}#{counts[kind]}: {w} words (band {lo}-{hi})")
            body_problems(body, f"{kind}#{counts[kind]}", problems)
        elif kind.startswith("MCQ") or kind.startswith("PRACTICE"):
            mcq_n += 1
            check_mcq(payload, path.name, problems, f"MCQ {mcq_n}")
    for kind, (lo, hi) in COUNTS.items():
        if not lo <= counts[kind] <= hi:
            problems.append(f"count {kind}: {counts[kind]} (band {lo}-{hi})")
    # 5-7 + 2-3 + 1-2 blocks -> 8 to 12 in total
    if not 8 <= sum(counts.values()) <= 12:
        problems.append(f"total blocks {sum(counts.values())} (band 8-12)")
    if mcq_n != 3:
        problems.append(f"MCQ count {mcq_n} != 3")
    if not 1600 <= total <= 2600:
        problems.append(f"total body words {total} (band 1600-2600)")
    if not has_facts:
        problems.append("missing FACTS & SOURCES")
    return problems, counts, total, mcq_n


def check_assessment(path: Path):
    text = path.read_text(encoding="utf-8")
    problems = []
    chunks = parse(text)
    qs = [p for c, p in chunks if c.startswith("ASSESSMENT Q")]
    if len(qs) != 12:
        problems.append(f"{len(qs)} questions (expected 12)")
    for i, payload in enumerate(qs, 1):
        check_mcq(payload, path.name, problems, f"Q{i}")
    if "coverage" not in text.lower():
        problems.append("no coverage map")
    if not any(c.startswith("FACTS") for c, _ in chunks):
        problems.append("missing FACTS & SOURCES")
    return problems, len(qs)


def main():
    files = [f for f in sorted(DRAFTS.glob("module-*/*.md")) if not f.name.startswith("errata")]
    bad = 0
    for path in files:
        rel = str(path.relative_to(DRAFTS))
        if path.name.startswith("assessment"):
            problems, n = check_assessment(path)
            status = "OK" if not problems else "ISSUES"
            print(f"[{status}] {rel} — {n} questions")
        else:
            problems, counts, total, mcq_n = check_lesson(path)
            status = "OK" if not problems else "ISSUES"
            print(f"[{status}] {rel} — KC {counts['KEY CONCEPT']} / WE {counts['WORKED EXAMPLE']} / IN {counts['IMPORTANT NOTE']}, {total}w, {mcq_n} MCQs")
        for p in problems:
            print(f"    - {p}")
        bad += bool(problems)
    if not files:
        print("no drafts yet — nothing to check (drafts live in curriculum/customs/drafts/module-*/)")
    print(f"\n{len(files)} files checked, {bad} with issues")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
