from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import parse_qs

import pytest

import aria.core.learning_worker as learning_worker
from aria.web.memories_routes import (
    _document_matches_filter,
    _memory_collection_link,
    _memory_document_link,
    _build_notes_collection_rows,
    _build_routing_collection_rows,
    _build_system_collection_rows,
    _build_memory_graph,
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
    _normalize_document_collection_name,
    _resolve_document_target_collection,
)
from aria.core.qdrant_collection_classifier import classify_qdrant_collection
from aria.skills.base import SkillResult
from aria.skills.memory import MemorySkill
from fastapi import UploadFile as FastAPIUploadFile
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile as StarletteUploadFile
from types import SimpleNamespace


@pytest.fixture(autouse=True)
def _isolated_learning_worker_audit(monkeypatch, tmp_path):
    monkeypatch.setattr(learning_worker, "_AUDIT_PATH", tmp_path / "learning_worker_audit.jsonl")


def _sanitize_collection_name(value: str | None) -> str:
    import re

    if not value:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", value).strip("_")
    clean = re.sub(r"_+", "_", clean)
    return clean[:64]


def _build_memories_app(
    memory_graph_points: list[dict[str, object]] | None = None,
) -> TestClient:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)

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

    class _MemorySkill:
        def __init__(self) -> None:
            self.payload_updates: list[dict[str, object]] = []
            self.execute_calls: list[dict[str, object]] = []

        async def get_user_collection_stats(self, _username: str) -> list[dict[str, object]]:
            return [
                {"name": "aria_facts_tester", "points": 12, "kind": "fact"},
                {"name": "aria_learning_tester", "points": 2, "kind": "reflection"},
                {"name": "aria_learning_events_tester", "points": 1, "kind": "learning_event"},
                {"name": "aria_learning_candidates_tester", "points": 1, "kind": "learning_candidate"},
                {"name": "aria_learning_active_hints_tester", "points": 1, "kind": "learning_active_hint"},
                {"name": "aria_learning_evals_tester", "points": 1, "kind": "learning_eval"},
            ]

        async def list_memory_graph_points(
            self,
            user_id: str,
            limit: int = 96,
            collection_limit: int = 18,
        ) -> list[dict[str, object]]:
            _ = (user_id, limit, collection_limit)
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
            ]

        async def list_memories_global(
            self,
            user_id: str,
            type_filter: str = "all",
            limit: int = 200,
            collection_filter: str = "",
        ) -> list[dict[str, object]]:
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
            ]
            clean_type = str(type_filter or "all").strip().lower()
            clean_collection = str(collection_filter or "").strip()
            if clean_type and clean_type != "all":
                rows = [row for row in rows if str(row.get("type", "")).strip().lower() == clean_type]
            if clean_collection:
                rows = [row for row in rows if str(row.get("collection", "")).strip() == clean_collection]
            return rows

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
            return True

        async def execute(self, query: str, params: dict) -> SkillResult:
            self.execute_calls.append({"query": query, "params": dict(params)})
            return SkillResult(skill_name="memory", content="Speicheraktion erfolgreich.", success=True)

    memory_skill = _MemorySkill()
    pipeline = SimpleNamespace(memory_skill=memory_skill)
    app.state.memory_skill = memory_skill

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

    from aria.web.memories_routes import register_memories_routes

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

    register_memories_routes(
        app,
        templates=templates,
        get_settings=lambda: settings,
        get_pipeline=lambda: pipeline,
        get_username_from_request=lambda _request: "tester",
        get_auth_session_from_request=lambda _request: {"role": "admin"},
        sanitize_role=lambda value: str(value or "").strip().lower(),
        qdrant_overview=_qdrant_overview,
        qdrant_dashboard_url=lambda _request: "http://qdrant.local:6333/dashboard",
        parse_collection_day_suffix=lambda _value: None,
        sanitize_collection_name=_sanitize_collection_name,
        default_memory_collection_for_user=lambda username: f"aria_facts_{username.lower()}",
        get_effective_memory_collection=lambda _request, username: f"aria_facts_{username.lower()}",
        is_auto_memory_enabled=lambda _request: True,
        read_raw_config=lambda: {},
        write_raw_config=lambda _raw: None,
        reload_runtime=lambda: None,
        resolve_prompt_file=lambda value: Path("/tmp") / value,
        get_secure_store=lambda _raw=None: None,
        memory_collection_cookie="aria_memory_collection",
        auto_memory_cookie="aria_auto_memory",
    )
    return TestClient(app)


