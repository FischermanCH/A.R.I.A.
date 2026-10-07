from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from aria.modules.configuration_foundations.config import EmbeddingsConfig, LLMConfig
from aria.modules.model_gateway_clients.embedding import EmbeddingClient
from aria.modules.model_gateway_clients.embedding import EmbeddingClientError
from aria.modules.model_gateway_clients.llm import LLMClient, LLMClientError
import aria.modules.model_gateway_clients.llm as llm_client_mod
import aria.modules.model_gateway_clients.embedding as embedding_client_mod


def _client() -> LLMClient:
    return LLMClient(
        LLMConfig(
            provider="openai",
            model="gpt-5.1",
            api_base="",
            api_key="test",
            temperature=0.1,
            max_tokens=128,
            timeout_seconds=10,
        )
    )


def test_llm_client_returns_non_empty_content(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hallo von ARIA."),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=5,
                total_tokens=17,
            ),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    response = asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))

    assert response.content == "Hallo von ARIA."
    assert response.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "total_tokens": 17,
    }


def test_llm_client_uses_first_tool_call_arguments_when_content_is_empty(monkeypatch):
    arguments = '{"decision":"personal_claim_recall"}'

    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content="",
                    tool_calls=[SimpleNamespace(function=SimpleNamespace(arguments=arguments))],
                ),
                finish_reason="tool_use",
            )],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=5, total_tokens=17),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    response = asyncio.run(_client().chat([{"role": "user", "content": "Recall"}]))

    assert response.content == arguments


def test_llm_client_keeps_content_when_tool_calls_are_also_present(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    content="existing content",
                    tool_calls=[{"function": {"arguments": '{"ignored":true}'}}],
                ),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    response = asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))

    assert response.content == "existing content"


def test_llm_client_normalizes_dict_tool_call_arguments_to_json(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[{
                "message": {
                    "content": " ",
                    "tool_calls": [{"function": {"arguments": {"decision": "defer_to_legacy"}}}],
                },
                "finish_reason": "tool_use",
            }],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    response = asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))

    assert json.loads(response.content) == {"decision": "defer_to_legacy"}


def test_llm_client_still_raises_when_content_and_tool_calls_are_empty(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="", tool_calls=[]),
                finish_reason="stop",
            )],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=0, total_tokens=1),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    with pytest.raises(LLMClientError, match="ohne Textinhalt"):
        asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))


def test_llm_client_forwards_structured_response_format(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}'), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "dispatch", "strict": False, "schema": {"type": "object"}},
    }

    asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}], response_format=response_format))

    assert captured["response_format"] == response_format


def test_llm_client_raises_on_empty_content(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="   "),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=0,
                total_tokens=12,
            ),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    with pytest.raises(LLMClientError, match="ohne Textinhalt"):
        asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))


def test_llm_client_raises_without_choices(monkeypatch):
    async def _fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=8,
                completion_tokens=0,
                total_tokens=8,
            ),
        )

    monkeypatch.setattr("aria.modules.model_gateway_clients.llm._acompletion", _fake_completion)

    with pytest.raises(LLMClientError, match="ohne Textinhalt"):
        asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))


def test_llm_client_import_is_not_hard_bound_to_litellm(monkeypatch):
    def _missing_litellm(_name: str):
        raise ModuleNotFoundError("No module named 'litellm'")

    monkeypatch.setattr(llm_client_mod, "import_module", _missing_litellm)

    with pytest.raises(LLMClientError, match="LiteLLM ist nicht installiert"):
        asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))


def test_embedding_client_fingerprint_ignores_api_base_trailing_slash() -> None:
    left = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_base="https://api.example.com/v1"))
    right = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_base="https://api.example.com/v1/"))

    assert left.fingerprint() == right.fingerprint()


def test_embedding_client_import_is_not_hard_bound_to_litellm(monkeypatch):
    def _missing_litellm(_name: str):
        raise ModuleNotFoundError("No module named 'litellm'")

    monkeypatch.setattr(embedding_client_mod, "import_module", _missing_litellm)
    client = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_key="test"))

    with pytest.raises(EmbeddingClientError, match="LiteLLM is not installed"):
        asyncio.run(client.embed(["Hallo"]))
