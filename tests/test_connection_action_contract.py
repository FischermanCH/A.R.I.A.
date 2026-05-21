from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import capability_executor_bindings
from aria.core.connection_action_contract import connection_action_capabilities_by_family
from aria.core.connection_action_contract import connection_action_capabilities_by_planner_role
from aria.core.connection_action_contract import connection_action_capability_for_executor_family
from aria.core.connection_action_contract import connection_action_contract
from aria.core.connection_action_contract import connection_action_binding_is_supported
from aria.core.connection_action_contract import connection_action_direct_gate_executor_kinds
from aria.core.connection_action_contract import connection_action_executor_bindings
from aria.core.connection_action_contract import connection_action_executor_kinds
from aria.core.connection_action_contract import connection_action_contracts
from aria.core.connection_action_contract import connection_action_manifest_rows
from aria.core.connection_action_contract import confirmation_required_for_capability
from aria.core.connection_action_contract import draft_capability_for_capability
from aria.core.connection_action_contract import guardrail_kind_for_capability
from aria.core.connection_action_contract import runtime_operation_for_capability
from aria.core.connection_action_contract import runtime_payload_for_action_plan
from aria.core.connection_action_contract import sensitive_content_for_capability
from aria.core.pipeline_capability_execution import PipelineCapabilityExecutor


def test_every_executor_binding_has_a_connection_action_contract() -> None:
    missing: list[tuple[str, str]] = []
    for connection_kind, capability in capability_executor_bindings():
        contract = connection_action_contract(capability)
        if contract is None or connection_kind not in contract.executors:
            missing.append((connection_kind, capability))

    assert missing == []


def test_connection_action_contract_is_the_executor_binding_source() -> None:
    assert set(connection_action_executor_bindings()) == set(capability_executor_bindings())
    assert connection_action_executor_kinds() == (
        "ssh",
        "http_api",
        "sftp",
        "smb",
        "webhook",
        "discord",
        "email",
        "mqtt",
        "rss",
        "google_calendar",
        "imap",
        "website",
    )
    assert connection_action_binding_is_supported("ssh", "ssh_command") is True
    assert connection_action_binding_is_supported("rss", "ssh_command") is False


def test_connection_action_contract_exposes_family_lookups_for_agentic_resolvers() -> None:
    assert set(connection_action_capabilities_by_family("read")) == {
        "feed_read",
        "calendar_read",
        "mail_read",
        "mail_search",
        "website_read",
        "website_list",
    }
    assert connection_action_capability_for_executor_family("discord", "message") == "discord_send"
    assert connection_action_capability_for_executor_family("webhook", "message") == "webhook_send"
    assert connection_action_capability_for_executor_family("email", "message") == "email_send"
    assert connection_action_capability_for_executor_family("mqtt", "message") == "mqtt_publish"
    assert connection_action_capability_for_executor_family("rss", "message") == ""


def test_connection_action_contract_exposes_provider_planner_boundaries() -> None:
    assert set(connection_action_capabilities_by_planner_role("search")) == {"mail_search"}
    assert "mail_read" in set(connection_action_capabilities_by_planner_role("read"))
    assert "email_send" in set(connection_action_capabilities_by_planner_role("send"))
    assert confirmation_required_for_capability("email_send") is True
    assert confirmation_required_for_capability("mail_search") is False
    assert sensitive_content_for_capability("mail_search") is True
    assert sensitive_content_for_capability("file_read") is True
    assert draft_capability_for_capability("email_send") == "email_draft"


def test_pipeline_capability_executor_has_handler_for_every_action_contract() -> None:
    missing = [
        contract.capability
        for contract in connection_action_contracts()
        if not hasattr(PipelineCapabilityExecutor, f"execute_{contract.capability}")
    ]

    assert missing == []


def test_direct_capability_gate_kinds_are_contract_backed() -> None:
    assert connection_action_direct_gate_executor_kinds() == (
        "http_api",
        "sftp",
        "smb",
        "webhook",
        "discord",
        "email",
        "mqtt",
        "rss",
        "imap",
        "website",
    )
    assert connection_action_contract("ssh_command").direct_capability_gate is False  # type: ignore[union-attr]
    assert connection_action_contract("calendar_read").direct_capability_gate is False  # type: ignore[union-attr]
    assert connection_action_contract("feed_read").direct_capability_gate is True  # type: ignore[union-attr]


