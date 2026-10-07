from __future__ import annotations

from aria.modules.action_contracts.connection import connection_action_contracts
from aria.modules.action_contracts.connection import connection_action_executor_kinds
from aria.modules.connections_provider_manifest.projection import build_connection_provider_manifests
from aria.modules.connections_provider_manifest.projection import connection_provider_manifest_rows
from aria.modules.connections_provider_manifest.projection import connection_provider_runtime_adapter_audit_rows
from aria.modules.connections_provider_manifest.projection import validate_connection_provider_manifest


def test_provider_manifests_cover_every_connection_action_executor_kind() -> None:
    manifests = build_connection_provider_manifests()

    assert tuple(row.connection_kind for row in manifests) == tuple(sorted(connection_action_executor_kinds()))
    assert {row.connection_kind for row in manifests} == set(connection_action_executor_kinds())


def test_provider_manifest_groups_capabilities_by_connection_kind() -> None:
    rows = {row["connection_kind"]: row for row in connection_provider_manifest_rows()}

    assert rows["ssh"]["provider_id"] == "builtin.ssh"
    assert rows["ssh"]["auth_modes"] == ["ssh_key", "password"]
    assert rows["ssh"]["capabilities"] == [
        {
            "capability": "ssh_command",
            "family": "command",
            "operation": "run_command",
            "planner_role": "command",
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
    ]
    assert {item["capability"] for item in rows["sftp"]["capabilities"]} == {
        "file_list",
        "file_read",
        "file_write",
    }
    assert next(item for item in rows["discord"]["capabilities"] if item["capability"] == "discord_send")["side_effect"] is True
    email_send = next(item for item in rows["email"]["capabilities"] if item["capability"] == "email_send")
    assert email_send["planner_role"] == "send"
    assert email_send["confirmation_required"] is True
    assert email_send["draft_capability"] == "email_draft"
    assert next(item for item in rows["imap"]["capabilities"] if item["capability"] == "mail_search")["planner_role"] == "search"
    assert rows["google_calendar"]["auth_modes"] == ["oauth2"]


def test_provider_manifest_rows_validate_against_manifest_contract() -> None:
    rows = connection_provider_manifest_rows()

    assert rows
    assert [validate_connection_provider_manifest(row) for row in rows] == [[] for _row in rows]


def test_provider_runtime_adapter_audit_reports_registry_status() -> None:
    rows = {row["connection_kind"]: row for row in connection_provider_runtime_adapter_audit_rows()}

    assert rows["ssh"]["runtime_adapter"] == "builtin.ssh"
    assert rows["ssh"]["registry_status"] == "specialized_handler"
    assert rows["rss"]["registry_status"] == "specialized_handler"
    assert rows["discord"]["runtime_adapter"] == "builtin.discord"
    assert rows["discord"]["registry_status"] == "generic_capability_handler"
    assert "discord_send" in rows["discord"]["capabilities"]


def test_provider_manifest_rows_mirror_action_contracts() -> None:
    manifest_pairs = {
        (row["connection_kind"], capability["capability"])
        for row in connection_provider_manifest_rows()
        for capability in row["capabilities"]
    }
    contract_pairs = {
        (executor, contract.capability)
        for contract in connection_action_contracts()
        for executor in contract.executors
    }

    assert manifest_pairs == contract_pairs


def test_validate_connection_provider_manifest_reports_contract_errors() -> None:
    errors = validate_connection_provider_manifest(
        {
            "schema_version": "0.2",
            "provider_id": "community.bad",
            "connection_kind": "http_api",
            "runtime_adapter": "community.bad",
            "auth_modes": ["api_key"],
            "capabilities": [
                {
                    "capability": "bad_write",
                    "family": "request",
                    "operation": "request",
                    "planner_role": "send",
                    "policy_family": "read_only",
                    "required_fields": "connection_ref",
                    "payload_fields": [{"payload": "path"}],
                    "side_effect": True,
                    "confirmation_required": False,
                    "sensitive_content": "yes",
                    "direct_capability_gate": "yes",
                }
            ],
        }
    )

    assert errors == [
        "runtime_adapter_registry",
        "capabilities[0].required_fields",
        "capabilities[0].payload_fields[0]",
        "capabilities[0].sensitive_content",
        "capabilities[0].direct_capability_gate",
        "capabilities[0].side_effect_policy",
        "capabilities[0].side_effect_confirmation",
    ]


def test_provider_runtime_adapter_audit_marks_unknown_adapter_unregistered() -> None:
    rows = connection_provider_runtime_adapter_audit_rows(
        [
            {
                "schema_version": "0.2",
                "provider_id": "community.todo",
                "connection_kind": "todo",
                "runtime_adapter": "community.todo",
                "auth_modes": ["api_key"],
                "capabilities": [{"capability": "todo_create"}],
            }
        ]
    )

    assert rows == [
        {
            "connection_kind": "todo",
            "provider_id": "community.todo",
            "runtime_adapter": "community.todo",
            "registry_status": "unregistered",
            "capabilities": ["todo_create"],
        }
    ]
