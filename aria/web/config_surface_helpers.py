from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request

RawConfigReader = Callable[[], dict[str, Any]]
LocalizedMessage = Callable[[str, str, str], str]
ReturnToSanitizer = Callable[[str | None], str]
SurfacePathResolver = Callable[[str | None], str]


@dataclass(frozen=True)
class ConfigOverviewHelperDeps:
    read_raw_config: RawConfigReader
    msg: LocalizedMessage


def build_surface_path_resolver(
    *,
    sanitize_return_to: ReturnToSanitizer,
    allowed_paths: set[str],
    fallback: str,
) -> SurfacePathResolver:
    def resolve(candidate: str | None, *, fallback: str | None = None, fallback_override: str | None = None) -> str:
        clean = sanitize_return_to(candidate)
        if clean:
            parsed = urlsplit(clean)
            path = str(parsed.path or "").strip()
            if path in allowed_paths:
                return path
        return fallback_override or fallback

    return resolve


def format_config_info_message(lang: str, info: str, *, msg: LocalizedMessage) -> str:
    clean = str(info or "").strip()
    if not clean:
        return ""
    if clean.startswith("sample_imported:"):
        parts = clean.split(":")
        kind = str(parts[1] if len(parts) > 1 else "").strip().upper()
        imported_count = str(parts[2] if len(parts) > 2 else "").strip() or "0"
        skipped_count = str(parts[3] if len(parts) > 3 else "").strip() or "0"
        return msg(
            lang,
            f"Sample-Connection importiert: {kind} · neu: {imported_count} · übersprungen: {skipped_count}",
            f"Sample connection imported: {kind} · new: {imported_count} · skipped: {skipped_count}",
        )
    if clean.startswith("guardrail_sample_imported:"):
        parts = clean.split(":")
        imported_count = str(parts[1] if len(parts) > 1 else "").strip() or "0"
        skipped_count = str(parts[2] if len(parts) > 2 else "").strip() or "0"
        return msg(
            lang,
            f"Guardrail-Samples importiert: neu {imported_count} · übersprungen {skipped_count}",
            f"Guardrail samples imported: new {imported_count} · skipped {skipped_count}",
        )
    return clean


def build_config_overview_checks_helper(deps: ConfigOverviewHelperDeps) -> Callable[[Request], list[dict[str, str]]]:
    _read_raw_config = deps.read_raw_config
    _msg = deps.msg

    def build_config_overview_checks(request: Request) -> list[dict[str, str]]:
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = _read_raw_config()
        profiles = raw.get("profiles", {}) if isinstance(raw.get("profiles", {}), dict) else {}
        active_profiles = profiles.get("active", {}) if isinstance(profiles.get("active", {}), dict) else {}
        active_llm_profile = str(active_profiles.get("llm", "") or "").strip() or _msg(lang, "direkt / default", "direct / default")
        active_embedding_profile = str(active_profiles.get("embeddings", "") or "").strip() or _msg(lang, "direkt / default", "direct / default")
        return [
            {
                "status": "ok" if request.state.can_access_advanced_config else "warn",
                "title": _msg(lang, "Admin-Modus", "Admin mode"),
                "summary": _msg(lang, "aktiv", "active") if request.state.can_access_advanced_config else _msg(lang, "aus", "off"),
                "meta": _msg(
                    lang,
                    "Erweiterte Systembereiche sind sichtbar und können von hier aus verwaltet werden."
                    if request.state.can_access_advanced_config
                    else "Erweiterte Systembereiche sind ausgeblendet, bis Admin-Modus wieder aktiv ist.",
                    "Advanced system areas are visible and manageable from here."
                    if request.state.can_access_advanced_config
                    else "Advanced system areas stay hidden until admin mode is enabled again.",
                ),
            },
            {
                "status": "ok",
                "title": _msg(lang, "Aktives LLM-Profil", "Active LLM profile"),
                "summary": active_llm_profile,
                "meta": _msg(
                    lang,
                    "Das aktuell aktive Chat-Gehirn-Profil für Antworten und Tool-Entscheidungen.",
                    "The currently active chat-brain profile for answers and tool decisions.",
                ),
            },
            {
                "status": "ok",
                "title": _msg(lang, "Aktives Embedding-Profil", "Active embedding profile"),
                "summary": active_embedding_profile,
                "meta": _msg(
                    lang,
                    "Das Embedding-Profil für Memory, Ähnlichkeit und semantisches Routing.",
                    "The embedding profile used for memory, similarity, and semantic routing.",
                ),
            },
            {
                "status": "ok",
                "title": _msg(lang, "Workbench", "Workbench"),
                "summary": "3",
                "meta": _msg(
                    lang,
                    "Technische Spezialwerkzeuge bleiben hier gebündelt, statt in Produkt-Domänen zu verstreuen.",
                    "Technical specialist tools stay bundled here instead of leaking into product domains.",
                ),
            },
        ]

    return build_config_overview_checks
