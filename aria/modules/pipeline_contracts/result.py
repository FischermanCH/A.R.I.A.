"""Passive result data returned by the pipeline boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineResult:
    request_id: str
    text: str
    usage: dict[str, int]
    intents: list[str]
    skill_errors: list[str]
    router_level: int
    duration_ms: int
    chat_cost_usd: float | None = None
    embedding_cost_usd: float | None = None
    total_cost_usd: float | None = None
    detail_lines: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    routed_action_confirm_command: str | None = None
    routed_action_confirm_preview: str | None = None
    clear_routed_action_affordance: bool = False
    suggestion_affordance: dict[str, str] | None = None
    agent_job_id: str = ""