def _app_learning_candidate_text(*, target_file: str = "tests/test_app_plan_generated.py") -> str:
    return (
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
        'Pytest skeleton proposal: {"proposal_kind":"pytest_skeleton_proposal","target_file":"'
        + target_file
        + '","test_functions":[{"name":"test_install_update_plan_renders_without_execution","test_kind":"plan_preview","act":"call the draft/validation helper under test"}],"safety_notes":["proposal only, do not write files automatically"],"write_allowed":false,"runtime_activation_allowed":false}'
    )


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
    assert rows[0]["browse_url"] == "/recipes/learned"
    assert rows[1]["kind"] == "system"
    assert rows[1]["browse_url"] == "/memories/config#qdrant-access"


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


def test_memories_overview_page_renders_unified_memory_hub() -> None:
    client = _build_memories_app()

    response = client.get("/memories")

    assert response.status_code == 200
    assert "Memory Overview" in response.text
    assert "Memory-Graph" in response.text
    assert "Nächste Schritte" not in response.text
    assert "/memories#memories-actions" not in response.text
    assert "Dokumente importieren" in response.text
    assert "Eigene Memory erfassen" in response.text
    assert "/memories/config#qdrant-access" in response.text
    assert '/memories/config#auto-memory' in response.text
    assert "Qdrant" in response.text
    assert "aria_recipe_experience_tester" in response.text
    assert "System-Collections" in response.text
    assert "data-memory-brain" not in response.text


def test_memories_map_page_shows_notes_and_routing_collections() -> None:
    client = _build_memories_app()

    response = client.get("/memories/map")

    assert response.status_code == 200
    assert "aria_notes_tester" in response.text
    assert "aria_learning_tester" in response.text
    assert "aria_learning_events_tester" in response.text
    assert "aria_learning_candidates_tester" in response.text
    assert "aria_learning_evals_tester" in response.text
    assert "aria_recipe_experience_tester" in response.text
    assert "Notes-Collections" in response.text
    assert "Routing-Collections" in response.text
    assert "System-Collections" in response.text
    assert 'href="/notes"' in response.text
    assert "/config/routing" in response.text
    assert "/recipes/learned" in response.text
    assert "type=reflection" in response.text
    assert "type=learning_event" in response.text
    assert "type=learning_candidate" in response.text
    assert "type=learning_eval" in response.text
    assert "collection_filter=aria_learning_events_tester" in response.text
    assert "collection_filter=aria_learning_candidates_tester" in response.text
    assert "collection_filter=aria_learning_evals_tester" in response.text
    assert 'href="/memories/config#rollup"' in response.text
    assert "Komprimierung im Memory-Setup öffnen" in response.text
    assert "Qdrant Brain" in response.text
    assert "data-memory-brain" in response.text
    assert "data-brain-touch-toggle" in response.text
    assert "memory-map-frame-wrap memory-graph-wrap" not in response.text
    assert "memory-legacy-graph-scroll" in response.text
    assert "SSH server context" in response.text
    assert "[1.0, 0.0, 0.0]" not in response.text


def test_memories_map_page_shows_brain_empty_state_when_no_vectors() -> None:
    client = _build_memories_app(memory_graph_points=[])

    response = client.get("/memories/map")

    assert response.status_code == 200
    assert "Qdrant Brain" in response.text
    assert "data-memory-brain" in response.text
    assert "Noch keine visualisierbaren Qdrant-Punkte gefunden" in response.text


