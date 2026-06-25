from __future__ import annotations

from contextlib import suppress
from datetime import datetime
import hmac
import json
import math
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile

from aria.core.artifact_review_learning import capture_prepared_artifact_review_learning
from aria.core.document_ingest import DocumentIngestError, prepare_uploaded_document, supported_upload_suffixes
from aria.core.app_regression_apply_preview import build_pytest_apply_preview
from aria.core.app_regression_apply_preview import prepare_prepared_artifact_review_payload
from aria.core.app_regression_apply_preview import prepare_pytest_write_payload
from aria.core.i18n import I18NStore
from aria.core.learning_promotion import build_learning_candidate_apply_preview
from aria.core.learning_promotion import build_learning_candidate_activation_preview
from aria.core.learning_promotion import learning_active_hint_store_params
from aria.core.learning_promotion import learning_candidate_gate_inputs
from aria.core.learning_promotion import learning_candidate_apply_allowed
from aria.core.learning_promotion import learning_candidate_apply_preview_allowed
from aria.core.learning_promotion import learning_candidate_activation_preflight_payload
from aria.core.learning_promotion import link_learning_candidate_regression_payload
from aria.core.learning_promotion import learning_candidate_promotion_gate
from aria.core.learning_promotion import prepare_learning_candidate_apply_payload
from aria.core.learning_promotion import run_learning_candidate_regression_payload
from aria.core.learning_promotion import verify_learning_candidate_regression_payload
from aria.core.learning_worker import flush_learning_worker_jobs
from aria.core.learning_worker import get_learning_worker_job
from aria.core.learning_worker import get_learning_worker_status
from aria.core.learning_worker import retry_learning_job
from aria.core.pipeline import Pipeline
from aria.core.qdrant_collection_classifier import classify_qdrant_collection
from aria.core.qdrant_collection_classifier import is_notes_qdrant_collection
from aria.core.qdrant_collection_classifier import is_recipe_experience_qdrant_collection
from aria.core.qdrant_collection_classifier import is_routing_qdrant_collection
from aria.core.runtime_endpoint import cookie_should_be_secure, request_is_secure


BASE_DIR = Path(__file__).resolve().parents[2]
_MEMORIES_ROUTES_I18N = I18NStore(BASE_DIR / "aria" / "i18n")

UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]

APP_LEARNING_ARTIFACT_TYPES = {
    "app_artifact_candidate",
    "app_identity_candidate",
    "install_plan_candidate",
    "health_check_candidate",
}
RoleSanitizer = Callable[[str | None], str]
SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Pipeline]
QdrantOverviewLoader = Callable[[Request], Awaitable[dict[str, Any]]]
QdrantDashboardUrlResolver = Callable[[Request], str]
CollectionDayParser = Callable[[str], datetime | None]
CollectionNameSanitizer = Callable[[str | None], str]
DefaultCollectionResolver = Callable[[str], str]
EffectiveCollectionResolver = Callable[[Request, str], str]
AutoMemoryResolver = Callable[[Request], bool]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
PromptFileResolver = Callable[[str], Path]
SecureStoreGetter = Callable[[dict[str, Any] | None], Any]


def _is_admin_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    auth = get_auth_session_from_request(request) or {}
    return sanitize_role(auth.get("role")) == "admin"


def _msg(lang: str, de: str, en: str) -> str:
    return de if str(lang or "de").strip().lower().startswith("de") else en


