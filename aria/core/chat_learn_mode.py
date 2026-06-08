from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import threading
from pathlib import Path
from typing import Any

from aria.core.learned_recipe_curator import CURATION_POLICY_CONTEXT_ONLY
from aria.core.learned_recipe_curator import CURATION_STATUS_SKIPPED
from aria.core.learned_recipe_curator import curate_learned_recipe_entry
from aria.core.learned_recipe_store import save_learned_recipe_store_entry
from aria.core.learned_recipe_store_contract import normalize_learned_recipe_store_entry

_CHAT_LEARN_LOCK = threading.RLock()
_COMMAND_START = {"/lernen start", "/learn start", "/rezept lernen", "/recipe learn"}
_COMMAND_STOP = {"/lernen stop", "/learn stop", "/rezept fertig", "/recipe done"}
_COMMAND_CANCEL = {"/lernen abbrechen", "/learn cancel", "/rezept abbrechen", "/recipe cancel"}
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(password|passwort|secret|token|api[_-]?key|authorization)\b\s*[:=]\s*([^\s,;]+)"
)
_CONNECTION_LINE_RE = re.compile(r"`([a-z0-9_./-]+)/([a-zA-Z0-9_.:-]+)`")
_RUNTIME_REF_KIND_RE = re.compile(r"\bref=([a-zA-Z0-9_.:-]+)\s+kind=([a-z0-9_./-]+)\b")
_EXECUTED_VIA_RE = re.compile(r"`([^`]+)`")
_COMMAND_LINE_RE = re.compile(r"^(?:Befehl|Command|Pfad|Path|Zeitraum|Range):\s*(.+)$", re.IGNORECASE)


def parse_chat_learn_command(message: str) -> str:
    clean = re.sub(r"\s+", " ", str(message or "").strip().lower())
    if clean in _COMMAND_START:
        return "start"
    if clean in _COMMAND_STOP:
        return "stop"
    if clean in _COMMAND_CANCEL:
        return "cancel"
    return ""


def chat_learn_sessions_path(base_dir: Path) -> Path:
    path = Path(base_dir) / "data" / "runtime" / "chat_learn_sessions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _session_key(username: str, session_id: str) -> str:
    user = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(username or "web").strip())[:80] or "web"
    session = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(session_id or "default").strip())[:120] or "default"
    return f"{user}:{session}"


def _read_sessions(base_dir: Path) -> dict[str, Any]:
    path = chat_learn_sessions_path(base_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"sessions": {}}
    if not isinstance(payload, dict):
        return {"sessions": {}}
    sessions = payload.get("sessions", {})
    if not isinstance(sessions, dict):
        sessions = {}
    return {"sessions": sessions}


def _write_sessions(base_dir: Path, payload: dict[str, Any]) -> None:
    path = chat_learn_sessions_path(base_dir)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: Any, *, max_len: int = 1400) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    text = _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[redacted]", text)
    return text[:max_len].strip()


def chat_learn_mode_active(base_dir: Path, *, username: str, session_id: str) -> bool:
    key = _session_key(username, session_id)
    with _CHAT_LEARN_LOCK:
        session = _read_sessions(base_dir).get("sessions", {}).get(key, {})
    return bool(isinstance(session, dict) and session.get("active"))


def chat_learn_mode_event_count(base_dir: Path, *, username: str, session_id: str) -> int:
    key = _session_key(username, session_id)
    with _CHAT_LEARN_LOCK:
        session = _read_sessions(base_dir).get("sessions", {}).get(key, {})
    if not isinstance(session, dict):
        return 0
    events = session.get("events", [])
    return len(events) if isinstance(events, list) else 0


def start_chat_learn_mode(base_dir: Path, *, username: str, session_id: str) -> dict[str, Any]:
    key = _session_key(username, session_id)
    session = {
        "active": True,
        "username": str(username or "").strip(),
        "session_id": str(session_id or "").strip(),
        "started_at": _now(),
        "events": [],
    }
    with _CHAT_LEARN_LOCK:
        payload = _read_sessions(base_dir)
        sessions = dict(payload.get("sessions", {}) or {})
        sessions[key] = session
        _write_sessions(base_dir, {"sessions": sessions})
    return dict(session)


