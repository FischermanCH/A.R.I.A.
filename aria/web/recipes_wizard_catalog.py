from __future__ import annotations

from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore

BASE_DIR = Path(__file__).resolve().parents[2]
_RECIPES_ROUTES_I18N = I18NStore(BASE_DIR / "aria" / "i18n")

def _recipes_routes_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPES_ROUTES_I18N.t(language or "de", f"recipes_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template

_RECIPE_TYPE_PRESETS: dict[str, dict[str, Any]] = {
    "custom": {
        "label_key": "preset.custom.label",
        "label": _recipes_routes_text("de", "preset.custom.label", "Custom"),
        "hint_key": "preset.custom.hint",
        "hint": _recipes_routes_text("de", "preset.custom.hint", "Free recipe without strong defaults. You define steps and details yourself."),
        "category": "custom",
        "description_key": "preset.custom.description",
        "description": _recipes_routes_text("de", "preset.custom.description", ""),
        "default_step_type": "ssh_run",
        "default_step_name": "",
        "default_params": {},
    },
    "health_check": {
        "label_key": "preset.health_check.label",
        "label": _recipes_routes_text("de", "preset.health_check.label", "Health Check"),
        "hint_key": "preset.health_check.hint",
        "hint": _recipes_routes_text("de", "preset.health_check.hint", "Runs a safe status check on a host or service."),
        "category": "monitoring",
        "description_key": "preset.health_check.description",
        "description": _recipes_routes_text("de", "preset.health_check.description", "Checks a host or service and returns a short status."),
        "default_step_type": "ssh_run",
        "default_step_name_key": "preset.health_check.default_step_name",
        "default_step_name": _recipes_routes_text("de", "preset.health_check.default_step_name", "Health Check"),
        "default_params": {
            "command": "uptime",
        },
    },
    "monitor": {
        "label_key": "preset.monitor.label",
        "label": _recipes_routes_text("de", "preset.monitor.label", "Monitor"),
        "hint_key": "preset.monitor.hint",
        "hint": _recipes_routes_text("de", "preset.monitor.hint", "Reads a source and prepares new events or changes for follow-up steps."),
        "category": "monitoring",
        "description_key": "preset.monitor.description",
        "description": _recipes_routes_text("de", "preset.monitor.description", "Reads a source and prepares changes for further steps."),
        "default_step_type": "rss_read",
        "default_step_name_key": "preset.monitor.default_step_name",
        "default_step_name": _recipes_routes_text("de", "preset.monitor.default_step_name", "Read source"),
        "default_params": {},
    },
    "notify": {
        "label_key": "preset.notify.label",
        "label": _recipes_routes_text("de", "preset.notify.label", "Notify"),
        "hint_key": "preset.notify.hint",
        "hint": _recipes_routes_text("de", "preset.notify.hint", "Sends a short notification to Discord or chat."),
        "category": "automation",
        "description_key": "preset.notify.description",
        "description": _recipes_routes_text("de", "preset.notify.description", "Sends a short notification to an output channel."),
        "default_step_type": "discord_send",
        "default_step_name_key": "preset.notify.default_step_name",
        "default_step_name": _recipes_routes_text("de", "preset.notify.default_step_name", "Send notification"),
        "default_params": {
            "message": "Status-Update:\n{prev_output}",
        },
    },
    "fetch": {
        "label_key": "preset.fetch.label",
        "label": _recipes_routes_text("de", "preset.fetch.label", "Fetch"),
        "hint_key": "preset.fetch.hint",
        "hint": _recipes_routes_text("de", "preset.fetch.hint", "Reads data or files from a connection and passes them to further steps."),
        "category": "automation",
        "description_key": "preset.fetch.description",
        "description": _recipes_routes_text("de", "preset.fetch.description", "Reads data or files from a connection."),
        "default_step_type": "sftp_read",
        "default_step_name_key": "preset.fetch.default_step_name",
        "default_step_name": _recipes_routes_text("de", "preset.fetch.default_step_name", "Read data"),
        "default_params": {
            "remote_path": "/",
        },
    },
    "sync": {
        "label_key": "preset.sync.label",
        "label": _recipes_routes_text("de", "preset.sync.label", "Sync"),
        "hint_key": "preset.sync.hint",
        "hint": _recipes_routes_text("de", "preset.sync.hint", "Writes prepared content back to a target system in a controlled way."),
        "category": "automation",
        "description_key": "preset.sync.description",
        "description": _recipes_routes_text("de", "preset.sync.description", "Writes prepared content to a target system in a controlled way."),
        "default_step_type": "sftp_write",
        "default_step_name_key": "preset.sync.default_step_name",
        "default_step_name": _recipes_routes_text("de", "preset.sync.default_step_name", "Write data"),
        "default_params": {
            "remote_path": "/",
            "content": "{prev_output}",
        },
    },
}

_RECIPE_TYPE_ALLOWED_STEP_TYPES: dict[str, list[str]] = {
    "custom": [
        "ssh_run",
        "sftp_read",
        "sftp_write",
        "smb_read",
        "smb_write",
        "rss_read",
        "llm_transform",
        "discord_send",
        "chat_send",
    ],
    "health_check": ["ssh_run", "llm_transform", "discord_send", "chat_send"],
    "monitor": ["rss_read", "llm_transform", "discord_send", "chat_send"],
    "notify": ["discord_send", "chat_send", "llm_transform"],
    "fetch": ["sftp_read", "smb_read", "llm_transform", "discord_send", "chat_send"],
    "sync": ["sftp_write", "smb_write", "llm_transform", "discord_send", "chat_send"],
}

_RECIPE_TYPE_FOLLOWUP_STEPS: dict[str, list[dict[str, Any]]] = {
    "custom": [],
    "health_check": [
        {
            "step_type": "llm_transform",
            "label_key": "followup.summarize.label",
            "label": _recipes_routes_text("de", "followup.summarize.label", "Summarize"),
            "name_key": "followup.summarize.name",
            "name": _recipes_routes_text("de", "followup.summarize.name", "Brief evaluation"),
            "params": {
                "prompt": _recipes_routes_text("de", "followup.summarize.prompt", "Summarize the result briefly and clearly:\n{prev_output}"),
            },
        },
        {
            "step_type": "discord_send",
            "label_key": "followup.discord_send.label",
            "label": _recipes_routes_text("de", "followup.discord_send.label", "Send to Discord"),
            "name_key": "followup.discord_send.name",
            "name": _recipes_routes_text("de", "followup.discord_send.name", "Status to Discord"),
            "params": {
                "message": _recipes_routes_text("de", "followup.health_discord.message", "Health check result:\n{prev_output}"),
            },
        },
        {
            "step_type": "chat_send",
            "label_key": "followup.chat_reply.label",
            "label": _recipes_routes_text("de", "followup.chat_reply.label", "Reply in chat"),
            "name_key": "followup.chat_reply.name",
            "name": _recipes_routes_text("de", "followup.chat_reply.name", "Reply to chat"),
            "params": {
                "chat_message": _recipes_routes_text("de", "followup.health_chat.message", "Health check result:\n{prev_output}"),
            },
        },
    ],
    "monitor": [
        {
            "step_type": "llm_transform",
            "label_key": "followup.monitor_summary.label",
            "label": _recipes_routes_text("de", "followup.monitor_summary.label", "Summarize changes"),
            "name_key": "followup.monitor_summary.name",
            "name": _recipes_routes_text("de", "followup.monitor_summary.name", "Evaluate changes"),
            "params": {
                "prompt": _recipes_routes_text("de", "followup.monitor_summary.prompt", "Check the read data for new or important changes and summarize them briefly:\n{prev_output}"),
            },
        },
        {
            "step_type": "discord_send",
            "label_key": "followup.alert.label",
            "label": _recipes_routes_text("de", "followup.alert.label", "Send as alert"),
            "name_key": "followup.alert.name",
            "name": _recipes_routes_text("de", "followup.alert.name", "Alert to Discord"),
            "params": {
                "message": _recipes_routes_text("de", "followup.monitor_alert.message", "Monitor update:\n{prev_output}"),
            },
        },
    ],
    "notify": [
        {
            "step_type": "llm_transform",
            "label_key": "followup.prepare_message.label",
            "label": _recipes_routes_text("de", "followup.prepare_message.label", "Prepare message"),
            "name_key": "followup.prepare_message.name",
            "name": _recipes_routes_text("de", "followup.prepare_message.name", "Condense message"),
            "params": {
                "prompt": _recipes_routes_text("de", "followup.prepare_message.prompt", "Create a short, friendly notification from the previous result:\n{prev_output}"),
            },
        },
        {
            "step_type": "chat_send",
            "label_key": "followup.also_chat.label",
            "label": _recipes_routes_text("de", "followup.also_chat.label", "Also send in chat"),
            "name_key": "followup.chat_reply.name",
            "name": _recipes_routes_text("de", "followup.chat_reply.name", "Reply to chat"),
            "params": {
                "chat_message": _recipes_routes_text("de", "followup.notify_chat.message", "Notification:\n{prev_output}"),
            },
        },
    ],
    "fetch": [
        {
            "step_type": "llm_transform",
            "label_key": "followup.content_summary.label",
            "label": _recipes_routes_text("de", "followup.content_summary.label", "Summarize content"),
            "name_key": "followup.content_summary.name",
            "name": _recipes_routes_text("de", "followup.content_summary.name", "Evaluate content"),
            "params": {
                "prompt": _recipes_routes_text("de", "followup.content_summary.prompt", "Briefly summarize the read content and highlight important points:\n{prev_output}"),
            },
        },
        {
            "step_type": "discord_send",
            "label_key": "followup.result_discord.label",
            "label": _recipes_routes_text("de", "followup.result_discord.label", "Result to Discord"),
            "name_key": "followup.result_discord.name",
            "name": _recipes_routes_text("de", "followup.result_discord.name", "Send result"),
            "params": {
                "message": _recipes_routes_text("de", "followup.fetch_result.message", "Fetch result:\n{prev_output}"),
            },
        },
    ],
    "sync": [
        {
            "step_type": "chat_send",
            "label_key": "followup.sync_confirm.label",
            "label": _recipes_routes_text("de", "followup.sync_confirm.label", "Confirm sync"),
            "name_key": "followup.sync_confirm.name",
            "name": _recipes_routes_text("de", "followup.sync_confirm.name", "Confirm sync"),
            "params": {
                "chat_message": _recipes_routes_text("de", "followup.sync_done.message", "Sync completed:\n{prev_output}"),
            },
        },
        {
            "step_type": "discord_send",
            "label_key": "followup.sync_discord.label",
            "label": _recipes_routes_text("de", "followup.sync_discord.label", "Report sync to Discord"),
            "name_key": "followup.sync_discord.name",
            "name": _recipes_routes_text("de", "followup.sync_discord.name", "Report sync"),
            "params": {
                "message": _recipes_routes_text("de", "followup.sync_done.message", "Sync completed:\n{prev_output}"),
            },
        },
    ],
}

_RECIPE_TYPE_CONNECTION_CHOICES: dict[str, list[dict[str, str]]] = {
    "custom": [],
    "health_check": [
        {
            "kind": "ssh",
            "label_key": "connection.ssh.label",
            "label": _recipes_routes_text("de", "connection.ssh.label", "SSH connection"),
            "field": "connection_ref",
            "step_type": "ssh_run",
            "hint_key": "connection.ssh.hint",
            "hint": _recipes_routes_text("de", "connection.ssh.hint", "Choose the host or service where the check should run."),
        }
    ],
    "monitor": [
        {
            "kind": "rss",
            "label_key": "connection.rss.label",
            "label": _recipes_routes_text("de", "connection.rss.label", "RSS source"),
            "field": "rss_connection_ref",
            "step_type": "rss_read",
            "hint_key": "connection.rss.hint",
            "hint": _recipes_routes_text("de", "connection.rss.hint", "Choose the source the monitor should watch."),
        }
    ],
    "notify": [
        {
            "kind": "discord",
            "label_key": "connection.discord.label",
            "label": _recipes_routes_text("de", "connection.discord.label", "Discord target"),
            "field": "discord_connection_ref",
            "step_type": "discord_send",
            "hint_key": "connection.discord.hint",
            "hint": _recipes_routes_text("de", "connection.discord.hint", "Choose the channel or webhook for notifications."),
        }
    ],
    "fetch": [
        {
            "kind": "sftp",
            "label_key": "connection.sftp.label",
            "label": _recipes_routes_text("de", "connection.sftp.label", "SFTP connection"),
            "field": "sftp_connection_ref",
            "step_type": "sftp_read",
            "hint_key": "connection.sftp.hint",
            "hint": _recipes_routes_text("de", "connection.sftp.hint", "Choose the source from which files or data are read."),
        },
        {
            "kind": "smb",
            "label_key": "connection.smb.label",
            "label": _recipes_routes_text("de", "connection.smb.label", "SMB connection"),
            "field": "smb_connection_ref",
            "step_type": "smb_read",
            "hint_key": "connection.smb.hint",
            "hint": _recipes_routes_text("de", "connection.smb.hint", "Alternatively, you can read an SMB share instead of SFTP."),
        },
    ],
    "sync": [
        {
            "kind": "sftp",
            "label_key": "connection.sftp_target.label",
            "label": _recipes_routes_text("de", "connection.sftp_target.label", "SFTP target"),
            "field": "sftp_connection_ref",
            "step_type": "sftp_write",
            "hint_key": "connection.sftp_target.hint",
            "hint": _recipes_routes_text("de", "connection.sftp_target.hint", "Choose the target system to write to."),
        },
        {
            "kind": "smb",
            "label_key": "connection.smb_target.label",
            "label": _recipes_routes_text("de", "connection.smb_target.label", "SMB target"),
            "field": "smb_connection_ref",
            "step_type": "smb_write",
            "hint_key": "connection.smb_target.hint",
            "hint": _recipes_routes_text("de", "connection.smb_target.hint", "Alternatively, you can write to an SMB share instead of SFTP."),
        },
    ],
}


def _sanitize_recipe_type(value: str | None) -> str:
    key = str(value or "").strip().lower()
    return key if key in _RECIPE_TYPE_PRESETS else "custom"


def _recipe_type_options() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": str(meta.get("label", key)).strip() or key,
            "hint": str(meta.get("hint", "")).strip(),
        }
        for key, meta in _RECIPE_TYPE_PRESETS.items()
    ]


