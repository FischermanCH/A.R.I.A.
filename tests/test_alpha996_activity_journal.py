from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import time
from pathlib import Path
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.activity_journal.native_tools import native_tool_contributions
from aria.modules.activity_journal.service import (
    build_job_entry,
    build_turn_entry,
    delete_migrated_legacy_rollups,
    legacy_rollup_projection,
    migrate_legacy_rollups,
)
from aria.modules.activity_journal.store import ActivityJournalStore
from aria.modules.activity_journal.routes import register_activity_journal_routes
from aria.modules.activity_journal.runtime import wire_activity_journal
from aria.modules.configuration_foundations.config import AgenticLoopFeatureConfig
from aria.modules.native_agent.tool_registry import assemble_native_tools
from aria.modules.sdk import NativeToolContext
from aria.modules import module_route_path
from aria.modules.runtime_bootstrap.manager import RuntimeBundle, RuntimeManager
from aria.modules.capability_context.store import CapabilityContextStore
from aria.modules.runtime_diagnostics import runtime as runtime_diagnostics
from aria.modules.stats_ui.routes import _build_preflight_meta
from aria.modules.navigation_shell.navigation import context_nav_context
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]


def _live_entry(**overrides):  # noqa: ANN003, ANN202
    row = {
        "id": "turn-alice-1",
        "user_id": "alice",
        "started_at": 1_700_000_000.0,
        "finished_at": 1_700_000_005.0,
        "kind": "turn",
        "job_id": "",
        "goal": "Inspect the scene",
        "tools": {"mcp__blender__get_scene_info": 1},
        "connection_kinds": ["mcp"],
        "connection_refs": [],
        "mcp_servers": ["blender"],
        "outcome_status": "ok",
        "confirmations": {"asked": 0, "approved": 0, "rejected": 0},
        "corrected": False,
        "outcome_phrase": "Scene inspected.",
        "source": "live",
        "keep": False,
    }
    row.update(overrides)
    return row


def test_store_is_user_scoped_bounded_idempotent_and_never_keeps_raw_outputs(tmp_path: Path) -> None:
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    secret = "sk-fixture-12345"
    raw_output = "RAW TOOL OUTPUT " + "x" * 1200
    entry = build_turn_entry(
        user_id="alice",
        turn_id="turn-1",
        started_at=1.0,
        finished_at=2.0,
        goal=f"Use api_key={secret} to inspect a file",
        used_tool_names=("file_read", "file_read"),
        outcome_status="ok",
        outcome_phrase=f"Done token={secret}. {raw_output}",
        connection_kinds=("sftp",),
        connection_refs=("srv-a",),
        confirmations={"asked": 0, "approved": 0, "rejected": 0},
        corrected=False,
    )
    assert entry is not None
    assert store.write(entry) is True
    assert store.write(entry) is False
    assert len(store.query("alice")) == 1
    assert store.query("bob") == []
    persisted = json.dumps(store.query("alice"), ensure_ascii=False)
    assert secret not in persisted
    assert raw_output not in persisted
    assert len(store.query("alice")[0]["goal"]) <= 300
    assert len(store.query("alice")[0]["outcome_phrase"]) <= 300
    assert store.query("alice")[0]["tools"] == {"file_read": 2}


def test_plain_chat_is_not_projected_and_job_projection_is_terminal_exactly_once(tmp_path: Path) -> None:
    assert build_turn_entry(
        user_id="alice", turn_id="plain", started_at=1, finished_at=2,
        goal="hello", used_tool_names=(), outcome_status="ok", outcome_phrase="hello",
    ) is None
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    record = SimpleNamespace(
        job_id="job-1", user_id="alice", goal="Build the scene", created_at=1.0,
        updated_at=4.0, status="done", result="Completed", step_log=(
            {"tool_names": ["mcp__blender__execute_blender_code"]},
            {"tool_names": ["mcp__blender__get_scene_info"]},
        ), corrected=True, confirmation_asked=1, confirmation_approved=1,
        confirmation_rejected=0,
    )
    entry = build_job_entry(record)
    assert store.write(entry) is True
    assert store.write(entry) is False
    saved = store.query("alice")[0]
    assert saved["job_id"] == "job-1"
    assert saved["corrected"] is True
    assert saved["confirmations"] == {"asked": 1, "approved": 1, "rejected": 0}


