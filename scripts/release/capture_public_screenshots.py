#!/usr/bin/env python3
"""Capture the public screenshot set exclusively from the isolated demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

from demo_capture import capture as _capture, focus as _focus, login as _login, safe_source as _safe_source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--output", type=Path, default=Path("docs/assets/screenshots"))
    parser.add_argument("--username", default="demo-admin")
    parser.add_argument("--password", default="aria-demo-access")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    manifest: list[dict[str, object]] = []
    views = (
        ("chat-tool-table", "/", "#messages .msg-assistant:has(table)"),
        ("chat-job-completion", "/", "#messages .msg-assistant[data-agent-job-event-key='terminal']"),
        ("chat-confirmation", "/", "#messages .msg-assistant[data-agent-job-state='demo_confirmation_preview']"),
        ("statistics", "/stats", "[data-stats-section='health']"),
        ("connections", "/connections", ".connection-profile-card"),
        ("rss-categories", "/config/connections/rss", ".rss-category-group"),
        ("activity-journal", "/memories/activity-journal", ".activity-journal-entry"),
        ("agent-jobs", "/jobs/panel", "[data-agent-job-card]"),
        ("personal-model", "/memories/auto-memory", ".learning-ledger-item"),
        ("memory-browser", "/memories", ".memory-domain-shell"),
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for language in ("de", "en"):
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            _login(page, base, args.username, args.password)
            for theme in ("matrix", "paper"):
                for slug, path, selector in views:
                    join = "&" if "?" in path else "?"
                    page.goto(
                        f"{base}{path}{join}{urlencode({'lang': language})}",
                        wait_until="domcontentloaded",
                    )
                    page.evaluate("theme => { document.body.dataset.theme = theme; }", theme)
                    page.wait_for_timeout(100)
                    locator = page.locator(selector).first
                    if locator.count():
                        _focus(locator)
                    _safe_source(page, f"{language}/{theme}/{slug}")
                    target = args.output / language / f"{theme}-{slug}.webp"
                    size = _capture(page, target)
                    manifest.append({
                        "language": language, "theme": theme, "view": slug,
                        "path": target.resolve().relative_to(Path.cwd().resolve()).as_posix(),
                        "bytes": size, "viewport": "1280x800", "source": "aria-demo",
                    })
            context.close()
        browser.close()
    manifest_path = args.output / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": 1, "screenshots": manifest}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"public_screenshots=passed count={len(manifest)} max_bytes={max(row['bytes'] for row in manifest)}")


if __name__ == "__main__":
    main()
