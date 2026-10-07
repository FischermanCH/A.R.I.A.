from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import unquote_plus

import pytest

from aria.modules import module_route_path, module_static_asset_path
import aria.modules.memory_admin_ui.routes as memories_routes
from aria.modules.memory_admin_ui.routes import (
    _document_matches_filter,
    _memory_collection_link,
    _memory_document_link,
    _routing_graph_link,
    _build_notes_collection_rows,
    _build_routing_collection_rows,
    _build_system_collection_rows,
    _build_memory_graph,
    _build_memory_drilldown_browser_snapshot,
    _build_qdrant_brain_graph,
    _build_document_collection_groups,
    _build_document_entries,
    _build_memory_groups,
    _build_rollup_entries,
    _build_rollup_groups,
    _default_document_collection_for_user,
    _document_collection_names,
    _is_uploaded_file,
    _memories_redirect,
    _memories_map_redirect,
    _memories_create_redirect,
    _memories_import_redirect,
    _memories_maintenance_redirect,
    _memories_overview_redirect,
    _normalize_document_collection_name,
    _resolve_document_target_collection,
)
from aria.modules.system_diagnostics.qdrant_collection_classifier import classify_qdrant_collection
from aria.skills.base import SkillResult
from aria.skills.memory import MemorySkill
from aria.modules.navigation_shell.navigation import admin_nav_groups, context_nav_context, context_nav_items, nav_section_items, settings_nav_groups
from fastapi import UploadFile as FastAPIUploadFile
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile as StarletteUploadFile
from types import SimpleNamespace


def _sanitize_collection_name(value: str | None) -> str:
    import re

    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return clean[:64]


def _extract_brain_payload(page: str) -> dict[str, object]:
    match = re.search(r'<script type="application/json" data-brain-payload>(.*?)</script>', page, re.S)
    assert match is not None
    return json.loads(html.unescape(match.group(1)))


def _extract_memory_browser_payload(page: str) -> dict[str, object]:
    match = re.search(r'<script type="application/json" data-memory-browser-payload>(.*?)</script>', page, re.S)
    assert match is not None
    return json.loads(html.unescape(match.group(1)))


def _first_memory_subnav(page: str) -> str:
    start = page.find('<nav class="memory-subnav"')
    if start < 0:
        return ""
    end = page.find("</nav>", start)
    return page[start : end + len("</nav>")] if end >= 0 else page[start:]


def _maintenance_section(page: str, focus: str) -> str:
    start = page.find(f'id="maint-{focus}"')
    assert start >= 0
    section_start = page.rfind("<section", 0, start)
    end = page.find("</section>", start)
    assert section_start >= 0 and end >= 0
    return page[section_start : end + len("</section>")]


def _build_memories_app(
    memory_graph_points: list[dict[str, object]] | None = None,
    *,
    advanced_mode: bool = True,
    auth_role: str = "admin",
    memory_skill_enabled: bool = True,
    authenticated: bool = True,
    observed_claim_store: object | None = None,
    observed_sequence_store: object | None = None,
    project_root: Path | None = None,
    include_observed_store_attributes: bool = True,
    qdrant: object | None = None,
    username: str = "tester",
) -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    import aria.modules.memory_admin_ui.routes as memories_routes_module

    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault(
        "module_route_path",
        lambda module_id, route_path: memories_routes_module.module_route_path(module_id, route_path) or "",
    )
    templates.env.globals.setdefault(
        "module_static_asset_url",
        lambda module_id, asset_name: f"/static/{asset_name}"
        if module_static_asset_path(module_id, asset_name, Path(__file__).resolve().parents[1])
        else "",
    )
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)

    settings = SimpleNamespace(
        aria=SimpleNamespace(public_url="https://aria.test"),
        ui=SimpleNamespace(title="Memories Test"),
        inventory_index=SimpleNamespace(
            enabled=True,
            run_on_startup=True,
            keep_backup=True,
            cron="17 */6 * * *",
            timezone="Europe/Zurich",
            score_threshold=0.35,
            candidate_limit=12,
        ),
        memory=SimpleNamespace(
            backend="qdrant",
            enabled=True,
            qdrant_url="http://qdrant.local:6333",
            qdrant_api_key="secret-key",
            compression_summary_prompt="prompts/memory_summary.md",
            collections=SimpleNamespace(
                sessions=SimpleNamespace(
                    compress_after_days=7,
                    monthly_after_days=30,
                )
            ),
        ),
        )

    class _MemorySkill:
        def __init__(self) -> None:
            self.text_updates: list[dict[str, object]] = []
            self.payload_updates: list[dict[str, object]] = []
            self.execute_calls: list[dict[str, object]] = []
            self.list_calls: list[dict[str, object]] = []
            self.search_calls: list[dict[str, object]] = []
            self.deleted_points: list[dict[str, object]] = []
            self.deleted_documents: list[dict[str, object]] = []
            self.stored_personal_claims: list[dict[str, object]] = []
            self.learning_point: dict[str, object] = {
                "id": "candidate-point-1",
                "collection": "aria_learning_candidates_tester",
                "type": "learning_candidate",
                "label": "Learning candidate",
                "text": "Learning Candidate: durable source rule\nType: source_rule_candidate\nRisk: low",
                "timestamp": "2026-07-23T00:00:00+00:00",
                "source": "learning_synthesis",
                "learning_effect": "review_only",
                "learning_purpose": "synthesis_review",
                "importance_score": 0.8,
                "review_worthy": True,
                "synthesis_target": "source_rule_candidate",
                "synthesis_state": "canonical",
                "candidate_status": "proposed",
                "artifact_type": "source_rule_candidate",
                "risk": "low",
                "promotion_state": "",
                "promotion_gate_result": "",
                "promotion_gate_reason": "",
                "apply_state": "",
                "regression_status": "",
                "regression_ref": "",
                "regression_verify_result": "",
                "activation_state": "",
                "title": "Durable test procedure",
                "summary": "A complete learning point shown on the page.",
                "source_point_ids": ["raw-point-1", "raw-point-2"],
                "review_queue": True,
                "user_id": "tester",
            }
            self.raw_learning_point: dict[str, object] = {
                **self.learning_point,
                "id": "raw-candidate-point-1",
                "source": "learning_classifier",
                "synthesis_state": "",
                "source_point_ids": [],
                "review_queue": False,
                "title": "Raw learning evidence",
                "summary": "Visible evidence that is not a manual review task.",
            }
            self.personal_claim_point: dict[str, object] = {
                "id": "personal-claim-point-1",
                "collection": "aria_preferences_tester",
                "type": "preference",
                "text": "short answers",
                "user_id": "tester",
                "personal_claim_contract": "personal_claim_v1",
                "claim_id": "personal-claim-1",
                "claim_key": "personal-claim-key-1",
                "claim_kind": "preference",
                "claim_subject": "user",
                "claim_predicate": "preferred answer detail",
                "claim_value": "short answers",
                "claim_scope": "global",
                "claim_scope_ref": "",
                "claim_confidence": 0.9,
                "claim_authority": "explicit_user",
                "claim_risk": "low",
                "claim_status": "active",
                "claim_presented_count": 4,
                "claim_used_count": 3,
                "claim_changed_outcome_count": 2,
                "claim_positive_feedback_count": 1,
                "claim_negative_feedback_count": 0,
                "claim_last_used_at": "2026-07-23T02:00:00+00:00",
            }

        async def update_memory_point(
            self,
            user_id: str,
            collection: str,
            point_id: str,
            text: str,
        ) -> bool:
            self.text_updates.append(
                {
                    "user_id": user_id,
                    "collection": collection,
                    "point_id": point_id,
                    "text": text,
                }
            )
            return True

        async def get_user_collection_stats(self, _username: str) -> list[dict[str, object]]:
            return [
                {"name": "aria_facts_tester", "points": 12, "kind": "fact"},
                {"name": "aria_learning_tester", "points": 2, "kind": "reflection"},
                {"name": "aria_learning_events_tester", "points": 1, "kind": "learning_event"},
                {"name": "aria_learning_candidates_tester", "points": 1, "kind": "learning_candidate"},
                {"name": "aria_learning_active_hints_tester", "points": 1, "kind": "learning_active_hint"},
                {"name": "aria_learning_evals_tester", "points": 1, "kind": "learning_eval"},
            ]

        async def list_learning_points_global(self, _username: str) -> list[dict[str, object]]:
            return [dict(self.learning_point), dict(self.raw_learning_point)]

        async def list_personal_claims(self, *, user_id: str, limit: int = 500) -> list[dict[str, object]]:
            assert user_id == "tester"
            return [dict(self.personal_claim_point), *[dict(row) for row in self.stored_personal_claims]][:limit]

        async def get_memory_point(
            self,
            user_id: str,
            collection: str,
            point_id: str,
        ) -> dict[str, object] | None:
            if (
                user_id == self.learning_point["user_id"]
                and collection == self.learning_point["collection"]
                and point_id == self.learning_point["id"]
            ):
                return dict(self.learning_point)
            if (
                user_id == self.personal_claim_point["user_id"]
                and collection == self.personal_claim_point["collection"]
                and point_id == self.personal_claim_point["id"]
            ):
                return dict(self.personal_claim_point)
            return None

        async def list_memory_graph_points(
            self,
            user_id: str,
            limit: int = 96,
            collection_limit: int = 18,
            preferred_collections: list[str] | tuple[str, ...] | None = None,
        ) -> list[dict[str, object]]:
            _ = (user_id, limit, collection_limit, preferred_collections)
            if memory_graph_points is not None:
                return memory_graph_points
            return [
                {
                    "id": "point-a",
                    "collection": "aria_facts_tester",
                    "type": "fact",
                    "label": "Fact",
                    "text": "SSH server context for development boxes",
                    "source": "memory",
                    "timestamp": "2026-06-06T01:00:00+00:00",
                    "vector": [1.0, 0.0, 0.0],
                },
                {
                    "id": "point-b",
                    "collection": "aria_facts_tester",
                    "type": "fact",
                    "label": "Fact",
                    "text": "Development server health status",
                    "source": "memory",
                    "timestamp": "2026-06-06T01:01:00+00:00",
                    "vector": [0.96, 0.04, 0.0],
                },
                {
                    "id": "doc-graph-1",
                    "collection": "aria_docs_tester_manuals",
                    "type": "document",
                    "label": "DOKUMENT",
                    "text": "Setup manual graph chunk with import notes.",
                    "source": "rag_upload",
                    "timestamp": "2026-06-16T10:00:00+00:00",
                    "document_name": "Setup Manual.pdf",
                    "chunk_index": 1,
                    "chunk_total": 2,
                    "vector": [0.1, 0.95, 0.0],
                },
                {
                    "id": "doc-graph-2",
                    "collection": "aria_docs_tester_manuals",
                    "type": "document",
                    "label": "DOKUMENT",
                    "text": "Setup manual graph chunk with troubleshooting notes.",
                    "source": "rag_upload",
                    "timestamp": "2026-06-16T10:01:00+00:00",
                    "document_name": "Setup Manual.pdf",
                    "chunk_index": 2,
                    "chunk_total": 2,
                    "vector": [0.12, 0.93, 0.01],
                },
                {
                    "id": "note-graph-1",
                    "collection": "aria_notes_tester",
                    "type": "notes",
                    "label": "NOTE",
                    "text": "Area41 note graph chunk with travel context.",
                    "source": "notes",
                    "timestamp": "2026-06-17T10:00:00+00:00",
                    "note_title": "Area41",
                    "vector": [0.0, 0.1, 0.95],
                },
                {
                    "id": "note-graph-2",
                    "collection": "aria_notes_tester",
                    "type": "notes",
                    "label": "NOTE",
                    "text": "Area41 note graph chunk with conference context.",
                    "source": "notes",
                    "timestamp": "2026-06-17T10:01:00+00:00",
                    "note_title": "Area41",
                    "vector": [0.0, 0.12, 0.93],
                },
            ]

        async def list_memories_global(
            self,
            user_id: str,
            type_filter: str = "all",
            limit: int = 200,
            collection_filter: str = "",
        ) -> list[dict[str, object]]:
            self.list_calls.append(
                {
                    "user_id": user_id,
                    "type_filter": type_filter,
                    "limit": limit,
                    "collection_filter": collection_filter,
                }
            )
            _ = (user_id, limit)
            rows = [
                {
                    "id": "candidate-1",
                    "collection": "aria_learning_candidates_tester",
                    "type": "learning_candidate",
                    "label": "LERN-KANDIDAT",
                    "text": "Learning Candidate: Official page excerpts first\nType: source_rule_candidate\nStatus: proposed\nRisk: low",
                    "source": "learning_classifier",
                    "timestamp": "2026-06-15T10:00:00+00:00",
                    "candidate_status": "reviewed",
                    "promotion_state": "eligible",
                    "promotion_gate_result": "eligible",
                    "apply_state": "prepared",
                    "apply_gate_result": "prepared",
                    "regression_required": True,
                    "regression_status": "missing",
                    "regression_ref": "",
                },
                {
                    "id": "candidate-app-1",
                    "collection": "aria_learning_candidates_tester",
                    "type": "learning_candidate",
                    "label": "LERN-KANDIDAT",
                    "text": (
                        "Learning Candidate: Compose install plan\n"
                        "Type: install_plan_candidate\n"
                        "Status: proposed\n"
                        "Risk: medium\n"
                        "Summary: Review-only install plan from app identity.\n"
                        'App identity hypothesis: {"runtime_kind":"docker_compose","app_root":"/srv/aria","entry_artifacts":["/srv/aria/docker-compose.yml"],"confidence":"medium"}\n'
                        'Install/update plan draft: {"plan_kind":"install_update_plan_draft","runtime_kind":"docker_compose","app_root":"/srv/aria","preflight_checks":["confirm app identity hypothesis with operator"],"backup_targets":["/srv/aria/docker-compose.yml"],"proposed_steps":["run docker compose up -d only after explicit confirmation"],"rollback_steps":["restore backed up config/artifact files"],"requires_confirmation":true,"runtime_activation_allowed":false}\n'
                        'Install/update plan validation: {"validation_state":"review_required","risk_level":"medium","missing_gates":[],"mutating_steps":["run docker compose up -d only after explicit confirmation"],"required_confirmations":["operator_review","explicit_execute_confirmation","mutating_step_confirmation"],"runtime_activation_allowed":false,"promotion_allowed":false}\n'
                        'Health check drafts: [{"check_kind":"tcp_port","target":"8080","command_preview":"ss -ltn | grep \\u0027:8080 \\u0027","mutating":false}]\n'
                        'Regression drafts: [{"test_kind":"plan_preview","name":"test_install_update_plan_renders_without_execution","expected":"plan renders preview"}]\n'
                        'Pytest skeleton proposal: {"proposal_kind":"pytest_skeleton_proposal","target_file":"tests/test_app_plan_generated.py","test_functions":[{"name":"test_install_update_plan_renders_without_execution","test_kind":"plan_preview","act":"call the draft/validation helper under test"}],"safety_notes":["proposal only, do not write files automatically"],"write_allowed":false,"runtime_activation_allowed":false}'
                    ),
                    "source": "learning_classifier",
                    "timestamp": "2026-06-15T10:02:00+00:00",
                    "candidate_status": "reviewed",
                    "promotion_state": "reviewed_blocked",
                    "promotion_gate_result": "blocked",
                    "apply_state": "",
                    "regression_status": "missing",
                    "regression_ref": "",
                },
                {
                    "id": "event-1",
                    "collection": "aria_learning_events_tester",
                    "type": "learning_event",
                    "label": "LERN-EVENT",
                    "text": "Learning Event: evt-1",
                    "source": "learning_event_ledger",
                    "timestamp": "2026-06-15T09:59:00+00:00",
                },
                {
                    "id": "eval-1",
                    "collection": "aria_learning_evals_tester",
                    "type": "learning_eval",
                    "label": "LERN-EVAL",
                    "text": "Learning Eval Dry-Run: source_rule_candidate\nPromotion allowed: no",
                    "source": "learning_validator",
                    "timestamp": "2026-06-15T10:01:00+00:00",
                },
                {
                    "id": "doc-1-chunk-1",
                    "collection": "aria_docs_tester_manuals",
                    "type": "document",
                    "label": "DOKUMENT",
                    "text": "Setup manual first chunk with import notes.",
                    "source": "rag_upload",
                    "timestamp": "2026-06-16T10:00:00+00:00",
                    "document_id": "doc-1",
                    "document_name": "Setup Manual.pdf",
                },
                {
                    "id": "doc-1-chunk-2",
                    "collection": "aria_docs_tester_manuals",
                    "type": "document",
                    "label": "DOKUMENT",
                    "text": "Setup manual second chunk with troubleshooting notes.",
                    "source": "rag_upload",
                    "timestamp": "2026-06-16T10:01:00+00:00",
                    "document_id": "doc-1",
                    "document_name": "Setup Manual.pdf",
                },
                {
                    "id": "death-note-chunk-1",
                    "collection": "aria_notes_tester",
                    "type": "notes",
                    "label": "NOTIZEN",
                    "text": "# Sample Project Note\n\n# Tweaks\n## Alpha Level\n- Mehr Druck fuer Player.",
                    "source": "notes",
                    "timestamp": "2026-07-20T10:44:00+00:00",
                    "note_id": "death-pays-overtime",
                    "note_title": "Sample Project Note",
                    "note_folder": "Games",
                    "note_path": "Games/death-pays-overtime.md",
                    "note_tags": ["game", "tweaks"],
                    "chunk_index": 1,
                    "chunk_total": 2,
                },
                {
                    "id": "death-note-chunk-2",
                    "collection": "aria_notes_tester",
                    "type": "notes",
                    "label": "NOTIZEN",
                    "text": "# Bugs\n\nPopups und Overlays stoeren das Game.",
                    "source": "notes",
                    "timestamp": "2026-07-20T10:44:01+00:00",
                    "note_id": "death-pays-overtime",
                    "note_title": "Sample Project Note",
                    "note_folder": "Games",
                    "note_path": "Games/death-pays-overtime.md",
                    "note_tags": ["game", "bugs"],
                    "chunk_index": 2,
                    "chunk_total": 2,
                },
            ]
            clean_type = str(type_filter or "all").strip().lower()
            clean_collection = str(collection_filter or "").strip()
            if clean_type and clean_type != "all":
                rows = [row for row in rows if str(row.get("type", "")).strip().lower() == clean_type]
            if clean_collection:
                rows = [row for row in rows if str(row.get("collection", "")).strip() == clean_collection]
            return rows

        async def search_memories(
            self,
            user_id: str,
            query: str,
            type_filter: str = "all",
            top_k: int = 200,
        ) -> list[dict[str, object]]:
            self.search_calls.append(
                {
                    "user_id": user_id,
                    "query": query,
                    "type_filter": type_filter,
                    "top_k": top_k,
                }
            )
            rows = await self.list_memories_global(user_id=user_id, type_filter=type_filter, limit=top_k)
            clean_query = str(query or "").strip().lower()
            if not clean_query:
                return rows
            return [
                row
                for row in rows
                if clean_query in str(row.get("text", "")).lower()
                or clean_query in str(row.get("label", "")).lower()
                or clean_query in str(row.get("document_name", "")).lower()
                or clean_query in str(row.get("note_title", "")).lower()
            ]

        async def update_memory_point_payload(
            self,
            user_id: str,
            collection: str,
            point_id: str,
            payload_updates: dict[str, object],
        ) -> bool:
            self.payload_updates.append(
                {
                    "user_id": user_id,
                    "collection": collection,
                    "point_id": point_id,
                    "payload_updates": dict(payload_updates),
                }
            )
            if collection == self.learning_point["collection"] and point_id == self.learning_point["id"]:
                self.learning_point.update(payload_updates)
            if collection == self.personal_claim_point["collection"] and point_id == self.personal_claim_point["id"]:
                self.personal_claim_point.update(payload_updates)
            return True

        async def delete_memory_point(
            self,
            user_id: str,
            collection: str,
            point_id: str,
        ) -> bool:
            self.deleted_points.append(
                {
                    "user_id": user_id,
                    "collection": collection,
                    "point_id": point_id,
                }
            )
            return True

        async def delete_document(
            self,
            user_id: str,
            collection: str,
            *,
            document_id: str = "",
            document_name: str = "",
        ) -> int:
            self.deleted_documents.append(
                {
                    "user_id": user_id,
                    "collection": collection,
                    "document_id": document_id,
                    "document_name": document_name,
                }
            )
            return 2

        async def execute(self, query: str, params: dict) -> SkillResult:
            self.execute_calls.append({"query": query, "params": dict(params)})
            if params.get("source") == "personal_claim":
                point_id = f"manual-claim-{len(self.stored_personal_claims) + 1}"
                collection = str(params.get("collection") or "")
                payload = dict(params.get("payload_metadata") or {})
                self.stored_personal_claims.append(
                    {
                        "id": point_id,
                        "point_id": point_id,
                        "collection": collection,
                        "type": str(params.get("memory_type") or "fact"),
                        "text": str(params.get("text") or query),
                        "user_id": "tester",
                        **payload,
                    }
                )
                return SkillResult(
                    skill_name="memory",
                    content="Speicheraktion erfolgreich.",
                    success=True,
                    metadata={"point_id": point_id, "collection": collection},
                )
            return SkillResult(skill_name="memory", content="Speicheraktion erfolgreich.", success=True)

    memory_skill = _MemorySkill() if memory_skill_enabled else None
    if memory_skill is not None and qdrant is not None:
        memory_skill.qdrant = qdrant
    pipeline_attributes: dict[str, object] = {
        "memory_skill": memory_skill,
        "_facts_collection_for_user": lambda user_id: f"aria_facts_{str(user_id).lower()}",
        "_preferences_collection_for_user": lambda user_id: f"aria_preferences_{str(user_id).lower()}",
    }
    if project_root is not None:
        pipeline_attributes["_project_root"] = project_root
    if include_observed_store_attributes:
        pipeline_attributes.update(
            _native_observed_claim_store=observed_claim_store,
            _native_observed_sequence_store=observed_sequence_store,
        )
    pipeline = SimpleNamespace(**pipeline_attributes)
    if memory_skill is not None:
        app.state.memory_skill = memory_skill

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.authenticated = authenticated
        request.state.auth_user = username if authenticated else ""
        request.state.auth_role = auth_role
        request.state.can_access_users = False
        request.state.can_access_advanced_config = advanced_mode
        request.state.debug_mode = True
        request.state.lang = "en"
        request.state.cookie_names = {}
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.update_status = SimpleNamespace(update_available=False)
        request.state.ui_theme = "matrix"
        request.state.ui_background = "grid"
        request.state.logical_back_url = ""
        return await call_next(request)

    from aria.modules.memory_admin_ui.routes import register_memories_routes

    async def _qdrant_overview(_request: Request) -> dict[str, object]:
        return {
            "reachable": True,
            "collections": [
                {"name": "aria_facts_tester", "points": 12, "status": "ok"},
                {"name": "aria_notes_tester", "points": 6, "status": "ok"},
                {"name": "aria_docs_tester_manuals", "points": 8, "status": "ok"},
                {"name": "aria_learning_tester", "points": 2, "status": "ok"},
                {"name": "aria_learning_events_tester", "points": 1, "status": "ok"},
                {"name": "aria_learning_candidates_tester", "points": 1, "status": "ok"},
                {"name": "aria_learning_active_hints_tester", "points": 1, "status": "ok"},
                {"name": "aria_learning_evals_tester", "points": 1, "status": "ok"},
                {"name": "aria_routing_connections_aria_8800", "points": 5, "status": "green"},
                {"name": "aria_recipe_experience_tester", "points": 0, "status": "ok"},
            ],
            "collection_count": 10,
        }

    async def _inventory_index_status(_settings: object) -> dict[str, object]:
        return {
            "status": "ok",
            "message": "Inventory index ready: 2/2 items indexed.",
            "collection_name": "aria_inventory_test",
            "backup_collection_name": "aria_inventory_test__backup",
            "document_count": 2,
            "indexed_count": 2,
            "meta_collection_name": "aria_meta_catalog_test",
            "meta_document_count": 3,
            "meta_indexed_count": 3,
            "backup_count": 2,
            "indexed_config_hash": "abcdef1234567890",
            "indexed_meta_catalog_hash": "fedcba0987654321",
            "detail": "",
        }

    register_memories_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_pipeline=lambda: pipeline,
        get_username_from_request=lambda _request: username if authenticated else "",
        get_auth_session_from_request=lambda _request: {"role": auth_role} if authenticated else None,
        sanitize_role=lambda value: str(value or "").strip().lower(),
        qdrant_overview=_qdrant_overview,
        qdrant_dashboard_url=lambda _request: "http://qdrant.local:6333/dashboard",
        parse_collection_day_suffix=lambda _value: None,
        sanitize_collection_name=_sanitize_collection_name,
        default_memory_collection_for_user=lambda username: f"aria_facts_{username.lower()}",
        get_effective_memory_collection=lambda _request, username: f"aria_facts_{username.lower()}",
        read_raw_config=lambda: {},
        write_raw_config=lambda _raw: None,
        reload_runtime=lambda: None,
        resolve_prompt_file=lambda value: Path("/tmp") / value,
        get_secure_store=lambda _raw=None: None,
        memory_collection_cookie="aria_memory_collection",
        inventory_index_status_builder=_inventory_index_status,
    )
    return TestClient(app)


