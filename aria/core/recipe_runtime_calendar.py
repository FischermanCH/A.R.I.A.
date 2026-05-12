from __future__ import annotations

import json
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
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
        return now, now + timedelta(days=30), 5
    return now, now + timedelta(days=14), 10


def google_calendar_token_request_body(connection: Any) -> bytes:
    return urlencode(
        {
            "client_id": str(getattr(connection, "client_id", "") or "").strip(),
            "client_secret": str(getattr(connection, "client_secret", "") or "").strip(),
            "refresh_token": str(getattr(connection, "refresh_token", "") or "").strip(),
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")


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
        calendar_id = str(getattr(connection, "calendar_id", "primary") or "primary").strip() or "primary"
        client_id = str(getattr(connection, "client_id", "") or "").strip()
        client_secret = str(getattr(connection, "client_secret", "") or "").strip()
        refresh_token = str(getattr(connection, "refresh_token", "") or "").strip()
        timeout_seconds = int(getattr(connection, "timeout_seconds", 10) or 10)
        if not client_id:
            raise ValueError(self._text(language, "message_1476", "Google client ID is missing in the profile."))
        if not client_secret:
            raise ValueError(self._text(language, "message_1478", "Google client secret is missing in the profile."))
        if not refresh_token:
            raise ValueError(self._text(language, "message_1480", "Google refresh token is missing in the profile."))

        token_request = URLRequest(
            "https://oauth2.googleapis.com/token",
            data=google_calendar_token_request_body(connection),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "ARIA/1.0",
            },
            method="POST",
        )
        try:
            with self.urlopen_func(token_request, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                token_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="sign_in")) from exc
        except URLError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="sign_in")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="sign_in")) from exc

        access_token = str((token_payload or {}).get("access_token", "") or "").strip()
        if not access_token:
            raise ValueError(self._text(language, "message_1503", "Google did not return an access token."))

        start_at, end_at, max_results = google_calendar_time_bounds(range_hint)
        query_pairs: list[tuple[str, str]] = [
            ("singleEvents", "true"),
            ("orderBy", "startTime"),
            ("showDeleted", "false"),
            ("maxResults", str(max_results)),
            ("timeMin", start_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")),
            ("timeMax", end_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")),
        ]
        clean_search = str(search_query or "").strip()
        if clean_search:
            query_pairs.append(("q", clean_search))
        events_url = (
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events?"
            + urlencode(query_pairs)
        )
        events_request = URLRequest(
            events_url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "ARIA/1.0",
            },
            method="GET",
        )
        try:
            with self.urlopen_func(events_request, timeout=max(5, timeout_seconds)) as resp:  # noqa: S310
                events_payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc
        except URLError as exc:
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc
        except Exception as exc:  # noqa: BLE001
            raise ValueError(friendly_google_calendar_error_message(exc, lang=language, operation="fetch")) from exc

        calendar_summary = str((events_payload or {}).get("summary", "") or "").strip() or calendar_id
        items = list((events_payload or {}).get("items", []) or [])
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
