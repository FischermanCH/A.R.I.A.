from __future__ import annotations

from datetime import UTC, datetime
import json
import re
from typing import Any

from aria.modules.llm_input_contract.decision_schema import TURN_DECISION_OUTPUT_PROFILE
from aria.modules.llm_input_contract.decision_schema import turn_decision_output_schema


LLM_INPUT_CONTRACT_VERSION = "llm_input_v1"
TURN_ROUTER_OUTPUT_PROFILE = TURN_DECISION_OUTPUT_PROFILE
ANSWER_COMPOSER_OUTPUT_PROFILE = "aria_answer_composer_output_v1"
ROUTER_WORLD_ROWS_PROFILE = "world_rows_v1"
_ROUTER_WORLD_ROW_FIELDS = {
    "surfaces": ("id", "type", "modes", "risk", "knows", "routing", "catalog_id", "score"),
    "connection_kind_options": ("id", "label", "configured_count", "capabilities"),
    "configured_connections": ("catalog_id", "kind", "ref"),
    "actions": ("name", "kind", "risk", "requires_confirmation", "input_schema"),
    "meta_catalog": (
        "catalog_id",
        "entity_type",
        "surface_id",
        "kind",
        "ref",
        "title",
        "aliases",
        "tags",
        "document_id",
        "document_name",
        "target_collection",
        "group_name",
        "description",
        "score",
    ),
}
_PERSONAL_CLAIM_ROW_FIELDS = (
    "claim_id",
    "claim_kind",
    "subject",
    "predicate",
    "value",
    "scope",
    "scope_ref",
    "authority",
    "valid_from",
    "valid_until",
    "review_after",
)
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


def _compact_router_surface_rows(rows: Any) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for raw_row in list(rows or []):
        if not isinstance(raw_row, dict):
            continue
        row = {
            key: raw_row.get(key)
            for key in ("id", "type", "modes", "risk", "knows", "routing", "catalog_id", "score")
            if raw_row.get(key) not in (None, "", [], {})
        }
        if row:
            compact.append(row)
    return compact


def _compact_world_rows(rows: Any, *, fields: tuple[str, ...]) -> dict[str, Any]:
    encoded_rows: list[list[Any]] = []
    used_fields = tuple(
        field
        for field in fields
        if any(isinstance(row, dict) and row.get(field) not in (None, "", [], {}) for row in list(rows or []))
    )
    for raw_row in list(rows or []):
        if not isinstance(raw_row, dict):
            continue
        row = [raw_row.get(field) if raw_row.get(field) not in ("", [], {}) else None for field in used_fields]
        while row and row[-1] is None:
            row.pop()
        encoded_rows.append(row)
    return {
        "fields": list(used_fields),
        "rows": encoded_rows,
    }


def _world_row_count(value: Any) -> int:
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return len(value["rows"])
    return len(value or []) if isinstance(value, list) else 0


def _reviewed_learning_hints(rows: Any) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in list(rows or [])[:3]:
        if not isinstance(row, dict):
            continue
        hint_id = _clean_text(row.get("hint_id") or row.get("point_id") or row.get("id"), limit=180)
        text = _clean_text(row.get("text"), limit=700)
        if not hint_id or not text or hint_id in seen:
            continue
        seen.add(hint_id)
        hints.append(
            {
                "hint_id": hint_id,
                "text": text,
                "runtime_effect": "weak_signal_only",
                "version": max(1, int(row.get("version", 1) or 1)),
                "relevance_score": max(0.0, min(1.0, float(row.get("relevance_score", 0.0) or 0.0))),
                "source_candidate_id": _clean_text(row.get("source_candidate_id"), limit=180),
            }
        )
    return hints


def validated_used_learning_hint_ids(payload: dict[str, Any], reviewed_hints: Any) -> tuple[str, ...]:
    allowed = {
        str(row.get("hint_id", "") or "").strip()
        for row in _reviewed_learning_hints(reviewed_hints)
        if str(row.get("hint_id", "") or "").strip()
    }
    raw = payload.get("used_learning_hint_ids")
    values = [raw] if isinstance(raw, str) else list(raw or []) if isinstance(raw, (list, tuple, set)) else []
    used: list[str] = []
    for value in values:
        clean = _clean_text(value, limit=180)
        if clean in allowed and clean not in used:
            used.append(clean)
    return tuple(used)


