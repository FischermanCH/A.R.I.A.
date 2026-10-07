"""Fixtures and failure artifacts for the explicitly invoked E2E scenarios."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.browser_driver import AriaBrowser, HarnessControl


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        pytest.fail(f"Missing E2E runner environment variable: {name}")
    return value


@pytest.fixture(scope="session")
def artifact_dir() -> Path:
    path = Path(_required_env("ARIA_E2E_ARTIFACT_DIR"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def controls() -> "HarnessControl":
    from .browser_driver import HarnessControl

    return HarnessControl(
        _required_env("ARIA_E2E_ANTHROPIC_CONTROL_URL"),
        _required_env("ARIA_E2E_MCP_CONTROL_URL"),
    )


@pytest.fixture()
def aria_browser(request: pytest.FixtureRequest, artifact_dir: Path) -> "AriaBrowser":
    from playwright.sync_api import sync_playwright
    from .browser_driver import AriaBrowser

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        driver = AriaBrowser(page, _required_env("ARIA_E2E_BASE_URL"), artifact_dir)
        driver.login(
            _required_env("ARIA_E2E_USERNAME"),
            _required_env("ARIA_E2E_PASSWORD"),
        )
        driver.clear_history()
        driver.evidence.failed_requests.clear()
        driver.evidence.navigations.clear()
        yield driver
        if getattr(request.node, "rep_call", None) and request.node.rep_call.failed:
            driver.screenshot(request.node.name)
        context.close()
        browser.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
