from __future__ import annotations

import re
import json
from pathlib import PurePosixPath
from pathlib import Path
from typing import Any

from aria.core.action_plan import CapabilityDraft, MemoryHints
from aria.core.connection_semantic_resolver import build_connection_aliases, connection_label_match_score

_MEMORY_ASSIST_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "memory_assist.json"


def _load_memory_assist_lexicon() -> dict[str, Any]:
    try:
        payload = json.loads(_MEMORY_ASSIST_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


_MEMORY_ASSIST_LEXICON = _load_memory_assist_lexicon()


def _lexicon_list(name: str) -> tuple[str, ...]:
    values = _MEMORY_ASSIST_LEXICON.get(name, [])
    if not isinstance(values, list):
        return ()
    return tuple(str(value).strip().lower() for value in values if str(value).strip())


class MemoryAssistResolver:
    _GENERIC_CONNECTION_ALIASES = {
        "server",
        "host",
        "service",
        "dienst",
        "profil",
        "profile",
        "api",
        "website",
        "webseite",
        "feed",
        "mailbox",
        "postfach",
        "channel",
    }

    def __init__(self, memory_skill_getter: Any, capability_context_getter: Any | None = None) -> None:
        self._memory_skill_getter = memory_skill_getter
        self._capability_context_getter = capability_context_getter or (lambda: None)
        self._same_server_phrases = (
            "wie letztes mal",
            "wie letztes mal",
            "wie beim letzten mal",
            "wie zuvor",
            "auf dem gleichen server",
            "auf dem selben server",
            "auf demselben server",
            "auf dem gleichen host",
            "mit dem gleichen profil",
            "mit demselben profil",
            "gleiches profil",
            "selbes profil",
        )
        self._same_path_phrases = (
            "im gleichen pfad",
            "im selben pfad",
            "im gleichen ordner",
            "im selben ordner",
            "im gleichen verzeichnis",
            "im selben verzeichnis",
            "gleicher pfad",
            "gleichen pfad",
            "selber pfad",
            "selben pfad",
            "gleicher ordner",
            "gleichen ordner",
            "wie letztes mal",
            "wie beim letzten mal",
            "wieder dort",
        )

    @staticmethod
    def _match_connection_from_text(text: str, available_connections: dict[str, Any], connection_kind: str = "") -> str:
        best_ref = ""
        best_score = 0
        tied_best = False
        for ref, row in available_connections.items():
            clean_ref = str(ref).strip()
            if not clean_ref:
                continue
            for alias in build_connection_aliases(connection_kind, clean_ref, row):
                if str(alias or "").strip().lower() in MemoryAssistResolver._GENERIC_CONNECTION_ALIASES:
                    continue
                score = connection_label_match_score(text, alias)
                if score > best_score:
                    best_ref = clean_ref
                    best_score = score
                    tied_best = False
                elif score > 0 and score == best_score and clean_ref != best_ref:
                    tied_best = True
        if best_score <= 0 or tied_best:
            return ""
        return best_ref

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip().lower()

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        clean_phrase = str(phrase or "").strip().lower()
        if not clean_phrase:
            return False
        return bool(re.search(rf"(?<!\w){re.escape(clean_phrase)}(?!\w)", text))

    def _looks_like_plural_target_request(self, message: str, connection_kind: str) -> bool:
        clean = self._normalize(message)
        if not clean:
            return False
        for pattern in _lexicon_list("plural_target_patterns"):
            try:
                if re.search(pattern, clean, flags=re.IGNORECASE):
                    return True
            except re.error:
                continue
        kind_key = f"plural_target_terms_{str(connection_kind or '').strip().lower()}"
        terms = _lexicon_list(kind_key) or _lexicon_list("plural_target_terms")
        return any(self._contains_phrase(clean, term) for term in terms)

    def _wants_previous_connection(self, message: str) -> bool:
        clean = self._normalize(message)
        return any(phrase in clean for phrase in self._same_server_phrases)

    def _wants_previous_path(self, message: str) -> bool:
        clean = self._normalize(message)
        return any(phrase in clean for phrase in self._same_path_phrases)

    @staticmethod
    def _path_hint_from_recent(message: str, recent_path: str, *, recent_capability: str = "") -> str:
        clean_message = str(message or "").lower()
        clean_path = str(recent_path or "").strip()
        if not clean_path:
            return ""
        if any(token in clean_message for token in ("ordner", "verzeichnis", "directory", "folder")):
            parsed_path = PurePosixPath(clean_path)
            if str(recent_capability or "").strip() == "file_list" and not parsed_path.suffix:
                return clean_path
            parent = str(parsed_path.parent).strip()
            return parent or clean_path
        return clean_path

    async def resolve(
        self,
        *,
        draft: CapabilityDraft,
        message: str,
        user_id: str,
        available_connections: dict[str, Any],
    ) -> MemoryHints:
        direct_match = self._match_connection_from_text(message, available_connections, draft.connection_kind)
        wants_previous_connection = self._wants_previous_connection(message)
        wants_previous_path = self._wants_previous_path(message)
        plural_target_request = self._looks_like_plural_target_request(message, draft.connection_kind)

        recent_context_store = self._capability_context_getter()
        recent_context = {}
        if recent_context_store is not None and hasattr(recent_context_store, "load_recent"):
            try:
                recent_context = recent_context_store.load_recent(user_id)
            except Exception:
                recent_context = {}

        if (wants_previous_connection or wants_previous_path) and isinstance(recent_context, dict):
            recent_ref = str(recent_context.get("connection_ref", "")).strip()
            recent_kind = str(recent_context.get("connection_kind", "")).strip()
            recent_capability = str(recent_context.get("capability", "")).strip()
            recent_path = str(recent_context.get("path", "")).strip()
            if recent_kind == draft.connection_kind and (recent_ref or recent_path):
                path_hint = self._path_hint_from_recent(
                    message,
                    recent_path,
                    recent_capability=recent_capability,
                )
                notes: list[str] = []
                if wants_previous_connection and recent_ref:
                    notes.append(f"context_connection:{recent_ref}")
                if wants_previous_path and path_hint:
                    notes.append(f"context_path:{path_hint}")
                draft_path = str(draft.path or "").strip()
                return MemoryHints(
                    connection_kind=recent_kind,
                    connection_ref=direct_match or recent_ref,
                    path=path_hint if wants_previous_path and draft_path in {"", "."} else "",
                    source="recent_context",
                    matched_text="",
                    notes=notes,
                )

        if direct_match:
            return MemoryHints(connection_kind=draft.connection_kind, connection_ref=direct_match, source="message_match")

        requested_ref = str(getattr(draft, "requested_connection_ref", "") or "").strip()
        if requested_ref:
            # If the user named a concrete target phrase that we could not map
            # deterministically, do not let stale memory silently override it.
            return MemoryHints()

        if plural_target_request:
            return MemoryHints()

        memory_skill = self._memory_skill_getter()
        if memory_skill is None or not hasattr(memory_skill, "search_memories"):
            return MemoryHints()

        try:
            rows = await memory_skill.search_memories(user_id=user_id, query=message, type_filter="all", top_k=10)
        except Exception:
            return MemoryHints()

        if not isinstance(rows, list):
            return MemoryHints()

        scores: dict[str, int] = {}
        match_text = ""
        for row in rows:
            text = str(row.get("text", "")).strip()
            ref = self._match_connection_from_text(text, available_connections, draft.connection_kind)
            if not ref:
                continue
            scores[ref] = scores.get(ref, 0) + 1
            if not match_text:
                match_text = text

        if not scores:
            return MemoryHints()

        best_ref = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0][0]
        return MemoryHints(
            connection_kind=draft.connection_kind,
            connection_ref=best_ref,
            source="memory_hint",
            matched_text=match_text,
            notes=[f"memory_hint:{best_ref}"],
        )
