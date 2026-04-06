from __future__ import annotations

import hashlib
from io import BytesIO
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 180
SUPPORTED_TEXT_SUFFIXES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


class DocumentIngestError(ValueError):
    """Raised when an uploaded document cannot be prepared for ingest."""


@dataclass(frozen=True)
class DocumentChunk:
    text: str
    index: int
    total: int


@dataclass(frozen=True)
class PreparedDocument:
    document_id: str
    filename: str
    mime_type: str
    source_type: str
    text: str
    chunks: list[DocumentChunk]
    summary: str
    keywords: list[str]


DOCUMENT_GUIDE_STOPWORDS = {
    "aber",
    "about",
    "alle",
    "also",
    "and",
    "are",
    "aus",
    "bei",
    "ber",
    "bitte",
    "can",
    "das",
    "dass",
    "dem",
    "den",
    "der",
    "des",
    "die",
    "dies",
    "dieser",
    "document",
    "dokument",
    "eine",
    "einem",
    "einer",
    "eines",
    "euch",
    "fuer",
    "für",
    "handbuch",
    "have",
    "ich",
    "ihr",
    "ihre",
    "into",
    "ist",
    "kann",
    "können",
    "manual",
    "mit",
    "nach",
    "oder",
    "pdf",
    "sich",
    "sie",
    "sind",
    "that",
    "the",
    "this",
    "und",
    "use",
    "user",
    "vom",
    "von",
    "was",
    "werden",
    "wie",
    "with",
}


def sanitize_uploaded_filename(filename: str | None) -> str:
    name = Path(str(filename or "").strip()).name.strip()
    return name or "document.txt"


def supported_upload_suffixes() -> tuple[str, ...]:
    return tuple(sorted(SUPPORTED_TEXT_SUFFIXES.keys()))


def _normalize_document_text(text: str) -> str:
    clean = str(text or "").replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    clean = clean.replace("\ufeff", "")
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    return clean.strip()


def _document_paragraphs(text: str) -> list[str]:
    clean = _normalize_document_text(text)
    if not clean:
        return []
    return [part.strip() for part in re.split(r"\n{2,}", clean) if part.strip()]


def _build_document_summary(text: str, *, max_chars: int = 360) -> str:
    paragraphs = _document_paragraphs(text)
    if not paragraphs:
        return ""
    summary_parts: list[str] = []
    total = 0
    for paragraph in paragraphs:
        clipped = re.sub(r"\s+", " ", paragraph).strip()
        if not clipped:
            continue
        remaining = max_chars - total
        if remaining <= 0:
            break
        if len(clipped) > remaining:
            clipped = clipped[: max(remaining - 1, 0)].rstrip(" ,;:.") + "…"
        summary_parts.append(clipped)
        total += len(clipped) + 1
        if total >= max_chars or len(summary_parts) >= 2:
            break
    return " ".join(summary_parts).strip()


def _extract_document_keywords(text: str, *, max_keywords: int = 8) -> list[str]:
    clean = _normalize_document_text(text).lower()
    if not clean:
        return []
    tokens = re.findall(r"[a-z0-9][a-z0-9._-]{2,}", clean)
    counts: Counter[str] = Counter()
    for token in tokens:
        normalized = token.strip("._-")
        if not normalized:
            continue
        if normalized in DOCUMENT_GUIDE_STOPWORDS:
            continue
        if normalized.isdigit() and len(normalized) < 4:
            continue
        counts[normalized] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [token for token, _count in ranked[:max_keywords]]


def _chunk_text(text: str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    content = _normalize_document_text(text)
    if not content:
        return []

    normalized_chunk_size = max(400, int(chunk_size))
    normalized_overlap = max(0, min(int(overlap), normalized_chunk_size // 2))
    chunks: list[str] = []
    start = 0
    total_length = len(content)

    while start < total_length:
        end = min(total_length, start + normalized_chunk_size)
        if end < total_length:
            break_at = max(
                content.rfind("\n\n", start + 200, end),
                content.rfind("\n", start + 200, end),
                content.rfind(" ", start + 200, end),
            )
            if break_at > start + 200:
                end = break_at
        chunk = content[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= total_length:
            break
        start = max(start + 1, end - normalized_overlap)

    return chunks


def _extract_pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency should exist in runtime/builds
        raise DocumentIngestError("PDF-Import ist aktuell nicht verfügbar.") from exc

    try:
        reader = PdfReader(BytesIO(payload))
    except Exception as exc:  # noqa: BLE001
        raise DocumentIngestError("PDF konnte nicht gelesen werden.") from exc

    page_texts: list[str] = []
    for page in getattr(reader, "pages", []) or []:
        try:
            extracted = str(page.extract_text() or "").strip()
        except Exception:  # noqa: BLE001
            extracted = ""
        if extracted:
            page_texts.append(extracted)

    text = _normalize_document_text("\n\n".join(page_texts))
    if text:
        return text
    raise DocumentIngestError(
        "PDF enthält keinen eingebetteten Text. Scan-/Bild-PDFs werden in RAG v1 noch nicht unterstützt."
    )


def prepare_uploaded_document(
    *,
    filename: str,
    data: bytes,
    content_type: str = "",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> PreparedDocument:
    clean_name = sanitize_uploaded_filename(filename)
    suffix = Path(clean_name).suffix.lower()
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        supported = ", ".join(supported_upload_suffixes())
        raise DocumentIngestError(f"Nur {supported} werden in RAG v1 unterstützt.")

    payload = bytes(data or b"")
    if not payload:
        raise DocumentIngestError("Die hochgeladene Datei ist leer.")
    if len(payload) > int(max_bytes):
        raise DocumentIngestError("Die Datei ist für RAG v1 zu groß.")

    if suffix == ".pdf":
        text = _extract_pdf_text(payload)
    else:
        text = _normalize_document_text(payload.decode("utf-8", errors="replace"))
    if not text:
        raise DocumentIngestError("Aus der Datei konnte kein Text gelesen werden.")

    raw_chunks = _chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
    if not raw_chunks:
        raise DocumentIngestError("Die Datei enthält keinen importierbaren Text.")

    total = len(raw_chunks)
    document_id = hashlib.sha256((clean_name + "\n").encode("utf-8") + payload).hexdigest()[:24]
    source_type = suffix.lstrip(".") or "text"
    mime_type = str(content_type or "").strip() or SUPPORTED_TEXT_SUFFIXES[suffix]
    chunks = [DocumentChunk(text=chunk, index=index + 1, total=total) for index, chunk in enumerate(raw_chunks)]
    summary = _build_document_summary(text)
    keywords = _extract_document_keywords(text)

    return PreparedDocument(
        document_id=document_id,
        filename=clean_name,
        mime_type=mime_type,
        source_type=source_type,
        text=text,
        chunks=chunks,
        summary=summary,
        keywords=keywords,
    )
