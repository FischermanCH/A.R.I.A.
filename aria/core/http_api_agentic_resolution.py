from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from aria.core.action_plan import ActionPlan
from aria.core.agentic_action_resolution import (
    action_draft_from_http_request,
    agentic_action_contract_prompt,
    agentic_debug_line,
    http_policy_result_from_decision,
)
from aria.core.http_api_policy import HTTPAPIPolicyDecision, validate_http_api_request_policy
from aria.core.i18n import I18NStore

_HTTP_API_AGENTIC_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")

_STATUS_PATH_HINTS = {
    "/",
    "/health",
    "/status",
    "/ready",
    "/live",
    "/ping",
    "/version",
    "/metrics",
}


def _http_api_agentic_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for lang in ("de", "en"):
        raw = _HTTP_API_AGENTIC_I18N.t(lang, f"http_api_agentic_resolution.{key}", "")
        terms.extend(term.strip().lower() for term in raw.split(",") if term.strip())
    return tuple(dict.fromkeys(terms)) or fallback


def is_http_api_status_like_request(message: str) -> bool:
    clean = str(message or "").strip().lower()
    if not clean:
        return False
    return any(
        token in clean
        for token in _http_api_agentic_terms(
            "status_like_terms",
            ("status", "health", "healthcheck", "health check", "alive", "availability"),
        )
    )


def normalize_http_api_path(path: str, *, health_path: str = "/", base_url: str = "") -> str:
    clean = str(path or "").strip()
    if not clean:
        return str(health_path or "/").strip() or "/"
    if clean.startswith("http://") or clean.startswith("https://"):
        parts = urlsplit(clean)
        normalized = parts.path or "/"
        if parts.query:
            normalized += f"?{parts.query}"
        return normalized
    if clean.startswith("?"):
        return f"{str(health_path or '/').strip() or '/'}{clean}"
    if not clean.startswith("/"):
        clean = "/" + clean.lstrip("/")
    _ = base_url
    return clean


def http_api_notes_mark_status_like(notes: list[str] | None) -> bool:
    note_set = {str(item or "").strip().lower() for item in list(notes or []) if str(item or "").strip()}
    return "api_status_like" in note_set or "api_agentic_request" in note_set


