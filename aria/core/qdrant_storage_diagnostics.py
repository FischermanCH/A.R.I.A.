from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def candidate_qdrant_storage_paths(base_dir: Path, qdrant_url: str) -> list[Path]:
    parsed = urlparse(str(qdrant_url or "").strip())
    host = str(parsed.hostname or "").strip().lower()

    paths = [Path("/qdrant/storage")]
    if host in {"", "localhost", "127.0.0.1", "::1", "host.docker.internal", "qdrant"}:
        paths.extend(
            [
                base_dir / "data" / "qdrant",
                base_dir / "qdrant" / "storage",
                Path("/var/lib/qdrant/storage"),
                Path("/var/lib/qdrant"),
                Path("/root/.local/share/qdrant/storage"),
            ]
        )
    return _dedupe_paths(paths)


def resolve_qdrant_storage_path(base_dir: Path, qdrant_url: str) -> Path | None:
    for path in candidate_qdrant_storage_paths(base_dir, qdrant_url):
        try:
            if path.exists() and path.is_dir():
                return path
        except OSError:
            continue
    return None


def list_local_qdrant_collection_names(storage_path: Path | None) -> list[str]:
    if storage_path is None:
        return []
    collections_dir = storage_path / "collections"
    try:
        if not collections_dir.exists() or not collections_dir.is_dir():
            return []
    except OSError:
        return []
    names: list[str] = []
    try:
        for candidate in collections_dir.iterdir():
            try:
                if candidate.is_dir():
                    clean = str(candidate.name or "").strip()
                    if clean:
                        names.append(clean)
            except OSError:
                continue
    except OSError:
        return []
    return sorted(set(names))


def build_qdrant_storage_warning(
    *,
    storage_path: Path | None,
    local_collection_names: list[str],
    api_collection_names: list[str],
) -> dict[str, object]:
    local_names = sorted({str(name or "").strip() for name in local_collection_names if str(name or "").strip()})
    api_names = sorted({str(name or "").strip() for name in api_collection_names if str(name or "").strip()})
    if not local_names:
        return {}

    missing_from_api = [name for name in local_names if name not in api_names]
    if not missing_from_api:
        return {}

    if not api_names:
        key = "storage_only"
        message = (
            f"Local Qdrant storage contains {len(local_names)} collection(s), but the live API currently reports none. "
            "This usually means the storage was not loaded yet or the mounted files are not readable by Qdrant."
        )
    else:
        key = "storage_partial"
        message = (
            f"Local Qdrant storage contains {len(local_names)} collection(s), but {len(missing_from_api)} of them are missing "
            "from the live API. This usually points to a partial load or a storage mount/permission problem."
        )

    return {
        "key": key,
        "message": message,
        "storage_path": str(storage_path) if storage_path else "",
        "local_collection_count": len(local_names),
        "api_collection_count": len(api_names),
        "missing_from_api": missing_from_api,
    }