def _memory_routes_text(lang: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _MEMORIES_ROUTES_I18N.t(lang or "de", f"memories_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _friendly_memory_error(lang: str, exc: Exception, de_default: str, en_default: str) -> str:
    if isinstance(exc, ValueError):
        detail = str(exc).strip()
        if detail:
            return detail
    return _msg(lang, de_default, en_default)


def _is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    submitted = str(submitted_token or "").strip()
    expected = str(expected_token or "").strip()
    return bool(submitted and expected and hmac.compare_digest(submitted, expected))


def _normalize_memory_sort(value: str) -> str:
    sort_key = str(value).strip().lower()
    allowed_sorts = {"updated_desc", "updated_asc", "type", "collection", "score_desc"}
    if sort_key not in allowed_sorts:
        return "updated_desc"
    return sort_key


def _coerce_page_size(value: int) -> int:
    return max(10, min(int(value), 100))


def _coerce_page_number(value: int) -> int:
    return max(1, int(value))


def _coerce_form_int(value: Any, default: int) -> int:
    try:
        return int(str(value if value is not None else default).strip() or default)
    except (TypeError, ValueError):
        return default


def _is_uploaded_file(value: Any) -> bool:
    return isinstance(value, (UploadFile, StarletteUploadFile))


def _memory_row_timestamp(row: dict[str, Any]) -> float:
    raw = str(row.get("timestamp", "")).strip()
    if not raw:
        return 0.0
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return parsed.timestamp()


def _sort_memory_rows(rows: list[dict[str, Any]], sort_key: str) -> None:
    if sort_key == "updated_asc":
        rows.sort(key=_memory_row_timestamp)
        return
    if sort_key == "type":
        rows.sort(key=lambda row: (str(row.get("type", "")).lower(), -_memory_row_timestamp(row)))
        return
    if sort_key == "collection":
        rows.sort(key=lambda row: (str(row.get("collection", "")).lower(), -_memory_row_timestamp(row)))
        return
    if sort_key == "score_desc":
        rows.sort(key=lambda row: float(row.get("score", 0.0) or 0.0), reverse=True)
        return
    rows.sort(key=_memory_row_timestamp, reverse=True)


def _build_memory_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for row in rows:
        key = str(row.get("type", "")).strip().lower()
        if key in counts:
            counts[key] += 1
    return counts


def _build_learning_review_queue(rows: list[dict[str, Any]]) -> dict[str, Any]:
    queue = {
        "candidate_total": 0,
        "candidate_open": 0,
        "candidate_reviewed": 0,
        "candidate_blocked": 0,
        "candidate_active": 0,
        "eval_total": 0,
        "active_hint_total": 0,
        "regression_missing": 0,
        "regression_linked": 0,
        "regression_passed": 0,
        "activation_ready": 0,
        "activation_blocked": 0,
    }
    for row in rows:
        row_type = str(row.get("type", "") or "").strip().lower()
        if row_type == "learning_eval":
            queue["eval_total"] += 1
            continue
        if row_type == "learning_active_hint":
            queue["active_hint_total"] += 1
            continue
        if row_type != "learning_candidate":
            continue
        queue["candidate_total"] += 1
        candidate_status = str(row.get("candidate_status", "") or row.get("status", "") or "").strip().lower()
        promotion_state = str(row.get("promotion_state", "") or "").strip().lower()
        activation_state = str(row.get("activation_state", "") or row.get("activation_preflight_state", "") or "").strip().lower()
        regression_status = str(row.get("regression_status", "") or "").strip().lower()
        regression_result = str(row.get("regression_verify_result", "") or "").strip().lower()
        if activation_state in {"active_hint_stored", "passed"}:
            queue["candidate_active"] += 1
        elif promotion_state in {"reviewed_blocked", "blocked"} or candidate_status == "rejected":
            queue["candidate_blocked"] += 1
        elif candidate_status == "reviewed" or promotion_state in {"eligible", "prepared"}:
            queue["candidate_reviewed"] += 1
        else:
            queue["candidate_open"] += 1
        if regression_result == "passed":
            queue["regression_passed"] += 1
        elif regression_status == "linked":
            queue["regression_linked"] += 1
        elif row_type == "learning_candidate":
            queue["regression_missing"] += 1
        if activation_state == "passed":
            queue["activation_ready"] += 1
        if activation_state == "blocked":
            queue["activation_blocked"] += 1
    queue["has_learning_items"] = any(
        int(queue[key] or 0) > 0
        for key in ("candidate_total", "eval_total", "active_hint_total")
    )
    return queue


def _memory_group_order(value: str) -> int:
    order = {
        "document": 0,
        "knowledge": 1,
        "fact": 2,
        "preference": 3,
        "session": 4,
    }
    return order.get(str(value or "").strip().lower(), 99)


def _build_type_points(collection_stats: list[dict[str, Any]]) -> dict[str, int]:
    type_points = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for item in collection_stats:
        kind = str(item.get("kind", "fact")).strip().lower()
        points = int(item.get("points", 0) or 0)
        if kind in type_points:
            type_points[kind] += points
    return type_points


def _build_memory_health(
    *,
    all_rows: list[dict[str, Any]],
    collection_stats: list[dict[str, Any]],
    filter_type: str,
    query: str,
    parse_collection_day_suffix: CollectionDayParser,
    compress_after_days: int,
    qdrant_reachable: bool,
) -> dict[str, Any]:
    type_points = _build_type_points(collection_stats)
    total_points = int(sum(type_points.values()))
    largest = max(collection_stats, key=lambda row: int(row.get("points", 0) or 0), default=None)
    largest_name = str((largest or {}).get("name", "")).strip() or "n/a"
    largest_points = int((largest or {}).get("points", 0) or 0)
    largest_share_pct = int((largest_points / total_points) * 100) if total_points > 0 else 0

    stale_sessions = 0
    now = datetime.now()
    for item in collection_stats:
        name = str(item.get("name", "")).strip()
        if "session" not in name.lower():
            continue
        day = parse_collection_day_suffix(name)
        if not day:
            continue
        age_days = max(0, (now - day).days)
        if age_days >= compress_after_days:
            stale_sessions += 1

    return {
        "rows_shown": 0,
        "rows_total": len(all_rows),
        "filter_type": filter_type,
        "search_query": query.strip(),
        "user_collections": len(collection_stats),
        "user_total_points": total_points,
        "type_points": type_points,
        "largest_collection_name": largest_name,
        "largest_collection_points": largest_points,
        "largest_collection_share_pct": largest_share_pct,
        "stale_sessions": stale_sessions,
        "compress_after_days": compress_after_days,
        "qdrant_reachable": bool(qdrant_reachable),
    }


def _build_cleanup_status(memory_skill: Any | None) -> dict[str, Any]:
    fallback = {
        "scope": "",
        "user_id": "",
        "removed_count": 0,
        "removed_collections": [],
        "timestamp": "",
    }
    if not memory_skill:
        return fallback
    return dict(getattr(memory_skill, "last_cleanup_status", {}) or fallback)


async def _build_memory_map_snapshot(
    *,
    pipeline: Any,
    username: str,
    overview: dict[str, Any],
    is_admin: bool,
    settings: Any,
    parse_collection_day_suffix: CollectionDayParser,
) -> dict[str, Any]:
    user_rows: list[dict[str, Any]] = []
    notes_rows: list[dict[str, Any]] = []
    routing_rows: list[dict[str, Any]] = []
    system_rows: list[dict[str, Any]] = []
    collection_stats: list[dict[str, Any]] = []
    document_entries: list[dict[str, Any]] = []
    document_groups: list[dict[str, Any]] = []
    rollup_entries: list[dict[str, Any]] = []
    rollup_groups: list[dict[str, Any]] = []
    memory_graph: dict[str, Any] = {"nodes": [], "edges": [], "width": 0, "height": 0, "has_graph": False}
    qdrant_brain_graph: dict[str, Any] = {
        "nodes": [],
        "edges": [],
        "width": 0,
        "height": 0,
        "has_graph": False,
        "sample_count": 0,
        "edge_count": 0,
        "collection_count": 0,
        "error": "",
    }
    memory_skill = getattr(pipeline, "memory_skill", None)

    if memory_skill:
        try:
            stats = await memory_skill.get_user_collection_stats(username)
            collection_stats = list(stats)
            all_status = {
                str(item.get("name", "")): str(item.get("status", "ok"))
                for item in overview.get("collections", [])
            }
            for row in stats:
                name = str(row.get("name", "")).strip()
                kind = str(row.get("kind", "fact"))
                user_rows.append(
                    {
                        "name": name,
                        "points": int(row.get("points", 0) or 0),
                        "kind": kind,
                        "status": all_status.get(name, "ok"),
                        "browse_url": _memory_collection_link(kind=kind, collection=name),
                    }
                )
        except Exception:
            user_rows = []
        try:
            document_rows = await memory_skill.list_memories_global(
                user_id=username,
                type_filter="document",
                limit=5000,
            )
            document_entries = _build_document_entries(document_rows)
            document_groups = _build_document_collection_groups(document_entries)
        except Exception:
            document_entries = []
            document_groups = []
        try:
            knowledge_rows = await memory_skill.list_memories_global(
                user_id=username,
                type_filter="knowledge",
                limit=5000,
            )
            rollup_entries = _build_rollup_entries(knowledge_rows)
            rollup_groups = _build_rollup_groups(rollup_entries)
        except Exception:
            rollup_entries = []
            rollup_groups = []
        if hasattr(memory_skill, "list_memory_graph_points"):
            try:
                graph_rows = await memory_skill.list_memory_graph_points(
                    user_id=username,
                    limit=96,
                    collection_limit=18,
                )
                qdrant_brain_graph = _build_qdrant_brain_graph(list(graph_rows))
            except Exception as exc:
                qdrant_brain_graph = {
                    "nodes": [],
                    "edges": [],
                    "width": 0,
                    "height": 0,
                    "has_graph": False,
                    "sample_count": 0,
                    "edge_count": 0,
                    "collection_count": 0,
                    "error": str(exc),
                }

    user_rows.sort(key=lambda row: int(row.get("points", 0) or 0), reverse=True)
    max_points = max((int(row.get("points", 0) or 0) for row in user_rows), default=0)
    total_points = int(sum(int(row.get("points", 0) or 0) for row in user_rows))
    for row in user_rows:
        points = int(row.get("points", 0) or 0)
        row["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
        row["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        row["node_size"] = max(16, min(54, int(16 + (row["pct"] / 100.0) * 38)))

    kind_totals = {"fact": 0, "preference": 0, "knowledge": 0, "reflection": 0, "learning_event": 0, "learning_candidate": 0, "learning_active_hint": 0, "learning_eval": 0, "document": 0, "session": 0}
    for row in user_rows:
        kind = str(row.get("kind", "fact"))
        if kind in kind_totals:
            kind_totals[kind] += int(row.get("points", 0) or 0)

    if is_admin:
        notes_rows = _build_notes_collection_rows(
            list(overview.get("collections", []) or []),
            username=username,
            browse_url="/notes",
        )
        routing_rows = _build_routing_collection_rows(
            list(overview.get("collections", []) or []),
            known_user_collection_names={
                str(row.get("name", "")).strip() for row in [*user_rows, *notes_rows]
            },
            browse_url="/config/routing",
        )
        system_rows = _build_system_collection_rows(
            list(overview.get("collections", []) or []),
            known_collection_names={
                str(row.get("name", "")).strip() for row in [*user_rows, *notes_rows, *routing_rows]
            },
        )

    notes_total_points = int(sum(int(row.get("points", 0) or 0) for row in notes_rows))
    routing_total_points = int(sum(int(row.get("points", 0) or 0) for row in routing_rows))
    system_total_points = int(sum(int(row.get("points", 0) or 0) for row in system_rows))
    cleanup_status = _build_cleanup_status(memory_skill)
    cleanup_status["timestamp"] = _format_display_timestamp(cleanup_status.get("timestamp"))

    health = _build_memory_health(
        all_rows=[],
        collection_stats=collection_stats,
        filter_type="all",
        query="",
        parse_collection_day_suffix=parse_collection_day_suffix,
        compress_after_days=int(settings.memory.collections.sessions.compress_after_days or 7),
        qdrant_reachable=bool(overview.get("reachable")),
    )
    memory_graph = _build_memory_graph(
        username=username,
        map_rows=user_rows,
        kind_totals=kind_totals,
        document_groups=document_groups,
        rollup_groups=rollup_groups,
        notes_rows=notes_rows,
        routing_rows=routing_rows,
        system_rows=system_rows,
    )
    memory_graph["brain"] = qdrant_brain_graph

    return {
        "user_rows": user_rows,
        "notes_rows": notes_rows,
        "notes_total_points": notes_total_points,
        "routing_rows": routing_rows,
        "routing_total_points": routing_total_points,
        "system_rows": system_rows,
        "system_total_points": system_total_points,
        "collection_stats": collection_stats,
        "document_entries": document_entries,
        "document_groups": document_groups,
        "rollup_entries": rollup_entries,
        "rollup_groups": rollup_groups,
        "memory_graph": memory_graph,
        "health": health,
        "cleanup_status": cleanup_status,
        "kind_totals": kind_totals,
        "total_points": total_points,
    }


def _format_display_timestamp(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw.replace("T", " ", 1)


def _slug_user_id(user_id: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() or ch in {"_", "-"} else "_" for ch in str(user_id or "").strip())
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    return clean or "web"


def _memory_title(text: str, *, limit: int = 88) -> str:
    raw = " ".join(str(text or "").strip().split())
    if not raw:
        return "Leerer Eintrag"
    for splitter in (". ", "! ", "? ", "\n"):
        if splitter in raw:
            raw = raw.split(splitter, 1)[0].strip()
            break
    if len(raw) <= limit:
        return raw
    return raw[: max(20, limit - 1)].rstrip() + "…"


def _memory_preview(text: str, *, limit: int = 180) -> str:
    raw = " ".join(str(text or "").strip().split())
    if len(raw) <= limit:
        return raw
    return raw[: max(40, limit - 1)].rstrip() + "…"


def _candidate_json_section(text: str, label: str) -> Any:
    prefix = f"{label}:"
    for line in str(text or "").splitlines():
        if not line.startswith(prefix):
            continue
        raw = line[len(prefix) :].strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return None
    return None


def _build_app_learning_preview(candidate_text: str) -> dict[str, Any]:
    app_identity = _candidate_json_section(candidate_text, "App identity hypothesis")
    plan_draft = _candidate_json_section(candidate_text, "Install/update plan draft")
    plan_validation = _candidate_json_section(candidate_text, "Install/update plan validation")
    health_drafts = _candidate_json_section(candidate_text, "Health check drafts")
    regression_drafts = _candidate_json_section(candidate_text, "Regression drafts")
    pytest_skeleton_proposal = _candidate_json_section(candidate_text, "Pytest skeleton proposal")
    app_identity = app_identity if isinstance(app_identity, dict) else {}
    plan_draft = plan_draft if isinstance(plan_draft, dict) else {}
    plan_validation = plan_validation if isinstance(plan_validation, dict) else {}
    health_drafts = health_drafts if isinstance(health_drafts, list) else []
    regression_drafts = regression_drafts if isinstance(regression_drafts, list) else []
    pytest_skeleton_proposal = pytest_skeleton_proposal if isinstance(pytest_skeleton_proposal, dict) else {}
    return {
        "available": bool(app_identity or plan_draft or plan_validation or health_drafts or regression_drafts or pytest_skeleton_proposal),
        "app_identity": app_identity,
        "plan_draft": plan_draft,
        "plan_validation": plan_validation,
        "health_drafts": health_drafts,
        "regression_drafts": regression_drafts,
        "pytest_skeleton_proposal": pytest_skeleton_proposal,
        "pytest_apply_preview": build_pytest_apply_preview(pytest_skeleton_proposal, repo_root=BASE_DIR)
        if pytest_skeleton_proposal
        else {},
        "runtime_kind": str(app_identity.get("runtime_kind") or plan_draft.get("runtime_kind") or "").strip(),
        "app_root": str(app_identity.get("app_root") or plan_draft.get("app_root") or "").strip(),
        "validation_state": str(plan_validation.get("validation_state") or "").strip(),
        "risk_level": str(plan_validation.get("risk_level") or plan_draft.get("risk") or "").strip(),
        "health_draft_count": len(health_drafts),
        "regression_draft_count": len(regression_drafts),
        "pytest_function_count": len(pytest_skeleton_proposal.get("test_functions", []) or []),
    }


def _build_prepared_artifact_review(
    *,
    pytest_write_state: str = "",
    pytest_write_gate_result: str = "",
    pytest_target_file: str = "",
    pytest_code_preview_sha256: str = "",
    pytest_write_review_state: str = "",
    pytest_write_review_decision: str = "",
    pytest_write_review_notes: str = "",
) -> dict[str, Any]:
    return {
        "pytest_write_state": str(pytest_write_state or "").strip(),
        "pytest_write_gate_result": str(pytest_write_gate_result or "").strip(),
        "pytest_target_file": str(pytest_target_file or "").strip(),
        "pytest_code_preview_sha256": str(pytest_code_preview_sha256 or "").strip(),
        "pytest_write_review_state": str(pytest_write_review_state or "").strip(),
        "pytest_write_review_decision": str(pytest_write_review_decision or "").strip(),
        "pytest_write_review_notes": str(pytest_write_review_notes or "").strip(),
        "reviewable": str(pytest_write_state or "").strip().lower() == "prepared",
    }


def _build_document_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if str(row.get("type", "")).strip().lower() != "document":
            continue
        collection = str(row.get("collection", "")).strip()
        document_id = str(row.get("document_id", "")).strip()
        document_name = str(row.get("document_name", "")).strip()
        key = (collection, document_id or document_name)
        if not key[0] or not key[1]:
            continue
        entry = grouped.setdefault(
            key,
            {
                "collection": collection,
                "document_id": document_id,
                "document_name": document_name or "Unbenanntes Dokument",
                "chunk_count": 0,
                "latest_timestamp": "",
                "preview": "",
                "source": str(row.get("source", "")).strip() or "n/a",
            },
        )
        entry["chunk_count"] += 1
        timestamp = str(row.get("timestamp", "")).strip()
        if timestamp and timestamp > str(entry.get("latest_timestamp", "")):
            entry["latest_timestamp"] = timestamp
        if not entry["preview"]:
            entry["preview"] = _memory_preview(str(row.get("text", "")).strip(), limit=120)

    items = list(grouped.values())
    items.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for item in items:
        item["display_timestamp"] = _format_display_timestamp(item.get("latest_timestamp"))
    return items


def _build_document_collection_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        collection = str(entry.get("collection", "")).strip()
        if not collection:
            continue
        group = grouped.setdefault(
            collection,
            {
                "collection": collection,
                "document_count": 0,
                "chunk_count": 0,
                "latest_timestamp": "",
                "documents": [],
            },
        )
        group["document_count"] += 1
        group["chunk_count"] += int(entry.get("chunk_count", 0) or 0)
        timestamp = str(entry.get("latest_timestamp", "")).strip()
        if timestamp and timestamp > str(group.get("latest_timestamp", "")):
            group["latest_timestamp"] = timestamp
        group["documents"].append(entry)

    items = list(grouped.values())
    items.sort(key=lambda item: str(item.get("latest_timestamp", "")), reverse=True)
    for item in items:
        item["display_timestamp"] = _format_display_timestamp(item.get("latest_timestamp"))
        item["documents"].sort(key=lambda row: str(row.get("latest_timestamp", "")), reverse=True)
    return items


def _document_matches_filter(row: dict[str, Any], *, document_id: str = "", document_name: str = "") -> bool:
    clean_document_id = str(document_id or "").strip()
    clean_document_name = str(document_name or "").strip()
    if clean_document_id and str(row.get("document_id", "")).strip() == clean_document_id:
        return True
    if clean_document_name and str(row.get("document_name", "")).strip() == clean_document_name:
        return True
    return False


def _rollup_group_order(level: str) -> int:
    order = {"week": 0, "month": 1}
    return order.get(str(level or "").strip().lower(), 99)


def _rollup_label(level: str) -> str:
    normalized = str(level or "").strip().lower()
    if normalized == "month":
        return "MONAT"
    return "WOCHE"


def _build_rollup_entries(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("source", "")).strip().lower() != "compression":
            continue
        level = str(row.get("rollup_level", "")).strip().lower()
        if level not in {"week", "month"}:
            continue
        bucket = str(row.get("rollup_bucket", "")).strip()
        items.append(
            {
                "id": str(row.get("id", "")).strip(),
                "collection": str(row.get("collection", "")).strip(),
                "level": level,
                "level_label": _rollup_label(level),
                "bucket": bucket,
                "period_start": str(row.get("rollup_period_start", "")).strip(),
                "period_end": str(row.get("rollup_period_end", "")).strip(),
                "source_kind": str(row.get("rollup_source_kind", "")).strip(),
                "source_count": int(row.get("rollup_source_count", 0) or 0),
                "timestamp": str(row.get("timestamp", "")).strip(),
                "display_timestamp": _format_display_timestamp(row.get("timestamp")),
                "preview": _memory_preview(str(row.get("text", "")).strip(), limit=160),
                "title": _memory_title(str(row.get("text", "")).strip(), limit=96),
            }
        )
    items.sort(key=lambda item: (str(item.get("period_end", "")), str(item.get("timestamp", ""))), reverse=True)
    return items


def _build_rollup_groups(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        level = str(entry.get("level", "")).strip().lower()
        if not level:
            continue
        group = grouped.setdefault(
            level,
            {
                "level": level,
                "label": _rollup_label(level),
                "count": 0,
                "entries": [],
            },
        )
        group["count"] += 1
        group["entries"].append(entry)
    items = list(grouped.values())
    items.sort(key=lambda item: (_rollup_group_order(item.get("level", "")), str(item.get("label", ""))))
    return items


def _graph_kind_order(kind: str) -> int:
    order = {
        "fact": 0,
        "preference": 1,
        "session": 2,
        "document": 3,
        "knowledge": 4,
        "reflection": 5,
        "learning_event": 6,
        "learning_candidate": 7,
        "learning_active_hint": 8,
        "learning_eval": 9,
        "notes": 10,
        "routing": 11,
        "recipe_experience": 12,
        "system": 13,
    }
    return order.get(str(kind or "").strip().lower(), 99)


def _graph_kind_label(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    labels = {
        "fact": _memory_routes_text("de", "graph.fact", "Facts"),
        "preference": _memory_routes_text("de", "graph.preference", "Preferences"),
        "session": _memory_routes_text("de", "graph.session", "Daily context"),
        "document": _memory_routes_text("de", "graph.document", "Documents"),
        "knowledge": _memory_routes_text("de", "graph.knowledge", "Knowledge"),
        "reflection": _memory_routes_text("de", "graph.reflection", "Learning"),
        "learning_event": _memory_routes_text("de", "graph.learning_event", "Learning Events"),
        "learning_candidate": _memory_routes_text("de", "graph.learning_candidate", "Learning Candidates"),
        "learning_active_hint": _memory_routes_text("de", "graph.learning_active_hint", "Active Learning Hints"),
        "learning_eval": _memory_routes_text("de", "graph.learning_eval", "Learning Evals"),
        "notes": _memory_routes_text("de", "graph.notes", "Notes"),
        "routing": "Routing",
        "recipe_experience": _memory_routes_text("de", "graph.recipe_experience", "Recipe Experience"),
        "system": _memory_routes_text("de", "graph.system", "System"),
    }
    return labels.get(normalized, normalized.upper() or "Memory")


def _graph_kind_icon(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    icons = {
        "root": "memories",
        "fact": "memories",
        "preference": "settings",
        "session": "activities",
        "document": "files",
        "knowledge": "llm",
        "reflection": "llm",
        "learning_event": "activities",
        "learning_candidate": "skills",
        "learning_active_hint": "llm",
        "learning_eval": "check",
        "notes": "notes",
        "routing": "routing",
        "recipe_experience": "skills",
        "system": "settings",
    }
    return icons.get(normalized, "memories")


def _routing_graph_link() -> str:
    return "/config/routing"


def _memory_graph_link(*, kind: str = "all", collection: str = "") -> str:
    url = f"/memories/explorer?type={quote_plus(kind)}&q=&sort=updated_desc&limit=50&page=1"
    if collection:
        url += f"&collection_filter={quote_plus(collection)}"
    return url


def _memory_collection_link(*, kind: str = "all", collection: str = "") -> str:
    normalized_kind = str(kind or "").strip().lower() or "all"
    if normalized_kind == "notes":
        return "/notes"
    if normalized_kind not in {"all", "fact", "preference", "knowledge", "reflection", "learning_event", "learning_candidate", "learning_active_hint", "learning_eval", "document", "session"}:
        normalized_kind = "all"
    return _memory_graph_link(kind=normalized_kind, collection=collection)


def _memory_document_link(
    *,
    collection: str = "",
    document_id: str = "",
    document_name: str = "",
) -> str:
    url = _memory_graph_link(kind="document", collection=collection)
    if document_id:
        url += f"&document_id={quote_plus(document_id)}"
    elif document_name:
        url += f"&document_name={quote_plus(document_name)}"
    return url


def _build_memory_graph(
    *,
    username: str,
    map_rows: list[dict[str, Any]],
    kind_totals: dict[str, int],
    document_groups: list[dict[str, Any]],
    rollup_groups: list[dict[str, Any]],
    notes_rows: list[dict[str, Any]] | None = None,
    routing_rows: list[dict[str, Any]] | None = None,
    system_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    note_items = list(notes_rows or [])
    routing_items = list(routing_rows or [])
    system_items = list(system_rows or [])
    kinds = [kind for kind, points in kind_totals.items() if int(points or 0) > 0]
    if note_items:
        kinds.append("notes")
    if routing_items:
        kinds.append("routing")
    for row in system_items:
        kind = str(row.get("kind", "system")).strip().lower() or "system"
        if kind not in kinds:
            kinds.append(kind)
    if not kinds:
        return {"nodes": [], "edges": [], "width": 0, "height": 0, "has_graph": False}

    kinds.sort(key=_graph_kind_order)
    collection_rows_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in kinds}
    for row in map_rows:
        kind = str(row.get("kind", "")).strip().lower()
        if kind in collection_rows_by_kind:
            collection_rows_by_kind[kind].append(row)
    for rows in collection_rows_by_kind.values():
        rows.sort(key=lambda item: int(item.get("points", 0) or 0), reverse=True)

    detail_nodes_by_kind: dict[str, list[dict[str, Any]]] = {kind: [] for kind in kinds}
    for kind in kinds:
        if kind == "document":
            for group in document_groups[:4]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(group.get("collection", "")).strip(),
                        "meta": (
                            f"{int(group.get('document_count', 0) or 0)} Dokumente"
                            f" · {int(group.get('chunk_count', 0) or 0)} Chunks"
                        ),
                        "href": _memory_collection_link(
                            kind="document",
                            collection=str(group.get("collection", "")).strip(),
                        ),
                        "variant": "collection",
                    }
                )
            continue
        if kind == "knowledge":
            for group in rollup_groups[:2]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(group.get("label", "")).strip(),
                        "meta": f"{int(group.get('count', 0) or 0)} Rollups",
                        "href": _memory_graph_link(kind="knowledge"),
                        "variant": "rollup",
                    }
                )
        if kind == "notes":
            for row in note_items[:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} Punkte"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or "/notes",
                        "variant": "notes",
                    }
                )
            continue
        if kind == "routing":
            for row in routing_items[:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} Punkte"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or _routing_graph_link(),
                        "variant": "routing",
                    }
                )
            continue
        if kind in {"recipe_experience", "system"}:
            for row in [item for item in system_items if str(item.get("kind", "")).strip().lower() == kind][:3]:
                detail_nodes_by_kind[kind].append(
                    {
                        "label": str(row.get("name", "")).strip(),
                        "meta": (
                            f"{int(row.get('points', 0) or 0)} Punkte"
                            f" · {int(row.get('share_pct', 0) or 0)}%"
                        ),
                        "href": str(row.get("browse_url", "")).strip() or "/memories/config#qdrant-access",
                        "variant": kind,
                    }
                )
            continue
        for row in collection_rows_by_kind.get(kind, [])[:2]:
            detail_nodes_by_kind[kind].append(
                {
                    "label": str(row.get("name", "")).strip(),
                    "meta": f"{int(row.get('points', 0) or 0)} Punkte · {int(row.get('share_pct', 0) or 0)}%",
                    "href": _memory_collection_link(
                        kind=kind,
                        collection=str(row.get("name", "")).strip(),
                    ),
                    "variant": "collection",
                }
            )

    column_gap = 184
    root_y = 70
    type_y = 188
    detail_start_y = 316
    detail_gap_y = 100
    root_width = 190
    type_width = 150
    detail_width = 148
    stage_padding = 72
    width = max(732, stage_padding * 2 + max(1, len(kinds) - 1) * column_gap + type_width)
    start_x = width / 2 if len(kinds) == 1 else stage_padding + type_width / 2
    step = 0 if len(kinds) == 1 else (width - stage_padding * 2 - type_width) / max(1, len(kinds) - 1)
    max_detail_rows = max((len(items) for items in detail_nodes_by_kind.values()), default=0)
    height = 414 + max(0, max_detail_rows - 1) * detail_gap_y

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, float]] = []
    memory_total_points = sum(int(value or 0) for value in kind_totals.values())
    notes_total_points = sum(int(row.get("points", 0) or 0) for row in note_items)
    routing_total_points = sum(int(row.get("points", 0) or 0) for row in routing_items)
    system_total_points = sum(int(row.get("points", 0) or 0) for row in system_items)
    root_meta = f"{memory_total_points} Punkte im Memory"
    if notes_total_points > 0:
        root_meta += f" · {notes_total_points} Notes-Punkte"
    if routing_total_points > 0:
        root_meta += f" · {routing_total_points} Routing-Punkte"
    if system_items:
        root_meta += f" · {len(system_items)} System-Collections"
    nodes.append(
        {
            "id": "graph-root",
            "kind": "root",
            "label": username,
            "meta": root_meta,
            "left": round(width / 2 - root_width / 2, 2),
            "top": 20,
            "width": root_width,
            "href": _memory_graph_link(),
            "variant": "root",
            "icon": _graph_kind_icon("root"),
        }
    )

    for index, kind in enumerate(kinds):
        x_center = start_x + index * step
        type_id = f"graph-kind-{kind}"
        nodes.append(
            {
                "id": type_id,
                "kind": kind,
                "label": _graph_kind_label(kind),
                "meta": (
                    _memory_routes_text("de", "graph.routing_points", "{points} points · System", points=routing_total_points)
                    if kind == "routing"
                    else _memory_routes_text(
                        "de",
                        "graph.recipe_experience_points",
                        "{points} points · Learning",
                        points=sum(
                            int(row.get("points", 0) or 0)
                            for row in system_items
                            if str(row.get("kind", "")).strip().lower() == "recipe_experience"
                        ),
                    )
                    if kind == "recipe_experience"
                    else _memory_routes_text("de", "graph.system_points", "{points} points · System", points=system_total_points)
                    if kind == "system"
                    else _memory_routes_text("de", "graph.notes_points", "{points} points · Notes", points=notes_total_points)
                    if kind == "notes"
                    else _memory_routes_text("de", "graph.points", "{points} points", points=int(kind_totals.get(kind, 0) or 0))
                ),
                "left": round(x_center - type_width / 2, 2),
                "top": round(type_y - 38, 2),
                "width": type_width,
                "href": _routing_graph_link()
                if kind == "routing"
                else "/recipes/learned"
                if kind == "recipe_experience"
                else "/memories/config#qdrant-access"
                if kind == "system"
                else "/notes"
                if kind == "notes"
                else _memory_graph_link(kind=kind if kind != "knowledge" else "knowledge"),
                "variant": "type",
                "icon": _graph_kind_icon(kind),
            }
        )
        edges.append(
            {
                "x1": round(width / 2, 2),
                "y1": root_y + 38,
                "x2": round(x_center, 2),
                "y2": type_y - 8,
            }
        )
        for detail_index, item in enumerate(detail_nodes_by_kind.get(kind, [])):
            detail_y = detail_start_y + detail_index * detail_gap_y
            nodes.append(
                {
                    "id": f"{type_id}-detail-{detail_index}",
                    "kind": kind,
                    "label": str(item.get("label", "")).strip(),
                    "meta": str(item.get("meta", "")).strip(),
                    "left": round(x_center - detail_width / 2, 2),
                    "top": round(detail_y - 28, 2),
                    "width": detail_width,
                    "href": str(item.get("href", "")).strip(),
                    "variant": str(item.get("variant", "detail")).strip(),
                    "icon": _graph_kind_icon(kind),
                }
            )
            edges.append(
                {
                    "x1": round(x_center, 2),
                    "y1": type_y + 34,
                    "x2": round(x_center, 2),
                    "y2": round(detail_y - 6, 2),
                }
            )

    return {
        "nodes": nodes,
        "edges": edges,
        "width": int(width),
        "height": int(height),
        "has_graph": True,
    }


