from __future__ import annotations

from aria.core.http_api_policy import validate_http_api_request_policy


def test_http_api_policy_allows_simple_health_get() -> None:
    decision = validate_http_api_request_policy("/health", method="GET", health_path="/health", status_like=True)

    assert decision.action == "allow"
    assert decision.reason == "http_api_readonly_policy_allow"
    assert decision.normalized_path == "/health"


def test_http_api_policy_blocks_mutating_path() -> None:
    decision = validate_http_api_request_policy("/admin/restart", method="GET", health_path="/health")

    assert decision.action == "block"
    assert decision.reason == "http_api_mutating_path"


def test_http_api_policy_asks_for_post_request() -> None:
    decision = validate_http_api_request_policy("/search", method="POST", content='{"q":"aria"}', health_path="/health")

    assert decision.action == "ask_user"
    assert decision.reason == "http_api_method_needs_confirmation"
