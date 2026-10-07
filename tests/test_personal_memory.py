from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from aria.modules.memory import personal as personal_memory
from aria.modules.memory.personal import apply_recent_personal_context_feedback
from aria.modules.memory.personal import PERSONAL_CLAIM_CONTRACT
from aria.modules.memory.personal import PERSONAL_CONTEXT_CAPSULE_CONTRACT
from aria.modules.memory.personal import build_personal_context_capsule
from aria.modules.memory.personal import consolidate_personal_claim_batch
from aria.modules.memory.personal import normalize_personal_claim
from aria.modules.memory.personal import personal_claim_activation_allowed
from aria.modules.memory.personal import personal_claim_activation_blockers
from aria.modules.memory.personal import personal_claim_payload
from aria.modules.memory.personal import personal_claim_payload_lifecycle_state
from aria.modules.memory.personal import personal_claim_payload_review_due
from aria.modules.memory.personal import personal_claim_payload_is_runtime_active
from aria.modules.memory.personal import personal_claim_review_candidate
from aria.modules.memory.personal import personal_context_capsule_llm_view
from aria.modules.memory.personal import record_personal_context_presentation
from aria.modules.memory.personal import record_personal_context_influence
from aria.modules.memory.personal import review_personal_context_influence
from aria.modules.memory.personal import select_personal_context_capsule
from aria.modules.memory.personal import store_personal_claim
from aria.skills.base import SkillResult


class _Response:
    def __init__(self, payload: dict) -> None:
        self.content = json.dumps(payload)
        self.usage = {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7}


class _RelationLLM:
    async def chat(self, messages, **kwargs):
        assert kwargs["operation"] == "personal_claim_relation"
        payload = json.loads(messages[-1]["content"])
        target = payload["existing_claims"][0]["claim_id"]
        return _Response(
            {
                "relation": "replaces",
                "target_claim_id": target,
                "confidence": "high",
                "reason": "new explicit preference replaces old preference",
            }
        )


class _UnexpectedRelationLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, messages, **kwargs):
        self.calls += 1
        raise AssertionError(f"unexpected relation call: {kwargs.get('operation')}")


class _InfluenceLLM:
    async def chat(self, messages, **kwargs):
        assert kwargs["operation"] == "personal_context_influence_review"
        payload = json.loads(messages[-1]["content"])
        return _Response(
            {
                "used_claim_ids": [payload["claims"][0]["claim_id"], "invented-id"],
                "changed_outcome": True,
                "confidence": "high",
                "reason": "The answer follows the requested response style.",
            }
        )


class _ContextSelectionLLM:
    async def chat(self, messages, **kwargs):
        assert kwargs["operation"] == "personal_context_selection"
        payload = json.loads(messages[-1]["content"])
        selected = next(
            claim["claim_id"]
            for claim in payload["claims"]
            if claim["value"] == "selected project context"
        )
        return _Response(
            {
                "selected_claim_ids": [selected, "invented-id"],
                "confidence": "high",
                "reason": "The selected project matches the current turn.",
            }
        )


class _BatchConsolidationLLM:
    async def chat(self, messages, **kwargs):
        assert kwargs["operation"] == "personal_claim_batch_consolidation"
        payload = json.loads(messages[-1]["content"])
        refs = [row["claim_ref"] for row in payload["claims"]]
        return _Response(
            {
                "groups": [{"claim_refs": refs, "representative_ref": refs[0]}],
                "confidence": "high",
            }
        )


class _Memory:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.existing = list(existing or [])
        self.stores: list[dict] = []
        self.updates: list[tuple[str, str, str, dict]] = []

    async def list_personal_claims(self, *, user_id: str, limit: int = 120):
        assert user_id == "u1"
        return list(self.existing)[:limit]

    async def execute(self, query: str, params: dict):
        self.stores.append({"query": query, "params": params})
        return SkillResult(
            skill_name="memory",
            content="ok",
            success=True,
            metadata={"point_id": "new-point", "collection": params["collection"]},
        )

    async def update_memory_point_payload(self, user_id: str, collection: str, point_id: str, updates: dict):
        self.updates.append((user_id, collection, point_id, dict(updates)))
        return True


