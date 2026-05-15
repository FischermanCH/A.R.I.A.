from __future__ import annotations

import json
import re
from typing import Any

from aria.core.text_utils import extract_json_object

RSS_DIGEST_OPTIONS_NOTE_PREFIX = "__rss_digest_options__:"
RSS_DIGEST_MAX_REQUESTED_COUNT = 12

_DIGIT_COUNT_RE = re.compile(r"\b(?:letzte[nsr]?|latest|last|top|neueste[nsr]?|recent)?\s*(\d{1,2})\b", re.IGNORECASE)
_COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "eins": 1,
    "eine": 1,
    "einen": 1,
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fuenf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwoelf": 12,
}
_OPTION_HINT_TERMS = (
    "letzte",
    "letzten",
    "latest",
    "last",
    "top",
    "neueste",
    "neuesten",
    "zusammenfassung",
    "summary",
    "digest",
    "kurz",
    "brief",
    "detail",
    "ausfuehrlich",
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _ascii_fold(value: Any) -> str:
    return (
        _clean_text(value)
        .lower()
        .replace("\u00e4", "ae")
        .replace("\u00f6", "oe")
        .replace("\u00fc", "ue")
        .replace("\u00df", "ss")
    )


def _bounded_count(value: Any) -> int:
    try:
        count = int(value)
    except Exception:
        return 0
    if count <= 0:
        return 0
    return min(count, RSS_DIGEST_MAX_REQUESTED_COUNT)


def rss_digest_query_has_option_hints(query: str) -> bool:
    lower = _ascii_fold(query)
    if not lower:
        return False
    if _DIGIT_COUNT_RE.search(lower):
        return True
    tokens = set(re.findall(r"[a-zA-Z]+", lower))
    if tokens & set(_COUNT_WORDS):
        return True
    return any(term in lower for term in _OPTION_HINT_TERMS)


def fallback_rss_digest_options(query: str) -> dict[str, Any]:
    lower = _ascii_fold(query)
    requested_count = 0
    digit_match = _DIGIT_COUNT_RE.search(lower)
    if digit_match:
        requested_count = _bounded_count(digit_match.group(1))
    if not requested_count:
        for token in re.findall(r"[a-zA-Z]+", lower):
            requested_count = _bounded_count(_COUNT_WORDS.get(token))
            if requested_count:
                break
    detail_level = "normal"
    if any(term in lower for term in ("kurz", "brief", "short")):
        detail_level = "brief"
    elif any(term in lower for term in ("detail", "ausfuehrlich", "detailed")):
        detail_level = "detailed"
    return {
        "requested_count": requested_count,
        "detail_level": detail_level,
        "source": "fallback",
    }


def normalize_rss_digest_options(source: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(source or {})
    requested_count = _bounded_count(payload.get("requested_count"))
    detail_level = str(payload.get("detail_level", "") or "").strip().lower()
    if detail_level not in {"brief", "normal", "detailed"}:
        detail_level = "normal"
    return {
        "requested_count": requested_count,
        "detail_level": detail_level,
        "source": _clean_text(payload.get("source")),
        "reason": _clean_text(payload.get("reason")),
    }


def build_rss_digest_options_note(options: dict[str, Any] | None) -> str:
    normalized = normalize_rss_digest_options(options)
    if not normalized["requested_count"] and normalized["detail_level"] == "normal":
        return ""
    return RSS_DIGEST_OPTIONS_NOTE_PREFIX + json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))


def parse_rss_digest_options_note(notes: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    for item in list(notes or []):
        text = str(item or "").strip()
        if not text.startswith(RSS_DIGEST_OPTIONS_NOTE_PREFIX):
            continue
        try:
            payload = json.loads(text[len(RSS_DIGEST_OPTIONS_NOTE_PREFIX) :])
        except Exception:
            return {}
        if isinstance(payload, dict):
            return normalize_rss_digest_options(payload)
    return {}


async def infer_rss_digest_options(
    query: str,
    *,
    llm_client: Any | None,
    language: str = "",
) -> dict[str, Any]:
    clean_query = _clean_text(query)
    if not rss_digest_query_has_option_hints(clean_query):
        return {}
    fallback = fallback_rss_digest_options(clean_query)
    if llm_client is None:
        return fallback
    system_prompt = (
        "You extract bounded RSS/news digest presentation preferences for ARIA. "
        "Do not choose feeds and do not execute anything. "
        f"Clamp requested_count to {RSS_DIGEST_MAX_REQUESTED_COUNT}. "
        "Return only JSON: "
        '{"requested_count":0|1..12,"detail_level":"brief|normal|detailed","reason":"short reason"}.'
    )
    user_prompt = "\n".join(
        [
            f"User request: {clean_query}",
            f"Language: {_clean_text(language) or '-'}",
            "If no explicit count is requested, use 0.",
        ]
    )
    try:
        response = await llm_client.chat(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            source="rss_digest_options",
            operation="rss_digest_options",
        )
    except Exception:
        return fallback
    payload = extract_json_object(str(getattr(response, "content", "") or "")) or {}
    normalized = normalize_rss_digest_options({**fallback, **payload, "source": "llm"})
    if not normalized["requested_count"]:
        normalized["requested_count"] = int(fallback.get("requested_count", 0) or 0)
    if normalized["detail_level"] == "normal" and fallback.get("detail_level") != "normal":
        normalized["detail_level"] = str(fallback.get("detail_level") or "normal")
    return normalized
