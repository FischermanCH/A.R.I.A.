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
    executors: tuple[str, ...] = field(default_factory=tuple)
    policy_family: str = ""
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    payload_fields: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    side_effect: bool = False

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
            "executors": list(self.executors),
            "policy_family": self.policy_family,
            "required_fields": list(self.required_fields),
            "payload_fields": [{"payload": key, "plan": attr} for key, attr in self.payload_fields],
            "side_effect": self.side_effect,
        }


def _contract(
    capability: str,
    *,
    family: str,
    operation: str,
    policy_family: str,
    required_fields: tuple[str, ...] = ("connection_ref",),
    payload_fields: tuple[tuple[str, str], ...] = (),
    side_effect: bool = False,
) -> ConnectionActionContract:
    clean_capability = normalize_capability(capability)
    return ConnectionActionContract(
        capability=clean_capability,
        family=str(family or "").strip().lower(),
        operation=str(operation or "").strip().lower(),
        executors=tuple(capability_executor_kinds(clean_capability)),
        policy_family=str(policy_family or "").strip().lower(),
        required_fields=tuple(str(item or "").strip() for item in required_fields if str(item or "").strip()),
        payload_fields=tuple(
            (str(key or "").strip(), str(attr or "").strip())
            for key, attr in payload_fields
            if str(key or "").strip() and str(attr or "").strip()
        ),
        side_effect=bool(side_effect),
    )


_CONNECTION_ACTION_CONTRACTS: dict[str, ConnectionActionContract] = {
    "ssh_command": _contract(
        "ssh_command",
        family="command",
        operation="run_command",
        policy_family="ssh_readonly",
        required_fields=("connection_ref", "content"),
        payload_fields=(("command", "content"),),
    ),
    "api_request": _contract(
        "api_request",
        family="request",
        operation="request",
        policy_family="http_api",
        payload_fields=(("path", "path"), ("content", "content")),
    ),
    "file_list": _contract(
        "file_list",
        family="file",
        operation="list",
        policy_family="file_access",
        payload_fields=(("path", "path"),),
    ),
    "file_read": _contract(
        "file_read",
        family="file",
        operation="read",
        policy_family="file_access",
        required_fields=("connection_ref", "path"),
        payload_fields=(("path", "path"),),
    ),
    "file_write": _contract(
        "file_write",
        family="file",
        operation="write",
        policy_family="file_access",
        required_fields=("connection_ref", "path", "content"),
        payload_fields=(("path", "path"), ("content", "content")),
        side_effect=True,
    ),
    "webhook_send": _contract(
        "webhook_send",
        family="message",
        operation="send",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("message", "content"),),
        side_effect=True,
    ),
    "discord_send": _contract(
        "discord_send",
        family="message",
        operation="send",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("message", "content"),),
        side_effect=True,
    ),
    "email_send": _contract(
        "email_send",
        family="message",
        operation="send",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("message", "content"),),
        side_effect=True,
    ),
    "mqtt_publish": _contract(
        "mqtt_publish",
        family="message",
        operation="publish",
        policy_family="message_confirm",
        required_fields=("connection_ref", "content"),
        payload_fields=(("topic", "path"), ("message", "content")),
        side_effect=True,
    ),
    "feed_read": _contract(
        "feed_read",
        family="read",
        operation="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "calendar_read": _contract(
        "calendar_read",
        family="read",
        operation="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "mail_read": _contract(
        "mail_read",
        family="read",
        operation="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "mail_search": _contract(
        "mail_search",
        family="read",
        operation="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "website_read": _contract(
        "website_read",
        family="read",
        operation="read",
        policy_family="read_only",
        payload_fields=(("selector", "path"), ("query", "content")),
    ),
    "website_list": _contract(
        "website_list",
        family="read",
        operation="read",
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


def connection_action_binding_is_supported(connection_kind: str, capability: str) -> bool:
    clean_kind = normalize_connection_kind(connection_kind)
    contract = connection_action_contract(capability)
    if contract is None:
        return False
    return clean_kind in set(contract.executors)


def runtime_operation_for_capability(capability: str) -> str:
    contract = connection_action_contract(capability)
    return contract.operation if contract is not None else normalize_capability(capability) or "execute"


def runtime_payload_for_action_plan(plan: ActionPlan) -> dict[str, Any]:
    contract = connection_action_contract(str(getattr(plan, "capability", "") or ""))
    if contract is None:
        return {}
    return contract.payload_for_plan(plan)
