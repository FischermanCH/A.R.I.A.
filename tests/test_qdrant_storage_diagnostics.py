from __future__ import annotations

from pathlib import Path

from aria.core.qdrant_storage_diagnostics import build_qdrant_storage_warning
from aria.core.qdrant_storage_diagnostics import list_local_qdrant_collection_names
from aria.core.qdrant_storage_diagnostics import qdrant_storage_has_local_data
from aria.core.qdrant_storage_diagnostics import resolve_qdrant_storage_path


def test_resolve_qdrant_storage_path_prefers_existing_local_candidate(tmp_path: Path) -> None:
    storage_dir = tmp_path / "data" / "qdrant"
    (storage_dir / "collections").mkdir(parents=True, exist_ok=True)

    resolved = resolve_qdrant_storage_path(tmp_path, "http://localhost:6333")

    assert resolved == storage_dir


def test_list_local_qdrant_collection_names_reads_collection_directories(tmp_path: Path) -> None:
    storage_dir = tmp_path / "qdrant" / "storage" / "collections"
    (storage_dir / "aria_facts_whity").mkdir(parents=True, exist_ok=True)
    (storage_dir / "aria_docs_whity_medikamente").mkdir(parents=True, exist_ok=True)

    names = list_local_qdrant_collection_names((tmp_path / "qdrant" / "storage"))

    assert names == ["aria_docs_whity_medikamente", "aria_facts_whity"]


def test_build_qdrant_storage_warning_flags_storage_only_state(tmp_path: Path) -> None:
    warning = build_qdrant_storage_warning(
        storage_path=tmp_path,
        local_collection_names=["aria_facts_whity", "aria_docs_whity_medikamente"],
        api_collection_names=[],
    )

    assert warning["key"] == "storage_only"
    assert warning["local_collection_count"] == 2
    assert warning["missing_from_api"] == ["aria_docs_whity_medikamente", "aria_facts_whity"]


def test_build_qdrant_storage_warning_flags_partial_api_state(tmp_path: Path) -> None:
    warning = build_qdrant_storage_warning(
        storage_path=tmp_path,
        local_collection_names=["aria_doc_guides_whity", "aria_facts_whity"],
        api_collection_names=["aria_facts_whity"],
    )

    assert warning["key"] == "storage_partial"
    assert warning["missing_from_api"] == ["aria_doc_guides_whity"]


def test_qdrant_storage_has_local_data_detects_non_empty_storage(tmp_path: Path) -> None:
    storage_dir = tmp_path / "data" / "qdrant"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "storage.sqlite").write_text("placeholder", encoding="utf-8")

    assert qdrant_storage_has_local_data(storage_dir) is True
    assert qdrant_storage_has_local_data(tmp_path / "missing") is False


def test_qdrant_storage_has_local_data_ignores_empty_collection_root(tmp_path: Path) -> None:
    storage_dir = tmp_path / "data" / "qdrant"
    (storage_dir / "collections").mkdir(parents=True, exist_ok=True)

    assert qdrant_storage_has_local_data(storage_dir) is False


def test_build_qdrant_storage_warning_flags_unreadable_layout(tmp_path: Path) -> None:
    storage_dir = tmp_path / "data" / "qdrant"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "storage.sqlite").write_text("placeholder", encoding="utf-8")

    warning = build_qdrant_storage_warning(
        storage_path=storage_dir,
        local_collection_names=[],
        api_collection_names=[],
    )

    assert warning["key"] == "storage_layout_unreadable"
    assert warning["storage_path"] == str(storage_dir)
