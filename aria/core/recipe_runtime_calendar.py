from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request as URLRequest

from aria.core.google_calendar_support import friendly_google_calendar_error_message

RecipeText = Callable[..., str]
UrlOpen = Callable[..., Any]


def google_calendar_time_bounds(range_hint: str) -> tuple[datetime, datetime, int]:
    now = datetime.now().astimezone()
    start_of_today = datetime.combine(now.date(), dt_time.min, tzinfo=now.tzinfo)
    clean = str(range_hint or "").strip().lower()
    if clean == "today":
        return start_of_today, start_of_today + timedelta(days=1), 12
    if clean == "tomorrow":
        start = start_of_today + timedelta(days=1)
        return start, start + timedelta(days=1), 12
    if clean == "day_after_tomorrow":
        start = start_of_today + timedelta(days=2)
        return start, start + timedelta(days=1), 12
    if clean == "this_week":
        start = start_of_today
        return start, start + timedelta(days=7), 20
    if clean == "next_week":
        days_until_next_week = 7 - start_of_today.weekday()
        start = start_of_today + timedelta(days=days_until_next_week)
        return start, start + timedelta(days=7), 20
    if clean == "next":
        return now, now + timedelta(days=30), 1
    return now, now + timedelta(days=14), 10


def google_calendar_range_label(recipe_text: RecipeText, range_hint: str, *, language: str = "de") -> str:
    clean = str(range_hint or "").strip().lower()
    labels = {
        "today": recipe_text(language, "message_839", "today"),
        "tomorrow": recipe_text(language, "message_840", "tomorrow"),
        "day_after_tomorrow": recipe_text(language, "message_841", "the day after tomorrow"),
        "this_week": recipe_text(language, "message_842", "this week"),
        "next_week": recipe_text(language, "message_843", "next week"),
        "next": recipe_text(language, "message_844", "the next appointment"),
        "upcoming": recipe_text(language, "message_845", "the upcoming events"),
    }
    return labels.get(clean, labels["upcoming"])


