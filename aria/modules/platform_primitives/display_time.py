"""Shared display-time policy for user-facing timestamps.

Persisted timestamps remain UTC.  This module only selects the zone used to
render them and to interpret date-only filters.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DISPLAY_TIMEZONE_COOKIE = "aria_display_timezone"


def normalize_display_timezone(value: object) -> str:
    clean = str(value or "").strip()[:100]
    if not clean:
        return ""
    try:
        ZoneInfo(clean)
    except (ZoneInfoNotFoundError, ValueError):
        return ""
    return clean


def resolve_display_timezone(
    settings: Any | None = None,
    *,
    browser_timezone: object = "",
    environ: dict[str, str] | None = None,
) -> str:
    """Resolve configured -> TZ environment -> browser -> UTC."""

    return resolve_display_timezone_with_source(
        settings,
        browser_timezone=browser_timezone,
        environ=environ,
    )[0]


def resolve_display_timezone_with_source(
    settings: Any | None = None,
    *,
    browser_timezone: object = "",
    environ: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve the display zone and retain which authority supplied it."""

    ui = getattr(settings, "ui", None)
    configured = normalize_display_timezone(getattr(ui, "display_timezone", ""))
    if configured:
        return configured, "setting"
    env = os.environ if environ is None else environ
    environment = normalize_display_timezone(env.get("TZ", ""))
    if environment:
        return environment, "environment"
    browser = normalize_display_timezone(browser_timezone)
    if browser:
        return browser, "browser"
    return "UTC", "fallback_utc"


def request_display_timezone(request: Any, settings: Any | None = None) -> str:
    return request_display_timezone_with_source(request, settings)[0]


def request_display_timezone_with_source(
    request: Any, settings: Any | None = None
) -> tuple[str, str]:
    cookies = getattr(request, "cookies", {}) or {}
    return resolve_display_timezone_with_source(
        settings,
        browser_timezone=cookies.get(DISPLAY_TIMEZONE_COOKIE, ""),
    )


def display_zone(name: object) -> ZoneInfo:
    return ZoneInfo(normalize_display_timezone(name) or "UTC")


def display_datetime(epoch: object, timezone_name: object) -> datetime:
    return datetime.fromtimestamp(float(epoch or 0), tz=timezone.utc).astimezone(
        display_zone(timezone_name)
    )


def display_datetime_from_iso(value: object, timezone_name: object) -> datetime | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = datetime.fromisoformat(clean.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(display_zone(timezone_name))


def format_display_timestamp(
    value: object,
    timezone_name: object,
    *,
    language: object = "de",
) -> str:
    """Format a persisted UTC ISO timestamp or epoch for user-facing output."""

    if isinstance(value, (int, float)):
        parsed = display_datetime(value, timezone_name)
    else:
        parsed = display_datetime_from_iso(value, timezone_name)
    if parsed is None:
        return ""
    pattern = "%d.%m.%Y, %H:%M" if str(language or "de").lower().startswith("de") else "%Y-%m-%d, %H:%M"
    return parsed.strftime(pattern)


def local_date_bound(
    value: object,
    timezone_name: object,
    *,
    end: bool = False,
) -> float | None:
    clean = str(value or "").strip()
    if not clean:
        return None
    try:
        parsed = datetime.fromisoformat(clean)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=display_zone(timezone_name))
    if end and len(clean) == 10:
        parsed += timedelta(days=1, microseconds=-1)
    return parsed.timestamp()
