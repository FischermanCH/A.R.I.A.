from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.error import URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request as URLRequest, urlopen

RecipeText = Callable[..., str]

_RSS_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36 ARIA/1.0"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.8",
}
_FEED_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_FEED_TRACKING_KEYS = {
    "wt_mc",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "mkt_tok",
}


def xml_name(tag: str) -> str:
    raw = str(tag or "")
    return raw.split("}", 1)[-1].lower()


def clean_feed_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        query_pairs = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            lower_key = str(key or "").strip().lower()
            if lower_key.startswith("utm_") or lower_key in _FEED_TRACKING_KEYS:
                continue
            query_pairs.append((key, item))
        cleaned_query = urlencode(query_pairs, doseq=True)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, cleaned_query, ""))
    except Exception:
        return raw


def format_feed_timestamp(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return raw


def clean_feed_summary(value: str, limit: int = 220) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _FEED_BR_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    short = text[:limit].rsplit(" ", 1)[0].strip()
    return (short or text[:limit]).rstrip(".,;:") + "…"


def parse_feed_timestamp(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(raw)
        except Exception:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    try:
        return parsed.astimezone(timezone.utc)
    except Exception:
        return parsed


class RecipeRssRuntime:
    def __init__(
        self,
        *,
        get_connection_profile: Callable[[str, str], Any],
        truncate_text: Callable[[str, int], str],
        recipe_text: RecipeText,
    ) -> None:
        self.get_connection_profile = get_connection_profile
        self.truncate_text = truncate_text
        self.recipe_text = recipe_text

    def _text(self, language: str, key: str, default: str, **values: Any) -> str:
        return self.recipe_text(language, key, default, **values)

    def load_entries(self, connection_ref: str, *, language: str = "de") -> tuple[str, list[dict[str, str]]]:
        connection = self.get_connection_profile("rss", connection_ref)
        feed_url = str(getattr(connection, "feed_url", "")).strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not feed_url:
            raise ValueError(self._text(language, "message_922", "RSS feed URL is missing in the profile."))

        req = URLRequest(feed_url, headers=_RSS_HTTP_HEADERS, method="GET")
        try:
            with urlopen(req, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                payload = resp.read(1024 * 512)
        except URLError as exc:
            raise ValueError(self._text(language, "message_929", "RSS fetch failed: {exc}", exc=exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_931", "RSS fetch failed: {exc}", exc=exc)) from exc

        text = payload.decode("utf-8", errors="replace").strip()
        try:
            root = ET.fromstring(text)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(self._text(language, "message_937", "RSS feed is not valid XML: {exc}", exc=exc)) from exc

        entries: list[dict[str, str]] = []
        feed_title = ""
        root_name = xml_name(root.tag)
        if root_name == "rss":
            channel = next((child for child in root if xml_name(child.tag) == "channel"), None)
            if channel is not None:
                for item in channel:
                    item_name = xml_name(item.tag)
                    if item_name == "title" and not feed_title:
                        feed_title = str(item.text or "").strip() or feed_title
                        continue
                    if item_name != "item":
                        continue
                    title = ""
                    link = ""
                    published = ""
                    summary = ""
                    for child in item:
                        name = xml_name(child.tag)
                        if name == "title":
                            title = str(child.text or "").strip()
                        elif name == "link":
                            link = str(child.text or "").strip()
                        elif name in {"pubdate", "published", "updated"}:
                            published = str(child.text or "").strip()
                        elif name in {"description", "summary", "content", "content:encoded"}:
                            summary = ET.tostring(child, encoding="unicode", method="xml") if list(child) else str(child.text or "").strip()
                    if title or link:
                        entries.append({"title": title, "link": link, "published": published, "summary": summary})
        elif root_name == "feed":
            for item in root:
                item_name = xml_name(item.tag)
                if item_name == "title" and not feed_title:
                    feed_title = str(item.text or "").strip() or feed_title
                    continue
                if item_name != "entry":
                    continue
                title = ""
                link = ""
                published = ""
                summary = ""
                for child in item:
                    name = xml_name(child.tag)
                    if name == "title":
                        title = str(child.text or "").strip()
                    elif name == "link":
                        link = str(child.attrib.get("href", "") or child.text or "").strip()
                    elif name in {"updated", "published"}:
                        published = str(child.text or "").strip()
                    elif name in {"summary", "content", "subtitle"}:
                        summary = ET.tostring(child, encoding="unicode", method="xml") if list(child) else str(child.text or "").strip()
                if title or link:
                    entries.append({"title": title, "link": link, "published": published, "summary": summary})
        return feed_title, entries

    def execute_read(self, connection_ref: str, *, language: str = "de") -> str:
        feed_title, entries = self.load_entries(connection_ref, language=language)

        if not entries:
            return self.truncate_text(
                self._text(language, "message_999", "Feed `{connection_ref}` was loaded, but no entries were found.", connection_ref=connection_ref),
                1400,
            )

        lines = [
            self._text(
                language,
                "message_1007",
                "Latest entries from {feed_title_or_connection_ref}:",
                feed_title_or_connection_ref=feed_title or connection_ref,
            )
        ]
        for idx, item in enumerate(entries[:5], start=1):
            title = item.get("title", "").strip() or self._text(language, "message_1009", "(untitled)")
            link = clean_feed_url(item.get("link", ""))
            published = format_feed_timestamp(item.get("published", ""))
            summary = clean_feed_summary(item.get("summary", ""))
            line = f"{idx}. {title}"
            if link:
                line = f"{idx}. [{title}]({link})"
            if published:
                line += f"\n   {published}"
            lines.append(line)
            if summary:
                lines.append(f"   {summary}")
            if idx < min(len(entries), 5):
                lines.append("")
        return self.truncate_text("\n".join(lines), 1800)

    def execute_group_read(
        self,
        group_name: str,
        connection_refs: list[str],
        *,
        language: str = "de",
        entry_loader: Callable[..., tuple[str, list[dict[str, str]]]] | None = None,
    ) -> str:
        clean_group = str(group_name or "").strip() or self._text(language, "message_1026", "RSS category")
        refs = [str(item or "").strip() for item in list(connection_refs or []) if str(item or "").strip()]
        if not refs:
            raise ValueError(self._text(language, "message_1029", "RSS category contains no feeds."))

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        seen_titles: set[str] = set()

        for ref in refs[:6]:
            try:
                loader = entry_loader or self.load_entries
                feed_title, entries = loader(ref, language=language)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{ref}: {exc}")
                continue
            for item in entries[:1]:
                title = str(item.get("title", "") or "").strip()
                key = title.lower()
                if key and key in seen_titles:
                    continue
                if key:
                    seen_titles.add(key)
                rows.append(
                    {
                        "feed_title": str(feed_title or ref).strip(),
                        "connection_ref": ref,
                        "title": title,
                        "link": str(item.get("link", "") or "").strip(),
                        "published": str(item.get("published", "") or "").strip(),
                        "summary": str(item.get("summary", "") or "").strip(),
                        "published_dt": parse_feed_timestamp(str(item.get("published", "") or "").strip()),
                    }
                )

        if not rows:
            if errors:
                raise ValueError(
                    self._text(
                        language,
                        "message_1062",
                        "RSS category could not be read: {join_errors_3}",
                        join_errors_3="; ".join(errors[:3]),
                    )
                )
            raise ValueError(self._text(language, "message_1063", "RSS category contains no readable entries."))
        rows.sort(
            key=lambda item: (
                item.get("published_dt") is not None,
                item.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
                str(item.get("feed_title", "") or ""),
            ),
            reverse=True,
        )

        lines = [
            self._text(
                language,
                "message_1075",
                "Latest entries from category `{clean_group}`:",
                clean_group=clean_group,
            )
        ]
        for idx, item in enumerate(rows[:6], start=1):
            title = str(item.get("title", "") or "").strip() or self._text(language, "message_1082", "(untitled)")
            link = clean_feed_url(str(item.get("link", "") or "").strip())
            published = format_feed_timestamp(str(item.get("published", "") or "").strip())
            summary = clean_feed_summary(str(item.get("summary", "") or "").strip())
            source_label = str(item.get("feed_title", "") or item.get("connection_ref", "") or "").strip()
            line = f"{idx}. {title}"
            if link:
                line = f"{idx}. [{title}]({link})"
            if source_label:
                line += self._text(language, "message_1091", " · Source: {source_label}", source_label=source_label)
            if published:
                line += f"\n   {published}"
            lines.append(line)
            if summary:
                lines.append(f"   {summary}")
            if idx < min(len(rows), 6):
                lines.append("")
        return self.truncate_text("\n".join(lines), 2200)
