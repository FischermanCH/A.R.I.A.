from __future__ import annotations

from aria.core.agentic_action_resolution import (
    AGENTIC_POLICY_ACTIONS,
    action_draft_from_file_operation,
    action_draft_from_http_request,
    action_draft_from_message_operation,
    action_draft_from_read_operation,
    action_draft_from_ssh_command,
    agentic_action_contract_prompt,
    agentic_debug_line,
    file_policy_result,
    message_policy_result,
    read_policy_result,
    http_policy_result,
    normalize_agentic_policy_action,
    ssh_policy_result,
)
from aria.core.agentic_prompt_flow import agentic_debug_boundary_phases
from aria.core.agentic_prompt_flow import normalize_agentic_debug_boundary
from aria.core.connection_dossiers import build_file_target_dossier
from aria.core.connection_dossiers import build_message_target_dossier
from aria.core.connection_dossiers import build_read_target_dossier
from aria.core.file_agentic_resolution import apply_agentic_file_operation_resolution
from aria.core.file_agentic_resolution import file_operation_from_action
from aria.core.http_api_agentic_resolution import resolve_http_api_request_from_dossier
from aria.core.messaging_agentic_resolution import apply_agentic_message_operation_resolution
from aria.core.messaging_agentic_resolution import message_draft_is_complete
from aria.core.read_agentic_resolution import apply_agentic_read_operation_resolution
from aria.core.read_agentic_resolution import read_draft_is_complete


class _LLMResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _FileLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation", "") or ""))
        self.messages.append(list(messages))
        return _LLMResponse(
            '{"operation":"read","path":"/etc/hosts","content":"","confidence":"high",'
            '"ask_user":false,"reason":"The user asked to inspect the hosts file."}'
        )


class _MessageLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation", "") or ""))
        self.messages.append(list(messages))
        return _LLMResponse(
            '{"topic":"aria/events","content":"Deployment finished","confidence":"high",'
            '"ask_user":false,"reason":"The user asked to publish a short status message."}'
        )


class _ReadLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation", "") or ""))
        self.messages.append(list(messages))
        return _LLMResponse(
            '{"selector":"","query":"backup failed","confidence":"high",'
            '"ask_user":false,"reason":"The user asked to search mail for backup failures."}'
        )


class _HTTPLLM:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.messages: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs):  # noqa: ANN001
        self.operations.append(str(kwargs.get("operation", "") or ""))
        self.messages.append(list(messages))
        return _LLMResponse(
            '{"path":"/health","content":"","confidence":"high",'
            '"ask_user":false,"reason":"The user asked for API health."}'
        )


def _first_system_prompt(llm: object) -> str:
    messages = list(getattr(llm, "messages", []) or [])
    if not messages:
        return ""
    return str(dict(messages[0][0]).get("content", "") or "")


def test_agentic_action_contract_prompt_makes_llm_and_policy_roles_explicit() -> None:
    prompt = agentic_action_contract_prompt("ssh_command")

    assert "Agentic action contract for ssh_command" in prompt
    assert "Propose one concrete action draft" in prompt
    assert "policy and guardrails decide allow, ask_user, or block" in prompt
    assert "Never invent secrets" in prompt


def test_agentic_ssh_action_draft_is_bounded_metadata() -> None:
    draft = action_draft_from_ssh_command(
        connection_ref="pihole1",
        command="uptime -p",
        source="llm_decision",
        confidence="HIGH",
        reason="Check host status",
        ask_user=False,
    )

    assert draft.capability == "ssh_command"
    assert draft.connection_kind == "ssh"
    assert draft.operation == "run_command"
    assert draft.normalized_payload_value("command") == "uptime -p"
    assert draft.confidence == "high"
    assert "agentic_source=llm_decision" in draft.as_debug_suffix()


