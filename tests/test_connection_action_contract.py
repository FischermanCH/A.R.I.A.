from __future__ import annotations

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import capability_executor_bindings
from aria.core.connection_action_contract import connection_action_contract
from aria.core.connection_action_contract import connection_action_binding_is_supported
from aria.core.connection_action_contract import connection_action_executor_bindings
from aria.core.connection_action_contract import connection_action_executor_kinds
from aria.core.connection_action_contract import connection_action_contracts
from aria.core.connection_action_contract import runtime_operation_for_capability
from aria.core.connection_action_contract import runtime_payload_for_action_plan


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


def test_connection_action_contracts_keep_policy_and_runtime_boundaries_explicit() -> None:
    contracts = {row.capability: row for row in connection_action_contracts()}

    assert contracts["ssh_command"].operation == "run_command"
    assert contracts["ssh_command"].policy_family == "ssh_readonly"
    assert contracts["ssh_command"].required_fields == ("connection_ref", "content")
    assert contracts["discord_send"].side_effect is True
    assert contracts["discord_send"].policy_family == "message_confirm"
    assert contracts["feed_read"].side_effect is False
    assert contracts["feed_read"].policy_family == "read_only"


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
