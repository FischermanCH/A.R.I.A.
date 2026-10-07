from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.notes.store", "aria.modules.notes.store"),
    ("aria.modules.notes.index", "aria.modules.notes.index"),
    ("aria.modules.notes.context", "aria.modules.notes.context"),
    ("aria.modules.notes.magic", "aria.modules.notes.magic"),
    ("aria.modules.notes.action_arbitration", "aria.modules.notes.action_arbitration"),
)


def test_legacy_notes_service_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_notes_service_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.notes.store": "NotesStore",
        "aria.modules.notes.index": "NotesIndex",
        "aria.modules.notes.context": "NotesContextHit",
        "aria.modules.notes.magic": "infer_note_title",
        "aria.modules.notes.action_arbitration": "NotesActionArbiter",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
