from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5
import re

from qdrant_client.models import FieldCondition, Filter, MatchValue, PointIdsList, PointStruct

from aria.core.qdrant_collection_classifier import RECIPE_EXPERIENCE_PREFIX

RECIPE_EXPERIENCE_COLLECTION_PREFIX = RECIPE_EXPERIENCE_PREFIX
RECIPE_EXPERIENCE_SOURCE = "recipe_experience"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_lower(value: Any) -> str:
    return _clean_text(value).lower()


def _fingerprint(*parts: Any) -> str:
    raw = "|".join(_clean_lower(part) for part in parts if _clean_text(part))
    raw = re.sub(r"[^a-z0-9|._:/-]+", "-", raw)
    raw = re.sub(r"-+", "-", raw).strip("-|")
    return raw[:180]


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id or "").strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "web"


def recipe_experience_collection_for_user(user_id: str) -> str:
    return f"{RECIPE_EXPERIENCE_COLLECTION_PREFIX}_{_slug_user_id(user_id)}"


def normalize_recipe_experience_memory_entry(entry: dict[str, Any]) -> dict[str, Any]:
    inputs = dict(entry.get("inputs", {}) or {})
    scope = dict(entry.get("recipe_scope", {}) or {})
    router_keywords = [
        _clean_text(item)
        for item in list(entry.get("router_keywords", []) or [])
        if _clean_text(item)
    ][:20]
    connection_kind = _clean_lower(entry.get("connection_kind"))
    connection_ref = _clean_text(entry.get("connection_ref"))
    capability = _clean_lower(entry.get("capability"))
    intent = _clean_lower(entry.get("intent"))
    chosen_action = _clean_text(entry.get("chosen_action"))
    learned_from_action = _clean_text(inputs.get("learned_from_command") or inputs.get("learned_from_action"))
    learning_origin = _clean_text(scope.get("learning_origin") or entry.get("learning_origin"))
    normalized = {
        **dict(entry or {}),
        "recipe_id": _clean_text(entry.get("recipe_id")),
        "title": _clean_text(entry.get("title")),
        "user_message": _clean_text(entry.get("user_message")),
        "intent": intent,
        "connection_kind": connection_kind,
        "connection_ref": connection_ref,
        "capability": capability,
        "chosen_action": chosen_action,
        "learned_from_action": learned_from_action,
        "experience_summary": _clean_text(entry.get("experience_summary") or entry.get("summary")),
        "router_keywords": router_keywords,
        "promotion_state": _clean_lower(entry.get("promotion_state")),
        "promotion_hint": _clean_text(entry.get("promotion_hint")),
        "experience_count": int(entry.get("experience_count", 0) or 0),
        "learning_signal": _clean_text(entry.get("learning_signal")),
        "learning_signal_reason": _clean_text(entry.get("learning_signal_reason")),
        "learning_weight": entry.get("learning_weight", 0.0) or 0.0,
        "learning_evidence": entry.get("learning_evidence", 0.0) or 0.0,
        "last_success_at": _clean_text(entry.get("last_success_at")),
        "learning_origin": learning_origin,
        "target_fingerprint": _fingerprint(connection_kind, connection_ref),
        "action_fingerprint": _fingerprint(capability, intent, chosen_action or learned_from_action),
        "experience_fingerprint": _fingerprint(connection_kind, connection_ref, capability, intent, chosen_action or learned_from_action),
    }
    return normalized


