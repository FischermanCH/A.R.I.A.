from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from aria.core.action_plan import ActionPlan
from aria.core.capability_catalog import build_capability_detail_lines
from aria.core.connection_catalog import connection_kind_label
from aria.core.i18n import I18NStore

_CAPABILITY_DETAILS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _capability_details_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CAPABILITY_DETAILS_I18N.t(language or "de", f"pipeline_capability_details.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


BundleNoteParser = Callable[[list[str] | tuple[str, ...] | None], tuple[str, list[str]] | None]
TextTruncator = Callable[[str, int], str]


def default_mqtt_topic_from_settings(settings: Any, connection_ref: str) -> str:
    connection_rows = getattr(getattr(settings, "connections", object()), "mqtt", {})
    if not isinstance(connection_rows, dict):
        return ""
    row = connection_rows.get(connection_ref, {})
    if isinstance(row, dict):
        return str(row.get("topic", "")).strip()
    return str(getattr(row, "topic", "")).strip()


def build_pipeline_capability_detail_lines(
    plan: ActionPlan,
    *,
    settings: Any,
    parse_rss_group_bundle_note: BundleNoteParser,
    truncate_text: TextTruncator,
    language: str | None = None,
) -> list[str]:
    effective_plan = plan
    if str(plan.capability or "").strip().lower() == "mqtt_publish" and not str(plan.path or "").strip():
        effective_plan = replace(plan, path=default_mqtt_topic_from_settings(settings, plan.connection_ref))
    elif str(plan.capability or "").strip().lower() == "mail_search" and str(plan.content or "").strip():
        effective_plan = replace(plan, content=truncate_text(plan.content, 160))
    elif str(plan.capability or "").strip().lower() == "feed_read":
        bundle = parse_rss_group_bundle_note(plan.notes)
        if bundle is not None:
            group_name, _ = bundle
            return [
                _capability_details_text(
                    language,
                    "rss_category_executed",
                    "Executed via RSS category `{group_name}`",
                    group_name=group_name,
                )
            ]
    elif str(plan.capability or "").strip().lower() == "website_list":
        if str(plan.content or "").strip():
            return [
                _capability_details_text(
                    language,
                    "website_group_executed",
                    "Executed via website group `{group_name}`",
                    group_name=plan.content,
                )
            ]
        return [
            _capability_details_text(
                language,
                "websites_executed",
                "Executed via watched websites",
            )
        ]
    return build_capability_detail_lines(effective_plan, connection_kind_label, language=language)
