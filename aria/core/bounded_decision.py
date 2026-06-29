from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from aria.core.text_utils import extract_json_object


@dataclass(frozen=True)
class BoundedDecisionResult:
    content: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    diagnostics: dict[str, int] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


def llm_response_usage(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage", None)
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def confidence_score(value: Any) -> float:
    raw = str(value or "").strip().lower()
    if raw in {"high", "hoch"}:
        return 0.82
    if raw in {"medium", "mittel"}:
        return 0.66
    if raw in {"low", "niedrig"}:
        return 0.34
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def bounded_decision_diagnostics(*, system: str, payload: dict[str, Any]) -> dict[str, int]:
    payload_json = encode_bounded_decision_payload(payload)
    return {
        "system_chars": len(str(system or "")),
        "payload_bytes": len(payload_json.encode("utf-8")),
        "payload_keys": len(payload),
    }


def encode_bounded_decision_payload(payload: dict[str, Any]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return "{}"


class BoundedDecisionClient:
    def __init__(self, llm_client: Any | None):
        self.llm_client = llm_client

    async def decide_json(
        self,
        *,
        operation: str,
        system: str,
        payload: dict[str, Any],
        source: str = "",
        user_id: str = "",
        request_id: str = "",
    ) -> BoundedDecisionResult:
        diagnostics = bounded_decision_diagnostics(system=system, payload=payload)
        if self.llm_client is None:
            return BoundedDecisionResult(diagnostics=diagnostics, error="no_llm_client")
        try:
            response = await self.llm_client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": encode_bounded_decision_payload(payload)},
                ],
                operation=operation,
                source=source,
                user_id=user_id,
                request_id=request_id,
            )
        except Exception:
            return BoundedDecisionResult(diagnostics=diagnostics, error="llm_error")
        content = str(getattr(response, "content", "") or "").strip()
        parsed = extract_json_object(content)
        if not isinstance(parsed, dict):
            return BoundedDecisionResult(
                content=content,
                usage=llm_response_usage(response),
                diagnostics=diagnostics,
                error="empty_or_invalid_response",
            )
        return BoundedDecisionResult(content=content, payload=parsed, usage=llm_response_usage(response), diagnostics=diagnostics)

    async def complete_text(
        self,
        *,
        operation: str,
        system: str,
        payload: dict[str, Any],
        source: str = "",
        user_id: str = "",
        request_id: str = "",
    ) -> BoundedDecisionResult:
        diagnostics = bounded_decision_diagnostics(system=system, payload=payload)
        if self.llm_client is None:
            return BoundedDecisionResult(diagnostics=diagnostics, error="no_llm_client")
        try:
            response = await self.llm_client.chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": encode_bounded_decision_payload(payload)},
                ],
                operation=operation,
                source=source,
                user_id=user_id,
                request_id=request_id,
            )
        except Exception:
            return BoundedDecisionResult(diagnostics=diagnostics, error="llm_error")
        return BoundedDecisionResult(
            content=str(getattr(response, "content", "") or "").strip(),
            usage=llm_response_usage(response),
            diagnostics=diagnostics,
        )
