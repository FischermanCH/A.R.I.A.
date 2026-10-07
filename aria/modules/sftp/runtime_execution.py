"""SFTP capability execution adapters."""

from __future__ import annotations

from typing import Any, Callable

from aria.modules.action_contracts.plan import ActionPlan
from aria.modules.runtime_result_summary.summarizers import summarize_file_result_for_chat


def execute_sftp_file_read(skill_runtime: Any, plan: ActionPlan) -> str:
    return skill_runtime.execute_sftp_read(plan.connection_ref, plan.path)


def execute_sftp_file_write(skill_runtime: Any, plan: ActionPlan, *, language: str = "de") -> str:
    result_text = skill_runtime.execute_sftp_write(plan.connection_ref, plan.path, plan.content)
    summarized = summarize_file_result_for_chat(
        result_text,
        connection_ref=plan.connection_ref,
        connection_kind=plan.connection_kind,
        capability="file_write",
        path=plan.path,
        language=language,
    )
    return summarized or result_text


def execute_sftp_file_list(
    skill_runtime: Any,
    plan: ActionPlan,
    *,
    call_with_optional_language: Callable[..., Any],
    language: str = "de",
) -> str:
    result_text = call_with_optional_language(
        skill_runtime.execute_sftp_list,
        plan.connection_ref,
        plan.path or ".",
        language=language,
    )
    summarized = summarize_file_result_for_chat(
        result_text,
        connection_ref=plan.connection_ref,
        connection_kind=plan.connection_kind,
        capability="file_list",
        path=plan.path or ".",
        language=language,
    )
    return summarized or result_text
