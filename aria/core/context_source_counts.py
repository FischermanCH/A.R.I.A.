from __future__ import annotations

from typing import Any


def context_source_count(sources: Any) -> int:
    """Count source evidence units without flattening the source payload."""
    if not isinstance(sources, list):
        return 0
    total = 0
    for source in sources:
        if not isinstance(source, dict):
            continue
        refs = source.get("refs")
        if isinstance(refs, list):
            ref_count = len([ref for ref in refs if str(ref or "").strip()])
            total += ref_count if ref_count else 1
        else:
            total += 1
    return total
