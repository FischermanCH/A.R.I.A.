from __future__ import annotations

import json
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start : end + 1])
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _normalize_group_name(name: str) -> str:
    clean = re.sub(r"\s+", " ", str(name or "").strip())
    if not clean:
        return "Weitere Feeds"
    clean = clean[:32].strip(" -_:,")
    if not clean:
        return "Weitere Feeds"
    return clean


def _fallback_group_name(ref: str, feed_url: str) -> str:
    sample = f"{ref} {feed_url}".lower()
    keyword_groups = (
        ("Security", ("security", "sec", "cve", "threat", "incident", "cert", "zero-day", "malware", "cyber")),
        ("Infrastruktur", ("infra", "ops", "devops", "server", "network", "linux", "cloud", "kubernetes", "proxmox", "vmware")),
        ("Entwicklung", ("dev", "developer", "programming", "python", "javascript", "java", "rust", "go", "git", "api")),
        ("KI & Daten", ("ai", "llm", "openai", "machine-learning", "analytics", "vector", "qdrant")),
        ("News & Tech", ("news", "heise", "golem", "tech", "digital", "computer", "hardware", "software")),
        ("Monitoring", ("monitor", "alert", "status", "uptime", "observability", "prometheus", "grafana")),
        ("Business", ("finance", "wirtschaft", "market", "startup", "business", "management")),
    )
    for group_name, keywords in keyword_groups:
        if any(keyword in sample for keyword in keywords):
            return group_name

    parsed = urlparse(feed_url)
    host = str(parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host:
        head = host.split(".")[0].replace("-", " ").strip()
        if head:
            return head.title()
    return "Weitere Feeds"


def _build_group_rows(status_rows: list[dict[str, Any]], group_map: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in status_rows:
        ref = str(row.get("ref", "")).strip()
        grouped[group_map.get(ref) or "Weitere Feeds"].append(row)

    result: list[dict[str, Any]] = []
    for group_name, rows in grouped.items():
        sorted_rows = sorted(rows, key=lambda item: (item.get("status") != "error", item.get("ref", "")))
        result.append(
            {
                "name": _normalize_group_name(group_name),
                "rows": sorted_rows,
                "total": len(sorted_rows),
                "healthy": sum(1 for item in sorted_rows if item.get("status") == "ok"),
                "issues": sum(1 for item in sorted_rows if item.get("status") == "error"),
            }
        )
    result.sort(key=lambda item: item["name"].lower())
    return result


def _group_map_from_cached_groups(groups: list[dict[str, Any]]) -> dict[str, str]:
    group_map: dict[str, str] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        group_name = _normalize_group_name(str(group.get("name", "")).strip())
        rows = group.get("rows", [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            ref = str(row.get("ref", "")).strip()
            if ref:
                group_map[ref] = group_name
    return group_map


async def build_rss_status_groups(status_rows: list[dict[str, Any]], llm_client: Any | None = None) -> list[dict[str, Any]]:
    rows = [row for row in status_rows if isinstance(row, dict) and str(row.get("ref", "")).strip()]
    if not rows:
        return []

    fallback_map = {
        str(row.get("ref", "")).strip(): _normalize_group_name(
            str(row.get("group_name", "")).strip()
        )
        if str(row.get("group_name", "")).strip()
        else _fallback_group_name(
            str(row.get("ref", "")).strip(),
            str(row.get("target", "")).strip(),
        )
        for row in rows
    }

    auto_rows = [row for row in rows if not str(row.get("group_name", "")).strip()]
    if llm_client is None or len(auto_rows) < 5:
        return _build_group_rows(rows, fallback_map)

    prompt_lines = []
    for row in auto_rows:
        ref = str(row.get("ref", "")).strip()
        feed_url = str(row.get("target", "")).strip()
        prompt_lines.append(f"- ref: {ref} | url: {feed_url}")

    system_prompt = (
        "Du gruppierst RSS-Feed-Profile thematisch fuer eine UI. "
        "Antworte nur als JSON-Objekt im Format "
        '{"groups": [{"name": "Security", "refs": ["feed-a", "feed-b"]}]}. '
        "Nutze kurze, klare Kategorienamen auf Deutsch. "
        "Jeder Ref muss genau einmal vorkommen. Keine Erklaerungen."
    )
    user_prompt = "\n".join(
        [
            "Gruppiere diese RSS-Feeds thematisch fuer eine kompakte UI:",
            *prompt_lines,
        ]
    )

    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            source="rss_grouping",
            operation="group_feeds",
            user_id="system",
        )
        payload = _extract_json_object(getattr(response, "content", "") or "") or {}
        raw_groups = payload.get("groups", [])
        llm_map: dict[str, str] = {}
        if isinstance(raw_groups, list):
            for item in raw_groups:
                if not isinstance(item, dict):
                    continue
                group_name = _normalize_group_name(str(item.get("name", "")).strip())
                refs = item.get("refs", [])
                if not isinstance(refs, list):
                    continue
                for ref in refs:
                    clean_ref = str(ref or "").strip()
                    if clean_ref:
                        llm_map[clean_ref] = group_name
        if llm_map:
            locked_map = {
                str(row.get("ref", "")).strip(): _normalize_group_name(
                    str(row.get("group_name", "")).strip()
                )
                for row in rows
                if str(row.get("ref", "")).strip() and str(row.get("group_name", "")).strip()
            }
            merged_map = {**fallback_map, **llm_map, **locked_map}
            return _build_group_rows(rows, merged_map)
    except Exception:
        pass

    return _build_group_rows(rows, fallback_map)


def _rss_signature(status_rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "ref": str(row.get("ref", "")).strip(),
            "target": str(row.get("target", "")).strip(),
            "group_name": _normalize_group_name(str(row.get("group_name", "")).strip())
            if str(row.get("group_name", "")).strip()
            else "",
            "status": str(row.get("status", "")).strip(),
        }
        for row in sorted(status_rows, key=lambda item: str(item.get("ref", "")))
        if isinstance(row, dict)
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_cached_rss_status_groups(cache_path: Path, status_rows: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("signature", "")).strip() != _rss_signature(status_rows):
        return None
    groups = payload.get("groups", [])
    if not isinstance(groups, list):
        return None
    cached_group_map = _group_map_from_cached_groups(groups)
    if not cached_group_map:
        return None
    return _build_group_rows(status_rows, cached_group_map)


def save_cached_rss_status_groups(cache_path: Path, status_rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signature": _rss_signature(status_rows),
        "groups": groups,
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
