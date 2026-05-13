from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from aria.core.recipe_promotion_contract import PROMOTION_STATE_PROMOTED
from aria.core.learned_recipe_store import load_learned_recipe_store_entries
from aria.core.learned_recipe_store import save_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import build_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry

LEARNING_SIGNAL_NEW_PATTERN = "new_pattern"
LEARNING_SIGNAL_REPEAT = "repeat"
LEARNING_SIGNAL_WORDING_VARIANT = "wording_variant"
LEARNING_SIGNAL_SCOPE_VARIANT = "scope_variant"
LEARNING_SIGNAL_ACTION_VARIANT = "action_variant"
LEARNING_SIGNAL_RISKY_DEVIATION = "risky_deviation"


_RISKY_ACTION_RE = re.compile(
    r"\b("
    r"rm|rmdir|mv|cp|chmod|chown|dd|mkfs|mount|umount|reboot|shutdown|restart|reload|"
    r"systemctl\s+(?:restart|stop|disable|enable|reload)|"
    r"docker\s+(?:rm|rmi|prune|stop|restart|compose\s+down)|"
    r"apt(?:-get)?\s+(?:install|remove|purge|upgrade|dist-upgrade)"
    r")\b",
    re.IGNORECASE,
)


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _safe_float(value: Any) -> float:
    try:
        raw = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, raw)


def _safe_int(value: Any) -> int:
    try:
        raw = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, raw)


def _classify_learning_signal(
    existing: dict[str, Any],
    *,
    connection_ref: str,
    chosen_action: str,
    user_message: str,
) -> dict[str, Any]:
    if not existing:
        return {
            "signal": LEARNING_SIGNAL_NEW_PATTERN,
            "weight": 1.0,
            "reason": "First successful observation for this learned recipe pattern.",
        }

    old_ref = _compact_text(existing.get("connection_ref"))
    new_ref = _compact_text(connection_ref)
    old_action = _compact_text(existing.get("chosen_action"))
    new_action = _compact_text(chosen_action)
    old_message = _compact_text(existing.get("user_message"))
    new_message = _compact_text(user_message)

    if old_action and new_action and old_action != new_action:
        if _RISKY_ACTION_RE.search(str(chosen_action or "")):
            return {
                "signal": LEARNING_SIGNAL_RISKY_DEVIATION,
                "weight": 0.0,
                "reason": "Successful run changed the remembered action toward a higher-risk operation; keep it for review only.",
            }
        return {
            "signal": LEARNING_SIGNAL_ACTION_VARIANT,
            "weight": 0.5,
            "reason": "Same learned pattern succeeded with a different action shape.",
        }

    if old_ref and new_ref and old_ref != new_ref:
        return {
            "signal": LEARNING_SIGNAL_SCOPE_VARIANT,
            "weight": 0.75,
            "reason": "Same learned pattern succeeded against a different target scope.",
        }

    if old_message and new_message and old_message != new_message:
        return {
            "signal": LEARNING_SIGNAL_WORDING_VARIANT,
            "weight": 0.75,
            "reason": "Same learned pattern matched a different user wording.",
        }

    return {
        "signal": LEARNING_SIGNAL_REPEAT,
        "weight": 0.25,
        "reason": "Repeated success for the same target, action and known wording.",
    }


def _learning_noise_patch(
    existing: dict[str, Any],
    *,
    signal: str,
    weight: float,
    reason: str,
    timestamp: str,
    chosen_action: str,
) -> dict[str, Any]:
    previous_evidence = _safe_float(existing.get("learning_evidence"))
    if existing and previous_evidence <= 0:
        previous_evidence = float(_safe_int(existing.get("experience_count")))
    patch: dict[str, Any] = {
        "learning_signal": signal,
        "learning_signal_reason": reason,
        "learning_weight": weight,
        "learning_evidence": previous_evidence + weight,
        "variant_count": _safe_int(existing.get("variant_count")),
        "scope_variant_count": _safe_int(existing.get("scope_variant_count")),
        "action_variant_count": _safe_int(existing.get("action_variant_count")),
        "last_deviation_action": str(existing.get("last_deviation_action", "") or "").strip(),
        "last_deviation_at": str(existing.get("last_deviation_at", "") or "").strip(),
    }
    if signal == LEARNING_SIGNAL_WORDING_VARIANT:
        patch["variant_count"] += 1
    if signal == LEARNING_SIGNAL_SCOPE_VARIANT:
        patch["scope_variant_count"] += 1
    if signal == LEARNING_SIGNAL_ACTION_VARIANT:
        patch["action_variant_count"] += 1
    if signal == LEARNING_SIGNAL_RISKY_DEVIATION:
        patch["action_variant_count"] += 1
        patch["last_deviation_action"] = str(chosen_action or "").strip()
        patch["last_deviation_at"] = timestamp
    return patch


