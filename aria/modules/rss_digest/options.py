from __future__ import annotations

import json
import re
from typing import Any

from aria.modules.platform_primitives.text_utils import extract_json_object

RSS_DIGEST_OPTIONS_NOTE_PREFIX = "__rss_digest_options__:"
RSS_DIGEST_MAX_REQUESTED_COUNT = 12

def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _bounded_count(value: Any) -> int:
    try:
        count = int(value)
    except Exception:
        return 0
    if count <= 0:
        return 0
    return min(count, RSS_DIGEST_MAX_REQUESTED_COUNT)


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
    if not clean_query or llm_client is None:
        return {}
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
        return {}
    payload = extract_json_object(str(getattr(response, "content", "") or "")) or {}
    return normalize_rss_digest_options({**payload, "source": "llm"})
