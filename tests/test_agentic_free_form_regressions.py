from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from aria.core.action_plan import ActionPlan
from aria.core.execution_dry_run import evaluate_guardrail_confirm_dry_run
from aria.core.file_agentic_resolution import apply_agentic_file_operation_resolution
from aria.core.http_api_agentic_resolution import apply_agentic_http_api_resolution
from aria.core.messaging_agentic_resolution import apply_agentic_message_operation_resolution
from aria.core.read_agentic_resolution import apply_agentic_read_operation_resolution
from aria.core.ssh_agentic_resolution import apply_agentic_ssh_command_resolution


class _LLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _JSONLLM:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.operations: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation", "") or ""))
        self.messages.append(list(messages))
        return _LLMResponse(json.dumps(self.payload))


class _DryRunSettings:
    class _Connections:
        ssh = {
            "dns-node-01": {
                "host": "dns-node-01.lan",
                "user": "root",
                "guardrail_ref": "safe-ssh",
            },
            "pihole-open": {"host": "dns-node-01.lan", "user": "root"},
        }
        http_api = {
            "inventory-api": {
                "base_url": "https://inventory.example.local",
                "health_path": "/health",
            }
        }
        webhook = {"ops-hook": {"url": "https://example.local/hook"}}

    class _Security:
        guardrails = {
            "safe-ssh": {
                "kind": "ssh_command",
                "allow_terms": ["uptime -p"],
                "deny_terms": ["apt install", "apt upgrade", "reboot", "shutdown"],
            }
        }

    connections = _Connections()
    security = _Security()


def _update_draft(obj, **updates):
    for key, value in updates.items():
        setattr(obj, key, value)
    return obj


def test_free_form_file_read_can_fill_missing_path_but_not_execute() -> None:
    draft = SimpleNamespace(capability="file_read", connection_kind="sftp", path="", content="", notes=[])
    llm = _JSONLLM(
        {
            "operation": "read",
            "path": "/var/log/syslog",
            "content": "",
            "confidence": "high",
            "ask_user": False,
            "reason": "The user asked to inspect the system log.",
        }
    )

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_file_operation_resolution(
            client=llm,
            message="schau mal ins systemlog auf dem mgmt server",
            routing_decision={"kind": "sftp", "ref": "mgmt"},
            action_debug={"decision": {"candidate_kind": "template", "plan_class": "file_read_basic"}},
            capability_draft=draft,
            build_file_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "root_path": "/",
                "allowed_operations": ["list", "read"],
            },
            extract_json_object=json.loads,
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=_update_draft,
        )
    )

    assert llm.operations == ["file_operation_decision"]
    assert updated_draft.path == "/var/log/syslog"
    assert action_debug["decision"]["inputs"] == {"remote_path": "/var/log/syslog"}
    assert "boundary=draft" in debug_line


def test_free_form_file_list_defaults_to_share_root_without_llm() -> None:
    draft = SimpleNamespace(capability="file_list", connection_kind="smb", path="", content="", notes=[])
    llm = _JSONLLM(
        {
            "operation": "list",
            "path": "",
            "content": "",
            "confidence": "high",
            "ask_user": False,
            "reason": "The user asked to list the root of the share.",
        }
    )

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_file_operation_resolution(
            client=llm,
            message='zeige mir die folder auf dem share "Example Share"',
            routing_decision={"kind": "smb", "ref": "example_share"},
            action_debug={"decision": {"candidate_kind": "template", "plan_class": "file_list_basic"}},
            capability_draft=draft,
            build_file_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "share": "Example_Share",
                "allowed_operations": ["list", "read"],
            },
            extract_json_object=json.loads,
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=_update_draft,
        )
    )

    assert llm.operations == []
    assert updated_draft.capability == "file_list"
    assert updated_draft.path == "."
    assert action_debug["decision"]["missing_input"] == ""
    assert action_debug["decision"]["inputs"] == {"remote_path": "."}
    assert debug_line == ""


def test_ssh_health_status_replaces_blocked_uptime_with_allowed_guardrail_bundle() -> None:
    draft = SimpleNamespace(capability="ssh_command", connection_kind="ssh", content="uptime", path="", notes=[])
    llm = _JSONLLM(
        {
            "intent": "health_check",
            "confidence": "high",
            "reason": "The user asks whether the DNS server is ok.",
        }
    )
    allow_terms = [
        "uptime -p",
        "df -h",
        "free -h",
        "systemctl --failed --no-pager",
        "journalctl -p 3 -xb --no-pager -n 40",
    ]

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_ssh_command_resolution(
            client=llm,
            message="ist mein dns server ok",
            routing_decision={"kind": "ssh", "ref": "dns-node-01"},
            action_debug={
                "decision": {
                    "candidate_kind": "template",
                    "candidate_id": "ssh_run_command",
                    "content": "uptime",
                    "inputs": {"command": "uptime"},
                }
            },
            capability_draft=draft,
            build_ssh_target_dossier=lambda ref, user_id="": {
                "connection_ref": ref,
                "guardrail_allow_terms": allow_terms,
            },
            extract_json_object=json.loads,
            normalize_spaces=lambda value: " ".join(str(value).split()),
            routing_debug_enabled=lambda: True,
            msg=lambda _lang, de, en: de or en,
            with_capability_draft_updates=_update_draft,
        )
    )

    command = action_debug["decision"]["inputs"]["command"]
    assert llm.operations == ["ssh_command_decision", "ssh_guardrail_intent"]
    assert "Agentic action contract for ssh_command" in llm.messages[0][0]["content"]
    assert command == " && ".join(allow_terms)
    assert updated_draft.content == command
    assert action_debug["decision"]["guardrail_fallback_from"] == "uptime"
    assert "ssh_command_guardrail_fallback" in debug_line