class _DeduplicatingMemory(_Memory):
    async def execute(self, query: str, params: dict):
        self.stores.append({"query": query, "params": params})
        return SkillResult(
            skill_name="memory",
            content="Bereits gespeichert.",
            success=True,
            metadata={
                "deduplicated": True,
                "point_id": "legacy-point",
                "collection": params["collection"],
            },
        )


class _FlakyMemory(_Memory):
    def __init__(self, *, failures_before_success: int) -> None:
        super().__init__()
        self.failures_before_success = failures_before_success

    async def execute(self, query: str, params: dict):
        self.stores.append({"query": query, "params": params})
        if len(self.stores) <= self.failures_before_success:
            return SkillResult(
                skill_name="memory",
                content="",
                success=False,
                error="embedding_error: boom",
            )
        return SkillResult(
            skill_name="memory",
            content="ok",
            success=True,
            metadata={"point_id": "new-point", "collection": params["collection"]},
        )


class _ContentFailureMemory(_Memory):
    async def execute(self, query: str, params: dict):
        self.stores.append({"query": query, "params": params})
        return SkillResult(
            skill_name="memory",
            content="embedding_error: fallback " + ("x" * 300),
            success=False,
        )


def _claim(value: str, *, authority: str = "explicit_user") -> dict:
    return {
        "claim_kind": "preference",
        "subject": "user",
        "predicate": "preferred answer detail",
        "value": value,
        "scope": "global",
        "explicit": True,
        "authority": authority,
        "risk": "low",
        "confidence": "high",
    }


def test_personal_claim_contract_is_stable_and_auto_activation_is_explicit_only() -> None:
    claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    inferred = normalize_personal_claim(
        {**_claim("short answers"), "explicit": False, "authority": "inferred"},
        user_id="u1",
    )

    assert claim["contract"] == PERSONAL_CLAIM_CONTRACT
    assert claim["claim_key"]
    assert claim["claim_id"]
    assert personal_claim_activation_allowed(claim) is True
    assert personal_claim_activation_allowed(inferred) is False


def test_personal_claim_batch_consolidates_same_turn_paraphrases_before_write() -> None:
    first = normalize_personal_claim(
        _claim("kurz und direkt"),
        user_id="u1",
        source="turn_action_contract",
    )
    second = normalize_personal_claim(
        {
            **_claim("knapp, ohne unnoetige Erklaerungen"),
            "predicate": "response_style",
        },
        user_id="u1",
        source="turn_action_contract",
    )

    result = asyncio.run(
        consolidate_personal_claim_batch(
            [first, second],
            llm_client=_BatchConsolidationLLM(),
            user_id="u1",
            request_id="request-1",
        )
    )

    assert result["ok"] is True
    assert result["input_count"] == 2
    assert result["output_count"] == 1
    assert result["claims"] == [first]


def test_entity_alias_cannot_bypass_evidence_bound_learning_activation() -> None:
    alias = normalize_personal_claim(
        {
            **_claim("Simpooni means Simponi 50 mg"),
            "claim_kind": "entity_alias",
            "predicate": "medication_alias",
        },
        user_id="u1",
    )

    assert alias["claim_kind"] == "entity_alias"
    assert personal_claim_activation_allowed(alias) is False


def test_session_scoped_claim_does_not_become_durable_personal_truth_or_review_backlog() -> None:
    claim = normalize_personal_claim({**_claim("short answers"), "scope": "session"}, user_id="u1")

    assert personal_claim_activation_allowed(claim) is False
    assert personal_claim_review_candidate(claim, reason="claim_not_auto_activatable") == {}


def test_expired_active_claim_is_not_runtime_active_or_auto_activatable() -> None:
    expired = normalize_personal_claim(
        {**_claim("short answers"), "valid_until": "2020-01-01T00:00:00+00:00"},
        user_id="u1",
    )
    payload = personal_claim_payload(expired, status="active")

    assert personal_claim_activation_allowed(expired) is False
    assert personal_claim_payload_is_runtime_active(payload) is False
    assert personal_claim_payload_lifecycle_state(payload) == "expired"


