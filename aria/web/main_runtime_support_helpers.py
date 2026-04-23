from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from aria.core.auth import AuthManager


SettingsGetter = Callable[[], Any]
RawConfigReader = Callable[[], dict[str, Any]]
RoleSanitizer = Callable[[str | None], str]
AuthSessionResolver = Callable[[Any], dict[str, Any] | None]
DiagnosticsGetter = Callable[[Callable[[], Awaitable[dict[str, Any]]] | Callable[[], dict[str, Any]], bool], Awaitable[dict[str, Any]]]
DiagnosticsBuilder = Callable[[], Awaitable[dict[str, Any]] | dict[str, Any]]


@dataclass(frozen=True)
class MainRuntimeSupportDeps:
    base_dir: Path
    config_path: Path
    read_raw_config: RawConfigReader
    get_settings: SettingsGetter
    get_master_key: Callable[[Path], str]
    sanitize_role: RoleSanitizer
    get_auth_session_from_request: AuthSessionResolver
    get_or_refresh_startup_diagnostics: DiagnosticsGetter
    build_runtime_diagnostics: DiagnosticsBuilder


@dataclass(frozen=True)
class MainRuntimeSupportHelpers:
    list_prompt_files: Callable[[], list[dict[str, Any]]]
    get_profiles: Callable[[dict[str, Any], str], dict[str, dict[str, Any]]]
    get_active_profile_name: Callable[[dict[str, Any], str], str]
    set_active_profile: Callable[[dict[str, Any], str, str], None]
    get_secure_store: Callable[[dict[str, Any] | None], Any]
    get_auth_manager: Callable[[], AuthManager | None]
    active_admin_count: Callable[[list[dict[str, Any]]], int]
    get_runtime_preflight_data: Callable[[bool], Awaitable[dict[str, Any]]]
    update_finished_after_session: Callable[[Any, dict[str, Any]], bool]


def build_main_runtime_support_helpers(deps: MainRuntimeSupportDeps) -> MainRuntimeSupportHelpers:
    def _list_prompt_files() -> list[dict[str, Any]]:
        settings = deps.get_settings()
        prompt_paths: set[Path] = set()
        prompts_root = (deps.base_dir / "prompts").resolve()

        persona_path = (deps.base_dir / settings.prompts.persona).resolve()
        if persona_path.exists() and persona_path.suffix.lower() == ".md":
            prompt_paths.add(persona_path)

        skills_dir = (deps.base_dir / settings.prompts.skills_dir).resolve()
        if skills_dir.exists() and skills_dir.is_dir():
            for path in skills_dir.rglob("*.md"):
                if path.is_file():
                    prompt_paths.add(path.resolve())

        if prompts_root.exists():
            for path in prompts_root.rglob("*.md"):
                if path.is_file():
                    prompt_paths.add(path.resolve())

        rows: list[dict[str, Any]] = []
        for path in sorted(prompt_paths):
            try:
                rel = str(path.relative_to(deps.base_dir)).replace("\\", "/")
                stat = path.stat()
                rows.append(
                    {
                        "path": rel,
                        "name": path.name,
                        "group": "prompts",
                        "mode": "edit",
                        "size": int(stat.st_size),
                        "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    }
                )
            except (OSError, ValueError):
                continue
        return rows

    def _get_profiles(raw: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict):
            return {}
        section = profiles.get(kind, {})
        if not isinstance(section, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for name, payload in section.items():
            if isinstance(payload, dict):
                result[str(name)] = payload
        return result

    def _get_active_profile_name(raw: dict[str, Any], kind: str) -> str:
        profiles = raw.get("profiles", {})
        if not isinstance(profiles, dict):
            return ""
        active = profiles.get("active", {})
        if not isinstance(active, dict):
            return ""
        return str(active.get(kind, "")).strip()

    def _set_active_profile(raw: dict[str, Any], kind: str, profile_name: str) -> None:
        raw.setdefault("profiles", {})
        if not isinstance(raw["profiles"], dict):
            raw["profiles"] = {}
        raw["profiles"].setdefault("active", {})
        if not isinstance(raw["profiles"]["active"], dict):
            raw["profiles"]["active"] = {}
        raw["profiles"]["active"][kind] = profile_name

    def _get_secure_store(raw: dict[str, Any] | None = None):
        cfg = raw if isinstance(raw, dict) else deps.read_raw_config()
        security = cfg.get("security", {})
        if not isinstance(security, dict):
            security = {}
        if not bool(security.get("enabled", True)):
            return None
        master = deps.get_master_key(deps.config_path)
        if not master:
            return None
        db_rel = str(security.get("db_path", "data/auth/aria_secure.sqlite")).strip() or "data/auth/aria_secure.sqlite"
        db_path = Path(db_rel)
        if not db_path.is_absolute():
            db_path = (deps.base_dir / db_path).resolve()
        from aria.core.secure_store import SecureConfigStore, SecureStoreConfig, decode_master_key

        return SecureConfigStore(
            config=SecureStoreConfig(db_path=db_path, enabled=True),
            master_key=decode_master_key(master),
        )

    def _get_auth_manager() -> AuthManager | None:
        store = _get_secure_store()
        if not store:
            return None
        return AuthManager(store=store)

    def _active_admin_count(users: list[dict[str, Any]]) -> int:
        count = 0
        for row in users:
            role = deps.sanitize_role(row.get("role"))
            active = bool(row.get("active"))
            if role == "admin" and active:
                count += 1
        return count

    async def _get_runtime_preflight_data(force_refresh: bool = False) -> dict[str, Any]:
        return await deps.get_or_refresh_startup_diagnostics(
            deps.build_runtime_diagnostics,
            force_refresh=force_refresh,
        )

    def _update_finished_after_session(request: Any, update_control: dict[str, Any]) -> bool:
        auth = deps.get_auth_session_from_request(request)
        if not auth:
            return False
        if bool(update_control.get("running", False)):
            return False
        finished_raw = str(update_control.get("last_finished_at", "") or "").strip()
        if not finished_raw:
            return False
        try:
            finished_at = datetime.fromisoformat(finished_raw.replace("Z", "+00:00")).timestamp()
        except Exception:
            return False
        issued_at = int(auth.get("iat", 0) or 0)
        if issued_at <= 0:
            return False
        return finished_at > (issued_at + 1)

    return MainRuntimeSupportHelpers(
        list_prompt_files=_list_prompt_files,
        get_profiles=_get_profiles,
        get_active_profile_name=_get_active_profile_name,
        set_active_profile=_set_active_profile,
        get_secure_store=_get_secure_store,
        get_auth_manager=_get_auth_manager,
        active_admin_count=_active_admin_count,
        get_runtime_preflight_data=_get_runtime_preflight_data,
        update_finished_after_session=_update_finished_after_session,
    )
