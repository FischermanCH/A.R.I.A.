from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient

from aria.core.config import Settings
from aria.core import connection_runtime
import aria.web.stats_routes as stats_routes
from aria.web.stats_routes import (
    _attach_connection_edit_urls,
    _build_preflight_meta,
    _build_qdrant_storage_meta,
    _build_release_meta,
    _collapse_large_connection_groups,
    _collapse_connection_kind_rows,
    _refresh_pricing_snapshot,
    _collapse_rss_rows,
    _directory_size_bytes,
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
    assert meta["checks"][0]["summary"] == "Prompt-Dateien ok (2 Skill-Prompts)."
    assert meta["checks"][2]["visual_status"] == "warn"
    assert len(meta["issue_checks"]) == 2


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

    assert meta["checks"][0]["summary"] == "Prompt files ok (2 skill prompts)."
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
  chat_models: {}
  embedding_models: {}
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

    async def fake_snapshot(*, include_openrouter: bool = True) -> dict[str, object]:
        assert include_openrouter is True
        return {
            "enabled": True,
            "currency": "USD",
            "last_updated": "2026-04-02",
            "default_source_name": "OpenAI/Anthropic via LiteLLM, OpenRouter Models API",
            "default_source_url": "https://openrouter.ai/docs/api-reference/list-available-models",
            "chat_models": {
                "openai/gpt-4o-mini": {
                    "input_per_million": 0.15,
                    "output_per_million": 0.6,
                    "source_name": "LiteLLM model_cost",
                    "source_url": "https://platform.openai.com/docs/pricing",
                    "verified_at": "2026-04-02",
                    "notes": "provider=openai",
                }
            },
            "embedding_models": {
                "openai/text-embedding-3-small": {
                    "input_per_million": 0.02,
                    "source_name": "LiteLLM model_cost",
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
    assert snapshot["last_updated"] == "2026-04-02"
    assert settings.pricing.enabled is True
    assert settings.pricing.chat_models["openai/gpt-4o-mini"].input_per_million == 0.15
    assert settings.pricing.embedding_models["openai/text-embedding-3-small"].input_per_million == 0.02


def test_stats_pricing_refresh_htmx_returns_fragment(monkeypatch, tmp_path) -> None:
    templates = Jinja2Templates(directory="/home/fischerman/ARIA/aria/templates")
    templates.env.globals["tr"] = lambda _request, _key, fallback="": fallback

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
        return {}

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
    assert "rss_metadata" in response.text