def test_future_claim_is_scheduled_until_its_validity_starts() -> None:
    future = normalize_personal_claim(
        {**_claim("short answers"), "valid_from": "2099-01-01T00:00:00+00:00"},
        user_id="u1",
    )
    payload = personal_claim_payload(future, status="active")

    assert personal_claim_activation_allowed(future) is True
    assert personal_claim_payload_is_runtime_active(payload) is False
    assert personal_claim_payload_lifecycle_state(payload) == "scheduled"


def test_review_due_is_visible_without_disabling_an_effective_claim() -> None:
    claim = normalize_personal_claim(
        {**_claim("short answers"), "review_after": "2020-01-01T00:00:00+00:00"},
        user_id="u1",
    )
    payload = personal_claim_payload(claim, status="active")

    assert personal_claim_payload_review_due(payload) is True
    assert personal_claim_payload_is_runtime_active(payload) is True


def test_store_personal_claim_activates_new_low_risk_explicit_claim() -> None:
    memory = _Memory()

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("short answers"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_activated"
    assert memory.stores[0]["params"]["collection"] == "aria_preferences_u1"
    payload = memory.stores[0]["params"]["payload_metadata"]
    assert payload["personal_claim_contract"] == PERSONAL_CLAIM_CONTRACT
    assert payload["claim_status"] == "active"
    assert memory.updates == []


def test_store_personal_claim_retries_transient_store_failures(monkeypatch) -> None:
    memory = _FlakyMemory(failures_before_success=2)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(personal_memory.asyncio, "sleep", fake_sleep)
    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("No Man's Sky"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["stored"] is True
    assert result["reason"] == "claim_activated"
    assert len(memory.stores) == 3
    assert sleeps == [0.2, 0.4]


def test_store_personal_claim_reports_persistent_store_error(monkeypatch) -> None:
    memory = _FlakyMemory(failures_before_success=3)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(personal_memory.asyncio, "sleep", fake_sleep)
    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("No Man's Sky"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["stored"] is False
    assert result["reason"] == "claim_store_failed"
    assert "embedding_error: boom" in result["store_error"]
    assert len(memory.stores) == 3
    assert sleeps == [0.2, 0.4]


def test_store_personal_claim_uses_bounded_content_when_error_is_empty(monkeypatch) -> None:
    memory = _ContentFailureMemory()

    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(personal_memory.asyncio, "sleep", fake_sleep)
    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("No Man's Sky"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["store_error"].startswith("embedding_error: fallback")
    assert len(result["store_error"]) <= 240
    assert len(memory.stores) == 3


def test_store_novel_personal_claim_does_not_compare_against_unrelated_profile() -> None:
    existing_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    memory = _Memory(
        [{
            "id": "existing-point",
            "collection": "aria_preferences_u1",
            **personal_claim_payload(existing_claim, status="active"),
        }]
    )
    llm = _UnexpectedRelationLLM()

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=llm,
            claim={
                "claim_kind": "project",
                "subject": "Projekt Nebel",
                "predicate": "Farbe",
                "value": "Tuerkis",
                "scope": "project",
                "scope_ref": "Projekt Nebel",
                "explicit": True,
                "authority": "explicit_user",
                "risk": "low",
                "confidence": "high",
            },
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_activated"
    assert result["relation"]["source"] == "no_same_proposition"
    assert llm.calls == 0
    assert len(memory.stores) == 1


def test_explicit_project_claim_round_trips_into_immediate_exact_subject_capsule() -> None:
    memory = _Memory()
    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim={
                "claim_kind": "project",
                "subject": "Projekt Nebel",
                "predicate": "Farbe",
                "value": "Tuerkis",
                "scope": "project",
                "scope_ref": "Projekt Nebel",
                "explicit": True,
                "authority": "explicit_user",
                "risk": "low",
                "confidence": "high",
            },
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )
    stored = memory.stores[0]["params"]
    memory.existing = [
        {
            "id": result["point_id"],
            "collection": stored["collection"],
            **stored["payload_metadata"],
        }
    ]

    capsule = asyncio.run(
        build_personal_context_capsule(
            memory,
            user_id="u1",
            message="Welche Farbe hat Projekt Nebel?",
        )
    )

    assert capsule["coverage"] == "complete_active_set"
    assert capsule["provided_claim_count"] == 1
    assert capsule["claims"][0]["value"] == "Tuerkis"


def test_store_personal_claim_adopts_matching_legacy_text_into_claim_contract() -> None:
    memory = _DeduplicatingMemory()

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("short answers"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_activated"
    assert memory.updates[0][2] == "legacy-point"
    assert memory.updates[0][3]["personal_claim_contract"] == PERSONAL_CLAIM_CONTRACT
    assert memory.updates[0][3]["claim_status"] == "active"


def test_repeated_exact_personal_claim_increments_support_without_duplicate() -> None:
    normalized = normalize_personal_claim(
        {**_claim("short answers"), "evidence_refs": [{"source": "chat", "request_id": "old"}]},
        user_id="u1",
    )
    existing = {
        "id": "existing-point",
        "collection": "aria_preferences_u1",
        **personal_claim_payload(normalized, status="active"),
        "claim_support_count": 2,
    }
    memory = _Memory([existing])

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim={
                **_claim("short answers"),
                "evidence_refs": [{"source": "chat", "request_id": "request-2"}],
            },
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
            request_id="request-2",
        )
    )

    assert result["reason"] == "existing_claim_supported"
    assert memory.stores == []
    assert memory.updates[0][2] == "existing-point"
    assert memory.updates[0][3]["claim_support_count"] == 3
    assert memory.updates[0][3]["claim_last_supported_request_id"] == "request-2"


def test_store_personal_claim_supersedes_old_claim_store_before_status_change() -> None:
    old_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    existing = {
        "id": "old-point",
        "collection": "aria_preferences_u1",
        **personal_claim_payload(old_claim, status="active"),
    }
    memory = _Memory([existing])

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=_RelationLLM(),
            claim={**_claim("detailed answers"), "authority": "user_correction"},
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_superseded"
    assert memory.stores[0]["params"]["payload_metadata"]["claim_status"] == "pending_supersession"
    assert memory.updates[0][2] == "old-point"
    assert memory.updates[0][3]["claim_status"] == "historical"
    assert memory.updates[1][2] == "new-point"
    assert memory.updates[1][3]["claim_status"] == "active"


def test_explicit_user_control_supersedes_selected_same_key_without_llm_relation() -> None:
    old_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    existing = {
        "id": "old-point",
        "collection": "aria_preferences_u1",
        **personal_claim_payload(old_claim, status="active"),
    }
    memory = _Memory([existing])

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim={**_claim("detailed answers"), "authority": "user_correction"},
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
            explicit_supersedes_claim_id=old_claim["claim_id"],
        )
    )

    assert result["reason"] == "claim_superseded"
    assert result["relation"]["source"] == "explicit_user_control"
    assert memory.updates[0][3]["claim_status"] == "historical"
    assert memory.updates[1][3]["claim_status"] == "active"


