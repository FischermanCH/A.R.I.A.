from __future__ import annotations

import asyncio
from pathlib import Path

from aria.modules.configuration_foundations.config import load_settings
from aria.modules.model_usage_observability.llm_audit import GLOBAL_LLM_AUDIT_LOG
from aria.modules.model_usage_observability.usage_meter import UsageMeter
from aria.modules.memory_learning_bridge.skill import MemorySkill

async def run_memory_maintenance(config_path: str | Path = "config/config.yaml") -> dict[str, int]:
    settings = load_settings(config_path)
    from aria.modules.model_usage_observability.token_tracker import TokenTracker

    stats = {
        "users": 0,
        "compressed_week": 0,
        "compressed_month": 0,
        "collections_removed": 0,
        "document_meta_documents": 0,
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
    skill = MemorySkill(
        memory=settings.memory,
        embeddings=settings.embeddings,
        usage_meter=usage_meter,
    )
    session_cfg = settings.memory.collections.sessions
    compress_after_days = int(getattr(session_cfg, "compress_after_days", 7) or 7)
    monthly_after_days = int(getattr(session_cfg, "monthly_after_days", 30) or 30)
    memory_stats = await skill.compress_all_users(
        compress_after_days=compress_after_days,
        monthly_after_days=monthly_after_days,
    )
    doc_meta_stats = await skill.rebuild_document_meta_catalogs_for_known_users()
    stats.update(memory_stats)
    stats["document_meta_documents"] = int(doc_meta_stats.get("documents", 0) or 0)
    return stats


def main() -> int:
    stats = asyncio.run(run_memory_maintenance())
    print(
        "Memory-Maintenance abgeschlossen: "
        f"users={stats.get('users', 0)} "
        f"week={stats.get('compressed_week', 0)} "
        f"month={stats.get('compressed_month', 0)} "
        f"removed={stats.get('collections_removed', 0)} "
        f"doc_meta={stats.get('document_meta_documents', 0)} "
        f"token_logs={stats.get('token_log_removed', 0)} "
        f"llm_audit={stats.get('llm_audit_removed', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
