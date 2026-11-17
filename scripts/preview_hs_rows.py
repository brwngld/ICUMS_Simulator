"""Render a montage of scan rows for eyeball checks.

Usage: preview_hs_rows.py CODE [CODE ...] --rows ROWS.json --output IMAGE.png

Each row is cropped from a 4x render of the 2024 schedule page that holds the
code, with the printed line number and page stamped beside it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import build_hs_dataset_update as hs  # noqa: E402

K = 4.0 / 1.529
CROP = (140, 860)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("codes", nargs="+")
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--ocr-dir", type=Path, default=Path("output/hs2024-ocr"))
    parser.add_argument("--codes-dir", type=Path, default=Path("output/hs2024-codes"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = {row["code"]: row for row in json.loads(args.rows.read_text(encoding="utf-8"))}
    pdf = pdfium.PdfDocument(str(args.pdf))
    tiles = []
    for code in args.codes:
        row = rows.get(code)
        if row is None or row.get("source_page") is None:
            print(f"{code}: no scan page")
            continue
        page = row["source_page"]
        ocr = json.loads((args.ocr_dir / f"page-{page}.json").read_text(encoding="utf-8"))
        repair_path = args.codes_dir / f"page-{page}.json"
        repair = (
            json.loads(repair_path.read_text(encoding="utf-8"))
            if repair_path.exists()
            else None
        )
        anchors = hs.page_anchors(page, ocr, repair)
        found = [anchor for anchor in anchors if anchor["code"] == code]
        if not found:
            print(f"{code}: no anchor on page {page}")
            continue
        y = found[0]["y"]
        image = pdf[page - 1].render(scale=4.0).to_pil().convert("RGB")
        crop = image.crop(
            (int(CROP[0] * K), int((y - 26) * K), int(CROP[1] * K), int((y + 34) * K))
        )
        tiles.append((f"{code}  page {page}  y {y:.0f}", crop))

    if not tiles:
        return 1
    width = max(tile.width for _label, tile in tiles) + 360
    height = sum(tile.height + 26 for _label, tile in tiles)
    montage = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(montage)
    offset = 0
    for label, tile in tiles:
        draw.text((6, offset + 10), label, fill="black")
        montage.paste(tile, (340, offset))
        offset += tile.height
        draw.line((0, offset, width, offset), fill="red")
        offset += 26
    montage.save(args.output)
    print(args.output, montage.size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