def format_google_calendar_event_time(recipe_text: RecipeText, event: dict[str, Any], *, language: str = "de") -> str:
    start = dict(event.get("start", {}) or {})
    date_value = str(start.get("date", "") or "").strip()
    datetime_value = str(start.get("dateTime", "") or "").strip()
    if date_value:
        try:
            parsed = datetime.fromisoformat(date_value)
            return parsed.strftime("%Y-%m-%d") + recipe_text(language, "message_857", " · all-day")
        except Exception:
            return date_value
    if datetime_value:
        try:
            parsed = datetime.fromisoformat(datetime_value.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            return datetime_value
    return ""


def _unfold_ical_lines(ical_text: str) -> list[str]:
    rows: list[str] = []
    for raw_line in str(ical_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and rows:
            rows[-1] += raw_line[1:]
        else:
            rows.append(raw_line.rstrip("\n"))
    return rows


def _decode_ical_text(value: str) -> str:
    return (
        str(value or "")
        .replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_ical_datetime(raw_value: str, *, value_type: str = "") -> tuple[dict[str, str], datetime | None]:
    clean = str(raw_value or "").strip()
    clean_type = str(value_type or "").strip().upper()
    if not clean:
        return {}, None
    if clean_type == "DATE" or (len(clean) == 8 and clean.isdigit()):
        try:
            parsed_date = datetime.strptime(clean, "%Y%m%d").date()
        except ValueError:
            return {"date": clean}, None
        start_at = datetime.combine(parsed_date, dt_time.min).astimezone()
        return {"date": parsed_date.isoformat()}, start_at
    try:
        if clean.endswith("Z"):
            parsed = datetime.strptime(clean, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        elif "T" in clean:
            parsed = datetime.strptime(clean, "%Y%m%dT%H%M%S").astimezone()
        else:
            parsed = datetime.fromisoformat(clean)
            if parsed.tzinfo is None:
                parsed = parsed.astimezone()
    except ValueError:
        return {"dateTime": clean}, None
    return {"dateTime": parsed.isoformat()}, parsed.astimezone()


def parse_google_calendar_ical_events(ical_text: str) -> tuple[str, list[dict[str, Any]]]:
    calendar_name = ""
    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for raw_line in _unfold_ical_lines(ical_text):
        if raw_line == "BEGIN:VEVENT":
            current = {}
            continue
        if raw_line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if ":" not in raw_line:
            continue
        left, raw_value = raw_line.split(":", 1)
        name, *param_parts = left.split(";")
        prop_name = name.strip().upper()
        params: dict[str, str] = {}
        for part in param_parts:
            if "=" not in part:
                continue
            param_name, param_value = part.split("=", 1)
            params[param_name.strip().upper()] = param_value.strip()
        if current is None:
            if prop_name == "X-WR-CALNAME" and not calendar_name:
                calendar_name = _decode_ical_text(raw_value)
            continue
        if prop_name == "SUMMARY":
            current["summary"] = _decode_ical_text(raw_value)
        elif prop_name == "LOCATION":
            current["location"] = _decode_ical_text(raw_value)
        elif prop_name == "DESCRIPTION":
            current["description"] = _decode_ical_text(raw_value)
        elif prop_name == "DTSTART":
            start_value, start_at = _parse_ical_datetime(raw_value, value_type=params.get("VALUE", ""))
            current["start"] = start_value
            current["_start_at"] = start_at
    return calendar_name, events


class RecipeCalendarRuntime:
    def __init__(
        self,
        *,
        get_connection_profile: Callable[[str, str], Any],
        truncate_text: Callable[[str, int], str],
        recipe_text: RecipeText,
        urlopen_func: UrlOpen,
    ) -> None:
        self.get_connection_profile = get_connection_profile
        self.truncate_text = truncate_text
        self.recipe_text = recipe_text
        self.urlopen_func = urlopen_func

    def _text(self, language: str, key: str, default: str, **values: Any) -> str:
        return self.recipe_text(language, key, default, **values)

    def range_label(self, range_hint: str, *, language: str = "de") -> str:
        return google_calendar_range_label(self.recipe_text, range_hint, language=language)

    def event_time(self, event: dict[str, Any], *, language: str = "de") -> str:
        return format_google_calendar_event_time(self.recipe_text, event, language=language)

    def execute_read(
        self,
        connection_ref: str,
        range_hint: str = "upcoming",
        search_query: str = "",
        *,
        language: str = "de",
    ) -> str:
        connection = self.get_connection_profile("google_calendar", connection_ref)
        ical_url = str(getattr(connection, "ical_url", "") or "").strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not ical_url:
            raise ValueError(self._text(language, "google_ical_url_missing", "Google Calendar iCal URL is missing in the profile."))
        parsed = urlparse(ical_url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError(self._text(language, "google_ical_url_invalid", "Google Calendar iCal URL must be a complete HTTPS URL."))

        start_at, end_at, max_results = google_calendar_time_bounds(range_hint)
        clean_search = str(search_query or "").strip()
        events_request = URLRequest(
            ical_url,
            headers={"Accept": "text/calendar,text/plain,*/*;q=0.8", "User-Agent": "ARIA/1.0"},
            method="GET",
        )
        try:
            with self.urlopen_func(events_request, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                ical_text = resp.read(1024 * 1024).decode("utf-8", errors="replace")
        except HTTPError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc
        except URLError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc

        if "BEGIN:VCALENDAR" not in ical_text:
            raise ValueError(self._text(language, "google_ical_invalid_feed", "Google Calendar iCal URL did not return a calendar feed."))
        calendar_name, parsed_events = parse_google_calendar_ical_events(ical_text)
        calendar_summary = calendar_name or str(getattr(connection, "title", "") or "").strip() or connection_ref
        items: list[dict[str, Any]] = []
        search_lower = clean_search.lower()
        for event in parsed_events:
            start_value = event.get("_start_at")
            if not isinstance(start_value, datetime):
                continue
            start_local = start_value.astimezone()
            if start_local < start_at or start_local >= end_at:
                continue
            if search_lower:
                haystack = " ".join(
                    str(event.get(field, "") or "").lower()
                    for field in ("summary", "location", "description")
                )
                if search_lower not in haystack:
                    continue
            public_event = {key: value for key, value in event.items() if not key.startswith("_")}
            items.append(public_event)
        items.sort(key=lambda item: str(item.get("start", {}).get("dateTime") or item.get("start", {}).get("date") or ""))
        range_label = self.range_label(range_hint, language=language)
        if not items:
            base = self._text(
                language,
                "message_1542",
                "No events found for {self__google_calendar_range_label_range_hint_language_language} in `{calendar_summary}`.",
                self__google_calendar_range_label_range_hint_language_language=range_label,
                calendar_summary=calendar_summary,
            )
            if clean_search:
                base += self._text(language, "message_1548", " Filter: {clean_search}", clean_search=clean_search)
            return base

        header = self._text(
            language,
            "message_1551",
            "Calendar `{calendar_summary}` for {self__google_calendar_range_label_range_hint_language_language}:",
            calendar_summary=calendar_summary,
            self__google_calendar_range_label_range_hint_language_language=range_label,
        )
        lines = [header]
        for index, item in enumerate(items[:max_results], start=1):
            event = dict(item or {})
            summary = str(event.get("summary", "") or "").strip() or self._text(language, "message_1559", "(untitled)")
            when = self.event_time(event, language=language)
            location = str(event.get("location", "") or "").strip()
            line = f"{index}. {summary}"
            if when:
                line += f" [{when}]"
            lines.append(line)
            if location:
                lines.append(f"   {self._text(language, 'message_1567', 'Location')}: {location}")
        return self.truncate_text("\n".join(lines), 1800)