def test_connection_action_contracts_keep_policy_and_runtime_boundaries_explicit() -> None:
    contracts = {row.capability: row for row in connection_action_contracts()}

    assert contracts["ssh_command"].operation == "run_command"
    assert contracts["ssh_command"].policy_family == "ssh_readonly"
    assert contracts["ssh_command"].required_fields == ("connection_ref", "content")
    assert contracts["discord_send"].side_effect is True
    assert contracts["discord_send"].policy_family == "message_confirm"
    assert contracts["feed_read"].side_effect is False
    assert contracts["feed_read"].policy_family == "read_only"
    assert contracts["api_request"].guardrail_kind == "http_request"
    assert contracts["webhook_send"].guardrail_kind == "http_request"
    assert contracts["mqtt_publish"].guardrail_kind == "mqtt_publish"
    assert contracts["discord_send"].guardrail_kind == ""


def test_connection_action_contracts_make_side_effect_boundaries_auditable() -> None:
    side_effect_contracts = [row for row in connection_action_contracts() if row.side_effect]

    assert {row.capability for row in side_effect_contracts} == {
        "discord_send",
        "email_send",
        "file_write",
        "mqtt_publish",
        "webhook_send",
    }
    for contract in side_effect_contracts:
        assert contract.policy_family
        assert contract.policy_family != "read_only"
        assert contract.confirmation_required is True
        assert "connection_ref" in contract.required_fields
        assert contract.payload_fields


def test_runtime_operation_and_payload_are_contract_backed() -> None:
    ssh = ActionPlan(
        capability="ssh_command",
        connection_kind="ssh",
        connection_ref="pihole1",
        content="uptime -p",
    )
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

    assert runtime_operation_for_capability("ssh_command") == "run_command"
    assert runtime_payload_for_action_plan(ssh) == {"command": "uptime -p"}
    assert runtime_operation_for_capability("mqtt_publish") == "publish"
    assert runtime_payload_for_action_plan(mqtt) == {"topic": "aria/events", "message": "Deployment finished"}
    assert runtime_operation_for_capability("mail_search") == "read"
    assert runtime_payload_for_action_plan(mail) == {"selector": "", "query": "backup failed"}
    assert guardrail_kind_for_capability("ssh_command") == "ssh_command"
    assert guardrail_kind_for_capability("file_list") == "file_access"
    assert guardrail_kind_for_capability("api_request") == "http_request"
    assert guardrail_kind_for_capability("webhook_send") == "http_request"
    assert guardrail_kind_for_capability("discord_send") == ""


def test_connection_action_manifest_rows_are_declarative_and_complete() -> None:
    rows = connection_action_manifest_rows()
    by_capability = {row["capability"]: row for row in rows}

    assert set(by_capability) == {contract.capability for contract in connection_action_contracts()}
    assert by_capability["ssh_command"] == {
        "capability": "ssh_command",
        "family": "command",
        "operation": "run_command",
        "planner_role": "command",
        "executors": ["ssh"],
        "policy_family": "ssh_readonly",
        "guardrail_kind": "ssh_command",
        "required_fields": ["connection_ref", "content"],
        "payload_fields": [{"payload": "command", "plan": "content"}],
        "side_effect": False,
        "confirmation_required": False,
        "sensitive_content": False,
        "draft_capability": "",
        "direct_capability_gate": False,
    }
    for row in rows:
        assert row["capability"]
        assert row["family"]
        assert row["operation"]
        assert row["planner_role"]
        assert row["executors"]
        assert row["policy_family"]
        assert "guardrail_kind" in row
        assert isinstance(row["side_effect"], bool)
        assert isinstance(row["confirmation_required"], bool)
        assert isinstance(row["sensitive_content"], bool)
        assert isinstance(row["draft_capability"], str)
        assert isinstance(row["direct_capability_gate"], bool)