def cancel_chat_learn_mode(base_dir: Path, *, username: str, session_id: str) -> int:
    key = _session_key(username, session_id)
    with _CHAT_LEARN_LOCK:
        payload = _read_sessions(base_dir)
        sessions = dict(payload.get("sessions", {}) or {})
        session = sessions.pop(key, {})
        _write_sessions(base_dir, {"sessions": sessions})
    events = session.get("events", []) if isinstance(session, dict) else []
    return len(events) if isinstance(events, list) else 0


def _extract_scope_from_details(details: list[str]) -> dict[str, list[str]]:
    kinds: list[str] = []
    refs: list[str] = []
    actions: list[str] = []
    for raw in details:
        line = str(raw or "").strip()
        for ref, kind in _RUNTIME_REF_KIND_RE.findall(line):
            if kind and kind not in kinds:
                kinds.append(kind)
            if ref and ref not in refs:
                refs.append(ref)
        for kind, ref in _CONNECTION_LINE_RE.findall(line):
            if kind and kind not in kinds:
                kinds.append(kind)
            if ref and ref not in refs:
                refs.append(ref)
        if "Executed via" in line or ("`" in line and "Routing " not in line and "Debug" not in line):
            match = _EXECUTED_VIA_RE.search(line)
            if match and match.group(1) and match.group(1) not in refs:
                refs.append(match.group(1))
        command = _COMMAND_LINE_RE.match(line)
        if command:
            action = _redact(command.group(1), max_len=220)
            if action and action not in actions:
                actions.append(action)
    return {"connection_kinds": kinds, "connection_refs": refs, "actions": actions}


def append_chat_learn_observation(
    base_dir: Path,
    *,
    username: str,
    session_id: str,
    user_message: str,
    assistant_text: str,
    intent_label: str,
    badge_details: list[str] | None = None,
) -> bool:
    key = _session_key(username, session_id)
    details = [_redact(item, max_len=700) for item in list(badge_details or []) if str(item or "").strip()]
    scope = _extract_scope_from_details(details)
    event = {
        "recorded_at": _now(),
        "user_message": _redact(user_message, max_len=700),
        "assistant_text": _redact(assistant_text, max_len=900),
        "intent_label": _redact(intent_label, max_len=80),
        "badge_details": details[:24],
        "connection_kinds": scope["connection_kinds"],
        "connection_refs": scope["connection_refs"],
        "actions": scope["actions"],
    }
    with _CHAT_LEARN_LOCK:
        payload = _read_sessions(base_dir)
        sessions = dict(payload.get("sessions", {}) or {})
        session = sessions.get(key, {})
        if not isinstance(session, dict) or not session.get("active"):
            return False
        events = list(session.get("events", []) or [])
        events.append(event)
        session["events"] = events[-24:]
        sessions[key] = session
        _write_sessions(base_dir, {"sessions": sessions})
    return True


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", str(value or "").lower()).strip("-")
    return clean[:48].strip("-") or "chat-session"


