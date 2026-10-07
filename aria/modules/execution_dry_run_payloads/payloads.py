from __future__ import annotations

from typing import Any

from aria.modules.action_planner_templates.taxonomy import is_recipe_candidate_kind
from aria.modules.action_contracts.plan import MemoryHints, build_action_plan
from aria.modules.connections_catalog.catalog import normalize_connection_kind
from aria.modules.recipe_store.manifests import load_stored_recipe_manifests
from aria.modules.execution_dry_run_payloads.template_payloads import apply_template_connection_defaults
from aria.modules.execution_dry_run_payloads.template_payloads import resolved_behavior_profile
from aria.modules.execution_dry_run_payloads.template_payloads import resolved_template_plan_class
from aria.modules.execution_dry_run_payloads.template_payloads import template_draft
from aria.modules.recipe_runtime.contracts import RECIPE_EXECUTION_CAPABILITY
from aria.modules.recipe_runtime.contracts import RECIPE_MANIFEST_SOURCE
from aria.modules.recipe_runtime.stored_manifest_view import stored_recipe_candidate_metadata


def read_row_value(row: Any, name: str) -> str:
    if isinstance(row, dict):
        return str(row.get(name, "") or "").strip()
    return str(getattr(row, name, "") or "").strip()


def read_row_list(row: Any, name: str) -> list[str]:
    if isinstance(row, dict):
        value = row.get(name, [])
    else:
        value = getattr(row, name, [])
    return [str(item or "").strip() for item in list(value or []) if str(item or "").strip()]


def connection_row(settings: Any, kind: str, ref: str) -> Any | None:
    rows = getattr(getattr(settings, "connections", object()), str(kind or "").strip().lower(), {})
    if not isinstance(rows, dict):
        return None
    return rows.get(ref)


def find_stored_recipe_manifest(skill_id: str) -> dict[str, Any] | None:
    clean_id = str(skill_id or "").strip()
    if not clean_id:
        return None
    manifests, _ = load_stored_recipe_manifests()
    for manifest in manifests:
        if str(manifest.get("id", "") or "").strip() == clean_id:
            return manifest
    return None


def find_skill_manifest(skill_id: str) -> dict[str, Any] | None:
    return find_stored_recipe_manifest(skill_id)


def skill_first_step_preview(manifest: dict[str, Any] | None) -> tuple[str, str, str]:
    if not isinstance(manifest, dict):
        return "", "", ""
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return "", "", ""
    first = dict((steps[0] or {}))
    step_type = str(first.get("type", "") or "").strip().lower()
    params = dict(first.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        return "ssh_command", command, f"SSH command: {command}" if command else "SSH command from stored recipe"
    if step_type in {"sftp_read", "smb_read"}:
        path = str(params.get("remote_path", "") or "").strip()
        return "file_read", path, f"Read remote path: {path}" if path else "Read remote file from stored recipe"
    if step_type in {"sftp_write", "smb_write"}:
        path = str(params.get("remote_path", "") or "").strip()
        return "file_write", path, f"Write remote path: {path}" if path else "Write remote file from stored recipe"
    if step_type == "discord_send":
        message = str(params.get("message", "") or "").strip()
        return "discord_send", message, f"Discord message: {message}" if message else "Discord message from stored recipe"
    if step_type == "rss_read":
        return "feed_read", "", "Read feed via stored recipe"
    return "", "", step_type or "Stored recipe step"


def plan_to_payload(
    plan: Any,
    *,
    preview: str = "",
    source: str = "structured_contract",
    plan_class: str = "",
    behavior_profile: str = "",
) -> dict[str, Any]:
    return {
        "found": True,
        "capability": str(plan.capability or "").strip(),
        "connection_kind": str(plan.connection_kind or "").strip(),
        "connection_ref": str(plan.connection_ref or "").strip(),
        "requested_connection_ref": str(plan.requested_connection_ref or "").strip(),
        "path": str(plan.path or "").strip(),
        "content": str(plan.content or "").strip(),
        "missing_fields": list(plan.missing_fields),
        "resolution_source": str(plan.resolution_source or "").strip(),
        "notes": list(plan.notes),
        "preview": str(preview or "").strip(),
        "source": source,
        "plan_class": str(plan_class or "").strip(),
        "behavior_profile": str(behavior_profile or "").strip(),
    }


def _apply_action_missing_input_contract(payload: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    missing_input = str(action.get("missing_input", "") or "").strip()
    if not missing_input:
        return payload

    field_by_input = {
        "command": "content",
        "message": "content",
        "search_query": "content",
        "remote_path": "path",
        "topic": "path",
    }
    payload_field = field_by_input.get(missing_input, "")
    if payload_field:
        payload[payload_field] = ""

    missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or [])]
    if payload_field and payload_field != missing_input:
        missing_fields = [item for item in missing_fields if item != payload_field]
    if missing_input not in missing_fields:
        missing_fields.append(missing_input)
    payload["missing_fields"] = [item for item in missing_fields if item]
    payload["preview"] = str(action.get("preview", "") or payload.get("preview", "") or "").strip()
    payload["source"] = "action_contract"
    return payload


