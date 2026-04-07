from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request as URLRequest, urlopen


@dataclass
class SearXNGSearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    published_at: str = ""
    published_label: str = ""


@dataclass
class SearXNGSearchResponse:
    query: str
    results: list[SearXNGSearchResult]
    raw: dict[str, Any]


class SearXNGClientError(RuntimeError):
    """Raised when a SearXNG query fails."""


class SearXNGClient:
    def __init__(self, *, user_agent: str = "ARIA/1.0") -> None:
        self.user_agent = user_agent

    @staticmethod
    def _normalize_list(values: Any) -> list[str]:
        if isinstance(values, list):
            items = values
        else:
            items = str(values or "").split(",")
        return [str(item).strip() for item in items if str(item).strip()]

    @staticmethod
    def _pick_engine(raw: Any) -> str:
        if isinstance(raw, list):
            engines = [str(item).strip() for item in raw if str(item).strip()]
            return ", ".join(engines[:2])
        return str(raw or "").strip()

    @staticmethod
    def _clean_text(value: Any, limit: int) -> str:
        text = str(value or "").strip()
        if len(text) <= limit:
            return text
        shortened = text[:limit].rsplit(" ", 1)[0].strip()
        return (shortened or text[:limit]).rstrip(".,;:") + "…"

    @staticmethod
    def _normalize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _parse_published_datetime(cls, raw: Any) -> datetime | None:
        if raw in (None, "", 0):
            return None
        if isinstance(raw, (int, float)):
            timestamp = float(raw)
            if timestamp > 1_000_000_000_000:
                timestamp = timestamp / 1000.0
            if timestamp <= 0:
                return None
            try:
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None

        text = str(raw or "").strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        for candidate in (normalized, normalized.replace(" UTC", "+00:00")):
            try:
                return cls._normalize_datetime(datetime.fromisoformat(candidate))
            except ValueError:
                pass
        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d.%m.%Y",
            "%d.%m.%Y %H:%M",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
        ):
            try:
                return cls._normalize_datetime(datetime.strptime(text, fmt))
            except ValueError:
                continue
        try:
            return cls._normalize_datetime(parsedate_to_datetime(text))
        except (TypeError, ValueError, IndexError):
            return None

    @classmethod
    def _extract_published_meta(cls, item: dict[str, Any]) -> tuple[str, str]:
        for key in (
            "publishedDate",
            "published_date",
            "published_at",
            "publishedAt",
            "pubdate",
            "pubDate",
            "created_at",
            "createdAt",
            "date",
            "published",
        ):
            parsed = cls._parse_published_datetime(item.get(key))
            if parsed is None:
                continue
            return parsed.isoformat(), parsed.date().isoformat()
        return "", ""

    def _search_sync(
        self,
        *,
        base_url: str,
        query: str,
        timeout_seconds: int,
        language: str = "",
        safe_search: int = 1,
        categories: list[str] | None = None,
        engines: list[str] | None = None,
        time_range: str = "",
        max_results: int = 5,
    ) -> SearXNGSearchResponse:
        clean_base_url = str(base_url or "").strip().rstrip("/")
        clean_query = str(query or "").strip()
        if not clean_base_url:
            raise SearXNGClientError("SearXNG base URL fehlt.")
        if not clean_query:
            raise SearXNGClientError("Suchanfrage fehlt.")

        params: dict[str, Any] = {
            "q": clean_query,
            "format": "json",
            "pageno": 1,
            "safesearch": max(0, min(int(safe_search or 0), 2)),
        }
        if language:
            params["language"] = str(language).strip()
        category_rows = self._normalize_list(categories or [])
        if category_rows:
            params["categories"] = ",".join(category_rows)
        engine_rows = self._normalize_list(engines or [])
        if engine_rows:
            params["engines"] = ",".join(engine_rows)
        if time_range:
            params["time_range"] = str(time_range).strip()

        target_url = f"{clean_base_url}/search?{urlencode(params)}"
        request = URLRequest(
            target_url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=max(5, int(timeout_seconds or 10))) as response:  # noqa: S310
                status_code = int(getattr(response, "status", 200) or 200)
                payload = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            if int(getattr(exc, "code", 0) or 0) == 429:
                raise SearXNGClientError(
                    "SearXNG request failed with HTTP 429 Too Many Requests. The internal SearXNG limiter is likely still active; set SEARXNG_LIMITER=false in the stack."
                ) from exc
            raise SearXNGClientError(f"SearXNG request failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise SearXNGClientError(f"SearXNG request failed: {exc}") from exc

        if status_code >= 400:
            raise SearXNGClientError(f"SearXNG request failed with HTTP {status_code}")

        try:
            data = json.loads(payload)
        except Exception as exc:  # noqa: BLE001
            raise SearXNGClientError(f"SearXNG returned invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise SearXNGClientError("SearXNG returned an unexpected JSON payload.")

        parsed_results: list[SearXNGSearchResult] = []
        for item in list(data.get("results") or [])[: max(1, min(int(max_results or 5), 10))]:
            if not isinstance(item, dict):
                continue
            title = self._clean_text(item.get("title", ""), 180)
            url = str(item.get("url", "")).strip()
            snippet = self._clean_text(item.get("content", "") or item.get("snippet", ""), 320)
            engine = self._pick_engine(item.get("engines") or item.get("engine"))
            published_at, published_label = self._extract_published_meta(item)
            if not title and not url:
                continue
            parsed_results.append(
                SearXNGSearchResult(
                    title=title or url,
                    url=url,
                    snippet=snippet,
                    engine=engine,
                    published_at=published_at,
                    published_label=published_label,
                )
            )

        return SearXNGSearchResponse(query=clean_query, results=parsed_results, raw=data)

    async def search(
        self,
        *,
        base_url: str,
        query: str,
        timeout_seconds: int,
        language: str = "",
        safe_search: int = 1,
        categories: list[str] | None = None,
        engines: list[str] | None = None,
        time_range: str = "",
        max_results: int = 5,
    ) -> SearXNGSearchResponse:
        return await asyncio.to_thread(
            self._search_sync,
            base_url=base_url,
            query=query,
            timeout_seconds=timeout_seconds,
            language=language,
            safe_search=safe_search,
            categories=categories or [],
            engines=engines or [],
            time_range=time_range,
            max_results=max_results,
        )
