from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
import asyncio
import inspect
from pathlib import Path
import re
from typing import Any
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen

from aria.core.i18n import I18NStore
from aria.core.notes_context import NotesContextHit, note_context_block, note_context_detail_lines
from aria.core.config import resolve_searxng_base_url
from aria.core.searxng_client import SearXNGClient, SearXNGClientError
from aria.skills.base import BaseSkill, SkillResult

_WEB_SEARCH_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _profile_rows_from_settings(settings: Any) -> dict[str, Any]:
    rows = getattr(getattr(settings, "connections", object()), "searxng", {})
    return rows if isinstance(rows, dict) else {}


def _profile_value(profile: Any, key: str, default: Any = "") -> Any:
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


def _profile_list(profile: Any, key: str, *, limit: int = 20, max_chars: int = 80) -> list[str]:
    raw = _profile_value(profile, key, [])
    if isinstance(raw, list):
        values = raw
    else:
        values = str(raw or "").split(",")
    rows: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = re.sub(r"\s+", " ", str(item or "").strip())[:max_chars]
        if not text:
            continue
        marker = text.lower()
        if marker in seen:
            continue
        seen.add(marker)
        rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def build_web_search_profile_options(settings: Any, *, limit: int = 12) -> list[dict[str, Any]]:
    rows = _profile_rows_from_settings(settings)
    options: list[dict[str, Any]] = []
    for ref in sorted(str(key) for key in rows.keys() if str(key).strip()):
        profile = rows.get(ref, {})
        options.append(
            {
                "ref": ref[:120],
                "title": str(_profile_value(profile, "title", "") or ref).strip()[:160],
                "description": re.sub(r"\s+", " ", str(_profile_value(profile, "description", "") or "").strip())[:260],
                "tags": _profile_list(profile, "tags", limit=12, max_chars=80),
                "aliases": _profile_list(profile, "aliases", limit=12, max_chars=80),
                "categories": _profile_list(profile, "categories", limit=12, max_chars=40),
                "engines": _profile_list(profile, "engines", limit=20, max_chars=60),
                "language": str(_profile_value(profile, "language", "") or "").strip()[:40],
                "safe_search": str(_profile_value(profile, "safe_search", "") or "").strip()[:20],
                "time_range": str(_profile_value(profile, "time_range", "") or "").strip()[:40],
                "max_results": int(_profile_value(profile, "max_results", 5) or 5),
            }
        )
        if len(options) >= limit:
            break
    return options


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "br", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag.lower() in {"p", "li", "h1", "h2", "h3", "h4", "section", "article"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth <= 0:
            clean = re.sub(r"\s+", " ", str(data or "")).strip()
            if clean:
                self._parts.append(clean)

    def text(self) -> str:
        raw = " ".join(self._parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        raw = re.sub(r"\s*\n\s*", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def _default_page_fetcher(url: str, timeout_seconds: int) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "ARIA-WebResearch/1.0 (+https://github.com/FischermanCH/A.R.I.A.)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.2",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - user-configured web research fetcher
        content_type = str(response.headers.get("content-type", "") or "").lower()
        if content_type and not any(marker in content_type for marker in ("html", "text", "xml")):
            return ""
        payload = response.read(750_000)
    return payload.decode("utf-8", errors="replace")


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Runs a web search via a configured SearXNG instance."
    max_context_chars = 6000

    def __init__(self, *, settings: Any, client: SearXNGClient | None = None, page_fetcher: Any | None = None):
        self.settings = settings
        self.client = client or SearXNGClient()
        self.page_fetcher = page_fetcher or _default_page_fetcher

    @staticmethod
    def _is_english(language: str | None) -> bool:
        return str(language or "").strip().lower().startswith("en")

    @classmethod
    def _text(cls, language: str | None, key: str, default: str = "", **values: object) -> str:
        template = _WEB_SEARCH_I18N.t(language or "de", f"web_search.{key}", default or key)
        if not values:
            return template
        try:
            return template.format(**values)
        except Exception:
            return template

    @classmethod
    def _terms(cls, key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
        raw = cls._text("de", key, ",".join(fallback))
        terms = tuple(item.strip().lower() for item in raw.split(",") if item.strip())
        return terms or fallback

    _QUERY_STOPWORDS = frozenset({
        "a",
        "an",
        "and",
        "bot",
        "comparison",
        "current",
        "difference",
        "differences",
        "for",
        "feature",
        "features",
        "in",
        "internet",
        "last",
        "latest",
        "model",
        "new",
        "newest",
        "news",
        "online",
        "official",
        "previous",
        "release",
        "releases",
        "search",
        "spec",
        "specs",
        "specification",
        "specifications",
        "the",
        "update",
        "updates",
        "web",
        "what",
    })

    _VERSION_QUERY_TERMS = (
        "aktuelle version",
        "aktuellste version",
        "neuste version",
        "neueste version",
        "momentan aktuell",
        "current version",
        "latest version",
        "latest release",
        "newest release",
        "changelog",
        "release notes",
    )

    _REGISTRY_DOMAINS = (
        "npmjs.com",
        "pypi.org",
        "crates.io",
        "packagist.org",
        "rubygems.org",
        "hub.docker.com",
        "ghcr.io",
    )

    _NEWS_DOMAINS = (
        "appgefahren.de",
        "computerbase.de",
        "heise.de",
        "itmagazine.ch",
        "it-daily.net",
        "n-tv.de",
        "runnersworld.de",
        "t3n.de",
        "zeit.de",
        "bernerzeitung.ch",
    )

    _SOURCE_NOISE_TERMS = (
        "deal",
        "deals",
        "prime day",
        "sale",
        "rabatt",
        "discount",
        "coupon",
        "shopping",
        "geruecht",
        "geruechte",
        "gerücht",
        "gerüchte",
        "rumor",
        "rumour",
        "rumors",
        "rumours",
        "leak",
        "leaks",
        "expected",
        "expectations",
    )

    _SITE_QUERY_RE = re.compile(r"(?:^|\s)site:([^\s]+)", re.IGNORECASE)

    @staticmethod
    def _profile_rows(settings: Any) -> dict[str, Any]:
        return _profile_rows_from_settings(settings)

    @staticmethod
    def _profile_value(profile: Any, key: str, default: Any = "") -> Any:
        return _profile_value(profile, key, default)

    @classmethod
    def _profile_list(cls, profile: Any, key: str) -> list[str]:
        return _profile_list(profile, key)

    @classmethod
    def _profile_by_ref(cls, rows: dict[str, Any], profile_ref: str) -> tuple[str, Any] | None:
        clean_ref = str(profile_ref or "").strip().lower()
        if not clean_ref:
            return None
        for ref, profile in rows.items():
            if str(ref or "").strip().lower() == clean_ref:
                return str(ref), profile
        return None

    def _select_profile(self, query: str, explicit_ref: str = "") -> tuple[str, Any] | None:
        rows = self._profile_rows(self.settings)
        if not rows:
            return None
        clean_query = str(query or "").strip().lower()
        if str(explicit_ref or "").strip():
            return self._profile_by_ref(rows, explicit_ref)

        scored: list[tuple[int, str, Any]] = []
        for ref, profile in rows.items():
            score = 0
            if ref.lower() in clean_query:
                score += 5
            title = str(self._profile_value(profile, "title", "")).strip()
            if title and title.lower() in clean_query:
                score += 4
            for alias in self._profile_list(profile, "aliases"):
                alias_text = str(alias).strip().lower()
                if alias_text and alias_text in clean_query:
                    score += 3
            for tag in self._profile_list(profile, "tags"):
                tag_text = str(tag).strip().lower()
                if tag_text and tag_text in clean_query:
                    score += 1
            scored.append((score, str(ref), profile))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if scored:
            return scored[0][1], scored[0][2]
        first_ref = sorted(rows.keys())[0]
        return first_ref, rows[first_ref]

    @classmethod
    def _detail_line(cls, language: str | None, title: str, url: str, engine: str, published_label: str = "") -> str:
        parts = [f"{cls._text(language, 'source_label', 'Source')}: {title}"]
        if url:
            parts.append(url)
        if engine:
            parts.append(engine)
        if published_label:
            parts.append(published_label)
        return " · ".join(parts)

    @staticmethod
    def _is_recency_query(query: str) -> bool:
        text = str(query or "").strip().lower()
        if not text:
            return False
        return any(
            token in text
            for token in (
                "latest",
                "newest",
                "most recent",
                "recent",
                "release",
                "update",
            ) + WebSearchSkill._terms("recency_terms", ())
        )

    @classmethod
    def _is_news_query(cls, query: str) -> bool:
        text = str(query or "").strip().lower()
        return any(term in text for term in ("news", "nachrichten", "meldungen", "headlines"))

    @classmethod
    def _is_current_version_query(cls, query: str) -> bool:
        text = re.sub(r"\s+", " ", str(query or "").strip().lower())
        if not text:
            return False
        return any(term in text for term in cls._VERSION_QUERY_TERMS)

    @staticmethod
    def _published_sort_value(published_at: str) -> float:
        clean = str(published_at or "").strip()
        if not clean:
            return 0.0
        try:
            return datetime.fromisoformat(clean.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    @classmethod
    def _query_terms(cls, query: str) -> list[str]:
        tokens = re.findall(r"[a-z0-9]+", str(query or "").lower())
        kept: list[str] = []
        seen: set[str] = set()
        for token in tokens:
            if token in cls._QUERY_STOPWORDS or token in cls._terms("query_stopwords", ()):
                continue
            if len(token) < 3 and not any(char.isdigit() for char in token):
                continue
            if token not in seen:
                seen.add(token)
                kept.append(token)
        return kept

    @classmethod
    def _query_phrases(cls, query: str) -> list[str]:
        terms = cls._query_terms(query)
        if len(terms) < 2:
            return []
        return [" ".join(terms[idx : idx + 2]) for idx in range(0, len(terms) - 1)]

    @classmethod
    def _result_relevance_score(cls, query: str, result: Any) -> tuple[int, int]:
        terms = cls._query_terms(query)
        title = str(getattr(result, "title", "") or "").lower()
        snippet = str(getattr(result, "snippet", "") or "").lower()
        url = str(getattr(result, "url", "") or "").lower()
        parsed = urlparse(url)
        domain = str(parsed.netloc or "").lower()
        path = str(parsed.path or "").lower()

        score = 0
        matches = 0
        for term in terms:
            matched = False
            if term in title:
                score += 6
                matched = True
            elif term in domain or term in path:
                score += 4
                matched = True
            elif term in snippet:
                score += 3
                matched = True
            if matched:
                matches += 1

        combined = " ".join(part for part in (title, snippet, url) if part)
        for phrase in cls._query_phrases(query):
            if phrase and phrase in combined:
                score += 5

        return score, matches

    @classmethod
    def _source_quality_score(cls, query: str, result: Any) -> int:
        if not cls._is_current_version_query(query):
            return 0
        title = str(getattr(result, "title", "") or "").lower()
        snippet = str(getattr(result, "snippet", "") or "").lower()
        url = str(getattr(result, "url", "") or "").lower()
        parsed = urlparse(url)
        domain = str(parsed.netloc or "").lower()
        path = str(parsed.path or "").lower()
        combined = " ".join(part for part in (title, snippet, url) if part)

        score = 0
        if "github.com" in domain and any(marker in path for marker in ("/releases", "/tags")):
            score += 28
        elif "github.com" in domain and any(marker in combined for marker in ("release", "changelog", "tag")):
            score += 18

        if any(registry in domain for registry in cls._REGISTRY_DOMAINS):
            score += 24
            if any(marker in path for marker in ("/package/", "/project/", "/packages/")):
                score += 6

        official_markers = ("docs.", "developer.", "dev.", "changelog", "release-notes", "releases", "download")
        if any(marker in domain or marker in path for marker in official_markers):
            score += 12
        if any(marker in title for marker in ("release", "releases", "changelog", "version", "versions")):
            score += 6

        if "mozilla.org" in domain and "manifest.json/version" in path:
            score -= 20

        return score

    @classmethod
    def _source_authority_label(
        cls,
        query: str,
        result: Any,
        source_plan: dict[str, Any],
    ) -> tuple[str, str]:
        required_sites = cls._source_plan_search_sites(source_plan)
        if required_sites and any(cls._result_matches_site_target(result, site) for site in required_sites):
            return "required_source", "required_site"

        preferred_sites = cls._source_plan_preferred_domains(source_plan)
        if preferred_sites and any(cls._result_matches_site_target(result, site) for site in preferred_sites):
            return "preferred_source", "preferred_domain"

        score = cls._source_quality_score(query, result)
        if score >= 18:
            return "strong_secondary", f"quality_score={score}"
        if cls._result_is_noise_source(result):
            return "noise", "noise_source"
        return "weak_secondary", f"quality_score={score}"

    @classmethod
    def _source_authority_summary(
        cls,
        query: str,
        results: list[Any],
        source_plan: dict[str, Any],
    ) -> tuple[list[dict[str, str]], dict[str, Any], list[str]]:
        labels: list[dict[str, str]] = []
        for result in results:
            label, reason = cls._source_authority_label(query, result, source_plan)
            labels.append({"label": label, "reason": reason})

        required_or_preferred = sum(1 for item in labels if item["label"] in {"required_source", "preferred_source"})
        strong_secondary = sum(1 for item in labels if item["label"] == "strong_secondary")
        weak_secondary = sum(1 for item in labels if item["label"] == "weak_secondary")
        noise = sum(1 for item in labels if item["label"] == "noise")

        if required_or_preferred:
            outcome = "preferred_sources"
            guidance = ""
        elif strong_secondary:
            outcome = "strong_secondary_only"
            guidance = (
                "Source authority: strong_secondary_only. No preferred/official source matched; "
                "answer from secondary sources, mark exact latest/current claims as source-limited, "
                "and avoid presenting them as official confirmation."
            )
        else:
            outcome = "weak_only"
            guidance = (
                "Source authority: weak_only. No preferred/official or strong secondary source matched; "
                "answer cautiously, avoid definitive latest/current claims, and state that the web evidence is weak."
            )

        detail = (
            "Routing Debug: web_source_authority "
            f"outcome={outcome} preferred_or_required={required_or_preferred} "
            f"strong_secondary={strong_secondary} weak_secondary={weak_secondary} noise={noise}"
        )
        return labels, {"outcome": outcome, "guidance": guidance}, [detail]

    def _prepare_results(self, query: str, results: list[Any]) -> list[Any]:
        prepared = list(results)
        recency_query = self._is_recency_query(query)
        current_version_query = self._is_current_version_query(query)
        scored: list[tuple[int, int, int, float, int, Any]] = []
        has_relevant_match = False
        for item in prepared:
            score, matches = self._result_relevance_score(query, item)
            if matches > 0:
                has_relevant_match = True
            scored.append(
                (
                    self._source_quality_score(query, item),
                    score,
                    matches,
                    self._published_sort_value(getattr(item, "published_at", "")),
                    1 if "news" in str(getattr(item, "engine", "") or "").lower() else 0,
                    item,
                )
            )

        if has_relevant_match:
            scored = [row for row in scored if row[2] > 0]

        if current_version_query:
            scored.sort(
                key=lambda row: (
                    row[0] > 0,
                    max(row[0], 0),
                    row[2],
                    row[1],
                    row[3] if recency_query else 0.0,
                    -row[4],
                ),
                reverse=True,
            )
        else:
            scored.sort(
                key=lambda row: (
                    row[2],
                    row[1],
                    row[3] if recency_query else 0.0,
                    row[4] if recency_query else 0,
                ),
                reverse=True,
            )
        return [row[5] for row in scored]

    @staticmethod
    def _clean_url(value: str) -> str:
        clean = str(value or "").strip().strip(".,;!?)\"]}'")
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return clean

    @classmethod
    def _explicit_urls(cls, query: str) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for match in re.finditer(r"https?://[^\s<>()\"']+", str(query or ""), flags=re.IGNORECASE):
            url = cls._clean_url(match.group(0))
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls

    @classmethod
    def _result_fetch_candidates(cls, query: str, ordered_results: list[Any]) -> list[str]:
        seen: set[str] = set()
        candidates: list[str] = []
        for url in cls._explicit_urls(query):
            base, _fragment = urldefrag(url)
            key = url.lower()
            seen.add(key)
            if base:
                seen.add(base.lower())
            candidates.append(url)

        def add_result_url(result: Any) -> None:
            url = cls._clean_url(str(getattr(result, "url", "") or ""))
            if not url:
                return
            base, _fragment = urldefrag(url)
            key = (base or url).lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(url)

        for result in ordered_results[:2]:
            add_result_url(result)

        if len(candidates) < 3:
            terms = set(cls._query_terms(query))
            domain_rows: list[tuple[int, Any]] = []
            for result in ordered_results[2:]:
                url = cls._clean_url(str(getattr(result, "url", "") or ""))
                if not url:
                    continue
                parsed = urlparse(url)
                domain = str(parsed.netloc or "").lower()
                path = str(parsed.path or "").lower()
                score = sum(1 for term in terms if term and (term in domain or term in path))
                if score > 0:
                    domain_rows.append((score, result))
            domain_rows.sort(key=lambda item: item[0], reverse=True)
            for _score, result in domain_rows:
                if len(candidates) >= 3:
                    break
                add_result_url(result)
        return candidates[:3]

    @staticmethod
    def _html_to_text(html: str) -> str:
        parser = _VisibleTextParser()
        try:
            parser.feed(str(html or ""))
            parser.close()
        except Exception:
            return re.sub(r"\s+", " ", str(html or "")).strip()
        return parser.text()

    @classmethod
    def _anchor_html_window(cls, html: str, fragment: str) -> str:
        clean_fragment = str(fragment or "").strip()
        if not clean_fragment:
            return str(html or "")
        pattern = re.compile(
            rf"""(?:id|name)\s*=\s*["']{re.escape(clean_fragment)}["']""",
            flags=re.IGNORECASE,
        )
        match = pattern.search(str(html or ""))
        if not match:
            return str(html or "")
        start = max(0, match.start() - 1200)
        end = min(len(html), match.start() + 24_000)
        return html[start:end]

    @classmethod
    def _relevant_page_excerpt(cls, html: str, *, query: str, url: str, max_chars: int = 1800) -> str:
        _base, fragment = urldefrag(url)
        scoped_html = cls._anchor_html_window(html, fragment)
        text = cls._html_to_text(scoped_html)
        if not text:
            return ""
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        if not lines:
            return ""

        terms = cls._query_terms(query)
        focus_terms = set(terms + ["speaker", "speakers", "talk", "talks", "agenda", "schedule", "topic", "topics", "vortrag", "themen"])
        best_index = 0
        best_score = -1
        for idx, line in enumerate(lines):
            lower = line.lower()
            score = sum(1 for term in focus_terms if term and term in lower)
            if fragment and fragment.lower() in lower:
                score += 8
            if score > best_score:
                best_score = score
                best_index = idx

        start = max(0, best_index - 4)
        selected: list[str] = []
        total = 0
        for line in lines[start:]:
            if total + len(line) + 1 > max_chars:
                break
            selected.append(line)
            total += len(line) + 1
            if total >= max_chars:
                break
        return "\n".join(selected).strip()

    async def _fetch_page_excerpt(self, url: str, *, query: str, timeout_seconds: int) -> str:
        clean_url = self._clean_url(url)
        if not clean_url:
            return ""
        try:
            if inspect.iscoroutinefunction(self.page_fetcher):
                html = await self.page_fetcher(clean_url, timeout_seconds)
            else:
                html = await asyncio.to_thread(self.page_fetcher, clean_url, timeout_seconds)
        except Exception:
            return ""
        return self._relevant_page_excerpt(str(html or ""), query=query, url=clean_url)

    async def _fetch_page_excerpts(self, urls: list[str], *, query: str, timeout_seconds: int) -> dict[str, str]:
        clean_urls: list[str] = []
        seen: set[str] = set()
        for url in urls:
            clean_url = self._clean_url(url)
            if not clean_url or clean_url in seen:
                continue
            seen.add(clean_url)
            clean_urls.append(clean_url)
        if not clean_urls:
            return {}

        async def _fetch(clean_url: str) -> tuple[str, str]:
            try:
                excerpt = await asyncio.wait_for(
                    self._fetch_page_excerpt(clean_url, query=query, timeout_seconds=timeout_seconds),
                    timeout=float(timeout_seconds) + 1.0,
                )
            except (asyncio.TimeoutError, Exception):
                return clean_url, ""
            return clean_url, excerpt

        fetched = await asyncio.gather(*(_fetch(url) for url in clean_urls))
        return {url: excerpt for url, excerpt in fetched if excerpt}

    @staticmethod
    def _note_context_hits(params: dict[str, Any]) -> list[NotesContextHit]:
        rows = params.get("note_context_hits")
        if not isinstance(rows, list):
            return []
        hits: list[NotesContextHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            note_id = str(row.get("note_id", "")).strip()
            title = str(row.get("title", "")).strip()
            if not note_id or not title:
                continue
            hits.append(
                NotesContextHit(
                    note_id=note_id,
                    title=title,
                    folder=str(row.get("folder", "")).strip(),
                    relative_path=str(row.get("relative_path", "")).strip(),
                    updated_at=str(row.get("updated_at", "")).strip(),
                    score=float(row.get("score", 0.0) or 0.0),
                    snippet=str(row.get("snippet", "")).strip(),
                    chunk_index=int(row.get("chunk_index", 0) or 0),
                    chunk_total=int(row.get("chunk_total", 0) or 0),
                    source=str(row.get("source", "markdown") or "markdown").strip(),
                )
            )
        return hits

    @staticmethod
    def _string_list(value: Any, *, limit: int = 5, max_chars: int = 180) -> list[str]:
        if not isinstance(value, list):
            return []
        rows: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = re.sub(r"\s+", " ", str(item or "")).strip()
            if not text:
                continue
            key = text.lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append(text[:max_chars])
            if len(rows) >= limit:
                break
        return rows

    @classmethod
    def _source_plan(cls, params: dict[str, Any]) -> dict[str, Any]:
        raw = params.get("web_source_plan")
        if not isinstance(raw, dict):
            return {}
        queries = cls._string_list(raw.get("queries") or raw.get("planned_queries"), limit=3, max_chars=220)
        if not queries:
            return {}
        raw_mode = re.sub(r"\s+", " ", str(raw.get("search_mode") or raw.get("mode") or "")).strip()[:40].lower()
        search_mode = raw_mode.replace("-", "_")
        if search_mode in {"deep_research", "curated_research", "source_audit"}:
            search_mode = "research"
        elif search_mode in {"ask_clarification", "clarification"}:
            search_mode = "clarify"
        elif search_mode != "research":
            search_mode = "fast_answer"
        return {
            "goal": re.sub(r"\s+", " ", str(raw.get("goal", "") or "")).strip()[:220],
            "queries": queries,
            "search_mode": search_mode,
            "must_have_domains": cls._string_list(
                raw.get("must_have_domains") or raw.get("required_domains") or raw.get("mandatory_domains"),
                limit=8,
                max_chars=120,
            ),
            "preferred_domains": cls._string_list(
                raw.get("preferred_domains") or raw.get("primary_domains") or raw.get("source_domains"),
                limit=8,
                max_chars=120,
            ),
            "required_sources": cls._string_list(raw.get("required_sources"), limit=8, max_chars=120),
            "avoid_sources": cls._string_list(raw.get("avoid_sources"), limit=8, max_chars=120),
            "search_profile_ref": re.sub(
                r"\s+",
                " ",
                str(raw.get("search_profile_ref") or raw.get("profile_ref") or raw.get("connection_ref") or "").strip(),
            )[:120],
        }

    @classmethod
    def _source_plan_required_domains(cls, source_plan: dict[str, Any]) -> list[str]:
        domains: list[str] = []
        seen: set[str] = set()
        for value in [
            *cls._string_list(source_plan.get("must_have_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("required_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("mandatory_domains"), limit=8, max_chars=120),
        ]:
            for domain in cls._domains_from_text(value):
                if domain in seen:
                    continue
                seen.add(domain)
                domains.append(domain[:160])
                if len(domains) >= 3:
                    return domains
        return domains

    @classmethod
    def _domains_from_text(cls, text: str) -> list[str]:
        domains: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(r"\b(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+)\b", str(text or ""), flags=re.IGNORECASE):
            domain = match.group(1).strip().lower().strip(".,;:!?)]}")
            if domain.startswith("www."):
                domain = domain[4:]
            if "." not in domain or domain in seen:
                continue
            seen.add(domain)
            domains.append(domain[:160])
        return domains

    @classmethod
    def _site_targets_from_text(cls, text: str) -> list[str]:
        targets: list[str] = []
        seen: set[str] = set()
        for match in re.finditer(
            r"\b(?:https?://)?(?:www\.)?([a-z0-9][a-z0-9-]*(?:\.[a-z0-9][a-z0-9-]*)+)((?:/[^\s,;:!?)]*)?)",
            str(text or ""),
            flags=re.IGNORECASE,
        ):
            domain = match.group(1).strip().lower().strip(".,;:!?)]}")
            path = str(match.group(2) or "").strip().rstrip(".,;:!?)]}")
            if domain.startswith("www."):
                domain = domain[4:]
            if "." not in domain:
                continue
            target = f"{domain}{path}" if path and path != "/" else domain
            if target in seen:
                continue
            seen.add(target)
            targets.append(target[:180])
            if len(targets) >= 3:
                break
        return targets

    @classmethod
    def _source_plan_preferred_domains(cls, source_plan: dict[str, Any]) -> list[str]:
        values = [
            str(source_plan.get("goal", "") or ""),
            *cls._string_list(source_plan.get("preferred_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("primary_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("source_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("required_sources"), limit=8, max_chars=120),
        ]
        required_domains = set(cls._source_plan_required_domains(source_plan))
        domains: list[str] = []
        seen: set[str] = set()
        for domain in cls._domains_from_text(" ".join(values)):
            if domain in seen or domain in required_domains:
                continue
            seen.add(domain)
            domains.append(domain)
            if len(domains) >= 3:
                break
        return domains

    @classmethod
    def _source_plan_search_sites(cls, source_plan: dict[str, Any]) -> list[str]:
        values = [
            *cls._string_list(source_plan.get("must_have_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("required_domains"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("mandatory_domains"), limit=8, max_chars=120),
        ]
        sites: list[str] = []
        seen: set[str] = set()
        for site in cls._site_targets_from_text(" ".join(values)):
            if site in seen:
                continue
            seen.add(site)
            sites.append(site)
            if len(sites) >= 3:
                break
        return sites

    @classmethod
    def _source_plan_search_domains(cls, source_plan: dict[str, Any]) -> list[str]:
        domains: list[str] = []
        seen: set[str] = set()
        for domain in [*cls._source_plan_required_domains(source_plan), *cls._source_plan_preferred_domains(source_plan)]:
            if domain in seen:
                continue
            seen.add(domain)
            domains.append(domain)
            if len(domains) >= 3:
                break
        return domains

    @classmethod
    def _query_site_domain(cls, query: str) -> str:
        match = cls._SITE_QUERY_RE.search(str(query or ""))
        if not match:
            return ""
        target = match.group(1).strip().lower().strip(".,;:!?)]}")
        domain = target.split("/", 1)[0]
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @staticmethod
    def _domain_matches(domain: str, required_domain: str) -> bool:
        clean_domain = str(domain or "").strip().lower()
        clean_required = str(required_domain or "").strip().lower()
        return bool(clean_domain and clean_required and (clean_domain == clean_required or clean_domain.endswith(f".{clean_required}")))

    @classmethod
    def _result_domain(cls, result: Any) -> str:
        domain = str(urlparse(str(getattr(result, "url", "") or "")).netloc or "").strip().lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @classmethod
    def _result_matches_site_target(cls, result: Any, site_target: str) -> bool:
        clean_target = str(site_target or "").strip().lower().strip(".,;:!?)]}")
        if not clean_target:
            return False
        target_domain, _sep, target_path = clean_target.partition("/")
        if target_domain.startswith("www."):
            target_domain = target_domain[4:]
        if not cls._domain_matches(cls._result_domain(result), target_domain):
            return False
        if not target_path:
            return True
        result_path = str(urlparse(str(getattr(result, "url", "") or "")).path or "").strip().lower().lstrip("/")
        clean_target_path = target_path.strip("/")
        return result_path == clean_target_path or result_path.startswith(f"{clean_target_path}/")

    @classmethod
    def _filter_results_for_site_query(cls, query: str, results: list[Any]) -> tuple[list[Any], str]:
        site_domain = cls._query_site_domain(query)
        if not site_domain:
            return results, ""
        filtered = [result for result in results if cls._domain_matches(cls._result_domain(result), site_domain)]
        removed = len(results) - len(filtered)
        if removed <= 0:
            return results, ""
        return (
            filtered,
            f"Routing Debug: web_source_provider_contract site_domain={site_domain} removed={removed} reason=site_query_domain_miss",
        )

    @classmethod
    def _search_queries(cls, query: str, source_plan: dict[str, Any]) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        plan_queries = cls._string_list(source_plan.get("queries"), limit=3, max_chars=220)
        search_sites = cls._source_plan_search_sites(source_plan)
        domain_queries: list[str] = []
        for plan_query in plan_queries[:2] or [str(query or "").strip()]:
            clean_plan = re.sub(r"\s+", " ", str(plan_query or "")).strip()
            if not clean_plan:
                continue
            if cls._query_site_domain(clean_plan):
                domain_queries.append(clean_plan)
                continue
            for site in search_sites:
                if site:
                    domain_queries.append(f"site:{site} {clean_plan}")
        candidates = [*domain_queries, *plan_queries, str(query or "").strip()] if plan_queries else [*domain_queries, str(query or "").strip()]
        search_mode = str(source_plan.get("search_mode") or "").strip().lower().replace("-", "_")
        query_limit = 6 if search_mode != "research" else 10
        for candidate in candidates:
            clean = re.sub(r"\s+", " ", str(candidate or "")).strip()
            key = clean.lower()
            if not clean or key in seen:
                continue
            seen.add(key)
            rows.append(clean)
            if len(rows) >= query_limit:
                break
        return rows or [str(query or "").strip()]

    @classmethod
    def _source_plan_avoid_text(cls, source_plan: dict[str, Any]) -> str:
        values = [
            str(source_plan.get("goal", "") or ""),
            *cls._string_list(source_plan.get("required_sources"), limit=8, max_chars=120),
            *cls._string_list(source_plan.get("avoid_sources"), limit=8, max_chars=120),
        ]
        return " ".join(values).lower()

    @classmethod
    def _source_plan_avoids_registry_results(cls, source_plan: dict[str, Any]) -> bool:
        text = cls._source_plan_avoid_text(source_plan)
        if not text:
            return False
        markers = (
            "package registr",
            "paketregistr",
            "software package",
            "container image",
            "container-images",
            "docker",
            "software repositor",
            "code repositor",
            "registry",
        )
        return any(marker in text for marker in markers)

    @classmethod
    def _is_registry_result(cls, result: Any) -> bool:
        url = str(getattr(result, "url", "") or "").lower()
        domain = str(urlparse(url).netloc or "").lower()
        engine = str(getattr(result, "engine", "") or "").lower()
        return any(registry in domain for registry in cls._REGISTRY_DOMAINS) or "docker" in engine

    @classmethod
    def _filter_results_for_source_plan(
        cls,
        results: list[Any],
        source_plan: dict[str, Any],
    ) -> tuple[list[Any], list[str]]:
        if not source_plan or not cls._source_plan_avoids_registry_results(source_plan):
            return results, []
        filtered = [result for result in results if not cls._is_registry_result(result)]
        removed = len(results) - len(filtered)
        if removed <= 0:
            return results, []
        return filtered, [f"Routing Debug: web_source_filter source=source_plan removed={removed} reason=avoid_registry_sources"]

    @classmethod
    def _source_plan_anchor_terms(cls, query: str, source_plan: dict[str, Any]) -> list[str]:
        values = [
            str(query or ""),
            str(source_plan.get("goal", "") or ""),
            *cls._string_list(source_plan.get("queries"), limit=3, max_chars=220),
        ]
        stopwords = set(cls._QUERY_STOPWORDS)
        counts: dict[str, int] = {}
        for value in values:
            tokens = {
                token.lower()
                for token in re.findall(r"[a-zA-Z0-9_+-]{2,}", value)
                if token.lower() not in stopwords and not re.fullmatch(r"20\d{2}", token)
            }
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
        threshold = 2 if len(values) >= 3 else 1
        anchors = [token for token, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])) if count >= threshold]
        return anchors[:6]

    @classmethod
    def _filter_results_for_anchor_terms(
        cls,
        results: list[Any],
        *,
        query: str,
        source_plan: dict[str, Any],
    ) -> tuple[list[Any], list[str]]:
        if not source_plan or not results:
            return results, []
        anchors = cls._source_plan_anchor_terms(query, source_plan)
        if len(anchors) < 2:
            return results, []
        kept: list[Any] = []
        for result in results:
            haystack = " ".join(
                str(getattr(result, key, "") or "").lower()
                for key in ("title", "url", "snippet")
            )
            matches = sum(1 for anchor in anchors if anchor in haystack)
            if matches >= 2:
                kept.append(result)
        removed = len(results) - len(kept)
        if removed <= 0:
            return results, []
        return kept, [
            "Routing Debug: web_source_filter "
            f"source=source_plan removed={removed} kept={len(kept)} reason=anchor_terms "
            f"anchors={','.join(anchors[:4])}"
        ]

    @classmethod
    def _source_plan_topic_terms(cls, query: str, source_plan: dict[str, Any]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for value in [
            str(query or ""),
            str(source_plan.get("goal", "") or ""),
            *cls._string_list(source_plan.get("queries"), limit=3, max_chars=220),
        ]:
            clean_value = re.sub(r"\bsite:[^\s]+\b", " ", value, flags=re.IGNORECASE)
            for term in cls._query_terms(clean_value):
                if re.fullmatch(r"20\d{2}", term):
                    continue
                if term in seen:
                    continue
                seen.add(term)
                terms.append(term)
        return terms[:8]

    @classmethod
    def _result_matches_source_plan_topic(cls, query: str, source_plan: dict[str, Any], result: Any) -> bool:
        terms = cls._source_plan_topic_terms(query, source_plan)
        if len(terms) < 2:
            return True
        haystack = " ".join(
            str(getattr(result, key, "") or "").lower()
            for key in ("title", "url", "snippet")
        )
        matches = sum(1 for term in terms if term and term in haystack)
        return matches >= min(2, len(terms))

    @classmethod
    def _source_plan_rejects_noise_sources(cls, query: str, source_plan: dict[str, Any]) -> bool:
        text = " ".join(
            [
                str(query or ""),
                str(source_plan.get("goal", "") or ""),
                *cls._string_list(source_plan.get("required_sources"), limit=8, max_chars=120),
            ]
        ).lower()
        if any(term in text for term in ("deal", "deals", "angebot", "rabatt", "rumor", "rumour", "geruecht", "gerücht")):
            return False
        return cls._is_recency_query(text) or cls._is_current_version_query(text) or any(
            marker in text for marker in ("official", "offiziell", "spec", "spezifikation", "vergleich", "comparison")
        )

    @classmethod
    def _result_is_noise_source(cls, result: Any) -> bool:
        haystack = " ".join(
            str(getattr(result, key, "") or "").lower()
            for key in ("title", "url", "snippet")
        )
        return any(marker in haystack for marker in cls._SOURCE_NOISE_TERMS)

    @classmethod
    def _source_plan_needs_preferred_source_gate(cls, query: str, source_plan: dict[str, Any]) -> bool:
        if not source_plan:
            return False
        if cls._source_plan_required_domains(source_plan):
            return True
        if cls._is_recency_query(query) or cls._is_current_version_query(query):
            return True
        required_text = " ".join(cls._string_list(source_plan.get("required_sources"), limit=8, max_chars=120)).lower()
        return any(marker in required_text for marker in ("official", "offiziell", "vendor", "hersteller", "release", "changelog"))

    @classmethod
    def _apply_source_quality_gate(
        cls,
        results: list[Any],
        *,
        query: str,
        source_plan: dict[str, Any],
    ) -> tuple[list[Any], list[str], bool]:
        if not source_plan or not results:
            return results, [], False
        details: list[str] = []
        if cls._source_plan_rejects_noise_sources(query, source_plan):
            before_noise = len(results)
            results = [result for result in results if not cls._result_is_noise_source(result)]
            removed_noise = before_noise - len(results)
            if removed_noise:
                details.append(
                    "Routing Debug: web_source_quality_gate "
                    f"outcome=noise_sources_removed removed={removed_noise}"
                )
            if not results:
                return (
                    [],
                    [
                        *details,
                        "Routing Debug: web_source_quality_gate "
                        "outcome=fail_closed reason=no_reliable_non_noise_sources",
                    ],
                    True,
                )

        required_sites = cls._source_plan_search_sites(source_plan)
        if required_sites:
            required_matches: list[Any] = []
            removed_required = 0
            for result in results:
                if any(cls._result_matches_site_target(result, site) for site in required_sites):
                    required_matches.append(result)
                else:
                    removed_required += 1
            relevant_required = [
                result
                for result in required_matches
                if cls._result_matches_source_plan_topic(query, source_plan, result)
            ]
            if not relevant_required:
                return (
                    [],
                    [
                        *details,
                        "Routing Debug: web_source_quality_gate "
                        f"outcome=fail_closed reason=no_relevant_required_sources "
                        f"required_sites={','.join(required_sites)}",
                    ],
                    True,
                )
            return (
                relevant_required,
                [
                    *details,
                    "Routing Debug: web_source_quality_gate "
                    f"outcome=required_sources_kept matches={len(relevant_required)} "
                    f"removed={removed_required + max(len(required_matches) - len(relevant_required), 0)} "
                    f"required_sites={','.join(required_sites)}",
                ],
                False,
            )

        preferred_sites = cls._source_plan_preferred_domains(source_plan)
        if not preferred_sites:
            return results, details, False
        preferred: list[Any] = []
        others: list[Any] = []
        for result in results:
            if any(cls._result_matches_site_target(result, site) for site in preferred_sites):
                preferred.append(result)
            else:
                others.append(result)
        if preferred:
            preferred_before = len(preferred)
            preferred = [
                result
                for result in preferred
                if cls._result_matches_source_plan_topic(query, source_plan, result)
                and not (
                    cls._source_plan_rejects_noise_sources(query, source_plan)
                    and cls._result_is_noise_source(result)
                )
            ]
            if not preferred and not others:
                return (
                    [],
                    [
                        *details,
                        "Routing Debug: web_source_quality_gate "
                        f"outcome=fail_closed reason=no_relevant_preferred_sources "
                        f"preferred_matches={preferred_before} preferred_sites={','.join(preferred_sites)}"
                    ],
                    True,
                )
            return (
                [*preferred, *others],
                [
                    *details,
                    "Routing Debug: web_source_quality_gate "
                    f"outcome=preferred_sources_promoted matches={len(preferred)} "
                    f"filtered={max(preferred_before - len(preferred), 0)} "
                    f"preferred_sites={','.join(preferred_sites)}"
                ],
                False,
            )
        return (
            results,
            [
                *details,
                "Routing Debug: web_source_quality_gate "
                f"outcome=preferred_sources_missing_continuing preferred_sites={','.join(preferred_sites)}",
            ],
            False,
        )

    @classmethod
    def _limit_results_for_source_plan(cls, results: list[Any], source_plan: dict[str, Any]) -> tuple[list[Any], list[str]]:
        if not source_plan or not results:
            return results, []
        search_mode = str(source_plan.get("search_mode") or "").strip().lower().replace("-", "_")
        if search_mode != "fast_answer":
            return results, []
        limit = 4
        if len(results) <= limit:
            return results, []
        return results[:limit], [
            "Routing Debug: web_source_result_budget "
            f"search_mode=fast_answer kept={limit} removed={len(results) - limit}"
        ]

    @staticmethod
    def _merge_search_results(results: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for result in results:
            url = str(getattr(result, "url", "") or "").strip().lower()
            title = str(getattr(result, "title", "") or "").strip().lower()
            key = url or title
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(result)
        return merged

    async def execute(self, query: str, params: dict) -> SkillResult:
        language = str(params.get("language", "") or "").strip().lower()
        note_hits = self._note_context_hits(params)
        source_plan = self._source_plan(params)
        requested_profile_ref = str(params.get("connection_ref", "") or "").strip()
        profile_source = "explicit_param" if requested_profile_ref else "auto"
        if not requested_profile_ref and str(source_plan.get("search_profile_ref", "") or "").strip():
            requested_profile_ref = str(source_plan.get("search_profile_ref", "") or "").strip()
            profile_source = "source_plan"
        selected = self._select_profile(query, explicit_ref=requested_profile_ref)
        if selected is None:
            if requested_profile_ref and self._profile_rows(self.settings):
                return SkillResult(
                    skill_name=self.name,
                    content="",
                    success=False,
                    error=self._text(
                        language,
                        "unknown_searxng_profile",
                        "Selected SearXNG profile is not configured: {profile_ref}",
                        profile_ref=requested_profile_ref,
                    ),
                    metadata={
                        "error_code": "web_search_profile_not_found",
                        "requested_profile_ref": requested_profile_ref,
                        "search_profile_source": profile_source,
                    },
                )
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=self._text(language, "no_searxng_connection", "No SearXNG connection configured."),
            )
        ref, profile = selected
        display_name = str(self._profile_value(profile, "title", "")).strip() or ref
        try:
            categories = self._profile_list(profile, "categories")
            if source_plan and not categories:
                categories = ["general"]
            search_kwargs = {
                "base_url": resolve_searxng_base_url(str(self._profile_value(profile, "base_url", "")).strip()),
                "timeout_seconds": int(self._profile_value(profile, "timeout_seconds", 10) or 10),
                "language": str(self._profile_value(profile, "language", "")).strip(),
                "safe_search": int(self._profile_value(profile, "safe_search", 1) or 1),
                "categories": categories,
                "engines": self._profile_list(profile, "engines"),
                "time_range": str(self._profile_value(profile, "time_range", "")).strip(),
                "max_results": int(self._profile_value(profile, "max_results", 5) or 5),
            }
            search_queries = self._search_queries(query, source_plan)
            if len(search_queries) > 1:
                search_kwargs["max_results"] = max(int(search_kwargs["max_results"] or 5), 8)

            async def _search_one(search_query: str) -> Any:
                return await self.client.search(query=search_query, **search_kwargs)

            responses = await asyncio.gather(*(_search_one(search_query) for search_query in search_queries), return_exceptions=True)
            search_errors = [str(item) for item in responses if isinstance(item, SearXNGClientError)]
            good_responses = [item for item in responses if not isinstance(item, Exception)]
            if not good_responses:
                error_text = search_errors[0] if search_errors else "no response"
                raise SearXNGClientError(error_text)
            all_results: list[Any] = []
            provider_contract_details: list[str] = []
            for response in good_responses:
                response_results = list(getattr(response, "results", []) or [])
                filtered_response_results, provider_contract_detail = self._filter_results_for_site_query(
                    str(getattr(response, "query", "") or ""),
                    response_results,
                )
                all_results.extend(filtered_response_results)
                if provider_contract_detail:
                    provider_contract_details.append(provider_contract_detail)
            response_query = "; ".join(search_queries)
        except SearXNGClientError as exc:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=self._text(language, "search_failed", "Web search failed: {error}", error=exc),
            )

        merged_results = self._merge_search_results(all_results)
        filtered_results, source_filter_details = self._filter_results_for_source_plan(merged_results, source_plan)
        filtered_results, anchor_filter_details = self._filter_results_for_anchor_terms(
            filtered_results,
            query=query,
            source_plan=source_plan,
        )
        source_filter_details = [*source_filter_details, *anchor_filter_details]
        source_filter_details = [*provider_contract_details, *source_filter_details]
        ranking_query = "; ".join(search_queries) if source_plan else query
        ordered_results = self._prepare_results(ranking_query, filtered_results)
        ordered_results, quality_gate_details, quality_gate_failed = self._apply_source_quality_gate(
            ordered_results,
            query=ranking_query,
            source_plan=source_plan,
        )
        source_filter_details = [*source_filter_details, *quality_gate_details]
        ordered_results, result_budget_details = self._limit_results_for_source_plan(ordered_results, source_plan)
        source_filter_details = [*source_filter_details, *result_budget_details]
        authority_labels: list[dict[str, str]] = []
        authority_summary: dict[str, Any] = {"outcome": "", "guidance": ""}
        authority_details: list[str] = []
        if ordered_results and source_plan:
            authority_labels, authority_summary, authority_details = self._source_authority_summary(
                ranking_query,
                ordered_results,
                source_plan,
            )
            source_filter_details = [*source_filter_details, *authority_details]
        profile_detail = ""
        if profile_source != "auto" or str(source_plan.get("search_profile_ref", "") or "").strip():
            profile_detail = (
                "Routing Debug: web_search_profile "
                f"selected={ref} source={profile_source} "
                f"categories={','.join(categories) or '-'} engines={','.join(self._profile_list(profile, 'engines')) or '-'}"
            )
        plan_detail = ""
        query_detail = ""
        if source_plan:
            plan_detail = (
                "Routing Debug: web_source_acquisition_plan "
                f"used=true planned_queries={len(source_plan.get('queries') or [])} "
                f"search_mode={source_plan.get('search_mode') or '-'} "
                f"search_profile_ref={source_plan.get('search_profile_ref') or '-'} "
                f"must_domains={', '.join(source_plan.get('must_have_domains') or []) or '-'} "
                f"preferred_domains={', '.join(source_plan.get('preferred_domains') or []) or '-'} "
                f"required={', '.join(source_plan.get('required_sources') or []) or '-'} "
                f"avoid={', '.join(source_plan.get('avoid_sources') or []) or '-'}"
            )
            query_detail = (
                "Routing Debug: web_source_queries "
                f"count={len(search_queries)} queries={' | '.join(search_queries)[:700]}"
            )

        explicit_urls = self._explicit_urls(query)
        if not ordered_results and explicit_urls:
            fetch_timeout = min(max(int(self._profile_value(profile, "timeout_seconds", 10) or 10), 2), 4)
            page_excerpts = await self._fetch_page_excerpts(
                explicit_urls[:3],
                query=query,
                timeout_seconds=fetch_timeout,
            )
            if page_excerpts:
                lines = [
                    f"[Web Search via {display_name}]",
                    f"{self._text(language, 'search_label', 'Search')}: {response_query}",
                ]
                detail_lines = [line for line in [profile_detail, plan_detail, query_detail, *source_filter_details] if line]
                source_entries = []
                for index, (url, excerpt) in enumerate(page_excerpts.items(), start=1):
                    lines.append(f"- [{index}] {url}\n  Page excerpt:\n{excerpt}")
                    detail = self._detail_line(language, url, url, "page_fetch")
                    detail_lines.append(detail)
                    source_entries.append(
                        {
                            "detail": detail,
                            "type": "web",
                            "title": url,
                            "url": url,
                            "engine": "page_fetch",
                            "published_at": "",
                            "published_label": "",
                            "page_excerpt": True,
                            "page_excerpt_text": excerpt,
                        }
                    )
                content, saved = self.truncate("\n".join(lines))
                return SkillResult(
                    skill_name=self.name,
                    content=content,
                    success=True,
                    tokens_saved=saved,
                    metadata={
                        "sources": source_entries,
                        "detail_lines": detail_lines,
                        "connection_ref": ref,
                        "connection_title": display_name,
                        "search_profile_ref": ref,
                        "search_profile_source": profile_source,
                        "result_count": len(source_entries),
                        "explicit_url_count": len(explicit_urls),
                        "fetch_attempt_count": len(explicit_urls[:3]),
                        "page_excerpt_count": len(page_excerpts),
                        "source_quality_outcome": "explicit_url_page_fetch",
                        "web_source_plan": source_plan,
                        "executed_queries": search_queries,
                        "planned_query_count": len(source_plan.get("queries") or []),
                        "search_error_count": len(search_errors),
                        "search_categories": categories,
                    },
                )

        if quality_gate_failed or not ordered_results:
            detail_lines = [
                profile_detail,
                *([plan_detail] if plan_detail else []),
                *([query_detail] if query_detail else []),
                *source_filter_details,
                self._text(
                    language,
                    "zero_results_detail",
                    "Web search via {display_name} · 0 results",
                    display_name=display_name,
                ),
            ]
            if source_plan:
                return SkillResult(
                    skill_name=self.name,
                    content="",
                    success=False,
                    error=self._text(
                        language,
                        "no_reliable_sources",
                        "I found no reliable web sources for this question.",
                    ),
                    metadata={
                        "sources": [],
                        "detail_lines": [line for line in detail_lines if line],
                        "web_source_plan": source_plan,
                        "executed_queries": search_queries,
                        "planned_query_count": len(source_plan.get("queries") or []),
                        "search_error_count": len(search_errors),
                        "search_categories": categories,
                        "connection_ref": ref,
                        "connection_title": display_name,
                        "search_profile_ref": ref,
                        "search_profile_source": profile_source,
                        "result_count": 0,
                        "error_code": "web_source_no_reliable_sources",
                    },
                )
            return SkillResult(
                skill_name=self.name,
                content=self._text(language, "no_results", "[Web Search]\nNo web results found."),
                success=True,
                metadata={
                    "detail_lines": [line for line in detail_lines if line],
                    "web_source_plan": source_plan,
                    "executed_queries": search_queries,
                    "planned_query_count": len(source_plan.get("queries") or []),
                    "search_error_count": len(search_errors),
                    "search_categories": categories,
                    "connection_ref": ref,
                    "connection_title": display_name,
                    "search_profile_ref": ref,
                    "search_profile_source": profile_source,
                    "result_count": 0,
                },
            )

        lines: list[str] = []
        detail_lines: list[str] = [line for line in [profile_detail, plan_detail, query_detail, *source_filter_details] if line]
        if note_hits:
            context_block = note_context_block(note_hits, language=language)
            if context_block:
                lines.extend(context_block.splitlines())
                lines.append("")
            detail_lines.extend(note_context_detail_lines(note_hits, language=language))
        lines.extend([f"[Web Search via {display_name}]", f"{self._text(language, 'search_label', 'Search')}: {response_query}"])
        if authority_summary.get("guidance"):
            lines.append(str(authority_summary["guidance"]))
        if self._is_recency_query(query):
            lines.append(
                self._text(
                    language,
                    "recency_note",
                    "Note: results with recognized publication dates are shown first.",
                )
            )
        source_entries: list[dict[str, Any]] = []
        page_excerpts: dict[str, str] = {}
        fetch_attempts: set[str] = set()
        fetch_timeout = min(max(int(self._profile_value(profile, "timeout_seconds", 10) or 10), 2), 4)
        fetch_candidates = self._result_fetch_candidates(ranking_query, ordered_results)
        for url in fetch_candidates:
            fetch_attempts.add(url)
            base_url, _fragment = urldefrag(url)
            if base_url:
                fetch_attempts.add(base_url)
        fetched_page_excerpts = await self._fetch_page_excerpts(
            fetch_candidates,
            query=ranking_query,
            timeout_seconds=fetch_timeout,
        )
        for url, excerpt in fetched_page_excerpts.items():
            page_excerpts[url] = excerpt
            base_url, _fragment = urldefrag(url)
            if base_url:
                page_excerpts[base_url] = excerpt
        for index, result in enumerate(ordered_results, start=1):
            authority = authority_labels[index - 1] if index - 1 < len(authority_labels) else {"label": "", "reason": ""}
            entry = f"- [{index}] {result.title}"
            if result.url:
                entry += f"\n  URL: {result.url}"
            if result.engine:
                entry += f"\n  Engine: {result.engine}"
            if authority.get("label"):
                entry += f"\n  Source authority: {authority['label']} ({authority.get('reason') or '-'})"
            if result.published_label:
                entry += f"\n  {self._text(language, 'date_label', 'Date')}: {result.published_label}"
            if result.snippet:
                entry += f"\n  Snippet: {result.snippet}"
            excerpt = page_excerpts.get(str(result.url or "")) or page_excerpts.get(urldefrag(str(result.url or ""))[0])
            if excerpt:
                entry += f"\n  Page excerpt:\n{excerpt}"
            elif str(result.url or "") in fetch_attempts or urldefrag(str(result.url or ""))[0] in fetch_attempts:
                entry += "\n  Page fetch: no readable page excerpt extracted; do not infer concrete page details from this result alone."
            lines.append(entry)
            detail = self._detail_line(language, result.title, result.url, result.engine, result.published_label)
            detail_lines.append(detail)
            source_entries.append(
                {
                    "detail": detail,
                    "type": "web",
                    "title": result.title,
                    "url": result.url,
                    "engine": result.engine,
                    "published_at": result.published_at,
                    "published_label": result.published_label,
                    "snippet": result.snippet,
                    "page_excerpt": bool(excerpt),
                    "page_excerpt_text": excerpt,
                    "source_authority_label": authority.get("label") or "",
                    "source_authority_reason": authority.get("reason") or "",
                }
            )

        content, saved = self.truncate("\n".join(lines))
        return SkillResult(
            skill_name=self.name,
            content=content,
            success=True,
            tokens_saved=saved,
            metadata={
                "sources": source_entries,
                "detail_lines": detail_lines,
                "connection_ref": ref,
                "connection_title": display_name,
                "search_profile_ref": ref,
                "search_profile_source": profile_source,
                "result_count": len(ordered_results),
                "explicit_url_count": len(explicit_urls),
                "fetch_attempt_count": len(fetch_candidates),
                "page_excerpt_count": len({value for value in page_excerpts.values()}),
                "source_quality_outcome": (
                    "explicit_url_with_page_excerpt"
                    if explicit_urls and page_excerpts
                    else "explicit_url_without_page_excerpt"
                    if explicit_urls
                    else "search_results_with_page_excerpt"
                    if page_excerpts
                    else "search_results_only"
                ),
                "source_authority_outcome": authority_summary.get("outcome") or "",
                "web_source_plan": source_plan,
                "executed_queries": search_queries,
                "planned_query_count": len(source_plan.get("queries") or []),
                "search_error_count": len(search_errors),
                "search_categories": categories,
            },
        )
