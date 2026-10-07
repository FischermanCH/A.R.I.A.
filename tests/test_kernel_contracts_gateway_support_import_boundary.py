from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.action_contracts.capabilities import capability_executor_bindings
from aria.modules.action_contracts.plan import ActionPlan
from aria.modules.integration_support.runtime_endpoint import cookie_should_be_secure
from aria.modules.model_gateway_clients.embedding import EmbeddingClient
from aria.modules.pipeline_contracts.capability_details import build_pipeline_capability_detail_lines
from aria.modules.pipeline_contracts.capability_details import default_mqtt_topic_from_settings
from aria.modules.pipeline_contracts.result import PipelineResult
from aria.modules.configuration_foundations.config import EmbeddingsConfig


def test_kernel_contract_gateway_support_legacy_imports_are_identity_aliases() -> None:
    pairs = {
        "aria.modules.pipeline_contracts.result": "aria.modules.pipeline_contracts.result",
        "aria.modules.pipeline_contracts.capability_details": "aria.modules.pipeline_contracts.capability_details",
        "aria.modules.action_contracts.capabilities": "aria.modules.action_contracts.capabilities",
        "aria.modules.integration_support.error_interpreter": "aria.modules.integration_support.error_interpreter",
        "aria.modules.integration_support.runtime_endpoint": "aria.modules.integration_support.runtime_endpoint",
        "aria.modules.integration_support.google_calendar": "aria.modules.integration_support.google_calendar",
        "aria.modules.model_gateway_clients.llm": "aria.modules.model_gateway_clients.llm",
        "aria.modules.model_gateway_clients.embedding": "aria.modules.model_gateway_clients.embedding",
    }

    for legacy_name, canonical_name in pairs.items():
        legacy = importlib.import_module(legacy_name)
        canonical = importlib.import_module(canonical_name)
        assert legacy is canonical
        assert sys.modules[legacy_name] is canonical


def test_kernel_contract_gateway_support_manifests_are_passive() -> None:
    for module_id in ("action_contracts", "pipeline_contracts", "integration_support", "model_gateway_clients"):
        manifest = MODULE_MANIFESTS[module_id]
        assert manifest["status"] == "import_boundary_active"
        assert manifest["build_allowed"] is False
        assert manifest["runtime_access_allowed"] is False


def test_pipeline_and_capability_contract_shapes_are_preserved() -> None:
    result = PipelineResult(
        request_id="req-1",
        text="ok",
        usage={"total_tokens": 3},
        intents=["chat"],
        skill_errors=[],
        router_level=0,
        duration_ms=4,
    )

    assert result.detail_lines == []
    assert result.pending_action is None
    assert ("ssh", "ssh_command") in capability_executor_bindings()

    settings = SimpleNamespace(connections=SimpleNamespace(mqtt={"ops": {"topic": "aria/ops"}}))
    plan = ActionPlan(capability="mqtt_publish", connection_kind="mqtt", connection_ref="ops", content="on")
    details = build_pipeline_capability_detail_lines(
        plan,
        settings=settings,
        parse_rss_group_bundle_note=lambda _notes: None,
        truncate_text=lambda value, limit: value[:limit],
        language="de",
    )

    assert default_mqtt_topic_from_settings(settings, "ops") == "aria/ops"
    assert any("aria/ops" in line for line in details)


def test_gateway_and_endpoint_helpers_remain_passive_until_explicitly_called() -> None:
    client = EmbeddingClient(EmbeddingsConfig(model="text-embedding-3-small", api_base="https://api.example/v1/"))
    request = SimpleNamespace(url=SimpleNamespace(scheme="http"), headers={})

    assert client._resolve_model() == "openai/text-embedding-3-small"
    assert len(client.fingerprint()) == 64
    assert cookie_should_be_secure(request, public_url="https://aria.example") is True
