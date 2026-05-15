from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.core.config import Settings
from aria.core import connection_runtime
import aria.core.learned_recipe_store as learned_store
import aria.web.stats_routes as stats_routes
from aria.web.stats_routes import (
    OPERATOR_GUARDRAIL_ROW_KEYS,
    _attach_connection_edit_urls,
    _build_model_gateway_meta,
    _build_operator_guardrail_meta,
    _build_preflight_meta,
    _build_pricing_meta,
    _build_recipe_experience_memory_meta,
    _build_stats_model_totals,
    _build_qdrant_storage_meta,
    _build_release_meta,
    _collapse_large_connection_groups,
    _collapse_connection_kind_rows,
    _refresh_pricing_snapshot,
    _collapse_rss_rows,
    _directory_size_bytes,
    _save_manual_pricing_model,
    _save_pricing_alias_override,
    _extract_qdrant_telemetry_disk_bytes,
    register_stats_routes,
)


def test_build_settings_connection_status_rows_supports_sftp_key_profiles(monkeypatch, tmp_path) -> None:
    connect_calls: list[dict[str, object]] = []

    class FakeSFTPClient:
        def listdir(self, _path: str) -> list[str]:
            return []

        def close(self) -> None:
            return None

    class FakeSSHClient:
        def set_missing_host_key_policy(self, _policy: object) -> None:
            return None

        def connect(self, **kwargs: object) -> None:
            connect_calls.append(kwargs)

        def open_sftp(self) -> FakeSFTPClient:
            return FakeSFTPClient()

        def close(self) -> None:
            return None

    fake_paramiko = SimpleNamespace(
        SSHClient=FakeSSHClient,
        AutoAddPolicy=lambda: object(),
    )

    key_path = tmp_path / "data" / "ssh_keys" / "stats_sftp_ed25519"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text("private-key", encoding="utf-8")

    monkeypatch.setattr(connection_runtime, "_project_root", lambda: tmp_path)
    monkeypatch.setitem(__import__("sys").modules, "paramiko", fake_paramiko)

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "connections": {
                "sftp": {
                    "stats-sftp": {
                        "host": "10.0.1.20",
                        "port": 22,
                        "user": "backup",
                        "key_path": "data/ssh_keys/stats_sftp_ed25519",
                        "root_path": "/data",
                    }
                }
            }
        }
    )

    rows = connection_runtime.build_settings_connection_status_rows(settings, base_dir=tmp_path)

    assert rows
    assert rows[0]["kind"] == "SFTP"
    assert rows[0]["status"] == "ok"
    assert connect_calls
    assert connect_calls[0]["key_filename"] == str(Path(tmp_path / "data" / "ssh_keys" / "stats_sftp_ed25519"))


def test_collapse_rss_rows_summarises_rss_and_keeps_other_connections() -> None:
    rows = [
        {"kind": "RSS", "ref": "feed-a", "status": "ok"},
        {"kind": "RSS", "ref": "feed-b", "status": "error"},
        {"kind": "SFTP", "ref": "srv-a", "status": "ok"},
    ]

    filtered_rows = _collapse_rss_rows(rows)

    assert len(filtered_rows) == 2
    assert filtered_rows[0]["kind"] == "RSS"
    assert filtered_rows[0]["status"] == "error"
    assert filtered_rows[0]["target"] == "2 konfigurierte Feeds"
    assert filtered_rows[0]["message"] == "1 grün · 1 rot"
    assert filtered_rows[0]["edit_url"] == "/config/connections/rss"
    assert filtered_rows[1]["kind"] == "SFTP"


def test_collapse_connection_kind_rows_summarises_ssh_profiles_from_threshold() -> None:
    rows = [
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-a", "status": "ok"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-b", "status": "ok"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-c", "status": "ok"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-d", "status": "error"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-e", "status": "ok"},
        {"kind_key": "rss", "kind": "RSS", "ref": "feed-a", "status": "ok"},
    ]

    filtered_rows = _collapse_connection_kind_rows(rows, kind_key="ssh", threshold=5, language="de")

    assert len(filtered_rows) == 2
    assert filtered_rows[0]["kind"] == "SSH"
    assert filtered_rows[0]["status"] == "error"
    assert filtered_rows[0]["target"] == "5 konfigurierte SSH-Profile"
    assert filtered_rows[0]["message"] == "4 grün · 1 rot"
    assert filtered_rows[0]["edit_url"] == "/config/connections/ssh"
    assert filtered_rows[1]["kind"] == "RSS"


def test_collapse_large_connection_groups_summarises_all_kinds_above_threshold() -> None:
    rows = [
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-a", "status": "ok"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-b", "status": "ok"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-c", "status": "warn"},
        {"kind_key": "ssh", "kind": "SSH", "ref": "srv-d", "status": "error"},
        {"kind_key": "rss", "kind": "RSS", "ref": "feed-a", "status": "ok"},
        {"kind_key": "rss", "kind": "RSS", "ref": "feed-b", "status": "ok"},
        {"kind_key": "rss", "kind": "RSS", "ref": "feed-c", "status": "ok"},
        {"kind_key": "rss", "kind": "RSS", "ref": "feed-d", "status": "error"},
        {"kind_key": "discord", "kind": "Discord", "ref": "alerts", "status": "ok"},
    ]

    filtered_rows = _collapse_large_connection_groups(rows, threshold=4, language="de")

    assert len(filtered_rows) == 3
    assert filtered_rows[0]["kind"] == "SSH"
    assert filtered_rows[0]["target"] == "4 konfigurierte SSH-Profile"
    assert filtered_rows[1]["kind"] == "RSS"
    assert filtered_rows[1]["target"] == "4 konfigurierte Feeds"
    assert filtered_rows[2]["kind"] == "Discord"


def test_build_settings_connection_status_rows_uses_cache_only_for_large_groups(monkeypatch) -> None:
    calls: list[tuple[str, str, bool, bool]] = []

    def fake_build_connection_status_row(
        kind: str,
        ref: str,
        row: object,
        *,
        page_probe: bool = False,
        cached_only: bool = False,
        base_dir: Path | None = None,
        lang: str = "de",
    ) -> dict[str, str]:
        del row, base_dir, lang
        calls.append((kind, ref, page_probe, cached_only))
        return {"kind_key": kind, "kind": kind.upper(), "ref": ref, "status": "ok"}

    monkeypatch.setattr(connection_runtime, "build_connection_status_row", fake_build_connection_status_row)
    monkeypatch.setattr(connection_runtime, "ordered_connection_kinds", lambda: ["ssh", "discord"])

    settings = SimpleNamespace(
        connections=SimpleNamespace(
            ssh={"a": {}, "b": {}, "c": {}, "d": {}},
            discord={"alerts": {}},
        )
    )

    rows = connection_runtime.build_settings_connection_status_rows(
        settings,
        page_probe=True,
        cached_only_threshold=4,
    )

    assert len(rows) == 5
    assert calls[:4] == [
        ("ssh", "a", False, True),
        ("ssh", "b", False, True),
        ("ssh", "c", False, True),
        ("ssh", "d", False, True),
    ]
    assert calls[4] == ("discord", "alerts", True, False)



