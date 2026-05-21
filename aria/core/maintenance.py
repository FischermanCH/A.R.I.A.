from __future__ import annotations

import asyncio
import json
from pathlib import Path

from aria.core.config import load_settings
from aria.core.i18n import I18NStore
from aria.core.llm_audit import GLOBAL_LLM_AUDIT_LOG
from aria.core.usage_meter import UsageMeter
from aria.skills.memory import MemorySkill

_MAINTENANCE_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _maintenance_terms(key: str, fallback: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for lang in ("de", "en"):
        raw = _MAINTENANCE_I18N.t(lang, f"maintenance.{key}", "")
        terms.extend(term.strip().lower() for term in raw.split(",") if term.strip())
    return list(dict.fromkeys(terms)) or list(fallback)


def _load_operational_trigger_phrases(project_root: Path) -> list[str]:
    skills_dir = project_root / "data" / "recipes"
    rows: list[str] = _maintenance_terms(
        "operational_trigger_phrases",
        ("what recipes are active", "which recipes are active"),
    )
    if not skills_dir.exists():
        return rows
    for path in sorted(skills_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        keywords = payload.get("router_keywords", [])
        if not isinstance(keywords, list):
            continue
        rows.extend(str(item).strip() for item in keywords if str(item).strip())
    return rows


async def run_memory_maintenance(config_path: str | Path = "config/config.yaml") -> dict[str, int]:
    settings = load_settings(config_path)
    from aria.core.token_tracker import TokenTracker

    stats = {
        "users": 0,
        "compressed_week": 0,
        "compressed_month": 0,
        "collections_removed": 0,
        "session_noise_removed": 0,
        "token_log_removed": 0,
        "llm_audit_removed": 0,
    }

    tracker = TokenTracker(settings.token_tracking.log_file, enabled=settings.token_tracking.enabled)
    retention_days = int(getattr(settings.token_tracking, "retention_days", 90) or 0)
    pruned = await tracker.prune_old_entries(retention_days)
    stats["token_log_removed"] = int(pruned.get("removed", 0) or 0)
    llm_pruned = GLOBAL_LLM_AUDIT_LOG.prune_old_entries(retention_days)
    stats["llm_audit_removed"] = int(llm_pruned.get("removed", 0) or 0)

    if not settings.memory.enabled or settings.memory.backend.lower() != "qdrant":
        return stats

    usage_meter = UsageMeter(settings)
    skill = MemorySkill(memory=settings.memory, embeddings=settings.embeddings, usage_meter=usage_meter)
    session_cfg = settings.memory.collections.sessions
    compress_after_days = int(getattr(session_cfg, "compress_after_days", 7) or 7)
    monthly_after_days = int(getattr(session_cfg, "monthly_after_days", 30) or 30)
    memory_stats = await skill.compress_all_users(
        compress_after_days=compress_after_days,
        monthly_after_days=monthly_after_days,
    )
    cleanup = await skill.cleanup_operational_session_entries(
        _load_operational_trigger_phrases(Path(config_path).resolve().parent.parent)
    )
    stats.update(memory_stats)
    stats["session_noise_removed"] = int(cleanup.get("removed_points", 0) or 0)
    return stats


def main() -> int:
    stats = asyncio.run(run_memory_maintenance())
    print(
        "Memory-Maintenance abgeschlossen: "
        f"users={stats.get('users', 0)} "
        f"week={stats.get('compressed_week', 0)} "
        f"month={stats.get('compressed_month', 0)} "
        f"removed={stats.get('collections_removed', 0)} "
        f"noise={stats.get('session_noise_removed', 0)} "
        f"token_logs={stats.get('token_log_removed', 0)} "
        f"llm_audit={stats.get('llm_audit_removed', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