def _brain_graph_preview(value: Any, limit: int = 180) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _brain_graph_kind_label(kind: str) -> str:
    return _graph_kind_label(kind)


def _brain_graph_vector(value: Any) -> list[float]:
    if isinstance(value, dict):
        value = next((item for item in value.values() if isinstance(item, list)), None)
    if not isinstance(value, list):
        return []
    vector: list[float] = []
    for item in value:
        if isinstance(item, (int, float)):
            vector.append(float(item))
    return vector


def _brain_graph_cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    if length <= 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(length))
    left_norm = math.sqrt(sum(left[index] * left[index] for index in range(length)))
    right_norm = math.sqrt(sum(right[index] * right[index] for index in range(length)))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _brain_graph_collection_label(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        return "Collection"
    if len(clean) <= 34:
        return clean
    return f"{clean[:31]}..."


def _build_qdrant_brain_graph(rows: list[dict[str, Any]], *, max_nodes: int = 96, max_edges: int = 180) -> dict[str, Any]:
    prepared: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        collection = str(row.get("collection", "")).strip()
        point_id = str(row.get("id", "")).strip()
        if not collection or not point_id:
            continue
        key = (collection, point_id)
        if key in seen:
            continue
        vector = _brain_graph_vector(row.get("vector"))
        if not vector:
            continue
        seen.add(key)
        kind = str(row.get("type", "")).strip().lower() or "unknown"
        title = (
            str(row.get("note_title", "")).strip()
            or str(row.get("document_name", "")).strip()
            or _brain_graph_preview(row.get("text"), 54)
            or point_id
        )
        prepared.append(
            {
                "raw": row,
                "vector": vector,
                "kind": kind,
                "collection": collection,
                "id": point_id,
                "label": title,
            }
        )
        if len(prepared) >= max_nodes:
            break

    if not prepared:
        return {
            "has_graph": False,
            "nodes": [],
            "edges": [],
            "width": 0,
            "height": 0,
            "sample_count": 0,
            "edge_count": 0,
            "collection_count": 0,
            "error": "",
        }

    collection_indexes: dict[str, list[int]] = {}
    for index, item in enumerate(prepared):
        collection_indexes.setdefault(str(item["collection"]), []).append(index)

    required_edges: dict[tuple[int, int], float] = {}
    optional_edges: dict[tuple[int, int], float] = {}

    def remember_edge(
        edges: dict[tuple[int, int], float],
        left_index: int,
        right_index: int,
        similarity: float,
    ) -> None:
        a, b = sorted((left_index, right_index))
        if a == b:
            return
        # Keep very weak but still best-known links visible enough to shape the graph.
        score = max(0.12, min(1.0, similarity))
        edges[(a, b)] = max(edges.get((a, b), 0.0), score)

    for indexes in collection_indexes.values():
        if len(indexes) < 2:
            continue
        pair_scores: list[tuple[int, int, float]] = []
        neighbor_scores: dict[int, list[tuple[int, float]]] = {index: [] for index in indexes}
        for offset, left_index in enumerate(indexes):
            left = prepared[left_index]
            for right_index in indexes[offset + 1 :]:
                right = prepared[right_index]
                similarity = _brain_graph_cosine(left["vector"], right["vector"])
                pair_scores.append((left_index, right_index, similarity))
                neighbor_scores[left_index].append((right_index, similarity))
                neighbor_scores[right_index].append((left_index, similarity))
        pair_scores.sort(key=lambda item: item[2], reverse=True)

        parent = {index: index for index in indexes}

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left_index: int, right_index: int) -> bool:
            left_root = find(left_index)
            right_root = find(right_index)
            if left_root == right_root:
                return False
            parent[right_root] = left_root
            return True

        # Qdrant's visualization feels connected because every point keeps a nearest-neighbor backbone.
        for left_index, right_index, similarity in pair_scores:
            if union(left_index, right_index):
                remember_edge(required_edges, left_index, right_index, similarity)

        k_neighbors = 7 if len(indexes) <= 48 else 5
        for left_index, scores in neighbor_scores.items():
            scores.sort(key=lambda item: item[1], reverse=True)
            for rank, (right_index, similarity) in enumerate(scores[:k_neighbors]):
                if rank < 2 or similarity >= 0.30:
                    remember_edge(optional_edges, left_index, right_index, similarity)

    combined_edges: dict[tuple[int, int], float] = dict(required_edges)
    optional_ranked = sorted(optional_edges.items(), key=lambda item: item[1], reverse=True)
    for edge_key, score in optional_ranked:
        if len(combined_edges) >= max_edges:
            break
        combined_edges[edge_key] = max(combined_edges.get(edge_key, 0.0), score)
    ranked_edges = sorted(
        [(a, b, score) for (a, b), score in combined_edges.items()],
        key=lambda item: item[2],
        reverse=True,
    )[:max_edges]

    width = 1180
    height = 760
    center_x = width / 2
    center_y = height / 2
    kinds = sorted({item["kind"] for item in prepared}, key=_graph_kind_order)
    kind_centers: dict[str, tuple[float, float]] = {}
    cluster_radius = 230 if len(kinds) > 1 else 0
    for index, kind in enumerate(kinds):
        angle = -math.pi / 2 + (2 * math.pi * index / max(1, len(kinds)))
        kind_centers[kind] = (
            center_x + math.cos(angle) * cluster_radius,
            center_y + math.sin(angle) * cluster_radius,
        )
    positions: list[list[float]] = []
    for index, item in enumerate(prepared):
        cluster_x, cluster_y = kind_centers.get(item["kind"], (center_x, center_y))
        angle = 2 * math.pi * index / max(1, len(prepared))
        positions.append([cluster_x + math.cos(angle) * 54, cluster_y + math.sin(angle) * 54])

    adjacency: dict[int, list[tuple[int, float]]] = {index: [] for index in range(len(prepared))}
    for a, b, score in ranked_edges:
        adjacency[a].append((b, score))
        adjacency[b].append((a, score))

    for _ in range(70):
        forces = [[0.0, 0.0] for _ in prepared]
        for index, item in enumerate(prepared):
            target_x, target_y = kind_centers.get(item["kind"], (center_x, center_y))
            forces[index][0] += (target_x - positions[index][0]) * 0.008
            forces[index][1] += (target_y - positions[index][1]) * 0.008
        for left_index in range(len(prepared)):
            for right_index in range(left_index + 1, len(prepared)):
                dx = positions[left_index][0] - positions[right_index][0]
                dy = positions[left_index][1] - positions[right_index][1]
                dist_sq = max(120.0, dx * dx + dy * dy)
                force = 820.0 / dist_sq
                dist = math.sqrt(dist_sq)
                fx = (dx / dist) * force
                fy = (dy / dist) * force
                forces[left_index][0] += fx
                forces[left_index][1] += fy
                forces[right_index][0] -= fx
                forces[right_index][1] -= fy
        for left_index, neighbors in adjacency.items():
            for right_index, score in neighbors:
                dx = positions[right_index][0] - positions[left_index][0]
                dy = positions[right_index][1] - positions[left_index][1]
                forces[left_index][0] += dx * 0.010 * score
                forces[left_index][1] += dy * 0.010 * score
        for index in range(len(prepared)):
            positions[index][0] = max(54, min(width - 54, positions[index][0] + forces[index][0]))
            positions[index][1] = max(54, min(height - 54, positions[index][1] + forces[index][1]))

    nodes: list[dict[str, Any]] = []
    collection_summaries: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(prepared):
        row = item["raw"]
        x, y = positions[index]
        text = _brain_graph_preview(row.get("text"), 220)
        source = str(row.get("source", "")).strip() or "n/a"
        document_name = str(row.get("document_name", "")).strip()
        note_title = str(row.get("note_title", "")).strip()
        note_folder = str(row.get("note_folder", "")).strip()
        rollup_level = str(row.get("rollup_level", "")).strip()
        detail_parts = [item["collection"], _brain_graph_kind_label(item["kind"]), source]
        if document_name:
            detail_parts.append(document_name)
        if note_title:
            detail_parts.append(note_title)
        if note_folder:
            detail_parts.append(note_folder)
        if rollup_level:
            detail_parts.append(f"Rollup: {rollup_level}")
        summary = collection_summaries.setdefault(
            item["collection"],
            {
                "id": f"brain-collection-{len(collection_summaries)}",
                "collection": item["collection"],
                "label": _brain_graph_collection_label(item["collection"]),
                "point_count": 0,
                "kinds": {},
                "preview": "",
            },
        )
        summary["point_count"] += 1
        summary["kinds"][item["kind"]] = int(summary["kinds"].get(item["kind"], 0) or 0) + 1
        if not summary["preview"]:
            summary["preview"] = text
        nodes.append(
            {
                "id": f"brain-node-{index}",
                "index": index,
                "kind": item["kind"],
                "label": _brain_graph_preview(item["label"], 48),
                "meta": " · ".join(part for part in detail_parts if part),
                "preview": text,
                "collection": item["collection"],
                "point_id": item["id"],
                "x": round(x, 2),
                "y": round(y, 2),
                "radius": 8 if item["kind"] in {"document", "notes"} else 7,
            }
        )
    collections: list[dict[str, Any]] = []
    for summary in collection_summaries.values():
        kinds_meta = ", ".join(
            f"{_brain_graph_kind_label(kind)}: {count}"
            for kind, count in sorted(summary["kinds"].items(), key=lambda item: _graph_kind_order(item[0]))
        )
        collections.append(
            {
                "id": summary["id"],
                "collection": summary["collection"],
                "label": summary["label"],
                "point_count": summary["point_count"],
                "meta": kinds_meta,
                "preview": summary["preview"],
            }
        )
    collections.sort(key=lambda item: (-int(item["point_count"]), str(item["collection"]).lower()))

    edges = [
        {
            "source": a,
            "target": b,
            "score": round(score, 4),
            "x1": round(positions[a][0], 2),
            "y1": round(positions[a][1], 2),
            "x2": round(positions[b][0], 2),
            "y2": round(positions[b][1], 2),
            "width": round(0.55 + max(0.0, min(1.0, score)) * 1.25, 2),
        }
        for a, b, score in ranked_edges
    ]
    return {
        "has_graph": True,
        "nodes": nodes,
        "edges": edges,
        "width": width,
        "height": height,
        "sample_count": len(nodes),
        "edge_count": len(edges),
        "collection_count": len({item["collection"] for item in prepared}),
        "collections": collections,
    }


