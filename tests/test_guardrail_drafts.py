from types import SimpleNamespace

import pytest

from aria.core.guardrail_drafts import (
    build_guardrail_draft_context,
    normalize_guardrail_draft,
    suggest_guardrail_with_llm,
)


def test_guardrail_draft_context_filters_by_guardrail_kind() -> None:
    raw = {
        "connections": {
            "ssh": {"dns-node-01": {}, "dev-node-02": {}},
            "smb": {"nas": {}},
        },
        "security": {
            "guardrails": {
                "safe-ssh": {
                    "kind": "ssh_command",
                    "title": "Safe SSH",
                    "allow_terms": ["uptime"],
                    "deny_terms": ["sudo"],
                },
                "safe-files": {"kind": "file_access", "title": "Files"},
            }
        },
    }

    context = build_guardrail_draft_context(raw, guardrail_kind="ssh_command", connection_kind="ssh")

    assert context["guardrail_kind"] == "ssh_command"
    assert context["compatible_connection_kinds"] == ["ssh"]
    assert context["connection_rows"] == [{"kind": "ssh", "count": 2, "refs": ["dev-node-02", "dns-node-01"]}]
    assert [row["ref"] for row in context["existing_guardrails"]] == ["safe-ssh"]


def test_normalize_guardrail_draft_cleans_terms_and_ref() -> None:
    draft = normalize_guardrail_draft(
        {
            "ref": "No Sudo On Ubuntu!",
            "kind": "ssh-command",
            "connection_kinds": ["ssh", "smb"],
            "title": "No sudo",
            "allow_terms": ["", " uptime ", "UPTIME", "df -h"],
            "deny_terms": "sudo\nsu\nsudo",
            "confidence": 2,
        },
        fallback_kind="ssh_command",
    )

    assert draft["ref"] == "no-sudo-on-ubuntu"
    assert draft["kind"] == "ssh_command"
    assert draft["connection_kinds"] == ["ssh"]
    assert draft["allow_terms"] == ["uptime", "df -h"]
    assert draft["deny_terms"] == ["sudo", "su"]
    assert draft["confidence"] == 1.0


@pytest.mark.anyio
async def test_suggest_guardrail_with_llm_returns_reviewable_draft() -> None:
    class FakeLLM:
        async def chat(self, *_args, **_kwargs):
            return SimpleNamespace(
                content=(
                    '{"ref":"no-sudo-linux","kind":"ssh_command","title":"No sudo",'
                    '"description":"Blocks privileged commands.",'
                    '"allow_terms":[],"deny_terms":["sudo","su"],'
                    '"scope_summary":"Attach to Ubuntu SSH profiles.",'
                    '"review_notes":["Check whether service restarts should remain possible."],'
                    '"examples":[{"text":"sudo systemctl restart nginx","expected":"block","reason":"sudo"}],'
                    '"confidence":0.86}'
                )
            )

    draft = await suggest_guardrail_with_llm(
        llm_client=FakeLLM(),
        instruction="Keine sudo Befehle auf Ubuntu Linux.",
        draft_context=build_guardrail_draft_context({}, guardrail_kind="ssh_command"),
    )

    assert draft["ref"] == "no-sudo-linux"
    assert draft["kind"] == "ssh_command"
    assert draft["allow_terms"] == []
    assert draft["deny_terms"] == ["sudo", "su"]
    assert draft["examples"][0]["expected"] == "block"
