from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
import inspect
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus
from urllib.parse import urlparse

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
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
from aria.core.i18n import I18NStore
from aria.core.pipeline import Pipeline
from aria.core.pricing_catalog import build_pricing_catalog_snapshot
from aria.core.pricing_catalog import resolve_pricing_entry as resolve_catalog_pricing_entry
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.qdrant_collection_classifier import is_recipe_experience_qdrant_collection
from aria.core.qdrant_storage_diagnostics import build_qdrant_storage_warning
from aria.core.qdrant_storage_diagnostics import list_local_qdrant_collection_names
from aria.core.qdrant_storage_diagnostics import resolve_qdrant_storage_path
from aria.core.release_meta import read_release_meta
from aria.core.recipe_experience_promotion import promote_recipe_experience_to_learned_review
from aria.core.routing_admin import build_connection_routing_index_status
from aria.core.runtime_endpoint import resolve_runtime_url
from aria.core.update_helper_client import fetch_update_helper_status
from aria.core.update_helper_client import helper_status_visual
from aria.core.update_helper_client import resolve_update_helper_config
from aria.web.activities_routes import _decorate_activity_rows


PricingResolver = Callable[[dict[str, Any], str], Any | None]
UsernameResolver = Callable[[Request], str]
SettingsGetter = Callable[[], Any]
PipelineGetter = Callable[[], Pipeline]
PreflightGetter = Callable[[], Any]
SecureStoreGetter = Callable[[], Any]
_STATS_ROUTES_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _stats_route_text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _STATS_ROUTES_I18N.t(language or "de", f"stats_routes.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


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


def _load_active_runtime_profiles(base_dir: Path) -> dict[str, str]:
    path = _config_path(base_dir)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(payload, dict):
        return {}
    profiles = payload.get("profiles", {})
    if not isinstance(profiles, dict):
        return {}
    active = profiles.get("active", {})
    if not isinstance(active, dict):
        return {}
    result: dict[str, str] = {}
    for kind in ("llm", "embeddings"):
        value = str(active.get(kind, "") or "").strip()
        if value:
            result[kind] = value
    return result


def _build_release_meta(base_dir: Path) -> dict[str, str]:
    return read_release_meta(base_dir)


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

    storage_path = resolve_qdrant_storage_path(base_dir, qdrant_url)
    if storage_path is not None:
        size_bytes = _directory_size_bytes(storage_path)
        if size_bytes <= 0 and telemetry_fallback_meta is not None:
            return telemetry_fallback_meta
        return {
            "size_human": _size_human(size_bytes),
            "path": str(storage_path),
            "available": True,
        }

    if telemetry_fallback_meta is not None:
        return telemetry_fallback_meta

    if host not in {"", "localhost", "127.0.0.1", "host.docker.internal"}:
        return {"size_human": "-", "path": "", "available": False}

    return {"size_human": "-", "path": "", "available": False}


def _collapse_rss_rows(rows: list[dict[str, str]], *, language: str = "de") -> list[dict[str, str]]:
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
        "target": _stats_route_text(language, "configured_feeds", "{total} configured feeds", total=total),
        "status": status,
        "message": _stats_route_text(language, "connection_summary", "{healthy} ok · {issues} error", healthy=healthy, issues=issues),
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


def _collapse_connection_kind_rows(
    rows: list[dict[str, Any]],
    *,
    kind_key: str,
    threshold: int,
    language: str = "de",
) -> list[dict[str, Any]]:
    normalized_kind = normalize_connection_kind(kind_key)
    matching_rows = [row for row in rows if normalize_connection_kind(str(row.get("kind_key", "") or row.get("kind", ""))) == normalized_kind]
    if len(matching_rows) < max(1, int(threshold or 0)):
        return rows

    total = len(matching_rows)
    healthy = sum(1 for row in matching_rows if str(row.get("status", "")).strip().lower() == "ok")
    issues = sum(1 for row in matching_rows if str(row.get("status", "")).strip().lower() == "error")
    warns = sum(1 for row in matching_rows if str(row.get("status", "")).strip().lower() == "warn")
    status = "error" if issues else ("warn" if warns else "ok")
    kind_label = connection_kind_label(normalized_kind)
    item_label = (
        _stats_route_text(language, "feeds_label", "feeds")
        if normalized_kind == "rss"
        else _stats_route_text(language, "profile_item_label", "{kind_label} profiles", kind_label=kind_label)
    )
    target = _stats_route_text(
        language,
        "configured_profiles",
        "{total} configured {item_label}",
        total=total,
        item_label=item_label,
    )
    parts = [_stats_route_text(language, "healthy_count", "{count} ok", count=healthy)]
    if warns:
        parts.append(f"{warns} warn")
    parts.append(_stats_route_text(language, "issue_count", "{count} error", count=issues))
    summary_card = {
        "kind_key": normalized_kind,
        "kind": kind_label,
        "kind_icon": connection_icon_name(normalized_kind),
        "kind_alpha": connection_is_alpha(normalized_kind),
        "ref": kind_label,
        "display_name": kind_label,
        "title": kind_label,
        "target": target,
        "status": status,
        "message": " · ".join(parts),
        "last_success_at": "",
        "edit_url": connection_edit_page(normalized_kind),
        "chat_icon": connection_chat_emoji(normalized_kind),
        "grouped_refs": [str(row.get("ref", "")).strip() for row in matching_rows if str(row.get("ref", "")).strip()],
    }

    collapsed: list[dict[str, Any]] = []
    inserted = False
    for row in rows:
        row_kind = normalize_connection_kind(str(row.get("kind_key", "") or row.get("kind", "")))
        if row_kind == normalized_kind:
            if not inserted:
                collapsed.append(summary_card)
                inserted = True
            continue
        collapsed.append(row)
    if not inserted:
        collapsed.append(summary_card)
    return collapsed


def _collapse_large_connection_groups(
    rows: list[dict[str, Any]],
    *,
    threshold: int,
    language: str = "de",
) -> list[dict[str, Any]]:
    collapsed_rows = list(rows)
    seen_kinds: set[str] = set()
    for row in rows:
        normalized_kind = normalize_connection_kind(str(row.get("kind_key", "") or row.get("kind", "")))
        if not normalized_kind or normalized_kind in seen_kinds:
            continue
        seen_kinds.add(normalized_kind)
        collapsed_rows = _collapse_connection_kind_rows(
            collapsed_rows,
            kind_key=normalized_kind,
            threshold=threshold,
            language=language,
        )
    return collapsed_rows


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


def _resolve_stats_pricing_entry(
    catalog: dict[str, Any],
    model: str,
    resolve_pricing_entry: PricingResolver,
    model_aliases: dict[str, str] | None = None,
) -> Any | None:
    clean = str(model or "").strip()
    if not clean:
        return None
    try:
        entry = resolve_pricing_entry(catalog, clean)
    except Exception:
        entry = None
    if entry is not None:
        return entry
    return resolve_catalog_pricing_entry(catalog, clean, model_aliases=model_aliases)


def _estimate_chat_cost_usd(entry: Any | None, prompt_tokens: int, completion_tokens: int) -> float | None:
    if entry is None:
        return None
    return (
        (int(prompt_tokens or 0) * float(getattr(entry, "input_per_million", 0.0) or 0.0))
        + (int(completion_tokens or 0) * float(getattr(entry, "output_per_million", 0.0) or 0.0))
    ) / 1_000_000


def _estimate_embedding_cost_usd(entry: Any | None, input_tokens: int) -> float | None:
    if entry is None:
        return None
    return (int(input_tokens or 0) * float(getattr(entry, "input_per_million", 0.0) or 0.0)) / 1_000_000


def _build_pricing_meta(stats: dict[str, Any], settings: Any, resolve_pricing_entry: PricingResolver) -> dict[str, Any]:
    chat_seen = [model for model in stats.get("chat_tokens_by_model", {}).keys() if str(model).strip()]
    embedding_seen = [model for model in stats.get("embedding_tokens_by_model", {}).keys() if str(model).strip()]
    chat_tokens_by_model = dict(stats.get("chat_tokens_by_model", {}) or {})
    chat_prompt_tokens_by_model = dict(stats.get("chat_prompt_tokens_by_model", {}) or {})
    chat_completion_tokens_by_model = dict(stats.get("chat_completion_tokens_by_model", {}) or {})
    embedding_tokens_by_model = dict(stats.get("embedding_tokens_by_model", {}) or {})
    embedding_prompt_tokens_by_model = dict(stats.get("embedding_prompt_tokens_by_model", {}) or {})
    chat_cost_by_model = dict(stats.get("chat_cost_usd_by_model", {}) or {})
    embedding_cost_by_model = dict(stats.get("embedding_cost_usd_by_model", {}) or {})

    priced_chat_models = sorted(getattr(settings.pricing, "chat_models", {}).keys())
    priced_embedding_models = sorted(getattr(settings.pricing, "embedding_models", {}).keys())

    def _has_logged_numeric_cost(cost_rows: dict[str, Any], model: str) -> bool:
        return isinstance(cost_rows.get(model), (int, float))

    def _is_priced_chat_model(model: str) -> bool:
        return (
            _resolve_stats_pricing_entry(getattr(settings.pricing, "chat_models", {}), model, resolve_pricing_entry, getattr(settings.pricing, "model_aliases", {}))
            is not None
            or _has_logged_numeric_cost(chat_cost_by_model, model)
        )

    def _is_priced_embedding_model(model: str) -> bool:
        return (
            _resolve_stats_pricing_entry(getattr(settings.pricing, "embedding_models", {}), model, resolve_pricing_entry, getattr(settings.pricing, "model_aliases", {}))
            is not None
            or _has_logged_numeric_cost(embedding_cost_by_model, model)
        )

    unpriced_chat_models = sorted(
        model for model in chat_seen if not _is_priced_chat_model(model)
    )
    unpriced_embedding_models = sorted(
        model for model in embedding_seen if not _is_priced_embedding_model(model)
    )
    priced_seen_chat_models = sorted(model for model in chat_seen if model not in unpriced_chat_models)
    priced_seen_embedding_models = sorted(model for model in embedding_seen if model not in unpriced_embedding_models)
    unpriced_chat_tokens = sum(int(chat_tokens_by_model.get(model, 0) or 0) for model in unpriced_chat_models)
    unpriced_embedding_tokens = sum(int(embedding_tokens_by_model.get(model, 0) or 0) for model in unpriced_embedding_models)
    unpriced_model_tokens = unpriced_chat_tokens + unpriced_embedding_tokens
    unpriced_model_rows = [
        {
            "kind": "Chat",
            "model": model,
            "tokens": int(chat_tokens_by_model.get(model, 0) or 0),
        }
        for model in unpriced_chat_models
    ] + [
        {
            "kind": "Embedding",
            "model": model,
            "tokens": int(embedding_tokens_by_model.get(model, 0) or 0),
        }
        for model in unpriced_embedding_models
    ]

    estimated_chat_cost_by_model: dict[str, float] = {}
    estimated_embedding_cost_by_model: dict[str, float] = {}
    for model in priced_seen_chat_models:
        entry = _resolve_stats_pricing_entry(getattr(settings.pricing, "chat_models", {}), model, resolve_pricing_entry, getattr(settings.pricing, "model_aliases", {}))
        prompt_tokens = int(chat_prompt_tokens_by_model.get(model, 0) or 0)
        completion_tokens = int(chat_completion_tokens_by_model.get(model, 0) or 0)
        if prompt_tokens <= 0 and completion_tokens <= 0:
            prompt_tokens = int(chat_tokens_by_model.get(model, 0) or 0)
        estimated_cost = _estimate_chat_cost_usd(entry, prompt_tokens, completion_tokens)
        if estimated_cost is not None:
            estimated_chat_cost_by_model[model] = estimated_cost
    for model in priced_seen_embedding_models:
        entry = _resolve_stats_pricing_entry(
            getattr(settings.pricing, "embedding_models", {}),
            model,
            resolve_pricing_entry,
            getattr(settings.pricing, "model_aliases", {}),
        )
        input_tokens = int(embedding_prompt_tokens_by_model.get(model, 0) or embedding_tokens_by_model.get(model, 0) or 0)
        estimated_cost = _estimate_embedding_cost_usd(entry, input_tokens)
        if estimated_cost is not None:
            estimated_embedding_cost_by_model[model] = estimated_cost

    logged_total_cost_usd = float(stats.get("total_cost_usd", 0.0) or 0.0)
    estimated_total_cost_usd = sum(estimated_chat_cost_by_model.values()) + sum(
        estimated_embedding_cost_by_model.values()
    )
    estimated_cost_gap_usd = max(0.0, estimated_total_cost_usd - logged_total_cost_usd)

    source_rows: list[dict[str, Any]] = []
    for model in sorted(priced_chat_models):
        entry = _resolve_stats_pricing_entry(getattr(settings.pricing, "chat_models", {}), model, resolve_pricing_entry, getattr(settings.pricing, "model_aliases", {}))
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
                "is_manual": _is_manual_pricing_entry(entry),
            }
        )
    for model in sorted(priced_embedding_models):
        entry = _resolve_stats_pricing_entry(
            getattr(settings.pricing, "embedding_models", {}),
            model,
            resolve_pricing_entry,
            getattr(settings.pricing, "model_aliases", {}),
        )
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
                "is_manual": _is_manual_pricing_entry(entry),
            }
        )

    pricing_source = str(getattr(settings.pricing, "source", "") or "").strip()
    default_source_name = str(getattr(settings.pricing, "default_source_name", "") or "").strip() or "-"
    default_source_url = str(getattr(settings.pricing, "default_source_url", "") or "").strip()
    if pricing_source == "litellm_github":
        default_source_name = "LiteLLM GitHub pricing JSON + local cache"
        default_source_url = "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"
    alias_rows = [
        {"alias": str(alias), "target": str(target)}
        for alias, target in sorted(dict(getattr(settings.pricing, "model_aliases", {}) or {}).items())
        if str(alias).strip() and str(target).strip()
    ]

    return {
        "last_updated": str(getattr(settings.pricing, "last_updated", "") or "").strip() or "-",
        "currency": str(getattr(settings.pricing, "currency", "USD") or "USD").strip() or "USD",
        "enabled": bool(getattr(settings.pricing, "enabled", False)),
        "default_source_name": default_source_name,
        "default_source_url": default_source_url,
        "source": pricing_source or "-",
        "litellm_cache_file": str(getattr(settings.pricing, "litellm_cache_file", "") or "").strip(),
        "refresh_interval_days": int(getattr(settings.pricing, "refresh_interval_days", 7) or 7),
        "priced_chat_models": priced_chat_models,
        "priced_embedding_models": priced_embedding_models,
        "priced_chat_count": len(priced_chat_models),
        "priced_embedding_count": len(priced_embedding_models),
        "chat_seen_count": len(chat_seen),
        "embedding_seen_count": len(embedding_seen),
        "priced_seen_chat_count": len(priced_seen_chat_models),
        "priced_seen_embedding_count": len(priced_seen_embedding_models),
        "unpriced_chat_models": unpriced_chat_models,
        "unpriced_embedding_models": unpriced_embedding_models,
        "unpriced_chat_tokens": unpriced_chat_tokens,
        "unpriced_embedding_tokens": unpriced_embedding_tokens,
        "unpriced_model_tokens": unpriced_model_tokens,
        "unpriced_model_rows": sorted(
            unpriced_model_rows,
            key=lambda row: (-int(row.get("tokens", 0) or 0), str(row.get("kind", "")), str(row.get("model", ""))),
        ),
        "has_unpriced_usage": unpriced_model_tokens > 0,
        "estimated_chat_cost_usd_by_model": estimated_chat_cost_by_model,
        "estimated_embedding_cost_usd_by_model": estimated_embedding_cost_by_model,
        "estimated_total_cost_usd": estimated_total_cost_usd,
        "logged_total_cost_usd": logged_total_cost_usd,
        "estimated_cost_gap_usd": estimated_cost_gap_usd,
        "has_estimated_cost_gap": estimated_cost_gap_usd > 0.0000005,
        "source_rows": source_rows,
        "alias_rows": alias_rows,
        "alias_count": len(alias_rows),
    }


