from __future__ import annotations

import json
from pathlib import Path
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

    _lexicon_path = Path(__file__).resolve().parents[1] / "lexicons" / "auto_memory.json"
    try:
        _lexicon_raw = json.loads(_lexicon_path.read_text(encoding="utf-8"))
        _lexicon = _lexicon_raw if isinstance(_lexicon_raw, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load auto-memory lexicon: {_lexicon_path}") from exc

    _ip_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    _cidr_re = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\b")
    _host_re = re.compile(r"\b[a-zA-Z0-9][a-zA-Z0-9-]{1,62}[a-zA-Z0-9]\b")
    _kv_re = re.compile(r"([a-zA-Z0-9_.-]{2,64})\s*[:=]\s*([^,;|\n]{2,160})")

    _stop_keys = {
        str(value).strip().lower()
        for value in _lexicon.get("stop_keys", [])
        if str(value).strip()
    }

    _preference_patterns = tuple(str(value) for value in _lexicon.get("preference_patterns", []) if str(value).strip())
    _transient_prefix_patterns = tuple(
        str(value) for value in _lexicon.get("transient_prefix_patterns", []) if str(value).strip()
    )
    _declarative_session_patterns = tuple(
        str(value) for value in _lexicon.get("declarative_session_patterns", []) if str(value).strip()
    )
    _sentence_signal_terms = tuple(
        str(value).strip().lower() for value in _lexicon.get("sentence_signal_terms", []) if str(value).strip()
    )
    _network_fact_labels = _lexicon.get("network_fact_labels", {})
    _cidr_label = str(_network_fact_labels.get("cidr", "network")) if isinstance(_network_fact_labels, dict) else "network"
    _ip_label = str(_network_fact_labels.get("ip", "ip")) if isinstance(_network_fact_labels, dict) else "ip"

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
            facts.append(f"{cls._cidr_label}: {cidr}")
        for ip in cls._ip_re.findall(text):
            facts.append(f"{cls._ip_label}: {ip}")
        return facts

    @classmethod
    def _extract_sentence_fact(cls, text: str) -> str | None:
        if len(text) < 12 or len(text) > 180:
            return None
        if cls._looks_like_transient_prompt(text):
            return None
        lowered = text.lower()
        if any(term in lowered for term in cls._sentence_signal_terms):
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
