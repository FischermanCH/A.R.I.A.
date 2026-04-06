from __future__ import annotations

from datetime import date
from functools import lru_cache
import re
from types import SimpleNamespace
from typing import Any

import httpx
import litellm


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
OPENAI_PRICING_SOURCE_URL = "https://platform.openai.com/docs/pricing"
ANTHROPIC_PRICING_SOURCE_URL = "https://www.anthropic.com/pricing"
OPENROUTER_PRICING_SOURCE_URL = "https://openrouter.ai/docs/api-reference/list-available-models"


def _today_label() -> str:
    return date.today().isoformat()


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


def _litellm_price_row(model_name: str, payload: dict[str, Any], *, provider: str, verified_at: str) -> tuple[str, dict[str, Any]] | None:
    mode = str(payload.get("mode", "") or "").strip().lower()
    if mode not in {"chat", "completion", "embedding"}:
        return None

    source_name = "LiteLLM model_cost"
    source_url = OPENAI_PRICING_SOURCE_URL if provider == "openai" else ANTHROPIC_PRICING_SOURCE_URL
    notes = f"provider={provider}; source=litellm.model_cost"
    if mode == "embedding":
        return model_name, {
            "input_per_million": _safe_float(payload.get("input_cost_per_token")) * 1_000_000,
            "source_name": source_name,
            "source_url": source_url,
            "verified_at": verified_at,
            "notes": notes,
        }
    return model_name, {
        "input_per_million": _safe_float(payload.get("input_cost_per_token")) * 1_000_000,
        "output_per_million": _safe_float(payload.get("output_cost_per_token")) * 1_000_000,
        "source_name": source_name,
        "source_url": source_url,
        "verified_at": verified_at,
        "notes": notes,
    }


def build_litellm_pricing_catalog(*, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
    verified_label = str(verified_at or "").strip() or _today_label()
    chat_models: dict[str, dict[str, Any]] = {}
    embedding_models: dict[str, dict[str, Any]] = {}
    for model_name, payload in dict(getattr(litellm, "model_cost", {}) or {}).items():
        if not isinstance(payload, dict):
            continue
        provider = str(payload.get("litellm_provider", "") or "").strip().lower()
        if provider not in {"openai", "anthropic"}:
            continue
        row = _litellm_price_row(str(model_name or "").strip(), payload, provider=provider, verified_at=verified_label)
        if row is None:
            continue
        model_key, entry = row
        target = embedding_models if "output_per_million" not in entry else chat_models
        for alias in _model_aliases(model_key):
            target.setdefault(alias, dict(entry))
            if provider in {"openai", "anthropic"}:
                target.setdefault(f"{provider}/{alias}", dict(entry))

    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
    }


@lru_cache(maxsize=1)
def _cached_litellm_pricing_catalog() -> dict[str, dict[str, dict[str, Any]]]:
    return build_litellm_pricing_catalog(verified_at=_today_label())


def resolve_litellm_pricing_entry(model_name: str) -> Any | None:
    clean = str(model_name or "").strip()
    if not clean:
        return None

    catalog = _cached_litellm_pricing_catalog()
    for table_name in ("chat_models", "embedding_models"):
        rows = catalog.get(table_name, {})
        if clean in rows and isinstance(rows[clean], dict):
            return SimpleNamespace(**rows[clean])
        lowered = {str(key).strip().lower(): value for key, value in rows.items()}
        entry = lowered.get(clean.lower())
        if isinstance(entry, dict):
            return SimpleNamespace(**entry)
        normalized_rows = {_normalize_lookup_key(str(key)): value for key, value in rows.items()}
        normalized_entry = normalized_rows.get(_normalize_lookup_key(clean))
        if isinstance(normalized_entry, dict):
            return SimpleNamespace(**normalized_entry)
        fallback_entry = _resolve_claude_family_fallback(rows, clean)
        if fallback_entry is not None:
            return fallback_entry
    return None


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


async def fetch_openrouter_pricing_catalog(*, timeout_seconds: float = 12.0, verified_at: str | None = None) -> dict[str, dict[str, dict[str, Any]]]:
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


async def build_pricing_catalog_snapshot(*, include_openrouter: bool = True) -> dict[str, Any]:
    verified_label = _today_label()
    snapshot = build_litellm_pricing_catalog(verified_at=verified_label)
    sources = ["OpenAI/Anthropic via LiteLLM"]
    errors: list[str] = []

    if include_openrouter:
        try:
            openrouter_catalog = await fetch_openrouter_pricing_catalog(verified_at=verified_label)
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
            "default_source_url": OPENROUTER_PRICING_SOURCE_URL if include_openrouter else OPENAI_PRICING_SOURCE_URL,
            "errors": errors,
        }
    )
    return snapshot
