"""Extract the Act 1106 "new tariff lines" table.

Only the pages before the correlation table carry new lines; later pages list
obsolete 2017 codes, which must not be mistaken for current tariff lines.
Each entry is a serial number, a TSN, a wrapped description, an SU and an
import-duty rate, in that order.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pypdf

ENTRY_RE = re.compile(r"(?m)^\s*(\d{1,3})\.\s+(\d{4}\.\d{2}\.\d{2}\.\d{2})")
SU_TOKENS = {"kg", "u", "l", "m2", "m3", "m", "2u", "t", "g", "pa", "ct"}
RATE_RE = re.compile(r"(?<![\d.])(\d{1,2})(?![\d.])")
NOISE_RE = re.compile(
    r"New tariff lines in the 2022 edition of the ECOWAS CET Page \d+ of \d+"
    r"|SN\s+TSN\s+Commodity Description\s+SU\s+Import\s*Duty\s*\(%\)"
    r"|Import\s*Duty\s*\(%\)"
)


def clean(text: str) -> str:
    text = NOISE_RE.sub(" ", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = " ".join(text.split())
    return text.strip()


def parse_block(block: str) -> tuple[str, str, str]:
    """Return description, SU and duty for one entry's text after its TSN."""
    text = clean(block)
    duty = ""
    match = None
    for match in RATE_RE.finditer(text):
        pass
    if match:
        duty = match.group(1)
        text = text[: match.start()].rstrip()
    unit = ""
    tokens = text.split()
    if tokens and tokens[-1].lower().rstrip(".,") in SU_TOKENS:
        unit = tokens[-1].lower().rstrip(".,")
        text = " ".join(tokens[:-1])
    description = re.sub(r"^[-–—\s]+", "", text)
    description = re.sub(r"\s+([,.;:])", r"\1", description)
    return description, unit, duty


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--last-page", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reader = pypdf.PdfReader(str(args.pdf))
    text = "\n".join(
        reader.pages[index].extract_text() or ""
        for index in range(min(args.last_page, len(reader.pages)))
    )

    matches = list(ENTRY_RE.finditer(text))
    rows = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        description, unit, duty = parse_block(text[match.end() : stop])
        rows.append(
            {
                "sn": int(match.group(1)),
                "code": match.group(2).replace(".", ""),
                "description": description,
                "quantity_unit": unit,
                "import_duty": duty,
            }
        )

    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with_duty = sum(1 for row in rows if row["import_duty"])
    print(f"entries={len(rows)} with_duty={with_duty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
