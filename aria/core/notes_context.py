from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from aria.core.notes_index import NoteSearchHit, NotesIndex
from aria.core.notes_store import NotesStore


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


def lexical_note_hits(base_dir: Path, username: str, query: str, *, limit: int = 8) -> list[NotesContextHit]:
    tokens = [token for token in re.findall(r"[\w.-]+", str(query or "").lower()) if len(token) >= 2]
    if not tokens:
        return []
    rows: list[tuple[int, Any]] = []
    for note in build_notes_store(base_dir).list_notes(username):
        haystack = " ".join([note.title, note.folder, note.body, " ".join(note.tags or [])]).lower()
        score = 0
        for token in tokens:
            if token in note.title.lower():
                score += 4
            elif token in note.folder.lower():
                score += 2
            elif token in " ".join(note.tags or []).lower():
                score += 2
            elif token in haystack:
                score += 1
        if score > 0:
            rows.append((score, note))
    rows.sort(key=lambda item: (-item[0], item[1].updated_at, item[1].title.lower()))
    return [
        NotesContextHit(
            note_id=note.note_id,
            title=note.title,
            folder=note.folder,
            relative_path=note.relative_path,
            updated_at=note.updated_at,
            score=float(score),
            snippet=note.summary,
            source="markdown",
        )
        for score, note in rows[: max(1, int(limit))]
    ]


async def search_note_hits(*, base_dir: Path, username: str, settings: Any, query: str, limit: int = 8) -> list[NotesContextHit]:
    if notes_index_enabled(settings):
        notes_index = NotesIndex(settings.memory, settings.embeddings)
        try:
            rows = await notes_index.search_notes(user_id=username, query=query, limit=limit)
            if rows:
                return [_from_index_hit(row) for row in rows]
        except Exception:
            pass
        finally:
            await notes_index.aclose()
    return lexical_note_hits(base_dir, username, query, limit=limit)


def note_context_detail_lines(hits: list[NotesContextHit], *, language: str | None = None) -> list[str]:
    english = str(language or "").strip().lower().startswith("en")
    prefix = "Note context" if english else "Notiz-Kontext"
    rows: list[str] = []
    for hit in hits:
        folder = hit.folder or ("Inbox" if not english else "Inbox")
        rows.append(f"{prefix}: {hit.title} · {folder}")
    return rows


def note_context_block(hits: list[NotesContextHit], *, language: str | None = None) -> str:
    if not hits:
        return ""
    english = str(language or "").strip().lower().startswith("en")
    heading = "Notes context for the search:" if english else "Notiz-Kontext für die Suche:"
    rows = [heading]
    for hit in hits:
        folder = hit.folder or "Inbox"
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
