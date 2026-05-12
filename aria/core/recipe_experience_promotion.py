from __future__ import annotations

import hashlib
import re
from typing import Any

from aria.core.learned_recipe_store import save_learned_recipe_store_entry
from aria.core.recipe_experience_memory import normalize_recipe_experience_memory_entry
from aria.core.recipe_promotion_contract import PROMOTION_STATE_REVIEW_READY

PROMOTABLE_RECIPE_CAPABILITIES = {
    "ssh_command",
    "feed_read",
    "discord_send",
    "file_read",
    "file_write",
}

_CONTEXT_ONLY_PROMOTION_HINT = "admin:Promoted from memory into review; context only until explicitly stored as a recipe."
_WEB_SEARCH_PROMOTION_HINT = "admin:Promoted from web/search result into review; context only and not directly executable."


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _slugify(value: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower())).strip("-")


def _stable_suffix(value: str) -> str:
    return hashlib.sha1(str(value or "").encode("utf-8")).hexdigest()[:10]


def _clean_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def is_stored_recipe_promotable_capability(capability: str) -> bool:
    return str(capability or "").strip().lower() in PROMOTABLE_RECIPE_CAPABILITIES


def _review_recipe_id(prefix: str, source: dict[str, Any]) -> str:
    explicit = _clean_text(source.get("recipe_id"))
    if explicit:
        return explicit
    fingerprint = _clean_text(source.get("experience_fingerprint")) or "|".join(
        _clean_text(source.get(key))
        for key in ("connection_kind", "connection_ref", "capability", "intent", "chosen_action")
    )
    stem = _slugify("-".join(_clean_text(source.get(key)) for key in ("connection_kind", "intent", "capability") if _clean_text(source.get(key))))
    return f"learned-{prefix}-{stem or 'context'}-{_stable_suffix(fingerprint)}"


def build_learned_recipe_review_entry_from_experience(source: dict[str, Any] | None) -> dict[str, Any]:
    entry = normalize_recipe_experience_memory_entry(source or {})
    recipe_id = _review_recipe_id("experience", entry)
    inputs = _clean_dict(entry.get("inputs"))
    if entry.get("chosen_action"):
        inputs.setdefault("observed_action", str(entry.get("chosen_action") or ""))
    if entry.get("learned_from_action"):
        inputs.setdefault("learned_from_action", str(entry.get("learned_from_action") or ""))
    experience_count = max(int(entry.get("experience_count", 0) or 0), 1)
    return {
        "recipe_id": recipe_id,
        "title": _clean_text(entry.get("title")) or _clean_text(entry.get("intent")) or "Reviewed experience",
        "summary": _clean_text(entry.get("experience_summary")) or _clean_text(entry.get("summary")),
        "preview": _clean_text(entry.get("chosen_action")) or _clean_text(entry.get("learned_from_action")),
        "inputs": inputs,
        "router_keywords": list(entry.get("router_keywords", []) or []),
        "recipe_scope": {
            "connection_kinds": [entry["connection_kind"]] if entry.get("connection_kind") else [],
            "connection_refs": [entry["connection_ref"]] if entry.get("connection_ref") else [],
            "learning_origin": _clean_text(entry.get("learning_origin")) or "memory_review",
        },
        "intent": _clean_text(entry.get("intent")),
        "connection_kind": _clean_text(entry.get("connection_kind")),
        "connection_ref": _clean_text(entry.get("connection_ref")),
        "capability": _clean_text(entry.get("capability")),
        "chosen_action": _clean_text(entry.get("chosen_action")) or _clean_text(entry.get("learned_from_action")),
        "policy_result": "context_only",
        "execution_result": "review",
        "user_feedback": "",
        "user_message": _clean_text(entry.get("user_message")),
        "experience_summary": _clean_text(entry.get("experience_summary")) or _clean_text(entry.get("summary")),
        "experience_count": experience_count,
        "last_success_at": _clean_text(entry.get("last_success_at")),
        "promotion_state": PROMOTION_STATE_REVIEW_READY,
        "promotion_hint": _CONTEXT_ONLY_PROMOTION_HINT,
    }


def build_learned_recipe_review_entry_from_web_search_result(
    *,
    query: str = "",
    title: str = "",
    url: str = "",
    snippet: str = "",
    source_ref: str = "web_search",
) -> dict[str, Any]:
    clean_query = _clean_text(query)
    clean_title = _clean_text(title) or clean_query or "Web/search context"
    clean_url = _clean_text(url)
    clean_snippet = _clean_text(snippet)
    recipe_id = f"learned-web-search-{_slugify(clean_title or clean_query or 'context')}-{_stable_suffix(clean_url or clean_snippet or clean_query)}"
    return {
        "recipe_id": recipe_id,
        "title": clean_title,
        "summary": clean_snippet,
        "preview": clean_url or clean_snippet,
        "inputs": {
            "query": clean_query,
            "source_url": clean_url,
            "source_title": clean_title,
        },
        "router_keywords": [value for value in (clean_query, clean_title) if value],
        "recipe_scope": {
            "connection_kinds": ["web"],
            "connection_refs": [source_ref] if source_ref else [],
            "learning_origin": "web_search_review",
        },
        "intent": "research_context",
        "connection_kind": "web",
        "connection_ref": source_ref,
        "capability": "web_search",
        "chosen_action": clean_query or clean_url,
        "policy_result": "context_only",
        "execution_result": "review",
        "user_feedback": "",
        "user_message": clean_query,
        "experience_summary": clean_snippet,
        "experience_count": 1,
        "promotion_state": PROMOTION_STATE_REVIEW_READY,
        "promotion_hint": _WEB_SEARCH_PROMOTION_HINT,
    }


def promote_recipe_experience_to_learned_review(source: dict[str, Any] | None) -> dict[str, Any]:
    return save_learned_recipe_store_entry(build_learned_recipe_review_entry_from_experience(source))


def promote_web_search_result_to_learned_review(**kwargs: Any) -> dict[str, Any]:
    return save_learned_recipe_store_entry(build_learned_recipe_review_entry_from_web_search_result(**kwargs))
