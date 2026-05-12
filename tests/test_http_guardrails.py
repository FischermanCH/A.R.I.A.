from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

from aria.core.recipe_runtime import RecipeRuntime


class _DummyResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/json") -> None:
        self._body = body
        self.status = status
        self.headers = {"Content-Type": content_type}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _runtime(*, webhook: object | None = None, http_api: object | None = None, guardrails: dict[str, object] | None = None) -> RecipeRuntime:
    settings = SimpleNamespace(
        connections=SimpleNamespace(
            webhook={"incident-hook": webhook} if webhook is not None else {},
            http_api={"inventory-api": http_api} if http_api is not None else {},
        ),
        security=SimpleNamespace(guardrails=guardrails or {}),
    )
    return RecipeRuntime(
        settings=settings,
        llm_client=None,
        memory_skill_getter=lambda: None,
        web_search_skill_getter=lambda: None,
        execute_custom_ssh_command=lambda **_: None,
        extract_memory_store_text=lambda *args, **kwargs: "",
        extract_memory_recall_query=lambda *args, **kwargs: "",
        extract_web_search_query=lambda *args, **kwargs: "",
        facts_collection_for_user=lambda user: f"facts-{user}",
        preferences_collection_for_user=lambda user: f"prefs-{user}",
        normalize_spaces=lambda text: " ".join(str(text or "").split()),
        truncate_text=lambda text, limit=4000: str(text or "")[:limit],
    )


def test_execute_webhook_send_blocks_on_http_guardrail() -> None:
    runtime = _runtime(
        webhook=SimpleNamespace(
            url="https://blocked.example/webhook",
            timeout_seconds=10,
            method="POST",
            content_type="application/json",
            guardrail_ref="internal-only",
        ),
        guardrails={
            "internal-only": {
                "kind": "http_request",
                "allow_terms": ["intranet.local"],
                "deny_terms": ["blocked.example"],
            }
        },
    )

    try:
        runtime.execute_webhook_send("incident-hook", "ARIA was here")
    except ValueError as exc:
        assert "HTTP-Guardrail blockiert die Anfrage" in str(exc)
        assert "internal-only" in str(exc)
    else:
        raise AssertionError("Webhook request should have been blocked by guardrail")


def test_execute_http_api_request_blocks_on_kind_mismatch() -> None:
    runtime = _runtime(
        http_api=SimpleNamespace(
            base_url="https://inventory.local/api",
            timeout_seconds=10,
            method="GET",
            health_path="/health",
            auth_token="",
            guardrail_ref="wrong-kind",
        ),
        guardrails={
            "wrong-kind": {
                "kind": "mqtt_publish",
                "allow_terms": [],
                "deny_terms": [],
            }
        },
    )

    try:
        runtime.execute_http_api_request("inventory-api", "/health", "")
    except ValueError as exc:
        assert "HTTP-Guardrail-Typ passt nicht" in str(exc)
        assert "wrong-kind" in str(exc)
    else:
        raise AssertionError("HTTP API request should have failed on guardrail kind mismatch")


def test_execute_http_api_request_allows_compatible_guardrail() -> None:
    runtime = _runtime(
        http_api=SimpleNamespace(
            base_url="https://inventory.local/api",
            timeout_seconds=10,
            method="GET",
            health_path="/health",
            auth_token="",
            guardrail_ref="inventory-readonly",
        ),
        guardrails={
            "inventory-readonly": {
                "kind": "http_request",
                "allow_terms": ["inventory.local", "/health"],
                "deny_terms": ["DELETE", "/admin"],
            }
        },
    )

    response = _DummyResponse(
        json.dumps({"status": "ok"}).encode("utf-8"),
        status=200,
        content_type="application/json",
    )

    with patch("aria.core.recipe_runtime.urlopen", return_value=response):
        result = runtime.execute_http_api_request("inventory-api", "/health", "")

    assert '"status": "ok"' in result


def test_execute_http_api_request_blocks_mutating_path_even_with_get() -> None:
    runtime = _runtime(
        http_api=SimpleNamespace(
            base_url="https://inventory.local/api",
            timeout_seconds=10,
            method="GET",
            health_path="/health",
            auth_token="",
            guardrail_ref="",
        )
    )

    try:
        runtime.execute_http_api_request("inventory-api", "/admin/restart", "")
    except ValueError as exc:
        assert "HTTP-API-Anfrage blockiert" in str(exc)
        assert "http_api_mutating_path" in str(exc)
    else:
        raise AssertionError("HTTP API request should have been blocked by the readonly policy")


def test_execute_http_api_request_requires_confirmation_for_post_method() -> None:
    runtime = _runtime(
        http_api=SimpleNamespace(
            base_url="https://inventory.local/api",
            timeout_seconds=10,
            method="POST",
            health_path="/health",
            auth_token="",
            guardrail_ref="",
        )
    )

    try:
        runtime.execute_http_api_request("inventory-api", "/search", '{"q":"aria"}')
    except ValueError as exc:
        assert "HTTP-API-Anfrage braucht Bestätigung" in str(exc)
        assert "http_api_method_needs_confirmation" in str(exc)
    else:
        raise AssertionError("HTTP API request should have required confirmation")


def test_execute_http_api_request_reports_404_with_health_path_hint() -> None:
    runtime = _runtime(
        http_api=SimpleNamespace(
            base_url="https://inventory.local/api",
            timeout_seconds=10,
            method="GET",
            health_path="/",
            auth_token="",
            guardrail_ref="",
        )
    )

    error = HTTPError(
        "https://inventory.local/api/health",
        404,
        "Not Found",
        hdrs={},
        fp=io.BytesIO(b'{"error":"missing route"}'),
    )

    with patch("aria.core.recipe_runtime.urlopen", side_effect=error):
        try:
            runtime.execute_http_api_request("inventory-api", "/health", "")
        except ValueError as exc:
            text = str(exc)
            assert "HTTP-API-Aufruf fehlgeschlagen: HTTP 404 auf `/health` (GET)" in text
            assert "Im Profil ist als Health-Pfad `/` konfiguriert." in text
            assert 'Antwort: {"error":"missing route"}' in text
        else:
            raise AssertionError("HTTP API request should have surfaced the HTTP 404 details")
