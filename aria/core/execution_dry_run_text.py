from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from aria.core.i18n import I18NStore
from aria.core.recipe_runtime_contract import is_recipe_confirmation_reason

_DRY_RUN_TEXT_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _dry_run_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    lang = "de" if str(language or "").strip().lower().startswith("de") else "en"
    template = _DRY_RUN_TEXT_I18N.t(lang, f"execution_dry_run_text.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template

from aria.core.i18n import I18NStore



def field_label(name: str, language: str) -> str:
    clean = str(name or "").strip().lower()
    labels = {
        "command": _dry_run_text(language, "message_16", 'Command'),
        "connection_ref": _dry_run_text(language, "message_17", 'Target profile'),
        "remote_path": _dry_run_text(language, "message_18", 'Remote path'),
        "message": _dry_run_text(language, "message_19", 'Message'),
        "search_query": _dry_run_text(language, "message_20", 'Search query'),
        "topic": _dry_run_text(language, "message_21", 'Topic'),
        "path": _dry_run_text(language, "message_22", 'Path'),
        "content": _dry_run_text(language, "message_23", 'Content'),
    }
    return labels.get(clean, clean or _dry_run_text(language, "message_25", 'Field'))


def capability_label(capability: str, language: str) -> str:
    clean = str(capability or "").strip().lower()
    labels = {
        "ssh_command": _dry_run_text(language, "message_31", 'SSH command'),
        "file_list": _dry_run_text(language, "message_32", 'List files'),
        "file_read": _dry_run_text(language, "message_33", 'Read file'),
        "file_write": _dry_run_text(language, "message_34", 'Write file'),
        "discord_send": _dry_run_text(language, "message_35", 'Send Discord message'),
        "calendar_read": _dry_run_text(language, "message_36", 'Read calendar events'),
        "webhook_send": _dry_run_text(language, "message_37", 'Send webhook'),
        "email_send": _dry_run_text(language, "message_38", 'Send email'),
        "mail_read": _dry_run_text(language, "message_39", 'Read mailbox'),
        "mail_search": _dry_run_text(language, "message_40", 'Search mailbox'),
        "mqtt_publish": _dry_run_text(language, "message_41", 'Publish MQTT message'),
        "api_request": _dry_run_text(language, "message_42", 'API request'),
        "recipe": _dry_run_text(language, "message_43", 'Stored recipe'),
        "custom_skill": _dry_run_text(language, "message_44", 'Stored recipe'),
    }
    return labels.get(clean, clean or _dry_run_text(language, "message_46", 'Action'))


def confirmation_action_label(action: str, language: str) -> str:
    clean = str(action or "").strip().lower()
    return {
        "allow": _dry_run_text(language, "message_52", 'Allow'),
        "ask_user": _dry_run_text(language, "message_53", 'Ask first'),
        "block": _dry_run_text(language, "message_54", 'Block'),
    }.get(clean, clean or _dry_run_text(language, "message_55", 'Unknown'))


def reason_label(
    reason: str,
    *,
    language: str,
    payload: dict[str, Any] | None = None,
    guardrail_ref: str = "",
) -> str:
    clean = str(reason or "").strip()
    if not clean:
        return ""
    payload = dict(payload or {})
    missing_fields = [str(item or "").strip() for item in list(payload.get("missing_fields", []) or []) if str(item or "").strip()]
    if clean == "missing_parameters":
        labels = ", ".join(field_label(name, language) for name in missing_fields) if missing_fields else ""
        if labels:
            return _dry_run_text(language, "message_73", 'Required fields are still missing: {labels}.', labels=labels)
        return _dry_run_text(language, "message_78", 'Required fields are still missing for this action.')
    if clean == "routing_target_confirmation":
        return _dry_run_text(language, "message_84", 'The target is not clearly confirmed yet.')
    if clean == "ssh_command_needs_confirmation":
        return _dry_run_text(language, "message_86", 'This command is not a clear safe default and should be confirmed first.')
    if clean == "ssh_command_empty":
        return _dry_run_text(language, "message_88", 'A concrete SSH command is still missing for this step.')
    if clean == "ssh_command_shell_injection":
        return _dry_run_text(language, "message_90", 'The SSH command contains shell constructs that ARIA blocks in this mode.')
    if clean == "ssh_command_backgrounding_blocked":
        return _dry_run_text(language, "message_92", 'Backgrounded processes are not allowed for agentic SSH commands.')
    if clean == "ssh_command_redirect_blocked":
        return _dry_run_text(language, "message_94", 'Redirects or input redirection are not allowed for agentic SSH commands.')
    if clean == "ssh_command_mutating_operation":
        return _dry_run_text(language, "message_96", 'This SSH command leaves the read-only operations contract and is blocked.')
    if clean == "ssh_command_not_in_allow_list":
        return _dry_run_text(language, "message_98", 'This SSH command does not match the configured allowlist for this profile.')
    if clean == "ssh_command_unknown_readonly":
        return _dry_run_text(language, "message_100", 'The SSH command looks read-only but sits outside the clearly allowed default scope and needs confirmation.')
    if clean == "ssh_readonly_policy_allow":
        return _dry_run_text(language, "message_102", 'The SSH command fits within the read-only operations contract.')
    if clean == "http_api_full_url_blocked":
        return _dry_run_text(language, "message_104", 'HTTP API requests in this mode must use paths, not full URLs.')
    if clean == "http_api_path_invalid":
        return _dry_run_text(language, "message_106", 'The API path contains invalid constructs and is blocked.')
    if clean == "http_api_mutating_method":
        return _dry_run_text(language, "message_108", 'Mutating HTTP methods are blocked by the read-only API contract.')
    if clean == "http_api_mutating_path":
        return _dry_run_text(language, "message_110", 'This API path looks mutating and leaves the read-only API contract.')
    if clean == "http_api_body_for_read_request":
        return _dry_run_text(language, "message_112", 'Read-only GET/HEAD API requests may not include a request body.')
    if clean == "http_api_method_needs_confirmation":
        return _dry_run_text(language, "message_114", 'This HTTP method is not clearly read-only and should be confirmed.')
    if clean == "http_api_method_unknown":
        return _dry_run_text(language, "message_116", 'This HTTP method is unusual and should be confirmed before execution.')
    if clean == "http_api_path_needs_confirmation":
        return _dry_run_text(language, "message_118", 'This API path is too specific for a safe default case and should be confirmed.')
    if clean == "http_api_sensitive_path":
        return _dry_run_text(language, "message_120", 'This API path looks sensitive and should be confirmed before execution.')
    if clean == "http_api_status_path_unclear":
        return _dry_run_text(language, "message_122", 'For a status request, this API path looks unusual and should be confirmed.')
    if clean == "http_api_readonly_policy_allow":
        return _dry_run_text(language, "message_124", 'The API request fits within the read-only operations contract.')
    if clean == "side_effect_confirmation":
        capability_text = capability_label(str(payload.get("capability", "") or ""), language)
        return _dry_run_text(language, "message_127", '{capability_text} changes something and should be confirmed before execution.', capability_text=capability_text)
    if clean == "outbound_message_confirmation":
        return _dry_run_text(language, "message_129", 'Outgoing messages should be confirmed briefly before sending.')
    if is_recipe_confirmation_reason(clean):
        return _dry_run_text(language, "message_131", 'Stored recipes should be confirmed before execution.')
    if clean in {"guardrail_blocked", "guardrail_denied"}:
        if guardrail_ref:
            return _dry_run_text(language, "message_134", 'Guardrail profile {guardrail_ref} blocks this action.', guardrail_ref=guardrail_ref)
        return _dry_run_text(language, "message_135", 'The active guardrail profile blocks this action.')
    if clean == "No extra confirmation needed.":
        return _dry_run_text(language, "message_137", 'No extra confirmation needed.')
    if "_" not in clean and len(clean.split()) > 1:
        return clean
    return clean


def _guardrail_config_link(guardrail_ref: str, language: str) -> str:
    clean_ref = str(guardrail_ref or "").strip()
    if not clean_ref:
        return ""
    href = f"/config/security?guardrail_ref={quote(clean_ref, safe='')}"
    link = f"[{clean_ref}]({href}) ({href})"
    return _dry_run_text(
        language,
        "message_163",
        "Guardrail profile: {link}",
        clean_ref=clean_ref,
        href=href,
        link=link,
    )


def decision_summary(*, action: str, language: str, target: str = "", preview: str = "", guardrail_ref: str = "") -> str:
    clean_action = str(action or "").strip().lower()
    clean_target = str(target or "").strip()
    clean_preview = str(preview or "").strip()
    if clean_action == "allow":
        if clean_target and clean_preview:
            return _dry_run_text(language, "message_149", 'ARIA would execute on {clean_target} directly: {clean_preview}', clean_target=clean_target, clean_preview=clean_preview)
        return _dry_run_text(language, "message_150", 'ARIA would allow this action without any further confirmation.')
    if clean_action == "ask_user":
        if clean_target and clean_preview:
            return _dry_run_text(language, "message_153", 'ARIA would ask for confirmation before executing on {clean_target}: {clean_preview}', clean_target=clean_target, clean_preview=clean_preview)
        if clean_target:
            return _dry_run_text(language, "message_155", 'ARIA would ask for confirmation before executing on {clean_target}.', clean_target=clean_target)
        return _dry_run_text(language, "message_156", 'ARIA would ask for confirmation before execution.')
    if clean_action == "block":
        guardrail_link = _guardrail_config_link(guardrail_ref, language)
        if clean_target and clean_preview:
            summary = _dry_run_text(language, "message_159", 'ARIA cannot execute this action on {clean_target}: {clean_preview}', clean_target=clean_target, clean_preview=clean_preview)
            return f"{summary}\n\n{guardrail_link}" if guardrail_link else summary
        if clean_target:
            summary = _dry_run_text(language, "message_161", 'ARIA cannot execute this action on {clean_target}.', clean_target=clean_target)
            return f"{summary}\n\n{guardrail_link}" if guardrail_link else summary
        summary = _dry_run_text(language, "message_162", 'ARIA cannot execute this action.')
        return f"{summary}\n\n{guardrail_link}" if guardrail_link else summary
    return ""
