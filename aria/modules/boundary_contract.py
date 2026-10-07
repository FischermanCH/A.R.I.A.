"""Pure contracts for external module boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


EXTERNAL_BOUNDARY_CATEGORIES = frozenset(
    {
        "composition_contract",
        "data_boundary",
        "kernel_platform",
        "library_service",
        "runtime_callback",
    }
)
EXTERNAL_BOUNDARY_DISPOSITIONS = frozenset({"durable", "transitional"})

_COMPOSITION_BOUNDARY_ROOTS = {
    "answer_composition",
    "audit_docs",
    "auth",
    "chat",
    "configuration",
    "legacy_source_markers",
    "llm",
    "operator_docs",
    "pipeline",
    "routing",
    "skills",
}
_TRANSITIONAL_BOUNDARY_IDS = frozenset({"chat", "pipeline", "routing", "skills"})


def classify_external_boundary(boundary_id: str) -> str:
    """Classify one boundary id without resolving or importing it."""

    value = str(boundary_id or "").strip()
    root = value.split(".", 1)[0]
    if "callback" in value or value.startswith(("runtime_", "injected_")) or value == "runtime_handlers":
        return "runtime_callback"
    if value.startswith("kernel."):
        return "kernel_platform"
    if value.startswith(("filesystem.", "qdrant_", "sqlite")) or "qdrant" in value or "storage" in value:
        return "data_boundary"
    if root in _COMPOSITION_BOUNDARY_ROOTS:
        return "composition_contract"
    return "library_service"


def external_boundary_disposition(boundary_id: str) -> str:
    """Return the explicit migration disposition for a known boundary id."""

    return "transitional" if str(boundary_id or "").strip() in _TRANSITIONAL_BOUNDARY_IDS else "durable"


def external_boundary_record(boundary_id: str) -> dict[str, str]:
    """Build one deterministic boundary record for manifest migration."""

    clean = str(boundary_id or "").strip()
    return {
        "id": clean,
        "category": classify_external_boundary(clean),
        "disposition": external_boundary_disposition(clean),
    }


def external_boundary_records(manifest: Mapping[str, Any]) -> tuple[dict[str, str], ...]:
    """Project validated records, with read-only compatibility for old fixtures."""

    raw_records = manifest.get("external_boundaries")
    if isinstance(raw_records, (list, tuple)):
        return tuple(
            {
                "id": str(record.get("id") or "").strip(),
                "category": str(record.get("category") or "").strip(),
                "disposition": str(record.get("disposition") or "").strip(),
            }
            for record in raw_records
            if isinstance(record, Mapping)
        )
    legacy = manifest.get("external_dependencies", ())
    if not isinstance(legacy, (list, tuple)):
        return ()
    return tuple(external_boundary_record(item) for item in legacy if isinstance(item, str) and item.strip())


def external_boundary_ids(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the compatibility id projection from the boundary authority."""

    return tuple(record["id"] for record in external_boundary_records(manifest))
