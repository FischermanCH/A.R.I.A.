from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score


NOTES_ACTIONS = {
    "open_notes",
    "search_notes",
    "list_folders",
    "list_notes_in_folder",
    "open_note",
    "create_note",
    "quick_note",
    "web_search_with_notes",
    "save_web_source",
    "no_action",
}


@dataclass(frozen=True)
class NotesActionDecision:
    action: str = "fallback"
    canonical_command: str = ""
    confidence: float = 0.0
    reason: str = ""
    source: str = "regex_fallback"
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""


def _clean_text(value: Any, *, limit: int = 1200) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


class NotesActionArbiter:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def decide(
        self,
        message: str,
        *,
        user_id: str = "",
        request_id: str = "",
        source: str = "chat_notes",
    ) -> NotesActionDecision:
        clean_message = _clean_text(message)
        if not clean_message:
            return NotesActionDecision(action="no_action", source="empty")
        if clean_message.startswith("/"):
            return NotesActionDecision(action="fallback", source="slash_command")
        result = await self.decision_client.decide_json(
            operation="notes_action_arbitration",
            system=(
                "Classify whether a chat message should trigger ARIA Notes. Return JSON only. "
                "Allowed actions: open_notes, search_notes, list_folders, list_notes_in_folder, open_note, "
                "create_note, quick_note, web_search_with_notes, save_web_source, no_action. "
                "Choose no_action for ordinary chat, explanation, or questions that merely mention notes without asking ARIA "
                "to open/search/list/create/save notes. For an action, provide canonical_command in the existing command language, "
                "for example 'open notes', 'suche in notizen nach <query>', 'zeige ordner in notizen', "
                "'zeige notizen in <folder>', 'oeffne notiz <query>', 'erstelle notiz <title>: <body>', "
                "'halte fest <body>', 'speichere webseite <url> als notiz', or "
                "'suche im internet nach <query> mit meinen notizen zu <topic>'. "
                "Do not invent note contents or URLs."
            ),
            payload={"message": clean_message},
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return NotesActionDecision(action="fallback", source="regex_fallback", usage=result.usage, error=result.error)
        action = str(result.payload.get("action") or "").strip().lower()
        if action not in NOTES_ACTIONS:
            return NotesActionDecision(action="fallback", source="regex_fallback", usage=result.usage, error="invalid_action")
        confidence = confidence_score(result.payload.get("confidence"))
        if confidence < 0.62:
            return NotesActionDecision(
                action="fallback",
                confidence=confidence,
                reason="low_confidence",
                source="regex_fallback",
                usage=result.usage,
            )
        return NotesActionDecision(
            action=action,
            canonical_command=_clean_text(result.payload.get("canonical_command"), limit=1400),
            confidence=confidence,
            reason=_clean_text(result.payload.get("reason"), limit=400),
            source="notes_action_arbitration",
            usage=result.usage,
        )
