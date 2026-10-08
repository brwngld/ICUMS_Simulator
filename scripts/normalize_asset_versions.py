"""Normalize the cache-buster versions of the shared CSS files across all templates."""
import pathlib
import re

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent / "templates"
VERSIONS = {
    "simulator-portal.css": "20261010-1",
    "cargo-page.css": "20261010-1",
    "ucr-create.css": "20261010-1",
    "ucr-document-codes.js": "20261010-1",
    "application-form.js": "20261010-1",
    "app-shell.js": "20261010-1",
    "ucr-create.js": "20261010-1",
    "ucr-amend.js": "20261010-1",
}
changed = 0
for path in TEMPLATE_DIR.rglob("*.html"):
    text = original = path.read_text(encoding="utf-8")
    for asset, version in VERSIONS.items():
        text = re.sub(
            "(" + re.escape(asset) + r"' %}\?v=)[0-9-]+",
            lambda m: m.group(1) + version,
            text,
        )
    if text != original:
        path.write_text(text, encoding="utf-8")
        changed += 1
print("templates updated:", changed)
for asset, version in VERSIONS.items():
    remaining = set()
    for path in TEMPLATE_DIR.rglob("*.html"):
        remaining.update(re.findall(re.escape(asset) + r"\?v=([0-9-]+)", path.read_text(encoding="utf-8")))
    print(asset, "->", sorted(remaining))