def test_build_settings_connection_status_rows_can_force_cached_only(monkeypatch) -> None:
    calls: list[tuple[str, str, bool, bool]] = []

    def fake_build_connection_status_row(
        kind: str,
        ref: str,
        row: object,
        *,
        page_probe: bool = False,
        cached_only: bool = False,
        base_dir: Path | None = None,
        lang: str = "de",
    ) -> dict[str, str]:
        del row, base_dir, lang
        calls.append((kind, ref, page_probe, cached_only))
        return {"kind_key": kind, "kind": kind.upper(), "ref": ref, "status": "ok"}

    monkeypatch.setattr(connection_runtime, "build_connection_status_row", fake_build_connection_status_row)
    monkeypatch.setattr(connection_runtime, "ordered_connection_kinds", lambda: ["rss", "discord"])

    settings = SimpleNamespace(
        connections=SimpleNamespace(
            rss={"feed-a": {}, "feed-b": {}},
            discord={"alerts": {}},
        )
    )

    rows = connection_runtime.build_settings_connection_status_rows(
        settings,
        page_probe=False,
        cached_only=True,
        cached_only_threshold=4,
    )

    assert len(rows) == 3
    assert calls == [
        ("rss", "feed-a", False, True),
        ("rss", "feed-b", False, True),
        ("discord", "alerts", False, True),
    ]

def test_attach_connection_edit_urls_maps_rows_to_edit_pages() -> None:
    rows = [
        {"kind": "SFTP", "ref": "srv-a", "status": "ok"},
        {"kind": "HTTP API", "ref": "inventory-api", "status": "ok"},
        {"kind": "SMTP", "ref": "alerts-mail", "status": "ok"},
    ]

    enriched = _attach_connection_edit_urls(rows)

    assert enriched[0]["edit_url"] == "/config/connections/sftp?sftp_ref=srv-a"
    assert enriched[1]["edit_url"] == "/config/connections/http-api?http_api_ref=inventory-api"
    assert enriched[2]["edit_url"] == "/config/connections/smtp?email_ref=alerts-mail"


def test_directory_size_bytes_prefers_allocated_size_for_sparse_files(tmp_path) -> None:
    sparse = tmp_path / "sparse.bin"
    with sparse.open("wb") as handle:
        handle.seek((1024 * 1024) - 1)
        handle.write(b"\0")

    size_bytes = _directory_size_bytes(tmp_path)

    assert size_bytes < 1024 * 1024


def test_build_preflight_meta_maps_labels_and_counts() -> None:
    payload = {
        "status": "warn",
        "checked_at": "2026-03-31T10:20:30+00:00",
        "checks": [
            {"id": "prompts", "status": "ok", "summary_key": "prompts_ok", "skill_prompt_count": 2, "summary": "Prompt-Dateien ok.", "detail": "prompts/persona.md"},
            {"id": "qdrant", "status": "error", "summary_key": "qdrant_error", "summary": "Qdrant nicht erreichbar.", "detail": "timeout"},
            {"id": "embeddings", "status": "skipped", "summary_key": "embeddings_missing_model", "summary": "Nicht aktiv.", "detail": ""},
        ],
    }

    meta = _build_preflight_meta(payload, "de")

    assert meta["overall_status"] == "warn"
    assert meta["ok_count"] == 1
    assert meta["error_count"] == 1
    assert meta["skipped_count"] == 1
    assert meta["checks"][0]["name"] == "Prompt-Dateien"
    assert meta["checks"][0]["summary"] == "Prompt-Dateien ok (2 Rezept-Prompts)."
    assert meta["checks"][2]["visual_status"] == "warn"
    assert len(meta["issue_checks"]) == 2


def test_build_stats_model_totals_exposes_combined_model_usage() -> None:
    totals = _build_stats_model_totals(
        {
            "chat_total_tokens": 120,
            "embedding_total_tokens": 45,
            "extraction_total_tokens": 9,
        }
    )

    assert totals == {
        "chat_total_tokens": 120,
        "embedding_total_tokens": 45,
        "extraction_total_tokens": 9,
        "model_total_tokens": 174,
    }


def test_build_pricing_meta_flags_unpriced_model_tokens() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={},
            embedding_models={},
            last_updated="2026-05-04",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "chat_tokens_by_model": {"private_chat/unknown-model": 123},
        "embedding_tokens_by_model": {"private_embed/unknown-model": 45},
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is True
    assert meta["unpriced_model_tokens"] == 168
    assert meta["unpriced_chat_tokens"] == 123
    assert meta["unpriced_embedding_tokens"] == 45
    assert meta["unpriced_chat_models"] == ["private_chat/unknown-model"]
    assert meta["unpriced_embedding_models"] == ["private_embed/unknown-model"]
    assert meta["unpriced_model_rows"] == [
        {"kind": "Chat", "model": "private_chat/unknown-model", "tokens": 123},
        {"kind": "Embedding", "model": "private_embed/unknown-model", "tokens": 45},
    ]
    assert meta["priced_seen_chat_count"] == 0
    assert meta["priced_seen_embedding_count"] == 0


def test_build_pricing_meta_counts_priced_seen_models() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={"openai/gpt-4o-mini": object()},
            embedding_models={"openai/text-embedding-3-small": object()},
            last_updated="2026-05-04",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "chat_tokens_by_model": {"openai/gpt-4o-mini": 100},
        "embedding_tokens_by_model": {"openai/text-embedding-3-small": 20},
    }

    def fake_resolver(catalog: dict[str, object], model: str) -> object | None:
        return catalog.get(model)

    meta = _build_pricing_meta(stats, settings, fake_resolver)

    assert meta["has_unpriced_usage"] is False
    assert meta["unpriced_model_tokens"] == 0
    assert meta["priced_seen_chat_count"] == 1
    assert meta["priced_seen_embedding_count"] == 1
    assert meta["unpriced_chat_models"] == []
    assert meta["unpriced_embedding_models"] == []


