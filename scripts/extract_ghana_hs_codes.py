"""Extract Ghana Customs HS tariff rows from the supplied reference PDF."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber


def clean(value):
    return " ".join((value or "").replace("\n", " ").split())


def extract(source: Path):
    records = {}
    with pdfplumber.open(source) as document:
        for page_number, page in enumerate(document.pages, 1):
            tables = page.extract_tables() or []
            candidates = [table for table in tables if table and len(table[0]) >= 9]
            if not candidates:
                continue
            table = max(candidates, key=len)
            for row in table[1:]:
                if len(row) < 9:
                    continue
                code = re.sub(r"\D", "", row[1] or "")
                if len(code) != 10:
                    continue
                record = {
                    "code": code,
                    "description": clean(row[2]),
                    "heading_code": clean(row[3]),
                    "quantity_unit": clean(row[4]),
                    "import_duty": clean(row[5]),
                    "import_vat": clean(row[6]),
                    "import_excise": clean(row[7]),
                    "export_duty": clean(row[8]),
                    "nhil_rate": clean(row[9]) if len(row) > 9 else "",
                    "source_page": page_number,
                }
                if record["description"]:
                    records[code] = record
    return [records[code] for code in sorted(records)]


if __name__ == "__main__":
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    rows = extract(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(rows, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(rows)} unique HS codes to {destination}")
