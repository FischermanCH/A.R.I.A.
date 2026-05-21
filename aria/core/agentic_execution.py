from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from aria.core.action_plan import ActionPlan
from aria.core.agentic_execution_learning import AgenticExecutionLearningService


@dataclass(slots=True)
class AgenticExecutionRequest:
    resolved: dict[str, Any]
    payload: dict[str, Any]
    action: dict[str, Any]
    user_id: str
    language: str = "de"


@dataclass(slots=True)
class AgenticExecutionResult:
    intents: list[str]
    text: str
    detail_lines: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_pipeline_tuple(self) -> tuple[list[str], str, list[str], list[str]]:
        return self.intents, self.text, self.detail_lines, self.errors


class AgenticExecutionHandler(Protocol):
    def can_handle(self, request: AgenticExecutionRequest) -> bool:
        ...

    async def execute(self, request: AgenticExecutionRequest) -> AgenticExecutionResult:
        ...


@dataclass(slots=True)
class AgenticExecutionHooks:
    routing_debug_enabled: Callable[[], bool]
    payload_to_action_plan: Callable[[dict[str, Any]], ActionPlan]
    format_missing_message: Callable[[ActionPlan, str], str]
    format_execution_error: Callable[[ActionPlan, Exception, str], str]
    build_capability_detail_lines: Callable[[ActionPlan, str], list[str]]
    text: Callable[..., str]
    learning_service: AgenticExecutionLearningService
