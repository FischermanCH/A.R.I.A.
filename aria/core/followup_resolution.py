from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score


TARGET_SPACES = {"web_search", "local_context", "chat"}


@dataclass(frozen=True)
class FollowupResolution:
    action: str = "fallback"
    target_space: str = "chat"
    rewritten_message: str = ""
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


def _recent_history(history: list[dict[str, Any]], *, limit: int = 6) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in list(history or [])[-limit:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "") or "").strip().lower()
        text = _clean_text(item.get("text"), limit=800)
        if role in {"user", "assistant"} and text:
            rows.append({"role": role, "text": text})
    return rows


class FollowupResolver:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def resolve(
        self,
        message: str,
        *,
        history: list[dict[str, Any]],
        user_id: str = "",
        request_id: str = "",
        source: str = "chat_followup",
    ) -> FollowupResolution:
        clean_message = _clean_text(message)
        if not clean_message:
            return FollowupResolution(action="no_rewrite", rewritten_message="", source="empty")
        if clean_message.startswith("/"):
            return FollowupResolution(action="fallback", rewritten_message=clean_message, source="slash_command")
        result = await self.decision_client.decide_json(
            operation="followup_resolution",
            system=(
                "Resolve whether the current user message is a vague follow-up that needs rewriting before ARIA routes it. "
                "Return JSON only. action must be rewrite or no_rewrite. target_space must be web_search, local_context, or chat. "
                "Rewrite only when the user clearly refers to a recent topic with words like dazu/davon/that/it/there and the rewrite improves routing. "
                "For web_search, preserve explicit search phrasing such as 'suche im internet nach <topic>'. "
                "For local_context, preserve explicit notes/documents phrasing such as 'was steht in meinen notizen zu <topic>'. "
                "Do not rewrite specific standalone queries. Do not invent topics not present in recent history."
            ),
            payload={"message": clean_message, "recent_history": _recent_history(history)},
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return FollowupResolution(
                action="fallback",
                rewritten_message=clean_message,
                source="regex_fallback",
                usage=result.usage,
                error=result.error,
            )
        action = str(result.payload.get("action") or "").strip().lower()
        target_space = str(result.payload.get("target_space") or "chat").strip().lower()
        confidence = confidence_score(result.payload.get("confidence"))
        if action not in {"rewrite", "no_rewrite"} or target_space not in TARGET_SPACES:
            return FollowupResolution(
                action="fallback",
                rewritten_message=clean_message,
                source="regex_fallback",
                usage=result.usage,
                error="invalid_payload",
            )
        if confidence < 0.62:
            return FollowupResolution(
                action="fallback",
                rewritten_message=clean_message,
                confidence=confidence,
                reason="low_confidence",
                source="regex_fallback",
                usage=result.usage,
            )
        rewritten = _clean_text(result.payload.get("rewritten_message") or clean_message)
        if action == "rewrite" and not rewritten:
            action = "no_rewrite"
            rewritten = clean_message
        return FollowupResolution(
            action=action,
            target_space=target_space,
            rewritten_message=rewritten,
            confidence=confidence,
            reason=_clean_text(result.payload.get("reason"), limit=400),
            source="followup_resolution",
            usage=result.usage,
        )
