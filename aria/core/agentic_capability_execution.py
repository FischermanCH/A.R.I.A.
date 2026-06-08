from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution import AgenticExecutionHooks
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult
from aria.core.agentic_runtime_debug import runtime_debug_line_for_plan


ContentAccessExecutor = Callable[[ActionPlan, str, str], Awaitable[tuple[str, list[str], list[str]] | None]]


@dataclass(slots=True)
class GenericCapabilityExecutionHooks(AgenticExecutionHooks):
    execute_plan: Callable[[ActionPlan, str], Awaitable[str]]
    remember_action: Callable[[str, ActionPlan], None]
    execute_content_access: ContentAccessExecutor
    capability_execution_error_code: Callable[[ActionPlan, Exception], str]


class GenericCapabilityExecutionHandler:
    def __init__(self, hooks: GenericCapabilityExecutionHooks) -> None:
        self._hooks = hooks

    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        plan = self._hooks.payload_to_action_plan(request.payload)
        return bool(str(plan.capability or "").strip())

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
        plan = self._hooks.payload_to_action_plan(request.payload)
        intents = [f"capability:{plan.capability}"] if str(plan.capability or "").strip() else ["chat"]

        content_access_result = await self._hooks.execute_content_access(plan, request.user_id, request.language)
        if content_access_result is not None:
            text, detail_lines, errors = content_access_result
            return AgenticExecutionResult(intents=intents, text=text, detail_lines=detail_lines, errors=errors)

        detail_lines: list[str] = []
        if self._hooks.routing_debug_enabled():
            detail_lines.append(runtime_debug_line_for_plan(plan))
        detail_lines.extend(self._hooks.build_capability_detail_lines(plan, request.language))
        try:
            result_text = await self._hooks.execute_plan(plan, request.language)
        except Exception as exc:
            error_text = self._hooks.format_execution_error(plan, exc, request.language)
            error_code = self._hooks.capability_execution_error_code(plan, exc)
            return AgenticExecutionResult(intents=intents, text=error_text, detail_lines=detail_lines, errors=[error_code])

        if plan.is_complete:
            self._hooks.remember_action(request.user_id, plan)
        self._hooks.learning_service.record_capability_success(
            action=request.action,
            plan=plan,
            result_text=result_text,
            user_message=str(request.resolved.get("query", "") or ""),
            user_id=request.user_id,
            language=request.language,
            detail_lines=detail_lines,
        )
        return AgenticExecutionResult(intents=intents, text=result_text, detail_lines=detail_lines, errors=[])
