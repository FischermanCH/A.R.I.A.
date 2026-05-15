from __future__ import annotations

import asyncio
from types import SimpleNamespace

from aria.core.config import EmbeddingsConfig, MemoryConfig
from aria.core.recipe_experience_memory import build_recipe_experience_memory_text
from aria.core.recipe_experience_memory import delete_recipe_experience_memory
from aria.core.recipe_experience_memory import normalize_recipe_experience_memory_entry
from aria.core.recipe_experience_memory import recipe_experience_collection_for_user
from aria.core.recipe_experience_memory import search_recipe_experience_memory
from aria.core.recipe_experience_memory import store_recipe_experience_memory
from aria.skills.memory import MemorySkill


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, list] = {}

    @staticmethod
    def _matches_filter(payload, query_filter) -> bool:
        if not query_filter or not getattr(query_filter, "must", None):
            return True
        for condition in query_filter.must:
            key = getattr(condition, "key", "")
            match = getattr(condition, "match", None)
            if key and hasattr(match, "value") and payload.get(key) != getattr(match, "value", None):
                return False
        return True

    async def collection_exists(self, collection_name: str):
        return collection_name in self.collections

    async def create_collection(self, collection_name: str, vectors_config=None, **kwargs):
        _ = (vectors_config, kwargs)
        self.collections.setdefault(collection_name, [])

    async def get_collection(self, collection_name: str):
        _ = collection_name
        return None

    async def upsert(self, collection_name: str, points):
        self.collections.setdefault(collection_name, [])
        existing = {str(getattr(point, "id", "")): point for point in self.collections[collection_name]}
        for point in points:
            existing[str(getattr(point, "id", ""))] = point
        self.collections[collection_name] = list(existing.values())

    async def query_points(self, collection_name: str, query, query_filter, limit: int):
        _ = query
        points = [
            point
            for point in self.collections.get(collection_name, [])
            if self._matches_filter(getattr(point, "payload", {}) or {}, query_filter)
        ][:limit]
        hits = [
            SimpleNamespace(id=getattr(point, "id", ""), payload=getattr(point, "payload", {}) or {}, score=0.9 - (index * 0.1))
            for index, point in enumerate(points)
        ]
        return SimpleNamespace(points=hits)

    async def scroll(
        self,
        collection_name: str,
        scroll_filter=None,
        limit: int = 128,
        offset=None,
        with_payload: bool = False,
        with_vectors: bool = False,
    ):
        _ = (offset, with_payload, with_vectors)
        points = [
            point
            for point in self.collections.get(collection_name, [])
            if self._matches_filter(getattr(point, "payload", {}) or {}, scroll_filter)
        ][:limit]
        return points, None

    async def delete(self, collection_name: str, points_selector, wait: bool = True):
        _ = wait
        point_ids = {str(point_id) for point_id in list(getattr(points_selector, "points", []) or [])}
        self.collections[collection_name] = [
            point for point in self.collections.get(collection_name, []) if str(getattr(point, "id", "")) not in point_ids
        ]

    async def get_collections(self):
        return SimpleNamespace(collections=[SimpleNamespace(name=name) for name in sorted(self.collections)])


def _memory_skill() -> MemorySkill:
    skill = MemorySkill(
        memory=MemoryConfig(enabled=True, qdrant_url="http://unused:6333", collection="aria_memory", top_k=3),
        embeddings=EmbeddingsConfig(model="fake-embeddings"),
    )
    skill.qdrant = FakeQdrant()

    async def fake_embed(text: str, **kwargs):
        _ = kwargs
        seed = float(len(str(text or "")) % 10) / 10.0
        return [seed, 0.2, 0.3], {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1}

    skill._embed = fake_embed  # type: ignore[assignment]
    return skill


