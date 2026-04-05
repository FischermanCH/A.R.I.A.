from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request as URLRequest
from urllib.request import urlopen


GITHUB_REPO = "FischermanCH/A.R.I.A."
GITHUB_TAGS_API = f"https://api.github.com/repos/{GITHUB_REPO}/tags?per_page=20"
GITHUB_CHANGELOG_RAW = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/CHANGELOG.md"
UPDATE_CHECK_CACHE = Path("data/runtime/update_status.json")

_RELEASE_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([a-z]+)\.?(\d+)?)?$", re.IGNORECASE)
_CHANGELOG_HEADING_RE = re.compile(r"^## \[([^\]]+)\]")


def normalize_release_label(value: str) -> str:
    text = str(value or "").strip()
    match = _RELEASE_RE.match(text)
    if not match:
        return text
    major, minor, patch, prerelease, prerelease_num = match.groups()
    normalized = f"{int(major)}.{int(minor)}.{int(patch)}"
    if prerelease:
        normalized += f"-{str(prerelease).lower()}"
        if prerelease_num:
            normalized += str(int(prerelease_num))
    return normalized


def release_sort_key(value: str) -> tuple[int, int, int, int, int]:
    text = normalize_release_label(value)
    match = _RELEASE_RE.match(text)
    if not match:
        return (0, 0, 0, -1, -1)
    major, minor, patch, prerelease, prerelease_num = match.groups()
    prerelease_rank = 99
    prerelease_index = 0
    if prerelease:
        label = str(prerelease).lower()
        prerelease_rank = 0 if label == "alpha" else 1
        prerelease_index = int(prerelease_num or 0)
    return (int(major), int(minor), int(patch), prerelease_rank, prerelease_index)


def is_newer_release(candidate: str, current: str) -> bool:
    return release_sort_key(candidate) > release_sort_key(current)


def extract_changelog_section(changelog_text: str, release_label: str) -> str:
    target = normalize_release_label(release_label)
    if not target:
        return ""
    lines = str(changelog_text or "").splitlines()
    section: list[str] = []
    collecting = False
    for line in lines:
        heading_match = _CHANGELOG_HEADING_RE.match(line.strip())
        if heading_match:
            heading_label = normalize_release_label(heading_match.group(1))
            if collecting:
                break
            if heading_label == target:
                collecting = True
        if collecting:
            section.append(line.rstrip())
    return "\n".join(section).strip()


def _cache_path(base_dir: Path) -> Path:
    path = (base_dir / UPDATE_CHECK_CACHE).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _default_status(current_label: str) -> dict[str, Any]:
    normalized_current = normalize_release_label(current_label)
    return {
        "current_label": normalized_current,
        "latest_label": normalized_current,
        "latest_tag": "",
        "update_available": False,
        "checked_at": "",
        "source": "github-tags",
        "release_notes": "",
        "release_notes_source": GITHUB_CHANGELOG_RAW,
        "error": "",
    }


def _load_cache(base_dir: Path) -> dict[str, Any] | None:
    path = _cache_path(base_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _save_cache(base_dir: Path, payload: dict[str, Any]) -> None:
    path = _cache_path(base_dir)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fetch_json(url: str, *, timeout: float = 1.2) -> Any:
    request = URLRequest(
        url,
        headers={
            "User-Agent": "ARIA Update Check/1.0",
            "Accept": "application/vnd.github+json, application/json;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_text(url: str, *, timeout: float = 1.2) -> str:
    request = URLRequest(
        url,
        headers={
            "User-Agent": "ARIA Update Check/1.0",
            "Accept": "text/plain, text/markdown;q=0.9, */*;q=0.5",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def refresh_update_status(base_dir: Path, *, current_label: str) -> dict[str, Any]:
    status = _default_status(current_label)
    payload = _fetch_json(GITHUB_TAGS_API)
    if not isinstance(payload, list):
        raise ValueError("GitHub tags response is not a list.")
    candidates: list[tuple[tuple[int, int, int, int, int], str, str]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        raw_name = str(row.get("name", "") or "").strip()
        normalized_name = normalize_release_label(raw_name)
        if not normalized_name:
            continue
        key = release_sort_key(normalized_name)
        if key == (0, 0, 0, -1, -1):
            continue
        candidates.append((key, raw_name, normalized_name))
    if not candidates:
        raise ValueError("No usable GitHub tags found.")
    _, latest_tag, latest_label = max(candidates, key=lambda item: item[0])
    status["latest_tag"] = latest_tag
    status["latest_label"] = latest_label
    status["update_available"] = is_newer_release(latest_label, status["current_label"])
    changelog_text = _fetch_text(GITHUB_CHANGELOG_RAW)
    status["release_notes"] = extract_changelog_section(changelog_text, latest_label)
    status["checked_at"] = datetime.now(timezone.utc).isoformat()
    return status


def get_update_status(base_dir: Path, *, current_label: str, ttl_seconds: int = 60 * 60 * 6) -> dict[str, Any]:
    normalized_current = normalize_release_label(current_label)
    cached = _load_cache(base_dir)
    now = time.time()
    if cached:
        cached_checked_at = str(cached.get("checked_at", "") or "").strip()
        try:
            checked_at = datetime.fromisoformat(cached_checked_at).timestamp() if cached_checked_at else 0.0
        except ValueError:
            checked_at = 0.0
        if (
            str(cached.get("current_label", "") or "").strip() == normalized_current
            and checked_at > 0
            and (now - checked_at) <= max(60, int(ttl_seconds or 0))
        ):
            return cached
    try:
        fresh = refresh_update_status(base_dir, current_label=normalized_current)
        _save_cache(base_dir, fresh)
        return fresh
    except (OSError, URLError, ValueError, TimeoutError) as exc:
        if cached:
            cached["current_label"] = normalized_current
            cached["update_available"] = is_newer_release(str(cached.get("latest_label", "") or ""), normalized_current)
            cached["error"] = str(exc)
            cached["checked_at"] = datetime.now(timezone.utc).isoformat()
            _save_cache(base_dir, cached)
            return cached
        fallback = _default_status(normalized_current)
        fallback["error"] = str(exc)
        fallback["checked_at"] = datetime.now(timezone.utc).isoformat()
        _save_cache(base_dir, fallback)
        return fallback
