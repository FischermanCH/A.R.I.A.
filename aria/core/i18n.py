from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class I18NStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def available_languages(self) -> list[str]:
        if not self.base_dir.exists():
            return ["de"]
        langs = sorted(path.stem for path in self.base_dir.glob("*.json") if path.is_file())
        return langs or ["de"]

    def _load(self, lang: str) -> dict[str, Any]:
        key = (lang or "de").strip().lower() or "de"
        if key in self._cache:
            return self._cache[key]
        file_path = self.base_dir / f"{key}.json"
        if not file_path.exists():
            self._cache[key] = {}
            return {}
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                self._cache[key] = payload
                return payload
        except Exception:
            pass
        self._cache[key] = {}
        return {}

    @staticmethod
    def _lookup(data: dict[str, Any], dotted_key: str) -> str:
        direct = data.get(dotted_key)
        if isinstance(direct, (str, int, float, bool)):
            return str(direct)
        cursor: Any = data
        for part in dotted_key.split("."):
            if not isinstance(cursor, dict):
                return ""
            cursor = cursor.get(part)
            if cursor is None:
                return ""
        return str(cursor) if isinstance(cursor, (str, int, float, bool)) else ""

    def t(self, lang: str, key: str, default: str = "") -> str:
        normalized_lang = (lang or "de").strip().lower() or "de"
        value = self._lookup(self._load(normalized_lang), key)
        if value:
            return value
        if normalized_lang != "de":
            fallback = self._lookup(self._load("de"), key)
            if fallback:
                return fallback
        return default or key

    def resolve_lang(self, requested: str | None, default_lang: str = "de") -> str:
        supported = set(self.available_languages())
        lang = (requested or "").strip().lower()
        if lang in supported:
            return lang
        fallback = (default_lang or "de").strip().lower() or "de"
        if fallback in supported:
            return fallback
        return "de"

    def clear_cache(self) -> None:
        self._cache.clear()
