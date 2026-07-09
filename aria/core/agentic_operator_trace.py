from __future__ import annotations

from typing import Any


OPERATOR_TRACE_PREFIX = "Routing Debug: operator_trace"
_ROUTING_PREFIX = "Routing Debug: "
_PHASE_ORDER = ("understanding", "context", "draft", "policy", "runtime", "result", "summary", "learning")


def _field_map(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in str(line or "").split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        clean_key = "".join(ch for ch in key.strip().lower() if ch.isalnum() or ch in {"_", "-"})
        clean_value = value.strip()
        if clean_key and clean_value:
            fields[clean_key] = clean_value[:240]
    return fields


def _routing_label(line: str) -> str:
    text = str(line or "").strip()
    if not text.startswith(_ROUTING_PREFIX):
        return ""
    return text[len(_ROUTING_PREFIX) :].split(" ", 1)[0].strip()


def _clean_value(value: Any, *, limit: int = 240) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "-"
    return " ".join(text.split())[: max(1, int(limit or 1))]


def _append_fields(parts: list[str], fields: dict[str, str], keys: tuple[str, ...]) -> None:
    for key in keys:
        value = fields.get(key)
        if value:
            parts.append(f"{key}={_clean_value(value)}")


def _append_field_alias(parts: list[str], fields: dict[str, str], source_key: str, target_key: str) -> None:
    value = fields.get(source_key)
    if value:
        parts.append(f"{target_key}={_clean_value(value)}")


def _trace_priority(trace: str) -> int:
    fields = _field_map(trace)
    source = fields.get("source", "")
    boundary = fields.get("boundary", "")
    if source.endswith("_result_contract"):
        return 80
    if source.endswith("_timing") and fields.get("targets"):
        return 90
    if source.endswith("_preflight_result"):
        return 90
    if source == "context_packet":
        return 65
    if boundary in {"policy", "draft_policy", "runtime_aggregate"}:
        return 70
    if source == "runtime_outcome_frame":
        return 70
    if source == "answer_contract":
        return 65
    return 50


def operator_trace_line_from_debug_line(line: str) -> str:
    text = str(line or "").strip()
    if not text or text.startswith(OPERATOR_TRACE_PREFIX):
        return ""
    label = _routing_label(text)
    fields = _field_map(text)

    if label == "aria_turn_surface_action_arbitration":
        parts = [OPERATOR_TRACE_PREFIX, "phase=understanding", "source=aria_turn_surface_action_arbitration", "boundary=llm_decision"]
        _append_fields(parts, fields, ("intents", "needs_context", "surfaces", "actions", "answer_mode", "risk", "needs_confirmation", "confidence"))
        return " ".join(parts)

    if label == "context_ledger":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=context_ledger", "boundary=context_load"]
        _append_field_alias(parts, fields, "phase", "ledger_phase")
        _append_fields(parts, fields, ("directions", "requests", "collections", "skills", "sources", "arbiter_tokens", "routing_payload_bytes"))
        return " ".join(parts)

    if label == "context_packet":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=context_packet", "boundary=context_packet"]
        _append_fields(parts, fields, ("turn_plan_source", "requests", "loaded", "empty", "missing", "blocked", "evidence_policy", "contract_mode", "freshness_contract"))
        return " ".join(parts)

    if label == "answer_contract":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=answer_contract", "boundary=answer_contract"]
        _append_fields(parts, fields, ("kind", "status", "mode", "evidence_policy", "answer_mode", "source_count", "source_bound"))
        return " ".join(parts)

    if label == "pre_rag_action_gate":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=pre_rag_action_gate", "boundary=context_enrichment"]
        _append_fields(parts, fields, ("action_path", "capability", "kind", "requested_ref", "requested_refs", "reason", "fallback_risk"))
        return " ".join(parts)

    if label.endswith("_preflight_result"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=policy", f"source={label}", "boundary=policy"]
        _append_fields(parts, fields, ("allowed", "blocked", "targets", "refs", "action", "reason", "guardrail", "policy", "policy_action", "policy_reason"))
        return " ".join(parts)

    if label.endswith("_policy"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=policy", f"source={label}", "boundary=policy"]
        _append_fields(parts, fields, ("action", "reason", "policy", "policy_action", "policy_reason", "risk", "confidence"))
        return " ".join(parts)

    boundary = fields.get("boundary", "")
    if label and label.startswith("agentic_") and boundary in {"draft", "policy", "draft_policy", "runtime_execution"}:
        phase = "runtime" if boundary == "runtime_execution" else "policy" if boundary in {"policy", "draft_policy"} else "draft"
        parts = [OPERATOR_TRACE_PREFIX, f"phase={phase}", f"source={label}", f"boundary={boundary}"]
        _append_fields(parts, fields, ("ref", "kind", "capability", "operation", "agentic_source", "policy", "policy_action", "policy_reason", "review_issues"))
        return " ".join(parts)

    if label.endswith("_timing") and fields.get("targets") and fields.get("total_ms"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=runtime", f"source={label}", "boundary=runtime_aggregate"]
        _append_fields(parts, fields, ("targets", "allowed", "blocked", "preflight_ms", "execution_ms", "summary_ms", "remember_ms", "total_ms", "slowest_ref", "max_target_ms"))
        return " ".join(parts)

    if label.endswith("_result_contract"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", f"source={label}", "boundary=result_contract"]
        _append_fields(
            parts,
            fields,
            (
                "task_intent",
                "command_profile",
                "targets",
                "allowed",
                "blocked",
                "records",
                "ok",
                "attention",
                "error",
                "empty",
                "assumption",
                "notable",
                "confidence",
            ),
        )
        return " ".join(parts)

    if label == "runtime_outcome_frame":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=runtime_outcome_frame", "boundary=runtime_result"]
        _append_fields(parts, fields, ("surface", "kind", "capability", "task_intent", "targets", "affordances"))
        return " ".join(parts)

    if label.endswith("_summary_timing"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=summary", f"source={label}", "boundary=operator_summary"]
        _append_fields(parts, fields, ("records", "operator_ms", "llm_ms", "total_ms"))
        return " ".join(parts)

    if text.startswith("Learned Recipe Curator:"):
        fields = _field_map(text)
        parts = [OPERATOR_TRACE_PREFIX, "phase=learning", "source=learned_recipe_curator", "boundary=review_only_learning"]
        _append_fields(parts, fields, ("agentic_source", "policy", "confidence", "risk", "reason"))
        return " ".join(parts)

    return ""


def build_operator_trace_lines(detail_lines: list[str] | tuple[str, ...] | None) -> list[str]:
    by_phase: dict[str, str] = {}
    for line in list(detail_lines or []):
        trace = operator_trace_line_from_debug_line(str(line or ""))
        if not trace:
            continue
        fields = _field_map(trace)
        phase = fields.get("phase", "")
        if not phase:
            continue
        existing = by_phase.get(phase)
        if existing and _trace_priority(existing) >= _trace_priority(trace):
            continue
        by_phase[phase] = trace
    return [by_phase[phase] for phase in _PHASE_ORDER if phase in by_phase]


def append_operator_trace_detail_lines(detail_lines: list[str] | None) -> list[str]:
    lines = list(detail_lines or [])
    if any(str(line or "").strip().startswith(OPERATOR_TRACE_PREFIX) for line in lines):
        return lines
    trace_lines = build_operator_trace_lines(lines)
    if not trace_lines:
        return lines
    insert_at = len(lines)
    while insert_at > 0:
        line = str(lines[insert_at - 1] or "").strip()
        if (
            line.startswith("Quelle:")
            or (line.startswith("Ausgef") and " via " in line)
            or line.startswith("Pfad:")
            or line.startswith("Suche:")
        ):
            insert_at -= 1
            continue
        break
    return [*lines[:insert_at], *trace_lines, *lines[insert_at:]]