def test_memories_explorer_stays_focused_on_browsing_not_creation() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer")

    assert response.status_code == 200
    assert "Memory Explorer" in response.text
    assert "Dokumente importieren" not in response.text
    assert "Eigene Memory erfassen" not in response.text


def test_memories_explorer_shows_learning_worker_status_card() -> None:
    from aria.core.learning_worker import reset_learning_worker_state

    reset_learning_worker_state()
    client = _build_memories_app()

    response = client.get("/memories/explorer")

    assert response.status_code == 200
    assert "Learning Worker" in response.text
    assert "Budget" in response.text
    assert "/memories/learning-worker/flush" in response.text


def test_memories_learning_worker_detail_route_returns_job_snapshot() -> None:
    import asyncio

    from aria.core.learning_worker import enqueue_learning_job
    from aria.core.learning_worker import reset_learning_worker_state

    async def _run() -> str:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            raise RuntimeError("detail route failure")

        result = enqueue_learning_job(
            job_type="runtime_outcome",
            user_id="tester",
            source="test",
            artifact_type="routing_hint",
            factory=job,
        )
        await asyncio.sleep(0)
        return str(result["job_id"])

    job_id = asyncio.run(_run())
    client = _build_memories_app()

    response = client.get(f"/memories/learning-worker/job/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["job"]["job_id"] == job_id
    assert payload["job"]["status"] == "failed"
    assert payload["job"]["retryable"] is True


def test_memories_learning_worker_flush_route_clears_finished_jobs() -> None:
    import asyncio

    from aria.core.learning_worker import enqueue_learning_job
    from aria.core.learning_worker import reset_learning_worker_state

    async def _run() -> None:
        reset_learning_worker_state()

        async def job() -> dict[str, object]:
            return {"captured": True}

        enqueue_learning_job(job_type="runtime_outcome", user_id="tester", source="test", factory=job)
        await asyncio.sleep(0)

    asyncio.run(_run())
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-worker/flush",
        data={"scope": "finished"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "learning_worker_flushed_finished_1" in response.headers["location"]


def test_memories_learning_worker_retry_route_requeues_failed_job() -> None:
    import asyncio

    from aria.core.learning_worker import enqueue_learning_job
    from aria.core.learning_worker import get_learning_worker_job
    from aria.core.learning_worker import reset_learning_worker_state

    async def _run() -> str:
        reset_learning_worker_state()
        attempts = {"count": 0}

        async def job() -> dict[str, object]:
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("retry route first failure")
            return {"captured": True}

        result = enqueue_learning_job(job_type="runtime_outcome", user_id="tester", source="test", factory=job)
        await asyncio.sleep(0)
        return str(result["job_id"])

    job_id = asyncio.run(_run())
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-worker/retry",
        data={"job_id": job_id, "force": "1"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "learning_worker_retry_queued" in response.headers["location"]
    detail = get_learning_worker_job(job_id)
    assert detail is not None
    assert detail["status"] in {"queued", "running", "completed"}


def test_memories_explorer_shows_learning_candidate_review_actions() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_candidate")

    assert response.status_code == 200
    assert "Official page excerpts first" in response.text
    assert "Review-only" in response.text
    assert "/memories/learning-candidate/status" in response.text
    assert "/memories/learning-candidate/apply" in response.text
    assert "/memories/learning-candidate/apply-preview" in response.text
    assert "Geprüft" in response.text
    assert "Apply vorbereiten" in response.text
    assert "Apply-Vorschau" in response.text
    assert "regression: missing" in response.text
    assert "Verwerfen" in response.text


def test_memories_explorer_shows_learning_review_queue_summary() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer")

    assert response.status_code == 200
    assert "Learning Review Queue" in response.text
    assert "Kandidaten" in response.text
    assert "Regression" in response.text
    assert "Activation" in response.text
    assert "missing" in response.text


def test_memories_explorer_shows_app_learning_status_chips() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_candidate")

    assert response.status_code == 200
    assert "app-learning" in response.text
    assert "docker_compose" in response.text
    assert "review_required" in response.text
    assert "risk: medium" in response.text
    assert "health drafts: 1" in response.text
    assert "regression drafts: 1" in response.text
    assert "pytest proposal: 1" in response.text
    assert "/srv/aria" in response.text


def test_memories_explorer_shows_learning_eval_dry_run_chunks() -> None:
    client = _build_memories_app()

    response = client.get("/memories/explorer?type=learning_eval")

    assert response.status_code == 200
    assert "Learning Eval Dry-Run" in response.text
    assert "Promotion allowed: no" in response.text
    assert "LERN-EVAL" in response.text


def test_learning_candidate_status_route_updates_qdrant_payload() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/status",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "decision": "review",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    memory_skill = client.app.state.memory_skill
    assert memory_skill.payload_updates[-1]["collection"] == "aria_learning_candidates_tester"
    assert memory_skill.payload_updates[-1]["point_id"] == "candidate-1"
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["candidate_status"] == "reviewed"
    assert payload["review_decision"] == "review"
    assert payload["promotion_state"] == "eligible"
    assert payload["promotion_gate_result"] == "eligible"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_status_route_blocks_higher_risk_candidate_promotion() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/status",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "decision": "review",
            "artifact_type": "procedure_candidate",
            "risk": "medium",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["candidate_status"] == "reviewed"
    assert payload["promotion_state"] == "reviewed_blocked"
    assert payload["promotion_gate_result"] == "blocked"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_apply_route_prepares_qdrant_payload() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/apply",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "promotion_state": "eligible",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["apply_state"] == "prepared"
    assert payload["apply_gate_result"] == "prepared"
    assert payload["apply_requires_regression"] is True
    assert payload["regression_status"] == "missing"
    assert payload["apply_runtime_effect"] == "none"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_apply_route_blocks_non_eligible_candidate() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/apply",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "procedure_candidate",
            "risk": "medium",
            "promotion_state": "reviewed_blocked",
            "candidate_text": "Learning Candidate: Procedure",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["apply_state"] == "blocked"
    assert payload["apply_gate_result"] == "blocked"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_apply_preview_renders_read_only_admin_preview() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories/learning-candidate/apply-preview",
        params={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_status": "missing",
            "candidate_text": (
                "Learning Candidate: Official page excerpts first\n"
                "Type: source_rule_candidate\n"
                "Summary: Prefer official page excerpts."
            ),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
    )

    assert response.status_code == 200
    assert "Apply-Vorschau" in response.text
    assert "source_rule_candidate" in response.text
    assert "source_rule" in response.text
    assert "/memories/learning-candidate/regression" in response.text
    assert "Regressionstest verlinken" in response.text
    assert "Pflicht vor jeder Aktivierung" in response.text
    assert "Regression missing" in response.text
    assert "regression_missing" in response.text
    assert "disabled" in response.text
    assert "prefer official page excerpts" in response.text


def test_learning_candidate_apply_preview_renders_app_learning_sections() -> None:
    client = _build_memories_app()
    candidate_text = (
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
    )

    response = client.get(
        "/memories/learning-candidate/apply-preview",
        params={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "candidate_text": candidate_text,
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
    )

    assert response.status_code == 200
    assert "App Identity" in response.text
    assert "Plan Draft" in response.text
    assert "Validation / Gates" in response.text
    assert "Health Drafts" in response.text
    assert "Regression Drafts" in response.text
    assert "Pytest Skeleton Proposal" in response.text
    assert "docker_compose" in response.text
    assert "/srv/aria/docker-compose.yml" in response.text
    assert "run docker compose up -d only after explicit confirmation" in response.text
    assert "test_install_update_plan_renders_without_execution" in response.text
    assert "tests/test_app_plan_generated.py" in response.text
    assert "write: False" in response.text
    assert "preview_ready" in response.text
    assert "target exists: False" in response.text
    assert "Code Preview" in response.text
    assert "/memories/learning-candidate/pytest/prepare-write" in response.text
    assert "Write vorbereiten" in response.text
    assert "def test_install_update_plan_renders_without_execution()" in response.text
    assert "runtime: False" in response.text


def test_learning_candidate_apply_preview_renders_prepared_artifact_review_actions() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories/learning-candidate/apply-preview",
        params={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "pytest_write_state": "prepared",
            "pytest_write_gate_result": "prepared",
            "pytest_target_file": "tests/test_app_plan_generated.py",
            "pytest_code_preview_sha256": "abcdef1234567890",
            "candidate_text": _app_learning_candidate_text(),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
    )

    assert response.status_code == 200
    assert "Prepared Artifact Review" in response.text
    assert "/memories/learning-candidate/artifact/review" in response.text
    assert "sha256: abcdef123456" in response.text
    assert "Akzeptieren" in response.text
    assert "Änderungen nötig" in response.text
    assert "Verwerfen" in response.text


def test_learning_candidate_pytest_prepare_write_route_stores_prepared_payload_without_writing() -> None:
    client = _build_memories_app()
    candidate_text = _app_learning_candidate_text()
    target = Path(__file__).resolve().parents[1] / "tests" / "test_app_plan_generated.py"

    response = client.post(
        "/memories/learning-candidate/pytest/prepare-write",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "candidate_text": candidate_text,
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "info=pytest_write_prepared" in response.headers["location"]
    assert "pytest_write_state=prepared" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["pytest_write_state"] == "prepared"
    assert payload["pytest_write_gate_result"] == "prepared"
    assert payload["pytest_write_requires_review"] is True
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert payload["pytest_target_file"] == "tests/test_app_plan_generated.py"
    assert payload["pytest_test_functions"] == ["test_install_update_plan_renders_without_execution"]
    assert "def test_install_update_plan_renders_without_execution()" in payload["pytest_code_preview"]
    assert len(payload["pytest_code_preview_sha256"]) == 64
    assert target.exists() is False


def test_learning_candidate_pytest_prepare_write_route_stores_blocked_payload_for_bad_target() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/pytest/prepare-write",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "candidate_text": _app_learning_candidate_text(target_file="aria/test_bad.py"),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "info=pytest_write_blocked" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["pytest_write_state"] == "blocked"
    assert payload["pytest_write_gate_result"] == "blocked"
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert "target_outside_tests" in payload["pytest_write_blockers"]
    assert "pytest_code_preview" not in payload


def test_learning_candidate_artifact_review_route_stores_accepted_outcome_in_qdrant() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/artifact/review",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_kind": "pytest_skeleton_write",
            "decision": "accepted",
            "review_notes": "Useful skeleton.",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "pytest_write_state": "prepared",
            "pytest_write_gate_result": "prepared",
            "pytest_target_file": "tests/test_app_plan_generated.py",
            "pytest_code_preview_sha256": "abcdef1234567890",
            "candidate_text": _app_learning_candidate_text(),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "info=artifact_review_reviewed" in response.headers["location"]
    assert "pytest_write_review_decision=accepted" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["prepared_artifact_kind"] == "pytest_skeleton_write"
    assert payload["prepared_artifact_review_state"] == "reviewed"
    assert payload["prepared_artifact_review_decision"] == "accepted"
    assert payload["prepared_artifact_review_signal"] == "positive"
    assert payload["pytest_write_review_state"] == "reviewed"
    assert payload["pytest_write_review_notes"] == "Useful skeleton."
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert [call["params"]["memory_type"] for call in memory_skill.execute_calls[-3:]] == [
        "learning_event",
        "learning_candidate",
        "learning_eval",
    ]
    assert memory_skill.execute_calls[-2]["params"]["collection"] == "aria_learning_candidates_tester"
    assert "artifact_pattern_candidate" in memory_skill.execute_calls[-2]["query"]


def test_learning_candidate_artifact_review_route_blocks_unprepared_artifact() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/artifact/review",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-app-1",
            "artifact_kind": "pytest_skeleton_write",
            "decision": "accepted",
            "artifact_type": "install_plan_candidate",
            "risk": "medium",
            "apply_state": "",
            "regression_status": "missing",
            "pytest_write_state": "blocked",
            "pytest_write_gate_result": "blocked",
            "candidate_text": _app_learning_candidate_text(target_file="aria/test_bad.py"),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "info=artifact_review_blocked" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["prepared_artifact_review_state"] == "blocked"
    assert "artifact_not_prepared" in payload["prepared_artifact_review_blockers"]
    assert payload["pytest_write_allowed"] is False
    assert payload["runtime_activation_allowed"] is False
    assert memory_skill.execute_calls == []


def test_learning_candidate_apply_preview_shows_linked_regression_ref() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories/learning-candidate/apply-preview",
        params={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "routing_hint",
            "risk": "low",
            "apply_state": "prepared",
            "regression_status": "linked",
            "regression_ref": "tests/test_pipeline.py::test_explicit_recall_uses_memory",
            "candidate_text": "Learning Candidate: Route explicit recall to memory\nType: routing_hint",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
    )

    assert response.status_code == 200
    assert "linked" in response.text
    assert "tests/test_pipeline.py::test_explicit_recall_uses_memory" in response.text
    assert "/memories/learning-candidate/regression/verify" in response.text
    assert "Regression prüfen" in response.text
    assert "regression_missing" not in response.text


def test_learning_candidate_regression_route_links_valid_test_ref() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/regression",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_ref": "tests/test_pipeline.py::test_explicit_recall_uses_memory",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "regression_status=linked" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["regression_status"] == "linked"
    assert payload["regression_ref"] == "tests/test_pipeline.py::test_explicit_recall_uses_memory"
    assert payload["regression_link_result"] == "linked"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_regression_route_rejects_invalid_test_ref() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/regression",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_ref": "docs/manual-check.md",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "regression_status=missing" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["regression_status"] == "missing"
    assert payload["regression_ref"] == ""
    assert payload["regression_link_result"] == "invalid"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_regression_verify_route_marks_existing_test_ref() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/regression/verify",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_ref": "tests/test_memories_routes.py::test_learning_candidate_regression_verify_route_marks_existing_test_ref",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "regression_verified=true" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["regression_status"] == "linked"
    assert payload["regression_verified"] is True
    assert payload["regression_test_exists"] is True
    assert payload["regression_verify_result"] == "not_run"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_regression_verify_route_marks_missing_test_ref() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/regression/verify",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_ref": "tests/test_memories_routes.py::test_missing_case",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "regression_verified=false" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["regression_verified"] is False
    assert payload["regression_verify_result"] == "missing"
    assert payload["regression_verify_reason"] == "test_name_missing"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_apply_preview_shows_run_button_after_verification() -> None:
    client = _build_memories_app()

    response = client.get(
        "/memories/learning-candidate/apply-preview",
        params={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "routing_hint",
            "risk": "low",
            "apply_state": "prepared",
            "regression_status": "linked",
            "regression_ref": "tests/test_pipeline.py::test_explicit_recall_uses_memory",
            "regression_verified": "true",
            "regression_verify_result": "not_run",
            "candidate_text": "Learning Candidate: Route explicit recall to memory\nType: routing_hint",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
    )

    assert response.status_code == 200
    assert "/memories/learning-candidate/regression/run" in response.text
    assert "Regression ausführen" in response.text
    assert "regression_not_passed" in response.text


def test_learning_candidate_regression_run_route_records_passed_result(monkeypatch) -> None:
    import aria.web.memories_routes as memories_routes

    client = _build_memories_app()

    def fake_run_learning_candidate_regression_payload(**kwargs):
        assert kwargs["regression_ref"] == "tests/test_pipeline.py::test_existing"
        return {
            "regression_required": True,
            "regression_status": "linked",
            "regression_ref": kwargs["regression_ref"],
            "regression_verified": True,
            "regression_test_exists": True,
            "regression_verify_result": "passed",
            "regression_verify_reason": "pytest_passed",
            "regression_last_run_output": "1 passed",
            "regression_run_returncode": 0,
            "runtime_activation_allowed": False,
        }

    monkeypatch.setattr(memories_routes, "run_learning_candidate_regression_payload", fake_run_learning_candidate_regression_payload)

    response = client.post(
        "/memories/learning-candidate/regression/run",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "source_rule_candidate",
            "risk": "low",
            "apply_state": "prepared",
            "regression_ref": "tests/test_pipeline.py::test_existing",
            "candidate_text": "Learning Candidate: Official page excerpts first",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "regression_verify_result=passed" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["regression_verify_result"] == "passed"
    assert payload["regression_run_returncode"] == 0
    assert payload["regression_last_run_output"] == "1 passed"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_activation_preflight_route_marks_candidate_ready() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/activation-preflight",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "routing_hint",
            "risk": "low",
            "promotion_state": "eligible",
            "apply_state": "prepared",
            "regression_status": "linked",
            "regression_ref": "tests/test_pipeline.py::test_existing",
            "regression_verified": "true",
            "regression_verify_result": "passed",
            "candidate_text": "Learning Candidate: URL source questions\nType: routing_hint",
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "activation_preflight_state=passed" in response.headers["location"]
    memory_skill = client.app.state.memory_skill
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["activation_preflight_state"] == "passed"
    assert payload["activation_runtime_effect"] == "weak_signal_only"
    assert payload["runtime_activation_allowed"] is False


def test_learning_candidate_activate_route_stores_active_hint_in_qdrant() -> None:
    client = _build_memories_app()

    response = client.post(
        "/memories/learning-candidate/activate",
        data={
            "collection": "aria_learning_candidates_tester",
            "point_id": "candidate-1",
            "artifact_type": "routing_hint",
            "risk": "low",
            "regression_ref": "tests/test_pipeline.py::test_existing",
            "activation_preflight_state": "passed",
            "candidate_text": (
                "Learning Candidate: URL source questions\n"
                "Type: routing_hint\n"
                "Summary: Concrete source URLs should bias toward web_search."
            ),
            "type": "learning_candidate",
            "collection_filter": "aria_learning_candidates_tester",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    memory_skill = client.app.state.memory_skill
    assert memory_skill.execute_calls[-1]["params"]["action"] == "store"
    assert memory_skill.execute_calls[-1]["params"]["collection"] == "aria_learning_active_hints_tester"
    assert memory_skill.execute_calls[-1]["params"]["memory_type"] == "learning_active_hint"
    payload = memory_skill.payload_updates[-1]["payload_updates"]
    assert payload["activation_state"] == "active_hint_stored"
    assert payload["active_hint_collection"] == "aria_learning_active_hints_tester"
    assert payload["runtime_activation_allowed"] is False


def test_memories_root_redirects_legacy_explorer_query_to_new_explorer_path() -> None:
    client = _build_memories_app()

    response = client.get("/memories?type=document&sort=collection", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/memories/explorer?type=document&sort=collection"


def test_memory_setup_page_keeps_qdrant_access_in_one_place() -> None:
    client = _build_memories_app()

    response = client.get("/memories/config")

    assert response.status_code == 200
    assert response.text.count("Qdrant Dashboard + API-Key kopieren") == 1
    assert 'id="qdrant-access"' in response.text
    assert 'data-copy-source="qdrant-url"' in response.text
    assert 'data-copy-source="qdrant-key"' in response.text
    assert 'type="password"' in response.text
    assert 'data-copy-value="secret-key"' in response.text
    assert 'data-dashboard-url="http://qdrant.local:6333/dashboard"' in response.text
    assert "Memory backend enabled" not in response.text


def test_memory_backend_save_always_keeps_backend_enabled() -> None:
    app = FastAPI()
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "aria" / "templates"))
    templates.env.globals.setdefault("tr", lambda _request, _key, fallback="": fallback)
    templates.env.globals.setdefault("agent_name", lambda _request, fallback="ARIA": fallback)

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

    from aria.web.memories_routes import register_memories_routes

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
        is_auto_memory_enabled=lambda _request: True,
        read_raw_config=_read_raw_config,
        write_raw_config=_write_raw_config,
        reload_runtime=_reload_runtime,
        resolve_prompt_file=lambda value: Path("/tmp") / value,
        get_secure_store=lambda _raw=None: None,
        memory_collection_cookie="aria_memory_collection",
        auto_memory_cookie="aria_auto_memory",
    )

    client = TestClient(app)
    response = client.post(
        "/memories/config/backend-save",
        data={"backend": "qdrant", "qdrant_url": "http://qdrant:6333", "qdrant_api_key": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert urlparse(response.headers["location"]).path == "/memories/config"
    assert runtime_reloaded["called"] is True
    assert writes
    assert writes[0]["memory"]["enabled"] is True


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
    assert response.headers["location"] == "/memories/map?info=ok&error=problem"


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
    assert "collection_filter=aria_docs_demo_user" in response.headers["location"]


def test_memory_collection_link_uses_matching_type_for_document_collections() -> None:
    url = _memory_collection_link(kind="document", collection="aria_docs_demo_user_manuals")

    assert url.startswith("/memories/explorer?type=document")
    assert "collection_filter=aria_docs_demo_user_manuals" in url


def test_memory_collection_link_uses_learning_event_type() -> None:
    url = _memory_collection_link(kind="learning_event", collection="aria_learning_events_tester")

    assert url.startswith("/memories/explorer?type=learning_event")
    assert "collection_filter=aria_learning_events_tester" in url


def test_memory_collection_link_uses_learning_candidate_type() -> None:
    url = _memory_collection_link(kind="learning_candidate", collection="aria_learning_candidates_tester")

    assert url.startswith("/memories/explorer?type=learning_candidate")
    assert "collection_filter=aria_learning_candidates_tester" in url


def test_memory_collection_link_uses_learning_eval_type() -> None:
    url = _memory_collection_link(kind="learning_eval", collection="aria_learning_evals_tester")

    assert url.startswith("/memories/explorer?type=learning_eval")
    assert "collection_filter=aria_learning_evals_tester" in url


def test_memory_document_link_points_to_document_chunks_view() -> None:
    url = _memory_document_link(
        collection="aria_docs_demo_user",
        document_id="doc-42",
        document_name="Atlas.pdf",
    )

    assert url.startswith("/memories/explorer?type=document")
    assert "collection_filter=aria_docs_demo_user" in url
    assert "document_id=doc-42" in url


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
                "browse_url": "/config/routing",
            }
        ],
        system_rows=[
            {
                "name": "aria_recipe_experience_neo",
                "kind": "recipe_experience",
                "points": 0,
                "share_pct": 0,
                "browse_url": "/recipes/learned",
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
    assert "type=document" in str(hrefs.get("aria_docs_neo_manuals", ""))
    assert hrefs.get("Notizen", "") == "/notes"
    assert hrefs.get("aria_notes_neo", "") == "/notes"
    assert hrefs.get("Routing", "") == "/config/routing"
    assert hrefs.get("aria_routing_connections_neo_8800", "") == "/config/routing"
    assert hrefs.get("Recipe Experience", "") == "/recipes/learned"
    assert hrefs.get("aria_recipe_experience_neo", "") == "/recipes/learned"
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
        ]
    )

    assert graph["has_graph"] is True
    assert graph["sample_count"] == 3
    assert graph["edge_count"] >= 1
    assert all("vector" not in node for node in graph["nodes"])
    assert graph["nodes"][0]["preview"] == "Dev server memory"


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
