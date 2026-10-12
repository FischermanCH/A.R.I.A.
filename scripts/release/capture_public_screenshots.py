#!/usr/bin/env python3
"""Capture the public screenshot set exclusively from the isolated demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode

from PIL import Image
from playwright.sync_api import Locator, Page, sync_playwright


SAFE_PATTERNS = (
    re.compile(r"\b172\.31\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b[a-z0-9.-]+\.lan\b", re.I),
    re.compile(r"\b[a-z0-9.-]+\.black(?:\.[a-z0-9.-]+)?\b", re.I),
    re.compile(r"/(?:home|Users)/(?!user\b|aria\b|app\b)[^/\s<]+"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)


def _login(page: Page, base: str, username: str, password: str) -> None:
    page.goto(base + "/login", wait_until="domcontentloaded")
    page.locator("#login-username").fill(username)
    page.locator("#login-password").fill(password)
    confirm = page.locator("#login-password-confirm")
    if confirm.count():
        confirm.fill(password)
    page.locator("form.login-form button[type=submit]").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)


def _safe_source(page: Page, label: str) -> None:
    text = page.locator("body").inner_text()
    findings = [pattern.pattern for pattern in SAFE_PATTERNS if pattern.search(text)]
    if findings:
        raise RuntimeError(f"unsafe rendered demo source for {label}: {findings}")


def _focus(locator: Locator | None) -> None:
    if locator is None:
        return
    locator.scroll_into_view_if_needed()
    locator.evaluate("node => node.scrollIntoView({block: 'center', inline: 'nearest'})")


def _capture(page: Page, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        page.screenshot(path=handle.name, full_page=False)
        with Image.open(handle.name) as image:
            image.convert("RGB").save(target, "WEBP", quality=78, method=6)
    size = target.stat().st_size
    if size > 400_000:
        with Image.open(target) as image:
            image.convert("RGB").save(target, "WEBP", quality=64, method=6)
        size = target.stat().st_size
    if size > 400_000:
        raise RuntimeError(f"screenshot exceeds 400 KB: {target} ({size})")
    return size


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