class _FakeLegacyLearningQdrant:
    def __init__(self, names: list[str], *, fail_delete: str = "") -> None:
        self.names = set(names)
        self.deleted: list[str] = []
        self.fail_delete = fail_delete
        self.get_calls = 0

    async def get_collections(self) -> object:
        self.get_calls += 1
        return SimpleNamespace(
            collections=[SimpleNamespace(name=name) for name in sorted(self.names)]
        )

    async def collection_exists(self, collection_name: str) -> bool:
        return collection_name in self.names

    async def delete_collection(self, collection_name: str) -> None:
        if collection_name == self.fail_delete:
            raise RuntimeError("delete unavailable")
        self.deleted.append(collection_name)
        self.names.remove(collection_name)


def _write_observed_runtime(project_root: Path, *, include_other_user: bool = False) -> tuple[Path, Path]:
    runtime_root = project_root / "data" / "runtime"
    runtime_root.mkdir(parents=True)
    claim_users = {"tester": {"claim-a": {"count": 6}, "claim-b": {"count": 2}}}
    sequence_users = {"tester": {"sequence-a": {"count": 3}}}
    cross_host_offers = {"tester": ["recipe-a\u0000new-host"]}
    if include_other_user:
        claim_users["other"] = {"claim-other": {"count": 4}}
        sequence_users["other"] = {"sequence-other": {"count": 5}}
        cross_host_offers["other"] = ["recipe-other\u0000other-host"]
    claims_path = runtime_root / "observed_claims.json"
    sequences_path = runtime_root / "observed_sequences.json"
    claims_path.write_text(json.dumps({"users": claim_users}), encoding="utf-8")
    sequences_path.write_text(
        json.dumps({"users": sequence_users, "cross_host_offers": cross_host_offers}),
        encoding="utf-8",
    )
    return claims_path, sequences_path


def test_reset_learning_suggestions_works_without_prior_native_turn(tmp_path: Path) -> None:
    claims_path, sequences_path = _write_observed_runtime(tmp_path)
    client = _build_memories_app(
        project_root=tmp_path,
        include_observed_store_attributes=False,
    )

    response = client.post(
        "/memories/maintenance/reset-learning-suggestions",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/memories/maintenance?info=Learning+suggestions+reset%3A+3."
        "&focus=reset#maint-reset"
    )
    assert "tester" not in json.loads(claims_path.read_text(encoding="utf-8"))["users"]
    sequences = json.loads(sequences_path.read_text(encoding="utf-8"))
    assert "tester" not in sequences["users"]
    assert "tester" not in sequences["cross_host_offers"]


def test_reset_learning_suggestions_is_strictly_user_scoped(tmp_path: Path) -> None:
    claims_path, sequences_path = _write_observed_runtime(tmp_path, include_other_user=True)
    client = _build_memories_app(
        project_root=tmp_path,
        include_observed_store_attributes=False,
    )

    response = client.post(
        "/memories/maintenance/reset-learning-suggestions",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/memories/maintenance?info=Learning+suggestions+reset%3A+3."
        "&focus=reset#maint-reset"
    )
    claims = json.loads(claims_path.read_text(encoding="utf-8"))
    sequences = json.loads(sequences_path.read_text(encoding="utf-8"))
    assert claims["users"] == {"other": {"claim-other": {"count": 4}}}
    assert sequences["users"] == {"other": {"sequence-other": {"count": 5}}}
    assert sequences["cross_host_offers"] == {"other": ["recipe-other\u0000other-host"]}


@pytest.mark.parametrize("file_state", ["missing", "empty"])
def test_reset_learning_suggestions_missing_or_empty_files_is_a_safe_noop(
    tmp_path: Path,
    file_state: str,
) -> None:
    if file_state == "empty":
        runtime_root = tmp_path / "data" / "runtime"
        runtime_root.mkdir(parents=True)
        (runtime_root / "observed_claims.json").write_text("", encoding="utf-8")
        (runtime_root / "observed_sequences.json").write_text("", encoding="utf-8")
    client = _build_memories_app(
        project_root=tmp_path,
        include_observed_store_attributes=False,
    )

    response = client.post(
        "/memories/maintenance/reset-learning-suggestions",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/memories/maintenance?info=Nothing+to+reset."
        "&focus=reset#maint-reset"
    )


