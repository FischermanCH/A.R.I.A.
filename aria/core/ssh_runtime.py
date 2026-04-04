from __future__ import annotations

import asyncio
import contextlib
import re
import shlex
from typing import Any, Callable

from aria.core.guardrails import evaluate_guardrail, resolve_guardrail_profile
from aria.skills.base import SkillResult


class SSHRuntime:
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
    ) -> SkillResult:
        if not connection_ref:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_missing_connection_ref",
            )
        if not command_template:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_missing_command",
            )

        connection = self.settings.connections.ssh.get(connection_ref)
        if not connection:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_ssh_connection_not_found:{connection_ref}",
            )

        host = str(connection.host or "").strip()
        user = str(connection.user or "").strip()
        if not host or not user:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_invalid_connection",
            )

        query = self.normalize_spaces(message)
        command = command_template.replace("{query}", query).strip()
        if not command:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_empty_command",
            )
        lowered = self.normalize_spaces(command).lower()
        allow_list = [str(item).strip().lower() for item in connection.allow_commands if str(item).strip()]
        if allow_list and not any(token in lowered for token in allow_list):
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_not_allowed",
            )
        guardrail_ref = str(getattr(connection, "guardrail_ref", "") or "").strip()
        guardrail_profile = resolve_guardrail_profile(self.settings, guardrail_ref)
        guardrail_decision = evaluate_guardrail(
            profile_ref=guardrail_ref,
            profile=guardrail_profile,
            kind="ssh_command",
            text=lowered,
        )
        if not guardrail_decision.allowed and guardrail_decision.reason == "guardrail_denied":
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_ssh_guardrail_denied:{guardrail_ref or 'default'}",
            )
        if not guardrail_decision.allowed and guardrail_decision.reason == "guardrail_not_allowed":
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_ssh_guardrail_not_allowed:{guardrail_ref or 'default'}",
            )
        if not guardrail_decision.allowed and guardrail_decision.reason.startswith("guardrail_kind_mismatch"):
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_ssh_guardrail_kind_mismatch:{guardrail_ref or 'default'}",
            )
        if any(char in command for char in ("`", "\n", "\r")):
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_command_rejected",
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
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error="custom_skill_ssh_timeout",
            )
        except Exception as exc:
            return SkillResult(
                skill_name=f"custom_skill_{skill_id}",
                content="",
                success=False,
                error=f"custom_skill_ssh_exec_error:{exc}",
            )

        exit_code = int(proc.returncode or 0)
        duration_seconds = max(0.0, asyncio.get_running_loop().time() - started)
        stdout = self.truncate_text((stdout_b or b"").decode("utf-8", errors="replace"))
        stderr = self.truncate_text((stderr_b or b"").decode("utf-8", errors="replace"))
        warning_hints = self._extract_warning_hints(stdout, stderr)
        lines = [
            f"[Custom Skill SSH] {skill_name}",
            f"Connection: {connection_ref} ({target})",
            f"Exit Code: {exit_code}",
            f"Dauer: {duration_seconds:.1f}s",
        ]
        interpretation = None
        if exit_code != 0:
            interpretation = self.error_interpreter.interpret(
                language=language,
                error_code="custom_skill_ssh_nonzero_exit",
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
        if stderr:
            lines.append("STDERR:\n" + stderr)
        held_packages = self.extract_held_packages(stdout + "\n" + stderr)
        return SkillResult(
            skill_name=f"custom_skill_{skill_id}",
            content="\n".join(lines),
            success=exit_code == 0,
            error="" if exit_code == 0 else "custom_skill_ssh_nonzero_exit",
            metadata={
                "custom_skill_id": skill_id,
                "custom_skill_name": skill_name,
                "custom_execution": "ssh_command",
                "custom_connection_ref": connection_ref,
                "custom_connection_target": target,
                "custom_exit_code": exit_code,
                "custom_duration_seconds": duration_seconds,
                "custom_timeout_seconds": configured_timeout,
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
