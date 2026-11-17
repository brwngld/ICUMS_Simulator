"""Extract tariff-line cells from the complete 2017 workbook for comparison."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from openpyxl import load_workbook


TSN_RE = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{2}$")
HEADING_RE = re.compile(r"^\d{2}\.\d{2}$")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    workbook = load_workbook(args.workbook, read_only=True, data_only=True)
    extracted = []
    headings: dict[str, str] = {}
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        header = None
        for row_index, row in enumerate(rows[:8]):
            for column_index, value in enumerate(row):
                if clean(value).upper() == "TSN":
                    header = (row_index, column_index)
                    break
            if header:
                break
        if not header:
            continue

        header_row, tsn_column = header
        labels = [clean(value).upper() for value in rows[header_row]]
        description_column = next(
            (i for i, label in enumerate(labels) if "COMMODITY" in label), None
        )
        unit_column = next((i for i, label in enumerate(labels) if label == "SU"), None)
        duty_column = next(
            (i for i, label in enumerate(labels) if label in {"CET ID", "IMPORT DUTY"}),
            None,
        )
        vat_column = next((i for i, label in enumerate(labels) if label == "VAT"), None)
        excise_column = next(
            (i for i, label in enumerate(labels) if label in {"IE", "IMPORT EXCISE"}),
            None,
        )

        def value_at(row: tuple, column: int | None) -> str:
            return clean(row[column]) if column is not None and column < len(row) else ""

        for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
            heading_cell = value_at(row, 0)
            if HEADING_RE.fullmatch(heading_cell):
                heading_text = value_at(row, description_column)
                if heading_text:
                    headings.setdefault(heading_cell.replace(".", ""), heading_text)
            dotted = value_at(row, tsn_column)
            if not TSN_RE.fullmatch(dotted):
                continue
            code = dotted.replace(".", "")
            extracted.append(
                {
                    "code": code,
                    "description": value_at(row, description_column),
                    "quantity_unit": value_at(row, unit_column),
                    "import_duty": value_at(row, duty_column),
                    "import_vat": value_at(row, vat_column),
                    "import_excise": value_at(row, excise_column),
                    "sheet": sheet.title,
                    "row": row_number,
                }
            )

    args.output.write_text(
        json.dumps(extracted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    headings_path = args.output.with_suffix(".headings.json")
    headings_path.write_text(
        json.dumps(headings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"extracted={len(extracted)} unique={len({row['code'] for row in extracted})}")
    print(f"headings={len(headings)} -> {headings_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
