from __future__ import annotations

import json
import re
from typing import Any

from aria.core.custom_skills import _validate_custom_skill_manifest


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
            "Aliases and tags must prioritize German routing and trigger terms someone would type in German. "
            "Keep product names and proper nouns unchanged. "
            "If an English product term is common, it may appear once, but include German trigger words too. "
            "Do not switch to English only because the source page is in English."
        )
    if code.startswith("en"):
        return (
            "Output language: English. "
            "Write title and description in natural English. "
            "Aliases and tags must prioritize English routing and trigger terms someone would type in English. "
            "Keep product names and proper nouns unchanged."
        )
    return (
        f"Output language: {code}. "
        "Write title, description, aliases, and tags primarily in that language when natural. "
        "Keep product names and proper nouns unchanged. "
        "Prefer routing terms a user would type in that language."
    )


def normalize_keyword_list(values: list[str], max_items: int = 20) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip().lower()
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
        text = text.strip(" \"'`;,")
        text = re.sub(r"\s+", " ", text)
        if not text or len(text) < 2:
            continue
        if text in seen:
            continue
        seen.add(text)
        rows.append(text[:80])
        if len(rows) >= max_items:
            break
    return rows


def extract_keyword_candidates(text: str) -> list[str]:
    raw = str(text or "").strip()
    if not raw:
        return []

    parsed: list[str] = []
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            values = payload.get("keywords", [])
            if isinstance(values, list):
                parsed = [str(item) for item in values]
        elif isinstance(payload, list):
            parsed = [str(item) for item in payload]
    except json.JSONDecodeError:
        pass

    if parsed:
        return normalize_keyword_list(parsed)

    lines: list[str] = []
    for row in raw.splitlines():
        parts = [piece.strip() for piece in row.split(",")]
        for part in parts:
            if part:
                lines.append(part)
    return normalize_keyword_list(lines)


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


async def suggest_skill_keywords_with_llm(
    llm_client: Any,
    manifest: dict[str, Any],
    *,
    language: str = "de",
    max_keywords: int = 12,
) -> list[str]:
    clean = _validate_custom_skill_manifest(manifest)
    lang = str(language or "de").strip().lower()
    lang_name = "German" if lang.startswith("de") else "English"
    steps = clean.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    step_lines: list[str] = []
    for step in steps[:8]:
        if not isinstance(step, dict):
            continue
        step_type = str(step.get("type", "")).strip()
        step_name = str(step.get("name", "")).strip()
        params = step.get("params", {})
        if not isinstance(params, dict):
            params = {}
        param_hint = ""
        if step_type == "ssh_run":
            param_hint = str(params.get("command", "")).strip()
        elif step_type == "llm_transform":
            param_hint = str(params.get("prompt", "")).strip()
        elif step_type == "discord_send":
            param_hint = str(params.get("message", "")).strip()
        elif step_type == "chat_send":
            param_hint = str(params.get("chat_message", "")).strip()
        row = f"- {step_type}"
        if step_name:
            row += f" | {step_name}"
        if param_hint:
            row += f" | {param_hint[:120]}"
        step_lines.append(row)

    prompt_payload = {
        "skill_id": clean.get("id", ""),
        "skill_name": clean.get("name", ""),
        "category": clean.get("category", ""),
        "description": clean.get("description", ""),
        "connections": clean.get("connections", []),
        "steps": step_lines,
        "max_keywords": max(6, min(int(max_keywords), 20)),
        "language": lang_name,
    }
    messages = [
        {
            "role": "system",
            "content": (
                "You generate routing trigger keywords for one automation skill. "
                "Return ONLY compact JSON object: {\"keywords\": [\"...\", \"...\"]}. "
                "Keywords must be short user phrases, no explanations, no markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Generate useful trigger keywords in {lang_name}.\n"
                "Use intent phrases users would actually type.\n"
                "Avoid duplicates.\n"
                f"Input:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
            ),
        },
    ]
    candidates: list[str] = []
    try:
        response = await llm_client.chat(
            messages,
            source="skill_keywords",
            operation="generate_keywords",
            user_id="system",
        )
        candidates = extract_keyword_candidates(getattr(response, "content", ""))
    except Exception:
        candidates = []

    if not candidates:
        fallback: list[str] = []
        skill_name = str(clean.get("name", "")).strip().lower()
        if skill_name:
            fallback.append(skill_name)
            fallback.append(f"{skill_name} ausführen")
        clean_id = str(clean.get("id", "")).strip().lower()
        if clean_id:
            fallback.append(clean_id.replace("-", " "))
        desc = str(clean.get("description", "")).strip().lower()
        if desc:
            pieces = re.split(r"[,.!?:;/]", desc)
            for piece in pieces[:3]:
                if piece.strip():
                    fallback.append(piece.strip()[:80])
        candidates = normalize_keyword_list(fallback, max_items=max_keywords)
    return normalize_keyword_list(candidates, max_items=max_keywords)


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
