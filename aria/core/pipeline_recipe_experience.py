from __future__ import annotations

from typing import Any, Awaitable, Callable

from aria.core.recipe_experience_memory import search_recipe_experience_memory

RecipeExperienceSearch = Callable[..., Awaitable[list[dict[str, Any]]]]


async def recipe_experience_context_rows(
    memory_skill: Any,
    *,
    user_id: str,
    message: str,
    connection_kind: str = "",
    connection_ref: str = "",
    capability: str = "",
    intent: str = "",
    top_k: int = 3,
    search: RecipeExperienceSearch = search_recipe_experience_memory,
) -> list[dict[str, Any]]:
    if memory_skill is None:
        return []
    try:
        return await search(
            memory_skill,
            user_id=user_id,
            query=message,
            connection_kind=connection_kind,
            connection_ref=connection_ref,
            capability=capability,
            intent=intent,
            top_k=top_k,
        )
    except Exception:
        return []


async def recipe_experience_context(
    memory_skill: Any,
    *,
    user_id: str,
    message: str,
    connection_kind: str = "",
    connection_ref: str = "",
    capability: str = "",
    intent: str = "",
    top_k: int = 3,
    search: RecipeExperienceSearch = search_recipe_experience_memory,
) -> dict[str, str]:
    rows = await recipe_experience_context_rows(
        memory_skill,
        user_id=user_id,
        message=message,
        connection_kind=connection_kind,
        connection_ref=connection_ref,
        capability=capability,
        intent=intent,
        top_k=top_k,
        search=search,
    )
    return format_recipe_experience_context(rows)


def format_recipe_experience_context(rows: list[dict[str, Any]]) -> dict[str, str]:
    if not rows:
        return {}
    formatted: list[str] = []
    for row in rows[:3]:
        title = str(row.get("title", "") or row.get("recipe_id", "") or "").strip()
        user_message = str(row.get("user_message", "") or "").strip()
        action = str(row.get("chosen_action", "") or "").strip()
        count = int(row.get("experience_count", 0) or 0)
        origin = str(row.get("learning_origin", "") or "").strip()
        target_fingerprint = str(row.get("target_fingerprint", "") or "").strip()
        action_fingerprint = str(row.get("action_fingerprint", "") or "").strip()
        target = "/".join(
            part
            for part in (
                str(row.get("connection_kind", "") or "").strip(),
                str(row.get("connection_ref", "") or "").strip(),
            )
            if part
        )
        parts = [title]
        if target:
            parts.append(f"target={target}")
        if user_message:
            parts.append(f"user_said={user_message}")
        if action:
            parts.append(f"worked_action={action}")
        if count:
            parts.append(f"successes={count}")
        if origin:
            parts.append(f"origin={origin}")
        if target_fingerprint:
            parts.append(f"target_fp={target_fingerprint}")
        if action_fingerprint:
            parts.append(f"action_fp={action_fingerprint}")
        formatted.append(" | ".join(parts))
    if not formatted:
        return {}
    return {
        "recipe_experience": " ; ".join(formatted),
        "recipe_experience_policy": "Context only: do not execute learned experience directly; still choose a bounded candidate and run normal guardrails.",
    }


def recipe_experience_debug_lines(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    lines = [
        "Planner: recipe_experience_context policy=context_only executor=bounded_candidate_guardrails"
    ]
    for row in rows[:3]:
        recipe_id = str(row.get("recipe_id", "") or "").strip()
        title = str(row.get("title", "") or "").strip()
        target = "/".join(
            part
            for part in (
                str(row.get("connection_kind", "") or "").strip(),
                str(row.get("connection_ref", "") or "").strip(),
            )
            if part
        )
        score = float(row.get("score", 0.0) or 0.0)
        semantic_score = float(row.get("semantic_score", score) or score)
        count = int(row.get("experience_count", 0) or 0)
        action = str(row.get("chosen_action", "") or "").strip()
        origin = str(row.get("learning_origin", "") or "").strip()
        label = recipe_id or title or "unknown"
        line = f"Planner: recipe_experience hit `{label}` score={score:.3f} semantic={semantic_score:.3f}"
        if target:
            line += f" target={target}"
        if count:
            line += f" successes={count}"
        if origin:
            line += f" origin={origin}"
        if action:
            line += f" worked_action={action}"
        lines.append(line)
    return lines