def test_recipe_experience_memory_text_keeps_context_without_executor_contract() -> None:
    text = build_recipe_experience_memory_text(
        {
            "recipe_id": "learned-ssh-health-check-pihole1",
            "title": "Gelernter Server-Healthcheck: pihole1",
            "user_message": "wie geht es meinem dns server",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "chosen_action": "uptime -p && df -h",
            "inputs": {"learned_from_command": "uptime"},
            "recipe_scope": {"learning_origin": "guardrail_healthcheck_fallback"},
            "confidence": 0.9,
            "risk_level": "low",
            "generalization_hint": "Useful for read-only health checks.",
            "suggested_triggers": ["dns health"],
            "promotion_reason": "Repeated safe status checks.",
            "limits": ["Do not restart services."],
            "learning_signal": "wording_variant",
            "learning_signal_reason": "Same pattern, different wording.",
            "learning_evidence": 2.5,
        }
    )

    assert "User phrasing: wie geht es meinem dns server" in text
    assert "Final action: uptime -p && df -h" in text
    assert "Learning origin: guardrail_healthcheck_fallback" in text
    assert "Curated confidence: 0.9" in text
    assert "Learning signal: wording_variant" in text
    assert "Learning evidence: 2.5" in text
    assert "Learning reason: Same pattern, different wording." in text
    assert "Generalization: Useful for read-only health checks." in text
    assert "Limits: Do not restart services." in text
    assert "Target fingerprint: ssh|pihole1" in text
    assert "Action fingerprint: ssh_command|health_check|uptime-p-df-h" in text


def test_normalize_recipe_experience_memory_entry_adds_stable_fingerprints() -> None:
    row = normalize_recipe_experience_memory_entry(
        {
            "recipe_id": " learned-health ",
            "intent": "Health_Check",
            "connection_kind": "SSH",
            "connection_ref": "pihole1",
            "capability": "SSH_COMMAND",
            "chosen_action": "uptime -p && df -h",
            "router_keywords": [" dns server ", "", "health"],
            "inputs": {"learned_from_command": "uptime"},
            "recipe_scope": {"learning_origin": "guardrail_healthcheck_fallback"},
        }
    )

    assert row["recipe_id"] == "learned-health"
    assert row["intent"] == "health_check"
    assert row["connection_kind"] == "ssh"
    assert row["capability"] == "ssh_command"
    assert row["router_keywords"] == ["dns server", "health"]
    assert row["learned_from_action"] == "uptime"
    assert row["learning_origin"] == "guardrail_healthcheck_fallback"
    assert row["target_fingerprint"] == "ssh|pihole1"
    assert row["action_fingerprint"] == "ssh_command|health_check|uptime-p-df-h"
    assert row["experience_fingerprint"] == "ssh|pihole1|ssh_command|health_check|uptime-p-df-h"


def test_store_and_search_recipe_experience_memory_round_trips_context_only() -> None:
    async def _run() -> None:
        skill = _memory_skill()
        entry = {
            "recipe_id": "learned-ssh-health-check-pihole1",
            "title": "Gelernter Server-Healthcheck: pihole1",
            "user_message": "wie geht es meinem dns server",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "chosen_action": "uptime -p && df -h && free -h",
            "promotion_state": "observed",
            "experience_count": 2,
        }

        stored = await store_recipe_experience_memory(skill, user_id="u1", entry=entry)
        rows = await search_recipe_experience_memory(
            skill,
            user_id="u1",
            query="wie geht es meinem dns server",
            connection_kind="ssh",
            connection_ref="pihole1",
        )

        assert stored["stored"] is True
        assert stored["collection"] == recipe_experience_collection_for_user("u1")
        assert len(rows) == 1
        assert rows[0]["recipe_id"] == "learned-ssh-health-check-pihole1"
        assert rows[0]["chosen_action"] == "uptime -p && df -h && free -h"
        assert rows[0]["promotion_state"] == "observed"
        assert rows[0]["target_fingerprint"] == "ssh|pihole1"
        assert rows[0]["action_fingerprint"] == "ssh_command|health_check|uptime-p-df-h-free-h"
        assert rows[0]["semantic_score"] == 0.9
        assert rows[0]["score"] > rows[0]["semantic_score"]

    asyncio.run(_run())


def test_recipe_experience_memory_keeps_distinct_actions_for_same_recipe() -> None:
    async def _run() -> None:
        skill = _memory_skill()
        base = {
            "recipe_id": "learned-ssh-health-check-pihole1",
            "title": "Gelernter Server-Healthcheck: pihole1",
            "user_message": "wie geht es meinem dns server",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "experience_count": 2,
        }

        await store_recipe_experience_memory(skill, user_id="u1", entry={**base, "chosen_action": "uptime -p"})
        await store_recipe_experience_memory(skill, user_id="u1", entry={**base, "chosen_action": "df -h"})
        rows = await search_recipe_experience_memory(
            skill,
            user_id="u1",
            query="wie geht es meinem dns server",
            connection_kind="ssh",
            connection_ref="pihole1",
            top_k=5,
        )

        assert {row["chosen_action"] for row in rows} == {"uptime -p", "df -h"}
        assert len({row["experience_fingerprint"] for row in rows}) == 2

    asyncio.run(_run())


