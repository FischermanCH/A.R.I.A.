from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import re

import yaml


@dataclass
class ErrorInterpretation:
    category: str
    title: str
    cause: str
    next_step: str
    matched_pattern: str = ""

    def summary(self) -> str:
        parts = [self.title.strip(), self.cause.strip(), self.next_step.strip()]
        return " ".join(part for part in parts if part)


class ErrorInterpreter:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self._cache_mtime: float | None = None
        self._cache_rules: list[dict[str, Any]] = []

    def _load_rules(self) -> list[dict[str, Any]]:
        try:
            if not self.config_path.exists():
                return []
            stat = self.config_path.stat()
            if self._cache_mtime == stat.st_mtime:
                return list(self._cache_rules)
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                self._cache_rules = []
                self._cache_mtime = stat.st_mtime
                return []
            rules = raw.get("rules", [])
            if not isinstance(rules, list):
                rules = []
            cleaned: list[dict[str, Any]] = []
            for item in rules:
                if not isinstance(item, dict):
                    continue
                rule_id = str(item.get("id", "")).strip().lower()
                patterns = item.get("patterns", [])
                messages = item.get("messages", {})
                if not rule_id or not isinstance(patterns, list) or not isinstance(messages, dict):
                    continue
                cleaned.append(
                    {
                        "id": rule_id,
                        "default": bool(item.get("default", False)),
                        "patterns": [str(pattern).strip() for pattern in patterns if str(pattern).strip()],
                        "messages": messages,
                    }
                )
            self._cache_rules = cleaned
            self._cache_mtime = stat.st_mtime
            return list(cleaned)
        except Exception:
            return []

    @staticmethod
    def _resolve_messages(messages: dict[str, Any], language: str) -> dict[str, str]:
        lang = str(language or "de").strip().lower() or "de"
        scoped = messages.get(lang) if isinstance(messages.get(lang), dict) else None
        fallback = messages.get("de") if isinstance(messages.get("de"), dict) else None
        source = scoped or fallback or {}
        return {
            "title": str(source.get("title", "")).strip(),
            "cause": str(source.get("cause", "")).strip(),
            "next_step": str(source.get("next_step", "")).strip(),
        }

    def interpret(
        self,
        *,
        language: str = "de",
        error_code: str = "",
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        command: str = "",
        connection_ref: str = "",
    ) -> ErrorInterpretation | None:
        rules = self._load_rules()
        if not rules:
            return None

        haystack = "\n".join(
            [
                str(error_code or "").strip(),
                str(command or "").strip(),
                str(stdout or "").strip(),
                str(stderr or "").strip(),
                str(connection_ref or "").strip(),
                str(exit_code),
            ]
        )
        matched_default: dict[str, Any] | None = None
        for rule in rules:
            if rule.get("default"):
                matched_default = rule
                continue
            for pattern in rule.get("patterns", []):
                try:
                    if re.search(pattern, haystack, flags=re.IGNORECASE | re.MULTILINE):
                        text = self._resolve_messages(rule.get("messages", {}), language)
                        return ErrorInterpretation(
                            category=str(rule.get("id", "unknown")),
                            title=text["title"],
                            cause=text["cause"],
                            next_step=text["next_step"],
                            matched_pattern=pattern,
                        )
                except re.error:
                    continue

        if exit_code != 0 or str(error_code or "").strip():
            rule = matched_default
            if rule is not None:
                text = self._resolve_messages(rule.get("messages", {}), language)
                return ErrorInterpretation(
                    category=str(rule.get("id", "unknown")),
                    title=text["title"],
                    cause=text["cause"],
                    next_step=text["next_step"],
                    matched_pattern="default",
                )
        return None
