from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan
from aria.core.agentic_runtime_debug import runtime_operation_for_plan
from aria.core.agentic_runtime_debug import runtime_payload_for_plan


def test_runtime_debug_line_exposes_normalized_ssh_execution_boundary() -> None:
    plan = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="pihole1",
        content="uptime -p",
    )

    assert runtime_operation_for_plan(plan) == "run_command"
    assert runtime_payload_for_plan(plan) == {"command": "uptime -p"}
    line = runtime_debug_line_for_plan(plan)

    assert line.startswith("Routing Debug: agentic_runtime ref=pihole1")
    assert "kind=ssh" in line
    assert "capability=ssh_command" in line
    assert "operation=run_command" in line
    assert "command=uptime -p" in line
    assert "boundary=runtime_execution" in line


def test_runtime_debug_line_uses_family_operations_for_messages_and_reads() -> None:
    mqtt = ActionPlan(
        capability="mqtt_publish",
        connection_kind="mqtt",
        connection_ref="event-bus",
        path="aria/events",
        content="Deployment finished",
    )
    mail = ActionPlan(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        content="backup failed",
    )

    assert runtime_operation_for_plan(mqtt) == "publish"
    assert runtime_payload_for_plan(mqtt) == {"topic": "aria/events", "message": "Deployment finished"}
    assert runtime_operation_for_plan(mail) == "read"
    assert runtime_payload_for_plan(mail) == {"selector": "", "query": "backup failed"}
