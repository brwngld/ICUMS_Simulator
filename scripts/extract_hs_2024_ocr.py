"""Extract resumable OCR JSON from selected scanned 2024 Ghana HS pages.

This is an audit/import preparation utility. It does not touch Django or the
database. Each page is written independently so an interrupted run can resume.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR()

    for page in range(args.first, args.last + 1):
        source = args.image_dir / f"page-{page}.jpg"
        target = args.output_dir / f"page-{page}.json"
        if target.exists():
            print(f"page {page}: cached", flush=True)
            continue
        if not source.exists():
            print(f"page {page}: missing image", flush=True)
            return 2

        result, elapsed = engine(str(source))
        records = []
        for box, text, confidence in result or []:
            records.append(
                {"box": box, "text": text, "confidence": confidence}
            )
        target.write_text(
            json.dumps(
                {"page": page, "elapsed": elapsed, "records": records},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"page {page}: {len(records)} records", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
