from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from aria.core.config import EmbeddingsConfig
from aria.core.embedding_client import EmbeddingClient


FileResolver = Callable[[str], Path]


def sanitize_csrf_token_local(value: str | None) -> str:
    token = str(value or "").strip()
    token = "".join(ch for ch in token if ch.isalnum() or ch in {"_", "-"})
    return token[:256]


def sanitize_reference_name_local(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    normalized: list[str] = []
    last_was_dash = False
    for ch in raw:
        if ch.isalnum() or ch == "_":
            normalized.append(ch)
            last_was_dash = False
            continue
        if ch == "-":
            if not last_was_dash:
                normalized.append("-")
            last_was_dash = True
            continue
        if not last_was_dash:
            normalized.append("-")
        last_was_dash = True
    return "".join(normalized).strip("-")[:48]


def is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    supplied = sanitize_csrf_token_local(submitted_token)
    expected = sanitize_csrf_token_local(expected_token)
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def size_human(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(0, size_bytes))
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} GB"


def format_session_timeout_label(total_minutes: int, lang: str = "de") -> str:
    minutes = max(0, int(total_minutes or 0))
    if minutes < 60:
        return f"{minutes} Minuten" if lang == "de" else f"{minutes} minutes"
    hours, rest_minutes = divmod(minutes, 60)
    if rest_minutes == 0:
        return f"{hours} Stunden" if lang == "de" else f"{hours} hours"
    if lang == "de":
        return f"{hours} Stunden {rest_minutes} Minuten"
    return f"{hours} hours {rest_minutes} minutes"


def resolve_embedding_model_label(model: str, api_base: str | None = None) -> str:
    config = EmbeddingsConfig(model=str(model or "").strip(), api_base=str(api_base or "").strip() or None)
    return EmbeddingClient(config)._resolve_model()


def embedding_fingerprint_for_values(model: str, api_base: str | None = None) -> str:
    config = EmbeddingsConfig(model=str(model or "").strip(), api_base=str(api_base or "").strip() or None)
    return EmbeddingClient(config).fingerprint()


def short_fingerprint(value: str, length: int = 12) -> str:
    return str(value or "").strip()[: max(1, int(length or 12))]


def memory_point_totals(stats: list[dict[str, Any]] | None) -> tuple[int, int]:
    rows = list(stats or [])
    return sum(int(row.get("points", 0) or 0) for row in rows), len(rows)


def embedding_switch_requires_confirmation(
    current_memory_fingerprint: str,
    new_fingerprint: str,
    memory_point_count: int,
    memory_collection_count: int = 0,
) -> bool:
    return (
        (int(memory_point_count or 0) > 0 or int(memory_collection_count or 0) > 0)
        and str(current_memory_fingerprint or "").strip() != str(new_fingerprint or "").strip()
    )


def build_editor_entries_from_paths(base_dir: Path, rel_paths: list[str], resolver: FileResolver) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rel_path in rel_paths:
        try:
            path = resolver(rel_path)
            stat = path.stat()
            rows.append(
                {
                    "path": rel_path,
                    "name": path.name,
                    "size": int(stat.st_size),
                    "size_label": size_human(int(stat.st_size)),
                    "updated": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                }
            )
        except (OSError, ValueError):
            continue
    return rows