def _build_model_gateway_meta(stats: dict[str, Any], settings: Any, pipeline: Any, pricing_meta: dict[str, Any]) -> dict[str, Any]:
    usage_meter = getattr(pipeline, "usage_meter", None)
    llm_client = getattr(pipeline, "llm_client", None)
    embedding_client = getattr(pipeline, "embedding_client", None)
    memory_skill = getattr(pipeline, "memory_skill", None)

    chat_model = str(getattr(llm_client, "model", "") or getattr(getattr(settings, "llm", object()), "model", "") or "").strip()
    embedding_model = ""
    resolve_model = getattr(embedding_client, "_resolve_model", None)
    if callable(resolve_model):
        try:
            embedding_model = str(resolve_model() or "").strip()
        except Exception:
            embedding_model = ""
    if not embedding_model:
        embedding_model = str(getattr(embedding_client, "model", "") or getattr(getattr(settings, "embeddings", object()), "model", "") or "").strip()

    llm_meter = getattr(llm_client, "usage_meter", None)
    embedding_meter = getattr(embedding_client, "usage_meter", None)
    memory_embedding_client = getattr(memory_skill, "embedding_client", None)
    memory_meter = getattr(memory_embedding_client, "usage_meter", None)

    token_tracking = getattr(settings, "token_tracking", object())
    token_tracking_enabled = bool(getattr(token_tracking, "enabled", False))
    log_file = str(getattr(token_tracking, "log_file", "") or "").strip()

    rows = [
        {
            "label_key": "stats.gateway_chat_client",
            "fallback": "Chat client",
            "status": "ok" if usage_meter is not None and llm_meter is usage_meter else "error",
            "detail": chat_model or "-",
        },
        {
            "label_key": "stats.gateway_embedding_client",
            "fallback": "Embedding client",
            "status": "ok" if usage_meter is not None and embedding_meter is usage_meter else "error",
            "detail": embedding_model or "-",
        },
        {
            "label_key": "stats.gateway_memory_client",
            "fallback": "Memory embeddings",
            "status": (
                "ok"
                if memory_skill is not None and memory_embedding_client is embedding_client and memory_meter is usage_meter
                else ("warn" if memory_skill is None else "error")
            ),
            "detail": "shared" if memory_skill is not None else "disabled",
        },
        {
            "label_key": "stats.gateway_token_log",
            "fallback": "Token log",
            "status": "ok" if token_tracking_enabled else "warn",
            "detail": log_file or "-",
        },
    ]

    has_error = any(row["status"] == "error" for row in rows)
    has_warn = any(row["status"] == "warn" for row in rows) or bool(pricing_meta.get("has_unpriced_usage"))
    status = "error" if has_error else ("warn" if has_warn else "ok")
    return {
        "status": status,
        "chat_model": chat_model or "-",
        "embedding_model": embedding_model or "-",
        "usage_meter_shared": usage_meter is not None and llm_meter is usage_meter and embedding_meter is usage_meter,
        "token_tracking_enabled": token_tracking_enabled,
        "log_file": log_file or "-",
        "chat_total_tokens": int(stats.get("chat_total_tokens", 0) or 0),
        "embedding_total_tokens": int(stats.get("embedding_total_tokens", 0) or 0),
        "model_total_tokens": int(stats.get("model_total_tokens", 0) or 0),
        "priced_seen_chat_count": int(pricing_meta.get("priced_seen_chat_count", 0) or 0),
        "priced_seen_embedding_count": int(pricing_meta.get("priced_seen_embedding_count", 0) or 0),
        "unpriced_model_tokens": int(pricing_meta.get("unpriced_model_tokens", 0) or 0),
        "has_unpriced_usage": bool(pricing_meta.get("has_unpriced_usage")),
        "rows": rows,
    }


