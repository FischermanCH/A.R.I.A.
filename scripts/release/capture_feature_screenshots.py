#!/usr/bin/env python3
"""Capture the website feature screenshots exclusively from the isolated demo.

Reads docs/website/features.json and writes
  docs/assets/screenshots/features/<lang>/<feature-id>.webp
  docs/assets/screenshots/themes/<lang>/<theme-id>.webp
Every image passes the public-safety check. All images are rendered into a
temporary directory first and only moved into place when every shot passed.

Per-shot keys: route, fill ({selector: {"de": ..., "en": ...}}), click
(selector list, in order), wait_for, focus (scrollIntoView center),
viewport ([w, h], default 1280x900), frame ("shell" = default for features,
"page" = whole viewport incl. background, default for the theme gallery).

Feature shots ("shell"): only the A.R.I.A. window (.app-shell) is captured,
cropped to what is visible in the viewport, page background transparent,
stored as WebP with alpha channel.

Run against the demo (scripts/demo/reset.sh):
  .venv/bin/python scripts/release/capture_feature_screenshots.py
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any
from urllib.parse import urlencode

from PIL import Image
from playwright.sync_api import Page, sync_playwright

from demo_capture import capture, focus, login, safe_source


LANGS = ("de", "en")
DEFAULT_VIEWPORT = (1280, 900)
FEATURE_THEME = "matrix"
SHELL_SELECTOR = ".app-shell"
SHELL_MARGIN = 10  # px Rand um das Fenster (transparent)
MAX_BYTES = 400_000
# Seitenhintergrund (Farbe, Hintergrundbild) für die Fenster-Aufnahme ausblenden.
TRANSPARENT_CSS = """
html, body { background: transparent !important; background-image: none !important; }
html::before, html::after, body::before, body::after { display: none !important; }
"""


def _capture_shell(page: Page, target: Path) -> int:
    """Only the A.R.I.A. window, cropped to the viewport, transparent background, WebP with alpha."""
    style = page.add_style_tag(content=TRANSPARENT_CSS)
    try:
        page.wait_for_timeout(150)
        box = page.locator(SHELL_SELECTOR).first.bounding_box()
        if not box:
            raise RuntimeError(f"{SHELL_SELECTOR} not visible")
        vp = page.viewport_size or {"width": DEFAULT_VIEWPORT[0], "height": DEFAULT_VIEWPORT[1]}
        x0 = max(0.0, box["x"] - SHELL_MARGIN)
        y0 = max(0.0, box["y"] - SHELL_MARGIN)
        x1 = min(float(vp["width"]), box["x"] + box["width"] + SHELL_MARGIN)
        y1 = min(float(vp["height"]), box["y"] + box["height"] + SHELL_MARGIN)
        png = page.screenshot(clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}, omit_background=True)
    finally:
        style.evaluate("node => node.remove()")
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(png)) as image:
        rgba = image.convert("RGBA")
        for quality in (80, 70, 60):
            rgba.save(target, "WEBP", quality=quality, method=6)
            if target.stat().st_size <= MAX_BYTES:
                break
    size = target.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f"screenshot exceeds 400 KB: {target} ({size})")
    return size


def _goto(page: Page, base: str, route: str, lang: str) -> None:
    join = "&" if "?" in route else "?"
    page.goto(f"{base}{route}{join}{urlencode({'lang': lang})}", wait_until="networkidle")


def _appearance(page: Page, base: str) -> tuple[str, str]:
    page.goto(base + "/config/appearance", wait_until="domcontentloaded")
    return (
        page.locator("[data-theme-select]").input_value(),
        page.locator("[data-background-select]").input_value(),
    )


def _set_appearance(page: Page, base: str, theme: str, background: str = "") -> None:
    """Save theme and background through the real appearance form."""
    page.goto(base + "/config/appearance", wait_until="domcontentloaded")
    if not background:
        preset = page.locator(f"[data-appearance-preset] option[data-theme='{theme}']").first
        if not preset.count():
            raise RuntimeError(f"no appearance preset for theme {theme}")
        background = str(preset.get_attribute("data-background") or "")
    page.locator("[data-theme-select]").select_option(theme)
    page.locator("[data-background-select]").select_option(background)
    page.locator("form.editor-form button[type=submit]").click()
    page.wait_for_load_state("networkidle")
    page.goto(base + "/", wait_until="domcontentloaded")
    body = page.locator("body")
    if body.get_attribute("data-theme") != theme or body.get_attribute("data-background") != background:
        raise RuntimeError(f"appearance not applied: {theme}/{background}")


def _admin_mode(page: Page, base: str, enabled: bool | None = None) -> bool:
    """Return the current admin mode; switch it when ``enabled`` is given."""
    page.goto(base + "/config/admin-mode", wait_until="domcontentloaded")
    box = page.locator("input[type=checkbox][name=debug_mode]")
    current = box.is_checked()
    if enabled is not None and enabled != current:
        box.set_checked(enabled)
        box.locator("xpath=ancestor::form").locator("button[type=submit]").click()
        page.wait_for_load_state("networkidle")
    return current


def _check_demo_state(page: Page, base: str) -> None:
    """Fail early when the prepared demo state from scripts/demo/seed_features.py is missing."""
    page.goto(base + "/config/security", wait_until="domcontentloaded")
    guardrail = page.locator("option[value='demo-safe-maintenance']").count()
    page.goto(base + "/", wait_until="domcontentloaded")
    update = page.locator(".topnav-update-indicator").count()
    if not guardrail or not update:
        raise SystemExit(
            "Demo-Zustand unvollständig (Guardrail-Profil oder «Update verfügbar» fehlt). "
            "scripts/demo/reset.sh ausführen und während der Aufnahme kein pytest laufen lassen "
            "(tests/test_alpha999_demo_instance.py schreibt demo/generated neu)."
        )


def _shoot(page: Page, base: str, shot: dict[str, Any], lang: str, target: Path, label: str, frame: str = "shell") -> int:
    width, height = shot.get("viewport") or DEFAULT_VIEWPORT
    page.set_viewport_size({"width": int(width), "height": int(height)})
    _goto(page, base, str(shot["route"]), lang)
    for selector, value in (shot.get("fill") or {}).items():
        text = value.get(lang, "") if isinstance(value, dict) else str(value)
        page.locator(selector).first.evaluate("(node, text) => { node.value = text; }", text)
    for selector in shot.get("click") or []:
        page.locator(selector).first.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(400)
    if shot.get("wait_for"):
        page.locator(str(shot["wait_for"])).first.wait_for(state="visible", timeout=20_000)
    if shot.get("focus"):
        locator = page.locator(str(shot["focus"])).first
        locator.wait_for(state="visible", timeout=10_000)
        focus(locator)
    page.wait_for_timeout(600)
    safe_source(page, label)
    if str(shot.get("frame", frame)) == "shell":
        return _capture_shell(page, target)
    return capture(page, target)


def _prune(directory: Path, keep: set[str]) -> list[Path]:
    removed = []
    if directory.is_dir():
        for path in directory.glob("*.webp"):
            if path.stem not in keep:
                path.unlink()
                removed.append(path)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--content", type=Path, default=Path("docs/website/features.json"))
    parser.add_argument("--output", type=Path, default=Path("docs/assets/screenshots"))
    parser.add_argument("--username", default="demo-admin")
    parser.add_argument("--password", default="aria-demo-access")
    parser.add_argument("--only", nargs="*", default=[], help="nur diese Feature-/Theme-IDs (keine Bereinigung)")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    content = json.loads(args.content.read_text(encoding="utf-8"))
    features = [f for f in content.get("features", []) if not f.get("hidden") and f.get("shot")]
    gallery = content.get("gallery") or {}
    themes = [str(t) for t in gallery.get("themes", [])] if gallery.get("shot") else []
    if args.only:
        features = [f for f in features if f["id"] in args.only]
        themes = [t for t in themes if t in args.only]
    rows: list[tuple[str, str, str, int]] = []

    with tempfile.TemporaryDirectory(prefix="aria-feature-shots-") as tmp:
        staging = Path(tmp)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": DEFAULT_VIEWPORT[0], "height": DEFAULT_VIEWPORT[1]})
            page = context.new_page()
            login(page, base, args.username, args.password)
            _check_demo_state(page, base)
            original_theme, original_background = _appearance(page, base)
            original_admin = _admin_mode(page, base, True)
            try:
                _set_appearance(page, base, FEATURE_THEME)
                for lang in LANGS:
                    for feature in features:
                        name = f"{feature['id']}.webp"
                        size = _shoot(page, base, feature["shot"], lang, staging / "features" / lang / name, f"{lang}/{feature['id']}")
                        rows.append(("features", feature["id"], lang, size))
                for theme in themes:
                    _set_appearance(page, base, theme)
                    for lang in LANGS:
                        size = _shoot(page, base, gallery["shot"], lang, staging / "themes" / lang / f"{theme}.webp", f"{lang}/theme-{theme}", frame="page")
                        rows.append(("themes", theme, lang, size))
                _check_demo_state(page, base)
            finally:
                _set_appearance(page, base, original_theme, original_background)
                _admin_mode(page, base, original_admin)
                context.close()
                browser.close()

        for kind, ident, lang, _ in rows:
            target = args.output / kind / lang / f"{ident}.webp"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staging / kind / lang / f"{ident}.webp"), target)

    removed: list[Path] = []
    if not args.only:
        for lang in LANGS:
            removed += _prune(args.output / "features" / lang, {f["id"] for f in features})
            removed += _prune(args.output / "themes" / lang, set(themes))
    for kind, ident, lang, size in rows:
        print(f"{kind:8} {ident:24} {lang}  {size / 1024:6.1f} KB")
    for path in removed:
        print(f"entfernt {path}")
    print(f"feature_screenshots=passed count={len(rows)} max_bytes={max((r[3] for r in rows), default=0)}")


if __name__ == "__main__":
    main()
