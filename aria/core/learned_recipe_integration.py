from __future__ import annotations

import re
from typing import Any, Callable

from aria.core.action_plan import ActionPlan
from aria.core.stored_recipe_manifest_view import stored_recipe_candidate_metadata
from aria.core.action_planner_recipe_candidates import recipe_manifest_inputs
from aria.core.action_planner_recipe_candidates import recipe_manifest_intent


GUARDRAIL_HEALTHCHECK_LEARNING_ORIGIN = "guardrail_healthcheck_fallback"


def _chosen_action_from_plan(plan: ActionPlan) -> str:
    capability = str(plan.capability or "").strip().lower()
    if capability == "ssh_command":
        return str(plan.content or "").strip()
    if capability in {"file_read", "file_write", "file_list", "api_request", "http_api_request"}:
        return str(plan.path or "").strip()
    if capability in {"mail_search", "discord_send", "webhook_send", "email_send", "mqtt_publish"}:
        return str(plan.content or "").strip()
    return str(plan.content or plan.path or "").strip()


def should_record_learned_recipe_success(action: dict[str, Any], plan: ActionPlan) -> bool:
    candidate_kind = str(action.get("candidate_kind", "") or "").strip().lower()
    candidate_role = str(action.get("candidate_role", "") or "").strip().lower()
    capability = str(plan.capability or "").strip().lower()
    if candidate_kind != "template":
        return False
    if candidate_role and candidate_role != "template_candidate":
        return False
    return capability in {
        "ssh_command",
        "file_read",
        "file_write",
        "file_list",
        "feed_read",
        "website_read",
        "website_list",
        "calendar_read",
        "mail_read",
        "mail_search",
        "mqtt_publish",
        "api_request",
        "http_api_request",
        "discord_send",
        "webhook_send",
        "email_send",
    }


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _unique_clean_list(values: list[Any]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = _clean_text(value)
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        rows.append(clean)
    return rows


def _is_guardrail_healthcheck_fallback(action: dict[str, Any], plan: ActionPlan) -> bool:
    reason = _clean_text(action.get("reason")).lower()
    fallback_from = _clean_text(action.get("guardrail_fallback_from"))
    capability = _clean_text(plan.capability).lower()
    return capability == "ssh_command" and bool(fallback_from) and reason == "guardrail_allowed_healthcheck"


def _slugify(value: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())).strip("-")


def _learning_recipe_id(action: dict[str, Any], plan: ActionPlan) -> str:
    if _is_guardrail_healthcheck_fallback(action, plan):
        target = _slugify(_clean_text(plan.connection_ref))
        return f"learned-ssh-health-check-{target}" if target else "learned-ssh-health-check"
    return _clean_text(action.get("candidate_id"))


def _learning_inputs(action: dict[str, Any], plan: ActionPlan, chosen_action: str) -> dict[str, Any]:
    inputs = dict(action.get("inputs", {}) or {})
    if _is_guardrail_healthcheck_fallback(action, plan):
        inputs["command"] = chosen_action
        fallback_from = _clean_text(action.get("guardrail_fallback_from"))
        if fallback_from:
            inputs["learned_from_command"] = fallback_from
    return inputs


def _learning_router_keywords(
    action: dict[str, Any],
    plan: ActionPlan,
    *,
    user_message: str = "",
) -> list[str]:
    keywords = [str(item or "").strip() for item in list(action.get("router_keywords", []) or []) if str(item or "").strip()]
    if _is_guardrail_healthcheck_fallback(action, plan):
        keywords.extend(
            [
                user_message,
                "server healthcheck",
                "server status",
                "healthcheck",
                "health check",
                "wie geht es",
                str(plan.connection_ref or ""),
            ]
        )
    return _unique_clean_list(keywords)


def _learning_recipe_scope(action: dict[str, Any], plan: ActionPlan) -> dict[str, Any]:
    scope = dict(action.get("recipe_scope", {}) or {})
    if _clean_text(plan.resolution_source).lower() == "plural_target_scope":
        scope["target_scope"] = "multi_target"
        scope["learning_origin"] = "plural_target_scope"
    if _is_guardrail_healthcheck_fallback(action, plan):
        connection_kind = _clean_text(plan.connection_kind).lower()
        connection_ref = _clean_text(plan.connection_ref)
        connection_kinds = [
            *list(scope.get("connection_kinds", []) or []),
            connection_kind,
        ]
        connection_refs = [
            *list(scope.get("connection_refs", []) or []),
            connection_ref,
        ]
        scope["connection_kinds"] = _unique_clean_list(connection_kinds)
        scope["connection_refs"] = _unique_clean_list(connection_refs)
        scope["learning_origin"] = GUARDRAIL_HEALTHCHECK_LEARNING_ORIGIN
    return scope