def test_build_pricing_meta_uses_bundled_fallback_for_known_models() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={},
            embedding_models={},
            last_updated="2026-05-04",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "chat_tokens_by_model": {"anthropic/claude-sonnet-4-20250514": 100},
        "embedding_tokens_by_model": {"openai/text-embedding-3-small": 20},
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is False
    assert meta["unpriced_model_tokens"] == 0
    assert meta["priced_seen_chat_count"] == 1
    assert meta["priced_seen_embedding_count"] == 1
    assert meta["unpriced_chat_models"] == []
    assert meta["unpriced_embedding_models"] == []
    assert meta["estimated_total_cost_usd"] > 0.0
    assert meta["estimated_chat_cost_usd_by_model"]["anthropic/claude-sonnet-4-20250514"] > 0.0
    assert meta["estimated_embedding_cost_usd_by_model"]["openai/text-embedding-3-small"] > 0.0


def test_build_pricing_meta_prices_embedding_deployment_aliases() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            model_aliases={},
            chat_models={},
            embedding_models={},
            last_updated="2026-05-07",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "embedding_tokens_by_model": {
            "openai/embed-small": 635,
            "embed-small": 0,
        },
        "embedding_prompt_tokens_by_model": {
            "openai/embed-small": 635,
            "embed-small": 0,
        },
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is False
    assert meta["unpriced_model_tokens"] == 0
    assert meta["priced_seen_embedding_count"] == 2
    assert meta["unpriced_embedding_models"] == []
    assert meta["estimated_embedding_cost_usd_by_model"]["openai/embed-small"] > 0.0


def test_build_pricing_meta_uses_bundled_fallback_for_non_openai_providers(monkeypatch) -> None:
    import aria.core.pricing_catalog as pricing_catalog

    monkeypatch.setattr(
        pricing_catalog,
        "_cached_bundled_pricing_catalog",
        lambda: {
            "chat_models": {
                "azure/gpt-4o-mini": {
                    "input_per_million": 0.15,
                    "output_per_million": 0.6,
                    "source_name": "ARIA bundled pricing seed",
                },
                "bedrock/anthropic.claude-3-haiku": {
                    "input_per_million": 0.25,
                    "output_per_million": 1.25,
                    "source_name": "ARIA bundled pricing seed",
                },
            },
            "embedding_models": {
                "cohere/embed-v4.0": {
                    "input_per_million": 0.12,
                    "source_name": "ARIA bundled pricing seed",
                },
            },
        },
    )
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={},
            embedding_models={},
            last_updated="2026-05-07",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "chat_tokens_by_model": {
            "azure/gpt-4o-mini": 100,
            "bedrock/anthropic.claude-3-haiku": 50,
        },
        "embedding_tokens_by_model": {"cohere/embed-v4.0": 20},
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is False
    assert meta["unpriced_model_tokens"] == 0
    assert meta["priced_seen_chat_count"] == 2
    assert meta["priced_seen_embedding_count"] == 1


def test_build_pricing_meta_reprices_known_models_when_logged_cost_is_missing() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={},
            embedding_models={},
            last_updated="2026-05-04",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "total_cost_usd": 0.0,
        "chat_tokens_by_model": {"anthropic/claude-sonnet-4-5": 125},
        "chat_prompt_tokens_by_model": {"anthropic/claude-sonnet-4-5": 100},
        "chat_completion_tokens_by_model": {"anthropic/claude-sonnet-4-5": 25},
        "embedding_tokens_by_model": {"openai/text-embedding-3-small": 30},
        "embedding_prompt_tokens_by_model": {"openai/text-embedding-3-small": 30},
        "chat_cost_usd_by_model": {},
        "embedding_cost_usd_by_model": {},
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is False
    assert meta["estimated_total_cost_usd"] > 0.0
    assert meta["logged_total_cost_usd"] == 0.0
    assert meta["estimated_cost_gap_usd"] == meta["estimated_total_cost_usd"]
    assert meta["has_estimated_cost_gap"] is True


def test_build_pricing_meta_treats_logged_numeric_cost_as_priced() -> None:
    settings = SimpleNamespace(
        pricing=SimpleNamespace(
            enabled=True,
            currency="USD",
            chat_models={},
            embedding_models={},
            last_updated="2026-05-04",
            default_source_name="test",
            default_source_url="",
        )
    )
    stats = {
        "chat_tokens_by_model": {"custom-priced-chat": 100},
        "embedding_tokens_by_model": {"custom-priced-embedding": 20},
        "chat_cost_usd_by_model": {"custom-priced-chat": 0.001},
        "embedding_cost_usd_by_model": {"custom-priced-embedding": 0.0},
    }

    meta = _build_pricing_meta(stats, settings, lambda _catalog, _model: None)

    assert meta["has_unpriced_usage"] is False
    assert meta["unpriced_model_tokens"] == 0
    assert meta["priced_seen_chat_count"] == 1
    assert meta["priced_seen_embedding_count"] == 1


def test_build_model_gateway_meta_reports_shared_runtime_clients() -> None:
    usage_meter = object()
    llm_client = SimpleNamespace(model="anthropic/claude-sonnet-4-5", usage_meter=usage_meter)

    class FakeEmbeddingClient:
        def __init__(self, meter: object) -> None:
            self.usage_meter = meter

        @staticmethod
        def _resolve_model() -> str:
            return "openai/text-embedding-3-small"

    embedding_client = FakeEmbeddingClient(usage_meter)
    pipeline = SimpleNamespace(
        usage_meter=usage_meter,
        llm_client=llm_client,
        embedding_client=embedding_client,
        memory_skill=SimpleNamespace(embedding_client=embedding_client),
    )
    settings = SimpleNamespace(
        llm=SimpleNamespace(model="fallback-chat"),
        embeddings=SimpleNamespace(model="fallback-embedding"),
        token_tracking=SimpleNamespace(enabled=True, log_file="data/logs/tokens.jsonl"),
    )
    stats = {
        "chat_total_tokens": 11,
        "embedding_total_tokens": 7,
        "model_total_tokens": 18,
    }
    pricing_meta = {
        "priced_seen_chat_count": 1,
        "priced_seen_embedding_count": 1,
        "unpriced_model_tokens": 0,
        "has_unpriced_usage": False,
    }

    meta = _build_model_gateway_meta(stats, settings, pipeline, pricing_meta)

    assert meta["status"] == "ok"
    assert meta["chat_model"] == "anthropic/claude-sonnet-4-5"
    assert meta["embedding_model"] == "openai/text-embedding-3-small"
    assert meta["usage_meter_shared"] is True
    assert meta["chat_total_tokens"] == 11
    assert meta["embedding_total_tokens"] == 7
    assert {row["status"] for row in meta["rows"]} == {"ok"}