def test_explicit_user_control_rejects_wrong_supersession_target() -> None:
    old_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    memory = _Memory(
        [
            {
                "id": "old-point",
                "collection": "aria_preferences_u1",
                **personal_claim_payload(old_claim, status="active"),
            }
        ]
    )

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim={**_claim("detailed answers"), "authority": "user_correction"},
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
            explicit_supersedes_claim_id="not-the-selected-claim",
        )
    )

    assert result["reason"] == "explicit_supersession_target_invalid"
    assert memory.stores == []


def test_sensitive_or_inferred_claim_is_not_written_as_active_memory() -> None:
    memory = _Memory()

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim={**_claim("run updates automatically"), "risk": "high"},
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_not_auto_activatable"
    assert result["activation_blockers"] == ["risk_not_low"]
    assert memory.stores == []


def test_personal_claim_activation_blockers_explain_review_authority() -> None:
    claim = normalize_personal_claim(
        {
            **_claim("usually prefers short answers"),
            "explicit": False,
            "authority": "inferred",
            "risk": "medium",
            "confidence": 0.4,
        },
        user_id="u1",
    )

    assert personal_claim_activation_blockers(claim) == (
        "not_explicit",
        "risk_not_low",
        "insufficient_authority",
        "low_confidence",
    )


def test_same_key_conflict_fails_closed_when_relation_review_is_unavailable() -> None:
    old_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    existing = {
        "id": "old-point",
        "collection": "aria_preferences_u1",
        **personal_claim_payload(old_claim, status="active"),
    }
    memory = _Memory([existing])

    result = asyncio.run(
        store_personal_claim(
            memory_skill=memory,
            llm_client=None,
            claim=_claim("detailed answers"),
            user_id="u1",
            facts_collection="aria_facts_u1",
            preferences_collection="aria_preferences_u1",
        )
    )

    assert result["reason"] == "claim_relation_unresolved"
    assert memory.stores == []


