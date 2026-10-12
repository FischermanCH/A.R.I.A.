from __future__ import annotations

import hashlib
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
STYLE = ROOT / "aria/static/style.css"
THEMES = (
    "matrix",
    "crt-amber",
    "cyberpunk",
    "cyberpunk-neo",
    "deep-space",
    "harbor",
    "nyan-cat",
    "paper",
    "pixel",
    "puke-unicorn",
    "sunset",
)


def test_alpha993_release_metadata_and_public_pin() -> None:
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    release_meta = (ROOT / "aria/modules/release_update/release_meta.py").read_text(encoding="utf-8")
    assert 'DEFAULT_RELEASE_LABEL = "0.1.0-alpha1007"' in release_meta
    assert "## 0.1.0-alpha996" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 0.1.0-alpha996" in (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8")
    assert "public release remains `0.1.0-alpha983`" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Fischerman.ch" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_all_theme_blocks_are_tokens_or_decorative_backgrounds_only() -> None:
    css = STYLE.read_text(encoding="utf-8")
    for theme in THEMES[1:]:
        selectors = re.findall(
            rf'body\[data-theme="{re.escape(theme)}"\]([^{{]*)\{{',
            css,
        )
        assert selectors, theme
        assert all(not suffix.strip() or suffix.strip() in {"::before", "::after"} for suffix in selectors), (
            theme,
            selectors,
        )


def test_roles_are_central_and_shape_tokens_are_not_theme_specific() -> None:
    css = STYLE.read_text(encoding="utf-8")
    for token in (
        "--ui-control-radius",
        "--ui-control-padding-y",
        "--ui-control-padding-x",
        "--ui-control-weight",
        "--ui-danger",
        "--ui-danger-contrast",
        "--ui-focus-ring",
    ):
        assert token in css
    secondary = re.search(r"\.ui-secondary-action,[^{]+\{([^}]*)", css, re.S)
    assert secondary
    assert "border:" in secondary.group(1)
    assert "background: var(" in secondary.group(1) or "background: transparent" in secondary.group(1)
    assert re.search(r"\.ui-primary-action\s*\{[^}]*background:", css, re.S)
    assert re.search(r"\.ui-tertiary-action", css)
    assert re.search(r"\.ui-danger-action", css)
    assert re.search(r"\.ui-tab", css)


def test_theme_linter_declares_r19_to_r24_and_report_contract() -> None:
    from aria.modules.config_ui.page_linter import THEME_RULE_IDS, lint_theme_snapshots

    assert THEME_RULE_IDS == tuple(f"R{number}" for number in range(19, 25))
    broken = {
        "theme": "paper",
        "path": "/config/connections/ssh/demo",
        "secondary": [{"border_contrast": 1.0, "filled": True, "plain_text": True}],
        "primary_per_section": [2],
        "primary_in_repeated_items": 1,
        "danger_inline": [{"redish": False, "filled": True}],
        "danger_final": [{"filled": False}],
        "tabs": [{"filled": True}],
        "contrast_failures": ["secondary border"],
        "geometry_mismatches": ["secondary radius"],
    }
    result = lint_theme_snapshots([broken])
    assert set(THEME_RULE_IDS) <= {row.rule for row in result.blocking_findings}
    scenarios = (ROOT / "tests/e2e/scenarios.py").read_text(encoding="utf-8")
    assert "theme-linter-0.1.0-alpha998" in scenarios


def test_alpha993_e2e_covers_all_themes_and_memory_browser_identity() -> None:
    scenarios = (ROOT / "tests/e2e/scenarios.py").read_text(encoding="utf-8")
    assert "R19-R24" in scenarios
    assert "theme-linter-0.1.0-alpha998" in scenarios
    for theme in THEMES:
        assert f'"{theme}"' in scenarios
    assert hashlib.sha256(
        (ROOT / "aria/templates/_memory_drilldown_browser.html").read_bytes()
    ).hexdigest() == "e91e7164266e0452a10622c7009075800b8ee6b4db64de3ddc17b972bfdfcc1c"