async def resolve_http_api_request_from_dossier(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    existing_path: str = "",
    existing_content: str = "",
    user_id: str = "",
    language: str | None = None,
    build_http_api_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if client is None or not str(connection_ref or "").strip():
        return {}
    dossier = build_http_api_target_dossier(connection_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("http_api_request")
                    + " "
                    "You decide one concrete HTTP API request target for ARIA. "
                    "Choose one request path and optional body text for the already-configured HTTP API target. "
                    "Prefer read-only, status-like requests. "
                    "If the user asks for status or health and the dossier has a health_path, prefer it unless the user named a more specific path. "
                    "Preserve an explicit request path when one is already present. "
                    "Return JSON only with this shape: "
                    '{"path":"<path or empty>","content":"<body text or empty>","confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Existing path: {str(existing_path or '').strip()}\n"
                    f"Existing content: {str(existing_content or '').strip()}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="http_api_request_decision",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    return {
        "path": str(payload.get("path", "") or "").strip(),
        "content": str(payload.get("content", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "dossier": dossier,
    }


def http_api_request_review_issues(path: str, content: str, *, method: str) -> list[str]:
    clean_path = str(path or "").strip()
    clean_content = str(content or "").strip()
    clean_method = str(method or "").strip().upper()
    issues: list[str] = []
    if clean_path.startswith("http://") or clean_path.startswith("https://"):
        issues.append("full_url_instead_of_path")
    if clean_path and not clean_path.startswith(("/", "?")):
        issues.append("missing_leading_slash")
    if len(clean_path) > 160:
        issues.append("path_too_long")
    if clean_method == "GET" and clean_content:
        issues.append("body_for_get_request")
    deduped: list[str] = []
    for issue in issues:
        if issue not in deduped:
            deduped.append(issue)
    return deduped


async def review_http_api_request_candidate(
    *,
    client: Any | None,
    message: str,
    connection_ref: str,
    path: str,
    content: str,
    issues: list[str],
    user_id: str = "",
    language: str | None = None,
    build_http_api_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if client is None or not issues or not str(connection_ref or "").strip():
        return {}
    dossier = build_http_api_target_dossier(connection_ref, user_id=user_id)
    if not dossier:
        return {}
    response = await client.chat(
        [
            {
                "role": "system",
                "content": (
                    agentic_action_contract_prompt("http_api_request_review")
                    + " "
                    "You review one HTTP API request target for ARIA. "
                    "Keep the request read-oriented and simple. "
                    "If the proposed path or body is awkward, simplify it while preserving the user's goal. "
                    "Return JSON only with this shape: "
                    '{"path":"<path or empty>","content":"<body text or empty>","confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}'
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Language: {str(language or 'de').strip() or 'de'}\n"
                    f"User request: {str(message or '').strip()}\n"
                    f"Current path: {str(path or '').strip()}\n"
                    f"Current content: {str(content or '').strip()}\n"
                    f"Review issues: {json.dumps(list(issues), ensure_ascii=False)}\n"
                    f"Target dossier: {json.dumps(dossier, ensure_ascii=False)}"
                ),
            },
        ],
        source="routing",
        operation="http_api_request_review",
        user_id=user_id,
    )
    payload = extract_json_object(getattr(response, "content", "") or "")
    if not payload:
        return {}
    return {
        "path": str(payload.get("path", "") or "").strip(),
        "content": str(payload.get("content", "") or "").strip(),
        "confidence": str(payload.get("confidence", "") or "").strip().lower(),
        "ask_user": bool(payload.get("ask_user", False)),
        "reason": str(payload.get("reason", "") or "").strip(),
        "issues": list(issues),
    }


async def apply_agentic_http_api_resolution(
    *,
    client: Any | None,
    settings: Any,
    message: str,
    plan: ActionPlan,
    user_id: str = "",
    language: str | None = None,
    build_http_api_target_dossier: Callable[..., dict[str, Any]],
    extract_json_object: Callable[[str], dict[str, Any]],
    routing_debug_enabled: Callable[[], bool],
) -> tuple[ActionPlan, list[str], HTTPAPIPolicyDecision | None]:
    if str(plan.connection_kind or "").strip().lower() != "http_api" or not str(plan.connection_ref or "").strip():
        return plan, [], None
    dossier = build_http_api_target_dossier(plan.connection_ref, user_id=user_id)
    if not dossier:
        return plan, [], None
    configured_method = str(dossier.get("configured_method", "GET") or "GET").strip().upper() or "GET"
    existing_path = str(plan.path or "").strip()
    should_decide = not existing_path and is_http_api_status_like_request(message)
    notes = list(plan.notes or [])
    debug_lines: list[str] = []
    content = str(plan.content or "").strip()
    path = existing_path
    if should_decide:
        api_rows = getattr(getattr(settings, "connections", object()), "http_api", {})
        if isinstance(api_rows, dict) and len([ref for ref in api_rows.keys() if str(ref).strip()]) == 1:
            path = normalize_http_api_path(
                str(dossier.get("health_path", "/") or "/"),
                health_path=str(dossier.get("health_path", "/") or "/"),
                base_url=str(dossier.get("base_url", "") or ""),
            )
            content = ""
            agentic_draft = action_draft_from_http_request(
                connection_ref=plan.connection_ref,
                path=path,
                content=content,
                method=configured_method,
                source="configured_health_path",
                confidence="high",
                reason="single_profile_status_path",
            )
            if routing_debug_enabled():
                debug_lines.append(
                    agentic_debug_line(
                        "http_api_request_decision",
                        connection_ref=plan.connection_ref,
                        fields={
                            "path": path,
                            "confidence": "high",
                            "reason": "single configured HTTP API profile uses configured health path for status-like request",
                        },
                        draft=agentic_draft,
                    )
                )
            if "api_agentic_request" not in notes:
                notes.append("api_agentic_request")
            if "api_status_like" not in notes:
                notes.append("api_status_like")
            policy = validate_http_api_request_policy(
                path,
                content=content,
                method=configured_method,
                health_path=str(dossier.get("health_path", "/") or "/"),
                status_like=True,
            )
            agentic_policy = http_policy_result_from_decision(policy, fallback_path=path)
            if routing_debug_enabled():
                debug_lines.append(
                    agentic_debug_line(
                        "http_api_request_policy",
                        connection_ref=plan.connection_ref,
                        fields={"action": policy.action, "reason": policy.reason, "path": policy.normalized_path or path},
                        draft=agentic_draft,
                        policy=agentic_policy,
                    )
                )
            return replace(plan, path=policy.normalized_path or path, content=policy.normalized_content, notes=notes), debug_lines, policy
        resolved = await resolve_http_api_request_from_dossier(
            client=client,
            message=message,
            connection_ref=plan.connection_ref,
            existing_path=existing_path,
            existing_content=content,
            user_id=user_id,
            language=language,
            build_http_api_target_dossier=build_http_api_target_dossier,
            extract_json_object=extract_json_object,
        )
        candidate_path = str(resolved.get("path", "") or "").strip() or str(dossier.get("health_path", "/") or "/").strip() or "/"
        candidate_content = str(resolved.get("content", "") or "").strip()
        path = normalize_http_api_path(
            candidate_path,
            health_path=str(dossier.get("health_path", "/") or "/"),
            base_url=str(dossier.get("base_url", "") or ""),
        )
        content = candidate_content
        agentic_draft = action_draft_from_http_request(
            connection_ref=plan.connection_ref,
            path=path,
            content=content,
            method=configured_method,
            source="llm_decision",
            confidence=str(resolved.get("confidence", "") or "").strip(),
            reason=str(resolved.get("reason", "") or "").strip(),
            ask_user=bool(resolved.get("ask_user", False)),
        )
        if routing_debug_enabled():
            debug_lines.append(
                agentic_debug_line(
                    "http_api_request_decision",
                    connection_ref=plan.connection_ref,
                    fields={
                        "path": path,
                        "confidence": str(resolved.get("confidence", "") or "").strip() or "unknown",
                        "reason": str(resolved.get("reason", "") or "").strip() or "n/a",
                    },
                    draft=agentic_draft,
                )
            )
        review_issues = http_api_request_review_issues(path, content, method=configured_method)
        if review_issues:
            reviewed = await review_http_api_request_candidate(
                client=client,
                message=message,
                connection_ref=plan.connection_ref,
                path=path,
                content=content,
                issues=review_issues,
                user_id=user_id,
                language=language,
                build_http_api_target_dossier=build_http_api_target_dossier,
                extract_json_object=extract_json_object,
            )
            reviewed_path = normalize_http_api_path(
                str(reviewed.get("path", "") or "").strip() or path,
                health_path=str(dossier.get("health_path", "/") or "/"),
                base_url=str(dossier.get("base_url", "") or ""),
            )
            reviewed_content = str(reviewed.get("content", "") or "").strip() or content
            if reviewed_path:
                path = reviewed_path
            content = reviewed_content
            agentic_draft = action_draft_from_http_request(
                connection_ref=plan.connection_ref,
                path=path,
                content=content,
                method=configured_method,
                source="llm_review",
                confidence=str(reviewed.get("confidence", "") or "").strip(),
                reason=str(reviewed.get("reason", "") or "").strip(),
                ask_user=bool(reviewed.get("ask_user", False)),
                review_issues=review_issues,
            )
            if routing_debug_enabled():
                debug_lines.append(
                    agentic_debug_line(
                        "http_api_request_review",
                        connection_ref=plan.connection_ref,
                        fields={
                            "issues": ",".join(review_issues),
                            "path": path,
                            "reason": str(reviewed.get("reason", "") or "").strip() or "n/a",
                        },
                        draft=agentic_draft,
                    )
                )
        if "api_agentic_request" not in notes:
            notes.append("api_agentic_request")
        if "api_status_like" not in notes:
            notes.append("api_status_like")
    policy = validate_http_api_request_policy(
        path,
        content=content,
        method=configured_method,
        health_path=str(dossier.get("health_path", "/") or "/"),
        status_like=http_api_notes_mark_status_like(notes),
    )
    agentic_draft = action_draft_from_http_request(
        connection_ref=plan.connection_ref,
        path=policy.normalized_path or path,
        content=policy.normalized_content,
        method=configured_method,
        source="llm_decision" if "api_agentic_request" in {str(item or "").strip() for item in notes} else "existing_plan",
    )
    agentic_policy = http_policy_result_from_decision(policy, fallback_path=path)
    if routing_debug_enabled():
        debug_lines.append(
            agentic_debug_line(
                "http_api_request_policy",
                connection_ref=plan.connection_ref,
                fields={"action": policy.action, "reason": policy.reason, "path": policy.normalized_path or path},
                draft=agentic_draft,
                policy=agentic_policy,
            )
        )
    return replace(plan, path=policy.normalized_path or path, content=policy.normalized_content, notes=notes), debug_lines, policy
