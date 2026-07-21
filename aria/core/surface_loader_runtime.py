from __future__ import annotations

from dataclasses import replace
import re
import sys
from typing import Any

from aria.core.aria_turn_arbitration import AriaTurnArbitration
from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.connection_catalog import connection_kind_label
from aria.core.connection_action_contract import connection_action_contracts
from aria.core.connection_action_contract import connection_action_executor_bindings
from aria.core.context_surface_adapters import build_builtin_surface_registry
from aria.core.context_surfaces import ContextRequest
from aria.core.inventory_index import build_inventory_documents
from aria.core.inventory_index import InventoryIndexStore
from aria.core.inventory_index import create_inventory_qdrant_client
from aria.core.inventory_index import inventory_collection_name
from aria.skills.base import SkillResult


INVENTORY_SEMANTIC_SCOPE_REVIEW_OPERATION = "inventory_semantic_scope_review"


def _query_requests_network_address(query: str) -> bool:
    tokens = set(_tokenize_inventory_scope(query))
    return bool(tokens & {"ip", "ips", "adresse", "adressen", "address", "addresses", "host", "hosts", "hostname", "hostnames", "hostnamen"})


_BROAD_ADDRESS_SCOPE_TOKENS = {
    "address",
    "addresses",
    "all",
    "alle",
    "adresse",
    "adressen",
    "connection",
    "connections",
    "haben",
    "host",
    "hostname",
    "hostnames",
    "hostnamen",
    "hosts",
    "including",
    "inklusive",
    "inventory",
    "ip",
    "ips",
    "list",
    "liste",
    "meine",
    "mein",
    "my",
    "overview",
    "server",
    "servern",
    "servers",
    "ssh",
    "srv",
    "uebersicht",
    "was",
    "welche",
    "übersicht",
}


