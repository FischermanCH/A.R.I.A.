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
        self.skill_status_keywords = (
            "welche skills",
            "skills aktiv",
            "aktive skills",
            "aktuelle skills",
            "aktuellen skills",
            "installierte skills",
            "vorhandene skills",
            "deine skills",
            "deine fähigkeiten",
            "deine fähigkeiten",
            "skill status",
            "skills überprüfen",
            "skills überprüfen",
            "was kannst du aktuell ausführen",
            "was kannst du ausführen",
        )
        self.skill_status_patterns = (
            re.compile(r"\bwas\s+f(?:ü|ue)r\s+skills\b"),
            re.compile(r"\bwas\s+sind\s+deine(?:r|n)?\s+.*skills\b"),
            re.compile(r"\bwelche\s+skills\b"),
            re.compile(r"\bskills?\s+hast\s+du\b"),
            re.compile(r"\bwelche\s+f(?:ä|ae)higkeiten\b"),
            re.compile(r"\bf(?:ä|ae)higkeiten\s+hast\s+du\b"),
        )

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

    def _contains_skill_status_intent(self, text: str) -> bool:
        if any(keyword in text for keyword in self.skill_status_keywords):
            return True

        if any(pattern.search(text) for pattern in self.skill_status_patterns):
            has_status_hint = any(
                token in text
                for token in ("aktiv", "aktiviert", "status", "übersicht", "überblick", "liste", "enabled")
            )
            if has_status_hint:
                return True

        has_skill_word = any(
            token in text for token in ("skill", "skills", "fähigkeit", "fähigkeiten", "fähigkeit", "fähigkeiten")
        )
        has_status_word = any(
            token in text
            for token in (
                "aktiv",
                "aktiviert",
                "status",
                "welche",
                "was für",
                "was für",
                "was sind",
                "hast du",
                "liste",
                "aktuell",
                "installiert",
                "vorhanden",
            )
        )
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

        if self._contains_skill_status_intent(text):
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
