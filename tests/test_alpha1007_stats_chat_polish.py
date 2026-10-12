from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from aria.modules.stats_ui import routes as stats_routes
from aria.modules.stats_ui.overview import StatsResourceSnapshot, StatsUsageAggregation


ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        aria=SimpleNamespace(log_level="info"),
        llm=SimpleNamespace(model="chat-model", api_base="http://fake.invalid"),
        web_llm=SimpleNamespace(model="web-model", api_base="http://fake.invalid"),
        embeddings=SimpleNamespace(model="embed-model", api_base="http://fake.invalid"),
        token_tracking=SimpleNamespace(enabled=True, log_file=str(tmp_path / "tokens.jsonl")),
        security=SimpleNamespace(enabled=False, db_path=str(tmp_path / "security.sqlite3")),
        connections=SimpleNamespace(model_dump=lambda: {"ssh": {"one": {}}}),
        mcp_servers={},
        pricing=SimpleNamespace(chat_models={}, embedding_models={}),
    )


def _blocks(tmp_path: Path, *, language: str = "de") -> list[dict[str, object]]:
    return stats_routes._build_stats_check_blocks(
        settings=_settings(tmp_path),
        pipeline=SimpleNamespace(_native_mcp_client=None),
        preflight_payload={
            "checked_at": "2026-10-12T21:02:53Z",
            "checks": [
                {"id": "prompts", "status": "ok", "detail": "ok"},
                {"id": "qdrant", "status": "ok", "detail": "ok"},
                {"id": "llm", "status": "ok", "detail": "chat-model"},
                {"id": "embeddings", "status": "ok", "detail": "embed-model"},
            ],
        },
        pricing_meta={"has_unpriced_usage": False},
        technical_stats={},
        release_meta={"label": "0.1.0-alpha1007"},
        update_status={},
        registry_meta={"module_count": 1, "validation_issue_count": 0, "dependency_cycle_count": 0},
        base_dir=tmp_path,
        language=language,
        timezone_name="Europe/Zurich",
    )


def test_stats_has_no_meta_or_duplicate_qdrant_tiles_and_header_uses_local_time(tmp_path: Path) -> None:
    blocks = _blocks(tmp_path)
    keys = [row["key"] for block in blocks for row in block["rows"]]
    assert "startup_time" not in keys
    assert "preflight" not in keys
    assert "runtime_health" not in keys
    assert "sidecars" not in keys
    assert "memory_live" not in keys
    assert keys.count("qdrant_startup") == 1
    assert keys.count("qdrant_live") == 1
    assert blocks[0]["time_label"] == "23:02"


def test_connections_never_checked_are_neutral_and_not_a_top_problem(tmp_path: Path) -> None:
    blocks = _blocks(tmp_path)
    connection = next(row for block in blocks for row in block["rows"] if row["key"] == "connections")
    assert connection["status"] == "ok"
    assert "keine einzelne" not in connection["detail"].casefold()
    health = stats_routes._build_stats_health_summary(blocks, [], language="de")
    assert not any(issue["name"] == connection["name"] for issue in health["issues"])


def test_routing_index_excess_is_a_concrete_warning(monkeypatch) -> None:
    async def routing(_settings):  # type: ignore[no-untyped-def]
        return {"status": "ok", "indexed_count": 142, "document_count": 131}

    async def recipes(_settings):  # type: ignore[no-untyped-def]
        return {"status": "ok", "collection_count": 1, "point_count": 2}

    monkeypatch.setattr(stats_routes, "build_connection_routing_index_status", routing)
    monkeypatch.setattr(stats_routes, "_build_recipe_experience_memory_meta", recipes)
    row = asyncio.run(stats_routes._build_stats_live_operation_rows(SimpleNamespace(), language="de"))["routing_index"]
    assert row["status"] == "warn"
    assert "11 veraltete" in f"{row['summary']} {row['detail']}".lower()
    assert row["url"] == "/config/operations"


def test_cost_chart_has_y_ticks_x_ticks_and_tooltips(tmp_path: Path) -> None:
    now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()
    usage = StatsUsageAggregation(tmp_path / "tokens.jsonl", "Europe/Zurich").build(language="de", now=now)
    assert len(usage["y_ticks"]) == 3
    assert usage["y_ticks"][0]["label"].startswith("US$")
    assert len(usage["x_ticks"]) >= 6
    template = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")
    assert "overview.usage.y_ticks" in template
    assert "overview.usage.x_ticks" in template
    assert 'tabindex="0"' in template


def test_resource_snapshot_reads_container_paths_and_waits_for_growth_history(tmp_path: Path, monkeypatch) -> None:
    qdrant = tmp_path / "qdrant-storage"
    (qdrant / "collections" / "aria_docs_manual").mkdir(parents=True)
    (qdrant / "collections" / "aria_docs_manual" / "data.bin").write_bytes(b"d" * 90)
    (qdrant / "collections" / "aria_other").mkdir()
    (qdrant / "collections" / "aria_other" / "data.bin").write_bytes(b"q" * 30)
    traces = tmp_path / "data" / "modules" / "native_agent"
    traces.mkdir(parents=True)
    (traces / "trace.jsonl").write_bytes(b"t" * 20)
    monkeypatch.setenv("ARIA_QDRANT_STORAGE_PATH", str(qdrant))
    result = StatsResourceSnapshot(tmp_path, ttl_seconds=0).build(language="de", now=1_760_000_000)
    assert result["qdrant"] >= 120
    assert result["qdrant_collections"] == 2
    by_name = {row["name"]: row for row in result["rows"]}
    assert by_name["documents"]["bytes"] >= 90
    assert by_name["traces"]["bytes"] >= 20
    assert result["growth_ready"] is False


def test_chat_replaces_toolbox_with_small_accessible_actions_menu() -> None:
    template = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    assert "chat-toolbox-panel" not in template
    assert "chat_toolbox_groups" not in template
    assert "chat-actions-menu" in template
    assert 'aria-haspopup="menu"' in template
    assert "chat_quick_actions" in template
    assert "data-chat-quick-action" in template


def test_chat_assistant_is_full_width_and_terminal_jobs_render_view_only() -> None:
    css = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")
    template = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    partial = (ROOT / "aria/templates/_chat_messages.html").read_text(encoding="utf-8")
    assert ".msg-assistant" in css and "width: 100%" in css
    assert "terminal_agent_job_ids" in template
    assert "agentJobView" in template
    assert "terminal_agent_job_ids" in partial
    assert 'jobActionButton(jobId, "cancel", uiText.agentJobCancel, "⏹", true)' in template
