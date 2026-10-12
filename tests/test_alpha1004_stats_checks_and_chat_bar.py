from __future__ import annotations

import asyncio
from pathlib import Path
import threading
from types import SimpleNamespace

from aria.modules.configuration_foundations.config import Settings
from aria.modules.release_update.release_meta import read_release_meta
from aria.modules.runtime_bootstrap.manager import RuntimeManager
from aria.modules.stats_ui.routes import _build_pricing_meta, _build_stats_check_blocks


ROOT = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path) -> Settings:
    return Settings.model_validate(
        {
            "llm": {"model": "provider/chat-live"},
            "embeddings": {"model": "provider/embed-live"},
            "token_tracking": {
                "enabled": True,
                "log_file": str(tmp_path / "tokens.jsonl"),
            },
            "security": {"enabled": False},
            "pricing": {
                "enabled": True,
                "chat_models": {
                    **{
                        f"catalog/chat-{index}": {
                            "input_per_million": 1.0,
                            "output_per_million": 2.0,
                        }
                        for index in range(30)
                    },
                    "provider/chat-live": {
                        "input_per_million": 1.0,
                        "output_per_million": 2.0,
                    },
                    "provider/chat-used": {
                        "input_per_million": 1.5,
                        "output_per_million": 2.5,
                    },
                },
                "embedding_models": {
                    **{
                        f"catalog/embed-{index}": {"input_per_million": 0.1}
                        for index in range(30)
                    },
                    "provider/embed-live": {"input_per_million": 0.2},
                },
            },
        }
    )


def test_stats_check_blocks_are_three_passive_groups_and_remain_closed(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    preflight = {
        "status": "warn",
        "checked_at": "2026-10-12T01:12:00Z",
        "checks": [
            {"id": "prompts", "status": "ok", "summary": "ok", "detail": "persona.md"},
            {"id": "qdrant", "status": "ok", "summary": "ok", "detail": "qdrant"},
            {
                "id": "llm",
                "status": "ok",
                "summary": "ok",
                "detail": "provider/chat-startup",
            },
            {
                "id": "embeddings",
                "status": "ok",
                "summary": "ok",
                "detail": "provider/embed-live",
            },
        ],
    }
    pricing = {
        "has_unpriced_usage": False,
        "priced_seen_chat_count": 1,
        "chat_seen_count": 1,
        "priced_seen_embedding_count": 1,
        "embedding_seen_count": 1,
        "logged_total_cost_usd": 0.05,
        "estimated_total_cost_usd": 0.05,
        "has_estimated_cost_gap": False,
    }
    pipeline = SimpleNamespace(
        usage_meter=object(),
        llm_client=SimpleNamespace(usage_meter=None),
        embedding_client=SimpleNamespace(usage_meter=None),
        memory_skill=None,
        _native_mcp_client=SimpleNamespace(statuses=lambda: ()),
    )

    blocks = _build_stats_check_blocks(
        settings=settings,
        pipeline=pipeline,
        preflight_payload=preflight,
        pricing_meta=pricing,
        technical_stats={"model_total_tokens": 10},
        release_meta={"label": "0.1.0-alpha1007", "version": "0.1.0-alpha1007"},
        update_status={"current_label": "0.1.0-alpha1007", "latest_label": "0.1.0-alpha983"},
        registry_meta={"module_count": 106, "validation_issue_count": 0, "dependency_cycle_count": 0},
        base_dir=tmp_path,
        language="de",
    )

    assert [block["key"] for block in blocks] == ["startup", "runtime", "operations"]
    assert all("ok" in block["summary"] and "Warnung" in block["summary"] for block in blocks)
    assert all(block["open"] is False for block in blocks)
    assert any(row["name"] == "Chat-LLM" and row["stale"] for row in blocks[0]["rows"])
    assert blocks[1]["open"] is False
    assert {row["key"] for block in blocks for row in block["rows"]} >= {
            "prompts", "qdrant_startup", "chat_llm", "embeddings",
            "aria_runtime", "model_stack", "qdrant_live", "security_store",
        "logs", "connections", "mcp_servers", "release", "module_registry",
        "model_gateway", "pricing", "cost_tracking", "recipe_memory", "updates",
    }


def test_pricing_meta_only_renders_active_or_used_models_and_caps_rows(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    stats = {
        "chat_tokens_by_model": {"provider/chat-used": 10},
        "chat_prompt_tokens_by_model": {"provider/chat-used": 8},
        "chat_completion_tokens_by_model": {"provider/chat-used": 2},
        "embedding_tokens_by_model": {},
        "embedding_prompt_tokens_by_model": {},
        "chat_cost_usd_by_model": {},
        "embedding_cost_usd_by_model": {},
        "total_cost_usd": 0.0,
    }

    meta = _build_pricing_meta(stats, settings, lambda table, model: table.get(model))

    assert len(meta["source_rows"]) <= 20
    assert {row["model"] for row in meta["source_rows"]} == {
        "provider/chat-live",
        "provider/chat-used",
        "provider/embed-live",
    }
    assert not any(row["model"].startswith("catalog/") for row in meta["source_rows"])


def test_stats_template_renders_three_closed_lazy_check_blocks() -> None:
    source = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")

    assert 'data-stats-check-block="{{ block.key }}"' in source
    assert "{% if block.open %}open{% endif %}" not in source
    assert "data-stats-check-summary" in source
    assert "data-stats-block-content" in source


def test_chat_idle_status_container_has_no_content_or_reserved_height() -> None:
    template = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    css = (ROOT / "aria/static/style.css").read_text(encoding="utf-8")

    assert '<div id="typing-indicator" class="typing-indicator" aria-live="polite" hidden></div>' in template
    assert "indicator.replaceChildren()" in template
    assert ".typing-indicator:empty" in css
    assert ".slash-menu[hidden]" in css


def test_passive_startup_snapshot_never_refreshes_dependencies() -> None:
    manager = object.__new__(RuntimeManager)
    manager._lock = threading.RLock()
    manager._startup_diagnostics = {
        "status": "warn",
        "checked_at": "2026-10-12T01:12:00Z",
        "checks": [{"id": "llm", "status": "warn"}],
    }
    refresh_calls = 0

    async def forbidden_refresh() -> dict[str, object]:
        nonlocal refresh_calls
        refresh_calls += 1
        raise AssertionError("passive stats snapshot must not refresh providers")

    result = asyncio.run(
        manager.get_or_refresh_startup_diagnostics(forbidden_refresh, passive=True)
    )

    assert result["checked_at"] == "2026-10-12T01:12:00Z"
    assert refresh_calls == 0


def test_alpha1006_release_metadata_and_public_pin() -> None:
    meta = read_release_meta(ROOT)
    assert meta["label"] == "0.1.0-alpha1007"
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").startswith(
        "# Changelog\n\n## 0.1.0-alpha1007"
    )
    assert (ROOT / "CHANGELOG.de.md").read_text(encoding="utf-8").startswith(
        "# Changelog\n\n## 0.1.0-alpha1007"
    )
    assert (ROOT / "docs/release/publish-runbook-alpha1006.md").exists()
    assert (ROOT / "docs/release/github-release-v0.1.0-alpha.1007.md").exists()
    assert (ROOT / "docs/release/public-release-summary-alpha1006.md").exists()
    public_stack = (ROOT / "docker-compose.public.yml").read_text(encoding="utf-8")
    assert "0.1.0-alpha.1007" not in public_stack
    docker_overview = (ROOT / "docs/release/docker-hub-overview.md").read_text(encoding="utf-8")
    assert "current public image remains Alpha983" in docker_overview
