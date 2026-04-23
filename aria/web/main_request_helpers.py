from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Request


Translator = Callable[[str, str, str], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
CookieValueResolver = Callable[[Request, str], str]


@dataclass(frozen=True)
class MainRequestHelperDeps:
    translate: Translator
    custom_skill_desc_i18n_fallbacks: dict[str, dict[str, str]]
    get_auth_session_from_request: AuthSessionResolver
    request_cookie_value: CookieValueResolver
    username_cookie: str


@dataclass(frozen=True)
class MainRequestHelpers:
    format_skill_routing_info: Callable[[str, str], str]
    localize_custom_skill_description: Callable[[dict[str, Any], str], str]
    sanitize_username: Callable[[str | None], str]
    get_username_from_request: Callable[[Request], str]
    sanitize_role: Callable[[str | None], str]
    sanitize_collection_name: Callable[[str | None], str]
    sanitize_session_id: Callable[[str | None], str]
    sanitize_csrf_token: Callable[[str | None], str]


def build_main_request_helpers(deps: MainRequestHelperDeps) -> MainRequestHelpers:
    def _format_skill_routing_info(lang: str, raw_info: str) -> str:
        value = str(raw_info or "").strip()
        if not value:
            return ""
        if value == "rebuild":
            return deps.translate(lang, "config_skill_routing.info_rebuild", "Trigger index rebuilt.")
        if value.startswith("suggest-all:"):
            parts = value.split(":")
            if len(parts) == 3:
                updated = parts[1]
                total = parts[2]
                text = deps.translate(
                    lang,
                    "config_skill_routing.info_suggest_all",
                    "LLM suggestion applied: {updated} skills updated, {total} keywords generated.",
                )
                return text.format(updated=updated, total=total)
        if value.startswith("suggest:"):
            parts = value.split(":")
            if len(parts) == 3:
                skill_id = parts[1]
                total = parts[2]
                text = deps.translate(
                    lang,
                    "config_skill_routing.info_suggest_one",
                    "LLM suggestion applied for {skill}: {total} keywords generated.",
                )
                return text.format(skill=skill_id, total=total)
        if value.startswith("keywords:auto:"):
            total = value.split(":")[-1]
            text = deps.translate(
                lang,
                "config_skill_routing.info_auto_keywords",
                "Auto-generated {total} trigger keywords via LLM.",
            )
            return text.format(total=total)
        if value.startswith("deleted:"):
            skill_id = value.split(":", 1)[1]
            text = deps.translate(lang, "skills.deleted_info", "Skill deleted: {skill}.")
            return text.format(skill=skill_id)
        if value.startswith("imported:"):
            skill_id = value.split(":", 1)[1]
            text = deps.translate(lang, "skills.imported_info", "Skill imported: {skill}.")
            return text.format(skill=skill_id)
        return value

    def _localize_custom_skill_description(manifest: dict[str, Any], lang: str) -> str:
        lang_code = str(lang or "de").strip().lower() or "de"
        i18n_map = manifest.get("description_i18n", {})
        if isinstance(i18n_map, dict):
            value = str(i18n_map.get(lang_code, "")).strip()
            if value:
                return value
        fallback = str(manifest.get("description", "")).strip()
        if lang_code == "de":
            return fallback
        mapped = deps.custom_skill_desc_i18n_fallbacks.get(fallback, {}).get(lang_code, "")
        return str(mapped or fallback)

    def _sanitize_username(value: str | None) -> str:
        if not value:
            return ""
        clean = re.sub(r"\s+", " ", value).strip()
        clean = re.sub(r"[^\w .-]", "", clean, flags=re.UNICODE)
        return clean[:40].strip()

    def _get_username_from_request(request: Request) -> str:
        auth_session = deps.get_auth_session_from_request(request)
        if auth_session:
            return _sanitize_username(auth_session.get("username"))
        return _sanitize_username(deps.request_cookie_value(request, deps.username_cookie))

    def _sanitize_role(value: str | None) -> str:
        role = str(value or "").strip().lower()
        if role not in {"admin", "user"}:
            return "user"
        return role

    def _sanitize_collection_name(value: str | None) -> str:
        if not value:
            return ""
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
        clean = re.sub(r"_+", "_", clean)
        return clean[:64]

    def _sanitize_session_id(value: str | None) -> str:
        if not value:
            return ""
        clean = re.sub(r"[^a-zA-Z0-9_-]", "", value)
        return clean[:32]

    def _sanitize_csrf_token(value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if not re.fullmatch(r"[A-Za-z0-9_\-]{20,128}", raw):
            return ""
        return raw

    return MainRequestHelpers(
        format_skill_routing_info=_format_skill_routing_info,
        localize_custom_skill_description=_localize_custom_skill_description,
        sanitize_username=_sanitize_username,
        get_username_from_request=_get_username_from_request,
        sanitize_role=_sanitize_role,
        sanitize_collection_name=_sanitize_collection_name,
        sanitize_session_id=_sanitize_session_id,
        sanitize_csrf_token=_sanitize_csrf_token,
    )
