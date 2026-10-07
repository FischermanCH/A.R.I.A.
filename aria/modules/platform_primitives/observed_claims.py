"""Bounded per-user recurrence store for native personal-memory candidates."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping, Sequence

MEMORY_RECURRENCE_THRESHOLD = 2
MEMORY_RECURRENCE_SIMILARITY_THRESHOLD = 0.82


def _clean(value: Any, *, limit: int = 700) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def claim_text(claim: Mapping[str, Any]) -> str:
    return " ".join(filter(None, (
        _clean(claim.get("subject") or "user", limit=160),
        _clean(claim.get("predicate"), limit=160),
        _clean(claim.get("value")),
    )))


def claim_recurrence_text(claim: Mapping[str, Any]) -> str:
    """Return only the normalized topic used for recurrence similarity."""
    return _clean(claim.get("value")).casefold()


def claim_signature(claim: Mapping[str, Any]) -> str:
    normalized = "\0".join((
        _clean(claim.get("claim_kind"), limit=40).casefold(),
        _clean(claim.get("subject") or "user", limit=160).casefold(),
        _clean(claim.get("predicate"), limit=160).casefold(),
        _clean(claim.get("value")).casefold(),
    ))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized.strip("\0") else ""


def recurrence_key(claim: Mapping[str, Any]) -> str:
    """Return the stable value-anchored key used only for recurrence counting."""
    normalized = "\0".join((
        _clean(claim.get("subject") or "user", limit=160).casefold(),
        _clean(claim.get("claim_kind"), limit=40).casefold(),
        _clean(claim.get("value")).casefold(),
    ))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized.strip("\0") else ""


def short_claim_signature(signature: str) -> str:
    return str(signature or "")[:12]


@dataclass(frozen=True)
class ObservedClaimRecord:
    signature: str
    recurrence_key: str
    count: int
    first_seen: float
    last_seen: float
    sample_claim: dict[str, str]
    offered: bool
    offer: bool = False
    similarity: float = 0.0


class ObservedClaimStore:
    def __init__(self, path: Path, *, per_user_cap: int = 200,
                 clock: Callable[[], float] = time.time) -> None:
        self._path = Path(path)
        self._cap = max(1, int(per_user_cap))
        self._clock = clock
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"users": {}}
        return payload if isinstance(payload, dict) and isinstance(payload.get("users"), dict) else {"users": {}}

    def _write(self, payload: Mapping[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self._path)

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @staticmethod
    def _record(row: Mapping[str, Any], *, offer: bool = False) -> ObservedClaimRecord:
        claim = row.get("sample_claim", {})
        return ObservedClaimRecord(
            signature=str(row.get("signature") or ""),
            recurrence_key=str(row.get("recurrence_key") or row.get("signature") or ""),
            count=int(row.get("count") or 0),
            first_seen=float(row.get("first_seen") or 0),
            last_seen=float(row.get("last_seen") or 0),
            sample_claim={str(key): str(value) for key, value in dict(claim).items()} if isinstance(claim, Mapping) else {},
            offered=bool(row.get("offered", False)), offer=offer,
            similarity=float(row.get("similarity") or 0.0),
        )

    @staticmethod
    def _bucket(claim: Mapping[str, Any]) -> str:
        return _clean(claim.get("subject") or "user", limit=160).casefold()

    def record(self, user_id: str, claim: Mapping[str, Any], *, turn_id: str,
               embedding: Sequence[float] | None, already_stored: bool,
               similarity_threshold: float = MEMORY_RECURRENCE_SIMILARITY_THRESHOLD) -> ObservedClaimRecord:
        user_key = _clean(user_id, limit=180)
        sample_signature = claim_signature(claim)
        key = recurrence_key(claim)
        clean_claim = {
            "claim_kind": _clean(claim.get("claim_kind"), limit=40),
            "subject": _clean(claim.get("subject") or "user", limit=160),
            "predicate": _clean(claim.get("predicate"), limit=160),
            "value": _clean(claim.get("value")),
        }
        if not user_key or not key or not clean_claim["predicate"] or not clean_claim["value"]:
            return ObservedClaimRecord("", "", 0, 0, 0, {}, False)
        now = float(self._clock())
        with self._lock:
            payload = self._read()
            rows = payload.setdefault("users", {}).setdefault(user_key, {})
            exact_existing = next((
                row_signature
                for row_signature, row in rows.items()
                if isinstance(row, Mapping)
                and str(row.get("recurrence_key") or recurrence_key(row.get("sample_claim", {}))) == key
            ), "")
            cluster_signature = exact_existing or key
            similarity = 1.0 if cluster_signature in rows else 0.0
            if cluster_signature not in rows and embedding:
                candidates = [
                    (row_signature, self._cosine(embedding, row.get("representative_embedding", ())))
                    for row_signature, row in rows.items()
                    if isinstance(row, Mapping)
                    and row.get("bucket") == self._bucket(clean_claim)
                    and row.get("representative_embedding")
                ]
                if candidates:
                    best_signature, best_similarity = max(candidates, key=lambda item: item[1])
                    if best_similarity >= float(similarity_threshold):
                        cluster_signature, similarity = best_signature, best_similarity
            previous = rows.get(cluster_signature, {}) if isinstance(rows.get(cluster_signature), Mapping) else {}
            same_turn = str(previous.get("last_turn_id") or "") == str(turn_id or "")
            count = int(previous.get("count") or 0) + (0 if same_turn else 1)
            offered = bool(previous.get("offered", False))
            offer = count >= MEMORY_RECURRENCE_THRESHOLD and not offered and not already_stored
            row = {
                "signature": cluster_signature,
                "recurrence_key": key,
                "claim_signature": sample_signature,
                "count": count,
                "first_seen": float(previous.get("first_seen") or now),
                "last_seen": now,
                "sample_claim": clean_claim,
                "offered": offered or offer,
                "last_turn_id": str(turn_id or ""),
                "bucket": self._bucket(clean_claim),
                "representative_embedding": list(previous.get("representative_embedding", ()))
                or (list(embedding) if embedding else []),
                "similarity": similarity,
            }
            rows[cluster_signature] = row
            if len(rows) > self._cap:
                ordered = sorted(rows, key=lambda item: float(rows[item].get("last_seen") or 0))
                for stale in ordered[:len(rows) - self._cap]:
                    rows.pop(stale, None)
            self._write(payload)
            return self._record(row, offer=offer)

    def rows_for_user(self, user_id: str) -> tuple[ObservedClaimRecord, ...]:
        with self._lock:
            rows = self._read().get("users", {}).get(_clean(user_id, limit=180), {})
            return tuple(self._record(row) for row in rows.values() if isinstance(row, Mapping))

    def clear_user(self, user_id: str) -> int:
        user_key = _clean(user_id, limit=180)
        if not user_key:
            return 0
        with self._lock:
            payload = self._read()
            users = payload.setdefault("users", {})
            rows = users.pop(user_key, None)
            if not isinstance(rows, Mapping):
                return 0
            self._write(payload)
            return len(rows)
