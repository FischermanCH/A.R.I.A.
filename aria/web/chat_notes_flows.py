from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from urllib.parse import quote_plus

from aria.core.i18n import I18NStore
from aria.core.notes_magic import (
    fetch_web_note_source,
    infer_note_folder,
    infer_note_tags,
    infer_note_title,
)
from aria.core.notes_context import (
    build_notes_store,
    note_context_block,
    notes_index_enabled,
    search_note_hits,
)
from aria.core.notes_store import NotesStore, NotesStoreError
from aria.skills.web_search import WebSearchSkill


@dataclass(frozen=True)
class ChatNotesOutcome:
    handled: bool
    assistant_text: str
    icon: str = "📝"
    intent_label: str = "notes"


_CHAT_NOTES_LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "chat_notes.json"


def _load_chat_notes_lexicon() -> dict[str, object]:
    try:
        raw = json.loads(_CHAT_NOTES_LEXICON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load chat notes lexicon: {_CHAT_NOTES_LEXICON_PATH}") from exc
    return raw if isinstance(raw, dict) else {}


_CHAT_NOTES_LEXICON = _load_chat_notes_lexicon()
_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _load_pattern_group(name: str, *, dotall: bool = False) -> tuple[re.Pattern[str], ...]:
    flags = re.IGNORECASE | (re.DOTALL if dotall else 0)
    pattern_groups = _CHAT_NOTES_LEXICON.get("patterns", {})
    if not isinstance(pattern_groups, dict):
        pattern_groups = {}
    patterns = pattern_groups.get(name, [])
    if not isinstance(patterns, list):
        patterns = []
    return tuple(re.compile(str(pattern), flags) for pattern in patterns if str(pattern).strip())


def _lexicon_terms(name: str) -> set[str]:
    raw = _CHAT_NOTES_LEXICON.get(name, [])
    if not isinstance(raw, list):
        return set()
    return {str(value).strip().lower() for value in raw if str(value).strip()}


def _text(key: str, default: str, **values: object) -> str:
    template = _I18N.t("de", key, default)
    try:
        return template.format(**values)
    except Exception:
        return template


def _optional_folder_line(folder: str | None) -> str:
    clean_folder = str(folder or "").strip()
    if not clean_folder:
        return ""
    return _text("chat_notes.optional_folder_line", "Folder: {folder}\n\n", folder=clean_folder)


def _optional_tags_line(tags: list[str] | tuple[str, ...]) -> str:
    clean_tags = ", ".join(str(tag).strip() for tag in tags if str(tag).strip())
    if not clean_tags:
        return ""
    return _text("chat_notes.optional_tags_line", "Tags: {tags}\n\n", tags=clean_tags)


_OPEN_NOTES_PATTERNS = _load_pattern_group("open_notes")
_SEARCH_NOTES_PATTERNS = _load_pattern_group("search_notes")
_LIST_NOTE_FOLDERS_PATTERNS = _load_pattern_group("list_note_folders")
_LIST_NOTES_IN_FOLDER_PATTERNS = _load_pattern_group("list_notes_in_folder")
_OPEN_NOTE_PATTERNS = _load_pattern_group("open_note")
_CREATE_NOTE_PATTERNS = _load_pattern_group("create_note", dotall=True)
_QUICK_NOTE_PATTERNS = _load_pattern_group("quick_note", dotall=True)
_NATURAL_NOTE_PATTERNS = _load_pattern_group("natural_note", dotall=True)
_WEB_SEARCH_WITH_NOTES_PATTERNS = _load_pattern_group("web_search_with_notes", dotall=True)
_SAVE_WEB_SOURCE_PATTERNS = _load_pattern_group("save_web_source")
_OPEN_FOLDER_VERBS = _lexicon_terms("open_folder_verbs")


def _store(base_dir: Path) -> NotesStore:
    return build_notes_store(base_dir)


def _notes_link(note_id: str | None = None) -> str:
    if note_id:
        return f"/notes?note={note_id}#note-editor"
    return "/notes"


def _notes_folder_link(folder: str) -> str:
    return f"/notes?folder={quote_plus(str(folder or '').strip())}"


def _folder_matches(note_folder: str, selected_folder: str) -> bool:
    clean_folder = str(note_folder or "").strip()
    clean_selected = str(selected_folder or "").strip().strip("/")
    if not clean_selected:
        return not clean_folder
    return clean_folder == clean_selected or clean_folder.startswith(f"{clean_selected}/")


async def _persist_note(
    *,
    base_dir: Path,
    username: str,
    settings: object,
    title: str,
    body: str,
    folder: str,
    tags: list[str] | None = None,
) -> tuple[object | None, str, str | None]:
    try:
        note = _store(base_dir).save_note(username, title=title, body=body, folder=folder, tags=tags or [])
    except NotesStoreError as exc:
        return None, _text("chat_notes.note_save_failed", "The note could not be saved: {error}", error=exc), None
    if notes_index_enabled(settings):
        from aria.core.notes_index import NotesIndex

        notes_index = NotesIndex(
            settings.memory,
            settings.embeddings,
            usage_meter=getattr(settings, "_aria_usage_meter", None),
        )
        try:
            await notes_index.reindex_note(note)
            index_hint = _text("chat_notes.index_updated", "Qdrant index updated.")
        except Exception as exc:  # noqa: BLE001
            index_hint = _text("chat_notes.index_update_failed", "Qdrant index could not be updated yet: {error}", error=exc)
        finally:
            await notes_index.aclose()
    else:
        index_hint = _text(
            "chat_notes.index_inactive",
            "Qdrant index is not active right now. The Markdown note is still saved.",
        )
    return note, index_hint, None


async def handle_chat_notes_flow(
    *,
    clean_message: str,
    username: str,
    base_dir: Path,
    settings: object,
) -> ChatNotesOutcome | None:
    text = str(clean_message or "").strip()
    if not text:
        return None

    for pattern in _OPEN_NOTES_PATTERNS:
        if pattern.match(text):
            notes = _store(base_dir).list_notes(username)
            return ChatNotesOutcome(
                handled=True,
                assistant_text=(
                    _text("chat_notes.open_notes", "Your notes are here: `{link}`\n\nCurrently available: {count}", link=_notes_link(), count=len(notes))
                ),
            )

    for pattern in _LIST_NOTE_FOLDERS_PATTERNS:
        if not pattern.match(text):
            continue
        folders = _store(base_dir).list_folders(username)
        if not folders:
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.no_folders",
                    "You do not have note folders yet. Start here: `{link}?new=1`",
                    link=_notes_link(),
                ),
            )
        lines = [_text("chat_notes.folder_list_heading", "Your note folders:")]
        for folder in folders[:12]:
            lines.append(f"- {folder}\n  `{_notes_link()}?folder={folder}`")
        return ChatNotesOutcome(handled=True, assistant_text="\n\n".join(lines))

    for pattern in _LIST_NOTES_IN_FOLDER_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        verb = str(match.groupdict().get("verb") or "").strip().lower()
        store = _store(base_dir)
        folder = str(match.group("folder") or "").strip().strip("/")
        resolved_folder = store.resolve_folder_name(username, folder)
        notes = [note for note in store.list_notes(username) if _folder_matches(note.folder, resolved_folder)]
        if not notes:
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.no_notes_in_folder",
                    "I found no notes in `{folder}` right now. Open: `{link}`",
                    folder=resolved_folder or folder,
                    link=_notes_folder_link(resolved_folder or folder),
                ),
            )
        if verb in _OPEN_FOLDER_VERBS:
            lines = [
                _text(
                    "chat_notes.open_folder",
                    "Open the note folder `{folder}` here: `{link}`",
                    folder=resolved_folder,
                    link=_notes_folder_link(resolved_folder),
                ),
                "",
                _text("chat_notes.existing_notes_heading", "Existing notes:"),
            ]
            for note in notes[:8]:
                lines.append(f"- {note.title}")
            return ChatNotesOutcome(handled=True, assistant_text="\n".join(lines))
        lines = [_text("chat_notes.notes_in_folder_heading", "Notes in `{folder}`:", folder=resolved_folder)]
        for note in notes[:8]:
            lines.append(f"- {note.title}\n  `{_notes_link(note.note_id)}`")
        return ChatNotesOutcome(handled=True, assistant_text="\n\n".join(lines))

    for pattern in _OPEN_NOTE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        query = str(match.group("query") or "").strip()
        hits = await search_note_hits(base_dir=base_dir, username=username, settings=settings, query=query, limit=3)
        if hits:
            top = hits[0]
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.open_matching_note",
                    "Open matching note: **{title}**\n\n`{link}`",
                    title=top.title or _text("chat_notes.note_fallback", "Note"),
                    link=_notes_link(str(top.note_id or "").strip()),
                ),
            )
        notes = _store(base_dir).list_notes(username)
        lowered = query.lower()
        fallback = next((note for note in notes if lowered in note.title.lower()), None)
        if fallback is not None:
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.open_matching_note",
                    "Open matching note: **{title}**\n\n`{link}`",
                    title=fallback.title,
                    link=_notes_link(fallback.note_id),
                ),
            )
        return ChatNotesOutcome(
            handled=True,
            assistant_text=_text(
                "chat_notes.note_not_found",
                "I found no note for `{query}`. Search: `{link}?q={query}`",
                query=query,
                link=_notes_link(),
            ),
        )

    for pattern in _SEARCH_NOTES_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        query = str(match.group("query") or "").strip()
        hits = await search_note_hits(base_dir=base_dir, username=username, settings=settings, query=query, limit=5)
        if not hits:
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.no_search_results",
                    "I found nothing matching `{query}` in your notes right now. Open: `{link}`",
                    query=query,
                    link=_notes_link(),
                ),
            )
        lines = [_text("chat_notes.search_results_heading", "Matching notes for `{query}`:", query=query)]
        for index, hit in enumerate(hits, start=1):
            folder = str(hit.folder or "").strip() or "Inbox"
            lines.append(
                f"- [{index}] {hit.title or _text('chat_notes.note_fallback', 'Note')} · {folder}\n"
                f"  `{_notes_link(str(hit.note_id or '').strip())}`\n  {hit.snippet}"
            )
        return ChatNotesOutcome(handled=True, assistant_text="\n\n".join(lines))

    for pattern in _WEB_SEARCH_WITH_NOTES_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        query = str(match.group("query") or "").strip()
        topic = str(match.groupdict().get("topic") or "").strip() or query
        hits = await search_note_hits(base_dir=base_dir, username=username, settings=settings, query=topic, limit=3)
        note_context = note_context_block(hits, language="de")
        web_result = await WebSearchSkill(settings=settings).execute(
            query,
            {
                "action": "search",
                "user_id": username,
                "language": "de",
                "note_context_hits": [hit.as_dict() for hit in hits],
            },
        )
        assistant_text = str(web_result.content or "").strip()
        if note_context and note_context not in assistant_text:
            assistant_text = f"{note_context}\n\n{assistant_text}".strip()
        if not assistant_text:
            assistant_text = _text("chat_notes.web_search_empty", "The web research could not produce an answer right now.")
        return ChatNotesOutcome(handled=True, assistant_text=assistant_text, icon="🌐", intent_label="web+notes")

    for pattern in _SAVE_WEB_SOURCE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        url = str(match.group("url") or "").strip().rstrip(").,;")
        try:
            source = fetch_web_note_source(url)
        except Exception as exc:  # noqa: BLE001
            return ChatNotesOutcome(
                handled=True,
                assistant_text=_text(
                    "chat_notes.web_source_capture_failed",
                    "The website could not be captured as a note right now: {error}",
                    error=exc,
                ),
                icon="⚠",
                intent_label="notes",
            )
        title = source.title.strip() or infer_note_title(url)
        body_parts = [f"# {title}", "", f"Quelle: {source.url}"]
        if source.description:
            body_parts.extend(["", source.description])
        if source.snippet and source.snippet != source.description:
            body_parts.extend(["", source.snippet])
        body = "\n".join(part for part in body_parts if part is not None).strip()
        tags = list(dict.fromkeys([*source.tags, *_safe_extra_tags(title, source.description, source.url)]))
        folder = infer_note_folder(title, body, tags=tags, source_url=source.url) or _text(
            "chat_notes.research_folder",
            "Research",
        )
        note, index_hint, error_text = await _persist_note(
            base_dir=base_dir,
            username=username,
            settings=settings,
            title=title,
            body=body,
            folder=folder,
            tags=tags,
        )
        if error_text:
            return ChatNotesOutcome(handled=True, assistant_text=error_text, icon="⚠", intent_label="notes")
        tags_line = _optional_tags_line(tags)
        return ChatNotesOutcome(
            handled=True,
            assistant_text=(
                f"{_text('chat_notes.web_source_saved', 'Web source saved as note')}: **{note.title}**\n\n"
                f"{_text('chat_notes.folder_label', 'Folder')}: {note.folder or 'Inbox'}\n\n"
                f"{tags_line}"
                f"{_text('chat_notes.open_label', 'Open')}: `{_notes_link(note.note_id)}`\n\n"
                f"{index_hint}"
            ),
            icon="🌐",
            intent_label="notes",
        )

    for pattern in _CREATE_NOTE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        title = str(match.group("title") or "").strip()
        body = str(match.group("body") or "").strip()
        tags = infer_note_tags(title, body)
        folder = infer_note_folder(title, body, tags=tags)
        note, index_hint, error_text = await _persist_note(
            base_dir=base_dir,
            username=username,
            settings=settings,
            title=title,
            body=body,
            folder=folder,
            tags=tags,
        )
        if error_text:
            return ChatNotesOutcome(handled=True, assistant_text=error_text, icon="⚠", intent_label="notes")
        return ChatNotesOutcome(
            handled=True,
            assistant_text=(
                f"{_text('chat_notes.note_saved', 'Note saved')}: **{note.title}**\n\n"
                f"{_optional_folder_line(note.folder)}"
                f"{_optional_tags_line(note.tags)}"
                f"{_text('chat_notes.open_label', 'Open')}: `{_notes_link(note.note_id)}`\n\n"
                f"{index_hint}"
            ),
        )

    for pattern in _NATURAL_NOTE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        body = str(match.group("body") or "").strip()
        title = infer_note_title(body)
        tags = infer_note_tags(title, body)
        folder = infer_note_folder(title, body, tags=tags)
        note, index_hint, error_text = await _persist_note(
            base_dir=base_dir,
            username=username,
            settings=settings,
            title=title,
            body=body,
            folder=folder,
            tags=tags,
        )
        if error_text:
            return ChatNotesOutcome(handled=True, assistant_text=error_text, icon="⚠", intent_label="notes")
        return ChatNotesOutcome(
            handled=True,
            assistant_text=(
                f"{_text('chat_notes.note_saved', 'Note saved')}: **{note.title}**\n\n"
                f"{_optional_folder_line(note.folder)}"
                f"{_optional_tags_line(note.tags)}"
                f"{_text('chat_notes.open_label', 'Open')}: `{_notes_link(note.note_id)}`\n\n"
                f"{index_hint}"
            ),
        )

    for pattern in _QUICK_NOTE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        body = str(match.group("body") or "").strip()
        title = infer_note_title(body)
        tags = infer_note_tags(title, body)
        folder = infer_note_folder(title, body, tags=tags)
        note, index_hint, error_text = await _persist_note(
            base_dir=base_dir,
            username=username,
            settings=settings,
            title=title,
            body=body,
            folder=folder,
            tags=tags,
        )
        if error_text:
            return ChatNotesOutcome(handled=True, assistant_text=error_text, icon="⚠", intent_label="notes")
        return ChatNotesOutcome(
            handled=True,
            assistant_text=(
                f"{_text('chat_notes.note_saved', 'Note saved')}: **{note.title}**\n\n"
                f"{_optional_folder_line(note.folder)}"
                f"{_optional_tags_line(note.tags)}"
                f"{_text('chat_notes.open_label', 'Open')}: `{_notes_link(note.note_id)}`\n\n"
                f"{index_hint}"
            ),
        )

    return None


def _safe_extra_tags(*parts: str) -> list[str]:
    return infer_note_tags(*parts)
