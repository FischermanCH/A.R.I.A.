from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from aria.core.pipeline import Pipeline


UsernameResolver = Callable[[Request], str]
SettingsGetter = Callable[[], object]
PipelineGetter = Callable[[], Pipeline]


def _normalize_activity_kind(value: str) -> str:
    active_kind = str(value or 'all').strip().lower()
    if active_kind not in {'all', 'skill', 'memory', 'system'}:
        return 'all'
    return active_kind


def _normalize_activity_status(value: str) -> str:
    active_status = str(value or 'all').strip().lower()
    if active_status not in {'all', 'ok', 'error'}:
        return 'all'
    return active_status


def _decorate_activity_rows(rows: list[dict]) -> list[dict]:
    for row in rows:
        raw_ts = str(row.get('timestamp', '')).strip()
        display_ts = raw_ts
        try:
            parsed = datetime.fromisoformat(raw_ts.replace('Z', '+00:00'))
            display_ts = parsed.astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
        row['display_timestamp'] = display_ts
        summary_bits: list[str] = [display_ts]
        kind = str(row.get('kind', '')).strip()
        if kind:
            summary_bits.append(kind)
        detail_items: list[dict[str, str]] = [
            {"key": "activities.kind", "fallback": "Typ", "value": kind or "n/a"},
            {"key": "activities.duration", "fallback": "Dauer", "value": f"{int(row.get('duration_ms', 0) or 0)} ms"},
        ]
        if bool(row.get('show_tokens')):
            detail_items.append(
                {
                    "key": "activities.tokens",
                    "fallback": "Tokens",
                    "value": str(int(row.get('total_tokens', 0) or 0)),
                }
            )
        if bool(row.get('show_cost')):
            detail_items.append(
                {
                    "key": "activities.cost",
                    "fallback": "Kosten",
                    "value": f"${float(row.get('total_cost_usd', 0.0) or 0.0):.6f}",
                }
            )
        if bool(row.get('show_model')):
            detail_items.append(
                {
                    "key": "activities.model",
                    "fallback": "Chat-Modell",
                    "value": str(row.get('chat_model', '')).strip() or "n/a",
                }
            )
        if bool(row.get('show_source')):
            detail_items.append(
                {
                    "key": "activities.source",
                    "fallback": "Quelle",
                    "value": str(row.get('source', '')).strip() or "n/a",
                }
            )
        detail_items.append(
            {
                "key": "activities.intent",
                "fallback": "Intent",
                "value": str(row.get('intent', '')).strip() or "n/a",
            }
        )
        row['summary_bits'] = summary_bits
        row['detail_items'] = detail_items
    return rows


def register_activities_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_pipeline: PipelineGetter,
    get_settings: SettingsGetter,
    get_username_from_request: UsernameResolver,
) -> None:
    @app.get('/activities', response_class=HTMLResponse)
    async def activities_page(request: Request, kind: str = 'all', status: str = 'all') -> HTMLResponse:
        settings = get_settings()
        pipeline = get_pipeline()
        username = get_username_from_request(request)
        active_kind = _normalize_activity_kind(kind)
        active_status = _normalize_activity_status(status)
        activity_data = await pipeline.token_tracker.get_recent_activities(
            user_id=username,
            limit=40,
            kind=active_kind,
            status=active_status,
        )
        rows = activity_data.get('rows', [])
        if not isinstance(rows, list):
            rows = []
        activity_data['rows'] = _decorate_activity_rows(rows)
        return templates.TemplateResponse(
            request=request,
            name='activities.html',
            context={
                'title': settings.ui.title,
                'username': username,
                'activities': activity_data,
                'activity_kind': active_kind,
                'activity_status': active_status,
            },
        )