def test_retention_only_deletes_expired_unkept_live_entries(tmp_path: Path) -> None:
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    now = 2_000_000_000.0
    old = now - 100 * 86400
    store.write(_live_entry(id="old-live", finished_at=old))
    store.write(_live_entry(id="kept-live", finished_at=old, keep=True))
    store.write(_live_entry(
        id="legacy", finished_at=old, source="legacy_context_rollup", keep=True,
    ))
    store.write(_live_entry(id="recent", finished_at=now - 2 * 86400))

    assert store.sweep(retention_days=90, now=now) == 1
    assert {row["id"] for row in store.query("alice", limit=50)} == {
        "kept-live", "legacy", "recent",
    }


def test_read_tool_is_bounded_user_scoped_and_flagged(tmp_path: Path) -> None:
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    for index in range(60):
        store.write(_live_entry(
            id=f"row-{index}", goal=f"Blender task {index}",
            outcome_phrase="done " + "y" * 280,
            finished_at=1_700_000_000 + index,
        ))
    owner = SimpleNamespace(_activity_journal_store=store)
    binding = native_tool_contributions(owner)[0]
    assert binding.contract.name == "activity_journal_read"
    assert binding.contract.effect == "read_only"
    assert binding.contract.confirmation_required is False
    assert binding.contract.rollout_flag == "activity_journal_enabled"
    result = asyncio.run(binding.handler(
        NativeToolContext(user_id="alice", auth_role="user", request_id="r1"),
        {"query": "Blender", "limit": 50},
    ))
    payload = json.loads(result.content)
    assert len(result.content) <= 4000
    assert 1 <= len(payload["entries"]) <= 50
    assert all(row["user_id"] == "alice" for row in payload["entries"])


def test_registry_is_38_when_enabled_and_37_when_disabled(tmp_path: Path) -> None:
    owner = SimpleNamespace(
        settings=SimpleNamespace(), memory_skill=object(),
        _activity_journal_store=ActivityJournalStore(tmp_path / "journal.sqlite3"),
    )
    core_flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_admin_write_enabled", "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled", "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled", "native_agent_recipe_learn_enabled", "native_agent_memory_learn_enabled",
    }
    disabled = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=core_flags)
    enabled = assemble_native_tools(
        MODULE_MANIFESTS, runtime_owner=owner,
        enabled_rollout_flags={*core_flags, "activity_journal_enabled"},
    )
    assert len(disabled) == 37
    assert len(enabled) == 38
    assert "activity_journal_read" in {binding.contract.name for binding in enabled}
    assert AgenticLoopFeatureConfig().activity_journal_enabled is True
    assert AgenticLoopFeatureConfig().activity_journal_retention_days == 90


class _MemorySkill:
    def __init__(self, rows):  # noqa: ANN001
        self.rows = list(rows)
        self.deleted: list[tuple[str, str, str]] = []

    async def list_memories_global(self, user_id: str, **_kwargs):  # noqa: ANN003, ANN202
        return [row for row in self.rows if row.get("user_id", user_id) == user_id]

    async def delete_memory_point(self, user_id: str, collection: str, point_id: str) -> bool:
        self.deleted.append((user_id, collection, point_id))
        return True


def test_legacy_migration_is_previewed_redacted_idempotent_and_never_deletes(tmp_path: Path) -> None:
    rows = [{
        "id": "point-1", "user_id": "alice", "collection": "aria_context-mem_alice_dim_3",
        "source": "compression", "rollup_level": "week", "rollup_bucket": "2026-W40",
        "rollup_period_start": "2026-09-28", "rollup_period_end": "2026-10-04",
        "text": "# Memory Compression Template\nBehalte nur wichtige Fakten.\nEntferne Wiederholungen.\nEintraege:\n- Blender geprüft.\n- api_key=very-secret-value",
    }, {
        "id": "point-other", "user_id": "bob", "collection": "aria_context-mem_bob",
        "source": "compression", "rollup_level": "week", "rollup_bucket": "2026-W40",
        "text": "other user",
    }]
    preview = legacy_rollup_projection("alice", rows[0])
    assert preview["keep"] is True
    assert preview["source"] == "legacy_context_rollup"
    assert "Memory Compression Template" not in preview["outcome_phrase"]
    assert "Behalte nur" not in preview["outcome_phrase"]
    assert "very-secret-value" not in preview["outcome_phrase"]

    skill = _MemorySkill(rows)
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    first = asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))
    second = asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))
    assert first == {"found": 1, "created": 1, "updated": 0, "existing": 0}
    assert second == {"found": 1, "created": 0, "updated": 0, "existing": 1}
    assert skill.deleted == []

    removed = asyncio.run(delete_migrated_legacy_rollups(store, skill, user_id="alice"))
    assert removed == 1
    assert skill.deleted == [("alice", "aria_context-mem_alice_dim_3", "point-1")]