def test_reset_learning_suggestions_rejects_unauthenticated_request() -> None:
    client = _build_memories_app(authenticated=False)

    response = client.post(
        "/memories/maintenance/reset-learning-suggestions",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_memories_maintenance_renders_confirmed_learning_suggestions_reset() -> None:
    response = _build_memories_app().get("/memories/maintenance")

    assert response.status_code == 200
    assert "Lern-Vorschläge zurücksetzen" in response.text
    assert "Wiederholungs-Zähler dieses Nutzers" in response.text
    assert "KEINE gespeicherten Erinnerungen oder Rezepte" in response.text
    assert 'action="/memories/maintenance/reset-learning-suggestions"' in response.text
    assert 'name="csrf_token" value="test-csrf"' in response.text
    assert "return window.confirm(" in response.text


def test_cleanup_legacy_learning_collections_is_user_scoped_and_idempotent() -> None:
    protected = {
        "aria_facts_fischerman",
        "aria_preferences_fischerman",
        "aria_recipe_experience_fischerman",
        "aria_docs_fischerman",
        "aria_doc_guides_fischerman",
        "aria_doc_meta_fischerman",
        "aria_notes_fischerman",
        "aria_sessions_fischerman",
        "aria_context-mem_fischerman",
        "aria_routing_fischerman",
        "aria_meta_catalog_fischerman",
        "aria_inventory_fischerman",
        "aria_learning_candidates_fischerman__backup",
        "aria_learning_other",
        "external_fischerman",
    }
    removable = {
        "aria_learning_candidates_fischerman",
        "aria_learning_evals_fischerman",
        "aria_learning_events_fischerman",
    }
    qdrant = _FakeLegacyLearningQdrant(sorted(protected | removable))
    client = _build_memories_app(qdrant=qdrant, username="fischerman")

    first = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert first.status_code == 303
    assert "removed%3A+3." in first.headers["location"]
    assert all(name in first.headers["location"] for name in removable)
    assert set(qdrant.deleted) == removable
    assert qdrant.names == protected

    second = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert second.status_code == 303
    assert "Nothing+to+clean+up" in second.headers["location"]
    assert set(qdrant.deleted) == removable
    assert qdrant.names == protected


def test_cleanup_legacy_learning_collections_rejects_unauthenticated_request() -> None:
    client = _build_memories_app(authenticated=False)

    response = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 401


def test_cleanup_legacy_learning_collections_contains_per_collection_failures() -> None:
    failed = "aria_learning_candidates_fischerman"
    removable = {
        failed,
        "aria_learning_evals_fischerman",
        "aria_learning_events_fischerman",
    }
    qdrant = _FakeLegacyLearningQdrant(sorted(removable), fail_delete=failed)
    client = _build_memories_app(qdrant=qdrant, username="fischerman")

    response = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "removed%3A+2." in response.headers["location"]
    assert set(qdrant.deleted) == removable - {failed}
    assert qdrant.names == {failed}


def test_memories_maintenance_renders_confirmed_legacy_learning_cleanup() -> None:
    qdrant = _FakeLegacyLearningQdrant(["aria_learning_candidates_tester"])
    client = _build_memories_app(qdrant=qdrant)
    response = client.get("/memories/maintenance")

    assert response.status_code == 200
    assert "Alte Lern-Collections aufräumen" in response.text
    assert "Gespeicherte Erinnerungen" in response.text
    assert "Recipe Experience" in response.text
    assert 'action="/memories/maintenance/cleanup-legacy-learning"' in response.text
    assert 'name="csrf_token" value="test-csrf"' in response.text
    assert "return window.confirm(" in response.text
    assert qdrant.get_calls == 0

    memory_browser = client.get("/memories")
    assert memory_browser.status_code == 200
    assert "/memories/maintenance/cleanup-legacy-learning" not in memory_browser.text


def test_maintenance_cleanup_feedback_redirects_and_renders_inside_cleanup_card() -> None:
    qdrant = _FakeLegacyLearningQdrant(["aria_learning_candidates_fischerman"])
    client = _build_memories_app(qdrant=qdrant, username="fischerman")

    response = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=True,
    )

    assert response.history[0].headers["location"].endswith(
        "&focus=cleanup#maint-cleanup"
    )
    cleanup = _maintenance_section(response.text, "cleanup")
    assert "Legacy learning collections removed: 1." in cleanup
    assert response.text.count("Legacy learning collections removed: 1.") == 1


