from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore
from aria.core.connection_action_contract import connection_action_contract
from aria.core.learned_recipe_store import load_learned_recipe_store_entries
from aria.core.learned_recipe_store import update_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry
from aria.core.stored_recipes import sanitize_recipe_id, save_stored_recipe_manifest

_LEARNED_PROMOTION_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _promotion_text(key: str, default: str = "", **values: object) -> str:
    template = _LEARNED_PROMOTION_I18N.t("de", f"learned_recipe_promotion.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _stored_recipe_id_from_learned_entry(entry: dict[str, Any]) -> str:
    explicit = str(entry.get("stored_recipe_id", "") or "").strip()
    if explicit:
        return sanitize_recipe_id(explicit)
    recipe_id = str(entry.get("recipe_id", "") or "").strip()
    if recipe_id.startswith("learned-"):
        recipe_id = recipe_id[len("learned-") :]
    return sanitize_recipe_id(recipe_id or str(entry.get("title", "") or ""))


def _stored_recipe_category(entry: dict[str, Any]) -> str:
    capability = str(entry.get("capability", "") or "").strip().lower()
    if capability == "ssh_command":
        return "monitoring"
    if capability in {"discord_send", "email_send", "webhook_send", "mqtt_publish"}:
        return "communication"
    if capability == "feed_read":
        return "knowledge"
    return "automation"


def _unique_recipe_keywords(*sources: Any) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for source in sources:
        for item in list(source or []) if isinstance(source, list) else []:
            clean = str(item or "").strip()[:80]
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            rows.append(clean)
    return rows


def _promoted_step(entry: dict[str, Any]) -> dict[str, Any]:
    capability = str(entry.get("capability", "") or "").strip().lower()
    connection_kind = str(entry.get("connection_kind", "") or "").strip().lower()
    connection_ref = str(entry.get("connection_ref", "") or "").strip()
    chosen_action = str(entry.get("chosen_action", "") or "").strip()
    inputs = entry.get("inputs", {})
    if not isinstance(inputs, dict):
        inputs = {}

    if capability == "ssh_command":
        command = str(inputs.get("command", "") or chosen_action).strip()
        if not command:
            raise ValueError(_promotion_text("ssh_command_missing", "Learned recipe cannot be promoted: SSH command is missing."))
        return {
            "id": "s1",
            "name": "SSH Check",
            "type": "ssh_run",
            "params": {
                "connection_ref": connection_ref,
                "command": command,
            },
            "on_error": "stop",
        }

    if capability == "feed_read":
        return {
            "id": "s1",
            "name": "Feed lesen",
            "type": "rss_read",
            "params": {
                "connection_ref": connection_ref,
            },
            "on_error": "stop",
        }

    if capability == "discord_send":
        message = str(inputs.get("message", "") or chosen_action).strip()
        if not message:
            raise ValueError(_promotion_text("discord_message_missing", "Learned recipe cannot be promoted: Discord message is missing."))
        return {
            "id": "s1",
            "name": "Discord senden",
            "type": "discord_send",
            "params": {
                "connection_ref": connection_ref,
                "message": message,
            },
            "on_error": "stop",
        }

    if capability in {"file_read", "file_write"} and connection_kind in {"sftp", "smb"}:
        remote_path = str(inputs.get("remote_path", "") or chosen_action).strip()
        if not remote_path:
            raise ValueError(_promotion_text("remote_path_missing", "Learned recipe cannot be promoted: remote path is missing."))
        step_type = f"{connection_kind}_{'read' if capability == 'file_read' else 'write'}"
        params = {
            "connection_ref": connection_ref,
            "remote_path": remote_path,
        }
        if capability == "file_write":
            content = str(inputs.get("content", "") or "").strip()
            if not content:
                raise ValueError(_promotion_text("write_content_missing", "Learned recipe cannot be promoted: write content is missing."))
            params["content"] = content
        return {
            "id": "s1",
            "name": "Dateiaktion",
            "type": step_type,
            "params": params,
            "on_error": "stop",
        }

    raise ValueError(_promotion_text("unsupported_capability", "Learned recipe cannot yet be promoted for capability `{capability}`.", capability=capability))


def build_stored_recipe_manifest_from_learned_entry(entry: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_learned_recipe_store_entry(entry)
    stored_recipe_id = _stored_recipe_id_from_learned_entry(normalized)
    if not stored_recipe_id:
        raise ValueError(_promotion_text("recipe_id_missing", "Learned recipe cannot be promoted: recipe ID is missing."))
    summary = str(normalized.get("summary", "") or normalized.get("experience_summary", "") or "").strip()
    title = str(normalized.get("title", "") or "").strip() or stored_recipe_id.replace("-", " ").title()
    router_keywords = normalized.get("router_keywords", [])
    if not isinstance(router_keywords, list):
        router_keywords = []
    suggested_triggers = normalized.get("suggested_triggers", [])
    if not isinstance(suggested_triggers, list):
        suggested_triggers = []
    connection_kind = str(normalized.get("connection_kind", "") or "").strip().lower()

    return {
        "id": stored_recipe_id,
        "name": title[:80],
        "version": "0.1.0",
        "description": summary[:400] or "Promoted from learned recipe.",
        "category": _stored_recipe_category(normalized),
        "prompt_file": "",
        "router_keywords": _unique_recipe_keywords(router_keywords, suggested_triggers),
        "connections": [connection_kind] if connection_kind else [],
        "enabled_default": True,
        "steps": [_promoted_step(normalized)],
        "schedule": {
            "enabled": False,
            "cron": "",
            "timezone": "Europe/Zurich",
            "run_on_startup": False,
        },
        "ui": {
            "config_path": "",
            "hint": f"Promoted from learned recipe {normalized.get('recipe_id', '')}".strip(),
        },
        "schema_version": "1.1",
    }


def _learned_recipe_by_id(recipe_id: str) -> dict[str, Any]:
    clean_recipe_id = str(recipe_id or "").strip()
    if not clean_recipe_id:
        raise ValueError("recipe_id missing")
    learned_entry = next(
        (
            dict(row)
            for row in load_learned_recipe_store_entries()
            if str(row.get("recipe_id", "") or "").strip() == clean_recipe_id
        ),
        None,
    )
    if learned_entry is None:
        raise ValueError(f"Learned recipe not found: {clean_recipe_id}")
    return normalize_learned_recipe_store_entry(learned_entry)


def build_learned_recipe_promotion_preview(recipe_id: str) -> dict[str, Any]:
    learned_entry = _learned_recipe_by_id(recipe_id)
    manifest = build_stored_recipe_manifest_from_learned_entry(learned_entry)
    capability = str(learned_entry.get("capability", "") or "").strip().lower()
    contract = connection_action_contract(capability)
    return {
        "learned": learned_entry,
        "manifest": manifest,
        "contract": contract.manifest_row() if contract is not None else {},
        "steps": list(manifest.get("steps", []) or []),
        "router_keywords": list(manifest.get("router_keywords", []) or []),
        "side_effect": bool(getattr(contract, "side_effect", False)) if contract is not None else False,
        "policy_family": str(getattr(contract, "policy_family", "") or "").strip() if contract is not None else "",
        "runtime_operation": str(getattr(contract, "operation", "") or "").strip() if contract is not None else "",
    }


def promote_learned_recipe_to_stored_recipe(recipe_id: str) -> dict[str, Any]:
    clean_recipe_id = str(recipe_id or "").strip()
    learned_entry = _learned_recipe_by_id(clean_recipe_id)
    manifest = build_stored_recipe_manifest_from_learned_entry(learned_entry)
    stored = save_stored_recipe_manifest(manifest)
    update_learned_recipe_store_entry(
        clean_recipe_id,
        {
            "promotion_state": "promoted",
            "promotion_hint": f"admin:Promoted into stored recipe `{stored['id']}`.",
            "stored_recipe_id": stored["id"],
        },
    )
    return stored
