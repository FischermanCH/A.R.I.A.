"""Passive, user-scoped projections for the owner statistics overview."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aria.modules.activity_journal.store import ActivityJournalStore
from aria.modules.platform_primitives.i18n import I18NStore


_MODEL_PROVIDER_PREFIXES = frozenset({
    "anthropic", "azure", "bedrock", "google", "groq", "huggingface",
    "mistral", "ollama", "openai", "openrouter", "vertex_ai",
})
_STATS_OVERVIEW_I18N = I18NStore(Path(__file__).resolve().parents[3] / "aria" / "i18n")
_COST_DRIVER_LABEL_KEYS = {
    "web_chat": "chat",
    "chat": "chat",
    "native_agent": "agent_jobs",
    "agent_job": "agent_jobs",
    "meta_catalog": "catalog_search",
    "embeddings": "semantic_search",
}


def normalize_model_alias(value: object) -> str:
    raw = str(value or "").strip()
    if "/" not in raw:
        return raw
    prefix, remainder = raw.split("/", 1)
    return remainder if prefix.casefold() in _MODEL_PROVIDER_PREFIXES and remainder else raw


def cost_driver_label(value: object, language: str) -> str:
    label_key = _COST_DRIVER_LABEL_KEYS.get(
        str(value or "").strip().casefold(), "other",
    )
    return _STATS_OVERVIEW_I18N.t(
        language, f"stats.overview.costs.driver_{label_key}", label_key,
    )


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(str(name or "Europe/Zurich"))
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def format_integer(value: object, language: str) -> str:
    raw = f"{int(value or 0):,}"
    return raw.replace(",", ".") if language == "de" else raw


def format_decimal(value: object, language: str, digits: int = 1) -> str:
    raw = f"{float(value or 0.0):,.{digits}f}"
    if language == "de":
        return raw.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return raw


def format_currency(value: object, language: str) -> str:
    amount = format_decimal(value, language, 2)
    return f"US$ {amount}" if language == "de" else f"US${amount}"


def format_percent(value: object, language: str) -> str:
    rendered = format_decimal(value, language, 1)
    return f"{rendered} %" if language == "de" else f"{rendered}%"


def format_bytes(value: object, language: str) -> str:
    size = max(0, int(value or 0))
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    number = float(size)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if number < 1024 or candidate == units[-1]:
            break
        number /= 1024
    digits = 0 if unit == "B" else 1
    return f"{format_decimal(number, language, digits)} {unit}"


def format_local_time(epoch: float, language: str, timezone_name: str) -> str:
    local = datetime.fromtimestamp(float(epoch or 0), tz=timezone.utc).astimezone(_zone(timezone_name))
    return local.strftime("%d.%m.%Y, %H:%M") if language == "de" else local.strftime("%b %d, %Y, %H:%M")


def format_relative_time(epoch: float, language: str, *, now: float | None = None) -> str:
    delta = max(0, int((time.time() if now is None else now) - float(epoch or 0)))
    if delta < 60:
        value, de, en = max(1, delta), "Sek.", "sec"
    elif delta < 3600:
        value, de, en = delta // 60, "Min.", "min"
    elif delta < 86400:
        value, de, en = delta // 3600, "Std.", "hr"
    else:
        value, de, en = delta // 86400, "Tagen", "days"
    return f"vor {value} {de}" if language == "de" else f"{value} {en} ago"


def _iter_json_lines(paths: Iterable[Path]) -> Iterable[dict[str, Any]]:
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue
                    if isinstance(row, dict):
                        yield row
        except OSError:
            continue


def _timestamp(row: dict[str, Any]) -> float | None:
    raw = str(row.get("timestamp") or "").strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass
class StatsUsageAggregation:
    log_path: Path
    timezone_name: str = "Europe/Zurich"
    price_lookup: Callable[[str, str], Any | None] | None = None

    def _paths(self) -> tuple[Path, ...]:
        archives = sorted(self.log_path.parent.glob(f"{self.log_path.stem}-archive-*{self.log_path.suffix}"))
        return (*archives, self.log_path)

    def build(self, *, language: str, now: float | None = None) -> dict[str, Any]:
        current = float(time.time() if now is None else now)
        zone = _zone(self.timezone_name)
        local_now = datetime.fromtimestamp(current, tz=timezone.utc).astimezone(zone)
        today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        seven_start = (local_now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        month_start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()
        chart_start = (local_now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        periods = {
            "today": {"start": today_start, "cost": 0.0, "estimated": 0.0, "chat": 0.0, "embedding": 0.0, "tokens": 0, "unpriced_tokens": 0},
            "seven_days": {"start": seven_start, "cost": 0.0, "estimated": 0.0, "chat": 0.0, "embedding": 0.0, "tokens": 0, "unpriced_tokens": 0},
            "month": {"start": month_start, "cost": 0.0, "estimated": 0.0, "chat": 0.0, "embedding": 0.0, "tokens": 0, "unpriced_tokens": 0},
        }
        daily: dict[str, float] = defaultdict(float)
        model_costs: Counter[str] = Counter()
        source_costs: Counter[str] = Counter()
        seen: set[tuple[str, str]] = set()
        for row in _iter_json_lines(self._paths()):
            epoch = _timestamp(row)
            if epoch is None or epoch < min(chart_start, month_start, seven_start):
                continue
            identity = (str(row.get("request_id") or ""), str(row.get("timestamp") or ""))
            if identity in seen:
                continue
            seen.add(identity)
            chat_cost_raw = row.get("chat_cost_usd")
            embedding_cost_raw = row.get("embedding_cost_usd")
            total_cost_raw = row.get("total_cost_usd")
            chat_cost = float(chat_cost_raw) if isinstance(chat_cost_raw, (int, float)) else 0.0
            embedding_cost = float(embedding_cost_raw) if isinstance(embedding_cost_raw, (int, float)) else 0.0
            total_cost = float(total_cost_raw) if isinstance(total_cost_raw, (int, float)) else chat_cost + embedding_cost
            current_estimate = total_cost
            if self.price_lookup is not None:
                current_estimate = 0.0
                chat_model_for_price = str(row.get("chat_model") or "").strip()
                embedding_model_for_price = str(row.get("embedding_model") or "").strip()
                chat_price = self.price_lookup("chat", chat_model_for_price) if chat_model_for_price else None
                embedding_price = self.price_lookup("embedding", embedding_model_for_price) if embedding_model_for_price else None
                if chat_price is not None:
                    current_estimate += (
                        max(0, int(row.get("prompt_tokens", 0) or 0)) * float(getattr(chat_price, "input_per_million", 0.0) or 0.0)
                        + max(0, int(row.get("completion_tokens", 0) or 0)) * float(getattr(chat_price, "output_per_million", 0.0) or 0.0)
                    ) / 1_000_000
                elif isinstance(chat_cost_raw, (int, float)):
                    current_estimate += chat_cost
                if embedding_price is not None:
                    current_estimate += max(0, int(row.get("embedding_prompt_tokens", row.get("embedding_total_tokens", 0)) or 0)) * float(getattr(embedding_price, "input_per_million", 0.0) or 0.0) / 1_000_000
                elif isinstance(embedding_cost_raw, (int, float)):
                    current_estimate += embedding_cost
            tokens = max(0, int(row.get("total_tokens", 0) or 0)) + max(0, int(row.get("embedding_total_tokens", 0) or 0))
            unpriced = tokens if not isinstance(total_cost_raw, (int, float)) else 0
            day_key = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(zone).date().isoformat()
            if epoch >= chart_start:
                daily[day_key] += total_cost
            for data in periods.values():
                if epoch >= float(data["start"]):
                    data["cost"] += total_cost
                    data["estimated"] += current_estimate
                    data["chat"] += chat_cost
                    data["embedding"] += embedding_cost
                    data["tokens"] += tokens
                    data["unpriced_tokens"] += unpriced
            chat_model = normalize_model_alias(row.get("chat_model"))
            embedding_model = normalize_model_alias(row.get("embedding_model"))
            if chat_model:
                model_costs[f"{chat_model} · Chat"] += chat_cost
            if embedding_model:
                model_costs[f"{embedding_model} · Embedding"] += embedding_cost
            source = str(row.get("source") or "chat").strip() or "chat"
            source_costs[source] += total_cost

        chart: list[dict[str, Any]] = []
        for offset in range(30):
            day = (local_now - timedelta(days=29 - offset)).date()
            value = float(daily.get(day.isoformat(), 0.0))
            chart.append({"date": day.isoformat(), "label": day.strftime("%d.%m." if language == "de" else "%b %d"), "cost": value})
        maximum = max((row["cost"] for row in chart), default=0.0) or 1.0
        for index, row in enumerate(chart):
            row["x"] = 22 + index * 19
            row["height"] = max(2, int(126 * row["cost"] / maximum)) if row["cost"] else 0
            row["y"] = 146 - row["height"]
            row["formatted"] = format_currency(row["cost"], language)
        chart_maximum = maximum if maximum != 1.0 or any(row["cost"] for row in chart) else 0.0
        y_ticks = [
            {"value": chart_maximum, "y": 20, "label": format_currency(chart_maximum, language)},
            {"value": chart_maximum / 2, "y": 83, "label": format_currency(chart_maximum / 2, language)},
            {"value": 0.0, "y": 146, "label": format_currency(0.0, language)},
        ]
        x_ticks = [
            {"x": row["x"] + 6, "label": datetime.fromisoformat(row["date"]).strftime("%d.%m")}
            for index, row in enumerate(chart)
            if index % 5 == 0 or index == len(chart) - 1
        ]
        for data in periods.values():
            data["cost_label"] = format_currency(data["cost"], language)
            data["estimated_label"] = format_currency(data["estimated"], language)
            data["token_label"] = format_integer(data["tokens"], language)
        return {
            "periods": periods,
            "chart": chart,
            "y_ticks": y_ticks,
            "x_ticks": x_ticks,
            "chart_min": format_currency(min((row["cost"] for row in chart), default=0.0), language),
            "chart_max": format_currency(chart_maximum, language),
            "models": [{"name": name, "cost": format_currency(cost, language)} for name, cost in sorted(model_costs.items(), key=lambda item: (-item[1], item[0].casefold()))],
            "drivers": [{
                "key": name,
                "name": cost_driver_label(name, language),
                "share": format_percent(
                    (cost / sum(source_costs.values()) * 100) if sum(source_costs.values()) else 0,
                    language,
                ),
            } for name, cost in source_costs.most_common(3)],
        }


@dataclass
class StatsActivityAggregation:
    journal_path: Path
    job_store: Any
    enabled: bool = True

    def build(self, *, user_id: str, language: str, now: float | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "empty": True, "turns": 0, "corrections": 0, "jobs_done": 0, "jobs_cancelled": 0, "errors": 0, "error_rate": format_percent(0, language), "top_tools": [], "connections": [], "servers": [], "latest": ""}
        cutoff = float(time.time() if now is None else now) - 7 * 86400
        rows = ActivityJournalStore(self.journal_path).query(user_id, since=cutoff, limit=10_000)
        tools: Counter[str] = Counter()
        connections: Counter[str] = Counter()
        servers: Counter[str] = Counter()
        for row in rows:
            tools.update({str(name): int(count or 1) for name, count in dict(row.get("tools") or {}).items()})
            connections.update(str(value) for value in (*row.get("connection_kinds", ()), *row.get("connection_refs", ())))
            servers.update(str(value) for value in row.get("mcp_servers", ()))
        jobs = tuple(self.job_store.list_for_user(user_id, limit=1000)) if self.job_store is not None else ()
        jobs = tuple(row for row in jobs if float(getattr(row, "updated_at", 0.0) or 0.0) >= cutoff)
        errors = sum(1 for row in rows if row.get("outcome_status") in {"error", "interrupted"})
        latest = max((float(row.get("finished_at") or 0.0) for row in rows), default=0.0)
        return {
            "enabled": True,
            "empty": not rows and not jobs,
            "turns": len(rows),
            "corrections": sum(1 for row in rows if row.get("corrected")),
            "jobs_done": sum(1 for row in jobs if getattr(row, "status", "") == "done"),
            "jobs_cancelled": sum(1 for row in jobs if getattr(row, "status", "") == "cancelled"),
            "errors": errors,
            "error_rate": format_percent((errors / len(rows) * 100) if rows else 0, language),
            "top_tools": [{"name": name, "count": count} for name, count in tools.most_common(4)],
            "connections": [{"name": name, "count": count} for name, count in connections.most_common(3)],
            "servers": [{"name": name, "count": count} for name, count in servers.most_common(3)],
            "latest": latest,
        }


@dataclass
class StatsHealthSnapshot:
    cache_path: Path

    def build(self, *, language: str, preflight: dict[str, Any] | None = None) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        checked_at = 0.0
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            checked_at = float(payload.get("saved_at") or self.cache_path.stat().st_mtime)
            cached_rows = payload.get("rows", [])
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            cached_rows = []
        for row in cached_rows if isinstance(cached_rows, list) else []:
            status = str(row.get("status") or "").lower()
            message = str(row.get("message") or "")
            if status == "warn" and any(term in message.casefold() for term in ("never", "noch nie", "not checked")):
                continue
            if status in {"warn", "error"}:
                rows.append({"status": status, "name": str(row.get("display_name") or row.get("ref") or row.get("kind") or "Connection"), "message": message, "url": str(row.get("edit_url") or "/connections/status")})
        preflight = dict(preflight or {})
        if preflight and str(preflight.get("status") or "ok").lower() not in {"", "ok", "passed"}:
            rows.append({"status": "warn", "name": "startup_preflight", "message": "stale", "url": "/config/logs"})
        return {"status": "ok" if not rows else ("error" if any(row["status"] == "error" for row in rows) else "warn"), "issues": rows, "checked_at": checked_at or time.time()}


_RESOURCE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass
class StatsResourceSnapshot:
    project_root: Path
    ttl_seconds: int = 60

    @staticmethod
    def _size(path: Path) -> int:
        if path.is_file():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        total = 0
        try:
            for child in path.rglob("*"):
                if child.is_file():
                    try:
                        total += child.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    @staticmethod
    def _ram() -> tuple[int, int]:
        rss = 0
        total = 0
        try:
            statm = Path("/proc/self/statm").read_text(encoding="utf-8").split()
            rss = int(statm[1]) * int(os.sysconf("SC_PAGE_SIZE"))  # type: ignore[name-defined]
            for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1]) * 1024
        except (OSError, ValueError, IndexError):
            pass
        return rss, total

    def build(self, *, language: str, now: float | None = None) -> dict[str, Any]:
        current = float(time.time() if now is None else now)
        # The numeric snapshot is shared, but the cached projection already
        # contains locale-formatted labels. Keep one entry per locale so an
        # EN request can never inherit DE decimal separators (or vice versa).
        key = f"{self.project_root.resolve()}:{language}"
        cached = _RESOURCE_CACHE.get(key)
        if cached and current - cached[0] <= self.ttl_seconds:
            result = dict(cached[1])
            result["cached"] = True
            return result
        runtime = self.project_root / "data" / "runtime"
        traces = self.project_root / "data" / "modules" / "native_agent"
        configured_qdrant = os.getenv("ARIA_QDRANT_STORAGE_PATH", "").strip()
        container_qdrant = Path("/qdrant/storage")
        qdrant = (
            Path(configured_qdrant)
            if configured_qdrant
            else container_qdrant if container_qdrant.exists()
            else self.project_root / "data" / "qdrant"
        )
        collections_root = qdrant / "collections"
        document_bytes = sum(
            self._size(path)
            for path in collections_root.glob("aria_doc*")
            if path.is_dir()
        ) if collections_root.exists() else 0
        rss, total_ram = self._ram()
        raw = {
            "rss": rss,
            "rss_percent": (rss / total_ram * 100) if total_ram else 0.0,
            "qdrant": self._size(qdrant),
            "qdrant_collections": sum(1 for path in collections_root.glob("*") if path.is_dir()) if collections_root.exists() else 0,
            "journal": self._size(runtime / "activity_journal.sqlite3"),
            "jobs": self._size(runtime / "agent_jobs.sqlite3"),
            "traces": self._size(traces),
            "documents": document_bytes,
            "captured_at": current,
            "cached": False,
        }
        history_path = runtime / "stats_resource_history.json"
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            history = history if isinstance(history, list) else []
        except (OSError, ValueError, json.JSONDecodeError):
            history = []
        day = datetime.fromtimestamp(current, tz=timezone.utc).date().isoformat()
        point = {"day": day, **{name: raw[name] for name in ("qdrant", "journal", "jobs", "traces", "documents")}}
        history = [row for row in history if isinstance(row, dict) and str(row.get("day")) != day][-34:] + [point]
        try:
            history_path.parent.mkdir(parents=True, exist_ok=True)
            temp = history_path.with_suffix(".tmp")
            temp.write_text(json.dumps(history, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
            temp.replace(history_path)
        except OSError:
            pass
        oldest = history[0] if history else point
        distinct_days = {str(row.get("day", "")) for row in history if isinstance(row, dict)}
        growth_ready = len(distinct_days) >= 2
        rows = []
        for name in ("journal", "jobs", "traces", "documents"):
            rows.append({"name": name, "bytes": raw[name], "size": format_bytes(raw[name], language), "growth": format_bytes(max(0, raw[name] - int(oldest.get(name, raw[name]) or 0)), language)})
        result = {
            **raw,
            "rss_label": format_bytes(rss, language),
            "rss_percent_label": format_percent(raw["rss_percent"], language),
            "qdrant_label": format_bytes(raw["qdrant"], language),
            "rows": rows,
            "growth_ready": growth_ready,
            "growth_since": str(oldest.get("day", day) or day),
        }
        _RESOURCE_CACHE[key] = (current, dict(result))
        return result


@dataclass
class StatsOverviewSnapshot:
    health: dict[str, Any]
    usage: dict[str, Any]
    activity: dict[str, Any]
    resources: dict[str, Any]
    freshness: str
    freshness_absolute: str


def build_cost_svg_description(usage: dict[str, Any], language: str) -> str:
    low = usage.get("chart_min", format_currency(0, language))
    high = usage.get("chart_max", format_currency(0, language))
    if language == "de":
        return f"Die protokollierten Tageskosten liegen zwischen {low} und {high}."
    return f"Recorded daily costs range from {low} to {high}."
