from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any


LLM_INPUT_CONTRACT_VERSION = "llm_input_v1"
_PRIVATE_EXACT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "base_url",
    "client_secret",
    "credential",
    "credentials",
    "executor_contract",
    "feed_url",
    "host",
    "loader_contract",
    "metadata",
    "password",
    "private_key",
    "secret",
    "secret_key",
    "secrets",
    "token",
    "url",
    "user",
    "username",
}
_PRIVATE_KEY_SUFFIXES = (
    "_api_key",
    "_authorization",
    "_client_secret",
    "_credential",
    "_credentials",
    "_password",
    "_private_key",
    "_refresh_token",
    "_secret",
    "_secret_key",
    "_secrets",
    "_token",
)


def _clean_text(value: Any, *, limit: int = 1000) -> str:
    return " ".join(str(value or "").strip().split())[: max(1, int(limit or 1))]


def _clean_scalar(value: Any, *, limit: int = 240) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int | float):
        return value
    return _clean_text(value, limit=limit)


def _normalized_key(value: str) -> str:
    clean = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value or "")).lower()
    clean = re.sub(r"[^a-z0-9]+", "_", clean).strip("_")
    return clean


def _allow_key_in_path(key: str, path: tuple[str, ...]) -> bool:
    if _normalized_key(key) != "host":
        return False
    normalized_path = tuple(_normalized_key(item) for item in path)
    return (
        "answer_request" in normalized_path
        and "outcome" in normalized_path
        and "sources" in normalized_path
        and "items" in normalized_path
    )


def _private_meta_key(key: str, path: tuple[str, ...]) -> bool:
    clean = _normalized_key(key)
    if not clean or _allow_key_in_path(clean, path):
        return False
    if clean in _PRIVATE_EXACT_KEYS:
        return True
    if clean.replace("_", "") == "apikey":
        return True
    return any(clean.endswith(suffix) for suffix in _PRIVATE_KEY_SUFFIXES)


def _clean_json(value: Any, *, depth: int = 5, item_limit: int = 40, path: tuple[str, ...] = ()) -> Any:
    if depth <= 0:
        return _clean_scalar(value)
    if isinstance(value, dict):
        rows: dict[str, Any] = {}
        for raw_key, raw_item in list(value.items())[: max(1, int(item_limit or 1))]:
            key = _clean_text(raw_key, limit=120)
            if not key:
                continue
            if _private_meta_key(key, path):
                continue
            rows[key] = _clean_json(raw_item, depth=depth - 1, item_limit=item_limit, path=(*path, key))
        return rows
    if isinstance(value, (list, tuple, set)):
        return [
            _clean_json(item, depth=depth - 1, item_limit=item_limit, path=path)
            for item in list(value)[: max(1, int(item_limit or 1))]
        ]
    return _clean_scalar(value)


def _current_date() -> str:
    return datetime.now(UTC).date().isoformat()


def _row_ids(rows: Any, *keys: str) -> list[str]:
    ids: list[str] = []
    for row in list(rows or []):
        if not isinstance(row, dict):
            continue
        for key in keys:
            value = _clean_text(row.get(key), limit=160)
            if value and value not in ids:
                ids.append(value)
                break
    return ids


