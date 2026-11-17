"""Turn per-page 2024 Ghana HS OCR output into reviewable tariff rows.

The parser deliberately writes an audit artifact only. It does not update the
application dataset or database; those steps require validation against the
2017 source and duplicate/missing-code checks.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CODE_RE = re.compile(r"(?<!\d)(\d{4})[.,](\d{2})[.,](\d{2})[.,](\d{2})(?!\d)")


def centre(record: dict) -> tuple[float, float]:
    points = record["box"]
    return (
        sum(point[0] for point in points) / len(points),
        sum(point[1] for point in points) / len(points),
    )


def normalise_code(text: str) -> str | None:
    cleaned = text.replace("O", "0").replace("o", "0").replace(" ", "")
    match = CODE_RE.search(cleaned)
    return "".join(match.groups()) if match else None


def numeric(text: str) -> str | None:
    cleaned = text.strip().replace(",", ".")
    match = re.fullmatch(r"\d+(?:\.\d+)?", cleaned)
    return match.group(0) if match else None


def nearest_value(records: list[dict], x_min: float, x_max: float, y: float) -> str:
    candidates = []
    for record in records:
        x_pos, y_pos = centre(record)
        value = numeric(record["text"])
        if value is not None and x_min <= x_pos < x_max and abs(y_pos - y) <= 12:
            candidates.append((abs(y_pos - y), value))
    return min(candidates)[1] if candidates else ""


def parse_page(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["records"]
    code_records = []
    for record in records:
        code = normalise_code(record["text"])
        x_pos, y_pos = centre(record)
        if code and 180 <= x_pos <= 340:
            code_records.append((y_pos, code, record))
    code_records.sort()

    rows = []
    for index, (y_pos, code, _) in enumerate(code_records):
        next_y = code_records[index + 1][0] if index + 1 < len(code_records) else 1060
        description_parts = []
        for record in records:
            x_desc, y_desc = centre(record)
            if 300 <= x_desc < 620 and y_pos - 9 <= y_desc < next_y - 7:
                if normalise_code(record["text"]):
                    continue
                description_parts.append((y_desc, x_desc, record["text"].strip()))
        description_parts.sort()
        description = " ".join(part for _, _, part in description_parts).strip()
        description = re.sub(r"\s+", " ", description)

        unit_candidates = []
        for record in records:
            x_unit, y_unit = centre(record)
            if 615 <= x_unit < 660 and abs(y_unit - y_pos) <= 12:
                unit_candidates.append((abs(y_unit - y_pos), record["text"].strip()))
        unit = min(unit_candidates)[1] if unit_candidates else ""

        rows.append(
            {
                "code": code,
                "description": description,
                "heading_code": code[:4],
                "quantity_unit": unit,
                "import_duty": nearest_value(records, 660, 720, y_pos),
                "import_vat": nearest_value(records, 720, 785, y_pos),
                "import_excise": nearest_value(records, 785, 850, y_pos),
                "export_duty": "",
                "nhil_rate": "",
                "source_page": payload["page"],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ocr_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    rows = []
    for path in sorted(
        args.ocr_dir.glob("page-*.json"),
        key=lambda item: int(item.stem.split("-")[-1]),
    ):
        rows.extend(parse_page(path))
    rows.sort(key=lambda row: row["code"])
    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"parsed {len(rows)} rows from {len(list(args.ocr_dir.glob('page-*.json')))} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
