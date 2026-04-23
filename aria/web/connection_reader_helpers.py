from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen


@dataclass(frozen=True)
class ConnectionReaderHelperDeps:
    base_dir: Path
    pipeline: Any
    read_raw_config: Callable[[], dict[str, Any]]
    get_secure_store: Callable[[dict[str, Any] | None], Any]
    sanitize_connection_name: Callable[[str | None], str]
    normalize_rss_feed_url_for_dedupe: Callable[[str | None], str]
    read_connection_metadata: Callable[[dict[str, Any]], dict[str, Any]]
    resolve_searxng_base_url: Callable[[str], str]
    suggest_connection_metadata_with_llm: Callable[..., Any]
    connection_metadata_is_sparse: Callable[..., bool]
    web_metadata_headers: dict[str, str]
    rss_metadata_headers: dict[str, str]


@dataclass(frozen=True)
class ConnectionReaderHelperBundle:
    read_ssh_connections: Any
    read_discord_connections: Any
    read_sftp_connections: Any
    read_smb_connections: Any
    read_webhook_connections: Any
    read_email_connections: Any
    read_imap_connections: Any
    read_http_api_connections: Any
    read_google_calendar_connections: Any
    read_rss_poll_interval_minutes: Any
    extract_html_attribute_map: Any
    clean_html_text: Any
    extract_ssh_service_seed: Any
    extract_rss_feed_seed: Any
    suggest_rss_metadata_with_llm: Any
    suggest_ssh_metadata_with_llm: Any
    autofill_service_connection_metadata: Any
    suggest_website_metadata_with_llm: Any
    autofill_website_connection_metadata: Any
    read_rss_connections: Any
    read_website_connections: Any
    read_searxng_connections: Any
    read_mqtt_connections: Any
    next_rss_import_ref: Any


