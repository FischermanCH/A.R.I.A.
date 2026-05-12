from __future__ import annotations

import asyncio

import aria.core.pricing_catalog as pricing_catalog


def test_resolve_bundled_pricing_entry_accepts_claude_family_alias(monkeypatch) -> None:
    monkeypatch.setattr(
        pricing_catalog,
        "_cached_bundled_pricing_catalog",
        lambda: {
            "chat_models": {
                "anthropic/claude-sonnet-4-5": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                    "source_name": "ARIA bundled pricing seed",
                },
            },
            "embedding_models": {},
        },
    )

    entry = pricing_catalog.resolve_bundled_pricing_entry("claude-sonnet")

    assert entry is not None
    assert entry.input_per_million == 3.0
    assert entry.output_per_million == 15.0


def test_resolve_bundled_pricing_entry_normalizes_latest_variant(monkeypatch) -> None:
    monkeypatch.setattr(
        pricing_catalog,
        "_cached_bundled_pricing_catalog",
        lambda: {
            "chat_models": {
                "anthropic/claude-sonnet-4-5": {
                    "input_per_million": 3.0,
                    "output_per_million": 15.0,
                    "source_name": "ARIA bundled pricing seed",
                },
            },
            "embedding_models": {},
        },
    )

    entry = pricing_catalog.resolve_bundled_pricing_entry("anthropic/claude-3-5-sonnet-latest")

    assert entry is not None
    assert entry.input_per_million == 3.0
    assert entry.output_per_million == 15.0


def test_build_bundled_pricing_catalog_exposes_known_openai_and_anthropic_prices() -> None:
    catalog = pricing_catalog.build_bundled_pricing_catalog(verified_at="2026-05-07")

    assert catalog["chat_models"]["openai/gpt-4o-mini"]["input_per_million"] == 0.15
    assert catalog["chat_models"]["gpt-4o-mini"]["output_per_million"] == 0.60
    assert catalog["chat_models"]["anthropic/claude-sonnet-4-5"]["output_per_million"] == 15.00
    assert catalog["embedding_models"]["openai/text-embedding-3-small"]["input_per_million"] == 0.02


def test_resolve_pricing_entry_maps_common_embedding_deployment_aliases() -> None:
    entry = pricing_catalog.resolve_pricing_entry({}, "openai/embed-small")

    assert entry is not None
    assert entry.input_per_million == 0.02


def test_resolve_pricing_entry_uses_configured_model_aliases() -> None:
    entry = pricing_catalog.resolve_pricing_entry(
        {},
        "company/fast-embed",
        model_aliases={"company/fast-embed": "openai/text-embedding-3-small"},
    )

    assert entry is not None
    assert entry.input_per_million == 0.02


def test_fetch_litellm_pricing_catalog_normalizes_chat_and_embedding_prices(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "gpt-4o-mini": {
                    "input_cost_per_token": 0.00000015,
                    "output_cost_per_token": 0.0000006,
                    "litellm_provider": "openai",
                    "mode": "chat",
                },
                "text-embedding-3-small": {
                    "input_cost_per_token": 0.00000002,
                    "litellm_provider": "openai",
                    "mode": "embedding",
                },
            }

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str]):
            assert url == pricing_catalog.LITELLM_PRICING_URL
            return FakeResponse()

    monkeypatch.setattr(pricing_catalog.httpx, "AsyncClient", FakeClient)

    catalog = asyncio.run(pricing_catalog.fetch_litellm_pricing_catalog(verified_at="2026-05-07"))

    assert catalog["chat_models"]["openai/gpt-4o-mini"]["input_per_million"] == 0.15
    assert catalog["chat_models"]["gpt-4o-mini"]["output_per_million"] == 0.6
    assert catalog["embedding_models"]["openai/text-embedding-3-small"]["input_per_million"] == 0.02
    assert catalog["embedding_models"]["text-embedding-3-small"]["source_name"] == "LiteLLM GitHub pricing JSON"


def test_build_pricing_catalog_snapshot_uses_litellm_cache_as_primary_source(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        pricing_catalog,
        "build_bundled_pricing_catalog",
        lambda *, verified_at=None: {
            "chat_models": {"openai/gpt-4o-mini": {"input_per_million": 0.15, "output_per_million": 0.6}},
            "embedding_models": {},
        },
    )

    async def fake_litellm_payload(*, timeout_seconds: float):
        captured["litellm_timeout_seconds"] = timeout_seconds
        return {
            "claude-sonnet-4-5": {
                "input_cost_per_token": 0.000003,
                "output_cost_per_token": 0.000015,
                "litellm_provider": "anthropic",
                "mode": "chat",
            }
        }

    monkeypatch.setattr(pricing_catalog, "fetch_litellm_pricing_payload", fake_litellm_payload)

    snapshot = asyncio.run(pricing_catalog.build_pricing_catalog_snapshot(litellm_cache_file=tmp_path / "prices.json"))

    assert captured["litellm_timeout_seconds"] == 3.0
    assert snapshot["default_source_name"] == "LiteLLM GitHub pricing JSON"
    assert snapshot["chat_models"]["anthropic/claude-sonnet-4-5"]["input_per_million"] == 3.0
    assert snapshot["litellm_cache"]["refreshed"] is True


def test_build_pricing_catalog_snapshot_reuses_fresh_litellm_cache(monkeypatch, tmp_path) -> None:
    cache_path = tmp_path / "prices.json"
    cache_path.write_text(
        '{"text-embedding-3-small":{"input_cost_per_token":0.00000002,"litellm_provider":"openai","mode":"embedding"}}',
        encoding="utf-8",
    )

    async def fail_if_called(*, timeout_seconds: float):
        raise AssertionError("fresh cache should avoid remote refresh")

    monkeypatch.setattr(pricing_catalog, "fetch_litellm_pricing_payload", fail_if_called)

    snapshot = asyncio.run(pricing_catalog.build_pricing_catalog_snapshot(litellm_cache_file=cache_path))

    assert snapshot["default_source_name"] == "LiteLLM GitHub pricing JSON"
    assert snapshot["embedding_models"]["openai/text-embedding-3-small"]["input_per_million"] == 0.02
    assert snapshot["litellm_cache"]["used_cache"] is True


def test_build_pricing_catalog_snapshot_keeps_bundled_prices_when_litellm_unavailable_without_cache(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        pricing_catalog,
        "build_bundled_pricing_catalog",
        lambda *, verified_at=None: {
            "chat_models": {"anthropic/claude-sonnet-4-5": {"input_per_million": 3.0, "output_per_million": 15.0}},
            "embedding_models": {},
        },
    )

    async def failing_litellm_payload(*, timeout_seconds: float):
        raise TimeoutError("litellm timeout")

    monkeypatch.setattr(pricing_catalog, "fetch_litellm_pricing_payload", failing_litellm_payload)

    snapshot = asyncio.run(pricing_catalog.build_pricing_catalog_snapshot(litellm_cache_file=tmp_path / "missing.json"))

    assert "anthropic/claude-sonnet-4-5" in snapshot["chat_models"]
    assert snapshot["default_source_name"] == "ARIA bundled pricing seed"
    assert snapshot["errors"] == ["LiteLLM pricing refresh failed: litellm timeout"]
