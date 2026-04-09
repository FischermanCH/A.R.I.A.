from __future__ import annotations

from pathlib import Path

import yaml

import aria.web.config_routes as config_routes_mod
from aria.core.guardrails import guardrail_kind_options


def test_guardrail_sample_yaml_uses_supported_guardrail_kinds() -> None:
    sample_path = Path("/home/fischerman/ARIA/samples/security/guardrails.sample.yaml")
    payload = yaml.safe_load(sample_path.read_text(encoding="utf-8"))

    guardrails = payload["security"]["guardrails"]
    assert isinstance(guardrails, dict) and guardrails
    assert "mqtt-status-only" in guardrails
    for row in guardrails.values():
        assert row["kind"] in guardrail_kind_options()


def test_build_sample_guardrail_rows_lists_starter_pack() -> None:
    rows = config_routes_mod._build_sample_guardrail_rows()

    assert rows
    starter = next(row for row in rows if row["file_name"] == "guardrails.sample.yaml")
    assert starter["profile_count"] == "4"
    assert "readonly-linux" in starter["profile_refs"]
    assert "MQTT Publish" in starter["kind_labels"]
