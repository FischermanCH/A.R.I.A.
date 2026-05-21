from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.core.connection_action_contract import ConnectionActionContract
from aria.core.connection_action_contract import connection_action_contracts
from aria.core.connection_catalog import normalize_connection_kind

PROVIDER_MANIFEST_SCHEMA_VERSION = "0.2"

_DEFAULT_AUTH_MODES: dict[str, tuple[str, ...]] = {
    "ssh": ("ssh_key", "password"),
    "sftp": ("ssh_key", "password"),
    "smb": ("username_password",),
    "http_api": ("api_key", "bearer_token", "none"),
    "webhook": ("url_secret", "none"),
    "discord": ("bot_token", "webhook_url"),
    "email": ("smtp_credentials",),
    "mqtt": ("username_password", "none"),
    "rss": ("none",),
    "google_calendar": ("oauth2",),
    "imap": ("username_password", "oauth2"),
    "website": ("none",),
}


@dataclass(frozen=True, slots=True)
class ConnectionProviderCapabilityManifest:
    capability: str
    family: str
    operation: str
    planner_role: str
    policy_family: str
    guardrail_kind: str = ""
    required_fields: tuple[str, ...] = field(default_factory=tuple)
    payload_fields: tuple[dict[str, str], ...] = field(default_factory=tuple)
    side_effect: bool = False
    confirmation_required: bool = False
    sensitive_content: bool = False
    draft_capability: str = ""
    direct_capability_gate: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "family": self.family,
            "operation": self.operation,
            "planner_role": self.planner_role,
            "policy_family": self.policy_family,
            "guardrail_kind": self.guardrail_kind,
            "required_fields": list(self.required_fields),
            "payload_fields": [dict(item) for item in self.payload_fields],
            "side_effect": self.side_effect,
            "confirmation_required": self.confirmation_required,
            "sensitive_content": self.sensitive_content,
            "draft_capability": self.draft_capability,
            "direct_capability_gate": self.direct_capability_gate,
        }


@dataclass(frozen=True, slots=True)
class ConnectionProviderManifest:
    connection_kind: str
    provider_id: str
    display_name: str
    runtime_adapter: str
    auth_modes: tuple[str, ...] = field(default_factory=tuple)
    capabilities: tuple[ConnectionProviderCapabilityManifest, ...] = field(default_factory=tuple)
    schema_version: str = PROVIDER_MANIFEST_SCHEMA_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider_id": self.provider_id,
            "connection_kind": self.connection_kind,
            "display_name": self.display_name,
            "runtime_adapter": self.runtime_adapter,
            "auth_modes": list(self.auth_modes),
            "capabilities": [capability.as_dict() for capability in self.capabilities],
        }


def _provider_display_name(connection_kind: str) -> str:
    return {
        "ssh": "SSH",
        "sftp": "SFTP",
        "smb": "SMB",
        "http_api": "HTTP API",
        "webhook": "Webhook",
        "discord": "Discord",
        "email": "Email",
        "mqtt": "MQTT",
        "rss": "RSS",
        "google_calendar": "Google Calendar",
        "imap": "IMAP",
        "website": "Website",
    }.get(connection_kind, connection_kind.replace("_", " ").title())


def _capability_manifest_from_contract(contract: ConnectionActionContract) -> ConnectionProviderCapabilityManifest:
    return ConnectionProviderCapabilityManifest(
        capability=contract.capability,
        family=contract.family,
        operation=contract.operation,
        planner_role=contract.planner_role,
        policy_family=contract.policy_family,
        guardrail_kind=contract.guardrail_kind,
        required_fields=tuple(contract.required_fields),
        payload_fields=tuple({"payload": key, "plan": value} for key, value in contract.payload_fields),
        side_effect=contract.side_effect,
        confirmation_required=contract.confirmation_required,
        sensitive_content=contract.sensitive_content,
        draft_capability=contract.draft_capability,
        direct_capability_gate=contract.direct_capability_gate,
    )


