from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    skill_name: str
    content: str
    success: bool
    tokens_saved: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    name: str = "base"
    description: str = ""
    keywords: list[str] = []
    prompt_file: str = ""
    max_context_chars: int = 1500

    @abstractmethod
    async def execute(self, query: str, params: dict) -> SkillResult:
        raise NotImplementedError

    def truncate(self, text: str) -> tuple[str, int]:
        if len(text) <= self.max_context_chars:
            return text, 0
        overflow = len(text) - self.max_context_chars
        return text[: self.max_context_chars] + "\n[... gekuerzt]", overflow