def build_recipe_experience_memory_text(entry: dict[str, Any]) -> str:
    entry = normalize_recipe_experience_memory_entry(entry)
    parts = [
        f"Recipe experience: {_clean_text(entry.get('title')) or _clean_text(entry.get('recipe_id'))}",
        f"User phrasing: {_clean_text(entry.get('user_message'))}" if _clean_text(entry.get("user_message")) else "",
        f"Intent: {_clean_text(entry.get('intent'))}" if _clean_text(entry.get("intent")) else "",
        f"Target: {_clean_text(entry.get('connection_kind'))}/{_clean_text(entry.get('connection_ref'))}"
        if _clean_text(entry.get("connection_kind")) or _clean_text(entry.get("connection_ref"))
        else "",
        f"Capability: {_clean_text(entry.get('capability'))}" if _clean_text(entry.get("capability")) else "",
        f"Final action: {_clean_text(entry.get('chosen_action'))}" if _clean_text(entry.get("chosen_action")) else "",
        f"Learned from draft: {_clean_text(entry.get('learned_from_action'))}" if _clean_text(entry.get("learned_from_action")) else "",
        f"Summary: {_clean_text(entry.get('experience_summary'))}"
        if _clean_text(entry.get("experience_summary"))
        else "",
        f"Learning signal: {_clean_text(entry.get('learning_signal'))}" if _clean_text(entry.get("learning_signal")) else "",
        f"Learning evidence: {_clean_text(entry.get('learning_evidence'))}" if _clean_text(entry.get("learning_evidence")) else "",
        f"Learning reason: {_clean_text(entry.get('learning_signal_reason'))}"
        if _clean_text(entry.get("learning_signal_reason"))
        else "",
        f"Curated confidence: {_clean_text(entry.get('confidence'))}" if _clean_text(entry.get("confidence")) else "",
        f"Curated risk: {_clean_text(entry.get('risk_level'))}" if _clean_text(entry.get("risk_level")) else "",
        f"Generalization: {_clean_text(entry.get('generalization_hint'))}"
        if _clean_text(entry.get("generalization_hint"))
        else "",
        "Suggested triggers: " + ", ".join(_clean_text(item) for item in list(entry.get("suggested_triggers", []) or []) if _clean_text(item))
        if list(entry.get("suggested_triggers", []) or [])
        else "",
        f"Promotion reason: {_clean_text(entry.get('promotion_reason'))}" if _clean_text(entry.get("promotion_reason")) else "",
        "Limits: " + "; ".join(_clean_text(item) for item in list(entry.get("limits", []) or []) if _clean_text(item))
        if list(entry.get("limits", []) or [])
        else "",
        "Triggers: " + ", ".join(_clean_text(item) for item in list(entry.get("router_keywords", []) or []) if _clean_text(item))
        if list(entry.get("router_keywords", []) or [])
        else "",
        f"Learning origin: {_clean_text(entry.get('learning_origin'))}" if _clean_text(entry.get("learning_origin")) else "",
        f"Target fingerprint: {_clean_text(entry.get('target_fingerprint'))}" if _clean_text(entry.get("target_fingerprint")) else "",
        f"Action fingerprint: {_clean_text(entry.get('action_fingerprint'))}" if _clean_text(entry.get("action_fingerprint")) else "",
        f"Promotion state: {_clean_text(entry.get('promotion_state'))}" if _clean_text(entry.get("promotion_state")) else "",
    ]
    return "\n".join(part for part in parts if part).strip()


