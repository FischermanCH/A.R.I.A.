from __future__ import annotations

from typing import Any


OPERATOR_TRACE_PREFIX = "Routing Debug: operator_trace"
_ROUTING_PREFIX = "Routing Debug: "
_PHASE_ORDER = ("understanding", "context", "draft", "policy", "runtime", "result", "summary", "learning")
_EXECUTED_VIA_PREFIX = "Ausgef\u00fchrt via "
_EXECUTION_DETAIL_PREFIXES = (
    (f"{_EXECUTED_VIA_PREFIX}SSH-Profil `", "ssh"),
    (f"{_EXECUTED_VIA_PREFIX}HTTP API-Profil `", "http_api"),
    (f"{_EXECUTED_VIA_PREFIX}Discord-Profil `", "discord"),
)


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


def _append_aria_turn_action_contract_traces(fields: dict[str, str]) -> list[str]:
    actions = fields.get("actions", "")
    if not actions:
        return []

    draft = [OPERATOR_TRACE_PREFIX, "phase=draft", "source=aria_turn_surface_action_arbitration", "boundary=draft"]
    _append_fields(draft, fields, ("actions", "answer_mode", "risk", "needs_confirmation", "confidence"))

    policy_action = "confirm" if fields.get("needs_confirmation", "").lower() == "true" else "allow"
    policy = [
        OPERATOR_TRACE_PREFIX,
        "phase=policy",
        "source=aria_turn_surface_action_arbitration",
        "boundary=policy",
        f"action={policy_action}",
    ]
    _append_field_alias(policy, fields, "risk", "reason")
    _append_fields(policy, fields, ("risk", "needs_confirmation", "confidence"))
    return [" ".join(draft), " ".join(policy)]


def _execution_detail_from_line(text: str) -> tuple[str, str]:
    for prefix, mapped_kind in _EXECUTION_DETAIL_PREFIXES:
        if text.startswith(prefix):
            ref = ""
            if "`" in text:
                parts = text.split("`", 2)
                if len(parts) >= 2:
                    ref = parts[1].strip()
            return mapped_kind, ref
    return "", ""


def _execution_trace_from_details(details: list[tuple[str, str]]) -> str:
    clean = [(kind, ref) for kind, ref in details if kind]
    if not clean:
        return ""
    kinds = {kind for kind, _ref in clean}
    kind = clean[0][0] if len(kinds) == 1 else "mixed"
    first_ref = next((ref for _kind, ref in clean if ref), "")
    trace = [
        OPERATOR_TRACE_PREFIX,
        "phase=runtime",
        "source=execution_detail",
        "boundary=runtime_execution",
        "next_step=executed",
        f"kind={kind}",
    ]
    if len(clean) > 1:
        trace.append(f"targets={len(clean)}")
        if first_ref:
            trace.append(f"first_ref={_clean_value(first_ref)}")
    elif first_ref:
        trace.append(f"ref={_clean_value(first_ref)}")
    return " ".join(trace)


def _execution_trace_from_detail_line(text: str) -> str:
    kind, ref = _execution_detail_from_line(text)
    if not kind:
        return ""
    return _execution_trace_from_details([(kind, ref)])


def _is_execution_detail_line(text: str) -> bool:
    kind, _ref = _execution_detail_from_line(text)
    return bool(kind)


def _is_trailing_timing_line(text: str) -> bool:
    label = _routing_label(text)
    return label.startswith(("web_", "browser_"))


def _trace_priority(trace: str) -> int:
    fields = _field_map(trace)
    source = fields.get("source", "")
    boundary = fields.get("boundary", "")
    if source == "agentic_policy_decision":
        return 85
    if source.endswith("_result_contract"):
        return 80
    if source.endswith("_timing") and fields.get("targets"):
        return 90
    if source.endswith("_preflight_result"):
        return 90
    if source == "context_packet":
        return 65
    if source == "turn_decision_owner":
        return 90
    if source == "evidence_contract":
        return 68
    if source == "answerability":
        return 72
    if source == "stabilization_gate_final_answer_guard":
        return 74
    if boundary in {"policy", "draft_policy", "runtime_aggregate"}:
        return 70
    if source == "runtime_outcome_frame":
        return 70
    if source == "answer_contract":
        return 65
    return 50


