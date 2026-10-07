from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class SessionCompressionService:
    def __init__(self, skill: Any) -> None:
        self.skill = skill

    async def compress_old_sessions(
        self,
        user_id: str,
        *,
        compress_after_days: int = 7,
        monthly_after_days: int = 30,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "compressed_week": 0,
            "compressed_month": 0,
            "collections_removed": 0,
            "compressed_collections": [],
            "removed_collections": [],
            "skipped_recent": [],
            "skipped_empty": [],
            "failed_delete": [],
            "week_rollups": [],
            "month_rollups": [],
        }
        slug = self.skill._slug_user_id(user_id)
        session_prefix = f"{self.skill.memory.collections.sessions.prefix}_{slug}_"
        legacy_session_prefix = f"aria_memory_{slug}_session_"
        context_mem_collection = self.skill._context_collection_for_user(user_id)
        now = datetime.now(timezone.utc)

        names = await self.skill._list_collection_names()
        session_names = [
            name
            for name in names
            if name.startswith(session_prefix) or name.startswith(legacy_session_prefix)
        ]
        weekly_groups: dict[str, dict[str, Any]] = {}
        for collection_name in session_names:
            rows = await self.skill._list_rows_from_collection(
                collection=collection_name,
                user_id=user_id,
                memory_type="session",
                label=self.skill._type_label("session"),
                limit=120,
            )
            if not rows:
                summary["skipped_empty"].append(collection_name)
                continue

            session_day = self.skill._session_day_from_collection_name(collection_name)
            newest_ts = None
            for row in rows:
                parsed = self.skill._parse_timestamp(row.get("timestamp"))
                if parsed is None:
                    continue
                if newest_ts is None or parsed > newest_ts:
                    newest_ts = parsed

            age_days: int | None = None
            if session_day is not None:
                age_days = max(0, int((now.date() - session_day).days))
            elif newest_ts is not None:
                age_days = max(0, int((now - newest_ts.astimezone(timezone.utc)).total_seconds() // 86400))
                session_day = newest_ts.astimezone(timezone.utc).date()

            if age_days is None or session_day is None:
                continue

            if age_days < max(1, compress_after_days):
                summary["skipped_recent"].append(collection_name)
                continue

            week_bucket, week_start, week_end = self.skill._week_bucket_for_day(session_day)
            group = weekly_groups.setdefault(
                week_bucket,
                {
                    "bucket": week_bucket,
                    "period_start": week_start,
                    "period_end": week_end,
                    "rows": [],
                    "collections": [],
                },
            )
            group["rows"].extend(rows)
            if collection_name not in group["collections"]:
                group["collections"].append(collection_name)

        for week_bucket, group in sorted(weekly_groups.items()):
            rows = list(group.get("rows", []))
            source_collections = list(group.get("collections", []))
            if not rows or not source_collections:
                continue
            text = self.skill._build_compression_summary(
                kind=self.skill.ROLLUP_LEVEL_WEEK,
                day_raw=week_bucket,
                rows=rows,
            )
            await self.skill._store_rollup_summary(
                user_id=user_id,
                text=text,
                base_collection=context_mem_collection,
                rollup_level=self.skill.ROLLUP_LEVEL_WEEK,
                rollup_bucket=week_bucket,
                period_start=group["period_start"],
                period_end=group["period_end"],
                source_kind="session_day",
                source_collections=source_collections,
            )
            summary["compressed_week"] += 1
            summary["week_rollups"].append(week_bucket)
            summary["compressed_collections"].extend(source_collections)
            for collection_name in source_collections:
                try:
                    await self.skill.qdrant.delete_collection(collection_name=collection_name)
                    summary["collections_removed"] += 1
                    summary["removed_collections"].append(collection_name)
                except Exception:
                    summary["failed_delete"].append(collection_name)

        weekly_rollups = await self.skill._list_rollup_rows(user_id, context_mem_collection)
        monthly_groups: dict[str, dict[str, Any]] = {}
        for row in weekly_rollups:
            if str(row.get("rollup_level", "")).strip().lower() != self.skill.ROLLUP_LEVEL_WEEK:
                continue
            period_end_raw = str(row.get("rollup_period_end", "")).strip()
            if not period_end_raw:
                continue
            try:
                period_end = datetime.fromisoformat(period_end_raw).date()
            except ValueError:
                continue
            age_days = max(0, int((now.date() - period_end).days))
            if age_days < max(monthly_after_days, compress_after_days + 1):
                continue
            period_start_raw = str(row.get("rollup_period_start", "")).strip()
            try:
                period_start = datetime.fromisoformat(period_start_raw).date() if period_start_raw else period_end
            except ValueError:
                period_start = period_end
            month_bucket, month_start, month_end = self.skill._month_bucket_for_day(period_start)
            group = monthly_groups.setdefault(
                month_bucket,
                {
                    "bucket": month_bucket,
                    "period_start": month_start,
                    "period_end": month_end,
                    "rows": [],
                    "collections": [],
                },
            )
            group["rows"].append(row)
            source_label = str(row.get("rollup_bucket", "")).strip() or str(row.get("collection", "")).strip()
            if source_label and source_label not in group["collections"]:
                group["collections"].append(source_label)

        for month_bucket, group in sorted(monthly_groups.items()):
            rows = list(group.get("rows", []))
            source_collections = list(group.get("collections", []))
            if not rows:
                continue
            text = self.skill._build_compression_summary(
                kind=self.skill.ROLLUP_LEVEL_MONTH,
                day_raw=month_bucket,
                rows=rows,
            )
            await self.skill._store_rollup_summary(
                user_id=user_id,
                text=text,
                base_collection=context_mem_collection,
                rollup_level=self.skill.ROLLUP_LEVEL_MONTH,
                rollup_bucket=month_bucket,
                period_start=group["period_start"],
                period_end=group["period_end"],
                source_kind="session_week",
                source_collections=source_collections,
            )
            summary["compressed_month"] += 1
            summary["month_rollups"].append(month_bucket)
        await self.skill.cleanup_empty_collections_for_user(user_id)
        return summary
