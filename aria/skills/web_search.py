from __future__ import annotations

from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

from aria.core.config import resolve_searxng_base_url
from aria.core.searxng_client import SearXNGClient, SearXNGClientError
from aria.skills.base import BaseSkill, SkillResult


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "Runs a web search via a configured SearXNG instance."
    max_context_chars = 2200

    def __init__(self, *, settings: Any, client: SearXNGClient | None = None):
        self.settings = settings
        self.client = client or SearXNGClient()

    _QUERY_STOPWORDS = {
        "a",
        "an",
        "and",
        "auf",
        "bot",
        "das",
        "den",
        "der",
        "die",
        "ein",
        "eine",
        "einen",
        "einer",
        "es",
        "for",
        "gibt",
        "gibts",
        "im",
        "in",
        "internet",
        "ist",
        "last",
        "latest",
        "letzten",
        "letzter",
        "letztes",
        "mit",
        "nach",
        "neu",
        "neueste",
        "neuesten",
        "neuigkeiten",
        "news",
        "online",
        "release",
        "releases",
        "search",
        "suche",
        "the",
        "ueber",
        "update",
        "updates",
        "vom",
        "von",
        "was",
        "web",
        "wie",
        "what",
        "zu",
    }

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

    @staticmethod
    def _detail_line(title: str, url: str, engine: str, published_label: str = "") -> str:
        parts = [f"Quelle: {title}"]
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
                "letzter",
                "letzte",
                "letztes",
                "neuester",
                "neuste",
                "neuest",
                "aktuellster",
                "latest",
                "newest",
                "most recent",
                "recent",
                "release",
                "update",
                "erschein",
                "veröffentlicht",
                "veroeffentlicht",
            )
        )

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
            if token in cls._QUERY_STOPWORDS:
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

    def _prepare_results(self, query: str, results: list[Any]) -> list[Any]:
        prepared = list(results)
        recency_query = self._is_recency_query(query)
        scored: list[tuple[int, int, float, int, Any]] = []
        has_relevant_match = False
        for item in prepared:
            score, matches = self._result_relevance_score(query, item)
            if matches > 0:
                has_relevant_match = True
            scored.append(
                (
                    score,
                    matches,
                    self._published_sort_value(getattr(item, "published_at", "")),
                    1 if "news" in str(getattr(item, "engine", "") or "").lower() else 0,
                    item,
                )
            )

        if has_relevant_match:
            scored = [row for row in scored if row[1] > 0]

        scored.sort(
            key=lambda row: (
                row[1],
                row[0],
                row[2] if recency_query else 0.0,
                row[3] if recency_query else 0,
            ),
            reverse=True,
        )
        return [row[4] for row in scored]

    async def execute(self, query: str, params: dict) -> SkillResult:
        selected = self._select_profile(query, explicit_ref=str(params.get("connection_ref", "")))
        if selected is None:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error="Keine SearXNG-Verbindung konfiguriert.",
            )
        ref, profile = selected
        display_name = str(self._profile_value(profile, "title", "")).strip() or ref
        try:
            response = await self.client.search(
                base_url=resolve_searxng_base_url(str(self._profile_value(profile, "base_url", "")).strip()),
                query=str(query or "").strip(),
                timeout_seconds=int(self._profile_value(profile, "timeout_seconds", 10) or 10),
                language=str(self._profile_value(profile, "language", "")).strip(),
                safe_search=int(self._profile_value(profile, "safe_search", 1) or 1),
                categories=self._profile_list(profile, "categories"),
                engines=self._profile_list(profile, "engines"),
                time_range=str(self._profile_value(profile, "time_range", "")).strip(),
                max_results=int(self._profile_value(profile, "max_results", 5) or 5),
            )
        except SearXNGClientError as exc:
            return SkillResult(
                skill_name=self.name,
                content="",
                success=False,
                error=f"Websuche fehlgeschlagen: {exc}",
            )

        ordered_results = self._prepare_results(query, response.results)

        if not ordered_results:
            return SkillResult(
                skill_name=self.name,
                content="[Web Search]\nKeine Web-Treffer gefunden.",
                success=True,
                metadata={"detail_lines": [f"Websuche via {display_name} · 0 Treffer"]},
            )

        lines = [f"[Web Search via {display_name}]", f"Suche: {response.query}"]
        if self._is_recency_query(query):
            lines.append("Hinweis: Treffer mit erkannten Datumsangaben werden zuerst gezeigt.")
        detail_lines: list[str] = []
        source_entries: list[dict[str, Any]] = []
        for index, result in enumerate(ordered_results, start=1):
            entry = f"- [{index}] {result.title}"
            if result.url:
                entry += f"\n  URL: {result.url}"
            if result.engine:
                entry += f"\n  Engine: {result.engine}"
            if result.published_label:
                entry += f"\n  Datum: {result.published_label}"
            if result.snippet:
                entry += f"\n  Snippet: {result.snippet}"
            lines.append(entry)
            detail = self._detail_line(result.title, result.url, result.engine, result.published_label)
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
            },
        )