def _web_search_profile_refs(world_map: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for row in list(world_map.get("web_search_profiles") or []):
        if not isinstance(row, dict):
            continue
        ref = _clean_text(row.get("ref") or row.get("id") or row.get("name"), limit=160)
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def build_llm_input_contract(
    *,
    message: str,
    language: str | None = None,
    user_id: str = "",
    decision_task: str = "select_relevant_context_or_action",
    routing_meta_context: dict[str, Any] | None = None,
    surface_meta_context: dict[str, Any] | None = None,
    world_map_extensions: dict[str, Any] | None = None,
    last_turn_frame: dict[str, Any] | None = None,
    recent_visible_chat_context: dict[str, Any] | None = None,
    current_date: str | None = None,
) -> dict[str, Any]:
    routing_meta = _clean_json(routing_meta_context or {}, depth=5)
    surface_meta = _clean_json(surface_meta_context or {}, depth=5)
    extensions = _clean_json(world_map_extensions or {}, depth=8)
    surfaces = list(surface_meta.get("surfaces") or []) if isinstance(surface_meta, dict) else []
    collections = list(routing_meta.get("collections") or []) if isinstance(routing_meta, dict) else []
    actions = list(routing_meta.get("actions") or []) if isinstance(routing_meta, dict) else []
    world_map = {
        "surfaces": surfaces,
        "collections": collections,
        "actions": actions,
        "routing_meta": routing_meta,
        "surface_meta": surface_meta,
    }
    if isinstance(extensions, dict):
        for key, value in extensions.items():
            if key not in world_map:
                world_map[key] = value
    allowed_surface_ids = _row_ids(surfaces, "id", "surface_id", "name")
    allowed_collection_names = _row_ids(collections, "name", "id")
    allowed_action_names = _row_ids(actions, "name", "id")
    allowed_catalog_ids = _row_ids(world_map.get("meta_catalog"), "catalog_id", "id")
    allowed_web_search_profile_refs = _web_search_profile_refs(world_map)
    return {
        "contract_version": LLM_INPUT_CONTRACT_VERSION,
        "canonical_input": True,
        "decision_task": _clean_text(decision_task, limit=120) or "select_relevant_context_or_action",
        "runtime": {
            "current_date": _clean_text(current_date or _current_date(), limit=40),
            "language": _clean_text(language, limit=24),
            "user_id": _clean_text(user_id, limit=160),
        },
        "user_prompt": _clean_text(message, limit=1200),
        "world_map": world_map,
        "conversation_context": {
            "last_turn_frame": _clean_json(last_turn_frame or {}, depth=4),
            "recent_visible_chat_context": _clean_json(recent_visible_chat_context or {}, depth=4),
        },
        "global_rules": {
            "llm_selects_context": True,
            "normalizer_is_not_router": True,
            "top_level_payload_fields_are_legacy_mirrors": False,
            "top_level_payload_fields_removed": True,
            "source_bound_for_fresh_facts": True,
            "fail_closed_if_evidence_insufficient": True,
            "deterministic_logic_only": [
                "safety",
                "guardrails",
                "runtime",
                "validation",
                "normalization",
                "structured_contracts",
                "fallback",
                "observability",
            ],
        },
        "requested_output_schema": {
            "output_must_be_json_object": True,
            "select_only_from_world_map": True,
            "allowed_surface_ids": allowed_surface_ids,
            "allowed_collection_names": allowed_collection_names,
            "allowed_action_names": allowed_action_names,
            "allowed_catalog_ids": allowed_catalog_ids,
            "allowed_web_search_profile_refs": allowed_web_search_profile_refs,
            "allowed_context_request_modes": ["inventory", "exists", "search", "answer", "summarize", "action", "clarify", "block"],
            "web_source_plan": {
                "search_profile_ref": "optional; choose only one allowed_web_search_profile_refs value when a web profile clearly fits",
            },
            "needed_context": [
                {
                    "surface_id": "registered surface id",
                    "mode": "inventory|exists|search|summarize|action|clarify|block",
                    "query": "concise context query",
                    "why": "short reason",
                }
            ],
            "answer_policy": {
                "answer_mode": "direct_answer|answer_from_context|answer_with_source_grouping|summarize_sources|ask_clarification|blocked",
                "evidence_policy": "source_bound|allow_general",
            },
            "action_policy": {
                "risk": "none|low|medium|high",
                "needs_confirmation": "boolean",
            },
        },
    }


def llm_input_contract_diagnostics(contract: dict[str, Any]) -> dict[str, int]:
    world_map = contract.get("world_map") if isinstance(contract, dict) else {}
    if not isinstance(world_map, dict):
        world_map = {}
    return {
        "llm_input_contract_v1": 1 if contract.get("contract_version") == LLM_INPUT_CONTRACT_VERSION else 0,
        "llm_input_world_surfaces": len(world_map.get("surfaces") or []),
        "llm_input_world_collections": len(world_map.get("collections") or []),
        "llm_input_world_actions": len(world_map.get("actions") or []),
        "llm_input_world_meta_catalog": len(world_map.get("meta_catalog") or []),
    }