OPERATOR_GUARDRAIL_ROW_KEYS = (
    "release",
    "gateway",
    "pricing",
    "cost_tracking",
    "recipe_memory",
    "preflight",
    "health",
    "updates",
)


def _guardrail_row(
    *,
    key: str,
    fallback: str,
    status: str,
    summary: str,
    detail: str = "",
    url: str = "",
) -> dict[str, str]:
    clean_status = str(status or "").strip().lower()
    if clean_status not in {"ok", "warn", "error"}:
        clean_status = "warn"
    return {
        "key": key,
        "label_key": f"stats.operator_guardrail_{key}",
        "fallback": fallback,
        "status": clean_status,
        "visual_status": clean_status,
        "summary": str(summary or "").strip(),
        "detail": str(detail or "").strip(),
        "url": str(url or "").strip(),
    }


def _build_operator_guardrail_meta(
    *,
    release_meta: dict[str, Any],
    pricing_meta: dict[str, Any],
    model_gateway: dict[str, Any],
    preflight_meta: dict[str, Any],
    health_meta: dict[str, Any],
    update_status: dict[str, Any],
    recipe_experience_memory: dict[str, Any] | None = None,
    language: str = "de",
) -> dict[str, Any]:
    pricing_status = "warn" if bool(pricing_meta.get("has_unpriced_usage")) else "ok"
    pricing_summary = (
        _stats_route_text(
            language,
            "operator_guardrail_pricing_warn",
            "{tokens} unpriced model tokens.",
            tokens=int(pricing_meta.get("unpriced_model_tokens", 0) or 0),
        )
        if pricing_status == "warn"
        else _stats_route_text(language, "operator_guardrail_pricing_ok", "All seen model usage is priced.")
    )
    cost_tracking_status = "ok"
    cost_tracking_summary = _stats_route_text(language, "operator_guardrail_cost_tracking_ok", "Token and cost tracking are active.")
    token_tracking_enabled = model_gateway.get("token_tracking_enabled")
    usage_meter_shared = model_gateway.get("usage_meter_shared")
    if token_tracking_enabled is False:
        cost_tracking_status = "error"
        cost_tracking_summary = _stats_route_text(language, "operator_guardrail_cost_tracking_error", "Token tracking is disabled.")
    elif usage_meter_shared is False:
        cost_tracking_status = "error"
        cost_tracking_summary = _stats_route_text(language, "operator_guardrail_cost_tracking_meter_error", "Model calls are not all behind the shared UsageMeter.")
    elif bool(pricing_meta.get("has_estimated_cost_gap")):
        cost_tracking_status = "warn"
        cost_tracking_summary = _stats_route_text(language, "operator_guardrail_cost_tracking_gap", "Estimated costs are higher than logged costs.")
    cost_tracking_detail = (
        f"{int(model_gateway.get('model_total_tokens', 0) or 0)} tokens"
        f" · logged ${float(pricing_meta.get('logged_total_cost_usd', 0.0) or 0.0):.6f}"
        f" · estimated ${float(pricing_meta.get('estimated_total_cost_usd', 0.0) or 0.0):.6f}"
    )
    gateway_status = str(model_gateway.get("status", "warn") or "warn").strip().lower()
    preflight_status = str(preflight_meta.get("overall_status", "warn") or "warn").strip().lower()
    health_status = str(health_meta.get("overall_status", "warn") or "warn").strip().lower()
    update_available = bool(update_status.get("update_available"))
    update_status_value = "warn" if update_available else "ok"
    release_label = str(release_meta.get("label", "") or "").strip()
    release_version = str(release_meta.get("version", "") or "").strip()
    current_label = str(update_status.get("current_label", "") or release_label or "-").strip() or "-"
    latest_label = str(update_status.get("latest_label", "") or current_label).strip() or current_label
    update_current_label = str(update_status.get("current_label", "") or "").strip()
    release_status = "ok"
    release_summary = _stats_route_text(language, "operator_guardrail_release_ok", "Release metadata is present.")
    if not release_label or not release_version:
        release_status = "error"
        release_summary = _stats_route_text(language, "operator_guardrail_release_error", "Release metadata is incomplete.")
    elif update_current_label and update_current_label != release_label:
        release_status = "warn"
        release_summary = _stats_route_text(language, "operator_guardrail_release_warn", "Release metadata differs from update status.")
    release_detail = f"{release_label or '-'} · {release_version or '-'}"
    if update_current_label and update_current_label != release_label:
        release_detail = f"{release_detail} · update: {update_current_label}"

    memory_row: dict[str, str] | None = None
    if recipe_experience_memory is not None:
        memory_enabled = bool(recipe_experience_memory.get("enabled"))
        memory_status_raw = str(recipe_experience_memory.get("status", "ok") or "ok").strip().lower()
        memory_collection_count = int(recipe_experience_memory.get("collection_count", 0) or 0)
        memory_point_count = int(recipe_experience_memory.get("point_count", 0) or 0)
        memory_error = str(recipe_experience_memory.get("error", "") or "").strip()
        if memory_enabled and memory_status_raw == "error":
            memory_status = "warn"
            memory_summary = _stats_route_text(language, "operator_guardrail_recipe_memory_warn", "Recipe Experience Memory is enabled but currently not reachable.")
        elif memory_enabled:
            memory_status = "ok"
            memory_summary = _stats_route_text(language, "operator_guardrail_recipe_memory_ok", "Recipe Experience Memory is available.")
        else:
            memory_status = "ok"
            memory_summary = _stats_route_text(language, "operator_guardrail_recipe_memory_disabled", "Recipe Experience Memory is optional and currently disabled.")
        memory_detail = f"{memory_collection_count} collections · {memory_point_count} points"
        if memory_error:
            memory_detail = f"{memory_detail} · {memory_error}"
        memory_row = _guardrail_row(
            key="recipe_memory",
            fallback="Recipe Experience Memory",
            status=memory_status,
            summary=memory_summary,
            detail=memory_detail,
            url="/stats#recipe-experience-memory",
        )

    rows = [
        _guardrail_row(
            key="release",
            fallback="Release metadata",
            status=release_status,
            summary=release_summary,
            detail=release_detail,
            url="/updates",
        ),
        _guardrail_row(
            key="gateway",
            fallback="Model Gateway",
            status=gateway_status,
            summary=_stats_route_text(language, "operator_guardrail_gateway_summary", "UsageMeter and token log path are checked."),
            detail=f"{model_gateway.get('chat_model', '-')} · {model_gateway.get('embedding_model', '-')}",
            url="/stats#model-gateway-audit",
        ),
        _guardrail_row(
            key="pricing",
            fallback="Pricing coverage",
            status=pricing_status,
            summary=pricing_summary,
            detail=(
                f"Chat {pricing_meta.get('priced_seen_chat_count', 0)}/{pricing_meta.get('chat_seen_count', 0)}"
                f" · Embedding {pricing_meta.get('priced_seen_embedding_count', 0)}/{pricing_meta.get('embedding_seen_count', 0)}"
            ),
            url="/stats#stats-pricing-details",
        ),
        _guardrail_row(
            key="cost_tracking",
            fallback="Cost tracking",
            status=cost_tracking_status,
            summary=cost_tracking_summary,
            detail=cost_tracking_detail,
            url="/stats#model-gateway-audit",
        ),
        *([memory_row] if memory_row is not None else []),
        _guardrail_row(
            key="preflight",
            fallback="Startup preflight",
            status=preflight_status,
            summary=_stats_route_text(
                language,
                "operator_guardrail_preflight_summary",
                "{ok} ok · {warn} warn · {error} error",
                ok=int(preflight_meta.get("ok_count", 0) or 0),
                warn=int(preflight_meta.get("warn_count", 0) or 0),
                error=int(preflight_meta.get("error_count", 0) or 0),
            ),
            detail=str(preflight_meta.get("checked_at", "") or ""),
        ),
        _guardrail_row(
            key="health",
            fallback="Runtime health",
            status=health_status,
            summary=_stats_route_text(
                language,
                "operator_guardrail_health_summary",
                "{ok} ok · {warn} warn · {error} error",
                ok=int(health_meta.get("ok_count", 0) or 0),
                warn=int(health_meta.get("warn_count", 0) or 0),
                error=int(health_meta.get("error_count", 0) or 0),
            ),
        ),
        _guardrail_row(
            key="updates",
            fallback="Update path",
            status=update_status_value,
            summary=(
                _stats_route_text(language, "operator_guardrail_update_warn", "Newer public version available.")
                if update_available
                else _stats_route_text(language, "operator_guardrail_update_ok", "No newer public version detected.")
            ),
            detail=f"{current_label} → {latest_label}",
            url="/updates",
        ),
    ]
    statuses = [row["status"] for row in rows]
    overall_status = "error" if "error" in statuses else ("warn" if "warn" in statuses else "ok")
    if overall_status == "ok":
        summary = _stats_route_text(language, "operator_guardrail_overall_ok", "Release and operations guardrails look healthy.")
    elif overall_status == "warn":
        summary = _stats_route_text(language, "operator_guardrail_overall_warn", "At least one operator guardrail needs review.")
    else:
        summary = _stats_route_text(language, "operator_guardrail_overall_error", "At least one operator guardrail currently fails.")
    return {
        "overall_status": overall_status,
        "summary": summary,
        "ok_count": sum(1 for row in rows if row["status"] == "ok"),
        "warn_count": sum(1 for row in rows if row["status"] == "warn"),
        "error_count": sum(1 for row in rows if row["status"] == "error"),
        "rows": rows,
    }