def _personal_context_capsule(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in list(value.get("claims") or [])[:24]:
        if not isinstance(row, dict):
            continue
        claim_id = _clean_text(row.get("claim_id"), limit=180)
        if not claim_id or claim_id in seen:
            continue
        seen.add(claim_id)
        claims.append(
            {
                key: _clean_json(row.get(key), depth=3)
                for key in (
                    "claim_id",
                    "claim_kind",
                    "subject",
                    "predicate",
                    "value",
                    "scope",
                    "scope_ref",
                    "authority",
                    "valid_from",
                    "valid_until",
                    "review_after",
                )
                if row.get(key) not in (None, "")
            }
        )
    coverage = _clean_text(value.get("coverage"), limit=40)
    if coverage not in {"complete_active_set", "relevance_selected"}:
        coverage = "relevance_selected"
    return {
        "contract": _clean_text(value.get("contract"), limit=80) or "personal_context_capsule_v1",
        "authority_policy": _clean_text(value.get("authority_policy"), limit=900),
        "coverage": coverage,
        "active_claim_count": max(0, int(value.get("active_claim_count", len(claims)) or 0)),
        "provided_claim_count": len(claims),
        "claims": claims,
    }


def _compact_router_personal_context(value: dict[str, Any]) -> dict[str, Any]:
    claims = list(value.get("claims") or [])
    return {
        key: item
        for key, item in {
            "contract": value.get("contract"),
            "coverage": value.get("coverage"),
            "active_claim_count": value.get("active_claim_count"),
            "provided_claim_count": value.get("provided_claim_count"),
            "claims": _compact_world_rows(claims, fields=_PERSONAL_CLAIM_ROW_FIELDS) if claims else [],
        }.items()
        if item not in (None, "")
    }


def validated_selected_personal_claim_ids(payload: dict[str, Any], capsule: Any) -> tuple[str, ...]:
    allowed = {
        str(row.get("claim_id") or "").strip()
        for row in list(_personal_context_capsule(capsule).get("claims") or [])
        if str(row.get("claim_id") or "").strip()
    }
    raw = payload.get("selected_personal_claim_ids")
    values = [raw] if isinstance(raw, str) else list(raw or []) if isinstance(raw, (list, tuple, set)) else []
    selected: list[str] = []
    for value in values:
        clean = _clean_text(value, limit=180)
        if clean in allowed and clean not in selected:
            selected.append(clean)
    return tuple(selected)


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
    reviewed_learning_hints: list[dict[str, Any]] | None = None,
    personal_context_capsule: dict[str, Any] | None = None,
    current_date: str | None = None,
    deduplicate_world_map: bool = False,
    output_profile: str = "",
    requested_output_schema_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    compact_router_output = str(output_profile or "").strip() == TURN_ROUTER_OUTPUT_PROFILE
    compact_answer_output = str(output_profile or "").strip() == ANSWER_COMPOSER_OUTPUT_PROFILE
    routing_meta = _clean_json(routing_meta_context or {}, depth=5)
    surface_meta = _clean_json(surface_meta_context or {}, depth=5)
    raw_extensions = world_map_extensions or {}
    extensions = _clean_json(raw_extensions, depth=8)
    if isinstance(raw_extensions, dict) and isinstance(raw_extensions.get("configured_connections"), list):
        extensions["configured_connections"] = _clean_json(
            raw_extensions["configured_connections"],
            depth=3,
            item_limit=200,
        )
    surfaces = list(surface_meta.get("surfaces") or []) if isinstance(surface_meta, dict) else []
    if compact_router_output:
        surfaces = _compact_router_surface_rows(surfaces)
    collections = list(routing_meta.get("collections") or []) if isinstance(routing_meta, dict) else []
    actions = list(routing_meta.get("actions") or []) if isinstance(routing_meta, dict) else []
    connection_kind_options: list[dict[str, Any]] = []
    if compact_router_output and isinstance(routing_meta, dict):
        connection_kind_options = [
            {
                key: row.get(key)
                for key in ("id", "label", "configured_count", "capabilities")
                if row.get(key) not in (None, "", [], {})
            }
            for row in list(routing_meta.get("connection_kind_options") or [])
            if isinstance(row, dict) and str(row.get("id") or "").strip()
        ]
    routing_meta_world = routing_meta
    surface_meta_world = surface_meta
    if deduplicate_world_map:
        routing_meta_world = {
            key: value
            for key, value in routing_meta.items()
            if key not in {"surfaces", "collections", "actions", "connection_kind_options"}
        }
        surface_meta_world = {
            key: value
            for key, value in surface_meta.items()
            if key != "surfaces"
        }
        if compact_router_output:
            # Registered surface rows and the router's global/schema contracts
            # already carry this authority. Repeating the adapter contract on
            # every turn adds transport without adding a selectable fact.
            surface_meta_world = {}
    world_map: dict[str, Any] = {}
    if surfaces:
        world_map["surfaces"] = surfaces
    if collections and not compact_router_output:
        world_map["collections"] = collections
    if routing_meta_world:
        world_map["routing_meta"] = routing_meta_world
    if connection_kind_options:
        world_map["connection_kind_options"] = connection_kind_options
    if surface_meta_world:
        world_map["surface_meta"] = surface_meta_world
    if compact_router_output and isinstance(extensions, dict) and extensions.get("routing_contract"):
        world_map["routing_contract"] = extensions["routing_contract"]
    if actions:
        world_map["actions"] = actions
    if isinstance(extensions, dict):
        for key, value in extensions.items():
            if key not in world_map:
                world_map[key] = value
    allowed_surface_ids = _row_ids(surfaces, "id", "surface_id", "name")
    allowed_collection_names = _row_ids(collections, "name", "id")
    allowed_action_names = _row_ids(actions, "name", "id")
    allowed_catalog_ids = _row_ids(world_map.get("meta_catalog"), "catalog_id", "id")
    for catalog_id in _row_ids(surfaces, "catalog_id"):
        if catalog_id not in allowed_catalog_ids:
            allowed_catalog_ids.append(catalog_id)
    allowed_web_search_profile_refs = _web_search_profile_refs(world_map)
    learning_hints = _reviewed_learning_hints(reviewed_learning_hints)
    allowed_learning_hint_ids = [str(row["hint_id"]) for row in learning_hints]
    personal_context = _personal_context_capsule(personal_context_capsule)
    allowed_personal_claim_ids = [
        str(row.get("claim_id") or "")
        for row in list(personal_context.get("claims") or [])
        if str(row.get("claim_id") or "")
    ]
    if compact_router_output and personal_context:
        personal_context = _compact_router_personal_context(personal_context)
    if compact_router_output:
        for key, fields in _ROUTER_WORLD_ROW_FIELDS.items():
            rows = world_map.get(key)
            if isinstance(rows, list) and rows:
                world_map[key] = _compact_world_rows(rows, fields=fields)
    global_rules: dict[str, Any]
    requested_output_schema: dict[str, Any]
    if compact_answer_output:
        global_rules = {
            "profile": "source_bound_answer_v1",
            "evidence_authority": "answer_request",
            "fail_closed_if_evidence_insufficient": True,
        }
        requested_output_schema = {
            "profile": ANSWER_COMPOSER_OUTPUT_PROFILE,
            "format": "plain_text",
            "content": "final user-facing answer only",
        }
    elif compact_router_output:
        global_rules = {
            "profile": "llm_first_guarded_v1",
            "world_map_rows": ROUTER_WORLD_ROWS_PROFILE,
            "turn_semantics_authority": "turn_semantics_v1",
            "learning_directive_authority": "derived_from_turn_semantics",
            "learning_hints_authority": "weak_signal_only",
        }
        requested_output_schema = turn_decision_output_schema()
    else:
        global_rules = {
            "llm_selects_context": True,
            "normalizer_is_not_router": True,
            "top_level_payload_fields_are_legacy_mirrors": False,
            "top_level_payload_fields_removed": True,
            "source_bound_for_fresh_facts": True,
            "fail_closed_if_evidence_insufficient": True,
            "learning_hints_are_weak_signals_only": True,
            "learning_hints_cannot_override_safety_config_explicit_targets_or_evidence": True,
            "non_semantic_runtime_authority_only": [
                "safety",
                "guardrails",
                "runtime",
                "validation",
                "normalization",
                "structured_contracts",
                "fail_closed_fallback",
                "observability",
            ],
        }
        requested_output_schema = {
            "output_must_be_json_object": True,
            "select_only_from_world_map": True,
            "allowed_surface_ids": allowed_surface_ids,
            "allowed_collection_names": allowed_collection_names,
            "allowed_action_names": allowed_action_names,
            "allowed_catalog_ids": allowed_catalog_ids,
            "allowed_web_search_profile_refs": allowed_web_search_profile_refs,
            "allowed_learning_hint_ids": allowed_learning_hint_ids,
            "used_learning_hint_ids": "optional list; only IDs actually used from allowed_learning_hint_ids",
            "allowed_personal_claim_ids": allowed_personal_claim_ids,
            "selected_personal_claim_ids": "optional list; only IDs selected from allowed_personal_claim_ids",
            "turn_semantics": {
                "contract": "turn_semantics_v1",
                "primary": (
                    "exactly one of ordinary|explicit_personal_memory|behavior_feedback|personal_observation|"
                    "entity_alias_candidate|procedure_or_recipe_candidate|runtime_outcome_review"
                ),
                "confidence": "0..1",
                "reason": "short semantic reason",
                "authority": (
                    "This is the single semantic authority for personal-memory capture and learning. "
                    "personal_memory_capture is valid only with explicit_personal_memory; learning lanes "
                    "are derived from the corresponding learning primary."
                ),
            },
            "learning_directive": {
                "mode": "none|capture",
                "lanes": {
                    "personal_observation": "durable personal fact or preference not already handled by personal_memory_capture",
                    "behavior_feedback": "evaluation, praise, correction, rejection, or instruction about ARIA's previous answer or behavior",
                    "entity_alias_candidate": "explicitly confirmed alias evidence",
                    "procedure_or_recipe_candidate": "durable procedure or recipe learning",
                    "runtime_outcome_review": "runtime outcome worth later review",
                },
                "confidence": "0..1",
                "reason": "short reason",
                "consistency": (
                    "Mirror turn_semantics for observability. Runtime authority is turn_semantics, "
                    "not this independently returned field. Evaluation of ARIA or its immediately "
                    "previous answer must use behavior_feedback semantics."
                ),
            },
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
            "action_inputs": (
                "When an action has input_schema, return an object keyed by the selected action name and fill that schema "
                "during the same semantic decision. Do not invent inputs or select a write action without valid inputs."
            ),
        }
    if requested_output_schema_override is not None:
        requested_output_schema = _clean_json(requested_output_schema_override, depth=8)
    if compact_router_output and connection_kind_options:
        id_sources = requested_output_schema.get("id_sources")
        if isinstance(id_sources, dict):
            id_sources["connection_kinds"] = "connection_kind_options[id]"
    contract: dict[str, Any] = {
        "contract_version": LLM_INPUT_CONTRACT_VERSION,
        "canonical_input": True,
        "decision_task": _clean_text(decision_task, limit=120) or "select_relevant_context_or_action",
    }
    if compact_router_output:
        # Keep the stable registered world prefix ahead of per-turn text so compatible
        # providers can reuse it without changing ARIA's semantic authority.
        contract["global_rules"] = global_rules
        contract["world_map"] = world_map
        contract["requested_output_schema"] = requested_output_schema
    else:
        contract.update(
            {
                "runtime": {
                    "current_date": _clean_text(current_date or _current_date(), limit=40),
                    "language": _clean_text(language, limit=24),
                    "user_id": _clean_text(user_id, limit=160),
                },
                "user_prompt": _clean_text(message, limit=1200),
                "world_map": world_map,
                "global_rules": global_rules,
                "requested_output_schema": requested_output_schema,
            }
        )
    conversation_context = {
        "last_turn_frame": _clean_json(last_turn_frame or {}, depth=4),
        "recent_visible_chat_context": _clean_json(recent_visible_chat_context or {}, depth=4),
    }
    if any(conversation_context.values()) or not (compact_router_output or compact_answer_output):
        contract["conversation_context"] = conversation_context
    if learning_hints or not (compact_router_output or compact_answer_output):
        contract["reviewed_learning_hints"] = learning_hints
    if personal_context or not (compact_router_output or compact_answer_output):
        contract["personal_context_capsule"] = personal_context
    if compact_router_output:
        # The current turn is the final authority-bearing input after older state.
        contract["runtime"] = {
            "current_date": _clean_text(current_date or _current_date(), limit=40),
            "language": _clean_text(language, limit=24),
            "user_id": _clean_text(user_id, limit=160),
        }
        contract["user_prompt"] = _clean_text(message, limit=1200)
    return contract


def llm_input_contract_diagnostics(contract: dict[str, Any]) -> dict[str, int]:
    world_map = contract.get("world_map") if isinstance(contract, dict) else {}
    if not isinstance(world_map, dict):
        world_map = {}
    def _encoded_size(value: Any) -> int:
        try:
            return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        except Exception:
            return 0

    return {
        "llm_input_contract_v1": 1 if contract.get("contract_version") == LLM_INPUT_CONTRACT_VERSION else 0,
        "llm_input_world_surfaces": _world_row_count(world_map.get("surfaces")),
        "llm_input_world_collections": _world_row_count(world_map.get("collections")),
        "llm_input_world_actions": _world_row_count(world_map.get("actions")),
        "llm_input_world_meta_catalog": _world_row_count(world_map.get("meta_catalog")),
        "llm_input_contract_bytes": _encoded_size(contract),
        "llm_input_world_map_bytes": _encoded_size(world_map),
        "llm_input_output_schema_bytes": _encoded_size(contract.get("requested_output_schema") or {}),
        "llm_input_world_surfaces_bytes": _encoded_size(world_map.get("surfaces") or {}),
        "llm_input_connection_kind_options_bytes": _encoded_size(world_map.get("connection_kind_options") or {}),
        "llm_input_world_actions_bytes": _encoded_size(world_map.get("actions") or {}),
        "llm_input_world_meta_catalog_bytes": _encoded_size(world_map.get("meta_catalog") or {}),
        "llm_input_conversation_bytes": _encoded_size(contract.get("conversation_context") or {}),
        "llm_input_personal_context_bytes": _encoded_size(contract.get("personal_context_capsule") or {}),
        "llm_input_learning_hints_bytes": _encoded_size(contract.get("reviewed_learning_hints") or []),
    }