def test_build_model_gateway_meta_flags_split_usage_meter() -> None:
    pipeline = SimpleNamespace(
        usage_meter=object(),
        llm_client=SimpleNamespace(model="openai/gpt-4o", usage_meter=object()),
        embedding_client=SimpleNamespace(model="openai/text-embedding-3-small", usage_meter=object()),
        memory_skill=None,
    )
    settings = SimpleNamespace(
        llm=SimpleNamespace(model="openai/gpt-4o"),
        embeddings=SimpleNamespace(model="openai/text-embedding-3-small"),
        token_tracking=SimpleNamespace(enabled=False, log_file=""),
    )

    meta = _build_model_gateway_meta(
        {},
        settings,
        pipeline,
        {"has_unpriced_usage": True, "unpriced_model_tokens": 42},
    )

    assert meta["status"] == "error"
    assert meta["usage_meter_shared"] is False
    assert meta["has_unpriced_usage"] is True
    assert meta["unpriced_model_tokens"] == 42
    assert [row["status"] for row in meta["rows"]] == ["error", "error", "warn", "warn"]


def test_build_operator_guardrail_meta_combines_gateway_pricing_health_and_updates() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={
            "has_unpriced_usage": True,
            "unpriced_model_tokens": 42,
            "priced_seen_chat_count": 1,
            "chat_seen_count": 2,
            "priced_seen_embedding_count": 0,
            "embedding_seen_count": 1,
        },
        model_gateway={
            "status": "ok",
            "chat_model": "claude-sonnet-4-5",
            "embedding_model": "openai/embed-small",
            "usage_meter_shared": True,
            "token_tracking_enabled": True,
            "model_total_tokens": 123,
        },
        preflight_meta={"overall_status": "ok", "ok_count": 4, "warn_count": 0, "error_count": 0, "checked_at": "2026-05-12T10:00:00Z"},
        health_meta={"overall_status": "warn", "ok_count": 6, "warn_count": 1, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha252", "update_available": True},
        recipe_experience_memory={"enabled": True, "status": "ok", "collection_count": 1, "point_count": 4},
        language="en",
    )

    assert meta["overall_status"] == "warn"
    assert meta["ok_count"] == 5
    assert meta["warn_count"] == 3
    assert meta["error_count"] == 0
    assert [row["status"] for row in meta["rows"]] == ["ok", "ok", "warn", "ok", "ok", "ok", "warn", "warn"]
    assert [row["key"] for row in meta["rows"]] == list(OPERATOR_GUARDRAIL_ROW_KEYS)
    assert meta["rows"][0]["fallback"] == "Release metadata"
    assert meta["rows"][2]["summary"] == "42 model tokens are still unpriced."
    assert meta["rows"][3]["fallback"] == "Cost tracking"
    assert meta["rows"][4]["fallback"] == "Recipe Experience Memory"
    assert meta["rows"][4]["detail"] == "1 collections · 4 points"
    assert meta["rows"][7]["url"] == "/updates"


def test_operator_guardrail_rows_are_machine_addressable_without_recipe_memory() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={"has_unpriced_usage": False, "unpriced_model_tokens": 0},
        model_gateway={"status": "ok", "chat_model": "x", "embedding_model": "y", "usage_meter_shared": True, "token_tracking_enabled": True},
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha251", "update_available": False},
        recipe_experience_memory=None,
        language="en",
    )

    expected_without_optional_memory = [key for key in OPERATOR_GUARDRAIL_ROW_KEYS if key != "recipe_memory"]
    assert [row["key"] for row in meta["rows"]] == expected_without_optional_memory
    assert all(row["label_key"] == f"stats.operator_guardrail_{row['key']}" for row in meta["rows"])


def test_build_operator_guardrail_meta_escalates_errors() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={"has_unpriced_usage": False, "unpriced_model_tokens": 0},
        model_gateway={"status": "error", "chat_model": "x", "embedding_model": "y"},
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha251", "update_available": False},
        language="de",
    )

    assert meta["overall_status"] == "error"
    assert meta["error_count"] == 1
    assert meta["summary"] == "Mindestens eine Operator-Guardrail meldet aktuell einen Fehler."


def test_build_operator_guardrail_meta_treats_disabled_token_tracking_as_error() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={
            "has_unpriced_usage": False,
            "unpriced_model_tokens": 0,
            "logged_total_cost_usd": 0.0,
            "estimated_total_cost_usd": 0.0,
        },
        model_gateway={
            "status": "warn",
            "chat_model": "x",
            "embedding_model": "y",
            "usage_meter_shared": True,
            "token_tracking_enabled": False,
            "model_total_tokens": 0,
        },
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha251", "update_available": False},
        language="de",
    )

    cost_row = meta["rows"][3]
    assert meta["overall_status"] == "error"
    assert cost_row["status"] == "error"
    assert cost_row["summary"] == "Token-Tracking ist deaktiviert."


def test_build_operator_guardrail_meta_warns_on_estimated_cost_gap() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={
            "has_unpriced_usage": False,
            "unpriced_model_tokens": 0,
            "logged_total_cost_usd": 0.001,
            "estimated_total_cost_usd": 0.009,
            "has_estimated_cost_gap": True,
        },
        model_gateway={
            "status": "ok",
            "chat_model": "x",
            "embedding_model": "y",
            "usage_meter_shared": True,
            "token_tracking_enabled": True,
            "model_total_tokens": 1200,
        },
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha251", "update_available": False},
        language="en",
    )

    cost_row = meta["rows"][3]
    assert meta["overall_status"] == "warn"
    assert cost_row["status"] == "warn"
    assert cost_row["summary"] == "Estimated costs are higher than logged costs."
    assert "1200 tokens" in cost_row["detail"]


def test_build_operator_guardrail_meta_treats_missing_release_metadata_as_error() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "", "version": ""},
        pricing_meta={"has_unpriced_usage": False, "unpriced_model_tokens": 0},
        model_gateway={"status": "ok", "chat_model": "x", "embedding_model": "y"},
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "", "latest_label": "", "update_available": False},
        language="en",
    )

    assert meta["overall_status"] == "error"
    assert meta["rows"][0]["status"] == "error"
    assert meta["rows"][0]["summary"] == "Release metadata is incomplete."