def _normalized_recipe_id(
    *,
    recipe_id: str = "",
    intent: str = "",
    connection_kind: str = "",
    capability: str = "",
) -> str:
    entry = build_learned_recipe_store_entry(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    )
    return str(entry.get("recipe_id", "") or "").strip()


def _find_existing_entry(
    *,
    recipe_id: str = "",
    intent: str = "",
    connection_kind: str = "",
    capability: str = "",
) -> dict[str, Any] | None:
    target_id = _normalized_recipe_id(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    )
    if not target_id:
        return None
    for row in load_learned_recipe_store_entries():
        if str(row.get("recipe_id", "") or "").strip() == target_id:
            return dict(row)
    return None


def record_successful_learned_recipe_execution(
    *,
    intent: str,
    connection_kind: str,
    capability: str,
    chosen_action: str,
    connection_ref: str = "",
    policy_result: str = "allow",
    execution_result: str = "success",
    user_feedback: str = "",
    user_message: str = "",
    summary: str = "",
    recipe_id: str = "",
    title: str = "",
    preview: str = "",
    inputs: dict[str, str] | None = None,
    router_keywords: list[str] | None = None,
    recipe_scope: dict[str, Any] | None = None,
    recorded_at: str = "",
) -> dict[str, Any] | None:
    clean_execution_result = str(execution_result or "").strip().lower()
    if clean_execution_result != "success":
        return None

    existing = _find_existing_entry(
        recipe_id=recipe_id,
        intent=intent,
        connection_kind=connection_kind,
        capability=capability,
    ) or {}
    preserved_promotion_state = str(existing.get("promotion_state", "") or "").strip().lower()
    preserved_promotion_hint = str(existing.get("promotion_hint", "") or "").strip()
    if preserved_promotion_state != PROMOTION_STATE_PROMOTED and not preserved_promotion_hint.startswith("admin:"):
        preserved_promotion_state = ""
        preserved_promotion_hint = ""
    timestamp = str(recorded_at or "").strip() or datetime.now(timezone.utc).isoformat()
    next_experience_count = int(existing.get("experience_count", 0) or 0) + 1
    signal_info = _classify_learning_signal(
        existing,
        connection_ref=connection_ref,
        chosen_action=chosen_action,
        user_message=user_message,
    )
    signal = str(signal_info["signal"])
    noise_patch = _learning_noise_patch(
        existing,
        signal=signal,
        weight=float(signal_info["weight"]),
        reason=str(signal_info["reason"]),
        timestamp=timestamp,
        chosen_action=chosen_action,
    )
    keep_previous_action = signal == LEARNING_SIGNAL_RISKY_DEVIATION

    merged = {
        **existing,
        **noise_patch,
        "recipe_id": str(recipe_id or existing.get("recipe_id", "") or "").strip(),
        "intent": str(intent or existing.get("intent", "") or "").strip(),
        "connection_kind": str(connection_kind or existing.get("connection_kind", "") or "").strip(),
        "connection_ref": str(connection_ref or existing.get("connection_ref", "") or "").strip(),
        "capability": str(capability or existing.get("capability", "") or "").strip(),
        "chosen_action": str((existing.get("chosen_action", "") if keep_previous_action else chosen_action) or existing.get("chosen_action", "") or "").strip(),
        "policy_result": str(policy_result or existing.get("policy_result", "") or "").strip(),
        "execution_result": clean_execution_result,
        "user_feedback": str(user_feedback or existing.get("user_feedback", "") or "").strip(),
        "user_message": str(user_message or existing.get("user_message", "") or "").strip(),
        "experience_summary": str(summary or existing.get("experience_summary", "") or existing.get("summary", "") or "").strip(),
        "title": str(title or existing.get("title", "") or "").strip(),
        "preview": str(preview or existing.get("preview", "") or "").strip(),
        "inputs": dict((existing.get("inputs", {}) if keep_previous_action else inputs) or existing.get("inputs", {}) or {}),
        "router_keywords": list(router_keywords or existing.get("router_keywords", []) or []),
        "recipe_scope": dict(recipe_scope or existing.get("recipe_scope", {}) or {}),
        "experience_count": next_experience_count,
        "last_success_at": timestamp,
        "promotion_state": preserved_promotion_state,
        "promotion_hint": preserved_promotion_hint,
    }
    normalized = normalize_learned_recipe_store_entry(merged, fallback_connection_kind=connection_kind)
    return save_learned_recipe_store_entry(
        normalized,
        previous_id=str(existing.get("recipe_id", "") or "").strip() or None,
    )
