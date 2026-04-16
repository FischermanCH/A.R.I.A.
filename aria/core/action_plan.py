from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CapabilityDraft:
    capability: str
    connection_kind: str = "sftp"
    explicit_connection_ref: str = ""
    requested_connection_ref: str = ""
    path: str = ""
    content: str = ""
    confidence: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MemoryHints:
    connection_kind: str = ""
    connection_ref: str = ""
    path: str = ""
    source: str = ""
    matched_text: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ActionPlan:
    capability: str
    connection_kind: str
    connection_ref: str = ""
    requested_connection_ref: str = ""
    path: str = ""
    content: str = ""
    missing_fields: list[str] = field(default_factory=list)
    resolution_source: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields


def build_action_plan(
    draft: CapabilityDraft,
    hints: MemoryHints,
    *,
    available_connection_refs: list[str],
) -> ActionPlan:
    connection_kind = str(hints.connection_kind or draft.connection_kind or "sftp").strip().lower() or "sftp"
    requested_connection_ref = str(draft.requested_connection_ref or "").strip()
    connection_ref = draft.explicit_connection_ref or hints.connection_ref
    resolution_source = "explicit" if draft.explicit_connection_ref else (hints.source or "")

    if not connection_ref and not requested_connection_ref and len(available_connection_refs) == 1:
        connection_ref = available_connection_refs[0]
        resolution_source = resolution_source or "default_single_profile"

    if requested_connection_ref:
        if connection_ref and connection_ref.lower() == requested_connection_ref.lower():
            resolution_source = resolution_source or "requested_exact"
        else:
            connection_ref = ""
            resolution_source = "requested_missing"

    missing_fields: list[str] = []
    if not connection_ref:
        missing_fields.append("connection_ref")
    resolved_path = str(draft.path or "").strip() or str(hints.path or "").strip()
    if not resolved_path:
        if draft.capability == "file_list":
            path = "."
        elif draft.capability in {
            "feed_read",
            "webhook_send",
            "discord_send",
            "api_request",
            "mail_read",
            "mail_search",
            "email_send",
            "mqtt_publish",
            "ssh_command",
        }:
            path = ""
        else:
            missing_fields.append("path")
            path = ""
    else:
        path = resolved_path

    content = str(draft.content or "").strip()
    if draft.capability in {
        "file_write",
        "webhook_send",
        "discord_send",
        "email_send",
        "mail_search",
        "mqtt_publish",
        "ssh_command",
    } and not content:
        missing_fields.append("content")

    return ActionPlan(
        capability=draft.capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        requested_connection_ref=requested_connection_ref,
        path=path,
        content=content,
        missing_fields=missing_fields,
        resolution_source=resolution_source,
        notes=list(draft.notes) + list(hints.notes),
    )
