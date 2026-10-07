from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.modules.platform_primitives.bounded_decision import BoundedDecisionClient, confidence_score


WEB_MODES = {"auto", "main", "web"}


@dataclass(frozen=True, slots=True)
class WebDispatchDecision:
    requested_mode: str
    effective_mode: str
    reason: str
    deterministic: bool = True
    usage: dict[str, int] = field(default_factory=dict)


def normalize_web_mode(value: str | None) -> str:
    clean = str(value or "auto").strip().lower()
    return clean if clean in WEB_MODES else "auto"


def decide_web_dispatch(message: str, requested_mode: str = "auto") -> WebDispatchDecision:
    mode = normalize_web_mode(requested_mode)
    text = str(message or "").strip()
    if mode == "web":
        if text.startswith("/"):
            return WebDispatchDecision(mode, "main", "explicit_command_protocol")
        return WebDispatchDecision(mode, "web", "explicit_web")
    if mode == "main":
        return WebDispatchDecision(mode, "main", "explicit_main")
    if not text:
        return WebDispatchDecision(mode, "main", "empty_message")
    if text.startswith("/"):
        return WebDispatchDecision(mode, "main", "explicit_command_protocol")
    return WebDispatchDecision(mode, "agent", "semantic_dispatch_required", deterministic=False)


async def decide_auto_web_dispatch(
    message: str,
    *,
    llm_client: Any | None,
    web_ready: bool,
    language: str = "",
    recent_history: list[dict[str, object]] | None = None,
    source: str = "web_chat",
    user_id: str = "",
    request_id: str = "",
) -> WebDispatchDecision:
    if not web_ready:
        return WebDispatchDecision("auto", "main", "web_not_ready", deterministic=False)
    prior_web_turns = [
        {"role": role, "content": content[:1200]}
        for role, content in select_web_followup_history(recent_history, limit=4)
    ]
    result = await BoundedDecisionClient(llm_client).decide_json(
        operation="native_web_dispatch_decision",
        system=(
            "Choose whether the current user turn belongs to ARIA's Main-LLM or Web-LLM by meaning and authority, not keywords. "
            "Use web for public information that requires internet evidence, current external facts, public URLs, or a follow-up to the "
            "provided prior web turns. Use main for local/private ARIA context, Memory, notes, documents, configured connections, runtime "
            "actions, general knowledge that does not require web evidence, or ambiguity. Return exactly one JSON object matching the schema. "
            "Never invent local access, web evidence, actions or context."
        ),
        payload={
            "current_user_message": str(message or "").strip(),
            "language": str(language or ""),
            "web_llm_ready": bool(web_ready),
            "prior_web_turns": prior_web_turns,
            "allowed_routes": ["main", "web"],
            "requested_output_schema": {
                "route": "main|web",
                "confidence": "0..1",
                "reason": "concise semantic authority reason",
            },
        },
        source=source,
        user_id=user_id,
        request_id=request_id,
    )
    usage = {key: int(result.usage.get(key, 0) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
    route = str(result.payload.get("route") or "").strip().lower()
    if not result.ok or route not in {"main", "web"} or confidence_score(result.payload.get("confidence")) < 0.62:
        return WebDispatchDecision("auto", "main", "semantic_dispatch_failed_closed", deterministic=False, usage=usage)
    return WebDispatchDecision("auto", route, "semantic_dispatch", deterministic=False, usage=usage)


def select_web_followup_history(history: list[dict[str, object]] | None, *, limit: int = 4) -> tuple[tuple[str, str], ...]:
    rows = [row for row in list(history or []) if isinstance(row, dict)]
    selected: list[tuple[str, str]] = []
    for index, row in enumerate(rows):
        if str(row.get("role", "") or "").strip().lower() != "assistant":
            continue
        if not str(row.get("badge_intent", "") or "").strip().lower().startswith("web_search"):
            continue
        if index > 0 and str(rows[index - 1].get("role", "") or "").strip().lower() == "user":
            selected.append(
                ("user", str(rows[index - 1].get("text", rows[index - 1].get("content", "")) or ""))
            )
        selected.append(("assistant", str(row.get("text", row.get("content", "")) or "")))
    return tuple(selected[-max(1, min(int(limit or 4), 8)):])
