#!/usr/bin/env python3
"""Crawl the authenticated demo in both languages and reject private content."""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from playwright.sync_api import Error as PlaywrightError, sync_playwright


FORBIDDEN = (
    re.compile(r"\b172\.31\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b[a-z0-9.-]+\.lan\b", re.I),
    re.compile(r"\b[a-z0-9.-]+\.black(?:\.[a-z0-9.-]+)?\b", re.I),
    re.compile(r"/(?:home/fischerman|Users/[^/\s<]+)"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._~+/-]{8,})\b", re.I),
    re.compile(r"(?i)(?:api[_ -]?key|authorization|secret|token|password)\s*[:=]\s*(?!\[?redacted\]?)[^\s<]{8,}"),
)
KEY_PATHS = (
    "/", "/stats", "/connections", "/config/connections/rss",
    "/memories/activity-journal", "/jobs/panel", "/memories/auto-memory", "/memories",
)


def _scannable_html(html: str) -> str:
    """Keep rendered data and attributes, but exclude shipped executable source."""
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script\s*>", "", html, flags=re.I | re.S)
    return re.sub(r"<style\b[^>]*>.*?</style\s*>", "", without_scripts, flags=re.I | re.S)


def _language_path(path: str, language: str) -> str:
    parsed = urlparse(path)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["lang"] = language
    return urlunparse(("", "", parsed.path or "/", parsed.params, urlencode(query), parsed.fragment))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--output", type=Path, default=Path("test-results/demo-screenshots"))
    parser.add_argument("--username", default="demo-admin")
    parser.add_argument("--password", default="aria-demo-access")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    origin = urlparse(base).netloc
    args.output.mkdir(parents=True, exist_ok=True)
    findings: list[str] = []
    visited_total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for language in ("de", "en"):
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            page.set_default_navigation_timeout(60_000)
            page.goto(base + "/login", wait_until="domcontentloaded")
            page.locator("#login-username").fill(args.username)
            page.locator("#login-password").fill(args.password)
            confirm = page.locator("#login-password-confirm")
            if confirm.count():
                confirm.fill(args.password)
            page.locator("form.login-form button[type=submit]").click()
            page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)
            queue = deque(KEY_PATHS)
            visited: set[str] = set()
            while queue and len(visited) < 180:
                path = queue.popleft().split("#", 1)[0]
                if path in visited or "{" in path:
                    continue
                visited.add(path)
                try:
                    response = page.goto(base + _language_path(path, language), wait_until="domcontentloaded")
                except PlaywrightError as exc:
                    if "Download is starting" in str(exc):
                        # Export endpoints are files, not rendered demo pages.
                        continue
                    raise
                if response is None or response.status >= 500:
                    findings.append(f"{language} {path}: HTTP {response.status if response else 'none'}")
                    continue
                html = _scannable_html(page.content())
                for pattern in FORBIDDEN:
                    match = pattern.search(html)
                    if match:
                        findings.append(f"{language} {path}: {pattern.pattern} -> {match.group(0)[:80]}")
                for href in page.locator("a[href]").evaluate_all("els => els.map(el => el.getAttribute('href'))"):
                    if not href or href.startswith(("#", "mailto:", "javascript:")):
                        continue
                    absolute = urljoin(base + path, href)
                    parsed = urlparse(absolute)
                    if parsed.path in {"/logout", "/login"}:
                        continue
                    if parsed.netloc == origin and parsed.path not in visited and "{" not in parsed.path:
                        queue.append(parsed.path + ("?" + parsed.query if parsed.query else ""))
            visited_total += len(visited)
            for theme in ("matrix", "paper"):
                for path in KEY_PATHS:
                    page.goto(base + _language_path(path, language), wait_until="domcontentloaded")
                    # Theme selection is normally persisted through the admin
                    # config. For the read-only public screenshot pass, apply
                    # the same body token directly without mutating the demo.
                    page.evaluate("theme => { document.body.dataset.theme = theme; }", theme)
                    slug = "chat" if path == "/" else path.strip("/").replace("/", "-")
                    page.screenshot(path=args.output / f"{language}-{theme}-{slug}.png", full_page=True)
            context.close()
        browser.close()
    if findings:
        raise SystemExit("Demo public-safety scan failed:\n" + "\n".join(findings))
    print(f"demo_public_safety=passed pages={visited_total} screenshots={len(tuple(args.output.glob('*.png')))}")


if __name__ == "__main__":
    main()