def test_agentic_http_action_draft_tracks_policy_boundary() -> None:
    draft = action_draft_from_http_request(
        connection_ref="inventory-api",
        method="get",
        path="/health",
        source="llm_decision",
        confidence="medium",
    )
    policy = http_policy_result(action="allow", reason="http_api_readonly_policy_allow", path="/health")

    assert draft.capability == "api_request"
    assert draft.connection_kind == "http_api"
    assert draft.payload["method"] == "GET"
    assert policy.allowed is True
    assert "policy=http_api" in policy.as_debug_suffix()


def test_agentic_file_action_draft_uses_connection_family_not_adapter_specific_shape() -> None:
    draft = action_draft_from_file_operation(
        connection_kind="smb",
        connection_ref="nas-share",
        operation="list",
        path="/docs",
        source="llm_decision",
        confidence="high",
    )
    policy = file_policy_result(action="allow", reason="guardrail_allow", path="/docs")

    assert draft.capability == "file_list"
    assert draft.connection_kind == "smb"
    assert draft.operation == "list"
    assert draft.normalized_payload_value("path") == "/docs"
    assert "policy=file_access" in policy.as_debug_suffix()


def test_agentic_message_action_draft_uses_outbound_message_shape() -> None:
    draft = action_draft_from_message_operation(
        capability="mqtt_publish",
        connection_kind="mqtt",
        connection_ref="event-bus",
        topic="aria/events",
        content="Deployment finished",
        source="llm_decision",
        confidence="high",
    )
    policy = message_policy_result(action="ask_user", reason="side_effect_confirmation", topic="aria/events", content="Deployment finished")

    assert draft.capability == "mqtt_publish"
    assert draft.operation == "publish"
    assert draft.normalized_payload_value("topic") == "aria/events"
    assert "policy=message_confirm" in policy.as_debug_suffix()


def test_agentic_read_action_draft_uses_read_only_shape() -> None:
    draft = action_draft_from_read_operation(
        capability="mail_search",
        connection_kind="imap",
        connection_ref="ops-inbox",
        query="backup failed",
        source="llm_decision",
        confidence="high",
    )
    policy = read_policy_result(query="backup failed")

    assert draft.capability == "mail_search"
    assert draft.operation == "read"
    assert draft.normalized_payload_value("query") == "backup failed"
    assert "policy=read_only" in policy.as_debug_suffix()


def test_agentic_policy_result_keeps_runtime_decision_separate_from_llm_draft() -> None:
    policy = ssh_policy_result(
        action="block",
        reason="ssh_command_mutating_operation",
        command="apt update",
    )

    assert policy.allowed is False
    assert policy.normalized_payload == {"command": "apt update"}
    assert "policy_action=block" in policy.as_debug_suffix()


def test_agentic_policy_actions_are_canonical_across_capabilities() -> None:
    assert AGENTIC_POLICY_ACTIONS == {"allow", "ask_user", "block"}
    assert normalize_agentic_policy_action("confirm") == "ask_user"
    assert normalize_agentic_policy_action("run") == "ask_user"
    assert normalize_agentic_policy_action("run", default="block") == "block"
    assert ssh_policy_result(action="run", reason="legacy", command="uptime").action == "ask_user"
    assert http_policy_result(action="confirm", reason="legacy", path="/health").action == "ask_user"
    assert file_policy_result(action="ALLOW", reason="ok", path="/tmp/a").action == "allow"
    assert message_policy_result(action="block", reason="side_effect", content="x").blocked is True
    assert read_policy_result(action="", query="backup").action == "allow"


def test_agentic_debug_line_uses_one_format_for_capabilities() -> None:
    draft = action_draft_from_ssh_command(
        connection_ref="pihole1",
        command="uptime",
        source="llm_decision",
        confidence="low",
    )
    policy = ssh_policy_result(action="block", reason="ssh_command_not_in_allow_list", command="uptime")

    line = agentic_debug_line(
        "ssh_command_policy",
        connection_ref="pihole1",
        fields={"action": "block", "command": "uptime"},
        draft=draft,
        policy=policy,
    )

    assert line.startswith("Routing Debug: ssh_command_policy ref=pihole1")
    assert "boundary=draft_policy" in line
    assert "agentic_source=llm_decision" in line
    assert "policy=ssh_readonly" in line


