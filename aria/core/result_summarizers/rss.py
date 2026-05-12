from __future__ import annotations

import html
import re
from pathlib import Path

from aria.core.i18n import I18NStore

_RSS_SUMMARY_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")
_RSS_ENTRY_RE = re.compile(r"^\d+\.\s+(.+)$")
_RSS_MARKDOWN_LINK_RE = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)(.*)$")
_RSS_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2})?")


def _rss_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _RSS_SUMMARY_I18N.t(language or "de", f"result_rss.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _entry_word(language: str | None, count: int) -> str:
    key = "entry_singular" if count == 1 else "entry_plural"
    return _rss_text(language, key, "entry" if count == 1 else "entries")


def _rss_terms(key: str, fallback: tuple[str, ...]) -> tuple[str, ...]:
    raw_values = [
        _RSS_SUMMARY_I18N.t("de", f"result_rss.{key}", ""),
        _RSS_SUMMARY_I18N.t("en", f"result_rss.{key}", ""),
    ]
    terms: list[str] = []
    for raw in raw_values:
        for item in str(raw or "").split("|"):
            clean = item.strip()
            if clean and clean not in terms:
                terms.append(clean)
    return tuple(terms) or fallback


def _match_category_header(first_line: str) -> re.Match[str] | None:
    for prefix in _rss_terms("category_header_prefixes", ("Latest entries from category",)):
        match = re.match(rf"^{re.escape(prefix)}\s+`?([^`]+?)`?:?$", first_line, re.IGNORECASE)
        if match:
            return match
    return None


def _split_source_suffix(value: str) -> tuple[str, str]:
    for label in _rss_terms("source_suffix_labels", ("Source",)):
        marker = f" · {label}: "
        if marker in value:
            return value.split(marker, 1)
    return value, ""


def _shorten(value: str, *, limit: int = 220) -> str:
    clean = " ".join(str(value or "").strip().split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "..."


def _parse_entry_headline(value: str) -> dict[str, str]:
    headline, source = _split_source_suffix(str(value or "").strip(" ."))
    headline = html.unescape(headline.strip(" ."))
    source = html.unescape(source.strip(" ."))
    link = ""
    match = _RSS_MARKDOWN_LINK_RE.match(headline)
    if match:
        headline = html.unescape(str(match.group(1) or "").strip())
        link = str(match.group(2) or "").strip()
        tail = str(match.group(3) or "").strip()
        if tail and not source:
            _, tail_source = _split_source_suffix(tail)
            source = html.unescape(tail_source.strip(" ."))
    return {"title": headline, "link": link, "source": source, "published": "", "summary": ""}


def _parse_entries(lines: list[str]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        clean = str(line or "").strip()
        if not clean:
            continue
        match = _RSS_ENTRY_RE.match(clean)
        if match:
            current = _parse_entry_headline(str(match.group(1) or ""))
            if current.get("title"):
                entries.append(current)
            continue
        if not current:
            continue
        if not current.get("published") and _RSS_TIMESTAMP_RE.match(clean):
            current["published"] = html.unescape(clean)
            continue
        if not current.get("summary"):
            current["summary"] = _shorten(html.unescape(clean))
    return entries


def _format_entry_title(entry: dict[str, str]) -> str:
    title = str(entry.get("title") or "").strip()
    link = str(entry.get("link") or "").strip()
    if link:
        return f"[{title}]({link})"
    return title


def _format_rss_digest(entries: list[dict[str, str]], *, group_name: str, language: str | None) -> str:
    if not entries:
        return ""
    count = len(entries)
    lines = [
        _rss_text(
            language,
            "digest",
            "RSS digest for `{group}`: {count} current {entry_word}.",
            group=group_name,
            count=count,
            entry_word=_entry_word(language, count),
        )
    ]
    link_label = _rss_text(language, "link_label", "Link")
    source_label = _rss_text(language, "source_label", "Source")
    summary_template = _rss_text(language, "summary", "Summary: {text}")
    for idx, entry in enumerate(entries[:6], start=1):
        title = _format_entry_title(entry)
        if not title:
            continue
        if len(lines) == 1:
            lines.append("")
        lines.append(f"{idx}. {title}")
        link = str(entry.get("link") or "").strip()
        if link:
            lines.append(f"   {link_label}: {link}")
        meta = []
        source = str(entry.get("source") or "").strip()
        published = str(entry.get("published") or "").strip()
        if source:
            meta.append(f"{source_label}: {source}")
        if published:
            meta.append(published)
        if meta:
            lines.append(f"   {' · '.join(meta)}")
        summary = str(entry.get("summary") or "").strip()
        if summary:
            lines.append(f"   {summary_template.format(text=summary)}")
    return "\n".join(lines).strip()


def summarize_rss_category_result_for_chat(text: str, *, language: str | None = None) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    lines = [str(line or "").rstrip() for line in clean_text.splitlines() if str(line or "").strip()]
    if not lines:
        return ""
    first = lines[0].strip()
    match = _match_category_header(first)
    if not match:
        return ""
    group_name = str(match.group(1) or "").strip() or "RSS"
    return _format_rss_digest(_parse_entries(lines[1:]), group_name=group_name, language=language)


def summarize_rss_group_result_for_chat(text: str, *, group_name: str, language: str | None = None) -> str:
    clean_text = str(text or "").strip()
    if not clean_text:
        return ""
    lines = [str(line or "").rstrip() for line in clean_text.splitlines() if str(line or "").strip()]
    if len(lines) < 2:
        return ""
    return _format_rss_digest(_parse_entries(lines[1:]), group_name=group_name, language=language)
