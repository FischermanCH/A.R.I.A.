from __future__ import annotations

from functools import lru_cache
import re
from typing import Any

from aria.core.i18n import I18NStore
from pathlib import Path
from aria.core.recipe_runtime_contract import build_recipe_runtime_skill_name
from aria.core.safe_fix import format_held_packages_summary
from aria.skills.base import SkillResult

BASE_DIR = Path(__file__).resolve().parents[2]
_RECIPE_STEP_I18N = I18NStore(BASE_DIR / "aria" / "i18n")


def _recipe_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPE_STEP_I18N.t(language or "de", f"recipe_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _recipe_step_error_prefix(language: str | None, step_id: str) -> str:
    return _recipe_text(language, "step_error_prefix", "[Step {step_id} error]", step_id=step_id)


@lru_cache(maxsize=128)
def _compile_condition_regex(pattern: str, flags: int) -> re.Pattern[str]:
    return re.compile(pattern, flags=flags)


def _evaluate_skill_step_condition(condition: dict[str, Any], values: dict[str, str]) -> bool:
    source = str(condition.get("source", "")).strip().lower()
    operator = str(condition.get("operator", "")).strip().lower()
    expected = str(condition.get("value", ""))
    ignore_case = bool(condition.get("ignore_case", False))
    actual = str(values.get(source, "")) if source else ""

    if ignore_case:
        actual_cmp = actual.lower()
        expected_cmp = expected.lower()
    else:
        actual_cmp = actual
        expected_cmp = expected

    if operator == "equals":
        return actual_cmp == expected_cmp
    if operator == "not_equals":
        return actual_cmp != expected_cmp
    if operator == "contains":
        return expected_cmp in actual_cmp
    if operator == "not_contains":
        return expected_cmp not in actual_cmp
    if operator == "regex":
        flags = re.IGNORECASE if ignore_case else 0
        try:
            return _compile_condition_regex(expected, flags).search(actual) is not None
        except re.error:
            return False
    if operator == "is_empty":
        return not actual.strip()
    if operator == "not_empty":
        return bool(actual.strip())
    return True


def render_step_template(template: str, values: dict[str, str]) -> str:
    rendered = str(template or "")
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _format_ssh_step_run_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    language = "de"
    lines = [_recipe_text(language, "technical_run_title", "Technical run:")]
    for row in rows:
        connection_ref = str(row.get("connection_ref", "")).strip()
        target = str(row.get("target", "")).strip()
        exit_code = int(row.get("exit_code", 0) or 0)
        duration = float(row.get("duration_seconds", 0.0) or 0.0)
        held = row.get("held_packages", [])
        warnings = row.get("warning_hints", [])
        status = "ok" if exit_code == 0 else f"Exit {exit_code}"
        details = [status, f"{duration:.1f}s"]
        if isinstance(held, list) and held:
            details.append(_recipe_text(language, "held_packages_count", "{count} held", count=len(held)))
        if isinstance(warnings, list) and warnings:
            warning_text = ", ".join(str(item) for item in warnings if str(item).strip())
            details.append(_recipe_text(language, "warnings_prefix", "Warnings: {warnings}", warnings=warning_text))
        place = f"{connection_ref} ({target})" if target else connection_ref
        lines.append(f"- {place}: " + ", ".join(details))
    return "\n".join(lines)




class RecipeStepExecutor:
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    async def execute(self, row: dict[str, Any], message: str, language: str = "de") -> SkillResult:
        runtime = self.runtime
        skill_id = str(row.get("id", "")).strip() or "custom"
        skill_name = str(row.get("name", skill_id)).strip() or skill_id
        steps = row.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error="recipe_steps_missing",
            )

        outputs: dict[str, str] = {}
        last_output = runtime.normalize_spaces(message)
        executed: list[str] = []
        held_by_connection: dict[str, list[str]] = {}
        connection_targets: dict[str, str] = {}
        error_interpretations: dict[str, dict[str, str]] = {}
        ssh_run_summaries: list[dict[str, Any]] = []
        direct_chat = False
        skipped: list[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        for idx, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("id", "")).strip() or f"s{idx}"
            step_type = str(step.get("type", "")).strip().lower()
            on_error = str(step.get("on_error", "stop")).strip().lower() or "stop"
            params = step.get("params", {})
            if not isinstance(params, dict):
                params = {}
            values = {
                "query": runtime.normalize_spaces(message),
                "prev_output": last_output,
                "last_output": last_output,
            }
            for key, val in outputs.items():
                values[f"{key}_output"] = val
                values[key] = val
            condition = step.get("condition", {})
            if isinstance(condition, dict) and condition:
                if not _evaluate_skill_step_condition(condition, values):
                    outputs[step_id] = ""
                    skipped.append(step_id)
                    executed.append(f"{idx}.{step_type}(skipped)")
                    continue

            if step_type == "ssh_run":
                configured_connection_ref = str(params.get("connection_ref", "")).strip()
                cmd_tpl = str(params.get("command", "")).strip()
                cmd = render_step_template(cmd_tpl, values)
                ssh_result = await runtime.execute_custom_ssh_command(
                    skill_id=skill_id,
                    skill_name=skill_name,
                    connection_ref=configured_connection_ref,
                    command_template=cmd,
                    message=message,
                    timeout_seconds=int(params.get("timeout_seconds", 0) or 0) or None,
                    language=language,
                )
                if not ssh_result.success:
                    meta = ssh_result.metadata or {}
                    interpretation = meta.get("error_interpretation")
                    if configured_connection_ref and isinstance(interpretation, dict):
                        error_interpretations[configured_connection_ref] = {
                            "title": str(interpretation.get("title", "")).strip(),
                            "cause": str(interpretation.get("cause", "")).strip(),
                            "next_step": str(interpretation.get("next_step", "")).strip(),
                        }
                    if on_error == "continue":
                        err_text = ssh_result.error or "ssh_step_failed"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.ssh_run(error-continue)")
                        continue
                    return ssh_result
                last_output = ssh_result.content
                outputs[step_id] = last_output
                executed.append(f"{idx}.ssh_run")
                meta = ssh_result.metadata or {}
                resolved_connection_ref = str(meta.get("custom_connection_ref", "")).strip()
                resolved_connection_target = str(meta.get("custom_connection_target", "")).strip()
                held_packages = meta.get("custom_held_packages", [])
                ssh_run_summaries.append(
                    {
                        "connection_ref": resolved_connection_ref or configured_connection_ref,
                        "target": resolved_connection_target,
                        "exit_code": int(meta.get("custom_exit_code", 0) or 0),
                        "duration_seconds": float(meta.get("custom_duration_seconds", 0.0) or 0.0),
                        "held_packages": held_packages if isinstance(held_packages, list) else [],
                        "warning_hints": meta.get("custom_warning_hints", []) if isinstance(meta.get("custom_warning_hints", []), list) else [],
                    }
                )
                if resolved_connection_ref and isinstance(held_packages, list) and held_packages:
                    merged = held_by_connection.setdefault(resolved_connection_ref, [])
                    for pkg in held_packages:
                        package_name = str(pkg).strip().lower()
                        if package_name and package_name not in merged:
                            merged.append(package_name)
                    if resolved_connection_target:
                        connection_targets[resolved_connection_ref] = resolved_connection_target
                continue

            if step_type == "sftp_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                remote_path = render_step_template(remote_path_tmpl, values)
                try:
                    last_output = runtime.execute_sftp_read(connection_ref, remote_path)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_sftp_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "sftp_read_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.sftp_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.sftp_read")
                continue

            if step_type == "sftp_write":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                content_tmpl = str(params.get("content", "")).strip() or "{prev_output}"
                remote_path = render_step_template(remote_path_tmpl, values)
                rendered_content = render_step_template(content_tmpl, values)
                try:
                    last_output = runtime.execute_sftp_write(connection_ref, remote_path, rendered_content)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_sftp_write_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "sftp_write_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.sftp_write(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.sftp_write")
                continue

            if step_type == "smb_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                remote_path = render_step_template(remote_path_tmpl, values)
                try:
                    last_output = runtime.execute_smb_read(connection_ref, remote_path)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_smb_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "smb_read_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.smb_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.smb_read")
                continue

            if step_type == "smb_write":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                remote_path_tmpl = str(params.get("remote_path", "")).strip()
                content_tmpl = str(params.get("content", "")).strip() or "{prev_output}"
                remote_path = render_step_template(remote_path_tmpl, values)
                rendered_content = render_step_template(content_tmpl, values)
                try:
                    last_output = runtime.execute_smb_write(connection_ref, remote_path, rendered_content)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_smb_write_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "smb_write_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.smb_write(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.smb_write")
                continue

            if step_type == "rss_read":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                try:
                    last_output = runtime.execute_rss_read(connection_ref, language=language)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_rss_read_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "rss_read_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.rss_read(error-continue)")
                        continue
                    return failure
                outputs[step_id] = last_output
                executed.append(f"{idx}.rss_read")
                continue

            if step_type == "llm_transform":
                prompt_tmpl = str(params.get("prompt", "")).strip() or "Fasse das kurz zusammen:\n{prev_output}"
                rendered = render_step_template(prompt_tmpl, values)
                rsp = await runtime.llm_client.chat(
                    [
                        {"role": "system", "content": "Du bist ein knapper Skill-Transformer. Antworte nur mit dem Ergebnis."},
                        {"role": "user", "content": rendered},
                    ],
                    source="recipe_runtime",
                    operation="llm_transform",
                )
                last_output = runtime.truncate_text(rsp.content, 1400)
                usage = rsp.usage if isinstance(rsp.usage, dict) else {}
                prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
                outputs[step_id] = last_output
                executed.append(f"{idx}.llm_transform")
                continue

            if step_type == "discord_send":
                connection_ref = str(params.get("connection_ref", "")).strip().lower()
                webhook = ""
                if connection_ref:
                    discord_conn = getattr(getattr(runtime.settings, "connections", object()), "discord", {}).get(connection_ref)
                    if discord_conn is not None:
                        if not bool(getattr(discord_conn, "allow_skill_messages", True)):
                            failure = SkillResult(
                                skill_name=build_recipe_runtime_skill_name(skill_id),
                                content="",
                                success=False,
                                error="recipe_discord_messages_disabled",
                            )
                            if on_error == "continue":
                                err_text = failure.error or "discord_send_error"
                                last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                                outputs[step_id] = last_output
                                executed.append(f"{idx}.discord_send(error-continue)")
                                continue
                            return failure
                        webhook = str(getattr(discord_conn, "webhook_url", "")).strip()
                if not webhook:
                    webhook = str(params.get("webhook_url", "")).strip()
                if not webhook:
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error="recipe_discord_missing_webhook",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "discord_step_failed"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.discord_send(error-continue)")
                        continue
                    return failure
                body_tmpl = str(params.get("message", "")).strip() or "{prev_output}"
                content = render_step_template(body_tmpl, values)
                try:
                    runtime.http_runtime.send_discord_webhook_url(webhook, content)
                except Exception as exc:  # noqa: BLE001
                    failure = SkillResult(
                        skill_name=build_recipe_runtime_skill_name(skill_id),
                        content="",
                        success=False,
                        error=f"recipe_discord_send_error:{exc}",
                    )
                    if on_error == "continue":
                        err_text = failure.error or "discord_send_error"
                        last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                        outputs[step_id] = last_output
                        executed.append(f"{idx}.discord_send(error-continue)")
                        continue
                    return failure
                last_output = _recipe_text(language, "discord_step_sent", "Discord sent ({length} characters).", length=len(content))
                outputs[step_id] = content
                executed.append(f"{idx}.discord_send")
                continue

            if step_type == "chat_send":
                body_tmpl = (
                    str(params.get("chat_message", "")).strip()
                    or str(params.get("message", "")).strip()
                    or "{prev_output}"
                )
                content = render_step_template(body_tmpl, values)
                last_output = runtime.truncate_text(content, 1400)
                outputs[step_id] = last_output
                executed.append(f"{idx}.chat_send")
                direct_chat = True
                continue

            failure = SkillResult(
                skill_name=build_recipe_runtime_skill_name(skill_id),
                content="",
                success=False,
                error=f"recipe_unknown_step_type:{step_type}",
            )
            if on_error == "continue":
                err_text = failure.error or "unknown_step_type"
                last_output = f"{_recipe_step_error_prefix(language, step_id)} {err_text}"
                outputs[step_id] = last_output
                executed.append(f"{idx}.unknown(error-continue)")
                continue
            return failure

        lines = [f"[Stored Recipe Steps] {skill_name}", _recipe_text(language, "steps_executed", "Executed: {steps}", steps=", ".join(executed))]
        ssh_summary = _format_ssh_step_run_summary(ssh_run_summaries)
        if ssh_summary:
            lines.append(ssh_summary)
        held_summary = format_held_packages_summary(held_by_connection, connection_targets)
        if held_summary:
            lines.append(held_summary)
        if last_output:
            lines.append(_recipe_text(language, "steps_result", "Result:\n{result}", result=runtime.truncate_text(last_output, 1400)))
        meta: dict[str, Any] = {
            "recipe_id": skill_id,
            "recipe_name": skill_name,
            "custom_skill_id": skill_id,
            "custom_skill_name": skill_name,
            "custom_execution": "steps",
            "custom_steps_executed": executed,
            "custom_steps_skipped": skipped,
            "direct_chat_response": direct_chat,
            "custom_ssh_run_summary": ssh_summary,
            "custom_held_packages_by_connection": held_by_connection,
            "custom_connection_targets": connection_targets,
            "custom_held_summary": held_summary,
            "error_interpretations_by_connection": error_interpretations,
        }
        if direct_chat and last_output:
            final_chat = last_output
            if ssh_summary and ssh_summary not in final_chat:
                final_chat = f"{final_chat}\n\n{ssh_summary}"
            if held_summary and held_summary not in final_chat:
                final_chat = f"{final_chat}\n\n{held_summary}"
            meta["direct_chat_text"] = final_chat
        if total_tokens > 0:
            meta["extraction_model"] = runtime.settings.llm.model
            meta["extraction_usage"] = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "calls": 1,
            }
        return SkillResult(
            skill_name=build_recipe_runtime_skill_name(skill_id),
            content="\n".join(lines),
            success=True,
            metadata=meta,
        )

