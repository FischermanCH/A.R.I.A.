"""Native read-only NotesStore tool contribution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from pathlib import Path
from typing import Any

from aria.modules.notes.context import build_notes_store, search_note_hits
from aria.modules.sdk import NativeToolBinding, NativeToolContext, NativeToolContract, NativeToolResult

NOTES_SOURCE_AUTHORITY = "notes:markdown_store"
_SAFE_FIELDS = ("note_id", "title", "folder", "excerpt", "updated_at")
_ROW_LIMIT = 16
_EXCERPT_CHARS = 1_600


def _safe_rows(
    items: Sequence[Mapping[str, Any]], *, user_id: str,
) -> tuple[list[dict[str, str]], bool]:
    rows: list[dict[str, str]] = []
    content_truncated = False
    for item in items:
        if str(item.get("source_authority") or "") != NOTES_SOURCE_AUTHORITY:
            raise ValueError("native_agent_notes_source_authority_mismatch")
        if str(item.get("scope_user_id") or "") != user_id:
            raise ValueError("native_agent_notes_scope_mismatch")
        row = {key: str(item.get(key) or "").strip() for key in _SAFE_FIELDS}
        if len(row["excerpt"]) > _EXCERPT_CHARS:
            row["excerpt"] = row["excerpt"][:_EXCERPT_CHARS]
            content_truncated = True
        rows.append(row)
    return rows[:_ROW_LIMIT], content_truncated


async def _load(runtime_owner: Any, user_id: str, arguments: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    loader = getattr(runtime_owner, "_native_agent_notes_loader", None)
    if callable(loader):
        return await loader(user_id, arguments)
    action = str(arguments.get("action") or "inventory")
    base_dir = Path(getattr(runtime_owner, "base_dir", Path.cwd()))
    notes_root = base_dir / "data" / "notes"
    if not notes_root.is_dir():
        return ()
    store = build_notes_store(base_dir)
    if not store.has_user_scope(user_id):
        return ()
    if action == "open":
        note = store.get_note(user_id, str(arguments.get("note_id") or ""))
        notes = [note] if note is not None else []
    elif action == "search":
        hits = await search_note_hits(base_dir=base_dir, username=user_id, settings=runtime_owner.settings,
                                      query=str(arguments.get("query") or ""), limit=12)
        return tuple({"source_authority": NOTES_SOURCE_AUTHORITY, "scope_user_id": user_id,
                      "note_id": hit.note_id, "title": hit.title, "folder": hit.folder,
                      "excerpt": hit.snippet, "updated_at": hit.updated_at} for hit in hits)
    else:
        notes = store.list_notes(user_id, preview_only=True)
        folder = str(arguments.get("folder") or "").strip()
        if folder:
            notes = [note for note in notes if note.folder == folder]
    return tuple({"source_authority": NOTES_SOURCE_AUTHORITY, "scope_user_id": user_id,
                  "note_id": note.note_id, "title": note.title, "folder": note.folder,
                  "excerpt": note.body if action == "open" else note.summary,
                  "updated_at": note.updated_at} for note in notes[:_ROW_LIMIT + 1])


def native_tool_contributions(runtime_owner: Any) -> tuple[NativeToolBinding, ...]:
    async def read_notes(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"action", "query", "note_id", "folder"}
        if set(arguments) - allowed or any(not isinstance(arguments.get(key, ""), str) for key in allowed):
            raise ValueError("native_agent_notes_arguments_invalid")
        action = str(arguments.get("action") or "inventory")
        if action not in {"inventory", "search", "open"} or (action == "search" and not str(arguments.get("query") or "").strip()) or (action == "open" and not str(arguments.get("note_id") or "").strip()):
            raise ValueError("native_agent_notes_arguments_invalid")
        items = await _load(runtime_owner, context.user_id, arguments)
        rows, content_truncated = _safe_rows(items, user_id=context.user_id)
        truncated = len(items) > len(rows) or content_truncated
        payload = {"status": "ok", "notes": rows, "selection": {
            "shown": len(rows), "available": len(items), "truncated": truncated,
            "notice": "gekuerzt: Ergebnisse oder Inhalte sind ausschnittweise" if truncated else "alle ausgewaehlten Treffer sind enthalten",
        }} if rows else {
            "status": "no_notes", "notes": [], "message": "No notes match the requested scope for this user.",
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "notes")

    async def write_note(context: NativeToolContext, arguments: Mapping[str, Any]) -> NativeToolResult:
        allowed = {"note_id", "title", "body", "folder"}
        if (
            set(arguments) - allowed
            or any(not isinstance(arguments.get(key, ""), str) for key in allowed)
            or not str(arguments.get("title") or "").strip()
            or not str(arguments.get("body") or "").strip()
        ):
            raise ValueError("native_agent_notes_write_arguments_invalid")
        store = getattr(runtime_owner, "_native_agent_notes_store", None)
        if store is None:
            store = build_notes_store(Path(
                getattr(runtime_owner, "base_dir", getattr(runtime_owner, "_project_root", Path.cwd()))
            ))
        clean_title = store._normalize_title(str(arguments["title"]))
        clean_folder = store._normalize_folder(str(arguments.get("folder") or ""))
        note_id = str(arguments.get("note_id") or "").strip()
        if note_id and store.get_note(context.user_id, note_id) is None:
            return NativeToolResult(
                json.dumps({
                    "status": "not_found", "action": "updated", "note_id": note_id,
                    "title": clean_title, "folder": clean_folder,
                }, ensure_ascii=True, sort_keys=True),
                "notes_write",
            )
        action = "updated" if note_id else "created"
        if not note_id:
            matches = [
                note for note in store.list_notes(context.user_id)
                if store._normalize_title(note.title) == clean_title
                and store._normalize_folder(note.folder) == clean_folder
            ]
            if len(matches) > 1:
                return NativeToolResult(
                    json.dumps({
                        "status": "ambiguous_title", "action": "ambiguous_title", "note_id": "",
                        "title": clean_title, "folder": clean_folder,
                        "matches": sorted(str(note.note_id) for note in matches),
                    }, ensure_ascii=True, sort_keys=True),
                    "notes_write",
                )
            if matches:
                note_id = str(matches[0].note_id)
                action = "updated"
        save_kwargs = {
            "title": clean_title,
            "body": str(arguments["body"]),
            "folder": clean_folder,
        }
        if note_id:
            save_kwargs["note_id"] = note_id
        note = store.save_note(context.user_id, **save_kwargs)
        payload = {
            "status": "ok", "action": action, "note_id": str(note.note_id),
            "title": str(note.title), "folder": str(note.folder),
        }
        return NativeToolResult(json.dumps(payload, ensure_ascii=True, sort_keys=True), "notes_write")

    return (NativeToolBinding(NativeToolContract(
        owner_module_id="notes", name="notes_read_search_inventory",
        description="List, search or open the current user's notes and folders. Read-only.",
        input_schema={"type": "object", "properties": {
            "action": {"type": "string", "enum": ["inventory", "search", "open"]},
            "query": {"type": "string"}, "note_id": {"type": "string"}, "folder": {"type": "string"},
        }, "required": ["action"]}, effect="read_only", confirmation_required=False,
        source_authority=NOTES_SOURCE_AUTHORITY, user_scoped=True,
        rollout_flag="native_agent_memory_enabled", order=130,
    ), read_notes), NativeToolBinding(NativeToolContract(
        owner_module_id="notes", name="notes_write",
        description="Create or update one note for the current user after explicit confirmation.",
        input_schema={"type": "object", "properties": {
            "note_id": {"type": "string"}, "title": {"type": "string"},
            "body": {"type": "string"}, "folder": {"type": "string"},
        }, "required": ["title", "body"]},
        effect="mutating", confirmation_required=True,
        source_authority=NOTES_SOURCE_AUTHORITY, user_scoped=True,
        rollout_flag="native_agent_write_notes_enabled", order=600,
    ), write_note))
