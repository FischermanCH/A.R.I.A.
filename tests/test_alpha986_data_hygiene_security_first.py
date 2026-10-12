from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import time
from types import SimpleNamespace

import pytest
import anyio

from aria.modules.action_confirmation.ledger import ActionConfirmationLedger
from aria.modules.config_backup.backup import (
    BACKUP_SCHEMA_VERSION,
    build_config_backup_payload,
    parse_config_backup_payload,
    restore_config_backup_payload,
)
from aria.modules.configuration_foundations.config import NativeTraceConfig
from aria.modules.inbound_event_storage.store import InboundEventStore, normalize_inbound_event
from aria.modules.model_usage_observability.token_tracker import TokenTracker
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.trace_store import NativeTraceStore
from aria.modules.native_web_llm.evidence import PublicWebEvidenceStore
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.security_storage.secure_store import (
    SecureConfigStore,
    SecureStoreConfig,
    decode_master_key,
    generate_master_key_b64,
)


def _secure_store(path: Path) -> SecureConfigStore:
    return SecureConfigStore(
        config=SecureStoreConfig(db_path=path, enabled=True),
        master_key=decode_master_key(generate_master_key_b64()),
    )


def test_backup_is_secret_free_by_default_and_manifest_is_explicit(tmp_path: Path) -> None:
    store = _secure_store(tmp_path / "auth.sqlite3")
    store.set_secret("llm.api_key", "secret-canary")
    store.upsert_user("admin", "password-hash-canary", role="admin")
    payload = build_config_backup_payload(
        base_dir=tmp_path,
        raw_config={"llm": {"api_key": "raw-secret", "model": "fake"}},
        secure_store=store,
    )

    serialized = json.dumps(payload, sort_keys=True)
    assert payload["schema_version"] == BACKUP_SCHEMA_VERSION
    assert "secret-canary" not in serialized
    assert "password-hash-canary" not in serialized
    assert "raw-secret" not in serialized
    assert payload["manifest"]["secrets"] == "excluded"
    assert {
        "memories", "documents", "notes", "chats", "jobs", "qdrant_data",
    }.issubset(set(payload["manifest"]["not_included"]))
    assert payload["manifest"]["persistent_volumes_are_a_backup"] is False


def test_encrypted_backup_roundtrip_and_wrong_passphrase_is_prewrite(tmp_path: Path) -> None:
    store = _secure_store(tmp_path / "source.sqlite3")
    store.set_secret("llm.api_key", "secret-canary")
    store.upsert_user("admin", "password-hash-canary", role="admin")
    payload = build_config_backup_payload(
        base_dir=tmp_path,
        raw_config={"llm": {"api_key": "raw-secret", "model": "fake"}},
        secure_store=store,
        include_secrets=True,
        passphrase="correct horse battery staple",
    )
    assert "secret-canary" not in json.dumps(payload)
    restored = parse_config_backup_payload(json.dumps(payload), passphrase="correct horse battery staple")
    assert restored["secure_store"]["secrets"]["llm.api_key"] == "secret-canary"

    writes: list[dict] = []
    with pytest.raises(ValueError, match="passphrase|decrypt|encrypted"):
        restore_config_backup_payload(
            base_dir=tmp_path / "restore",
            payload=payload,
            passphrase="wrong passphrase",
            write_raw_config=lambda raw: writes.append(raw),
            get_secure_store=lambda _raw: None,
        )
    assert writes == []


def test_secret_free_restore_marks_reentry_and_legacy_plaintext_warns(tmp_path: Path) -> None:
    payload = build_config_backup_payload(base_dir=tmp_path, raw_config={"llm": {"model": "fake"}})
    writes: list[dict] = []
    summary = restore_config_backup_payload(
        base_dir=tmp_path / "restore",
        payload=payload,
        write_raw_config=lambda raw: writes.append(raw),
        get_secure_store=lambda _raw: None,
    )
    assert writes
    assert summary["needs_secret_reentry"] == 1

    legacy = dict(payload)
    legacy["schema_version"] = "aria-config-backup-v1"
    legacy["secure_store"] = {"enabled": False, "secrets": {}, "users": []}
    parsed = parse_config_backup_payload(json.dumps(legacy))
    assert parsed["restore_warnings"] == ["legacy_plaintext_backup"]


