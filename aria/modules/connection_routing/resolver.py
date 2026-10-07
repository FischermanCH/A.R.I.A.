from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aria.modules.connections_catalog.catalog import normalize_connection_kind


@dataclass(slots=True)
class RoutingDecision:
    kind: str = ""
    ref: str = ""
    capability: str = ""
    source: str = ""
    score: float = 0.0
    reason: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.kind and self.ref)


def validate_qdrant_connection_candidate(
    candidate: dict[str, Any],
    available_connection_pools: dict[str, dict[str, Any]],
    *,
    preferred_kind: str = "",
) -> tuple[str, str] | None:
    kind = normalize_connection_kind(str(candidate.get("kind", "") or ""))
    ref = str(candidate.get("ref", "") or "").strip()
    if not kind or not ref:
        return None
    clean_preferred = normalize_connection_kind(preferred_kind)
    if clean_preferred and kind != clean_preferred:
        return None
    pool = available_connection_pools.get(kind, {})
    if not isinstance(pool, dict) or not pool:
        return None
    for configured_ref in pool:
        if str(configured_ref).strip().lower() == ref.lower():
            return kind, str(configured_ref).strip()
    return None
