from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class AutoMemoryDecision:
    recall_query: str
    facts: list[str]
    preferences: list[str]
    should_persist_session: bool = False


class AutoMemoryExtractor:
    """Rule-based fact extraction to keep auto-memory deterministic and cheap."""

    _ip_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    _cidr_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\b")
    _host_re = re.compile(r"\b[a-zA-Z0-9][a-zA-Z0-9-]{1,62}[a-zA-Z0-9]\b")
    _kv_re = re.compile(r"([a-zA-Z0-9_.-]{2,64})\s*[:=]\s*([^,;|\n]{2,160})")

    _stop_keys = {
        "ich",
        "du",
        "mein",
        "meine",
        "dein",
        "deine",
        "und",
        "oder",
        "ist",
        "sind",
        "das",
        "dass",
    }

    _preference_patterns = (
        r"\bich bevorzuge\b",
        r"\bich mag\b",
        r"\bich möchte\b",
        r"\bbitte antworte\b",
        r"\bantworte bitte\b",
        r"\bohne floskeln\b",
        r"\bdirekt\b",
    )

    _transient_prefix_patterns = (
        r"^\s*was\b",
        r"^\s*wie\b",
        r"^\s*wo\b",
        r"^\s*wann\b",
        r"^\s*warum\b",
        r"^\s*wieso\b",
        r"^\s*welche?\b",
        r"^\s*gibt es\b",
        r"^\s*brauchen\b",
        r"^\s*erklär[e]?\b",
        r"^\s*erkläre\b",
        r"^\s*vergleiche\b",
        r"^\s*zeige?\b",
        r"^\s*list[e]?\b",
        r"^\s*schick[e]?\b",
        r"^\s*sende\b",
        r"^\s*prüf[e]?\b",
        r"^\s*check[e]?\b",
        r"^\s*ping\b",
        r"^\s*please\b",
        r"^\s*can you\b",
        r"^\s*could you\b",
        r"^\s*show me\b",
        r"^\s*explain\b",
        r"^\s*compare\b",
        r"^\s*send\b",
        r"^\s*check\b",
        r"^\s*ping\b",
    )

    _declarative_session_patterns = (
        r"\bmein(?:e[nmr])?\b",
        r"\bich nutze\b",
        r"\bich verwende\b",
        r"\bich arbeite\b",
        r"\bich betreibe\b",
        r"\bich habe\b",
        r"\bheisst\b",
        r"\bheißt\b",
        r"\bläuft auf\b",
        r"\bist\b",
        r"\bsind\b",
        r"\bhas\b",
        r"\bruns on\b",
        r"\bis\b",
        r"\bare\b",
        r"\bmy\b",
        r"\bi use\b",
        r"\bi run\b",
        r"\bi have\b",
    )

    @staticmethod
    def _clean_spaces(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _extract_kv_facts(cls, text: str) -> list[str]:
        facts: list[str] = []
        for key, value in cls._kv_re.findall(text):
            k = cls._clean_spaces(key).strip(" .,:;").lower()
            v = cls._clean_spaces(value).strip(" .,:;")
            if not k or not v:
                continue
            if k in cls._stop_keys:
                continue
            facts.append(f"{k}: {v}")
        return facts

    @classmethod
    def _extract_network_facts(cls, text: str) -> list[str]:
        facts: list[str] = []
        for cidr in cls._cidr_re.findall(text):
            facts.append(f"netz: {cidr}")
        for ip in cls._ip_re.findall(text):
            facts.append(f"ip: {ip}")
        return facts

    @classmethod
    def _extract_sentence_fact(cls, text: str) -> str | None:
        if len(text) < 12 or len(text) > 180:
            return None
        if cls._looks_like_transient_prompt(text):
            return None
        lowered = text.lower()
        signal_terms = (
            "ip",
            "hostname",
            "dns",
            "gateway",
            "firewall",
            "nas",
            "proxmox",
            "server",
            "vlan",
            "netz",
        )
        if any(t in lowered for t in signal_terms):
            return cls._clean_spaces(text).strip(" .")
        return None

    @classmethod
    def _looks_like_transient_prompt(cls, text: str) -> bool:
        cleaned = cls._clean_spaces(text)
        if not cleaned:
            return True
        lowered = cleaned.lower()
        if "?" in cleaned:
            return True
        if lowered.startswith(("/", "!")):
            return True
        return any(re.search(pattern, lowered) for pattern in cls._transient_prefix_patterns)

    @classmethod
    def _should_persist_session(cls, text: str, facts: list[str], preferences: list[str]) -> bool:
        if cls._looks_like_transient_prompt(text):
            return bool(preferences)
        if facts or preferences:
            return True
        lowered = cls._clean_spaces(text).lower()
        if len(lowered) < 12:
            return False
        return any(re.search(pattern, lowered) for pattern in cls._declarative_session_patterns)

    @classmethod
    def _extract_preferences(cls, text: str) -> list[str]:
        lowered = text.lower()
        if not any(re.search(pattern, lowered) for pattern in cls._preference_patterns):
            return []
        cleaned = cls._clean_spaces(text).strip(" .")
        if not cleaned:
            return []
        return [cleaned]

    @classmethod
    def decide(cls, message: str, max_facts: int = 3) -> AutoMemoryDecision:
        clean = cls._clean_spaces(message)
        facts: list[str] = []
        preferences: list[str] = []
        facts.extend(cls._extract_kv_facts(clean))
        facts.extend(cls._extract_network_facts(clean))
        preferences.extend(cls._extract_preferences(clean))
        sentence_fact = cls._extract_sentence_fact(clean)
        if sentence_fact:
            facts.append(sentence_fact)

        deduped: list[str] = []
        seen: set[str] = set()
        for fact in facts:
            key = fact.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(fact)
            if len(deduped) >= max(1, max_facts):
                break

        recall_query = re.sub(r"[?!.:,;]+", " ", clean)
        recall_query = cls._clean_spaces(recall_query)
        return AutoMemoryDecision(
            recall_query=recall_query or clean,
            facts=deduped,
            preferences=preferences,
            should_persist_session=cls._should_persist_session(clean, deduped, preferences),
        )