def test_non_activatable_claim_becomes_review_candidate_contract() -> None:
    normalized = normalize_personal_claim(
        {**_claim("usually prefers short answers"), "explicit": False, "authority": "inferred"},
        user_id="u1",
    )

    candidate = personal_claim_review_candidate(normalized, reason="claim_not_auto_activatable")

    assert candidate["artifact_type"] == "personal_claim_candidate"
    assert candidate["synthesis_target"] == "personal_claim"
    assert candidate["review_worthy"] is True
    assert candidate["proposed_change"]["personal_claim"]["explicit"] is False


def test_personal_context_capsule_contains_only_active_claims() -> None:
    active_claim = normalize_personal_claim(_claim("short answers"), user_id="u1")
    historical_claim = normalize_personal_claim(
        {
            **_claim("detailed answers"),
            "predicate": "previous answer detail",
        },
        user_id="u1",
    )
    memory = _Memory(
        [
            {
                "id": "active-point",
                "collection": "aria_preferences_u1",
                **personal_claim_payload(active_claim, status="active"),
            },
            {
                "id": "historical-point",
                "collection": "aria_preferences_u1",
                **personal_claim_payload(historical_claim, status="historical"),
            },
        ]
    )

    capsule = asyncio.run(build_personal_context_capsule(memory, user_id="u1"))

    assert capsule["contract"] == PERSONAL_CONTEXT_CAPSULE_CONTRACT
    assert capsule["coverage"] == "complete_active_set"
    assert capsule["active_claim_count"] == 1
    assert capsule["provided_claim_count"] == 1
    assert [claim["point_id"] for claim in capsule["claims"]] == ["active-point"]
    assert "short answers" in capsule["text"]
    assert "detailed answers" not in capsule["text"]


def test_personal_context_presentation_keeps_explicit_global_baseline_when_router_omits_ids() -> None:
    capsule = {
        "contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT,
        "claims": [
            {
                "claim_id": "global-preference",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "response_style",
                "value": "short and direct",
                "scope": "global",
                "authority": "explicit_user",
            },
            {
                "claim_id": "scoped-preference",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "project_format",
                "value": "table",
                "scope": "project",
                "scope_ref": "project-a",
                "authority": "explicit_user",
            },
            {
                "claim_id": "inferred-global-preference",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "tone",
                "value": "formal",
                "scope": "global",
                "authority": "inferred",
            },
            {
                "claim_id": "global-fact",
                "claim_kind": "fact",
                "subject": "user",
                "predicate": "favorite_color",
                "value": "green",
                "scope": "global",
                "authority": "explicit_user",
            },
        ],
    }

    selected = select_personal_context_capsule(capsule, ())

    assert [claim["claim_id"] for claim in selected["claims"]] == ["global-preference"]
    assert selected["selection_source"] == "structured_global_baseline"
    assert selected["available_count"] == 4
    assert selected["router_selected_count"] == 0
    assert selected["structured_global_baseline_count"] == 1


