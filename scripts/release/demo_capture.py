"""Shared helpers for screenshot scripts that capture the isolated ARIA demo."""

from __future__ import annotations

from pathlib import Path
import re
import tempfile

from PIL import Image
from playwright.sync_api import Locator, Page


SAFE_PATTERNS = (
    re.compile(r"\b172\.31\.\d{1,3}\.\d{1,3}\b"),
    re.compile(r"\b[a-z0-9.-]+\.lan\b", re.I),
    re.compile(r"\b[a-z0-9.-]+\.black(?:\.[a-z0-9.-]+)?\b", re.I),
    re.compile(r"/(?:home|Users)/(?!user\b|aria\b|app\b)[^/\s<]+"),
    re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
)
MAX_BYTES = 400_000


def login(page: Page, base: str, username: str, password: str) -> None:
    page.goto(base + "/login", wait_until="domcontentloaded")
    page.locator("#login-username").fill(username)
    page.locator("#login-password").fill(password)
    confirm = page.locator("#login-password-confirm")
    if confirm.count():
        confirm.fill(password)
    page.locator("form.login-form button[type=submit]").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)


def safe_source(page: Page, label: str) -> None:
    text = page.locator("body").inner_text()
    findings = [pattern.pattern for pattern in SAFE_PATTERNS if pattern.search(text)]
    if findings:
        raise RuntimeError(f"unsafe rendered demo source for {label}: {findings}")


def focus(locator: Locator | None) -> None:
    if locator is None:
        return
    locator.scroll_into_view_if_needed()
    locator.evaluate("node => node.scrollIntoView({block: 'center', inline: 'nearest'})")


def capture(page: Page, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".png") as handle:
        page.screenshot(path=handle.name, full_page=False)
        with Image.open(handle.name) as image:
            image.convert("RGB").save(target, "WEBP", quality=78, method=6)
    size = target.stat().st_size
    if size > MAX_BYTES:
        with Image.open(target) as image:
            image.convert("RGB").save(target, "WEBP", quality=64, method=6)
        size = target.stat().st_size
    if size > MAX_BYTES:
        raise RuntimeError(f"screenshot exceeds 400 KB: {target} ({size})")
    return size
