from __future__ import annotations

import json
import re
from typing import Any

from aria.core.action_candidate_taxonomy import normalize_action_candidate_kind
from aria.core.agentic_prompt_flow import build_agentic_prompt_flow
from aria.core.planner_candidates import PlannerCandidate, PlannerInputSet, planner_candidate_to_dict
from aria.core.recipe_candidate_view import recipe_candidate_decision_fields
from aria.core.recipe_candidate_view import recipe_candidate_prompt_parts


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


def _result_payload(
    *,
    available: bool,
    used: bool,
    status: str,
    message: str,
    decision: dict[str, Any] | None = None,
    confidence: str = "",
    ask_user: bool = False,
    planner_source: str = "",
    planner_source_label: str = "",
    raw_response: str = "",
    planner_input: dict[str, Any] | None = None,
    agentic_flow: dict[str, Any] | None = None,
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
        "ask_user": bool(ask_user),
        "planner_source": str(planner_source or "").strip().lower(),
        "planner_source_label": str(planner_source_label or "").strip(),
        "raw_response": str(raw_response or "").strip(),
        "planner_input": dict(planner_input or {}),
        "agentic_flow": dict(agentic_flow or {}),
    }


def _planner_source_label(source: str, language: str = "") -> str:
    clean = str(source or "").strip().lower()
    if clean == "llm":
        return "LLM"
    if clean == "heuristic":
        return "Heuristik" if not str(language or "").strip().lower().startswith("en") else "Heuristic"
    return clean or ("Unbekannt" if not str(language or "").strip().lower().startswith("en") else "Unknown")


def _candidate_rows_for_prompt(candidates: list[PlannerCandidate], *, kind: str) -> list[str]:
    rows: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        role = str(candidate.metadata.get("candidate_role", "") or "").strip()
        label = f"{kind}/{candidate.candidate_type}/{candidate.candidate_id}"
        if role:
            label = f"{label} [{role}]"
        parts = [f"{index}. {label}"]
        if candidate.connection_kind:
            parts.append(f"connection_kind={candidate.connection_kind}")
        if candidate.title:
            parts.append(f"title={candidate.title}")
        if candidate.intent:
            parts.append(f"intent={candidate.intent}")
        if candidate.capability:
            parts.append(f"capability={candidate.capability}")
        if candidate.preview:
            parts.append(f"preview={candidate.preview}")
        if candidate.summary:
            parts.append(f"summary={candidate.summary}")
        if candidate.router_keywords:
            parts.append("keywords=" + ", ".join(candidate.router_keywords))
        if candidate.source:
            parts.append(f"source={candidate.source}")
        if candidate.score:
            parts.append(f"score={float(candidate.score):.1f}")
        if candidate.metadata:
            alias = str(candidate.metadata.get("alias", "") or "").strip()
            note = str(candidate.metadata.get("note", "") or "").strip()
            if alias:
                parts.append(f"alias={alias}")
            if note:
                parts.append(f"note={note}")
            parts.extend(recipe_candidate_prompt_parts(candidate.metadata))
        rows.append(" | ".join(parts))
    return rows


