from __future__ import annotations

import contextlib
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request as URLRequest

from aria.core.connection_action_contract import guardrail_kind_for_capability
from aria.core.http_api_policy import validate_http_api_request_policy

RecipeText = Callable[..., str]
UrlOpen = Callable[..., Any]
GuardrailEnforcer = Callable[..., None]


class RecipeHttpRuntime:
    def __init__(
        self,
        *,
        get_connection_profile: Callable[[str, str], Any],
        enforce_connection_guardrail: GuardrailEnforcer,
        truncate_text: Callable[[str, int], str],
        recipe_text: RecipeText,
        urlopen_func: UrlOpen,
    ) -> None:
        self.get_connection_profile = get_connection_profile
        self.enforce_connection_guardrail = enforce_connection_guardrail
        self.truncate_text = truncate_text
        self.recipe_text = recipe_text
        self.urlopen_func = urlopen_func

    def _text(self, language: str, key: str, default: str, **values: Any) -> str:
        return self.recipe_text(language, key, default, **values)

    def execute_webhook_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("webhook", connection_ref)
        webhook_url = str(getattr(connection, "url", "")).strip()
        if not webhook_url:
            raise ValueError(self._text(language, "message_1574", "Webhook URL is missing in profile: {connection_ref}", connection_ref=connection_ref))
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        method = str(getattr(connection, "method", "POST")).strip().upper() or "POST"
        content_type = str(getattr(connection, "content_type", "application/json")).strip() or "application/json"
        payload_text = str(content or "").strip()
        if not payload_text:
            raise ValueError(self._text(language, "message_1580", "Webhook content is missing."))
        self.enforce_connection_guardrail(
            connection=connection,
            connection_ref=connection_ref,
            guardrail_kind=guardrail_kind_for_capability("webhook_send"),
            evaluation_text=" ".join(
                part
                for part in (
                    method,
                    webhook_url,
                    content_type,
                    payload_text,
                )
                if str(part).strip()
            ),
            label="HTTP",
        )

        if "json" in content_type.lower():
            payload = json.dumps({"message": payload_text}, ensure_ascii=False).encode("utf-8")
        else:
            payload = payload_text.encode("utf-8")

        req = URLRequest(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": content_type,
                "User-Agent": "ARIA/1.0",
            },
            method=method,
        )
        try:
            with self.urlopen_func(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                status_code = int(getattr(resp, "status", 200) or 200)
                _ = resp.read()
        except URLError as exc:
            raise ValueError(self._text(language, "message_1617", "Webhook send failed: {exc}", exc=exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_1619", "Webhook send failed: {exc}", exc=exc)) from exc
        if status_code >= 400:
            raise ValueError(self._text(language, "message_1621", "Webhook send failed: HTTP {status_code}", status_code=status_code))
        return self._text(language, "message_1622", "Webhook sent via `{connection_ref}` ({method}, {status_code})", connection_ref=connection_ref, method=method, status_code=status_code)

    def execute_discord_send(self, connection_ref: str, content: str, *, language: str = "de") -> str:
        connection = self.get_connection_profile("discord", connection_ref)
        if not bool(getattr(connection, "allow_skill_messages", True)):
            raise ValueError(self._text(language, "message_1631", "Discord profile currently does not allow skill/chat messages."))
        webhook_url = str(getattr(connection, "webhook_url", "")).strip()
        if not webhook_url:
            raise ValueError(self._text(language, "message_1634", "Discord webhook is missing in profile: {connection_ref}", connection_ref=connection_ref))
        payload_text = str(content or "").strip()
        if not payload_text:
            raise ValueError(self._text(language, "message_1637", "Discord content is missing."))
        payload = json.dumps({"content": payload_text[:1900]}, ensure_ascii=False).encode("utf-8")
        req = URLRequest(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ARIA/1.0",
            },
            method="POST",
        )
        try:
            with self.urlopen_func(req, timeout=10) as resp:  # noqa: S310
                status_code = int(getattr(resp, "status", 204) or 204)
                _ = resp.read()
        except URLError as exc:
            raise ValueError(self._text(language, "message_1653", "Discord send failed: {exc}", exc=exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_1655", "Discord send failed: {exc}", exc=exc)) from exc
        if status_code >= 400:
            raise ValueError(self._text(language, "message_1657", "Discord send failed: HTTP {status_code}", status_code=status_code))
        return self._text(language, "message_1658", "Discord message sent via `{connection_ref}`", connection_ref=connection_ref)

    def send_discord_webhook_url(self, webhook_url: str, content: str) -> None:
        payload_text = str(content or "").strip()
        payload = json.dumps({"content": payload_text[:1900]}, ensure_ascii=False).encode("utf-8")
        req = URLRequest(
            str(webhook_url or "").strip(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ARIA/1.0",
            },
            method="POST",
        )
        with self.urlopen_func(req, timeout=10) as resp:  # noqa: S310
            _ = resp.read()

    def execute_http_api_request(
        self,
        connection_ref: str,
        request_path: str = "",
        content: str = "",
        *,
        language: str = "de",
        confirmed: bool = False,
    ) -> str:
        connection = self.get_connection_profile("http_api", connection_ref)
        base_url = str(getattr(connection, "base_url", "")).strip()
        if not base_url:
            raise ValueError(self._text(language, "message_1672", "Base URL is missing in the HTTP API profile: {connection_ref}", connection_ref=connection_ref))
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        method = str(getattr(connection, "method", "GET")).strip().upper() or "GET"
        health_path = str(getattr(connection, "health_path", "/")).strip() or "/"
        auth_token = str(getattr(connection, "auth_token", "")).strip()
        resolved_path = str(request_path or "").strip() or health_path
        policy = validate_http_api_request_policy(
            resolved_path,
            content=str(content or "").strip(),
            method=method,
            health_path=health_path,
        )
        if policy.action == "block":
            raise ValueError(
                self._text(language, "message_1686", "HTTP API request blocked: {policy_reason}", policy_reason=policy.reason)
            )
        if policy.action == "ask_user" and not confirmed:
            raise ValueError(
                self._text(language, "message_1694", "HTTP API request requires confirmation: {policy_reason}", policy_reason=policy.reason)
            )
        resolved_path = policy.normalized_path or health_path
        target_url = urljoin(base_url.rstrip("/") + "/", resolved_path.lstrip("/"))
        self.enforce_connection_guardrail(
            connection=connection,
            connection_ref=connection_ref,
            guardrail_kind=guardrail_kind_for_capability("api_request"),
            evaluation_text=" ".join(
                part
                for part in (
                    method,
                    target_url,
                    resolved_path,
                    str(content or "").strip(),
                )
                if str(part).strip()
            ),
            label="HTTP",
        )
        headers = {"User-Agent": "ARIA/1.0"}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = None
        if method in {"POST", "PUT", "PATCH"}:
            headers["Content-Type"] = "application/json"
            payload_text = str(content or "").strip()
            payload = json.dumps({"message": payload_text}, ensure_ascii=False).encode("utf-8") if payload_text else b"{}"

        req = URLRequest(
            target_url,
            data=payload,
            headers=headers,
            method=method,
        )
        try:
            with self.urlopen_func(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                body = resp.read()
                status_code = int(getattr(resp, "status", 200) or 200)
                content_type = str(getattr(resp, "headers", {}).get("Content-Type", "") if getattr(resp, "headers", None) else "")
        except HTTPError as exc:
            status_code = int(getattr(exc, "code", 0) or 0)
            response_excerpt = ""
            with contextlib.suppress(Exception):
                response_body = exc.read()
                if isinstance(response_body, bytes):
                    response_excerpt = response_body.decode("utf-8", errors="replace").strip()
                else:
                    response_excerpt = str(response_body or "").strip()
            if response_excerpt:
                response_excerpt = self.truncate_text(" ".join(response_excerpt.split()), 220)
            message_parts = [
                self._text(language, "message_1751", "HTTP API request failed: HTTP {status_code} on `{resolved_path}` ({method})", status_code=status_code, resolved_path=resolved_path, method=method)
            ]
            if status_code == 404 and resolved_path != health_path:
                message_parts.append(
                    self._text(language, "message_1759", "The profile is configured with `{health_path}` as health path.", health_path=health_path)
                )
            if response_excerpt:
                message_parts.append(
                    self._text(language, "message_1767", "Response: {response_excerpt}", response_excerpt=response_excerpt)
                )
            raise ValueError(" ".join(part for part in message_parts if part)) from exc
        except URLError as exc:
            raise ValueError(self._text(language, "message_1775", "HTTP API request failed: {exc}", exc=exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_1777", "HTTP API request failed: {exc}", exc=exc)) from exc
        if status_code >= 400:
            raise ValueError(self._text(language, "message_1779", "HTTP API request failed: HTTP {status_code}", status_code=status_code))

        text = body.decode("utf-8", errors="replace").strip()
        if text:
            if "json" in content_type.lower():
                try:
                    parsed = json.loads(text)
                    text = json.dumps(parsed, ensure_ascii=False, indent=2)
                except Exception:
                    pass
            return self.truncate_text(text, 1400)
        return self._text(language, "message_1790", "HTTP API executed via `{connection_ref}` ({method}, {status_code})", connection_ref=connection_ref, method=method, status_code=status_code)
