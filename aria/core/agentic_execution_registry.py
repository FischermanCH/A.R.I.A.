from __future__ import annotations

from dataclasses import dataclass

from aria.core.agentic_execution import AgenticExecutionHandler
from aria.core.agentic_execution import AgenticExecutionRequest
from aria.core.agentic_execution import AgenticExecutionResult


@dataclass(slots=True)
class AgenticExecutionRegistry:
    handlers: list[AgenticExecutionHandler]

    async def execute_first(self, request: AgenticExecutionRequest) -> AgenticExecutionResult | None:
        for handler in self.handlers:
            if handler.can_handle(request):
                return await handler.execute(request)
        return None