def test_agentic_debug_boundaries_map_to_prompt_flow_phases() -> None:
    assert agentic_debug_boundary_phases("context_enrichment") == ("context_enrichment",)
    assert agentic_debug_boundary_phases("draft") == ("llm_action_proposal",)
    assert agentic_debug_boundary_phases("policy") == ("policy_guardrail_decision",)
    assert agentic_debug_boundary_phases("draft_policy") == ("llm_action_proposal", "policy_guardrail_decision")
    assert agentic_debug_boundary_phases("runtime_execution") == ("runtime_execution",)
    assert normalize_agentic_debug_boundary("unknown") == "context_enrichment"


def test_agentic_runtime_debug_line_uses_runtime_boundary() -> None:
    line = agentic_debug_line(
        "agentic_runtime",
        connection_ref="event-bus",
        fields={"kind": "mqtt", "capability": "mqtt_publish", "operation": "publish"},
        boundary="runtime_execution",
    )

    assert "boundary=runtime_execution" in line
    assert "kind=mqtt" in line


def test_file_target_dossier_excludes_secrets_for_modular_agentic_resolution() -> None:
    dossier = build_file_target_dossier(
        {
            "nas-share": {
                "host": "nas.local",
                "share": "team",
                "user": "aria",
                "password": "secret",
                "root_path": "/docs",
                "aliases": ["team files"],
                "guardrail_ref": "team-docs",
            }
        },
        "nas-share",
        connection_kind="smb",
    )

    assert dossier["kind"] == "smb"
    assert dossier["connection_ref"] == "nas-share"
    assert dossier["share"] == "team"
    assert dossier["root_path"] == "/docs"
    assert dossier["guardrail_ref"] == "team-docs"
    assert "password" not in dossier
    assert "user" not in dossier


def test_message_target_dossier_excludes_secrets_for_modular_agentic_resolution() -> None:
    dossier = build_message_target_dossier(
        {
            "event-bus": {
                "host": "mqtt.local",
                "user": "aria",
                "password": "secret",
                "topic": "aria/events",
                "aliases": ["events"],
            }
        },
        "event-bus",
        connection_kind="mqtt",
    )

    assert dossier["kind"] == "mqtt"
    assert dossier["connection_ref"] == "event-bus"
    assert dossier["default_topic"] == "aria/events"
    assert "password" not in dossier
    assert "user" not in dossier
    assert "host" not in dossier


def test_read_target_dossier_excludes_secrets_for_modular_agentic_resolution() -> None:
    dossier = build_read_target_dossier(
        {
            "ops-inbox": {
                "host": "imap.local",
                "user": "aria",
                "password": "secret",
                "mailbox": "INBOX",
                "aliases": ["ops inbox"],
            }
        },
        "ops-inbox",
        connection_kind="imap",
    )

    assert dossier["kind"] == "imap"
    assert dossier["connection_ref"] == "ops-inbox"
    assert dossier["mailbox"] == "INBOX"
    assert "password" not in dossier
    assert "user" not in dossier
    assert "host" not in dossier


def test_file_operation_from_action_uses_family_shape() -> None:
    assert file_operation_from_action({"plan_class": "file_read_basic"}) == "read"
    assert file_operation_from_action({"candidate_id": "smb_list_files"}) == "list"
    assert file_operation_from_action({}, "file_write") == "write"


def test_agentic_file_operation_resolution_updates_draft_without_executing() -> None:
    import asyncio
    from types import SimpleNamespace

    draft = SimpleNamespace(capability="file_read", connection_kind="sftp", path="", content="", notes=[])
    llm = _FileLLM()

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_file_operation_resolution(
            client=llm,
            message="lies die hosts datei",
            routing_decision={"kind": "sftp", "ref": "mgmt"},
            action_debug={"decision": {"candidate_kind": "template", "plan_class": "file_read_basic"}},
            capability_draft=draft,
            build_file_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "root_path": "/",
                "allowed_operations": ["list", "read", "write"],
            },
            extract_json_object=lambda text: __import__("json").loads(text),
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=lambda obj, **updates: [setattr(obj, key, value) for key, value in updates.items()] and obj,
        )
    )

    assert llm.operations == ["file_operation_decision"]
    assert "Agentic action contract for file_operation" in _first_system_prompt(llm)
    assert updated_draft.path == "/etc/hosts"
    assert updated_draft.capability == "file_read"
    assert "file_operation_decision" in debug_line
    assert "agentic_source=llm_decision" in debug_line
    assert action_debug["decision"]["inputs"] == {"remote_path": "/etc/hosts"}


