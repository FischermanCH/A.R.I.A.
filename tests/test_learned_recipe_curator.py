from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aria.core.learned_recipe_store as learned_store
from aria.core.learned_recipe_curator import CURATION_POLICY_CONTEXT_ONLY
from aria.core.learned_recipe_curator import curate_learned_recipe_entry
from aria.core.learned_recipe_curator import learned_recipe_needs_llm_curation
from aria.core.learned_recipe_curator import validate_learned_recipe_curation_payload


class _FakeLLM:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []

    async def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, **kwargs})
        return SimpleNamespace(content=self.content)


def test_validate_learned_recipe_curation_payload_bounds_review_metadata() -> None:
    payload = validate_learned_recipe_curation_payload(
        {
            "confidence": 7,
            "risk_level": "surprise",
            "generalization_hint": " Useful for safe status checks. ",
            "suggested_triggers": ["dns status", "", "dns status", "server ok"],
            "promotion_reason": "Repeated read-only success.",
            "limits": ["Do not restart services.", "Do not restart services."],
        }
    )

    assert payload["curation_policy"] == CURATION_POLICY_CONTEXT_ONLY
    assert payload["curation_status"] == "ok"
    assert payload["curation_last_error"] == ""
    assert payload["confidence"] == 1.0
    assert payload["risk_level"] == "unknown"
    assert payload["generalization_hint"] == "Useful for safe status checks."
    assert payload["suggested_triggers"] == ["dns status", "server ok"]
    assert payload["limits"] == ["Do not restart services."]


def test_learned_recipe_needs_llm_curation_skips_promoted_entries() -> None:
    assert learned_recipe_needs_llm_curation({"promotion_state": "promoted"}) is False
    assert learned_recipe_needs_llm_curation({"experience_count": 1}) is True
    assert learned_recipe_needs_llm_curation({"curation_source": "llm_curator", "experience_count": 2}) is False
    assert learned_recipe_needs_llm_curation({"curation_source": "llm_curator", "experience_count": 3}) is True


def test_curate_learned_recipe_entry_uses_llm_and_updates_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()
    llm = _FakeLLM(
        """
        {
          "confidence": 0.82,
          "risk_level": "low",
          "generalization_hint": "Works for read-only DNS health checks.",
          "suggested_triggers": ["ist mein dns server ok", "dns health"],
          "promotion_reason": "Same target and read-only action succeeded.",
          "limits": ["Do not use for restarts or writes."]
        }
        """
    )

    stored, debug = asyncio.run(
        curate_learned_recipe_entry(
            llm_client=llm,
            entry={
                "recipe_id": "learned-ssh-health-check-dns-node-01",
                "title": "Gelernter Server-Healthcheck: dns-node-01",
                "intent": "health_check",
                "connection_kind": "ssh",
                "connection_ref": "dns-node-01",
                "capability": "ssh_command",
                "chosen_action": "uptime -p && df -h",
                "execution_result": "success",
                "experience_count": 1,
            },
            language="de",
            user_id="neo",
        )
    )

    rows = learned_store.load_learned_recipe_store_entries()
    assert len(rows) == 1
    assert stored["confidence"] == 0.82
    assert stored["risk_level"] == "low"
    assert stored["generalization_hint"] == "Works for read-only DNS health checks."
    assert stored["suggested_triggers"] == ["ist mein dns server ok", "dns health"]
    assert stored["limits"] == ["Do not use for restarts or writes."]
    assert rows[0]["curation_source"] == "llm_curator"
    assert rows[0]["curation_status"] == "ok"
    assert rows[0]["curation_last_error"] == ""
    assert "agentic_source=llm_decision" in debug
    assert llm.calls[0]["source"] == "learned_recipe_curator"
    assert llm.calls[0]["operation"] == "curate_learned_recipe"


def test_curate_learned_recipe_entry_persists_skip_reason(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(learned_store, "_learned_recipe_store_path", lambda: tmp_path / "learned_recipes.json")
    learned_store.invalidate_learned_recipe_store_cache()

    stored, debug = asyncio.run(
        curate_learned_recipe_entry(
            llm_client=None,
            entry={
                "recipe_id": "learned-ssh-health-check-dns-node-01",
                "intent": "health_check",
                "connection_kind": "ssh",
                "connection_ref": "dns-node-01",
                "capability": "ssh_command",
                "chosen_action": "uptime -p && df -h",
                "execution_result": "success",
                "experience_count": 1,
            },
        )
    )

    rows = learned_store.load_learned_recipe_store_entries()
    assert stored["curation_status"] == "skipped"
    assert stored["curation_last_error"] == "llm_client_unavailable"
    assert rows[0]["curation_policy"] == CURATION_POLICY_CONTEXT_ONLY
    assert rows[0]["curation_status"] == "skipped"
    assert "llm_client_unavailable" in debug
