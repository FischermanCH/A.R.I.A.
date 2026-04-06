from __future__ import annotations

import aria.core.pricing_catalog as pricing_catalog


def test_resolve_litellm_pricing_entry_accepts_claude_family_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        pricing_catalog,
        "_cached_litellm_pricing_catalog",
        lambda: {
            "chat_models": {
                "anthropic/claude-sonnet-4-5": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                    "source_name": "LiteLLM model_cost",
                },
            },
            "embedding_models": {},
        },
    )

    entry = pricing_catalog.resolve_litellm_pricing_entry("claude-sonnet")

    assert entry is not None
    assert entry.input_per_million == 3.0
    assert entry.output_per_million == 15.0


def test_resolve_litellm_pricing_entry_normalizes_latest_variant(monkeypatch) -> None:
    monkeypatch.setattr(
        pricing_catalog,
        "_cached_litellm_pricing_catalog",
        lambda: {
            "chat_models": {
                "anthropic/claude-sonnet-4-5": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                    "source_name": "LiteLLM model_cost",
                },
            },
            "embedding_models": {},
        },
    )

    entry = pricing_catalog.resolve_litellm_pricing_entry("anthropic/claude-3-5-sonnet-latest")

    assert entry is not None
    assert entry.input_per_million == 3.0
    assert entry.output_per_million == 15.0
