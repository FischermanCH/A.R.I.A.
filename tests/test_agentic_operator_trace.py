from __future__ import annotations

from aria.modules.operator_trace_boundary.operator_trace import OPERATOR_TRACE_PREFIX
from aria.modules.operator_trace_boundary.operator_trace import append_operator_trace_detail_lines
from aria.modules.operator_trace_boundary.operator_trace import build_operator_trace_lines
from aria.modules.operator_trace_boundary.operator_trace import operator_trace_line_from_debug_line


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
        "draft",
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


def test_operator_trace_maps_agentic_action_policy_and_execution_contracts() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
            "Routing Debug: agentic_action_contract candidate_kind=template candidate_id=discord_send_message candidate_role=template_candidate capability=discord_send kind=discord ref=alerts execution_state=needs_confirmation",
            "Routing Debug: agentic_policy_decision action=ask_user reason=outbound_message_confirmation policy=message_confirm guardrail=- capability=discord_send kind=discord ref=alerts",
            "Routing Debug: agentic_runtime ref=alerts kind=discord capability=discord_send operation=send message=ARIA_smoke_test boundary=runtime_execution",
        ]
    )

    assert any("phase=context" in line and "source=meta_catalog_contract" in line for line in traces)
    assert any("phase=draft" in line and "source=agentic_action_contract" in line for line in traces)
    assert any("candidate_id=discord_send_message" in line for line in traces)
    assert any("phase=policy" in line and "source=agentic_policy_decision" in line for line in traces)
    assert any("phase=runtime" in line and "source=agentic_runtime" in line for line in traces)


def test_operator_trace_maps_live_routed_action_shape_to_draft_policy_and_runtime() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
            "intents=chat,runtime_action needs_context=true context_directions=connections "
            "surfaces=connections actions=discord_send_message answer_mode=plan_action "
            "risk=medium needs_confirmation=true confidence=0.97 priority=connection|discord|fischerman-aria-messages",
            "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
            "Ausgeführt via Discord-Profil `fischerman-aria-messages`",
        ]
    )

    assert any("phase=understanding" in line and "actions=discord_send_message" in line for line in traces)
    assert any("phase=draft" in line and "source=aria_turn_surface_action_arbitration" in line for line in traces)
    assert any("phase=policy" in line and "action=confirm" in line for line in traces)
    assert any(
        "phase=runtime" in line
        and "source=execution_detail" in line
        and "kind=discord" in line
        and "ref=fischerman-aria-messages" in line
        for line in traces
    )


def test_operator_trace_aggregates_multi_target_execution_details() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
            "intents=runtime_action needs_context=true surfaces=connections "
            "actions=connection_action_ssh answer_mode=plan_action risk=medium "
            "needs_confirmation=true confidence=0.95",
            "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
            "Ausgeführt via SSH-Profil `dev-node-01`",
            "Befehl: df -h",
            "Ausgeführt via SSH-Profil `dev-node-02`",
            "Befehl: df -h",
            "Ausgeführt via SSH-Profil `app-node-01`",
            "Befehl: df -h",
        ]
    )

    runtime = next(line for line in traces if "phase=runtime" in line)
    assert "source=execution_detail" in runtime
    assert "kind=ssh" in runtime
    assert "targets=3" in runtime
    assert "first_ref=dev-node-01" in runtime
    assert " ref=dev-node-01" not in runtime


def test_operator_trace_keeps_monitoring_explicit_ref_single_target_runtime() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
            "intents=chat,runtime_action needs_context=true context_directions=connections "
            "surfaces=connections actions=ssh_run_command answer_mode=direct_answer "
            "risk=medium needs_confirmation=true confidence=0.88 priority=connection|ssh|ops-alert-01",
            "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
            "Routing Debug: capability_draft capability=ssh_command kind=ssh explicit_ref=ops-alert-01 requested_ref=- path=- content=uptime boundary=context_enrichment",
            "Routing Debug: plural_target_scope disabled_by_explicit_single_target explicit_ref=ops-alert-01",
            "Routing Debug: agentic_runtime ref=ops-alert-01 kind=ssh capability=ssh_command operation=run_command command=uptime boundary=runtime_execution",
            "Ausgeführt via SSH-Profil `ops-alert-01`",
            "Befehl: uptime",
        ]
    )

    runtime = next(line for line in traces if "phase=runtime" in line)
    assert "source=agentic_runtime" in runtime
    assert "ref=ops-alert-01" in runtime
    assert "targets=" not in runtime
    assert not any("source=multi_target_ssh_timing" in line for line in traces)


def test_operator_trace_real_policy_decision_overrides_turn_confirmation_hint() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
            "intents=chat,runtime_action needs_context=true context_directions=connections "
            "surfaces=connections actions=ssh_run_command answer_mode=plan_action "
            "risk=medium needs_confirmation=true confidence=0.88 priority=connection|ssh|ops-alert-01",
            "Routing Debug: agentic_policy_decision action=allow reason=ssh_readonly_policy_allow "
            "policy=- guardrail=ssh-dangerous-commands-block capability=ssh_command kind=ssh ref=ops-alert-01",
            "Routing Debug: agentic_execution_decision next_step=allow capability=ssh_command "
            "kind=ssh ref=ops-alert-01 operation=run_command",
        ]
    )

    policy = next(line for line in traces if "phase=policy" in line)
    assert "source=agentic_policy_decision" in policy
    assert "action=allow" in policy
    assert "action=confirm" not in policy


