#!/usr/bin/env python3
"""Run the canonical page and theme linters against the isolated demo seed."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.e2e.browser_driver import AriaBrowser
from tests.e2e.scenarios import (
    _assert_u19_alpha994_bilingual_page_linter_and_connection_inventory,
    test_u17_alpha993_theme_role_linter_and_visual_review,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--username", default="demo-admin")
    parser.add_argument("--password", default="aria-demo-access")
    parser.add_argument(
        "--output", type=Path, default=Path("test-results/demo-screenshots/linter"),
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        driver = AriaBrowser(context.new_page(), args.url, args.output)
        driver.login(args.username, args.password)
        _assert_u19_alpha994_bilingual_page_linter_and_connection_inventory(driver)
        test_u17_alpha993_theme_role_linter_and_visual_review(driver)
        context.close()
        browser.close()
    print("demo_page_linter=passed rules=R1-R32 themes=11")


if __name__ == "__main__":
    main()
