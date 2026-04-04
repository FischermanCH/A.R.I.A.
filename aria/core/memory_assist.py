from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

from aria.core.action_plan import CapabilityDraft, MemoryHints
from aria.core.connection_semantic_resolver import build_connection_aliases, connection_label_match_score


class MemoryAssistResolver:
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
        for ref, row in available_connections.items():
            clean_ref = str(ref).strip()
            if not clean_ref:
                continue
            for alias in build_connection_aliases(connection_kind, clean_ref, row):
                score = connection_label_match_score(text, alias)
                if score > best_score:
                    best_ref = clean_ref
                    best_score = score
        return best_ref if best_score > 0 else ""

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip().lower()

    def _wants_previous_connection(self, message: str) -> bool:
        clean = self._normalize(message)
        return any(phrase in clean for phrase in self._same_server_phrases)

    def _wants_previous_path(self, message: str) -> bool:
        clean = self._normalize(message)
        return any(phrase in clean for phrase in self._same_path_phrases)

    @staticmethod
    def _path_hint_from_recent(message: str, recent_path: str) -> str:
        clean_message = str(message or "").lower()
        clean_path = str(recent_path or "").strip()
        if not clean_path:
            return ""
        if any(token in clean_message for token in ("ordner", "verzeichnis", "directory", "folder")):
            parent = str(PurePosixPath(clean_path).parent).strip()
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
            recent_path = str(recent_context.get("path", "")).strip()
            if recent_kind == draft.connection_kind and (recent_ref or recent_path):
                path_hint = self._path_hint_from_recent(message, recent_path)
                notes: list[str] = []
                if wants_previous_connection and recent_ref:
                    notes.append(f"context_connection:{recent_ref}")
                if wants_previous_path and path_hint:
                    notes.append(f"context_path:{path_hint}")
                return MemoryHints(
                    connection_kind=recent_kind,
                    connection_ref=direct_match or recent_ref,
                    path=path_hint if wants_previous_path and not str(draft.path or "").strip() else "",
                    source="recent_context",
                    matched_text="",
                    notes=notes,
                )

        if direct_match:
            return MemoryHints(connection_kind=draft.connection_kind, connection_ref=direct_match, source="message_match")

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
