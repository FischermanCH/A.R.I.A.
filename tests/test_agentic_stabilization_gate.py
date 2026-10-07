from __future__ import annotations

from aria.modules.operator_trace_boundary.operator_trace import build_operator_trace_lines
from aria.modules.agentic_stabilization.gate import STABILIZATION_PROMPT_MATRIX
from aria.modules.agentic_stabilization.gate import append_stabilization_gate_detail_lines
from aria.modules.agentic_stabilization.gate import enforce_stabilization_gate_answerability
from aria.modules.agentic_stabilization.gate import stabilization_prompt_ids


def test_stabilization_prompt_matrix_has_unique_core_live_families() -> None:
    ids = stabilization_prompt_ids()

    assert len(ids) == len(set(ids))
    assert len(ids) >= 10
    assert "server_status_all" in ids
    assert "ssh_inventory_dev_followup" in ids
    assert "docker_compose_current" in ids
    assert {row.family for row in STABILIZATION_PROMPT_MATRIX} >= {
        "connections_runtime",
        "connections_inventory",
        "web_currentness",
        "recipes",
    }


def test_stabilization_gate_adds_decision_evidence_and_answerability_without_routing() -> None:
    lines = [
        "Routing Debug: aria_turn_surface_action_arbitration "
        "source=aria_meta_catalog_routing intents=context_inventory needs_context=true "
        "surfaces=connections actions=- answer_mode=direct_answer confidence=0.94",
        "Routing Debug: context_packet "
        "turn_plan_source=aria_meta_catalog_routing requests=connections:inventory "
        "loaded=connections:14 empty=- missing=- blocked=- evidence_policy=source_bound "
        "contract_mode=answer answer_mode=direct_answer freshness_contract=false",
        "Routing Debug: answer_contract "
        "kind=inventory status=found mode=answer evidence_policy=source_bound "
        "answer_mode=direct_answer source_count=14 source_bound=true",
    ]

    updated = append_stabilization_gate_detail_lines(lines)

    assert any("Routing Debug: turn_decision_owner owner=aria_meta_catalog_routing" in line for line in updated)
    assert any("Routing Debug: evidence_contract surface=mixed authority=source_bound" in line for line in updated)
    assert any("sources=14" in line and "answer_permissions=source_bound_claims" in line for line in updated)
    assert any("Routing Debug: answerability surface=inventory" in line for line in updated)
    assert append_stabilization_gate_detail_lines(updated) == updated


def test_stabilization_gate_prefers_evidence_bundle_contract_for_followup() -> None:
    updated = append_stabilization_gate_detail_lines(
        [
            "Routing Debug: evidence_bundle reused "
            "surface=connections authority=config completeness=full_kind fields=host,ref rows=14 matched=2 status=found",
            "Routing Debug: answerability "
            "surface=connections completeness=full_kind authority=config field=host "
            "decision=answer_from_last_evidence_bundle",
            "Routing Debug: direct_context_answer kind=evidence_bundle_followup reason=last_turn_field_reuse",
        ]
    )

    assert any("turn_decision_owner owner=evidence_bundle_followup" in line for line in updated)
    assert any(
        "evidence_contract surface=connections authority=config completeness=full_kind" in line
        and "answer_permissions=bound_claims" in line
        for line in updated
    )
    assert len([line for line in updated if "Routing Debug: answerability " in line]) == 1


def test_operator_trace_maps_stabilization_gate_contract_lines() -> None:
    traces = build_operator_trace_lines(
        append_stabilization_gate_detail_lines(
            [
                "Routing Debug: aria_turn_surface_action_arbitration "
                "source=aria_meta_catalog_routing surfaces=connections actions=- "
                "answer_mode=direct_answer confidence=0.94",
                "Routing Debug: evidence_bundle stored "
                "surface=connections authority=config completeness=full_kind fields=host,ref rows=14",
                "Routing Debug: answer_contract "
                "kind=inventory status=found mode=answer evidence_policy=source_bound "
                "answer_mode=direct_answer source_count=14 source_bound=true",
            ]
        )
    )

    assert any("phase=understanding" in line and "source=turn_decision_owner" in line for line in traces)
    assert any("phase=context" in line and "source=evidence_contract" in line for line in traces)
    assert any("phase=result" in line and "source=answerability" in line for line in traces)


def test_stabilization_gate_normalizes_runtime_outcome_contracts() -> None:
    lines = append_stabilization_gate_detail_lines(
        [
            "Routing Debug: runtime_outcome_followup "
            "action=use_previous_outcome affordance=summarize_targets surface=connections kind=ssh "
            "capability=ssh_command task_intent=capacity_check targets=14 confidence=0.00 "
            "claim=fail_closed_previous_outcome",
            "Routing Debug: runtime_outcome_evidence_contract "
            "surface=runtime_outcome authority=runtime_records completeness=records "
            "task_intent=capacity_check records=14 claim_limits=observed_runtime_fields_only",
        ]
    )

    assert any(
        "turn_decision_owner owner=runtime_outcome_followup" in line
        and "boundary=last_runtime_outcome" in line
        for line in lines
    )
    assert any(
        "evidence_contract surface=runtime_outcome authority=runtime_records completeness=records" in line
        and "rows=14" in line
        and "claim_limits=observed_runtime_fields_only" in line
        for line in lines
    )
    assert any(
        "answerability surface=runtime_outcome completeness=records authority=runtime_records" in line
        and "decision=answer_from_runtime_outcome" in line
        for line in lines
    )
    traces = build_operator_trace_lines(lines)
    assert any("phase=context" in line and "source=evidence_contract" in line for line in traces)
    assert any("phase=result" in line and "source=answerability" in line for line in traces)


def test_stabilization_gate_does_not_reinterpret_answer_text() -> None:
    original = "Ich habe 12 SSH/SFTP-Verbindungen mit Hostname und IP-Adresse gefunden."
    text, lines = enforce_stabilization_gate_answerability(
        original,
        [
            "Routing Debug: evidence_bundle stored "
            "surface=connections authority=candidate completeness=candidate_only fields=host,ref rows=12",
        ],
        language="de",
    )

    assert text == original
    assert not any("stabilization_gate_final_answer_guard" in line for line in lines)
    assert any("evidence_contract surface=connections authority=candidate completeness=candidate_only" in line for line in lines)


def test_stabilization_gate_allows_cautious_candidate_answer() -> None:
    original = "Ich habe moegliche Kandidaten fuer Host/IP-Daten gefunden, bezeichne sie aber nicht als vollstaendig."

    text, lines = enforce_stabilization_gate_answerability(
        original,
        [
            "Routing Debug: evidence_bundle stored "
            "surface=connections authority=candidate completeness=candidate_only fields=host,ref rows=12",
        ],
        language="de",
    )

    assert text == original
    assert not any("stabilization_gate_final_answer_guard" in line for line in lines)
