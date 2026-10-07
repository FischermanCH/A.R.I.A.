"""Native read-only local release information owned by Release Update."""

from __future__ import annotations

from collections.abc import Mapping
import inspect
import json
from pathlib import Path
from typing import Any

from aria.modules.release_update.release_meta import read_release_meta
from aria.modules.release_update.release_meta import DEFAULT_RELEASE_LABEL
from aria.modules.release_update.update_check import get_update_status
from aria.modules.release_update.helper_client import resolve_update_helper_config, trigger_update_helper_run
from aria.modules.auth_policy.access_policy import is_admin
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

RELEASE_SOURCE_AUTHORITY = "release_update:local_release_files"
UPDATE_STATUS_SOURCE_AUTHORITY = "update:status_store"
_SECTIONS = {"all", "metadata", "changelog", "upgrade"}


def _bounded(path: Path, limit: int) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""


async def _load_release(runtime_owner: Any, section: str) -> Mapping[str, Any]:
    loader = getattr(runtime_owner, "_native_agent_release_loader", None)
    if callable(loader):
        result = loader(section)
        return await result if inspect.isawaitable(result) else result
    base_dir = Path(getattr(runtime_owner, "base_dir", Path(__file__).resolve().parents[3]))
    meta = read_release_meta(base_dir)
    return {
        "version": meta.get("version", ""), "label": meta.get("label", ""),
        "changelog": _bounded(base_dir / "CHANGELOG.md", 12000),
        "upgrade": _bounded(base_dir / "docs" / "wiki" / "Releases-and-Upgrades.md", 6000),
    }


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def update_run(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_admin_update_run_arguments_invalid")
        if not is_admin(context.auth_role):
            return NativeToolResult(json.dumps({
                "status": "forbidden_admin_only", "effect": "mutating",
                "message": "Administrator access is required.",
            }, ensure_ascii=True, sort_keys=True), "admin_update_run")
        try:
            trigger = getattr(runtime_owner, "_native_agent_update_run_trigger", None)
            if callable(trigger):
                raw = trigger()
                raw = await raw if inspect.isawaitable(raw) else raw
            else:
                secure_store = None
                secure_store_getter = getattr(runtime_owner, "_native_agent_secure_store_getter", None)
                if callable(secure_store_getter):
                    try:
                        secure_store = secure_store_getter(None)
                    except Exception:
                        secure_store = None
                config = resolve_update_helper_config(secure_store=secure_store)
                if not bool(getattr(config, "enabled", False)):
                    return NativeToolResult(json.dumps({
                        "status": "update_helper_disabled", "effect": "mutating",
                    }, ensure_ascii=True, sort_keys=True), "admin_update_run")
                raw = trigger_update_helper_run(config)
            if not isinstance(raw, Mapping):
                raise ValueError("native_agent_admin_update_run_result_invalid")
        except (RuntimeError, ValueError, OSError) as exc:
            status = "already_running" if "already running" in str(exc).casefold() else "update_trigger_failed"
            return NativeToolResult(json.dumps({
                "status": status, "effect": "mutating", "error_class": type(exc).__name__,
            }, ensure_ascii=True, sort_keys=True), "admin_update_run")
        payload: dict[str, Any] = {
            "status": str(raw.get("status") or "").strip() or "accepted",
            "effect": "mutating",
        }
        for key in ("accepted", "requested", "running"):
            if key in raw:
                payload[key] = bool(raw[key])
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "admin_update_run")

    async def update_status(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if arguments:
            raise ValueError("native_agent_admin_update_status_arguments_invalid")
        if not is_admin(context.auth_role):
            return NativeToolResult(json.dumps({
                "status": "forbidden_admin_only", "effect": "read_only",
                "message": "Administrator access is required.",
            }, ensure_ascii=True, sort_keys=True), "admin_update_status")
        loader = getattr(runtime_owner, "_native_agent_update_status_loader", None)
        if callable(loader):
            raw = loader()
            raw = await raw if inspect.isawaitable(raw) else raw
        else:
            base_dir = Path(getattr(runtime_owner, "base_dir", Path(__file__).resolve().parents[3]))
            raw = get_update_status(base_dir, current_label=DEFAULT_RELEASE_LABEL)
        if not isinstance(raw, Mapping):
            raise ValueError("native_agent_admin_update_status_result_invalid")
        payload = {
            "current_label": str(raw.get("current_label") or "").strip(),
            "available_label": str(raw.get("available_label") or raw.get("latest_label") or "").strip(),
            "update_available": bool(raw.get("update_available", False)),
            "checked_at": str(raw.get("checked_at") or "").strip(),
        }
        return NativeToolResult(json.dumps({
            "status": "ok", "effect": "read_only", "update": payload,
        }, ensure_ascii=True, sort_keys=True), "admin_update_status")

    async def read(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) - {"section"} or not isinstance(arguments.get("section", ""), str):
            raise ValueError("native_agent_release_arguments_invalid")
        section = str(arguments.get("section") or "all").strip()
        if section not in _SECTIONS:
            raise ValueError("native_agent_release_arguments_invalid")
        raw = await _load_release(runtime_owner, section)
        allowed = {key: str(raw.get(key) or "").strip() for key in ("version", "label", "changelog", "upgrade")}
        selected = {"version": allowed["version"], "label": allowed["label"]}
        if section in {"all", "changelog"}:
            selected["changelog"] = allowed["changelog"]
        if section in {"all", "upgrade"}:
            selected["upgrade"] = allowed["upgrade"]
        available = any(selected.values())
        payload = {"status": "ok", "effect": "read_only", "release": selected} if available else {
            "status": "release_information_unavailable", "effect": "read_only", "release": {},
            "message": "No local release information is available.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "product_release")

    return (NativeToolBinding(contract=NativeToolContract(
        owner_module_id="release_update", name="product_release_read",
        description="Read installed or bundled ARIA version, changelog and upgrade documentation from local files. Read-only.",
        input_schema={"type": "object", "properties": {
            "section": {"type": "string", "enum": sorted(_SECTIONS)},
        }, "required": []}, effect="read_only", confirmation_required=False,
        source_authority=RELEASE_SOURCE_AUTHORITY, user_scoped=False,
        rollout_flag="native_agent_memory_enabled", order=310,
    ), handler=read), NativeToolBinding(contract=NativeToolContract(
        owner_module_id="release_update", name="admin_update_status",
        description="Read the current administrative update status. Administrator-only and read-only.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="read_only", confirmation_required=False,
        source_authority=UPDATE_STATUS_SOURCE_AUTHORITY, user_scoped=False,
        rollout_flag="native_agent_admin_enabled", order=610,
    ), handler=update_status), NativeToolBinding(contract=NativeToolContract(
        owner_module_id="release_update", name="admin_update_run",
        description="Start the configured ARIA GUI Update Helper run. Administrator-only and confirmation required.",
        input_schema={"type": "object", "properties": {}, "required": []},
        effect="mutating", confirmation_required=True,
        source_authority=UPDATE_STATUS_SOURCE_AUTHORITY, user_scoped=False,
        rollout_flag="native_agent_admin_write_enabled", order=611,
    ), handler=update_run))
