from __future__ import annotations

from typing import Any

from aria.modules.action_contracts.plan import CapabilityDraft, MemoryHints


class MemoryAssistResolver:
    """Compatibility boundary for legacy callers.

    Personal context selection belongs to the LLM-owned turn plan. This adapter
    deliberately performs no free-language matching or target selection.
    """

    def __init__(self, memory_skill_getter: Any, capability_context_getter: Any | None = None) -> None:
        self._memory_skill_getter = memory_skill_getter
        self._capability_context_getter = capability_context_getter

    async def resolve(
        self,
        *,
        draft: CapabilityDraft,
        message: str,
        user_id: str,
        available_connections: dict[str, Any],
    ) -> MemoryHints:
        _ = (draft, message, user_id, available_connections)
        return MemoryHints()
