"""Build the rows that extend the Ghana HS dataset past its current cutoff.

Reads the audit artifacts produced from the four sources (the 2024 schedule
scan, the repaired TSN column, the 2017 workbook and the Act 1106 tables) and
writes:

* ``--output`` — the new tariff rows, in the same shape as
  ``scenarios/data/ghana_hs_codes.json``;
* ``--report`` — counts, provenance and the differences between the sources.

Nothing here touches Django or a database, and no existing row is rewritten.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

CODE_TEXT_RE = re.compile(r"(?<!\d)(\d{4})[.,](\d{2})[.,](\d{2})[.,](\d{2})(?!\d)")
NUMERIC_RE = re.compile(r"\d+(?:[.,]\d+)?")
PERCENT_RE = re.compile(r"(?:(\d{1,2})\s*%|%\s*(\d{1,2}))")
UNIT_TOKENS = {"u", "kg", "m2", "m3", "l", "m", "pa", "ct", "2u", "g", "t"}

UNIT_LABELS = {
    "u": "Number of items(u)",
    "kg": "Weight in kilograms(k g)",
    "m2": "Area in square meters(m2 )",
    "m3": "Volume in cubic meters(m3 )",
    "l": "Volume in liters(l)",
    "2u": "Number of pairs(2u)",
    "m": "Length in meters(m)",
    "ct": "Weight in carats(cara t)",
}

#: Ghana's CET duty bands. A printed duty outside this set is a read error.
ALLOWED_DUTY = {"0", "5", "10", "20", "35"}
ALLOWED_VAT = {"0", "15"}

GLYPH_FIXES = str.maketrans(
    {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "|": "1",
        "S": "5",
        "s": "5",
        "Z": "2",
        "B": "8",
        "g": "9",
    }
)

PUNCTUATION = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\uff0c": ",",
    "\uff0e": ".",
    "\uff08": "(",
    "\uff09": ")",
    "\uff0f": "/",
    "\uff05": "%",
    "\uff1a": ":",
    "\u00b7": ".",
}

#: Text in these columns is the tariff line's own description, quantity unit
#: and rates. Measured from the whole-page OCR boxes.
DESC_RANGE = (295, 625)
UNIT_RANGE = (605, 665)
DUTY_RANGE = (655, 725)
VAT_RANGE = (725, 790)
EXCISE_RANGE = (790, 860)
PERCENT_RANGE = (775, 870)

#: The page images used for OCR are 910 px wide; a 4x PDF render is 2.616 times
#: wider. Cells that the small page misses are re-read from that render.
RENDER_SCALE = 4.0
RENDER_K = RENDER_SCALE / 1.529


def centre(record: dict) -> tuple[float, float]:
    points = record["box"]
    return (
        sum(point[0] for point in points) / 4,
        sum(point[1] for point in points) / 4,
    )


def clean_text(text: str) -> str:
    for source, target in PUNCTUATION.items():
        text = text.replace(source, target)
    text = " ".join(text.split())
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text


def number(text: str) -> str | None:
    cleaned = text.strip().replace(" ", "").replace("%", "")
    match = NUMERIC_RE.fullmatch(cleaned)
    if not match:
        return None
    return match.group(0).replace(",", ".")


def digits(text: str) -> str:
    return re.sub(r"[^0-9.]", "", text.translate(GLYPH_FIXES))


def valid_rate(value: str, allowed: set[str]) -> bool:
    return bool(value) and value in allowed


def repair_rate(value: str, allowed: set[str]) -> tuple[str, str]:
    """Return the rate and how it was obtained.

    The scan's two-character rate cells are sometimes read with the digits
    transposed (a printed "10" read as "01"). The CET bands make that
    detectable: if the read value is not a valid band but its reverse is, the
    reading was transposed.
    """
    if not value:
        return "", "unread"
    cleaned = digits(value)
    if cleaned in allowed:
        return cleaned, "read"
    reversed_value = cleaned[::-1]
    if reversed_value in allowed:
        return reversed_value, "transposed"
    return cleaned, "invalid"


def value_in(
    records: list[dict], x_range: tuple[int, int], y: float, tolerance: float = 6
) -> str:
    """The numeric value written in one rate column at the given row."""
    best: tuple[float, str] | None = None
    for record in records:
        x_pos, y_pos = centre(record)
        if not x_range[0] <= x_pos < x_range[1]:
            continue
        if abs(y_pos - y) > tolerance:
            continue
        value = number(record["text"])
        if value is None:
            continue
        distance = abs(y_pos - y)
        if best is None or distance < best[0]:
            best = (distance, value)
    return best[1] if best else ""


def percent_in(records: list[dict], y: float, tolerance: float = 30) -> str:
    """The concessionary rate printed as ``N%`` for chapter 98 lines."""
    best: tuple[float, str] | None = None
    for record in records:
        x_pos, y_pos = centre(record)
        if not PERCENT_RANGE[0] <= x_pos < PERCENT_RANGE[1]:
            continue
        if abs(y_pos - y) > tolerance:
            continue
        match = PERCENT_RE.search(record["text"])
        if match is None:
            continue
        distance = abs(y_pos - y)
        if best is None or distance < best[0]:
            best = (distance, match.group(1) or match.group(2))
    return best[1] if best else ""


def description(records: list[dict], code_y: float, next_y: float) -> str:
    """The text of the tariff line, gathered across its wrapped lines."""
    band = [
        record
        for record in records
        if DESC_RANGE[0] <= centre(record)[0] < DESC_RANGE[1]
        and code_y - 22 <= centre(record)[1] < min(next_y - 8, code_y + 46)
        # Wrapped descriptions often end with a bare code (the last one in a
        # "subheadings … and 8701.29.10.00" run); inside the description column
        # that is text, not a new tariff line.
        and number(record["text"]) is None
        and record["text"].strip().lower() not in UNIT_TOKENS
    ]
    band.sort(key=lambda record: (centre(record)[1], centre(record)[0]))

    clusters: list[list[dict]] = []
    for record in band:
        if clusters and abs(centre(record)[1] - centre(clusters[-1][0])[1]) <= 7:
            clusters[-1].append(record)
        else:
            clusters.append([record])

    if not clusters:
        return ""

    first = 0
    while first < len(clusters) and centre(clusters[first][0])[1] < code_y - 8:
        first += 1
    if first == len(clusters):
        return ""

    # A wrapped line can begin above the code column; if what we caught starts
    # mid-sentence, take the line just above it as well.
    if first > 0:
        caught = " ".join(record["text"].strip() for record in clusters[first])
        if caught[:1].islower() and code_y - centre(clusters[first - 1][0])[1] <= 24:
            first -= 1

    parts: list[str] = []
    previous_y = centre(clusters[first][0])[1]
    for index in range(first, min(first + 3, len(clusters))):
        cluster_y = centre(clusters[index][0])[1]
        words = " ".join(
            record["text"].strip()
            for record in sorted(clusters[index], key=lambda record: centre(record)[0])
        )
        if index > first:
            # A new dashed entry is a subheading for the lines below, not this
            # line's continuation.
            if words.lstrip().startswith("-") or cluster_y - previous_y > 24:
                break
        parts.append(words)
        previous_y = cluster_y

    text = clean_text(" ".join(parts))
    return re.sub(r"^[-–—\s]+", "", text)


WORD_RE = re.compile(r"[A-Za-z]{6,}")


#: Lines the 2024 scan holds but OCR missed entirely. Read off the page images
#: and cross-checked against the 2017 workbook rates; both agree.
VISUAL_ROWS = {
    "9101910000": {
        "page": 424,
        "description": "Electrically operated",
        "quantity_unit": "u",
        "import_duty": "20",
        "import_vat": "15",
    },
    "9110110000": {
        "page": 426,
        "description": "Complete movements, unassembled or partly assembled (movement sets)",
        "quantity_unit": "u",
        "import_duty": "20",
        "import_vat": "15",
    },
    "9110190000": {
        "page": 426,
        "description": "Rough movements",
        "quantity_unit": "kg",
        "import_duty": "10",
        "import_vat": "15",
    },
    "9611000000": {
        "page": 443,
        "description": (
            "Date, sealing or numbering stamps, and the like (including devices"
            " for printing or embossing labels), designed for operating in the"
            " hand; hand-operated composing sticks and hand printing sets"
            " incorporating such composing sticks"
        ),
        "quantity_unit": "kg",
        "import_duty": "20",
        "import_vat": "15",
    },
}


def build_vocab(*sources: list[dict]) -> set[str]:
    """Words the typed descriptions use, for repairing run-together OCR."""
    counts: collections.Counter = collections.Counter()
    for source in sources:
        for row in source:
            text = row.get("description") or ""
            counts.update(re.findall(r"[a-z]{2,}", text.lower()))
    return {word for word, count in counts.items() if count >= 1} | {"a", "i"}


def split_run_together(text: str, vocab: set[str]) -> str:
    """Re-insert the spaces OCR drops between words ("ofpaper" → "of paper")."""

    def segment(token: str) -> list[str] | None:
        """Fewest-word segmentation of a token, or None if it does not split."""
        memo: dict[int, list[str] | None] = {}

        def solve(index: int) -> list[str] | None:
            if index == len(token):
                return []
            if index in memo:
                return memo[index]
            best: list[str] | None = None
            for end in range(min(len(token), index + 20), index + 1, -1):
                piece = token[index:end]
                if piece not in vocab:
                    continue
                rest = solve(end)
                if rest is not None and (best is None or len(rest) + 1 < len(best)):
                    best = [piece, *rest]
            memo[index] = best
            return best

        pieces = solve(0)
        return pieces if pieces and len(pieces) > 1 else None

    def replace(match: re.Match) -> str:
        token = match.group(0)
        if token.lower() in vocab:
            return token
        pieces = segment(token.lower())
        if not pieces:
            return token
        head = token[0].upper() + pieces[0][1:] if token[0].isupper() else pieces[0]
        return " ".join([head, *pieces[1:]])

    text = WORD_RE.sub(replace, text)
    text = re.sub(r"(?<=[A-Za-z])\((?=[A-Za-z])", " (", text)
    text = re.sub(r",(?=[A-Za-z])", ", ", text)
    return text


def unit(records: list[dict], code_y: float) -> str:
    best: tuple[float, str] | None = None
    for record in records:
        x_pos, y_pos = centre(record)
        if not UNIT_RANGE[0] <= x_pos < UNIT_RANGE[1]:
            continue
        token = record["text"].strip().lower().replace(" ", "")
        if token not in UNIT_TOKENS:
            continue
        if not code_y - 10 <= y_pos <= code_y + 16:
            continue
        distance = abs(y_pos - code_y)
        if best is None or distance < best[0]:
            best = (distance, token)
    if best is None:
        return ""
    return UNIT_LABELS.get(best[1], best[1])


def load_page(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def page_anchors(page: int, ocr_payload: dict, repair_payload: dict | None) -> list[dict]:
    """The tariff-line positions on one page.

    Both passes are kept: the whole-page read catches lines the banded crop
    clips, and the repaired column recovers lines the whole-page read turned
    into digit noise. Where both find the same code, the repaired position and
    confidence win because it was read at eight times the resolution.
    """
    anchors: dict[str, dict] = {}
    for record in ocr_payload["records"]:
        cleaned = record["text"].replace(" ", "").replace("O", "0")
        match = CODE_TEXT_RE.search(cleaned)
        x_pos, y_pos = centre(record)
        if match is None or not 200 <= x_pos <= 330:
            continue
        code = "".join(match.groups())
        confidence = record["confidence"]
        existing = anchors.get(code)
        if existing is None or confidence > existing["confidence"]:
            anchors[code] = {"code": code, "y": y_pos, "confidence": confidence}
    if repair_payload is not None:
        for record in repair_payload["records"]:
            code = record["code"]
            existing = anchors.get(code)
            if existing is None or record["confidence"] > existing["confidence"]:
                anchors[code] = {
                    "code": code,
                    "y": record["y"],
                    "confidence": record["confidence"],
                }
    return sorted(anchors.values(), key=lambda anchor: anchor["y"])


def page_rate_offset(anchors: list[dict], records: list[dict]) -> int | None:
    """The vertical distance from a code to its printed rate row.

    Rates sit a few pixels above the code baseline and the exact gap varies by
    page, so the modal gap is used. Without it the nearest duty cell can belong
    to the neighbouring line.
    """
    cells = []
    for record in records:
        x_pos, y_pos = centre(record)
        if DUTY_RANGE[0] <= x_pos < DUTY_RANGE[1] and number(record["text"]):
            cells.append(y_pos)
    offsets: list[int] = []
    for anchor in anchors:
        near = [
            round(y_pos - anchor["y"])
            for y_pos in cells
            if -10 <= y_pos - anchor["y"] <= 10
        ]
        if near:
            offsets.append(min(near, key=abs))
    if not offsets:
        return None
    return collections.Counter(offsets).most_common(1)[0][0]


def act_description(text: str) -> str:
    """Reject the occasional garbled Act 1106 description (two codes, etc.)."""
    if len(text) < 3 or CODE_TEXT_RE.search(text.replace(" ", "")):
        return ""
    return text


def repair_from_render(
    rows, positions, offsets, needs, pdf_path, desc_sources
) -> collections.Counter:
    """Re-read cells the small page missed from a four-times-larger render."""
    import numpy as np
    import pypdfium2 as pdfium
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    pdf = pdfium.PdfDocument(str(pdf_path))
    images: dict[int, object] = {}
    counts: collections.Counter = collections.Counter()

    def page_image(page: int):
        if page not in images:
            images.clear()
            images[page] = pdf[page - 1].render(scale=RENDER_SCALE).to_pil().convert("RGB")
        return images[page]

    def read(image, box) -> str:
        result, _elapsed = engine(np.array(image.crop(box)))
        if not result:
            return ""
        lines = sorted(
            result, key=lambda item: (sum(point[1] for point in item[0]) / 4, item[0][0][0])
        )
        return " ".join(line[1] for line in lines)

    def box(x_range, y, half):
        return (
            int(x_range[0] * RENDER_K),
            int((y - half) * RENDER_K),
            int(x_range[1] * RENDER_K),
            int((y + half) * RENDER_K),
        )

    for code, row in rows.items():
        position = positions.get(code)
        if position is None:
            continue
        page, y, next_y = position
        problems = needs.get(code, set())
        if not problems:
            continue
        image = page_image(page)
        if "description" in problems:
            bottom = min(next_y - 4, y + 48)
            text = clean_text(
                read(
                    image,
                    (
                        int(310 * RENDER_K),
                        int((y - 10) * RENDER_K),
                        int(618 * RENDER_K),
                        int(bottom * RENDER_K),
                    ),
                )
            )
            text = re.sub(r"^[-–—\s]+", "", text)
            text = re.sub(r"\d{4}[.,]\d{2}[.,]\d{2}[.,]\d{2}.*$", "", text).strip()
            if text:
                row["description"] = text
                desc_sources[code] = "render"
                counts["description"] += 1

        offset = offsets.get(page)
        if "duty" in problems:
            if offset is not None:
                text = read(image, box(DUTY_RANGE, y + offset, 14))
                value, state = repair_rate(number(text) or "", ALLOWED_DUTY)
            else:
                text = read(image, box(PERCENT_RANGE, y, 22))
                match = PERCENT_RE.search(text)
                value = (match.group(1) or match.group(2)) if match else ""
                state = "read" if value in ALLOWED_DUTY else "unread"
            if state in {"read", "transposed"}:
                row["import_duty"] = value
                counts["duty"] += 1

        if "vat" in problems and offset is not None and not code.startswith("98"):
            text = read(image, box(VAT_RANGE, y + offset, 14))
            value, state = repair_rate(number(text) or "", ALLOWED_VAT)
            if state in {"read", "transposed"}:
                row["import_vat"] = value
                row["nhil_rate"] = "2.5" if value == "15" else "0"
                counts["vat"] += 1
    return counts


KNOWN_UNITS = set(UNIT_LABELS.values()) | {"No quantity(-)", "pack"}


def fill_unit_from_heading(rows, current) -> list[str]:
    """Give a missed quantity unit the one its heading prints on its lines."""
    by_heading: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for row in list(rows.values()) + current:
        if row.get("quantity_unit") in KNOWN_UNITS:
            by_heading[row["heading_code"]][row["quantity_unit"]] += 1

    filled: list[str] = []
    for row in rows.values():
        if row["quantity_unit"] in KNOWN_UNITS:
            continue
        if row["code"].startswith("98"):
            row["quantity_unit"] = "No quantity(-)"
            filled.append(row["code"])
            continue
        counter = by_heading.get(row["heading_code"])
        if not counter:
            continue
        row["quantity_unit"] = counter.most_common(1)[0][0]
        filled.append(row["code"])
    return filled


def fill_vat_from_heading(rows, current) -> list[str]:
    """Give an unread VAT the rate its heading prints everywhere else.

    A few cells print so faintly that neither the page nor the enlarged render
    yields a digit. The surrounding lines of the same heading still show
    whether that heading is standard-rated or zero-rated.
    """
    by_heading: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for row in list(rows.values()) + current:
        if row.get("import_vat"):
            by_heading[row["heading_code"]][row["import_vat"]] += 1

    filled: list[str] = []
    for row in rows.values():
        if row["import_vat"] or row["code"].startswith("98"):
            continue
        counter = by_heading.get(row["heading_code"])
        if not counter:
            counter = by_heading.get(row["code"][:2])
        if not counter:
            continue
        value = counter.most_common(1)[0][0]
        row["import_vat"] = value
        row["nhil_rate"] = "2.5" if value == "15" else "0"
        filled.append(row["code"])
    return filled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, required=True)
    parser.add_argument("--codes-dir", type=Path, required=True)
    parser.add_argument("--workbook-2017", type=Path, required=True)
    parser.add_argument("--headings-2017", type=Path, required=True)
    parser.add_argument("--act1106", type=Path, required=True)
    parser.add_argument("--correlation", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, help="the 2024 schedule scan, for cell re-reads")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    current = json.loads(args.current.read_text(encoding="utf-8"))
    existing = {row["code"] for row in current}
    cutoff = max(existing)

    workbook_rows = json.loads(args.workbook_2017.read_text(encoding="utf-8"))
    workbook = {row["code"]: row for row in workbook_rows}
    headings = json.loads(args.headings_2017.read_text(encoding="utf-8"))
    act = {
        row["code"]: row
        for row in json.loads(args.act1106.read_text(encoding="utf-8"))
    }
    correlation = json.loads(args.correlation.read_text(encoding="utf-8"))
    obsolete = {entry["obsolete"]: entry["replacements"] for entry in correlation}

    rows: dict[str, dict] = {}
    provenance: dict[str, collections.Counter] = {
        "duty": collections.Counter(),
        "vat": collections.Counter(),
        "description": collections.Counter(),
        "unit": collections.Counter(),
    }
    rate_repairs: list[dict] = []
    percent_rows: list[str] = []
    desc_sources: dict[str, str] = {}
    vocab = build_vocab(current, workbook_rows)
    positions: dict[str, tuple[int, float, float]] = {}
    offsets: dict[int, int | None] = {}
    needs: dict[str, set[str]] = collections.defaultdict(set)

    for ocr_path in sorted(
        args.ocr_dir.glob("page-*.json"),
        key=lambda item: int(item.stem.split("-")[-1]),
    ):
        page = int(ocr_path.stem.split("-")[-1])
        ocr_payload = load_page(ocr_path)
        repair_path = args.codes_dir / ocr_path.name
        repair_payload = load_page(repair_path) if repair_path.exists() else None
        records = ocr_payload["records"]
        anchors = page_anchors(page, ocr_payload, repair_payload)
        offset = page_rate_offset(anchors, records)
        offsets[page] = offset

        for index, anchor in enumerate(anchors):
            code = anchor["code"]
            if code <= cutoff or len(code) != 10:
                continue
            if code in existing or code in rows:
                continue
            next_y = anchor["y"] + 60
            for later in anchors[index + 1 :]:
                if later["y"] > anchor["y"] + 10:
                    next_y = later["y"]
                    break
            reference = workbook.get(code) or {}
            act_row = act.get(code) or {}

            text = ""
            desc_source = ""
            if act_row:
                text = act_description(act_row.get("description", ""))
                if text:
                    desc_source = "act1106"
            if not text:
                text = description(records, anchor["y"], next_y)
                if text:
                    desc_source = "scan"
            if not text and reference.get("description", "").strip():
                text = clean_text(reference["description"])
                desc_source = "workbook"
            if not text:
                text = headings.get(code[:4], "")
                if text:
                    desc_source = "heading"
            if not text:
                desc_source = "none"
            provenance["description"][desc_source] += 1
            desc_sources[code] = desc_source
            if desc_source in {"none", "heading"}:
                needs[code].add("description")

            quantity_unit = unit(records, anchor["y"])
            if quantity_unit:
                provenance["unit"]["scan"] += 1
            elif reference.get("quantity_unit"):
                quantity_unit = UNIT_LABELS.get(
                    reference["quantity_unit"], reference["quantity_unit"]
                )
                provenance["unit"]["workbook"] += 1
            elif act_row.get("quantity_unit"):
                quantity_unit = UNIT_LABELS.get(
                    act_row["quantity_unit"], act_row["quantity_unit"]
                )
                provenance["unit"]["act1106"] += 1
            else:
                provenance["unit"]["none"] += 1

            duty = vat = excise = ""
            if offset is not None:
                rate_y = anchor["y"] + offset
                duty = value_in(records, DUTY_RANGE, rate_y)
                vat = value_in(records, VAT_RANGE, rate_y)
                excise = value_in(records, EXCISE_RANGE, rate_y)
            if not duty:
                concession = percent_in(records, anchor["y"])
                if concession:
                    duty = concession
                    percent_rows.append(code)
                    vat = ""

            duty, duty_state = repair_rate(duty, ALLOWED_DUTY)
            if duty_state == "transposed":
                rate_repairs.append({"code": code, "field": "duty"})
            if duty_state in {"read", "transposed"}:
                provenance["duty"][duty_state] += 1
            elif reference.get("import_duty"):
                duty = reference["import_duty"]
                provenance["duty"]["workbook"] += 1
            elif act_row.get("import_duty"):
                duty = act_row["import_duty"]
                provenance["duty"]["act1106"] += 1
            else:
                duty = ""
                provenance["duty"]["none"] += 1

            vat, vat_state = repair_rate(vat, ALLOWED_VAT)
            if vat_state == "transposed":
                rate_repairs.append({"code": code, "field": "vat"})
            if vat_state in {"read", "transposed"}:
                provenance["vat"][vat_state] += 1
            elif reference.get("import_vat"):
                vat = reference["import_vat"]
                provenance["vat"]["workbook"] += 1
            else:
                vat = ""
                provenance["vat"]["none"] += 1

            if not excise:
                excise = "0"

            if not duty:
                needs[code].add("duty")
            if not vat and not code.startswith("98"):
                needs[code].add("vat")
            if needs[code]:
                positions[code] = (page, anchor["y"], next_y)

            rows[code] = {
                "code": code,
                "description": text,
                "heading_code": code[:4],
                "quantity_unit": quantity_unit,
                "import_duty": duty,
                "import_vat": vat,
                "import_excise": excise,
                "export_duty": "0",
                "nhil_rate": "2.5" if vat == "15" else "0",
                "source_page": page,
            }

    # Tariff lines created by Act 1106 that the scan does not show.
    added_from_act: list[str] = []
    for code, act_row in act.items():
        if code <= cutoff or code in existing or code in rows:
            continue
        rows[code] = {
            "code": code,
            "description": act_description(act_row.get("description", "")),
            "heading_code": code[:4],
            "quantity_unit": UNIT_LABELS.get(
                act_row.get("quantity_unit", ""), act_row.get("quantity_unit", "")
            ),
            "import_duty": act_row.get("import_duty", ""),
            "import_vat": "",
            "import_excise": "0",
            "export_duty": "0",
            "nhil_rate": "0",
            "source_page": None,
        }
        added_from_act.append(code)

    added_from_visual: list[str] = []
    for code, visual in VISUAL_ROWS.items():
        if code <= cutoff or code in existing or code in rows:
            continue
        vat = visual["import_vat"]
        rows[code] = {
            "code": code,
            "description": visual["description"],
            "heading_code": code[:4],
            "quantity_unit": UNIT_LABELS.get(
                visual["quantity_unit"], visual["quantity_unit"]
            ),
            "import_duty": visual["import_duty"],
            "import_vat": vat,
            "import_excise": "0",
            "export_duty": "0",
            "nhil_rate": "2.5" if vat == "15" else "0",
            "source_page": visual["page"],
        }
        added_from_visual.append(code)

    repaired: collections.Counter = collections.Counter()
    if args.pdf is not None:
        repaired = repair_from_render(
            rows, positions, offsets, needs, args.pdf, desc_sources
        )
    vat_filled = fill_vat_from_heading(rows, current)
    unit_filled = fill_unit_from_heading(rows, current)

    for code, source in desc_sources.items():
        if source in {"scan", "render"}:
            rows[code]["description"] = split_run_together(
                rows[code]["description"], vocab
            )

    ordered = [rows[code] for code in sorted(rows)]

    blank_description = [row["code"] for row in ordered if not row["description"]]
    blank_duty = [row["code"] for row in ordered if not row["import_duty"]]
    blank_vat = [row["code"] for row in ordered if not row["import_vat"]]
    invalid_duty = [
        row["code"] for row in ordered if row["import_duty"] not in ALLOWED_DUTY
    ]

    codes = set(rows)
    workbook_later = {code for code in workbook if code > cutoff}
    act_later = {code for code in act if code > cutoff}
    only_2017 = sorted(workbook_later - codes)
    only_act = sorted(act_later - codes)
    retired = [code for code in only_2017 if code in obsolete]
    unexplained = [code for code in only_2017 if code not in obsolete]
    # A replacement may name a six-digit subheading that the current schedule
    # splits into its own tariff lines (8519.81 → 8519.81.10/.90).
    present_prefixes = {code[:6] for code in codes | existing}
    replacements_missing = sorted(
        {
            replacement
            for code in only_2017
            for replacement in obsolete.get(code, [])
            if replacement > cutoff
            and replacement not in codes
            and replacement not in existing
            and replacement[:6] not in present_prefixes
        }
    )

    shared = sorted(codes & workbook_later)
    duty_changes = []
    for code in shared:
        old = (workbook[code].get("import_duty") or "").strip()
        new = rows[code]["import_duty"].strip()
        if old in ALLOWED_DUTY and new in ALLOWED_DUTY and old != new:
            duty_changes.append({"code": code, "duty_2017": old, "duty_2024": new})

    report = {
        "cutoff": cutoff,
        "existing_rows": len(current),
        "added_rows": len(ordered),
        "added_from_act1106": added_from_act,
        "added_from_visual_check": added_from_visual,
        "total_rows": len(current) + len(ordered),
        "per_chapter": dict(
            sorted(collections.Counter(row["code"][:2] for row in ordered).items())
        ),
        "provenance": {key: dict(value) for key, value in provenance.items()},
        "repaired_from_render": dict(repaired),
        "vat_filled_from_heading": vat_filled,
        "unit_filled_from_heading": unit_filled,
        "rate_repairs": rate_repairs,
        "chapter_98_percent_rows": percent_rows,
        "blank_description": blank_description,
        "blank_duty": blank_duty,
        "blank_vat": blank_vat,
        "invalid_duty": invalid_duty,
        "not_in_2017_workbook": sorted(codes - workbook_later),
        "not_in_act1106": sorted(codes - act_later),
        "in_2017_but_not_added": only_2017,
        "retired_by_correlation": {code: obsolete[code] for code in retired},
        "unexplained_2017_missing": unexplained,
        "replacement_codes_missing": replacements_missing,
        "in_act1106_but_not_added": only_act,
        "shared_with_2017": len(shared),
        "duty_changes_2017_to_2024": duty_changes,
    }

    args.output.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"added={len(ordered)} (act_only={len(added_from_act)}) "
        f"total={len(current) + len(ordered)} "
        f"blank_desc={len(blank_description)} blank_duty={len(blank_duty)} "
        f"blank_vat={len(blank_vat)} invalid_duty={len(invalid_duty)} "
        f"duty_changes={len(duty_changes)} "
        f"repaired={dict(repaired)} vat_filled={len(vat_filled)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