def _learning_intent(action: dict[str, Any], plan: ActionPlan) -> str:
    if _is_guardrail_healthcheck_fallback(action, plan):
        return "health_check"
    return _clean_text(action.get("intent"))


def _learning_title(action: dict[str, Any], plan: ActionPlan) -> str:
    if _is_guardrail_healthcheck_fallback(action, plan):
        target = _clean_text(plan.connection_ref)
        return f"Gelernter Server-Healthcheck: {target}" if target else "Gelernter Server-Healthcheck"
    return _clean_text(action.get("title"))


def _learning_preview(action: dict[str, Any], plan: ActionPlan, chosen_action: str) -> str:
    if _is_guardrail_healthcheck_fallback(action, plan):
        return f"SSH-Healthcheck aus Guardrail-Erfahrung: {chosen_action}"
    return _clean_text(action.get("preview"))


def _stored_recipe_single_step_capability(row: dict[str, Any]) -> str:
    steps = list(row.get("steps", []) or [])
    if len(steps) != 1:
        return ""
    step = dict(steps[0] or {})
    step_type = str(step.get("type", "") or "").strip().lower()
    return {
        "ssh_run": "ssh_command",
        "sftp_read": "file_read",
        "smb_read": "file_read",
        "sftp_write": "file_write",
        "smb_write": "file_write",
        "rss_read": "feed_read",
        "discord_send": "discord_send",
    }.get(step_type, "")


def _stored_recipe_single_step_chosen_action(row: dict[str, Any]) -> str:
    steps = list(row.get("steps", []) or [])
    if len(steps) != 1:
        return ""
    step = dict(steps[0] or {})
    step_type = str(step.get("type", "") or "").strip().lower()
    params = dict(step.get("params", {}) or {})
    if step_type == "ssh_run":
        return str(params.get("command", "") or "").strip()
    if step_type in {"sftp_read", "smb_read", "sftp_write", "smb_write"}:
        return str(params.get("remote_path", "") or "").strip()
    if step_type == "rss_read":
        return str(params.get("connection_ref", "") or "").strip()
    if step_type == "discord_send":
        return str(params.get("message", "") or "").strip()
    return ""


def record_routed_action_success(
    *,
    action: dict[str, Any],
    plan: ActionPlan,
    result_text: str,
    recorder: Callable[..., dict[str, Any] | None],
    user_message: str = "",
) -> dict[str, Any] | None:
    if not should_record_learned_recipe_success(action, plan):
        return None
    chosen_action = _chosen_action_from_plan(plan)
    if not chosen_action:
        return None
    return recorder(
        recipe_id=_learning_recipe_id(action, plan),
        title=_learning_title(action, plan),
        preview=_learning_preview(action, plan, chosen_action),
        inputs=_learning_inputs(action, plan, chosen_action),
        router_keywords=_learning_router_keywords(action, plan, user_message=user_message),
        recipe_scope=_learning_recipe_scope(action, plan),
        intent=_learning_intent(action, plan),
        connection_kind=str(plan.connection_kind or "").strip(),
        connection_ref=str(plan.connection_ref or "").strip(),
        capability=str(plan.capability or "").strip(),
        chosen_action=chosen_action,
        policy_result="allow",
        execution_result="success",
        user_feedback="",
        user_message=_clean_text(user_message),
        summary=str(result_text or "").strip(),
    )


def record_routed_stored_recipe_success(
    *,
    row: dict[str, Any],
    skill_result: Any,
    recorder: Callable[..., dict[str, Any] | None],
) -> dict[str, Any] | None:
    if not bool(getattr(skill_result, "success", False)):
        return None
    capability = _stored_recipe_single_step_capability(row)
    chosen_action = _stored_recipe_single_step_chosen_action(row)
    if not capability or not chosen_action:
        return None
    skill_id = str(row.get("id", "") or "").strip()
    metadata = stored_recipe_candidate_metadata(row)
    return recorder(
        recipe_id=f"learned-{skill_id}" if skill_id else "",
        title=str(row.get("name", "") or "").strip(),
        preview="",
        inputs=recipe_manifest_inputs(row),
        router_keywords=[str(item or "").strip() for item in list(row.get("router_keywords", []) or []) if str(item or "").strip()],
        recipe_scope=dict(metadata.get("recipe_scope", {}) or {}),
        intent=recipe_manifest_intent(row),
        connection_kind=str((metadata.get("recipe_scope", {}) or {}).get("connection_kinds", [""])[0] or "").strip(),
        connection_ref="",
        capability=capability,
        chosen_action=chosen_action,
        policy_result="allow",
        execution_result="success",
        user_feedback="",
        user_message="",
        summary=str(getattr(skill_result, "content", "") or "").strip(),
    )