def build_payload_dry_run(
    query: str,
    *,
    settings: Any,
    routing_decision: dict[str, Any] | None = None,
    action_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    routing = dict(routing_decision or {})
    action = dict(action_decision or {})
    if not bool(routing.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Payload dry-run skipped: no routing target was resolved first.",
            "payload": {},
        }
    if not bool(action.get("found")):
        return {
            "available": True,
            "used": False,
            "status": "warn",
            "visual_status": "warn",
            "message": "Payload dry-run skipped: no action or recipe candidate was selected first.",
            "payload": {},
        }

    connection_kind = normalize_connection_kind(str(routing.get("kind", "") or ""))
    connection_ref = str(routing.get("ref", "") or "").strip()
    candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
    candidate_id = str(action.get("candidate_id", "") or "").strip()
    plan_class = str(action.get("plan_class", "") or "").strip().lower()
    behavior_profile = str(action.get("behavior_profile", "") or "").strip().lower()
    if not behavior_profile:
        behavior_profile = resolved_behavior_profile(plan_class=plan_class, candidate_id=candidate_id)

    if candidate_kind == "template":
        draft, preview = template_draft(
            query,
            candidate_id=candidate_id,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            plan_class=plan_class,
            inputs=dict(action.get("inputs", {}) or {}),
        )
        draft, preview = apply_template_connection_defaults(
            settings=settings,
            candidate_id=candidate_id,
            plan_class=plan_class,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            draft=draft,
            preview=preview,
            connection_row=lambda kind, ref: connection_row(settings, kind, ref),
            read_row_value=read_row_value,
        )
        hints = MemoryHints(connection_kind=connection_kind, connection_ref=connection_ref, source="routing_dry_run")
        plan = build_action_plan(draft, hints, available_connection_refs=[connection_ref] if connection_ref else [])
        payload = plan_to_payload(
            plan,
            preview=preview,
            source="template_contract",
            plan_class=plan_class or resolved_template_plan_class(candidate_id=candidate_id),
            behavior_profile=behavior_profile or resolved_behavior_profile(plan_class=plan_class, candidate_id=candidate_id),
        )
        payload = _apply_action_missing_input_contract(payload, action)
        status = "ok" if not payload["missing_fields"] else "warn"
        message = "Payload dry-run built a concrete executor payload." if status == "ok" else "Payload dry-run still needs one or more parameters."
        return {
            "available": True,
            "used": True,
            "status": status,
            "visual_status": status,
            "message": message,
            "payload": payload,
        }

    if is_recipe_candidate_kind(candidate_kind):
        manifest = find_stored_recipe_manifest(candidate_id)
        capability, raw_value, preview = skill_first_step_preview(manifest)
        metadata = stored_recipe_candidate_metadata(
            manifest or {},
            fallback_connection_kind=connection_kind,
        )
        payload = {
            "found": True,
            "capability": capability or RECIPE_EXECUTION_CAPABILITY,
            "connection_kind": connection_kind,
            "connection_ref": connection_ref,
            "requested_connection_ref": "",
            "path": raw_value if capability in {"file_read", "file_write"} else "",
            "content": raw_value if capability in {"ssh_command", "discord_send"} else "",
            "missing_fields": [],
            "resolution_source": RECIPE_MANIFEST_SOURCE,
            "notes": [],
            "preview": preview,
            "source": RECIPE_MANIFEST_SOURCE,
            "skill_id": candidate_id,
            "skill_name": str((manifest or {}).get("name", "") or "").strip(),
            **metadata,
        }
        return {
            "available": True,
            "used": True,
            "status": "ok" if manifest else "warn",
            "visual_status": "ok" if manifest else "warn",
            "message": (
                "Payload dry-run resolved the selected stored recipe preview."
                if manifest
                else "Payload dry-run could not load the selected stored recipe manifest."
            ),
            "payload": payload,
        }

    return {
        "available": True,
        "used": False,
        "status": "warn",
        "visual_status": "warn",
        "message": "Payload dry-run skipped: unsupported action candidate type.",
        "payload": {},
    }
