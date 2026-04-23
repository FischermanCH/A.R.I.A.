from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

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


_OPEN_NOTES_PATTERNS = (
    re.compile(r"^(?:zeige|oeffne|öffne)\s+(?:meine\s+)?notizen\s*$", re.IGNORECASE),
    re.compile(r"^(?:show|open)\s+(?:my\s+)?notes\s*$", re.IGNORECASE),
)
_SEARCH_NOTES_PATTERNS = (
    re.compile(r"^(?:suche|finde)\s+(?:in\s+(?:meinen\s+)?)?notizen(?:\s+nach|\s+zu)?\s+(?P<query>.+)$", re.IGNORECASE),
    re.compile(r"^(?:search|find)\s+(?:my\s+)?notes(?:\s+for|\s+about)?\s+(?P<query>.+)$", re.IGNORECASE),
)
_CREATE_NOTE_PATTERNS = (
    re.compile(r"^(?:erstelle|create|add|neue?)\s+notiz\s+(?P<title>[^:\n]{2,140})\s*:\s*(?P<body>.+)$", re.IGNORECASE | re.DOTALL),
    re.compile(r"^(?:notiere|note)\s+(?P<title>[^:\n]{2,140})\s*:\s*(?P<body>.+)$", re.IGNORECASE | re.DOTALL),
)
_QUICK_NOTE_PATTERNS = (
    re.compile(r"^(?:notiere|merk\s+als\s+notiz|save\s+note)\s+(?P<body>.+)$", re.IGNORECASE | re.DOTALL),
)
_NATURAL_NOTE_PATTERNS = (
    re.compile(r"^(?:halte\s+fest|halt\s+fest|schreib\s+(?:mir\s+)?eine?\s+notiz(?:\s+dazu|\s+darueber|\s+darüber)?|create\s+a\s+note(?:\s+about)?)\s+(?P<body>.+)$", re.IGNORECASE | re.DOTALL),
)
_WEB_SEARCH_WITH_NOTES_PATTERNS = (
    re.compile(
        r"^(?:suche im internet nach|recherchiere(?:\s+im internet)?\s+nach)\s+(?P<query>.+?)\s+mit\s+(?:meinen\s+)?notizen(?:\s+zu\s+(?P<topic>.+))?$",
        re.IGNORECASE | re.DOTALL,
    ),
        re.compile(
            r"^(?:search the web for|search the internet for|research)\s+(?P<query>.+?)\s+with\s+(?:my\s+)?notes(?:\s+about\s+(?P<topic>.+))?$",
            re.IGNORECASE | re.DOTALL,
        ),
)
_SAVE_WEB_SOURCE_PATTERNS = (
    re.compile(r"^(?:speichere|notiere|uebernimm|übernimm)\s+(?:diese\s+)?(?:webseite|quelle|url|link)\s+(?P<url>https?://\S+)(?:\s+als\s+notiz)?\s*$", re.IGNORECASE),
    re.compile(r"^(?:mach|erstelle)\s+(?:aus\s+)?(?P<url>https?://\S+)\s+(?:eine\s+)?notiz\s*$", re.IGNORECASE),
    re.compile(r"^(?:save|capture)\s+(?:this\s+)?(?:website|source|url|link)(?:\s+as\s+note)?\s+(?P<url>https?://\S+)\s*$", re.IGNORECASE),
)


def _store(base_dir: Path) -> NotesStore:
    return build_notes_store(base_dir)


def _notes_link(note_id: str | None = None) -> str:
    if note_id:
        return f"/notes?note={note_id}#note-editor"
    return "/notes"


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
        return None, f"Die Notiz konnte nicht gespeichert werden: {exc}", None
    if notes_index_enabled(settings):
        from aria.core.notes_index import NotesIndex

        notes_index = NotesIndex(settings.memory, settings.embeddings)
        try:
            await notes_index.reindex_note(note)
            index_hint = "Qdrant-Index aktualisiert."
        except Exception as exc:  # noqa: BLE001
            index_hint = f"Qdrant-Index konnte noch nicht aktualisiert werden: {exc}"
        finally:
            await notes_index.aclose()
    else:
        index_hint = "Qdrant-Index ist aktuell nicht aktiv. Die Markdown-Notiz ist trotzdem gespeichert."
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
                    f"Deine Notizen liegen hier: `{_notes_link()}`\n\n"
                    f"Aktuell vorhanden: {len(notes)}"
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
                assistant_text=f"Zu `{query}` habe ich in deinen Notizen gerade nichts Passendes gefunden. Öffnen: `{_notes_link()}`",
            )
        lines = [f"Passende Notizen zu `{query}`:"]
        for index, hit in enumerate(hits, start=1):
            folder = str(hit.folder or "").strip() or "Inbox"
            lines.append(
                f"- [{index}] {hit.title or 'Notiz'} · {folder}\n  `{_notes_link(str(hit.note_id or '').strip())}`\n  {hit.snippet}"
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
            assistant_text = "Die Web-Recherche konnte gerade keine Antwort erzeugen."
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
                assistant_text=f"Die Webseite konnte gerade nicht als Notiz übernommen werden: {exc}",
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
        folder = infer_note_folder(title, body, tags=tags, source_url=source.url) or "Recherche"
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
        tags_line = f"Tags: {', '.join(tags)}\n\n" if tags else ""
        return ChatNotesOutcome(
            handled=True,
            assistant_text=(
                f"Webquelle als Notiz gespeichert: **{note.title}**\n\n"
                f"Ordner: {note.folder or 'Inbox'}\n\n"
                f"{tags_line}"
                f"Öffnen: `{_notes_link(note.note_id)}`\n\n"
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
                f"Notiz gespeichert: **{note.title}**\n\n"
                f"{'Ordner: ' + note.folder + chr(10) + chr(10) if note.folder else ''}"
                f"{'Tags: ' + ', '.join(note.tags) + chr(10) + chr(10) if note.tags else ''}"
                f"Öffnen: `{_notes_link(note.note_id)}`\n\n"
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
                f"Notiz gespeichert: **{note.title}**\n\n"
                f"{'Ordner: ' + note.folder + chr(10) + chr(10) if note.folder else ''}"
                f"{'Tags: ' + ', '.join(note.tags) + chr(10) + chr(10) if note.tags else ''}"
                f"Öffnen: `{_notes_link(note.note_id)}`\n\n"
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
                f"Notiz gespeichert: **{note.title}**\n\n"
                f"{'Ordner: ' + note.folder + chr(10) + chr(10) if note.folder else ''}"
                f"{'Tags: ' + ', '.join(note.tags) + chr(10) + chr(10) if note.tags else ''}"
                f"Öffnen: `{_notes_link(note.note_id)}`\n\n"
                f"{index_hint}"
            ),
        )

    return None


def _safe_extra_tags(*parts: str) -> list[str]:
    return infer_note_tags(*parts)
