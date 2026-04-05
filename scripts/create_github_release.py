from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO = os.getenv("GITHUB_REPOSITORY", "FischermanCH/A.R.I.A.")
API_BASE = f"https://api.github.com/repos/{REPO}"
CHANGELOG_PATH = Path(__file__).resolve().parents[1] / "CHANGELOG.md"
TAG_RE = re.compile(r"^v?(\d+\.\d+\.\d+(?:-[a-z]+\.\d+|-[a-z]+\d+)?)$", re.IGNORECASE)
SECTION_RE = re.compile(r"^## \[([^\]]+)\]")


def normalize_tag(tag: str) -> str:
    raw = str(tag or "").strip()
    if not raw:
        raise ValueError("Missing tag.")
    return raw if raw.startswith("v") else f"v{raw}"


def normalize_release_label(tag: str) -> str:
    raw = str(tag or "").strip()
    if raw.startswith("v"):
        raw = raw[1:]
    return raw.replace("-alpha.", "-alpha")


def changelog_section(label: str) -> str:
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    target = normalize_release_label(label)
    lines = text.splitlines()
    section: list[str] = []
    collecting = False
    for line in lines:
        match = SECTION_RE.match(line.strip())
        if match:
            heading = normalize_release_label(match.group(1))
            if collecting:
                break
            if heading == target:
                collecting = True
        if collecting:
            section.append(line.rstrip())
    result = "\n".join(section).strip()
    if not result:
        raise ValueError(f"No changelog section found for {label}.")
    return result


def github_request(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    body = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ARIA release helper",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: create_github_release.py <tag>", file=sys.stderr)
        return 2

    token = str(os.getenv("GITHUB_TOKEN", "")).strip()
    if not token:
        print("GITHUB_TOKEN is missing.", file=sys.stderr)
        return 2

    tag = normalize_tag(sys.argv[1])
    if not TAG_RE.match(tag):
        print(f"Unsupported tag format: {tag}", file=sys.stderr)
        return 2

    body = changelog_section(tag)
    payload = {
        "tag_name": tag,
        "name": tag,
        "body": body,
        "draft": False,
        "prerelease": True,
        "generate_release_notes": False,
    }

    try:
        result = github_request("POST", f"{API_BASE}/releases", token, payload)
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        print(f"GitHub API error: {exc.code} {exc.reason}\n{error_body}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1

    print(result.get("html_url", "Release created."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