def test_native_trace_defaults_minimize_sensitive_content_and_sweep(tmp_path: Path) -> None:
    assert NativeTraceConfig().retention_days == 7
    assert NativeTraceConfig().detail_level == "minimal"
    assert NativeTraceConfig().max_mebibytes == 50
    store = NativeTraceStore(tmp_path, detail_level="minimal", retention_days=7, max_mebibytes=1)
    trace = store.write(
        turn_id="turn-1",
        row={
            "event": "tool_result",
            "step_index": 2,
            "tool_name": "document_search",
            "effect": "read_only",
            "arguments": {"query": "medical sentence secret-canary"},
            "result": {"content": "medical sentence secret-canary"},
            "status": "ok",
        },
    )
    raw = trace.read_text(encoding="utf-8")
    assert "secret-canary" not in raw
    row = json.loads(raw)
    assert row["argument_bytes"] > 0 and len(row["argument_sha256"]) == 64
    assert row["output_bytes"] > 0 and len(row["output_sha256"]) == 64

    full = NativeTraceStore(tmp_path / "full", detail_level="full")
    assert "secret-canary" in full.write(
        turn_id="turn-2", row={"result": "secret-canary", "status": "ok"}
    ).read_text(encoding="utf-8")

    old = tmp_path / "old.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    os.utime(old, (time.time() - 8 * 86400, time.time() - 8 * 86400))
    stats = store.sweep(now=time.time())
    assert stats["removed_retention"] == 1
    assert not old.exists()


def test_pending_ledger_inbound_and_token_archives_are_physically_pruned(tmp_path: Path) -> None:
    pending = NativePendingStore(tmp_path / "pending.sqlite3", ttl_seconds=60)
    pending.put(user_id="u", token="a", tool_name="t", frozen_arguments={}, preview="x", now=1)
    assert pending.prune_expired(now=62) == 1

    ledger = ActionConfirmationLedger(tmp_path / "ledger.sqlite3", retention_seconds=3600)
    assert ledger.claim(user_id="u", token="a", pending_action={"x": 1}, now=1) == "claimed"
    assert ledger.prune_expired(now=3602) == 1

    inbound = InboundEventStore(tmp_path / "inbound.sqlite3")
    for offset in range(3):
        event = normalize_inbound_event(
            source_ref="source-a", provider_profile="", content_type="text/plain",
            body=f"row-{offset}".encode(), headers={}, remote_host="fake",
        )
        values = event.__dict__ if hasattr(event, "__dict__") else None
        inbound.record(event, max_events_per_source=1000)
    with sqlite3.connect(inbound.db_path) as connection:
        connection.execute("UPDATE inbound_events SET received_at='2020-01-01T00:00:00+00:00'")
    stats = inbound.prune_expired(retention_days=30, max_events_per_source=1000)
    assert stats["removed_age"] == 3

    tracker = TokenTracker(log_file=str(tmp_path / "tokens.jsonl"))
    for index in range(5):
        archive = tmp_path / f"tokens-archive-2020010{index + 1}T000000Z.jsonl"
        archive.write_text("{}\n", encoding="utf-8")
        os.utime(archive, (index + 1, index + 1))
    archive_stats = tracker.prune_archives(max_archives=3, max_age_days=180, now=200 * 86400)
    assert archive_stats["kept"] <= 3