def _recipe_type_allowed_steps() -> dict[str, list[str]]:
    return {key: list(values) for key, values in _RECIPE_TYPE_ALLOWED_STEP_TYPES.items()}


def _recipe_type_followup_steps() -> dict[str, list[dict[str, Any]]]:
    return {key: [dict(item) for item in values] for key, values in _RECIPE_TYPE_FOLLOWUP_STEPS.items()}


def _recipe_type_connection_choices() -> dict[str, list[dict[str, str]]]:
    return {key: [dict(item) for item in values] for key, values in _RECIPE_TYPE_CONNECTION_CHOICES.items()}


# Legacy aliases: templates/forms still submit `skill_type` in alpha installs.
_SKILL_TYPE_PRESETS = _RECIPE_TYPE_PRESETS
_SKILL_TYPE_ALLOWED_STEP_TYPES = _RECIPE_TYPE_ALLOWED_STEP_TYPES
_SKILL_TYPE_FOLLOWUP_STEPS = _RECIPE_TYPE_FOLLOWUP_STEPS
_SKILL_TYPE_CONNECTION_CHOICES = _RECIPE_TYPE_CONNECTION_CHOICES
_sanitize_skill_type = _sanitize_recipe_type
_skill_type_options = _recipe_type_options
_skill_type_allowed_steps = _recipe_type_allowed_steps
_skill_type_followup_steps = _recipe_type_followup_steps
_skill_type_connection_choices = _recipe_type_connection_choices
