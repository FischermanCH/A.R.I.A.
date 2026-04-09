from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aria.core.config import EmbeddingsConfig, LLMConfig, MemoryConfig, PromptConfig, Settings
from aria.core.embedding_client import EmbeddingClient
from aria.core.llm_client import LLMClient, LLMClientError
from aria.core.qdrant_client import create_async_qdrant_client
from aria.core.qdrant_storage_diagnostics import build_qdrant_storage_warning
from aria.core.qdrant_storage_diagnostics import list_local_qdrant_collection_names
from aria.core.qdrant_storage_diagnostics import resolve_qdrant_storage_path
from aria.core.usage_meter import UsageMeter


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_embedding_model(model: str) -> str:
    clean = str(model or "").strip()
    if not clean:
        return clean
    if "/" not in clean and not clean.lower().startswith("ollama"):
        return f"openai/{clean}"
    return clean


def _embedding_vector_present(response: Any) -> bool:
    data = list(getattr(response, "data", []) or [])
    if not data:
        return False
    first = data[0]
    if isinstance(first, dict):
        return bool(first.get("embedding"))
    return bool(getattr(first, "embedding", None))


async def probe_qdrant(memory: MemoryConfig, *, base_dir: Path | None = None) -> dict[str, Any]:
    if not bool(memory.enabled):
        return {
            "id": "qdrant",
            "status": "skipped",
            "summary_key": "qdrant_disabled",
            "summary": "Memory deaktiviert.",
            "detail": "",
        }
    if str(memory.backend or "").strip().lower() != "qdrant":
        return {
            "id": "qdrant",
            "status": "skipped",
            "summary_key": "qdrant_backend_inactive",
            "summary": "Qdrant nicht als Backend aktiv.",
            "detail": "",
        }

    client = create_async_qdrant_client(
        url=memory.qdrant_url,
        api_key=(memory.qdrant_api_key or None),
        timeout=4,
    )
    try:
        response = await client.get_collections()
        collections = list(getattr(response, "collections", []) or [])
        collection_names = [
            str(getattr(row, "name", "") or "").strip()
            for row in collections
            if str(getattr(row, "name", "") or "").strip()
        ]
        storage_warning: dict[str, Any] = {}
        if base_dir is not None:
            storage_path = resolve_qdrant_storage_path(base_dir, str(memory.qdrant_url or ""))
            local_collection_names = list_local_qdrant_collection_names(storage_path)
            storage_warning = build_qdrant_storage_warning(
                storage_path=storage_path,
                local_collection_names=local_collection_names,
                api_collection_names=collection_names,
            )
        if storage_warning:
            return {
                "id": "qdrant",
                "status": "warn",
                "summary_key": "qdrant_storage_warning",
                "summary": "Qdrant erreichbar, aber gespeicherte Collections fehlen in der API.",
                "detail": str(storage_warning.get("message", "") or str(memory.qdrant_url or "").strip() or "-"),
                "collection_count": len(collections),
            }
        return {
            "id": "qdrant",
            "status": "ok",
            "summary_key": "qdrant_ok",
            "summary": f"Qdrant erreichbar ({len(collections)} Collections).",
            "detail": str(memory.qdrant_url or "").strip() or "-",
            "collection_count": len(collections),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "qdrant",
            "status": "error",
            "summary_key": "qdrant_error",
            "summary": "Qdrant nicht erreichbar.",
            "detail": str(exc),
        }
    finally:
        try:
            await client.close()
        except Exception:  # noqa: BLE001
            pass