async def _build_recipe_experience_memory_meta(settings: Any) -> dict[str, Any]:
    memory = getattr(settings, "memory", object())
    enabled = bool(getattr(memory, "enabled", False))
    backend = str(getattr(memory, "backend", "") or "").strip().lower()
    if not enabled or backend != "qdrant":
        return {
            "status": "warn",
            "enabled": False,
            "collection_count": 0,
            "point_count": 0,
            "collections": [],
            "recent_rows": [],
        }
    client = create_async_qdrant_client(
        url=str(getattr(memory, "qdrant_url", "") or "").strip(),
        api_key=str(getattr(memory, "qdrant_api_key", "") or "").strip() or None,
        timeout=float(getattr(memory, "timeout_seconds", 10) or 10),
    )
    collections: list[dict[str, Any]] = []
    recent_rows: list[dict[str, Any]] = []
    try:
        resp = await client.get_collections()
        names = [
            str(getattr(item, "name", "") or "").strip()
            for item in getattr(resp, "collections", []) or []
            if is_recipe_experience_qdrant_collection(str(getattr(item, "name", "") or "").strip())
        ]
        for name in sorted(names):
            points = 0
            try:
                info = await client.get_collection(collection_name=name)
                points = int(getattr(info, "points_count", 0) or getattr(info, "vectors_count", 0) or 0)
            except Exception:
                points = 0
            collections.append({"name": name, "points": points})
            if len(recent_rows) < 5:
                try:
                    scroll = getattr(client, "scroll", None)
                    if callable(scroll):
                        result = await scroll(collection_name=name, limit=5, with_payload=True, with_vectors=False)
                        points_result = result[0] if isinstance(result, tuple) else getattr(result, "points", [])
                        for point in list(points_result or []):
                            payload = getattr(point, "payload", {}) or {}
                            if str(payload.get("source", "") or "").strip() != "recipe_experience":
                                continue
                            recent_rows.append(
                                {
                                    "recipe_id": str(payload.get("recipe_id", "") or "").strip(),
                                    "title": str(payload.get("title", "") or payload.get("recipe_id", "") or "").strip() or "-",
                                    "target": "/".join(
                                        part
                                        for part in (
                                            str(payload.get("connection_kind", "") or "").strip(),
                                            str(payload.get("connection_ref", "") or "").strip(),
                                        )
                                        if part
                                    )
                                    or "-",
                                    "intent": str(payload.get("intent", "") or "").strip(),
                                    "connection_kind": str(payload.get("connection_kind", "") or "").strip(),
                                    "connection_ref": str(payload.get("connection_ref", "") or "").strip(),
                                    "capability": str(payload.get("capability", "") or "").strip(),
                                    "action": str(payload.get("chosen_action", "") or payload.get("learned_from_action", "") or "").strip() or "-",
                                    "summary": str(payload.get("experience_summary", "") or payload.get("summary", "") or "").strip(),
                                    "user_message": str(payload.get("user_message", "") or "").strip(),
                                    "experience_count": int(payload.get("experience_count", 0) or 0),
                                    "origin": str(payload.get("learning_origin", "") or payload.get("promotion_state", "") or "").strip() or "-",
                                    "updated_at": str(payload.get("updated_at", "") or payload.get("timestamp", "") or "").strip(),
                                }
                            )
                            if len(recent_rows) >= 5:
                                break
                except Exception:
                    pass
    except Exception as exc:
        return {
            "status": "error",
            "enabled": True,
            "collection_count": 0,
            "point_count": 0,
            "collections": [],
            "recent_rows": [],
            "error": str(exc),
        }
    point_count = sum(int(row.get("points", 0) or 0) for row in collections)
    return {
        "status": "ok" if collections else "warn",
        "enabled": True,
        "collection_count": len(collections),
        "point_count": point_count,
        "collections": collections[:6],
        "recent_rows": sorted(recent_rows, key=lambda row: str(row.get("updated_at", "") or ""), reverse=True)[:5],
        "error": "",
    }