def test_operator_trace_live_export_golden_shape() -> None:
    ssh_lines = [
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
        "intents=runtime_action needs_context=true surfaces=connections actions=connection_action_ssh "
        "answer_mode=plan_action risk=medium needs_confirmation=true confidence=0.95",
        "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
        "Ausgeführt via SSH-Profil `dev-node-01`",
        "Ausgeführt via SSH-Profil `dev-node-02`",
    ]
    http_lines = [
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
        "intents=chat,runtime_action needs_context=true surfaces=connections actions=http_api_request "
        "answer_mode=plan_action risk=low needs_confirmation=false confidence=0.95",
        "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
        "Ausgeführt via HTTP API-Profil `n8n-test-http-api`",
        "Pfad: /health",
    ]
    pending_discord_lines = [
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
        "intents=chat,runtime_action needs_context=true surfaces=connections actions=discord_send_message "
        "answer_mode=plan_action risk=medium needs_confirmation=true confidence=0.95",
        "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
    ]
    confirmed_discord_lines = [
        "Routing Debug: agentic_action_contract candidate_kind=template candidate_id=discord_send_message "
        "candidate_role=template_candidate capability=discord_send kind=discord ref=fischerman-aria-messages "
        "execution_state=needs_confirmation",
        "Routing Debug: agentic_policy_decision action=ask_user reason=outbound_message_confirmation "
        "policy=message_confirm guardrail=- capability=discord_send kind=discord ref=fischerman-aria-messages",
        "Ausgeführt via Discord-Profil `fischerman-aria-messages`",
    ]

    ssh_phases = [line.split("phase=", 1)[1].split(" ", 1)[0] for line in build_operator_trace_lines(ssh_lines)]
    http_phases = [line.split("phase=", 1)[1].split(" ", 1)[0] for line in build_operator_trace_lines(http_lines)]
    pending_phases = [line.split("phase=", 1)[1].split(" ", 1)[0] for line in build_operator_trace_lines(pending_discord_lines)]
    confirmed_phases = [line.split("phase=", 1)[1].split(" ", 1)[0] for line in build_operator_trace_lines(confirmed_discord_lines)]

    assert ssh_phases == ["understanding", "context", "draft", "policy", "runtime"]
    assert http_phases == ["understanding", "context", "draft", "policy", "runtime"]
    assert pending_phases == ["understanding", "context", "draft", "policy"]
    assert confirmed_phases == ["draft", "policy", "runtime"]


def test_operator_trace_pending_confirmation_does_not_invent_runtime() -> None:
    traces = build_operator_trace_lines(
        [
            "Routing Debug: aria_turn_surface_action_arbitration source=aria_meta_catalog_routing "
            "intents=chat,runtime_action needs_context=true surfaces=connections "
            "actions=discord_send_message answer_mode=plan_action risk=medium "
            "needs_confirmation=true confidence=0.97",
            "Routing Debug: meta_catalog_contract phase=action_preflight legacy_semantics=skipped",
        ]
    )

    assert any("phase=draft" in line for line in traces)
    assert any("phase=policy" in line and "action=confirm" in line for line in traces)
    assert not any("phase=runtime" in line for line in traces)


def test_operator_trace_append_handles_confirm_execute_without_routing_debug() -> None:
    lines = [
        "Ausgeführt via Discord-Profil `fischerman-aria-messages`",
        "Routing Debug: web_total_wall_time total_ms=3227 source=web_chat_route boundary=prompt_in_to_html_ready",
    ]

    appended = append_operator_trace_detail_lines(lines, allow_execution_only=True)

    assert any(
        "operator_trace phase=runtime" in line
        and "source=execution_detail" in line
        and "kind=discord" in line
        and "ref=fischerman-aria-messages" in line
        for line in appended
    )
    assert appended.index("Ausgeführt via Discord-Profil `fischerman-aria-messages`") > next(
        index for index, line in enumerate(appended) if "operator_trace phase=runtime" in line
    )


def test_operator_trace_append_handles_execution_only_detail_shapes() -> None:
    cases = [
        ("Ausgeführt via SSH-Profil `dev-node-01`", "kind=ssh", "ref=dev-node-01"),
        ("Ausgeführt via HTTP API-Profil `n8n-test-http-api`", "kind=http_api", "ref=n8n-test-http-api"),
        ("Ausgeführt via Discord-Profil `fischerman-aria-messages`", "kind=discord", "ref=fischerman-aria-messages"),
    ]

    for detail, kind_field, ref_field in cases:
        appended = append_operator_trace_detail_lines([detail], allow_execution_only=True)
        runtime = next(line for line in appended if "operator_trace phase=runtime" in line)
        assert "source=execution_detail" in runtime
        assert kind_field in runtime
        assert ref_field in runtime


def test_operator_trace_append_is_idempotent() -> None:
    lines = [
        "Routing Debug: aria_turn_surface_action_arbitration source=aria_turn_arbitration intents=chat confidence=0.88",
    ]

    once = append_operator_trace_detail_lines(lines)
    twice = append_operator_trace_detail_lines(once)

    assert once == twice
    assert sum(1 for line in twice if line.startswith(OPERATOR_TRACE_PREFIX)) == 1
