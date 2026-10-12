from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from aria.modules.activity_journal.service import build_job_entry, plain_text_summary
from aria.modules.configuration_foundations.config import MCPServerConfig
from aria.modules.mcp.runtime import MCPClientManager, MCPDiscoveredTool
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.recipe_runtime.runtime import (
    _iter_runtime_recipe_manifest_paths,
    load_stored_recipe_runtime,
)
from aria.modules.release_update.release_meta import read_release_meta
from aria.modules.release_update.update_check import (
    _tag_from_release_label,
    extract_changelog_section,
    is_newer_release,
    normalize_release_label,
    release_sort_key,
)
from aria.modules.stats_ui.overview import StatsUsageAggregation


ROOT = Path(__file__).resolve().parents[1]


def test_four_digit_alpha_orders_above_999_across_release_surfaces(tmp_path: Path) -> None:
    assert normalize_release_label("v0.1.0-alpha.1000") == "0.1.0-alpha1000"
    assert release_sort_key("0.1.0-alpha1000") > release_sort_key("0.1.0-alpha999")
    assert is_newer_release("v0.1.0-alpha.1000", "0.1.0-alpha999") is True
    section = extract_changelog_section(
        "# Changelog\n\n## 0.1.0-alpha1000\n\n- newest\n\n## 0.1.0-alpha999\n\n- older\n",
        "v0.1.0-alpha.1000",
    )
    assert "newest" in section and "older" not in section
    meta = read_release_meta(ROOT)
    assert meta["version"] == "0.1.0"
    assert meta["label"] == "0.1.0-alpha1007"
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert _tag_from_release_label(meta["label"]) == "v0.1.0-alpha.1007"

    for version in (999, 1000, 1001, 1002):
        (tmp_path / f"aria-alpha{version}-local.tar").touch()
    command = r"""find "$1" -maxdepth 1 -type f -name 'aria-alpha*-local.tar' | sed 's#^.*/##' | awk '$0 ~ /^aria-alpha[0-9]+-local\.tar$/ { version=$0; sub(/^aria-alpha/,"",version); sub(/-local\.tar$/,"",version); printf "%012d %s\n", version + 0, $0 }' | sort | tail -n1 | cut -d' ' -f2-"""
    newest = subprocess.run(
        ["bash", "-c", command, "bash", str(tmp_path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert newest == "aria-alpha1002-local.tar"


def test_recipe_warm_cache_does_not_parse_manifests_again(monkeypatch, tmp_path: Path) -> None:
    recipes = tmp_path / "data" / "recipes"
    recipes.mkdir(parents=True)
    config = tmp_path / "config.yaml"
    config.write_text("skills: {}\n", encoding="utf-8")
    for index in range(80):
        (recipes / f"r-{index}.json").write_text(json.dumps({
            "id": f"r-{index}", "name": f"Recipe {index}",
            "steps": [{"type": "ssh_run", "params": {"command": "true"}}],
        }), encoding="utf-8")
    rows, cache = load_stored_recipe_runtime(skills_dir=recipes, config_path=config, cache={})
    assert len(rows) == 80
    reads = 0
    original = Path.read_text

    def counted(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        nonlocal reads
        if path.suffix == ".json":
            reads += 1
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    started = time.perf_counter()
    warm_rows, _ = load_stored_recipe_runtime(skills_dir=recipes, config_path=config, cache=cache)
    assert len(warm_rows) == 80
    assert reads == 0
    assert time.perf_counter() - started < 0.15
    assert len(_iter_runtime_recipe_manifest_paths(recipes)) == 80


def test_job_journal_projection_is_single_plain_and_keeps_connection_context(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="job-1", user_id="alice", goal="**Inspect** host", status="detached")
    store.append_step(job_id="job-1", step_index=1, tool_names=("ssh_read",), outcome_summary="ok")
    store.set_journal_context(
        "job-1", connection_kinds=("ssh",), connection_refs=("workstation",),
    )
    store.set_terminal(
        "job-1", status="done",
        result="| Disk | Free |\n|---|---|\n| root | **4.3G** |\n- complete",
    )
    record = store.get("job-1")
    assert record is not None
    entry = build_job_entry(record)
    assert entry["connection_refs"] == ["workstation"]
    assert entry["connection_kinds"] == ["ssh"]
    assert entry["job_id"] == "job-1"
    assert "**" not in entry["goal"] + entry["outcome_phrase"]
    assert "|" not in entry["outcome_phrase"]
    assert "Disk: root" in entry["outcome_phrase"]
    assert "Free: 4.3G" in entry["outcome_phrase"]


def test_plain_text_summary_flattens_lists_links_and_tables() -> None:
    value, _ = plain_text_summary(
        "## Result\n- **Ready**\n| Name | State |\n|---|---|\n| Node | `ok` |\n[Open](/jobs/1)",
        limit=300,
    )
    assert value == "Result · Ready · Name: Node; State: ok · Open"


def test_stats_deduplicates_provider_aliases_and_localizes_driver_names(tmp_path: Path) -> None:
    log = tmp_path / "tokens.jsonl"
    now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
    rows = [
        {"timestamp": now.isoformat(), "request_id": "a", "chat_model": "claude-sonnet-5", "chat_cost_usd": 1.0, "total_cost_usd": 1.0, "source": "web_chat"},
        {"timestamp": now.isoformat(), "request_id": "b", "chat_model": "anthropic/claude-sonnet-5", "chat_cost_usd": 2.0, "total_cost_usd": 2.0, "source": "native_agent"},
        {"timestamp": now.isoformat(), "request_id": "c", "embedding_model": "openai/embed-small", "embedding_cost_usd": 0.5, "total_cost_usd": 0.5, "source": "meta_catalog"},
        {"timestamp": now.isoformat(), "request_id": "d", "embedding_model": "embed-small", "embedding_cost_usd": 0.5, "total_cost_usd": 0.5, "source": "meta_catalog"},
    ]
    log.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = StatsUsageAggregation(log).build(language="de", now=now.timestamp())
    assert [row["name"] for row in result["models"]] == [
        "claude-sonnet-5 · Chat", "embed-small · Embedding",
    ]
    assert {row["name"] for row in result["drivers"]} == {
        "Chat", "Agent-Aufträge", "Katalog-Suche",
    }
    assert {row["key"] for row in result["drivers"]} == {
        "web_chat", "native_agent", "meta_catalog",
    }


def test_templates_use_safe_job_markdown_empty_journal_dates_and_nonstale_statuses() -> None:
    jobs = (ROOT / "aria/templates/agent_jobs.html").read_text(encoding="utf-8")
    journal = (ROOT / "aria/templates/activity_journal.html").read_text(encoding="utf-8")
    stats = (ROOT / "aria/templates/stats.html").read_text(encoding="utf-8")
    base = (ROOT / "aria/templates/base.html").read_text(encoding="utf-8")
    chat = (ROOT / "aria/templates/chat.html").read_text(encoding="utf-8")
    assert 'data-safe-markdown-rendered="server"' in jobs
    assert 'resultTarget.dataset.safeMarkdownRendered = "poll"' in jobs
    assert 'name="since" autocomplete="off"{% if filters.since %} value="{{ filters.since|e }}"{% endif %}' in journal
    assert 'name="until" autocomplete="off"{% if filters.until %} value="{{ filters.until|e }}"{% endif %}' in journal
    assert 'viewBox="0 0 640 180"' in stats and "overview.usage.y_ticks" in stats
    assert "aria_restart_probe_failure_count" not in base
    assert "consecutiveHealthFailures" in base
    assert 'if (event.persisted && exportStatus) exportStatus.textContent = "";' in chat


def test_mcp_failed_discovery_retries_in_background_without_a_turn(monkeypatch) -> None:
    async def scenario() -> None:
        calls = 0
        manager = MCPClientManager({
            "bridge": MCPServerConfig.model_validate({
                "transport": "sse", "url": "https://mcp.invalid/sse", "enabled": True,
            }),
        })

        async def fail_once(_server_name, _config):  # noqa: ANN001, ANN202
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("offline")
            return (MCPDiscoveredTool(
                server_name="bridge", remote_name="look", description="Look",
                input_schema={"type": "object"}, annotations={}, read_only=True,
            ),)

        manager._discover_server = fail_once  # type: ignore[method-assign]
        monkeypatch.setattr(manager, "failure_backoff_seconds", lambda _name: 0.02)
        first = await manager.discover_all(refresh=True)
        assert first == {"bridge": ()}
        for _ in range(20):
            if manager.statuses()[0].connected:
                break
            await asyncio.sleep(0.01)
        assert calls == 2
        assert manager.statuses()[0].connected is True
        assert [tool.contract.name for tool in manager.native_tool_bindings()] == ["mcp__bridge__look"]
        await manager.close()

    asyncio.run(scenario())


def test_mcp_discovery_cache_survives_unrelated_runtime_reload() -> None:
    config = MCPServerConfig.model_validate({
        "transport": "sse", "url": "https://mcp.invalid/sse", "enabled": True,
    })
    previous = MCPClientManager({"bridge": config})
    previous._discovery["bridge"] = (MCPDiscoveredTool(
        server_name="bridge", remote_name="look", description="Look",
        input_schema={"type": "object"}, annotations={}, read_only=True,
    ),)
    previous._statuses["bridge"] = SimpleNamespace(
        server_name="bridge", connected=True, tool_count=1, error="",
    )
    reloaded = MCPClientManager({"bridge": config})
    reloaded.inherit_discovery_cache(previous)
    assert [tool.contract.name for tool in reloaded.native_tool_bindings()] == ["mcp__bridge__look"]
    assert reloaded.statuses()[0].connected is True


def test_mcp_transport_call_failure_schedules_background_recovery(monkeypatch) -> None:
    async def scenario() -> None:
        config = MCPServerConfig.model_validate({
            "transport": "sse", "url": "https://mcp.invalid/sse", "enabled": True,
        })
        manager = MCPClientManager({"bridge": config})

        async def fail_call(*_args, **_kwargs):  # noqa: ANN002, ANN003, ANN202
            raise ConnectionError("bridge down")

        async def recovered_discovery(_server_name, _config):  # noqa: ANN001, ANN202
            return (MCPDiscoveredTool(
                server_name="bridge", remote_name="look", description="Look",
                input_schema={"type": "object"}, annotations={}, read_only=True,
            ),)

        manager._run_server_operation = fail_call  # type: ignore[method-assign]
        manager._discover_server = recovered_discovery  # type: ignore[method-assign]
        monkeypatch.setattr(manager, "failure_backoff_seconds", lambda _name: 0.02)
        result = await manager._call_remote("bridge", "look", {}, intent="mcp__bridge__look")
        assert "mcp_call_failed" in result.content
        for _ in range(20):
            if manager.statuses()[0].connected:
                break
            await asyncio.sleep(0.01)
        assert manager.statuses()[0].connected is True
        assert [binding.contract.name for binding in manager.native_tool_bindings()] == [
            "mcp__bridge__look",
        ]
        await manager.close()

    asyncio.run(scenario())
