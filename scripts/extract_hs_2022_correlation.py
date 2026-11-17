"""Extract the Act 1106 obsolete-to-replacement correlation table.

The last pages of the Act 1106 PDF list each discontinued 2017 tariff line and
the 2022 lines that replace it. The text is a linear stream, so the entries are
recovered by scanning codes in order: the code that follows a serial number is
the obsolete line, and every code before the next serial number replaces it.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pypdf

CODE_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}\.\d{2}")
ENTRY_RE = re.compile(r"(?<![\d.])(\d{1,3})\s+(\d{4}\.\d{2}\.\d{2}\.\d{2})(?![\d.])")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--first-page", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reader = pypdf.PdfReader(str(args.pdf))
    text = "\n".join(
        reader.pages[index].extract_text() or ""
        for index in range(args.first_page - 1, len(reader.pages))
    )
    text = text.replace("\u2013", "-").replace("\u2014", "-")

    spans = []
    for match in ENTRY_RE.finditer(text):
        spans.append(
            (
                {
                    "sn": int(match.group(1)),
                    "obsolete": match.group(2).replace(".", ""),
                    "replacements": [],
                },
                match.start(),
                match.end(),
            )
        )
    entries = []
    for index, (entry, _start, end) in enumerate(spans):
        stop = spans[index + 1][1] if index + 1 < len(spans) else len(text)
        entry["replacements"] = [
            code.replace(".", "") for code in CODE_RE.findall(text[end:stop])
        ]
        entries.append(entry)

    args.output.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"entries={len(entries)} replacements={sum(len(e['replacements']) for e in entries)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