def test_delete_recipe_experience_memory_removes_all_points_for_recipe() -> None:
    async def _run() -> None:
        skill = _memory_skill()
        base = {
            "recipe_id": "learned-ssh-health-check-pihole1",
            "title": "Gelernter Server-Healthcheck: pihole1",
            "user_message": "wie geht es meinem dns server",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "experience_count": 2,
        }

        await store_recipe_experience_memory(skill, user_id="u1", entry={**base, "chosen_action": "uptime -p"})
        await store_recipe_experience_memory(skill, user_id="u1", entry={**base, "chosen_action": "df -h"})
        await store_recipe_experience_memory(
            skill,
            user_id="u1",
            entry={**base, "recipe_id": "learned-other", "chosen_action": "free -h"},
        )

        deleted = await delete_recipe_experience_memory(
            skill,
            user_id="u1",
            recipe_id="learned-ssh-health-check-pihole1",
        )
        rows = await search_recipe_experience_memory(
            skill,
            user_id="u1",
            query="wie geht es meinem dns server",
            connection_kind="ssh",
            connection_ref="pihole1",
            top_k=5,
        )

        assert deleted["deleted"] is True
        assert deleted["deleted_points"] == 2
        assert {row["recipe_id"] for row in rows} == {"learned-other"}

    asyncio.run(_run())


def test_recipe_experience_debug_lines_mark_context_only_policy() -> None:
    from aria.core.pipeline import Pipeline

    rows = [
        {
            "recipe_id": "learned-ssh-health-check-pihole1",
            "title": "Gelernter Server-Healthcheck: pihole1",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "chosen_action": "uptime -p && df -h && free -h",
            "experience_count": 3,
            "score": 0.91,
        }
    ]

    context = Pipeline._format_recipe_experience_context(rows)
    debug_lines = Pipeline._recipe_experience_debug_lines(rows)

    assert context["recipe_experience_policy"].startswith("Context only")
    assert "worked_action=uptime -p && df -h && free -h" in context["recipe_experience"]
    assert debug_lines[0] == "Planner: recipe_experience_context policy=context_only executor=bounded_candidate_guardrails"
    assert debug_lines[1] == (
        "Planner: recipe_experience hit `learned-ssh-health-check-pihole1` "
        "score=0.910 semantic=0.910 target=ssh/pihole1 successes=3 worked_action=uptime -p && df -h && free -h"
    )


def test_recipe_experience_promotion_builds_review_candidate_without_executor() -> None:
    from aria.core.recipe_experience_promotion import build_learned_recipe_review_entry_from_experience
    from aria.core.recipe_experience_promotion import build_learned_recipe_review_entry_from_web_search_result
    from aria.core.recipe_experience_promotion import is_stored_recipe_promotable_capability

    ssh_entry = build_learned_recipe_review_entry_from_experience(
        {
            "title": "DNS health",
            "intent": "health_check",
            "connection_kind": "ssh",
            "connection_ref": "pihole1",
            "capability": "ssh_command",
            "chosen_action": "uptime -p && df -h",
            "experience_count": 2,
            "learning_origin": "guardrail_healthcheck_fallback",
        }
    )
    web_entry = build_learned_recipe_review_entry_from_web_search_result(
        query="aria pricing",
        title="ARIA pricing note",
        url="https://example.test/pricing",
        snippet="Useful source for pricing review.",
    )

    assert ssh_entry["promotion_state"] == "review_ready"
    assert ssh_entry["policy_result"] == "context_only"
    assert ssh_entry["recipe_scope"]["learning_origin"] == "guardrail_healthcheck_fallback"
    assert is_stored_recipe_promotable_capability(ssh_entry["capability"]) is True
    assert web_entry["capability"] == "web_search"
    assert web_entry["policy_result"] == "context_only"
    assert web_entry["inputs"]["source_url"] == "https://example.test/pricing"
    assert is_stored_recipe_promotable_capability(web_entry["capability"]) is False
