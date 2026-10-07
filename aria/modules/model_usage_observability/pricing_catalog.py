from __future__ import annotations

from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from functools import lru_cache
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

import httpx


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
LITELLM_PRICING_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
OPENAI_PRICING_SOURCE_URL = "https://platform.openai.com/docs/pricing"
ANTHROPIC_PRICING_SOURCE_URL = "https://www.anthropic.com/pricing"
OPENROUTER_PRICING_SOURCE_URL = "https://openrouter.ai/docs/api-reference/list-available-models"
LITELLM_PRICING_SOURCE_URL = "https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json"
DEFAULT_LITELLM_PRICING_CACHE_FILE = "data/pricing/litellm_model_prices.json"

ARIA_PRICING_SOURCE_NAME = "ARIA bundled pricing seed"
ARIA_PRICING_SOURCE_URL = "docs/help/pricing.md"

_BUNDLED_CHAT_PRICES: dict[str, dict[str, Any]] = {
    "openai/gpt-4o-mini": {
        "input_per_million": 0.15,
        "output_per_million": 0.60,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/gpt-4o": {
        "input_per_million": 2.50,
        "output_per_million": 10.00,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/gpt-4.1": {
        "input_per_million": 2.00,
        "output_per_million": 8.00,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/gpt-4.1-mini": {
        "input_per_million": 0.40,
        "output_per_million": 1.60,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/gpt-4.1-nano": {
        "input_per_million": 0.10,
        "output_per_million": 0.40,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "anthropic/claude-sonnet-4-5": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "source_url": ANTHROPIC_PRICING_SOURCE_URL,
        "notes": "provider=anthropic; source=aria_pricing_seed",
    },
    "anthropic/claude-3-5-sonnet": {
        "input_per_million": 3.00,
        "output_per_million": 15.00,
        "source_url": ANTHROPIC_PRICING_SOURCE_URL,
        "notes": "provider=anthropic; source=aria_pricing_seed",
    },
    "anthropic/claude-3-haiku": {
        "input_per_million": 0.25,
        "output_per_million": 1.25,
        "source_url": ANTHROPIC_PRICING_SOURCE_URL,
        "notes": "provider=anthropic; source=aria_pricing_seed",
    },
    "anthropic/claude-3-opus": {
        "input_per_million": 15.00,
        "output_per_million": 75.00,
        "source_url": ANTHROPIC_PRICING_SOURCE_URL,
        "notes": "provider=anthropic; source=aria_pricing_seed",
    },
}

