"""Website metadata seed helpers."""

from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen


def _extract_html_attribute_map(tag_html: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for match in re.finditer(r'([a-zA-Z_:][\w:.-]*)\s*=\s*(["\'])(.*?)\2', str(tag_html or ""), flags=re.DOTALL):
        key = str(match.group(1) or "").strip().lower()
        if not key:
            continue
        attrs[key] = unescape(str(match.group(3) or "").strip())
    return attrs


def _clean_html_text(value: str, max_length: int = 240) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def extract_website_service_seed(url: str, *, web_metadata_headers: dict[str, str]) -> dict[str, Any]:
    clean_url = str(url or "").strip()
    parsed = urlparse(clean_url)
    host = str(parsed.netloc or "").strip().lower()
    host_short = host[4:] if host.startswith("www.") else host
    fallback_aliases = [value for value in [host_short, host_short.split(".", 1)[0].replace("-", " ")] if value]
    seed = {
        "service_title": host_short or clean_url,
        "service_description": "",
        "keywords": [],
        "host": host_short,
        "aliases": fallback_aliases,
    }
    if not clean_url:
        return seed
    req = URLRequest(clean_url, headers=web_metadata_headers, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            payload = resp.read(256 * 1024)
    except Exception:
        return seed
    text = payload.decode("utf-8", errors="replace").strip()
    if not text:
        return seed

    title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.IGNORECASE | re.DOTALL)
    title = _clean_html_text(title_match.group(1), 120) if title_match else ""
    meta_description = ""
    keywords: list[str] = []
    og_title = ""
    h1_title = ""

    for match in re.finditer(r"<meta\b[^>]*>", text, flags=re.IGNORECASE):
        attrs = _extract_html_attribute_map(match.group(0))
        key = str(attrs.get("name") or attrs.get("property") or "").strip().lower()
        content = _clean_html_text(attrs.get("content", ""), 240)
        if not key or not content:
            continue
        if key in {"description", "og:description", "twitter:description"} and not meta_description:
            meta_description = content
        elif key in {"keywords", "news_keywords"} and not keywords:
            keywords = [item.strip()[:24] for item in re.split(r"[;,]", content) if item.strip()][:8]
        elif key in {"og:title", "twitter:title"} and not og_title:
            og_title = content[:120]

    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", text, flags=re.IGNORECASE | re.DOTALL)
    if h1_match:
        h1_title = _clean_html_text(h1_match.group(1), 120)

    resolved_title = title or og_title or h1_title
    if resolved_title:
        seed["service_title"] = resolved_title
    if meta_description:
        seed["service_description"] = meta_description
    seed["keywords"] = keywords
    return seed