def test_maintenance_feedback_focus_contract_covers_all_three_actions() -> None:
    client = _build_memories_app()

    rollup = client.post(
        "/memories/maintenance",
        data={"source_view": "maintenance"},
        follow_redirects=False,
    )
    reset = client.post(
        "/memories/maintenance/reset-learning-suggestions",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    cleanup = client.post(
        "/memories/maintenance/cleanup-legacy-learning",
        data={"csrf_token": "test-csrf"},
        follow_redirects=False,
    )
    non_maintenance_rollup = client.post(
        "/memories/maintenance",
        data={"source_view": ""},
        follow_redirects=False,
    )

    assert rollup.headers["location"].endswith("&focus=rollup#maint-rollup")
    assert reset.headers["location"].endswith("&focus=reset#maint-reset")
    assert cleanup.headers["location"].endswith("&focus=cleanup#maint-cleanup")
    assert non_maintenance_rollup.headers["location"].startswith("/memories?")
    assert "focus=" not in non_maintenance_rollup.headers["location"]
    assert "#maint-" not in non_maintenance_rollup.headers["location"]


def test_maintenance_unknown_focus_keeps_single_top_feedback_fallback() -> None:
    response = _build_memories_app().get(
        "/memories/maintenance?info=Fallback+feedback&focus=unknown"
    )

    assert response.status_code == 200
    assert response.text.count("Fallback feedback") == 1
    assert "Fallback feedback" not in _maintenance_section(response.text, "cleanup")


def test_maintenance_reindex_feedback_renders_once_inside_reindex_card() -> None:
    response = _build_memories_app().get(
        "/memories/maintenance?info=Inventory+index+rebuilt.&focus=reindex"
    )

    assert response.status_code == 200
    reindex = _maintenance_section(response.text, "reindex")
    assert "Inventory index rebuilt." in reindex
    assert response.text.count("Inventory index rebuilt.") == 1


def test_maintenance_reindex_card_is_hidden_without_advanced_access() -> None:
    response = _build_memories_app(advanced_mode=False).get("/memories/maintenance")

    assert response.status_code == 200
    assert 'id="maint-reindex"' not in response.text
    assert 'action="/memories/reindex/run"' not in response.text


def test_maintenance_setup_wording_no_longer_mentions_auto_memory() -> None:
    response = _build_memories_app().get("/memories/maintenance")
    de = json.loads((Path(__file__).resolve().parents[1] / "aria" / "i18n" / "de.json").read_text(encoding="utf-8"))
    en = json.loads((Path(__file__).resolve().parents[1] / "aria" / "i18n" / "en.json").read_text(encoding="utf-8"))

    assert "Auto-Memory" not in response.text
    assert "auto-memory" not in de["memories_maintenance"]["setup_desc"].lower()
    assert "auto-memory" not in de["memories_overview"]["setup_desc"].lower()
    assert "auto-memory" not in en["memories_maintenance"]["setup_desc"].lower()
    assert "auto-memory" not in en["memories_overview"]["setup_desc"].lower()


def test_memories_export_returns_readable_json_attachment_contract() -> None:
    client = _build_memories_app()

    response = client.get("/memories/export?type=all&sort=updated_desc")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert re.fullmatch(
        r'attachment; filename="aria-memory-tester-all-all-\d{8}-\d{6}\.json"',
        response.headers["content-disposition"],
    )
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["user_id"] == "tester"
    assert payload["filter"] == {"type": "all", "query": "", "sort": "updated_desc"}
    assert payload["count"] == len(payload["items"])
    assert payload["count"] > 0
    assert json.loads(response.text) == payload
    assert client.app.state.memory_skill.list_calls[-1] == {
        "user_id": "tester",
        "type_filter": "all",
        "limit": 10000,
        "collection_filter": "",
    }


def test_memory_edit_success_uses_request_language_and_updates_once() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/edit",
        data={
            "collection": "aria_facts_tester",
            "point_id": "fact-1",
            "text": "Updated fact",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "info=Entry+updated" in response.headers["location"]
    assert client.app.state.memory_skill.text_updates == [
        {
            "user_id": "tester",
            "collection": "aria_facts_tester",
            "point_id": "fact-1",
            "text": "Updated fact",
        }
    ]


@pytest.mark.parametrize(
    ("path", "data", "expected_location", "cookie_name", "cookie_value"),
    [
        (
            "/memories/config/select",
            {"collection": "aria_facts_tester"},
            "/memories/config?",
            "aria_memory_collection",
            "aria_facts_tester",
        ),
        (
            "/memories/config/create",
            {"collection_name": "new facts"},
            "/memories/config?",
            "aria_memory_collection",
            "new_facts",
        ),
    ],
)
def test_memory_config_cookie_mutations_use_current_settings(
    path: str,
    data: dict[str, str],
    expected_location: str,
    cookie_name: str,
    cookie_value: str,
) -> None:
    client = _build_memories_app()

    response = client.post(path, data=data, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith(expected_location)
    assert f"{cookie_name}={cookie_value}" in response.headers["set-cookie"]


def test_memories_export_search_uses_search_filename_and_filters_collection() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories/export",
        params={
            "type": "document",
            "q": "setup",
            "collection_filter": "aria_docs_tester_manuals",
            "sort": "updated_asc",
        },
    )

    assert response.status_code == 200
    assert re.fullmatch(
        r'attachment; filename="aria-memory-tester-document-search-\d{8}-\d{6}\.json"',
        response.headers["content-disposition"],
    )
    payload = response.json()
    assert payload["filter"] == {"type": "document", "query": "setup", "sort": "updated_asc"}
    assert payload["count"] == 2
    assert {item["id"] for item in payload["items"]} == {"doc-1-chunk-1", "doc-1-chunk-2"}
    assert {item["collection"] for item in payload["items"]} == {"aria_docs_tester_manuals"}
    assert client.app.state.memory_skill.search_calls[-1] == {
        "user_id": "tester",
        "query": "setup",
        "type_filter": "document",
        "top_k": 5000,
    }


def test_default_document_collection_for_user_uses_docs_prefix() -> None:
    assert _default_document_collection_for_user("Neo User") == "aria_docs_neo_user"


def test_document_collection_names_only_keep_docs_collections() -> None:
    names = _document_collection_names(
        ["aria_docs_handbuch", "aria_facts_neo", "aria_docs_manual", "aria_memory", "aria_docs_manual"]
    )

    assert names == ["aria_docs_handbuch", "aria_docs_manual"]


def test_build_routing_collection_rows_keeps_only_system_routing_collections() -> None:
    rows = _build_routing_collection_rows(
        [
            {"name": "aria_routing_connections_aria_8800", "points": 116, "status": "green"},
            {"name": "aria_facts_neo", "points": 12, "status": "ok"},
            {"name": "aria_docs_neo_manuals", "points": 24, "status": "ok"},
            {"name": "aria_routing_skills_aria_8800", "points": 8, "status": "yellow"},
        ],
        known_user_collection_names={"aria_facts_neo", "aria_docs_neo_manuals"},
        browse_url="/config/routing",
    )

    assert [row["name"] for row in rows] == [
        "aria_routing_connections_aria_8800",
        "aria_routing_skills_aria_8800",
    ]
    assert all(row["kind"] == "routing" for row in rows)
    assert all(row["browse_url"] == "/config/routing" for row in rows)
    assert rows[0]["share_pct"] == 93


def test_build_notes_collection_rows_keeps_only_active_user_notes_collection() -> None:
    rows = _build_notes_collection_rows(
        [
            {"name": "aria_notes_tester", "points": 6, "status": "ok"},
            {"name": "aria_notes_other", "points": 3, "status": "ok"},
            {"name": "aria_facts_tester", "points": 12, "status": "ok"},
        ],
        username="tester",
        browse_url="/notes",
    )

    assert [row["name"] for row in rows] == ["aria_notes_tester"]
    assert rows[0]["kind"] == "notes"
    assert rows[0]["browse_url"] == "/notes"


def test_build_notes_collection_rows_uses_registry_route_readpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    real_route_path = memories_routes.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", tracking_route_path)

    rows = _build_notes_collection_rows(
        [
            {"name": "aria_notes_tester", "points": 6, "status": "ok"},
        ],
        username="tester",
    )

    assert rows[0]["browse_url"] == "/notes"
    assert ("notes", "/notes") in calls


def test_build_notes_collection_rows_fails_closed_without_route_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_notes_route(module_id: str, route_path: str) -> str | None:
        if module_id == "notes" and route_path == "/notes":
            return None
        return module_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", missing_notes_route)

    with pytest.raises(RuntimeError, match="notes route is not registered: /notes"):
        _build_notes_collection_rows(
            [
                {"name": "aria_notes_tester", "points": 6, "status": "ok"},
            ],
            username="tester",
        )


def test_build_system_collection_rows_includes_recipe_experience_and_future_aria_collections() -> None:
    rows = _build_system_collection_rows(
        [
            {"name": "aria_recipe_experience_tester", "points": 0, "status": "ok"},
            {"name": "aria_routing_connections_aria_8800", "points": 5, "status": "ok"},
            {"name": "aria_notes_tester", "points": 6, "status": "ok"},
            {"name": "aria_future_signal_tester", "points": 2, "status": "yellow"},
            {"name": "aria_facts_tester", "points": 12, "status": "ok"},
            {"name": "aria_docs_tester_manuals", "points": 4, "status": "ok"},
        ],
        known_collection_names={"aria_facts_tester"},
    )

    assert [row["name"] for row in rows] == ["aria_recipe_experience_tester", "aria_future_signal_tester"]
    assert rows[0]["kind"] == "recipe_experience"
    assert rows[0]["browse_url"] == "/recipes/mine"
    assert rows[1]["kind"] == "system"
    assert rows[1]["browse_url"] == "/memories/config#qdrant-access"


def test_build_system_collection_rows_uses_registry_route_readpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    real_route_path = memories_routes.module_route_path

    def tracking_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", tracking_route_path)

    rows = _build_system_collection_rows(
        [
            {"name": "aria_recipe_experience_tester", "points": 0, "status": "ok"},
            {"name": "aria_future_signal_tester", "points": 2, "status": "yellow"},
        ],
    )

    assert [row["browse_url"] for row in rows] == [
        "/recipes/mine",
        "/memories/config#qdrant-access",
    ]
    assert ("recipes_ui", "/recipes/mine") in calls
    assert ("memory_admin_ui", "/memories/config") in calls


def test_build_system_collection_rows_fails_closed_without_route_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_recipe_route(module_id: str, route_path: str) -> str | None:
        if module_id == "recipes_ui" and route_path == "/recipes/mine":
            return None
        return module_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", missing_recipe_route)

    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes/mine"):
        _build_system_collection_rows(
            [
                {"name": "aria_recipe_experience_tester", "points": 0, "status": "ok"},
            ],
        )


def test_qdrant_collection_classifier_keeps_learning_collections_as_user_memory() -> None:
    reflection = classify_qdrant_collection("aria_learning_tester", username="tester")
    event = classify_qdrant_collection("aria_learning_events_tester", username="tester")
    candidate = classify_qdrant_collection("aria_learning_candidates_tester", username="tester")
    active_hint = classify_qdrant_collection("aria_learning_active_hints_tester", username="tester")
    eval_collection = classify_qdrant_collection("aria_learning_evals_tester", username="tester")

    assert reflection.kind == "reflection"
    assert reflection.is_user_memory is True
    assert reflection.is_system is False
    assert event.kind == "learning_event"
    assert event.is_user_memory is True
    assert event.is_system is False
    assert candidate.kind == "learning_candidate"
    assert candidate.is_user_memory is True
    assert candidate.is_system is False
    assert active_hint.kind == "learning_active_hint"
    assert active_hint.is_user_memory is True
    assert active_hint.is_system is False
    assert eval_collection.kind == "learning_eval"
    assert eval_collection.is_user_memory is True
    assert eval_collection.is_system is False


def test_memory_browser_keeps_all_learning_entries_and_exposes_effect_metadata() -> None:
    browser = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[{"name": "aria_learning_evals_tester", "points": 2, "kind": "learning_eval"}],
        all_collections=[{"name": "aria_learning_evals_tester", "points": 2}],
        document_rows=[],
        collection_rows=[
            {
                "id": "eval-1",
                "collection": "aria_learning_evals_tester",
                "type": "learning_eval",
                "label": "LERN-EVAL",
                "text": "first eval",
                "learning_effect": "audit_only",
                "importance_score": 0.8,
                "synthesis_target": "regression",
            },
            {
                "id": "eval-2",
                "collection": "aria_learning_evals_tester",
                "type": "learning_eval",
                "label": "LERN-EVAL",
                "text": "second eval",
                "learning_effect": "audit_only",
                "importance_score": 0.6,
                "synthesis_target": "regression",
            },
        ],
        brain=None,
    )

    collection = next(item for item in browser["collections"] if item["name"] == "aria_learning_evals_tester")
    assert len(collection["entries"]) == 2
    assert collection["entries"][0]["learning_effect"] == "audit_only"
    assert collection["entries"][0]["importance_score"] in {0.6, 0.8}


def test_normalize_document_collection_name_adds_docs_prefix() -> None:
    assert _normalize_document_collection_name("handbuch", _sanitize_collection_name) == "aria_docs_handbuch"
    assert _normalize_document_collection_name("aria_docs_manual", _sanitize_collection_name) == "aria_docs_manual"


def test_resolve_document_target_collection_rejects_non_docs_selection() -> None:
    try:
        _resolve_document_target_collection(
            request=object(),  # type: ignore[arg-type]
            username="Neo User",
            selected_collection="aria_facts_neo_user",
            new_collection_name="",
            existing_collections=["aria_docs_neo_user", "aria_facts_neo_user"],
            sanitize_collection_name=_sanitize_collection_name,
            get_effective_memory_collection=lambda _request, _username: "aria_memory_neo_user",
        )
    except ValueError as exc:
        assert "Dokument-Collections" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-document collection selection")


def test_resolve_document_target_collection_defaults_to_personal_docs_collection() -> None:
    target = _resolve_document_target_collection(
        request=object(),  # type: ignore[arg-type]
        username="Neo User",
        selected_collection="",
        new_collection_name="",
        existing_collections=["aria_facts_neo_user"],
        sanitize_collection_name=_sanitize_collection_name,
        get_effective_memory_collection=lambda _request, _username: "aria_memory_neo_user",
    )

    assert target == "aria_docs_neo_user"


def test_build_document_entries_groups_chunks_by_document() -> None:
    rows = [
        {
            "type": "document",
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "timestamp": "2026-04-06T02:00:00+00:00",
            "text": "Erster Chunk mit etwas Text",
            "source": "rag_upload",
        },
        {
            "type": "document",
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "timestamp": "2026-04-06T02:01:00+00:00",
            "text": "Zweiter Chunk mit mehr Kontext",
            "source": "rag_upload",
        },
        {
            "type": "knowledge",
            "collection": "aria_context-mem_neo",
            "document_id": "",
            "document_name": "",
            "timestamp": "2026-04-06T02:02:00+00:00",
            "text": "Nicht als Dokument gruppieren",
            "source": "compression",
        },
    ]

    entries = _build_document_entries(rows)

    assert len(entries) == 1
    assert entries[0]["document_name"] == "Arlo.pdf"
    assert entries[0]["chunk_count"] == 2
    assert entries[0]["collection"] == "aria_docs_manuals"


def test_memories_page_is_view_only_memory_area() -> None:
    client = _build_memories_app()

    response = client.get("/memories")

    assert response.status_code == 200
    assert 'data-memory-browser' in response.text
    assert "Graphical browser" in response.text
    assert "Struktur" in response.text
    assert "Semantische Naehe" in response.text
    assert "data-memory-brain" in response.text
    assert "data-brain-payload" in response.text
    assert "aria:memory-brain-focus" in response.text
    assert "aria:memory-brain-back" in response.text
    assert "viewportCenterInSvg" in response.text
    assert "stableHash" in response.text
    assert "seededUnit" in response.text
    assert "2.399963229728653" in response.text
    assert "labelSide: x > centerX ? 'left' : 'right'" in response.text
    assert "const columns = collections.length" not in response.text
    assert "fitScaleForBounds" not in response.text
    assert "viewportSizeInSvg" not in response.text
    assert "viewport.scrollLeft || 0" in response.text
    assert "const visibleCenter = () =>" not in response.text
    assert "__ariaMemoryBrain" in response.text
    assert "canFocusCollection" in response.text
    assert "strict: true" in response.text
    assert "root.dataset.initialCollection || ''" in response.text
    assert "canShowSemantic" in response.text
    assert "semanticTargetHasPoint" in response.text
    assert "selectedPointContext" in response.text
    assert "documentChunks" in response.text
    assert "context.pointKind === 'chunk'" in response.text
    assert "context.pointKind === 'entry'" in response.text
    assert "selectedSemanticCollection" in response.text
    assert "allCollectionEntries(collection)[0]" in response.text
    assert "memoryBrowserSemanticDetail" in response.text
    assert "memory-brain-detail-home" in response.text
    assert "spreadCollectionLabels" not in response.text
    assert "overview-mode" not in response.text
    assert "fitStructureStage" in response.text
    assert "--memory-browser-stage-scale" in response.text
    assert 'data-memory-browser-zoom="in"' in response.text
    assert 'data-memory-browser-zoom="out"' in response.text
    assert "data-memory-browser-fit" in response.text
    assert "data-memory-browser-expand-all" in response.text
    assert "data-label-collapse" in response.text
    assert "Alles einklappen" in response.text
    assert "memory-drilldown-next-level" in response.text
    assert "memory-drilldown-next-list" in response.text
    assert "memory-drilldown-breadcrumb" in response.text
    assert "data-memory-browser-select-root" in response.text
    assert "data-memory-browser-select-type" in response.text
    assert "data-memory-browser-select-collection" in response.text
    assert "data-memory-browser-select-document" in response.text
    assert "data-memory-browser-select-entry" in response.text
    assert "memory-drilldown-chunk-list" in response.text
    assert "data-memory-browser-select-chunk" in response.text
    assert "const inspectorItem = item =>" in response.text
    assert "item = inspectorItem(item)" in response.text
    assert "level: 'document'" in response.text
    assert "level: 'chunk'" in response.text
    assert '"all_chunks"' in response.text
    assert "document.all_chunks || []" in response.text
    assert "Array.isArray(item.all_chunks) && item.all_chunks.length" in response.text
    assert "state.document = documentId" in response.text
    assert "state.collection = collectionId || state.collection" in response.text
    assert "state.entry = entryId" in response.text
    assert "const selectCollection = (collectionId, kind = '') =>" in response.text
    assert "const selectDocument = (documentId, collectionId = '') =>" in response.text
    assert "const collectionKindForSelection = (collectionId = '', documentId = '') =>" in response.text
    assert "state.type = kind || collectionKindForSelection(collectionId) || state.type" in response.text
    assert "state.type = collectionKindForSelection(collectionId || state.collection, documentId)" in response.text
    assert "state.type = collectionKindForSelection(collectionId || state.collection, documentId || state.document)" in response.text
    assert "state.type = collectionKindForSelection(collectionId || state.collection);" in response.text
    assert "parentCollection?.kind || item.kind || state.type || 'document'" in response.text
    assert "state.type = ''" in response.text
    assert "structurePanX += dx" in response.text
    assert "structurePanY += dy" in response.text
    assert 'data-memory-browser-pan-axis="x"' in response.text
    assert 'data-memory-browser-pan-axis="y"' in response.text
    assert "setStructurePanFromBar" in response.text
    assert "updateStructurePanBars" in response.text
    assert "data-memory-browser-delete-point" in response.text
    assert "data-memory-browser-delete-document" in response.text
    assert "['chunk', 'entry'].includes(item.level)" in response.text
    assert "state.collection = item.parentId || state.collection" in response.text
    assert "state.collection = parentDocument?.parentId || state.collection" in response.text
    assert "state.document = item.parentId || state.document" in response.text
    assert "const collectionInspectorItem = item => item ? ({" in response.text
    assert "level: item.level || 'collection'" in response.text
    assert "allCollectionItems().find(item => item.id === state.collection)" in response.text
    assert "const typeInspectorItem = item => item ? ({" in response.text
    assert "level: item.level || 'type'" in response.text
    assert "data-brain-delete-point" in response.text
    assert "/memories/browser/delete-point" in response.text
    assert "/memories/browser/delete-document" in response.text
    assert "const memoryBrowserFullscreenPath = \"/memories\";" in response.text
    assert "const memoryBrowserDeletePointPath = \"/memories/browser/delete-point\";" in response.text
    assert "const memoryBrowserDeleteDocumentPath = \"/memories/browser/delete-document\";" in response.text
    assert "const memoryGraphDeletePointPath = \"/memories/browser/delete-point\";" in response.text
    assert "postBrowserDelete('/memories/browser/delete-point'" not in response.text
    assert "postBrowserDelete('/memories/browser/delete-document'" not in response.text
    assert "fetch('/memories/browser/delete-point'" not in response.text
    assert "csrfToken" in response.text
    assert '"can_delete": true' in response.text
    assert "centerStructureView" in response.text
    assert "shiftStructureGraph" in response.text
    assert "visibleCenterX" in response.text
    assert "graphCenterX" in response.text
    assert "structurePanX" in response.text
    assert "--memory-browser-stage-pan-x" in response.text
    assert "focusStructureNode" in response.text
    assert "relaxStructureLayout" in response.text
    assert "edgeLengthFor" in response.text
    assert "seededUnit" in response.text
    assert "placeInCloud" in response.text
    assert "placeAroundParent" in response.text
    assert "clampNodePosition" not in response.text
    assert "structureEdges" in response.text
    assert "wheelStructureZoom" in response.text
    assert "zoomStructureAt" in response.text
    assert "gentleFocus" in response.text
    assert "preserveView" in response.text
    assert "keepScale: Boolean(options.gentleFocus)" in response.text
    assert "structureScale + (direction === 'in' ? 0.075 : -0.075)" in response.text
    assert "event.deltaY < 0 ? 1.04 : 0.96" in response.text
    assert 'min="55" max="190" value="112" data-memory-browser-force="spacing"' in response.text
    assert 'min="45" max="180" value="108" data-memory-browser-force="cluster"' in response.text
    assert 'min="35" max="170" value="92" data-memory-browser-force="attraction"' in response.text
    assert "aria.memoryBrowser.structureOptions.v1" in response.text
    assert "loadStructureOptions" in response.text
    assert "saveStructureOptions" in response.text
    assert "window.localStorage?.setItem" in response.text
    assert "startPinchZoom" in response.text
    assert "pinchLastCenter" in response.text
    assert "pointerDistance" in response.text
    assert "coarseStructurePointer" in response.text
    assert "event.pointerType === 'touch'" in response.text
    assert "pendingStructureFocusId" in response.text
    assert "activeStructureNodeId" in response.text
    assert "data-memory-drilldown-node-button" in response.text
    assert "memory-drilldown-hitbox" in response.text
    assert "data-edge-from" in response.text
    assert "updateStructureEdges" in response.text
    assert "draggedStructureNode" in response.text
    assert "manualStructureAnchors" in response.text
    assert "driftStructureDrag" in response.text
    assert "settleStructureDrag" in response.text
    assert "connectedStructureItems" in response.text
    assert "is-dragging" in response.text
    assert "pointerup" in response.text
    assert "startStagePan" in response.text
    assert "moveStagePan" in response.text
    assert "stage.addEventListener('wheel', wheelStructureZoom, { passive: false })" in response.text
    assert "event.target.closest?.('[data-memory-drilldown-node-button]')" in response.text
    assert "if (event.pointerType === 'touch' || coarseStructurePointer) return;" not in response.text
    assert "data-memory-browser-panel=\"semantic\"" not in response.text
    assert "memory-drilldown-node semantic-node" not in response.text
    assert "aria_learning_candidates_tester" in response.text
    assert "aria_docs_tester_manuals" in response.text
    assert "Setup Manual.pdf" in response.text
    assert "Setup manual first chunk" in response.text
    assert "Nächste Schritte" not in response.text
    assert "/memories#memories-actions" not in response.text
    assert 'href="/memories/import"' in response.text
    assert 'href="/memories/create"' in response.text
    assert 'href="/memories/auto-memory"' in response.text
    assert 'href="/memories/maintenance"' in response.text
    assert "Dokumente importieren" not in response.text
    assert 'name="source_view" value="import"' not in response.text
    assert 'id="memory-create"' not in response.text
    assert "/memories/config#qdrant-access" not in response.text


def test_memory_admin_pages_use_registry_template_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_template_name = memories_routes.module_template_name
    calls: list[tuple[str, str]] = []

    def _module_template_name(module_id: str, template_name: str) -> str | None:
        calls.append((module_id, template_name))
        return real_template_name(module_id, template_name)

    monkeypatch.setattr(memories_routes, "module_template_name", _module_template_name)
    client = _build_memories_app()

    pages = [
        "/memories",
        "/memories/import",
        "/memories/create",
        "/memories/maintenance",
        "/memories/config",
        "/memories/auto-memory",
    ]
    for page in pages:
        response = client.get(page)
        assert response.status_code == 200

    assert {
        ("memory_admin_ui", "memories_overview.html"),
        ("memory_admin_ui", "memories_import.html"),
        ("memory_admin_ui", "memories_create.html"),
        ("memory_admin_ui", "memories_maintenance.html"),
        ("memory_admin_ui", "config_memory.html"),
        ("memory_admin_ui", "memories_auto_memory.html"),
    }.issubset(set(calls))


def test_memory_admin_template_readpoint_fails_closed_for_unregistered_template(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    monkeypatch.setattr(memories_routes, "module_template_name", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="memory_admin_ui template is not registered: memories_overview.html"):
        memories_routes._memory_admin_template("memories_overview.html")


def test_memory_admin_route_readpoints_fail_closed_without_route_owner(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    monkeypatch.setattr(memories_routes, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories"):
        memories_routes._memory_admin_route("/memories")
    with pytest.raises(RuntimeError, match="notes route is not registered: /notes"):
        memories_routes._documents_route("/notes")
    with pytest.raises(RuntimeError, match="config_ui route is not registered: /config/routing"):
        memories_routes._config_ui_route("/config/routing")
    with pytest.raises(RuntimeError, match="recipes_ui route is not registered: /recipes/mine"):
        memories_routes._recipes_ui_route("/recipes/mine")


def test_memory_admin_visible_urls_use_registry_route_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)
    client = _build_memories_app()

    for page in (
        "/memories",
        "/memories/import",
        "/memories/create",
        "/memories/maintenance",
        "/memories/auto-memory",
        "/memories/config",
    ):
        response = client.get(page)
        assert response.status_code == 200

    assert {
        ("memory_admin_ui", "/memories"),
        ("memory_admin_ui", "/memories/import"),
        ("memory_admin_ui", "/memories/create"),
        ("memory_admin_ui", "/memories/upload"),
        ("memory_admin_ui", "/memories/maintenance"),
        ("memory_admin_ui", "/memories/config"),
        ("memory_admin_ui", "/memories/config/backend-save"),
        ("memory_admin_ui", "/memories/config/select"),
        ("memory_admin_ui", "/memories/config/create"),
        ("memory_admin_ui", "/memories/config/compression-save"),
        ("memory_admin_ui", "/memories/config/compress"),
        ("memory_admin_ui", "/memories/browser/delete-point"),
        ("memory_admin_ui", "/memories/browser/delete-document"),
        ("memory_admin_ui", "/memories/auto-memory/claim-action"),
        ("memory_admin_ui", "/memories/auto-memory/correct-claim"),
        ("memory_admin_ui", "/memories/auto-memory/delete-claim"),
        ("notes", "/notes"),
        ("recipes_ui", "/recipes/mine"),
        ("ops_config_backup", "/memories/reindex/run"),
        ("ops_config_backup", "/memories/reindex/save"),
        ("static_help_docs", "/help"),
            ("memory_admin_ui", "/memories"),
        ("config_ui", "/config/prompts"),
    }.issubset(set(calls))


def test_memories_nav_hides_admin_tools_when_admin_mode_is_off() -> None:
    client = _build_memories_app(advanced_mode=False)

    response = client.get("/memories")

    assert response.status_code == 200
    assert 'href="/memories"' in response.text
    assert 'href="/config/admin-mode"' in response.text
    assert 'href="/config/users?return_to=/config/access#admin-mode"' not in response.text
    assert 'href="/memories/import"' in response.text
    assert 'href="/memories/create"' in response.text
    assert 'href="/memories/auto-memory"' not in response.text
    assert 'href="/memories/maintenance"' not in response.text


def test_memories_fullscreen_semantic_request_without_point_stays_in_structure_browser() -> None:
    client = _build_memories_app()

    response = client.get("/memories?fullscreen=1&mode=semantic")

    assert response.status_code == 200
    assert 'data-memory-browser' in response.text
    assert "data-memory-brain" in response.text
    assert "memory-browser-fullscreen-page" in response.text
    assert 'data-memory-browser-inspector' in response.text
    assert "memory-drilldown-workbench" in response.text
    assert 'data-memory-browser-mode="structure" aria-pressed="true"' in response.text
    assert 'data-memory-browser-mode="semantic" aria-pressed="false" hidden disabled aria-disabled="true"' in response.text
    assert "data-memory-browser-semantic-panel hidden" in response.text
    assert "memory-browser-fullscreen-brand" in response.text
    assert "module_static_asset_url('navigation_shell', 'logo-aria-v01.png')" in Path(
        "aria/templates/_memory_drilldown_browser.html"
    ).read_text(encoding="utf-8")
    assert "module_route_path('chat_surface', '/')" in Path("aria/templates/_memory_drilldown_browser.html").read_text(
        encoding="utf-8"
    )
    assert 'class="memory-browser-fullscreen-brand brand brand-home" href="/"' in response.text
    assert 'src="/static/logo-aria-v01.png?v=' in response.text
    assert 'class="brand-logo">' in response.text
    assert 'class="brand-logo-rotate"' in response.text
    assert 'href="/memories?fullscreen=1"' not in response.text
    assert 'class="memory-subnav"' not in response.text


def test_memories_fullscreen_layout_keeps_header_compact_and_touch_ready() -> None:
    css = (Path(__file__).resolve().parents[1] / "aria" / "static" / "style.css").read_text()

    assert ".memory-browser-fullscreen-page .memory-drilldown-head" in css
    assert "grid-template-columns: minmax(12rem, 17rem) minmax(18rem, 1fr) auto;" in css
    assert "padding: 0.05rem 0.15rem 0.25rem;" in css
    assert ".memory-browser-fullscreen-brand.brand-home" in css
    assert "height: calc(100dvh - 5.05rem);" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "height: clamp(23rem, 56dvh, 34rem);" in css
    assert "-webkit-line-clamp: 2;" in css
    assert ".memory-brain-svg" in css
    assert "overflow: visible;" in css


def test_memories_fullscreen_collection_focus_does_not_enable_semantic_before_point() -> None:
    client = _build_memories_app()

    response = client.get("/memories?fullscreen=1&mode=semantic&collection=aria_docs_tester_manuals")

    assert response.status_code == 200
    assert '"initial_collection"' in response.text
    assert "collection-aria-docs-tester-manuals" in response.text
    assert 'data-memory-browser-mode="structure" aria-pressed="true"' in response.text
    assert 'data-memory-browser-mode="semantic" aria-pressed="false" hidden disabled aria-disabled="true"' in response.text
    assert "data-memory-browser-semantic-panel hidden" in response.text
    assert "aria:memory-brain-focus" in response.text
    assert "aria:memory-brain-focus-point" in response.text
    assert "__ariaMemoryBrain" in response.text
    assert "focusPoint" in response.text
    assert "selectedSemanticTarget" in response.text
    assert "selectedPointContext" in response.text
    assert "documentChunks" in response.text
    assert "renderActiveMode" in response.text
    assert "semanticTargetHasPoint" in response.text
    assert "spreadCollectionLabels" not in response.text
    assert "overview-mode" not in response.text
    assert "semanticPanel?.querySelector('[data-brain-center]')?.click()" not in response.text
    assert "renderStructure({ focusId: chunkId, gentleFocus: true, preserveView: true })" not in response.text
    assert 'data-initial-collection="aria_docs_tester_manuals"' in response.text
    assert "aria:memory-brain-back" in response.text
    assert "memoryBrowserSemanticDetail" in response.text
    assert "aria_docs_tester_manuals" in response.text
    assert "Setup manual graph chunk with import notes." in response.text
    assert "Setup manual graph chunk with troubleshooting notes." in response.text
    assert "data.initial_collection_name" in response.text


def test_memories_fullscreen_semantic_payload_keeps_document_chunk_details() -> None:
    client = _build_memories_app()

    response = client.get("/memories?fullscreen=1&mode=semantic&collection=aria_docs_tester_manuals")

    assert response.status_code == 200
    payload = _extract_brain_payload(response.text)
    nodes = [
        node
        for node in payload["nodes"]
        if node["collection"] == "aria_docs_tester_manuals"
    ]
    by_chunk = {int(node["chunk_index"]): node for node in nodes}
    assert set(by_chunk) == {1, 2}
    assert by_chunk[1]["label"] == "Chunk 1"
    assert by_chunk[1]["level"] == "chunk"
    assert by_chunk[1]["document_name"] == "Setup Manual.pdf"
    assert by_chunk[1]["chunk_total"] == 2
    assert "Setup manual graph chunk with import notes." in by_chunk[1]["preview"]
    assert "Chunk 1/2" in by_chunk[1]["meta"]
    assert by_chunk[2]["label"] == "Chunk 2"
    assert "Setup manual graph chunk with troubleshooting notes." in by_chunk[2]["preview"]
    assert "draggedPointerMoved" in response.text
    assert "activeDetailItem" in response.text
    assert "isChunk ? 'Chunk' : 'Payload Preview'" in response.text
    assert "data-detail-field=\"document\"" in response.text


def test_memories_fullscreen_semantic_starts_with_chunk_focus() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories?fullscreen=1&mode=semantic"
        "&collection=aria_docs_tester_manuals"
        "&document=doc-1"
        "&chunk=doc-1-chunk-1"
    )

    assert response.status_code == 200
    assert '"initial_document": "document:aria_docs_tester_manuals:doc-1"' in response.text
    assert '"initial_chunk": "doc-1-chunk-1"' in response.text
    assert 'mode: "semantic"' in response.text
    assert "aria:memory-brain-focus-point" in response.text
    assert "focusSemanticBrowser" in response.text


def test_memories_fullscreen_semantic_document_focus_promotes_first_chunk() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories?fullscreen=1&mode=semantic"
        "&collection=aria_docs_tester_manuals"
        "&document=document:aria_docs_tester_manuals:doc-1"
    )

    assert response.status_code == 200
    assert '"initial_document": "document:aria_docs_tester_manuals:doc-1"' in response.text
    assert '"initial_chunk": "doc-1-chunk-1"' in response.text
    assert 'mode: "semantic"' in response.text


def test_memories_detached_fullscreen_link_preserves_point_context() -> None:
    client = _build_memories_app()

    response = client.get("/memories")

    assert response.status_code == 200
    assert "const pointContext = semanticReady ? selectedPointContext() : null" in response.text
    assert "params.set('document', state.document || pointContext.document.id)" in response.text
    assert "params.set('chunk', state.chunk || pointContext.point.id)" in response.text
    assert "params.set('entry', state.entry || pointContext.point.id)" in response.text


def test_memories_browser_delete_point_uses_csrf_and_memory_skill() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/browser/delete-point",
        json={
            "collection": "aria_docs_tester_manuals",
            "point_id": "doc-1-chunk-1",
            "csrf_token": "test-csrf",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert client.app.state.memory_skill.deleted_points == [
        {
            "user_id": "tester",
            "collection": "aria_docs_tester_manuals",
            "point_id": "doc-1-chunk-1",
        }
    ]


def test_memories_browser_delete_document_uses_csrf_and_memory_skill() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/browser/delete-document",
        headers={"x-csrf-token": "test-csrf"},
        json={
            "collection": "aria_docs_tester_manuals",
            "document_id": "doc-1",
            "document_name": "Setup Manual.pdf",
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["removed"] == 2
    assert client.app.state.memory_skill.deleted_documents == [
        {
            "user_id": "tester",
            "collection": "aria_docs_tester_manuals",
            "document_id": "doc-1",
            "document_name": "Setup Manual.pdf",
        }
    ]


def test_memories_browser_delete_point_rejects_missing_csrf() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/browser/delete-point",
        json={"collection": "aria_docs_tester_manuals", "point_id": "doc-1-chunk-1"},
    )

    assert response.status_code == 403
    assert client.app.state.memory_skill.deleted_points == []


def test_memories_fullscreen_semantic_supports_notes_collection_focus() -> None:
    client = _build_memories_app()

    response = client.get("/memories?fullscreen=1&mode=semantic&collection=aria_notes_tester")

    assert response.status_code == 200
    assert 'data-memory-browser-mode="structure" aria-pressed="true"' in response.text
    assert 'data-memory-browser-mode="semantic" aria-pressed="false" hidden disabled aria-disabled="true"' in response.text
    assert "data-memory-browser-semantic-panel hidden" in response.text
    assert "aria_notes_tester" in response.text
    assert "Area41 note graph chunk with travel context." in response.text
    assert "Area41 note graph chunk with conference context." in response.text


def test_memories_import_page_contains_only_intake_actions() -> None:
    client = _build_memories_app()

    response = client.get("/memories/import")

    assert response.status_code == 200
    assert "Dokumente importieren" in response.text
    assert 'href="/memories/create"' in response.text
    assert 'id="memory-create"' not in response.text
    assert 'name="source_view" value="import"' in response.text
    assert 'data-busy-immediate="true"' in response.text
    assert "Memory-Graph" not in response.text
    assert "Memory Reindex" not in response.text


def test_memories_create_page_contains_manual_memory_form() -> None:
    client = _build_memories_app()

    response = client.get("/memories/create")

    assert response.status_code == 200
    assert "Eigene Memory erfassen" in response.text or "Create memory" in response.text
    assert 'href="/memories/create"' in response.text
    assert 'id="memory-create"' in response.text
    assert 'name="source_view" value="create"' in response.text
    assert 'action="/memories/create"' in response.text
    assert 'name="kind"' in response.text
    assert 'name="subject"' in response.text
    assert 'name="predicate"' in response.text
    assert 'name="value"' in response.text
    assert 'value="ich"' in response.text
    assert 'maxlength="700"' in response.text
    assert 'value="knowledge"' not in response.text
    assert 'name="memory_type"' not in response.text
    assert 'name="text"' not in response.text
    assert "Dokumente importieren" not in response.text


def test_memories_create_stores_and_lists_structured_preference_claim() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/create",
        data={
            "source_view": "create",
            "kind": "preference",
            "subject": "ich",
            "predicate": "bevorzugt",
            "value": "grünen Tee",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/memories/create?info=")
    stored = client.app.state.memory_skill.stored_personal_claims
    assert len(stored) == 1
    assert stored[0]["collection"] == "aria_preferences_tester"
    assert stored[0]["claim_kind"] == "preference"
    assert stored[0]["claim_subject"] == "ich"
    assert stored[0]["claim_predicate"] == "bevorzugt"
    assert stored[0]["claim_value"] == "grünen Tee"
    assert stored[0]["claim_authority"] == "explicit_user"
    assert stored[0]["claim_status"] == "active"
    assert stored[0]["claim_id"]
    assert stored[0]["claim_key"]
    assert client.app.state.memory_skill.execute_calls[-1]["params"]["source"] == "personal_claim"
    personal_model = client.get("/memories/auto-memory")
    assert personal_model.status_code == 200
    assert "grünen Tee" in personal_model.text


@pytest.mark.parametrize(
    ("field", "value"),
    (("subject", ""), ("predicate", ""), ("value", "")),
)
def test_memories_create_rejects_empty_structured_claim_field(field: str, value: str) -> None:
    client = _build_memories_app()
    payload = {
        "source_view": "create",
        "kind": "fact",
        "subject": "ich",
        "predicate": "nutzt",
        "value": "Linux",
    }
    payload[field] = value

    response = client.post("/memories/create", data=payload, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/memories/create?error=")
    assert client.app.state.memory_skill.execute_calls == []


def test_memories_create_rejects_legacy_knowledge_kind() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/create",
        data={
            "source_view": "create",
            "kind": "knowledge",
            "subject": "ich",
            "predicate": "kennt",
            "value": "Legacy-Wissen",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/memories/create?error=")
    assert client.app.state.memory_skill.execute_calls == []


def test_memories_create_surfaces_bounded_personal_claim_store_error(monkeypatch) -> None:
    async def failed_store(**_kwargs: object) -> dict[str, object]:
        return {
            "stored": False,
            "reason": "claim_store_failed",
            "store_error": "embedding_error: boom",
        }

    monkeypatch.setattr(memories_routes, "store_personal_claim", failed_store)
    client = _build_memories_app()

    response = client.post(
        "/memories/create",
        data={
            "source_view": "create",
            "kind": "fact",
            "subject": "ich",
            "predicate": "spielt",
            "value": "No Man's Sky",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = unquote_plus(response.headers["location"])
    assert location.startswith("/memories/create?error=")
    assert "claim_store_failed" in location
    assert "embedding_error: boom" in location


def test_memories_maintenance_page_groups_admin_tools() -> None:
    client = _build_memories_app()

    response = client.get("/memories/maintenance")

    assert response.status_code == 200
    assert "Wartung" in response.text
    assert "Kontext-Rollup" in response.text
    assert "Memory Reindex" in response.text
    assert 'id="maint-reindex"' in response.text
    assert 'action="/memories/reindex/run"' in response.text
    assert "Inventory index ready: 2/2 items indexed." in response.text
    assert "aria_inventory_test" in response.text
    assert 'href="/memories/reindex"' not in response.text
    assert "Memory-Setup" in response.text
    assert 'config-admin-return-link" href="/config/admin"' not in response.text
    assert 'href="/memories/maintenance"' in response.text
    assert "Learning Worker" not in response.text
    assert "Self-Learning" not in response.text
    assert "aria_learning_candidates_tester" not in response.text
    assert "Learning Candidate: Official page excerpts first" not in response.text
    assert 'action="/memories/maintenance/reset-learning-suggestions"' in response.text
    assert 'name="source_view" value="maintenance"' in response.text
    assert "Dokumente importieren" not in response.text


def test_memory_config_page_contains_reindex_scheduler() -> None:
    client = _build_memories_app()

    response = client.get("/memories/config")

    assert response.status_code == 200
    assert "Reindex-Scheduler" in response.text
    assert 'id="reindex-scheduler"' in response.text
    assert 'action="/memories/reindex/save"' in response.text
    for field_name in (
        "enabled",
        "run_on_startup",
        "keep_backup",
        "cron",
        "timezone",
        "score_threshold",
        "candidate_limit",
    ):
        assert f'name="{field_name}"' in response.text


def test_memories_page_shows_notes_and_routing_collections() -> None:
    client = _build_memories_app()

    response = client.get("/memories")

    assert response.status_code == 200
    assert "aria_notes_tester" in response.text
    assert "aria_learning_tester" in response.text
    assert "aria_learning_events_tester" in response.text
    assert "aria_learning_candidates_tester" in response.text
    assert "aria_learning_evals_tester" in response.text
    assert "aria_recipe_experience_tester" in response.text
    assert 'href="/memories"' in response.text
    assert "Qdrant Brain" in response.text
    assert "data-memory-brain" in response.text
    assert "data-brain-touch-toggle" in response.text
    assert "memory-map-frame-wrap memory-graph-wrap" not in response.text
    assert "data-memory-browser" in response.text
    assert "data-memory-browser-payload" in response.text
    assert 'href="/notes"' in response.text
    assert "SSH server context" in response.text
    assert "[1.0, 0.0, 0.0]" not in response.text
    payload = _extract_memory_browser_payload(response.text)
    collections = [
        collection for collection in payload.get("collections", []) if isinstance(collection, dict)
    ]
    collection_names = {
        str(collection.get("name") or collection.get("id") or "")
        for collection in collections
    }
    assert "aria_notes_tester" in collection_names
    assert "aria_learning_tester" in collection_names
    assert "aria_recipe_experience_tester" in collection_names
    browser_hrefs = {
        str(collection.get("name") or collection.get("id") or ""): collection.get("href")
        for collection in collections
    }
    assert browser_hrefs["aria_notes_tester"] == "/notes"
    assert browser_hrefs["aria_routing_connections_aria_8800"] == "/memories"


def test_memories_page_shows_brain_empty_state_when_no_vectors() -> None:
    client = _build_memories_app(memory_graph_points=[])

    response = client.get("/memories")

    assert response.status_code == 200
    assert "Qdrant Brain" in response.text
    assert "data-memory-brain" in response.text
    assert "No visualizable Qdrant points found yet" in response.text
    assert "data-memory-browser" in response.text


def test_memories_explorer_stays_focused_on_browsing_not_creation() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories"


def test_memories_explorer_does_not_duplicate_memory_browser_or_maintenance() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer")

    assert response.status_code == 200
    assert 'data-memory-browser' in response.text
    assert "Memory Browser" not in response.text
    assert "Semantische Map" not in response.text
    assert "Learning Worker" not in response.text
    assert "/memories/learning-worker/flush" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "data"),
    [
        ("get", "/memories/learning-worker/job/dead-job", None),
        ("post", "/memories/learning-worker/retry", {"job_id": "dead-job", "force": "1"}),
        ("post", "/memories/learning-worker/flush", {"scope": "finished"}),
    ],
)
def test_memories_learning_worker_admin_routes_are_removed(
    method: str,
    path: str,
    data: dict[str, str] | None,
) -> None:
    client = _build_memories_app()

    response = client.request(method, path, data=data, follow_redirects=False)

    assert response.status_code == 404


def test_memories_explorer_learning_candidate_filter_redirects_to_memory_browser() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_candidate", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories"


def test_memories_maintenance_omits_legacy_worker_and_keeps_native_reset() -> None:
    client = _build_memories_app()

    response = client.get("/memories/maintenance")

    assert response.status_code == 200
    assert "Learning Worker" not in response.text
    assert "Self-Learning" not in response.text
    assert "/memories/learning-worker/flush" not in response.text
    assert 'action="/memories/maintenance/reset-learning-suggestions"' in response.text


def test_memories_explorer_app_learning_filter_redirects_to_memory_browser() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_candidate", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories"


def test_memories_explorer_learning_eval_filter_redirects_to_memory_browser() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_eval", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories"


def test_learning_candidate_admin_routes_are_not_registered() -> None:
    client = _build_memories_app()
    retired = (
        ("post", "/memories/learning-candidate/status"),
        ("post", "/memories/learning-candidate/apply"),
        ("get", "/memories/learning-candidate/apply-preview"),
        ("post", "/memories/learning-candidate/regression"),
        ("post", "/memories/learning-candidate/pytest/prepare-write"),
        ("post", "/memories/learning-candidate/artifact/review"),
        ("post", "/memories/learning-candidate/regression/verify"),
        ("post", "/memories/learning-candidate/regression/run"),
        ("post", "/memories/learning-candidate/activation-preflight"),
        ("post", "/memories/learning-candidate/activate"),
    )

    for method, path in retired:
        response = client.request(method, path, follow_redirects=False)
        assert response.status_code == 404

def test_memories_root_ignores_legacy_explorer_query_and_renders_browser() -> None:
    client = _build_memories_app()

    response = client.get("/memories?type=document&sort=collection", follow_redirects=False)

    assert response.status_code == 200
    assert 'data-memory-browser' in response.text


def test_memory_drilldown_browser_counts_only_real_document_collections() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_docs_whity_medikamente", "kind": "document", "points": 338},
            {"name": "aria_docs_fischerman", "kind": "document", "points": 207},
            {"name": "aria_recipe_experience_fischerman", "kind": "recipe_experience", "points": 94},
            {"name": "aria_facts_fischerman", "kind": "fact", "points": 19},
        ],
        document_rows=[
            {
                "id": "d1-c1",
                "type": "document",
                "collection": "aria_docs_whity_medikamente",
                "document_id": "doc-1",
                "document_name": "Olumiant.pdf",
                "text": "Olumiant chunk",
            },
            {
                "id": "d2-c1",
                "type": "document",
                "collection": "aria_docs_fischerman",
                "document_id": "doc-2",
                "document_name": "Arlo.pdf",
                "text": "Arlo chunk",
            },
            {
                "id": "r1",
                "type": "document",
                "collection": "aria_recipe_experience_fischerman",
                "document_id": "recipe-1",
                "document_name": "Recipe Experience",
                "text": "Recipe experience must not count as a document store",
            },
        ],
        brain={},
    )

    document_type = next(item for item in snapshot["types"] if item["kind"] == "document")
    collections = {item["name"]: item for item in snapshot["collections"]}

    assert document_type["points"] == 545
    assert document_type["collection_count"] == 2
    assert "aria_docs_whity_medikamente" in collections
    assert "aria_docs_fischerman" in collections
    assert collections["aria_recipe_experience_fischerman"]["kind"] == "recipe_experience"
    whity_doc = collections["aria_docs_whity_medikamente"]["documents"][0]
    assert len(whity_doc["all_chunks"]) == 1
    assert whity_doc["all_chunks"][0]["label"] == "Chunk 1"


def test_memory_drilldown_browser_keeps_all_document_chunks_for_inspector() -> None:
    document_rows = [
        {
            "id": f"doc-1-chunk-{index}",
            "type": "document",
            "collection": "aria_docs_tester_manuals",
            "document_id": "doc-1",
            "document_name": "Setup Manual.pdf",
            "timestamp": f"2026-04-06T02:{index:02d}:00+00:00",
            "text": f"Setup manual chunk {index}",
        }
        for index in range(1, 15)
    ]
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[{"name": "aria_docs_tester_manuals", "kind": "document", "points": 14}],
        document_rows=document_rows,
        brain={},
    )

    collection = next(item for item in snapshot["collections"] if item["name"] == "aria_docs_tester_manuals")
    document = collection["documents"][0]

    assert document["chunk_count"] == 14
    assert len(document["chunks"]) == 12
    assert len(document["all_chunks"]) == 14
    assert document["all_chunks"][-1]["label"] == "Chunk 14"


def test_memory_drilldown_browser_shows_self_learning_collections_read_only() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_learning_tester", "kind": "reflection", "points": 4},
            {"name": "aria_learning_events_tester", "kind": "learning_event", "points": 37},
            {"name": "aria_learning_candidates_tester", "kind": "learning_candidate", "points": 65},
            {"name": "aria_learning_evals_tester", "kind": "learning_eval", "points": 1},
        ],
        document_rows=[],
        brain={},
    )

    collections = {item["name"]: item for item in snapshot["collections"]}

    assert any(item["kind"] == "reflection" for item in snapshot["types"])
    assert collections["aria_learning_tester"]["kind"] == "reflection"
    assert collections["aria_learning_candidates_tester"]["kind"] == "learning_candidate"


