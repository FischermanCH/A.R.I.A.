from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.execution_dry_run.dry_run", "aria.modules.execution_dry_run.dry_run"),
    ("aria.modules.execution_dry_run.text", "aria.modules.execution_dry_run.text"),
)


def test_legacy_execution_dry_run_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_execution_dry_run_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.execution_dry_run.dry_run": "evaluate_guardrail_confirm_dry_run",
        "aria.modules.execution_dry_run.text": "decision_summary",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