async def probe_llm(llm: LLMConfig, usage_meter: UsageMeter | None = None) -> dict[str, Any]:
    client = LLMClient(
        llm.model_copy(
            update={
                "max_tokens": min(int(llm.max_tokens or 16), 16),
                "timeout_seconds": min(int(llm.timeout_seconds or 8), 8),
                "temperature": 0.0,
            }
        ),
        usage_meter=usage_meter,
    )
    try:
        response = await client.chat(
            [{"role": "user", "content": "Reply with OK only."}],
            source="runtime_diagnostics",
            operation="probe_llm",
            user_id="system",
        )
        content = str(response.content or "").strip()
        status = "ok" if content else "warn"
        return {
            "id": "llm",
            "status": status,
            "summary_key": "llm_ok" if content else "llm_empty",
            "summary": "LLM erreichbar." if content else "LLM antwortet leer.",
            "detail": str(llm.model or "").strip() or "-",
        }
    except LLMClientError as exc:
        return {
            "id": "llm",
            "status": "error",
            "summary_key": "llm_error",
            "summary": "LLM nicht erreichbar.",
            "detail": str(exc),
        }


async def probe_embeddings(
    embeddings: EmbeddingsConfig,
    usage_meter: UsageMeter | None = None,
) -> dict[str, Any]:
    model = _resolve_embedding_model(embeddings.model)
    if not model:
        return {
            "id": "embeddings",
            "status": "warn",
            "summary_key": "embeddings_missing_model",
            "summary": "Embedding-Modell fehlt.",
            "detail": "",
        }
    try:
        client = EmbeddingClient(
            embeddings.model_copy(update={"timeout_seconds": min(int(embeddings.timeout_seconds or 8), 8)}),
            usage_meter=usage_meter,
        )
        response = await client.embed(
            ["healthcheck"],
            source="runtime_diagnostics",
            operation="probe_embeddings",
            user_id="system",
        )
        has_vector = bool(response.vectors and response.vectors[0])
        return {
            "id": "embeddings",
            "status": "ok" if has_vector else "warn",
            "summary_key": "embeddings_ok" if has_vector else "embeddings_empty_vector",
            "summary": "Embeddings erreichbar." if has_vector else "Embeddings antworten ohne Vektor.",
            "detail": str(embeddings.model or "").strip() or "-",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "embeddings",
            "status": "error",
            "summary_key": "embeddings_error",
            "summary": "Embeddings nicht erreichbar.",
            "detail": str(exc),
        }


def probe_prompt_files(base_dir: Path, prompts: PromptConfig) -> dict[str, Any]:
    persona_path = (base_dir / str(prompts.persona or "").strip()).resolve()
    skills_dir = (base_dir / str(prompts.skills_dir or "").strip()).resolve()

    missing: list[str] = []
    if not persona_path.exists() or persona_path.suffix.lower() != ".md":
        missing.append("persona")
    if not skills_dir.exists() or not skills_dir.is_dir():
        missing.append("skills_dir")

    skill_prompt_count = 0
    if skills_dir.exists() and skills_dir.is_dir():
        skill_prompt_count = len([path for path in skills_dir.rglob("*.md") if path.is_file()])

    if missing:
        return {
            "id": "prompts",
            "status": "error",
            "summary_key": "prompts_incomplete",
            "summary": "Prompt-Dateien unvollständig.",
            "detail": ", ".join(missing),
            "persona_path": str(persona_path),
            "skill_prompt_count": skill_prompt_count,
        }

    return {
        "id": "prompts",
        "status": "ok",
        "summary_key": "prompts_ok",
        "summary": f"Prompt-Dateien ok ({skill_prompt_count} Skill-Prompts).",
        "detail": str(persona_path.relative_to(base_dir)).replace("\\", "/"),
        "persona_path": str(persona_path),
        "skill_prompt_count": skill_prompt_count,
    }


async def build_runtime_diagnostics(
    base_dir: Path,
    settings: Settings,
    usage_meter: UsageMeter | None = None,
) -> dict[str, Any]:
    checks = [
        probe_prompt_files(base_dir, settings.prompts),
        await probe_qdrant(settings.memory, base_dir=base_dir),
        await probe_llm(settings.llm, usage_meter=usage_meter),
        await probe_embeddings(settings.embeddings, usage_meter=usage_meter),
    ]
    statuses = [str(row.get("status", "warn")) for row in checks]
    overall = "ok"
    if "error" in statuses:
        overall = "error"
    elif "warn" in statuses:
        overall = "warn"

    return {
        "status": overall,
        "checked_at": _now_iso(),
        "checks": checks,
    }