def test_memory_drilldown_browser_attaches_non_document_collection_entries() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_learning_tester", "kind": "reflection", "points": 2},
        ],
        document_rows=[],
        brain={
            "nodes": [
                {
                    "id": "learning-1",
                    "collection": "aria_learning_tester",
                    "kind": "reflection",
                    "label": "Learning",
                    "preview": "User prefers direct inspector drilldown.",
                    "source": "memory",
                    "timestamp": "2026-07-05T10:00:00+00:00",
                }
            ]
        },
    )

    collection = next(item for item in snapshot["collections"] if item["name"] == "aria_learning_tester")

    assert collection["entries"][0]["id"] == "learning-1"
    assert collection["entries"][0]["label"] == "Learning"
    assert "inspector drilldown" in collection["entries"][0]["preview"]


def test_memory_drilldown_browser_uses_full_rows_for_notes_not_graph_sample() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_notes_tester", "kind": "notes", "points": 54},
        ],
        document_rows=[],
        collection_rows=[
            {
                "id": "death-note-chunk-1",
                "collection": "aria_notes_tester",
                "type": "notes",
                "label": "NOTIZEN",
                "text": "# Sample Project Note\n\n# Tweaks\n## Alpha Level",
                "source": "notes",
                "timestamp": "2026-07-20T10:44:00+00:00",
                "note_id": "death-pays-overtime",
                "note_title": "Sample Project Note",
                "note_folder": "Games",
                "note_path": "Games/death-pays-overtime.md",
                "chunk_index": 1,
                "chunk_total": 2,
            },
            {
                "id": "death-note-chunk-2",
                "collection": "aria_notes_tester",
                "type": "notes",
                "label": "NOTIZEN",
                "text": "# Bugs\n\nOverlays stoeren das Game.",
                "source": "notes",
                "timestamp": "2026-07-20T10:44:01+00:00",
                "note_id": "death-pays-overtime",
                "note_title": "Sample Project Note",
                "note_folder": "Games",
                "note_path": "Games/death-pays-overtime.md",
                "chunk_index": 2,
                "chunk_total": 2,
            },
        ],
        brain={
            "nodes": [
                {
                    "id": "old-note",
                    "collection": "aria_notes_tester",
                    "kind": "notes",
                    "label": "Area41",
                    "preview": "Older sampled note",
                    "source": "notes",
                }
            ]
        },
    )

    collection = next(item for item in snapshot["collections"] if item["name"] == "aria_notes_tester")
    note = collection["documents"][0]

    assert collection["kind"] == "notes"
    assert collection["document_count"] == 1
    assert collection["chunk_count"] == 2
    assert collection["entries"] == []
    assert note["label"] == "Sample Project Note"
    assert note["kind"] == "notes"
    assert [chunk["id"] for chunk in note["all_chunks"]] == ["death-note-chunk-1", "death-note-chunk-2"]
    assert "Alpha Level" in note["preview"]