async def store_recipe_experience_memory(
    memory_skill: Any,
    *,
    user_id: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    clean_user = _clean_text(user_id) or "web"
    entry = normalize_recipe_experience_memory_entry(entry)
    recipe_id = _clean_text(entry.get("recipe_id"))
    text = build_recipe_experience_memory_text(entry)
    if memory_skill is None or not recipe_id or not text:
        return {"stored": False, "reason": "missing_memory_or_entry"}

    vector, usage = await memory_skill._embed(
        text,
        source=RECIPE_EXPERIENCE_SOURCE,
        operation="store_recipe_experience",
        user_id=clean_user,
    )
    collection = await memory_skill._get_collection_for_vector(
        len(vector),
        base_collection=recipe_experience_collection_for_user(clean_user),
    )
    point_key = _clean_text(entry.get("experience_fingerprint")) or recipe_id
    point_id = str(uuid5(NAMESPACE_URL, f"{collection}|{clean_user}|{recipe_id}|{point_key}"))
    now = datetime.now(timezone.utc).isoformat()
    point = PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "text": text,
            "user_id": clean_user,
            "timestamp": now,
            "type": "knowledge",
            "source": RECIPE_EXPERIENCE_SOURCE,
            "recipe_id": recipe_id,
            "title": _clean_text(entry.get("title")),
            "intent": _clean_text(entry.get("intent")),
            "connection_kind": _clean_text(entry.get("connection_kind")).lower(),
            "connection_ref": _clean_text(entry.get("connection_ref")),
            "capability": _clean_text(entry.get("capability")).lower(),
            "chosen_action": _clean_text(entry.get("chosen_action")),
            "user_message": _clean_text(entry.get("user_message")),
            "promotion_state": _clean_text(entry.get("promotion_state")).lower(),
            "promotion_hint": _clean_text(entry.get("promotion_hint")),
            "experience_count": int(entry.get("experience_count", 0) or 0),
            "last_success_at": _clean_text(entry.get("last_success_at")),
            "learning_origin": _clean_text(entry.get("learning_origin")),
            "learned_from_action": _clean_text(entry.get("learned_from_action")),
            "target_fingerprint": _clean_text(entry.get("target_fingerprint")),
            "action_fingerprint": _clean_text(entry.get("action_fingerprint")),
            "experience_fingerprint": _clean_text(entry.get("experience_fingerprint")),
            "embedding_model": memory_skill._resolve_embedding_model(),
            "embedding_fingerprint": memory_skill._active_embedding_fingerprint(),
            "created_at": now,
            "updated_at": now,
        },
    )
    await memory_skill.qdrant.upsert(collection_name=collection, points=[point])
    return {
        "stored": True,
        "collection": collection,
        "point_id": point_id,
        "embedding_usage": dict(usage or {}),
    }


async def delete_recipe_experience_memory(
    memory_skill: Any,
    *,
    user_id: str,
    recipe_id: str,
) -> dict[str, Any]:
    clean_user = _clean_text(user_id) or "web"
    clean_recipe_id = _clean_text(recipe_id)
    if memory_skill is None or not clean_recipe_id:
        return {"deleted": False, "reason": "missing_memory_or_recipe_id", "deleted_points": 0, "collections": []}

    base_collection = recipe_experience_collection_for_user(clean_user)
    try:
        collections = await memory_skill._candidate_collections(base_collection)
    except Exception:
        collections = [base_collection]

    recipe_filter = Filter(
        must=[
            FieldCondition(key="user_id", match=MatchValue(value=clean_user)),
            FieldCondition(key="source", match=MatchValue(value=RECIPE_EXPERIENCE_SOURCE)),
            FieldCondition(key="recipe_id", match=MatchValue(value=clean_recipe_id)),
        ]
    )
    deleted_points = 0
    touched_collections: list[str] = []
    errors: list[str] = []
    for collection in collections:
        collection_name = _clean_text(collection)
        if not collection_name:
            continue
        try:
            exists = await memory_skill.qdrant.collection_exists(collection_name=collection_name)
            if not exists:
                continue
            point_ids: list[str | int] = []
            offset: Any = None
            while True:
                rows, next_offset = await memory_skill.qdrant.scroll(
                    collection_name=collection_name,
                    scroll_filter=recipe_filter,
                    limit=128,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False,
                )
                for row in rows:
                    point_id = getattr(row, "id", None)
                    if point_id not in (None, ""):
                        point_ids.append(point_id)
                if next_offset is None:
                    break
                offset = next_offset
            if not point_ids:
                continue
            await memory_skill.qdrant.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids),
                wait=True,
            )
            deleted_points += len(point_ids)
            touched_collections.append(collection_name)
        except Exception as exc:
            errors.append(f"{collection_name}:{exc}")
            continue

    return {
        "deleted": deleted_points > 0,
        "deleted_points": deleted_points,
        "collections": touched_collections,
        "errors": errors,
    }


