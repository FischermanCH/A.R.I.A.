from __future__ import annotations

import re
from dataclasses import dataclass

from aria.core.agentic_contracts import derive_answerability_contract
from aria.core.agentic_contracts import derive_evidence_contract
from aria.core.agentic_contracts import derive_turn_decision_contract
from aria.core.agentic_contracts import evidence_contract_from_debug_lines
from aria.core.agentic_contracts import line_exists



@dataclass(frozen=True)
class StabilizationPrompt:
    prompt_id: str
    family: str
    prompt: str
    expected_surface: str
    expected_contract: str


STABILIZATION_PROMPT_MATRIX: tuple[StabilizationPrompt, ...] = (
    StabilizationPrompt(
        prompt_id="server_status_all",
        family="connections_runtime",
        prompt="Zeige mir den Status meiner Server.",
        expected_surface="connections",
        expected_contract="runtime_full_kind",
    ),
    StabilizationPrompt(
        prompt_id="ssh_inventory_host_ip",
        family="connections_inventory",
        prompt="Gib mir eine Uebersicht meiner SSH-Server mit Hostname und IP.",
        expected_surface="connections",
        expected_contract="config_inventory_full_kind",
    ),
    StabilizationPrompt(
        prompt_id="ssh_inventory_dev_followup",
        family="connections_inventory",
        prompt="Welche IP/Hostnamen haben meine dev-server?",
        expected_surface="connections",
        expected_contract="last_turn_evidence_followup",
    ),
    StabilizationPrompt(
        prompt_id="syncthing_connections",
        family="connections_inventory",
        prompt="Welche Verbindungen kennst du fuer Syncthing?",
        expected_surface="connections",
        expected_contract="connection_inventory",
    ),
    StabilizationPrompt(
        prompt_id="dns_runtime_scope",
        family="connections_runtime",
        prompt="Wie lange ist mein DNS Server schon online?",
        expected_surface="connections",
        expected_contract="bounded_runtime_scope",
    ),
    StabilizationPrompt(
        prompt_id="active_skills",
        family="capability_inventory",
        prompt="Welche Skills sind aktuell aktiv?",
        expected_surface="capabilities",
        expected_contract="capability_inventory",
    ),
    StabilizationPrompt(
        prompt_id="recipe_templates",
        family="recipes",
        prompt="Welche Rezepte/Templates kennst du?",
        expected_surface="recipes",
        expected_contract="recipe_inventory",
    ),
    StabilizationPrompt(
        prompt_id="docker_compose_current",
        family="web_currentness",
        prompt="Was ist die aktuelle Docker Compose Version?",
        expected_surface="web",
        expected_contract="source_authority",
    ),
    StabilizationPrompt(
        prompt_id="broad_server_knowledge",
        family="memory_connections",
        prompt="Was weisst du noch ueber meine Server?",
        expected_surface="mixed",
        expected_contract="bounded_loaded_context",
    ),
    StabilizationPrompt(
        prompt_id="generic_ssh_explanation",
        family="general_knowledge",
        prompt="Wie wuerdest du per SSH auf einen Server zugreifen?",
        expected_surface="chat",
        expected_contract="general_explanation_no_private_inventory_claim",
    ),
)


def stabilization_prompt_ids() -> tuple[str, ...]:
    return tuple(row.prompt_id for row in STABILIZATION_PROMPT_MATRIX)


def _line_exists(lines: list[str], label: str) -> bool:
    return line_exists(lines, label)


def _decision_owner_line(lines: list[str]) -> str:
    contract = derive_turn_decision_contract(lines)
    return contract.to_debug_line() if contract is not None else ""


def _evidence_contract_line(lines: list[str]) -> str:
    contract = derive_evidence_contract(lines)
    return contract.to_debug_line() if contract is not None else ""


def _answerability_line(lines: list[str]) -> str:
    contract = derive_answerability_contract(lines)
    return contract.to_debug_line() if contract is not None else ""


