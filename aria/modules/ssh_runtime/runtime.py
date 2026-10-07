from __future__ import annotations

import asyncio
import contextlib
import re
import shlex
from collections.abc import Mapping
from typing import Any, Callable

from aria.modules.runtime_guardrails.guardrails import clean_guardrail_recipe_ids, evaluate_guardrail, resolve_guardrail_profile, ssh_command_hits_absolute_block
from aria.modules.recipe_runtime.contracts import DIRECT_SSH_RECIPE_ID
from aria.modules.recipe_runtime.contracts import RECIPE_SSH_NONZERO_EXIT_ERROR
from aria.modules.recipe_runtime.contracts import build_recipe_runtime_skill_name
from aria.modules.recipe_runtime.contracts import recipe_ssh_error
from aria.modules.ssh_policy.guardrail_commands import combined_ssh_allow_commands
from aria.modules.ssh_policy.guardrail_commands import ssh_guardrail_allow_terms
from aria.modules.ssh_policy.policy import command_matches_allow_commands, validate_ssh_readonly_policy
from aria.modules.skill_contracts.contracts import SkillResult


def _profile_text(profile: Any, field: str) -> str:
    value = profile.get(field, "") if isinstance(profile, Mapping) else getattr(profile, field, "")
    return str(value or "").strip()


def resolve_ssh_connection(profiles: Mapping[str, Any], target: str) -> tuple[str, Any] | None:
    """Resolve one configured SSH profile without guessing ambiguous display values."""
    clean_target = str(target or "").strip()
    if not clean_target:
        return None
    if clean_target in profiles:
        return clean_target, profiles[clean_target]
    folded_target = clean_target.casefold()
    ref_matches = [
        (str(ref), profile) for ref, profile in profiles.items()
        if str(ref or "").strip().casefold() == folded_target
    ]
    if ref_matches:
        return ref_matches[0] if len(ref_matches) == 1 else None
    name_matches = [
        (str(ref), profile) for ref, profile in profiles.items()
        if next((
            value for value in (
                _profile_text(profile, "title"),
                _profile_text(profile, "display_name"),
                _profile_text(profile, "name"),
            ) if value
        ), "").casefold() == folded_target
    ]
    if name_matches:
        return name_matches[0] if len(name_matches) == 1 else None
    host_matches = [
        (str(ref), profile) for ref, profile in profiles.items()
        if _profile_text(profile, "host").casefold() == folded_target
    ]
    return host_matches[0] if len(host_matches) == 1 else None


