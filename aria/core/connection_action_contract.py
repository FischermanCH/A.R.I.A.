from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import capability_executor_kinds
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind


@dataclass(frozen=True, slots=True)
class ConnectionActionContract:
    capability: str
    family: str
    operation: str
    planner_role: str = ""
    executors: tuple[str, ...] = field(default_factory=tuple)
    policy_family: str = ""
    guardrail_kind: str = ""
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    payload_fields: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    side_effect: bool = False
    confirmation_required: bool = False
    sensitive_content: bool = False
    draft_capability: str = ""
    direct_capability_gate: bool = True

    def payload_for_plan(self, plan: ActionPlan) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for payload_key, plan_attr in self.payload_fields:
            clean_key = str(payload_key or "").strip()
            clean_attr = str(plan_attr or "").strip()
            if not clean_key or not clean_attr:
                continue
            payload[clean_key] = str(getattr(plan, clean_attr, "") or "").strip()
        return payload

    def manifest_row(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "family": self.family,
            "operation": self.operation,
            "planner_role": self.planner_role,
            "executors": list(self.executors),
            "policy_family": self.policy_family,
            "guardrail_kind": self.guardrail_kind,
            "required_fields": list(self.required_fields),
            "payload_fields": [{"payload": key, "plan": attr} for key, attr in self.payload_fields],
            "side_effect": self.side_effect,
            "confirmation_required": self.confirmation_required,
            "sensitive_content": self.sensitive_content,
            "draft_capability": self.draft_capability,
            "direct_capability_gate": self.direct_capability_gate,
        }


def _contract(
    capability: str,
    *,
    family: str,
    operation: str,
    planner_role: str = "",
    policy_family: str,
    guardrail_kind: str = "",
    required_fields: tuple[str, ...] = ("connection_ref",),
    payload_fields: tuple[tuple[str, str], ...] = (),
    side_effect: bool = False,
    confirmation_required: bool | None = None,
    sensitive_content: bool = False,
    draft_capability: str = "",
    direct_capability_gate: bool = True,
) -> ConnectionActionContract:
    clean_capability = normalize_capability(capability)
    clean_planner_role = str(planner_role or operation or family).strip().lower()
    return ConnectionActionContract(
        capability=clean_capability,
        family=str(family or "").strip().lower(),
        operation=str(operation or "").strip().lower(),
        planner_role=clean_planner_role,
        executors=tuple(capability_executor_kinds(clean_capability)),
        policy_family=str(policy_family or "").strip().lower(),
        guardrail_kind=str(guardrail_kind or "").strip().lower(),
        required_fields=tuple(str(item or "").strip() for item in required_fields if str(item or "").strip()),
        payload_fields=tuple(
            (str(key or "").strip(), str(attr or "").strip())
            for key, attr in payload_fields
            if str(key or "").strip() and str(attr or "").strip()
        ),
        side_effect=bool(side_effect),
        confirmation_required=bool(side_effect) if confirmation_required is None else bool(confirmation_required),
        sensitive_content=bool(sensitive_content),
        draft_capability=normalize_capability(draft_capability),
        direct_capability_gate=bool(direct_capability_gate),
    )


_CONNECTION_ACTION_CONTRACTS: dict[str, ConnectionActionContract] = {
    "ssh_command": _contract(
        "ssh_command",
        family="command",
        operation="run_command",
        planner_role="command",
        policy_family="ssh_readonly",
        guardrail_kind="ssh_command",
        required_fields=("connection_ref", "content"),
        payload_fields=(("command", "content"),),
        direct_capability_gate=False,
    ),
    "api_request": _contract(
        "api_request",
        family="request",
        operation="request",
        planner_role="request",
        policy_family="http_api",
        guardrail_kind="http_request",
        payload_fields=(("path", "path"), ("content", "content")),
    ),
    "file_list": _contract(
        "file_list",
        family="file",
        operation="list",
        planner_role="list",
        policy_family="file_access",
        guardrail_kind="file_access",
        payload_fields=(("path", "path"),),
    ),
    "file_read": _contract(
        "file_read",
        family="file",
        operation="read",
        planner_role="read",
        policy_family="file_access",
        guardrail_kind="file_access",
        required_fields=("connection_ref", "path"),
        payload_fields=(("path", "path"),),
        sensitive_content=True,
    ),
    "file_write": _contract(
        "file_write",
        family="file",
        operation="write",
        planner_role="write",
        policy_family="file_access",
        guardrail_kind="file_access",
        required_fields=("connection_ref", "path", "content"),
        payload_fields=(("path", "path"), ("content", "content")),
        side_effect=True,
    ),
    "webhook_send": _contract(
        "webhook_send",
        family="message",
        operation="send",
        planner_role="send",
        policy_family="message_confirm",
        guardrail_kind="http_request",
        required_fields=("connection_ref", "content"),
        payload_fields=(("message", "content"),),
        side_effect=True,
    ),
    "discord_send": _contract(
        "discord_send",
        family="message",
        operation="send",
        planner_role="send",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("message", "content"),),
        side_effect=True,
    ),
    "email_send": _contract(
        "email_send",
        family="message",
        operation="send",
        planner_role="send",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("to", "path"), ("message", "content")),
        side_effect=True,
        draft_capability="email_draft",
    ),
    "mqtt_publish": _contract(
        "mqtt_publish",
        family="message",
        operation="publish",
        planner_role="publish",
        policy_family="message_confirm",
        guardrail_kind="mqtt_publish",
        required_fields=("connection_ref", "content"),
        payload_fields=(("topic", "path"), ("message", "content")),
        side_effect=True,
    ),
    "feed_read": _contract(
        "feed_read",
        family="read",
        operation="read",
        planner_role="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "calendar_read": _contract(
        "calendar_read",
        family="read",
        operation="read",
        planner_role="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
        direct_capability_gate=False,
    ),
    "mail_read": _contract(
        "mail_read",
        family="read",
        operation="read",
        planner_role="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
        sensitive_content=True,
    ),
    "mail_search": _contract(
        "mail_search",
        family="read",
        operation="read",
        planner_role="search",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
        sensitive_content=True,
    ),
    "website_read": _contract(
        "website_read",
        family="read",
        operation="read",
        planner_role="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "website_list": _contract(
        "website_list",
        family="read",
        operation="read",
        planner_role="list",
        policy_family="read_only",
        required_fields=(),
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
}


