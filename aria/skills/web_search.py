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
from aria.core.searxng_client import SearXNGClient, SearXNGClientError, SearXNGSearchResponse
from aria.skills.base import BaseSkill, SkillResult

_WEB_SEARCH_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


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
        "for",
        "in",
        "internet",
        "last",
        "latest",
        "news",
        "online",
        "release",
        "releases",
        "search",
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
        "version",
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

    _DEAL_TERMS = (
        "angebot",
        "angebote",
        "bundle",
        "deal",
        "deals",
        "discount",
        "g" + chr(252) + "nstig",
        "guenstig",
        "shopping",
        "sale",
        "rabatt",
        "1 euro",
        "one euro",
    )

    _TARGET_TERM_STOPWORDS = frozenset({
        "apple",
        "google",
        "microsoft",
        "samsung",
        "sony",
    })

    @staticmethod
    def _profile_rows(settings: Any) -> dict[str, Any]:
        rows = getattr(getattr(settings, "connections", object()), "searxng", {})
        return rows if isinstance(rows, dict) else {}

    @staticmethod
    def _profile_value(profile: Any, key: str, default: Any = "") -> Any:
        if isinstance(profile, dict):
            return profile.get(key, default)
        return getattr(profile, key, default)

    @classmethod
    def _profile_list(cls, profile: Any, key: str) -> list[str]:
        raw = cls._profile_value(profile, key, [])
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return [str(item).strip() for item in str(raw or "").split(",") if str(item).strip()]

    def _select_profile(self, query: str, explicit_ref: str = "") -> tuple[str, Any] | None:
        rows = self._profile_rows(self.settings)
        if not rows:
            return None
        clean_query = str(query or "").strip().lower()
        clean_ref = str(explicit_ref or "").strip().lower()
        if clean_ref and clean_ref in rows:
            return clean_ref, rows[clean_ref]

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
    def _should_run_official_supplement(cls, query: str) -> bool:
        if cls._is_news_query(query):
            return False
        return cls._is_recency_query(query) or cls._is_current_version_query(query)

    @classmethod
    def _official_supplement_query(cls, query: str) -> str:
        clean = re.sub(r"\s+", " ", str(query or "").strip())
        if not clean:
            return ""
        lowered = clean.lower()
        if "official" in lowered or "offizielle" in lowered or "hersteller" in lowered:
            return clean
        return f"{clean} official manufacturer product page"

    @classmethod
    def _official_supplement_queries(cls, query: str) -> list[str]:
        primary = cls._official_supplement_query(query)
        queries: list[str] = []
        seen: set[str] = set()

        def add(value: str) -> None:
            clean = re.sub(r"\s+", " ", str(value or "").strip(" .,:;!?"))
            key = clean.lower()
            if clean and key not in seen and key != str(query or "").strip().lower():
                seen.add(key)
                queries.append(clean)

        add(primary)
        for target in cls._official_product_targets(query):
            add(f"{target} latest model official manufacturer product page")
        return queries[:4]

    @classmethod
    def _official_product_targets(cls, query: str) -> list[str]:
        if not cls._should_run_official_supplement(query):
            return []
        clean = re.sub(r"\s+", " ", str(query or "").strip())
        if not clean:
            return []
        subject = clean
        cleanup_patterns = (
            r"\b(?:bitte|please)\b",
            r"\b(?:suche|such|suchen|search|research|recherchier(?:e|en)?)\b",
            r"\b(?:im|in dem|in|on the)\s+(?:internet|web)\b",
            r"\b(?:online|nach|for)\b",
            r"\b(?:der|die|das|dem|den|des|einer?|the)\b",
            r"\b(?:neuste[ns]?|neueste[ns]?|aktuell(?:e[nsr]?)?|latest|newest|current|most recent)\b",
            r"\b(?:modell|model|version|release)\b",
        )
        for pattern in cleanup_patterns:
            subject = re.sub(pattern, " ", subject, flags=re.IGNORECASE)
        subject = re.sub(r"\s+", " ", subject).strip(" .,:;!?")
        if not subject:
            return []
        parts = [
            re.sub(r"\s+", " ", part).strip(" .,:;!?")
            for part in re.split(r"\s+(?:und|and|sowie|plus)\s+|[,;/]+", subject, flags=re.IGNORECASE)
        ]
        parts = [part for part in parts if part and len(part) >= 4]
        if len(parts) < 2:
            return []
        query_lower = clean.lower()
        targets: list[str] = []
        seen: set[str] = set()
        carried_brand = ""
        for part in parts:
            target = part
            tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]*", target)
            if carried_brand and tokens and tokens[0].lower() != carried_brand.lower():
                target = f"{carried_brand} {target}"
            elif not carried_brand and len(tokens) >= 2 and tokens[0].lower() in query_lower:
                carried_brand = tokens[0]
            key = target.lower()
            if key not in seen:
                seen.add(key)
                targets.append(target)
        return targets[:3]

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
        title = str(getattr(result, "title", "") or "").lower()
        snippet = str(getattr(result, "snippet", "") or "").lower()
        engine = str(getattr(result, "engine", "") or "").lower()
        url = str(getattr(result, "url", "") or "").lower()
        parsed = urlparse(url)
        domain = str(parsed.netloc or "").lower()
        path = str(parsed.path or "").lower()
        combined = " ".join(part for part in (title, snippet, url) if part)

        score = 0
        terms = cls._query_terms(query)
        meaningful_domain_terms = [term for term in terms if len(term) >= 4 and term not in {"latest", "neuste", "neueste"}]
        if cls._should_run_official_supplement(query):
            if any(term in domain for term in meaningful_domain_terms):
                score += 22
            if any(marker in domain for marker in ("official", "store.")):
                score += 8
            if any(marker in path for marker in ("/shop/", "/store/", "/product", "/iphone", "/watch")):
                score += 5

        if not cls._is_current_version_query(query) and not cls._should_run_official_supplement(query):
            return score

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

        news_like = "news" in engine or any(news_domain in domain for news_domain in cls._NEWS_DOMAINS)
        if news_like:
            score -= 28 if cls._should_run_official_supplement(query) else 12

        if any(term in combined for term in cls._DEAL_TERMS):
            score -= 18

        if "mozilla.org" in domain and "manifest.json/version" in path:
            score -= 20

        return score

    @staticmethod
    def _merge_search_results(primary: list[Any], supplemental: list[Any]) -> list[Any]:
        merged: list[Any] = []
        seen: set[str] = set()
        for item in [*primary, *supplemental]:
            url = str(getattr(item, "url", "") or "").strip().lower()
            key = url or str(getattr(item, "title", "") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
        return merged

    @classmethod
    def _target_match_terms(cls, target: str) -> list[str]:
        terms = [
            term
            for term in cls._query_terms(target)
            if term not in cls._TARGET_TERM_STOPWORDS
        ]
        if terms:
            return terms
        return cls._query_terms(target)

    @classmethod
    def _result_search_text(cls, result: Any) -> str:
        return " ".join(
            str(value or "").lower()
            for value in (
                getattr(result, "title", ""),
                getattr(result, "snippet", ""),
                getattr(result, "url", ""),
                getattr(result, "engine", ""),
            )
            if str(value or "").strip()
        )

    @classmethod
    def _target_coverage_rows(cls, query: str, ordered_results: list[Any]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for target in cls._official_product_targets(query):
            terms = cls._target_match_terms(target)
            if not terms:
                continue
            best: Any | None = None
            best_score = -10_000
            for index, result in enumerate(ordered_results):
                combined = cls._result_search_text(result)
                if not any(term in combined for term in terms):
                    continue
                quality = cls._source_quality_score(target, result)
                relevance, matches = cls._result_relevance_score(target, result)
                score = quality + relevance + matches * 8 - index
                if score > best_score:
                    best = result
                    best_score = score
            if best is None:
                continue
            rows.append(
                {
                    "target": target,
                    "title": str(getattr(best, "title", "") or "").strip(),
                    "url": str(getattr(best, "url", "") or "").strip(),
                    "snippet": str(getattr(best, "snippet", "") or "").strip(),
                    "engine": str(getattr(best, "engine", "") or "").strip(),
                }
            )
        return rows

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

        official_supplement_query = self._should_run_official_supplement(query)
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
        elif official_supplement_query:
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

    async def execute(self, query: str, params: dict) -> SkillResult:
        language = str(params.get("language", "") or "").strip().lower()
        note_hits = self._note_context_hits(params)
        selected = self._select_profile(query, explicit_ref=str(params.get("connection_ref", "")))
        if selected is None:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=self._text(language, "no_searxng_connection", "No SearXNG connection configured."),
            )
        ref, profile = selected
        display_name = str(self._profile_value(profile, "title", "")).strip() or ref
        try:
            search_kwargs = {
                "base_url": resolve_searxng_base_url(str(self._profile_value(profile, "base_url", "")).strip()),
                "timeout_seconds": int(self._profile_value(profile, "timeout_seconds", 10) or 10),
                "language": str(self._profile_value(profile, "language", "")).strip(),
                "safe_search": int(self._profile_value(profile, "safe_search", 1) or 1),
                "categories": self._profile_list(profile, "categories"),
                "engines": self._profile_list(profile, "engines"),
                "time_range": str(self._profile_value(profile, "time_range", "")).strip(),
                "max_results": max(int(self._profile_value(profile, "max_results", 5) or 5), 8)
                if self._should_run_official_supplement(query)
                else int(self._profile_value(profile, "max_results", 5) or 5),
            }
            supplemental_count = 0
            supplemental_errors: list[str] = []
            supplement_queries = self._official_supplement_queries(query) if self._should_run_official_supplement(query) else []
            try:
                response = await self.client.search(
                    query=str(query or "").strip(),
                    **search_kwargs,
                )
            except SearXNGClientError as exc:
                if not supplement_queries:
                    raise
                supplemental_errors.append(f"primary: {str(exc)[:170]}")
                response = SearXNGSearchResponse(query=str(query or "").strip(), results=[], raw={})
            if self._should_run_official_supplement(query):
                if supplement_queries:
                    supplemental_responses = await asyncio.gather(
                        *[
                            self.client.search(
                                query=supplement_query,
                                **search_kwargs,
                            )
                            for supplement_query in supplement_queries
                        ],
                        return_exceptions=True,
                    )
                    supplemental_results = []
                    for supplemental_response in supplemental_responses:
                        if isinstance(supplemental_response, Exception):
                            supplemental_errors.append(str(supplemental_response)[:180])
                            continue
                        supplemental_results.extend(list(supplemental_response.results or []))
                    response.results = self._merge_search_results(response.results, supplemental_results)
                    supplemental_count = len(supplemental_results)
                    if not response.results and supplemental_errors:
                        raise SearXNGClientError("; ".join(supplemental_errors[:3]))
        except SearXNGClientError as exc:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=self._text(language, "search_failed", "Web search failed: {error}", error=exc),
            )

        ordered_results = self._prepare_results(query, response.results)

        explicit_urls = self._explicit_urls(query)
        if not ordered_results and explicit_urls:
            page_excerpts: dict[str, str] = {}
            fetch_timeout = min(max(int(self._profile_value(profile, "timeout_seconds", 10) or 10), 2), 8)
            for url in explicit_urls[:3]:
                excerpt = await self._fetch_page_excerpt(url, query=query, timeout_seconds=fetch_timeout)
                if excerpt:
                    page_excerpts[url] = excerpt
            if page_excerpts:
                lines = [
                    f"[Web Search via {display_name}]",
                    f"{self._text(language, 'search_label', 'Search')}: {response.query}",
                ]
                detail_lines = []
                detail_lines.extend(f"Web search supplemental query failed: {error}" for error in supplemental_errors[:3])
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
                        "result_count": len(source_entries),
                        "explicit_url_count": len(explicit_urls),
                        "fetch_attempt_count": len(explicit_urls[:3]),
                        "page_excerpt_count": len(page_excerpts),
                        "source_quality_outcome": "explicit_url_page_fetch",
                        "official_supplement_count": supplemental_count,
                        "official_supplement_error_count": len(supplemental_errors),
                        "official_supplement_errors": supplemental_errors[:3],
                    },
                )

        if not ordered_results:
            return SkillResult(
                skill_name=self.name,
                content=self._text(language, "no_results", "[Web Search]\nNo web results found."),
                success=True,
                metadata={
                    "detail_lines": [
                        self._text(
                            language,
                            "zero_results_detail",
                            "Web search via {display_name} · 0 results",
                            display_name=display_name,
                        )
                    ],
                    "official_supplement_count": supplemental_count,
                    "official_supplement_error_count": len(supplemental_errors),
                    "official_supplement_errors": supplemental_errors[:3],
                },
            )

        lines: list[str] = []
        detail_lines: list[str] = []
        detail_lines.extend(f"Web search supplemental query failed: {error}" for error in supplemental_errors[:3])
        if note_hits:
            context_block = note_context_block(note_hits, language=language)
            if context_block:
                lines.extend(context_block.splitlines())
                lines.append("")
            detail_lines.extend(note_context_detail_lines(note_hits, language=language))
        lines.extend([f"[Web Search via {display_name}]", f"{self._text(language, 'search_label', 'Search')}: {response.query}"])
        if self._is_recency_query(query):
            lines.append(
                self._text(
                    language,
                    "recency_note",
                    "Note: results with recognized publication dates are shown first.",
                )
            )
        target_coverage = self._target_coverage_rows(query, ordered_results)
        if target_coverage:
            lines.append("Target coverage for the answer (answer each listed target separately; do not claim a target is missing when it has a row here):")
            for row in target_coverage:
                entry = f"- {row['target']}: {row['title']}"
                if row["url"]:
                    entry += f" · {row['url']}"
                if row["engine"]:
                    entry += f" · {row['engine']}"
                if row["snippet"]:
                    entry += f"\n  Evidence snippet: {row['snippet']}"
                lines.append(entry)
        source_entries: list[dict[str, Any]] = []
        page_excerpts: dict[str, str] = {}
        fetch_attempts: set[str] = set()
        fetch_timeout = min(max(int(self._profile_value(profile, "timeout_seconds", 10) or 10), 2), 8)
        fetch_candidates = self._result_fetch_candidates(query, ordered_results)
        for url in fetch_candidates:
            fetch_attempts.add(url)
            base_url, _fragment = urldefrag(url)
            if base_url:
                fetch_attempts.add(base_url)
            excerpt = await self._fetch_page_excerpt(url, query=query, timeout_seconds=fetch_timeout)
            if excerpt:
                page_excerpts[url] = excerpt
                if base_url:
                    page_excerpts[base_url] = excerpt
        for index, result in enumerate(ordered_results, start=1):
            entry = f"- [{index}] {result.title}"
            if result.url:
                entry += f"\n  URL: {result.url}"
            if result.engine:
                entry += f"\n  Engine: {result.engine}"
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
                    "page_excerpt": bool(excerpt),
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
                "result_count": len(ordered_results),
                "explicit_url_count": len(explicit_urls),
                "fetch_attempt_count": len(fetch_candidates),
                "page_excerpt_count": len({value for value in page_excerpts.values()}),
                "official_supplement_count": supplemental_count,
                "official_supplement_error_count": len(supplemental_errors),
                "official_supplement_errors": supplemental_errors[:3],
                "target_coverage": target_coverage,
                "source_quality_outcome": (
                    "explicit_url_with_page_excerpt"
                    if explicit_urls and page_excerpts
                    else "explicit_url_without_page_excerpt"
                    if explicit_urls
                    else "search_results_with_page_excerpt"
                    if page_excerpts
                    else "search_results_only"
                ),
            },
        )
