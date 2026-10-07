from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from aria.modules.platform_primitives.bounded_decision import BoundedDecisionClient
from aria.modules.platform_primitives.bounded_decision import confidence_score


PERSONAL_CLAIM_CONTRACT = "personal_claim_v1"
PERSONAL_CLAIM_KINDS = {
    "fact",
    "preference",
    "identity",
    "goal",
    "project",
    "relationship",
    "routine",
    "boundary",
    "entity_alias",
}
PERSONAL_CLAIM_SCOPES = {"global", "domain", "project", "session"}
PERSONAL_CLAIM_STATUSES = {
    "active",
    "paused",
    "completed",
    "pending_supersession",
    "historical",
    "disputed",
    "suspended",
}
PERSONAL_CLAIM_RELATIONS = {"supports", "refines", "contradicts", "replaces", "unrelated"}
PERSONAL_CLAIM_AUTHORITIES = {"inferred": 10, "repeated_observation": 20, "explicit_user": 30, "user_correction": 40}
PERSONAL_CONTEXT_CAPSULE_CONTRACT = "personal_context_capsule_v1"
PERSONAL_CONTEXT_FEEDBACK_WINDOW_SECONDS = 30 * 60


def _clean_text(value: Any, *, limit: int = 400) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _stable_key(value: Any) -> str:
    text = _clean_text(value, limit=500).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _clean_iso_timestamp(value: Any) -> str:
    clean = _clean_text(value, limit=80)
    if not clean:
        return ""
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def normalize_personal_claim(
    value: Any,
    *,
    user_id: str = "",
    default_kind: str = "",
    default_value: str = "",
    source: str = "auto_memory",
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    kind = _clean_text(value.get("claim_kind") or value.get("kind") or default_kind, limit=60).lower()
    if kind not in PERSONAL_CLAIM_KINDS:
        return {}
    subject = _clean_text(value.get("subject") or "user", limit=160)
    predicate = _clean_text(value.get("predicate"), limit=160)
    claim_value = _clean_text(value.get("value") or default_value, limit=700)
    scope = _clean_text(value.get("scope") or "global", limit=60).lower()
    if scope not in PERSONAL_CLAIM_SCOPES:
        scope = "global"
    scope_ref = _clean_text(value.get("scope_ref"), limit=180)
    risk = _clean_text(value.get("risk") or "medium", limit=40).lower()
    if risk not in {"low", "medium", "high"}:
        risk = "medium"
    explicit = value.get("explicit") is True or value.get("explicit_user_statement") is True
    authority = _clean_text(
        value.get("authority") or ("explicit_user" if explicit else "inferred"),
        limit=60,
    ).lower()
    if authority not in PERSONAL_CLAIM_AUTHORITIES:
        authority = "explicit_user" if explicit else "inferred"
    if not subject or not predicate or not claim_value:
        return {}
    confidence = max(0.0, min(1.0, confidence_score(value.get("confidence") or 0.0)))
    valid_from = _clean_iso_timestamp(value.get("valid_from"))
    valid_until = _clean_iso_timestamp(value.get("valid_until"))
    review_after = _clean_iso_timestamp(value.get("review_after"))
    claim_key = str(
        uuid5(
            NAMESPACE_URL,
            "|".join(
                (
                    PERSONAL_CLAIM_CONTRACT,
                    _stable_key(user_id),
                    kind,
                    _stable_key(subject),
                    _stable_key(predicate),
                    scope,
                    _stable_key(scope_ref),
                )
            ),
        )
    )
    claim_id = str(uuid5(NAMESPACE_URL, f"{claim_key}|{_stable_key(claim_value)}"))
    evidence_refs = value.get("evidence_refs")
    safe_refs = []
    if isinstance(evidence_refs, list):
        for item in evidence_refs[:8]:
            if isinstance(item, Mapping):
                ref = {
                    "collection": _clean_text(item.get("collection"), limit=180),
                    "point_id": _clean_text(item.get("point_id") or item.get("id"), limit=180),
                    "request_id": _clean_text(item.get("request_id"), limit=180),
                }
                if any(ref.values()):
                    safe_refs.append(ref)
            else:
                ref = _clean_text(item, limit=240)
                if ref:
                    safe_refs.append({"ref": ref})
    return {
        "contract": PERSONAL_CLAIM_CONTRACT,
        "claim_id": claim_id,
        "claim_key": claim_key,
        "claim_kind": kind,
        "subject": subject,
        "predicate": predicate,
        "value": claim_value,
        "scope": scope,
        "scope_ref": scope_ref,
        "confidence": confidence,
        "explicit": explicit,
        "authority": authority,
        "risk": risk,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "review_after": review_after,
        "source": _clean_text(source, limit=120) or "auto_memory",
        "evidence_refs": safe_refs,
    }


def personal_claim_activation_blockers(claim: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if claim.get("contract") != PERSONAL_CLAIM_CONTRACT:
        blockers.append("invalid_contract")
    if claim.get("claim_kind") == "entity_alias":
        blockers.append("entity_alias_requires_learning_contract")
    if claim.get("explicit") is not True:
        blockers.append("not_explicit")
    if str(claim.get("scope") or "").lower() == "session":
        blockers.append("session_scope")
    if str(claim.get("risk") or "").lower() != "low":
        blockers.append("risk_not_low")
    if str(claim.get("authority") or "") not in {"explicit_user", "user_correction"}:
        blockers.append("insufficient_authority")
    if confidence_score(claim.get("confidence")) < 0.62:
        blockers.append("low_confidence")
    valid_until = _clean_iso_timestamp(claim.get("valid_until"))
    if valid_until and datetime.fromisoformat(valid_until) <= datetime.now(timezone.utc):
        blockers.append("expired")
    return tuple(blockers)


def personal_claim_activation_allowed(claim: Mapping[str, Any]) -> bool:
    return not personal_claim_activation_blockers(claim)


def personal_claim_payload(
    claim: Mapping[str, Any],
    *,
    status: str,
    relation: str = "unrelated",
    supersedes: str = "",
) -> dict[str, Any]:
    clean_status = _clean_text(status, limit=60).lower()
    if clean_status not in PERSONAL_CLAIM_STATUSES:
        clean_status = "disputed"
    clean_relation = _clean_text(relation, limit=60).lower()
    if clean_relation not in PERSONAL_CLAIM_RELATIONS:
        clean_relation = "unrelated"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "personal_claim_contract": PERSONAL_CLAIM_CONTRACT,
        "claim_id": _clean_text(claim.get("claim_id"), limit=180),
        "claim_key": _clean_text(claim.get("claim_key"), limit=180),
        "claim_kind": _clean_text(claim.get("claim_kind"), limit=60),
        "claim_subject": _clean_text(claim.get("subject"), limit=160),
        "claim_predicate": _clean_text(claim.get("predicate"), limit=160),
        "claim_value": _clean_text(claim.get("value"), limit=700),
        "claim_scope": _clean_text(claim.get("scope"), limit=60),
        "claim_scope_ref": _clean_text(claim.get("scope_ref"), limit=180),
        "claim_confidence": float(claim.get("confidence", 0.0) or 0.0),
        "claim_authority": _clean_text(claim.get("authority"), limit=60),
        "claim_risk": _clean_text(claim.get("risk"), limit=40),
        "claim_status": clean_status,
        "claim_relation": clean_relation,
        "claim_supersedes": _clean_text(supersedes, limit=180),
        "claim_evidence_refs": json.dumps(claim.get("evidence_refs") or [], ensure_ascii=True, separators=(",", ":")),
        "claim_support_count": 1,
        "claim_last_supported_at": now,
        "claim_valid_from": _clean_iso_timestamp(claim.get("valid_from")) or now,
        "claim_valid_until": _clean_iso_timestamp(claim.get("valid_until")),
        "claim_review_after": _clean_iso_timestamp(claim.get("review_after")),
        "claim_updated_at": now,
    }


def personal_claim_from_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    if str(value.get("personal_claim_contract") or "") != PERSONAL_CLAIM_CONTRACT:
        return {}
    return {
        "contract": PERSONAL_CLAIM_CONTRACT,
        "claim_id": _clean_text(value.get("claim_id"), limit=180),
        "claim_key": _clean_text(value.get("claim_key"), limit=180),
        "claim_kind": _clean_text(value.get("claim_kind"), limit=60),
        "subject": _clean_text(value.get("claim_subject"), limit=160),
        "predicate": _clean_text(value.get("claim_predicate"), limit=160),
        "value": _clean_text(value.get("claim_value") or value.get("text"), limit=700),
        "scope": _clean_text(value.get("claim_scope"), limit=60),
        "scope_ref": _clean_text(value.get("claim_scope_ref"), limit=180),
        "confidence": float(value.get("claim_confidence", 0.0) or 0.0),
        "authority": _clean_text(value.get("claim_authority"), limit=60),
        "risk": _clean_text(value.get("claim_risk"), limit=40),
        "status": _clean_text(value.get("claim_status"), limit=60),
        "valid_from": _clean_iso_timestamp(value.get("claim_valid_from")),
        "valid_until": _clean_iso_timestamp(value.get("claim_valid_until")),
        "review_after": _clean_iso_timestamp(value.get("claim_review_after")),
        "collection": _clean_text(value.get("collection"), limit=180),
        "point_id": _clean_text(value.get("id") or value.get("point_id"), limit=180),
    }


def personal_claim_payload_is_runtime_active(value: Mapping[str, Any]) -> bool:
    return personal_claim_payload_lifecycle_state(value) == "effective"


def personal_claim_payload_lifecycle_state(value: Mapping[str, Any]) -> str:
    if str(value.get("personal_claim_contract") or "") != PERSONAL_CLAIM_CONTRACT:
        return "effective"
    if str(value.get("claim_status") or "").strip().lower() != "active":
        return "inactive"
    now = datetime.now(timezone.utc)
    valid_from = _clean_iso_timestamp(value.get("claim_valid_from"))
    if valid_from and datetime.fromisoformat(valid_from) > now:
        return "scheduled"
    valid_until = _clean_iso_timestamp(value.get("claim_valid_until"))
    if valid_until and datetime.fromisoformat(valid_until) <= now:
        return "expired"
    return "effective"


def personal_claim_payload_review_due(value: Mapping[str, Any]) -> bool:
    if str(value.get("personal_claim_contract") or "") != PERSONAL_CLAIM_CONTRACT:
        return False
    if str(value.get("claim_status") or "").strip().lower() not in {"active", "paused"}:
        return False
    review_after = _clean_iso_timestamp(value.get("claim_review_after"))
    return bool(review_after and datetime.fromisoformat(review_after) <= datetime.now(timezone.utc))


def personal_claim_review_candidate(claim: Mapping[str, Any], *, reason: str) -> dict[str, Any]:
    normalized = (
        dict(claim)
        if str(claim.get("contract") or "") == PERSONAL_CLAIM_CONTRACT
        else normalize_personal_claim(claim, source=str(claim.get("source") or "auto_memory"))
    )
    if not normalized:
        return {}
    if normalized.get("scope") == "session":
        return {}
    explicit_label = "explicit" if normalized["explicit"] else "inferred"
    return {
        "candidate_id": f"personal-claim-candidate-{uuid4().hex}",
        "artifact_type": "personal_claim_candidate",
        "status": "proposed",
        "risk": normalized["risk"],
        "title": f"Personal claim: {normalized['predicate']}",
        "summary": f"{explicit_label}: {normalized['value']}",
        "reason": _clean_text(reason, limit=400) or "Personal claim requires review.",
        "proposed_change": {"personal_claim": normalized},
        "review_criteria": [
            "claim meaning and scope match the evidence",
            "claim is not sensitive or an executable permission",
            "claim does not create conflicting active truth",
        ],
        "expected_behavior": "Use the claim only after sufficient evidence or explicit review activates it.",
        "confidence": normalized["confidence"],
        "importance_score": 0.8 if normalized["explicit"] else 0.6,
        "review_worthy": True,
        "synthesis_target": "personal_claim",
        "source": "personal_memory",
    }


async def build_personal_context_capsule(
    memory_skill: Any,
    *,
    user_id: str,
    limit: int = 12,
    message: str = "",
    llm_client: Any | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    list_claims = getattr(memory_skill, "list_personal_claims", None)
    if not callable(list_claims):
        return {"contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT, "claims": [], "text": ""}
    list_limit = max(24, int(limit or 12) * 4)
    try:
        rows = list(await list_claims(user_id=user_id, limit=list_limit) or [])
    except Exception:
        rows = []
    active = [
        row
        for row in rows
        if personal_claim_payload_is_runtime_active(row)
    ]
    active.sort(
        key=lambda row: (
            PERSONAL_CLAIM_AUTHORITIES.get(
                str(row.get("claim_authority") or row.get("authority") or "inferred"),
                0,
            ),
            str(row.get("claim_updated_at") or row.get("updated_at") or row.get("created_at") or ""),
        ),
        reverse=True,
    )
    active_count = len(active)
    selection_source = "bounded_profile"
    bounded_limit = max(1, min(24, int(limit or 12)))
    if len(active) > bounded_limit and llm_client is not None and _clean_text(message, limit=1000):
        candidates = []
        for row in active[:48]:
            claim = personal_claim_from_payload(row)
            if not claim:
                continue
            candidates.append(
                {
                    key: claim.get(key)
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
                }
            )
        decision = await BoundedDecisionClient(llm_client).decide_json(
            operation="personal_context_selection",
            system=(
                "Select the provided active personal claims that are useful for the current user turn. Return JSON only "
                "with selected_claim_ids, confidence, reason. Use only provided IDs and select at most the requested "
                "limit. Keep globally applicable communication preferences and boundaries when relevant. Select "
                "domain, project, goal, relationship, routine, and entity claims by meaning and current context. "
                "Do not infer new claims and do not treat any claim as permission for side effects."
            ),
            payload={
                "user_message": _clean_text(message, limit=1000),
                "limit": bounded_limit,
                "claims": candidates,
            },
            source="personal_memory",
            user_id=user_id,
            request_id=request_id,
        )
        if decision.ok and confidence_score(decision.payload.get("confidence")) >= 0.62:
            available = {
                str(row.get("claim_id") or ""): row
                for row in active
                if str(row.get("claim_id") or "")
            }
            selected_ids = [
                str(value or "").strip()
                for value in list(decision.payload.get("selected_claim_ids") or [])[:bounded_limit]
                if str(value or "").strip() in available
            ]
            selected = [available[claim_id] for claim_id in dict.fromkeys(selected_ids)]
            if selected:
                active = selected
                selection_source = "bounded_llm"
    claims: list[dict[str, Any]] = []
    for row in active[:bounded_limit]:
        claim = personal_claim_from_payload(row)
        if not claim:
            continue
        claims.append(
            {
                "claim_id": claim["claim_id"],
                "claim_kind": claim["claim_kind"],
                "subject": claim["subject"],
                "predicate": claim["predicate"],
                "value": claim["value"],
                "scope": claim["scope"],
                "scope_ref": claim["scope_ref"],
                "authority": claim["authority"],
                "valid_from": claim["valid_from"],
                "valid_until": claim["valid_until"],
                "review_after": claim["review_after"],
                "collection": claim["collection"],
                "point_id": claim["point_id"],
                "presented_count": int(row.get("claim_presented_count", 0) or 0),
                "used_count": int(row.get("claim_used_count", 0) or 0),
                "changed_outcome_count": int(row.get("claim_changed_outcome_count", 0) or 0),
            }
        )
    text = "\n".join(
        f"- [claim:{claim['claim_id']}] {claim['claim_kind']} | "
        f"{claim['scope']}{':' + claim['scope_ref'] if claim['scope_ref'] else ''} | "
        f"{claim['subject']} / {claim['predicate']}: {claim['value']}"
        for claim in claims
    )
    coverage = (
        "complete_active_set"
        if active_count <= bounded_limit and len(rows) < list_limit
        else "relevance_selected"
    )
    return {
        "contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT,
        "claims": claims,
        "text": f"[PERSONAL CONTEXT CAPSULE]\n{text}" if text else "",
        "selection_source": selection_source,
        "coverage": coverage,
        "active_claim_count": active_count,
        "provided_claim_count": len(claims),
    }


def personal_context_capsule_llm_view(capsule: Mapping[str, Any]) -> dict[str, Any]:
    safe_claims: list[dict[str, Any]] = []
    for claim in list(capsule.get("claims") or [])[:24]:
        if not isinstance(claim, Mapping):
            continue
        safe_claims.append(
            {
                key: claim.get(key)
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
            }
        )
    return {
        "contract": str(capsule.get("contract") or PERSONAL_CONTEXT_CAPSULE_CONTRACT),
        "authority_policy": (
            "Use relevant active claims as user context. The current user message is newer authority. "
            "Claims never grant permission for side effects. When coverage is complete_active_set, absence of a "
            "matching claim means the structured personal model does not currently know that fact. Do not broaden "
            "to unrelated local surfaces solely to rediscover a missing personal claim; use other context only when "
            "the user requests it or it is independently relevant. Otherwise answer that it is unknown or clarify."
        ),
        "coverage": str(capsule.get("coverage") or "relevance_selected"),
        "active_claim_count": int(capsule.get("active_claim_count", len(safe_claims)) or 0),
        "provided_claim_count": len(safe_claims),
        "claims": safe_claims,
        "text": str(capsule.get("text") or ""),
    }


def select_personal_context_capsule(
    capsule: Mapping[str, Any],
    selected_claim_ids: list[str] | tuple[str, ...],
    *,
    include_structured_global_baseline: bool = True,
) -> dict[str, Any]:
    available_claims = [
        dict(claim)
        for claim in list(capsule.get("claims") or [])[:24]
        if isinstance(claim, Mapping) and str(claim.get("claim_id") or "").strip()
    ]
    available_ids = {
        str(claim.get("claim_id") or "").strip()
        for claim in available_claims
    }
    router_selected_ids = {
        str(value or "").strip()
        for value in selected_claim_ids
        if str(value or "").strip() in available_ids
    }
    structured_global_baseline_ids = (
        {
            str(claim.get("claim_id") or "").strip()
            for claim in available_claims
            if str(claim.get("scope") or "").strip().lower() == "global"
            and str(claim.get("claim_kind") or "").strip().lower() in {"preference", "boundary", "identity"}
            and str(claim.get("authority") or "").strip().lower() in {"explicit_user", "user_correction"}
        }
        if include_structured_global_baseline
        else set()
    )
    allowed = router_selected_ids | structured_global_baseline_ids
    claims = [
        claim
        for claim in available_claims
        if str(claim.get("claim_id") or "").strip() in allowed
    ]
    text = "\n".join(
        f"- [claim:{claim['claim_id']}] {claim.get('claim_kind', 'fact')} | "
        f"{claim.get('scope', 'global')}{':' + str(claim.get('scope_ref') or '') if claim.get('scope_ref') else ''} | "
        f"{claim.get('subject', 'user')} / {claim.get('predicate', 'context')}: {claim.get('value', '')}"
        for claim in claims
    )
    return {
        "contract": str(capsule.get("contract") or PERSONAL_CONTEXT_CAPSULE_CONTRACT),
        "claims": claims,
        "text": f"[PERSONAL CONTEXT CAPSULE]\n{text}" if text else "",
        "selection_source": (
            "turn_plan+structured_global_baseline"
            if router_selected_ids and structured_global_baseline_ids - router_selected_ids
            else "structured_global_baseline"
            if structured_global_baseline_ids and not router_selected_ids
            else "turn_plan"
        ),
        "available_count": len(available_claims),
        "router_selected_count": len(router_selected_ids),
        "structured_global_baseline_count": len(structured_global_baseline_ids),
    }


async def record_personal_context_presentation(
    memory_skill: Any,
    *,
    user_id: str,
    request_id: str,
    capsule: Mapping[str, Any],
    surfaces: list[str],
) -> dict[str, int]:
    update_payload = getattr(memory_skill, "update_memory_point_payload", None)
    if not callable(update_payload):
        return {"presented": 0, "updated": 0}
    clean_surfaces = [
        _clean_text(surface, limit=80)
        for surface in list(surfaces or [])[:5]
        if _clean_text(surface, limit=80)
    ]
    now = datetime.now(timezone.utc).isoformat()
    updates = []
    for claim in list(capsule.get("claims") or [])[:24]:
        if not isinstance(claim, Mapping):
            continue
        collection = _clean_text(claim.get("collection"), limit=180)
        point_id = _clean_text(claim.get("point_id"), limit=180)
        if not collection or not point_id:
            continue
        updates.append(
            update_payload(
                user_id,
                collection,
                point_id,
                {
                    "claim_presented_count": int(claim.get("presented_count", 0) or 0) + 1,
                    "claim_last_presented_at": now,
                    "claim_last_presented_request_id": _clean_text(request_id, limit=180),
                    "claim_last_presented_surfaces": json.dumps(
                        clean_surfaces,
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                },
            )
        )
    if not updates:
        return {"presented": 0, "updated": 0}
    results = await asyncio.gather(*updates, return_exceptions=True)
    return {
        "presented": len(updates),
        "updated": sum(result is True for result in results),
    }


async def review_personal_context_influence(
    llm_client: Any | None,
    *,
    user_id: str,
    request_id: str,
    message: str,
    response: str,
    capsule: Mapping[str, Any],
) -> dict[str, Any]:
    claims = [
        dict(claim)
        for claim in list(capsule.get("claims") or [])[:24]
        if isinstance(claim, Mapping) and str(claim.get("claim_id") or "").strip()
    ]
    if llm_client is None or not claims:
        return {
            "used_claim_ids": [],
            "changed_outcome": False,
            "confidence": 0.0,
            "source": "review_unavailable",
        }
    result = await BoundedDecisionClient(llm_client).decide_json(
        operation="personal_context_influence_review",
        system=(
            "Review whether any provided active personal claims materially influenced the final response. "
            "Return JSON only with used_claim_ids, changed_outcome, confidence, reason. Use only provided claim IDs. "
            "A claim is used only when the response's content, style, scope, or decision clearly reflects it; mere "
            "availability is not use. changed_outcome is true only when the response would materially differ without it."
        ),
        payload={
            "user_message": _clean_text(message, limit=1000),
            "final_response": _clean_text(response, limit=1800),
            "claims": personal_context_capsule_llm_view(capsule)["claims"],
        },
        source="personal_memory",
        user_id=user_id,
        request_id=request_id,
    )
    if not result.ok:
        return {
            "used_claim_ids": [],
            "changed_outcome": False,
            "confidence": 0.0,
            "source": "review_unavailable",
        }
    allowed_ids = {str(claim.get("claim_id") or "") for claim in claims}
    used_claim_ids = [
        str(value or "").strip()
        for value in list(result.payload.get("used_claim_ids") or [])[:12]
        if str(value or "").strip() in allowed_ids
    ]
    confidence = max(0.0, min(1.0, confidence_score(result.payload.get("confidence"))))
    if confidence < 0.62:
        used_claim_ids = []
    return {
        "used_claim_ids": list(dict.fromkeys(used_claim_ids)),
        "changed_outcome": bool(result.payload.get("changed_outcome") is True and used_claim_ids),
        "confidence": confidence,
        "reason": _clean_text(result.payload.get("reason"), limit=400),
        "source": "bounded_llm",
        "usage": result.usage,
    }


async def record_personal_context_influence(
    memory_skill: Any,
    *,
    user_id: str,
    request_id: str,
    capsule: Mapping[str, Any],
    review: Mapping[str, Any],
) -> dict[str, int]:
    update_payload = getattr(memory_skill, "update_memory_point_payload", None)
    if not callable(update_payload):
        return {"used": 0, "updated": 0}
    used_ids = {
        str(value or "").strip()
        for value in list(review.get("used_claim_ids") or [])
        if str(value or "").strip()
    }
    if not used_ids:
        return {"used": 0, "updated": 0}
    changed_outcome = bool(review.get("changed_outcome") is True)
    now = datetime.now(timezone.utc).isoformat()
    updates = []
    for claim in list(capsule.get("claims") or [])[:24]:
        if not isinstance(claim, Mapping) or str(claim.get("claim_id") or "") not in used_ids:
            continue
        collection = _clean_text(claim.get("collection"), limit=180)
        point_id = _clean_text(claim.get("point_id"), limit=180)
        if not collection or not point_id:
            continue
        receipt = {
            "request_id": _clean_text(request_id, limit=180),
            "phase": "answer",
            "used": True,
            "changed_outcome": changed_outcome,
            "review_source": _clean_text(review.get("source"), limit=80),
            "review_confidence": float(review.get("confidence", 0.0) or 0.0),
            "timestamp": now,
        }
        updates.append(
            update_payload(
                user_id,
                collection,
                point_id,
                {
                    "claim_used_count": int(claim.get("used_count", 0) or 0) + 1,
                    "claim_changed_outcome_count": int(claim.get("changed_outcome_count", 0) or 0)
                    + int(changed_outcome),
                    "claim_last_used_at": now,
                    "claim_last_used_request_id": _clean_text(request_id, limit=180),
                    "claim_last_influence_receipt": json.dumps(
                        receipt,
                        ensure_ascii=True,
                        separators=(",", ":"),
                    ),
                },
            )
        )
    results = await asyncio.gather(*updates, return_exceptions=True)
    return {"used": len(updates), "updated": sum(result is True for result in results)}


async def apply_recent_personal_context_feedback(
    memory_skill: Any,
    *,
    user_id: str,
    sentiment: str,
    target_request_id: str | None = None,
) -> dict[str, Any]:
    clean_target_request_id = (
        _clean_text(target_request_id, limit=180)
        if target_request_id is not None
        else None
    )
    return {
        "linked_claim_ids": [],
        **(
            {"request_id": clean_target_request_id}
            if clean_target_request_id is not None
            else {}
        ),
    }


class PersonalClaimResolver:
    def __init__(self, llm_client: Any | None):
        self.decision_client = BoundedDecisionClient(llm_client)

    async def resolve_relation(
        self,
        claim: Mapping[str, Any],
        *,
        existing_claims: list[Mapping[str, Any]],
        user_id: str,
        request_id: str = "",
    ) -> dict[str, Any]:
        active = [
            personal_claim_from_payload(row)
            for row in existing_claims[:24]
            if str(row.get("claim_status") or row.get("status") or "active").lower() == "active"
        ]
        active = [row for row in active if row]
        if not active:
            return {"relation": "unrelated", "target_claim_id": "", "confidence": 1.0, "source": "empty_profile"}
        exact = next(
            (
                row
                for row in active
                if row.get("claim_key") == claim.get("claim_key")
                and _stable_key(row.get("value")) == _stable_key(claim.get("value"))
            ),
            None,
        )
        if exact:
            return {
                "relation": "supports",
                "target_claim_id": exact["claim_id"],
                "confidence": 1.0,
                "source": "exact_claim",
            }
        result = await self.decision_client.decide_json(
            operation="personal_claim_relation",
            system=(
                "You compare one new explicit personal-memory claim with existing active claims for the same user. "
                "Return JSON only. Decide relation supports|refines|contradicts|replaces|unrelated and select at most "
                "one target_claim_id from the provided existing claims. Meaning and scope decide the relation. "
                "Use replaces when the user clearly states a newer preference or truth that should become current; "
                "use contradicts when both cannot be current but replacement is uncertain. Do not invent IDs. "
                "Return relation,target_claim_id,confidence,reason."
            ),
            payload={"new_claim": dict(claim), "existing_claims": active},
            source="personal_memory",
            user_id=user_id,
            request_id=request_id,
        )
        if not result.ok:
            return {"relation": "unrelated", "target_claim_id": "", "confidence": 0.0, "source": "llm_unavailable"}
        relation = _clean_text(result.payload.get("relation"), limit=60).lower()
        target_id = _clean_text(result.payload.get("target_claim_id"), limit=180)
        allowed_ids = {str(row.get("claim_id") or "") for row in active}
        confidence = max(0.0, min(1.0, confidence_score(result.payload.get("confidence"))))
        if relation not in PERSONAL_CLAIM_RELATIONS:
            relation = "unrelated"
        if target_id not in allowed_ids:
            target_id = ""
        if not target_id:
            relation = "unrelated"
        return {
            "relation": relation,
            "target_claim_id": target_id,
            "confidence": confidence,
            "reason": _clean_text(result.payload.get("reason"), limit=400),
            "source": "bounded_llm",
            "usage": result.usage,
        }


async def consolidate_personal_claim_batch(
    claims: list[Mapping[str, Any]],
    *,
    llm_client: Any | None,
    user_id: str,
    request_id: str = "",
) -> dict[str, Any]:
    unique: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for raw_claim in list(claims or [])[:5]:
        source = str(raw_claim.get("source") or "turn_action_contract") if isinstance(raw_claim, Mapping) else "turn_action_contract"
        claim = normalize_personal_claim(
            raw_claim,
            user_id=user_id,
            source=source,
        )
        claim_id = _clean_text(claim.get("claim_id"), limit=180)
        if not claim_id or claim_id in seen_claim_ids:
            continue
        seen_claim_ids.add(claim_id)
        unique.append(claim)
    if len(unique) <= 1:
        return {
            "ok": True,
            "claims": unique,
            "input_count": len(claims or []),
            "output_count": len(unique),
            "source": "exact_claim_id",
            "usage": {},
        }

    indexed = [
        {
            "claim_ref": f"claim-{index}",
            "claim_kind": claim.get("claim_kind"),
            "subject": claim.get("subject"),
            "predicate": claim.get("predicate"),
            "value": claim.get("value"),
            "scope": claim.get("scope"),
            "scope_ref": claim.get("scope_ref"),
        }
        for index, claim in enumerate(unique, start=1)
    ]
    by_ref = {
        row["claim_ref"]: claim
        for row, claim in zip(indexed, unique, strict=True)
    }
    result = await BoundedDecisionClient(llm_client).decide_json(
        operation="personal_claim_batch_consolidation",
        system=(
            "You consolidate structured personal-memory claims extracted from one user turn before any write. "
            "Return JSON only with groups and confidence. Group claims only when they express the same durable "
            "proposition as paraphrases or redundant fragments. Keep independent facts, preferences, scopes, "
            "and time bounds in separate groups. Every provided claim_ref must occur exactly once across groups. "
            "For each group return claim_refs and one representative_ref selected from that group. "
            "Do not rewrite claims, invent refs, or infer new personal information."
        ),
        payload={"claims": indexed},
        source="personal_memory",
        user_id=user_id,
        request_id=request_id,
    )
    if not result.ok or confidence_score(result.payload.get("confidence")) < 0.62:
        return {
            "ok": False,
            "claims": [],
            "input_count": len(unique),
            "output_count": 0,
            "source": "bounded_llm",
            "reason": result.error or "low_confidence",
            "usage": result.usage,
        }

    raw_groups = result.payload.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        return {
            "ok": False,
            "claims": [],
            "input_count": len(unique),
            "output_count": 0,
            "source": "bounded_llm",
            "reason": "invalid_groups",
            "usage": result.usage,
        }
    covered: list[str] = []
    representatives: list[dict[str, Any]] = []
    for raw_group in raw_groups:
        if not isinstance(raw_group, Mapping):
            return {
                "ok": False,
                "claims": [],
                "input_count": len(unique),
                "output_count": 0,
                "source": "bounded_llm",
                "reason": "invalid_group",
                "usage": result.usage,
            }
        raw_refs = raw_group.get("claim_refs")
        group_refs = (
            [_clean_text(value, limit=40) for value in raw_refs]
            if isinstance(raw_refs, list)
            else []
        )
        representative_ref = _clean_text(raw_group.get("representative_ref"), limit=40)
        if (
            not group_refs
            or len(set(group_refs)) != len(group_refs)
            or any(ref not in by_ref for ref in group_refs)
            or representative_ref not in group_refs
        ):
            return {
                "ok": False,
                "claims": [],
                "input_count": len(unique),
                "output_count": 0,
                "source": "bounded_llm",
                "reason": "invalid_group_refs",
                "usage": result.usage,
            }
        covered.extend(group_refs)
        representatives.append(by_ref[representative_ref])
    if len(covered) != len(set(covered)) or set(covered) != set(by_ref):
        return {
            "ok": False,
            "claims": [],
            "input_count": len(unique),
            "output_count": 0,
            "source": "bounded_llm",
            "reason": "incomplete_group_coverage",
            "usage": result.usage,
        }
    return {
        "ok": True,
        "claims": representatives,
        "input_count": len(unique),
        "output_count": len(representatives),
        "source": "bounded_llm",
        "usage": result.usage,
    }


async def store_personal_claim(
    *,
    memory_skill: Any,
    llm_client: Any | None,
    claim: Mapping[str, Any],
    user_id: str,
    facts_collection: str,
    preferences_collection: str,
    request_id: str = "",
    explicit_supersedes_claim_id: str = "",
) -> dict[str, Any]:
    started = time.perf_counter()
    timings = {
        "list_existing_ms": 0,
        "relation_ms": 0,
        "store_ms": 0,
    }
    normalized = normalize_personal_claim(claim, user_id=user_id, source=str(claim.get("source") or "auto_memory"))
    if not normalized:
        return {"stored": False, "reason": "invalid_claim"}
    activation_blockers = personal_claim_activation_blockers(normalized)
    if activation_blockers:
        return {
            "stored": False,
            "reason": "claim_not_auto_activatable",
            "activation_blockers": list(activation_blockers),
            "claim": normalized,
        }
    list_claims = getattr(memory_skill, "list_personal_claims", None)
    lookup_limit = 500 if _clean_text(explicit_supersedes_claim_id, limit=180) else 120
    phase_started = time.perf_counter()
    existing = await list_claims(user_id=user_id, limit=lookup_limit) if callable(list_claims) else []
    timings["list_existing_ms"] = max(0, int((time.perf_counter() - phase_started) * 1000))
    explicit_target_id = _clean_text(explicit_supersedes_claim_id, limit=180)
    explicit_target = next(
        (
            row
            for row in existing
            if str(row.get("claim_id") or "") == explicit_target_id
            and str(row.get("claim_status") or "").strip().lower() == "active"
            and str(row.get("claim_key") or "") == normalized["claim_key"]
        ),
        None,
    )
    if explicit_target_id and not explicit_target:
        return {"stored": False, "reason": "explicit_supersession_target_invalid", "claim": normalized}
    active_same_key = [
        row
        for row in existing
        if str(row.get("claim_status") or row.get("status") or "active").lower() == "active"
        and str(row.get("claim_key") or "") == normalized["claim_key"]
    ]
    phase_started = time.perf_counter()
    relation = (
        {
            "relation": "replaces",
            "target_claim_id": explicit_target_id,
            "confidence": 1.0,
            "reason": "explicit user correction of selected active claim",
            "source": "explicit_user_control",
        }
        if explicit_target
        else (
            await PersonalClaimResolver(llm_client).resolve_relation(
                normalized,
                existing_claims=active_same_key,
                user_id=user_id,
                request_id=request_id,
            )
            if active_same_key
            else {
                "relation": "unrelated",
                "target_claim_id": "",
                "confidence": 1.0,
                "reason": "no active claim shares the structured proposition identity",
                "source": "no_same_proposition",
            }
        )
    )
    timings["relation_ms"] = max(0, int((time.perf_counter() - phase_started) * 1000))
    relation_name = str(relation.get("relation") or "unrelated")
    target_id = str(relation.get("target_claim_id") or "")
    target = next(
        (row for row in existing if str(row.get("claim_id") or "") == target_id),
        None,
    )
    if relation_name == "supports" and target:
        update_payload = getattr(memory_skill, "update_memory_point_payload", None)
        target_collection = _clean_text(target.get("collection"), limit=180)
        target_point_id = _clean_text(target.get("id") or target.get("point_id"), limit=180)
        if not callable(update_payload) or not target_collection or not target_point_id:
            return {
                "stored": False,
                "reason": "claim_support_update_unavailable",
                "claim": normalized,
                "relation": relation,
            }
        existing_refs: list[dict[str, str]] = []
        raw_refs = target.get("claim_evidence_refs")
        try:
            parsed_refs = json.loads(raw_refs) if isinstance(raw_refs, str) else raw_refs
        except json.JSONDecodeError:
            parsed_refs = []
        for row in list(parsed_refs or [])[:8]:
            if isinstance(row, Mapping):
                ref = {
                    "source": _clean_text(row.get("source"), limit=80),
                    "request_id": _clean_text(row.get("request_id"), limit=180),
                    "excerpt": _clean_text(row.get("excerpt"), limit=240),
                }
            else:
                ref = {"source": _clean_text(row, limit=80), "request_id": "", "excerpt": ""}
            if any(ref.values()) and ref not in existing_refs:
                existing_refs.append(ref)
        for row in list(normalized.get("evidence_refs") or [])[:8]:
            ref = (
                {
                    "source": _clean_text(row.get("source"), limit=80),
                    "request_id": _clean_text(row.get("request_id") or request_id, limit=180),
                    "excerpt": _clean_text(row.get("excerpt"), limit=240),
                }
                if isinstance(row, Mapping)
                else {
                    "source": _clean_text(row, limit=80),
                    "request_id": _clean_text(request_id, limit=180),
                    "excerpt": "",
                }
            )
            if any(ref.values()) and ref not in existing_refs:
                existing_refs.append(ref)
        supported_at = datetime.now(timezone.utc).isoformat()
        updated = await update_payload(
            user_id,
            target_collection,
            target_point_id,
            {
                "claim_support_count": int(target.get("claim_support_count", 1) or 1) + 1,
                "claim_last_supported_at": supported_at,
                "claim_last_supported_request_id": _clean_text(request_id, limit=180),
                "claim_evidence_refs": json.dumps(
                    existing_refs[-8:],
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                "claim_updated_at": supported_at,
            },
        )
        return {
            "stored": bool(updated),
            "reason": "existing_claim_supported" if updated else "claim_support_update_failed",
            "claim": normalized,
            "relation": relation,
            "point_id": target_point_id,
            "collection": target_collection,
            "timings": {
                **timings,
                "total_ms": max(0, int((time.perf_counter() - started) * 1000)),
            },
        }
    relation_confidence = float(relation.get("confidence", 0.0) or 0.0)
    if active_same_key and (
        target not in active_same_key
        or relation_name not in {"refines", "contradicts", "replaces"}
        or relation_confidence < 0.62
    ):
        return {
            "stored": False,
            "reason": "claim_relation_unresolved",
            "claim": normalized,
            "relation": relation,
        }
    superseding = bool(
        target
        and relation_name in {"refines", "contradicts", "replaces"}
        and relation_confidence >= 0.62
        and PERSONAL_CLAIM_AUTHORITIES.get(normalized["authority"], 0)
        >= PERSONAL_CLAIM_AUTHORITIES.get(str(target.get("claim_authority") or target.get("authority") or "inferred"), 0)
    )
    initial_status = "pending_supersession" if superseding else "active"
    collection = preferences_collection if normalized["claim_kind"] == "preference" else facts_collection
    memory_type = "preference" if normalized["claim_kind"] == "preference" else "fact"
    phase_started = time.perf_counter()
    store_params = {
        "action": "store",
        "text": normalized["value"],
        "user_id": user_id,
        "collection": collection,
        "memory_type": memory_type,
        "source": "personal_claim",
        "payload_metadata": personal_claim_payload(
            normalized,
            status=initial_status,
            relation=relation_name,
            supersedes=target_id if superseding else "",
        ),
    }
    for attempt in range(3):
        store_result = await memory_skill.execute(query=normalized["value"], params=store_params)
        if getattr(store_result, "success", False):
            break
        if attempt < 2:
            await asyncio.sleep(0.2 * (attempt + 1))
    timings["store_ms"] = max(0, int((time.perf_counter() - phase_started) * 1000))
    if not getattr(store_result, "success", False):
        store_error = _clean_text(
            getattr(store_result, "error", "") or getattr(store_result, "content", ""),
            limit=240,
        )
        return {
            "stored": False,
            "reason": "claim_store_failed",
            "store_error": store_error,
            "claim": normalized,
            "relation": relation,
        }
    point_id = str((getattr(store_result, "metadata", {}) or {}).get("point_id") or "")
    stored_collection = str((getattr(store_result, "metadata", {}) or {}).get("collection") or collection)
    if bool((getattr(store_result, "metadata", {}) or {}).get("deduplicated")):
        adopted = await memory_skill.update_memory_point_payload(
            user_id,
            stored_collection,
            point_id,
            personal_claim_payload(
                normalized,
                status=initial_status,
                relation=relation_name,
                supersedes=target_id if superseding else "",
            ),
        )
        if not adopted:
            return {
                "stored": False,
                "reason": "legacy_claim_adoption_failed",
                "claim": normalized,
                "relation": relation,
                "point_id": point_id,
                "collection": stored_collection,
            }
    if not superseding:
        return {
            "stored": True,
            "reason": "claim_activated",
            "claim": normalized,
            "relation": relation,
            "point_id": point_id,
            "collection": stored_collection,
            "timings": {
                **timings,
                "total_ms": max(0, int((time.perf_counter() - started) * 1000)),
            },
        }
    target_collection = str(target.get("collection") or "")
    target_point_id = str(target.get("id") or target.get("point_id") or "")
    old_updated = await memory_skill.update_memory_point_payload(
        user_id,
        target_collection,
        target_point_id,
        {
            "claim_status": "historical",
            "claim_superseded_by": normalized["claim_id"],
            "claim_superseded_at": datetime.now(timezone.utc).isoformat(),
            "claim_supersession_relation": relation_name,
        },
    )
    if not old_updated:
        return {
            "stored": False,
            "reason": "superseded_claim_update_failed",
            "claim": normalized,
            "relation": relation,
            "point_id": point_id,
            "collection": stored_collection,
        }
    new_activated = await memory_skill.update_memory_point_payload(
        user_id,
        stored_collection,
        point_id,
        {"claim_status": "active", "claim_activated_at": datetime.now(timezone.utc).isoformat()},
    )
    if not new_activated:
        await memory_skill.update_memory_point_payload(
            user_id,
            target_collection,
            target_point_id,
            {
                "claim_status": "active",
                "claim_superseded_by": "",
                "claim_supersession_rollback_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "stored": False,
            "reason": "new_claim_activation_failed",
            "claim": normalized,
            "relation": relation,
            "point_id": point_id,
            "collection": stored_collection,
        }
    return {
        "stored": True,
        "reason": "claim_superseded",
        "claim": normalized,
        "relation": relation,
        "point_id": point_id,
        "collection": stored_collection,
        "superseded_claim_id": target_id,
        "timings": {
            **timings,
            "total_ms": max(0, int((time.perf_counter() - started) * 1000)),
        },
    }
