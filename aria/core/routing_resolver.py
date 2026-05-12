from __future__ import annotations

import json
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from aria.core.connection_catalog import normalize_connection_kind
from aria.core.connection_semantic_resolver import build_connection_aliases, connection_label_match_score

_ROUTING_RESOLVER_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "routing_resolver.json"


def _load_routing_resolver_lexicon() -> dict[str, Any]:
    try:
        raw = json.loads(_ROUTING_RESOLVER_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load routing resolver lexicon: {_ROUTING_RESOLVER_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_ROUTING_RESOLVER_LEXICON = _load_routing_resolver_lexicon()


class RoutingCandidateProvider(Protocol):
    async def query_connections(
        self,
        query: str,
        *,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> list[dict[str, Any]]: ...


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


def _normalize_message(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _contains_label(text: str, label: str) -> bool:
    clean_label = _normalize_message(label)
    if not clean_label:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(clean_label)}(?![a-z0-9])", text) is not None


def _available_refs(rows: dict[str, Any]) -> set[str]:
    return {str(ref).strip().lower() for ref in rows if str(ref).strip()}


def _has_any_word(text: str, terms: Iterable[str]) -> bool:
    for term in terms:
        clean = _normalize_message(term)
        if clean and _contains_label(text, clean):
            return True
    return False


def infer_preferred_connection_kind(
    message: str,
    *,
    explicit_kind: str = "",
    available_kinds: Iterable[str] = (),
) -> str:
    """Infer a safe connection kind from action words when the UI is on auto.

    This is intentionally conservative: it only returns a kind when the user
    asks for an action class that maps clearly to one connection type.
    """

    clean_explicit = normalize_connection_kind(explicit_kind)
    if clean_explicit and clean_explicit != "auto":
        return clean_explicit

    available = {normalize_connection_kind(kind) for kind in available_kinds if normalize_connection_kind(kind)}
    lower = _normalize_message(message)
    if not lower:
        return ""

    scores = {
        "ssh": 0,
        "sftp": 0,
        "smb": 0,
        "google_calendar": 0,
        "discord": 0,
        "rss": 0,
        "http_api": 0,
        "webhook": 0,
        "email": 0,
        "imap": 0,
        "mqtt": 0,
    }

    for row in _ROUTING_RESOLVER_LEXICON.get("regex_scores", []):
        if not isinstance(row, dict):
            continue
        kind = normalize_connection_kind(str(row.get("kind") or ""))
        patterns = row.get("all", [])
        if not kind or kind not in scores or not isinstance(patterns, list):
            continue
        if all(re.search(str(pattern), lower, re.IGNORECASE) for pattern in patterns if str(pattern).strip()):
            scores[kind] += int(row.get("score") or 0)

    word_scores = _ROUTING_RESOLVER_LEXICON.get("word_scores", {})
    if isinstance(word_scores, dict):
        for kind, rows in word_scores.items():
            clean_kind = normalize_connection_kind(str(kind))
            if clean_kind not in scores or not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if row.get("requires_existing_score") and not scores[clean_kind]:
                    continue
                terms = row.get("terms", [])
                if isinstance(terms, list) and _has_any_word(lower, tuple(str(term) for term in terms)):
                    scores[clean_kind] += int(row.get("score") or 0)

    path_regex = str(_ROUTING_RESOLVER_LEXICON.get("path_regex") or "")
    path_score = _ROUTING_RESOLVER_LEXICON.get("path_score", {})
    if path_regex and isinstance(path_score, dict) and re.search(path_regex, lower):
        kind = normalize_connection_kind(str(path_score.get("kind") or ""))
        if kind in scores:
            scores[kind] += int(path_score.get("score") or 0)

    adjustments = _ROUTING_RESOLVER_LEXICON.get("score_adjustments", [])
    if isinstance(adjustments, list):
        for row in adjustments:
            if not isinstance(row, dict):
                continue
            kind = normalize_connection_kind(str(row.get("kind") or ""))
            required_kind = normalize_connection_kind(str(row.get("requires_kind_score") or ""))
            terms = row.get("terms", [])
            if kind not in scores or (required_kind and not scores.get(required_kind, 0)) or not isinstance(terms, list):
                continue
            if not _has_any_word(lower, tuple(str(term) for term in terms)):
                continue
            value = int(row.get("value") or 0)
            if row.get("operation") == "subtract":
                scores[kind] -= value
                if "min" in row:
                    scores[kind] = max(int(row.get("min") or 0), scores[kind])
            else:
                scores[kind] += value

    if available:
        scores = {kind: score for kind, score in scores.items() if kind in available}
    if not scores:
        return ""

    best_kind, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return ""
    if sum(1 for score in scores.values() if score == best_score) > 1:
        return ""
    return best_kind


class RoutingResolver:
    """Resolve action targets without letting vector search override safe rules.

    The resolver is deliberately hybrid:
    1. exact refs and aliases win deterministically
    2. Qdrant candidates are only considered if they still point to a configured
       kind/ref pair and pass the preferred-kind filter
    """

    def __init__(self, *, candidate_provider: RoutingCandidateProvider | None = None) -> None:
        self.candidate_provider = candidate_provider

    @staticmethod
    def _iter_pools(
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
    ) -> list[tuple[str, dict[str, Any]]]:
        clean_preferred = normalize_connection_kind(preferred_kind)
        rows: list[tuple[str, dict[str, Any]]] = []
        for kind, pool in sorted((available_connection_pools or {}).items()):
            clean_kind = normalize_connection_kind(kind)
            if clean_preferred and clean_kind != clean_preferred:
                continue
            if isinstance(pool, dict) and pool:
                rows.append((clean_kind, pool))
        return rows

    @classmethod
    def _deterministic_connection_match(
        cls,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
    ) -> RoutingDecision:
        lower = _normalize_message(message)
        if not lower:
            return RoutingDecision()

        exact_best: tuple[float, str, str, str, str] | None = None
        alias_candidates: list[tuple[float, str, str, str, str]] = []
        for kind, pool in cls._iter_pools(available_connection_pools, preferred_kind=preferred_kind):
            for ref, row in pool.items():
                clean_ref = str(ref).strip()
                if not clean_ref:
                    continue
                ref_lower = clean_ref.lower()
                ref_spaced = ref_lower.replace("-", " ").replace("_", " ")
                if _contains_label(lower, ref_lower):
                    candidate = (10000.0 + len(clean_ref), kind, clean_ref, "exact_ref", clean_ref)
                    if exact_best is None or candidate > exact_best:
                        exact_best = candidate
                    continue
                if ref_spaced != ref_lower and _contains_label(lower, ref_spaced):
                    candidate = (9500.0 + len(clean_ref), kind, clean_ref, "exact_ref_spaced", ref_spaced)
                    if exact_best is None or candidate > exact_best:
                        exact_best = candidate
                    continue

                best_alias = ""
                best_alias_score = 0
                for alias in build_connection_aliases(kind, clean_ref, row):
                    if "://" in str(alias or ""):
                        continue
                    score = connection_label_match_score(message, alias)
                    if score > best_alias_score:
                        best_alias_score = score
                        best_alias = alias
                if best_alias_score > 0:
                    alias_candidates.append((float(best_alias_score), kind, clean_ref, "alias", best_alias))

        if exact_best is not None:
            score, kind, ref, source, reason = exact_best
            return RoutingDecision(kind=kind, ref=ref, source=source, score=score, reason=reason)

        if not alias_candidates:
            return RoutingDecision()

        alias_candidates.sort(reverse=True)
        top_score = float(alias_candidates[0][0] or 0.0)
        top_aliases = [candidate for candidate in alias_candidates if float(candidate[0] or 0.0) == top_score]
        if len(top_aliases) > 1:
            return RoutingDecision(
                candidates=[
                    {
                        "kind": kind,
                        "ref": ref,
                        "source": source,
                        "score": score,
                        "reason": reason,
                    }
                    for score, kind, ref, source, reason in top_aliases
                ]
            )

        score, kind, ref, source, reason = alias_candidates[0]
        return RoutingDecision(kind=kind, ref=ref, source=source, score=score, reason=reason)

    @staticmethod
    def _qdrant_candidate_is_valid(
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
        ref_lookup = _available_refs(pool)
        if ref.lower() not in ref_lookup:
            return None
        for configured_ref in pool:
            if str(configured_ref).strip().lower() == ref.lower():
                return kind, str(configured_ref).strip()
        return None

    async def resolve_connection(
        self,
        message: str,
        available_connection_pools: dict[str, dict[str, Any]],
        *,
        preferred_kind: str = "",
        qdrant_limit: int = 5,
        qdrant_score_threshold: float = 0.0,
    ) -> RoutingDecision:
        effective_preferred_kind = infer_preferred_connection_kind(
            message,
            explicit_kind=preferred_kind,
            available_kinds=available_connection_pools.keys(),
        )
        deterministic = self._deterministic_connection_match(
            message,
            available_connection_pools,
            preferred_kind=effective_preferred_kind,
        )
        if deterministic.found:
            return deterministic

        if self.candidate_provider is None:
            return deterministic if deterministic.candidates else RoutingDecision()

        query_limit = max(1, int(qdrant_limit))
        if effective_preferred_kind:
            query_limit = max(query_limit, min(50, query_limit * 4))
        candidates = await self.candidate_provider.query_connections(
            message,
            limit=query_limit,
            score_threshold=qdrant_score_threshold,
        )
        valid_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            resolved = self._qdrant_candidate_is_valid(
                candidate,
                available_connection_pools,
                preferred_kind=effective_preferred_kind,
            )
            if not resolved:
                continue
            kind, ref = resolved
            score = float(candidate.get("score", 0.0) or 0.0)
            reason = str(candidate.get("reason", "") or "").strip()
            valid = {
                "kind": kind,
                "ref": ref,
                "capability": str(candidate.get("capability", "") or "").strip(),
                "score": score,
                "source": str(candidate.get("source", "") or "qdrant_routing"),
                "reason": reason,
            }
            valid_candidates.append(valid)

        valid_candidates.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        if not valid_candidates:
            return RoutingDecision(candidates=list(candidates))

        winner = valid_candidates[0]
        return RoutingDecision(
            kind=str(winner["kind"]),
            ref=str(winner["ref"]),
            capability=str(winner.get("capability", "") or ""),
            source=str(winner["source"]),
            score=float(winner["score"]),
            reason=str(winner.get("reason", "") or ""),
            candidates=valid_candidates,
        )
