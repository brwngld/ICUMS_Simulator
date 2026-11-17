"""Re-read the TSN column of the 2024 scan at higher resolution.

The whole-page OCR is reliable for descriptions and rates but occasionally
turns a tariff line into digit noise (9011.10.00.00 was read as 0000011106).
Cropping the TSN column and enlarging it before OCR recovers those lines, so
the 2024 comparison does not depend on one pass being perfect.

Writes one JSON file per page with the code, its y position and confidence.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image
from rapidocr_onnxruntime import RapidOCR

#: The TSN column in page-image coordinates, measured from the whole-page OCR.
COLUMN = (215, 195, 315, 1200)
SCALE = 8
BAND = 150
CODE_RE = re.compile(r"(?<!\d)(\d{4})[.,](\d{2})[.,](\d{2})[.,](\d{2})(?!\d)")


def normalise(text: str) -> str | None:
    cleaned = text.replace("O", "0").replace("o", "0").replace(" ", "").replace(",", ".")
    cleaned = cleaned.replace("S", "5").replace("I", "1").replace("l", "1")
    match = CODE_RE.search(cleaned)
    return "".join(match.groups()) if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--first", type=int)
    parser.add_argument("--last", type=int)
    parser.add_argument(
        "--pages", help="comma-separated page numbers, instead of --first/--last"
    )
    args = parser.parse_args()

    if args.pages:
        pages = [int(value) for value in args.pages.split(",") if value.strip()]
    elif args.first is not None and args.last is not None:
        pages = list(range(args.first, args.last + 1))
    else:
        parser.error("give --pages, or both --first and --last")

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()

    for page in pages:
        target = args.output_dir / f"page-{page}.json"
        if target.exists():
            print(f"page {page}: cached", flush=True)
            continue
        source = args.image_dir / f"page-{page}.jpg"
        if not source.exists():
            print(f"page {page}: missing image", flush=True)
            return 2

        with Image.open(source) as image:
            records = []
            left, top, right, bottom = COLUMN
            for band_top in range(top, bottom, BAND):
                band_bottom = min(band_top + BAND, bottom)
                crop = image.crop((left, band_top, right, band_bottom))
                crop = crop.resize(
                    (crop.width * SCALE, crop.height * SCALE), Image.LANCZOS
                )
                # A white margin stops the recogniser clipping text at the border.
                framed = Image.new(
                    "RGB", (crop.width + 80, crop.height + 80), "white"
                )
                framed.paste(crop, (40, 40))

                result, _elapsed = engine(framed)
                for box, text, confidence in result or []:
                    code = normalise(text)
                    if code is None:
                        continue
                    x_center = sum(point[0] for point in box) / 4
                    y_center = (sum(point[1] for point in box) / 4 - 40) / SCALE
                    records.append(
                        {
                            "code": code,
                            "x": round(x_center, 1),
                            "y": round(y_center + band_top, 1),
                            "confidence": confidence,
                        }
                    )
        records.sort(key=lambda record: record["y"])
        target.write_text(
            json.dumps({"page": page, "records": records}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(f"page {page}: {len(records)} codes", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