_BUNDLED_EMBEDDING_PRICES: dict[str, dict[str, Any]] = {
    "openai/text-embedding-3-small": {
        "input_per_million": 0.02,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/text-embedding-3-large": {
        "input_per_million": 0.13,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
    "openai/text-embedding-ada-002": {
        "input_per_million": 0.10,
        "source_url": OPENAI_PRICING_SOURCE_URL,
        "notes": "provider=openai; source=aria_pricing_seed",
    },
}

_DEFAULT_MODEL_ALIASES: dict[str, str] = {
    "embed-small": "openai/text-embedding-3-small",
    "openai/embed-small": "openai/text-embedding-3-small",
}


def _today_label() -> str:
    return date.today().isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _model_aliases(model_name: str) -> list[str]:
    clean = str(model_name or "").strip()
    if not clean:
        return []
    aliases = [clean]
    if "/" in clean:
        aliases.append(clean.rsplit("/", 1)[-1])
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _normalize_lookup_key(model_name: str) -> str:
    clean = str(model_name or "").strip().lower()
    if not clean:
        return ""
    if "/" in clean:
        clean = clean.rsplit("/", 1)[-1]
    clean = clean.replace("_", "-").replace(" ", "-")
    clean = re.sub(r"-+", "-", clean).strip("-")
    if clean.endswith("-latest"):
        clean = clean[: -len("-latest")]
    return clean


def _lookup_mapping(mapping: dict[str, Any], model_name: str) -> Any | None:
    clean = str(model_name or "").strip()
    if not clean:
        return None
    if clean in mapping:
        return mapping[clean]
    lowered = {str(key).strip().lower(): value for key, value in mapping.items()}
    entry = lowered.get(clean.lower())
    if entry is not None:
        return entry
    normalized_rows = {_normalize_lookup_key(str(key)): value for key, value in mapping.items()}
    return normalized_rows.get(_normalize_lookup_key(clean))


def resolve_model_alias(model_name: str, model_aliases: dict[str, str] | None = None) -> str:
    clean = str(model_name or "").strip()
    if not clean:
        return ""
    configured_alias = _lookup_mapping(model_aliases or {}, clean)
    if configured_alias:
        return str(configured_alias).strip() or clean
    default_alias = _lookup_mapping(_DEFAULT_MODEL_ALIASES, clean)
    if default_alias:
        return str(default_alias).strip() or clean
    return clean


def _extract_claude_family(model_name: str) -> str:
    normalized = _normalize_lookup_key(model_name)
    if not normalized.startswith("claude-"):
        return ""
    tokens = [token for token in normalized.split("-") if token]
    for family in ("sonnet", "haiku", "opus"):
        if family in tokens:
            return f"claude-{family}"
    return ""


def _extract_claude_version_tuple(model_name: str) -> tuple[int, ...]:
    normalized = _normalize_lookup_key(model_name)
    if not normalized.startswith("claude-"):
        return ()
    tokens = [token for token in normalized.split("-") if token]
    numeric_tokens = [token for token in tokens[1:] if token.isdigit()]
    return tuple(int(token) for token in numeric_tokens)


def _resolve_claude_family_fallback(rows: dict[str, dict[str, Any]], model_name: str) -> Any | None:
    requested_family = _extract_claude_family(model_name)
    if not requested_family:
        return None

    best_entry: dict[str, Any] | None = None
    best_version: tuple[int, ...] = ()
    for key, entry in rows.items():
        if not isinstance(entry, dict):
            continue
        if _extract_claude_family(str(key)) != requested_family:
            continue
        version = _extract_claude_version_tuple(str(key))
        if best_entry is None or version > best_version:
            best_entry = entry
            best_version = version
    return SimpleNamespace(**best_entry) if isinstance(best_entry, dict) else None


def _bundled_price_entry(entry: dict[str, Any], *, verified_at: str) -> dict[str, Any]:
    payload = dict(entry)
    payload.setdefault("source_name", ARIA_PRICING_SOURCE_NAME)
    payload.setdefault("source_url", ARIA_PRICING_SOURCE_URL)
    payload["verified_at"] = verified_at
    return payload


def build_bundled_pricing_catalog(*, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    verified_label = str(verified_at or "").strip() or _today_label()
    chat_models: dict[str, dict[str, Any]] = {}
    embedding_models: dict[str, dict[str, Any]] = {}
    for model_key, entry in _BUNDLED_CHAT_PRICES.items():
        for alias in _model_aliases(model_key):
            chat_models.setdefault(alias, _bundled_price_entry(entry, verified_at=verified_label))
    for model_key, entry in _BUNDLED_EMBEDDING_PRICES.items():
        for alias in _model_aliases(model_key):
            embedding_models.setdefault(alias, _bundled_price_entry(entry, verified_at=verified_label))

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
    }


@lru_cache(maxsize=1)
def _cached_bundled_pricing_catalog() -> dict[str, dict[str, dict[str, Any]]]:
    return build_bundled_pricing_catalog(verified_at=_today_label())


def resolve_bundled_pricing_entry(model_name: str) -> Any | None:
    clean = str(model_name or "").strip()
    if not clean:
        return None
    canonical = resolve_model_alias(clean)
    lookup_names = list(dict.fromkeys([clean, canonical]))

    catalog = _cached_bundled_pricing_catalog()
    for lookup_name in lookup_names:
        for table_name in ("chat_models", "embedding_models"):
            rows = catalog.get(table_name, {})
            entry = _lookup_mapping(rows, lookup_name)
            if isinstance(entry, dict):
                return SimpleNamespace(**entry)
            fallback_entry = _resolve_claude_family_fallback(rows, lookup_name)
            if fallback_entry is not None:
                return fallback_entry
    return None


def resolve_pricing_entry(
    entries: dict[str, Any],
    model_name: str,
    *,
    model_aliases: dict[str, str] | None = None,
) -> Any | None:
    clean = str(model_name or "").strip()
    if not clean:
        return None
    entry = _lookup_mapping(entries, clean)
    if entry is not None:
        return entry
    canonical = resolve_model_alias(clean, model_aliases)
    if canonical and canonical != clean:
        entry = _lookup_mapping(entries, canonical)
        if entry is not None:
            return entry
    return resolve_bundled_pricing_entry(canonical or clean)


def _openrouter_price_row(model_name: str, payload: dict[str, Any], *, verified_at: str) -> tuple[str, dict[str, Any]] | None:
    pricing = payload.get("pricing")
    if not isinstance(pricing, dict):
        return None

    prompt_rate = _safe_float(pricing.get("prompt")) * 1_000_000
    completion_rate = _safe_float(pricing.get("completion")) * 1_000_000
    if prompt_rate <= 0.0 and completion_rate <= 0.0:
        return None

    architecture = payload.get("architecture")
    modality = ""
    if isinstance(architecture, dict):
        modality = str(architecture.get("modality", "") or "").strip().lower()
    is_embedding = "embedding" in modality or model_name.lower().endswith("embedding")
    if is_embedding:
        return model_name, {
            "input_per_million": prompt_rate,
            "source_name": "OpenRouter Models API",
            "source_url": OPENROUTER_PRICING_SOURCE_URL,
            "verified_at": verified_at,
            "notes": "provider=openrouter; source=openrouter.ai/api/v1/models",
        }

    return model_name, {
        "input_per_million": prompt_rate,
        "output_per_million": completion_rate,
        "source_name": "OpenRouter Models API",
        "source_url": OPENROUTER_PRICING_SOURCE_URL,
        "verified_at": verified_at,
        "notes": "provider=openrouter; source=openrouter.ai/api/v1/models",
    }


def _litellm_model_aliases(model_name: str, provider: str) -> list[str]:
    aliases = _model_aliases(model_name)
    clean_provider = str(provider or "").strip().lower()
    if clean_provider and "/" not in model_name:
        aliases.extend(_model_aliases(f"{clean_provider}/{model_name}"))
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _litellm_price_row(model_name: str, payload: dict[str, Any], *, verified_at: str) -> tuple[str, dict[str, Any], bool] | None:
    input_rate = _safe_float(payload.get("input_cost_per_token")) * 1_000_000
    output_rate = _safe_float(payload.get("output_cost_per_token")) * 1_000_000
    if input_rate <= 0.0 and output_rate <= 0.0:
        return None

    mode = str(payload.get("mode", "") or "").strip().lower()
    provider = str(payload.get("litellm_provider", "") or "").strip().lower()
    is_embedding = mode == "embedding" or "embedding" in model_name.lower() or payload.get("output_vector_size") is not None
    notes = f"provider={provider or 'unknown'}; source=litellm_github_pricing_json"
    if is_embedding:
        return model_name, {
            "input_per_million": input_rate,
            "source_name": "LiteLLM GitHub pricing JSON",
            "source_url": LITELLM_PRICING_SOURCE_URL,
            "verified_at": verified_at,
            "notes": notes,
        }, True

    if output_rate <= 0.0:
        return None
    return model_name, {
        "input_per_million": input_rate,
        "output_per_million": output_rate,
        "source_name": "LiteLLM GitHub pricing JSON",
        "source_url": LITELLM_PRICING_SOURCE_URL,
        "verified_at": verified_at,
        "notes": notes,
    }, False


async def fetch_openrouter_pricing_catalog(*, timeout_seconds: float = 3.0, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    verified_label = str(verified_at or "").strip() or _today_label()
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(
            OPENROUTER_MODELS_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "ARIA-PricingSync/1.0",
            },
        )
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("data", []) if isinstance(payload, dict) else []
    chat_models: dict[str, dict[str, Any]] = {}
    embedding_models: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        model_name = str(row.get("id", "") or "").strip()
        if not model_name:
            continue
        parsed = _openrouter_price_row(model_name, row, verified_at=verified_label)
        if parsed is None:
            continue
        model_key, entry = parsed
        target = embedding_models if "output_per_million" not in entry else chat_models
        for alias in _model_aliases(model_key):
            target.setdefault(alias, dict(entry))
            target.setdefault(f"openrouter/{alias}", dict(entry))

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
    }


