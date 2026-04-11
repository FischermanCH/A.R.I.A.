from __future__ import annotations

from dataclasses import dataclass
import re

from aria.core.config import RoutingLanguageConfig


@dataclass
class RouterDecision:
    intents: list[str]
    level: int = 1


class KeywordRouter:
    """Router Stufe 1: deterministisches Keyword-Matching."""

    def __init__(self, routing: RoutingLanguageConfig):
        self._default_routing = routing

    @staticmethod
    def _contains_guarded_store_phrase(text: str) -> bool:
        return "vergiss nicht" in text

    def _contains_forget_intent(self, text: str, forget_keywords: tuple[str, ...]) -> bool:
        for keyword in forget_keywords:
            if not keyword:
                continue
            if keyword == "vergiss" and self._contains_guarded_store_phrase(text):
                continue
            if keyword in text:
                return True
        return False

    @staticmethod
    def _compile_patterns(values: list[str]) -> tuple[re.Pattern[str], ...]:
        rows: list[re.Pattern[str]] = []
        for value in values:
            clean = str(value or "").strip()
            if not clean:
                continue
            try:
                rows.append(re.compile(clean))
            except re.error:
                continue
        return tuple(rows)

    def _contains_skill_status_intent(self, text: str, active: RoutingLanguageConfig) -> bool:
        skill_status_keywords = self._normalize_keywords(active.skill_status_keywords)
        if any(keyword in text for keyword in skill_status_keywords):
            return True

        skill_status_patterns = self._compile_patterns(active.skill_status_patterns)
        if any(pattern.search(text) for pattern in skill_status_patterns):
            has_status_hint = any(token in text for token in self._normalize_keywords(active.skill_status_status_terms))
            if has_status_hint:
                return True

        has_skill_word = any(token in text for token in self._normalize_keywords(active.skill_status_skill_terms))
        has_status_word = any(token in text for token in self._normalize_keywords(active.skill_status_status_terms))
        return has_skill_word and has_status_word

    @staticmethod
    def _normalize_keywords(values: list[str]) -> tuple[str, ...]:
        return tuple(str(item).lower().strip() for item in values if str(item).strip())

    def classify(self, message: str, routing: RoutingLanguageConfig | None = None) -> RouterDecision:
        text = message.lower().strip()
        active = routing or self._default_routing
        memory_store_keywords = self._normalize_keywords(active.memory_store_keywords)
        memory_recall_keywords = self._normalize_keywords(active.memory_recall_keywords)
        memory_forget_keywords = self._normalize_keywords(active.memory_forget_keywords)
        web_search_keywords = self._normalize_keywords(active.web_search_keywords)
        intents: list[str] = []

        if self._contains_skill_status_intent(text, active):
            return RouterDecision(intents=["skill_status"], level=1)

        if self._contains_forget_intent(text, memory_forget_keywords):
            return RouterDecision(intents=["memory_forget"], level=1)

        if any(keyword in text for keyword in memory_store_keywords):
            intents.append("memory_store")

        if any(keyword in text for keyword in memory_recall_keywords):
            intents.append("memory_recall")

        if any(keyword in text for keyword in web_search_keywords):
            intents.append("web_search")

        if not intents:
            intents = ["chat"]

        return RouterDecision(intents=intents, level=1)