def build_connection_provider_manifests(
    contracts: list[ConnectionActionContract] | None = None,
) -> list[ConnectionProviderManifest]:
    grouped: dict[str, list[ConnectionProviderCapabilityManifest]] = {}
    for contract in list(contracts or connection_action_contracts()):
        capability_manifest = _capability_manifest_from_contract(contract)
        for executor in contract.executors:
            connection_kind = normalize_connection_kind(executor)
            if not connection_kind:
                continue
            grouped.setdefault(connection_kind, []).append(capability_manifest)

    manifests: list[ConnectionProviderManifest] = []
    for connection_kind in sorted(grouped):
        capabilities = tuple(sorted(grouped[connection_kind], key=lambda item: item.capability))
        manifests.append(
            ConnectionProviderManifest(
                connection_kind=connection_kind,
                provider_id=f"builtin.{connection_kind}",
                display_name=_provider_display_name(connection_kind),
                runtime_adapter=f"builtin.{connection_kind}",
                auth_modes=tuple(_DEFAULT_AUTH_MODES.get(connection_kind, ("custom",))),
                capabilities=capabilities,
            )
        )
    return manifests


def connection_provider_manifest_rows() -> list[dict[str, Any]]:
    return [manifest.as_dict() for manifest in build_connection_provider_manifests()]


def validate_connection_provider_manifest(source: dict[str, Any] | None) -> list[str]:
    manifest = dict(source or {})
    errors: list[str] = []
    if str(manifest.get("schema_version", "") or "").strip() != PROVIDER_MANIFEST_SCHEMA_VERSION:
        errors.append("schema_version")
    connection_kind = normalize_connection_kind(str(manifest.get("connection_kind", "") or ""))
    if not connection_kind:
        errors.append("connection_kind")
    if not str(manifest.get("provider_id", "") or "").strip():
        errors.append("provider_id")
    if not str(manifest.get("runtime_adapter", "") or "").strip():
        errors.append("runtime_adapter")
    auth_modes = manifest.get("auth_modes", [])
    if not isinstance(auth_modes, list) or not [item for item in auth_modes if str(item or "").strip()]:
        errors.append("auth_modes")
    capabilities = manifest.get("capabilities", [])
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("capabilities")
        return errors
    for index, capability in enumerate(capabilities):
        if not isinstance(capability, dict):
            errors.append(f"capabilities[{index}]")
            continue
        prefix = f"capabilities[{index}]"
        for key in ("capability", "family", "operation", "planner_role", "policy_family"):
            if not str(capability.get(key, "") or "").strip():
                errors.append(f"{prefix}.{key}")
        if not isinstance(capability.get("required_fields", []), list):
            errors.append(f"{prefix}.required_fields")
        payload_fields = capability.get("payload_fields", [])
        if not isinstance(payload_fields, list):
            errors.append(f"{prefix}.payload_fields")
        else:
            for field_index, item in enumerate(payload_fields):
                if not isinstance(item, dict) or not str(item.get("payload", "") or "").strip() or not str(item.get("plan", "") or "").strip():
                    errors.append(f"{prefix}.payload_fields[{field_index}]")
        if not isinstance(capability.get("side_effect", False), bool):
            errors.append(f"{prefix}.side_effect")
        if not isinstance(capability.get("confirmation_required", False), bool):
            errors.append(f"{prefix}.confirmation_required")
        if not isinstance(capability.get("sensitive_content", False), bool):
            errors.append(f"{prefix}.sensitive_content")
        if "draft_capability" in capability and not isinstance(capability.get("draft_capability", ""), str):
            errors.append(f"{prefix}.draft_capability")
        if not isinstance(capability.get("direct_capability_gate", True), bool):
            errors.append(f"{prefix}.direct_capability_gate")
        if bool(capability.get("side_effect", False)) and str(capability.get("policy_family", "") or "").strip() == "read_only":
            errors.append(f"{prefix}.side_effect_policy")
        if bool(capability.get("side_effect", False)) and not bool(capability.get("confirmation_required", False)):
            errors.append(f"{prefix}.side_effect_confirmation")
    return errors
