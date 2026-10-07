"""Read-only Personal Memory evidence projection owned by the Memory module."""

from __future__ import annotations

from typing import Any

from aria.modules.memory.personal import personal_claim_from_payload, personal_claim_payload_is_runtime_active
from aria.modules.sdk import Evidence

PERSONAL_CLAIM_SOURCE_AUTHORITY = "memory:personal_claim_store"


async def load_personal_claim_evidence(memory_skill: Any, *, user_id: str, limit: int = 48) -> tuple[Evidence, ...]:
    list_claims = getattr(memory_skill, "list_personal_claims", None)
    if not callable(list_claims):
        raise RuntimeError("personal_claim_source_unavailable")
    rows = list(await list_claims(user_id=user_id, limit=limit) or [])
    evidence: list[Evidence] = []
    for row in rows:
        if not isinstance(row, dict) or not personal_claim_payload_is_runtime_active(row):
            continue
        claim = personal_claim_from_payload(row)
        claim_id = str(claim.get("claim_id") or "").strip()
        value = str(claim.get("value") or "").strip()
        if not claim_id or not value:
            continue
        summary = " ".join(
            part for part in (
                str(claim.get("subject") or "").strip(),
                str(claim.get("predicate") or "").strip(),
                value,
            ) if part
        )
        evidence.append(Evidence(
            source=f"personal_claim:{claim_id}", summary=summary,
            payload={"claim_id": claim_id, "source_authority": PERSONAL_CLAIM_SOURCE_AUTHORITY},
        ))
    return tuple(evidence)
