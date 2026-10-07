"""SSH capability execution adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from aria.modules.action_contracts.plan import ActionPlan
from aria.modules.recipe_runtime.contracts import DIRECT_SSH_RECIPE_ID
from aria.modules.recipe_runtime.contracts import RECIPE_SSH_NONZERO_EXIT_ERROR
from aria.modules.runtime_result_summary.summarizers import extract_df_metrics
from aria.modules.runtime_result_summary.summarizers import extract_docker_ps_metrics
from aria.modules.runtime_result_summary.summarizers import extract_free_metrics
from aria.modules.runtime_result_summary.summarizers import extract_systemctl_active_states
from aria.modules.runtime_result_summary.summarizers import extract_uptime_metrics
from aria.modules.runtime_result_summary.summarizers import summarize_ssh_result_for_chat
from aria.modules.skill_contracts.contracts import SkillResult
from aria.modules.ssh_policy.policy import validate_ssh_readonly_policy

ExecuteCustomSSHCommand = Callable[..., Awaitable[SkillResult]]
MessageBuilder = Callable[[str | None, str, str], str]
SpaceNormalizer = Callable[[str], str]


def plan_has_user_policy_confirmation(plan: ActionPlan) -> bool:
    return any(
        str(note or "").strip().lower().startswith("user_confirmed_policy")
        for note in list(plan.notes or [])
    )


async def execute_ssh_command(
    *,
    plan: ActionPlan,
    execute_custom_ssh_command: ExecuteCustomSSHCommand,
    normalize_spaces: SpaceNormalizer,
    text: MessageBuilder,
    language: str = "de",
) -> str:
    ssh_kwargs: dict[str, object] = {}
    if plan_has_user_policy_confirmation(plan):
        ssh_kwargs["policy_confirmed"] = True
    result = await execute_custom_ssh_command(
        skill_id=DIRECT_SSH_RECIPE_ID,
        skill_name="SSH Command",
        connection_ref=plan.connection_ref,
        command_template=plan.content,
        message=plan.content,
        language=language,
        **ssh_kwargs,
    )
    if result.success:
        summarized = summarize_ssh_result_for_chat(
            result,
            connection_ref=plan.connection_ref,
            language=language,
        )
        if summarized:
            return summarized
        return result.content
    if can_salvage_partial_ssh_result(result, normalize_spaces=normalize_spaces):
        summarized = summarize_ssh_result_for_chat(
            result,
            connection_ref=plan.connection_ref,
            language=language,
        )
        if summarized:
            return summarized + " " + text(
                language,
                "partial_ssh_note",
                "Note: at least one sub-check in the command did not complete cleanly.",
            )
    raise ValueError(
        str(result.error or "").strip()
        or text(language, "ssh_command_failed", "SSH command failed.")
    )


def can_salvage_partial_ssh_result(
    result: SkillResult,
    *,
    normalize_spaces: SpaceNormalizer,
) -> bool:
    if bool(result.success):
        return False
    if str(result.error or "").strip() != RECIPE_SSH_NONZERO_EXIT_ERROR:
        return False
    meta = result.metadata or {}
    stdout = str(meta.get("custom_stdout", "") or "").strip()
    command = normalize_spaces(str(meta.get("custom_command", "") or ""))
    if not stdout or not command:
        return False
    if validate_ssh_readonly_policy(command).action == "block":
        return False
    metrics = extract_uptime_metrics(stdout)
    df_metrics = extract_df_metrics(stdout)
    free_metrics = extract_free_metrics(stdout)
    docker_metrics = extract_docker_ps_metrics(stdout)
    service_states = extract_systemctl_active_states(stdout)
    return bool(metrics or df_metrics or free_metrics or docker_metrics or service_states)
