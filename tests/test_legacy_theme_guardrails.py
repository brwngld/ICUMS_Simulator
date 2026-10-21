"""Guardrails for the approved Unfold/system theme contract."""

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEME_SOURCE_ROOTS = (
    PROJECT_ROOT / "static",
    PROJECT_ROOT / "templates",
    PROJECT_ROOT / "core",
)
FORBIDDEN_LEGACY_VALUES = (
    "#5145cd",
    "#5a3fc0",
    "#412a9a",
    "#9b8cff",
    "#bdb3ff",
    "#3d3a7a",
    "#262254",
    "rgba(120, 110, 220",
)
#: Three of the forbidden colours stayed live for six days after the hex sweep
#: because they were written as rgb() triples, which a literal search cannot see.
RGB_TRIPLE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _forbidden_rgb_forms():
    forms = {}
    for value in FORBIDDEN_LEGACY_VALUES:
        if not value.startswith("#") or len(value) != 7:
            continue
        digits = value.lstrip("#")
        forms[tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))] = value
    return forms


def _active_theme_sources():
    for root in THEME_SOURCE_ROOTS:
        for path in root.rglob("*"):
            if path.suffix in {".css", ".html", ".js", ".py"} and path.is_file():
                yield path


def test_active_theme_sources_do_not_reintroduce_legacy_palette_literals():
    rgb_forms = _forbidden_rgb_forms()
    findings = []
    for path in _active_theme_sources():
        relative = path.relative_to(PROJECT_ROOT)
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            for value in FORBIDDEN_LEGACY_VALUES:
                if value.lower() in lowered:
                    findings.append(f"{relative}:{number}: {value}")
            for match in RGB_TRIPLE.finditer(line):
                triple = tuple(int(group) for group in match.groups())
                if triple in rgb_forms:
                    findings.append(f"{relative}:{number}: {rgb_forms[triple]} written as rgb()")
    assert findings == [], "Legacy theme literals found:\n" + "\n".join(findings)


def test_theme_controller_is_the_only_theme_state_writer():
    controller = (PROJECT_ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")
    assert "window.ICUMSThemeReady = true" in controller

    # The pre-Unfold shell kept a second controller that wrote its own `icums-theme`
    # key; nothing but theme.js may touch either key now.
    writers = []
    for path in sorted((PROJECT_ROOT / "static" / "js").glob("*.js")):
        if path.name == "theme.js":
            continue
        if re.search(r"""["'](?:adminTheme|icums-theme)["']""", path.read_text(encoding="utf-8")):
            writers.append(str(path.relative_to(PROJECT_ROOT)))
    assert writers == [], "Scripts writing theme state: " + ", ".join(writers)