async def search_recipe_experience_memory(
    memory_skill: Any,
    *,
    user_id: str,
    query: str,
    connection_kind: str = "",
    connection_ref: str = "",
    capability: str = "",
    intent: str = "",
    top_k: int = 3,
) -> list[dict[str, Any]]:
    clean_user = _clean_text(user_id) or "web"
    clean_query = _clean_text(query)
    if memory_skill is None or not clean_query:
        return []

    vector, _usage = await memory_skill._embed(
        clean_query,
        source=RECIPE_EXPERIENCE_SOURCE,
        operation="search_recipe_experience",
        user_id=clean_user,
    )
    base_collection = recipe_experience_collection_for_user(clean_user)
    collections = await memory_skill._candidate_collections(base_collection)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    user_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=clean_user))])
    requested_kind = _clean_lower(connection_kind)
    requested_ref = _clean_text(connection_ref)
    requested_capability = _clean_lower(capability)
    requested_intent = _clean_lower(intent)
    for collection in collections:
        try:
            exists = await memory_skill.qdrant.collection_exists(collection_name=collection)
            if not exists:
                continue
            query_result = await memory_skill.qdrant.query_points(
                collection_name=collection,
                query=vector,
                query_filter=user_filter,
                limit=max(2, int(top_k) + 2),
            )
        except Exception:
            continue
        for hit in memory_skill._extract_hits(query_result):
            payload = getattr(hit, "payload", {}) or {}
            if not memory_skill._payload_embedding_compatible(payload):
                continue
            if str(payload.get("source", "") or "").strip() != RECIPE_EXPERIENCE_SOURCE:
                continue
            if requested_kind and _clean_lower(payload.get("connection_kind")) != requested_kind:
                continue
            if requested_ref and _clean_text(payload.get("connection_ref")) != requested_ref:
                continue
            if requested_capability and _clean_lower(payload.get("capability")) != requested_capability:
                continue
            if requested_intent and _clean_lower(payload.get("intent")) != requested_intent:
                continue
            recipe_id = _clean_text(payload.get("recipe_id"))
            if not recipe_id:
                continue
            key = (collection, _clean_text(payload.get("experience_fingerprint")) or recipe_id)
            if key in seen:
                continue
            seen.add(key)
            score = float(getattr(hit, "score", 0.0) or 0.0)
            if requested_kind and _clean_lower(payload.get("connection_kind")) == requested_kind:
                score += 0.05
            if requested_ref and _clean_text(payload.get("connection_ref")) == requested_ref:
                score += 0.1
            if requested_capability and _clean_lower(payload.get("capability")) == requested_capability:
                score += 0.05
            if requested_intent and _clean_lower(payload.get("intent")) == requested_intent:
                score += 0.05
            rows.append(
                {
                    "recipe_id": recipe_id,
                    "title": _clean_text(payload.get("title")),
                    "intent": _clean_text(payload.get("intent")),
                    "connection_kind": _clean_text(payload.get("connection_kind")),
                    "connection_ref": _clean_text(payload.get("connection_ref")),
                    "capability": _clean_text(payload.get("capability")),
                    "chosen_action": _clean_text(payload.get("chosen_action")),
                    "user_message": _clean_text(payload.get("user_message")),
                    "promotion_state": _clean_text(payload.get("promotion_state")),
                    "promotion_hint": _clean_text(payload.get("promotion_hint")),
                    "experience_count": int(payload.get("experience_count", 0) or 0),
                    "last_success_at": _clean_text(payload.get("last_success_at")),
                    "learning_origin": _clean_text(payload.get("learning_origin")),
                    "learned_from_action": _clean_text(payload.get("learned_from_action")),
                    "target_fingerprint": _clean_text(payload.get("target_fingerprint")),
                    "action_fingerprint": _clean_text(payload.get("action_fingerprint")),
                    "experience_fingerprint": _clean_text(payload.get("experience_fingerprint")),
                    "score": score,
                    "semantic_score": float(getattr(hit, "score", 0.0) or 0.0),
                    "collection": collection,
                    "text": _clean_text(payload.get("text")),
                }
            )
    rows.sort(key=lambda row: (float(row.get("score", 0.0) or 0.0), int(row.get("experience_count", 0) or 0)), reverse=True)
    return rows[: max(1, int(top_k))]
