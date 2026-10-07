from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.native_web_llm.authority import validate_native_web_result
from aria.modules.native_web_llm.contracts import NativeWebCitation, NativeWebRequest, NativeWebResult
from aria.modules.native_web_llm.dispatch import decide_auto_web_dispatch, decide_web_dispatch, select_web_followup_history
from aria.modules.native_web_llm.gateway import NativeWebLLMGateway, NativeWebLLMError
from aria.modules.native_web_llm.evidence import PublicWebEvidenceStore
from aria.modules.native_web_llm.normalization import normalize_native_web_response
from aria.modules.native_web_llm.pipeline_mixin import NativeWebPipelineMixin
from aria.modules.native_web_llm.source_policy import resolve_native_web_source_policy


FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _config() -> LLMConfig:
    return LLMConfig(
        model="openai/gpt-5.6-luna",
        api_base="https://gateway.example/v1",
        api_key="test-key-not-a-secret",
        max_tokens=1500,
        timeout_seconds=20,
    )


def _request(**overrides: object) -> NativeWebRequest:
    values = {
        "question": "Welches ist die neueste Version von n8n?",
        "current_date": "2026-09-02",
        "allowed_domains": ("n8n.io", "docs.n8n.io", "github.com"),
        "required_url_prefixes": ("https://github.com/n8n-io/",),
        "max_search_uses": 3,
    }
    values.update(overrides)
    return NativeWebRequest(**values)


def test_openai_responses_normalization_keeps_provider_citations() -> None:
    result = normalize_native_web_response(
        _fixture("native_web_llm_openai_response.json"),
        duration_ms=4210,
    )

    assert result.answer
    assert result.native_search_uses == 1
    assert result.provider_shape == "openai_responses"
    assert result.citations[0].source == "openai.url_citation"
    assert result.usage["total_tokens"] == 500


def test_openai_responses_normalization_preserves_token_details() -> None:
    payload = _fixture("native_web_llm_openai_response.json")
    payload["usage"]["input_tokens_details"] = {"cached_tokens": 240}
    payload["usage"]["output_tokens_details"] = {"reasoning_tokens": 60}

    result = normalize_native_web_response(payload, duration_ms=4210)

    assert result.usage == {
        "prompt_tokens": 420,
        "completion_tokens": 80,
        "reasoning_tokens": 60,
        "cached_tokens": 240,
        "total_tokens": 500,
    }


def test_anthropic_normalization_uses_server_tool_receipt() -> None:
    result = normalize_native_web_response(
        _fixture("native_web_llm_anthropic_response.json"),
        duration_ms=5380,
    )

    assert result.answer
    assert result.native_search_uses == 1
    assert result.provider_shape == "anthropic_messages"
    assert result.citations[0].source == "anthropic.web_search_citation"


def test_text_url_only_response_fails_closed() -> None:
    result = normalize_native_web_response(
        _fixture("native_web_llm_text_url_only_response.json"),
    )

    assert "provider_citations_missing" in result.errors
    assert not result.passed


def test_authority_rejects_private_citation_and_search_overrun() -> None:
    payload = _fixture("native_web_llm_openai_response.json")
    payload["output"][0]["type"] = "web_search_call"
    payload["output"].insert(1, {"type": "web_search_call"})
    payload["output"].insert(2, {"type": "web_search_call"})
    payload["output"].insert(3, {"type": "web_search_call"})
    payload["output"][-1]["content"][0]["annotations"][0]["url"] = "http://127.0.0.1/private"
    result = validate_native_web_result(
        normalize_native_web_response(payload),
        _request(max_search_uses=3),
    )

    assert "native_web_search_budget_exceeded" in result.errors
    assert "private_or_invalid_citation" in result.errors
    assert "required_primary_source_missing" in result.errors
    assert not result.passed


