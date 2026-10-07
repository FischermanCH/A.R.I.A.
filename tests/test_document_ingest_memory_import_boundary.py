from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.document_ingest.ingest", "aria.modules.document_ingest.ingest"),
    ("aria.modules.document_memory.meta_catalog", "aria.modules.document_memory.meta_catalog"),
    ("aria.modules.document_memory.helpers", "aria.modules.document_memory.helpers"),
    ("aria.modules.document_memory.service", "aria.modules.document_memory.service"),
)


def test_legacy_document_ingest_memory_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_document_ingest_memory_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.document_ingest.ingest": "prepare_uploaded_document",
        "aria.modules.document_memory.meta_catalog": "DocumentMetaCatalogStore",
        "aria.modules.document_memory.helpers": "is_document_payload",
        "aria.modules.document_memory.service": "DocumentMemoryService",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