def test_personal_context_presentation_preserves_router_selected_scoped_claims() -> None:
    capsule = {
        "contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT,
        "claims": [
            {
                "claim_id": "global-boundary",
                "claim_kind": "boundary",
                "subject": "user",
                "predicate": "interaction_boundary",
                "value": "do not infer consent",
                "scope": "global",
                "authority": "user_correction",
            },
            {
                "claim_id": "selected-project",
                "claim_kind": "project",
                "subject": "user",
                "predicate": "current_project",
                "value": "ARIA",
                "scope": "project",
                "scope_ref": "aria",
                "authority": "explicit_user",
            },
        ],
    }

    selected = select_personal_context_capsule(capsule, ("selected-project", "invented-id"))

    assert [claim["claim_id"] for claim in selected["claims"]] == [
        "global-boundary",
        "selected-project",
    ]
    assert selected["selection_source"] == "turn_plan+structured_global_baseline"
    assert selected["router_selected_count"] == 1
    assert selected["structured_global_baseline_count"] == 1


def test_personal_context_presentation_empty_profile_stays_empty() -> None:
    selected = select_personal_context_capsule({}, ())

    assert selected["claims"] == []
    assert selected["text"] == ""
    assert selected["available_count"] == 0
    assert selected["router_selected_count"] == 0
    assert selected["structured_global_baseline_count"] == 0


def test_independent_context_suppresses_unselected_global_personal_baseline() -> None:
    capsule = {
        "contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT,
        "claims": [
            {
                "claim_id": "global-preference",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "response_style",
                "value": "short and direct",
                "scope": "global",
                "authority": "explicit_user",
            }
        ],
    }

    selected = select_personal_context_capsule(
        capsule,
        (),
        include_structured_global_baseline=False,
    )

    assert selected["claims"] == []
    assert selected["text"] == ""
    assert selected["available_count"] == 1
    assert selected["router_selected_count"] == 0
    assert selected["structured_global_baseline_count"] == 0
    assert selected["selection_source"] == "turn_plan"


def test_overfull_personal_context_capsule_uses_bounded_llm_context_selection() -> None:
    rows = []
    for index in range(13):
        value = "selected project context" if index == 12 else f"other context {index}"
        claim = normalize_personal_claim(
            {
                **_claim(value),
                "claim_kind": "project",
                "predicate": f"project context {index}",
            },
            user_id="u1",
        )
        rows.append(
            {
                "id": f"point-{index}",
                "collection": "aria_facts_u1",
                **personal_claim_payload(claim, status="active"),
            }
        )
    memory = _Memory(rows)

    capsule = asyncio.run(
        build_personal_context_capsule(
            memory,
            user_id="u1",
            limit=12,
            message="Continue the selected project.",
            llm_client=_ContextSelectionLLM(),
            request_id="request-1",
        )
    )

    assert capsule["selection_source"] == "bounded_llm"
    assert capsule["coverage"] == "relevance_selected"
    assert capsule["active_claim_count"] == 13
    assert capsule["provided_claim_count"] == 1
    assert [claim["value"] for claim in capsule["claims"]] == ["selected project context"]


def test_personal_context_presentation_updates_existing_claim_without_new_points() -> None:
    memory = _Memory()
    capsule = {
        "claims": [
            {
                "collection": "aria_preferences_u1",
                "point_id": "claim-point",
                "presented_count": 2,
            }
        ]
    }

    result = asyncio.run(
        record_personal_context_presentation(
            memory,
            user_id="u1",
            request_id="request-1",
            capsule=capsule,
            surfaces=["turn_arbitration", "final_response"],
        )
    )

    assert result == {"presented": 1, "updated": 1}
    assert memory.stores == []
    assert memory.updates[0][3]["claim_presented_count"] == 3
    assert memory.updates[0][3]["claim_last_presented_surfaces"] == '["turn_arbitration","final_response"]'


