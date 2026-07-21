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
    plan_class: str = ""
    behavior_profile: str = ""
    confidence: float = 0.0
    connection_refs: list[str] = field(default_factory=list)
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
    plan_class: str = ""
    behavior_profile: str = ""
    missing_fields: list[str] = field(default_factory=list)
    resolution_source: str = ""
    notes: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields


def _requested_ref_is_soft_hint(value: str) -> bool:
    clean = str(value or "").strip().lower()
    if not clean:
        return False
    generic_tail_terms = (
        "channel",
        "kanal",
        "profile",
        "profil",
        "server",
        "mailbox",
        "inbox",
        "topic",
        "broker",
        "feed",
        "endpoint",
        "http",
        "api",
    )
    return " " in clean or clean.endswith(generic_tail_terms)


def build_action_plan(
    draft: CapabilityDraft,
    hints: MemoryHints,
    *,
    available_connection_refs: list[str],
) -> ActionPlan:
    draft_capability = str(getattr(draft, "capability", "") or "").strip()
    draft_connection_kind = str(getattr(draft, "connection_kind", "") or "").strip()
    draft_explicit_ref = str(getattr(draft, "explicit_connection_ref", "") or "").strip()
    draft_requested_ref = str(getattr(draft, "requested_connection_ref", "") or "").strip()
    draft_path = str(getattr(draft, "path", "") or "").strip()
    draft_content = str(getattr(draft, "content", "") or "").strip()
    draft_plan_class = str(getattr(draft, "plan_class", "") or "").strip().lower()
    draft_behavior_profile = str(getattr(draft, "behavior_profile", "") or "").strip().lower()
    draft_notes = list(getattr(draft, "notes", []) or [])

    connection_kind = str(hints.connection_kind or draft_connection_kind or "sftp").strip().lower() or "sftp"
    requested_connection_ref = draft_requested_ref
    connection_ref = draft_explicit_ref or hints.connection_ref
    resolution_source = "explicit" if draft_explicit_ref else (hints.source or "")

    if not connection_ref and not requested_connection_ref and len(available_connection_refs) == 1:
        connection_ref = available_connection_refs[0]
        resolution_source = resolution_source or "default_single_profile"

    if requested_connection_ref:
        if connection_ref and connection_ref.lower() == requested_connection_ref.lower():
            resolution_source = resolution_source or "requested_exact"
        elif connection_ref and _requested_ref_is_soft_hint(requested_connection_ref):
            requested_connection_ref = ""
            resolution_source = resolution_source or "requested_hint"
        else:
            connection_ref = ""
            resolution_source = "requested_missing"

    missing_fields: list[str] = []
    if not connection_ref and draft_capability != "website_list":
        missing_fields.append("connection_ref")
    resolved_path = draft_path or str(hints.path or "").strip()
    if not resolved_path:
        if draft_capability == "file_list":
            path = "."
        elif draft_capability in {
            "feed_read",
            "website_read",
            "website_list",
            "calendar_read",
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

    content = draft_content
    if draft_capability in {
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
        capability=draft_capability,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        requested_connection_ref=requested_connection_ref,
        path=path,
        content=content,
        plan_class=draft_plan_class,
        behavior_profile=draft_behavior_profile,
        missing_fields=missing_fields,
        resolution_source=resolution_source,
        notes=draft_notes + list(hints.notes),
    )