def operator_trace_lines_from_debug_line(line: str) -> list[str]:
    text = str(line or "").strip()
    if not text or text.startswith(OPERATOR_TRACE_PREFIX):
        return []
    execution_trace = _execution_trace_from_detail_line(text)
    if execution_trace:
        return [execution_trace]
    label = _routing_label(text)
    fields = _field_map(text)

    if label == "aria_turn_surface_action_arbitration":
        parts = [OPERATOR_TRACE_PREFIX, "phase=understanding", "source=aria_turn_surface_action_arbitration", "boundary=llm_decision"]
        _append_fields(parts, fields, ("intents", "needs_context", "surfaces", "actions", "answer_mode", "risk", "needs_confirmation", "confidence"))
        return [" ".join(parts), *_append_aria_turn_action_contract_traces(fields)]

    if label == "context_ledger":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=context_ledger", "boundary=context_load"]
        _append_field_alias(parts, fields, "phase", "ledger_phase")
        _append_fields(parts, fields, ("directions", "requests", "collections", "skills", "sources", "arbiter_tokens", "routing_payload_bytes"))
        return [" ".join(parts)]

    if label == "context_packet":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=context_packet", "boundary=context_packet"]
        _append_fields(parts, fields, ("turn_plan_source", "requests", "loaded", "empty", "missing", "blocked", "evidence_policy", "contract_mode", "freshness_contract"))
        return [" ".join(parts)]

    if label == "turn_decision_owner":
        parts = [OPERATOR_TRACE_PREFIX, "phase=understanding", "source=turn_decision_owner", "boundary=decision_owner"]
        _append_fields(parts, fields, ("owner", "surfaces", "actions", "answer_mode", "confidence", "legacy_fallback_allowed"))
        return [" ".join(parts)]

    if label == "evidence_contract":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=evidence_contract", "boundary=evidence_contract"]
        _append_fields(parts, fields, ("surface", "authority", "completeness", "fields", "rows", "sources", "answer_permissions", "claim_limits"))
        return [" ".join(parts)]

    if label == "answer_contract":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=answer_contract", "boundary=answer_contract"]
        _append_fields(parts, fields, ("kind", "status", "mode", "evidence_policy", "answer_mode", "source_count", "source_bound"))
        return [" ".join(parts)]

    if label == "answerability":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=answerability", "boundary=answerability"]
        _append_fields(parts, fields, ("surface", "completeness", "authority", "field", "decision", "status", "claim_limits"))
        return [" ".join(parts)]

    if label == "stabilization_gate_final_answer_guard":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=stabilization_gate_final_answer_guard", "boundary=answerability_guard"]
        _append_fields(parts, fields, ("status", "reason", "answer_permissions", "claim_limits"))
        return [" ".join(parts)]

    if label == "pre_rag_action_gate":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=pre_rag_action_gate", "boundary=context_enrichment"]
        _append_fields(parts, fields, ("action_path", "capability", "kind", "requested_ref", "requested_refs", "reason", "fallback_risk"))
        return [" ".join(parts)]

    if label == "meta_catalog_contract":
        parts = [OPERATOR_TRACE_PREFIX, "phase=context", "source=meta_catalog_contract", "boundary=context_enrichment"]
        _append_field_alias(parts, fields, "phase", "contract_phase")
        _append_fields(parts, fields, ("legacy_semantics", "reason"))
        return [" ".join(parts)]

    if label == "agentic_action_contract":
        parts = [OPERATOR_TRACE_PREFIX, "phase=draft", "source=agentic_action_contract", "boundary=draft"]
        _append_fields(parts, fields, ("candidate_kind", "candidate_id", "candidate_role", "capability", "kind", "ref", "execution_state"))
        return [" ".join(parts)]

    if label == "agentic_policy_decision":
        parts = [OPERATOR_TRACE_PREFIX, "phase=policy", "source=agentic_policy_decision", "boundary=policy"]
        _append_fields(parts, fields, ("action", "reason", "policy", "guardrail", "capability", "kind", "ref"))
        return [" ".join(parts)]

    if label == "agentic_execution_decision":
        parts = [OPERATOR_TRACE_PREFIX, "phase=runtime", "source=agentic_execution_decision", "boundary=runtime_execution"]
        _append_fields(parts, fields, ("next_step", "capability", "kind", "ref", "operation"))
        return [" ".join(parts)]

    if label.endswith("_preflight_result"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=policy", f"source={label}", "boundary=policy"]
        _append_fields(parts, fields, ("allowed", "blocked", "targets", "refs", "action", "reason", "guardrail", "policy", "policy_action", "policy_reason"))
        return [" ".join(parts)]

    if label.endswith("_policy"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=policy", f"source={label}", "boundary=policy"]
        _append_fields(parts, fields, ("action", "reason", "policy", "policy_action", "policy_reason", "risk", "confidence"))
        return [" ".join(parts)]

    boundary = fields.get("boundary", "")
    if label and label.startswith("agentic_") and boundary in {"draft", "policy", "draft_policy", "runtime_execution"}:
        phase = "runtime" if boundary == "runtime_execution" else "policy" if boundary in {"policy", "draft_policy"} else "draft"
        parts = [OPERATOR_TRACE_PREFIX, f"phase={phase}", f"source={label}", f"boundary={boundary}"]
        _append_fields(parts, fields, ("ref", "kind", "capability", "operation", "agentic_source", "policy", "policy_action", "policy_reason", "review_issues"))
        return [" ".join(parts)]

    if label.endswith("_timing") and fields.get("targets") and fields.get("total_ms"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=runtime", f"source={label}", "boundary=runtime_aggregate"]
        _append_fields(parts, fields, ("targets", "allowed", "blocked", "preflight_ms", "execution_ms", "summary_ms", "remember_ms", "total_ms", "slowest_ref", "max_target_ms"))
        return [" ".join(parts)]

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
        return [" ".join(parts)]

    if label == "runtime_outcome_frame":
        parts = [OPERATOR_TRACE_PREFIX, "phase=result", "source=runtime_outcome_frame", "boundary=runtime_result"]
        _append_fields(parts, fields, ("surface", "kind", "capability", "task_intent", "targets", "affordances"))
        return [" ".join(parts)]

    if label.endswith("_summary_timing"):
        parts = [OPERATOR_TRACE_PREFIX, "phase=summary", f"source={label}", "boundary=operator_summary"]
        _append_fields(parts, fields, ("records", "operator_ms", "llm_ms", "total_ms"))
        return [" ".join(parts)]

    if text.startswith("Learned Recipe Curator:"):
        fields = _field_map(text)
        parts = [OPERATOR_TRACE_PREFIX, "phase=learning", "source=learned_recipe_curator", "boundary=review_only_learning"]
        _append_fields(parts, fields, ("agentic_source", "policy", "confidence", "risk", "reason"))
        return [" ".join(parts)]

    return []


def operator_trace_line_from_debug_line(line: str) -> str:
    traces = operator_trace_lines_from_debug_line(line)
    return traces[0] if traces else ""


def build_operator_trace_lines(detail_lines: list[str] | tuple[str, ...] | None) -> list[str]:
    by_phase: dict[str, str] = {}
    execution_details: list[tuple[str, str]] = []
    for line in list(detail_lines or []):
        text = str(line or "")
        execution_detail = _execution_detail_from_line(text.strip())
        if execution_detail[0]:
            execution_details.append(execution_detail)
            continue
        for trace in operator_trace_lines_from_debug_line(text):
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
    execution_trace = _execution_trace_from_details(execution_details)
    if execution_trace:
        existing = by_phase.get("runtime")
        if not existing or _trace_priority(existing) < _trace_priority(execution_trace):
            by_phase["runtime"] = execution_trace
    return [by_phase[phase] for phase in _PHASE_ORDER if phase in by_phase]


def append_operator_trace_detail_lines(detail_lines: list[str] | None, *, allow_execution_only: bool = False) -> list[str]:
    lines = list(detail_lines or [])
    if any(str(line or "").strip().startswith(OPERATOR_TRACE_PREFIX) for line in lines):
        return lines
    has_routing_line = any(str(line or "").strip().startswith(_ROUTING_PREFIX) for line in lines)
    has_execution_detail = any(_is_execution_detail_line(str(line or "").strip()) for line in lines)
    if not has_routing_line and not (allow_execution_only and has_execution_detail):
        return lines
    trace_lines = build_operator_trace_lines(lines)
    if not trace_lines:
        return lines
    insert_at = len(lines)
    while insert_at > 0:
        line = str(lines[insert_at - 1] or "").strip()
        if (
            line.startswith("Quelle:")
            or _is_execution_detail_line(line)
            or _is_trailing_timing_line(line)
            or line.startswith("Pfad:")
            or line.startswith("Suche:")
        ):
            insert_at -= 1
            continue
        break
    return [*lines[:insert_at], *trace_lines, *lines[insert_at:]]
