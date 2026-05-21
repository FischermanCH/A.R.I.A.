from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import aria.core.llm_client as llm_client_mod
from aria.core.config import LLMConfig
from aria.core.llm_audit import GLOBAL_LLM_AUDIT_LOG, LLMAuditLog
from aria.core.llm_client import LLMClient


def test_llm_audit_redacts_and_records_gateway_prompt(monkeypatch) -> None:
    GLOBAL_LLM_AUDIT_LOG.clear()

    async def fake_acompletion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content='{"ok": true}'),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3, total_tokens=10),
        )

    monkeypatch.setattr(llm_client_mod, "_acompletion", fake_acompletion)
    client = LLMClient(
        LLMConfig(
            model="test-model",
            api_key="sk-secret-key-that-must-not-leak",
        )
    )

    response = asyncio.run(
        client.chat(
            [
                {"role": "system", "content": "Use api_key: sk-secret-key-that-must-not-leak"},
                {"role": "user", "content": "webhook_url=https://discord.com/api/webhooks/abc/def"},
            ],
            source="test",
            operation="unit",
            user_id="user-1",
        )
    )

    assert response.content == '{"ok": true}'
    rows = GLOBAL_LLM_AUDIT_LOG.entries()
    assert len(rows) == 1
    row = rows[0]
    assert row["model"] == "test-model"
    assert row["source"] == "test"
    assert row["operation"] == "unit"
    assert row["usage"]["total_tokens"] == 10
    text = "\n".join(message["content"] for message in row["messages"])
    assert "sk-secret-key-that-must-not-leak" not in text
    assert "https://discord.com/api/webhooks/abc/def" not in text
    assert "[REDACTED]" in text


def test_llm_audit_reads_redacted_entries_from_shared_file(tmp_path) -> None:
    path = tmp_path / "llm_audit.jsonl"
    first = LLMAuditLog(path=path)
    first.record(
        model="model-a",
        source="chat",
        operation="final_chat_response",
        messages=[{"role": "user", "content": "authorization: secret-token"}],
        response="ok",
        usage={"total_tokens": 5},
    )

    second = LLMAuditLog(path=path)
    rows = second.entries()

    assert len(rows) == 1
    assert rows[0]["operation"] == "final_chat_response"
    assert rows[0]["usage"]["total_tokens"] == 5
    assert "secret-token" not in rows[0]["messages"][0]["content"]


def test_llm_audit_prunes_entries_by_retention_days(tmp_path) -> None:
    path = tmp_path / "llm_audit.jsonl"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat(timespec="seconds")
    fresh_ts = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    path.write_text(
        "\n".join(
            [
                json.dumps({"created_at": old_ts, "operation": "old", "messages": []}),
                json.dumps({"created_at": fresh_ts, "operation": "fresh", "messages": []}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    audit = LLMAuditLog(path=path)
    stats = audit.prune_old_entries(90)

    assert stats == {"total": 2, "kept": 1, "removed": 1}
    rows = audit.entries()
    assert len(rows) == 1
    assert rows[0]["operation"] == "fresh"
