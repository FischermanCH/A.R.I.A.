"""Safe projections into the activity-journal authority."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import logging
import re
import time
from typing import Any, Mapping, Sequence

from .store import ActivityJournalStore


LOGGER = logging.getLogger(__name__)
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_ -]?key|authorization|bearer|token|secret|password|passwd|cookie|webhook_url)(\s*[:=]\s*)[^\s,;)}\]]+"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"(?i)(https://discord(?:app)?\.com/api/webhooks/)[^\s'\",}]+"),
    re.compile(r"(?i)\b(?:Bearer\s+)[A-Za-z0-9._~+/-]{8,}=*"),
)
_SAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.:@/-]+")
_TEMPLATE_PREFIXES = (
    "# memory compression template", "memory compression template", "behalte nur",
    "entferne ", "eintraege:", "eintr\u00e4ge:",
)
_LIST_PREFIX_RE = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+|>\s*|#{1,6}\s*)")
_MARKDOWN_LINK_RE = re.compile(r"!?\[([^\]]+)\]\([^\)]+\)")
_MARKDOWN_DECORATION_RE = re.compile(r"(?<!\\)[`*_~]+")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?(?:\s*\|\s*:?-{3,}:?)+\s*\|?\s*$")


def redact_text(value: object, *, limit: int) -> tuple[str, int]:
    text = " ".join(str(value or "").split())
    redacted = 0
    for pattern in _SECRET_PATTERNS:
        text, count = pattern.subn(
            lambda match: (match.group(1) + (match.group(2) if match.lastindex and match.lastindex >= 2 else "") + "[REDACTED]")
            if match.lastindex else "[REDACTED]",
            text,
        )
        redacted += count
    if len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text, redacted


def plain_text_summary(value: object, *, limit: int) -> tuple[str, int]:
    """Redact and flatten Markdown into a compact human-readable sentence."""

    raw_lines = str(value or "").replace("\r", "").splitlines()
    table_headers: list[str] = []
    output: list[str] = []
    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("```") or _TABLE_SEPARATOR_RE.match(line):
            continue
        if "|" in line:
            cells = [
                _MARKDOWN_DECORATION_RE.sub("", cell.strip())
                for cell in line.strip("|").split("|")
            ]
            if not table_headers:
                table_headers = cells
                continue
            pairs = [
                f"{header}: {cell}" for header, cell in zip(table_headers, cells)
                if header and cell
            ]
            if pairs:
                output.append("; ".join(pairs))
                continue
        line = _LIST_PREFIX_RE.sub("", line)
        line = _MARKDOWN_LINK_RE.sub(r"\1", line)
        line = _MARKDOWN_DECORATION_RE.sub("", line)
        line = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|>])", r"\1", line)
        line = " ".join(line.replace("|", "; ").split()).strip()
        if line:
            output.append(line)
    return redact_text(" · ".join(output), limit=limit)


def _safe_id(value: object, limit: int = 160) -> str:
    return _SAFE_ID_RE.sub("_", str(value or "").strip())[:limit].strip("_")


def _entry_id(prefix: str, user_id: str, authority_id: str) -> str:
    digest = hashlib.sha256(f"{prefix}\0{user_id}\0{authority_id}".encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:32]}"


def _mcp_servers(tool_names: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({
        parts[1]
        for name in tool_names
        if len(parts := str(name).split("__", 2)) == 3 and parts[0] == "mcp" and parts[1]
    }))


def _inferred_connection_kinds(tool_names: Sequence[str]) -> tuple[str, ...]:
    result: set[str] = set()
    for name in tool_names:
        clean = str(name).strip().casefold()
        if clean.startswith("mcp__"):
            result.add("mcp")
            continue
        for kind in ("ssh", "sftp", "smb", "discord", "webhook", "smtp", "imap", "http_api", "rss", "mqtt", "google_calendar", "website"):
            if clean.startswith(kind + "_"):
                result.add(kind)
                break
    return tuple(sorted(result))


def build_turn_entry(
    *, user_id: str, turn_id: str, started_at: float, finished_at: float,
    goal: str, used_tool_names: Sequence[str], outcome_status: str,
    outcome_phrase: str, connection_kinds: Sequence[str] = (),
    connection_refs: Sequence[str] = (), confirmations: Mapping[str, int] | None = None,
    corrected: bool = False, usage: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    tools = Counter(_safe_id(name) for name in used_tool_names if _safe_id(name))
    if not tools or set(tools) == {"activity_journal_read"}:
        return None
    safe_goal, goal_redactions = plain_text_summary(goal, limit=300)
    safe_outcome, outcome_redactions = plain_text_summary(outcome_phrase, limit=300)
    if goal_redactions or outcome_redactions:
        LOGGER.info(
            "Activity journal projection redacted fields count=%d",
            goal_redactions + outcome_redactions,
        )
    kinds = {_safe_id(value, 80) for value in connection_kinds if _safe_id(value, 80)}
    kinds.update(_inferred_connection_kinds(tuple(tools)))
    measured = dict(usage or {})
    return {
        "id": _entry_id("turn", user_id, turn_id), "user_id": str(user_id),
        "started_at": float(started_at), "finished_at": float(finished_at),
        "kind": "turn", "job_id": "", "goal": safe_goal, "tools": dict(tools),
        "connection_kinds": sorted(kinds),
        "connection_refs": sorted({_safe_id(value) for value in connection_refs if _safe_id(value)}),
        "mcp_servers": list(_mcp_servers(tuple(tools))), "outcome_status": outcome_status,
        "confirmations": dict(confirmations or {}), "corrected": bool(corrected),
        "outcome_phrase": safe_outcome, "source": "live", "keep": False,
        "input_tokens": max(0, int(measured.get("input_tokens", 0) or 0)),
        "output_tokens": max(0, int(measured.get("output_tokens", 0) or 0)),
        "embedding_tokens": max(0, int(measured.get("embedding_tokens", 0) or 0)),
        "cost_usd": measured.get("cost_usd"),
        "_redaction_count": goal_redactions + outcome_redactions,
    }


def build_job_entry(record: Any) -> dict[str, Any]:
    tool_names = tuple(
        str(name)
        for step in tuple(getattr(record, "step_log", ()) or ())
        for name in tuple(dict(step).get("tool_names", ()) or ())
    )
    status = str(getattr(record, "status", "error") or "error")
    outcome_status = {
        "done": "ok", "error": "error", "cancelled": "cancelled", "interrupted": "interrupted",
    }.get(status, "error")
    if status == "error" and str(getattr(record, "result", "") or "") == "worker_restart":
        outcome_status = "interrupted"
    user_id = str(getattr(record, "user_id", ""))
    safe_goal, goal_redactions = plain_text_summary(getattr(record, "goal", ""), limit=300)
    safe_outcome, outcome_redactions = plain_text_summary(
        getattr(record, "result", "") or outcome_status, limit=300,
    )
    if goal_redactions or outcome_redactions:
        LOGGER.info(
            "Activity journal job projection redacted fields count=%d",
            goal_redactions + outcome_redactions,
        )
    tools = Counter(_safe_id(name) for name in tool_names if _safe_id(name))
    measured = dict(getattr(record, "usage", None) or {})
    return {
        "id": _entry_id("job", user_id, str(getattr(record, "job_id", ""))),
        "user_id": user_id,
        "started_at": float(getattr(record, "created_at", time.time()) or time.time()),
        "finished_at": float(getattr(record, "updated_at", time.time()) or time.time()),
        "kind": "job", "job_id": _safe_id(getattr(record, "job_id", "")),
        "goal": safe_goal, "tools": dict(tools),
        "connection_kinds": sorted(set(_inferred_connection_kinds(tuple(tools))) | set(getattr(record, "connection_kinds", ()) or ())),
        "connection_refs": sorted(set(getattr(record, "connection_refs", ()) or ())),
        "mcp_servers": sorted(set(_mcp_servers(tuple(tools))) | set(getattr(record, "mcp_servers", ()) or ())),
        "outcome_status": outcome_status,
        "outcome_phrase": safe_outcome,
        "confirmations": {
            "asked": int(getattr(record, "confirmation_asked", 0) or 0),
            "approved": int(getattr(record, "confirmation_approved", 0) or 0),
            "rejected": int(getattr(record, "confirmation_rejected", 0) or 0),
        },
        "corrected": bool(getattr(record, "corrected", False)),
        "source": "live", "keep": False,
        "input_tokens": max(0, int(measured.get("input_tokens", 0) or 0)),
        "output_tokens": max(0, int(measured.get("output_tokens", 0) or 0)),
        "embedding_tokens": max(0, int(measured.get("embedding_tokens", 0) or 0)),
        "cost_usd": measured.get("cost_usd"),
        "_redaction_count": goal_redactions + outcome_redactions,
    }


def _slug_user_id(user_id: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id).strip().lower())
    return re.sub(r"_+", "_", clean).strip("_") or "web"


def _legacy_row_matches(user_id: str, row: Mapping[str, Any]) -> bool:
    collection = str(row.get("collection") or "").strip()
    base = f"aria_context-mem_{_slug_user_id(user_id)}"
    return bool(
        str(row.get("source") or "").strip().casefold() == "compression"
        and (collection == base or collection.startswith(base + "_dim_"))
        and (not str(row.get("user_id") or "").strip() or str(row.get("user_id")).strip() == str(user_id))
    )


def _legacy_lines(text: object) -> tuple[list[str], int]:
    lines: list[str] = []
    seen: set[str] = set()
    redactions = 0
    for raw in str(text or "").splitlines():
        clean = " ".join(raw.split()).strip()
        semantic = clean
        while True:
            stripped = _LIST_PREFIX_RE.sub("", semantic).strip()
            if stripped == semantic:
                break
            semantic = stripped
        if not semantic or semantic.casefold().startswith(_TEMPLATE_PREFIXES):
            continue
        safe, count = redact_text(semantic, limit=1000)
        redactions += count
        if safe.casefold() not in seen:
            seen.add(safe.casefold())
            lines.append(safe)
    complete = tuple(line.casefold() for line in lines if not line.rstrip().endswith("-"))
    lines = [
        line for line in lines
        if not line.rstrip().endswith("-")
        or not any(value.startswith(line.casefold().rstrip("-")) for value in complete)
    ]
    return lines, redactions


def _join_legacy_lines(lines: Sequence[str], *, limit: int = 1000) -> str:
    result: list[str] = []
    used = 0
    for raw in lines:
        line = " ".join(str(raw).split()).strip()
        if not line:
            continue
        separator = 1 if result else 0
        if used + separator + len(line) > limit:
            remaining = limit - used - separator
            if remaining > 1:
                candidate = line[: remaining - 1].rstrip()
                if " " in candidate:
                    candidate = candidate.rsplit(" ", 1)[0].rstrip(" -–—,;:")
                if candidate:
                    result.append(candidate + "…")
            break
        result.append(line)
        used += separator + len(line)
    return "\n".join(result)


def _without_truncated_prefixes(lines: Sequence[str]) -> list[str]:
    complete = tuple(str(line).casefold() for line in lines if not str(line).rstrip().endswith("-"))
    return [
        str(line) for line in lines
        if not str(line).rstrip().endswith("-")
        or not any(value.startswith(str(line).casefold().rstrip("-")) for value in complete)
    ]


def _legacy_level(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("rollup_level") or "").strip().casefold()
    if explicit in {"week", "month"}:
        return explicit
    return "week" if re.search(r"-W\d{1,2}$", str(row.get("rollup_bucket") or ""), re.I) else "month"


def legacy_rollup_projection(user_id: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if not _legacy_row_matches(user_id, row):
        raise ValueError("legacy_rollup_user_scope_mismatch")
    collection = str(row.get("collection") or "").strip()
    point_id = str(row.get("id") or "").strip()
    period_start = str(row.get("rollup_period_start") or "").strip()
    period_end = str(row.get("rollup_period_end") or "").strip()
    timestamp = time.time()
    for candidate in (period_end, period_start, str(row.get("timestamp") or "")):
        try:
            timestamp = datetime.fromisoformat(candidate.replace("Z", "+00:00")).replace(tzinfo=timezone.utc).timestamp() if len(candidate) == 10 else datetime.fromisoformat(candidate.replace("Z", "+00:00")).timestamp()
            break
        except (TypeError, ValueError):
            continue
    lines, redacted = _legacy_lines(row.get("text"))
    outcome = _join_legacy_lines(lines)
    if redacted:
        LOGGER.info("Activity journal legacy projection redacted fields count=%d", redacted)
    return {
        "id": _entry_id("legacy", user_id, f"{collection}:{point_id}"),
        "user_id": str(user_id), "started_at": timestamp, "finished_at": timestamp,
        "kind": "legacy", "job_id": "",
        "goal": str(row.get("rollup_bucket") or "Legacy context rollup")[:300],
        "tools": {}, "connection_kinds": [], "connection_refs": [], "mcp_servers": [],
        "outcome_status": "ok", "confirmations": {}, "corrected": False,
        "outcome_phrase": outcome, "source": "legacy_context_rollup", "keep": True,
        "legacy_collection": collection, "legacy_point_id": point_id,
        "legacy_sources": [{"collection": collection, "point_id": point_id}],
        "legacy_level": _legacy_level(row),
        "legacy_bucket": str(row.get("rollup_bucket") or "").strip(),
        "period_start": period_start, "period_end": period_end,
        "_legacy_lines": lines,
        "_redaction_count": redacted,
    }


async def list_legacy_rollups(memory_skill: Any, *, user_id: str) -> list[dict[str, Any]]:
    rows = await memory_skill.list_memories_global(
        user_id=user_id, type_filter="knowledge", limit=10000,
    )
    projected = [
        legacy_rollup_projection(user_id, row)
        for row in rows if _legacy_row_matches(user_id, row)
    ]
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for row in projected:
        key = (
            str(row["legacy_level"]), str(row["legacy_bucket"]),
            str(row["period_start"]), str(row["period_end"]),
        )
        grouped.setdefault(key, []).append(row)

    combined: list[dict[str, Any]] = []
    week_period_lines: list[tuple[str, str, set[str]]] = []
    ordered = sorted(grouped.items(), key=lambda item: (item[0][0] == "month", item[0]))
    for (level, bucket, period_start, period_end), members in ordered:
        lines: list[str] = []
        seen: set[str] = set()
        sources: list[dict[str, str]] = []
        redactions = 0
        for member in members:
            redactions += int(member.get("_redaction_count") or 0)
            sources.extend(dict(source) for source in member.get("legacy_sources", ()))
            for line in member.get("_legacy_lines", ()):
                key = str(line).casefold()
                if key and key not in seen:
                    seen.add(key)
                    lines.append(str(line))
        lines = _without_truncated_prefixes(lines)
        if level == "month":
            covered = {
                value
                for week_start, week_end, values in week_period_lines
                if (not period_end or not week_start or week_start <= period_end)
                and (not period_start or not week_end or week_end >= period_start)
                for value in values
            }
            lines = [line for line in lines if line.casefold() not in covered]
            if not lines:
                continue
        else:
            week_period_lines.append((
                period_start, period_end, {line.casefold() for line in lines},
            ))
        first = members[0]
        authority = f"{level}:{bucket}:{period_start}:{period_end}"
        combined.append({
            **{key: value for key, value in first.items() if not key.startswith("_")},
            "id": _entry_id("legacy", user_id, authority),
            "goal": bucket or ("Weekly context rollup" if level == "week" else "Monthly context rollup"),
            "outcome_phrase": _join_legacy_lines(lines),
            "legacy_sources": sorted(
                sources, key=lambda source: (source.get("collection", ""), source.get("point_id", "")),
            ),
            "legacy_level": level,
            "legacy_bucket": bucket,
            "period_start": period_start,
            "period_end": period_end,
            "_redaction_count": redactions,
        })
    return combined


async def migrate_legacy_rollups(
    store: ActivityJournalStore, memory_skill: Any, *, user_id: str,
) -> dict[str, int]:
    rows = await list_legacy_rollups(memory_skill, user_id=user_id)
    existing = store.query(user_id, source="legacy_context_rollup", limit=10_000)
    unmatched = {str(row["id"]): row for row in existing}
    created = updated = unchanged = 0
    duplicate_ids: list[str] = []
    for row in rows:
        source_keys = {
            (str(source.get("collection") or ""), str(source.get("point_id") or ""))
            for source in row.get("legacy_sources", ())
        }
        matches: list[dict[str, Any]] = []
        for candidate in existing:
            candidate_sources = {
                (str(source.get("collection") or ""), str(source.get("point_id") or ""))
                for source in candidate.get("legacy_sources", ())
            } or {(
                str(candidate.get("legacy_collection") or ""),
                str(candidate.get("legacy_point_id") or ""),
            )}
            same_rollup = (
                str(candidate.get("period_start") or "") == str(row.get("period_start") or "")
                and str(candidate.get("period_end") or "") == str(row.get("period_end") or "")
                and str(candidate.get("goal") or "") == str(row.get("goal") or "")
            )
            if source_keys & candidate_sources or same_rollup:
                matches.append(candidate)
        chosen_id = str(matches[0]["id"]) if matches else str(row["id"])
        result = store.upsert_legacy(row, entry_id=chosen_id)
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            unchanged += 1
        unmatched.pop(chosen_id, None)
        duplicate_ids.extend(str(value["id"]) for value in matches[1:])
        for value in matches[1:]:
            unmatched.pop(str(value["id"]), None)

    current_source_keys = {
        (str(source.get("collection") or ""), str(source.get("point_id") or ""))
        for row in rows for source in row.get("legacy_sources", ())
    }
    for stale_id, candidate in unmatched.items():
        candidate_keys = {
            (str(source.get("collection") or ""), str(source.get("point_id") or ""))
            for source in candidate.get("legacy_sources", ())
        } or {(
            str(candidate.get("legacy_collection") or ""),
            str(candidate.get("legacy_point_id") or ""),
        )}
        if candidate_keys & current_source_keys:
            duplicate_ids.append(stale_id)
    store.delete_legacy_entries(user_id, duplicate_ids)
    return {
        "found": len(rows), "created": created, "updated": updated,
        "existing": unchanged,
    }


async def delete_migrated_legacy_rollups(
    store: ActivityJournalStore, memory_skill: Any, *, user_id: str,
) -> int:
    removed = 0
    for row in store.query(user_id, source="legacy_context_rollup", limit=10_000):
        sources = list(row.get("legacy_sources") or ()) or [{
            "collection": row.get("legacy_collection"), "point_id": row.get("legacy_point_id"),
        }]
        for source in sources:
            collection = str(source.get("collection") or "")
            point_id = str(source.get("point_id") or "")
            if not collection or not point_id:
                continue
            if await memory_skill.delete_memory_point(
                user_id=user_id, collection=collection, point_id=point_id,
            ):
                removed += 1
    return removed
