from __future__ import annotations

import importlib
from pathlib import Path


MODULE_PAIRS = (
    ("aria.modules.model_usage_observability.pricing_catalog", "aria.modules.model_usage_observability.pricing_catalog"),
    ("aria.modules.model_usage_observability.token_tracker", "aria.modules.model_usage_observability.token_tracker"),
    ("aria.modules.model_usage_observability.usage_meter", "aria.modules.model_usage_observability.usage_meter"),
    ("aria.modules.model_usage_observability.llm_audit", "aria.modules.model_usage_observability.llm_audit"),
)


def test_legacy_model_usage_observability_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_model_usage_observability_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.model_usage_observability.pricing_catalog": "resolve_pricing_entry",
        "aria.modules.model_usage_observability.token_tracker": "TokenTracker",
        "aria.modules.model_usage_observability.usage_meter": "UsageMeter",
        "aria.modules.model_usage_observability.llm_audit": "LLMAuditLog",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)


def test_canonical_llm_audit_default_path_remains_repository_relative() -> None:
    module = importlib.import_module("aria.modules.model_usage_observability.llm_audit")
    expected = Path(__file__).resolve().parents[1] / "data" / "runtime" / "llm_audit.jsonl"
    assert module._DEFAULT_AUDIT_PATH == expected
