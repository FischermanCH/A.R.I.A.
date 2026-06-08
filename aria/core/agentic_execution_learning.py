from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable

from aria.core.action_plan import ActionPlan
from aria.core.learned_recipe_integration import record_routed_action_success
from aria.core.learned_recipe_store_updates import record_successful_learned_recipe_execution


LearningScheduler = Callable[[dict[str, Any] | None, str, str, list[str], bool], None]
_AUTO_LEARNING_SUPPRESSED: ContextVar[bool] = ContextVar("aria_auto_learning_suppressed", default=False)


def auto_learning_suppressed() -> bool:
    return bool(_AUTO_LEARNING_SUPPRESSED.get())


@contextmanager
def suppress_auto_learning():
    token = _AUTO_LEARNING_SUPPRESSED.set(True)
    try:
        yield
    finally:
        _AUTO_LEARNING_SUPPRESSED.reset(token)


@dataclass(slots=True)
class AgenticExecutionLearningService:
    schedule_followup: LearningScheduler

    def record_capability_success(
        self,
        *,
        action: dict[str, Any],
        plan: ActionPlan,
        result_text: str,
        user_message: str,
        user_id: str,
        language: str,
        detail_lines: list[str],
        curate: bool = True,
    ) -> None:
        if auto_learning_suppressed():
            return
        try:
            learned_entry = record_routed_action_success(
                action=action,
                plan=plan,
                result_text=result_text,
                recorder=record_successful_learned_recipe_execution,
                user_message=user_message,
            )
            self.schedule_followup(learned_entry, user_id, language, detail_lines, curate)
        except Exception:
            pass