def connection_action_contract(capability: str) -> ConnectionActionContract | None:
    return _CONNECTION_ACTION_CONTRACTS.get(normalize_capability(capability))


def connection_action_contracts() -> list[ConnectionActionContract]:
    return list(_CONNECTION_ACTION_CONTRACTS.values())


def connection_action_manifest_rows() -> list[dict[str, Any]]:
    return [contract.manifest_row() for contract in connection_action_contracts()]


def connection_action_executor_bindings() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for contract in connection_action_contracts():
        for executor in contract.executors:
            clean_kind = normalize_connection_kind(executor)
            if clean_kind:
                rows.append((clean_kind, contract.capability))
    return rows


def connection_action_executor_kinds() -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for connection_kind, _capability in connection_action_executor_bindings():
        if connection_kind in seen:
            continue
        seen.add(connection_kind)
        rows.append(connection_kind)
    return tuple(rows)


def connection_action_direct_gate_executor_kinds() -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for contract in connection_action_contracts():
        if not contract.direct_capability_gate:
            continue
        for executor in contract.executors:
            clean_kind = normalize_connection_kind(executor)
            if not clean_kind or clean_kind in seen:
                continue
            seen.add(clean_kind)
            rows.append(clean_kind)
    return tuple(rows)


def connection_action_capabilities_by_family(family: str) -> tuple[str, ...]:
    clean_family = str(family or "").strip().lower()
    rows: list[str] = []
    for contract in connection_action_contracts():
        if contract.family != clean_family:
            continue
        rows.append(contract.capability)
    return tuple(rows)


def connection_action_capabilities_by_planner_role(planner_role: str) -> tuple[str, ...]:
    clean_role = str(planner_role or "").strip().lower()
    rows: list[str] = []
    for contract in connection_action_contracts():
        if contract.planner_role != clean_role:
            continue
        rows.append(contract.capability)
    return tuple(rows)


def connection_action_capability_for_executor_family(connection_kind: str, family: str) -> str:
    clean_kind = normalize_connection_kind(connection_kind)
    clean_family = str(family or "").strip().lower()
    for contract in connection_action_contracts():
        if contract.family != clean_family:
            continue
        if clean_kind in set(contract.executors):
            return contract.capability
    return ""


def connection_action_binding_is_supported(connection_kind: str, capability: str) -> bool:
    clean_kind = normalize_connection_kind(connection_kind)
    contract = connection_action_contract(capability)
    if contract is None:
        return False
    return clean_kind in set(contract.executors)


def runtime_operation_for_capability(capability: str) -> str:
    contract = connection_action_contract(capability)
    return contract.operation if contract is not None else normalize_capability(capability) or "execute"


def guardrail_kind_for_capability(capability: str) -> str:
    contract = connection_action_contract(capability)
    return contract.guardrail_kind if contract is not None else ""


def confirmation_required_for_capability(capability: str) -> bool:
    contract = connection_action_contract(capability)
    return bool(contract.confirmation_required) if contract is not None else False


def sensitive_content_for_capability(capability: str) -> bool:
    contract = connection_action_contract(capability)
    return bool(contract.sensitive_content) if contract is not None else False


def draft_capability_for_capability(capability: str) -> str:
    contract = connection_action_contract(capability)
    return contract.draft_capability if contract is not None else ""


def runtime_payload_for_action_plan(plan: ActionPlan) -> dict[str, Any]:
    contract = connection_action_contract(str(getattr(plan, "capability", "") or ""))
    if contract is None:
        return {}
    return contract.payload_for_plan(plan)