def test_expired_web_evidence_is_physically_deleted() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.deleted: list[str] = []

        async def retrieve(self, **_kwargs):
            return [SimpleNamespace(payload={"expires_at": "2020-01-01T00:00:00+00:00"})]

        async def delete(self, *, points_selector, **_kwargs):
            self.deleted.extend(str(item) for item in points_selector.points)

    client = FakeClient()
    store = PublicWebEvidenceStore(
        qdrant_url="http://fake", qdrant_api_key="", collection="evidence", client=client,
    )
    assert anyio.run(store.lookup, "expired question") == ()
    assert len(client.deleted) == 1


def test_terminal_jobs_drop_resume_and_raw_step_output_and_cap_per_user(tmp_path: Path) -> None:
    store = AgentJobStore(tmp_path / "jobs.sqlite3")
    store.create(job_id="terminal", user_id="u", goal="goal", status="detached", now=1)
    store.append_step(
        "terminal", step_index=1, tool_names=["ssh_run"],
        outcome_summary="raw command output secret-canary", now=2,
    )
    assert store.stage_resume_state(
        "terminal", {"messages": [{"content": "secret-canary"}]}, user_id="u",
    )
    store.queue_correction("terminal", user_id="u", text="secret-canary", now=4)
    store.set_terminal("terminal", status="done", result="safe result", now=5)
    record = store.get("terminal")
    assert record is not None and record.resume_state is None and record.correction_queue == ()
    assert "secret-canary" not in json.dumps(record.as_dict())

    for index in range(505):
        job_id = f"old-{index:03d}"
        store.create(job_id=job_id, user_id="u", goal="g", status="detached", now=10 + index)
        store.set_terminal(job_id, status="done", result="ok", now=10 + index)
    assert len(store.list_for_user("u", limit=1000)) <= 500


def test_shipped_compose_and_setup_have_log_and_backup_hygiene() -> None:
    root = Path(__file__).resolve().parents[1]
    setup = (root / "docker" / "setup-compose-stack.sh").read_text(encoding="utf-8")
    assert "chmod 600" in setup
    assert "prune_upgrade_backups" in setup
    assert "successful" in setup.lower() or "health" in setup.lower()
    for rel in (
        "docker/portainer-stack.public.yml",
        "docker/portainer-stack.local.yml",
        "dist/docker-compose.managed.yml",
    ):
        raw = (root / rel).read_text(encoding="utf-8")
        assert "max-size: \"10m\"" in raw
        assert "max-file: \"3\"" in raw


def test_trace_admin_form_and_factory_reset_scope_are_explicit() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (root / "aria" / "templates" / "config_logs.html").read_text(encoding="utf-8")
    routes = (root / "aria" / "modules" / "ops_config_backup" / "detail_routes.py").read_text(encoding="utf-8")
    assert 'name="trace_retention_days"' in template
    assert 'name="trace_detail_level"' in template
    assert 'name="trace_max_mebibytes"' in template
    assert "sensitive document text" in template
    for path in ("data/notes", "data/modules/native_agent", "data/pricing", "data/runtime"):
        assert f'"{path}"' in routes
    assert "Host files outside ARIA data/config mounts are never touched" in template


def test_cleanup_resolves_pending_store_even_before_first_native_turn() -> None:
    root = Path(__file__).resolve().parents[1]
    routes = (root / "aria" / "modules" / "ops_config_backup" / "detail_routes.py").read_text(encoding="utf-8")
    main = (root / "aria" / "main.py").read_text(encoding="utf-8")
    expected = 'NativePendingStore(BASE_DIR / "data" / "runtime" / "native_pending_actions.sqlite3")'
    assert "NativePendingStore(" in routes and "pipeline._native_pending_store = pending" in routes
    assert "ActionConfirmationLedger(" in routes and "pipeline._native_confirmation_ledger = ledger" in routes
    assert "InboundEventStore(" in routes and "pipeline._inbound_event_store = inbound_store" in routes
    assert expected in main and "pipeline._native_pending_store = pending" in main
