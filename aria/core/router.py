from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from aria.core.config import RoutingLanguageConfig
from aria.core.i18n import I18NStore
from aria.core.recipe_runtime_contract import RECIPE_STATUS_INTENT

_ROUTER_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _router_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    terms: list[str] = []
    for lang in ("de", "en"):
        raw = _ROUTER_I18N.t(lang, f"router.{key}", "")
        terms.extend(term.strip().lower() for term in raw.split(",") if term.strip())
    return tuple(dict.fromkeys(terms)) or fallback


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

    @staticmethod
    def _looks_like_memory_object(text: str) -> bool:
        memory_terms = _router_terms(
            "memory_object_terms",
            ("memory", "note", "notes", "fact", "facts", "alias"),
        )
        return any(term in text for term in memory_terms)

    @staticmethod
    def _looks_like_operational_delete(text: str) -> bool:
        operational_terms = (
            " server",
            " host",
            " ssh",
            " docker",
            " service",
            " dienst",
            " api",
            " webhook",
            " discord",
            " mqtt",
            " http",
            " webseite",
            " rss",
            " postfach",
            " mailbox",
            " kalender",
            " datei",
            " file",
            " ordner",
            " verzeichnis",
            " festplatte",
            " disk",
            "/",
            " auf dem ",
            " auf den ",
            " auf der ",
            " neu",
        )
        return any(term in text for term in operational_terms)

    def _contains_forget_intent(self, text: str, forget_keywords: tuple[str, ...]) -> bool:
        for keyword in forget_keywords:
            if not keyword:
                continue
            if keyword == "vergiss" and self._contains_guarded_store_phrase(text):
                continue
            if keyword in text:
                if self._looks_like_operational_delete(text) and not self._looks_like_memory_object(text):
                    continue
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

    def _contains_recipe_status_intent(self, text: str, active: RoutingLanguageConfig) -> bool:
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

    @staticmethod
    def _contains_store_keyword(text: str, keyword: str) -> bool:
        clean = str(keyword or "").strip().lower()
        if not clean:
            return False
        if " " in clean:
            return clean in text
        # Store verbs like "speicher" must not match nouns such as "speicherplatz".
        pattern = rf"(?<!\w){re.escape(clean)}e?(?!\w)"
        return re.search(pattern, text, re.IGNORECASE) is not None

    def _contains_store_intent(self, text: str, store_keywords: tuple[str, ...]) -> bool:
        for keyword in store_keywords:
            clean_keyword = str(keyword or "").strip().lower()
            if clean_keyword == "speicher" and "speicher frei" in text:
                continue
            if self._contains_store_keyword(text, keyword):
                return True
        return False

    def classify(self, message: str, routing: RoutingLanguageConfig | None = None) -> RouterDecision:
        text = message.lower().strip()
        active = routing or self._default_routing
        memory_store_keywords = self._normalize_keywords(active.memory_store_keywords)
        memory_recall_keywords = self._normalize_keywords(active.memory_recall_keywords)
        memory_forget_keywords = self._normalize_keywords(active.memory_forget_keywords)
        web_search_keywords = self._normalize_keywords(active.web_search_keywords)
        intents: list[str] = []

        if self._contains_recipe_status_intent(text, active):
            return RouterDecision(intents=[RECIPE_STATUS_INTENT], level=1)

        if self._contains_forget_intent(text, memory_forget_keywords):
            return RouterDecision(intents=["memory_forget"], level=1)

        if self._contains_store_intent(text, memory_store_keywords):
            intents.append("memory_store")

        if any(keyword in text for keyword in memory_recall_keywords):
            intents.append("memory_recall")

        if any(keyword in text for keyword in web_search_keywords):
            intents.append("web_search")

        if not intents:
            intents = ["chat"]

        return RouterDecision(intents=intents, level=1)