def test_legacy_delete_covers_all_migrated_rows_not_only_first_page(tmp_path: Path) -> None:
    rows = [
        {
            "id": f"point-{index}", "user_id": "alice",
            "collection": "aria_context-mem_alice_dim_3",
            "source": "compression", "rollup_bucket": f"2026-W{index:02d}",
            "text": f"Entry {index}",
        }
        for index in range(75)
    ]
    skill = _MemorySkill(rows)
    store = ActivityJournalStore(tmp_path / "journal.sqlite3")
    assert asyncio.run(migrate_legacy_rollups(store, skill, user_id="alice"))["created"] == 75

    assert asyncio.run(
        delete_migrated_legacy_rollups(store, skill, user_id="alice")
    ) == 75
    assert len(skill.deleted) == 75


def test_version_and_prompt_boundary() -> None:
    assert 'version = "0.1.0-alpha1007"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "activity_journal" in MODULE_MANIFESTS
    handler = (ROOT / "aria/modules/native_agent/handler.py").read_text(encoding="utf-8")
    assert "activity_journal_read" not in handler
    assert "activity_journal" not in handler.split("TURN-SPECIFIC SYSTEM CONTEXT", 1)[0]


def test_writer_failure_is_fire_and_forget_and_never_breaks_turn(tmp_path: Path, monkeypatch) -> None:
    owner = SimpleNamespace(
        _project_root=tmp_path,
        settings=SimpleNamespace(agentic_loop=AgenticLoopFeatureConfig()),
    )
    wire_activity_journal(owner)
    store = owner._activity_journal_store
    monkeypatch.setattr(store, "write", lambda _entry: (_ for _ in ()).throw(OSError("disk unavailable")))

    async def exercise() -> None:
        entry_id = owner._activity_journal_turn_finalizer(
            user_id="alice", turn_id="turn-failure", started_at=1, finished_at=2,
            goal="Run a safe tool", used_tool_names=("file_list",), outcome_status="ok",
            outcome_phrase="Done.", confirmations={}, corrected=False,
        )
        assert entry_id.startswith("turn-")
        await asyncio.gather(*tuple(owner._activity_journal_tasks))

    asyncio.run(exercise())
    assert store.query("alice") == []


class _Manager(RuntimeManager):
    def _build_runtime_bundle(self, runtime_settings):  # type: ignore[override]
        marker = object()
        return RuntimeBundle(runtime_settings, marker, marker, marker, marker)


def test_stale_failed_preflight_refreshes_on_view(tmp_path: Path) -> None:
    manager = _Manager(
        base_dir=tmp_path, config_path=tmp_path / "config.yaml",
        initial_settings=SimpleNamespace(),
        capability_context_store=CapabilityContextStore(tmp_path / "capability.json"),
    )
    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
    manager.set_startup_diagnostics({
        "status": "error", "checked_at": stale_time,
        "checks": [{"id": "qdrant", "status": "error"}],
    })
    calls = 0

    async def refreshed():  # noqa: ANN202
        nonlocal calls
        calls += 1
        return {"status": "ok", "checked_at": datetime.now(timezone.utc).isoformat(), "checks": [{"id": "qdrant", "status": "ok"}]}

    result = asyncio.run(manager.get_or_refresh_startup_diagnostics(refreshed))
    assert calls == 1
    assert result["status"] == "ok"


