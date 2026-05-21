from __future__ import annotations

from dataclasses import dataclass

from aria.core.agentic_content_access import AgenticContentAccessHandler
from aria.core.agentic_content_access import AgenticContentAccessRequest
from aria.core.agentic_content_access import AgenticContentAccessResult


@dataclass(slots=True)
class AgenticContentAccessRegistry:
    handlers: list[AgenticContentAccessHandler]

    async def access_first(self, request: AgenticContentAccessRequest) -> AgenticContentAccessResult | None:
        for handler in self.handlers:
            if handler.can_handle(request):
                return await handler.access(request)
        return None
