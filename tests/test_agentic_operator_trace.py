from __future__ import annotations

from aria.core.agentic_operator_trace import OPERATOR_TRACE_PREFIX
from aria.core.agentic_operator_trace import append_operator_trace_detail_lines
from aria.core.agentic_operator_trace import build_operator_trace_lines
from aria.core.agentic_operator_trace import operator_trace_line_from_debug_line


def test_operator_trace_maps_turn_plan_to_understanding_without_new_semantics() -> None:
    line = (
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_turn_arbitration "
        "intents=runtime_action needs_context=true surfaces=connections actions=ssh_command "
        "answer_mode=direct_answer risk=low needs_confirmation=false confidence=0.91"
    )

    trace = operator_trace_line_from_debug_line(line)

    assert trace.startswith(OPERATOR_TRACE_PREFIX)
    assert "phase=understanding" in trace
    assert "boundary=llm_decision" in trace
    assert "intents=runtime_action" in trace
    assert "actions=ssh_command" in trace
    assert "confidence=0.91" in trace


def test_operator_trace_orders_existing_operator_phases() -> None:
    lines = [
        "Routing Debug: context_ledger phase=loaded skills=memory_recall sources=2 arbiter_tokens=40 routing_payload_bytes=300",
        "Routing Debug: agentic_runtime ref=dns-node-01 kind=ssh capability=ssh_command operation=run_command command=uptime boundary=runtime_execution",
        "Routing Debug: multi_target_ssh_preflight_result allowed=2 blocked=0",
        "Routing Debug: multi_target_ssh_timing targets=2 allowed=2 blocked=0 preflight_ms=1 execution_ms=9 summary_ms=3 remember_ms=0 total_ms=13 slowest_ref=dns-node-02 max_target_ms=8",
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_turn_arbitration intents=runtime_action needs_context=true actions=ssh_command confidence=0.92",
        "Routing Debug: multi_target_ssh_result_contract task_intent=health_check command_profile=host_health targets=2 allowed=2 blocked=0 records=2 ok=1 attention=1 error=0 empty=0 assumption=runtime_snapshot_review notable=dns-node-02 confidence=high source=runtime_records",
        "Routing Debug: runtime_outcome_frame stored surface=connections kind=ssh capability=ssh_command task_intent=health_check targets=1 affordances=rerun_check",
        "Routing Debug: multi_target_ssh_summary_timing records=1 operator_ms=2 llm_ms=0 total_ms=2",
        "Learned Recipe Curator: agentic_source=llm_decision policy=context_only_not_executable confidence=0.74 risk=low",
    ]

    traces = build_operator_trace_lines(lines)

    assert [line.split("phase=", 1)[1].split(" ", 1)[0] for line in traces] == [
        "understanding",
        "context",
        "policy",
        "runtime",
        "result",
        "summary",
        "learning",
    ]
    assert all(line.startswith(OPERATOR_TRACE_PREFIX) for line in traces)
    assert any("phase=policy" in line and "source=multi_target_ssh_preflight_result" in line for line in traces)
    assert any("phase=runtime" in line and "boundary=runtime_aggregate" in line and "targets=2" in line for line in traces)
    assert any(
        "phase=result" in line
        and "source=multi_target_ssh_result_contract" in line
        and "boundary=result_contract" in line
        and "notable=dns-node-02" in line
        for line in traces
    )
    assert any("boundary=review_only_learning" in line for line in traces)


def test_operator_trace_maps_policy_and_summary_by_shape_not_specific_use_case() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: generic_runtime_preflight_result allowed=3 blocked=1 reason=read_only_guardrail",
            "Routing Debug: generic_runtime_timing targets=4 allowed=3 blocked=1 preflight_ms=2 execution_ms=20 summary_ms=5 remember_ms=1 total_ms=28 slowest_ref=item-3 max_target_ms=19",
            "Routing Debug: generic_runtime_summary_timing records=4 operator_ms=1 llm_ms=7 total_ms=8",
        ]
    )

    assert any("phase=policy" in line and "source=generic_runtime_preflight_result" in line for line in traces)
    assert any("phase=runtime" in line and "source=generic_runtime_timing" in line for line in traces)
    assert any("phase=summary" in line and "source=generic_runtime_summary_timing" in line for line in traces)


def test_operator_trace_maps_context_packet_and_answer_contract() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: context_ledger phase=loaded skills=memory_recall sources=2",
            "Routing Debug: context_packet turn_plan_source=aria_meta_catalog_routing requests=docs:search loaded=docs:2 empty=- missing=- blocked=- evidence_policy=source_bound contract_mode=answer answer_mode=direct_answer freshness_contract=false",
            "Routing Debug: answer_contract kind=docs_search status=found mode=answer evidence_policy=source_bound answer_mode=direct_answer source_count=2 source_bound=true",
        ]
    )

    assert any("phase=context" in line and "source=context_packet" in line for line in traces)
    assert any("requests=docs:search" in line and "loaded=docs:2" in line for line in traces)
    assert any("phase=result" in line and "source=answer_contract" in line for line in traces)
    assert any("status=found" in line and "source_bound=true" in line for line in traces)


def test_operator_trace_append_is_idempotent() -> None:
    lines = [
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_turn_arbitration intents=chat confidence=0.88",
    ]

    once = append_operator_trace_detail_lines(lines)
    twice = append_operator_trace_detail_lines(once)

    assert once == twice
    assert sum(1 for line in twice if line.startswith(OPERATOR_TRACE_PREFIX)) == 1
