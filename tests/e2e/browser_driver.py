"""Playwright helpers for the isolated ARIA browser review harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any

import httpx
from playwright.sync_api import Page, expect


@dataclass(slots=True)
class BrowserEvidence:
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    failed_requests: list[str] = field(default_factory=list)
    navigations: list[str] = field(default_factory=list)


class AriaBrowser:
    def __init__(self, page: Page, base_url: str, artifact_dir: Path) -> None:
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.artifact_dir = artifact_dir
        self.evidence = BrowserEvidence()
        page.on("console", self._console)
        page.on("pageerror", lambda error: self.evidence.page_errors.append(str(error)))
        page.on("requestfailed", lambda request: self.evidence.failed_requests.append(
            f"{request.method} {request.url}: {request.failure}"
        ))
        page.on("framenavigated", self._navigation)

    def _console(self, message: Any) -> None:
        if str(message.type).lower() == "error":
            self.evidence.console_errors.append(str(message.text))

    def _navigation(self, frame: Any) -> None:
        if frame == self.page.main_frame:
            self.evidence.navigations.append(str(frame.url))

    def reset_navigation_evidence(self) -> None:
        self.evidence.navigations.clear()

    def login(self, username: str, password: str) -> None:
        self.page.goto(f"{self.base_url}/login", wait_until="domcontentloaded")
        if "/login" not in self.page.url:
            return
        self.page.locator("#login-username").fill(username)
        self.page.locator("#login-password").fill(password)
        confirm = self.page.locator("#login-password-confirm")
        if confirm.count():
            confirm.fill(password)
        self.page.locator("form.login-form button[type=submit]").click()
        self.page.wait_for_url(lambda url: "/login" not in url, timeout=15_000)

    def open_chat(self) -> None:
        self.page.goto(f"{self.base_url}/", wait_until="domcontentloaded")
        expect(self.page.locator("#chat-form")).to_be_visible()

    def clear_history(self) -> None:
        self.open_chat()
        status = self.page.evaluate("""async () => {
          const meta = document.querySelector("meta[name='csrf-token']");
          const token = meta ? String(meta.content || "") : "";
          const response = await fetch("/chat/history/clear", {
            method: "POST",
            credentials: "same-origin",
            headers: {"X-CSRF-Token": token}
          });
          return response.status;
        }""")
        assert status == 204
        self.page.reload(wait_until="domcontentloaded")

    def assistant_count(self) -> int:
        return self.page.locator("#messages .msg-assistant:not(.pending-assistant)").count()

    def send_chat(self, message: str, *, timeout_ms: int = 30_000) -> Any:
        before = self.assistant_count()
        self.page.locator("#message").fill(message)
        self.page.locator("#chat-form #send-btn").click()
        self.page.wait_for_function(
            "count => document.querySelectorAll('#messages .msg-assistant:not(.pending-assistant)').length > count",
            arg=before,
            timeout=timeout_ms,
        )
        return self.page.locator("#messages .msg-assistant:not(.pending-assistant)").last

    def wait_for_job_bubble(self, *, timeout_ms: int = 20_000) -> Any:
        bubble = self.page.locator(
            "#messages .msg-assistant[data-agent-job-id][data-agent-job-notice='false']"
        ).last
        expect(bubble).to_be_visible(timeout=timeout_ms)
        return bubble

    def wait_for_job_notice(self, text: str = "", *, timeout_ms: int = 30_000) -> Any:
        notices = self.page.locator("#messages .msg-assistant[data-agent-job-notice='true']")
        expect(notices.last).to_be_visible(timeout=timeout_ms)
        if text:
            expect(notices.last).to_contain_text(text, timeout=timeout_ms)
        return notices.last

    def assert_clean_js(
        self, *, allow_failed_contains: tuple[str, ...] = (),
        allow_console_contains: tuple[str, ...] = (),
    ) -> None:
        console_errors = [
            row for row in self.evidence.console_errors
            if not any(fragment in row for fragment in allow_console_contains)
        ]
        assert not console_errors, console_errors
        assert not self.evidence.page_errors, self.evidence.page_errors
        unexpected = [
            row for row in self.evidence.failed_requests
            if not (
                row.startswith("GET ")
                and row.endswith("net::ERR_ABORTED")
                and any(path in row for path in ("/chat/progress:", "/jobs:"))
            )
            if not any(fragment in row for fragment in allow_failed_contains)
        ]
        assert not unexpected, unexpected

    def screenshot(self, name: str) -> Path:
        path = self.artifact_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)
        return path


class HarnessControl:
    def __init__(self, anthropic_url: str, mcp_url: str) -> None:
        self.anthropic_url = anthropic_url.rstrip("/")
        self.mcp_url = mcp_url.rstrip("/")
        self.client = httpx.Client(timeout=10.0, trust_env=False)

    def script(
        self, scenario: str, steps: list[dict[str, Any]], *,
        temperature_free_models: tuple[str, ...] = (),
    ) -> None:
        response = self.client.post(
            f"{self.anthropic_url}/__control/reset",
            json={
                "scenario": scenario,
                "steps": steps,
                "litellm_proxy_compatibility": True,
                "temperature_free_models": list(temperature_free_models),
            },
        )
        response.raise_for_status()

    def anthropic_logs(self) -> dict[str, Any]:
        response = self.client.get(f"{self.anthropic_url}/__control/logs")
        response.raise_for_status()
        return response.json()

    def mcp(self, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.client.post(f"{self.mcp_url}/__control/{action}", json=payload or {})
        response.raise_for_status()
        return response.json()

    def mcp_logs(self) -> dict[str, Any]:
        response = self.client.get(f"{self.mcp_url}/__control/logs")
        response.raise_for_status()
        return response.json()

    def wait_mcp_running(self, running: bool, *, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if bool(self.mcp_logs().get("listener_running")) is running:
                return
            time.sleep(0.2)
        raise AssertionError(f"MCP listener did not reach running={running}")