def _tokenize_inventory_scope(value: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").strip().lower()) if token]


def _query_mentions_selected_ref_topic(query: str, selected_refs: list[str]) -> bool:
    query_tokens = [
        token
        for token in _tokenize_inventory_scope(query)
        if len(token) >= 3 and token not in _BROAD_ADDRESS_SCOPE_TOKENS
    ]
    if not query_tokens:
        return False
    ref_tokens = [
        token
        for ref in selected_refs
        for token in _tokenize_inventory_scope(ref)
        if len(token) >= 3 and token not in _BROAD_ADDRESS_SCOPE_TOKENS
    ]
    return any(query_token in ref_token or ref_token in query_token for query_token in query_tokens for ref_token in ref_tokens)


def _query_has_specific_inventory_topic(query: str) -> bool:
    return any(
        len(token) >= 3 and token not in _BROAD_ADDRESS_SCOPE_TOKENS
        for token in _tokenize_inventory_scope(query)
    )


def _selected_refs_are_broad_kind_scope(query: str, selected_refs: list[str], selected_kinds: list[str]) -> bool:
    return (
        _query_requests_network_address(query)
        and len(selected_refs) > 1
        and len(set(selected_kinds)) == 1
        and not _query_mentions_selected_ref_topic(query, selected_refs)
    )


def _query_requests_broad_connection_inventory(query: str) -> bool:
    tokens = set(_tokenize_inventory_scope(query))
    return (
        _query_requests_network_address(query)
        and bool(tokens & {"server", "servern", "servers", "ssh", "sftp"})
        and not _query_has_specific_inventory_topic(query)
    )


def _query_requests_specific_connection_scope(query: str) -> bool:
    return _query_requests_network_address(query) and _query_has_specific_inventory_topic(query)


def _connection_inventory_evidence_row(hit: dict[str, Any]) -> dict[str, Any]:
    payload = dict(hit.get("payload", {}) or {})
    return {
        "kind": str(payload.get("kind", "") or hit.get("kind", "") or "").strip(),
        "ref": str(payload.get("ref", "") or hit.get("ref", "") or "").strip(),
        "title": str(payload.get("title", "") or "").strip(),
        "host": str(payload.get("host", "") or "").strip(),
        "description": str(payload.get("description", "") or "").strip(),
        "group_name": str(payload.get("group_name", "") or "").strip(),
        "tags": [str(tag) for tag in list(payload.get("tags", []) or [])[:12]],
    }


def _connection_inventory_field_set(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for field in ("kind", "ref", "title", "host", "description", "group_name", "tags"):
        if any(row.get(field) for row in rows):
            fields.append(field)
    return fields


def _connection_inventory_evidence_bundle(
    *,
    request: ContextRequest,
    query: str,
    hits: list[dict[str, Any]],
    scope_contract: str,
    bound_refs: list[str],
    completeness: str,
    authority: str,
    semantic_scope_authority: str,
) -> dict[str, Any]:
    if request.surface_id != "connections":
        return {}
    rows = [_connection_inventory_evidence_row(hit) for hit in hits[: max(1, int(request.limit or 80))]]
    rows = [row for row in rows if row.get("ref") or row.get("host")]
    selected_kinds: list[str] = []
    row_refs: list[str] = []
    for row in rows:
        kind = str(row.get("kind", "") or "").strip()
        ref = str(row.get("ref", "") or "").strip()
        if kind and kind not in selected_kinds:
            selected_kinds.append(kind)
        if ref and ref not in row_refs:
            row_refs.append(ref)
    return {
        "surface": "connections",
        "authority": authority,
        "completeness": completeness,
        "scope_contract": scope_contract,
        "semantic_scope_authority": semantic_scope_authority,
        "query": str(query or "").strip(),
        "field_set": _connection_inventory_field_set(rows),
        "row_count": len(rows),
        "selected_kinds": selected_kinds,
        "selected_refs": [str(ref or "").strip() for ref in bound_refs if str(ref or "").strip()],
        "row_refs": row_refs,
        "rows": rows,
    }


def _query_contract_selected_connection_kinds(query: str, available_kinds: set[str]) -> list[str]:
    tokens = set(_tokenize_inventory_scope(query))
    if not (
        _query_requests_network_address(query)
        and bool(tokens & {"server", "servern", "servers"})
        and available_kinds
    ):
        return []
    selected: list[str] = []
    selected_kind_tokens: set[str] = set()
    for kind in sorted(available_kinds):
        kind_tokens = set(_tokenize_inventory_scope(kind))
        if kind_tokens and kind_tokens.issubset(tokens):
            selected.append(kind)
            selected_kind_tokens.update(kind_tokens)
    if not selected:
        return []
    non_scope_tokens = {
        token
        for token in tokens
        if token not in _BROAD_ADDRESS_SCOPE_TOKENS and token not in selected_kind_tokens
    }
    if non_scope_tokens:
        return []
    return selected


def _full_scope_contract_selected_connection_kinds(query: str, available_kinds: set[str]) -> list[str]:
    tokens = set(_tokenize_inventory_scope(query))
    if not tokens or not available_kinds:
        return []
    selected: list[str] = []
    for kind in sorted(available_kinds):
        kind_tokens = set(_tokenize_inventory_scope(kind))
        if kind_tokens and kind_tokens.issubset(tokens):
            selected.append(kind)
    return selected if len(selected) == 1 else []


class SurfaceLoaderRuntime:
    """Loader boundary from TurnPlan context requests to loaded SkillResults."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    async def load_inventory(self, arbitration: AriaTurnArbitration | None) -> list[SkillResult]:
        if arbitration is None:
            return []
        results: list[SkillResult] = []
        requests: list[ContextRequest] = []
        for request in arbitration.plan.context_requests:
            if request.mode == "inventory":
                requests.append(request)
                continue
            if request.surface_id in {"capabilities", "recipes"} and request.mode in {"answer", "search"}:
                requests.append(replace(request, mode="inventory"))
                continue
            if (
                request.surface_id == "connections"
                and request.mode == "answer"
                and _query_requests_network_address(str(request.query or ""))
                and any(str(catalog_id or "").strip().startswith("connection|") for catalog_id in arbitration.plan.priority)
            ):
                requests.append(replace(request, mode="inventory", limit=max(int(request.limit or 0), 50)))
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
        if context_overrides.get("document_target_collections"):
            recall_params["document_target_collections"] = list(context_overrides.get("document_target_collections") or [])
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
        request = self._bind_inventory_request_from_turn_contract(arbitration, request)
        query = str(request.query or self.owner._aria_turn_context_request_query(arbitration, request.surface_id)).strip()
        request = self._bind_full_kind_inventory_request_from_turn_contract(arbitration, request, query)
        if request.surface_id == "capabilities":
            return self._load_capability_inventory(request, query)
        if request.surface_id == "recipes":
            return self._load_recipe_inventory(request, query)
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
                "scope_contract": "unbound_metadata",
                "bound_refs": [],
                "requires_llm_narrowing": True,
                "detail_lines": [
                    *detail_lines,
                    "Routing Debug: context_inventory "
                    f"surface={request.surface_id} mode=inventory matches={len(sources)} query={query or '-'}"
                ],
            },
        )

    def _load_capability_inventory(self, request: ContextRequest, query: str) -> SkillResult:
        configured_kinds = set(self._connection_inventory_kinds())
        bindings = [
            (kind, capability)
            for kind, capability in connection_action_executor_bindings()
            if not configured_kinds or kind in configured_kinds
        ]
        rows = ["Aktive ARIA-Faehigkeiten:"]
        sources: list[dict[str, Any]] = []
        for contract in connection_action_contracts():
            configured_executors = [kind for kind in contract.executors if not configured_kinds or kind in configured_kinds]
            if not configured_executors and configured_kinds:
                continue
            confirm = "ja" if bool(contract.confirmation_required) else "nein"
            executors = ", ".join(configured_executors or list(contract.executors) or ["-"])
            rows.append(
                f"- **{contract.capability}**: Operation `{contract.operation}`, Executor `{executors}`, Bestaetigung `{confirm}`"
            )
            sources.append(
                {
                    "surface": "capabilities",
                    "kind": "capability",
                    "refs": [contract.capability],
                    "items": [
                        {
                            "ref": contract.capability,
                            "operation": contract.operation,
                            "family": contract.family,
                            "executors": list(configured_executors or contract.executors),
                            "confirmation_required": bool(contract.confirmation_required),
                            "configured_bindings": [
                                {"kind": kind, "capability": capability}
                                for kind, capability in bindings
                                if capability == contract.capability
                            ],
                        }
                    ],
                }
            )
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n".join(rows[: max(2, int(request.limit or 80) + 1)]),
            metadata={
                "sources": sources,
                "scope_contract": "bound",
                "bound_refs": [str(source["refs"][0]) for source in sources if source.get("refs")],
                "requires_llm_narrowing": False,
                "detail_lines": [
                    "Routing Debug: inventory_system "
                    f"surface=capabilities matches={len(sources)} query={query or '-'} authoritative=true"
                ],
            },
        )

    def _load_recipe_inventory(self, request: ContextRequest, query: str) -> SkillResult:
        loader = getattr(self.owner, "_load_stored_recipe_runtime", None)
        recipes = loader() if callable(loader) else []
        rows = ["Gespeicherte Rezeptvorlagen:"]
        sources: list[dict[str, Any]] = []
        for recipe in sorted(list(recipes or []), key=lambda item: str(dict(item).get("name", "")).lower()):
            item = dict(recipe or {})
            recipe_id = str(item.get("id", "") or "").strip()
            name = str(item.get("name", "") or recipe_id or "recipe").strip()
            description = str(item.get("description", "") or "").strip()
            enabled = "aktiv" if bool(item.get("enabled", False)) else "deaktiviert"
            connections = ", ".join(str(value).strip() for value in list(item.get("connections", []) or []) if str(value).strip())
            detail = "; ".join(part for part in (description, f"Connections: {connections}" if connections else "", enabled) if part)
            rows.append(f"- **{recipe_id or name}** - {name}" + (f" ({detail})" if detail else ""))
            sources.append(
                {
                    "surface": "recipes",
                    "kind": "recipe",
                    "refs": [recipe_id or name],
                    "items": [
                        {
                            "ref": recipe_id or name,
                            "title": name,
                            "description": description,
                            "enabled": bool(item.get("enabled", False)),
                            "connections": [str(value).strip() for value in list(item.get("connections", []) or []) if str(value).strip()],
                            "keywords": [str(value).strip() for value in list(item.get("keywords", []) or []) if str(value).strip()],
                            "step_count": len(list(item.get("steps", []) or [])),
                        }
                    ],
                }
            )
        if not sources:
            rows.append("- Keine gespeicherten Rezeptvorlagen geladen.")
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n".join(rows[: max(2, int(request.limit or 80) + 1)]),
            metadata={
                "sources": sources,
                "scope_contract": "bound",
                "bound_refs": [str(source["refs"][0]) for source in sources if source.get("refs")],
                "requires_llm_narrowing": False,
                "detail_lines": [
                    "Routing Debug: inventory_system "
                    f"surface=recipes matches={len(sources)} query={query or '-'} authoritative=true"
                ],
            },
        )

    @staticmethod
    def _bind_inventory_request_from_turn_contract(arbitration: AriaTurnArbitration, request: ContextRequest) -> ContextRequest:
        if request.surface_id != "connections" or request.mode != "inventory" or dict(request.budget or {}).get("bind_selected_refs"):
            return request
        budget = dict(request.budget or {})
        selected_refs: list[str] = []
        selected_kinds: list[str] = []
        hinted_ref = str(budget.get("ref_hint") or budget.get("ref") or "").strip()
        hinted_kind = str(budget.get("kind_hint") or budget.get("kind") or "").strip()
        if hinted_ref:
            selected_refs.append(hinted_ref)
        if hinted_kind:
            selected_kinds.append(hinted_kind)
        for catalog_id in list(arbitration.plan.priority or [])[:20]:
            parts = str(catalog_id or "").strip().split("|")
            if len(parts) != 3 or parts[0] != "connection":
                continue
            kind = parts[1].strip()
            ref = parts[2].strip()
            if not kind or not ref:
                continue
            if ref not in selected_refs:
                selected_refs.append(ref)
            if kind not in selected_kinds:
                selected_kinds.append(kind)
        if not selected_refs:
            return request
        if _selected_refs_are_broad_kind_scope(str(request.query or ""), selected_refs, selected_kinds):
            budget.update(
                {
                    "bind_selected_kinds": True,
                    "selected_kinds": selected_kinds,
                    "selected_refs": selected_refs,
                }
            )
            return replace(request, budget=budget)
        budget.update(
            {
                "bind_selected_refs": True,
                "selected_refs": selected_refs,
                "selected_kinds": selected_kinds,
            }
        )
        return replace(request, budget=budget)

    def _bind_full_kind_inventory_request_from_turn_contract(
        self,
        arbitration: AriaTurnArbitration,
        request: ContextRequest,
        query: str,
    ) -> ContextRequest:
        if request.surface_id != "connections" or request.mode != "inventory":
            return request
        budget = dict(request.budget or {})
        if bool(budget.get("bind_selected_refs")) or bool(budget.get("bind_selected_kinds")):
            return request
        plan = arbitration.plan
        scope_authority = str(getattr(plan, "target_scope_authority", "") or "").strip()
        scope_operation = str(getattr(plan, "scope_operation", "") or budget.get("scope_operation", "") or "").strip()
        if scope_authority != "full_kind" and scope_operation != "expand_to_kind":
            return request
        available_kinds = set(self._connection_inventory_kinds())
        selected_kinds: list[str] = []
        selected_refs: list[str] = []
        for catalog_id in list(getattr(plan, "priority", ()) or ())[:20]:
            parts = str(catalog_id or "").strip().split("|")
            if len(parts) != 3 or parts[0] != "connection":
                continue
            kind = parts[1].strip()
            ref = parts[2].strip()
            if kind and kind in available_kinds and kind not in selected_kinds:
                selected_kinds.append(kind)
            if ref and ref not in selected_refs:
                selected_refs.append(ref)
        if not selected_kinds:
            selected_kinds = _full_scope_contract_selected_connection_kinds(query, available_kinds)
        if not selected_kinds:
            return request
        budget.update(
            {
                "bind_selected_kinds": True,
                "selected_kinds": selected_kinds,
                "selected_refs": selected_refs,
                "scope_operation": scope_operation,
                "scope_authority": scope_authority,
                "full_kind_binding_source": "turn_contract",
            }
        )
        return replace(request, budget=budget)

    def _connection_inventory_document_hits(
        self,
        *,
        selected_refs: list[str] | None = None,
        selected_kinds: list[str] | None = None,
        require_host: bool = False,
    ) -> list[dict[str, Any]]:
        selected_ref_set = {str(ref or "").strip() for ref in list(selected_refs or []) if str(ref or "").strip()}
        selected_kind_set = {str(kind or "").strip() for kind in list(selected_kinds or []) if str(kind or "").strip()}
        hits: list[dict[str, Any]] = []
        for document in build_inventory_documents(self.owner.settings):
            if document.surface_id != "connections":
                continue
            if selected_ref_set and str(document.ref or "").strip() not in selected_ref_set:
                continue
            if selected_kind_set and str(document.kind or "").strip() not in selected_kind_set:
                continue
            if require_host and not str(document.host or "").strip():
                continue
            hits.append(
                {
                    "surface_id": document.surface_id,
                    "kind": document.kind,
                    "ref": document.ref,
                    "payload": document.payload(),
                }
            )
        return hits

    def _connection_inventory_kinds(self) -> list[str]:
        kinds: list[str] = []
        for document in build_inventory_documents(self.owner.settings):
            if document.surface_id != "connections":
                continue
            kind = str(document.kind or "").strip().lower()
            if kind and kind not in kinds:
                kinds.append(kind)
        return kinds

    async def _review_connection_inventory_semantic_scope(
        self,
        *,
        query: str,
        hits: list[dict[str, Any]],
        source: str,
    ) -> tuple[list[dict[str, Any]], str, list[str], str]:
        if len(hits) <= 1 or not _query_requests_specific_connection_scope(query):
            return hits, "explicit_config", [], "not_required"
        candidates: list[dict[str, Any]] = []
        for hit in hits:
            payload = dict(hit.get("payload", {}) or {})
            candidates.append(
                {
                    "ref": str(payload.get("ref", "") or hit.get("ref", "") or "").strip(),
                    "kind": str(payload.get("kind", "") or hit.get("kind", "") or "").strip(),
                    "title": str(payload.get("title", "") or "").strip(),
                    "description": str(payload.get("description", "") or "").strip(),
                    "group_name": str(payload.get("group_name", "") or "").strip(),
                    "tags": [str(tag) for tag in list(payload.get("tags", []) or [])[:12]],
                }
            )
        result = await BoundedDecisionClient(getattr(self.owner, "llm_client", None)).decide_json(
            operation=INVENTORY_SEMANTIC_SCOPE_REVIEW_OPERATION,
            system=(
                "You review whether already selected configured connection refs match the user's requested semantic group. "
                "Use only the provided candidate metadata. Keep refs whose title, description, group_name, tags, or ref clearly fit the requested group. "
                "Reject refs whose metadata points to a different purpose. Do not infer from private knowledge. "
                'Return JSON only: {"accepted_refs":["..."],"rejected_refs":["..."],"confidence":"high|medium|low","reason":"short"}'
            ),
            payload={
                "query": str(query or "").strip(),
                "candidates": candidates,
                "rules": {
                    "config_metadata_authority": "Config proves ref/host data, not semantic group membership.",
                    "review_boundary": "Filter only the provided refs; do not add refs.",
                },
            },
            source=source,
        )
        if not result.ok:
            return hits, "candidate", [], f"unavailable:{result.error or 'unknown'}"
        available = {str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip() for hit in hits}
        accepted: list[str] = []
        rejected: list[str] = []
        for ref in list(result.payload.get("accepted_refs", []) or []):
            clean = str(ref or "").strip()
            if clean and clean in available and clean not in accepted:
                accepted.append(clean)
        for ref in list(result.payload.get("rejected_refs", []) or []):
            clean = str(ref or "").strip()
            if clean and clean in available and clean not in rejected:
                rejected.append(clean)
        if not accepted:
            return hits, "candidate", rejected, "no_accepted_refs"
        accepted_set = set(accepted)
        filtered = [
            hit
            for hit in hits
            if str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip() in accepted_set
        ]
        confidence = str(result.payload.get("confidence", "") or "").strip().lower() or "-"
        reason = " ".join(str(result.payload.get("reason", "") or "").strip().split())[:120] or "-"
        return filtered, "reviewed", rejected, f"confidence={confidence} reason={reason}"

    @staticmethod
    def _inventory_skill_result(
        *,
        request: ContextRequest,
        query: str,
        hits: list[dict[str, Any]],
        evidence_debug: list[str],
        scope_contract: str,
        bound_refs: list[str],
        completeness: str = "candidate_only",
        authority: str = "candidate",
        semantic_scope_authority: str = "explicit_config",
        semantic_scope_rejected_refs: list[str] | None = None,
    ) -> SkillResult:
        evidence_bundle = _connection_inventory_evidence_bundle(
            request=request,
            query=query,
            hits=hits,
            scope_contract=scope_contract,
            bound_refs=bound_refs,
            completeness=completeness,
            authority=authority,
            semantic_scope_authority=semantic_scope_authority,
        )
        evidence_bundle_debug = [
            "Routing Debug: evidence_bundle built "
            f"surface={evidence_bundle.get('surface') or '-'} authority={evidence_bundle.get('authority') or '-'} "
            f"completeness={evidence_bundle.get('completeness') or '-'} "
            f"fields={','.join(list(evidence_bundle.get('field_set', []) or [])) or '-'} "
            f"rows={int(evidence_bundle.get('row_count') or 0)}"
        ] if evidence_bundle else []
        if not hits:
            return SkillResult(
                skill_name="context_inventory",
                success=True,
                content="No matching inventory metadata was found for the selected query.",
                metadata={
                    "sources": [],
                    "scope_contract": scope_contract,
                    "bound_refs": bound_refs,
                    "semantic_scope_authority": semantic_scope_authority,
                    "semantic_scope_rejected_refs": list(semantic_scope_rejected_refs or []),
                    "evidence_bundle": evidence_bundle,
                    "requires_llm_narrowing": scope_contract != "bound",
                    "detail_lines": [
                        "Routing Debug: inventory_index "
                        f"surface={request.surface_id} matches=0 query={query or '-'} authoritative=true",
                        *evidence_debug,
                        *evidence_bundle_debug,
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
            source_items: list[dict[str, Any]] = []
            rows.append(f"{connection_kind_label(kind)} ({kind}): {len(refs)} Treffer")
            for hit in kind_hits:
                payload = dict(hit.get("payload", {}) or {})
                ref = str(payload.get("ref", "") or hit.get("ref", "") or "").strip()
                title = str(payload.get("title", "") or "").strip()
                description = str(payload.get("description", "") or "").strip()
                host = str(payload.get("host", "") or "").strip()
                group_name = str(payload.get("group_name", "") or "").strip()
                tags = list(payload.get("tags", []) or [])
                details = "; ".join(
                    part
                    for part in (
                        f"Host: {host}" if host and _query_requests_network_address(query) else "",
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
                source_items.append(
                    {
                        "ref": ref,
                        "title": title,
                        "description": description,
                        "host": host,
                        "group_name": group_name,
                        "tags": [str(tag) for tag in tags[:12]],
                    }
                )
            sources.append({"surface": request.surface_id, "kind": kind, "refs": refs, "items": source_items})
        return SkillResult(
            skill_name="context_inventory",
            success=True,
            content="\n".join(rows[:80]),
            metadata={
                "sources": sources,
                "scope_contract": scope_contract,
                "bound_refs": bound_refs,
                "semantic_scope_authority": semantic_scope_authority,
                "semantic_scope_rejected_refs": list(semantic_scope_rejected_refs or []),
                "evidence_bundle": evidence_bundle,
                "requires_llm_narrowing": scope_contract != "bound",
                "detail_lines": [
                    "Routing Debug: inventory_index "
                    f"surface={request.surface_id} matches={len(hits)} query={query or '-'} authoritative=true",
                    *evidence_debug,
                    *evidence_bundle_debug,
                ],
            },
        )

    async def _load_inventory_index_result(self, request: ContextRequest, query: str) -> SkillResult | None:
        if not request.surface_id or not str(query or "").strip():
            return None
        inventory_cfg = getattr(self.owner.settings, "inventory_index", None)
        if not bool(getattr(inventory_cfg, "enabled", True)):
            return None
        budget = dict(request.budget or {})
        bound_ref = str(budget.get("ref", "") or "").strip()
        bound_kind = str(budget.get("kind", "") or "").strip()
        bound_catalog_id = str(budget.get("catalog_id", "") or "").strip()
        bind_ref = bool(budget.get("bind_ref") or budget.get("exact_ref"))
        selected_refs = [
            str(ref or "").strip()
            for ref in list(budget.get("selected_refs", []) or [])
            if str(ref or "").strip()
        ]
        selected_kinds = [
            str(kind or "").strip()
            for kind in list(budget.get("selected_kinds", []) or [])
            if str(kind or "").strip()
        ]
        kind_authority = "context_request"
        if request.surface_id == "connections" and selected_kinds:
            available_kinds = set(self._connection_inventory_kinds())
            selected_kinds = [kind for kind in selected_kinds if kind in available_kinds]
        elif request.surface_id == "connections":
            available_kinds = set(self._connection_inventory_kinds())
            selected_kinds = _query_contract_selected_connection_kinds(query, available_kinds)
            if selected_kinds:
                kind_authority = "query_contract"
        bind_selected_refs = bool(budget.get("bind_selected_refs")) and bool(selected_refs)
        bind_selected_kinds = bool(budget.get("bind_selected_kinds")) and bool(selected_kinds)
        if selected_kinds and kind_authority == "query_contract" and not bind_selected_refs:
            bind_selected_kinds = True
        if request.surface_id == "connections" and (bound_ref and bind_ref or bind_selected_refs or bind_selected_kinds or _query_requests_broad_connection_inventory(query)):
            if bound_ref and bind_ref:
                hits = self._connection_inventory_document_hits(
                    selected_refs=[bound_ref],
                    selected_kinds=[bound_kind] if bound_kind else [],
                    require_host=_query_requests_network_address(query),
                )
                evidence_debug = [
                    "Routing Debug: inventory_metadata_authority "
                    f"surface={request.surface_id} catalog_id={bound_catalog_id or '-'} kind={bound_kind or '-'} "
                    f"ref={bound_ref} kept={len(hits)} authority=config"
                ]
                return self._inventory_skill_result(
                    request=request,
                    query=query,
                    hits=hits,
                    evidence_debug=evidence_debug,
                    scope_contract="bound",
                    bound_refs=[bound_ref],
                    completeness="explicit_refs",
                    authority="config",
                )
            if bind_selected_refs:
                hits = self._connection_inventory_document_hits(
                    selected_refs=selected_refs,
                    selected_kinds=selected_kinds,
                    require_host=_query_requests_network_address(query),
                )
                semantic_scope_authority = "explicit_config"
                semantic_scope_rejected_refs: list[str] = []
                semantic_review_debug = "not_required"
                if _query_requests_specific_connection_scope(query):
                    hits, semantic_scope_authority, semantic_scope_rejected_refs, semantic_review_debug = (
                        await self._review_connection_inventory_semantic_scope(
                            query=query,
                            hits=hits,
                            source="surface_loader_runtime",
                        )
                    )
                request = replace(request, limit=max(int(request.limit or 0), len(hits), 50))
                evidence_debug = [
                    "Routing Debug: inventory_metadata_authority "
                    f"surface={request.surface_id} selected_refs={','.join(selected_refs) or '-'} "
                    f"selected_kinds={','.join(selected_kinds) or '-'} kept={len(hits)} authority=config "
                    f"semantic_scope_authority={semantic_scope_authority}"
                ]
                if semantic_scope_authority != "explicit_config":
                    evidence_debug.append(
                        "Routing Debug: inventory_semantic_scope_review "
                        f"authority={semantic_scope_authority} rejected={','.join(semantic_scope_rejected_refs) or '-'} "
                        f"{semantic_review_debug}"
                    )
                return self._inventory_skill_result(
                    request=request,
                    query=query,
                    hits=hits,
                    evidence_debug=evidence_debug,
                    scope_contract="bound",
                    bound_refs=[
                        str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip()
                        for hit in hits
                        if str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip()
                    ],
                    completeness="semantic_subset" if semantic_scope_authority == "reviewed" else "explicit_refs",
                    authority="config",
                    semantic_scope_authority=semantic_scope_authority,
                    semantic_scope_rejected_refs=semantic_scope_rejected_refs,
                )
            if bind_selected_kinds:
                hits = self._connection_inventory_document_hits(
                    selected_kinds=selected_kinds,
                    require_host=_query_requests_network_address(query),
                )
                request = replace(request, limit=max(int(request.limit or 0), len(hits), 50))
                evidence_debug = [
                    "Routing Debug: inventory_metadata_authority "
                    f"surface={request.surface_id} selected_refs_hint={','.join(selected_refs) or '-'} "
                    f"selected_kinds={','.join(selected_kinds) or '-'} kept={len(hits)} "
                    f"kind_authority={kind_authority} ref_authority=kind_only authority=config"
                ]
                return self._inventory_skill_result(
                    request=request,
                    query=query,
                    hits=hits,
                    evidence_debug=evidence_debug,
                    scope_contract="bound",
                    bound_refs=[],
                    completeness="full_kind",
                    authority="config",
                )
            hits = self._connection_inventory_document_hits(require_host=True)
            request = replace(request, limit=max(int(request.limit or 0), len(hits), 50))
            evidence_debug = [
                "Routing Debug: inventory_metadata_authority "
                f"surface={request.surface_id} scope=all_host_ip kept={len(hits)} authority=config"
            ]
            return self._inventory_skill_result(
                request=request,
                query=query,
                hits=hits,
                evidence_debug=evidence_debug,
                scope_contract="bound",
                bound_refs=[],
                completeness="full_kind",
                authority="config",
            )
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
        evidence_debug: list[str]
        scope_contract = "candidate_context"
        bound_refs: list[str] = []
        semantic_scope_authority = "explicit_config"
        semantic_scope_rejected_refs: list[str] = []
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
            scope_contract = "bound"
            bound_refs = [bound_ref]
        elif bind_selected_refs:
            pre_bound_count = len(hits)
            selected_ref_set = set(selected_refs)
            selected_kind_set = set(selected_kinds)
            hits = [
                hit
                for hit in hits
                if str(dict(hit.get("payload", {}) or {}).get("ref", "") or hit.get("ref", "") or "").strip() in selected_ref_set
                and (
                    not selected_kind_set
                    or str(dict(hit.get("payload", {}) or {}).get("kind", "") or hit.get("kind", "") or "").strip() in selected_kind_set
                )
            ][: max(1, int(getattr(inventory_cfg, "candidate_limit", 12) or 12))]
            semantic_review_debug = "not_required"
            if _query_requests_specific_connection_scope(query):
                hits, semantic_scope_authority, semantic_scope_rejected_refs, semantic_review_debug = (
                    await self._review_connection_inventory_semantic_scope(
                        query=query,
                        hits=hits,
                        source="surface_loader_runtime",
                    )
                )
            evidence_debug = [
                "Routing Debug: inventory_index_bound "
                f"surface={request.surface_id} selected_refs={','.join(selected_refs) or '-'} "
                f"selected_kinds={','.join(selected_kinds) or '-'} kept={len(hits)} candidates={pre_bound_count} "
                f"semantic_scope_authority={semantic_scope_authority}"
            ]
            if semantic_scope_authority != "explicit_config":
                evidence_debug.append(
                    "Routing Debug: inventory_semantic_scope_review "
                    f"authority={semantic_scope_authority} rejected={','.join(semantic_scope_rejected_refs) or '-'} "
                    f"{semantic_review_debug}"
                )
            scope_contract = "bound"
            bound_refs = [
                str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip()
                for hit in hits
                if str(hit.get("ref", "") or dict(hit.get("payload", {}) or {}).get("ref", "") or "").strip()
            ]
        elif bind_selected_kinds:
            pre_bound_count = len(hits)
            selected_kind_set = set(selected_kinds)
            hits = [
                hit
                for hit in hits
                if str(dict(hit.get("payload", {}) or {}).get("kind", "") or hit.get("kind", "") or "").strip()
                in selected_kind_set
            ]
            request = replace(request, limit=max(int(request.limit or 0), len(hits), 50))
            evidence_debug = [
                "Routing Debug: inventory_index_bound "
                f"surface={request.surface_id} selected_refs_hint={','.join(selected_refs) or '-'} "
                f"selected_kinds={','.join(selected_kinds) or '-'} kept={len(hits)} candidates={pre_bound_count} "
                "ref_authority=kind_only"
            ]
            scope_contract = "bound"
            bound_refs = []
        else:
            hits, evidence_debug = self.owner._aria_turn_inventory_evidence_hits(
                hits,
                request=request,
                query=query,
                limit=int(getattr(inventory_cfg, "candidate_limit", 12) or 12),
            )
        return self._inventory_skill_result(
            request=request,
            query=query,
            hits=hits,
            evidence_debug=evidence_debug,
            scope_contract=scope_contract,
            bound_refs=bound_refs,
            completeness=(
                "explicit_refs"
                if bound_ref and bind_ref
                else "semantic_subset"
                if bind_selected_refs and semantic_scope_authority == "reviewed"
                else "explicit_refs"
                if bind_selected_refs
                else "full_kind"
                if bind_selected_kinds
                else "candidate_only"
            ),
            authority="config" if scope_contract == "bound" else "candidate",
            semantic_scope_authority=semantic_scope_authority,
            semantic_scope_rejected_refs=semantic_scope_rejected_refs,
        )
