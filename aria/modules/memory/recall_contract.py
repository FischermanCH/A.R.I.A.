from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def build_memory_recall_params(
    *,
    context_overrides: Mapping[str, Any],
    user_id: str,
    collection: str,
    top_k: int,
    default_include_documents: bool,
) -> dict[str, Any]:
    """Build the shared technical contract for every Memory recall adapter."""

    params: dict[str, Any] = {
        "action": "recall",
        "top_k": int(top_k),
        "user_id": user_id,
        "collection": collection,
        "target_collections": list(context_overrides.get("memory_target_collections") or []),
        "include_documents": bool(context_overrides.get("include_documents", default_include_documents)),
        "docs_only": bool(context_overrides.get("docs_only", False)),
    }
    if bool(context_overrides.get("include_learning_audit", False)):
        params["include_learning_audit"] = True
    if bool(context_overrides.get("document_corpus_scan", False)):
        params["document_corpus_scan"] = True

    for key in ("document_target_collections", "document_ids", "document_names"):
        values = list(context_overrides.get(key) or [])
        if values:
            params[key] = values

    if bool(context_overrides.get("document_inventory", False)):
        params.update(
            {
                "document_inventory": True,
                "document_ids": list(context_overrides.get("document_ids") or []),
                "document_names": list(context_overrides.get("document_names") or []),
                "document_target_collections": list(context_overrides.get("document_target_collections") or []),
            }
        )
    return params
