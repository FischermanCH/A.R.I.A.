"""Deprecated skill import namespace backed by exact lazy aliases."""

from aria.modules.compatibility import install_legacy_module_aliases

install_legacy_module_aliases()

from aria.skills.base import BaseSkill, SkillResult  # noqa: E402
from aria.skills.memory import MemorySkill  # noqa: E402

__all__ = ["BaseSkill", "SkillResult", "MemorySkill"]