def _serialize_planner_input(input_set: PlannerInputSet) -> dict[str, Any]:
    return {
        "query": str(input_set.query or "").strip(),
        "language": str(input_set.language or "").strip(),
        "preferred_connection_kind": str(input_set.preferred_connection_kind or "").strip(),
        "connection_ref": str(input_set.connection_ref or "").strip(),
        "connection_candidates": [planner_candidate_to_dict(candidate) for candidate in list(input_set.connection_candidates or [])],
        "action_candidates": [planner_candidate_to_dict(candidate) for candidate in list(input_set.action_candidates or [])],
        "notes": [str(item or "").strip() for item in list(input_set.notes or []) if str(item or "").strip()],
        "session_context": {
            str(key or "").strip(): str(value or "").strip()
            for key, value in dict(input_set.session_context or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        },
    }


def _decision_payload(
    *,
    connection_candidate: PlannerCandidate,
    action_candidate: PlannerCandidate,
    reason: str,
    ask_user: bool,
    confidence: str,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "found": True,
        "target_kind": str(connection_candidate.connection_kind or "").strip().lower(),
        "target_ref": str(connection_candidate.candidate_id or "").strip(),
        "action_candidate_type": str(action_candidate.candidate_type or "").strip().lower(),
        "action_candidate_id": str(action_candidate.candidate_id or "").strip(),
        **recipe_candidate_decision_fields(action_candidate.metadata, prefix="action_"),
        "capability": str(action_candidate.capability or "").strip().lower(),
        "intent": str(action_candidate.intent or "").strip().lower(),
        "plan_mode": "single_candidate",
        "steps": [str(item or "").strip() for item in list(steps or [action_candidate.candidate_id]) if str(item or "").strip()],
        "reason": str(reason or "").strip(),
        "ask_user": bool(ask_user),
        "confidence": str(confidence or "").strip().lower(),
    }


async def debug_bounded_planner_decision(
    planner_input: PlannerInputSet,
    *,
    llm_client: Any | None,
    language: str = "",
) -> dict[str, Any]:
    clean_query = str(planner_input.query or "").strip()
    planner_payload = _serialize_planner_input(planner_input)
    agentic_flow = build_agentic_prompt_flow(planner_input)
    agentic_flow_payload = agentic_flow.as_dict()
    connection_candidates = list(planner_input.connection_candidates or [])
    action_candidates = list(planner_input.action_candidates or [])

    if not clean_query:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message="Bounded planner skipped: query is empty.",
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )
    if not connection_candidates or not action_candidates:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message="Bounded planner skipped: bounded connection or action candidates are missing.",
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )

    if llm_client is None:
        if len(connection_candidates) == 1 and len(action_candidates) == 1:
            decision = _decision_payload(
                connection_candidate=connection_candidates[0],
                action_candidate=action_candidates[0],
                reason="single bounded target and action candidate",
                ask_user=False,
                confidence="medium",
            )
            return _result_payload(
                available=True,
                used=False,
                status="ok",
                message="Bounded planner used the only bounded target/action pair.",
                decision=decision,
                confidence="medium",
                ask_user=False,
                planner_source="heuristic",
                planner_source_label=_planner_source_label("heuristic", language),
                planner_input=planner_payload,
                agentic_flow=agentic_flow_payload,
            )
        return _result_payload(
            available=False,
            used=False,
            status="warn",
            message="Bounded planner unavailable: no LLM client is configured.",
            planner_source="heuristic",
            planner_source_label=_planner_source_label("heuristic", language),
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )

    connection_by_key = {
        (str(candidate.connection_kind or "").strip().lower(), str(candidate.candidate_id or "").strip()): candidate
        for candidate in connection_candidates
    }
    action_by_key = {
        (str(candidate.candidate_type or "").strip().lower(), str(candidate.candidate_id or "").strip()): candidate
        for candidate in action_candidates
    }

    system_prompt = (
        "You are ARIA's bounded planner for live routing and execution planning. "
        "Choose exactly one bounded connection candidate and one bounded action candidate. "
        "Never invent targets, actions, templates, recipes or commands outside the provided bounded candidates. "
        "Prefer safe health/status actions for generic SSH host checks. "
        "Only use a direct command-style action when the user clearly requests a concrete command. "
        "Stored and learned recipe candidates use action_candidate_type='recipe' in the JSON contract. "
        "Legacy payloads may still send action_candidate_type='skill'; treat that as 'recipe'. "
        "Respond only as JSON in this format: "
        '{"target_kind":"<connection kind or empty>","target_ref":"<connection ref or empty>",'
        '"action_candidate_type":"<template|recipe or empty>","action_candidate_id":"<candidate id or empty>",'
        '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation","steps":["candidate_id", "..."]}.'
    )
    user_prompt = "\n".join(
        [
            f"User request: {clean_query}",
            f"Language: {str(language or planner_input.language or '').strip().lower() or '-'}",
            f"Preferred connection kind: {str(planner_input.preferred_connection_kind or '').strip().lower() or '-'}",
            f"Resolved connection ref hint: {str(planner_input.connection_ref or '').strip() or '-'}",
            "",
            *agentic_flow.as_prompt_lines(),
            (
                "Session context: "
                + "; ".join(f"{key}={value}" for key, value in dict(planner_input.session_context or {}).items())
                if dict(planner_input.session_context or {})
                else "Session context: -"
            ),
            "",
            "Bounded connection candidates:",
            *_candidate_rows_for_prompt(connection_candidates, kind="connection"),
            "",
            "Bounded action candidates:",
            *_candidate_rows_for_prompt(action_candidates, kind="action"),
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            source="bounded_planner_debug",
            operation="bounded_planner_debug",
        )
    except Exception as exc:
        return _result_payload(
            available=True,
            used=True,
            status="error",
            message=f"Bounded planner failed: {exc}",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )

    raw_response = str(getattr(response, "content", "") or "").strip()
    payload = _extract_json_object(raw_response) or {}
    target_kind = str(payload.get("target_kind", "") or "").strip().lower()
    target_ref = str(payload.get("target_ref", "") or "").strip()
    action_type = normalize_action_candidate_kind(str(payload.get("action_candidate_type", "") or "").strip().lower())
    action_id = str(payload.get("action_candidate_id", "") or "").strip()
    confidence = str(payload.get("confidence", "") or "").strip().lower()
    ask_user = bool(payload.get("ask_user", False))
    reason = str(payload.get("reason", "") or "").strip()
    steps = [str(item or "").strip() for item in list(payload.get("steps", []) or []) if str(item or "").strip()]

    if confidence not in {"high", "medium", "low"}:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message="Bounded planner returned invalid confidence.",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            raw_response=raw_response[:500],
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )

    connection_candidate = connection_by_key.get((target_kind, target_ref))
    action_candidate = action_by_key.get((action_type, action_id))
    if connection_candidate is None or action_candidate is None:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message="Bounded planner chose a target or action outside the bounded set.",
            confidence=confidence,
            ask_user=ask_user,
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            raw_response=raw_response[:500],
            planner_input=planner_payload,
            agentic_flow=agentic_flow_payload,
        )

    decision = _decision_payload(
        connection_candidate=connection_candidate,
        action_candidate=action_candidate,
        reason=reason or f"{target_kind}/{target_ref} + {action_type}/{action_id}",
        ask_user=ask_user or confidence == "low",
        confidence=confidence,
        steps=steps or [action_id],
    )
    return _result_payload(
        available=True,
        used=True,
        status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
        message=f"Bounded planner selected {target_kind}/{target_ref} + {action_type}/{action_id}.",
        decision=decision,
        confidence=confidence,
        ask_user=bool(decision["ask_user"]),
        planner_source="llm",
        planner_source_label=_planner_source_label("llm", language),
        raw_response=raw_response[:500],
        planner_input=planner_payload,
        agentic_flow=agentic_flow_payload,
    )