def test_startup_preflight_retries_transient_dependency_failure(tmp_path: Path, monkeypatch) -> None:
    attempts = 0

    async def fake_build(*_args, **_kwargs):  # noqa: ANN202
        nonlocal attempts
        attempts += 1
        status = "error" if attempts < 3 else "ok"
        return {
            "status": status,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": [
                {"id": "prompts", "status": "ok"},
                {"id": "qdrant", "status": status, "detail": "connection refused"},
                {"id": "llm", "status": "ok"},
                {"id": "embeddings", "status": "ok"},
            ],
        }

    async def no_wait(_delay):  # noqa: ANN001, ANN202
        return None

    monkeypatch.setattr(runtime_diagnostics, "build_runtime_diagnostics", fake_build)
    result = asyncio.run(runtime_diagnostics.build_runtime_diagnostics_with_retry(
        tmp_path, SimpleNamespace(), retry_window_seconds=60, sleeper=no_wait,
    ))
    assert attempts == 3
    assert result["status"] == "ok"
    meta = _build_preflight_meta(
        {"status": "error", "checked_at": datetime.now(timezone.utc).isoformat(), "checks": [{"id": "qdrant", "status": "error", "summary": "down", "detail": "refused"}]},
        "de",
        health_meta={"services": [{"name": "Memory / Qdrant", "status": "ok"}]},
    )
    assert meta["checks"][0]["stale"] is True


def test_journal_page_is_user_scoped_and_typed_delete_is_required(tmp_path: Path) -> None:
    store = ActivityJournalStore(tmp_path / "data/runtime/activity_journal.sqlite3")
    store.write(_live_entry(id="alice-entry", user_id="alice"))
    store.write(_live_entry(id="bob-entry", user_id="bob", goal="Bob secret activity"))
    pipeline = SimpleNamespace(_project_root=tmp_path, _activity_journal_store=store, memory_skill=_MemorySkill([]))
    settings = SimpleNamespace(
        ui=SimpleNamespace(title="ARIA"),
        agentic_loop=SimpleNamespace(activity_journal_enabled=True, activity_journal_retention_days=90),
    )
    templates = Jinja2Templates(directory=str(ROOT / "aria/templates"))
    templates.env.globals.update({
        "tr": lambda _request, _key, fallback="": fallback,
        "agent_name": lambda _request, title="": title or "ARIA",
        "module_route_path": lambda module_id, path: module_route_path(module_id, path) or path,
        "canonical_parent_section": lambda _request: "memory",
        "canonical_parent_href": lambda _request: "/memories",
        "nav_section_items": lambda *_args, **_kwargs: [],
        "context_nav_items": lambda *_args, **_kwargs: [],
        "context_nav_context": context_nav_context,
    })
    app = FastAPI()

    @app.middleware("http")
    async def state(request, call_next):  # type: ignore[no-untyped-def]
        request.state.lang = "de"
        request.state.csrf_token = "csrf"
        request.state.authenticated = True
        request.state.auth_user = "alice"
        request.state.auth_role = "admin"
        request.state.can_access_advanced_config = True
        request.state.release_meta = {"label": "test"}
        request.state.update_status = {}
        request.state.ui_background_asset_url = ""
        return await call_next(request)

    writes: list[dict[str, object]] = []
    register_activity_journal_routes(
        app, templates=templates, get_pipeline=lambda: pipeline, get_settings=lambda: settings,
        get_username_from_request=lambda _request: "alice", read_raw_config=lambda: {},
        write_raw_config=lambda payload: writes.append(payload), reload_runtime=lambda: None,
    )
    client = TestClient(app)
    page = client.get("/memories/activity-journal")
    assert page.status_code == 200
    assert "alice-entry" in page.text
    assert "Bob secret activity" not in page.text
    refused = client.post("/memories/activity-journal/delete-range", data={
        "csrf_token": "csrf", "since": "2020-01-01", "until": "2035-01-01", "confirmation": "wrong",
    }, follow_redirects=False)
    assert refused.status_code == 303
    assert store.get("alice", "alice-entry") is not None
    saved = client.post("/memories/activity-journal/settings", data={
        "csrf_token": "csrf", "retention_days": "30",
    }, follow_redirects=False)
    assert saved.status_code == 303
    assert writes[-1]["agentic_loop"] == {
        "activity_journal_enabled": False,
        "activity_journal_retention_days": 30,
    }
    accepted = client.post("/memories/activity-journal/delete-range", data={
        "csrf_token": "csrf", "since": "2020-01-01", "until": "2035-01-01",
        "confirmation": "AKTIVITÄTSJOURNAL LÖSCHEN",
    }, follow_redirects=False)
    assert accepted.status_code == 303
    assert store.get("alice", "alice-entry") is None
    assert store.get("bob", "bob-entry") is not None