def _build_memory_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        kind = str(row.get("type", "")).strip().lower() or "unknown"
        entry = grouped.setdefault(
            kind,
            {
                "type": kind,
                "label": str(row.get("label", kind.upper())),
                "count": 0,
                "rows": [],
            },
        )
        entry["count"] += 1
        entry["rows"].append(row)
    items = list(grouped.values())
    items.sort(key=lambda item: (_memory_group_order(item.get("type", "")), str(item.get("label", ""))))
    return items


def _memory_collection_for_type(settings: Any, user_id: str, memory_type: str) -> str:
    slug = _slug_user_id(user_id)
    normalized = str(memory_type or "").strip().lower()
    if normalized == "preference":
        return f"{settings.memory.collections.preferences.prefix}_{slug}"
    if normalized == "knowledge":
        return f"{settings.memory.collections.knowledge.prefix}_{slug}"
    return f"{settings.memory.collections.facts.prefix}_{slug}"


def _memories_redirect(
    *,
    filter_type: str,
    query: str,
    collection_filter: str,
    document_id: str = "",
    document_name: str = "",
    page: int,
    limit: int,
    sort: str,
    info: str = "",
    error: str = "",
) -> RedirectResponse:
    url = (
        f"/memories/explorer?type={quote_plus(filter_type)}&q={quote_plus(query)}"
        f"&collection_filter={quote_plus(collection_filter)}"
        f"&page={_coerce_page_number(page)}&limit={_coerce_page_size(limit)}&sort={quote_plus(sort)}"
    )
    if str(document_id or "").strip():
        url += f"&document_id={quote_plus(str(document_id).strip())}"
    if str(document_name or "").strip():
        url += f"&document_name={quote_plus(str(document_name).strip())}"
    if info:
        url += f"&info={quote_plus(info)}"
    if error:
        url += f"&error={quote_plus(error)}"
    return RedirectResponse(url=url, status_code=303)


def _memories_map_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    url = "/memories/map"
    params: list[str] = []
    if info:
        params.append(f"info={quote_plus(info)}")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        url += "?" + "&".join(params)
    return RedirectResponse(url=url, status_code=303)


def _memories_overview_redirect(*, info: str = "", error: str = "") -> RedirectResponse:
    url = "/memories"
    params: list[str] = []
    if info:
        params.append(f"info={quote_plus(info)}")
    if error:
        params.append(f"error={quote_plus(error)}")
    if params:
        url += "?" + "&".join(params)
    return RedirectResponse(url=url, status_code=303)


def _memory_export_filename(username: str, filter_type: str, query: str) -> str:
    slug = _slug_user_id(username)
    scope = str(filter_type or "all").strip().lower() or "all"
    if scope not in {"all", "fact", "preference", "session", "knowledge", "document"}:
        scope = "all"
    suffix = "search" if str(query or "").strip() else "all"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"aria-memory-{slug}-{scope}-{suffix}-{stamp}.json"


def _document_collection_prefix() -> str:
    return "aria_docs"


def _default_document_collection_for_user(username: str) -> str:
    slug = _slug_user_id(username)
    prefix = _document_collection_prefix()
    return f"{prefix}_{slug}" if slug else prefix


def _is_document_collection_name(name: str) -> bool:
    clean = str(name or "").strip().lower()
    prefix = _document_collection_prefix()
    return bool(clean) and (clean == prefix or clean.startswith(f"{prefix}_"))


def _normalize_document_collection_name(raw_name: str, sanitize_collection_name: CollectionNameSanitizer) -> str:
    clean = sanitize_collection_name(raw_name)
    if not clean:
        return ""
    if _is_document_collection_name(clean):
        return clean
    return sanitize_collection_name(f"{_document_collection_prefix()}_{clean}")


def _document_collection_names(collection_names: list[str]) -> list[str]:
    rows = [str(name or "").strip() for name in collection_names if _is_document_collection_name(str(name or "").strip())]
    return sorted(set(name for name in rows if name))


def _is_routing_collection_name(name: str) -> bool:
    return is_routing_qdrant_collection(name)


def _is_recipe_experience_collection_name(name: str) -> bool:
    return is_recipe_experience_qdrant_collection(name)


def _is_notes_collection_name(name: str, *, username: str = "") -> bool:
    return is_notes_qdrant_collection(name, username=username)


