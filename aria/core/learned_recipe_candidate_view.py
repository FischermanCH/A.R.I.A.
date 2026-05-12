from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from aria.core.i18n import I18NStore

from aria.core.action_candidate_taxonomy import LEARNED_EXPERIENCE_ORIGIN
from aria.core.action_candidate_taxonomy import LEARNED_RECIPE_CANDIDATE_ROLE
from aria.core.recipe_candidate_contract import build_recipe_candidate_metadata

_LEARNED_RECIPE_CANDIDATE_VIEW_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _learned_recipe_candidate_view_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _LEARNED_RECIPE_CANDIDATE_VIEW_I18N.t(language or "de", f"learned_recipe_candidate_view.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template



def _source_value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        if key in source:
            return source.get(key)
        nested = source.get("metadata")
        if isinstance(nested, dict) and key in nested:
            return nested.get(key)
        return None
    return getattr(source, key, None)


def _slugify(value: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())).strip("-")


def _inferred_step_type(capability: str) -> str:
    clean = str(capability or "").strip().lower()
    return {
        "ssh_command": "ssh_run",
        "file_read": "remote_read",
        "file_write": "remote_write",
        "file_list": "remote_list",
        "feed_read": "rss_read",
        "discord_send": "discord_send",
        "webhook_send": "webhook_send",
        "email_send": "email_send",
        "mail_read": "imap_read",
        "mail_search": "imap_search",
        "mqtt_publish": "mqtt_publish",
        "calendar_read": "calendar_read",
        "http_api_request": "http_api_request",
        "website_read": "website_read",
        "website_list": "website_list",
    }.get(clean, clean)


def learned_recipe_candidate_id(record: dict[str, Any]) -> str:
    explicit = str(record.get("candidate_id", "") or record.get("recipe_id", "") or record.get("id", "") or "").strip()
    if explicit:
        return explicit
    connection_kind = str(record.get("connection_kind", "") or "").strip().lower()
    intent = str(record.get("intent", "") or "").strip().lower()
    capability = str(record.get("capability", "") or "").strip().lower()
    stem = "-".join(part for part in (connection_kind, intent or capability) if part)
    return f"learned-{_slugify(stem or 'recipe')}"


def learned_recipe_connection_kinds(record: dict[str, Any], *, fallback_connection_kind: str = "") -> list[str]:
    scope = record.get("recipe_scope", {})
    if isinstance(scope, dict):
        values = scope.get("connection_kinds", [])
        if isinstance(values, list):
            rows = [str(item or "").strip().lower() for item in values if str(item or "").strip()]
            if rows:
                return list(dict.fromkeys(rows))
    rows: list[str] = []
    for raw in (
        record.get("connection_kind", ""),
        fallback_connection_kind,
    ):
        clean = str(raw or "").strip().lower()
        if clean and clean not in rows:
            rows.append(clean)
    return rows


def learned_recipe_step_types(record: dict[str, Any]) -> list[str]:
    scope = record.get("recipe_scope", {})
    if isinstance(scope, dict):
        values = scope.get("step_types", [])
        if isinstance(values, list):
            rows = [str(item or "").strip().lower() for item in values if str(item or "").strip()]
            if rows:
                return list(dict.fromkeys(rows))
    inferred = _inferred_step_type(str(record.get("capability", "") or ""))
    return [inferred] if inferred else []


def learned_recipe_scope(record: dict[str, Any], *, fallback_connection_kind: str = "") -> dict[str, Any]:
    scope = record.get("recipe_scope", {})
    normalized = {
        "connection_kinds": learned_recipe_connection_kinds(record, fallback_connection_kind=fallback_connection_kind),
        "step_types": learned_recipe_step_types(record),
    }
    if isinstance(scope, dict):
        connection_refs = [
            str(item or "").strip()
            for item in list(scope.get("connection_refs", []) or [])
            if str(item or "").strip()
        ]
        learning_origin = str(scope.get("learning_origin", "") or "").strip()
        if connection_refs:
            normalized["connection_refs"] = list(dict.fromkeys(connection_refs))
        if learning_origin:
            normalized["learning_origin"] = learning_origin
    return normalized


def learned_recipe_candidate_metadata(
    record: dict[str, Any],
    *,
    fallback_connection_kind: str = "",
) -> dict[str, Any]:
    return build_recipe_candidate_metadata(
        candidate_role=LEARNED_RECIPE_CANDIDATE_ROLE,
        recipe_scope=learned_recipe_scope(record, fallback_connection_kind=fallback_connection_kind),
        recipe_origin=LEARNED_EXPERIENCE_ORIGIN,
        experience=record,
    )


