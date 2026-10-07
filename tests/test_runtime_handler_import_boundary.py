from __future__ import annotations

import importlib

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_runtime_debug.debug import runtime_debug_line_for_plan
from aria.modules.ssh_runtime.outcome import ssh_runtime_outcome_metadata


def test_capability_runtime_handler_import_is_canonical() -> None:
    imported = importlib.import_module("aria.modules.capability_runtime.handler")
    canonical = importlib.import_module("aria.modules.capability_runtime.handler")

    assert imported is canonical
    assert imported.GenericCapabilityExecutionHandler is canonical.GenericCapabilityExecutionHandler


def test_capability_runtime_keeps_live_debug_and_ssh_boundaries() -> None:
    handler = importlib.import_module("aria.modules.capability_runtime.handler")
    manifest = MODULE_MANIFESTS["capability_runtime"]

    assert manifest["python"] == ["aria/modules/capability_runtime/handler.py"]
    assert "action_runtime_debug" in manifest["depends_on"]
    assert "ssh_runtime" in manifest["depends_on"]
    assert handler.runtime_debug_line_for_plan is runtime_debug_line_for_plan
    assert handler.ssh_runtime_outcome_metadata is ssh_runtime_outcome_metadata
