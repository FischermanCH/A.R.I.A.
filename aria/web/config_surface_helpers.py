from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request

from aria.core.i18n import I18NStore

RawConfigReader = Callable[[], dict[str, Any]]
LocalizedMessage = Callable[[str, str, str], str]
ReturnToSanitizer = Callable[[str | None], str]
SurfacePathResolver = Callable[[str | None], str]
_CONFIG_SURFACE_HELPERS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _config_surface_text(lang: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CONFIG_SURFACE_HELPERS_I18N.t(lang or "de", f"config_surface_helpers.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


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
        return _config_surface_text(
            lang,
            "sample_imported",
            "Sample connection imported: {kind} · new: {imported_count} · skipped: {skipped_count}",
            kind=kind,
            imported_count=imported_count,
            skipped_count=skipped_count,
        )
    if clean.startswith("guardrail_sample_imported:"):
        parts = clean.split(":")
        imported_count = str(parts[1] if len(parts) > 1 else "").strip() or "0"
        skipped_count = str(parts[2] if len(parts) > 2 else "").strip() or "0"
        return _config_surface_text(
            lang,
            "guardrail_sample_imported",
            "Guardrail samples imported: new {imported_count} · skipped {skipped_count}",
            imported_count=imported_count,
            skipped_count=skipped_count,
        )
    return clean


def build_config_overview_checks_helper(deps: ConfigOverviewHelperDeps) -> Callable[[Request], list[dict[str, str]]]:
    _read_raw_config = deps.read_raw_config

    def build_config_overview_checks(request: Request) -> list[dict[str, str]]:
        lang = str(getattr(request.state, "lang", "de") or "de")
        raw = _read_raw_config()
        profiles = raw.get("profiles", {}) if isinstance(raw.get("profiles", {}), dict) else {}
        active_profiles = profiles.get("active", {}) if isinstance(profiles.get("active", {}), dict) else {}
        active_llm_profile = str(active_profiles.get("llm", "") or "").strip() or _config_surface_text(lang, "profile_direct_default", "direct / default")
        active_embedding_profile = str(active_profiles.get("embeddings", "") or "").strip() or _config_surface_text(lang, "profile_direct_default", "direct / default")
        return [
            {
                "status": "ok" if request.state.can_access_advanced_config else "warn",
                "title": _config_surface_text(lang, "admin_mode_title", "Admin mode"),
                "summary": _config_surface_text(lang, "status_active", "active") if request.state.can_access_advanced_config else _config_surface_text(lang, "status_off", "off"),
                "meta": _config_surface_text(lang, "admin_mode_meta_on", "Advanced system areas are visible and manageable from here.")
                if request.state.can_access_advanced_config
                else _config_surface_text(lang, "admin_mode_meta_off", "Advanced system areas stay hidden until admin mode is enabled again."),
            },
            {
                "status": "ok",
                "title": _config_surface_text(lang, "active_llm_profile", "Active LLM profile"),
                "summary": active_llm_profile,
                "meta": _config_surface_text(lang, "active_llm_meta", "The currently active chat-brain profile for answers and tool decisions."),
            },
            {
                "status": "ok",
                "title": _config_surface_text(lang, "active_embedding_profile", "Active embedding profile"),
                "summary": active_embedding_profile,
                "meta": _config_surface_text(lang, "active_embedding_meta", "The embedding profile used for memory, similarity, and semantic routing."),
            },
            {
                "status": "ok",
                "title": _config_surface_text(lang, "workbench_title", "Workbench"),
                "summary": "3",
                "meta": _config_surface_text(lang, "workbench_meta", "Technical specialist tools stay bundled here instead of leaking into product domains."),
            },
        ]

    return build_config_overview_checks