async def fetch_litellm_pricing_payload(*, timeout_seconds: float = 3.0) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(
            LITELLM_PRICING_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": "ARIA-PricingSync/1.0",
            },
        )
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, dict) else {}


def build_litellm_pricing_catalog(payload: dict[str, Any], *, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    verified_label = str(verified_at or "").strip() or _today_label()
    rows = payload if isinstance(payload, dict) else {}
    chat_models: dict[str, dict[str, Any]] = {}
    embedding_models: dict[str, dict[str, Any]] = {}
    for model_name, row in rows.items():
        if not isinstance(row, dict):
            continue
        clean_model = str(model_name or "").strip()
        if not clean_model:
            continue
        parsed = _litellm_price_row(clean_model, row, verified_at=verified_label)
        if parsed is None:
            continue
        model_key, entry, is_embedding = parsed
        provider = str(row.get("litellm_provider", "") or "").strip().lower()
        target = embedding_models if is_embedding else chat_models
        for alias in _litellm_model_aliases(model_key, provider):
            target.setdefault(alias, dict(entry))

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
    }


async def fetch_litellm_pricing_catalog(*, timeout_seconds: float = 3.0, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    payload = await fetch_litellm_pricing_payload(timeout_seconds=timeout_seconds)
    return build_litellm_pricing_catalog(payload, verified_at=verified_at)


def _litellm_cache_path(cache_file: str | Path | None = None) -> Path:
    return Path(str(cache_file or DEFAULT_LITELLM_PRICING_CACHE_FILE)).expanduser()


def _read_litellm_pricing_cache(cache_file: str | Path | None = None) -> dict[str, Any]:
    path = _litellm_cache_path(cache_file)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _write_litellm_pricing_cache(payload: dict[str, Any], cache_file: str | Path | None = None) -> None:
    path = _litellm_cache_path(cache_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    tmp_path.replace(path)


def _litellm_cache_age(cache_file: str | Path | None = None, *, now: datetime | None = None) -> timedelta | None:
    path = _litellm_cache_path(cache_file)
    if not path.exists():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (now or _utc_now()) - mtime


def _litellm_cache_is_fresh(
    cache_file: str | Path | None = None,
    *,
    refresh_interval_days: int = 7,
    now: datetime | None = None,
) -> bool:
    age = _litellm_cache_age(cache_file, now=now)
    if age is None:
        return False
    interval = max(int(refresh_interval_days or 0), 1)
    return age <= timedelta(days=interval)


async def load_litellm_pricing_catalog(
    *,
    cache_file: str | Path | None = None,
    refresh_interval_days: int = 7,
    force_refresh: bool = False,
    timeout_seconds: float = 3.0,
    verified_at: str | None = None,
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, Any]]:
    path = _litellm_cache_path(cache_file)
    errors: list[str] = []
    refreshed = False
    used_cache = False
    payload: dict[str, Any] = {}

    should_refresh = force_refresh or not _litellm_cache_is_fresh(
        path,
        refresh_interval_days=refresh_interval_days,
    )
    if should_refresh:
        try:
            payload = await fetch_litellm_pricing_payload(timeout_seconds=timeout_seconds)
            _write_litellm_pricing_cache(payload, path)
            refreshed = True
        except Exception as exc:  # noqa: BLE001
            errors.append(f"LiteLLM pricing refresh failed: {exc}")

    if not payload:
        try:
            payload = _read_litellm_pricing_cache(path)
            used_cache = bool(payload)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"LiteLLM pricing cache read failed: {exc}")

    catalog = build_litellm_pricing_catalog(payload, verified_at=verified_at) if payload else {"chat_models": {}, "embedding_models": {}}
    meta = {
        "cache_file": str(path),
        "cache_exists": path.exists(),
        "cache_age_seconds": int((_litellm_cache_age(path) or timedelta()).total_seconds()) if path.exists() else None,
        "refresh_interval_days": max(int(refresh_interval_days or 0), 1),
        "refreshed": refreshed,
        "used_cache": used_cache,
        "errors": errors,
    }
    return catalog, meta


