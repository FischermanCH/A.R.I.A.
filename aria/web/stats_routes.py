from __future__ import annotations

import asyncio
import inspect
import json
import os
import sqlite3
import time
import tomllib
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import yaml

from aria.core.config import ChatPricingModelConfig
from aria.core.config import EmbeddingPricingModelConfig
from aria.core.connection_catalog import (
    connection_chat_emoji,
    connection_edit_page,
    connection_icon_name,
    connection_is_alpha,
    connection_kind_label,
    connection_ref_query_param,
    normalize_connection_kind,
)
from aria.core.connection_runtime import build_settings_connection_status_rows
from aria.core.config import get_master_key
from aria.core.pipeline import Pipeline
from aria.core.pricing_catalog import build_pricing_catalog_snapshot
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.runtime_endpoint import resolve_runtime_url
from aria.web.activities_routes import _decorate_activity_rows


PricingResolver = Callable[[dict[str, Any], str], Any | None]
UsernameResolver = Callable[[Request], str]
SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Pipeline]
PreflightGetter = Callable[[], Any]


def _size_human(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_path(base_dir: Path) -> Path:
    return base_dir / "config" / "config.yaml"


def _build_release_meta(base_dir: Path) -> dict[str, str]:
    version = "0.1.0"
    try:
        pyproject = base_dir / "pyproject.toml"
        payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = payload.get("project", {})
        if isinstance(project, dict):
            version = str(project.get("version", version) or version).strip() or version
    except Exception:
        pass

    release_label = str(os.getenv("ARIA_RELEASE_LABEL", "") or "").strip()
    if not release_label:
        release_label = f"{version}-alpha26"
    return {
        "version": version,
        "label": release_label,
    }


def _stats_connections_cache_path(base_dir: Path) -> Path:
    path = base_dir / "data" / "runtime" / "stats_connections_cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _clear_runtime_stats_cache(base_dir: Path) -> None:
    for cache_name in ("stats_connections_cache.json",):
        try:
            (base_dir / "data" / "runtime" / cache_name).unlink(missing_ok=True)
        except OSError:
            pass


def _load_cached_stats_connections(base_dir: Path, *, ttl_seconds: int = 20, language: str = "de") -> list[dict[str, Any]] | None:
    path = _stats_connections_cache_path(base_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    cached_language = str(payload.get("language", "")).strip().lower() or "de"
    if cached_language != str(language or "de").strip().lower():
        return None
    generated_at = float(payload.get("generated_at", 0.0) or 0.0)
    if generated_at <= 0 or (time.time() - generated_at) > ttl_seconds:
        return None
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else None


def _save_cached_stats_connections(base_dir: Path, rows: list[dict[str, Any]], *, language: str = "de") -> None:
    path = _stats_connections_cache_path(base_dir)
    payload = {
        "generated_at": time.time(),
        "language": str(language or "de").strip().lower() or "de",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_runtime_path(base_dir: Path, value: str) -> Path:
    path = Path(str(value or "").strip())
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _overall_status(services: list[dict[str, str]]) -> str:
    statuses = [str(row.get("status", "ok")).strip().lower() for row in services]
    if "error" in statuses:
        return "error"
    if "warn" in statuses:
        return "warn"
    return "ok"


def _pick_text(language: str, de_text: str, en_text: str) -> str:
    return de_text if str(language or "de").strip().lower().startswith("de") else en_text


def _read_meminfo_kb() -> dict[str, int]:
    data: dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if ":" not in line:
                    continue
                key, raw = line.split(":", 1)
                parts = raw.strip().split()
                if not parts:
                    continue
                try:
                    data[key.strip()] = int(parts[0])
                except ValueError:
                    continue
    except OSError:
        return {}
    return data


def _current_process_rss_bytes() -> int:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.startswith("VmRSS:"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1]) * 1024
    except OSError:
        return 0
    return 0


def _build_runtime_memory_meta(language: str) -> dict[str, Any]:
    rss_bytes = _current_process_rss_bytes()
    meminfo = _read_meminfo_kb()
    total_bytes = int(meminfo.get("MemTotal", 0) or 0) * 1024
    percent = (rss_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
    percent = max(0.0, min(percent, 100.0))
    if percent >= 12.0:
        status = "error"
    elif percent >= 6.0:
        status = "warn"
    else:
        status = "ok"
    return {
        "rss_bytes": rss_bytes,
        "rss_human": _size_human(rss_bytes),
        "total_bytes": total_bytes,
        "total_human": _size_human(total_bytes) if total_bytes > 0 else "-",
        "percent": percent,
        "percent_label": f"{percent:.1f}%",
        "status": status,
    }


def _directory_size_bytes(path: Path) -> int:
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for name in files:
                file_path = Path(root) / name
                try:
                    stat = file_path.stat()
                    allocated_bytes = int(getattr(stat, "st_blocks", 0) or 0) * 512
                    total += allocated_bytes if allocated_bytes > 0 else int(stat.st_size)
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sum_local_shard_disk_bytes(local_shard: Any) -> int:
    segments = getattr(local_shard, "segments", None) or []
    segment_total = 0
    for segment in segments:
        info = getattr(segment, "info", None)
        if info is None:
            continue
        segment_total += _safe_int(getattr(info, "disk_usage_bytes", 0))
    if segment_total > 0:
        return segment_total

    return _safe_int(getattr(local_shard, "vectors_size_bytes", 0)) + _safe_int(
        getattr(local_shard, "payloads_size_bytes", 0)
    )


def _extract_qdrant_telemetry_disk_bytes(telemetry: Any) -> tuple[int, int]:
    result = getattr(telemetry, "result", telemetry)
    collections_meta = getattr(result, "collections", None)
    if collections_meta is None:
        return 0, 0

    collection_items = getattr(collections_meta, "collections", None) or []
    collection_count = _safe_int(getattr(collections_meta, "number_of_collections", 0)) or len(collection_items)
    total_bytes = 0
    for collection in collection_items:
        shards = getattr(collection, "shards", None) or []
        for shard in shards:
            local_shard = getattr(shard, "local", None)
            if local_shard is None:
                continue
            total_bytes += _sum_local_shard_disk_bytes(local_shard)
    return total_bytes, collection_count


async def _build_qdrant_storage_meta(base_dir: Path, settings: Any) -> dict[str, Any]:
    if not bool(getattr(settings.memory, "enabled", False)) or str(getattr(settings.memory, "backend", "")).strip().lower() != "qdrant":
        return {"size_human": "-", "path": "", "available": False}

    qdrant_url = str(getattr(settings.memory, "qdrant_url", "") or "").strip()
    parsed = urlparse(qdrant_url)
    host = str(parsed.hostname or "").strip().lower()
    qdrant_api_key = str(getattr(settings.memory, "qdrant_api_key", "") or "").strip() or None
    telemetry_fallback_meta: dict[str, Any] | None = None

    client = None
    try:
        client = create_async_qdrant_client(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=4.0,
        )
        telemetry_result = await client._client.openapi_client.service_api.telemetry(details_level=1, timeout=4)
        total_bytes, collection_count = _extract_qdrant_telemetry_disk_bytes(telemetry_result)
        if total_bytes > 0:
            return {
                "size_human": _size_human(total_bytes),
                "path": f"Telemetry · {collection_count} Collections",
                "available": True,
            }
        if collection_count > 0:
            telemetry_fallback_meta = {
                "size_human": _size_human(total_bytes),
                "path": f"Telemetry · {collection_count} Collections",
                "available": True,
            }
    except Exception:
        pass
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass

    shared_qdrant_mount = Path("/qdrant/storage")
    candidate_paths = [shared_qdrant_mount]

    if host in {"", "localhost", "127.0.0.1", "host.docker.internal"}:
        candidate_paths.extend(
            [
                base_dir / "data" / "qdrant",
                base_dir / "qdrant" / "storage",
                Path("/var/lib/qdrant/storage"),
                Path("/var/lib/qdrant"),
                Path("/root/.local/share/qdrant/storage"),
            ]
        )

    for path in candidate_paths:
        try:
            if not path.exists() or not path.is_dir():
                continue
        except OSError:
            continue
        size_bytes = _directory_size_bytes(path)
        if size_bytes <= 0 and telemetry_fallback_meta is not None:
            continue
        return {
            "size_human": _size_human(size_bytes),
            "path": str(path),
            "available": True,
        }

    if telemetry_fallback_meta is not None:
        return telemetry_fallback_meta

    if host not in {"", "localhost", "127.0.0.1", "host.docker.internal"}:
        return {"size_human": "-", "path": "", "available": False}

    return {"size_human": "-", "path": "", "available": False}


def _collapse_rss_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rss_rows = [row for row in rows if str(row.get("kind", "")).strip() == "RSS"]
    if not rss_rows:
        return rows

    total = len(rss_rows)
    healthy = sum(1 for row in rss_rows if row.get("status") == "ok")
    issues = sum(1 for row in rss_rows if row.get("status") == "error")
    status = "error" if issues else "ok"
    rss_card = {
        "kind_key": "rss",
        "kind": connection_kind_label("rss"),
        "kind_icon": connection_icon_name("rss"),
        "kind_alpha": connection_is_alpha("rss"),
        "ref": connection_kind_label("rss"),
        "target": f"{total} konfigurierte Feeds",
        "status": status,
        "message": f"{healthy} grün · {issues} rot",
        "last_success_at": "",
        "edit_url": connection_edit_page("rss"),
        "chat_icon": connection_chat_emoji("rss"),
    }

    collapsed: list[dict[str, str]] = []
    inserted = False
    for row in rows:
        if str(row.get("kind", "")).strip() == "RSS":
            if not inserted:
                collapsed.append(rss_card)
                inserted = True
            continue
        collapsed.append(row)
    if not inserted:
        collapsed.append(rss_card)
    return collapsed


def _connection_edit_url(row: dict[str, Any]) -> str:
    kind = normalize_connection_kind(str(row.get("kind", "")).strip().replace(" ", "_"))
    ref = str(row.get("ref", "")).strip()
    route = connection_edit_page(kind)
    param = connection_ref_query_param(kind)
    if kind == "rss" and ref == "RSS":
        return route
    if not route:
        return ""
    if not ref or not param:
        return route
    return f"{route}?{param}={quote_plus(ref)}"


def _attach_connection_edit_urls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["edit_url"] = _connection_edit_url(payload)
        enriched.append(payload)
    return enriched


def _build_pricing_meta(stats: dict[str, Any], settings: Any, resolve_pricing_entry: PricingResolver) -> dict[str, Any]:
    chat_seen = [model for model in stats.get("chat_tokens_by_model", {}).keys() if str(model).strip()]
    embedding_seen = [model for model in stats.get("embedding_tokens_by_model", {}).keys() if str(model).strip()]

    priced_chat_models = sorted(getattr(settings.pricing, "chat_models", {}).keys())
    priced_embedding_models = sorted(getattr(settings.pricing, "embedding_models", {}).keys())

    unpriced_chat_models = sorted(
        model for model in chat_seen if resolve_pricing_entry(getattr(settings.pricing, "chat_models", {}), model) is None
    )
    unpriced_embedding_models = sorted(
        model
        for model in embedding_seen
        if resolve_pricing_entry(getattr(settings.pricing, "embedding_models", {}), model) is None
    )

    source_rows: list[dict[str, str]] = []
    for model in sorted(priced_chat_models):
        entry = resolve_pricing_entry(getattr(settings.pricing, "chat_models", {}), model)
        if entry is None:
            continue
        source_rows.append(
            {
                "kind": "Chat",
                "model": model,
                "rate": f"in {float(getattr(entry, 'input_per_million', 0.0) or 0.0):.4f} / out {float(getattr(entry, 'output_per_million', 0.0) or 0.0):.4f} USD / 1M",
                "verified_at": str(getattr(entry, "verified_at", "") or "").strip() or "-",
                "source_name": str(getattr(entry, "source_name", "") or "").strip() or "-",
                "source_url": str(getattr(entry, "source_url", "") or "").strip(),
            }
        )
    for model in sorted(priced_embedding_models):
        entry = resolve_pricing_entry(getattr(settings.pricing, "embedding_models", {}), model)
        if entry is None:
            continue
        source_rows.append(
            {
                "kind": "Embedding",
                "model": model,
                "rate": f"in {float(getattr(entry, 'input_per_million', 0.0) or 0.0):.4f} USD / 1M",
                "verified_at": str(getattr(entry, "verified_at", "") or "").strip() or "-",
                "source_name": str(getattr(entry, "source_name", "") or "").strip() or "-",
                "source_url": str(getattr(entry, "source_url", "") or "").strip(),
            }
        )

    return {
        "last_updated": str(getattr(settings.pricing, "last_updated", "") or "").strip() or "-",
        "currency": str(getattr(settings.pricing, "currency", "USD") or "USD").strip() or "USD",
        "enabled": bool(getattr(settings.pricing, "enabled", False)),
        "default_source_name": str(getattr(settings.pricing, "default_source_name", "") or "").strip() or "-",
        "default_source_url": str(getattr(settings.pricing, "default_source_url", "") or "").strip(),
        "priced_chat_models": priced_chat_models,
        "priced_embedding_models": priced_embedding_models,
        "priced_chat_count": len(priced_chat_models),
        "priced_embedding_count": len(priced_embedding_models),
        "chat_seen_count": len(chat_seen),
        "embedding_seen_count": len(embedding_seen),
        "unpriced_chat_models": unpriced_chat_models,
        "unpriced_embedding_models": unpriced_embedding_models,
        "source_rows": source_rows,
    }


def _read_raw_config(base_dir: Path) -> dict[str, Any]:
    path = _config_path(base_dir)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return payload if isinstance(payload, dict) else {}


def _write_raw_config(base_dir: Path, payload: dict[str, Any]) -> None:
    path = _config_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


async def _refresh_pricing_snapshot(settings: Any, base_dir: Path) -> dict[str, Any]:
    snapshot = await build_pricing_catalog_snapshot(include_openrouter=True)
    raw = _read_raw_config(base_dir)
    pricing_section = raw.get("pricing")
    if not isinstance(pricing_section, dict):
        pricing_section = {}
    pricing_section.update(
        {
            "enabled": True,
            "currency": "USD",
            "last_updated": snapshot.get("last_updated", ""),
            "default_source_name": snapshot.get("default_source_name", ""),
            "default_source_url": snapshot.get("default_source_url", ""),
            "chat_models": snapshot.get("chat_models", {}),
            "embedding_models": snapshot.get("embedding_models", {}),
        }
    )
    raw["pricing"] = pricing_section
    _write_raw_config(base_dir, raw)

    settings.pricing.enabled = True
    settings.pricing.currency = "USD"
    settings.pricing.last_updated = str(snapshot.get("last_updated", "") or "").strip()
    settings.pricing.default_source_name = str(snapshot.get("default_source_name", "") or "").strip()
    settings.pricing.default_source_url = str(snapshot.get("default_source_url", "") or "").strip()
    settings.pricing.chat_models = {
        str(model): ChatPricingModelConfig.model_validate(entry)
        for model, entry in dict(snapshot.get("chat_models", {}) or {}).items()
        if isinstance(entry, dict)
    }
    settings.pricing.embedding_models = {
        str(model): EmbeddingPricingModelConfig.model_validate(entry)
        for model, entry in dict(snapshot.get("embedding_models", {}) or {}).items()
        if isinstance(entry, dict)
    }
    return snapshot


def _build_preflight_meta(payload: dict[str, Any], language: str) -> dict[str, Any]:
    labels = {
        "prompts": _pick_text(language, "Prompt-Dateien", "Prompt files"),
        "qdrant": _pick_text(language, "Memory / Qdrant", "Memory / Qdrant"),
        "llm": _pick_text(language, "Chat LLM", "Chat LLM"),
        "embeddings": _pick_text(language, "Embeddings", "Embeddings"),
    }
    summary_labels = {
        "prompts_ok": lambda row: _pick_text(
            language,
            f"Prompt-Dateien ok ({int(row.get('skill_prompt_count', 0) or 0)} Skill-Prompts).",
            f"Prompt files ok ({int(row.get('skill_prompt_count', 0) or 0)} skill prompts).",
        ),
        "prompts_incomplete": lambda row: _pick_text(language, "Prompt-Dateien unvollständig.", "Prompt files incomplete."),
        "qdrant_disabled": lambda row: _pick_text(language, "Memory deaktiviert.", "Memory disabled."),
        "qdrant_backend_inactive": lambda row: _pick_text(language, "Qdrant nicht als Backend aktiv.", "Qdrant not active as backend."),
        "qdrant_ok": lambda row: _pick_text(
            language,
            f"Qdrant erreichbar ({int(row.get('collection_count', 0) or 0)} Collections).",
            f"Qdrant reachable ({int(row.get('collection_count', 0) or 0)} collections).",
        ),
        "qdrant_error": lambda row: _pick_text(language, "Qdrant nicht erreichbar.", "Qdrant unavailable."),
        "llm_ok": lambda row: _pick_text(language, "LLM erreichbar.", "LLM reachable."),
        "llm_empty": lambda row: _pick_text(language, "LLM antwortet leer.", "LLM responded empty."),
        "llm_error": lambda row: _pick_text(language, "LLM nicht erreichbar.", "LLM unavailable."),
        "embeddings_missing_model": lambda row: _pick_text(language, "Embedding-Modell fehlt.", "Embedding model missing."),
        "embeddings_ok": lambda row: _pick_text(language, "Embeddings erreichbar.", "Embeddings reachable."),
        "embeddings_empty_vector": lambda row: _pick_text(language, "Embeddings antworten ohne Vektor.", "Embeddings responded without vector."),
        "embeddings_error": lambda row: _pick_text(language, "Embeddings nicht erreichbar.", "Embeddings unavailable."),
    }
    checks: list[dict[str, Any]] = []
    for row in list(payload.get("checks", []) or []):
        check_id = str(row.get("id", "")).strip()
        status = str(row.get("status", "warn")).strip().lower() or "warn"
        summary_key = str(row.get("summary_key", "")).strip()
        summary = str(row.get("summary", "")).strip()
        if summary_key in summary_labels:
            summary = str(summary_labels[summary_key](row)).strip()
        checks.append(
            {
                "id": check_id,
                "name": labels.get(check_id, check_id or "-"),
                "status": status,
                "visual_status": "warn" if status == "skipped" else status,
                "summary": summary,
                "detail": str(row.get("detail", "")).strip(),
            }
        )
    overall = str(payload.get("status", "warn")).strip().lower() or "warn"
    return {
        "overall_status": overall,
        "checked_at": str(payload.get("checked_at", "")).strip(),
        "checks": checks,
        "issue_checks": [row for row in checks if row["status"] not in {"ok"}],
        "ok_count": sum(1 for row in checks if row["status"] == "ok"),
        "warn_count": sum(1 for row in checks if row["status"] == "warn"),
        "error_count": sum(1 for row in checks if row["status"] == "error"),
        "skipped_count": sum(1 for row in checks if row["status"] == "skipped"),
    }


async def _build_health_meta(settings: Any, pipeline: Pipeline, language: str, request: Request | None = None) -> dict[str, Any]:
    base_dir = _project_root()
    services: list[dict[str, str]] = []
    runtime_url = resolve_runtime_url(settings, request)

    services.append(
        {
            "name": "ARIA Runtime",
            "status": "ok",
            "summary": _pick_text(
                language,
                f"Web-App erreichbar unter {runtime_url}.",
                f"Web app reachable at {runtime_url}.",
            ),
            "detail": f"log_level={settings.aria.log_level}",
        }
    )

    llm_model = str(getattr(settings.llm, "model", "") or "").strip() or "-"
    embed_model = str(getattr(settings.embeddings, "model", "") or "").strip() or "-"
    llm_base = str(getattr(settings.llm, "api_base", "") or "").strip()
    embed_base = str(getattr(settings.embeddings, "api_base", "") or "").strip()
    model_status = "ok" if llm_base or embed_base else "warn"
    services.append(
        {
            "name": "Model Stack",
            "status": model_status,
            "summary": _pick_text(
                language,
                f"Chat: {llm_model} · Embeddings: {embed_model}",
                f"Chat: {llm_model} · Embeddings: {embed_model}",
            ),
            "detail": _pick_text(
                language,
                f"LLM API: {llm_base or '-'} · Embeddings API: {embed_base or '-'}",
                f"LLM API: {llm_base or '-'} · Embeddings API: {embed_base or '-'}",
            ),
        }
    )

    memory_status = "warn"
    memory_summary = _pick_text(language, "Memory ist deaktiviert.", "Memory is disabled.")
    memory_detail = f"backend={settings.memory.backend}"
    if bool(getattr(settings.memory, "enabled", True)):
        qdrant_url = str(getattr(settings.memory, "qdrant_url", "") or "").strip()
        try:
            client = create_async_qdrant_client(
                url=qdrant_url,
                api_key=(getattr(settings.memory, "qdrant_api_key", "") or None),
                timeout=4.0,
            )
            result = client.get_collections()
            if inspect.isawaitable(result):
                result = await result
            collections = getattr(result, "collections", []) or []
            memory_status = "ok"
            memory_summary = _pick_text(
                language,
                f"Qdrant erreichbar ({len(collections)} Collections).",
                f"Qdrant reachable ({len(collections)} collections).",
            )
            memory_detail = qdrant_url or "-"
        except Exception as exc:  # noqa: BLE001
            memory_status = "error"
            memory_summary = _pick_text(language, "Qdrant/Memories nicht erreichbar.", "Qdrant/memory unavailable.")
            memory_detail = str(exc)
    services.append(
        {
            "name": "Memory / Qdrant",
            "status": memory_status,
            "summary": memory_summary,
            "detail": memory_detail,
        }
    )

    security_db = _resolve_runtime_path(base_dir, getattr(settings.security, "db_path", ""))
    try:
        master_key = get_master_key()
    except Exception:
        master_key = ""
    security_status = "ok" if not bool(getattr(settings.security, "enabled", True)) or (security_db.exists() and master_key) else "warn"
    services.append(
        {
            "name": "Security Store",
            "status": security_status,
            "summary": _pick_text(
                language,
                "Security Store aktiv." if bool(getattr(settings.security, "enabled", True)) else "Security ist deaktiviert.",
                "Security store active." if bool(getattr(settings.security, "enabled", True)) else "Security is disabled.",
            ),
            "detail": f"db={security_db} · master_key={'ok' if master_key else 'missing'}",
        }
    )

    log_path = _resolve_runtime_path(base_dir, getattr(settings.token_tracking, "log_file", "data/logs/tokens.jsonl"))
    log_exists = log_path.exists()
    log_size = _size_human(log_path.stat().st_size) if log_exists else "0 B"
    log_status = "ok" if bool(getattr(settings.token_tracking, "enabled", True)) and log_exists else "warn"
    services.append(
        {
            "name": "Activities / Logs",
            "status": log_status,
            "summary": _pick_text(
                language,
                "Run-/Token-Logs verfügbar." if log_exists else "Noch keine Run-/Token-Logs vorhanden.",
                "Run/token logs available." if log_exists else "No run/token logs yet.",
            ),
            "detail": f"{log_path} · {log_size}",
        }
    )

    overall_status = _overall_status(services)
    for service in services:
        service["visual_status"] = str(service.get("status", "warn")).strip().lower() or "warn"
    return {
        "services": services,
        "overall_status": overall_status,
        "ok_count": sum(1 for row in services if row["status"] == "ok"),
        "warn_count": sum(1 for row in services if row["status"] == "warn"),
        "error_count": sum(1 for row in services if row["status"] == "error"),
    }


def register_stats_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_pipeline: PipelineGetter,
    get_settings: SettingsGetter,
    get_username_from_request: UsernameResolver,
    resolve_pricing_entry: PricingResolver,
    get_runtime_preflight: PreflightGetter,
) -> None:
    @app.post("/stats/pricing/refresh")
    async def stats_pricing_refresh(request: Request) -> RedirectResponse:
        can_access_advanced = bool(
            getattr(getattr(request, "state", object()), "can_access_advanced_config", False)
        )
        if can_access_advanced:
            settings = get_settings()
            await _refresh_pricing_snapshot(settings, _project_root())
        return RedirectResponse("/stats", status_code=303)

    @app.post("/stats/reset")
    async def stats_reset(request: Request, confirm_text: str = Form("")) -> RedirectResponse:
        can_access_advanced = bool(
            getattr(getattr(request, "state", object()), "can_access_advanced_config", False)
        )
        if not can_access_advanced:
            return RedirectResponse("/stats", status_code=303)

        language = str(getattr(getattr(request, "state", object()), "lang", "") or "de")
        if str(confirm_text or "").strip().upper() != "RESET":
            error = _pick_text(
                language,
                'Bitte zur Bestätigung genau "RESET" eingeben.',
                'Please type "RESET" exactly to confirm.',
            )
            return RedirectResponse(f"/stats?reset_error={quote_plus(error)}", status_code=303)

        pipeline = get_pipeline()
        removed = await pipeline.token_tracker.clear_log()
        _clear_runtime_stats_cache(_project_root())
        return RedirectResponse(
            f"/stats?reset_done={int(removed.get('removed', 0) or 0)}",
            status_code=303,
        )

    @app.get('/stats', response_class=HTMLResponse)
    async def stats_page(
        request: Request,
        reset_done: int | None = None,
        reset_error: str = "",
    ) -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        base_dir = _project_root()
        stats = await pipeline.token_tracker.get_stats(days=7)
        username = get_username_from_request(request)
        pricing_meta = _build_pricing_meta(stats, settings, resolve_pricing_entry)
        language = str(getattr(getattr(request, "state", object()), "lang", "") or settings.ui.language or "de")
        health_meta = await _build_health_meta(settings, pipeline, language, request)
        preflight_payload = get_runtime_preflight() or {}
        if inspect.isawaitable(preflight_payload):
            preflight_payload = await preflight_payload
        preflight_meta = _build_preflight_meta(preflight_payload if isinstance(preflight_payload, dict) else {}, language)
        runtime_memory = _build_runtime_memory_meta(language)
        qdrant_storage = await _build_qdrant_storage_meta(base_dir, settings)
        release_meta = _build_release_meta(base_dir)
        activity_data = await pipeline.token_tracker.get_recent_activities(
            user_id=username,
            limit=18,
            kind="all",
            status="all",
        )
        activity_rows = activity_data.get("rows", [])
        if not isinstance(activity_rows, list):
            activity_rows = []
        activity_data["rows"] = _decorate_activity_rows(activity_rows)
        connection_status_rows = _load_cached_stats_connections(base_dir, language=language)
        if connection_status_rows is None:
            connection_status_rows = build_settings_connection_status_rows(
                settings,
                page_probe=True,
                base_dir=base_dir,
                lang=language,
            )
            connection_status_rows = _collapse_rss_rows(connection_status_rows)
            connection_status_rows = _attach_connection_edit_urls(connection_status_rows)
            _save_cached_stats_connections(base_dir, connection_status_rows, language=language)
        else:
            connection_status_rows = _attach_connection_edit_urls(connection_status_rows)
        return templates.TemplateResponse(
            request=request,
            name='stats.html',
            context={
                'title': settings.ui.title,
                'stats': stats,
                'username': username,
                'pricing_meta': pricing_meta,
                'health_meta': health_meta,
                'preflight_meta': preflight_meta,
                'runtime_memory': runtime_memory,
                'qdrant_storage': qdrant_storage,
                'release_meta': release_meta,
                'activities': activity_data,
                'connection_status_rows': connection_status_rows,
                'reset_done': reset_done,
                'reset_error': reset_error,
            },
        )
