#!/usr/bin/env python3
"""Safari-like activity-journal date restoration gate for the isolated stack."""

from __future__ import annotations

import argparse

from playwright.sync_api import Error as PlaywrightError, sync_playwright


def _goto(page, url: str) -> None:  # noqa: ANN001
    """Tolerate WebKit's harmless post-commit navigation diagnostic."""

    try:
        page.goto(url, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        if "WebKit encountered an internal error" not in str(exc) or page.url != url:
            raise
        page.wait_for_selector("body", state="attached", timeout=5_000)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    base = args.url.rstrip("/")

    with sync_playwright() as playwright:
        for browser_name in ("webkit", "chromium"):
            browser = getattr(playwright, browser_name).launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()
            _goto(page, base + "/login")
            page.locator("#login-username").fill(args.username)
            page.locator("#login-password").fill(args.password)
            confirm = page.locator("#login-password-confirm")
            if confirm.count():
                confirm.fill(args.password)
            page.locator("form.login-form button[type=submit]").click()
            page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)

            storage_state = context.storage_state()
            journal = base + "/memories/activity-journal"
            _goto(page, journal)
            assert page.locator("#journal-period").input_value() == "all"
            assert not page.locator("#journal-custom-range").is_visible()
            assert not page.locator("#journal-since").is_visible()
            assert not page.locator("#journal-until").is_visible()
            _goto(page, base + "/stats")
            page.go_back(wait_until="domcontentloaded")
            assert page.locator("#journal-period").input_value() == "all"
            assert not page.locator("#journal-custom-range").is_visible()
            page.reload(wait_until="domcontentloaded")
            assert page.locator("#journal-period").input_value() == "all"
            page.go_forward(wait_until="domcontentloaded")
            page.go_back(wait_until="domcontentloaded")
            assert not page.locator("#journal-custom-range").is_visible()

            _goto(page, journal + "?since=2026-09-01&until=2026-09-30")
            assert page.locator("#journal-period").input_value() == "custom"
            assert page.locator("#journal-custom-range").is_visible()
            assert page.locator("#journal-since").input_value() == "2026-09-01"
            assert page.locator("#journal-until").input_value() == "2026-09-30"

            if browser_name == "webkit":
                viewports = (
                    ("iphone13_portrait", 390, 844),
                    ("iphone15_portrait", 393, 852),
                    ("iphone13_landscape", 844, 390),
                    ("iphone15_landscape", 852, 393),
                    ("iphone_se_portrait", 375, 667),
                    ("iphone_extreme_landscape", 667, 320),
                )
                for label, width, height in viewports:
                    mobile = browser.new_context(
                        storage_state=storage_state,
                        viewport={"width": width, "height": height},
                        is_mobile=True,
                        has_touch=True,
                        device_scale_factor=3,
                    )
                    mobile_page = mobile.new_page()
                    _goto(mobile_page, base + "/?layout_debug=1")
                    mobile_page.evaluate("""() => {
                      const messages = document.querySelector('#messages');
                      for (let index = 0; index < 32; index += 1) {
                        const row = document.createElement('article');
                        row.className = 'msg msg-assistant';
                        row.textContent = `Mobile layout message ${index + 1}`;
                        messages.appendChild(row);
                      }
                    }""")
                    mobile_page.locator("body").evaluate("(node) => node.dataset.theme = 'paper'")
                    mobile_page.locator("body").evaluate("(node) => node.dataset.theme = 'matrix'")
                    mobile_page.evaluate("() => document.querySelector('#chat-form').scrollIntoView({block: 'end'})")
                    geometry = mobile_page.evaluate("""() => {
                      const viewport = window.visualViewport;
                      const viewportTop = viewport ? viewport.offsetTop : 0;
                      const viewportHeight = viewport ? viewport.height : window.innerHeight;
                      const composer = document.querySelector('#chat-form').getBoundingClientRect();
                      const header = document.querySelector('.topbar').getBoundingClientRect();
                      const logo = document.querySelector('.brand-mark').getBoundingClientRect();
                      const menu = document.querySelector('.topnav .app-menu-trigger').getBoundingClientRect();
                      const messageList = document.querySelector('#messages');
                      const hiddenAncestors = [];
                      let ancestor = document.querySelector('#chat-form').parentElement;
                      while (ancestor) {
                        const style = getComputedStyle(ancestor);
                        if (['hidden', 'clip'].includes(style.overflowY)) hiddenAncestors.push(ancestor.className || ancestor.tagName);
                        ancestor = ancestor.parentElement;
                      }
                      const assets = Array.from(document.querySelectorAll('link[href], script[src], img[src]'))
                        .map((node) => node.getAttribute('href') || node.getAttribute('src') || '')
                        .filter((value) => value.includes('/static/'));
                      const background = getComputedStyle(document.body).getPropertyValue('--background-art');
                      return {
                        composerVisible: composer.top >= viewportTop - 1 && composer.bottom <= viewportTop + viewportHeight + 1,
                        headerSingleRow: Math.abs(menu.top - logo.top) <= 8,
                        headerAway: header.bottom <= viewportTop + 1,
                        hiddenAncestors,
                        documentScrolls: document.documentElement.scrollHeight > viewportHeight,
                        messageOverflow: getComputedStyle(messageList).overflowY,
                        pageWide: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        unversionedAssets: assets.filter((value) => !/[?&]v=/.test(value)),
                        backgroundVersioned: !background.includes('/static/') || /[?&]v=/.test(background),
                        debug: document.querySelector('#chat-layout-debug-values')?.textContent || '',
                      };
                    }""")
                    assert geometry["composerVisible"], (label, geometry)
                    assert geometry["headerSingleRow"], (label, geometry)
                    assert not geometry["hiddenAncestors"], (label, geometry)
                    assert geometry["documentScrolls"], (label, geometry)
                    assert geometry["messageOverflow"] == "visible", (label, geometry)
                    assert not geometry["pageWide"], (label, geometry)
                    assert not geometry["unversionedAssets"], (label, geometry)
                    assert geometry["backgroundVersioned"], (label, geometry)
                    assert all(key in geometry["debug"] for key in (
                        "innerWidth", "innerHeight", "visualViewport", "header",
                        "messages", "composer", "scrollContainer", "userAgent", "cssVersion",
                    )), (label, geometry)
                    if height <= 500:
                        assert geometry["headerAway"], (label, geometry)
                    before = mobile_page.locator("#messages .msg-user").count()
                    mobile_page.locator("#message").fill(f"{label}: Tippen und Senden")
                    mobile_page.locator("#send-btn").click()
                    mobile_page.wait_for_function(
                        "expected => document.querySelectorAll('#messages .msg-user').length > expected",
                        arg=before,
                        timeout=20_000,
                    )
                    mobile_page.reload(wait_until="domcontentloaded")
                    mobile_page.evaluate("() => document.querySelector('#chat-form').scrollIntoView({block: 'end'})")
                    assert mobile_page.locator("#chat-form").is_visible(), label
                    mobile.close()

                for width, height in ((844, 390), (667, 320)):
                    landscape = browser.new_context(
                        storage_state=storage_state,
                        viewport={"width": width, "height": height},
                        is_mobile=True,
                        has_touch=True,
                    )
                    landscape_page = landscape.new_page()
                    for path in ("/stats", "/memories/activity-journal", "/jobs/panel"):
                        _goto(landscape_page, base + path)
                        assert landscape_page.evaluate(
                            "() => document.documentElement.scrollHeight > window.innerHeight"
                        ), (width, height, path)
                    landscape.close()
                print("phone_page_linter_viewports=passed 844x390,667x320")
            context.close()
            browser.close()
            print(f"journal_date_filter_{browser_name}=passed")


if __name__ == "__main__":
    main()
