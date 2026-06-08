from __future__ import annotations

import re

from aria.core.capability_router import CapabilityRouter
from aria.skills.base import SkillResult


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalized_user_text(message: str) -> str:
    text = f" {str(message or '').strip().lower()} "
    return (
        text.replace(chr(228), "ae")
        .replace(chr(246), "oe")
        .replace(chr(252), "ue")
        .replace(chr(223), "ss")
    )


def looks_like_general_knowledge_or_howto_request(message: str) -> bool:
    text = _normalize_spaces(str(message or "").strip().lower())
    if not text:
        return False
    if CapabilityRouter.looks_like_general_instruction_request(text):
        return True
    patterns = (
        r"\bwelche\s+version\b",
        r"\bwelche\s+.*\b(?:aktuell|neuste|neueste|latest|current)\b",
        r"\bwas\s+ist\s+(?:die\s+)?(?:aktuelle|neuste|neueste)\b",
        r"\bwhat\s+is\s+(?:the\s+)?(?:latest|current|newest)\b",
        r"\bhow\s+(?:do|can|to)\b",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def looks_like_general_diagnostic_or_advice_request(message: str) -> bool:
    text = _normalized_user_text(message)
    if not text:
        return False
    asks_for_advice = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in (
            r"\bwas\s+mach(?:e)?\s+ich\s+damit\b",
            r"\bwas\s+soll\s+ich\s+damit\b",
            r"\bwas\s+tun\s+damit\b",
            r"\bwhat\s+do\s+i\s+do\s+with\b",
            r"\bwhat\s+should\s+i\s+do\s+with\b",
            r"\bhow\s+should\s+i\s+handle\b",
        )
    )
    if not asks_for_advice:
        return False
    diagnostic_markers = (
        " message from syslogd",
        " kernel:",
        " watchdog:",
        " soft lockup",
        " traceback",
        " exception",
        " error:",
        " fehler:",
        " stack trace",
        " segfault",
        " oom-killer",
    )
    return any(marker in text for marker in diagnostic_markers)


def explicitly_requests_local_context(message: str) -> bool:
    text = _normalize_spaces(_normalized_user_text(message))
    if not text:
        return False
    markers = (
        "in meinen notizen",
        "in meinen dokumenten",
        "aus meinen notizen",
        "aus meinen dokumenten",
        "meine notizen",
        "meine dokumente",
        "mein memory",
        "meine erinnerungen",
        "was weiss aria",
        "according to my notes",
        "from my notes",
        "in my notes",
        "in my documents",
        "my memory",
    )
    return any(marker in text for marker in markers)


def skill_result_source_types(result: SkillResult) -> set[str]:
    meta = result.metadata or {}
    rows = meta.get("sources")
    types: set[str] = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            source_type = str(row.get("type", "") or "").strip().lower()
            if source_type:
                types.add(source_type)
    if types:
        return types
    detail_lines = meta.get("detail_lines")
    if isinstance(detail_lines, list) and any("Quelle:" in str(line) for line in detail_lines):
        return {"unknown"}
    return set()


def _source_entry_is_local_memory_context(row: dict[str, object]) -> bool:
    source_type = str(row.get("type", "") or "").strip().lower()
    collection = str(row.get("collection", "") or "").strip().lower()
    if source_type in {"document", "fact", "preference", "knowledge", "session", "note"}:
        return True
    return collection.startswith(("aria_docs", "aria_facts", "aria_sessions", "aria_notes"))


def _detail_line_is_local_memory_context(line: object) -> bool:
    text = str(line or "").strip().lower()
    if not text:
        return False
    return any(
        marker in text
        for marker in (
            "aria_docs",
            "aria_facts",
            "aria_sessions",
            "notiz-kontext:",
            "quelle:",
        )
    )


def skill_result_is_local_memory_context(result: SkillResult) -> bool:
    if str(result.skill_name or "").strip() == "web_search":
        return False
    meta = result.metadata or {}
    rows = meta.get("sources")
    if isinstance(rows, list) and rows:
        local_rows = [
            row
            for row in rows
            if isinstance(row, dict) and _source_entry_is_local_memory_context(row)
        ]
        if local_rows:
            return True
    source_types = skill_result_source_types(result)
    if source_types & {"document", "fact", "preference", "knowledge", "session", "note", "unknown"}:
        return True
    detail_lines = meta.get("detail_lines")
    if isinstance(detail_lines, list) and any(_detail_line_is_local_memory_context(line) for line in detail_lines):
        return True
    return str(result.skill_name or "").strip() == "memory_recall"


def filter_chat_context_skill_results(
    skill_results: list[SkillResult],
    *,
    message: str,
    intents: list[str],
    allow_web_search_local_context: bool = True,
) -> list[SkillResult]:
    if not skill_results:
        return []
    if "web_search" in intents:
        if allow_web_search_local_context:
            return list(skill_results)
        return [result for result in skill_results if not skill_result_is_local_memory_context(result)]
    if not (
        looks_like_general_knowledge_or_howto_request(message)
        or looks_like_general_diagnostic_or_advice_request(message)
    ):
        return list(skill_results)
    if explicitly_requests_local_context(message):
        return list(skill_results)

    filtered: list[SkillResult] = []
    for result in skill_results:
        if skill_result_is_local_memory_context(result):
            continue
        filtered.append(result)
    return filtered
