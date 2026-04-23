from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Callable

from aria.core.routing_admin import ensure_connection_routing_index_ready


@dataclass(frozen=True)
class ConnectionAdminHelperDeps:
    connection_admin_specs: dict[str, dict[str, Any]]
    connection_edit_page: Callable[[str], str]
    connection_ref_query_param: Callable[[str], str]
    normalize_connection_kind: Callable[[str], str]
    delete_connection_health: Callable[[str], None]
    read_raw_config: Callable[[], dict[str, Any]]
    write_raw_config: Callable[[dict[str, Any]], None]
    reload_runtime: Callable[[], None]
    get_secure_store: Callable[[dict[str, Any] | None], Any]
    sanitize_connection_name: Callable[[str | None], str]
    settings: Any
    pipeline: Any


class ConnectionAdminHelpers:
    def __init__(self, deps: ConnectionAdminHelperDeps) -> None:
        self._deps = deps

    def get_connection_delete_spec(self, kind: str) -> dict[str, Any]:
        clean_kind = self._deps.normalize_connection_kind(kind)
        admin_spec = self._deps.connection_admin_specs.get(clean_kind)
        if not admin_spec:
            raise ValueError("Unbekannter Connection-Typ.")
        return {
            "section": clean_kind,
            "page": self._deps.connection_edit_page(clean_kind),
            "ref_query": self._deps.connection_ref_query_param(clean_kind),
            "secret_keys": list(admin_spec.get("secret_keys", [])),
            "health_prefix": str(admin_spec.get("health_prefix", clean_kind)),
            "success_message": str(admin_spec.get("success_message", "Connection-Profil gelöscht")),
        }

    async def trigger_connection_routing_refresh(self, *, wait: bool = False) -> None:
        with suppress(Exception):
            await ensure_connection_routing_index_ready(
                self._deps.settings,
                embedding_client=self._deps.pipeline.embedding_client,
                wait=wait,
            )

    def delete_connection_profile(self, kind: str, ref_raw: str) -> dict[str, Any]:
        spec = self.get_connection_delete_spec(kind)
        ref = self._deps.sanitize_connection_name(ref_raw)
        if not ref:
            raise ValueError("Connection-Ref ist ungültig.")
        raw = self._deps.read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}
        raw["connections"].setdefault(spec["section"], {})
        if not isinstance(raw["connections"][spec["section"]], dict):
            raw["connections"][spec["section"]] = {}
        rows = raw["connections"][spec["section"]]
        if ref not in rows:
            raise ValueError("Connection-Profil nicht gefunden.")
        rows.pop(ref, None)
        store = self._deps.get_secure_store(raw)
        if store:
            for key_tmpl in spec["secret_keys"]:
                store.delete_secret(str(key_tmpl).format(ref=ref))
        self._deps.write_raw_config(raw)
        self._deps.delete_connection_health(f"{spec['health_prefix']}:{ref}")
        self._deps.reload_runtime()
        return spec

    def prepare_connection_save(
        self,
        kind: str,
        connection_ref: str,
        original_ref: str = "",
    ) -> tuple[dict[str, Any], Any, dict[str, Any], str, str, bool]:
        spec = self.get_connection_delete_spec(kind)
        ref = self._deps.sanitize_connection_name(connection_ref)
        original_ref_clean = self._deps.sanitize_connection_name(original_ref)
        is_create = not original_ref_clean
        if not ref:
            raise ValueError("Connection-Ref ist ungültig.")
        raw = self._deps.read_raw_config()
        raw.setdefault("connections", {})
        if not isinstance(raw["connections"], dict):
            raw["connections"] = {}
        raw["connections"].setdefault(spec["section"], {})
        if not isinstance(raw["connections"][spec["section"]], dict):
            raw["connections"][spec["section"]] = {}
        rows = raw["connections"][spec["section"]]
        if is_create:
            if ref in rows:
                raise ValueError("Connection-Profil existiert bereits.")
        else:
            if original_ref_clean not in rows:
                raise ValueError("Connection-Profil nicht gefunden.")
            if ref != original_ref_clean and ref in rows:
                raise ValueError("Connection-Ref existiert bereits.")
        store = self._deps.get_secure_store(raw)
        return raw, store, rows, ref, original_ref_clean, is_create

    def _rename_connection_secret(self, store: Any, key_from: str, key_to: str) -> None:
        if not store or key_from == key_to:
            return
        value = store.get_secret(key_from, default=None)
        if value in (None, ""):
            return
        store.set_secret(key_to, value)
        store.delete_secret(key_from)

    async def finalize_connection_save(
        self,
        kind: str,
        *,
        raw: dict[str, Any],
        rows: dict[str, Any],
        ref: str,
        original_ref: str,
        row_value: dict[str, Any],
        store: Any = None,
        secret_renames: list[tuple[str, str]] | None = None,
    ) -> None:
        spec = self.get_connection_delete_spec(kind)
        rows[ref] = row_value
        if original_ref and original_ref != ref:
            rows.pop(original_ref, None)
            self._deps.delete_connection_health(f"{spec['health_prefix']}:{original_ref}")
            if store:
                for src, dest in secret_renames or []:
                    self._rename_connection_secret(store, src, dest)
        self._deps.write_raw_config(raw)
        self._deps.reload_runtime()
        await self.trigger_connection_routing_refresh(wait=True)