def test_build_operator_guardrail_meta_warns_on_recipe_memory_errors() -> None:
    meta = _build_operator_guardrail_meta(
        release_meta={"label": "0.1.0-alpha251", "version": "0.1.0"},
        pricing_meta={"has_unpriced_usage": False, "unpriced_model_tokens": 0},
        model_gateway={"status": "ok", "chat_model": "x", "embedding_model": "y"},
        preflight_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        health_meta={"overall_status": "ok", "ok_count": 1, "warn_count": 0, "error_count": 0},
        update_status={"current_label": "0.1.0-alpha251", "latest_label": "0.1.0-alpha251", "update_available": False},
        recipe_experience_memory={"enabled": True, "status": "error", "collection_count": 0, "point_count": 0, "error": "qdrant timeout"},
        language="de",
    )

    memory_row = meta["rows"][4]
    assert meta["overall_status"] == "warn"
    assert memory_row["fallback"] == "Recipe Experience Memory"
    assert memory_row["status"] == "warn"
    assert memory_row["summary"] == "Recipe Experience Memory ist aktiviert, aber aktuell nicht erreichbar."
    assert "qdrant timeout" in memory_row["detail"]


def test_build_recipe_experience_memory_meta_counts_qdrant_collections(monkeypatch) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333"},
        }
    )

    class FakeClient:
        async def get_collections(self):
            return SimpleNamespace(
                collections=[
                    SimpleNamespace(name="aria_recipe_experience_neo"),
                    SimpleNamespace(name="aria_recipe_experiencefoo"),
                    SimpleNamespace(name="aria_memory_neo"),
                ]
            )

        async def get_collection(self, collection_name: str):
            assert collection_name == "aria_recipe_experience_neo"
            return SimpleNamespace(points_count=3)

        async def scroll(self, collection_name: str, limit: int, with_payload: bool, with_vectors: bool):
            assert collection_name == "aria_recipe_experience_neo"
            assert limit == 5
            assert with_payload is True
            assert with_vectors is False
            return (
                [
                    SimpleNamespace(
                        payload={
                            "source": "recipe_experience",
                            "recipe_id": "learned-dns-health",
                            "title": "DNS health",
                            "intent": "health_check",
                            "connection_kind": "ssh",
                            "connection_ref": "pihole1",
                            "capability": "ssh_command",
                            "chosen_action": "uptime -p && df -h",
                            "experience_summary": "ok",
                            "user_message": "check dns",
                            "experience_count": 3,
                            "learning_origin": "guardrail_healthcheck_fallback",
                            "updated_at": "2026-05-08T00:00:00Z",
                        }
                    )
                ],
                None,
            )

    monkeypatch.setattr(stats_routes, "create_async_qdrant_client", lambda **_kwargs: FakeClient())

    meta = asyncio.run(_build_recipe_experience_memory_meta(settings))

    assert meta["status"] == "ok"
    assert meta["collection_count"] == 1
    assert meta["point_count"] == 3
    assert meta["collections"] == [{"name": "aria_recipe_experience_neo", "points": 3}]
    assert meta["recent_rows"] == [
        {
            "recipe_id": "learned-dns-health",
            "title": "DNS health",
            "target": "ssh/pihole1",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "action": "uptime -p && df -h",
            "summary": "ok",
            "user_message": "check dns",
            "experience_count": 3,
            "origin": "guardrail_healthcheck_fallback",
            "updated_at": "2026-05-08T00:00:00Z",
        }
    ]


def test_build_preflight_meta_localizes_summaries_for_english() -> None:
    payload = {
        "status": "ok",
        "checked_at": "2026-03-31T10:20:30+00:00",
        "checks": [
            {"id": "prompts", "status": "ok", "summary_key": "prompts_ok", "skill_prompt_count": 2, "summary": "Prompt-Dateien ok (2 Skill-Prompts).", "detail": "prompts/persona.md"},
            {"id": "qdrant", "status": "ok", "summary_key": "qdrant_ok", "collection_count": 0, "summary": "Qdrant erreichbar (0 Collections).", "detail": "http://localhost:6333"},
            {"id": "llm", "status": "ok", "summary_key": "llm_ok", "summary": "LLM erreichbar.", "detail": "gpt-4.1"},
            {"id": "embeddings", "status": "ok", "summary_key": "embeddings_ok", "summary": "Embeddings erreichbar.", "detail": "embed-small"},
        ],
    }

    meta = _build_preflight_meta(payload, "en")

    assert meta["checks"][0]["summary"] == "Prompt files ok (2 recipe prompts)."
    assert meta["checks"][1]["summary"] == "Qdrant reachable (0 collections)."
    assert meta["checks"][2]["summary"] == "LLM reachable."
    assert meta["checks"][3]["summary"] == "Embeddings reachable."


def test_build_preflight_meta_includes_active_profile_names() -> None:
    payload = {
        "status": "warn",
        "checked_at": "2026-03-31T10:20:30+00:00",
        "checks": [
            {"id": "llm", "status": "error", "summary_key": "llm_error", "summary": "LLM nicht erreichbar.", "detail": "model-a"},
            {"id": "embeddings", "status": "ok", "summary_key": "embeddings_ok", "summary": "Embeddings erreichbar.", "detail": "model-b"},
        ],
    }

    meta = _build_preflight_meta(payload, "de", active_profiles={"llm": "litellm-main", "embeddings": "litellm-emb"})

    assert meta["checks"][0]["name"] == "Chat LLM (litellm-main)"
    assert meta["checks"][1]["name"] == "Embeddings (litellm-emb)"


def test_build_release_meta_uses_env_override(tmp_path, monkeypatch) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    monkeypatch.setenv("ARIA_RELEASE_LABEL", "0.1.0-alpha7")

    meta = _build_release_meta(tmp_path)

    assert meta["version"] == "0.1.0"
    assert meta["label"] == "0.1.0-alpha7"


def test_extract_qdrant_telemetry_disk_bytes_prefers_segment_disk_usage() -> None:
    telemetry = SimpleNamespace(
        result=SimpleNamespace(
            collections=SimpleNamespace(
                number_of_collections=2,
                collections=[
                    SimpleNamespace(
                        shards=[
                            SimpleNamespace(
                                local=SimpleNamespace(
                                    segments=[
                                        SimpleNamespace(info=SimpleNamespace(disk_usage_bytes=1024)),
                                        SimpleNamespace(info=SimpleNamespace(disk_usage_bytes=2048)),
                                    ],
                                    vectors_size_bytes=999999,
                                    payloads_size_bytes=999999,
                                )
                            )
                        ]
                    ),
                    SimpleNamespace(
                        shards=[
                            SimpleNamespace(
                                local=SimpleNamespace(
                                    segments=[],
                                    vectors_size_bytes=4096,
                                    payloads_size_bytes=512,
                                )
                            )
                        ]
                    ),
                ],
            )
        )
    )

    total_bytes, collection_count = _extract_qdrant_telemetry_disk_bytes(telemetry)

    assert total_bytes == 7680
    assert collection_count == 2