async def build_pricing_catalog_snapshot(
    *,
    include_litellm: bool = True,
    include_openrouter: bool = False,
    litellm_cache_file: str | Path | None = None,
    litellm_refresh_interval_days: int = 7,
    force_litellm_refresh: bool = False,
    litellm_timeout_seconds: float = 3.0,
    openrouter_timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    verified_label = _today_label()
    snapshot = build_bundled_pricing_catalog(verified_at=verified_label)
    sources: list[str] = []
    errors: list[str] = []
    litellm_meta: dict[str, Any] = {}

    if include_litellm:
        litellm_catalog, litellm_meta = await load_litellm_pricing_catalog(
            cache_file=litellm_cache_file,
            refresh_interval_days=litellm_refresh_interval_days,
            force_refresh=force_litellm_refresh,
            timeout_seconds=litellm_timeout_seconds,
            verified_at=verified_label,
        )
        snapshot["chat_models"].update(litellm_catalog.get("chat_models", {}))
        snapshot["embedding_models"].update(litellm_catalog.get("embedding_models", {}))
        errors.extend(str(error) for error in litellm_meta.get("errors", []) if str(error).strip())
        if litellm_catalog.get("chat_models") or litellm_catalog.get("embedding_models"):
            sources.append("LiteLLM GitHub pricing JSON")

    if not sources:
        sources.append(ARIA_PRICING_SOURCE_NAME)

    if include_openrouter:
        try:
            openrouter_catalog = await fetch_openrouter_pricing_catalog(
                timeout_seconds=openrouter_timeout_seconds,
                verified_at=verified_label,
            )
            snapshot["chat_models"].update(openrouter_catalog.get("chat_models", {}))
            snapshot["embedding_models"].update(openrouter_catalog.get("embedding_models", {}))
            sources.append("OpenRouter Models API")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"OpenRouter refresh failed: {exc}")

    snapshot.update(
        {
            "enabled": True,
            "currency": "USD",
            "last_updated": verified_label,
            "default_source_name": ", ".join(sources),
            "default_source_url": LITELLM_PRICING_SOURCE_URL if "LiteLLM GitHub pricing JSON" in sources else ARIA_PRICING_SOURCE_URL,
            "litellm_cache": litellm_meta,
            "errors": errors,
        }
    )
    return snapshot