def test_gateway_makes_one_responses_call_with_provider_domain_filter() -> None:
    calls: list[dict] = []

    async def provider_call(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return _fixture("native_web_llm_openai_response.json")

    gateway = NativeWebLLMGateway(
        _config(),
        transport="openai_responses",
        provider_call=provider_call,
    )
    result = asyncio.run(gateway.answer(_request()))

    assert result.passed
    assert result.provider_requests == 1
    assert result.main_llm_requests == 0
    assert result.retries == 0
    assert len(calls) == 1
    assert calls[0]["tools"] == [
        {
            "type": "web_search",
            "search_context_size": "low",
            "filters": {"allowed_domains": ["n8n.io", "docs.n8n.io", "github.com"]},
        }
    ]
    assert "Use native web search" in calls[0]["instructions"]
    assert calls[0]["input"] == "Welches ist die neueste Version von n8n?"
    assert calls[0]["reasoning"] == {"effort": "low"}
    assert "temperature" not in calls[0]


def test_gateway_current_date_overrides_stale_year_and_prior_evidence_is_not_injected() -> None:
    calls: list[dict[str, object]] = []

    async def provider_call(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return _fixture("native_web_llm_openai_response.json")

    request = _request(
        question="Welches ist das neueste iPhone Modell 2024?",
        current_date="2026-09-24",
        prior_evidence=(NativeWebCitation(
            url="https://example.com/iphone-2024", title="Old iPhone 2024",
        ),),
        search_context_size="high",
    )
    result = asyncio.run(NativeWebLLMGateway(
        _config(), transport="openai_responses", provider_call=provider_call,
    ).answer(request))

    assert result.passed
    assert calls[0]["input"] == "Welches ist das neueste iPhone Modell 2024?"
    assert "iphone-2024" not in str(calls[0]["input"])
    assert "The current date is 2026-09-24" in str(calls[0]["instructions"])
    assert "ignore it and return the CURRENT state as of 2026-09-24 via live web search" in str(
        calls[0]["instructions"]
    )
    assert "never anchor to a past year" in str(calls[0]["instructions"])
    assert calls[0]["tools"] == [{
        "type": "web_search", "search_context_size": "high",
        "filters": {"allowed_domains": ["n8n.io", "docs.n8n.io", "github.com"]},
    }]
    assert calls[0]["max_output_tokens"] == 1200
    assert calls[0]["reasoning"] == {"effort": "low"}


def test_gateway_exposes_exact_non_secret_request_diagnostics() -> None:
    calls: list[dict[str, object]] = []

    async def provider_call(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return _fixture("native_web_llm_openai_response.json")

    request = _request(
        question="Welche Version ist heute aktuell?",
        prior_evidence=(NativeWebCitation(url="https://example.com/old", title="Old"),),
        search_context_size="high",
        max_output_tokens=777,
    )
    result = asyncio.run(
        NativeWebLLMGateway(
            _config(),
            transport="openai_responses",
            provider_call=provider_call,
        ).answer(request)
    )

    assert result.passed
    assert result.diagnostics["request_input"] == calls[0]["input"]
    assert result.diagnostics["model"] == "openai/gpt-5.6-luna"
    assert result.diagnostics["search_context_size"] == "high"
    assert result.diagnostics["max_output_tokens"] == 777
    assert result.diagnostics["source_urls"] == [citation.url for citation in result.citations]
    assert "api_key" not in result.diagnostics
    assert "test-key-not-a-secret" not in json.dumps(result.diagnostics)


def test_alpha882_web_debug_file_dump_is_removed() -> None:
    gateway_source = Path(__file__).resolve().parents[1] / "aria/modules/native_web_llm/gateway.py"
    source = gateway_source.read_text(encoding="utf-8")

    assert "WEB_DEBUG_PATH" not in source
    assert "_write_web_debug_dump" not in source
    assert "last_web_debug.json" not in source


def test_responses_gateway_omits_reasoning_for_non_gpt5_model() -> None:
    calls: list[dict] = []

    async def provider_call(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return _fixture("native_web_llm_openai_response.json")

    config = _config().model_copy(update={"model": "openai/gpt-4.1"})
    gateway = NativeWebLLMGateway(config, transport="openai_responses", provider_call=provider_call)

    result = asyncio.run(gateway.answer(_request()))

    assert result.passed
    assert len(calls) == 1
    assert "reasoning" not in calls[0]
    assert result.diagnostics["reasoning_effort"] == "provider_default"


def test_gateway_does_not_retry_provider_failure() -> None:
    calls = 0

    async def provider_call(**kwargs: object) -> dict:
        nonlocal calls
        del kwargs
        calls += 1
        raise TimeoutError("fixture timeout")

    gateway = NativeWebLLMGateway(_config(), provider_call=provider_call)

    with pytest.raises(NativeWebLLMError, match="native_web_provider_failed:TimeoutError"):
        asyncio.run(gateway.answer(_request()))
    assert calls == 1


def test_native_web_pipeline_exports_bounded_usage_components_without_prompt_text() -> None:
    flush_calls: list[dict[str, object]] = []

    class GatewayFixture:
        async def answer(self, request: NativeWebRequest, **_kwargs: object) -> NativeWebResult:
            return NativeWebResult(
                answer="n8n 2.37.7",
                citations=(
                    NativeWebCitation(
                        url="https://github.com/n8n-io/n8n/releases/latest",
                        source="openai.url_citation",
                    ),
                ),
                model="gpt-5.6-luna",
                provider_shape="openai_responses",
                native_search_uses=1,
                usage={
                    "prompt_tokens": 7000,
                    "completion_tokens": 375,
                    "reasoning_tokens": 300,
                    "cached_tokens": 250,
                    "total_tokens": 7375,
                },
                duration_ms=2828,
                diagnostics={"request_text_chars": 633, "reasoning_effort": "low"},
            )

    class UsageFixture:
        async def flush_current_scope(self, **kwargs: object) -> None:
            flush_calls.append(dict(kwargs))

    class PipelineFixture(NativeWebPipelineMixin):
        settings = SimpleNamespace(
            web_llm=SimpleNamespace(
                enabled=True,
                model="gpt-5.6-luna",
                capability_verified_at="2026-09-02T16:13:00Z",
                allowed_domains=(),
                required_url_prefixes=(),
                search_context_size="low",
                max_search_uses=3,
                max_output_tokens=1200,
                transport="openai_responses",
            )
        )
        web_llm_gateway = GatewayFixture()
        web_evidence_store = None
        usage_meter = UsageFixture()

    prompt = "Welches ist die neueste stabile Version von n8n?"
    result = asyncio.run(PipelineFixture().process_native_web(prompt, language="de"))

    assert flush_calls == [
        {"intents": ["web_search"], "duration_ms": result.duration_ms, "skill_errors": []}
    ]
    usage_line = next(line for line in result.detail_lines if "native_web_usage" in line)
    assert "prompt_tokens=7000" in usage_line
    assert "completion_tokens=375" in usage_line
    assert "reasoning_tokens=300" in usage_line
    assert "cached_tokens=250" in usage_line
    assert "total_tokens=7375" in usage_line
    assert "request_text_chars=633" in usage_line
    assert "reasoning_effort=low" in usage_line
    assert prompt not in usage_line


@pytest.mark.parametrize(
    ("message", "requested", "expected", "reason"),
    [
        ("Starte meinen Container", "web", "web", "explicit_web"),
        ("Was weisst du ueber mein Projekt?", "web", "web", "explicit_web"),
        ("Was weisst du ueber mein Projekt?", "main", "main", "explicit_main"),
        ("Welches ist die neueste Version von n8n?", "auto", "agent", "semantic_dispatch_required"),
        ("Erklaere mir Rekursion", "auto", "agent", "semantic_dispatch_required"),
    ],
)
def test_explicit_dispatch_has_no_natural_language_classifier(message: str, requested: str, expected: str, reason: str) -> None:
    decision = decide_web_dispatch(message, requested)

    assert decision.effective_mode == expected
    assert decision.reason == reason
    assert decision.deterministic is (requested != "auto")


def test_auto_dispatch_uses_one_bounded_semantic_decision_across_paraphrases() -> None:
    class DispatchLLM:
        def __init__(self, route: str) -> None:
            self.route = route
            self.calls: list[dict[str, object]] = []

        async def chat(self, messages, **kwargs):  # noqa: ANN001
            self.calls.append({"messages": messages, "kwargs": kwargs})
            return SimpleNamespace(
                content=json.dumps({
                    "route": self.route,
                    "confidence": 0.98,
                    "reason": "semantic authority and freshness decision",
                }),
                usage={"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
            )

    cases = (
        ("Was ist heute bei n8n neu?", "web"),
        ("Welche Fassung wird derzeit offiziell angeboten?", "web"),
        ("Welche Version ist auf meinem n8n-Server installiert?", "main"),
        ("Erklaere mir semantische Suche allgemein.", "main"),
    )
    for message, expected in cases:
        llm = DispatchLLM(expected)
        decision = asyncio.run(decide_auto_web_dispatch(
            message, llm_client=llm, web_ready=True, language="de", recent_history=[],
        ))

        assert decision.effective_mode == expected
        assert decision.reason == "semantic_dispatch"
        assert not decision.deterministic
        assert len(llm.calls) == 1
        assert llm.calls[0]["kwargs"]["operation"] == "native_web_dispatch_decision"
        payload = json.loads(llm.calls[0]["messages"][-1]["content"])
        assert set(payload) == {"current_user_message", "language", "web_llm_ready", "prior_web_turns", "allowed_routes", "requested_output_schema"}
        assert "keywords" not in json.dumps(payload).lower()


def test_auto_dispatch_fails_closed_to_main_on_invalid_or_unavailable_decision() -> None:
    class InvalidLLM:
        async def chat(self, _messages, **_kwargs):
            return SimpleNamespace(content='{"route":"web","confidence":0.2,"reason":"uncertain"}', usage={})

    low = asyncio.run(decide_auto_web_dispatch("Was gilt hier?", llm_client=InvalidLLM(), web_ready=True))
    missing = asyncio.run(decide_auto_web_dispatch("Was gilt hier?", llm_client=None, web_ready=True))
    unavailable = asyncio.run(decide_auto_web_dispatch("Was ist heute neu?", llm_client=InvalidLLM(), web_ready=False))

    assert low.effective_mode == "main"
    assert missing.effective_mode == "main"
    assert unavailable.effective_mode == "main"


def test_native_web_source_policy_is_generic_without_product_word_rules() -> None:
    policies = [
        resolve_native_web_source_policy("Neueste n8n Version"),
        resolve_native_web_source_policy("Neueste Apple Watch"),
        resolve_native_web_source_policy("Aktuelles Qdrant Release"),
    ]

    assert all(policy.policy_id == "public-primary-preferred" for policy in policies)
    assert all(policy.allowed_domains == () for policy in policies)
    assert all(policy.required_url_prefixes == () for policy in policies)


def test_web_followup_history_excludes_unmarked_main_context() -> None:
    history = [
        {"role": "user", "text": "Mein privates Serverpasswort ist geheim"},
        {"role": "assistant", "text": "Main response", "badge_intent": "chat"},
        {"role": "user", "text": "Welche n8n Version war das?"},
        {"role": "assistant", "text": "n8n 2.36.9", "badge_intent": "web_search"},
    ]

    selected = select_web_followup_history(history)

    assert selected == (
        ("user", "Welche n8n Version war das?"),
        ("assistant", "n8n 2.36.9"),
    )
    assert "Serverpasswort" not in str(selected)




def test_public_evidence_store_reads_once_and_writes_no_prompt_or_answer() -> None:
    now = "2999-01-01T00:00:00+00:00"

    class QdrantFixture:
        def __init__(self) -> None:
            self.retrieve_calls = 0
            self.upserts: list[dict] = []

        async def retrieve(self, **kwargs: object) -> list[object]:
            self.retrieve_calls += 1
            assert kwargs["with_vectors"] is False
            return [
                SimpleNamespace(
                    payload={
                        "expires_at": now,
                        "citations": [
                            {
                                "url": "https://github.com/n8n-io/n8n/releases",
                                "title": "n8n releases",
                            }
                        ],
                    }
                )
            ]

        async def get_collection(self, _name: str) -> object:
            return object()

        async def upsert(self, **kwargs: object) -> None:
            self.upserts.append(dict(kwargs))

    async def run() -> tuple[tuple[object, ...], QdrantFixture]:
        client = QdrantFixture()
        store = PublicWebEvidenceStore(
            qdrant_url="http://unused:6333",
            qdrant_api_key="",
            collection="aria_web_evidence",
            client=client,
        )
        question = "Welches ist die neueste Version von n8n?"
        evidence = await store.lookup(question)
        result = normalize_native_web_response(_fixture("native_web_llm_openai_response.json"))
        assert store.schedule_update(question, result)
        await asyncio.gather(*tuple(store._tasks))
        return evidence, client

    evidence, client = asyncio.run(run())

    assert client.retrieve_calls == 1
    assert evidence[0].source == "qdrant.public_web_evidence"
    assert len(client.upserts) == 1
    point = client.upserts[0]["points"][0]
    serialized = json.dumps(point.payload, ensure_ascii=True)
    assert "Welches ist" not in serialized
    assert "Die neueste" not in serialized
    assert "query_fingerprint" in point.payload
    assert point.payload["citations"] == [
        {"url": "https://github.com/n8n-io/n8n/releases/latest", "title": "n8n latest release"}
    ]
