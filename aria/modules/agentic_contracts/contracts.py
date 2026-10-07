from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ROUTING_PREFIX = "Routing Debug: "


def routing_label(line: str) -> str:
    text = str(line or "").strip()
    if not text.startswith(ROUTING_PREFIX):
        return ""
    return text[len(ROUTING_PREFIX) :].split(" ", 1)[0].strip()


def routing_fields(line: str) -> dict[str, str]:
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


def clean_contract_value(value: Any, *, limit: int = 180) -> str:
    text = str(value if value is not None else "").strip()
    if not text:
        return "-"
    return "_".join(text.split())[: max(1, int(limit or 1))]


def loaded_source_count(loaded: str) -> int:
    total = 0
    for item in str(loaded or "").split(","):
        if ":" not in item:
            continue
        value = item.rsplit(":", 1)[-1].strip()
        try:
            total += max(0, int(value or 0))
        except ValueError:
            continue
    return total


def first_debug_line(lines: list[str], labels: set[str]) -> tuple[str, dict[str, str]]:
    for line in lines:
        label = routing_label(line)
        if label in labels:
            return label, routing_fields(line)
    return "", {}


def line_exists(lines: list[str], label: str) -> bool:
    return any(routing_label(line) == label for line in lines)


def first_line_fields(lines: list[str], label: str) -> dict[str, str]:
    _label, fields = first_debug_line(lines, {label})
    return fields


def evidence_permission(authority: str, completeness: str) -> tuple[str, str]:
    clean_authority = str(authority or "").strip().lower()
    clean_completeness = str(completeness or "").strip().lower()
    if clean_authority in {"config", "runtime", "runtime_records", "required_source", "preferred_source"}:
        return "bound_claims", "loaded_fields_only"
    if clean_authority in {"source_bound", "strong_secondary"}:
        return "source_bound_claims", "loaded_sources_only"
    if clean_completeness in {"candidate_only", "priority_sample"} or clean_authority == "candidate":
        return "candidate_claims_only", "no_completeness_claim"
    return "bounded_claims", "loaded_context_only"


@dataclass(frozen=True)
class TurnDecisionContract:
    owner: str
    boundary: str
    surfaces: str = "-"
    actions: str = "-"
    answer_mode: str = "-"
    confidence: str = "-"
    legacy_fallback_allowed: bool = False

    def to_debug_line(self) -> str:
        return (
            "Routing Debug: turn_decision_owner "
            f"owner={clean_contract_value(self.owner)} "
            f"boundary={clean_contract_value(self.boundary)} "
            f"surfaces={clean_contract_value(self.surfaces)} "
            f"actions={clean_contract_value(self.actions)} "
            f"answer_mode={clean_contract_value(self.answer_mode)} "
            f"confidence={clean_contract_value(self.confidence)} "
            f"legacy_fallback_allowed={str(bool(self.legacy_fallback_allowed)).lower()}"
        )


@dataclass(frozen=True)
class EvidenceContract:
    surface: str
    authority: str
    completeness: str
    fields: str = "-"
    rows: str = "-"
    sources: str = "-"
    answer_permissions: str = ""
    claim_limits: str = ""

    def normalized(self) -> "EvidenceContract":
        permissions = self.answer_permissions
        limits = self.claim_limits
        if not permissions or not limits:
            permissions, limits = evidence_permission(self.authority, self.completeness)
        if str(self.authority or "").strip().lower() == "runtime_records" and not self.claim_limits:
            limits = "observed_runtime_fields_only"
        return EvidenceContract(
            surface=self.surface,
            authority=self.authority,
            completeness=self.completeness,
            fields=self.fields,
            rows=self.rows,
            sources=self.sources,
            answer_permissions=permissions,
            claim_limits=limits,
        )

    def to_debug_line(self) -> str:
        contract = self.normalized()
        return (
            "Routing Debug: evidence_contract "
            f"surface={clean_contract_value(contract.surface)} "
            f"authority={clean_contract_value(contract.authority)} "
            f"completeness={clean_contract_value(contract.completeness)} "
            f"fields={clean_contract_value(contract.fields)} "
            f"rows={clean_contract_value(contract.rows)} "
            f"sources={clean_contract_value(contract.sources)} "
            f"answer_permissions={clean_contract_value(contract.answer_permissions)} "
            f"claim_limits={clean_contract_value(contract.claim_limits)}"
        )


@dataclass(frozen=True)
class AnswerabilityContract:
    surface: str
    completeness: str
    authority: str
    field: str = "-"
    decision: str = "-"
    status: str = "-"
    claim_limits: str = ""

    def to_debug_line(self) -> str:
        base = (
            "Routing Debug: answerability "
            f"surface={clean_contract_value(self.surface)} "
            f"completeness={clean_contract_value(self.completeness)} "
            f"authority={clean_contract_value(self.authority)} "
            f"field={clean_contract_value(self.field)} "
            f"decision={clean_contract_value(self.decision)} "
            f"status={clean_contract_value(self.status)}"
        )
        if self.claim_limits:
            return f"{base} claim_limits={clean_contract_value(self.claim_limits)}"
        return base


