from __future__ import annotations

import importlib
import sys

from aria.modules import MODULE_MANIFESTS
from aria.modules.agentic_contracts.contracts import derive_evidence_contract
from aria.modules.agentic_prompt_flow.prompt_flow import agentic_context_debug_line
from aria.modules.agentic_prompt_flow.prompt_flow import agentic_debug_boundary_phases
from aria.modules.agentic_prompt_flow.prompt_flow import normalize_agentic_debug_boundary
from aria.modules.agentic_stabilization.gate import append_stabilization_gate_detail_lines
from aria.modules.agentic_stabilization.gate import enforce_stabilization_gate_answerability


def test_agentic_contract_prompt_flow_legacy_imports_are_identity_aliases() -> None:
    pairs = {
        "aria.modules.agentic_prompt_flow.prompt_flow": "aria.modules.agentic_prompt_flow.prompt_flow",
        "aria.modules.agentic_contracts.contracts": "aria.modules.agentic_contracts.contracts",
        "aria.modules.agentic_stabilization.gate": "aria.modules.agentic_stabilization.gate",
    }

    for legacy_name, canonical_name in pairs.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert legacy is canonical
        assert sys.modules[legacy_name] is canonical


def test_agentic_contract_prompt_flow_modules_are_registered_without_runtime_access() -> None:
    for module_id in ("agentic_prompt_flow", "agentic_contracts", "agentic_stabilization"):
        manifest = MODULE_MANIFESTS[module_id]
        assert manifest["status"] == "import_boundary_active"
        assert manifest["build_allowed"] is False
        assert manifest["runtime_access_allowed"] is False
        assert "runtime_access" in manifest["explicitly_excluded"]


def test_agentic_prompt_flow_debug_boundary_output_is_preserved() -> None:
    assert normalize_agentic_debug_boundary("runtime_execution") == "runtime_execution"
    assert normalize_agentic_debug_boundary("unknown") == "context_enrichment"
    assert agentic_debug_boundary_phases("draft_policy") == (
        "llm_action_proposal",
        "policy_guardrail_decision",
    )

    line = agentic_context_debug_line("action_context", {"source": "candidate", "count": 2})

    assert line == "Routing Debug: action_context source=candidate count=2 boundary=context_enrichment"


def test_agentic_contract_and_stabilization_output_is_preserved_without_rewriting_text() -> None:
    lines = [
        "Routing Debug: evidence_bundle stored "
        "surface=connections authority=candidate completeness=candidate_only fields=host,ref rows=12",
    ]

    evidence = derive_evidence_contract(lines)
    assert evidence is not None
    assert evidence.to_debug_line() == (
        "Routing Debug: evidence_contract surface=connections authority=candidate "
        "completeness=candidate_only fields=host,ref rows=12 sources=- "
        "answer_permissions=candidate_claims_only claim_limits=no_completeness_claim"
    )

    text, updated = enforce_stabilization_gate_answerability("Antwort bleibt unveraendert.", lines)

    assert text == "Antwort bleibt unveraendert."
    assert updated == append_stabilization_gate_detail_lines(lines)
    assert any("Routing Debug: evidence_contract surface=connections" in line for line in updated)