def test_build_qdrant_storage_meta_uses_qdrant_telemetry_for_remote_service(monkeypatch, tmp_path) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {
                "enabled": True,
                "backend": "qdrant",
                "qdrant_url": "http://qdrant:6333",
            },
        }
    )

    class FakeServiceApi:
        async def telemetry(self, details_level: int | None = None, timeout: int | None = None) -> object:
            assert details_level == 1
            assert timeout == 4
            return SimpleNamespace(
                result=SimpleNamespace(
                    collections=SimpleNamespace(
                        number_of_collections=1,
                        collections=[
                            SimpleNamespace(
                                shards=[
                                    SimpleNamespace(
                                        local=SimpleNamespace(
                                            segments=[
                                                SimpleNamespace(info=SimpleNamespace(disk_usage_bytes=3 * 1024 * 1024))
                                            ],
                                            vectors_size_bytes=None,
                                            payloads_size_bytes=None,
                                        )
                                    )
                                ]
                            )
                        ],
                    )
                )
            )

    class FakeClient:
        def __init__(self) -> None:
            self._client = SimpleNamespace(openapi_client=SimpleNamespace(service_api=FakeServiceApi()))
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    fake_client = FakeClient()
    monkeypatch.setattr(stats_routes, "create_async_qdrant_client", lambda **_: fake_client)

    meta = asyncio.run(_build_qdrant_storage_meta(tmp_path, settings))

    assert meta["available"] is True
    assert meta["size_human"] == "3.00 MB"
    assert meta["path"] == "Telemetry · 1 Collections"
    assert fake_client.closed is True


def test_build_qdrant_storage_meta_prefers_local_storage_when_telemetry_reports_zero_bytes(
    monkeypatch,
    tmp_path,
) -> None:
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "memory": {
                "enabled": True,
                "backend": "qdrant",
                "qdrant_url": "http://localhost:6333",
            },
        }
    )

    local_qdrant_file = tmp_path / "data" / "qdrant" / "collection" / "segment.bin"
    local_qdrant_file.parent.mkdir(parents=True, exist_ok=True)
    local_qdrant_file.write_bytes(b"x" * 4096)

    class FakeServiceApi:
        async def telemetry(self, details_level: int | None = None, timeout: int | None = None) -> object:
            assert details_level == 1
            assert timeout == 4
            return SimpleNamespace(
                result=SimpleNamespace(
                    collections=SimpleNamespace(
                        number_of_collections=1,
                        collections=[
                            SimpleNamespace(
                                shards=[
                                    SimpleNamespace(
                                        local=SimpleNamespace(
                                            segments=[
                                                SimpleNamespace(info=SimpleNamespace(disk_usage_bytes=0))
                                            ],
                                            vectors_size_bytes=0,
                                            payloads_size_bytes=0,
                                        )
                                    )
                                ]
                            )
                        ],
                    )
                )
            )

    class FakeClient:
        def __init__(self) -> None:
            self._client = SimpleNamespace(openapi_client=SimpleNamespace(service_api=FakeServiceApi()))

        async def close(self) -> None:
            return None

    monkeypatch.setattr(stats_routes, "create_async_qdrant_client", lambda **_: FakeClient())

    meta = asyncio.run(_build_qdrant_storage_meta(tmp_path, settings))

    assert meta["available"] is True
    assert meta["size_human"] == "4.0 KB"
    assert meta["path"] == str(tmp_path / "data" / "qdrant")


def test_refresh_pricing_snapshot_updates_config_and_settings(monkeypatch, tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        """
llm:
  model: fake
pricing:
  enabled: false
  currency: USD
  model_aliases:
    company/fast-chat: company/private-chat
    company/fast-embed: company/private-embed
  chat_models:
    company/private-chat:
      input_per_million: 1.23
      output_per_million: 4.56
      source_name: Manual
      notes: source=manual
    openai/gpt-4o-mini:
      input_per_million: 0.01
      output_per_million: 0.02
      source_name: Manual
      notes: source=manual
  embedding_models:
    company/private-embed:
      input_per_million: 0.77
      source_name: Custom contract
""".lstrip(),
        encoding="utf-8",
    )
    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "pricing": {
                "enabled": False,
                "currency": "USD",
                "chat_models": {},
                "embedding_models": {},
            },
        }
    )

    async def fake_snapshot(**kwargs: object) -> dict[str, object]:
        assert kwargs["include_litellm"] is True
        assert kwargs["include_openrouter"] is False
        assert kwargs["force_litellm_refresh"] is True
        return {
            "enabled": True,
            "currency": "USD",
            "last_updated": "2026-04-02",
            "default_source_name": "LiteLLM GitHub pricing JSON",
            "default_source_url": "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json",
            "chat_models": {
                "openai/gpt-4o-mini": {
                    "input_per_million": 0.15,
                    "output_per_million": 0.6,
                    "source_name": "ARIA bundled pricing seed",
                    "source_url": "https://platform.openai.com/docs/pricing",
                    "verified_at": "2026-04-02",
                    "notes": "provider=openai",
                }
            },
            "embedding_models": {
                "openai/text-embedding-3-small": {
                    "input_per_million": 0.02,
                    "source_name": "ARIA bundled pricing seed",
                    "source_url": "https://platform.openai.com/docs/pricing",
                    "verified_at": "2026-04-02",
                    "notes": "provider=openai",
                }
            },
            "errors": [],
        }

    monkeypatch.setattr(stats_routes, "build_pricing_catalog_snapshot", fake_snapshot)

    snapshot = asyncio.run(_refresh_pricing_snapshot(settings, tmp_path))

    raw = config_path.read_text(encoding="utf-8")
    assert "openai/gpt-4o-mini" in raw
    assert "openai/text-embedding-3-small" in raw
    assert "company/private-chat" in raw
    assert "company/private-embed" in raw
    assert "company/fast-chat" in raw
    assert "company/fast-embed" in raw
    assert snapshot["last_updated"] == "2026-04-02"
    assert settings.pricing.enabled is True
    assert settings.pricing.model_aliases["company/fast-chat"] == "company/private-chat"
    assert settings.pricing.model_aliases["company/fast-embed"] == "company/private-embed"
    assert settings.pricing.chat_models["openai/gpt-4o-mini"].input_per_million == 0.01
    assert settings.pricing.chat_models["company/private-chat"].output_per_million == 4.56
    assert settings.pricing.embedding_models["company/private-embed"].input_per_million == 0.77
    assert settings.pricing.embedding_models["openai/text-embedding-3-small"].input_per_million == 0.02

    pricing_meta = _build_pricing_meta(
        {
            "chat_tokens_by_model": {"company/fast-chat": 100},
            "chat_prompt_tokens_by_model": {"company/fast-chat": 80},
            "chat_completion_tokens_by_model": {"company/fast-chat": 20},
            "embedding_tokens_by_model": {"company/fast-embed": 50},
            "embedding_prompt_tokens_by_model": {"company/fast-embed": 50},
        },
        settings,
        lambda catalog, model: catalog.get(model),
    )
    assert pricing_meta["has_unpriced_usage"] is False
    assert any(row["model"] == "company/private-chat" and row["is_manual"] for row in pricing_meta["source_rows"])
    assert any(row["model"] == "company/private-embed" and row["is_manual"] for row in pricing_meta["source_rows"])
    assert {"alias": "company/fast-chat", "target": "company/private-chat"} in pricing_meta["alias_rows"]


