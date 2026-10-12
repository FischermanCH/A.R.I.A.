#!/usr/bin/env python3
"""Create the deterministic, public-safe seed for the isolated ARIA demo."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any

import yaml

from aria.modules.activity_journal.store import ActivityJournalStore
from aria.modules.pipeline_orchestrator.agent_jobs import AgentJobStore
from aria.modules.security_storage.auth_manager import AuthManager
from aria.modules.security_storage.secure_store import SecureConfigStore, SecureStoreConfig


DEMO_USER = "demo-admin"
DEMO_PASSWORD = "aria-demo-access"
ANCHOR = datetime(2026, 10, 10, 14, 30, tzinfo=timezone.utc)


def _reset_directory_contents(directory: Path) -> None:
    """Reset generated content without invalidating an active demo bind mount."""

    directory.mkdir(parents=True, exist_ok=True)
    for child in directory.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_text_atomic(target: Path, content: str) -> None:
    temporary = target.with_name(f".{target.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, target)


def _connection_config() -> dict[str, Any]:
    rows: dict[str, Any] = {
        "ssh": {
            "observatory": {"title": "Demo Observatory", "host": "observatory.example.com", "user": "demo", "timeout_seconds": 1},
            "workshop": {"title": "Demo Workshop", "host": "workshop.example.org", "user": "demo", "timeout_seconds": 1},
        },
        "sftp": {"archive": {"title": "Demo Archive", "host": "archive.example.com", "user": "demo", "root_path": "/demo", "timeout_seconds": 1}},
        "smb": {"library": {"title": "Demo Library", "host": "library.example.org", "share": "public-demo", "user": "demo", "root_path": "/", "timeout_seconds": 1}},
        "discord": {"community": {"title": "Demo Community", "webhook_url": "https://example.com/demo-webhook", "timeout_seconds": 1}},
        "website": {"handbook": {"title": "Demo Handbook", "url": "https://example.org/handbook", "group_name": "Documentation", "timeout_seconds": 1}},
        "webhook": {"automation": {"title": "Demo Automation", "url": "https://example.com/hooks/demo", "method": "POST", "timeout_seconds": 1}},
        "http_api": {"catalog": {"title": "Demo Catalog API", "base_url": "https://api.example.org/v1", "health_path": "/health", "method": "GET", "timeout_seconds": 1}},
        "google_calendar": {"events": {"title": "Demo Events", "ical_url": "https://example.com/calendar/demo.ics", "timeout_seconds": 1}},
        "mqtt": {"sensors": {"title": "Demo Sensors", "host": "mqtt.example.org", "port": 1883, "topic": "demo/status", "timeout_seconds": 1}},
        "email": {"outbox": {"title": "Demo Outbox", "smtp_host": "smtp.example.com", "from_email": "aria@example.com", "to_email": "team@example.org", "timeout_seconds": 1}},
        "imap": {"inbox": {"title": "Demo Inbox", "host": "imap.example.org", "user": "demo@example.org", "mailbox": "INBOX", "timeout_seconds": 1}},
    }
    groups = ("Engineering", "Research", "Product")
    rows["rss"] = {
        f"feed-{index:02d}": {
            "title": f"Demo Feed {index:02d}",
            "feed_url": f"https://feed-{index:02d}.example.org/rss.xml",
            **({"group_name": groups[(index - 1) % 3]} if index <= 27 else {}),
            "timeout_seconds": 1,
        }
        for index in range(1, 33)
    }
    return rows


def _config() -> dict[str, Any]:
    return {
        "aria": {"host": "0.0.0.0", "port": 8800, "log_level": "info", "public_url": ""},
        "llm": {"model": "demo/offline", "api_base": "", "api_key": "", "temperature": None, "max_tokens": 1024, "timeout_seconds": 8},
        "embeddings": {"model": "demo/offline-embedding", "api_base": "", "api_key": "", "timeout_seconds": 8},
        "memory": {"enabled": True, "backend": "qdrant", "qdrant_url": "http://qdrant:6333", "qdrant_api_key": ""},
        "inventory_index": {"enabled": False, "run_on_startup": False, "timezone": "Europe/Zurich"},
        "routing": {"qdrant_connection_routing_enabled": False},
        "agentic_loop": {"enabled": False, "native_agent_mcp_enabled": False, "activity_journal_enabled": True, "activity_journal_retention_days": 90},
        "mcp_servers": {"studio": {"transport": "sse", "url": "https://mcp.example.org/sse", "headers": {}, "enabled": False, "trusted": False, "title": "Demo Studio MCP"}},
        "ui": {"title": "ARIA Demo", "debug_mode": True, "language": "de", "theme": "matrix", "background": "grid-signal", "display_timezone": "Europe/Zurich"},
        "security": {"enabled": True, "db_path": "data/auth/aria_secure.sqlite", "bootstrap_locked": True},
        "pricing": {
            "enabled": True,
            "chat_models": {
                "demo/sonnet": {"input_per_million": 3.0, "output_per_million": 15.0, "source_name": "Demo price"},
                "demo/haiku": {"input_per_million": 0.8, "output_per_million": 4.0, "source_name": "Demo price"},
            },
            "embedding_models": {"demo/embed": {"input_per_million": 0.02, "source_name": "Demo price"}},
        },
        "token_tracking": {"enabled": True, "log_file": "data/logs/tokens.jsonl", "retention_days": 90},
        "connections": _connection_config(),
    }


def _seed_journal(data: Path) -> None:
    store = ActivityJournalStore(data / "runtime" / "activity_journal.sqlite3")
    tools = ("document_content_read", "ssh_read", "rss_feed_read", "activity_journal_read", "mcp__studio__scene_info")
    for day in range(30):
        for index in range(2):
            when = (ANCHOR - timedelta(days=day, hours=index)).timestamp()
            tool = tools[(day + index) % len(tools)]
            store.write({
                "id": f"demo-journal-{day:02d}-{index}", "user_id": DEMO_USER,
                "started_at": when - 4, "finished_at": when, "kind": "turn", "job_id": "",
                "goal": f"Review fictitious demo item {day + 1}", "tools": {tool: 1},
                "connection_kinds": ["mcp" if tool.startswith("mcp__") else tool.split("_", 1)[0]],
                "connection_refs": ["observatory"] if tool == "ssh_read" else [],
                "mcp_servers": ["studio"] if tool.startswith("mcp__") else [],
                "outcome_status": "error" if day in {9, 22} and index == 1 else "ok",
                "confirmations": {"asked": int(day % 8 == 0), "approved": int(day % 8 == 0), "rejected": 0},
                "corrected": bool(day % 11 == 0), "outcome_phrase": "Demo task completed with synthetic data.",
                "source": "live", "keep": False, "input_tokens": 640 + day * 7,
                "output_tokens": 120 + index * 20, "embedding_tokens": 32, "cost_usd": round(0.03 + day * 0.001, 5),
                "created_at": when,
            })


def _seed_jobs(data: Path) -> None:
    store = AgentJobStore(data / "runtime" / "agent_jobs.sqlite3")
    states = ("running", "detached", "paused", "awaiting_confirmation", "done", "error", "cancelled")
    for index, status in enumerate(states):
        job_id = f"demo-job-{index + 1:02d}"
        created = (ANCHOR - timedelta(days=index)).timestamp()
        initial = status if status not in {"done", "error", "cancelled"} else "detached"
        store.create(job_id=job_id, user_id=DEMO_USER, goal=f"Synthetic {status} showcase task", status=initial, worker_id="demo", now=created)
        store.append_step(job_id, step_index=1, tool_names=("mcp__studio__scene_info",), outcome_summary="Synthetic scene summary", now=created + 1)
        store.set_usage(job_id, {"input_tokens": 850 + index * 100, "output_tokens": 210, "cost_usd": 0.08 + index * 0.01}, now=created + 2)
        if status in {"done", "error", "cancelled"}:
            result = "## Demo result\n\n| Item | Status |\n|---|---|\n| Synthetic scene | Ready |" if status == "done" else f"Synthetic {status} result"
            store.set_terminal(job_id, status=status, result=result, now=created + 3)


def _seed_usage(data: Path) -> None:
    target = data / "logs" / "tokens.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for day in range(35):
        when = ANCHOR - timedelta(days=day)
        for index, model in enumerate(("demo/sonnet", "demo/haiku")):
            cost = round((0.18 if index == 0 else 0.06) + (day % 7) * 0.012, 6)
            lines.append(json.dumps({
                "timestamp": when.isoformat().replace("+00:00", "Z"), "request_id": f"demo-usage-{day:02d}-{index}",
                "user_id": DEMO_USER, "intents": ["native_agent"], "router_level": 1,
                "prompt_tokens": 2200 + day * 17, "completion_tokens": 420 + index * 35,
                "total_tokens": 2620 + day * 17 + index * 35, "chat_model": model,
                "embedding_model": "demo/embed", "embedding_prompt_tokens": 160,
                "embedding_total_tokens": 160, "chat_cost_usd": cost - 0.002,
                "embedding_cost_usd": 0.002, "total_cost_usd": cost, "duration_ms": 820,
                "source": "agent_job" if day % 3 == 0 else "chat",
            }, ensure_ascii=True))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_chats(data: Path) -> None:
    directory = data / "chat_history"
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {"role": "user", "text": "Zeige mir den Demo-Katalog.", "timestamp": "2026-10-10T13:00:00Z"},
        {"role": "assistant", "text": "Das Werkzeug hat drei vollständig erfundene Katalogeinträge gefunden.\n\n| Eintrag | Status |\n|---|---|\n| Demo-Handbuch | Bereit |\n| Beispielkatalog | Bereit |\n| Testnotiz | Bereit |", "badge_icon": "🔧", "badge_intent": "documents_read_search_inventory", "badge_tokens": 312, "badge_cost_usd": "0.0040", "badge_duration": "0.8", "badge_details": ["Demo tool result"], "timestamp": "2026-10-10T13:00:02Z"},
        {"role": "user", "text": "Starte die längere Demo-Aufgabe.", "timestamp": "2026-10-10T13:10:00Z"},
        {"role": "assistant", "text": "Die Aufgabe läuft im Hintergrund als Demo-Job.", "agent_job_id": "demo-job-05", "timestamp": "2026-10-10T13:10:25Z"},
        {"role": "assistant", "text": "✅ Der Demo-Job ist fertig.\n\n| Ergebnis | Zustand |\n|---|---|\n| Fiktive Szene | Bereit |", "agent_job_id": "demo-job-05", "agent_job_notice": True, "agent_job_event_key": "terminal", "timestamp": "2026-10-10T13:10:31Z"},
        {"role": "assistant", "text": "Bestätigungsvorschau für die fiktive Aktion.\n\n**Server:** studio  \n**Tool:** execute_demo_action  \n**Argument:** `target=workshop`\n\nDie echte Ausführung würde eine ausdrückliche Bestätigung verlangen.", "badge_intent": "demo_confirmation_preview", "agent_job_id": "demo-job-04", "agent_job_notice": True, "agent_job_event_key": "confirmation", "timestamp": "2026-10-10T13:20:00Z"},
        {"role": "user", "text": "Show the synthetic studio scene.", "timestamp": "2026-10-10T13:30:00Z"},
        {"role": "assistant", "text": "The MCP demo returned a synthetic scene with one cube and one light.", "badge_icon": "🧩", "badge_intent": "mcp__studio__scene_info", "timestamp": "2026-10-10T13:30:02Z"},
    ]
    (directory / f"{DEMO_USER}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_recipes(data: Path) -> None:
    directory = data / "recipes"
    directory.mkdir(parents=True, exist_ok=True)
    recipes = (
        ("morning-demo-brief", "Morning Demo Brief", "rss_read", "feed-01"),
        ("workshop-health-summary", "Workshop Health Summary", "ssh_run", "workshop"),
        ("catalog-watch", "Catalog Watch", "http_api_request", "catalog"),
    )
    for recipe_id, name, step_type, connection_ref in recipes:
        payload = {"schema_version": "1.1", "id": recipe_id, "name": name, "version": "0.1.0", "description": "Synthetic inactive recipe for the public demo.", "category": "demo", "router_keywords": ["demo"], "connections": [], "prompt_file": "", "schedule": {"enabled": False, "cron": "", "timezone": "Europe/Zurich", "run_on_startup": False}, "ui": {"hint": "Fictitious demo data"}, "enabled_default": False, "steps": [{"id": "step-1", "name": "Demo step", "type": step_type, "connection_ref": connection_ref, "params": {}, "on_error": "stop"}]}
        (directory / f"{recipe_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    generated = args.root / "demo" / "generated"
    config_dir = generated / "config"
    data = generated / "data"
    generated.mkdir(parents=True, exist_ok=True)
    # Keep entrypoint-managed security files intact when regenerating a seed
    # while the isolated demo bind mount is active.
    config_dir.mkdir(parents=True, exist_ok=True)
    _reset_directory_contents(data)
    _write_text_atomic(
        config_dir / "config.yaml",
        yaml.safe_dump(_config(), allow_unicode=True, sort_keys=False),
    )
    master = hashlib.sha256(b"ARIA public synthetic demo master key").digest()
    master_text = base64.urlsafe_b64encode(master).decode("ascii").rstrip("=")
    _write_text_atomic(
        generated / ".env",
        f"ARIA_DEMO_IMAGE={os.environ.get('ARIA_DEMO_IMAGE', 'fischermanch/aria:0.1.0-alpha.1007')}\n"
        f"ARIA_DEMO_PORT={os.environ.get('ARIA_DEMO_PORT', '8090')}\n"
        f"ARIA_DEMO_QDRANT_PORT={os.environ.get('ARIA_DEMO_QDRANT_PORT', '8091')}\n"
        f"ARIA_DEMO_MASTER_KEY={master_text}\n",
    )
    auth_store = SecureConfigStore(SecureStoreConfig(data / "auth" / "aria_secure.sqlite", enabled=True), master)
    AuthManager(auth_store).upsert_user(DEMO_USER, DEMO_PASSWORD, role="admin")
    _seed_journal(data)
    _seed_jobs(data)
    _seed_usage(data)
    _seed_chats(data)
    _seed_recipes(data)
    docs = data / "documents"
    docs.mkdir(parents=True)
    (docs / "demo-handbook.txt").write_text("Synthetic demo handbook. No real user or organization data.\n", encoding="utf-8")
    manifest = {"schema": 1, "seed": "alpha1007-demo-v1", "user": DEMO_USER, "anchor": ANCHOR.isoformat(), "connections": 13, "rss_feeds": 32, "journal_entries": 60, "jobs": 7, "recipes": 3}
    (data / "demo-seed-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
