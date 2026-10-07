"""Per-user bounded memory of the last native actionable tool sequence."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping, Sequence

SIMILARITY_THRESHOLD = 0.88


@dataclass(frozen=True)
class ActionableCall:
    tool_name: str
    arguments: dict[str, Any]
    outcome: str


@dataclass(frozen=True)
class ActionableSequence:
    turn_id: str
    intent: str
    calls: tuple[ActionableCall, ...]


_ACTIONABLE_STEP_TYPES = {
    "file_read": "{kind}_read", "file_write": "{kind}_write", "file_list": "{kind}_list",
    "discord_send": "discord_send", "webhook_send": "webhook_send", "email_send": "email_send",
    "mqtt_publish": "mqtt_publish", "http_api_request": "http_api_request",
    "mail_read": "imap_read", "mail_search": "imap_search", "calendar_read": "calendar_read",
}


def actionable_sequence_to_recipe_steps(sequence: ActionableSequence) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for call in sequence.calls:
        args = dict(call.arguments)
        if call.tool_name in {"ssh_command", "ssh_read"}:
            targets = args.get("targets", ())
            targets = targets if isinstance(targets, Sequence) and not isinstance(targets, str) else ()
            for target in targets:
                params: dict[str, Any] = {
                    "connection_ref": str(target), "command": str(args.get("command") or ""),
                }
                if isinstance(args.get("timeout"), int):
                    params["timeout_seconds"] = args["timeout"]
                rows.append({"type": "ssh_run", "params": params})
            continue
        kind = str(args.get("connection_kind") or "").strip()
        pattern = _ACTIONABLE_STEP_TYPES.get(call.tool_name, "")
        step_type = pattern.format(kind=kind) if pattern else ""
        if not step_type:
            continue
        params = {key: value for key, value in args.items() if key != "connection_kind"}
        if "path" in params:
            params["remote_path"] = params.pop("path")
        if call.tool_name == "discord_send" and "content" in params:
            params["message"] = params.pop("content")
        rows.append({"type": step_type, "params": params})
    return [{
        "id": f"s{index}", "name": f"Remembered {row['type']}",
        "type": row["type"], "params": row["params"], "on_error": "stop",
    } for index, row in enumerate(rows, 1)]


def _normalized_signature_value(value: Any) -> str:
    return " ".join(str(value or "").split())


def primary_action_recurrence_key(
    steps: Sequence[Mapping[str, Any]],
) -> tuple[str, str, str]:
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        step_type = str(step.get("type") or "").strip()
        params = step.get("params", {})
        if not step_type or not isinstance(params, Mapping):
            continue
        key_text = next((
            str(params.get(key) or "").strip()
            for key in ("command", "remote_path", "path", "request_path", "topic", "query")
            if str(params.get(key) or "").strip()
        ), "")
        return step_type, str(params.get("connection_ref") or "").strip(), key_text
    return "", "", ""


def recipe_steps_signature(steps: Sequence[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for step in steps:
        step_type = str(step.get("type") or "").strip()
        params = step.get("params", {})
        if not step_type or not isinstance(params, Mapping):
            continue
        connection_ref = _normalized_signature_value(params.get("connection_ref"))
        action = next((
            _normalized_signature_value(params.get(key))
            for key in ("command", "remote_path", "path", "request_path", "topic", "query")
            if _normalized_signature_value(params.get(key))
        ), "")
        parts.append(f"{step_type}:{connection_ref}:{action}")
    return "|".join(parts)


def actionable_sequence_signature(sequence: ActionableSequence) -> str:
    return recipe_steps_signature(actionable_sequence_to_recipe_steps(sequence))


def short_signature_hash(signature: str) -> str:
    return hashlib.sha256(str(signature).encode("utf-8")).hexdigest()[:12] if signature else ""


@dataclass(frozen=True)
class ObservedSequenceRecord:
    signature: str
    count: int
    first_seen: float
    last_seen: float
    sample_intent: str
    steps: tuple[dict[str, Any], ...]
    last_outcome: str
    offered: bool
    offer: bool = False
    similarity: float = 0.0


class ObservedSequenceStore:
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
    def _record(row: Mapping[str, Any], *, offer: bool = False) -> ObservedSequenceRecord:
        return ObservedSequenceRecord(
            signature=str(row.get("signature") or ""), count=int(row.get("count") or 0),
            first_seen=float(row.get("first_seen") or 0), last_seen=float(row.get("last_seen") or 0),
            sample_intent=str(row.get("sample_intent") or ""),
            steps=tuple(dict(step) for step in row.get("steps", ()) if isinstance(step, Mapping)),
            last_outcome="blocked" if row.get("last_outcome") == "blocked" else "success",
            offered=bool(row.get("offered", False)), offer=offer,
            similarity=float(row.get("similarity") or 0.0),
        )

    @staticmethod
    def _bucket(steps: Sequence[Mapping[str, Any]]) -> str:
        if not steps:
            return ""
        first = steps[0]
        params = first.get("params", {}) if isinstance(first, Mapping) else {}
        return f"{first.get('type', '')}:{params.get('connection_ref', '')}" if isinstance(params, Mapping) else ""

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sum(value * value for value in left) ** 0.5
        right_norm = sum(value * value for value in right) ** 0.5
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def record(self, user_id: str, sequence: ActionableSequence, *,
               existing_recipes: Sequence[Mapping[str, Any]],
               embedding: Sequence[float] | None = None,
               similarity_threshold: float = SIMILARITY_THRESHOLD) -> ObservedSequenceRecord:
        key = str(user_id or "").strip()
        signature = actionable_sequence_signature(sequence)
        if not key or not signature:
            return ObservedSequenceRecord("", 0, 0, 0, "", (), "success", False, False)
        steps = actionable_sequence_to_recipe_steps(sequence)
        now = float(self._clock())
        existing_signatures = {
            recipe_steps_signature(tuple(recipe.get("steps", ()) or ()))
            for recipe in existing_recipes if isinstance(recipe, Mapping)
        }
        with self._lock:
            payload = self._read()
            users = payload.setdefault("users", {})
            rows = users.setdefault(key, {})
            cluster_signature = signature
            similarity = 1.0 if signature in rows else 0.0
            if signature not in rows and embedding:
                bucket = self._bucket(steps)
                candidates = [
                    (row_signature, self._cosine(embedding, row.get("embedding", ())))
                    for row_signature, row in rows.items()
                    if isinstance(row, Mapping) and row.get("bucket") == bucket and row.get("embedding")
                ]
                if candidates:
                    best_signature, best_similarity = max(candidates, key=lambda item: item[1])
                    similarity = best_similarity
                    if best_similarity >= float(similarity_threshold):
                        cluster_signature = best_signature
            previous = rows.get(cluster_signature, {}) if isinstance(rows.get(cluster_signature), Mapping) else {}
            same_turn = str(previous.get("last_turn_id") or "") == str(sequence.turn_id)
            count = int(previous.get("count") or 0) + (0 if same_turn else 1)
            offered = bool(previous.get("offered", False))
            offer = count >= 3 and not offered and cluster_signature not in existing_signatures
            row = {
                "signature": cluster_signature, "count": count,
                "first_seen": float(previous.get("first_seen") or now), "last_seen": now,
                "sample_intent": str(sequence.intent or "")[:1500], "steps": steps,
                "last_outcome": "blocked" if any(call.outcome == "blocked" for call in sequence.calls) else "success",
                "offered": offered or offer, "last_turn_id": str(sequence.turn_id),
                "bucket": self._bucket(steps),
                "embedding": list(embedding) if embedding else list(previous.get("embedding", ())),
                "similarity": similarity,
            }
            rows[cluster_signature] = row
            if len(rows) > self._cap:
                ordered = sorted(rows, key=lambda item: float(rows[item].get("last_seen") or 0))
                for stale in ordered[:len(rows) - self._cap]:
                    rows.pop(stale, None)
            self._write(payload)
            return self._record(row, offer=offer)

    def claim_cross_host_offer(self, user_id: str, *, recipe_id: str, new_host: str) -> bool:
        key = str(user_id or "").strip()
        pair = f"{str(recipe_id).strip()}\0{str(new_host).strip()}"
        if not key or not pair.strip("\0"):
            return False
        with self._lock:
            payload = self._read()
            offered = payload.setdefault("cross_host_offers", {}).setdefault(key, [])
            if pair in offered:
                return False
            offered.append(pair)
            self._write(payload)
            return True

    def get(self, user_id: str, signature: str) -> ObservedSequenceRecord | None:
        with self._lock:
            row = self._read().get("users", {}).get(str(user_id), {}).get(str(signature))
            return self._record(row) if isinstance(row, Mapping) else None

    def rows_for_user(self, user_id: str) -> tuple[ObservedSequenceRecord, ...]:
        with self._lock:
            rows = self._read().get("users", {}).get(str(user_id), {})
            return tuple(self._record(row) for row in rows.values() if isinstance(row, Mapping))

    def clear_user(self, user_id: str) -> int:
        key = str(user_id or "").strip()
        if not key:
            return 0
        with self._lock:
            payload = self._read()
            users = payload.setdefault("users", {})
            rows = users.pop(key, None)
            cross_host_offers = payload.get("cross_host_offers")
            removed_offer = isinstance(cross_host_offers, dict) and cross_host_offers.pop(key, None) is not None
            if not isinstance(rows, Mapping) and not removed_offer:
                return 0
            self._write(payload)
            return len(rows) if isinstance(rows, Mapping) else 0


class LastActionableSequenceStore:
    def __init__(self, *, ttl_seconds: int = 900, clock: Callable[[], float] = time.time) -> None:
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._clock = clock
        self._lock = threading.RLock()
        self._rows: dict[str, tuple[float, ActionableSequence]] = {}

    def append(self, user_id: str, *, turn_id: str, intent: str, tool_name: str,
               arguments: Mapping[str, Any], outcome: str) -> None:
        key = str(user_id or "").strip()
        if not key:
            return
        call = ActionableCall(tool_name=str(tool_name), arguments=dict(arguments),
                              outcome="blocked" if outcome == "blocked" else "success")
        now = self._clock()
        with self._lock:
            current = self._rows.get(key)
            calls = current[1].calls if current and current[1].turn_id == turn_id else ()
            self._rows[key] = (now + self._ttl_seconds, ActionableSequence(
                turn_id=str(turn_id), intent=str(intent)[:1500], calls=(*calls, call),
            ))

    def get(self, user_id: str) -> ActionableSequence | None:
        key = str(user_id or "").strip()
        now = self._clock()
        with self._lock:
            row = self._rows.get(key)
            if row is None:
                return None
            if row[0] <= now:
                self._rows.pop(key, None)
                return None
            return row[1]


LAST_ACTIONABLE_SEQUENCE_STORE = LastActionableSequenceStore()


@dataclass(frozen=True)
class CrossHostRecipeSuggestion:
    recipe_id: str
    recipe_name: str
    source_host: str
    new_host: str
    steps: tuple[dict[str, Any], ...]
    similarity: float


class CrossHostRecipeSuggestionStore:
    def __init__(self, *, ttl_seconds: int = 900, clock: Callable[[], float] = time.time) -> None:
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._clock = clock
        self._lock = threading.RLock()
        self._rows: dict[str, tuple[float, CrossHostRecipeSuggestion]] = {}

    def put(self, user_id: str, suggestion: CrossHostRecipeSuggestion) -> None:
        with self._lock:
            self._rows[str(user_id)] = (self._clock() + self._ttl_seconds, suggestion)

    def get(self, user_id: str) -> CrossHostRecipeSuggestion | None:
        with self._lock:
            row = self._rows.get(str(user_id))
            if row is None or row[0] <= self._clock():
                self._rows.pop(str(user_id), None)
                return None
            return row[1]

    def consume(self, user_id: str) -> CrossHostRecipeSuggestion | None:
        suggestion = self.get(user_id)
        if suggestion is not None:
            with self._lock:
                self._rows.pop(str(user_id), None)
        return suggestion


CROSS_HOST_RECIPE_SUGGESTIONS = CrossHostRecipeSuggestionStore()