def _build_source_usage_rows(stats: dict[str, Any]) -> list[dict[str, Any]]:
    requests_by_source = dict(stats.get("requests_by_source", {}) or {})
    tokens_by_source = dict(stats.get("model_tokens_by_source", {}) or {})
    cost_by_source = dict(stats.get("cost_usd_by_source", {}) or {})

    sources = {
        str(source).strip()
        for source in (
            list(requests_by_source.keys()) + list(tokens_by_source.keys()) + list(cost_by_source.keys())
        )
        if str(source).strip()
    }

    rows: list[dict[str, Any]] = []
    for source in sources:
        request_count = int(requests_by_source.get(source, 0) or 0)
        token_count = int(tokens_by_source.get(source, 0) or 0)
        cost_usd = float(cost_by_source.get(source, 0.0) or 0.0)
        rows.append(
            {
                "source": source,
                "request_count": request_count,
                "token_count": token_count,
                "cost_usd": cost_usd,
            }
        )

    rows.sort(
        key=lambda row: (
            row["cost_usd"],
            row["token_count"],
            row["request_count"],
            row["source"],
        ),
        reverse=True,
    )
    return rows


def _build_stats_model_totals(stats: dict[str, Any]) -> dict[str, int]:
    chat_total = int(stats.get("chat_total_tokens", 0) or 0)
    embedding_total = int(stats.get("embedding_total_tokens", 0) or 0)
    extraction_total = int(stats.get("extraction_total_tokens", 0) or 0)
    model_total = int(stats.get("model_total_tokens", 0) or (chat_total + embedding_total + extraction_total) or 0)
    return {
        "chat_total_tokens": chat_total,
        "embedding_total_tokens": embedding_total,
        "extraction_total_tokens": extraction_total,
        "model_total_tokens": model_total,
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


def _today_utc_label() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _pricing_entry_text(entry: Any, field: str) -> str:
    if isinstance(entry, dict):
        return str(entry.get(field, "") or "").strip().lower()
    return str(getattr(entry, field, "") or "").strip().lower()


def _is_manual_pricing_entry(entry: Any) -> bool:
    source_name = _pricing_entry_text(entry, "source_name")
    notes = _pricing_entry_text(entry, "notes")
    return "manual" in source_name or "custom" in source_name or "source=manual" in notes or "manual_override=true" in notes


def _merge_refreshed_pricing_entries(existing: Any, refreshed: Any) -> dict[str, Any]:
    existing_rows = dict(existing or {}) if isinstance(existing, dict) else {}
    refreshed_rows = dict(refreshed or {}) if isinstance(refreshed, dict) else {}
    merged: dict[str, Any] = {}

    for model, entry in existing_rows.items():
        if _is_manual_pricing_entry(entry):
            merged[str(model)] = entry

    for model, entry in refreshed_rows.items():
        model_key = str(model)
        if model_key not in merged:
            merged[model_key] = entry

    for model, entry in existing_rows.items():
        model_key = str(model)
        if model_key not in merged:
            merged[model_key] = entry

    return merged


def _ensure_pricing_section(raw: dict[str, Any]) -> dict[str, Any]:
    pricing_section = raw.get("pricing")
    if not isinstance(pricing_section, dict):
        pricing_section = {}
        raw["pricing"] = pricing_section
    pricing_section.setdefault("enabled", True)
    pricing_section.setdefault("currency", "USD")
    pricing_section.setdefault("source", "litellm_github")
    pricing_section.setdefault("model_aliases", {})
    pricing_section.setdefault("chat_models", {})
    pricing_section.setdefault("embedding_models", {})
    return pricing_section


def _normalize_pricing_kind(value: str) -> str:
    clean = str(value or "").strip().lower().replace("-", "_")
    if clean in {"chat", "chat_model", "llm"}:
        return "chat"
    if clean in {"embedding", "embed", "embeddings", "embedding_model"}:
        return "embedding"
    return ""


def _pricing_table_key(kind: str) -> str:
    normalized = _normalize_pricing_kind(kind)
    return "chat_models" if normalized == "chat" else "embedding_models" if normalized == "embedding" else ""


def _manual_pricing_notes(notes: str = "") -> str:
    clean = str(notes or "").strip()
    markers = ["source=manual", "manual_override=true"]
    if clean:
        existing = {part.strip().lower() for part in clean.split(";")}
        additions = [marker for marker in markers if marker not in existing]
        return "; ".join([clean, *additions]) if additions else clean
    return "; ".join(markers)


def _sync_pricing_settings(settings: Any, pricing_section: dict[str, Any]) -> None:
    settings.pricing.enabled = bool(pricing_section.get("enabled", True))
    settings.pricing.currency = str(pricing_section.get("currency", "USD") or "USD")
    settings.pricing.last_updated = str(pricing_section.get("last_updated", "") or "")
    settings.pricing.default_source_name = str(pricing_section.get("default_source_name", "") or "")
    settings.pricing.default_source_url = str(pricing_section.get("default_source_url", "") or "")
    settings.pricing.source = str(pricing_section.get("source", "litellm_github") or "litellm_github")
    settings.pricing.litellm_cache_file = str(pricing_section.get("litellm_cache_file", "data/pricing/litellm_model_prices.json") or "data/pricing/litellm_model_prices.json")
    settings.pricing.refresh_interval_days = int(pricing_section.get("refresh_interval_days", 7) or 7)
    settings.pricing.model_aliases = {
        str(alias): str(target)
        for alias, target in dict(pricing_section.get("model_aliases", {}) or {}).items()
        if str(alias).strip() and str(target).strip()
    }
    settings.pricing.chat_models = {
        str(model): ChatPricingModelConfig.model_validate(entry)
        for model, entry in dict(pricing_section.get("chat_models", {}) or {}).items()
        if isinstance(entry, dict)
    }
    settings.pricing.embedding_models = {
        str(model): EmbeddingPricingModelConfig.model_validate(entry)
        for model, entry in dict(pricing_section.get("embedding_models", {}) or {}).items()
        if isinstance(entry, dict)
    }


def _save_pricing_alias_override(settings: Any, base_dir: Path, *, alias: str, target: str) -> dict[str, Any]:
    clean_alias = str(alias or "").strip()
    clean_target = str(target or "").strip()
    if not clean_alias or not clean_target:
        raise ValueError("Alias and target model are required.")
    raw = _read_raw_config(base_dir)
    pricing_section = _ensure_pricing_section(raw)
    aliases = pricing_section.get("model_aliases")
    if not isinstance(aliases, dict):
        aliases = {}
        pricing_section["model_aliases"] = aliases
    aliases[clean_alias] = clean_target
    _write_raw_config(base_dir, raw)
    _sync_pricing_settings(settings, pricing_section)
    return {"kind": "alias", "alias": clean_alias, "target": clean_target}


def _delete_pricing_alias_override(settings: Any, base_dir: Path, *, alias: str) -> dict[str, Any]:
    clean_alias = str(alias or "").strip()
    if not clean_alias:
        raise ValueError("Alias is required.")
    raw = _read_raw_config(base_dir)
    pricing_section = _ensure_pricing_section(raw)
    aliases = pricing_section.get("model_aliases")
    if isinstance(aliases, dict):
        aliases.pop(clean_alias, None)
    _write_raw_config(base_dir, raw)
    _sync_pricing_settings(settings, pricing_section)
    return {"kind": "alias", "alias": clean_alias, "deleted": True}


def _save_manual_pricing_model(
    settings: Any,
    base_dir: Path,
    *,
    kind: str,
    model: str,
    input_per_million: float,
    output_per_million: float = 0.0,
    source_name: str = "Manual",
    source_url: str = "",
    notes: str = "",
) -> dict[str, Any]:
    normalized_kind = _normalize_pricing_kind(kind)
    table_key = _pricing_table_key(normalized_kind)
    clean_model = str(model or "").strip()
    if not table_key or not clean_model:
        raise ValueError("Model kind and model name are required.")
    input_rate = float(input_per_million or 0.0)
    output_rate = float(output_per_million or 0.0)
    if input_rate < 0 or output_rate < 0:
        raise ValueError("Pricing rates must not be negative.")
    raw = _read_raw_config(base_dir)
    pricing_section = _ensure_pricing_section(raw)
    table = pricing_section.get(table_key)
    if not isinstance(table, dict):
        table = {}
        pricing_section[table_key] = table
    entry: dict[str, Any] = {
        "input_per_million": input_rate,
        "source_name": str(source_name or "").strip() or "Manual",
        "source_url": str(source_url or "").strip(),
        "verified_at": _today_utc_label(),
        "notes": _manual_pricing_notes(notes),
    }
    if normalized_kind == "chat":
        entry["output_per_million"] = output_rate
    table[clean_model] = entry
    pricing_section["last_updated"] = _today_utc_label()
    _write_raw_config(base_dir, raw)
    _sync_pricing_settings(settings, pricing_section)
    return {"kind": normalized_kind, "model": clean_model, "entry": entry}


def _delete_manual_pricing_model(settings: Any, base_dir: Path, *, kind: str, model: str) -> dict[str, Any]:
    normalized_kind = _normalize_pricing_kind(kind)
    table_key = _pricing_table_key(normalized_kind)
    clean_model = str(model or "").strip()
    if not table_key or not clean_model:
        raise ValueError("Model kind and model name are required.")
    raw = _read_raw_config(base_dir)
    pricing_section = _ensure_pricing_section(raw)
    table = pricing_section.get(table_key)
    if isinstance(table, dict):
        entry = table.get(clean_model)
        if entry is not None and not _is_manual_pricing_entry(entry):
            raise ValueError("Only manual pricing overrides can be deleted from this admin action.")
        table.pop(clean_model, None)
    _write_raw_config(base_dir, raw)
    _sync_pricing_settings(settings, pricing_section)
    return {"kind": normalized_kind, "model": clean_model, "deleted": True}


async def _refresh_pricing_snapshot(
    settings: Any,
    base_dir: Path,
    *,
    force_litellm_refresh: bool = True,
) -> dict[str, Any]:
    pricing = getattr(settings, "pricing", None)
    cache_file = Path(str(getattr(pricing, "litellm_cache_file", "data/pricing/litellm_model_prices.json") or "data/pricing/litellm_model_prices.json"))
    if not cache_file.is_absolute():
        cache_file = base_dir / cache_file
    snapshot = await build_pricing_catalog_snapshot(
        include_litellm=True,
        include_openrouter=False,
        litellm_cache_file=cache_file,
        litellm_refresh_interval_days=int(getattr(pricing, "refresh_interval_days", 7) or 7),
        force_litellm_refresh=force_litellm_refresh,
    )
    raw = _read_raw_config(base_dir)
    pricing_section = raw.get("pricing")
    if not isinstance(pricing_section, dict):
        pricing_section = {}
    chat_models = _merge_refreshed_pricing_entries(
        pricing_section.get("chat_models"),
        snapshot.get("chat_models"),
    )
    embedding_models = _merge_refreshed_pricing_entries(
        pricing_section.get("embedding_models"),
        snapshot.get("embedding_models"),
    )
    pricing_section.update(
        {
            "enabled": True,
            "currency": "USD",
            "last_updated": snapshot.get("last_updated", ""),
            "default_source_name": snapshot.get("default_source_name", ""),
            "default_source_url": snapshot.get("default_source_url", ""),
            "source": "litellm_github",
            "litellm_cache_file": str(getattr(pricing, "litellm_cache_file", "data/pricing/litellm_model_prices.json") or "data/pricing/litellm_model_prices.json"),
            "refresh_interval_days": int(getattr(pricing, "refresh_interval_days", 7) or 7),
            "chat_models": chat_models,
            "embedding_models": embedding_models,
        }
    )
    raw["pricing"] = pricing_section
    _write_raw_config(base_dir, raw)
    _sync_pricing_settings(settings, pricing_section)
    return snapshot


def _pricing_refresh_meta(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    payload = snapshot if isinstance(snapshot, dict) else {}
    chat_models = payload.get("chat_models", {})
    embedding_models = payload.get("embedding_models", {})
    errors = payload.get("errors", [])
    litellm_cache = payload.get("litellm_cache", {})
    cache = litellm_cache if isinstance(litellm_cache, dict) else {}
    return {
        "refreshed": bool(payload),
        "last_updated": str(payload.get("last_updated", "") or "").strip(),
        "chat_model_count": len(chat_models) if isinstance(chat_models, dict) else 0,
        "embedding_model_count": len(embedding_models) if isinstance(embedding_models, dict) else 0,
        "cache_refreshed": bool(cache.get("refreshed", False)),
        "cache_used": bool(cache.get("used_cache", False)),
        "cache_file": str(cache.get("cache_file", "") or "").strip(),
        "errors": [str(item) for item in errors] if isinstance(errors, list) else [],
    }


def _build_preflight_meta(payload: dict[str, Any], language: str, active_profiles: dict[str, str] | None = None) -> dict[str, Any]:
    active_profiles = active_profiles or {}
    labels = {
        "prompts": _pick_text(language, "Prompt-Dateien", "Prompt files"),
        "qdrant": _pick_text(language, "Memory / Qdrant", "Memory / Qdrant"),
        "llm": _pick_text(language, "Chat LLM", "Chat LLM"),
        "embeddings": _pick_text(language, "Embeddings", "Embeddings"),
    }
    summary_labels = {
        "prompts_ok": lambda row: _pick_text(
            language,
            _stats_route_text(
                language,
                "prompts_ok",
                "Prompt files ok ({count} recipe prompts).",
                count=int(row.get("skill_prompt_count", 0) or 0),
            ),
            "Prompt files ok ({count} recipe prompts).".format(count=int(row.get("skill_prompt_count", 0) or 0)),
        ),
        "prompts_incomplete": lambda row: _stats_route_text(language, "prompts_incomplete", "Prompt files incomplete."),
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
        "embeddings_missing_model": lambda row: _stats_route_text(language, "embeddings_missing_model", "Embedding model missing."),
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
        active_profile = str(active_profiles.get(check_id, "") or "").strip()
        display_name = labels.get(check_id, check_id or "-")
        if active_profile:
            display_name = f"{display_name} ({active_profile})"
        checks.append(
            {
                "id": check_id,
                "name": display_name,
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


async def _build_health_meta(
    settings: Any,
    pipeline: Pipeline,
    language: str,
    request: Request | None = None,
    *,
    get_secure_store: SecureStoreGetter | None = None,
) -> dict[str, Any]:
    base_dir = _project_root()
    services: list[dict[str, Any]] = []
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
            collection_names = [
                str(getattr(row, "name", "") or "").strip()
                for row in collections
                if str(getattr(row, "name", "") or "").strip()
            ]
            storage_path = resolve_qdrant_storage_path(base_dir, qdrant_url)
            local_collection_names = list_local_qdrant_collection_names(storage_path)
            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=collection_names,
            )
            if storage_warning:
                memory_status = "warn"
                memory_summary = _pick_text(
                    language,
                    "Qdrant erreichbar, aber gespeicherte Collections fehlen in der API.",
                    "Qdrant reachable, but stored collections are missing from the API.",
                )
                memory_detail = str(storage_warning.get("message", "") or qdrant_url or "-")
            else:
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
                _stats_route_text(language, "logs_available", "Run/token logs available.")
                if log_exists
                else _stats_route_text(language, "logs_missing", "No run/token logs yet."),
                "Run/token logs available." if log_exists else "No run/token logs yet.",
            ),
            "detail": f"{log_path} · {log_size}",
        }
    )

    update_status = dict(getattr(getattr(request, "state", object()), "update_status", {}) or {}) if request else {}
    release_meta = dict(getattr(getattr(request, "state", object()), "release_meta", {}) or {}) if request else {}
    current_label = str(update_status.get("current_label", "") or release_meta.get("label", "") or "-").strip() or "-"
    latest_label = str(update_status.get("latest_label", "") or current_label).strip() or current_label
    update_available = bool(update_status.get("update_available"))
    services.append(
        {
            "name": "Updates",
            "status": "warn" if update_available else "ok",
            "summary": _pick_text(
                language,
                "Neueste Public-Version erkannt. Release Notes anzeigen." if update_available else "Kein neuer Public-Release erkannt. Release-Status ansehen.",
                "A newer public release was found. Open the release notes." if update_available else "No newer public release detected. Open the release status.",
            ),
            "detail": _pick_text(
                language,
                f"Installiert: {current_label} · Public: {latest_label}",
                f"Installed: {current_label} · Public: {latest_label}",
            ),
            "url": "/updates",
        }
    )

    helper_store = None
    if get_secure_store is not None:
        try:
            helper_store = get_secure_store()
        except Exception:
            helper_store = None
    helper_config = resolve_update_helper_config(secure_store=helper_store)
    helper_status = "warn"
    helper_summary = _pick_text(
        language,
        "Kein GUI-Update-Helper konfiguriert.",
        "No GUI update helper configured.",
    )
    helper_detail = _pick_text(
        language,
        "Managed-Installationen und interne aria-pull-Setups koennen hier ihren Update-Helper melden.",
        "Managed installations and internal aria-pull setups can expose their update helper here.",
    )
    if helper_config.enabled:
        try:
            helper_payload = fetch_update_helper_status(helper_config, timeout=1.2)
            helper_status = helper_status_visual(
                str(helper_payload.get("status", "") or ""),
                running=bool(helper_payload.get("running", False)),
                configured=True,
                reachable=bool(helper_payload.get("reachable", True)),
                last_error=str(helper_payload.get("last_error", "") or helper_payload.get("error", "") or ""),
            )
            if bool(helper_payload.get("running", False)):
                helper_summary = _pick_text(
                    language,
                    "Update-Helper arbeitet gerade an einem Lauf.",
                    "Update helper is currently processing a run.",
                )
            elif helper_status == "ok":
                helper_summary = _pick_text(
                    language,
                    "GUI-Update-Helper erreichbar und bereit.",
                    "GUI update helper reachable and ready.",
                )
            elif helper_status == "error":
                helper_summary = _pick_text(
                    language,
                    _stats_route_text(language, "update_helper_error", "GUI update helper reports an error."),
                    "GUI update helper reports an error.",
                )
            else:
                helper_summary = _pick_text(
                    language,
                    "GUI-Update-Helper erreichbar, aber mit Hinweisstatus.",
                    "GUI update helper reachable with a warning state.",
                )
            helper_detail = str(helper_payload.get("current_step", "") or helper_payload.get("last_result", "") or helper_payload.get("last_error", "") or "/updates").strip() or "/updates"
        except RuntimeError as exc:
            helper_status = "error"
            helper_summary = _pick_text(
                language,
                "GUI-Update-Helper nicht erreichbar.",
                "GUI update helper not reachable.",
            )
            helper_detail = str(exc)
    services.append(
        {
            "name": "Update Helper",
            "status": helper_status,
            "summary": helper_summary,
            "detail": helper_detail,
            "url": "/updates",
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
    get_secure_store: SecureStoreGetter | None = None,
) -> None:
    async def _pricing_panel_response(
        request: Request,
        *,
        pricing_refresh: dict[str, Any] | None = None,
        pricing_admin: dict[str, Any] | None = None,
    ) -> Response:
        settings = get_settings()
        pipeline = get_pipeline()
        stats = await pipeline.token_tracker.get_stats(days=7)
        pricing_meta = _build_pricing_meta(stats, settings, resolve_pricing_entry)
        return templates.TemplateResponse(
            request=request,
            name="_stats_pricing_panel.html",
            context={
                "stats": stats,
                "pricing_meta": pricing_meta,
                "pricing_refresh": pricing_refresh,
                "pricing_admin": pricing_admin,
            },
        )

    @app.post("/stats/pricing/refresh")
    async def stats_pricing_refresh(request: Request) -> Response:
        can_access_advanced = bool(
            getattr(getattr(request, "state", object()), "can_access_advanced_config", False)
        )
        settings = get_settings()
        refresh_meta: dict[str, Any] | None = None
        if can_access_advanced:
            refresh_meta = _pricing_refresh_meta(await _refresh_pricing_snapshot(settings, _project_root()))
        if str(request.headers.get("HX-Request", "")).strip().lower() == "true":
            return await _pricing_panel_response(request, pricing_refresh=refresh_meta)
        return RedirectResponse("/stats#stats-pricing-details", status_code=303)

    @app.post("/stats/pricing/alias")
    async def stats_pricing_alias(
        request: Request,
        alias: str = Form(""),
        target: str = Form(""),
    ) -> Response:
        if not bool(getattr(getattr(request, "state", object()), "can_access_advanced_config", False)):
            return RedirectResponse("/stats#stats-pricing-details", status_code=303)
        status = "ok"
        message = "Pricing alias saved."
        try:
            _save_pricing_alias_override(get_settings(), _project_root(), alias=alias, target=target)
        except ValueError as exc:
            status = "warn"
            message = str(exc)
        if str(request.headers.get("HX-Request", "")).strip().lower() == "true":
            return await _pricing_panel_response(request, pricing_admin={"status": status, "message": message})
        return RedirectResponse(f"/stats#stats-pricing-details", status_code=303)

    @app.post("/stats/pricing/alias/delete")
    async def stats_pricing_alias_delete(
        request: Request,
        alias: str = Form(""),
    ) -> Response:
        if not bool(getattr(getattr(request, "state", object()), "can_access_advanced_config", False)):
            return RedirectResponse("/stats#stats-pricing-details", status_code=303)
        status = "ok"
        message = "Pricing alias deleted."
        try:
            _delete_pricing_alias_override(get_settings(), _project_root(), alias=alias)
        except ValueError as exc:
            status = "warn"
            message = str(exc)
        if str(request.headers.get("HX-Request", "")).strip().lower() == "true":
            return await _pricing_panel_response(request, pricing_admin={"status": status, "message": message})
        return RedirectResponse("/stats#stats-pricing-details", status_code=303)

    @app.post("/stats/pricing/manual")
    async def stats_pricing_manual(
        request: Request,
        kind: str = Form(""),
        model: str = Form(""),
        input_per_million: float = Form(0.0),
        output_per_million: float = Form(0.0),
        source_name: str = Form("Manual"),
        source_url: str = Form(""),
        notes: str = Form(""),
    ) -> Response:
        if not bool(getattr(getattr(request, "state", object()), "can_access_advanced_config", False)):
            return RedirectResponse("/stats#stats-pricing-details", status_code=303)
        status = "ok"
        message = "Manual pricing saved."
        try:
            _save_manual_pricing_model(
                get_settings(),
                _project_root(),
                kind=kind,
                model=model,
                input_per_million=input_per_million,
                output_per_million=output_per_million,
                source_name=source_name,
                source_url=source_url,
                notes=notes,
            )
        except ValueError as exc:
            status = "warn"
            message = str(exc)
        if str(request.headers.get("HX-Request", "")).strip().lower() == "true":
            return await _pricing_panel_response(request, pricing_admin={"status": status, "message": message})
        return RedirectResponse("/stats#stats-pricing-details", status_code=303)

    @app.post("/stats/pricing/manual/delete")
    async def stats_pricing_manual_delete(
        request: Request,
        kind: str = Form(""),
        model: str = Form(""),
    ) -> Response:
        if not bool(getattr(getattr(request, "state", object()), "can_access_advanced_config", False)):
            return RedirectResponse("/stats#stats-pricing-details", status_code=303)
        status = "ok"
        message = "Manual pricing deleted."
        try:
            _delete_manual_pricing_model(get_settings(), _project_root(), kind=kind, model=model)
        except ValueError as exc:
            status = "warn"
            message = str(exc)
        if str(request.headers.get("HX-Request", "")).strip().lower() == "true":
            return await _pricing_panel_response(request, pricing_admin={"status": status, "message": message})
        return RedirectResponse("/stats#stats-pricing-details", status_code=303)

    @app.post("/stats/recipe-experience/review")
    async def stats_recipe_experience_review(
        request: Request,
        recipe_id: str = Form(""),
        title: str = Form(""),
        intent: str = Form(""),
        connection_kind: str = Form(""),
        connection_ref: str = Form(""),
        capability: str = Form(""),
        action: str = Form(""),
        summary: str = Form(""),
        user_message: str = Form(""),
        experience_count: int = Form(1),
        origin: str = Form(""),
        updated_at: str = Form(""),
    ) -> RedirectResponse:
        if not bool(getattr(getattr(request, "state", object()), "can_access_advanced_config", False)):
            return RedirectResponse("/stats#recipe-experience-memory", status_code=303)
        try:
            row = promote_recipe_experience_to_learned_review(
                {
                    "recipe_id": recipe_id,
                    "title": title,
                    "intent": intent,
                    "connection_kind": connection_kind,
                    "connection_ref": connection_ref,
                    "capability": capability,
                    "chosen_action": action,
                    "experience_summary": summary,
                    "user_message": user_message,
                    "experience_count": experience_count,
                    "learning_origin": origin,
                    "last_success_at": updated_at,
                }
            )
            info = quote_plus(f"experience_review:{row.get('recipe_id', '')}")
            return RedirectResponse(f"/recipes/learned?saved=1&info={info}", status_code=303)
        except (OSError, ValueError) as exc:
            error = quote_plus(str(exc))
            return RedirectResponse(f"/stats?error={error}#recipe-experience-memory", status_code=303)

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
                _stats_route_text(language, "reset_confirm_exact", 'Please type "RESET" exactly to confirm.'),
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
        model_gateway = _build_model_gateway_meta(stats, settings, pipeline, pricing_meta)
        recipe_experience_memory = await _build_recipe_experience_memory_meta(settings)
        language = str(getattr(getattr(request, "state", object()), "lang", "") or settings.ui.language or "de")
        health_meta = await _build_health_meta(settings, pipeline, language, request, get_secure_store=get_secure_store)
        preflight_payload = get_runtime_preflight() or {}
        if inspect.isawaitable(preflight_payload):
            preflight_payload = await preflight_payload
        active_profiles = _load_active_runtime_profiles(base_dir)
        preflight_meta = _build_preflight_meta(
            preflight_payload if isinstance(preflight_payload, dict) else {},
            language,
            active_profiles=active_profiles,
        )
        runtime_memory = _build_runtime_memory_meta(language)
        qdrant_storage = await _build_qdrant_storage_meta(base_dir, settings)
        routing_index_meta = await build_connection_routing_index_status(settings)
        release_meta = dict(getattr(getattr(request, "state", object()), "release_meta", {}) or _build_release_meta(base_dir))
        update_status = dict(getattr(getattr(request, "state", object()), "update_status", {}) or {})
        operator_guardrail = _build_operator_guardrail_meta(
            release_meta=release_meta,
            pricing_meta=pricing_meta,
            model_gateway=model_gateway,
            preflight_meta=preflight_meta,
            health_meta=health_meta,
            update_status=update_status,
            recipe_experience_memory=recipe_experience_memory,
            language=language,
        )
        source_usage_rows = _build_source_usage_rows(stats)
        model_totals = _build_stats_model_totals(stats)
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
                cached_only_threshold=4,
                base_dir=base_dir,
                lang=language,
            )
            connection_status_rows = _collapse_large_connection_groups(
                connection_status_rows,
                threshold=4,
                language=language,
            )
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
                'model_gateway': model_gateway,
                'recipe_experience_memory': recipe_experience_memory,
                'health_meta': health_meta,
                'preflight_meta': preflight_meta,
                'runtime_memory': runtime_memory,
                'qdrant_storage': qdrant_storage,
                'routing_index_meta': routing_index_meta,
                'release_meta': release_meta,
                'update_status': update_status,
                'operator_guardrail': operator_guardrail,
                'source_usage_rows': source_usage_rows,
                'model_totals': model_totals,
                'activities': activity_data,
                'connection_status_rows': connection_status_rows,
                'reset_done': reset_done,
                'reset_error': reset_error,
            },
        )