def test_memories_page_browser_payload_contains_fresh_notes_from_full_rows() -> None:
    client = _build_memories_app()

    response = client.get("/memories?collection=aria_notes_tester")

    assert response.status_code == 200
    payload = _extract_memory_browser_payload(response.text)
    collection = next(item for item in payload["collections"] if item["name"] == "aria_notes_tester")
    note = collection["documents"][0]

    assert payload["initial_collection"] == collection["id"]
    assert collection["kind"] == "notes"
    assert note["label"] == "Sample Project Note"
    assert note["chunk_count"] == 2
    assert [chunk["id"] for chunk in note["all_chunks"]] == ["death-note-chunk-1", "death-note-chunk-2"]


def test_memory_drilldown_browser_does_not_use_graph_sample_as_notes_truth() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_notes_tester", "kind": "notes", "points": 54},
        ],
        document_rows=[],
        collection_rows=[],
        brain={
            "nodes": [
                {
                    "id": "old-note",
                    "collection": "aria_notes_tester",
                    "kind": "notes",
                    "label": "Area41",
                    "preview": "Older sampled note",
                    "source": "notes",
                }
            ]
        },
    )

    collection = next(item for item in snapshot["collections"] if item["name"] == "aria_notes_tester")

    assert collection["kind"] == "notes"
    assert collection["documents"] == []
    assert collection["entries"] == []


def test_memory_drilldown_browser_uses_qdrant_overview_as_collection_source() -> None:
    snapshot = _build_memory_drilldown_browser_snapshot(
        username="tester",
        lang="de",
        collection_stats=[
            {"name": "aria_facts_tester", "kind": "fact", "points": 12},
        ],
        all_collections=[
            {"name": "aria_facts_tester", "points": 12, "status": "green", "vectors": 12},
            {"name": "aria_inventory_aria_8800", "points": 133, "status": "green", "vectors": 133},
            {"name": "external_manual_index", "points": 7, "status": "green", "vectors": 7},
        ],
        document_rows=[],
        brain={},
    )

    collections = {item["name"]: item for item in snapshot["collections"]}
    kinds = {item["kind"] for item in snapshot["types"]}

    assert "aria_facts_tester" in collections
    assert "aria_inventory_aria_8800" in collections
    assert collections["aria_inventory_aria_8800"]["kind"] == "system"
    assert "external_manual_index" in collections
    assert collections["external_manual_index"]["kind"] == "external"
    assert "system" in kinds
    assert "external" in kinds