def build_connection_reader_helpers(deps: ConnectionReaderHelperDeps) -> ConnectionReaderHelperBundle:
    BASE_DIR = deps.base_dir
    pipeline = deps.pipeline
    _read_raw_config = deps.read_raw_config
    _get_secure_store = deps.get_secure_store
    _sanitize_connection_name = deps.sanitize_connection_name
    _normalize_rss_feed_url_for_dedupe = deps.normalize_rss_feed_url_for_dedupe
    _read_connection_metadata = deps.read_connection_metadata
    resolve_searxng_base_url = deps.resolve_searxng_base_url
    suggest_connection_metadata_with_llm = deps.suggest_connection_metadata_with_llm
    connection_metadata_is_sparse = deps.connection_metadata_is_sparse
    _WEB_METADATA_HEADERS = deps.web_metadata_headers
    _RSS_METADATA_HEADERS = deps.rss_metadata_headers

    def _read_ssh_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            ssh = connections.get("ssh", {})
            if not isinstance(ssh, dict):
                return {}
            rows: dict[str, dict[str, Any]] = {}
            for key, value in ssh.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                rows[ref] = {
                    "host": str(value.get("host", "")).strip(),
                    "port": int(value.get("port", 22) or 22),
                    "user": str(value.get("user", "")).strip(),
                    "service_url": str(value.get("service_url", "")).strip(),
                    "key_path": str(value.get("key_path", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 20) or 20),
                    "strict_host_key_checking": str(value.get("strict_host_key_checking", "accept-new")).strip() or "accept-new",
                    "allow_commands": list(value.get("allow_commands", []) if isinstance(value.get("allow_commands", []), list) else []),
                    "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_discord_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            discord = connections.get("discord", {})
            if not isinstance(discord, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in discord.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                webhook = store.get_secret(f"connections.discord.{ref}.webhook_url", default="") if store else ""
                rows[ref] = {
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "send_test_messages": bool(value.get("send_test_messages", True)),
                    "allow_skill_messages": bool(value.get("allow_skill_messages", True)),
                    "alert_skill_errors": bool(value.get("alert_skill_errors", False)),
                    "alert_safe_fix": bool(value.get("alert_safe_fix", False)),
                    "alert_connection_changes": bool(value.get("alert_connection_changes", False)),
                    "alert_system_events": bool(value.get("alert_system_events", False)),
                    "webhook_url": webhook,
                    "webhook_present": bool(webhook),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_sftp_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            sftp = connections.get("sftp", {})
            if not isinstance(sftp, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in sftp.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                password = store.get_secret(f"connections.sftp.{ref}.password", default="") if store else ""
                key_path = str(value.get("key_path", "")).strip()
                key_exists = False
                if key_path:
                    candidate = Path(key_path)
                    if not candidate.is_absolute():
                        candidate = (BASE_DIR / candidate).resolve()
                    key_exists = candidate.exists()
                rows[ref] = {
                    "host": str(value.get("host", "")).strip(),
                    "port": int(value.get("port", 22) or 22),
                    "user": str(value.get("user", "")).strip(),
                    "service_url": str(value.get("service_url", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "root_path": str(value.get("root_path", "")).strip(),
                    "key_path": key_path,
                    "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                    "key_present": key_exists,
                    "password": password,
                    "password_present": bool(password),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_smb_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            smb = connections.get("smb", {})
            if not isinstance(smb, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in smb.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                password = store.get_secret(f"connections.smb.{ref}.password", default="") if store else ""
                rows[ref] = {
                    "host": str(value.get("host", "")).strip(),
                    "port": int(value.get("port", 445) or 445),
                    "share": str(value.get("share", "")).strip(),
                    "user": str(value.get("user", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "root_path": str(value.get("root_path", "")).strip(),
                    "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                    "password": password,
                    "password_present": bool(password),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_webhook_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            webhook = connections.get("webhook", {})
            if not isinstance(webhook, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in webhook.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                url = store.get_secret(f"connections.webhook.{ref}.url", default="") if store else ""
                rows[ref] = {
                    "url": url,
                    "url_present": bool(url),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "method": str(value.get("method", "POST")).strip().upper() or "POST",
                    "content_type": str(value.get("content_type", "application/json")).strip() or "application/json",
                    "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_email_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            email = connections.get("email", {})
            if not isinstance(email, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in email.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                password = store.get_secret(f"connections.email.{ref}.password", default="") if store else ""
                rows[ref] = {
                    "smtp_host": str(value.get("smtp_host", "")).strip(),
                    "port": int(value.get("port", 587) or 587),
                    "user": str(value.get("user", "")).strip(),
                    "from_email": str(value.get("from_email", "")).strip(),
                    "to_email": str(value.get("to_email", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "starttls": bool(value.get("starttls", True)),
                    "use_ssl": bool(value.get("use_ssl", False)),
                    "password": password,
                    "password_present": bool(password),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_imap_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            imap = connections.get("imap", {})
            if not isinstance(imap, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in imap.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                password = store.get_secret(f"connections.imap.{ref}.password", default="") if store else ""
                rows[ref] = {
                    "host": str(value.get("host", "")).strip(),
                    "port": int(value.get("port", 993) or 993),
                    "user": str(value.get("user", "")).strip(),
                    "mailbox": str(value.get("mailbox", "INBOX")).strip() or "INBOX",
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "use_ssl": bool(value.get("use_ssl", True)),
                    "password": password,
                    "password_present": bool(password),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_http_api_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            http_api = connections.get("http_api", {})
            if not isinstance(http_api, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in http_api.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                auth_token = store.get_secret(f"connections.http_api.{ref}.auth_token", default="") if store else ""
                rows[ref] = {
                    "base_url": str(value.get("base_url", "")).strip(),
                    "health_path": str(value.get("health_path", "/")).strip() or "/",
                    "method": str(value.get("method", "GET")).strip().upper() or "GET",
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "auth_token": auth_token,
                    "auth_token_present": bool(auth_token),
                    "guardrail_ref": str(value.get("guardrail_ref", "")).strip(),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_google_calendar_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            google_calendar = connections.get("google_calendar", {})
            if not isinstance(google_calendar, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in google_calendar.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                client_secret = store.get_secret(f"connections.google_calendar.{ref}.client_secret", default="") if store else ""
                refresh_token = store.get_secret(f"connections.google_calendar.{ref}.refresh_token", default="") if store else ""
                rows[ref] = {
                    "calendar_id": str(value.get("calendar_id", "primary")).strip() or "primary",
                    "client_id": str(value.get("client_id", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "client_secret": client_secret,
                    "client_secret_present": bool(client_secret),
                    "refresh_token": refresh_token,
                    "refresh_token_present": bool(refresh_token),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_rss_poll_interval_minutes(raw: dict[str, Any] | None = None) -> int:
            source = raw if isinstance(raw, dict) else _read_raw_config()
            rss_settings = source.get("rss", {}) if isinstance(source, dict) else {}
            if not isinstance(rss_settings, dict):
                rss_settings = {}
            try:
                poll_interval = int(rss_settings.get("poll_interval_minutes", 60) or 60)
            except (TypeError, ValueError):
                poll_interval = 60
            return max(1, min(poll_interval, 10080))

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

    def _extract_ssh_service_seed(service_url: str) -> dict[str, Any]:
            clean_url = str(service_url or "").strip()
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
            req = URLRequest(clean_url, headers=_WEB_METADATA_HEADERS, method="GET")
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

    def _extract_rss_feed_seed(feed_url: str) -> dict[str, Any]:
            clean_url = str(feed_url or "").strip()
            parsed = urlparse(clean_url)
            host = str(parsed.netloc or "").strip()
            host_short = host[4:] if host.startswith("www.") else host
            fallback_aliases = [value for value in [host_short, host_short.split(".", 1)[0].replace("-", " ")] if value]
            seed = {
                "feed_title": host_short or clean_url,
                "feed_description": "",
                "entry_titles": [],
                "host": host_short,
                "aliases": fallback_aliases,
            }
            if not clean_url:
                return seed
            req = URLRequest(clean_url, headers=_RSS_METADATA_HEADERS, method="GET")
            try:
                with urlopen(req, timeout=10) as resp:  # noqa: S310
                    payload = resp.read(256 * 1024)
            except Exception:
                return seed
            text = payload.decode("utf-8", errors="replace").strip()
            if not text or text.startswith("{") or text.startswith("["):
                return seed
            try:
                root = ET.fromstring(text)
            except Exception:
                return seed
            root_title = ""
            root_description = ""
            entry_titles: list[str] = []
            for elem in root.iter():
                tag = str(elem.tag or "").split("}", 1)[-1].lower()
                value = str(elem.text or "").strip()
                if not value:
                    continue
                if tag == "channel":
                    continue
                if tag == "title" and not root_title:
                    root_title = value[:120]
                elif tag in {"description", "subtitle", "summary"} and not root_description:
                    root_description = value[:240]
                elif tag == "title" and root_title and len(entry_titles) < 8 and value != root_title:
                    entry_titles.append(value[:120])
            if root_title:
                seed["feed_title"] = root_title
            if root_description:
                seed["feed_description"] = root_description
            seed["entry_titles"] = entry_titles
            return seed

    async def _suggest_rss_metadata_with_llm(
            *,
            feed_url: str,
            connection_ref: str,
            current_title: str,
            current_description: str,
            current_aliases: str,
            current_tags: str,
            group_name: str,
            lang: str,
        ) -> dict[str, Any]:
            seed = _extract_rss_feed_seed(feed_url)
            return await suggest_connection_metadata_with_llm(
                getattr(pipeline, "llm_client", None),
                connection_kind_label="RSS",
                connection_ref=connection_ref,
                source_label="Feed URL",
                source_value=feed_url,
                detected_title=seed["feed_title"],
                detected_description=seed["feed_description"],
                detected_keywords=[],
                fallback_aliases=seed["aliases"],
                current_title=current_title,
                current_description=current_description,
                current_aliases=current_aliases,
                current_tags=current_tags,
                lang=lang,
                goal_text=(
                    "Goal: produce user-friendly metadata that helps ARIA route chat requests to this RSS connection. "
                    "Aliases should contain the terms people would naturally use when referring to this feed in the preferred language. "
                    f"Current group: {str(group_name or '').strip() or '-'}\n"
                    f"Example entries: {', '.join(seed['entry_titles']) or '-'}"
                ),
            )

    async def _suggest_ssh_metadata_with_llm(
            *,
            service_url: str,
            connection_ref: str,
            current_title: str,
            current_description: str,
            current_aliases: str,
            current_tags: str,
            lang: str,
        ) -> dict[str, Any]:
            seed = _extract_ssh_service_seed(service_url)
            return await suggest_connection_metadata_with_llm(
                getattr(pipeline, "llm_client", None),
                connection_kind_label="SSH",
                connection_ref=connection_ref,
                source_label="Service URL",
                source_value=service_url,
                detected_title=seed["service_title"],
                detected_description=seed["service_description"],
                detected_keywords=seed["keywords"],
                fallback_aliases=seed["aliases"],
                current_title=current_title,
                current_description=current_description,
                current_aliases=current_aliases,
                current_tags=current_tags,
                lang=lang,
                goal_text=(
                    "Goal: produce user-friendly metadata that helps ARIA route chat requests to this SSH connection. "
                    "Aliases should reflect how someone would naturally refer to the service behind this host."
                ),
            )

    async def _suggest_website_metadata_with_llm(
            *,
            url: str,
            connection_ref: str,
            current_title: str,
            current_description: str,
            current_aliases: str,
            current_tags: str,
            group_name: str,
            lang: str,
        ) -> dict[str, Any]:
            seed = _extract_ssh_service_seed(url)
            return await suggest_connection_metadata_with_llm(
                getattr(pipeline, "llm_client", None),
                connection_kind_label="Website",
                connection_ref=connection_ref,
                source_label="URL",
                source_value=url,
                detected_title=seed["service_title"],
                detected_description=seed["service_description"],
                detected_keywords=seed["keywords"],
                fallback_aliases=seed["aliases"],
                current_title=current_title,
                current_description=current_description,
                current_aliases=current_aliases,
                current_tags=current_tags,
                lang=lang,
                goal_text=(
                    "Goal: produce concise metadata that helps ARIA recognize this watched website in chat and source lists. "
                    "Prefer natural aliases people would actually use. "
                    f"Current group: {str(group_name or '').strip() or '-'}"
                ),
            )

    async def _autofill_service_connection_metadata(
            *,
            connection_ref: str,
            service_url: str,
            current_title: str,
            current_description: str,
            current_aliases: str,
            current_tags: str,
            lang: str,
        ) -> tuple[dict[str, str], bool]:
            metadata = {
                "title": str(current_title or "").strip(),
                "description": str(current_description or "").strip(),
                "aliases": str(current_aliases or "").strip(),
                "tags": str(current_tags or "").strip(),
            }
            clean_service_url = str(service_url or "").strip()
            if not clean_service_url:
                return metadata, False
            if not connection_metadata_is_sparse(
                title=metadata["title"],
                description=metadata["description"],
                aliases=metadata["aliases"],
                tags=metadata["tags"],
            ):
                return metadata, False
            suggestion = await _suggest_ssh_metadata_with_llm(
                service_url=clean_service_url,
                connection_ref=connection_ref,
                current_title=metadata["title"],
                current_description=metadata["description"],
                current_aliases=metadata["aliases"],
                current_tags=metadata["tags"],
                lang=lang,
            )
            return (
                {
                    "title": str(suggestion.get("title", "") or "").strip(),
                    "description": str(suggestion.get("description", "") or "").strip(),
                    "aliases": str(suggestion.get("aliases", "") or "").strip(),
                    "tags": str(suggestion.get("tags", "") or "").strip(),
                },
                True,
            )

    async def _autofill_website_connection_metadata(
            *,
            connection_ref: str,
            url: str,
            current_title: str,
            current_description: str,
            current_aliases: str,
            current_tags: str,
            group_name: str,
            lang: str,
        ) -> tuple[dict[str, str], bool]:
            metadata = {
                "title": str(current_title or "").strip(),
                "description": str(current_description or "").strip(),
                "aliases": str(current_aliases or "").strip(),
                "tags": str(current_tags or "").strip(),
            }
            clean_url = str(url or "").strip()
            if not clean_url:
                return metadata, False
            if not connection_metadata_is_sparse(
                title=metadata["title"],
                description=metadata["description"],
                aliases=metadata["aliases"],
                tags=metadata["tags"],
            ):
                return metadata, False
            suggestion = await _suggest_website_metadata_with_llm(
                url=clean_url,
                connection_ref=connection_ref,
                current_title=metadata["title"],
                current_description=metadata["description"],
                current_aliases=metadata["aliases"],
                current_tags=metadata["tags"],
                group_name=group_name,
                lang=lang,
            )
            return (
                {
                    "title": str(suggestion.get("title", "") or "").strip(),
                    "description": str(suggestion.get("description", "") or "").strip(),
                    "aliases": str(suggestion.get("aliases", "") or "").strip(),
                    "tags": str(suggestion.get("tags", "") or "").strip(),
                },
                True,
            )

    def _read_rss_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            rss = connections.get("rss", {})
            if not isinstance(rss, dict):
                return {}
            poll_interval_minutes = _read_rss_poll_interval_minutes(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in rss.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                rows[ref] = {
                    "feed_url": str(value.get("feed_url", "")).strip(),
                    "group_name": str(value.get("group_name", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "poll_interval_minutes": poll_interval_minutes,
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_website_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            websites = connections.get("website", {})
            if not isinstance(websites, dict):
                return {}
            rows: dict[str, dict[str, Any]] = {}
            for key, value in websites.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                rows[ref] = {
                    "url": str(value.get("url", "")).strip(),
                    "group_name": str(value.get("group_name", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_searxng_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            searxng = connections.get("searxng", {})
            if not isinstance(searxng, dict):
                return {}
            rows: dict[str, dict[str, Any]] = {}
            for key, value in searxng.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                safe_search = int(value.get("safe_search", 1) or 1)
                max_results = int(value.get("max_results", 5) or 5)
                rows[ref] = {
                    "base_url": resolve_searxng_base_url(str(value.get("base_url", "")).strip()),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "language": str(value.get("language", "de-CH")).strip() or "de-CH",
                    "safe_search": max(0, min(safe_search, 2)),
                    "categories": [str(item).strip() for item in (value.get("categories", []) or []) if str(item).strip()],
                    "engines": [str(item).strip() for item in (value.get("engines", []) or []) if str(item).strip()],
                    "time_range": str(value.get("time_range", "")).strip(),
                    "max_results": max(1, min(max_results, 20)),
                    **_read_connection_metadata(value),
                }
            return rows

    def _read_mqtt_connections() -> dict[str, dict[str, Any]]:
            raw = _read_raw_config()
            connections = raw.get("connections", {})
            if not isinstance(connections, dict):
                return {}
            mqtt = connections.get("mqtt", {})
            if not isinstance(mqtt, dict):
                return {}
            store = _get_secure_store(raw)
            rows: dict[str, dict[str, Any]] = {}
            for key, value in mqtt.items():
                ref = _sanitize_connection_name(key)
                if not ref or not isinstance(value, dict):
                    continue
                password = store.get_secret(f"connections.mqtt.{ref}.password", default="") if store else ""
                rows[ref] = {
                    "host": str(value.get("host", "")).strip(),
                    "port": int(value.get("port", 1883) or 1883),
                    "user": str(value.get("user", "")).strip(),
                    "topic": str(value.get("topic", "")).strip(),
                    "timeout_seconds": int(value.get("timeout_seconds", 10) or 10),
                    "use_tls": bool(value.get("use_tls", False)),
                    "password": password,
                    "password_present": bool(password),
                    **_read_connection_metadata(value),
                }
            return rows

    def _next_rss_import_ref(rows: dict[str, Any], title: str, feed_url: str) -> str:
            normalized_feed_url = _normalize_rss_feed_url_for_dedupe(feed_url) or feed_url
            parsed_host = urlparse(normalized_feed_url).netloc.replace("www.", "")
            seed = _sanitize_connection_name(title) or _sanitize_connection_name(parsed_host) or "rss-feed"
            if seed not in rows:
                return seed
            for idx in range(2, 1000):
                candidate = _sanitize_connection_name(f"{seed}-{idx}")
                if candidate and candidate not in rows:
                    return candidate
            raise ValueError("Kein freier RSS-Ref mehr für OPML-Import gefunden.")

    return ConnectionReaderHelperBundle(
        read_ssh_connections=_read_ssh_connections,
        read_discord_connections=_read_discord_connections,
        read_sftp_connections=_read_sftp_connections,
        read_smb_connections=_read_smb_connections,
        read_webhook_connections=_read_webhook_connections,
        read_email_connections=_read_email_connections,
        read_imap_connections=_read_imap_connections,
        read_http_api_connections=_read_http_api_connections,
        read_google_calendar_connections=_read_google_calendar_connections,
        read_rss_poll_interval_minutes=_read_rss_poll_interval_minutes,
        extract_html_attribute_map=_extract_html_attribute_map,
        clean_html_text=_clean_html_text,
        extract_ssh_service_seed=_extract_ssh_service_seed,
        extract_rss_feed_seed=_extract_rss_feed_seed,
        suggest_rss_metadata_with_llm=_suggest_rss_metadata_with_llm,
        suggest_ssh_metadata_with_llm=_suggest_ssh_metadata_with_llm,
        autofill_service_connection_metadata=_autofill_service_connection_metadata,
        suggest_website_metadata_with_llm=_suggest_website_metadata_with_llm,
        autofill_website_connection_metadata=_autofill_website_connection_metadata,
        read_rss_connections=_read_rss_connections,
        read_website_connections=_read_website_connections,
        read_searxng_connections=_read_searxng_connections,
        read_mqtt_connections=_read_mqtt_connections,
        next_rss_import_ref=_next_rss_import_ref,
    )
