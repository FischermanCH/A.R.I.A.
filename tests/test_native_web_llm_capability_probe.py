from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts" / "native_web_llm_capability_probe.py"
FIXTURES = ROOT / "tests" / "fixtures"


def _load_probe_module():
    spec = importlib.util.spec_from_file_location("native_web_llm_capability_probe", PROBE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture(name: str) -> dict:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    payload.pop("_probe_duration_ms", None)
    return payload


def test_openai_responses_fixture_requires_native_search_and_provider_citation() -> None:
    probe = _load_probe_module()
    result = probe.normalize_native_web_response(_fixture("native_web_llm_openai_response.json"))

    assert result.passed is True
    assert result.provider_shape == "openai_responses"
    assert result.native_search_uses == 1
    assert result.citations[0].url == "https://github.com/n8n-io/n8n/releases/latest"


def test_anthropic_fixture_requires_server_tool_use_and_citation() -> None:
    probe = _load_probe_module()
    result = probe.normalize_native_web_response(_fixture("native_web_llm_anthropic_response.json"))

    assert result.passed is True
    assert result.provider_shape == "anthropic_messages"
    assert result.native_search_uses == 1
    assert result.citations[0].source == "anthropic.web_search_citation"


def test_litellm_normalized_anthropic_chat_shape_flattens_nested_citations() -> None:
    probe = _load_probe_module()
    payload = {
        "model": "anthropic/test",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "Eine belegte Antwort.",
                    "provider_specific_fields": {
                        "citations": [
                            [
                                {
                                    "type": "web_search_result_location",
                                    "url": "https://docs.n8n.io/release-notes/",
                                    "title": "n8n release notes",
                                    "supported_text": "Eine belegte Antwort.",
                                }
                            ]
                        ]
                    },
                },
            }
        ],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "server_tool_use": {"web_search_requests": 1},
        },
    }

    result = probe.normalize_native_web_response(payload)

    assert result.passed is True
    assert result.provider_shape == "chat_completion"
    assert result.citations[0].cited_text == "Eine belegte Antwort."


def test_text_url_without_provider_annotation_is_not_a_citation() -> None:
    probe = _load_probe_module()
    result = probe.normalize_native_web_response(_fixture("native_web_llm_text_url_only_response.json"))

    assert result.passed is False
    assert "provider_citations_missing" in result.errors
    assert "native_web_search_not_observed" in result.errors


def test_expectation_gate_checks_primary_host_and_search_budget() -> None:
    probe = _load_probe_module()
    result = probe.normalize_native_web_response(_fixture("native_web_llm_openai_response.json"))

    assert probe._validate_expectations(result, ["github.com"], 1) == []
    assert probe._validate_expectations(result, ["n8n.io"], 1) == ["expected_primary_host_missing"]
    assert probe._validate_expectations(result, ["github.com"], 0) == []
    assert probe._validate_expectations(
        result,
        ["github.com"],
        1,
        ["https://github.com/n8n-io/"],
    ) == []
    assert probe._validate_expectations(
        result,
        ["github.com"],
        1,
        ["https://github.com/home-assistant/"],
    ) == ["expected_primary_url_prefix_missing"]


def test_live_probe_stops_before_import_or_network_without_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = _load_probe_module()
    monkeypatch.delenv("ARIA_WEB_LLM_API_KEY", raising=False)
    args = SimpleNamespace(
        confirm_paid_probe="",
        model="anthropic/test",
        api_base="https://example.invalid",
        prompt="test",
        transport="anthropic_native",
        max_search_uses=1,
        timeout_seconds=1,
    )

    with pytest.raises(ValueError, match="live_confirmation_missing"):
        asyncio.run(probe._run_live(args))


def test_openai_responses_live_transport_is_one_bounded_native_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe_module()
    calls: list[dict] = []

    async def fake_aresponses(**kwargs):
        calls.append(kwargs)
        return _fixture("native_web_llm_openai_response.json")

    import litellm

    monkeypatch.setattr(litellm, "aresponses", fake_aresponses)
    monkeypatch.setenv("ARIA_WEB_LLM_API_KEY", "redacted-test-key")
    args = SimpleNamespace(
        confirm_paid_probe=probe.LIVE_CONFIRMATION,
        model="openai/test",
        api_base="https://example.invalid",
        prompt="Welches ist die neueste Version von n8n?",
        transport="openai_responses",
        max_search_uses=1,
        timeout_seconds=10,
        authority_instruction="Use only official n8n sources.",
        allowed_domains=["n8n.io", "docs.n8n.io", "github.com"],
    )

    payload, duration_ms = asyncio.run(probe._run_live(args))

    assert payload["model"] == "openai/web-capable-fixture"
    assert duration_ms >= 0
    assert len(calls) == 1
    assert calls[0]["model"] == "openai/test"
    assert calls[0]["input"] == args.prompt
    assert calls[0]["tools"] == [
        {
            "type": "web_search",
            "search_context_size": "low",
            "filters": {"allowed_domains": ["n8n.io", "docs.n8n.io", "github.com"]},
        }
    ]
    assert calls[0]["include"] == ["web_search_call.action.sources"]
    assert calls[0]["api_key"] == "redacted-test-key"
    assert "temperature" not in calls[0]
    assert "Use only official n8n sources." in calls[0]["instructions"]


def test_openai_chat_web_search_omits_gpt5_incompatible_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    probe = _load_probe_module()
    calls: list[dict] = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _fixture("native_web_llm_openai_response.json")

    import litellm

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    monkeypatch.setenv("ARIA_WEB_LLM_API_KEY", "redacted-test-key")
    args = SimpleNamespace(
        confirm_paid_probe=probe.LIVE_CONFIRMATION,
        model="openai/gpt-5-search-api",
        api_base="https://example.invalid",
        prompt="Welches ist die neueste Version von n8n?",
        transport="openai_web_search_options",
        max_search_uses=1,
        timeout_seconds=10,
    )

    asyncio.run(probe._run_live(args))

    assert len(calls) == 1
    assert calls[0]["model"] == "openai/gpt-5-search-api"
    assert calls[0]["web_search_options"] == {"search_context_size": "low"}
    assert "temperature" not in calls[0]


def test_openai_search_only_chat_model_uses_provider_citation_as_search_receipt() -> None:
    probe = _load_probe_module()
    payload = {
        "model": "gpt-5-search-api-2025-10-14",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "Eine aktuelle Antwort.",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://github.com/n8n-io/n8n/releases/latest",
                                "title": "n8n latest release",
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }

    result = probe.normalize_native_web_response(payload)

    assert result.passed is True
    assert result.native_search_uses == 1
    assert result.citations[0].source == "openai.chat_annotation"