def test_manual_pricing_admin_helpers_persist_alias_and_price(tmp_path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text("llm:\n  model: fake\n", encoding="utf-8")
    settings = Settings.model_validate({"llm": {"model": "fake"}})

    alias_result = _save_pricing_alias_override(
        settings,
        tmp_path,
        alias="company/embed-small",
        target="openai/text-embedding-3-small",
    )
    price_result = _save_manual_pricing_model(
        settings,
        tmp_path,
        kind="chat",
        model="company/private-chat",
        input_per_million=1.25,
        output_per_million=5.0,
        source_name="Manual",
        source_url="https://contracts.example/pricing",
        notes="private deployment",
    )

    raw = (config_dir / "config.yaml").read_text(encoding="utf-8")
    assert alias_result["alias"] == "company/embed-small"
    assert price_result["model"] == "company/private-chat"
    assert "company/embed-small" in raw
    assert "company/private-chat" in raw
    assert "manual_override=true" in raw
    assert settings.pricing.model_aliases["company/embed-small"] == "openai/text-embedding-3-small"
    assert settings.pricing.chat_models["company/private-chat"].output_per_million == 5.0


def test_stats_pricing_refresh_htmx_returns_fragment(monkeypatch, tmp_path) -> None:
    templates = Jinja2Templates(directory="/home/fischerman/ARIA/aria/templates")
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback
    templates.env.globals["agent_name"] = lambda _request, title="": title or "ARIA"

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request, call_next):  # type: ignore[no-untyped-def]
        request.state.can_access_advanced_config = True
        request.state.lang = "de"
        request.state.release_meta = {}
        request.state.update_status = {}
        return await call_next(request)

    settings = Settings.model_validate(
        {
            "llm": {"model": "fake"},
            "pricing": {
                "enabled": True,
                "currency": "USD",
                "chat_models": {},
                "embedding_models": {},
                "default_source_name": "Test source",
            },
        }
    )

    class FakeTokenTracker:
        async def get_stats(self, days: int = 7) -> dict[str, object]:
            assert days == 7
            return {
                "chat_tokens_by_model": {},
                "embedding_tokens_by_model": {},
                "chat_cost_usd_by_model": {},
                "embedding_cost_usd_by_model": {},
                "cost_usd_by_source": {"rss_metadata": 0.123456},
            }

    pipeline = SimpleNamespace(token_tracker=FakeTokenTracker())

    async def fake_refresh(_settings: object, _base_dir: Path) -> dict[str, object]:
        return {
            "last_updated": "2026-05-07",
            "chat_models": {"anthropic/claude-sonnet-4-5": {}},
            "embedding_models": {
                "openai/text-embedding-3-small": {},
                "openai/text-embedding-3-large": {},
            },
            "errors": [],
        }

    monkeypatch.setattr(stats_routes, "_refresh_pricing_snapshot", fake_refresh)

    register_stats_routes(
        app,
        templates=templates,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=lambda _request: "neo",
        resolve_pricing_entry=lambda entries, model: entries.get(model),
        get_runtime_preflight=lambda: {},
    )

    client = TestClient(app)
    response = client.post("/stats/pricing/refresh", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert 'id="stats-pricing-panel"' in response.text
    assert "Pricing refresh completed" in response.text
    assert "1 chat models" in response.text
    assert "2 embedding models" in response.text
    assert "rss_metadata" in response.text


def test_stats_pricing_admin_htmx_saves_alias_and_manual_price(monkeypatch, tmp_path) -> None:
    templates = Jinja2Templates(directory="/home/fischerman/ARIA/aria/templates")
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback
    templates.env.globals["agent_name"] = lambda _request, title="": title or "ARIA"

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text("llm:\n  model: fake\n", encoding="utf-8")
    monkeypatch.setattr(stats_routes, "_project_root", lambda: tmp_path)

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request, call_next):  # type: ignore[no-untyped-def]
        request.state.can_access_advanced_config = True
        request.state.lang = "en"
        request.state.release_meta = {}
        request.state.update_status = {}
        return await call_next(request)

    settings = Settings.model_validate({"llm": {"model": "fake"}})

    class FakeTokenTracker:
        async def get_stats(self, days: int = 7) -> dict[str, object]:
            return {
                "chat_tokens_by_model": {"company/private-chat": 1000},
                "embedding_tokens_by_model": {"company/embed-small": 100},
                "chat_cost_usd_by_model": {},
                "embedding_cost_usd_by_model": {},
                "cost_usd_by_source": {},
                "total_cost_usd": 0.0,
            }

    pipeline = SimpleNamespace(token_tracker=FakeTokenTracker())
    register_stats_routes(
        app,
        templates=templates,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=lambda _request: "neo",
        resolve_pricing_entry=lambda entries, model: entries.get(model),
        get_runtime_preflight=lambda: {},
    )
    client = TestClient(app)

    alias_response = client.post(
        "/stats/pricing/alias",
        data={"alias": "company/embed-small", "target": "openai/text-embedding-3-small"},
        headers={"HX-Request": "true"},
    )
    price_response = client.post(
        "/stats/pricing/manual",
        data={
            "kind": "chat",
            "model": "company/private-chat",
            "input_per_million": "1.25",
            "output_per_million": "5.0",
            "source_name": "Manual",
        },
        headers={"HX-Request": "true"},
    )

    assert alias_response.status_code == 200
    assert "Pricing alias saved." in alias_response.text
    assert "company/embed-small" in alias_response.text
    assert price_response.status_code == 200
    assert "Manual pricing saved." in price_response.text
    assert "company/private-chat" in price_response.text
    assert settings.pricing.model_aliases["company/embed-small"] == "openai/text-embedding-3-small"
    assert settings.pricing.chat_models["company/private-chat"].input_per_million == 1.25