class SSHRuntime:
    _DISPLAY_ONLY_STDERR_FILTERS: tuple[re.Pattern[str], ...] = (
        re.compile(r"^Warning: Permanently added '.+' \([^)]+\) to the list of known hosts\.$"),
        re.compile(r"^Warning: Permanently added the .+ host key for IP address '.+' to the list of known hosts\.$"),
    )

    def __init__(
        self,
        *,
        settings: Any,
        error_interpreter: Any,
        normalize_spaces: Callable[[str], str],
        truncate_text: Callable[[str, int], str],
        extract_held_packages: Callable[[str], list[str]],
    ) -> None:
        self.settings = settings
        self.error_interpreter = error_interpreter
        self.normalize_spaces = normalize_spaces
        self.truncate_text = truncate_text
        self.extract_held_packages = extract_held_packages

    @staticmethod
    def _extract_warning_hints(stdout: str, stderr: str) -> list[str]:
        text = f"{stdout}\n{stderr}".lower()
        rows: list[str] = []
        if "apt-key is deprecated" in text or "legacy trusted.gpg" in text:
            rows.append("apt-key/GPG")
        if "failed to fetch" in text:
            rows.append("Fetch")
        if "temporary failure resolving" in text or "name or service not known" in text:
            rows.append("DNS/Netz")
        if "dpkg was interrupted" in text or "could not get lock" in text:
            rows.append("dpkg/Lock")
        return rows

    @classmethod
    def _filter_stderr_for_display(cls, stderr: str) -> str:
        visible_lines: list[str] = []
        for line in str(stderr or "").splitlines():
            stripped = line.strip()
            if stripped and any(pattern.match(stripped) for pattern in cls._DISPLAY_ONLY_STDERR_FILTERS):
                continue
            visible_lines.append(line)
        return "\n".join(visible_lines).strip()

    @staticmethod
    def _render_command_template(command_template: str, query: str) -> str:
        """Render user input as one shell argument by default.

        Custom SSH skills run remotely via ``bash -lc``. That is useful for
        admin-authored command templates, but user-provided ``{query}`` values
        must not become shell syntax.
        """

        quoted_query = shlex.quote(str(query or ""))
        rendered = str(command_template or "").replace("{query:q}", quoted_query)
        rendered = rendered.replace("{query}", quoted_query)
        return rendered.strip()

    async def execute_custom_ssh_command(
        self,
        *,
        skill_id: str,
        skill_name: str,
        connection_ref: str,
        command_template: str,
        message: str,
        timeout_seconds: int | None = None,
        language: str = "de",
        policy_confirmed: bool = False,
    ) -> SkillResult:
        if not connection_ref:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("missing_connection_ref"),
            )
        if not command_template:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("missing_command"),
            )

        resolved = resolve_ssh_connection(self.settings.connections.ssh, connection_ref)
        if resolved is None:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("connection_not_found", connection_ref),
            )
        connection_ref, connection = resolved

        host = str(connection.host or "").strip()
        user = str(connection.user or "").strip()
        if not host or not user:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("invalid_connection"),
            )

        query = self.normalize_spaces(message)
        command = self._render_command_template(command_template, query)
        if not command:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("empty_command"),
            )
        lowered = self.normalize_spaces(command).lower()
        if ssh_command_hits_absolute_block(command):
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("absolute_block"),
            )
        guardrail_ref = str(getattr(connection, "guardrail_ref", "") or "").strip()
        guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
        whitelisted_recipe = (
            skill_id != DIRECT_SSH_RECIPE_ID
            and str(skill_id or "").strip() in clean_guardrail_recipe_ids((guardrail_profile or {}).get("allow_recipe_ids", []))
        )
        allow_list = [str(item).strip().lower() for item in connection.allow_commands if str(item).strip()]
        guardrail_allow_list = [item.lower() for item in ssh_guardrail_allow_terms(guardrail_profile)]
        effective_allow_list = combined_ssh_allow_commands(allow_list, guardrail_allow_list)
        if skill_id == DIRECT_SSH_RECIPE_ID:
            policy = validate_ssh_readonly_policy(command, allow_commands=effective_allow_list)
            if policy.action != "allow":
                if policy.action == "ask_user" and policy_confirmed:
                    pass
                elif policy.reason == "ssh_command_not_in_allow_list":
                    error = recipe_ssh_error("not_allowed")
                elif policy.action == "ask_user":
                    error = recipe_ssh_error("policy_confirmation_required", policy.reason)
                else:
                    error = recipe_ssh_error("policy_blocked", policy.reason)
                if not (policy.action == "ask_user" and policy_confirmed):
                    return SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=error,
                    )
        elif not whitelisted_recipe and allow_list and not command_matches_allow_commands(command, allow_list):
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("not_allowed"),
            )
        guardrail_decision = evaluate_guardrail(
            profile_ref=guardrail_ref,
            profile=None if whitelisted_recipe else guardrail_profile,
            kind="ssh_command",
            text=lowered,
        )
        if not guardrail_decision.allowed and guardrail_decision.reason == "guardrail_denied":
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("guardrail_denied", guardrail_ref or "default"),
            )
        if not guardrail_decision.allowed and guardrail_decision.reason == "guardrail_not_allowed":
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("guardrail_not_allowed", guardrail_ref or "default"),
            )
        if not guardrail_decision.allowed and guardrail_decision.reason.startswith("guardrail_kind_mismatch"):
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("guardrail_kind_mismatch", guardrail_ref or "default"),
            )
        if any(char in command for char in ("`", "\n", "\r")):
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("command_rejected"),
            )

        target = f"{user}@{host}"
        configured_timeout = max(5, int(timeout_seconds or connection.timeout_seconds))
        connect_timeout = min(configured_timeout, 20)
        command_timeout = configured_timeout + 5

        args = [
            "ssh",
            "-p",
            str(int(connection.port)),
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={connect_timeout}",
            "-o",
            f"StrictHostKeyChecking={str(connection.strict_host_key_checking or 'accept-new')}",
        ]
        key_path = str(connection.key_path or "").strip()
        if key_path:
            args.extend(["-i", key_path])
        args.append(target)
        args.append(f"bash -lc {shlex.quote(command)}")

        proc: asyncio.subprocess.Process | None = None
        started = asyncio.get_running_loop().time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=command_timeout)
        except asyncio.TimeoutError:
            if proc is not None:
                with contextlib.suppress(Exception):
                    proc.kill()
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("timeout"),
            )
        except Exception as exc:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=recipe_ssh_error("exec_error", str(exc)),
            )

        exit_code = int(proc.returncode or 0)
        duration_seconds = max(0.0, asyncio.get_running_loop().time() - started)
        stdout = self.truncate_text((stdout_b or b"").decode("utf-8", errors="replace"))
        stderr = self.truncate_text((stderr_b or b"").decode("utf-8", errors="replace"))
        display_stderr = self._filter_stderr_for_display(stderr)
        warning_hints = self._extract_warning_hints(stdout, stderr)
        lines = [
            f"[Stored Recipe SSH] {skill_name}",
            f"Connection: {connection_ref} ({target})",
            f"Exit Code: {exit_code}",
            f"Dauer: {duration_seconds:.1f}s",
        ]
        interpretation = None
        if exit_code != 0:
            interpretation = self.error_interpreter.interpret(
                language=language,
                error_code=RECIPE_SSH_NONZERO_EXIT_ERROR,
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                command=command,
                connection_ref=connection_ref,
            )
            if interpretation is not None:
                lines.append("Interpretation:\n" + interpretation.summary())
        if stdout:
            lines.append("STDOUT:\n" + stdout)
        if display_stderr:
            lines.append("STDERR:\n" + display_stderr)
        held_packages = self.extract_held_packages(stdout + "\n" + stderr)
        return SkillResult(
            skill_name=build_recipe_runtime_skill_name(skill_id),
            content="\n".join(lines),
            success=exit_code == 0,
            error="" if exit_code == 0 else RECIPE_SSH_NONZERO_EXIT_ERROR,
            metadata={
                "custom_skill_id": skill_id,
                "custom_skill_name": skill_name,
                "custom_execution": "ssh_command",
                "custom_connection_ref": connection_ref,
                "custom_connection_target": target,
                "custom_command": command,
                "custom_exit_code": exit_code,
                "custom_duration_seconds": duration_seconds,
                "custom_timeout_seconds": configured_timeout,
                "custom_stdout": stdout,
                "custom_stderr": stderr,
                "custom_held_packages": held_packages,
                "custom_warning_hints": warning_hints,
                "error_interpretation": (
                    {
                        "category": interpretation.category,
                        "title": interpretation.title,
                        "cause": interpretation.cause,
                        "next_step": interpretation.next_step,
                        "matched_pattern": interpretation.matched_pattern,
                    }
                    if interpretation is not None
                    else None
                ),
            },
        )
