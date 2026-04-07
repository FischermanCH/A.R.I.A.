from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aria.core.config import EmbeddingsConfig, LLMConfig
from aria.core.embedding_client import EmbeddingClient
from aria.core.llm_client import LLMClient, LLMClientError


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

    monkeypatch.setattr("aria.core.llm_client.acompletion", _fake_completion)

    response = asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))

    assert response.content == "Hallo von ARIA."
    assert response.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 5,
        "total_tokens": 17,
    }


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

    monkeypatch.setattr("aria.core.llm_client.acompletion", _fake_completion)

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

    monkeypatch.setattr("aria.core.llm_client.acompletion", _fake_completion)

    with pytest.raises(LLMClientError, match="ohne Textinhalt"):
        asyncio.run(_client().chat([{"role": "user", "content": "Hallo"}]))


def test_embedding_client_fingerprint_ignores_api_base_trailing_slash() -> None:
    left = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_base="https://api.example.com/v1"))
    right = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_base="https://api.example.com/v1/"))

    assert left.fingerprint() == right.fingerprint()