def test_stats_page_renders_model_gateway_audit(monkeypatch, tmp_path) -> None:
    templates = Jinja2Templates(directory="/home/fischerman/ARIA/aria/templates")
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback
    templates.env.globals["agent_name"] = lambda _request, title="": title or "ARIA"

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request, call_next):  # type: ignore[no-untyped-def]
        request.state.can_access_advanced_config = True
        request.state.lang = "de"
        request.state.release_meta = {"label": "test", "version": "0.1.0"}
        request.state.update_status = {}
        return await call_next(request)

    settings = Settings.model_validate(
        {
            "llm": {"model": "anthropic/claude-sonnet-4-5"},
            "embeddings": {"model": "openai/text-embedding-3-small"},
            "token_tracking": {"enabled": True, "log_file": str(tmp_path / "tokens.jsonl")},
        }
    )
    usage_meter = object()

    class FakeEmbeddingClient:
        def __init__(self) -> None:
            self.usage_meter = usage_meter

        @staticmethod
        def _resolve_model() -> str:
            return "openai/text-embedding-3-small"

    embedding_client = FakeEmbeddingClient()

    class FakeTokenTracker:
        async def get_stats(self, days: int = 7) -> dict[str, object]:
            return {
                "days": days,
                "request_count": 1,
                "total_tokens": 12,
                "chat_total_tokens": 10,
                "embedding_total_tokens": 2,
                "extraction_total_tokens": 0,
                "model_total_tokens": 12,
                "avg_tokens_per_request": 10,
                "requests_by_intent": {},
                "requests_by_router_level": {},
                "requests_by_source": {},
                "model_tokens_by_source": {},
                "chat_tokens_by_model": {"anthropic/claude-sonnet-4-5": 10},
                "embedding_tokens_by_model": {"openai/text-embedding-3-small": 2},
                "total_cost_usd": 0.01,
                "avg_cost_usd_per_request": 0.01,
                "priced_requests_count": 1,
                "chat_cost_usd_by_model": {},
                "embedding_cost_usd_by_model": {},
                "cost_usd_by_source": {},
            }

        async def get_recent_activities(self, **_kwargs) -> dict[str, object]:
            return {"summary": {"count": 0, "success": 0, "errors": 0, "avg_duration_ms": 0}, "rows": []}

    pipeline = SimpleNamespace(
        token_tracker=FakeTokenTracker(),
        usage_meter=usage_meter,
        llm_client=SimpleNamespace(model="anthropic/claude-sonnet-4-5", usage_meter=usage_meter),
        embedding_client=embedding_client,
        memory_skill=SimpleNamespace(embedding_client=embedding_client),
    )

    async def fake_health(*_args, **_kwargs) -> dict[str, object]:
        return {"services": [], "overall_status": "ok", "ok_count": 0, "warn_count": 0, "error_count": 0}

    async def fake_qdrant(*_args, **_kwargs) -> dict[str, object]:
        return {"available": False, "size_human": "-", "path": ""}

    async def fake_routing_index(_settings) -> dict[str, object]:
        return {"status": "warn", "summary": "", "collection": "", "fingerprint": "", "point_count": 0}

    async def fake_experience_memory(_settings) -> dict[str, object]:
        return {
            "status": "ok",
            "enabled": True,
            "collection_count": 1,
            "point_count": 3,
            "collections": [{"name": "aria_recipe_experience_neo", "points": 3}],
            "error": "",
        }

    monkeypatch.setattr(stats_routes, "_build_health_meta", fake_health)
    monkeypatch.setattr(stats_routes, "_build_qdrant_storage_meta", fake_qdrant)
    monkeypatch.setattr(stats_routes, "_build_recipe_experience_memory_meta", fake_experience_memory)
    monkeypatch.setattr(stats_routes, "build_connection_routing_index_status", fake_routing_index)
    monkeypatch.setattr(stats_routes, "build_settings_connection_status_rows", lambda *_args, **_kwargs: [])

    register_stats_routes(
        app,
        templates=templates,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=lambda _request: "neo",
        resolve_pricing_entry=lambda _entries, _model: SimpleNamespace(input_per_million=1.0, output_per_million=1.0),
        get_runtime_preflight=lambda: {},
    )

    response = TestClient(app).get("/stats")

    assert response.status_code == 200
    assert "Model Gateway Audit" in response.text
    assert "Recipe Experience Memory" in response.text
    assert "aria_recipe_experience_neo" in response.text
    assert "anthropic/claude-sonnet-4-5" in response.text
    assert "openai/text-embedding-3-small" in response.text


def test_stats_recipe_experience_review_promotes_context_candidate(monkeypatch, tmp_path) -> None:
    templates = Jinja2Templates(directory="/home/fischerman/ARIA/aria/templates")
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback
    templates.env.globals["agent_name"] = lambda _request, title="": title or "ARIA"

    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    app = FastAPI()

    @app.middleware("http")
    async def inject_state(request, call_next):  # type: ignore[no-untyped-def]
        request.state.can_access_advanced_config = True
        request.state.lang = "en"
        request.state.release_meta = {}
        request.state.update_status = {}
        return await call_next(request)

    class FakeTokenTracker:
        async def get_stats(self, days: int = 7) -> dict[str, object]:
            return {"chat_tokens_by_model": {}, "embedding_tokens_by_model": {}, "cost_usd_by_source": {}}

        async def get_recent_activities(self, **_kwargs: object) -> dict[str, object]:
            return {"rows": []}

    pipeline = SimpleNamespace(token_tracker=FakeTokenTracker())
    settings = Settings.model_validate({"llm": {"model": "fake"}})
    register_stats_routes(
        app,
        templates=templates,
        get_pipeline=lambda: pipeline,
        get_settings=lambda: settings,
        get_username_from_request=lambda _request: "neo",
        resolve_pricing_entry=lambda entries, model: entries.get(model),
        get_runtime_preflight=lambda: {},
    )

    response = TestClient(app).post(
        "/stats/recipe-experience/review",
        data={
            "recipe_id": "learned-dns-health",
            "title": "DNS health",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "action": "uptime -p && df -h",
            "summary": "Looks healthy.",
            "user_message": "check dns",
            "experience_count": "3",
            "origin": "guardrail_healthcheck_fallback",
            "updated_at": "2026-05-08T00:00:00Z",
        },
        follow_redirects=False,
    )

    rows = learned_store.load_learned_recipe_store_entries()
    assert response.status_code == 303
    assert response.headers["location"].startswith("/recipes/learned?saved=1")
    assert rows[0]["recipe_id"] == "learned-dns-health"
    assert rows[0]["promotion_state"] == "review_ready"
    assert rows[0]["policy_result"] == "context_only"
    assert rows[0]["recipe_scope"]["learning_origin"] == "guardrail_healthcheck_fallback"
