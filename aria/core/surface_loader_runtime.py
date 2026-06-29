from __future__ import annotations

import sys
from typing import Any

from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.connection_catalog import connection_kind_label
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.context_surfaces import ContextRequest
from aria.core.inventory_index import InventoryIndexStore
from aria.core.inventory_index import create_inventory_qdrant_client
from aria.core.inventory_index import inventory_collection_name
from aria.skills.base import SkillResult


class SurfaceLoaderRuntime:
    """Loader boundary from TurnPlan context requests to loaded SkillResults."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    async def load_inventory(self, arbitration: AriaTurnArbitration | None) -> list[SkillResult]:
        if arbitration is None:
            return []
        results: list[SkillResult] = []
        requests = [request for request in arbitration.plan.context_requests if request.mode == "inventory"]
        requests = [
            request
            for request in requests
            if not (request.surface_id in {"memory", "notes", "docs"} and str(request.query or "").strip())
        ]
        if not requests and "context_inventory" in arbitration.plan.intents:
            requests = [
                ContextRequest(surface_id=direction, mode="inventory", query=arbitration.plan.queries.get(direction, ""))
                for direction in arbitration.plan.context_directions
                if build_builtin_surface_registry(self.owner.settings).get(direction) is not None
            ]
        for request in requests:
            inventory = await self._load_inventory_request(arbitration, request)
            if inventory is not None:
                results.append(inventory)
        return results

    async def load_memory_exists(
        self,
        *,
        arbitration: AriaTurnArbitration,
        user_id: str,
        memory_collection: str | None,
        session_collection: str | None,
        context_overrides: dict[str, Any],
    ) -> SkillResult:
        if self.owner.memory_skill is None:
            return SkillResult(
                skill_name="memory_recall",
                success=True,
                content="",
                metadata={"detail_lines": ["Routing Debug: memory_recall skipped reason=no_memory_skill"]},
            )
        query = self.owner._aria_turn_memory_exists_evidence_query(arbitration)
        family_base = str(memory_collection or session_collection or "").strip()
        if not family_base:
            family_base = f"{self.owner.settings.memory.collections.facts.prefix}_{user_id}"
        top_k = int(context_overrides.get("memory_top_k") or max(2, int(self.owner.settings.memory.top_k or 2)))
        recall_params: dict[str, Any] = {
            "action": "recall",
            "top_k": top_k,
            "user_id": user_id,
            "collection": family_base,
            "target_collections": list(context_overrides.get("memory_target_collections") or []),
            "include_documents": bool(context_overrides.get("include_documents", False)),
            "docs_only": bool(context_overrides.get("docs_only", False)),
        }
        if bool(context_overrides.get("document_corpus_scan", False)):
            recall_params["document_corpus_scan"] = True
        if bool(context_overrides.get("document_inventory", False)):
            recall_params.update(
                {
                    "document_inventory": True,
                    "document_ids": list(context_overrides.get("document_ids") or []),
                    "document_names": list(context_overrides.get("document_names") or []),
                    "document_target_collections": list(context_overrides.get("document_target_collections") or []),
                }
            )
        result = await self.owner.memory_skill.execute(
            query=query,
            params=recall_params,
        )
        result.skill_name = "memory_recall"
        return result

    async def _load_inventory_request(self, arbitration: AriaTurnArbitration, request: ContextRequest) -> SkillResult | None:
        registry = build_builtin_surface_registry(self.owner.settings)
        surface = registry.get(request.surface_id)
        if surface is None:
            return None
        query = str(request.query or self.owner._aria_turn_context_request_query(arbitration, request.surface_id)).strip()
        indexed_result = await self._load_inventory_index_result(request, query)
        if indexed_result is not None:
            return indexed_result
        message, sources = self.owner._aria_turn_format_inventory_metadata(request.surface_id, dict(surface.metadata or {}), query, limit=request.limit)
        detail_lines = []
        if indexed_result is not None:
            detail_lines.extend(list((indexed_result.metadata or {}).get("detail_lines", []) or []))
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content=message,
            metadata={
                "sources": sources,
                "detail_lines": [
                    *detail_lines,
                    "Routing Debug: context_inventory "
                    f"surface={request.surface_id} mode=inventory matches={len(sources)} query={query or '-'}"
                ],
            },
        )

    async def _load_inventory_index_result(self, request: ContextRequest, query: str) -> SkillResult | None:
        if not request.surface_id or not str(query or "").strip():
            return None
        inventory_cfg = getattr(self.owner.settings, "inventory_index", None)
        if not bool(getattr(inventory_cfg, "enabled", True)):
            return None
        memory_cfg = getattr(self.owner.settings, "memory", None)
        if not bool(getattr(memory_cfg, "enabled", False)) or str(getattr(memory_cfg, "backend", "") or "").strip().lower() != "qdrant":
            return None
        qdrant = None
        try:
            pipeline_module = sys.modules.get("aria.core.pipeline")
            qdrant_factory = getattr(pipeline_module, "create_inventory_qdrant_client", create_inventory_qdrant_client)
            qdrant = await qdrant_factory(self.owner.settings, timeout=5)
            store = InventoryIndexStore(
                qdrant=qdrant,
                embedding_client=self.owner.embedding_client,
                collection_name=inventory_collection_name(self.owner.settings),
            )
            hits = await store.query_inventory(
                query,
                surface_id=request.surface_id,
                limit=min(80, max(12, int(getattr(inventory_cfg, "candidate_limit", 12) or 12) * 5)),
                score_threshold=float(getattr(inventory_cfg, "score_threshold", 0.35) or 0.0),
            )
        except Exception as exc:
            return SkillResult(
                skill_name="context_inventory",
                success=True,
                content="No matching inventory metadata was found for the selected query.",
                metadata={
                    "sources": [],
                    "detail_lines": [
                        "Routing Debug: inventory_index skipped "
                        f"surface={request.surface_id} authoritative=true reason={str(exc).strip() or 'query_failed'}"
                    ],
                },
            )
        finally:
            close = getattr(qdrant, "close", None) or getattr(qdrant, "aclose", None)
            if callable(close):
                result = close()
                if hasattr(result, "__await__"):
                    await result
        budget = dict(request.budget or {})
        bound_ref = str(budget.get("ref", "") or "").strip()
        bound_kind = str(budget.get("kind", "") or "").strip()
        bound_catalog_id = str(budget.get("catalog_id", "") or "").strip()
        bind_ref = bool(budget.get("bind_ref") or budget.get("exact_ref"))
        evidence_debug: list[str]
        if bound_ref and bind_ref:
            pre_bound_count = len(hits)
            hits = [
                hit
                for hit in hits
                if str(dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip() == bound_ref
                and (not bound_kind or str(dict(hit.get("payload", {}) or {}).get("kind", "") or "").strip() == bound_kind)
            ][: max(1, int(getattr(inventory_cfg, "candidate_limit", 12) or 12))]
            evidence_debug = [
                "Routing Debug: inventory_index_bound "
                f"surface={request.surface_id} catalog_id={bound_catalog_id or '-'} kind={bound_kind or '-'} "
                f"ref={bound_ref} kept={len(hits)} candidates={pre_bound_count}"
            ]
        else:
            hits, evidence_debug = self.owner._aria_turn_inventory_evidence_hits(
                hits,
                request=request,
                query=query,
                limit=int(getattr(inventory_cfg, "candidate_limit", 12) or 12),
            )
        if not hits:
            return SkillResult(
                skill_name="context_inventory",
                success=True,
                content="No matching inventory metadata was found for the selected query.",
                metadata={
                    "sources": [],
                    "detail_lines": [
                        "Routing Debug: inventory_index "
                        f"surface={request.surface_id} matches=0 query={query or '-'} authoritative=true",
                        *evidence_debug,
                    ],
                },
            )
        rows = ["Beobachtete Quellen:"]
        sources: list[dict[str, Any]] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for hit in hits[: max(1, int(request.limit or 50))]:
            grouped.setdefault(str(hit.get("kind", "") or "-"), []).append(hit)
        for kind, kind_hits in sorted(grouped.items()):
            refs = [str(hit.get("ref", "") or "").strip() for hit in kind_hits if str(hit.get("ref", "") or "").strip()]
            rows.append(f"{connection_kind_label(kind)} ({kind}): {len(refs)} Treffer")
            for hit in kind_hits:
                payload = dict(hit.get("payload", {}) or {})
                ref = str(payload.get("ref", "") or hit.get("ref", "") or "").strip()
                title = str(payload.get("title", "") or "").strip()
                description = str(payload.get("description", "") or "").strip()
                group_name = str(payload.get("group_name", "") or "").strip()
                tags = list(payload.get("tags", []) or [])
                details = "; ".join(
                    part
                    for part in (
                        description,
                        f"Gruppe: {group_name}" if group_name else "",
                        f"Tags: {', '.join(str(tag) for tag in tags[:6])}" if tags else "",
                    )
                    if part
                )
                row = f"- **{ref}**"
                if title:
                    row = f"{row} - {title}"
                if details:
                    row = f"{row} ({details})"
                rows.append(row)
            sources.append({"surface": request.surface_id, "kind": kind, "refs": refs})
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n".join(rows[:80]),
            metadata={
                "sources": sources,
                "detail_lines": [
                    "Routing Debug: inventory_index "
                    f"surface={request.surface_id} matches={len(hits)} query={query or '-'} authoritative=true",
                    *evidence_debug,
                ],
            },
        )
