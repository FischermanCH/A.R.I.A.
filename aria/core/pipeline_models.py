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
    safe_fix_plan: list[dict[str, Any]] | None = None
    detail_lines: list[str] = field(default_factory=list)
    pending_action: dict[str, Any] | None = None
