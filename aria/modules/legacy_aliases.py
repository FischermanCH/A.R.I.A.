"""Exact deprecated module names mapped to canonical module owners."""

from __future__ import annotations

LEGACY_MODULE_ALIASES: dict[str, str] = {
    "aria.skills.base": "aria.modules.skill_contracts.contracts",
    "aria.skills.memory": "aria.modules.memory_learning_bridge.skill",
}

DURABLE_LEGACY_MODULE_ALIASES = frozenset(LEGACY_MODULE_ALIASES)