def test_memory_setup_page_keeps_qdrant_access_in_one_place() -> None:
    client = _build_memories_app()

    response = client.get("/memories/config")

    assert response.status_code == 200
    assert response.text.count("Qdrant Dashboard + API-Key kopieren") == 1
    assert 'class="ui-action-link config-admin-return-link"' not in response.text
    assert "Admin-Übersicht" not in response.text
    assert "Admin overview" not in response.text
    assert 'id="qdrant-access"' in response.text
    assert 'data-copy-source="qdrant-url"' in response.text
    assert 'data-copy-source="qdrant-key"' in response.text
    assert 'type="password"' in response.text
    assert 'data-copy-value="secret-key"' in response.text
    assert 'data-dashboard-url="http://qdrant.local:6333/dashboard"' in response.text
    assert "Memory backend enabled" not in response.text


def test_auto_memory_page_renders_only_the_personal_model() -> None:
    client = _build_memories_app()

    setup_response = client.get("/memories/config")
    response = client.get("/memories/auto-memory")

    assert setup_response.status_code == 200
    assert 'id="auto-memory"' not in setup_response.text
    assert response.status_code == 200
    nav = _first_memory_subnav(response.text)
    assert 'href="/config/admin/memory"' not in nav
    assert 'class="memory-subnav-item active" href="/memories/auto-memory"' in nav
    assert 'id="auto-memory"' not in response.text
    assert 'id="auto_memory_enabled"' not in response.text
    assert "Auto-memory &amp; learning" not in response.text
    assert "Personal model" in response.text
    assert "/help?doc=memory" in response.text
    assert "short answers" in response.text
    assert "Presented / used" in response.text
    assert "4 / 3" in response.text
    assert "Feedback +1/-0" in response.text
    assert 'action="/memories/auto-memory/claim-action"' in response.text
    assert 'action="/memories/auto-memory/delete-claim"' in response.text
    assert "Learning inventory" not in response.text
    assert "Synthesize now" not in response.text
    assert "To review" not in response.text
    assert "Durable test procedure" not in response.text
    assert "Raw learning evidence" not in response.text
    assert 'action="/memories/auto-memory/delete-point"' not in response.text
    assert 'action="/memories/auto-memory/candidate-action"' not in response.text
    assert 'action="/memories/auto-memory/hint-action"' not in response.text


def test_memories_auto_memory_page_uses_registry_action_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)
    client = _build_memories_app()

    response = client.get("/memories/auto-memory")

    assert response.status_code == 200
    assert 'action="/memories/auto-memory/claim-action"' in response.text
    assert 'action="/memories/auto-memory/correct-claim"' in response.text
    assert 'action="/memories/auto-memory/delete-claim"' in response.text
    assert {
        ("memory_admin_ui", "/memories/auto-memory/claim-action"),
        ("memory_admin_ui", "/memories/auto-memory/correct-claim"),
        ("memory_admin_ui", "/memories/auto-memory/delete-claim"),
    }.issubset(set(calls))


def test_personal_model_page_does_not_collect_legacy_learning_data() -> None:
    client = _build_memories_app()

    async def _unexpected_learning_read(_username: str) -> list[dict[str, object]]:
        raise AssertionError("Legacy Learning inventory must not be read")

    client.app.state.memory_skill.list_learning_points_global = _unexpected_learning_read

    response = client.get("/memories/auto-memory")

    assert response.status_code == 200
    assert "Personal model" in response.text
    assert "short answers" in response.text


@pytest.mark.parametrize(
    "path",
    (
        "/memories/auto-memory/synthesize",
        "/memories/config/auto-save",
        "/config/memory/auto-save",
        "/memories/auto-memory/hint-action",
        "/memories/auto-memory/candidate-action",
    ),
)
def test_retired_auto_memory_post_routes_are_absent(path: str) -> None:
    client = _build_memories_app()

    response = client.post(path, follow_redirects=False)

    assert response.status_code == 404


def test_auto_memory_personal_claim_can_be_suspended_reactivated_and_deleted() -> None:
    client = _build_memories_app()
    data = {
        "csrf_token": "test-csrf",
        "collection": "aria_preferences_tester",
        "point_id": "personal-claim-point-1",
        "decision": "suspend",
    }

    suspended = client.post("/memories/auto-memory/claim-action", data=data, follow_redirects=False)

    assert suspended.headers["location"] == "/memories/auto-memory?saved=1"
    assert client.app.state.memory_skill.personal_claim_point["claim_status"] == "suspended"

    data["decision"] = "reactivate"
    reactivated = client.post("/memories/auto-memory/claim-action", data=data, follow_redirects=False)

    assert reactivated.headers["location"] == "/memories/auto-memory?saved=1"
    assert client.app.state.memory_skill.personal_claim_point["claim_status"] == "active"

    deleted = client.post(
        "/memories/auto-memory/delete-claim",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_preferences_tester",
            "point_id": "personal-claim-point-1",
        },
        follow_redirects=False,
    )

    assert deleted.headers["location"] == "/memories/auto-memory?saved=1"
    assert client.app.state.memory_skill.deleted_points[-1]["point_id"] == "personal-claim-point-1"


def test_auto_memory_feedback_redirects_use_registry_route_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)
    client = _build_memories_app()

    csrf_error = client.post(
        "/memories/auto-memory/claim-action",
        data={
            "csrf_token": "wrong",
            "collection": "aria_preferences_tester",
            "point_id": "personal-claim-point-1",
            "decision": "suspend",
        },
        follow_redirects=False,
    )
    saved = client.post(
        "/memories/auto-memory/claim-action",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_preferences_tester",
            "point_id": "personal-claim-point-1",
            "decision": "suspend",
        },
        follow_redirects=False,
    )

    assert csrf_error.status_code == 303
    assert csrf_error.headers["location"] == "/memories/auto-memory?error=csrf_failed"
    assert saved.status_code == 303
    assert saved.headers["location"] == "/memories/auto-memory?saved=1"
    assert ("memory_admin_ui", "/memories/auto-memory") in calls


def test_auto_memory_feedback_redirects_fail_closed_without_route_owner(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    monkeypatch.setattr(
        memories_routes,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "memory_admin_ui" and route_path == "/memories/auto-memory"
        else real_route_path(module_id, route_path),
    )
    client = _build_memories_app()

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/auto-memory"):
        client.post(
            "/memories/auto-memory/claim-action",
            data={
                "csrf_token": "wrong",
                "collection": "aria_preferences_tester",
                "point_id": "personal-claim-point-1",
                "decision": "suspend",
            },
            follow_redirects=False,
        )


def test_auto_memory_expired_personal_claim_cannot_be_reactivated() -> None:
    client = _build_memories_app()
    point = client.app.state.memory_skill.personal_claim_point
    point["claim_status"] = "suspended"
    point["claim_valid_until"] = "2020-01-01T00:00:00+00:00"

    response = client.post(
        "/memories/auto-memory/claim-action",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_preferences_tester",
            "point_id": "personal-claim-point-1",
            "decision": "reactivate",
        },
        follow_redirects=False,
    )

    assert response.headers["location"] == "/memories/auto-memory?error=personal_claim_expired"
    assert point["claim_status"] == "suspended"


def test_auto_memory_goal_claim_supports_pause_resume_and_complete() -> None:
    client = _build_memories_app()
    point = client.app.state.memory_skill.personal_claim_point
    point["claim_kind"] = "goal"
    data = {
        "csrf_token": "test-csrf",
        "collection": "aria_preferences_tester",
        "point_id": "personal-claim-point-1",
    }

    paused = client.post(
        "/memories/auto-memory/claim-action",
        data={**data, "decision": "pause"},
        follow_redirects=False,
    )
    assert paused.headers["location"] == "/memories/auto-memory?saved=1"
    assert point["claim_status"] == "paused"

    resumed = client.post(
        "/memories/auto-memory/claim-action",
        data={**data, "decision": "resume"},
        follow_redirects=False,
    )
    assert resumed.headers["location"] == "/memories/auto-memory?saved=1"
    assert point["claim_status"] == "active"

    completed = client.post(
        "/memories/auto-memory/claim-action",
        data={**data, "decision": "complete"},
        follow_redirects=False,
    )
    assert completed.headers["location"] == "/memories/auto-memory?saved=1"
    assert point["claim_status"] == "completed"


def test_auto_memory_personal_claim_correction_uses_explicit_supersession(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    captured: dict[str, object] = {}

    async def fake_store_personal_claim(**kwargs):
        captured.update(kwargs)
        return {"stored": True, "reason": "claim_superseded"}

    monkeypatch.setattr(memories_routes, "store_personal_claim", fake_store_personal_claim)
    client = _build_memories_app()

    response = client.post(
        "/memories/auto-memory/correct-claim",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_preferences_tester",
            "point_id": "personal-claim-point-1",
            "corrected_value": "detailed answers",
        },
        follow_redirects=False,
    )

    assert response.headers["location"] == "/memories/auto-memory?saved=1"
    assert captured["explicit_supersedes_claim_id"] == "personal-claim-1"
    assert captured["claim"]["value"] == "detailed answers"
    assert captured["claim"]["authority"] == "user_correction"


def test_auto_memory_learning_point_delete_is_scoped_to_learning_collections() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/auto-memory/delete-point",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-point-1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/memories/auto-memory?saved=1"

    rejected = client.post(
        "/memories/auto-memory/delete-point",
        data={
            "csrf_token": "test-csrf",
            "collection": "aria_notes_tester",
            "point_id": "note-point-1",
        },
        follow_redirects=False,
    )

    assert rejected.status_code == 303
    assert rejected.headers["location"] == "/memories/auto-memory?error=invalid_learning_point"
    assert client.app.state.memory_skill.deleted_points == [
        {
            "user_id": "tester",
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-point-1",
        }
    ]


