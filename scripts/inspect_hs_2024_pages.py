"""OCR selected pages from the scanned 2024 Ghana HS tariff for inspection."""

from __future__ import annotations

import sys
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    engine = RapidOCR()
    for raw_path in sys.argv[1:]:
        path = Path(raw_path)
        result, _ = engine(str(path))
        print(f"=== {path.name} ===")
        if not result:
            continue
        for item in result[:25]:
            print(item[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