def _build_notes_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    username: str,
    browse_url: str = "",
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or not _is_notes_collection_name(name, username=username):
            continue
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": "notes",
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": str(browse_url or "").strip() or "/notes",
            }
        )
    items.sort(key=lambda item: (-(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _build_routing_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    known_user_collection_names: set[str] | None = None,
    browse_url: str = "",
) -> list[dict[str, Any]]:
    blocked = {str(name or "").strip() for name in (known_user_collection_names or set()) if str(name or "").strip()}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or name in blocked or not _is_routing_collection_name(name):
            continue
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": "routing",
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": str(browse_url or "").strip(),
            }
        )
    items.sort(key=lambda item: (-(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _build_system_collection_rows(
    overview_rows: list[dict[str, Any]],
    *,
    known_collection_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    blocked = {str(name or "").strip() for name in (known_collection_names or set()) if str(name or "").strip()}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in overview_rows:
        name = str(row.get("name", "")).strip()
        if not name or name in seen or name in blocked:
            continue
        classification = classify_qdrant_collection(name)
        if not classification.is_aria or classification.kind not in {"recipe_experience", "system"}:
            continue
        kind = classification.kind if classification.kind == "recipe_experience" else "system"
        seen.add(name)
        items.append(
            {
                "name": name,
                "kind": kind,
                "points": int(row.get("points", 0) or 0),
                "status": str(row.get("status", "ok")).strip() or "ok",
                "browse_url": "/recipes/learned" if kind == "recipe_experience" else "/memories/config#qdrant-access",
            }
        )
    items.sort(key=lambda item: (str(item.get("kind", "")), -(int(item.get("points", 0) or 0)), str(item.get("name", "")).lower()))
    total_points = int(sum(int(item.get("points", 0) or 0) for item in items))
    max_points = max((int(item.get("points", 0) or 0) for item in items), default=0)
    for item in items:
        points = int(item.get("points", 0) or 0)
        item["share_pct"] = int((points / total_points) * 100) if total_points > 0 else 0
        item["pct"] = int((points / max_points) * 100) if max_points > 0 else 0
    return items


def _resolve_document_target_collection(
    *,
    request: Request,
    username: str,
    selected_collection: str,
    new_collection_name: str,
    existing_collections: list[str],
    sanitize_collection_name: CollectionNameSanitizer,
    get_effective_memory_collection: EffectiveCollectionResolver,
) -> str:
    lang = str(getattr(getattr(request, "state", object()), "lang", "de") or "de")
    existing_document_collections = set(_document_collection_names(existing_collections))

    normalized_new = _normalize_document_collection_name(new_collection_name, sanitize_collection_name)
    if normalized_new:
        return normalized_new

    clean_selected = sanitize_collection_name(selected_collection)
    if clean_selected:
        if not _is_document_collection_name(clean_selected):
            raise ValueError(_memory_routes_text(lang, "error.document_collections_only", "Please use document collections only."))
        if clean_selected not in existing_document_collections:
            raise ValueError(_memory_routes_text(lang, "error.document_collection_missing", "The selected document collection no longer exists."))
        return clean_selected

    active_collection = sanitize_collection_name(get_effective_memory_collection(request, username))
    if active_collection and _is_document_collection_name(active_collection):
        return active_collection

    return _default_document_collection_for_user(username)


def _build_compression_result_message(stats: dict[str, Any], compress_after_days: int, *, lang: str = "de") -> str:
    moved = list(stats.get("compressed_collections", []) or [])
    removed = list(stats.get("removed_collections", []) or [])
    skipped_recent = list(stats.get("skipped_recent", []) or [])
    failed_delete = list(stats.get("failed_delete", []) or [])
    moved_total = int(stats.get("compressed_week", 0) or 0) + int(stats.get("compressed_month", 0) or 0)

    if moved_total <= 0:
        if skipped_recent:
            preview = ", ".join(skipped_recent[:3])
            return _memory_routes_text(
                lang,
                "compression.no_move_recent",
                (
                    "Rollup finished: nothing moved. {count} daily collections are younger than "
                    "{days} days or still active daily context. Examples: {preview}"
                ),
                count=len(skipped_recent),
                days=compress_after_days,
                preview=preview,
            )
        return _memory_routes_text(lang, "compression.no_move", "Rollup finished: nothing to move.")

    parts = [
        _memory_routes_text(
            lang,
            "compression.summary",
            "Rollup finished: moved={moved}, removed={removed}",
            moved=moved_total,
            removed=int(stats.get("collections_removed", 0) or 0),
        ),
    ]
    if moved:
        parts.append(_memory_routes_text(lang, "compression.moved", "Moved: {items}", items=", ".join(moved[:3])))
    if skipped_recent:
        parts.append(
            _memory_routes_text(
                lang,
                "compression.skipped_recent",
                "Unchanged ({count}): younger than {days} days or current daily context",
                count=len(skipped_recent),
                days=compress_after_days,
            )
        )
    if failed_delete:
        parts.append(
            _memory_routes_text(
                lang,
                "compression.failed_delete",
                "Not deleted ({count}): {items}",
                count=len(failed_delete),
                items=", ".join(failed_delete[:3]),
            )
        )
    if removed and len(removed) != len(moved):
        parts.append(_memory_routes_text(lang, "compression.removed", "Removed: {items}", items=", ".join(removed[:3])))
    return " | ".join(parts)


def register_memories_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_settings: SettingsGetter,
    get_pipeline: PipelineGetter,
    get_username_from_request: UsernameResolver,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
    qdrant_overview: QdrantOverviewLoader,
    qdrant_dashboard_url: QdrantDashboardUrlResolver,
    parse_collection_day_suffix: CollectionDayParser,
    sanitize_collection_name: CollectionNameSanitizer,
    default_memory_collection_for_user: DefaultCollectionResolver,
    get_effective_memory_collection: EffectiveCollectionResolver,
    is_auto_memory_enabled: AutoMemoryResolver,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
    resolve_prompt_file: PromptFileResolver,
    get_secure_store: SecureStoreGetter,
    memory_collection_cookie: str,
    auto_memory_cookie: str,
) -> None:
    def _cookie_name_for_request(request: Request, key: str, fallback: str) -> str:
        cookie_names = getattr(request.state, "cookie_names", {}) or {}
        if isinstance(cookie_names, dict):
            candidate = str(cookie_names.get(key, "") or "").strip()
            if candidate:
                return candidate
        return fallback

    @app.get("/memories", response_class=HTMLResponse)
    @app.get("/memories/overview", response_class=HTMLResponse)
    async def memories_overview_page(
        request: Request,
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        legacy_explorer_params = {
            "type",
            "q",
            "collection_filter",
            "document_id",
            "document_name",
            "limit",
            "page",
            "sort",
        }
        if any(key in request.query_params for key in legacy_explorer_params):
            target = "/memories/explorer"
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(url=target, status_code=307)
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        is_admin = _is_admin_request(request, get_auth_session_from_request, sanitize_role)
        overview = await qdrant_overview(request)
        active_collection = get_effective_memory_collection(request, username)
        default_collection = default_memory_collection_for_user(username)
        default_document_collection = _default_document_collection_for_user(username)
        collection_names = [
            str(row.get("name", "")).strip()
            for row in overview.get("collections", [])
            if str(row.get("name", "")).strip()
        ]
        document_collections = _document_collection_names(collection_names)
        collection_stats: list[dict[str, Any]] = []
        if getattr(pipeline, "memory_skill", None):
            with suppress(Exception):
                collection_stats = await pipeline.memory_skill.get_user_collection_stats(username)
        user_memory_points = sum(int(row.get("points", 0) or 0) for row in collection_stats)
        auto_memory_enabled = bool(is_auto_memory_enabled(request))
        map_snapshot = await _build_memory_map_snapshot(
            pipeline=pipeline,
            username=username,
            overview=overview,
            is_admin=is_admin,
            settings=settings,
            parse_collection_day_suffix=parse_collection_day_suffix,
        )
        routing_rows = list(map_snapshot.get("routing_rows", []) or [])
        system_rows = list(map_snapshot.get("system_rows", []) or [])
        overview_checks = [
            {
                "title": "Qdrant",
                "status": "ok" if overview.get("reachable") else "error",
                "summary": "Erreichbar" if overview.get("reachable") else "Nicht erreichbar",
                "meta": f"{len(collection_names)} Collections",
            },
            {
                "title": "Aktive Collection",
                "status": "ok" if active_collection else "warn",
                "summary": active_collection or default_collection,
                "meta": f"Default: {default_collection}",
            },
            {
                "title": "User Memory",
                "status": "ok" if user_memory_points > 0 else "warn",
                "summary": str(user_memory_points),
                "meta": f"{len(collection_stats)} Collections mit Punkten",
            },
            {
                "title": "Dokumente",
                "status": "ok" if document_collections else "warn",
                "summary": default_document_collection,
                "meta": f"{len(document_collections)} Dokument-Collections",
            },
            {
                "title": "System-Collections",
                "status": "ok" if system_rows or routing_rows else "warn",
                "summary": str(len(system_rows) + len(routing_rows)),
                "meta": "Routing, Recipe Experience und weitere ARIA-Collections",
            },
            {
                "title": "Auto-Memory",
                "status": "ok" if auto_memory_enabled else "warn",
                "summary": "Aktiv" if auto_memory_enabled else "Aus",
                "meta": f"Backend: {settings.memory.backend or 'n/a'}",
                "href": "/memories/config#auto-memory",
            },
        ]
        next_steps = [
            {
                "icon": "plus",
                "title": _memory_routes_text(
                    lang,
                    "next_step_memory_title_empty" if user_memory_points <= 0 else "next_step_memory_title_more",
                    "Create first memory" if user_memory_points <= 0 else "Add memory",
                ),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_memory_desc_empty" if user_memory_points <= 0 else "next_step_memory_desc_more",
                    "Start with one small fact or preference so ARIA has something concrete in memory."
                    if user_memory_points <= 0
                    else "Add another fact or preference directly from the hub without jumping into the explorer first.",
                ),
                "href": "/memories#memories-actions",
                "badge": _memory_routes_text(lang, "next_step_memory_badge", "Right here"),
            },
            {
                "icon": "upload",
                "title": _memory_routes_text(
                    lang,
                    "next_step_document_title_empty" if not document_collections else "next_step_document_title_more",
                    "Import first document" if not document_collections else "Import another document",
                ),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_document_desc_empty" if not document_collections else "next_step_document_desc_more",
                    "PDFs, Markdown, and text files land in a document collection and then show up in the explorer and the map."
                    if not document_collections
                    else "Keep using the hub as the intake point for new PDFs or text files without opening setup.",
                ),
                "href": "/memories#memories-actions",
                "badge": default_document_collection,
            },
            {
                "icon": "memories",
                "title": _memory_routes_text(lang, "next_step_explorer_title", "Open explorer"),
                "desc": _memory_routes_text(
                    lang,
                    "next_step_explorer_desc",
                    "Filter facts, documents, rollups, and day context so entries do not blur together later.",
                ),
                "href": "/memories/explorer",
                "badge": _memory_routes_text(lang, "next_step_explorer_badge", "Search & filters"),
            },
        ]
        return templates.TemplateResponse(
            request=request,
            name="memories_overview.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "overview",
                "info_message": info,
                "error_message": error,
                "active_collection": active_collection,
                "default_collection": default_collection,
                "default_document_collection": default_document_collection,
                "auto_memory_enabled": auto_memory_enabled,
                "memory_cfg": settings.memory,
                "qdrant_overview": overview,
                "collection_count": len(collection_names),
                "document_collection_count": len(document_collections),
                "routing_collection_count": len(routing_rows),
                "system_collection_count": len(system_rows),
                "user_memory_points": user_memory_points,
                "overview_checks": overview_checks,
                "next_steps": next_steps,
                "memory_graph": map_snapshot["memory_graph"],
                "show_qdrant_brain": False,
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "document_collections": document_collections,
                "active_document_collection": (
                    active_collection
                    if _is_document_collection_name(active_collection)
                    else default_document_collection
                ),
                "supported_upload_suffixes": supported_upload_suffixes(),
            },
        )

    @app.get("/memories/explorer", response_class=HTMLResponse)
    async def memories_page(
        request: Request,
        type: str = "all",
        q: str = "",
        collection_filter: str = "",
        document_id: str = "",
        document_name: str = "",
        limit: int = 120,
        page: int = 1,
        sort: str = "updated_desc",
        info: str = "",
        error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        overview = await qdrant_overview(request)
        sort_key = _normalize_memory_sort(sort)
        page_size = _coerce_page_size(limit)
        page_number = _coerce_page_number(page)
        selected_collection = sanitize_collection_name(collection_filter)
        selected_document_id = str(document_id or "").strip()
        selected_document_name = str(document_name or "").strip()
        all_rows: list[dict[str, Any]] = []
        collection_stats: list[dict[str, Any]] = []

        if pipeline.memory_skill:
            try:
                if q.strip():
                    all_rows = await pipeline.memory_skill.search_memories(
                        user_id=username,
                        query=q.strip(),
                        type_filter=type,
                        top_k=300,
                    )
                    if selected_collection:
                        all_rows = [
                            row
                            for row in all_rows
                            if str(row.get("collection", "")).strip() == selected_collection
                        ]
                else:
                    all_rows = await pipeline.memory_skill.list_memories_global(
                        user_id=username,
                        type_filter=type,
                        limit=2000 if selected_collection else 600,
                        collection_filter=selected_collection,
                    )
                collection_stats = await pipeline.memory_skill.get_user_collection_stats(username)
            except Exception as exc:  # noqa: BLE001
                error = error or str(exc)

        counts = _build_memory_counts(all_rows)
        learning_review_queue = _build_learning_review_queue(all_rows)
        document_browser_entries: list[dict[str, Any]] = []
        active_document_entry: dict[str, Any] | None = None
        document_store_view = False
        if str(type or "").strip().lower() == "document" and all_rows:
            document_browser_entries = _build_document_entries(all_rows)
            for entry in document_browser_entries:
                entry["browse_url"] = _memory_document_link(
                    collection=str(entry.get("collection", "")).strip(),
                    document_id=str(entry.get("document_id", "")).strip(),
                    document_name=str(entry.get("document_name", "")).strip(),
                )
            if selected_document_id or selected_document_name:
                active_document_entry = next(
                    (
                        entry
                        for entry in document_browser_entries
                        if _document_matches_filter(
                            entry,
                            document_id=selected_document_id,
                            document_name=selected_document_name,
                        )
                    ),
                    None,
                )
                all_rows = [
                    row
                    for row in all_rows
                    if _document_matches_filter(
                        row,
                        document_id=selected_document_id,
                        document_name=selected_document_name,
                    )
                ]
            elif selected_collection and not q.strip():
                document_store_view = True
                all_rows = []

        _sort_memory_rows(all_rows, sort_key)
        total_rows = len(all_rows)
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        if page_number > total_pages:
            page_number = total_pages
        start = (page_number - 1) * page_size
        end = start + page_size
        rows = all_rows[start:end]
        for row in rows:
            row["display_timestamp"] = _format_display_timestamp(row.get("timestamp"))
            row["title"] = _memory_title(str(row.get("text", "")))
            row["preview"] = _memory_preview(str(row.get("text", "")))
            if str(row.get("type", "")).strip().lower() == "learning_candidate":
                gate_inputs = learning_candidate_gate_inputs(row)
                row["candidate_artifact_type"] = gate_inputs["artifact_type"]
                row["candidate_risk"] = gate_inputs["risk"]
                row["app_learning_preview"] = _build_app_learning_preview(str(row.get("text", "")))
                row["is_app_learning_candidate"] = gate_inputs["artifact_type"] in APP_LEARNING_ARTIFACT_TYPES
                row["prepared_artifact_review"] = _build_prepared_artifact_review(
                    pytest_write_state=str(row.get("pytest_write_state", "") or ""),
                    pytest_write_gate_result=str(row.get("pytest_write_gate_result", "") or ""),
                    pytest_target_file=str(row.get("pytest_target_file", "") or ""),
                    pytest_code_preview_sha256=str(row.get("pytest_code_preview_sha256", "") or ""),
                    pytest_write_review_state=str(row.get("pytest_write_review_state", "") or ""),
                    pytest_write_review_decision=str(row.get("pytest_write_review_decision", "") or ""),
                    pytest_write_review_notes=str(row.get("pytest_write_review_notes", "") or ""),
                )
                row["apply_allowed"] = learning_candidate_apply_allowed(
                    artifact_type=gate_inputs["artifact_type"],
                    risk=gate_inputs["risk"],
                    promotion_state=str(row.get("promotion_state", "")).strip(),
                )
                row["apply_preview_allowed"] = learning_candidate_apply_preview_allowed(
                    artifact_type=gate_inputs["artifact_type"],
                    risk=gate_inputs["risk"],
                    apply_state=str(row.get("apply_state", "")).strip(),
                )
        grouped_rows = _build_memory_groups(rows)
        if document_store_view:
            total_rows = len(document_browser_entries)
            total_pages = 1
            page_number = 1
            start = 0
            end = total_rows
            grouped_rows = []
        all_collection_names = [
            str(row.get("name", "")).strip()
            for row in overview.get("collections", [])
            if str(row.get("name", "")).strip()
        ]
        document_collections = _document_collection_names(all_collection_names)
        active_collection = get_effective_memory_collection(request, username)
        active_document_collection = (
            active_collection
            if _is_document_collection_name(active_collection)
            else _default_document_collection_for_user(username)
        )
        learning_worker_status = get_learning_worker_status(limit=5)
        return templates.TemplateResponse(
            request=request,
            name="memories.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "explorer",
                "rows": rows,
                "grouped_rows": grouped_rows,
                "filter_type": type,
                "query": q,
                "collection_filter": selected_collection,
                "document_id_filter": selected_document_id,
                "document_name_filter": selected_document_name,
                "document_browser_entries": document_browser_entries,
                "document_store_view": document_store_view,
                "active_document_entry": active_document_entry,
                "limit": page_size,
                "page": page_number,
                "sort": sort_key,
                "total_rows": total_rows,
                "page_start": (start + 1) if total_rows > 0 else 0,
                "page_end": min(end, total_rows),
                "total_pages": total_pages,
                "prev_page": (page_number - 1) if page_number > 1 else 1,
                "next_page": (page_number + 1) if page_number < total_pages else total_pages,
                "counts": counts,
                "learning_review_queue": learning_review_queue,
                "info_message": info,
                "error_message": error,
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "manual_memory_types": [
                    {"value": "fact", "label": _memory_routes_text(lang, "manual_type.fact", "Fact")},
                    {"value": "preference", "label": _memory_routes_text(lang, "manual_type.preference", "Preference")},
                    {"value": "knowledge", "label": _memory_routes_text(lang, "manual_type.knowledge", "Knowledge")},
                ],
                "collections": all_collection_names,
                "document_collections": document_collections,
                "active_collection": active_collection,
                "active_document_collection": active_document_collection,
                "default_collection": default_memory_collection_for_user(username),
                "default_document_collection": _default_document_collection_for_user(username),
                "supported_upload_suffixes": supported_upload_suffixes(),
                "learning_worker_status": learning_worker_status,
            },
        )

    @app.get("/memories/learning-worker/job/{job_id}")
    async def memories_learning_worker_job(job_id: str) -> JSONResponse:
        job = get_learning_worker_job(job_id)
        if not job:
            return JSONResponse(content={"ok": False, "reason": "job_not_found"}, status_code=404)
        return JSONResponse(content={"ok": True, "job": job})

    @app.post("/memories/learning-worker/retry")
    async def memories_learning_worker_retry(
        request: Request,
        job_id: str = Form(...),
        force: str = Form("1"),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories/explorer?error=learning_worker_admin_required", status_code=303)
        result = retry_learning_job(
            job_id=job_id,
            force=str(force or "").strip().lower() in {"1", "true", "on", "yes"},
        )
        if not result.get("accepted"):
            return RedirectResponse(
                url=f"/memories/explorer?error=learning_worker_retry_{quote_plus(str(result.get('reason', 'failed')))}",
                status_code=303,
            )
        return RedirectResponse(url="/memories/explorer?info=learning_worker_retry_queued", status_code=303)

    @app.post("/memories/learning-worker/flush")
    async def memories_learning_worker_flush(
        request: Request,
        scope: str = Form("finished"),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories/explorer?error=learning_worker_admin_required", status_code=303)
        result = flush_learning_worker_jobs(scope=scope)
        return RedirectResponse(
            url=(
                "/memories/explorer?info="
                f"learning_worker_flushed_{quote_plus(str(result.get('scope', 'finished')))}_"
                f"{int(result.get('removed_count', 0) or 0)}"
            ),
            status_code=303,
        )

    @app.get("/memories/export")
    async def memories_export(
        request: Request,
        type: str = "all",
        q: str = "",
        collection_filter: str = "",
        sort: str = "updated_desc",
    ) -> JSONResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        sort_key = _normalize_memory_sort(sort)
        selected_collection = sanitize_collection_name(collection_filter)
        all_rows: list[dict[str, Any]] = []
        if pipeline.memory_skill:
            if q.strip():
                all_rows = await pipeline.memory_skill.search_memories(
                    user_id=username,
                    query=q.strip(),
                    type_filter=type,
                    top_k=5000,
                )
                if selected_collection:
                    all_rows = [
                        row
                        for row in all_rows
                        if str(row.get("collection", "")).strip() == selected_collection
                    ]
            else:
                all_rows = await pipeline.memory_skill.list_memories_global(
                    user_id=username,
                    type_filter=type,
                    limit=10000,
                    collection_filter=selected_collection,
                )
        _sort_memory_rows(all_rows, sort_key)
        payload = {
            "schema_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "user_id": username,
            "filter": {
                "type": str(type or "all").strip().lower() or "all",
                "query": str(q or "").strip(),
                "sort": sort_key,
            },
            "count": len(all_rows),
            "items": all_rows,
        }
        return JSONResponse(
            content=payload,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{_memory_export_filename(username, type, q)}"'
                )
            },
        )

    @app.get("/memories/map", response_class=HTMLResponse)
    async def memories_map_page(request: Request) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        is_admin = _is_admin_request(request, get_auth_session_from_request, sanitize_role)
        info = str(request.query_params.get("info") or "").strip()
        error = str(request.query_params.get("error") or "").strip()
        overview = await qdrant_overview(request)
        snapshot = await _build_memory_map_snapshot(
            pipeline=pipeline,
            username=username,
            overview=overview,
            is_admin=is_admin,
            settings=settings,
            parse_collection_day_suffix=parse_collection_day_suffix,
        )

        return templates.TemplateResponse(
            request=request,
            name="memories_map.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "map",
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "qdrant_api_key": str(getattr(settings.memory, "qdrant_api_key", "") or ""),
                "qdrant_overview": overview,
                "map_rows": snapshot["user_rows"],
                "map_total_points": snapshot["total_points"],
                "map_kind_totals": snapshot["kind_totals"],
                "notes_rows": snapshot["notes_rows"],
                "notes_total_points": snapshot["notes_total_points"],
                "routing_rows": snapshot["routing_rows"],
                "routing_total_points": snapshot["routing_total_points"],
                "system_rows": snapshot["system_rows"],
                "system_total_points": snapshot["system_total_points"],
                "document_entries": snapshot["document_entries"],
                "document_groups": snapshot["document_groups"],
                "rollup_entries": snapshot["rollup_entries"],
                "rollup_groups": snapshot["rollup_groups"],
                "memory_graph": snapshot["memory_graph"],
                "show_qdrant_brain": True,
                "health": snapshot["health"],
                "cleanup_status": snapshot["cleanup_status"],
                "info_message": info,
                "error_message": error,
            },
        )

    @app.post("/memories/delete")
    async def memories_delete(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        ok = await pipeline.memory_skill.delete_memory_point(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.entry_deleted", "Entry deleted"),
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=document_id,
            document_name=document_name,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.entry_delete_failed", "Entry could not be deleted"),
        )

    @app.post("/memories/delete-document")
    async def memories_delete_document(
        request: Request,
        collection: str = Form(...),
        document_id: str = Form(""),
        document_name: str = Form(""),
        view: str = Form(""),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        selected_document_id: str = Form(""),
        selected_document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        removed = await pipeline.memory_skill.delete_document(
            user_id=username,
            collection=sanitize_collection_name(collection),
            document_id=str(document_id).strip(),
            document_name=str(document_name).strip(),
        )
        target_view = str(view or "").strip().lower()
        if removed > 0:
            if target_view == "map":
                return _memories_map_redirect(info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.document_removed", "Document removed · {count} chunks deleted", count=removed))
            return _memories_redirect(
                filter_type="document" if str(type).strip().lower() in {"all", "document"} else type,
                query=q,
                collection_filter=collection_filter,
                document_id="",
                document_name="",
                page=1,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "info.document_removed", "Document removed · {count} chunks deleted", count=removed),
            )
        if target_view == "map":
            return _memories_map_redirect(error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.document_remove_failed", "Document could not be removed"))
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=selected_document_id,
            document_name=selected_document_name,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.document_remove_failed", "Document could not be removed"),
        )

    @app.post("/memories/edit")
    async def memories_edit(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        text: str = Form(...),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        clean_text = str(text).strip()
        if not clean_text:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.memory_text_empty", "Memory text must not be empty"),
            )
        ok = await pipeline.memory_skill.update_memory_point(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            text=clean_text,
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                info="Eintrag aktualisiert",
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            document_id=document_id,
            document_name=document_name,
            page=page,
            limit=limit,
            sort=sort,
            error="Eintrag konnte nicht aktualisiert werden",
        )

    @app.post("/memories/learning-candidate/status")
    async def memories_learning_candidate_status(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        decision: str = Form(...),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        clean_decision = str(decision or "").strip().lower()
        status = {"review": "reviewed", "reject": "rejected"}.get(clean_decision, "")
        if not status:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.learning_candidate_status_invalid", "Invalid candidate status action"),
            )
        gate_payload = learning_candidate_promotion_gate(
            artifact_type=artifact_type,
            risk=risk,
            decision=clean_decision,
            reviewed_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates={
                "candidate_status": status,
                "review_decision": clean_decision,
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": username,
                **gate_payload,
            },
        )
        if ok:
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                page=page,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(lang, "info.learning_candidate_status_updated", "Learning candidate updated"),
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(lang, "error.learning_candidate_status_failed", "Learning candidate could not be updated"),
        )

    @app.post("/memories/learning-candidate/apply")
    async def memories_learning_candidate_apply(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        promotion_state: str = Form(""),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        apply_payload = prepare_learning_candidate_apply_payload(
            artifact_type=artifact_type,
            risk=risk,
            promotion_state=promotion_state,
            candidate_text=candidate_text,
            applied_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=apply_payload,
        )
        if ok:
            info_key = "info.learning_candidate_apply_prepared" if apply_payload.get("apply_state") == "prepared" else "info.learning_candidate_apply_blocked"
            default = (
                "Learning candidate apply prepared"
                if apply_payload.get("apply_state") == "prepared"
                else "Learning candidate apply blocked"
            )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                page=page,
                limit=limit,
                sort=sort,
                info=_memory_routes_text(lang, info_key, default),
            )
        return _memories_redirect(
            filter_type=type,
            query=q,
            collection_filter=collection_filter,
            page=page,
            limit=limit,
            sort=sort,
            error=_memory_routes_text(lang, "error.learning_candidate_apply_failed", "Learning candidate apply could not be updated"),
        )

    @app.get("/memories/learning-candidate/apply-preview", response_class=HTMLResponse)
    async def memories_learning_candidate_apply_preview(
        request: Request,
        collection: str = "",
        point_id: str = "",
        artifact_type: str = "",
        risk: str = "",
        apply_state: str = "",
        regression_status: str = "",
        regression_ref: str = "",
        regression_verified: str = "",
        regression_verify_result: str = "",
        regression_verify_reason: str = "",
        activation_preflight_state: str = "",
        activation_blockers: str = "",
        pytest_write_state: str = "",
        pytest_write_gate_result: str = "",
        pytest_target_file: str = "",
        pytest_code_preview_sha256: str = "",
        pytest_write_review_state: str = "",
        pytest_write_review_decision: str = "",
        pytest_write_review_notes: str = "",
        candidate_text: str = "",
        type: str = "learning_candidate",
        q: str = "",
        collection_filter: str = "",
        page: int = 1,
        limit: int = 50,
        sort: str = "updated_desc",
    ) -> HTMLResponse:
        settings = get_settings()
        preview = build_learning_candidate_apply_preview(
            artifact_type=artifact_type,
            risk=risk,
            apply_state=apply_state,
            candidate_text=candidate_text,
            collection=collection,
            point_id=point_id,
            regression_status=regression_status,
            regression_ref=regression_ref,
            regression_verified=regression_verified,
            regression_verify_result=regression_verify_result,
            regression_verify_reason=regression_verify_reason,
        )
        activation_preview = build_learning_candidate_activation_preview(
            artifact_type=artifact_type,
            risk=risk,
            candidate_text=candidate_text,
            collection=collection,
            point_id=point_id,
            regression_ref=regression_ref,
            activation_preflight_state=activation_preflight_state,
            activation_blockers=activation_blockers,
            user_id=get_username_from_request(request) or "web",
        )
        app_learning_preview = _build_app_learning_preview(candidate_text)
        prepared_artifact_review = _build_prepared_artifact_review(
            pytest_write_state=pytest_write_state,
            pytest_write_gate_result=pytest_write_gate_result,
            pytest_target_file=pytest_target_file,
            pytest_code_preview_sha256=pytest_code_preview_sha256,
            pytest_write_review_state=pytest_write_review_state,
            pytest_write_review_decision=pytest_write_review_decision,
            pytest_write_review_notes=pytest_write_review_notes,
        )
        return templates.TemplateResponse(
            request=request,
            name="memories_learning_candidate_apply_preview.html",
            context={
                "title": settings.ui.title,
                "username": get_username_from_request(request) or "web",
                "memory_nav": "explorer",
                "preview": preview,
                "activation_preview": activation_preview,
                "app_learning_preview": app_learning_preview,
                "prepared_artifact_review": prepared_artifact_review,
                "return_url": (
                    f"/memories/explorer?type={quote_plus(type)}&q={quote_plus(q)}"
                    f"&collection_filter={quote_plus(collection_filter)}&page={max(1, int(page))}"
                    f"&limit={max(10, min(int(limit), 100))}&sort={quote_plus(sort)}"
                ),
            },
        )

    @app.post("/memories/learning-candidate/regression")
    async def memories_learning_candidate_regression_link(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        regression_ref: str = Form(""),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        apply_state: str = Form("prepared"),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        payload = link_learning_candidate_regression_payload(
            regression_ref=regression_ref,
            linked_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        clean_ref = str(payload.get("regression_ref", "") or "").strip()
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(str(payload.get('regression_status', '') or 'missing'))}"
            f"&regression_ref={quote_plus(clean_ref)}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=regression_update_failed", status_code=303)
        return RedirectResponse(url=preview_url, status_code=303)

    @app.post("/memories/learning-candidate/pytest/prepare-write")
    async def memories_learning_candidate_pytest_prepare_write(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        apply_state: str = Form("prepared"),
        regression_status: str = Form(""),
        regression_ref: str = Form(""),
        regression_verified: str = Form(""),
        regression_verify_result: str = Form(""),
        regression_verify_reason: str = Form(""),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        app_learning_preview = _build_app_learning_preview(candidate_text)
        payload = prepare_pytest_write_payload(
            app_learning_preview.get("pytest_apply_preview") or {},
            prepared_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(regression_status)}"
            f"&regression_ref={quote_plus(regression_ref)}"
            f"&regression_verified={quote_plus(regression_verified)}"
            f"&regression_verify_result={quote_plus(regression_verify_result)}"
            f"&regression_verify_reason={quote_plus(regression_verify_reason)}"
            f"&pytest_write_state={quote_plus(str(payload.get('pytest_write_state', '') or ''))}"
            f"&pytest_write_gate_result={quote_plus(str(payload.get('pytest_write_gate_result', '') or ''))}"
            f"&pytest_target_file={quote_plus(str(payload.get('pytest_target_file', '') or ''))}"
            f"&pytest_code_preview_sha256={quote_plus(str(payload.get('pytest_code_preview_sha256', '') or ''))}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=pytest_write_prepare_failed", status_code=303)
        return RedirectResponse(
            url=f"{preview_url}&info=pytest_write_{quote_plus(str(payload.get('pytest_write_state', 'blocked')))}",
            status_code=303,
        )

    @app.post("/memories/learning-candidate/artifact/review")
    async def memories_learning_candidate_artifact_review(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        artifact_kind: str = Form("pytest_skeleton_write"),
        decision: str = Form(...),
        review_notes: str = Form(""),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        apply_state: str = Form("prepared"),
        regression_status: str = Form(""),
        regression_ref: str = Form(""),
        regression_verified: str = Form(""),
        regression_verify_result: str = Form(""),
        regression_verify_reason: str = Form(""),
        pytest_write_state: str = Form(""),
        pytest_write_gate_result: str = Form(""),
        pytest_target_file: str = Form(""),
        pytest_code_preview_sha256: str = Form(""),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        payload = prepare_prepared_artifact_review_payload(
            artifact_kind=artifact_kind,
            decision=decision,
            review_notes=review_notes,
            reviewed_by=username,
            prepared_state=pytest_write_state,
            code_preview_sha256=pytest_code_preview_sha256,
            target_file=pytest_target_file,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        review_state = str(payload.get("pytest_write_review_state", "") or "")
        review_decision = str(payload.get("pytest_write_review_decision", "") or "")
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(regression_status)}"
            f"&regression_ref={quote_plus(regression_ref)}"
            f"&regression_verified={quote_plus(regression_verified)}"
            f"&regression_verify_result={quote_plus(regression_verify_result)}"
            f"&regression_verify_reason={quote_plus(regression_verify_reason)}"
            f"&pytest_write_state={quote_plus(pytest_write_state)}"
            f"&pytest_write_gate_result={quote_plus(pytest_write_gate_result)}"
            f"&pytest_target_file={quote_plus(pytest_target_file)}"
            f"&pytest_code_preview_sha256={quote_plus(pytest_code_preview_sha256)}"
            f"&pytest_write_review_state={quote_plus(review_state)}"
            f"&pytest_write_review_decision={quote_plus(review_decision)}"
            f"&pytest_write_review_notes={quote_plus(str(payload.get('pytest_write_review_notes', '') or ''))}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=artifact_review_failed", status_code=303)
        await capture_prepared_artifact_review_learning(
            user_id=username,
            memory_skill=pipeline.memory_skill,
            candidate_collection=sanitize_collection_name(collection),
            candidate_point_id=str(point_id).strip(),
            candidate_text=candidate_text,
            artifact_kind=artifact_kind,
            review_payload=payload,
        )
        return RedirectResponse(url=f"{preview_url}&info=artifact_review_{quote_plus(review_state)}", status_code=303)

    @app.post("/memories/learning-candidate/regression/verify")
    async def memories_learning_candidate_regression_verify(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        regression_ref: str = Form(""),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        apply_state: str = Form("prepared"),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        payload = verify_learning_candidate_regression_payload(
            regression_ref=regression_ref,
            repo_root=BASE_DIR,
            verified_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        clean_ref = str(payload.get("regression_ref", "") or "").strip()
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(str(payload.get('regression_status', '') or 'missing'))}"
            f"&regression_ref={quote_plus(clean_ref)}"
            f"&regression_verified={quote_plus(str(payload.get('regression_verified', False)).lower())}"
            f"&regression_verify_result={quote_plus(str(payload.get('regression_verify_result', '') or ''))}"
            f"&regression_verify_reason={quote_plus(str(payload.get('regression_verify_reason', '') or ''))}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=regression_verify_failed", status_code=303)
        return RedirectResponse(url=preview_url, status_code=303)

    @app.post("/memories/learning-candidate/regression/run")
    async def memories_learning_candidate_regression_run(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        regression_ref: str = Form(""),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        apply_state: str = Form("prepared"),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        payload = run_learning_candidate_regression_payload(
            regression_ref=regression_ref,
            repo_root=BASE_DIR,
            run_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        clean_ref = str(payload.get("regression_ref", "") or "").strip()
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(str(payload.get('regression_status', '') or 'missing'))}"
            f"&regression_ref={quote_plus(clean_ref)}"
            f"&regression_verified={quote_plus(str(payload.get('regression_verified', False)).lower())}"
            f"&regression_verify_result={quote_plus(str(payload.get('regression_verify_result', '') or ''))}"
            f"&regression_verify_reason={quote_plus(str(payload.get('regression_verify_reason', '') or ''))}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=regression_run_failed", status_code=303)
        return RedirectResponse(url=preview_url, status_code=303)

    @app.post("/memories/learning-candidate/activation-preflight")
    async def memories_learning_candidate_activation_preflight(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        promotion_state: str = Form("eligible"),
        apply_state: str = Form("prepared"),
        regression_status: str = Form("linked"),
        regression_ref: str = Form(""),
        regression_verified: str = Form(""),
        regression_verify_result: str = Form(""),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        payload = learning_candidate_activation_preflight_payload(
            artifact_type=artifact_type,
            risk=risk,
            promotion_state=promotion_state,
            apply_state=apply_state,
            regression_status=regression_status,
            regression_verified=regression_verified,
            regression_verify_result=regression_verify_result,
            checked_by=username,
        )
        ok = await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates=payload,
        )
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state={quote_plus(apply_state)}"
            f"&regression_status={quote_plus(regression_status)}"
            f"&regression_ref={quote_plus(regression_ref)}"
            f"&regression_verified={quote_plus(str(regression_verified).lower())}"
            f"&regression_verify_result={quote_plus(str(regression_verify_result or ''))}"
            f"&activation_preflight_state={quote_plus(str(payload.get('activation_preflight_state', '') or ''))}"
            f"&activation_blockers={quote_plus(','.join(payload.get('activation_blockers', []) or []))}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not ok:
            return RedirectResponse(url=f"{preview_url}&error=activation_preflight_failed", status_code=303)
        return RedirectResponse(url=preview_url, status_code=303)

    @app.post("/memories/learning-candidate/activate")
    async def memories_learning_candidate_activate(
        request: Request,
        collection: str = Form(...),
        point_id: str = Form(...),
        artifact_type: str = Form(""),
        risk: str = Form(""),
        regression_ref: str = Form(""),
        activation_preflight_state: str = Form(""),
        activation_blockers: str = Form(""),
        candidate_text: str = Form(""),
        type: str = Form("learning_candidate"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        activation_preview = build_learning_candidate_activation_preview(
            artifact_type=artifact_type,
            risk=risk,
            candidate_text=candidate_text,
            collection=collection,
            point_id=str(point_id).strip(),
            regression_ref=regression_ref,
            activation_preflight_state=activation_preflight_state,
            activation_blockers=activation_blockers,
            user_id=username,
        )
        preview_url = (
            f"/memories/learning-candidate/apply-preview?collection={quote_plus(collection)}"
            f"&point_id={quote_plus(str(point_id).strip())}"
            f"&artifact_type={quote_plus(artifact_type)}&risk={quote_plus(risk)}"
            f"&apply_state=prepared&regression_status=linked"
            f"&regression_ref={quote_plus(regression_ref)}"
            f"&regression_verified=true&regression_verify_result=passed"
            f"&activation_preflight_state={quote_plus(activation_preflight_state)}"
            f"&activation_blockers={quote_plus(activation_blockers)}"
            f"&candidate_text={quote_plus(candidate_text)}"
            f"&type={quote_plus(type)}&q={quote_plus(q)}"
            f"&collection_filter={quote_plus(collection_filter)}"
            f"&page={max(1, int(page))}&limit={max(10, min(int(limit), 100))}"
            f"&sort={quote_plus(sort)}"
        )
        if not activation_preview.get("activation_allowed"):
            return RedirectResponse(url=f"{preview_url}&error=activation_blocked", status_code=303)
        store_result = await pipeline.memory_skill.execute(
            query=str(activation_preview.get("summary", "") or ""),
            params=learning_active_hint_store_params(preview=activation_preview, user_id=username),
        )
        if not store_result.success:
            return RedirectResponse(url=f"{preview_url}&error=active_hint_store_failed", status_code=303)
        await pipeline.memory_skill.update_memory_point_payload(
            user_id=username,
            collection=sanitize_collection_name(collection),
            point_id=str(point_id).strip(),
            payload_updates={
                "activation_state": "active_hint_stored",
                "active_hint_collection": str(activation_preview.get("active_hint_collection", "") or ""),
                "active_hint_type": str(activation_preview.get("active_hint_type", "") or ""),
                "active_hint_stored_at": datetime.now().isoformat(),
                "active_hint_stored_by": username,
                "activation_runtime_effect": str(activation_preview.get("runtime_activation", "") or ""),
                "runtime_activation_allowed": False,
            },
        )
        return RedirectResponse(url=f"{preview_url}&info=active_hint_stored", status_code=303)

    @app.post("/memories/create")
    async def memories_create(
        request: Request,
        memory_type: str = Form("fact"),
        text: str = Form(...),
        source_view: str = Form("explorer"),
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        page: int = Form(1),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            if str(source_view or "").strip().lower() == "overview":
                return _memories_overview_redirect(error="Memory+nicht+aktiv")
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)

        clean_type = str(memory_type or "fact").strip().lower()
        if clean_type not in {"fact", "preference", "knowledge"}:
            clean_type = "fact"
        clean_text = str(text or "").strip()
        if not clean_text:
            if str(source_view or "").strip().lower() == "overview":
                return _memories_overview_redirect(error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.memory_text_empty", "Memory text must not be empty"))
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.memory_text_empty", "Memory text must not be empty"),
            )
        if len(clean_text) > 4000:
            clean_text = clean_text[:4000]

        try:
            result = await pipeline.memory_skill.execute(
                query=clean_text,
                params={
                    "action": "store",
                    "user_id": username,
                    "collection": _memory_collection_for_type(settings, username, clean_type),
                    "memory_type": clean_type,
                    "text": clean_text,
                    "source": "manual_ui",
                },
            )
            if result.success:
                if str(source_view or "").strip().lower() == "overview":
                    return _memories_overview_redirect(info=result.content or "Memory gespeichert")
                return _memories_redirect(
                    filter_type=type,
                    query=q,
                    collection_filter=collection_filter,
                    document_id=document_id,
                    document_name=document_name,
                    page=1,
                    limit=limit,
                    sort=sort,
                    info=result.content or "Memory gespeichert",
                )
            if str(source_view or "").strip().lower() == "overview":
                return _memories_overview_redirect(
                    error=result.error or result.content or "Memory konnte nicht gespeichert werden"
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=result.error or result.content or "Memory konnte nicht gespeichert werden",
            )
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            if str(source_view or "").strip().lower() == "overview":
                return _memories_overview_redirect(
                    error=_friendly_memory_error(
                        lang,
                        exc,
                        "Memory konnte nicht gespeichert werden.",
                        "Could not save memory.",
                    )
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_friendly_memory_error(lang, exc, "Memory konnte nicht gespeichert werden.", "Could not save memory."),
            )

    @app.post("/memories/upload")
    async def memories_upload(request: Request) -> RedirectResponse:
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        lang = str(getattr(request.state, "lang", "de") or "de")
        try:
            form = await request.form()
        except Exception:
            return _memories_redirect(
                filter_type="all",
                query="",
                collection_filter="",
                page=1,
                limit=50,
                sort="updated_desc",
                error=_msg(
                    lang,
                    "Upload-Formular konnte nicht gelesen werden. Bitte Seite neu laden und erneut versuchen.",
                    "Could not read the upload form. Please reload the page and try again.",
                ),
            )

        collection = str(form.get("collection", "") or "")
        new_collection_name = str(form.get("new_collection_name", "") or "")
        type = str(form.get("type", "all") or "all")
        q = str(form.get("q", "") or "")
        collection_filter = str(form.get("collection_filter", "") or "")
        document_id = str(form.get("document_id", "") or "")
        document_name = str(form.get("document_name", "") or "")
        source_view = str(form.get("source_view", "explorer") or "explorer").strip().lower()
        page = _coerce_form_int(form.get("page"), 1)
        limit = _coerce_form_int(form.get("limit"), 50)
        sort = _normalize_memory_sort(str(form.get("sort", "updated_desc") or "updated_desc"))
        csrf_token = str(form.get("csrf_token", "") or "")
        document_file = form.get("document_file") or form.get("file")

        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            if source_view == "overview":
                return _memories_overview_redirect(
                    error=_memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.csrf_failed", "Security check failed. Please reload the page."),
            )
        if not pipeline.memory_skill:
            if source_view == "overview":
                return _memories_overview_redirect(
                    error=_memory_routes_text(lang, "error.memory_backend_unavailable", "Memory backend is currently unavailable.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.memory_backend_unavailable", "Memory backend is currently unavailable."),
            )
        if not _is_uploaded_file(document_file):
            if source_view == "overview":
                return _memories_overview_redirect(error=_memory_routes_text(lang, "error.choose_file", "Please choose a file."))
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_memory_routes_text(lang, "error.choose_file", "Please choose a file."),
            )

        try:
            overview = await qdrant_overview(request)
            existing_collection_names = [
                str(row.get("name", "")).strip()
                for row in overview.get("collections", [])
                if str(row.get("name", "")).strip()
            ]
            raw = await document_file.read()
            prepared = prepare_uploaded_document(
                filename=document_file.filename or "",
                data=raw,
                content_type=getattr(document_file, "content_type", "") or "",
            )
            target_collection = _resolve_document_target_collection(
                request=request,
                username=username,
                selected_collection=collection,
                new_collection_name=new_collection_name,
                existing_collections=existing_collection_names,
                sanitize_collection_name=sanitize_collection_name,
                get_effective_memory_collection=get_effective_memory_collection,
            )
            result = await pipeline.memory_skill.store_document(
                user_id=username,
                document=prepared,
                base_collection=target_collection,
            )
            if not result.success:
                raise ValueError(result.error or _msg(lang, "Dokument konnte nicht importiert werden.", "Could not import document."))
            chunk_count = int((result.metadata or {}).get("chunk_count", 0) or 0)
            if source_view == "overview":
                return _memories_overview_redirect(
                    info=_msg(
                        lang,
                        f"Dokument importiert: {prepared.filename} · {chunk_count} Chunks in {target_collection}",
                        f"Document imported: {prepared.filename} · {chunk_count} chunks into {target_collection}",
                    )
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id="",
                document_name="",
                page=1,
                limit=limit,
                sort=sort,
                info=_msg(
                    lang,
                    f"Dokument importiert: {prepared.filename} · {chunk_count} Chunks in {target_collection}",
                    f"Document imported: {prepared.filename} · {chunk_count} chunks into {target_collection}",
                ),
            )
        except (DocumentIngestError, ValueError) as exc:
            if source_view == "overview":
                return _memories_overview_redirect(
                    error=str(exc).strip() or _memory_routes_text(lang, "error.document_import_failed", "Could not import document.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=str(exc).strip() or _memory_routes_text(lang, "error.document_import_failed", "Could not import document."),
            )
        except Exception as exc:  # noqa: BLE001
            if source_view == "overview":
                return _memories_overview_redirect(
                    error=_friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.document_import_failed_short", "Document import failed."), "Document import failed.")
                )
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=page,
                limit=limit,
                sort=sort,
                error=_friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.document_import_failed_short", "Document import failed."), "Document import failed."),
            )

    @app.post("/memories/maintenance")
    async def memories_maintenance(
        request: Request,
        type: str = Form("all"),
        q: str = Form(""),
        collection_filter: str = Form(""),
        document_id: str = Form(""),
        document_name: str = Form(""),
        limit: int = Form(50),
        sort: str = Form("updated_desc"),
    ) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request) or "web"
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/explorer?error=Memory+nicht+aktiv", status_code=303)
        try:
            session_cfg = settings.memory.collections.sessions
            result = await pipeline.memory_skill.execute(
                query="",
                params={
                    "action": "compress_sessions",
                    "user_id": username,
                    "compress_after_days": int(getattr(session_cfg, "compress_after_days", 7)),
                    "monthly_after_days": int(getattr(session_cfg, "monthly_after_days", 30)),
                },
            )
            if result.success:
                return _memories_redirect(
                    filter_type=type,
                    query=q,
                    collection_filter=collection_filter,
                    document_id=document_id,
                    document_name=document_name,
                    page=1,
                    limit=limit,
                    sort=sort,
                    info=result.content,
                )
            message = result.error or _memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.compression_failed", "Compression failed")
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=1,
                limit=limit,
                sort=sort,
                error=message,
            )
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierung konnte nicht gestartet werden.", "Could not start compression.")
            return _memories_redirect(
                filter_type=type,
                query=q,
                collection_filter=collection_filter,
                document_id=document_id,
                document_name=document_name,
                page=1,
                limit=limit,
                sort=sort,
                error=error,
            )

    @app.get("/memories/config", response_class=HTMLResponse)
    @app.get("/config/memory", response_class=HTMLResponse)
    async def config_memory_page(
        request: Request,
        saved: int = 0,
        error: str = "",
        compress_result: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        username = get_username_from_request(request) or "web"
        overview = await qdrant_overview(request)
        return templates.TemplateResponse(
            request=request,
            name="config_memory.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "memory_nav": "setup",
                "saved": bool(saved),
                "error_message": error,
                "collections": [row["name"] for row in overview.get("collections", [])],
                "default_collection": default_memory_collection_for_user(username),
                "active_collection": get_effective_memory_collection(request, username),
                "auto_memory": settings.auto_memory,
                "memory_cfg": settings.memory,
                "auto_memory_cookie": is_auto_memory_enabled(request),
                "qdrant_overview": overview,
                "has_qdrant_api_key": bool(getattr(settings.memory, "qdrant_api_key", "")),
                "qdrant_api_key_value": str(getattr(settings.memory, "qdrant_api_key", "") or ""),
                "qdrant_dashboard_url": qdrant_dashboard_url(request),
                "compress_result": compress_result,
            },
        )

    @app.post("/memories/config/backend-save")
    @app.post("/config/memory/backend-save")
    async def config_memory_backend_save(
        request: Request,
        backend: str = Form("qdrant"),
        qdrant_url: str = Form(""),
        qdrant_api_key: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        try:
            clean_backend = str(backend or "").strip().lower() or "qdrant"
            if clean_backend != "qdrant":
                raise ValueError(_memory_routes_text(str(getattr(request.state, "lang", "de") or "de"), "error.only_qdrant_supported", "Only Qdrant is currently supported as memory backend."))
            clean_url = str(qdrant_url or "").strip().rstrip("/")
            if not clean_url:
                raise ValueError("Qdrant URL darf nicht leer sein.")

            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            # Keep the memory backend active whenever this Qdrant setup is saved from the UI.
            raw["memory"]["enabled"] = True
            raw["memory"]["backend"] = clean_backend
            raw["memory"]["qdrant_url"] = clean_url
            raw["memory"]["qdrant_api_key"] = ""

            secure_store = get_secure_store(raw)
            clean_api_key = str(qdrant_api_key or "").strip()
            if secure_store:
                if clean_api_key:
                    secure_store.set_secret("memory.qdrant_api_key", clean_api_key)
                else:
                    stored_key = secure_store.get_secret("memory.qdrant_api_key", "")
                    if not stored_key:
                        secure_store.delete_secret("memory.qdrant_api_key")
            else:
                raw["memory"]["qdrant_api_key"] = clean_api_key

            write_raw_config(raw)
            reload_runtime()
            return RedirectResponse(url="/memories/config?saved=1", status_code=303)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Memory-Backend konnte nicht gespeichert werden.", "Could not save memory backend.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}", status_code=303)

    @app.post("/memories/config/select")
    @app.post("/config/memory/select")
    async def config_memory_select(request: Request, collection: str = Form("")) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        clean = sanitize_collection_name(collection)
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
        if clean:
            response.set_cookie(
                key=_cookie_name_for_request(request, "memory_collection", memory_collection_cookie),
                value=clean,
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
        else:
            response.delete_cookie(_cookie_name_for_request(request, "memory_collection", memory_collection_cookie))
        return response

    @app.post("/memories/config/create")
    @app.post("/config/memory/create")
    async def config_memory_create(request: Request, collection_name: str = Form(...)) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        clean = sanitize_collection_name(collection_name)
        if not clean:
            return RedirectResponse(url=f"/memories/config?error={quote_plus(_memory_routes_text(str(getattr(request.state, 'lang', 'de') or 'de'), 'error.invalid_collection_name', 'Invalid collection name'))}", status_code=303)
        secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
        response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
        response.set_cookie(
            key=_cookie_name_for_request(request, "memory_collection", memory_collection_cookie),
            value=clean,
            max_age=60 * 60 * 24 * 365,
            samesite="lax",
            secure=secure_cookie,
            httponly=False,
        )
        return response

    @app.post("/memories/config/auto-save")
    @app.post("/config/memory/auto-save")
    async def config_memory_auto_save(
        request: Request,
        enabled: str = Form("0"),
        session_recall_top_k: int = Form(...),
        user_recall_top_k: int = Form(...),
        max_facts_per_message: int = Form(...),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        try:
            if session_recall_top_k <= 0:
                raise ValueError("session_recall_top_k muss > 0 sein.")
            if user_recall_top_k <= 0:
                raise ValueError("user_recall_top_k muss > 0 sein.")
            if max_facts_per_message <= 0:
                raise ValueError("max_facts_per_message muss > 0 sein.")

            raw = read_raw_config()
            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            auto_memory_active = str(enabled).strip().lower() in {"1", "true", "on", "yes"}
            raw["auto_memory"]["enabled"] = auto_memory_active
            raw["auto_memory"]["agentic_extraction_enabled"] = auto_memory_active
            raw["auto_memory"]["session_recall_top_k"] = int(session_recall_top_k)
            raw["auto_memory"]["user_recall_top_k"] = int(user_recall_top_k)
            raw["auto_memory"]["max_facts_per_message"] = int(max_facts_per_message)
            write_raw_config(raw)
            reload_runtime()

            secure_cookie = cookie_should_be_secure(request, public_url=str(settings.aria.public_url or ""))
            response = RedirectResponse(url="/memories/config?saved=1", status_code=303)
            response.set_cookie(
                key=_cookie_name_for_request(request, "auto_memory", auto_memory_cookie),
                value="1" if raw["auto_memory"]["enabled"] else "0",
                max_age=60 * 60 * 24 * 365,
                samesite="lax",
                secure=secure_cookie,
                httponly=False,
            )
            return response
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Auto-Memory konnte nicht gespeichert werden.", "Could not save auto-memory settings.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}", status_code=303)

    @app.post("/memories/config/compress")
    @app.post("/config/memory/compress")
    async def config_memory_compress(request: Request) -> RedirectResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        username = get_username_from_request(request)
        if not username:
            return RedirectResponse(url="/memories/config?error=Bitte+zuerst+Benutzernamen+setzen#rollup", status_code=303)
        if not pipeline.memory_skill:
            return RedirectResponse(url="/memories/config?error=Memory+nicht+aktiv#rollup", status_code=303)
        try:
            session_cfg = settings.memory.collections.sessions
            compress_after_days = int(session_cfg.compress_after_days or 7)
            monthly_after_days = int(session_cfg.monthly_after_days or 30)
            stats = await pipeline.memory_skill.compress_old_sessions(
                user_id=username,
                compress_after_days=compress_after_days,
                monthly_after_days=monthly_after_days,
            )
            await pipeline.token_tracker.log(
                request_id=str(uuid4()),
                user_id=username,
                intents=["memory_compress"],
                router_level=0,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                chat_model=settings.llm.model,
                embedding_model=settings.embeddings.model,
                embedding_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0},
                chat_cost_usd=None,
                embedding_cost_usd=None,
                total_cost_usd=None,
                duration_ms=0,
                source="system",
                skill_errors=[],
                extraction_model="compression",
                extraction_usage={
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "calls": int(stats.get("compressed_week", 0)) + int(stats.get("compressed_month", 0)),
                },
            )
            message = _build_compression_result_message(stats, compress_after_days, lang=str(getattr(request.state, "lang", "de") or "de"))
            return RedirectResponse(url=f"/memories/config?compress_result={quote_plus(message)}#rollup", status_code=303)
        except Exception as exc:  # noqa: BLE001
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, _memory_routes_text(lang, "error.memory_compression_failed", "Memory compression failed."), "Memory compression failed.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}#rollup", status_code=303)

    @app.post("/memories/config/compression-save")
    @app.post("/config/memory/compression-save")
    async def config_memory_compression_save(
        request: Request,
        compression_summary_prompt: str = Form(""),
        compress_after_days: int = Form(...),
        monthly_after_days: int = Form(...),
    ) -> RedirectResponse:
        if not _is_admin_request(request, get_auth_session_from_request, sanitize_role):
            return RedirectResponse(url="/memories?error=no_admin", status_code=303)
        try:
            if compress_after_days < 1:
                raise ValueError("compress_after_days muss >= 1 sein.")
            if monthly_after_days < compress_after_days:
                raise ValueError("monthly_after_days muss >= compress_after_days sein.")

            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            clean_path = str(compression_summary_prompt).strip().replace("\\", "/")
            if clean_path:
                target = resolve_prompt_file(clean_path)
                if not target.exists():
                    raise ValueError("Prompt-Datei existiert nicht.")
                raw["memory"]["compression_summary_prompt"] = clean_path
            raw["memory"].setdefault("collections", {})
            if not isinstance(raw["memory"]["collections"], dict):
                raw["memory"]["collections"] = {}
            raw["memory"]["collections"].setdefault("sessions", {})
            if not isinstance(raw["memory"]["collections"]["sessions"], dict):
                raw["memory"]["collections"]["sessions"] = {}
            raw["memory"]["collections"]["sessions"]["compress_after_days"] = int(compress_after_days)
            raw["memory"]["collections"]["sessions"]["monthly_after_days"] = int(monthly_after_days)
            write_raw_config(raw)
            reload_runtime()
            return RedirectResponse(url="/memories/config?saved=1#rollup", status_code=303)
        except (OSError, ValueError) as exc:
            lang = str(getattr(request.state, "lang", "de") or "de")
            error = _friendly_memory_error(lang, exc, "Komprimierungs-Einstellungen konnten nicht gespeichert werden.", "Could not save compression settings.")
            return RedirectResponse(url=f"/memories/config?error={quote_plus(error)}#rollup", status_code=303)