def test_memory_backend_save_always_keeps_backend_enabled(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)
    templates.env.globals.setdefault("nav_section_items", nav_section_items)
    templates.env.globals.setdefault("context_nav_items", context_nav_items)
    templates.env.globals.setdefault("context_nav_context", context_nav_context)
    templates.env.globals.setdefault("admin_nav_groups", admin_nav_groups)
    templates.env.globals.setdefault("settings_nav_groups", settings_nav_groups)

    writes: list[dict[str, object]] = []
    runtime_reloaded = {"called": False}

    settings = SimpleNamespace(
        ui=SimpleNamespace(title="Memories Test"),
        memory=SimpleNamespace(
            backend="qdrant",
            enabled=True,
            qdrant_url="http://qdrant.local:6333",
            qdrant_api_key="secret-key",
            compression_summary_prompt="prompts/memory_summary.md",
            collections=SimpleNamespace(
                sessions=SimpleNamespace(
                    compress_after_days=7,
                    monthly_after_days=30,
                )
            ),
        ),
        auto_memory=SimpleNamespace(
            enabled=True,
            session_recall_top_k=4,
            user_recall_top_k=4,
            max_facts_per_message=3,
        ),
    )

    @app.middleware("http")
    async def _inject_state(request: Request, call_next):
        request.state.authenticated = True
        request.state.auth_user = "tester"
        request.state.auth_role = "admin"
        request.state.can_access_users = False
        request.state.can_access_advanced_config = True
        request.state.debug_mode = True
        request.state.lang = "en"
        request.state.cookie_names = {}
        request.state.csrf_token = "test-csrf"
        request.state.release_meta = {"label": "test"}
        request.state.update_status = SimpleNamespace(update_available=False)
        request.state.ui_theme = "matrix"
        request.state.ui_background = "grid"
        request.state.logical_back_url = ""
        return await call_next(request)

    from aria.modules.memory_admin_ui.routes import register_memories_routes

    async def _qdrant_overview(_request: Request) -> dict[str, object]:
        return {"reachable": True, "collections": [], "collection_count": 0}

    def _read_raw_config() -> dict[str, object]:
        return {"memory": {"enabled": False, "backend": "qdrant", "qdrant_url": "http://old:6333"}}

    def _write_raw_config(raw: dict[str, object]) -> None:
        writes.append(raw)

    def _reload_runtime() -> None:
        runtime_reloaded["called"] = True

    register_memories_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_pipeline=lambda: SimpleNamespace(memory_skill=None),
        get_username_from_request=lambda _request: "tester",
        get_auth_session_from_request=lambda _request: {"role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        qdrant_overview=_qdrant_overview,
        qdrant_dashboard_url=lambda _request: "http://qdrant.local:6333/dashboard",
        parse_collection_day_suffix=lambda _value: None,
        sanitize_collection_name=_sanitize_collection_name,
        default_memory_collection_for_user=lambda username: f"aria_facts_{username.lower()}",
        get_effective_memory_collection=lambda _request, username: f"aria_facts_{username.lower()}",
        read_raw_config=_read_raw_config,
        write_raw_config=_write_raw_config,
        reload_runtime=_reload_runtime,
        resolve_prompt_file=lambda value: Path("/tmp") / value,
        get_secure_store=lambda _raw=None: None,
        memory_collection_cookie="aria_memory_collection",
    )

    client = TestClient(app)
    response = client.post(
        "/memories/config/backend-save",
        data={"backend": "qdrant", "qdrant_url": "http://qdrant:6333", "qdrant_api_key": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/memories/config?saved=1"
    assert ("memory_admin_ui", "/memories/config") in calls
    assert runtime_reloaded["called"] is True
    assert writes
    assert writes[0]["memory"]["enabled"] is True


def test_memory_config_feedback_redirects_fail_closed_without_route_owner(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    monkeypatch.setattr(
        memories_routes,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "memory_admin_ui" and route_path == "/memories/config"
        else real_route_path(module_id, route_path),
    )

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/config"):
        memories_routes._memories_config_redirect(saved=True)


def test_build_document_collection_groups_summarizes_per_collection() -> None:
    entries = [
        {
            "collection": "aria_docs_manuals",
            "document_id": "doc-1",
            "document_name": "Arlo.pdf",
            "chunk_count": 12,
            "latest_timestamp": "2026-04-06T02:01:00+00:00",
            "preview": "Arlo preview",
        },
        {
            "collection": "aria_docs_manuals",
            "document_id": "doc-2",
            "document_name": "Camera.pdf",
            "chunk_count": 8,
            "latest_timestamp": "2026-04-06T02:05:00+00:00",
            "preview": "Camera preview",
        },
        {
            "collection": "aria_docs_notes",
            "document_id": "doc-3",
            "document_name": "Notes.md",
            "chunk_count": 3,
            "latest_timestamp": "2026-04-05T10:00:00+00:00",
            "preview": "Notes preview",
        },
    ]

    groups = _build_document_collection_groups(entries)

    assert [group["collection"] for group in groups] == ["aria_docs_manuals", "aria_docs_notes"]
    assert groups[0]["document_count"] == 2
    assert groups[0]["chunk_count"] == 20
    assert groups[0]["documents"][0]["document_name"] == "Camera.pdf"


def test_memories_map_redirect_keeps_feedback_on_map() -> None:
    response = _memories_map_redirect(info="ok", error="problem")

    assert response.status_code == 303
    assert response.headers["location"] == "/memories?info=ok&error=problem"


def test_memory_admin_redirect_helpers_use_registry_route_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return route_path

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    responses = [
        _memories_redirect(
            filter_type="all",
            query="atlas",
            collection_filter="",
            page=1,
            limit=50,
            sort="updated_desc",
            info="ok",
        ),
        _memories_map_redirect(error="map problem"),
        _memories_overview_redirect(info="overview ok"),
        _memories_import_redirect(info="import ok"),
        _memories_create_redirect(error="create problem"),
        _memories_maintenance_redirect(info="maintenance ok"),
    ]

    assert [response.headers["location"] for response in responses] == [
        "/memories?info=ok",
        "/memories?error=map+problem",
        "/memories?info=overview+ok",
        "/memories/import?info=import+ok",
        "/memories/create?error=create+problem",
        "/memories/maintenance?info=maintenance+ok",
    ]
    assert calls == [
        ("memory_admin_ui", "/memories"),
        ("memory_admin_ui", "/memories"),
        ("memory_admin_ui", "/memories"),
        ("memory_admin_ui", "/memories/import"),
        ("memory_admin_ui", "/memories/create"),
        ("memory_admin_ui", "/memories/maintenance"),
    ]


def test_memory_admin_redirect_helpers_fail_closed_without_route_owner(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    monkeypatch.setattr(memories_routes, "module_route_path", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories"):
        _memories_map_redirect(info="ok")
    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/import"):
        _memories_import_redirect(info="ok")
    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/create"):
        _memories_create_redirect(info="ok")
    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories/maintenance"):
        _memories_maintenance_redirect(info="ok")


def test_memory_overview_guard_redirects_use_registry_route_readpoints(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return real_route_path(module_id, route_path)

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    inactive_client = _build_memories_app(memory_skill_enabled=False)
    inactive_response = inactive_client.post(
        "/memories/delete",
        data={"collection": "aria_facts_tester", "point_id": "point-1"},
        follow_redirects=False,
    )
    assert inactive_response.status_code == 303
    assert inactive_response.headers["location"] == "/memories?error=Memory+nicht+aktiv"
    assert ("memory_admin_ui", "/memories") in calls


def test_memory_overview_guard_redirects_fail_closed_without_route_owner(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    real_route_path = memories_routes.module_route_path
    monkeypatch.setattr(
        memories_routes,
        "module_route_path",
        lambda module_id, route_path: None
        if module_id == "memory_admin_ui" and route_path == "/memories"
        else real_route_path(module_id, route_path),
    )
    client = _build_memories_app(memory_skill_enabled=False)

    with pytest.raises(RuntimeError, match="memory_admin_ui route is not registered: /memories"):
        client.post(
            "/memories/delete",
            data={"collection": "aria_facts_tester", "point_id": "point-1"},
            follow_redirects=False,
        )


def test_memories_map_route_redirects_to_canonical_memories_page() -> None:
    client = _build_memories_app()

    response = client.get("/memories/map?info=ok&error=problem", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/memories?info=ok&error=problem"


def test_memories_redirect_keeps_collection_filter() -> None:
    response = _memories_redirect(
        filter_type="all",
        query="atlas",
        collection_filter="aria_docs_demo_user",
        page=2,
        limit=50,
        sort="collection",
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/memories"


def test_memory_collection_link_uses_matching_type_for_document_collections(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return route_path

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    url = _memory_collection_link(kind="document", collection="aria_docs_demo_user_manuals")

    assert url == "/memories"
    assert calls == [("memory_admin_ui", "/memories")]


def test_memory_collection_link_uses_learning_event_type() -> None:
    url = _memory_collection_link(kind="learning_event", collection="aria_learning_events_tester")

    assert url == "/memories"


def test_memory_collection_link_uses_learning_candidate_type() -> None:
    url = _memory_collection_link(kind="learning_candidate", collection="aria_learning_candidates_tester")

    assert url == "/memories"


def test_memory_collection_link_uses_learning_eval_type() -> None:
    url = _memory_collection_link(kind="learning_eval", collection="aria_learning_evals_tester")

    assert url == "/memories"


def test_memory_collection_link_uses_notes_readpoint(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return route_path

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    assert _memory_collection_link(kind="notes", collection="aria_notes_tester") == "/notes"
    assert calls == [("notes", "/notes")]


def test_memory_document_link_uses_registry_route_readpoint(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return route_path

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    assert _memory_document_link(collection="aria_docs_demo_user", document_id="doc-42") == "/memories"
    assert calls == [("memory_admin_ui", "/memories")]


def test_routing_graph_link_uses_registry_route_readpoint(monkeypatch) -> None:
    import aria.modules.memory_admin_ui.routes as memories_routes

    calls: list[tuple[str, str]] = []

    def _module_route_path(module_id: str, route_path: str) -> str | None:
        calls.append((module_id, route_path))
        return route_path

    monkeypatch.setattr(memories_routes, "module_route_path", _module_route_path)

    assert _routing_graph_link() == "/memories"
    assert calls == [("memory_admin_ui", "/memories")]


def test_memory_document_link_points_to_document_chunks_view() -> None:
    url = _memory_document_link(
        collection="aria_docs_demo_user",
        document_id="doc-42",
        document_name="Atlas.pdf",
    )

    assert url == "/memories"


def test_document_matches_filter_accepts_id_or_name() -> None:
    row = {"document_id": "doc-42", "document_name": "Atlas.pdf"}

    assert _document_matches_filter(row, document_id="doc-42") is True
    assert _document_matches_filter(row, document_name="Atlas.pdf") is True
    assert _document_matches_filter(row, document_id="doc-99", document_name="Other.pdf") is False


def test_build_memory_groups_orders_document_before_other_types() -> None:
    rows = [
        {"type": "fact", "label": "FAKT", "text": "a"},
        {"type": "document", "label": "DOKUMENT", "text": "b"},
        {"type": "knowledge", "label": "WISSEN", "text": "c"},
        {"type": "document", "label": "DOKUMENT", "text": "d"},
    ]

    groups = _build_memory_groups(rows)

    assert [group["type"] for group in groups] == ["document", "knowledge", "fact"]
    assert groups[0]["count"] == 2


def test_build_rollup_entries_and_groups() -> None:
    rows = [
        {
            "id": "r1",
            "collection": "aria_context-mem_neo",
            "source": "compression",
            "rollup_level": "week",
            "rollup_bucket": "2026-W14",
            "rollup_period_start": "2026-03-30",
            "rollup_period_end": "2026-04-05",
            "rollup_source_kind": "session_day",
            "rollup_source_count": 4,
            "timestamp": "2026-04-06T02:00:00+00:00",
            "text": "Wochen-Rollup mit Netzwerk- und Kamera-Themen",
        },
        {
            "id": "r2",
            "collection": "aria_context-mem_neo",
            "source": "compression",
            "rollup_level": "month",
            "rollup_bucket": "2026-03",
            "rollup_period_start": "2026-03-01",
            "rollup_period_end": "2026-03-31",
            "rollup_source_kind": "session_week",
            "rollup_source_count": 3,
            "timestamp": "2026-04-06T03:00:00+00:00",
            "text": "Monats-Rollup mit den wichtigsten Infrastruktur-Themen",
        },
    ]

    entries = _build_rollup_entries(rows)
    groups = _build_rollup_groups(entries)

    assert [entry["level"] for entry in entries] == ["week", "month"]
    assert groups[0]["level"] == "week"
    assert groups[1]["level"] == "month"
    assert groups[0]["entries"][0]["bucket"] == "2026-W14"


def test_build_memory_graph_includes_root_kinds_and_detail_nodes() -> None:
    graph = _build_memory_graph(
        username="neo",
        lang="de",
        map_rows=[
            {"name": "aria_facts_neo", "kind": "fact", "points": 12, "share_pct": 20},
            {"name": "aria_prefs_neo", "kind": "preference", "points": 8, "share_pct": 13},
            {"name": "aria_docs_neo_manuals", "kind": "document", "points": 24, "share_pct": 40},
            {"name": "aria_context-mem_neo", "kind": "knowledge", "points": 16, "share_pct": 27},
        ],
        kind_totals={"fact": 12, "preference": 8, "knowledge": 16, "document": 24, "session": 0},
        document_groups=[
            {
                "collection": "aria_docs_neo_manuals",
                "document_count": 2,
                "chunk_count": 24,
            }
        ],
        rollup_groups=[
            {
                "level": "week",
                "label": "WOCHE",
                "count": 3,
            }
        ],
        notes_rows=[
            {
                "name": "aria_notes_neo",
                "kind": "notes",
                "points": 6,
                "share_pct": 100,
                "browse_url": "/notes",
            }
        ],
        routing_rows=[
            {
                "name": "aria_routing_connections_neo_8800",
                "kind": "routing",
                "points": 116,
                "share_pct": 100,
                "browse_url": "/memories",
            }
        ],
        system_rows=[
            {
                "name": "aria_recipe_experience_neo",
                "kind": "recipe_experience",
                "points": 0,
                "share_pct": 0,
                "browse_url": "/recipes/mine",
            }
        ],
    )

    labels = [node["label"] for node in graph["nodes"]]
    hrefs = {node["label"]: node.get("href", "") for node in graph["nodes"]}
    assert graph["has_graph"] is True
    assert "neo" in labels
    assert "Fakten" in labels
    assert "Dokumente" in labels
    assert "aria_docs_neo_manuals" in labels
    assert "WOCHE" in labels
    assert "Notizen" in labels
    assert "aria_notes_neo" in labels
    assert "Routing" in labels
    assert "aria_routing_connections_neo_8800" in labels
    assert "Recipe Experience" in labels
    assert "aria_recipe_experience_neo" in labels
    assert hrefs.get("aria_docs_neo_manuals", "") == "/memories"
    assert hrefs.get("Notizen", "") == "/notes"
    assert hrefs.get("aria_notes_neo", "") == "/notes"
    assert hrefs.get("Routing", "") == "/memories"
    assert hrefs.get("aria_routing_connections_neo_8800", "") == "/memories"
    assert hrefs.get("Recipe Experience", "") == "/recipes/mine"
    assert hrefs.get("aria_recipe_experience_neo", "") == "/recipes/mine"
    icons = {node["label"]: node.get("icon", "") for node in graph["nodes"]}
    assert icons.get("aria_docs_neo_manuals") == "files"
    assert icons.get("WOCHE") == "llm"
    assert icons.get("aria_notes_neo") == "notes"
    assert icons.get("aria_routing_connections_neo_8800") == "routing"
    assert icons.get("aria_recipe_experience_neo") == "skills"
    assert graph["edges"]


def test_build_qdrant_brain_graph_uses_similarity_without_exposing_vectors() -> None:
    graph = _build_qdrant_brain_graph(
        [
            {
                "id": "a",
                "collection": "aria_facts_neo",
                "type": "fact",
                "text": "Dev server memory",
                "source": "memory",
                "vector": [1.0, 0.0, 0.0],
            },
            {
                "id": "b",
                "collection": "aria_facts_neo",
                "type": "fact",
                "text": "Development host memory",
                "source": "memory",
                "vector": [0.95, 0.05, 0.0],
            },
            {
                "id": "c",
                "collection": "aria_docs_neo",
                "type": "document",
                "document_name": "Manual.pdf",
                "text": "Manual chunk",
                "source": "document",
                "vector": [0.0, 1.0, 0.0],
            },
        ],
        lang="de",
    )

    assert graph["has_graph"] is True
    assert graph["sample_count"] == 3
    assert graph["edge_count"] >= 1
    assert all("vector" not in node for node in graph["nodes"])
    assert graph["nodes"][0]["preview"] == "Dev server memory"


def test_build_qdrant_brain_graph_labels_document_chunks_as_chunks() -> None:
    graph = _build_qdrant_brain_graph(
        [
            {
                "id": "chunk-7",
                "collection": "aria_docs_tester",
                "type": "document",
                "document_name": "Manual.pdf",
                "chunk_index": 7,
                "chunk_total": 12,
                "text": "The actual chunk text should drive the visible detail.",
                "source": "rag_upload",
                "vector": [1.0, 0.0, 0.0],
            },
            {
                "id": "chunk-8",
                "collection": "aria_docs_tester",
                "type": "document",
                "document_name": "Manual.pdf",
                "chunk_index": 8,
                "chunk_total": 12,
                "text": "Neighbor chunk content.",
                "source": "rag_upload",
                "vector": [0.98, 0.02, 0.0],
            },
        ],
        lang="de",
        max_nodes=8,
        max_edges=8,
    )

    first = graph["nodes"][0]
    assert first["label"] == "Chunk 7"
    assert first["level"] == "chunk"
    assert first["document_name"] == "Manual.pdf"
    assert first["chunk_index"] == 7
    assert first["chunk_total"] == 12
    assert "Manual.pdf" in first["meta"]
    assert "Chunk 7/12" in first["meta"]
    assert "actual chunk text" in first["preview"]


def test_build_qdrant_brain_graph_keeps_collection_points_connected() -> None:
    graph = _build_qdrant_brain_graph(
        [
            {
                "id": "a",
                "collection": "aria_notes_neo",
                "type": "notes",
                "text": "Architecture note",
                "source": "notes",
                "vector": [1.0, 0.0, 0.0],
            },
            {
                "id": "b",
                "collection": "aria_notes_neo",
                "type": "notes",
                "text": "Architecture feature backlog",
                "source": "notes",
                "vector": [0.92, 0.08, 0.0],
            },
            {
                "id": "c",
                "collection": "aria_notes_neo",
                "type": "notes",
                "text": "Distant but same collection",
                "source": "notes",
                "vector": [0.0, 1.0, 0.0],
            },
            {
                "id": "d",
                "collection": "aria_notes_neo",
                "type": "notes",
                "text": "Another distant same collection point",
                "source": "notes",
                "vector": [0.0, 0.0, 1.0],
            },
        ],
        lang="de",
        max_edges=12,
    )

    assert graph["has_graph"] is True
    assert graph["edge_count"] >= 3
    connected = {int(edge["source"]) for edge in graph["edges"]} | {int(edge["target"]) for edge in graph["edges"]}
    assert connected == {0, 1, 2, 3}


def test_memory_skill_graph_sampler_uses_existing_user_normalization() -> None:
    assert hasattr(MemorySkill, "_user_filter") is True
    assert hasattr(MemorySkill, "_normalize_user_id") is False
    assert "_normalize_user_id" not in MemorySkill.list_memory_graph_points.__code__.co_names


def test_is_uploaded_file_accepts_fastapi_and_starlette_uploadfile() -> None:
    assert _is_uploaded_file(FastAPIUploadFile(filename="a.txt", file=None)) is True
    assert _is_uploaded_file(StarletteUploadFile(filename="b.txt", file=None)) is True
    assert _is_uploaded_file("not-a-file") is False
