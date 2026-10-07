from __future__ import annotations

import json
import re
from typing import Any

_JSON_FENCE_START_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_END_RE = re.compile(r"\s*```$")


def is_english(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("en")


def is_german(language: str | None) -> bool:
    return str(language or "").strip().lower().startswith("de")


def localized_text(language: str | None, *, de: str, en: str) -> str:
    return en if is_english(language) else de


def extract_json_object(raw: str, *, allow_fenced: bool = True) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if allow_fenced and text.startswith("```"):
        text = _JSON_FENCE_START_RE.sub("", text)
        text = _JSON_FENCE_END_RE.sub("", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
