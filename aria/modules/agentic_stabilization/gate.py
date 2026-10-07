from __future__ import annotations

from dataclasses import dataclass

from aria.modules.agentic_contracts.contracts import derive_answerability_contract
from aria.modules.agentic_contracts.contracts import derive_evidence_contract
from aria.modules.agentic_contracts.contracts import derive_turn_decision_contract
from aria.modules.agentic_contracts.contracts import line_exists



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
        prompt="Which connections do you know for Syncthing?",
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
        prompt="Which recipes or templates do you know?",
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
        prompt="What else do you know about my servers?",
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


def enforce_stabilization_gate_answerability(
    text: str,
    detail_lines: list[str] | None,
    *,
    language: str | None = None,
) -> tuple[str, list[str]]:
    """Attach structured evidence contracts without reinterpreting answer text."""
    _ = language
    lines = append_stabilization_gate_detail_lines(detail_lines)
    return str(text or ""), lines
