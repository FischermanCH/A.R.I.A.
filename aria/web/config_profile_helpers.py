from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus

import yaml

from aria.core.connection_admin import CONNECTION_ADMIN_SPECS
from aria.core.connection_catalog import normalize_connection_kind
from aria.web.config_misc_helpers import (
    embedding_fingerprint_for_values,
    embedding_switch_requires_confirmation,
    memory_point_totals,
    resolve_embedding_model_label,
    short_fingerprint,
)
from aria.web.connection_support_helpers import (
    SAMPLE_CONNECTIONS_DIR,
    friendly_ssh_setup_error_impl,
)

EMBEDDING_SWITCH_CONFIRM_PHRASE = "EMBEDDINGS WECHSELN"


@dataclass(slots=True)
class ConfigProfileHelperDeps:
    read_raw_config: Callable[[], dict[str, Any]]
    write_raw_config: Callable[[dict[str, Any]], None]
    reload_runtime: Callable[[], None]
    sanitize_connection_name: Callable[[str | None], str]
    get_active_profile_name: Callable[[dict[str, Any], str], str]
    settings: Any
    pipeline: Any


class ConfigProfileHelpers:
    def __init__(self, deps: ConfigProfileHelperDeps) -> None:
        self._deps = deps

    @staticmethod
    def msg(lang: str, de: str, en: str) -> str:
        return de if str(lang or "de").strip().lower().startswith("de") else en

    def friendly_route_error(self, lang: str, exc: Exception, de_default: str, en_default: str) -> str:
        if isinstance(exc, ValueError):
            detail = str(exc).strip()
            if detail:
                return detail
        return self.msg(lang, de_default, en_default)

    def friendly_ssh_setup_error(self, lang: str, exc: Exception) -> str:
        return friendly_ssh_setup_error_impl(lang, exc)

    async def embedding_memory_guard_context(self, username: str) -> dict[str, Any]:
        memory_stats: list[dict[str, Any]] = []
        if getattr(self._deps.pipeline, "memory_skill", None):
            with suppress(Exception):
                memory_stats = list(await self._deps.pipeline.memory_skill.get_user_collection_stats(username))
        memory_point_count, memory_collection_count = memory_point_totals(memory_stats)
        current_fingerprint = embedding_fingerprint_for_values(
            self._deps.settings.embeddings.model,
            self._deps.settings.embeddings.api_base,
        )
        memory_fingerprint = str(getattr(self._deps.settings.memory, "embedding_fingerprint", "") or "").strip() or current_fingerprint
        memory_model = str(getattr(self._deps.settings.memory, "embedding_model", "") or "").strip() or resolve_embedding_model_label(
            self._deps.settings.embeddings.model,
            self._deps.settings.embeddings.api_base,
        )
        return {
            "memory_stats": memory_stats,
            "memory_point_count": memory_point_count,
            "memory_collection_count": memory_collection_count,
            "current_fingerprint": current_fingerprint,
            "current_fingerprint_short": short_fingerprint(current_fingerprint),
            "memory_fingerprint": memory_fingerprint,
            "memory_fingerprint_short": short_fingerprint(memory_fingerprint),
            "memory_model": memory_model,
            "requires_switch_confirmation": memory_point_count > 0,
            "confirm_phrase": EMBEDDING_SWITCH_CONFIRM_PHRASE,
            "export_url": "/memories/export?type=all&sort=updated_desc",
            "memory_fingerprint_tracked": bool(str(getattr(self._deps.settings.memory, "embedding_fingerprint", "") or "").strip()),
        }

    async def guard_embedding_switch(
        self,
        *,
        username: str,
        new_model: str,
        new_api_base: str,
        confirm_switch: str,
        confirm_phrase: str,
    ) -> tuple[str, str]:
        new_fingerprint = embedding_fingerprint_for_values(new_model, new_api_base)
        resolved_model = resolve_embedding_model_label(new_model, new_api_base)
        guard = await self.embedding_memory_guard_context(username)
        if embedding_switch_requires_confirmation(
            guard["memory_fingerprint"],
            new_fingerprint,
            guard["memory_point_count"],
        ):
            confirmed = str(confirm_switch or "").strip().lower() in {"1", "true", "yes", "on"}
            typed_phrase = str(confirm_phrase or "").strip().upper()
            if not confirmed or typed_phrase != EMBEDDING_SWITCH_CONFIRM_PHRASE:
                raise ValueError(
                    "Embedding-Wechsel blockiert: Vorhandenes Memory/RAG wurde mit einem anderen Embedding-Fingerprint erstellt. "
                    f"Bitte zuerst exportieren ({guard['export_url']}) und den Wechsel bewusst bestaetigen "
                    f"({EMBEDDING_SWITCH_CONFIRM_PHRASE})."
                )
        return new_fingerprint, resolved_model

    def connection_saved_test_info(self, kind_label: str, lang: str, *, success: bool) -> str:
        if success:
            return self.msg(
                lang,
                f"{kind_label}-Profil gespeichert · Verbindung erfolgreich getestet",
                f"{kind_label} profile saved · connection test succeeded",
            )
        return self.msg(
            lang,
            f"{kind_label}-Profil gespeichert · Verbindungstest fehlgeschlagen",
            f"{kind_label} profile saved · connection test failed",
        )

    def active_profile_runtime_meta(self, raw: dict[str, Any], kind: str) -> dict[str, str]:
        active_name = self._deps.get_active_profile_name(raw, kind) or "default"
        current = self._deps.settings.llm if kind == "llm" else self._deps.settings.embeddings
        return {
            "active_name": active_name,
            "model": str(getattr(current, "model", "") or "").strip(),
            "api_base": str(getattr(current, "api_base", "") or "").strip(),
        }

    @staticmethod
    def profile_test_redirect_url(page: str, *, ok: bool, message: str) -> str:
        key = "info" if ok else "error"
        return f"{page}?test_status={'ok' if ok else 'error'}&{key}={quote_plus(str(message))}"

    def profile_test_result_message(self, kind: str, active_name: str, result: dict[str, Any], lang: str) -> str:
        label = self.msg(lang, "LLM-Profil", "LLM profile") if kind == "llm" else self.msg(lang, "Embedding-Profil", "Embedding profile")
        active = str(active_name or "default").strip() or "default"
        detail = str(result.get("detail", "") or "").strip()
        if str(result.get("status", "")).strip().lower() == "ok":
            return self.msg(
                lang,
                f"{label} „{active}“ erfolgreich getestet.",
                f"{label} '{active}' tested successfully.",
            )
        return self.msg(
            lang,
            f"{label} „{active}“ Test fehlgeschlagen: {detail or '-'}",
            f"{label} '{active}' test failed: {detail or '-'}",
        )

    def import_sample_connection_manifest(self, sample_file: str) -> tuple[str, int, int]:
        clean_name = Path(str(sample_file or "").strip()).name
        if not clean_name or not clean_name.endswith(".sample.yaml"):
            raise ValueError("Unbekanntes Sample-Connection-Profil.")
        sample_path = SAMPLE_CONNECTIONS_DIR / clean_name
        if not sample_path.exists() or not sample_path.is_file():
            raise ValueError("Sample-Connection nicht gefunden.")
        payload = yaml.safe_load(sample_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Sample-Import erwartet ein YAML-Objekt.")

        sample_connections = payload.get("connections")
        if not isinstance(sample_connections, dict) or not sample_connections:
            raise ValueError("Sample-Connection enthält keine Connections.")

        raw = self._deps.read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}

        imported_count = 0
        skipped_count = 0
        primary_kind = ""
        for raw_kind, profiles in sample_connections.items():
            kind = normalize_connection_kind(str(raw_kind).strip())
            if not kind or kind not in CONNECTION_ADMIN_SPECS or not isinstance(profiles, dict):
                continue
            primary_kind = primary_kind or kind
            raw["connections"].setdefault(kind, {})
            if not isinstance(raw["connections"][kind], dict):
                raw["connections"][kind] = {}
            for raw_ref, profile in profiles.items():
                ref = self._deps.sanitize_connection_name(str(raw_ref).strip())
                if not ref or not isinstance(profile, dict):
                    skipped_count += 1
                    continue
                if ref in raw["connections"][kind]:
                    skipped_count += 1
                    continue
                raw["connections"][kind][ref] = dict(profile)
                imported_count += 1

        if not primary_kind:
            raise ValueError("Sample-Connection-Typ ist nicht unterstützt.")
        if imported_count <= 0 and skipped_count <= 0:
            raise ValueError("Sample-Connection enthält keine importierbaren Profile.")
        self._deps.write_raw_config(raw)
        self._deps.reload_runtime()
        return primary_kind, imported_count, skipped_count


def build_config_profile_helpers(deps: ConfigProfileHelperDeps) -> ConfigProfileHelpers:
    return ConfigProfileHelpers(deps)
