from __future__ import annotations

import asyncio
import json

from aria.core.notes_action_arbitration import NotesActionArbiter


class _Response:
    def __init__(self, content: str) -> None:
        self.content = content
        self.usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}


class _NotesLLM:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.operations: list[str] = []

    async def chat(self, messages, **kwargs):
        _ = messages
        operation = str(kwargs.get("operation") or "")
        self.operations.append(operation)
        if operation == "notes_action_arbitration":
            return _Response(json.dumps(self.payload))
        return _Response("{}")


def test_notes_action_arbiter_returns_canonical_notes_command() -> None:
    llm = _NotesLLM(
        {
            "action": "search_notes",
            "canonical_command": "suche in notizen nach ARIA",
            "confidence": "high",
            "reason": "The user asks to search their notes.",
        }
    )

    decision = asyncio.run(
        NotesActionArbiter(llm).decide(
            "was steht in meinen notizen zu ARIA?",
            user_id="u1",
            request_id="req-1",
        )
    )

    assert decision.action == "search_notes"
    assert decision.canonical_command == "suche in notizen nach ARIA"
    assert decision.source == "notes_action_arbitration"
    assert llm.operations == ["notes_action_arbitration"]


def test_notes_action_arbiter_low_confidence_falls_back_to_regex() -> None:
    llm = _NotesLLM({"action": "search_notes", "canonical_command": "suche in notizen nach ARIA", "confidence": "low"})

    decision = asyncio.run(NotesActionArbiter(llm).decide("notizen?", user_id="u1"))

    assert decision.action == "fallback"
    assert decision.source == "regex_fallback"
