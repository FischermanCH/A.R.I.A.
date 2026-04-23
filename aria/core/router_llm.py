from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RouterLLMBoundedCandidate:
    kind: str
    ref: str
    source: str = ""
    score: float = 0.0
    title: str = ""
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    supported_actions: list[str] = field(default_factory=list)
    target_hints: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return (str(self.kind or "").strip().lower(), str(self.ref or "").strip())


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _dedupe_items(values: list[str], *, limit: int = 8) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").strip().split())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(clean)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def _candidate_rows_for_prompt(candidates: list[RouterLLMBoundedCandidate]) -> list[str]:
    rows: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        details: list[str] = [
            f"{index}. {candidate.kind}/{candidate.ref}",
            f"source={candidate.source or '-'}",
        ]
        if candidate.score:
            details.append(f"score={candidate.score:.3f}")
        if candidate.title:
            details.append(f"title={candidate.title}")
        if candidate.description:
            details.append(f"description={candidate.description}")
        if candidate.aliases:
            details.append("aliases=" + ", ".join(candidate.aliases))
        if candidate.tags:
            details.append("tags=" + ", ".join(candidate.tags))
        if candidate.supported_actions:
            details.append("supported_actions=" + ", ".join(candidate.supported_actions))
        if candidate.target_hints:
            details.append("target_hints=" + ", ".join(candidate.target_hints))
        rows.append(" | ".join(details))
    return rows


def _default_capability(candidate: RouterLLMBoundedCandidate) -> str:
    return str((candidate.supported_actions or [""])[0] or "").strip()


def _result_payload(
    *,
    available: bool,
    used: bool,
    status: str,
    message: str,
    decision: dict[str, Any] | None = None,
    confidence: str = "",
    ask_user: bool = False,
    candidate_count: int = 0,
    raw_response: str = "",
) -> dict[str, Any]:
    return {
        "available": bool(available),
        "used": bool(used),
        "status": str(status or "warn").strip().lower() or "warn",
        "visual_status": str(status or "warn").strip().lower() or "warn",
        "message": str(message or "").strip(),
        "decision": dict(decision or {}),
        "confidence": str(confidence or "").strip().lower(),
        "ask_user": bool(ask_user),
        "candidate_count": int(candidate_count or 0),
        "raw_response": str(raw_response or "").strip(),
    }


async def debug_bounded_router_llm_decision(
    query: str,
    *,
    llm_client: Any | None,
    candidates: list[RouterLLMBoundedCandidate],
    language: str = "",
    deterministic_hint: str = "",
) -> dict[str, Any]:
    clean_query = str(query or "").strip()
    clean_language = str(language or "").strip().lower()
    clean_candidates = list(candidates or [])
    if llm_client is None:
        return _result_payload(
            available=False,
            used=False,
            status="warn",
            message="LLM router debug unavailable: no LLM client is configured.",
            candidate_count=len(clean_candidates),
        )
    if not clean_query:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message="LLM router debug skipped: query is empty.",
            candidate_count=len(clean_candidates),
        )
    if len(clean_candidates) < 2:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message="LLM router debug skipped: fewer than two bounded candidates are available.",
            candidate_count=len(clean_candidates),
        )

    valid_by_key = {candidate.key: candidate for candidate in clean_candidates}
    system_prompt = (
        "You are ARIA's bounded routing judge for admin/debug dry-runs. "
        "Choose only from the provided candidates. Never invent a candidate. "
        "Prefer a deterministic exact/alias match when it remains plausible. "
        "If the candidates are ambiguous or weak, set ask_user to true. "
        "Respond only as JSON in this format: "
        '{"kind":"<kind or empty>","ref":"<ref or empty>","capability":"<supported action or empty>",'
        '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}.'
    )
    user_prompt_lines = [
        f"User request: {clean_query}",
        f"Language: {clean_language or '-'}",
        f"Deterministic hint: {deterministic_hint or '-'}",
        "",
        "Bounded routing candidates:",
        *_candidate_rows_for_prompt(clean_candidates),
    ]
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "\n".join(user_prompt_lines)},
            ],
            source="routing_llm_debug",
            operation="routing_debug",
        )
    except Exception as exc:
        return _result_payload(
            available=True,
            used=True,
            status="error",
            message=f"LLM router debug failed: {exc}",
            candidate_count=len(clean_candidates),
        )

    raw_response = str(getattr(response, "content", "") or "").strip()
    payload = _extract_json_object(raw_response) or {}
    kind = str(payload.get("kind", "") or "").strip().lower()
    ref = str(payload.get("ref", "") or "").strip()
    capability = str(payload.get("capability", "") or "").strip()
    confidence = str(payload.get("confidence", "") or "").strip().lower()
    ask_user = bool(payload.get("ask_user", False))
    reason = str(payload.get("reason", "") or "").strip()

    if confidence not in {"high", "medium", "low"}:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message="LLM router debug returned invalid confidence.",
            candidate_count=len(clean_candidates),
            raw_response=raw_response[:500],
        )

    candidate = valid_by_key.get((kind, ref))
    if not candidate:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message="LLM router debug chose a candidate outside the bounded set.",
            confidence=confidence,
            ask_user=ask_user,
            candidate_count=len(clean_candidates),
            raw_response=raw_response[:500],
        )

    if capability and capability not in set(candidate.supported_actions):
        capability = _default_capability(candidate)
    elif not capability:
        capability = _default_capability(candidate)

    message = f"LLM router debug selected {candidate.kind}/{candidate.ref}."
    if ask_user or confidence == "low":
        message = "LLM router debug recommends asking the user before routing."

    return _result_payload(
        available=True,
        used=True,
        status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
        message=message,
        confidence=confidence,
        ask_user=ask_user,
        candidate_count=len(clean_candidates),
        raw_response=raw_response[:500],
        decision={
            "found": True,
            "kind": candidate.kind,
            "ref": candidate.ref,
            "capability": capability,
            "source": "router_llm_debug",
            "score": 0.0,
            "reason": reason or f"{candidate.kind}/{candidate.ref}",
        },
    )
