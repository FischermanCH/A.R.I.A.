from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(slots=True)
class OPMLFeedEntry:
    title: str
    feed_url: str
    tags: list[str]


def _clean_text(value: Any, *, max_length: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:max_length].strip()


def _clean_tags(values: list[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        clean = _clean_text(value, max_length=40).strip(" ,;")
        if clean:
            tags.append(clean)
    return list(dict.fromkeys(tags))[:12]


def _default_title(feed_url: str) -> str:
    parsed = urlparse(str(feed_url or "").strip())
    host = str(parsed.netloc or "").strip()
    if host.startswith("www."):
        host = host[4:]
    path_bits = [part for part in str(parsed.path or "").split("/") if part]
    if host and path_bits:
        return _clean_text(f"{host} {path_bits[-1].replace('-', ' ')}", max_length=160)
    return _clean_text(host or feed_url or "RSS Feed", max_length=160)


def _feed_from_outline(node: ET.Element, parent_tags: list[str]) -> OPMLFeedEntry | None:
    feed_url = _clean_text(node.attrib.get("xmlUrl") or node.attrib.get("xmlurl") or node.attrib.get("url"), max_length=512)
    if not feed_url:
        return None
    title = _clean_text(node.attrib.get("title") or node.attrib.get("text"), max_length=160) or _default_title(feed_url)
    node_tags = list(parent_tags)
    category_raw = _clean_text(node.attrib.get("category"), max_length=240)
    if category_raw:
        node_tags.extend(part.strip() for part in category_raw.split(",") if part.strip())
    return OPMLFeedEntry(title=title, feed_url=feed_url, tags=_clean_tags(node_tags))


def parse_opml_feeds(raw_xml: str) -> list[OPMLFeedEntry]:
    root = ET.fromstring(str(raw_xml or "").strip())
    feeds: list[OPMLFeedEntry] = []
    seen_urls: set[str] = set()

    def _walk(node: ET.Element, parent_tags: list[str]) -> None:
        node_title = _clean_text(node.attrib.get("title") or node.attrib.get("text"), max_length=80)
        next_tags = [*parent_tags]
        if node.tag.lower().endswith("outline") and node_title:
            next_tags.append(node_title)

        feed = _feed_from_outline(node, parent_tags)
        if feed is not None and feed.feed_url not in seen_urls:
            feeds.append(feed)
            seen_urls.add(feed.feed_url)

        for child in list(node):
            _walk(child, next_tags)

    body = root.find("body")
    walk_root = body if body is not None else root
    for child in list(walk_root):
        _walk(child, [])

    return feeds


def build_opml_document(feeds: list[dict[str, Any]], *, title: str = "ARIA RSS Export") -> str:
    opml = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = _clean_text(title, max_length=160) or "ARIA RSS Export"
    body = ET.SubElement(opml, "body")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in feeds:
        if not isinstance(row, dict):
            continue
        feed_url = _clean_text(row.get("feed_url"), max_length=512)
        if not feed_url:
            continue
        tags_raw = row.get("tags", [])
        tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
        group_name = _clean_text(row.get("group_name"), max_length=80) or (
            _clean_text(tags[0], max_length=80) if tags else "Weitere Feeds"
        )
        grouped.setdefault(group_name or "Weitere Feeds", []).append(row)

    for group_name in sorted(grouped.keys(), key=lambda value: value.lower()):
        group_node = ET.SubElement(body, "outline", {"text": group_name, "title": group_name})
        for row in sorted(grouped[group_name], key=lambda item: str(item.get("title") or item.get("ref") or "").lower()):
            feed_url = _clean_text(row.get("feed_url"), max_length=512)
            title_text = _clean_text(row.get("title") or row.get("ref") or "", max_length=160) or _default_title(feed_url)
            tags_raw = row.get("tags", [])
            tags = [str(item).strip() for item in tags_raw if str(item).strip()] if isinstance(tags_raw, list) else []
            attrs = {
                "text": title_text,
                "title": title_text,
                "type": "rss",
                "xmlUrl": feed_url,
            }
            extra_tags = [tag for tag in tags if tag != group_name]
            if extra_tags:
                attrs["category"] = ", ".join(_clean_tags(extra_tags))
            ET.SubElement(group_node, "outline", attrs)

    return ET.tostring(opml, encoding="unicode", xml_declaration=True)
