"""Native read-only exact Recipe inspection owned by Recipe Runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import inspect
import json
from typing import Any

from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult
from aria.modules.recipe_runtime.pipeline_helpers import expand_recipe_connection_bindings
from aria.modules.platform_primitives.actionable_sequence import (
    CROSS_HOST_RECIPE_SUGGESTIONS,
    LAST_ACTIONABLE_SEQUENCE_STORE,
    actionable_sequence_to_recipe_steps,
)
from aria.modules.recipe_store.manifests import load_stored_recipe_manifests, save_stored_recipe_manifest

RECIPE_SOURCE_AUTHORITY = "recipes:validated_runtime_manifests"
CONNECTION_READ_SOURCE_AUTHORITIES = {
    "google_calendar": "google_calendar:configured_profile",
    "sftp": "sftp:configured_profile",
    "smb": "smb:configured_profile",
    "imap": "imap:configured_profile",
}
CONNECTION_SEND_SOURCE_AUTHORITIES = {
    "discord": "discord:configured_profile",
    "webhook": "webhook:configured_profile",
    "email": "email:configured_profile",
    "mqtt": "mqtt:configured_profile",
    "sftp": "sftp:configured_profile",
    "smb": "smb:configured_profile",
    "http_api": "http_api:configured_profile",
}
_SECRET_PARAMETER_MARKERS = ("password", "passwd", "secret", "token", "api_key", "apikey", "private_key")


def _safe_parameter_name(value: Any) -> str:
    name = str(value or "").strip()
    lowered = name.lower()
    return "" if any(marker in lowered for marker in _SECRET_PARAMETER_MARKERS) else name


async def _load_recipes(runtime_owner: Any) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_recipe_loader", None)
    if callable(loader):
        result = loader()
        return await result if inspect.isawaitable(result) else result
    runtime_loader = getattr(runtime_owner, "_load_stored_recipe_runtime", None)
    return tuple(runtime_loader()) if callable(runtime_loader) else ()


def _safe_recipe(item: Mapping[str, Any], *, preview: bool) -> dict[str, Any]:
    steps = []
    for raw in item.get("steps", ()):
        if not isinstance(raw, Mapping):
            continue
        params = raw.get("params", {})
        params = params if isinstance(params, Mapping) else {}
        step = {
            "id": str(raw.get("id") or "").strip(),
            "name": str(raw.get("name") or "").strip(),
            "type": str(raw.get("type") or "").strip(),
            "on_error": str(raw.get("on_error") or "stop").strip(),
            "parameter_names": sorted(name for key in params if (name := _safe_parameter_name(key))),
        }
        connection_ref = str(params.get("connection_ref") or "").strip()
        if connection_ref:
            step["connection_ref"] = connection_ref
        if preview:
            step["sequence"] = len(steps) + 1
        steps.append(step)
    return {
        "id": str(item.get("id") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "description": str(item.get("description") or "").strip(),
        "connections": [str(value).strip() for value in item.get("connections", ()) if str(value).strip()],
        "steps": steps,
    }


async def _exact_recipe(
    runtime_owner: Any,
    recipe_id: str,
    *,
    recipes: Sequence[Mapping[str, Any]] | None = None,
) -> Mapping[str, Any] | None:
    source = recipes if recipes is not None else await _load_recipes(runtime_owner)
    identifier = str(recipe_id or "").strip()
    enabled = [item for item in source if bool(item.get("enabled", False))]
    id_matches = [item for item in enabled if str(item.get("id") or "").strip() == identifier]
    if id_matches:
        return id_matches[0] if len(id_matches) == 1 else None
    folded_identifier = identifier.casefold()
    name_matches = [
        item for item in enabled
        if str(item.get("name") or "").strip().casefold() == folded_identifier
    ]
    return name_matches[0] if len(name_matches) == 1 else None


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    def recipe_remember_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
        if set(arguments) - {"name", "description", "_frozen_recipe"}:
            raise ValueError("native_agent_recipe_remember_arguments_invalid")
        values: dict[str, Any] = {}
        for key in ("name", "description"):
            value = arguments.get(key, "")
            if not isinstance(value, str):
                raise ValueError("native_agent_recipe_remember_arguments_invalid")
            if value.strip():
                values[key] = value.strip()
        frozen = arguments.get("_frozen_recipe")
        if frozen is not None:
            if not isinstance(frozen, Mapping) or not isinstance(frozen.get("steps"), list):
                raise ValueError("native_agent_recipe_remember_arguments_invalid")
            values["_frozen_recipe"] = dict(frozen)
        return values

    def remembered_steps(sequence: Any) -> list[dict[str, Any]]:
        return actionable_sequence_to_recipe_steps(sequence)

    def remember_sequence(context: NativeToolContext) -> Any:
        store = getattr(runtime_owner, "_native_actionable_sequence_store", LAST_ACTIONABLE_SEQUENCE_STORE)
        return store.get(context.user_id) if store is not None else None

    def copy_suggestion(context: NativeToolContext) -> Any:
        store = getattr(runtime_owner, "_native_cross_host_recipe_suggestions", CROSS_HOST_RECIPE_SUGGESTIONS)
        return store.get(context.user_id) if store is not None else None

    async def recipe_remember(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        values = recipe_remember_arguments(arguments)
        sequence = remember_sequence(context)
        suggestion = copy_suggestion(context)
        frozen_recipe = values.get("_frozen_recipe")
        if sequence is None and suggestion is None and not isinstance(frozen_recipe, Mapping):
            return NativeToolResult("There is no recent actionable sequence to remember as a Recipe.", "recipe_remember")
        steps = [dict(step) for step in frozen_recipe.get("steps", ()) if isinstance(step, Mapping)] if isinstance(frozen_recipe, Mapping) else (remembered_steps(sequence) if suggestion is None else [
            {
                **dict(step),
                "params": {
                    **dict(step.get("params", {})),
                    **({"connection_ref": suggestion.new_host} if (
                        str(dict(step.get("params", {})).get("connection_ref") or "") == suggestion.source_host
                    ) else {}),
                },
            }
            for step in suggestion.steps
        ])
        if not steps:
            return NativeToolResult("There is no supported actionable sequence to remember as a Recipe.", "recipe_remember")
        default_name = str(frozen_recipe.get("name") or "").strip() if isinstance(frozen_recipe, Mapping) else (
            f"{suggestion.recipe_name} ({suggestion.new_host})" if suggestion is not None
            else str(sequence.intent or "Remembered action").strip()[:80]
        )
        name = values.get("name") or default_name
        base_id = "-".join("".join(char.lower() if char.isalnum() else " " for char in name).split())[:40] or "remembered-action"
        existing, _errors = load_stored_recipe_manifests()
        existing_ids = {str(row.get("id") or "") for row in existing}
        recipe_id, suffix = base_id, 2
        while recipe_id in existing_ids:
            recipe_id, suffix = f"{base_id[:42]}-{suffix}", suffix + 1
        manifest = {
            "id": recipe_id, "name": name,
            "description": values.get("description") or (str(frozen_recipe.get("description") or "") if isinstance(frozen_recipe, Mapping) else (
                f"Inactive cross-host copy of {suggestion.recipe_name} for {suggestion.new_host}"
                if suggestion is not None else f"Inactive draft captured from: {sequence.intent}"
            )),
            "version": "0.1.0", "category": "custom", "enabled_default": False,
            "steps": steps, "schedule": {"enabled": False}, "schema_version": "1.1",
        }
        saver = getattr(runtime_owner, "_native_agent_recipe_saver", save_stored_recipe_manifest)
        stored = saver(manifest)
        if inspect.isawaitable(stored):
            await stored
        if suggestion is not None:
            suggestion_store = getattr(
                runtime_owner, "_native_cross_host_recipe_suggestions", CROSS_HOST_RECIPE_SUGGESTIONS,
            )
            suggestion_store.consume(context.user_id)
        return NativeToolResult(
            f'Recipe "{name}" saved as an inactive draft in My Recipes. Review and activate it and, '
            "for mutating commands, whitelist it before running.", "recipe_remember",
        )

    async def recipe_remember_preview(context: NativeToolContext, arguments: Mapping[str, Any]) -> str:
        values = recipe_remember_arguments(arguments)
        sequence = remember_sequence(context)
        suggestion = copy_suggestion(context)
        frozen_recipe = values.get("_frozen_recipe")
        if sequence is None and suggestion is None and not isinstance(frozen_recipe, Mapping):
            return "Confirm recipe_remember: nothing recent to remember; no Recipe will be written"
        name = values.get("name") or (str(frozen_recipe.get("name") or "") if isinstance(frozen_recipe, Mapping) else (
            f"{suggestion.recipe_name} ({suggestion.new_host})" if suggestion is not None
            else str(sequence.intent or "Remembered action").strip()[:80]
        ))
        steps = [dict(step) for step in frozen_recipe.get("steps", ()) if isinstance(step, Mapping)] if isinstance(frozen_recipe, Mapping) else (remembered_steps(sequence) if suggestion is None else [
            {
                **dict(step), "params": {
                    **dict(step.get("params", {})),
                    **({"connection_ref": suggestion.new_host} if (
                        str(dict(step.get("params", {})).get("connection_ref") or "") == suggestion.source_host
                    ) else {}),
                },
            }
            for step in suggestion.steps
        ])
        details = ", ".join(
            f"{row['type']}({json.dumps(row['params'], ensure_ascii=True, sort_keys=True)})" for row in steps
        )
        return f"Confirm recipe_remember: recipe={name}; steps={details}; will be saved inactive"
    async def connection_read(
        context: NativeToolContext, *, kind: str, ref: str, operation: str,
        parameters: Mapping[str, Any],
    ) -> NativeToolResult:
        authority = CONNECTION_READ_SOURCE_AUTHORITIES[kind]
        loader = getattr(runtime_owner, "_native_agent_connection_read_loader", None)
        if callable(loader):
            raw = loader(context.user_id, kind, ref, operation, dict(parameters))
            row = await raw if inspect.isawaitable(raw) else raw
            if not isinstance(row, Mapping):
                raise ValueError("native_agent_connection_read_result_invalid")
            if str(row.get("source_authority") or "") != authority:
                raise ValueError("native_agent_connection_read_authority_mismatch")
            if str(row.get("scope_user_id") or "") != context.user_id:
                raise ValueError("native_agent_connection_read_scope_mismatch")
            content = str(row.get("content") or "").strip()
        else:
            settings_connections = getattr(getattr(runtime_owner, "settings", None), "connections", None)
            profiles = getattr(settings_connections, kind, None)
            if not isinstance(profiles, Mapping) or ref not in profiles:
                content = ""
            else:
                runtime = getattr(runtime_owner, "_skill_runtime", None)
                if runtime is None:
                    raise ValueError("native_agent_connection_read_runtime_unavailable")
                method = getattr(runtime, f"execute_{kind}_{operation}")
                try:
                    content = str(method(ref, **dict(parameters)) or "").strip()
                except Exception as exc:  # resolved profile, transport/config failure -> honest degradation
                    return NativeToolResult(json.dumps({
                        "status": "read_failed", "effect": "read_only",
                        "connection_kind": kind, "connection_ref": ref,
                        "message": "The configured profile was resolved but could not be read.",
                        "error_class": type(exc).__name__, "detail": str(exc)[:200],
                    }, ensure_ascii=True, sort_keys=True), f"{kind}_{operation}")
        payload = {
            "status": "ok" if content else "not_found_or_empty", "effect": "read_only",
            "connection_kind": kind, "connection_ref": ref, "content": content,
        }
        if not content:
            payload["message"] = "No content was found for this exact profile and request."
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), f"{kind}_{operation}")

    async def connection_send(
        context: NativeToolContext, *, kind: str, ref: str, operation: str,
        parameters: Mapping[str, Any], failure_status: str = "send_failed",
    ) -> NativeToolResult:
        authority = CONNECTION_SEND_SOURCE_AUTHORITIES[kind]
        loader = getattr(runtime_owner, "_native_agent_connection_send_loader", None)
        if callable(loader):
            raw = loader(context.user_id, kind, ref, operation, dict(parameters))
            row = await raw if inspect.isawaitable(raw) else raw
            if not isinstance(row, Mapping):
                raise ValueError("native_agent_connection_send_result_invalid")
            if str(row.get("source_authority") or "") != authority:
                raise ValueError("native_agent_connection_send_authority_mismatch")
            if str(row.get("scope_user_id") or "") != context.user_id:
                raise ValueError("native_agent_connection_send_scope_mismatch")
            result_content = str(row.get("content") or "").strip()
        else:
            settings_connections = getattr(getattr(runtime_owner, "settings", None), "connections", None)
            profiles = getattr(settings_connections, kind, None)
            if not isinstance(profiles, Mapping) or ref not in profiles:
                return NativeToolResult(json.dumps({
                    "status": "connection_not_found", "effect": "mutating",
                    "connection_kind": kind, "connection_ref": ref,
                    "message": "No configured profile exists for this exact connection reference.",
                }, ensure_ascii=True, sort_keys=True), f"{kind}_{operation}")
            runtime = getattr(runtime_owner, "_skill_runtime", None)
            if runtime is None:
                raise ValueError("native_agent_connection_send_runtime_unavailable")
            method = getattr(runtime, f"execute_{kind}_{operation}")
            try:
                raw = method(ref, **dict(parameters))
                result_content = str(await raw if inspect.isawaitable(raw) else raw).strip()
            except Exception as exc:  # resolved profile, provider/runtime failure -> honest result
                return NativeToolResult(json.dumps({
                    "status": failure_status, "effect": "mutating",
                    "connection_kind": kind, "connection_ref": ref,
                    "error_class": type(exc).__name__,
                    "message": "The configured profile was resolved but the requested operation failed.",
                }, ensure_ascii=True, sort_keys=True), f"{kind}_{operation}")
        return NativeToolResult(json.dumps({
            "status": "ok", "effect": "mutating", "connection_kind": kind,
            "connection_ref": ref, "result": result_content,
        }, ensure_ascii=True, sort_keys=True), f"{kind}_{operation}")

    def exact_text(arguments: Mapping[str, Any], allowed: set[str], required: set[str]) -> dict[str, str]:
        if set(arguments) - allowed or not required.issubset(arguments):
            raise ValueError("native_agent_connection_read_arguments_invalid")
        clean = {}
        for key, value in arguments.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("native_agent_connection_read_arguments_invalid")
            clean[key] = value.strip()
        return clean

    async def calendar_read(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        values = exact_text(arguments, {"connection_ref", "range_hint", "query"}, {"connection_ref"})
        return await connection_read(context, kind="google_calendar", ref=values.pop("connection_ref"),
                                     operation="read", parameters={"range_hint": values.pop("range_hint", "upcoming"), "search_query": values.pop("query", "")})

    async def file_read(context: NativeToolContext, arguments: Mapping[str, Any], *, operation: str) -> NativeToolResult:
        values = exact_text(arguments, {"connection_kind", "connection_ref", "path"}, {"connection_kind", "connection_ref", "path"})
        kind = values.pop("connection_kind")
        if kind not in {"sftp", "smb"}:
            raise ValueError("native_agent_file_connection_kind_invalid")
        return await connection_read(context, kind=kind, ref=values.pop("connection_ref"), operation=operation,
                                     parameters={"remote_path": values.pop("path")})

    async def file_list(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await file_read(context, arguments, operation="list")

    async def file_content(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await file_read(context, arguments, operation="read")

    async def mail_read(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        values = exact_text(arguments, {"connection_ref"}, {"connection_ref"})
        return await connection_read(context, kind="imap", ref=values["connection_ref"], operation="read", parameters={})

    async def mail_search(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        values = exact_text(arguments, {"connection_ref", "query"}, {"connection_ref", "query"})
        return await connection_read(context, kind="imap", ref=values["connection_ref"], operation="search",
                                     parameters={"query": values["query"]})

    async def send_message(
        context: NativeToolContext, arguments: Mapping[str, Any], *, kind: str, operation: str,
    ) -> NativeToolResult:
        allowed = {"connection_ref", "content", "topic"} if kind == "mqtt" else {"connection_ref", "content"}
        required = set(allowed)
        values = exact_text(arguments, allowed, required)
        ref = values.pop("connection_ref")
        return await connection_send(
            context, kind=kind, ref=ref, operation=operation, parameters=values,
        )

    async def discord_send(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await send_message(context, arguments, kind="discord", operation="send")

    async def webhook_send(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await send_message(context, arguments, kind="webhook", operation="send")

    async def email_send(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await send_message(context, arguments, kind="email", operation="send")

    async def mqtt_publish(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await send_message(context, arguments, kind="mqtt", operation="publish")

    async def file_write(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        values = exact_text(
            arguments, {"connection_kind", "connection_ref", "path", "content"},
            {"connection_kind", "connection_ref", "path", "content"},
        )
        kind = values.pop("connection_kind")
        if kind not in {"sftp", "smb"}:
            raise ValueError("native_agent_file_connection_kind_invalid")
        return await connection_send(
            context, kind=kind, ref=values.pop("connection_ref"), operation="write",
            parameters={"remote_path": values.pop("path"), "content": values.pop("content")},
            failure_status="write_failed",
        )

    async def http_api_request(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) - {"connection_ref", "request_path", "content"}:
            raise ValueError("native_agent_http_api_arguments_invalid")
        ref = arguments.get("connection_ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ValueError("native_agent_http_api_arguments_invalid")
        parameters: dict[str, Any] = {"request_path": "", "content": "", "confirmed": True}
        for key in ("request_path", "content"):
            value = arguments.get(key, "")
            if not isinstance(value, str):
                raise ValueError("native_agent_http_api_arguments_invalid")
            parameters[key] = value.strip()
        return await connection_send(
            context, kind="http_api", ref=ref.strip(), operation="request",
            parameters=parameters, failure_status="request_failed",
        )

    async def recipes_execute(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        if set(arguments) != {"recipe_id"} or not isinstance(arguments.get("recipe_id"), str):
            raise ValueError("native_agent_recipe_arguments_invalid")
        recipe_id = str(arguments["recipe_id"]).strip()
        if not recipe_id:
            raise ValueError("native_agent_recipe_arguments_invalid")
        runtime_recipes = [dict(row) for row in await _load_recipes(runtime_owner) if isinstance(row, Mapping)]
        item = await _exact_recipe(runtime_owner, recipe_id, recipes=runtime_recipes)
        if item is None:
            return NativeToolResult(
                f"Recipe '{recipe_id}' was not found or is not enabled.", "recipes_execute",
                activity={"title": recipe_id, "target": "", "success": False},
            )
        canonical_recipe_id = str(item.get("id") or "").strip()
        if not canonical_recipe_id:
            raise ValueError("native_agent_recipe_id_invalid")
        recipe_name = str(item.get("name") or canonical_recipe_id).strip()
        expansion = expand_recipe_connection_bindings(item, settings=getattr(runtime_owner, "settings", None))
        activity_target = ", ".join(expansion.targets)
        executor = getattr(runtime_owner, "_execute_recipe_by_id", None)
        if not callable(executor):
            raise RuntimeError("native_agent_recipe_runtime_unavailable")
        try:
            raw = executor(
                canonical_recipe_id, "", runtime_recipes=runtime_recipes, language="de",
                user_id=_context.user_id,
            )
            result = await raw if inspect.isawaitable(raw) else raw
        except Exception as exc:
            return NativeToolResult(
                f"Recipe '{canonical_recipe_id}' could not be executed ({type(exc).__name__}).",
                "recipes_execute",
                activity={"title": recipe_name, "target": activity_target, "success": False},
            )
        success = bool(getattr(result, "success", False))
        result_content = str(getattr(result, "content", "") or "").strip()
        result_metadata = getattr(result, "metadata", {}) or {}
        direct_chat_text = (
            str(result_metadata.get("direct_chat_text", "") or "").strip()
            if isinstance(result_metadata, Mapping) else ""
        )
        if success:
            return NativeToolResult(
                direct_chat_text or result_content or f"Recipe '{canonical_recipe_id}' completed without output.",
                "recipes_execute",
                activity={"title": recipe_name, "target": activity_target, "success": True},
            )
        error = str(getattr(result, "error", "") or "").strip()[:200]
        detail = error or result_content or "unknown error"
        return NativeToolResult(
            f"Recipe '{canonical_recipe_id}' failed: {detail}", "recipes_execute",
            activity={"title": recipe_name, "target": activity_target, "success": False},
        )

    async def recipes_execute_confirmation_preview(
        _context: NativeToolContext, arguments: Mapping[str, Any],
    ) -> str:
        recipe_id = str(arguments.get("recipe_id") or "").strip()
        item = await _exact_recipe(runtime_owner, recipe_id)
        if item is None:
            return f"Confirm recipes_execute: recipe={recipe_id}; recipe not found"
        recipe_name = str(item.get("name") or item.get("id") or recipe_id).strip()
        expansion = expand_recipe_connection_bindings(item, settings=getattr(runtime_owner, "settings", None))
        if expansion.error == "recipe_connection_no_connection_configured":
            return f"Confirm recipes_execute: recipe={recipe_name}; no connection configured"
        if expansion.error:
            return f"Confirm recipes_execute: recipe={recipe_name}; target resolution failed ({expansion.error})"
        if expansion.targets:
            return f"Confirm recipes_execute: recipe={recipe_name}; runs on: {', '.join(expansion.targets)}"
        return f"Confirm recipes_execute: recipe={recipe_name}"

    async def inspect_recipe(arguments: Mapping[str, Any], *, preview: bool) -> NativeToolResult:
        if set(arguments) != {"recipe_id"} or not isinstance(arguments.get("recipe_id"), str):
            raise ValueError("native_agent_recipe_arguments_invalid")
        recipe_id = str(arguments["recipe_id"]).strip()
        if not recipe_id:
            raise ValueError("native_agent_recipe_arguments_invalid")
        item = await _exact_recipe(runtime_owner, recipe_id)
        payload = {
            "status": "ok", "effect": "read_only",
            "preview" if preview else "recipe": _safe_recipe(item, preview=preview),
        } if item is not None else {
            "status": "recipe_not_found", "effect": "read_only", "recipe_id": recipe_id,
            "message": "No enabled stored Recipe exists for this exact identifier.",
        }
        return NativeToolResult(
            json.dumps(payload, ensure_ascii=True, sort_keys=True),
            "recipes_preview" if preview else "recipes_explain",
        )

    async def explain(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await inspect_recipe(arguments, preview=False)

    async def preview(_context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await inspect_recipe(arguments, preview=True)

    schema = {"type": "object", "properties": {"recipe_id": {"type": "string"}}, "required": ["recipe_id"]}
    exact_ref_schema = {"type": "object", "properties": {"connection_ref": {"type": "string"}}, "required": ["connection_ref"]}
    file_schema = {"type": "object", "properties": {"connection_kind": {"type": "string", "enum": ["sftp", "smb"]}, "connection_ref": {"type": "string"}, "path": {"type": "string"}}, "required": ["connection_kind", "connection_ref", "path"]}
    send_schema = {"type": "object", "properties": {"connection_ref": {"type": "string"}, "content": {"type": "string"}}, "required": ["connection_ref", "content"]}
    mqtt_schema = {"type": "object", "properties": {"connection_ref": {"type": "string"}, "topic": {"type": "string"}, "content": {"type": "string"}}, "required": ["connection_ref", "topic", "content"]}
    file_write_schema = {"type": "object", "properties": {"connection_kind": {"type": "string", "enum": ["sftp", "smb"]}, "connection_ref": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["connection_kind", "connection_ref", "path", "content"]}
    http_api_schema = {"type": "object", "properties": {"connection_ref": {"type": "string"}, "request_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["connection_ref"]}
    return (
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="recipes_explain",
            description="Explain one exact enabled stored Recipe and its safe step structure. Read-only; never executes it.",
            input_schema=schema, effect="read_only", confirmation_required=False,
            source_authority=RECIPE_SOURCE_AUTHORITY, user_scoped=False,
            rollout_flag="native_agent_memory_enabled", order=330,
        ), handler=explain),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="recipes_preview",
            description="Render a safe execution preview for one exact enabled stored Recipe. Read-only; never executes it.",
            input_schema=schema, effect="read_only", confirmation_required=False,
            source_authority=RECIPE_SOURCE_AUTHORITY, user_scoped=False,
            rollout_flag="native_agent_memory_enabled", order=340,
        ), handler=preview),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="calendar_read",
            description="Read events from one exact configured calendar profile for a bounded range. Read-only and credential-free.",
            input_schema={"type": "object", "properties": {"connection_ref": {"type": "string"}, "range_hint": {"type": "string"}, "query": {"type": "string"}}, "required": ["connection_ref"]},
            effect="read_only", confirmation_required=False, source_authority=CONNECTION_READ_SOURCE_AUTHORITIES["google_calendar"],
            user_scoped=True, rollout_flag="native_agent_connections_enabled", order=500,
            required_connection_kinds=("google_calendar",),
        ), handler=calendar_read),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="file_list", description="List one exact remote SFTP or SMB directory. Read-only and credential-free.",
            input_schema=file_schema, effect="read_only", confirmation_required=False,
            source_authority="remote_files:configured_profile", user_scoped=True,
            rollout_flag="native_agent_connections_enabled", order=510,
            required_connection_kinds=("sftp", "smb"),
        ), handler=file_list),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="file_read", description="Read one exact remote SFTP or SMB file. Read-only and credential-free.",
            input_schema=file_schema, effect="read_only", confirmation_required=False,
            source_authority="remote_files:configured_profile", user_scoped=True,
            rollout_flag="native_agent_connections_enabled", order=520,
            required_connection_kinds=("sftp", "smb"),
        ), handler=file_content),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="mail_read", description="Read recent mail from one exact configured IMAP profile. Read-only and credential-free.",
            input_schema=exact_ref_schema, effect="read_only", confirmation_required=False,
            source_authority=CONNECTION_READ_SOURCE_AUTHORITIES["imap"], user_scoped=True,
            rollout_flag="native_agent_connections_enabled", order=530,
            required_connection_kinds=("imap",),
        ), handler=mail_read),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="mail_search", description="Search one exact configured IMAP mailbox with a bounded query. Read-only and credential-free.",
            input_schema={"type": "object", "properties": {"connection_ref": {"type": "string"}, "query": {"type": "string"}}, "required": ["connection_ref", "query"]},
            effect="read_only", confirmation_required=False, source_authority=CONNECTION_READ_SOURCE_AUTHORITIES["imap"],
            user_scoped=True, rollout_flag="native_agent_connections_enabled", order=540,
            required_connection_kinds=("imap",),
        ), handler=mail_search),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="discord_send",
            description="Send exact content through one configured Discord profile after confirmation.",
            input_schema=send_schema, effect="mutating", confirmation_required=True,
            source_authority=CONNECTION_SEND_SOURCE_AUTHORITIES["discord"], user_scoped=True,
            rollout_flag="native_agent_messaging_enabled", order=700,
            required_connection_kinds=("discord",),
        ), handler=discord_send),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="webhook_send",
            description="Send exact content through one configured webhook profile after confirmation.",
            input_schema=send_schema, effect="mutating", confirmation_required=True,
            source_authority=CONNECTION_SEND_SOURCE_AUTHORITIES["webhook"], user_scoped=True,
            rollout_flag="native_agent_messaging_enabled", order=710,
            required_connection_kinds=("webhook",),
        ), handler=webhook_send),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="email_send",
            description="Send exact content through one configured email profile after confirmation.",
            input_schema=send_schema, effect="mutating", confirmation_required=True,
            source_authority=CONNECTION_SEND_SOURCE_AUTHORITIES["email"], user_scoped=True,
            rollout_flag="native_agent_messaging_enabled", order=720,
            required_connection_kinds=("email",),
        ), handler=email_send),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="mqtt_publish",
            description="Publish exact content to an exact topic through one configured MQTT profile after confirmation.",
            input_schema=mqtt_schema, effect="mutating", confirmation_required=True,
            source_authority=CONNECTION_SEND_SOURCE_AUTHORITIES["mqtt"], user_scoped=True,
            rollout_flag="native_agent_messaging_enabled", order=730,
            required_connection_kinds=("mqtt",),
        ), handler=mqtt_publish),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="file_write",
            description="Write exact content to an exact path through one configured SFTP or SMB profile after confirmation.",
            input_schema=file_write_schema, effect="mutating", confirmation_required=True,
            source_authority="remote_files:configured_profile", user_scoped=True,
            rollout_flag="native_agent_infra_write_enabled", order=740,
            required_connection_kinds=("sftp", "smb"),
        ), handler=file_write),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="http_api_request",
            description="Run one request through an exact configured HTTP API profile after confirmation.",
            input_schema=http_api_schema, effect="mutating", confirmation_required=True,
            source_authority=CONNECTION_SEND_SOURCE_AUTHORITIES["http_api"], user_scoped=True,
            rollout_flag="native_agent_infra_write_enabled", order=750,
            required_connection_kinds=("http_api",),
        ), handler=http_api_request),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="recipes_execute",
            description=(
                "Execute one exact enabled stored Recipe through its existing guarded step engine after confirmation. "
                "Prefer this whenever the user refers to a stored recipe by name or intent, rather than composing an "
                "equivalent ad-hoc command."
            ),
            input_schema=schema, effect="mutating", confirmation_required=True,
            source_authority=RECIPE_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_recipe_execute_enabled", order=760,
            relay_result_content=True,
        ), handler=recipes_execute, confirmation_preview=recipes_execute_confirmation_preview),
        NativeToolBinding(contract=NativeToolContract(
            owner_module_id="recipe_runtime", name="recipe_remember",
            description="Remember the caller's last actionable native-tool sequence as an inactive stored Recipe draft after confirmation.",
            input_schema={"type": "object", "properties": {
                "name": {"type": "string"}, "description": {"type": "string"},
            }}, effect="mutating", confirmation_required=True,
            source_authority=RECIPE_SOURCE_AUTHORITY, user_scoped=True,
            rollout_flag="native_agent_recipe_learn_enabled", order=770,
            relay_result_content=True,
        ), handler=recipe_remember, confirmation_preview=recipe_remember_preview),
    )
