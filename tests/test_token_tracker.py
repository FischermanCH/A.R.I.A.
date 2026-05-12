import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT
from aria.core.recipe_runtime_contract import build_recipe_intent
from aria.core.token_tracker import TokenTracker


def test_get_recent_activities_filters_and_summarizes(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": "2026-03-26T10:00:00+00:00",
            "user_id": "DemoUser",
            "intents": [build_recipe_intent("server-update-2nodes")],
            "duration_ms": 3200,
            "total_tokens": 421,
            "total_cost_usd": 0.001508,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
        {
            "timestamp": "2026-03-26T09:00:00+00:00",
            "user_id": "DemoUser",
            "intents": ["memory_recall"],
            "duration_ms": 600,
            "total_tokens": 120,
            "total_cost_usd": 0.0,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
        {
            "timestamp": "2026-03-26T08:00:00+00:00",
            "user_id": "DemoUser",
            "intents": [RECIPE_STATUS_INTENT],
            "duration_ms": 250,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "chat_model": "",
            "source": "chat",
            "recipe_errors": ["recipe_ssh_nonzero_exit"],
        },
        {
            "timestamp": "2026-03-26T07:00:00+00:00",
            "user_id": "anderer",
            "intents": [build_recipe_intent("ignored")],
            "duration_ms": 100,
            "total_tokens": 1,
            "total_cost_usd": 0.0,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
        {
            "timestamp": "2026-03-26T06:00:00+00:00",
            "user_id": "DemoUser",
            "intents": ["chat"],
            "duration_ms": 100,
            "total_tokens": 1,
            "total_cost_usd": 0.0,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    data = asyncio.run(tracker.get_recent_activities(user_id="DemoUser", limit=10))

    assert data["summary"] == {"count": 3, "success": 2, "errors": 1, "avg_duration_ms": 1350}
    assert [row["intent"] for row in data["rows"]] == [
        "recipe:server-update-2nodes",
        "memory_recall",
        "recipe_status",
    ]
    assert data["rows"][0]["kind"] == "recipe"
    assert data["rows"][0]["title"] == "Server Update 2Nodes"
    assert data["rows"][2]["success"] is False
    assert data["rows"][2]["recipe_errors"] == ["recipe_ssh_nonzero_exit"]
    assert data["rows"][2]["skill_errors"] == ["recipe_ssh_nonzero_exit"]
    assert data["rows"][2]["show_tokens"] is False
    assert data["rows"][2]["show_cost"] is False
    assert data["rows"][2]["show_model"] is False
    assert data["rows"][2]["show_source"] is False


def test_prune_old_entries_removes_expired_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    new_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    entries = [
        {"timestamp": old_ts, "user_id": "u1", "intents": ["memory_recall"]},
        {"timestamp": new_ts, "user_id": "u1", "intents": ["memory_recall"]},
        {"timestamp": "broken", "user_id": "u1", "intents": ["memory_recall"]},
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    result = asyncio.run(tracker.prune_old_entries(retention_days=30))

    assert result == {"total": 3, "kept": 2, "removed": 1}
    remaining = log_path.read_text(encoding="utf-8").splitlines()
    assert len(remaining) == 2
    assert old_ts not in log_path.read_text(encoding="utf-8")


def test_get_recent_activities_applies_kind_and_status_filters(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": "2026-03-26T10:00:00+00:00",
            "user_id": "DemoUser",
            "intents": [build_recipe_intent("server-update-2nodes")],
            "duration_ms": 3200,
            "total_tokens": 421,
            "total_cost_usd": 0.001508,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": ["recipe_ssh_nonzero_exit"],
        },
        {
            "timestamp": "2026-03-26T09:00:00+00:00",
            "user_id": "DemoUser",
            "intents": [build_recipe_intent("server-update-2nodes")],
            "duration_ms": 1200,
            "total_tokens": 300,
            "total_cost_usd": 0.001000,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
        {
            "timestamp": "2026-03-26T08:00:00+00:00",
            "user_id": "DemoUser",
            "intents": ["memory_recall"],
            "duration_ms": 500,
            "total_tokens": 80,
            "total_cost_usd": 0.0,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    data = asyncio.run(
        tracker.get_recent_activities(user_id="DemoUser", limit=10, kind="recipe", status="error")
    )

    assert data["summary"] == {"count": 1, "success": 0, "errors": 1, "avg_duration_ms": 3200}
    assert len(data["rows"]) == 1
    assert data["rows"][0]["intent"] == "recipe:server-update-2nodes"
    assert data["rows"][0]["success"] is False


def test_get_recent_activities_includes_capability_runs(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": "2026-03-26T10:00:00+00:00",
            "user_id": "DemoUser",
            "intents": ["capability:file_list"],
            "duration_ms": 850,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "chat_model": "",
            "source": "chat",
            "recipe_errors": [],
        },
        {
            "timestamp": "2026-03-26T09:00:00+00:00",
            "user_id": "DemoUser",
            "intents": ["chat"],
            "duration_ms": 120,
            "total_tokens": 5,
            "total_cost_usd": 0.0,
            "chat_model": "gpt-4.1",
            "source": "chat",
            "recipe_errors": [],
        },
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    data = asyncio.run(tracker.get_recent_activities(user_id="DemoUser", limit=10))

    assert data["summary"] == {"count": 1, "success": 1, "errors": 0, "avg_duration_ms": 850}
    assert len(data["rows"]) == 1
    assert data["rows"][0]["intent"] == "capability:file_list"
    assert data["rows"][0]["kind"] == "system"
    assert data["rows"][0]["title"] == "File List"


def test_clear_log_removes_all_entries_and_file(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {"timestamp": "2026-03-26T10:00:00+00:00", "user_id": "u1", "intents": ["chat"]},
        {"timestamp": "2026-03-26T11:00:00+00:00", "user_id": "u1", "intents": ["memory_recall"]},
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    result = asyncio.run(tracker.clear_log())

    assert result == {"removed": 2}
    assert not log_path.exists()


def test_get_stats_does_not_count_zero_cost_rows_as_priced(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "u1",
            "intents": [RECIPE_STATUS_INTENT],
            "total_tokens": 0,
            "chat_model": "",
            "embedding_model": "",
            "chat_cost_usd": None,
            "embedding_cost_usd": None,
            "total_cost_usd": None,
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "u1",
            "intents": ["memory_recall"],
            "total_tokens": 10,
            "chat_model": "gpt-4.1",
            "embedding_model": "",
            "chat_cost_usd": 0.0,
            "embedding_cost_usd": 0.0,
            "total_cost_usd": 0.0,
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "u1",
            "intents": ["chat"],
            "total_tokens": 1000,
            "chat_model": "gpt-4.1",
            "embedding_model": "",
            "chat_cost_usd": 0.001,
            "embedding_cost_usd": None,
            "total_cost_usd": 0.001,
        },
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    stats = asyncio.run(tracker.get_stats(days=7))

    assert stats["priced_requests_count"] == 1
    assert stats["total_cost_usd"] == 0.001
    assert stats["avg_cost_usd_per_request"] == 0.001


def test_get_stats_groups_requests_and_costs_by_source(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    entries = [
        {
            "timestamp": now,
            "user_id": "u1",
            "intents": ["chat"],
            "source": "chat",
            "total_tokens": 120,
            "embedding_total_tokens": 0,
            "extraction_total_tokens": 0,
            "chat_model": "gpt-4.1",
            "embedding_model": "",
            "chat_cost_usd": 0.0012,
            "embedding_cost_usd": 0.0,
            "total_cost_usd": 0.0012,
        },
        {
            "timestamp": now,
            "user_id": "u1",
            "intents": ["memory_recall"],
            "source": "rag_ingest",
            "total_tokens": 0,
            "embedding_total_tokens": 320,
            "extraction_total_tokens": 0,
            "chat_model": "",
            "embedding_model": "text-embedding-3-small",
            "chat_cost_usd": 0.0,
            "embedding_cost_usd": 0.0001,
            "total_cost_usd": 0.0001,
        },
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    stats = asyncio.run(tracker.get_stats(days=7))

    assert stats["requests_by_source"] == {"chat": 1, "rag_ingest": 1}
    assert stats["model_tokens_by_source"] == {"chat": 120, "rag_ingest": 320}
    assert stats["cost_usd_by_source"] == {"chat": 0.0012, "rag_ingest": 0.0001}


def test_get_stats_exposes_chat_embedding_and_model_token_totals(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "u1",
            "intents": ["chat"],
            "total_tokens": 120,
            "embedding_total_tokens": 45,
            "extraction_total_tokens": 9,
            "chat_model": "gpt-5.5",
            "embedding_model": "text-embedding-3-small",
            "chat_cost_usd": 0.0012,
            "embedding_cost_usd": 0.0001,
            "total_cost_usd": 0.0013,
        }
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    stats = asyncio.run(tracker.get_stats(days=7))

    assert stats["total_tokens"] == 120
    assert stats["chat_total_tokens"] == 120
    assert stats["embedding_total_tokens"] == 45
    assert stats["extraction_total_tokens"] == 9
    assert stats["model_total_tokens"] == 174
    assert stats["chat_prompt_tokens_by_model"] == {"gpt-5.5": 0}
    assert stats["chat_completion_tokens_by_model"] == {"gpt-5.5": 0}
    assert stats["embedding_prompt_tokens_by_model"] == {"text-embedding-3-small": 45}


def test_get_stats_exposes_model_prompt_completion_breakdown_for_cost_replay(tmp_path: Path) -> None:
    log_path = tmp_path / "tokens.jsonl"
    entries = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": "u1",
            "intents": ["chat"],
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "embedding_prompt_tokens": 30,
            "embedding_total_tokens": 30,
            "chat_model": "anthropic/claude-sonnet-4-5",
            "embedding_model": "openai/text-embedding-3-small",
            "chat_cost_usd": None,
            "embedding_cost_usd": None,
            "total_cost_usd": None,
        }
    ]
    with log_path.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry) + "\n")

    tracker = TokenTracker(str(log_path), enabled=True)
    stats = asyncio.run(tracker.get_stats(days=7))

    assert stats["chat_tokens_by_model"] == {"anthropic/claude-sonnet-4-5": 125}
    assert stats["chat_prompt_tokens_by_model"] == {"anthropic/claude-sonnet-4-5": 100}
    assert stats["chat_completion_tokens_by_model"] == {"anthropic/claude-sonnet-4-5": 25}
    assert stats["embedding_tokens_by_model"] == {"openai/text-embedding-3-small": 30}
    assert stats["embedding_prompt_tokens_by_model"] == {"openai/text-embedding-3-small": 30}