def append_stabilization_gate_detail_lines(detail_lines: list[str] | None) -> list[str]:
    lines = [str(line or "").strip() for line in list(detail_lines or []) if str(line or "").strip()]
    if not lines:
        return []

    additions: list[str] = []
    if not _line_exists(lines, "turn_decision_owner"):
        line = _decision_owner_line(lines)
        if line:
            additions.append(line)
    if not _line_exists(lines, "evidence_contract"):
        line = _evidence_contract_line(lines)
        if line:
            additions.append(line)
    if not _line_exists(lines, "answerability"):
        line = _answerability_line(lines)
        if line:
            additions.append(line)

    existing = set(lines)
    clean_additions = [line for line in additions if line and line not in existing]
    if not clean_additions:
        return lines
    return [*lines, *clean_additions]


def _text_has_candidate_caution(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "candidate",
            "candidates",
            "kandidat",
            "kandidaten",
            "mögliche",
            "moegliche",
            "möglicherweise",
            "moeglicherweise",
            "possible",
            "possibly",
            "keine vertraglich gebundene",
            "not contract-bound",
            "not complete",
        )
    )


def _text_claims_complete_or_hard_inventory(lowered: str) -> bool:
    if any(
        phrase in lowered
        for phrase in (
            "complete inventory",
            "complete list",
            "all configured",
            "all servers",
            "vollständige übersicht",
            "vollstaendige uebersicht",
            "vollständige liste",
            "vollstaendige liste",
            "alle konfigurierten",
            "alle server",
        )
    ):
        return True
    return bool(
        re.search(r"\bich\s+habe\s+(?:\*\*)?\d+\b", lowered)
        or re.search(r"\bi\s+(?:found|loaded)\s+\d+\b", lowered)
        or re.search(r"\b\d+\s+(?:ssh|sftp|server|servern|servers|verbindungen|connections|quellen|sources)\b", lowered)
    )


def _candidate_contract_guard_text(*, language: str | None) -> str:
    if str(language or "de").lower().startswith("en"):
        return (
            "I only loaded candidate context here, not contract-bound evidence for a complete answer. "
            "I will not turn that into a hard inventory or completeness claim."
        )
    return (
        "Ich habe hier nur Kandidatenkontext geladen, aber keine vertraglich gebundene Evidenz "
        "fuer eine vollstaendige oder harte Antwort. Ich mache daraus keine belastbare Inventar-Aussage."
    )


def enforce_stabilization_gate_answerability(
    text: str,
    detail_lines: list[str] | None,
    *,
    language: str | None = None,
) -> tuple[str, list[str]]:
    """Fail closed when the final answer is stronger than the evidence contract.

    This guard does not route or infer user meaning. It only validates the final
    answer against already-emitted contract lines from the stabilization gate.
    """

    lines = append_stabilization_gate_detail_lines(detail_lines)
    evidence = evidence_contract_from_debug_lines(lines)
    if evidence is None:
        return str(text or ""), lines
    permission = str(evidence.answer_permissions or "").strip().lower()
    claim_limits = str(evidence.claim_limits or "").strip().lower()
    if permission != "candidate_claims_only" and claim_limits != "no_completeness_claim":
        return str(text or ""), lines
    lowered = str(text or "").strip().lower()
    if not lowered:
        return str(text or ""), lines
    if _text_has_candidate_caution(lowered):
        return str(text or ""), lines
    if not _text_claims_complete_or_hard_inventory(lowered):
        return str(text or ""), lines
    guard_line = (
        "Routing Debug: stabilization_gate_final_answer_guard "
        "status=blocked reason=candidate_contract_overclaim "
        f"answer_permissions={permission or '-'} claim_limits={claim_limits or '-'}"
    )
    if guard_line not in lines:
        lines = [*lines, guard_line]
    return _candidate_contract_guard_text(language=language), lines