def _keywords_from_events(events: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for event in events:
        message = str(event.get("user_message", "") or "").strip()
        if message:
            rows.append(message[:90])
        for ref in list(event.get("connection_refs", []) or []):
            rows.append(str(ref or "").strip())
        for kind in list(event.get("connection_kinds", []) or []):
            rows.append(str(kind or "").strip())
    seen: set[str] = set()
    result: list[str] = []
    for row in rows:
        clean = re.sub(r"\s+", " ", str(row or "").strip()).lower()
        if len(clean) < 3 or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= 12:
            break
    return result


def _build_review_entry(session: dict[str, Any]) -> dict[str, Any]:
    events = [dict(item or {}) for item in list(session.get("events", []) or []) if isinstance(item, dict)]
    first_message = str(events[0].get("user_message", "") if events else "").strip()
    all_kinds = list(dict.fromkeys(
        str(kind or "").strip().lower()
        for event in events
        for kind in list(event.get("connection_kinds", []) or [])
        if str(kind or "").strip()
    ))
    all_refs = list(dict.fromkeys(
        str(ref or "").strip()
        for event in events
        for ref in list(event.get("connection_refs", []) or [])
        if str(ref or "").strip()
    ))
    all_actions = list(dict.fromkeys(
        str(action or "").strip()
        for event in events
        for action in list(event.get("actions", []) or [])
        if str(action or "").strip()
    ))
    primary_kind = all_kinds[0] if all_kinds else ""
    primary_ref = all_refs[0] if all_refs else ""
    primary_action = all_actions[0] if all_actions else "review chat learning session"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = (
        f"Review-only recipe candidate from chat learn mode with {len(events)} observed turn(s). "
        "The candidate stores context and observed routing/action evidence only; it is not directly executable."
    )
    return normalize_learned_recipe_store_entry(
        {
            "recipe_id": f"chat-learn-{timestamp}-{_slug(first_message)}",
            "title": f"Chat learn mode: {first_message[:80] or 'review candidate'}",
            "summary": summary,
            "preview": primary_action,
            "intent": "chat_learn_mode",
            "connection_kind": primary_kind,
            "connection_ref": primary_ref,
            "capability": str(events[-1].get("intent_label", "") if events else "").strip(),
            "chosen_action": primary_action,
            "policy_result": "context_only",
            "execution_result": "success",
            "user_message": first_message,
            "experience_summary": summary,
            "router_keywords": _keywords_from_events(events),
            "recipe_scope": {
                "connection_kinds": all_kinds,
                "connection_refs": all_refs,
                "step_types": [str(event.get("intent_label", "") or "").strip() for event in events if str(event.get("intent_label", "") or "").strip()],
                "learning_origin": "chat_learn_mode",
                "target_scope": "review_only",
            },
            "inputs": {
                "observed_turns": str(len(events)),
                "started_at": str(session.get("started_at", "") or ""),
            },
            "experience_count": len(events),
            "last_success_at": _now(),
            "curation_source": "chat_learn_mode",
            "curation_policy": CURATION_POLICY_CONTEXT_ONLY,
            "curation_status": CURATION_STATUS_SKIPPED,
            "confidence": 0.35,
            "risk_level": "unknown",
            "generalization_hint": "Review the observed chat sequence and promote only if target scope, guardrails and action boundaries are clear.",
            "suggested_triggers": _keywords_from_events(events)[:8],
            "promotion_reason": "Explicit user-driven learn mode captured a pattern for human review.",
            "limits": [
                "Review-only candidate; do not execute automatically.",
                "Keep existing guardrails and confirmation rules in force.",
                "Do not promote if target scope or mutating behavior is unclear.",
            ],
        },
        fallback_connection_kind=primary_kind,
    )


async def finish_chat_learn_mode(
    base_dir: Path,
    *,
    username: str,
    session_id: str,
    llm_client: Any | None = None,
    language: str = "de",
) -> tuple[dict[str, Any] | None, int, str]:
    key = _session_key(username, session_id)
    with _CHAT_LEARN_LOCK:
        payload = _read_sessions(base_dir)
        sessions = dict(payload.get("sessions", {}) or {})
        session = sessions.pop(key, {})
        _write_sessions(base_dir, {"sessions": sessions})
    if not isinstance(session, dict):
        return None, 0, "not_active"
    events = [dict(item or {}) for item in list(session.get("events", []) or []) if isinstance(item, dict)]
    if not events:
        return None, 0, "empty"
    entry = save_learned_recipe_store_entry(_build_review_entry({**session, "events": events}))
    curated, _debug = await curate_learned_recipe_entry(
        llm_client=llm_client,
        entry=entry,
        language=language,
        user_id=username,
        request_id=f"chat-learn-{_slug(str(session.get('started_at', '') or 'session'))}",
    )
    return curated, len(events), "stored"
