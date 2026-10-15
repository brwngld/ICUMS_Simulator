"""Guardrails for the approved Unfold/system theme contract."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
THEME_SOURCE_ROOTS = (
    PROJECT_ROOT / "static" / "css",
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
    "rgba(120, 110, 220",
)


def _active_theme_sources():
    for root in THEME_SOURCE_ROOTS:
        for path in root.rglob("*"):
            if path.suffix in {".css", ".html", ".py"} and path.is_file():
                yield path


def test_active_theme_sources_do_not_reintroduce_legacy_palette_literals():
    findings = []
    for path in _active_theme_sources():
        source = path.read_text(encoding="utf-8").lower()
        for value in FORBIDDEN_LEGACY_VALUES:
            if value.lower() in source:
                findings.append(f"{path.relative_to(PROJECT_ROOT)}: {value}")
    assert findings == [], "Legacy theme literals found:\n" + "\n".join(findings)


def test_theme_controller_is_the_only_theme_state_writer():
    controller = (PROJECT_ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")
    shell = (PROJECT_ROOT / "static" / "js" / "app-shell.js").read_text(encoding="utf-8")

    assert "window.ICUMSThemeReady = true" in controller
    assert "localStorage.setItem(themeKey" not in shell
    assert "const themeKey" not in shell
