from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.bounded_decision import confidence_score
from aria.core.router import RouterDecision


TURN_INTENT_ALLOWED = {
    "chat",
    "memory_store",
    "memory_recall",
    "memory_forget",
    "web_search",
}


@dataclass(frozen=True)
class TurnIntentArbitration:
    decision: RouterDecision
    source: str = "keyword_router"
    reason: str = ""
    confidence: float = 0.0
    usage: dict[str, int] = field(default_factory=dict)
    error: str = ""


def _clean_intents(values: Any, *, allowed: set[str]) -> list[str]:
    raw_values: Iterable[Any]
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list | tuple | set):
        raw_values = values
    else:
        raw_values = []
    rows: list[str] = []
    for value in raw_values:
        clean = str(value or "").strip().lower()
        if clean == "no_action":
            clean = "chat"
        if clean not in allowed:
            continue
        if clean not in rows:
            rows.append(clean)
    if not rows:
        return ["chat"]
    if "chat" in rows and len(rows) > 1:
        rows = [item for item in rows if item != "chat"]
    return rows or ["chat"]


def _keyword_signal_payload(decision: RouterDecision) -> dict[str, Any]:
    return {
        "intents": [str(intent or "").strip() for intent in list(decision.intents or [])],
        "level": int(decision.level or 0),
        "source": "keyword_router",
    }


class TurnIntentArbiter:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def arbitrate(
        self,
        *,
        message: str,
        keyword_decision: RouterDecision,
        language: str | None = None,
        available_intents: set[str] | None = None,
        source: str = "pipeline",
        user_id: str = "",
        request_id: str = "",
        active_learning_hints: list[dict[str, Any]] | None = None,
    ) -> TurnIntentArbitration:
        allowed = set(available_intents or TURN_INTENT_ALLOWED) & TURN_INTENT_ALLOWED
        if not allowed:
            allowed = {"chat"}
        fallback_intents = _clean_intents(keyword_decision.intents, allowed=allowed | {"chat"})
        fallback = RouterDecision(intents=fallback_intents, level=int(keyword_decision.level or 1))
        clean_message = str(message or "").strip()
        if not clean_message:
            return TurnIntentArbitration(decision=fallback, source="keyword_router", reason="empty_message")
        if clean_message.startswith("/"):
            return TurnIntentArbitration(decision=fallback, source="keyword_router", reason="slash_command")

        system = (
            "You arbitrate ARIA's top-level turn intent from keyword-router signals. "
            "Return JSON only. Allowed intents: chat, memory_store, memory_recall, memory_forget, web_search. "
            "Choose chat for ordinary conversation, explanation, advice, diagnostics, or when the user does not ask "
            "to store/recall/forget memory or search the web. "
            "Choose memory_store only when the user asks ARIA to remember/store/save a durable fact or preference. "
            "Choose memory_recall only when the user asks what ARIA remembers or what the user previously said. "
            "Choose memory_forget only when the user asks ARIA to forget/delete its memory, not operational files/servers. "
            "Choose web_search only when the user asks to search/look up current web information or gives a concrete URL/source question. "
            "Active learning hints are weak learned signals from reviewed Qdrant memory. Use them only when relevant; "
            "they must never force an intent by themselves. "
            "You may override keyword signals when they are misleading. Do not invent unavailable intents. "
            "Output keys: intents, confidence, reason."
        )
        result = await self.decision_client.decide_json(
            operation="turn_intent_arbitration",
            system=system,
            payload={
                "message": clean_message,
                "language": str(language or ""),
                "keyword_signal": _keyword_signal_payload(keyword_decision),
                "available_intents": sorted(allowed),
                "active_learning_hints": active_learning_hints or [],
            },
            source=source,
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return TurnIntentArbitration(
                decision=fallback,
                source="keyword_router",
                reason=result.error or "arbiter_unavailable",
                usage=result.usage,
                error=result.error,
            )
        confidence = confidence_score(result.payload.get("confidence"))
        if confidence < 0.62:
            return TurnIntentArbitration(
                decision=fallback,
                source="keyword_router",
                reason="arbiter_low_confidence",
                confidence=confidence,
                usage=result.usage,
            )
        intents = _clean_intents(result.payload.get("intents") or result.payload.get("intent"), allowed=allowed | {"chat"})
        if any(intent not in allowed and intent != "chat" for intent in intents):
            intents = fallback_intents
        return TurnIntentArbitration(
            decision=RouterDecision(intents=intents, level=max(int(keyword_decision.level or 1), 2)),
            source="turn_intent_arbitration",
            reason=str(result.payload.get("reason", "") or "").strip()[:300],
            confidence=confidence,
            usage=result.usage,
        )
