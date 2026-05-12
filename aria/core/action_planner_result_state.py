from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aria.core.i18n import I18NStore


_RESULT_STATE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _result_state_text(language: str | None, key: str, default: str = "") -> str:
    return _RESULT_STATE_I18N.t(language or "de", f"action_planner_result_state.{key}", default or key)


def execution_state(*, ask_user: bool = False, missing_input: str = "") -> str:
    if str(missing_input or "").strip():
        return "needs_input"
    if ask_user:
        return "needs_confirmation"
    return "ready"


def execution_state_label(state: str, language: str = "") -> str:
    clean = str(state or "").strip().lower()
    mapping = {
        "ready": _result_state_text(language, "ready", "Ready"),
        "needs_input": _result_state_text(language, "needs_input", "Needs input"),
        "needs_confirmation": _result_state_text(language, "needs_confirmation", "Needs confirmation"),
    }
    return mapping.get(clean, clean)


def planner_source_label(source: str, language: str = "") -> str:
    clean = str(source or "").strip().lower()
    mapping = {
        "heuristic": _result_state_text(language, "source_heuristic", "Heuristic"),
        "llm": "LLM",
        "catalog": _result_state_text(language, "source_catalog", "Catalog"),
    }
    return mapping.get(clean, clean)


def confidence_label(confidence: str, language: str = "") -> str:
    clean = str(confidence or "").strip().lower()
    mapping = {
        "high": _result_state_text(language, "confidence_high", "High"),
        "medium": _result_state_text(language, "confidence_medium", "Medium"),
        "low": _result_state_text(language, "confidence_low", "Low"),
    }
    return mapping.get(clean, clean)


def execution_state_rank(state: str) -> int:
    clean = str(state or "").strip().lower()
    return {
        "ready": 0,
        "needs_confirmation": 1,
        "needs_input": 2,
    }.get(clean, 9)


def target_context(kind: str, ref: str) -> str:
    clean_kind = str(kind or "").strip()
    clean_ref = str(ref or "").strip()
    if clean_kind and clean_ref:
        return f"{clean_kind}/{clean_ref}"
    return clean_ref or clean_kind


def sort_serialized_candidates(
    rows: list[dict[str, Any]],
    *,
    candidate_kind_priority: Callable[[str], int],
) -> list[dict[str, Any]]:
    return sorted(
        list(rows or []),
        key=lambda item: (
            execution_state_rank(str(item.get("execution_state", "") or "")),
            candidate_kind_priority(str(item.get("candidate_kind", "") or "")),
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("candidate_id", "") or ""),
        ),
    )


def result_payload(
    *,
    available: bool,
    used: bool,
    status: str,
    message: str,
    decision: dict[str, Any] | None = None,
    confidence: str = "",
    confidence_label: str = "",
    ask_user: bool = False,
    execution_state: str = "",
    execution_state_label: str = "",
    planner_source: str = "",
    planner_source_label: str = "",
    candidate_count: int = 0,
    candidates: list[dict[str, Any]] | None = None,
    target_context: str = "",
    target_reason: str = "",
    missing_input: str = "",
    missing_input_label: str = "",
    clarifying_question: str = "",
    example_prompt: str = "",
    raw_response: str = "",
) -> dict[str, Any]:
    clean_status = str(status or "warn").strip().lower() or "warn"
    return {
        "available": bool(available),
        "used": bool(used),
        "status": clean_status,
        "visual_status": clean_status,
        "message": str(message or "").strip(),
        "decision": dict(decision or {}),
        "confidence": str(confidence or "").strip().lower(),
        "confidence_label": str(confidence_label or "").strip(),
        "ask_user": bool(ask_user),
        "execution_state": str(execution_state or "").strip().lower(),
        "execution_state_label": str(execution_state_label or "").strip(),
        "planner_source": str(planner_source or "").strip().lower(),
        "planner_source_label": str(planner_source_label or "").strip(),
        "candidate_count": int(candidate_count or 0),
        "candidates": list(candidates or []),
        "target_context": str(target_context or "").strip(),
        "target_reason": str(target_reason or "").strip(),
        "missing_input": str(missing_input or "").strip(),
        "missing_input_label": str(missing_input_label or "").strip(),
        "clarifying_question": str(clarifying_question or "").strip(),
        "example_prompt": str(example_prompt or "").strip(),
        "raw_response": str(raw_response or "").strip(),
    }