def test_free_form_message_can_fill_content_but_policy_still_confirms_send() -> None:
    draft = SimpleNamespace(capability="webhook_send", connection_kind="webhook", path="", content="", notes=[])
    llm = _JSONLLM(
        {
            "topic": "",
            "content": "Backup ist fertig.",
            "confidence": "high",
            "ask_user": False,
            "reason": "The user asked to notify operations.",
        }
    )

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_message_operation_resolution(
            client=llm,
            message="sag dem ops hook dass backup fertig ist",
            routing_decision={"kind": "webhook", "ref": "ops-hook"},
            action_debug={"decision": {"candidate_kind": "template", "candidate_id": "webhook_send_message"}},
            capability_draft=draft,
            build_message_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "allowed_operations": ["send"],
            },
            extract_json_object=json.loads,
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=_update_draft,
        )
    )
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "webhook_send",
            "connection_kind": "webhook",
            "connection_ref": "ops-hook",
            "content": updated_draft.content,
            "missing_fields": [],
        }
    }
    dry_run = evaluate_guardrail_confirm_dry_run(_DryRunSettings(), payload_debug=payload_debug)

    assert llm.operations == ["message_operation_decision"]
    assert action_debug["decision"]["inputs"] == {"message": "Backup ist fertig."}
    assert "boundary=draft" in debug_line
    assert dry_run["decision"]["action"] == "ask_user"
    assert dry_run["decision"]["reason"] == "side_effect_confirmation"
    assert "boundary=draft_policy" in dry_run["decision"]["agentic_debug"]


def test_free_form_mail_search_can_fill_query_and_remains_read_only() -> None:
    draft = SimpleNamespace(capability="mail_search", connection_kind="imap", path="", content="", notes=[])
    llm = _JSONLLM(
        {
            "selector": "",
            "query": "backup failed",
            "confidence": "high",
            "ask_user": False,
            "reason": "The user wants mail about failed backups.",
        }
    )

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_read_operation_resolution(
            client=llm,
            message="finde mails wo backup schief ging",
            routing_decision={"kind": "imap", "ref": "ops-mailbox"},
            action_debug={"decision": {"candidate_kind": "template", "plan_class": "mailbox_search_basic"}},
            capability_draft=draft,
            build_read_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "mailbox": "INBOX",
                "allowed_operations": ["read", "search"],
            },
            extract_json_object=json.loads,
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=_update_draft,
        )
    )
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "mail_search",
            "connection_kind": "imap",
            "connection_ref": "ops-mailbox",
            "content": updated_draft.content,
            "missing_fields": [],
        }
    }
    dry_run = evaluate_guardrail_confirm_dry_run(_DryRunSettings(), payload_debug=payload_debug)

    assert llm.operations == ["read_operation_decision"]
    assert action_debug["decision"]["inputs"] == {"query": "backup failed"}
    assert "boundary=draft" in debug_line
    assert dry_run["decision"]["action"] == "allow"
    assert "policy=read_only" in dry_run["decision"]["agentic_debug"]


def test_free_form_http_status_uses_bounded_health_path_and_policy() -> None:
    plan = ActionPlan(
        capability="api_request",
        connection_kind="http_api",
        connection_ref="inventory-api",
    )
    settings = SimpleNamespace(
        connections=SimpleNamespace(
            http_api={
                "inventory-api": {
                    "base_url": "https://inventory.example.local",
                    "health_path": "/health",
                    "method": "GET",
                }
            }
        )
    )

    updated_plan, debug_lines, policy = asyncio.run(
        apply_agentic_http_api_resolution(
            client=None,
            settings=settings,
            message="wie ist der status der inventory api?",
            plan=plan,
            build_http_api_target_dossier=lambda ref, user_id="": {
                "connection_ref": ref,
                "health_path": "/health",
                "configured_method": "GET",
            },
            extract_json_object=json.loads,
            routing_debug_enabled=lambda: True,
        )
    )

    assert updated_plan.path == "/health"
    assert policy is not None
    assert policy.action == "allow"
    assert any("http_api_request_decision" in line and "boundary=draft" in line for line in debug_lines)
    assert any("http_api_request_policy" in line and "boundary=draft_policy" in line for line in debug_lines)


def test_mutating_ssh_free_form_is_blocked_by_policy() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "ssh_command",
            "connection_kind": "ssh",
            "connection_ref": "pihole-open",
            "content": "rm -rf /tmp/aria-probe",
            "preview": "SSH command: rm -rf /tmp/aria-probe",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_DryRunSettings(), payload_debug=payload_debug)

    assert result["status"] == "error"
    assert result["decision"]["action"] == "block"
    assert "policy=ssh_readonly" in result["decision"]["agentic_debug"]
    assert "boundary=draft_policy" in result["decision"]["agentic_debug"]


def test_mutating_http_free_form_is_blocked_by_policy() -> None:
    payload_debug = {
        "payload": {
            "found": True,
            "capability": "api_request",
            "connection_kind": "http_api",
            "connection_ref": "inventory-api",
            "path": "/admin/restart",
            "preview": "API request: /admin/restart",
            "missing_fields": [],
        }
    }

    result = evaluate_guardrail_confirm_dry_run(_DryRunSettings(), payload_debug=payload_debug)

    assert result["status"] == "error"
    assert result["decision"]["action"] == "block"
    assert result["decision"]["reason"] == "http_api_mutating_path"
    assert "policy=http_api" in result["decision"]["agentic_debug"]
    assert "boundary=draft_policy" in result["decision"]["agentic_debug"]
