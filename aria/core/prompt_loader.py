from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


class PromptLoadError(RuntimeError):
    """Prompt-Datei konnte nicht geladen werden."""


@dataclass
class CachedPrompt:
    content: str
    mtime: float


class PromptLoader:
    def __init__(self, persona_path: str | Path):
        self.persona_path = Path(persona_path)
        self._persona_cache: CachedPrompt | None = None

    def get_persona(self) -> str:
        if not self.persona_path.exists():
            raise PromptLoadError(f"Persona-Datei fehlt: {self.persona_path}")

        mtime = self.persona_path.stat().st_mtime
        if self._persona_cache and self._persona_cache.mtime == mtime:
            return self._persona_cache.content

        content = self.persona_path.read_text(encoding="utf-8").strip()
        if not content:
            raise PromptLoadError(f"Persona-Datei ist leer: {self.persona_path}")

        self._persona_cache = CachedPrompt(content=content, mtime=mtime)
        return content

    def get_persona_name(self, default: str = "ARIA") -> str:
        content = self.get_persona()
        match = re.search(r"(?im)^\s*name\s*:\s*(.+?)\s*$", content)
        if not match:
            return str(default or "ARIA").strip() or "ARIA"
        clean = str(match.group(1) or "").strip()
        return clean or (str(default or "ARIA").strip() or "ARIA")
