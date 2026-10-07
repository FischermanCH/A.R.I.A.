from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.notes.index import NoteSearchHit, NotesIndex
from aria.modules.notes.store import NoteRecord, NotesStore

_NOTES_CONTEXT_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _notes_context_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _NOTES_CONTEXT_I18N.t(language or "de", f"notes_context.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


@dataclass(frozen=True)
class NotesContextHit:
    note_id: str
    title: str
    folder: str
    relative_path: str
    updated_at: str
    score: float
    snippet: str
    chunk_index: int = 0
    chunk_total: int = 0
    source: str = "markdown"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_notes_store(base_dir: Path) -> NotesStore:
    return NotesStore(Path(base_dir) / "data" / "notes")


def notes_index_enabled(settings: Any) -> bool:
    memory = getattr(settings, "memory", None)
    return bool(
        getattr(memory, "enabled", False)
        and str(getattr(memory, "backend", "") or "").strip().lower() == "qdrant"
        and str(getattr(memory, "qdrant_url", "") or "").strip()
    )


async def search_note_hits(
    *,
    base_dir: Path,
    username: str,
    settings: Any,
    query: str,
    limit: int = 8,
    allow_markdown_fallback: bool = False,
) -> list[NotesContextHit]:
    if notes_index_enabled(settings):
        notes_index = NotesIndex(
            settings.memory,
            settings.embeddings,
            usage_meter=getattr(settings, "_aria_usage_meter", None),
        )
        try:
            rows = await notes_index.search_notes(user_id=username, query=query, limit=limit)
            if rows:
                return [_from_index_hit(row) for row in rows]
        except Exception:
            pass
        finally:
            await notes_index.aclose()
    if allow_markdown_fallback:
        return _markdown_note_hits(base_dir=base_dir, username=username, query=query, limit=limit)
    return []


def note_context_detail_lines(hits: list[NotesContextHit], *, language: str | None = None) -> list[str]:
    prefix = _notes_context_text(language, "detail_prefix", "Note context")
    rows: list[str] = []
    for hit in hits:
        folder = hit.folder or _notes_context_text(language, "inbox", "Inbox")
        rows.append(f"{prefix}: {hit.title} · {folder}")
    return rows


def note_context_block(hits: list[NotesContextHit], *, language: str | None = None) -> str:
    if not hits:
        return ""
    heading = _notes_context_text(language, "search_heading", "Notes context for the search:")
    rows = [heading]
    for hit in hits:
        folder = hit.folder or _notes_context_text(language, "inbox", "Inbox")
        snippet = str(hit.snippet or "").strip()
        line = f"- {hit.title} ({folder})"
        if snippet:
            line += f": {snippet}"
        rows.append(line)
    return "\n".join(rows).strip()


def _from_index_hit(hit: NoteSearchHit) -> NotesContextHit:
    return NotesContextHit(
        note_id=hit.note_id,
        title=hit.title,
        folder=hit.folder,
        relative_path=hit.relative_path,
        updated_at=hit.updated_at,
        score=hit.score,
        snippet=hit.snippet,
        chunk_index=hit.chunk_index,
        chunk_total=hit.chunk_total,
        source="qdrant",
    )


def _markdown_note_hits(*, base_dir: Path, username: str, query: str, limit: int) -> list[NotesContextHit]:
    clean_query = _normalize_source_label(query)
    if not clean_query:
        return []
    store = build_notes_store(base_dir)
    notes = store.list_notes(username, preview_only=True)
    if not notes:
        return []

    folders = store.list_folders(username, notes=notes)
    folder_labels = [folder for folder in folders if _source_label_matches_query(folder, clean_query)]
    rows: list[tuple[NoteRecord, float]] = []
    for folder in folder_labels:
        for note in notes:
            if _note_in_folder(note, folder):
                rows.append((note, 1.0))

    exact_title_rows = [(note, 0.96) for note in notes if _normalize_source_label(note.title) == clean_query]
    if not rows and exact_title_rows:
        return [_from_markdown_note(note, score=score) for note, score in exact_title_rows[: max(1, int(limit or 1))]]

    for note in notes:
        if _source_label_matches_query(note.title, clean_query):
            rows.append((note, 0.96))

    for note in notes:
        if any(_source_label_matches_query(tag, clean_query) for tag in note.tags):
            rows.append((note, 0.92))

    hits: list[NotesContextHit] = []
    seen_note_ids: set[str] = set()
    for note, score in rows:
        if note.note_id in seen_note_ids:
            continue
        seen_note_ids.add(note.note_id)
        hits.append(_from_markdown_note(note, score=score))
        if len(hits) >= max(1, int(limit or 1)):
            break
    return hits


def _normalize_source_label(value: str) -> str:
    chars = [char.casefold() if char.isalnum() else " " for char in str(value or "")]
    return " ".join("".join(chars).split())


def _source_label_matches_query(label: str, normalized_query: str) -> bool:
    normalized_label = _normalize_source_label(label)
    if not normalized_label:
        return False
    if normalized_label == normalized_query:
        return True
    return f" {normalized_label} " in f" {normalized_query} "


def _note_in_folder(note: NoteRecord, folder: str) -> bool:
    clean_folder = str(folder or "").strip()
    note_folder = str(note.folder or "").strip()
    return note_folder == clean_folder or note_folder.startswith(f"{clean_folder}/")


def _from_markdown_note(note: NoteRecord, *, score: float) -> NotesContextHit:
    return NotesContextHit(
        note_id=note.note_id,
        title=note.title,
        folder=note.folder,
        relative_path=note.relative_path,
        updated_at=note.updated_at,
        score=score,
        snippet=note.summary,
        source="markdown",
    )