def test_personal_context_llm_view_hides_storage_coordinates() -> None:
    capsule = {
        "contract": PERSONAL_CONTEXT_CAPSULE_CONTRACT,
        "text": "[PERSONAL CONTEXT CAPSULE]",
        "claims": [
            {
                "claim_id": "claim-1",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "preferred answer detail",
                "value": "short answers",
                "scope": "global",
                "scope_ref": "",
                "authority": "explicit_user",
                "collection": "aria_preferences_u1",
                "point_id": "private-point-id",
                "presented_count": 4,
            }
        ],
    }

    llm_view = personal_context_capsule_llm_view(capsule)

    assert llm_view["claims"][0]["claim_id"] == "claim-1"
    assert "collection" not in llm_view["claims"][0]
    assert "point_id" not in llm_view["claims"][0]
    assert "presented_count" not in llm_view["claims"][0]


def test_empty_complete_personal_context_capsule_remains_authoritative_for_llm() -> None:
    capsule = asyncio.run(build_personal_context_capsule(_Memory(), user_id="u1"))

    llm_view = personal_context_capsule_llm_view(capsule)

    assert llm_view["coverage"] == "complete_active_set"
    assert llm_view["active_claim_count"] == 0
    assert llm_view["provided_claim_count"] == 0
    assert llm_view["claims"] == []
    assert "structured personal model does not currently know" in llm_view["authority_policy"]


def test_personal_context_influence_review_validates_ids_and_persists_used_receipt() -> None:
    memory = _Memory()
    capsule = {
        "claims": [
            {
                "claim_id": "claim-1",
                "claim_kind": "preference",
                "subject": "user",
                "predicate": "preferred answer detail",
                "value": "short answers",
                "scope": "global",
                "scope_ref": "",
                "authority": "explicit_user",
                "collection": "aria_preferences_u1",
                "point_id": "claim-point",
                "used_count": 2,
                "changed_outcome_count": 1,
            }
        ]
    }

    review = asyncio.run(
        review_personal_context_influence(
            _InfluenceLLM(),
            user_id="u1",
            request_id="request-2",
            message="Explain this.",
            response="Short explanation.",
            capsule=capsule,
        )
    )
    result = asyncio.run(
        record_personal_context_influence(
            memory,
            user_id="u1",
            request_id="request-2",
            capsule=capsule,
            review=review,
        )
    )

    assert review["used_claim_ids"] == ["claim-1"]
    assert review["changed_outcome"] is True
    assert result == {"used": 1, "updated": 1}
    updates = memory.updates[0][3]
    assert updates["claim_used_count"] == 3
    assert updates["claim_changed_outcome_count"] == 2
    assert '"request_id":"request-2"' in updates["claim_last_influence_receipt"]


def test_personal_context_feedback_no_longer_links_persisted_learning_receipts() -> None:
    now = datetime.now(timezone.utc)
    memory = _Memory(
        [
            {
                "id": "latest-point",
                "collection": "aria_preferences_u1",
                "claim_id": "claim-latest",
                "claim_last_used_at": now.isoformat(),
                "claim_last_used_request_id": "request-latest",
            },
            {
                "id": "older-point",
                "collection": "aria_preferences_u1",
                "claim_id": "claim-older",
                "claim_last_used_at": (now - timedelta(minutes=5)).isoformat(),
                "claim_last_used_request_id": "request-older",
            },
        ]
    )

    result = asyncio.run(
        apply_recent_personal_context_feedback(
            memory,
            user_id="u1",
            sentiment="negative",
            target_request_id="request-latest",
        )
    )

    assert result == {
        "linked_claim_ids": [],
        "request_id": "request-latest",
    }
    assert memory.updates == []


def test_personal_context_feedback_keeps_request_id_without_linking() -> None:
    now = datetime.now(timezone.utc)
    memory = _Memory(
        [
            {
                "id": "older-point",
                "collection": "aria_preferences_u1",
                "claim_id": "claim-older",
                "claim_last_used_at": now.isoformat(),
                "claim_last_used_request_id": "request-influenced",
            }
        ]
    )

    result = asyncio.run(
        apply_recent_personal_context_feedback(
            memory,
            user_id="u1",
            sentiment="positive",
            target_request_id="request-plain-turn",
        )
    )

    assert result == {
        "linked_claim_ids": [],
        "request_id": "request-plain-turn",
    }
    assert memory.updates == []
