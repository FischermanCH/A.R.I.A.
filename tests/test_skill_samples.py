from __future__ import annotations

import json
from pathlib import Path


EXPECTED_KEYS = {
    "category",
    "description",
    "enabled_default",
    "id",
    "name",
    "router_keywords",
    "schedule",
    "schema_version",
    "steps",
    "ui",
    "version",
}


ALLOWED_STEP_TYPES = {
    "chat_send",
    "discord_send",
    "llm_transform",
    "rss_read",
    "sftp_read",
    "smb_read",
    "ssh_run",
}


def test_sample_skill_manifests_are_valid_json_and_use_supported_step_types() -> None:
    sample_dir = Path("/home/fischerman/ARIA/samples/skills")
    files = sorted(sample_dir.glob("*.json"))

    assert files
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert EXPECTED_KEYS.issubset(payload.keys()), path.name
        assert isinstance(payload["steps"], list) and payload["steps"], path.name
        for step in payload["steps"]:
            assert step["type"] in ALLOWED_STEP_TYPES, f"{path.name}: {step['type']}"