def learned_recipe_candidate_title(
    record: dict[str, Any],
    *,
    language: str = "",
    localized_text: Callable[..., str],
) -> str:
    explicit = str(record.get("title", "") or record.get("name", "") or record.get("recipe_title", "") or "").strip()
    if explicit:
        return explicit
    intent = str(record.get("intent", "") or "").strip().replace("_", " ")
    capability = str(record.get("capability", "") or "").strip().replace("_", " ")
    base = intent or capability or _learned_recipe_candidate_view_text(language, "message_133", 'Learned recipe')
    label = _learned_recipe_candidate_view_text(language, "message_134", "Learned recipe")
    return f"{label}: {base}".strip()


def learned_recipe_candidate_summary(
    record: dict[str, Any],
    *,
    language: str = "",
    localized_text: Callable[..., str],
) -> str:
    explicit = str(record.get("summary", "") or record.get("experience_summary", "") or "").strip()
    if explicit:
        return explicit
    summary = str(record.get("summary_text", "") or "").strip()
    if summary:
        return summary
    return _learned_recipe_candidate_view_text(language, "message_149", 'Recipe candidate derived from successful executions.')


def learned_recipe_candidate_preview(
    record: dict[str, Any],
    *,
    language: str = "",
    localized_text: Callable[..., str],
) -> str:
    capability = str(record.get("capability", "") or "").strip().lower()
    chosen_action = str(record.get("chosen_action", "") or "").strip()
    if capability == "ssh_command":
        label = _learned_recipe_candidate_view_text(language, "message_166", "SSH command")
        return (
            f"{label}: {chosen_action}"
            if chosen_action
            else _learned_recipe_candidate_view_text(language, "message_168", 'SSH command from learned recipe')
        )
    if capability == "file_read":
        label = _learned_recipe_candidate_view_text(language, "message_172", "Read remote path")
        return (
            f"{label}: {chosen_action}"
            if chosen_action
            else _learned_recipe_candidate_view_text(language, "message_174", 'Read remote file from learned recipe')
        )
    if capability == "file_write":
        label = _learned_recipe_candidate_view_text(language, "message_178", "Write remote path")
        return (
            f"{label}: {chosen_action}"
            if chosen_action
            else _learned_recipe_candidate_view_text(language, "message_180", 'Write remote file from learned recipe')
        )
    if capability == "mail_search":
        label = _learned_recipe_candidate_view_text(language, "message_184", "Mail search")
        return (
            f"{label}: {chosen_action}"
            if chosen_action
            else _learned_recipe_candidate_view_text(language, "message_186", 'Search mailbox via learned recipe')
        )
    if capability in {"discord_send", "webhook_send", "email_send", "mqtt_publish"}:
        label = _learned_recipe_candidate_view_text(language, "message_190", "Message")
        return (
            f"{label}: {chosen_action}"
            if chosen_action
            else _learned_recipe_candidate_view_text(language, "message_192", 'Send message via learned recipe')
        )
    explicit = str(record.get("preview", "") or "").strip()
    if explicit:
        return explicit
    if chosen_action:
        return chosen_action
    return _learned_recipe_candidate_view_text(language, "message_199", 'Action from learned recipe')


def learned_recipe_candidate_inputs(record: dict[str, Any]) -> dict[str, str]:
    explicit = record.get("inputs", {})
    if isinstance(explicit, dict) and explicit:
        return {
            str(key or "").strip(): str(value or "").strip()
            for key, value in explicit.items()
            if str(key or "").strip() and str(value or "").strip()
        }
    capability = str(record.get("capability", "") or "").strip().lower()
    chosen_action = str(record.get("chosen_action", "") or "").strip()
    if capability == "ssh_command" and chosen_action:
        return {"command": chosen_action}
    if capability in {"file_read", "file_write", "file_list"} and chosen_action.startswith("/"):
        return {"remote_path": chosen_action}
    if capability in {"discord_send", "webhook_send", "email_send", "mqtt_publish"} and chosen_action:
        return {"message": chosen_action}
    if capability == "mail_search" and chosen_action:
        return {"search_query": chosen_action}
    return {}


def learned_recipe_trigger_values(record: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in [
        str(record.get("title", "") or record.get("name", "") or "").strip().lower(),
        str(record.get("intent", "") or "").strip().replace("_", " ").lower(),
        str(record.get("capability", "") or "").strip().replace("_", " ").lower(),
        *[
            str(item or "").strip().lower()
            for item in list(record.get("router_keywords", []) or [])
            if str(item or "").strip()
        ],
    ]:
        if not raw or len(raw) < 3 or raw in seen:
            continue
        seen.add(raw)
        rows.append(raw)
    return rows
