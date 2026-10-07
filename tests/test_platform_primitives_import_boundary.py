from __future__ import annotations

import importlib


MODULE_PAIRS = (
    ("aria.modules.platform_primitives.i18n", "aria.modules.platform_primitives.i18n"),
    ("aria.modules.platform_primitives.text_utils", "aria.modules.platform_primitives.text_utils"),
    ("aria.modules.platform_primitives.bounded_decision", "aria.modules.platform_primitives.bounded_decision"),
    ("aria.modules.platform_primitives.prompt_loader", "aria.modules.platform_primitives.prompt_loader"),
    ("aria.modules.platform_primitives.stage_timing", "aria.modules.platform_primitives.stage_timing"),
)


def test_legacy_platform_primitive_modules_are_canonical_modules() -> None:
    for legacy_path, canonical_path in MODULE_PAIRS:
        assert importlib.import_module(legacy_path) is importlib.import_module(canonical_path)


def test_legacy_platform_primitive_objects_are_canonical_objects() -> None:
    object_names = {
        "aria.modules.platform_primitives.i18n": "I18NStore",
        "aria.modules.platform_primitives.text_utils": "extract_json_object",
        "aria.modules.platform_primitives.bounded_decision": "BoundedDecisionClient",
        "aria.modules.platform_primitives.prompt_loader": "PromptLoader",
        "aria.modules.platform_primitives.stage_timing": "StageTimingLedger",
    }
    for legacy_path, canonical_path in MODULE_PAIRS:
        legacy_module = importlib.import_module(legacy_path)
        canonical_module = importlib.import_module(canonical_path)
        object_name = object_names[legacy_path]
        assert getattr(legacy_module, object_name) is getattr(canonical_module, object_name)
