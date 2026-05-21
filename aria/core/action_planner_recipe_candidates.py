from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from aria.core.i18n import I18NStore

from aria.core.action_candidate_taxonomy import LEARNED_EXPERIENCE_ORIGIN
from aria.core.action_candidate_taxonomy import LEARNED_RECIPE_CANDIDATE_ROLE
from aria.core.action_candidate_taxonomy import RECIPE_CANDIDATE_KIND
from aria.core.action_candidate_taxonomy import STORED_RECIPE_MANIFEST_ORIGIN
from aria.core.action_candidate_taxonomy import STORED_RECIPE_CANDIDATE_ROLE
from aria.core.connection_action_contract import connection_action_binding_is_supported
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_id
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_inputs
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_metadata
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_preview
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_summary
from aria.core.learned_recipe_candidate_view import learned_recipe_candidate_title
from aria.core.learned_recipe_candidate_view import learned_recipe_trigger_values
from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata

_ACTION_PLANNER_RECIPE_CANDIDATES_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _action_planner_recipe_candidates_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _ACTION_PLANNER_RECIPE_CANDIDATES_I18N.t(language or "de", f"action_planner_recipe_candidates.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template



def recipe_manifest_intent(manifest: dict[str, Any]) -> str:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return ""
    step_type = str((steps[0] or {}).get("type", "") or "").strip().lower()
    return {
        "ssh_run": "health_check",
        "rss_read": "read_feed",
        "discord_send": "send_message",
        "chat_send": "send_message",
        "sftp_read": "read_file",
        "smb_read": "read_file",
        "sftp_write": "write_file",
        "smb_write": "write_file",
        "llm_transform": "transform",
    }.get(step_type, "")


def recipe_manifest_preview(
    manifest: dict[str, Any],
    *,
    language: str = "",
    localized_text: Callable[..., str],
) -> str:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return ""
    step = dict((steps[0] or {}))
    step_type = str(step.get("type", "") or "").strip().lower()
    params = dict(step.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        label = _action_planner_recipe_candidates_text(language, "message_53", "SSH command")
        return (
            f"{label}: {command}"
            if command
            else _action_planner_recipe_candidates_text(language, "message_55", 'SSH command from recipe')
        )
    if step_type in {"sftp_read", "smb_read"}:
        path = str(params.get("remote_path", "") or "").strip()
        label = _action_planner_recipe_candidates_text(language, "message_60", "Read remote path")
        return (
            f"{label}: {path}"
            if path
            else _action_planner_recipe_candidates_text(language, "message_62", 'Read remote file from recipe')
        )
    if step_type in {"sftp_write", "smb_write"}:
        path = str(params.get("remote_path", "") or "").strip()
        label = _action_planner_recipe_candidates_text(language, "message_67", "Write remote path")
        return (
            f"{label}: {path}"
            if path
            else _action_planner_recipe_candidates_text(language, "message_69", 'Write remote file from recipe')
        )
    if step_type == "rss_read":
        return _action_planner_recipe_candidates_text(language, "message_72", 'Read feed via recipe')
    if step_type == "discord_send":
        return _action_planner_recipe_candidates_text(language, "message_74", 'Send Discord message via recipe')
    if step_type == "chat_send":
        return _action_planner_recipe_candidates_text(language, "message_76", 'Send chat reply via recipe')
    return step_type or _action_planner_recipe_candidates_text(language, "message_77", 'Custom recipe step')


def recipe_manifest_inputs(manifest: dict[str, Any]) -> dict[str, str]:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return {}
    step = dict((steps[0] or {}))
    step_type = str(step.get("type", "") or "").strip().lower()
    params = dict(step.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        return {"command": command} if command else {}
    if step_type in {"sftp_read", "sftp_write", "smb_read", "smb_write"}:
        remote_path = str(params.get("remote_path", "") or "").strip()
        return {"remote_path": remote_path} if remote_path else {}
    if step_type in {"discord_send", "chat_send"}:
        message = str(params.get("message", "") or "").strip() or str(params.get("text", "") or "").strip()
        return {"message": message} if message else {}
    if step_type == "rss_read":
        limit = str(params.get("limit", "") or "").strip()
        return {"limit": limit} if limit else {}
    return {}


def build_stored_recipe_action_candidates(
    manifests: list[dict[str, Any]],
    *,
    query: str,
    connection_kind: str,
    language: str = "",
    candidate_factory: Callable[..., Any],
    normalize_capability: Callable[[str], str],
    intent_score: Callable[[str, str, list[str]], float],
    safe_list: Callable[[Any], list[str]],
    localized_text: Callable[..., str],
) -> list[Any]:
    clean_kind = str(connection_kind or "").strip().lower()
    rows: list[Any] = []
    for manifest in manifests:
        if not bool(manifest.get("enabled_default", True)):
            continue
        connections = [str(item).strip().lower() for item in list(manifest.get("connections", []) or []) if str(item).strip()]
        if clean_kind and clean_kind not in connections:
            continue
        intent = recipe_manifest_intent(manifest)
        keywords = safe_list(manifest.get("router_keywords", []))
        metadata = stored_recipe_candidate_metadata(manifest, fallback_connection_kind=clean_kind)
        rows.append(
            candidate_factory(
                candidate_kind=RECIPE_CANDIDATE_KIND,
                candidate_id=str(manifest.get("id", "") or "").strip(),
                title=str(manifest.get("name", "") or "").strip(),
                summary=str(manifest.get("description", "") or "").strip(),
                intent=intent,
                connection_kind=clean_kind,
                capability=normalize_capability(str(connections[0] if connections else clean_kind)),
                preview=recipe_manifest_preview(manifest, language=language, localized_text=localized_text),
                inputs=recipe_manifest_inputs(manifest),
                router_keywords=keywords,
                source="custom_recipe_candidate",
                candidate_role=str(metadata.get("candidate_role", "") or STORED_RECIPE_CANDIDATE_ROLE),
                recipe_scope=dict(metadata.get("recipe_scope", {}) or {}),
                recipe_origin=str(metadata.get("recipe_origin", "") or STORED_RECIPE_MANIFEST_ORIGIN),
                experience_count=int(metadata.get("experience_count", 0) or 0),
                last_success_at=str(metadata.get("last_success_at", "") or "").strip(),
                promotion_state=str(metadata.get("promotion_state", "") or "").strip(),
                promotion_hint=str(metadata.get("promotion_hint", "") or "").strip(),
                score=intent_score(query, intent, keywords),
            )
        )
    return rows


def build_learned_recipe_action_candidates(
    records: list[dict[str, Any]],
    *,
    query: str,
    connection_kind: str,
    language: str = "",
    candidate_factory: Callable[..., Any],
    normalize_capability: Callable[[str], str],
    intent_score: Callable[[str, str, list[str]], float],
    safe_list: Callable[[Any], list[str]],
    localized_text: Callable[..., str],
) -> list[Any]:
    clean_kind = str(connection_kind or "").strip().lower()
    rows: list[Any] = []
    for record in records:
        metadata = learned_recipe_candidate_metadata(record, fallback_connection_kind=clean_kind)
        connection_kinds = [
            str(item or "").strip().lower()
            for item in list(metadata.get("recipe_scope", {}).get("connection_kinds", []) or [])
            if str(item or "").strip()
        ]
        if clean_kind and connection_kinds and clean_kind not in connection_kinds:
            continue
        stored_recipe_id = str(record.get("stored_recipe_id", "") or "").strip()
        if not stored_recipe_id:
            continue
        intent = str(record.get("intent", "") or "").strip().lower()
        capability = normalize_capability(str(record.get("capability", "") or "").strip())
        candidate_kind = clean_kind or str(record.get("connection_kind", "") or "").strip().lower()
        if candidate_kind and capability and not connection_action_binding_is_supported(candidate_kind, capability):
            continue
        keywords = safe_list(learned_recipe_trigger_values(record))
        rows.append(
            candidate_factory(
                candidate_kind=RECIPE_CANDIDATE_KIND,
                candidate_id=stored_recipe_id,
                title=learned_recipe_candidate_title(record, language=language, localized_text=localized_text),
                summary=learned_recipe_candidate_summary(record, language=language, localized_text=localized_text),
                intent=intent,
                connection_kind=candidate_kind,
                capability=capability,
                preview=learned_recipe_candidate_preview(record, language=language, localized_text=localized_text),
                inputs=learned_recipe_candidate_inputs(record),
                router_keywords=keywords,
                source="learned_recipe_candidate",
                candidate_role=str(metadata.get("candidate_role", "") or LEARNED_RECIPE_CANDIDATE_ROLE),
                recipe_scope=dict(metadata.get("recipe_scope", {}) or {}),
                recipe_origin=str(metadata.get("recipe_origin", "") or LEARNED_EXPERIENCE_ORIGIN),
                experience_count=int(metadata.get("experience_count", 0) or 0),
                last_success_at=str(metadata.get("last_success_at", "") or "").strip(),
                promotion_state=str(metadata.get("promotion_state", "") or "").strip(),
                promotion_hint=str(metadata.get("promotion_hint", "") or "").strip(),
                score=intent_score(query, intent, keywords),
            )
        )
    return rows


def build_custom_recipe_action_candidates(
    manifests: list[dict[str, Any]],
    *,
    query: str,
    connection_kind: str,
    language: str = "",
    candidate_factory: Callable[..., Any],
    normalize_capability: Callable[[str], str],
    intent_score: Callable[[str, str, list[str]], float],
    safe_list: Callable[[Any], list[str]],
    localized_text: Callable[..., str],
) -> list[Any]:
    return build_stored_recipe_action_candidates(
        manifests,
        query=query,
        connection_kind=connection_kind,
        language=language,
        candidate_factory=candidate_factory,
        normalize_capability=normalize_capability,
        intent_score=intent_score,
        safe_list=safe_list,
        localized_text=localized_text,
    )


# Legacy aliases for older imports/tests.
skill_manifest_intent = recipe_manifest_intent
skill_manifest_preview = recipe_manifest_preview
skill_manifest_inputs = recipe_manifest_inputs
build_custom_skill_action_candidates = build_custom_recipe_action_candidates
