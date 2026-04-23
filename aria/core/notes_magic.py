from __future__ import annotations

from dataclasses import dataclass
import html
import re
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen


_WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TAG_STOPWORDS = {
    "aber", "about", "auch", "calendar", "dass", "dein", "deine", "deiner", "deinen", "dem", "den", "der", "des",
    "die", "eine", "einer", "einen", "einem", "eines", "etwas", "fuer", "google", "have", "hier", "html", "https", "http",
    "ich", "ist", "mit", "nach", "nicht", "note", "notiz", "oder", "page", "save", "schreib", "seite", "soll", "source",
    "that", "this", "und", "unter", "von", "vom", "web", "website", "wie", "wir", "you", "zum", "zur",
}


@dataclass(frozen=True)
class WebNoteSource:
    url: str
    title: str
    description: str
    snippet: str
    tags: list[str]


def infer_note_title(body: str) -> str:
    text = re.sub(r"\s+", " ", str(body or "")).strip()
    if not text:
        return "Neue Notiz"
    first = re.split(r"(?<=[.!?])\s+|\n+", text, maxsplit=1)[0].strip(" -:;,.")
    return (first[:80] or "Neue Notiz").strip()


def infer_note_folder(title: str, body: str, *, tags: list[str] | None = None, source_url: str = "") -> str:
    haystack = " ".join([str(title or ""), str(body or ""), str(source_url or ""), " ".join(tags or [])]).lower()
    mapping = (
        (("projekt", "project", "roadmap", "release"), "Projekte"),
        (("idee", "idea", "brainstorm"), "Ideen"),
        (("todo", "task", "aufgabe", "checkliste"), "Aufgaben"),
        (("meeting", "call", "besprechung"), "Meetings"),
        (("research", "recherche", "quelle", "source", "docs", "documentation", "guide", "oauth"), "Recherche"),
        (("server", "infra", "ssh", "docker", "qdrant", "searxng"), "Betrieb"),
    )
    for terms, folder in mapping:
        if any(term in haystack for term in terms):
            return folder
    return ""


def infer_note_tags(*parts: str, limit: int = 8) -> list[str]:
    text = " ".join(str(part or "") for part in parts)
    rows: list[str] = []
    seen: set[str] = set()
    for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9+._/-]{1,24}", text.lower()):
        clean = token.strip("-._/")
        if len(clean) < 3 or clean in _TAG_STOPWORDS:
            continue
        if clean.startswith("www"):
            continue
        if clean not in seen:
            seen.add(clean)
            rows.append(clean)
        if len(rows) >= limit:
            break
    return rows


def fetch_web_note_source(url: str) -> WebNoteSource:
    clean_url = str(url or "").strip()
    if not clean_url:
        raise ValueError("URL fehlt.")
    req = URLRequest(clean_url, headers=_WEB_HEADERS, method="GET")
    with urlopen(req, timeout=12) as resp:  # noqa: S310
        payload = resp.read(256 * 1024)
    text = payload.decode("utf-8", errors="replace")

    title = _clean_html_text(_first_match(text, r"<title[^>]*>(.*?)</title>"), 120)
    meta_description = ""
    meta_keywords: list[str] = []
    og_title = ""
    for match in re.finditer(r"<meta\b[^>]*>", text, flags=re.IGNORECASE):
        attrs = _extract_html_attribute_map(match.group(0))
        key = str(attrs.get("name") or attrs.get("property") or "").strip().lower()
        content = _clean_html_text(attrs.get("content", ""), 240)
        if not key or not content:
            continue
        if key in {"description", "og:description", "twitter:description"} and not meta_description:
            meta_description = content
        elif key in {"og:title", "twitter:title"} and not og_title:
            og_title = content[:120]
        elif key in {"keywords", "news_keywords"} and not meta_keywords:
            meta_keywords = [item.strip()[:24].lower() for item in re.split(r"[;,]", content) if item.strip()][:8]

    h1_title = _clean_html_text(_first_match(text, r"<h1[^>]*>(.*?)</h1>"), 120)
    resolved_title = title or og_title or h1_title or _fallback_title_from_url(clean_url)
    snippet = meta_description or _clean_html_text(_first_match(text, r"<p[^>]*>(.*?)</p>"), 280)
    tags = meta_keywords or infer_note_tags(resolved_title, meta_description, clean_url)
    return WebNoteSource(
        url=clean_url,
        title=resolved_title,
        description=meta_description,
        snippet=snippet,
        tags=tags,
    )


def _fallback_title_from_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    host = str(parsed.netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host or str(url or "").strip()


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text or "", flags=re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else ""


def _clean_html_text(value: str, limit: int) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].strip()


def _extract_html_attribute_map(raw_tag: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for key, _quote, content in re.findall(r'([a-zA-Z_:.-]+)\s*=\s*(["\'])(.*?)\2', str(raw_tag or ""), flags=re.DOTALL):
        attrs[str(key or "").lower()] = html.unescape(str(content or ""))
    return attrs
