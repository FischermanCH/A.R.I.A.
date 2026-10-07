"""Native admin-only SSH tools backed by the canonical SSH runtime policy."""

from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

from aria.modules.auth_policy.access_policy import is_admin
from aria.modules.recipe_runtime.contracts import DIRECT_SSH_RECIPE_ID
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult
from aria.modules.ssh_runtime.runtime import resolve_ssh_connection

SSH_SOURCE_AUTHORITY = "ssh_runtime:configured_profiles"
MAX_SSH_TARGETS = 20
_TOTAL_OUTPUT_CHARS = 9_000
_MAX_OUTPUT_CHARS_PER_TARGET = 2_000
_BLOCKED_ERRORS = {
    "recipe_ssh_not_allowed",
    "recipe_ssh_policy_blocked",
    "recipe_ssh_guardrail_denied",
    "recipe_ssh_guardrail_not_allowed",
    "recipe_ssh_guardrail_kind_mismatch",
    "recipe_ssh_command_rejected",
}


def _forbidden(intent: str) -> NativeToolResult:
    return NativeToolResult(json.dumps({
        "status": "forbidden_admin_only",
        "message": "Administrator access is required.",
    }, ensure_ascii=True, sort_keys=True), intent)


def _arguments(arguments: Mapping[str, Any]) -> tuple[str, tuple[str, ...], int | None] | None:
    if set(arguments) - {"command", "targets", "timeout"}:
        raise ValueError("native_agent_ssh_arguments_invalid")
    command = arguments.get("command")
    targets = arguments.get("targets")
    timeout = arguments.get("timeout")
    if (
        not isinstance(command, str)
        or not command.strip()
        or not isinstance(targets, list)
        or not targets
        or any(not isinstance(target, str) or not target.strip() for target in targets)
        or len({target.strip() for target in targets}) != len(targets)
        or (timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 300))
    ):
        raise ValueError("native_agent_ssh_arguments_invalid")
    if len(targets) > MAX_SSH_TARGETS:
        return None
    return command.strip(), tuple(target.strip() for target in targets), timeout


def _safe_failure(error: str, *, read_only: bool) -> tuple[str, str]:
    clean_error = str(error or "recipe_ssh_execution_failed").split(":", 1)[0]
    if read_only and clean_error == "recipe_ssh_policy_confirmation_required":
        return "requires_ssh_command", "This command requires the confirmed ssh_command tool."
    if clean_error in _BLOCKED_ERRORS or clean_error.startswith("recipe_ssh_guardrail_kind_mismatch"):
        return "blocked", clean_error
    return "failed", clean_error


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def execute(
        context: NativeToolContext, arguments: Mapping[str, Any], *, read_only: bool,
    ) -> NativeToolResult:
        intent = "ssh_read" if read_only else "ssh_command"
        if not is_admin(context.auth_role):
            return _forbidden(intent)
        parsed = _arguments(arguments)
        if parsed is None:
            return NativeToolResult(json.dumps({
                "status": "invalid_arguments",
                "message": f"At most {MAX_SSH_TARGETS} explicit SSH targets are allowed.",
                "results": [],
            }, ensure_ascii=True, sort_keys=True), intent)
        command, targets, timeout = parsed
        profiles = getattr(getattr(runtime_owner.settings, "connections", None), "ssh", None)
        if not isinstance(profiles, Mapping):
            profiles = {}
        runtime = getattr(runtime_owner, "_ssh_runtime", None)
        execute_command = getattr(runtime, "execute_custom_ssh_command", None)
        if not callable(execute_command):
            raise RuntimeError("native_agent_ssh_runtime_unavailable")
        output_limit = min(_MAX_OUTPUT_CHARS_PER_TARGET, max(200, _TOTAL_OUTPUT_CHARS // len(targets)))
        rows: list[dict[str, str]] = []
        actionable_targets: list[str] = []
        actionable_outcomes: list[str] = []
        for target in targets:
            resolved = resolve_ssh_connection(profiles, target)
            if resolved is None:
                rows.append({"target": target, "status": "unknown_target", "output": ""})
                continue
            canonical_ref, _connection = resolved
            result = await execute_command(
                skill_id=DIRECT_SSH_RECIPE_ID,
                skill_name=intent,
                connection_ref=canonical_ref,
                command_template=command,
                message="",
                timeout_seconds=timeout,
                language="de",
                policy_confirmed=not read_only,
            )
            if result.success:
                output = str(result.content or "")
                truncated = len(output) > output_limit
                if truncated:
                    notice = "\n[truncated: additional SSH output omitted]"
                    output = output[:max(0, output_limit - len(notice))] + notice
                rows.append({"target": canonical_ref, "status": "ok", "output": output})
                actionable_targets.append(canonical_ref)
                actionable_outcomes.append("success")
            else:
                status, output = _safe_failure(str(result.error or ""), read_only=read_only)
                rows.append({"target": canonical_ref, "status": status, "output": output})
                if status == "blocked":
                    actionable_targets.append(canonical_ref)
                    actionable_outcomes.append("blocked")
        actionable_arguments = None
        actionable_outcome = "skip"
        if actionable_targets:
            actionable_arguments = {"command": command, "targets": actionable_targets}
            if timeout is not None:
                actionable_arguments["timeout"] = timeout
            actionable_outcome = "blocked" if "blocked" in actionable_outcomes else "success"
        return NativeToolResult(json.dumps({
            "status": "ok", "command": command, "results": rows,
        }, ensure_ascii=True, sort_keys=True), intent, actionable_arguments, actionable_outcome)

    async def ssh_read(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await execute(context, arguments, read_only=True)

    async def ssh_command(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        return await execute(context, arguments, read_only=False)

    schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "targets": {
                "type": "array", "items": {"type": "string"},
                "minItems": 1, "maxItems": MAX_SSH_TARGETS,
            },
            "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
        },
        "required": ["command", "targets"],
    }
    shared = {
        "owner_module_id": "ssh_runtime",
        "input_schema": schema,
        "source_authority": SSH_SOURCE_AUTHORITY,
        "user_scoped": True,
        "rollout_flag": "native_agent_ssh_enabled",
        "required_connection_kinds": ("ssh",),
    }
    return (
        NativeToolBinding(NativeToolContract(
            name="ssh_read",
            description=(
                "Run one policy-approved read-only SSH command on explicit configured targets. "
                "Administrator-only; mutating commands require ssh_command instead. Use only for one-off ad-hoc commands "
                "the user states literally; if the user names or means a stored Recipe, use recipes_execute instead."
            ),
            effect="read_only", confirmation_required=False, order=620, **shared,
        ), ssh_read),
        NativeToolBinding(NativeToolContract(
            name="ssh_command",
            description=(
                "Run one SSH command on explicit configured targets after confirmation. "
                "Administrator-only; SSH policy hard blocks and allow-lists remain authoritative. Use only for one-off "
                "ad-hoc commands the user states literally; if the user names or means a stored Recipe, use "
                "recipes_execute instead."
            ),
            effect="mutating", confirmation_required=True, order=621, **shared,
        ), ssh_command),
    )