def derive_turn_decision_contract(lines: list[str]) -> TurnDecisionContract | None:
    label, fields = first_debug_line(lines, {"aria_turn_surface_action_arbitration"})
    if label:
        return TurnDecisionContract(
            owner=fields.get("source") or "aria_turn_arbitration",
            boundary="llm_decision",
            surfaces=fields.get("surfaces") or fields.get("context_directions") or "-",
            actions=fields.get("actions") or "-",
            answer_mode=fields.get("answer_mode") or "-",
            confidence=fields.get("confidence") or "-",
        )
    if any(routing_label(line) == "evidence_bundle" and " reused " in f" {line} " for line in lines):
        return TurnDecisionContract(
            owner="evidence_bundle_followup",
            boundary="last_turn_evidence",
            surfaces="connections",
            actions="-",
            answer_mode="direct_answer",
            confidence="1.0",
        )
    label, _fields = first_debug_line(lines, {"runtime_outcome_followup"})
    if label:
        return TurnDecisionContract(
            owner="runtime_outcome_followup",
            boundary="last_runtime_outcome",
            surfaces="connections",
            actions="-",
            answer_mode="direct_answer",
            confidence="1.0",
        )
    return None


def derive_evidence_contract(lines: list[str]) -> EvidenceContract | None:
    for line in lines:
        if routing_label(line) != "evidence_bundle":
            continue
        fields = routing_fields(line)
        return EvidenceContract(
            surface=fields.get("surface") or "connections",
            authority=fields.get("authority") or "-",
            completeness=fields.get("completeness") or "-",
            fields=fields.get("fields") or "-",
            rows=fields.get("rows") or "-",
            sources="-",
        )

    label, fields = first_debug_line(lines, {"runtime_outcome_evidence_contract"})
    if label:
        return EvidenceContract(
            surface=fields.get("surface") or "runtime_outcome",
            authority=fields.get("authority") or "runtime_records",
            completeness=fields.get("completeness") or "records",
            fields=fields.get("task_intent") or "observed_runtime_fields",
            rows=fields.get("records") or "-",
            sources="-",
            answer_permissions="bound_claims",
            claim_limits=fields.get("claim_limits") or "observed_runtime_fields_only",
        )

    label, fields = first_debug_line(lines, {"context_packet"})
    if label:
        authority = "source_bound" if fields.get("evidence_policy") == "source_bound" else "loaded_context"
        return EvidenceContract(
            surface="mixed",
            authority=authority,
            completeness="loaded_context",
            fields="-",
            rows="-",
            sources=str(loaded_source_count(fields.get("loaded", ""))),
        )
    return None


def evidence_contract_from_debug_lines(lines: list[str]) -> EvidenceContract | None:
    label, fields = first_debug_line(lines, {"evidence_contract"})
    if label:
        return EvidenceContract(
            surface=fields.get("surface") or "-",
            authority=fields.get("authority") or "-",
            completeness=fields.get("completeness") or "-",
            fields=fields.get("fields") or "-",
            rows=fields.get("rows") or "-",
            sources=fields.get("sources") or "-",
            answer_permissions=fields.get("answer_permissions") or "",
            claim_limits=fields.get("claim_limits") or "",
        ).normalized()
    contract = derive_evidence_contract(lines)
    return contract.normalized() if contract is not None else None


def derive_answerability_contract(lines: list[str]) -> AnswerabilityContract | None:
    label, fields = first_debug_line(lines, {"runtime_outcome_evidence_contract"})
    if label:
        return AnswerabilityContract(
            surface=fields.get("surface") or "runtime_outcome",
            completeness=fields.get("completeness") or "records",
            authority=fields.get("authority") or "runtime_records",
            field=fields.get("task_intent") or "observed_runtime_fields",
            decision="answer_from_runtime_outcome",
            status="found",
            claim_limits=fields.get("claim_limits") or "observed_runtime_fields_only",
        )

    label, fields = first_debug_line(lines, {"answer_contract"})
    if not label:
        return None
    status = clean_contract_value(fields.get("status"))
    decision = "answer_from_evidence_contract" if status == "found" else "fail_closed_or_empty"
    authority = "source_bound" if fields.get("source_bound") == "true" else "loaded_context"
    return AnswerabilityContract(
        surface=fields.get("kind") or "-",
        completeness="-",
        authority=authority,
        field="-",
        decision=decision,
        status=status,
    )
