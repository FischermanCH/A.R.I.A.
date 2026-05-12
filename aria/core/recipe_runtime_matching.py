from __future__ import annotations

import re
from typing import Any, Callable

from aria.core.recipe_runtime_contract import build_recipe_intent
from aria.core.text_utils import extract_json_object as core_extract_json_object

RecipeText = Callable[[str | None, str, str], str]

_SKILL_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9]+")


def recipe_tokens(value: str) -> list[str]:
    return [token for token in _SKILL_TOKEN_SPLIT_RE.split(str(value or "").lower()) if token]


def significant_recipe_tokens(value: str, *, stopwords: set[str]) -> list[str]:
    rows: list[str] = []
    for token in recipe_tokens(value):
        if len(token) < 4:
            continue
        if token in stopwords:
            continue
        if token not in rows:
            rows.append(token)
    return rows


def recipe_match_score(message: str, row: dict[str, Any], *, stopwords: set[str], action_hints: set[str]) -> int:
    lower = str(message or "").strip().lower()
    if not lower:
        return 0
    message_tokens = set(significant_recipe_tokens(lower, stopwords=stopwords))
    if not message_tokens:
        return 0

    best_score = 0
    keywords = row.get("keywords", [])
    if isinstance(keywords, list):
        for keyword in keywords:
            phrase = str(keyword or "").strip().lower()
            if not phrase:
                continue
            if phrase in lower:
                best_score = max(best_score, 120 + len(phrase))
                continue
            phrase_tokens = significant_recipe_tokens(phrase, stopwords=stopwords)
            if not phrase_tokens:
                continue
            first_token = phrase_tokens[0]
            if first_token not in message_tokens:
                continue
            overlap = sum(1 for token in phrase_tokens if token in message_tokens)
            if overlap == len(phrase_tokens) and overlap >= 2:
                best_score = max(best_score, 95 + overlap * 10 + len(phrase_tokens))
                continue
            if overlap >= 2:
                best_score = max(best_score, 55 + overlap * 12)

    name_tokens = set(significant_recipe_tokens(str(row.get("name", "")), stopwords=stopwords))
    if name_tokens:
        overlap = len(name_tokens & message_tokens)
        if overlap >= 2:
            best_score = max(best_score, 48 + overlap * 9)

    recipe_id_tokens = set(significant_recipe_tokens(str(row.get("id", "")), stopwords=stopwords))
    if recipe_id_tokens:
        overlap = len(recipe_id_tokens & message_tokens)
        if overlap >= 2:
            best_score = max(best_score, 52 + overlap * 10)

    description_tokens = set(significant_recipe_tokens(str(row.get("description", "")), stopwords=stopwords))
    if description_tokens:
        overlap = len(description_tokens & message_tokens)
        if overlap >= 3:
            best_score = max(best_score, 42 + overlap * 8)

    combined_tokens = set()
    combined_tokens.update(name_tokens)
    combined_tokens.update(recipe_id_tokens)
    combined_tokens.update(description_tokens)
    if isinstance(keywords, list):
        for keyword in keywords:
            combined_tokens.update(significant_recipe_tokens(str(keyword or ""), stopwords=stopwords))
    action_overlap = len(combined_tokens & message_tokens)
    if action_overlap >= 2 and any(token in action_hints for token in recipe_tokens(lower)):
        best_score = max(best_score, 58 + action_overlap * 7)

    connections = row.get("connections", [])
    if isinstance(connections, list):
        connection_tokens = {
            token
            for item in connections
            for token in significant_recipe_tokens(str(item), stopwords=stopwords)
        }
        overlap = len(connection_tokens & message_tokens)
        if overlap >= 1 and best_score > 0:
            best_score += 6

    return best_score


def looks_like_recipe_execution_request(message: str, *, action_hints: set[str], execution_phrases: tuple[str, ...]) -> bool:
    tokens = set(recipe_tokens(message))
    if not tokens:
        return False
    if any(token in action_hints for token in tokens):
        return True
    lower = str(message or "").strip().lower()
    return any(phrase in lower for phrase in execution_phrases)


def match_stored_recipe_intents(
    message: str,
    runtime_recipes: list[dict[str, Any]],
    *,
    stopwords: set[str],
    action_hints: set[str],
) -> list[str]:
    text = str(message or "").strip()
    if not text:
        return []
    scored: list[tuple[int, str]] = []
    for row in runtime_recipes:
        if not row.get("enabled", False):
            continue
        recipe_id = str(row.get("id", "")).strip()
        if not recipe_id:
            continue
        score = recipe_match_score(text, row, stopwords=stopwords, action_hints=action_hints)
        if score >= 55:
            scored.append((score, recipe_id))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [build_recipe_intent(recipe_id) for _, recipe_id in scored[:3]]


async def resolve_stored_recipe_intent_with_llm(
    message: str,
    runtime_recipes: list[dict[str, Any]],
    llm_client: Any | None,
    *,
    action_hints: set[str],
    execution_phrases: tuple[str, ...],
    recipe_text: RecipeText,
) -> list[str]:
    if llm_client is None:
        return []
    clean_message = str(message or "").strip()
    if not clean_message:
        return []
    if not looks_like_recipe_execution_request(
        clean_message,
        action_hints=action_hints,
        execution_phrases=execution_phrases,
    ):
        return []

    rows_for_prompt: list[str] = []
    valid_ids: set[str] = set()
    for row in runtime_recipes:
        if not bool(row.get("enabled", False)):
            continue
        recipe_id = str(row.get("id", "")).strip()
        if not recipe_id:
            continue
        valid_ids.add(recipe_id)
        keywords = row.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        connections = row.get("connections", [])
        if not isinstance(connections, list):
            connections = []
        rows_for_prompt.append(
            "\n".join(
                [
                    f"- id: {recipe_id}",
                    f"  name: {str(row.get('name', '')).strip() or recipe_id}",
                    f"  description: {str(row.get('description', '')).strip() or '-'}",
                    f"  connections: {', '.join(str(item).strip() for item in connections if str(item).strip()) or '-'}",
                    f"  keywords: {', '.join(str(item).strip() for item in keywords if str(item).strip()) or '-'}",
                ]
            )
        )
    if not valid_ids:
        return []

    system_prompt = recipe_text(
        "de",
        "select_recipe_system_prompt",
        (
            "Select exactly one suitable stored recipe for a user request. "
            "Answer only as JSON in the format "
            '{"id":"<skill-id or empty>","confidence":"high|medium|low","reason":"short"}. '
            "Only choose a recipe from the list. If nothing really matches, return an empty id. "
            "Prefer medium or high only when the request clearly asks for execution or action."
        ),
    )
    user_prompt = "\n".join(
        [
            f"Nutzeranfrage: {clean_message}",
            "",
            recipe_text("de", "select_recipe_available_recipes", "Available stored recipes:"),
            *rows_for_prompt,
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception:
        return []

    payload = core_extract_json_object(getattr(response, "content", "") or "") or {}
    recipe_id = str(payload.get("id", "")).strip()
    confidence = str(payload.get("confidence", "")).strip().lower()
    if confidence not in {"high", "medium"}:
        return []
    if recipe_id not in valid_ids:
        return []
    return [build_recipe_intent(recipe_id)]
