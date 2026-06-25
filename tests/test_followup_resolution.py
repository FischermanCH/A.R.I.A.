from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from aria.core.followup_resolution import FollowupResolver


class _FollowupLLM:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload
        self.operations: list[str] = []

    async def chat(self, _messages, **kwargs):
        self.operations.append(str(kwargs.get("operation") or ""))
        return SimpleNamespace(
            content=json.dumps(self.payload),
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        )


def test_followup_resolver_accepts_high_confidence_rewrite() -> None:
    llm = _FollowupLLM(
        {
            "action": "rewrite",
            "target_space": "web_search",
            "rewritten_message": "suche im internet nach claude code latest release",
            "confidence": "high",
            "reason": "vague follow-up refers to recent Claude Code topic",
        }
    )

    decision = asyncio.run(
        FollowupResolver(llm).resolve(
            "suche im internet nach der neusten version",
            history=[{"role": "user", "text": "welche version von claude code ist momentan aktuell"}],
            user_id="neo",
        )
    )

    assert decision.source == "followup_resolution"
    assert decision.action == "rewrite"
    assert decision.target_space == "web_search"
    assert decision.rewritten_message == "suche im internet nach claude code latest release"
    assert decision.usage["total_tokens"] == 5
    assert llm.operations == ["followup_resolution"]


def test_followup_resolver_low_confidence_uses_fallback_boundary() -> None:
    llm = _FollowupLLM(
        {
            "action": "rewrite",
            "target_space": "web_search",
            "rewritten_message": "suche im internet nach guessed topic",
            "confidence": "low",
        }
    )

    decision = asyncio.run(
        FollowupResolver(llm).resolve(
            "suche im internet nach der neusten version",
            history=[{"role": "user", "text": "welche version von claude code ist momentan aktuell"}],
        )
    )

    assert decision.source == "regex_fallback"
    assert decision.action == "fallback"
    assert decision.rewritten_message == "suche im internet nach der neusten version"


def test_followup_resolver_slash_commands_skip_llm() -> None:
    llm = _FollowupLLM({"action": "rewrite", "target_space": "chat", "confidence": "high"})

    decision = asyncio.run(FollowupResolver(llm).resolve("/stats", history=[]))

    assert decision.source == "slash_command"
    assert decision.action == "fallback"
    assert decision.rewritten_message == "/stats"
    assert llm.operations == []
