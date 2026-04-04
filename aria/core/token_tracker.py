from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile


class TokenTracker:
    def __init__(self, log_file: str, enabled: bool = True):
        self.enabled = enabled
        self.log_path = Path(log_file)

    @staticmethod
    def _parse_timestamp(value: object) -> tuple[str, float] | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            return raw, datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None

    def _iter_log_items(self) -> tuple[str, dict]:
        if not self.log_path.exists():
            return
        with self.log_path.open("r", encoding="utf-8") as file:
            for line in file:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    yield raw, item

    @staticmethod
    def _empty_stats(days: int) -> dict:
        return {
            "days": days,
            "request_count": 0,
            "total_tokens": 0,
            "avg_tokens_per_request": 0,
            "requests_by_intent": {},
            "requests_by_router_level": {},
            "chat_tokens_by_model": {},
            "embedding_tokens_by_model": {},
            "total_cost_usd": 0.0,
            "avg_cost_usd_per_request": 0.0,
            "priced_requests_count": 0,
            "chat_cost_usd_by_model": {},
            "embedding_cost_usd_by_model": {},
        }

    @staticmethod
    def _empty_activity_summary() -> dict[str, int]:
        return {"count": 0, "success": 0, "errors": 0, "avg_duration_ms": 0}

    @staticmethod
    def _summarize_activity_rows(rows: list[dict]) -> dict[str, int]:
        count = len(rows)
        success = sum(1 for row in rows if bool(row.get("success")))
        errors = sum(1 for row in rows if not bool(row.get("success")))
        avg_duration_ms = int(sum(int(row.get("duration_ms", 0) or 0) for row in rows) / count) if count else 0
        return {
            "count": count,
            "success": success,
            "errors": errors,
            "avg_duration_ms": avg_duration_ms,
        }

    @staticmethod
    def _build_activity_row(item: dict, activity: dict) -> dict:
        skill_errors = item.get("skill_errors", [])
        if not isinstance(skill_errors, list):
            skill_errors = []
        clean_errors = [str(err).strip() for err in skill_errors if str(err).strip()]
        total_tokens = int(item.get("total_tokens", 0) or 0)
        total_cost_usd = float(item.get("total_cost_usd", 0.0) or 0.0)
        chat_model = str(item.get("chat_model", "")).strip()
        raw_source = str(item.get("source", "")).strip().lower()
        source = "" if raw_source in {"", "web", "chat"} else raw_source
        return {
            "timestamp": str(item.get("timestamp", "")).strip(),
            "kind": activity["kind"],
            "title": activity["title"],
            "intent": activity["intent"],
            "duration_ms": int(item.get("duration_ms", 0) or 0),
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "chat_model": chat_model,
            "source": source,
            "show_tokens": total_tokens > 0,
            "show_cost": total_cost_usd > 0.0,
            "show_model": bool(chat_model) and total_tokens > 0,
            "show_source": bool(source),
            "skill_errors": clean_errors,
            "success": len(clean_errors) == 0,
        }

    async def log(
        self,
        request_id: str,
        user_id: str,
        intents: list[str],
        router_level: int,
        usage: dict[str, int],
        chat_model: str,
        embedding_model: str,
        embedding_usage: dict[str, int],
        chat_cost_usd: float | None,
        embedding_cost_usd: float | None,
        total_cost_usd: float | None,
        duration_ms: int,
        source: str,
        skill_errors: list[str] | None = None,
        extraction_model: str = "",
        extraction_usage: dict[str, int] | None = None,
    ) -> None:
        if not self.enabled:
            return

        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "user_id": user_id,
            "intents": intents,
            "router_level": router_level,
            "source": source,
            "duration_ms": duration_ms,
            "chat_model": chat_model,
            "embedding_model": embedding_model,
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
            "embedding_prompt_tokens": int(embedding_usage.get("prompt_tokens", 0) or 0),
            "embedding_completion_tokens": int(embedding_usage.get("completion_tokens", 0) or 0),
            "embedding_total_tokens": int(embedding_usage.get("total_tokens", 0) or 0),
            "embedding_calls": int(embedding_usage.get("calls", 0) or 0),
            "chat_cost_usd": chat_cost_usd,
            "embedding_cost_usd": embedding_cost_usd,
            "total_cost_usd": total_cost_usd,
            "skill_errors": skill_errors or [],
            "extraction_model": extraction_model,
            "extraction_prompt_tokens": int((extraction_usage or {}).get("prompt_tokens", 0) or 0),
            "extraction_completion_tokens": int((extraction_usage or {}).get("completion_tokens", 0) or 0),
            "extraction_total_tokens": int((extraction_usage or {}).get("total_tokens", 0) or 0),
            "extraction_calls": int((extraction_usage or {}).get("calls", 0) or 0),
        }

        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=True) + "\n")

    async def get_stats(self, days: int = 7) -> dict:
        if not self.log_path.exists():
            return self._empty_stats(days)

        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
        request_count = 0
        total_tokens = 0
        requests_by_intent: dict[str, int] = {}
        requests_by_router_level: dict[str, int] = {}
        chat_tokens_by_model: dict[str, int] = {}
        embedding_tokens_by_model: dict[str, int] = {}
        total_cost_usd = 0.0
        priced_requests_count = 0
        chat_cost_usd_by_model: dict[str, float] = {}
        embedding_cost_usd_by_model: dict[str, float] = {}

        for _, item in self._iter_log_items():
            parsed_ts = self._parse_timestamp(item.get("timestamp"))
            if not parsed_ts or parsed_ts[1] < cutoff:
                continue

            request_count += 1
            total_tokens += int(item.get("total_tokens", 0) or 0)

            level = str(item.get("router_level", "unknown"))
            requests_by_router_level[level] = requests_by_router_level.get(level, 0) + 1

            intents = item.get("intents", [])
            if isinstance(intents, list):
                for intent in intents:
                    key = str(intent)
                    requests_by_intent[key] = requests_by_intent.get(key, 0) + 1

            chat_model = str(item.get("chat_model", "")).strip()
            chat_tokens = int(item.get("total_tokens", 0) or 0)
            chat_tokens_by_model[chat_model] = chat_tokens_by_model.get(chat_model, 0) + chat_tokens
            chat_cost_raw = item.get("chat_cost_usd")
            if isinstance(chat_cost_raw, (int, float)):
                chat_cost_usd_by_model[chat_model] = (
                    chat_cost_usd_by_model.get(chat_model, 0.0) + float(chat_cost_raw)
                )

            embedding_model = str(item.get("embedding_model", "")).strip()
            embedding_tokens = int(item.get("embedding_total_tokens", 0) or 0)
            embedding_tokens_by_model[embedding_model] = (
                embedding_tokens_by_model.get(embedding_model, 0) + embedding_tokens
            )
            embedding_cost_raw = item.get("embedding_cost_usd")
            if isinstance(embedding_cost_raw, (int, float)):
                embedding_cost_usd_by_model[embedding_model] = (
                    embedding_cost_usd_by_model.get(embedding_model, 0.0) + float(embedding_cost_raw)
                )

            total_cost_raw = item.get("total_cost_usd")
            if isinstance(total_cost_raw, (int, float)):
                total_cost_value = float(total_cost_raw)
                total_cost_usd += total_cost_value
                if total_cost_value > 0.0:
                    priced_requests_count += 1

        avg_tokens = int(total_tokens / request_count) if request_count else 0
        avg_cost = (total_cost_usd / priced_requests_count) if priced_requests_count else 0.0
        return {
            "days": days,
            "request_count": request_count,
            "total_tokens": total_tokens,
            "avg_tokens_per_request": avg_tokens,
            "requests_by_intent": requests_by_intent,
            "requests_by_router_level": requests_by_router_level,
            "chat_tokens_by_model": chat_tokens_by_model,
            "embedding_tokens_by_model": embedding_tokens_by_model,
            "total_cost_usd": total_cost_usd,
            "avg_cost_usd_per_request": avg_cost,
            "priced_requests_count": priced_requests_count,
            "chat_cost_usd_by_model": chat_cost_usd_by_model,
            "embedding_cost_usd_by_model": embedding_cost_usd_by_model,
        }

    async def prune_old_entries(self, retention_days: int) -> dict[str, int]:
        if retention_days <= 0 or not self.log_path.exists():
            return {"total": 0, "kept": 0, "removed": 0}

        cutoff = datetime.now(timezone.utc).timestamp() - (retention_days * 86400)
        total = 0
        kept = 0
        removed = 0

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("r", encoding="utf-8") as source, NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(self.log_path.parent),
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            for line in source:
                total += 1
                raw = line.strip()
                if not raw:
                    continue
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    tmp.write(line)
                    kept += 1
                    continue
                parsed_ts = self._parse_timestamp(item.get("timestamp")) if isinstance(item, dict) else None
                if not parsed_ts:
                    tmp.write(line)
                    kept += 1
                    continue

                if parsed_ts[1] < cutoff:
                    removed += 1
                    continue

                tmp.write(line)
                kept += 1

        tmp_path.replace(self.log_path)
        return {"total": total, "kept": kept, "removed": removed}

    async def clear_log(self) -> dict[str, int]:
        if not self.log_path.exists():
            return {"removed": 0}
        removed = 0
        for _raw, _item in self._iter_log_items():
            removed += 1
        self.log_path.unlink(missing_ok=True)
        return {"removed": removed}

    async def get_log_health(self) -> dict[str, object]:
        if not self.log_path.exists():
            return {
                "exists": False,
                "line_count": 0,
                "size_bytes": 0,
                "oldest_timestamp": "",
                "newest_timestamp": "",
            }

        line_count = 0
        oldest_timestamp = ""
        newest_timestamp = ""
        oldest_ts: float | None = None
        newest_ts: float | None = None
        for _, item in self._iter_log_items():
            line_count += 1
            parsed_ts = self._parse_timestamp(item.get("timestamp"))
            if not parsed_ts:
                continue
            raw_ts, ts = parsed_ts
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
                oldest_timestamp = raw_ts
            if newest_ts is None or ts > newest_ts:
                newest_ts = ts
                newest_timestamp = raw_ts

        return {
            "exists": True,
            "line_count": line_count,
            "size_bytes": int(self.log_path.stat().st_size),
            "oldest_timestamp": oldest_timestamp,
            "newest_timestamp": newest_timestamp,
        }

    @staticmethod
    def _classify_activity(item: dict) -> dict | None:
        intents = item.get("intents", [])
        if not isinstance(intents, list):
            intents = []
        clean_intents = [str(intent).strip() for intent in intents if str(intent).strip()]
        if not clean_intents:
            return None

        custom_skill_intents = [intent for intent in clean_intents if intent.startswith("custom_skill:")]
        if custom_skill_intents:
            skill_id = custom_skill_intents[0].split(":", 1)[1].strip()
            return {
                "kind": "skill",
                "title": skill_id.replace("-", " ").strip().title() or "Custom Skill",
                "intent": custom_skill_intents[0],
            }

        if "skill_status" in clean_intents:
            return {"kind": "system", "title": "Skill Status", "intent": "skill_status"}
        capability_intents = [intent for intent in clean_intents if intent.startswith("capability:")]
        if capability_intents:
            capability_name = capability_intents[0].split(":", 1)[1].strip()
            capability_title = capability_name.replace("_", " ").strip().title() or "Capability"
            return {
                "kind": "system",
                "title": capability_title,
                "intent": capability_intents[0],
            }
        if any(intent in {"memory_store", "memory_recall", "memory_forget"} for intent in clean_intents):
            primary = next(
                intent for intent in clean_intents if intent in {"memory_store", "memory_recall", "memory_forget"}
            )
            title_map = {
                "memory_store": "Memory Store",
                "memory_recall": "Memory Recall",
                "memory_forget": "Memory Forget",
            }
            return {"kind": "memory", "title": title_map.get(primary, primary), "intent": primary}
        return None

    async def get_recent_activities(
        self,
        user_id: str,
        limit: int = 40,
        kind: str = "all",
        status: str = "all",
    ) -> dict:
        if not self.log_path.exists():
            return {"rows": [], "summary": self._empty_activity_summary()}

        active_kind = str(kind or "all").strip().lower()
        if active_kind not in {"all", "skill", "memory", "system"}:
            active_kind = "all"
        active_status = str(status or "all").strip().lower()
        if active_status not in {"all", "ok", "error"}:
            active_status = "all"

        rows: list[dict] = []
        for _, item in self._iter_log_items():
            if str(item.get("user_id", "")).strip() != str(user_id).strip():
                continue

            activity = self._classify_activity(item)
            if activity is None:
                continue
            row = self._build_activity_row(item, activity)
            if active_kind != "all" and str(row.get("kind", "")).strip() != active_kind:
                continue
            if active_status == "ok" and not bool(row.get("success")):
                continue
            if active_status == "error" and bool(row.get("success")):
                continue
            rows.append(row)

        rows.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
        rows = rows[:limit]
        return {"rows": rows, "summary": self._summarize_activity_rows(rows)}
