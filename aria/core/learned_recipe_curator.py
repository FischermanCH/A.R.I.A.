from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

from aria.core.learned_recipe_store import save_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry
from aria.core.text_utils import extract_json_object

CURATION_POLICY_CONTEXT_ONLY = "context_only_not_executable"
CURATION_SOURCE_LLM = "llm_curator"
CURATION_STATUS_OK = "ok"
CURATION_STATUS_SKIPPED = "skipped"
CURATION_REFRESH_COUNTS = {1, 3, 5}
RISK_LEVELS = {"low", "medium", "high", "unknown"}


def _clean_text(value: Any, *, max_len: int = 320) -> str:
    clean = re.sub(r"\s+", " ", str(value or "")).strip()
    return clean[:max_len].strip()


def _clean_list(value: Any, *, max_items: int, max_len: int) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for item in list(value or []) if isinstance(value, list) else []:
        clean = _clean_text(item, max_len=max_len)
        key = clean.lower()
        if not clean or key in seen:
            continue
        seen.add(key)
        rows.append(clean)
        if len(rows) >= max_items:
            break
    return rows


def _confidence(value: Any) -> float:
    try:
        raw = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, raw))


def learned_recipe_needs_llm_curation(entry: dict[str, Any] | None) -> bool:
    normalized = normalize_learned_recipe_store_entry(entry or {})
    if str(normalized.get("promotion_state", "") or "").strip().lower() == "promoted":
        return False
    if not str(normalized.get("curation_source", "") or "").strip():
        return True
    count = int(normalized.get("experience_count", 0) or 0)
    return count in CURATION_REFRESH_COUNTS


def validate_learned_recipe_curation_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(payload or {})
    risk_level = _clean_text(data.get("risk_level"), max_len=24).lower() or "unknown"
    if risk_level not in RISK_LEVELS:
        risk_level = "unknown"
    return {
        "curation_source": CURATION_SOURCE_LLM,
        "curation_policy": CURATION_POLICY_CONTEXT_ONLY,
        "curation_status": CURATION_STATUS_OK,
        "curation_last_error": "",
        "curated_at": datetime.now(timezone.utc).isoformat(),
        "confidence": _confidence(data.get("confidence")),
        "risk_level": risk_level,
        "generalization_hint": _clean_text(data.get("generalization_hint"), max_len=360),
        "suggested_triggers": _clean_list(data.get("suggested_triggers"), max_items=8, max_len=90),
        "promotion_reason": _clean_text(data.get("promotion_reason"), max_len=360),
        "limits": _clean_list(data.get("limits"), max_items=5, max_len=140),
    }


def _curator_prompt(entry: dict[str, Any], *, language: str = "de") -> list[dict[str, str]]:
    normalized = normalize_learned_recipe_store_entry(entry)
    compact = {
        key: normalized.get(key)
        for key in (
            "recipe_id",
            "title",
            "summary",
            "intent",
            "connection_kind",
            "connection_ref",
            "capability",
            "chosen_action",
            "policy_result",
            "execution_result",
            "user_message",
            "experience_count",
            "last_success_at",
            "promotion_state",
            "promotion_hint",
            "router_keywords",
            "recipe_scope",
        )
    }
    return [
        {
            "role": "system",
            "content": (
                "You are ARIA's bounded Learned Recipe Curator. "
                "Your job is to describe what was learned from a successful, policy-approved run. "
                "Never create executable commands, never approve actions, never weaken guardrails. "
                "Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "Analyze this learned recipe candidate and return exactly this JSON shape:\n"
                "{"
                "\"confidence\": 0.0-1.0, "
                "\"risk_level\": \"low|medium|high|unknown\", "
                "\"generalization_hint\": \"when this pattern is likely useful\", "
                "\"suggested_triggers\": [\"natural user phrasings, max 8\"], "
                "\"promotion_reason\": \"why an admin may or may not promote this\", "
                "\"limits\": [\"boundaries and cases where this must not be reused\"]"
                "}\n"
                "The result is context-only review metadata. It must not be directly executable.\n"
                f"UI language: {language or 'de'}\n"
                f"Candidate:\n{json.dumps(compact, ensure_ascii=False, indent=2)}"
            ),
        },
    ]


async def curate_learned_recipe_entry(
    *,
    llm_client: Any | None,
    entry: dict[str, Any],
    language: str = "de",
    user_id: str = "",
    request_id: str = "",
) -> tuple[dict[str, Any], str]:
    normalized = normalize_learned_recipe_store_entry(entry)
    if not learned_recipe_needs_llm_curation(normalized):
        return normalized, ""
    if llm_client is None:
        skipped = normalize_learned_recipe_store_entry(
            {
                **normalized,
                "curation_policy": CURATION_POLICY_CONTEXT_ONLY,
                "curation_status": CURATION_STATUS_SKIPPED,
                "curation_last_error": "llm_client_unavailable",
            }
        )
        stored = save_learned_recipe_store_entry(skipped, previous_id=str(normalized.get("recipe_id", "") or "").strip())
        return stored, "Learned Recipe Curator: skipped reason=llm_client_unavailable"
    try:
        response = await llm_client.chat(
            _curator_prompt(normalized, language=language),
            source="learned_recipe_curator",
            operation="curate_learned_recipe",
            user_id=user_id,
            request_id=request_id,
        )
        payload = extract_json_object(getattr(response, "content", "") or "") or {}
        curated = validate_learned_recipe_curation_payload(payload)
        merged = normalize_learned_recipe_store_entry({**normalized, **curated})
        stored = save_learned_recipe_store_entry(merged, previous_id=str(normalized.get("recipe_id", "") or "").strip())
        debug = (
            "Learned Recipe Curator: agentic_source=llm_decision "
            f"policy={CURATION_POLICY_CONTEXT_ONLY} "
            f"confidence={stored.get('confidence', 0.0)} "
            f"risk={stored.get('risk_level', 'unknown')}"
        )
        return stored, debug
    except Exception as exc:  # noqa: BLE001
        skipped = normalize_learned_recipe_store_entry(
            {
                **normalized,
                "curation_policy": CURATION_POLICY_CONTEXT_ONLY,
                "curation_status": CURATION_STATUS_SKIPPED,
                "curation_last_error": type(exc).__name__,
            }
        )
        stored = save_learned_recipe_store_entry(skipped, previous_id=str(normalized.get("recipe_id", "") or "").strip())
        return stored, f"Learned Recipe Curator: skipped reason={type(exc).__name__}"