def test_agentic_message_operation_resolution_updates_incomplete_draft_without_executing() -> None:
    import asyncio
    from types import SimpleNamespace

    draft = SimpleNamespace(capability="mqtt_publish", connection_kind="mqtt", path="", content="", notes=[])
    llm = _MessageLLM()

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_message_operation_resolution(
            client=llm,
            message="publiziere deployment fertig",
            routing_decision={"kind": "mqtt", "ref": "event-bus"},
            action_debug={"decision": {"candidate_kind": "template", "candidate_id": "mqtt_publish_message"}},
            capability_draft=draft,
            build_message_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "default_topic": "aria/events",
                "allowed_operations": ["publish"],
            },
            extract_json_object=lambda text: __import__("json").loads(text),
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=lambda obj, **updates: [setattr(obj, key, value) for key, value in updates.items()] and obj,
        )
    )

    assert llm.operations == ["message_operation_decision"]
    assert "Agentic action contract for outbound_message" in _first_system_prompt(llm)
    assert updated_draft.path == "aria/events"
    assert updated_draft.content == "Deployment finished"
    assert message_draft_is_complete(capability="mqtt_publish", topic=updated_draft.path, content=updated_draft.content)
    assert "message_operation_decision" in debug_line
    assert action_debug["decision"]["inputs"] == {"message": "Deployment finished", "topic": "aria/events"}


def test_agentic_read_operation_resolution_updates_missing_mail_search_query_without_executing() -> None:
    import asyncio
    from types import SimpleNamespace

    draft = SimpleNamespace(capability="mail_search", connection_kind="imap", path="", content="", notes=[])
    llm = _ReadLLM()

    action_debug, updated_draft, debug_line = asyncio.run(
        apply_agentic_read_operation_resolution(
            client=llm,
            message="suche im ops postfach nach backup fehlern",
            routing_decision={"kind": "imap", "ref": "ops-inbox"},
            action_debug={"decision": {"candidate_kind": "template", "plan_class": "mailbox_search_basic"}},
            capability_draft=draft,
            build_read_target_dossier=lambda kind, ref, user_id="": {
                "kind": kind,
                "connection_ref": ref,
                "mailbox": "INBOX",
                "allowed_operations": ["read", "search"],
            },
            extract_json_object=lambda text: __import__("json").loads(text),
            routing_debug_enabled=lambda: True,
            with_capability_draft_updates=lambda obj, **updates: [setattr(obj, key, value) for key, value in updates.items()] and obj,
        )
    )

    assert llm.operations == ["read_operation_decision"]
    assert "Agentic action contract for read_operation" in _first_system_prompt(llm)
    assert updated_draft.content == "backup failed"
    assert read_draft_is_complete(capability="mail_search", query=updated_draft.content)
    assert "read_operation_decision" in debug_line
    assert action_debug["decision"]["inputs"] == {"query": "backup failed"}


def test_agentic_http_request_resolution_uses_shared_contract_prompt() -> None:
    import asyncio
    import json

    llm = _HTTPLLM()

    resolved = asyncio.run(
        resolve_http_api_request_from_dossier(
            client=llm,
            message="prüf ob die api erreichbar ist",
            connection_ref="inventory-api",
            build_http_api_target_dossier=lambda ref, user_id="": {
                "connection_ref": ref,
                "health_path": "/health",
                "configured_method": "GET",
            },
            extract_json_object=json.loads,
        )
    )

    assert llm.operations == ["http_api_request_decision"]
    assert "Agentic action contract for http_api_request" in _first_system_prompt(llm)
    assert resolved["path"] == "/health"
