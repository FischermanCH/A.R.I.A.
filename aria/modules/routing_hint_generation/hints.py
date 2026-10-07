from __future__ import annotations

import json
import re
from typing import Any



def extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def routing_hint_language_instruction(lang: str) -> str:
    code = str(lang or "de").strip().lower() or "de"
    if code.startswith("de"):
        return (
            "Output language: German (Deutsch). "
            "Write title and description in natural German. "
            "Aliases and tags must provide useful German semantic retrieval context. "
            "Keep product names and proper nouns unchanged. "
            "If an English product term is common, it may appear once alongside natural German context. "
            "Do not switch to English only because the source page is in English."
        )
    if code.startswith("en"):
        return (
            "Output language: English. "
            "Write title and description in natural English. "
            "Aliases and tags must provide useful English semantic retrieval context. "
            "Keep product names and proper nouns unchanged."
        )
    return (
        f"Output language: {code}. "
        "Write title, description, aliases, and tags primarily in that language when natural. "
        "Keep product names and proper nouns unchanged. "
        "Prefer natural semantic retrieval context in that language."
    )


def connection_metadata_is_sparse(
    *,
    title: str = "",
    description: str = "",
    aliases: str = "",
    tags: str = "",
) -> bool:
    return not all(
        [
            str(title or "").strip(),
            str(description or "").strip(),
            str(aliases or "").strip(),
            str(tags or "").strip(),
        ]
    )


async def suggest_connection_metadata_with_llm(
    llm_client: Any,
    *,
    connection_kind_label: str,
    connection_ref: str,
    source_label: str,
    source_value: str,
    detected_title: str,
    detected_description: str,
    detected_keywords: list[str],
    fallback_aliases: list[str],
    current_title: str,
    current_description: str,
    current_aliases: str,
    current_tags: str,
    lang: str,
    goal_text: str,
) -> dict[str, str]:
    fallback_tags = [item for item in detected_keywords if item][:8]
    if llm_client is None:
        return {
            "title": current_title.strip() or detected_title,
            "description": current_description.strip() or detected_description,
            "aliases": ", ".join(fallback_aliases),
            "tags": ", ".join(fallback_tags),
        }

    system_prompt = (
        f"You generate concise metadata for an {connection_kind_label} connection profile in ARIA. "
        'Respond with JSON only in the format {"title":"...","description":"...","aliases":["..."],"tags":["..."]}. '
        "Description max 120 characters. Aliases max 8 entries, each 2-40 chars. "
        "Tags max 8 entries, each 2-24 chars. No markdown. "
        + routing_hint_language_instruction(lang)
    )
    user_prompt = "\n".join(
        [
            f"Preferred language: {str(lang or 'de').strip() or 'de'}",
            f"Connection ref: {str(connection_ref or '').strip() or '-'}",
            f"{source_label}: {str(source_value or '').strip() or '-'}",
            f"Detected page title: {detected_title or '-'}",
            f"Detected description: {detected_description or '-'}",
            f"Detected keywords: {', '.join(detected_keywords) or '-'}",
            f"Current title: {str(current_title or '').strip() or '-'}",
            f"Current description: {str(current_description or '').strip() or '-'}",
            f"Current aliases: {str(current_aliases or '').strip() or '-'}",
            f"Current tags: {str(current_tags or '').strip() or '-'}",
            "",
            goal_text,
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            source=f"{str(connection_kind_label or '').strip().lower()}_metadata",
            operation="suggest_metadata",
            user_id="system",
        )
    except Exception:
        response = None

    payload = extract_json_object(str(getattr(response, "content", "") if response else "") or "") or {}
    title = str(payload.get("title", "") or "").strip()[:80]
    description = str(payload.get("description", "") or "").strip()[:120]
    aliases_raw = payload.get("aliases", [])
    aliases = [str(item).strip()[:40] for item in aliases_raw if str(item).strip()][:8] if isinstance(aliases_raw, list) else []
    tags_raw = payload.get("tags", [])
    tags = [str(item).strip()[:24] for item in tags_raw if str(item).strip()][:8] if isinstance(tags_raw, list) else []
    return {
        "title": title or current_title.strip() or detected_title,
        "description": description or current_description.strip() or detected_description,
        "aliases": ", ".join(aliases or fallback_aliases),
        "tags": ", ".join(tags or fallback_tags),
    }
