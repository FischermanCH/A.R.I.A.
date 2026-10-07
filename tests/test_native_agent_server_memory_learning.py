from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from aria.modules import MODULE_MANIFESTS
from aria.modules.configuration_foundations.config import LLMConfig
from aria.modules.memory import native_tools as memory_native_tools
from aria.modules.native_agent.handler import (
    _MEMORY_FIRST_PERSON_CUES,
    _MEMORY_LEARN_SYSTEM_PROMPT,
    _memory_learning_prefilter,
    run_native_agent_turn,
)
from aria.modules.native_agent.pending_store import NativePendingStore
from aria.modules.native_agent.tool_registry import assemble_native_tools
from aria.modules.platform_primitives.observed_claims import (
    MEMORY_RECURRENCE_THRESHOLD,
    ObservedClaimStore,
    claim_recurrence_text,
    recurrence_key,
)
from aria.modules.sdk import NativeToolBinding, NativeToolContract, NativeToolResult


DOWNBEAT_CLAIM = {
    "claim_kind": "preference",
    "subject": "user",
    "predicate": "music_preference",
    "value": "downbeat",
}

CHILI_CLAIM = {
    "claim_kind": "preference",
    "subject": "user",
    "predicate": "food_spiciness_preference",
    "value": "scharfes essen mit chili",
}


def _response(*, content: str = "", tool_name: str = "", arguments=None):  # noqa: ANN001
    calls = []
    if tool_name:
        calls = [SimpleNamespace(
            id=f"call-{tool_name}",
            function=SimpleNamespace(name=tool_name, arguments=json.dumps(arguments or {})),
        )]
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=content, tool_calls=calls),
            finish_reason="tool_use" if calls else "stop",
        )],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def _owner(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        settings=SimpleNamespace(),
        memory_skill=SimpleNamespace(
            list_personal_claims=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("learning must not call list_personal_claims")
            )
        ),
        llm_client=object(),
        _facts_collection_for_user=lambda user_id: f"facts-{user_id}",
        _preferences_collection_for_user=lambda user_id: f"preferences-{user_id}",
    )


def _memory_capture_binding(owner: SimpleNamespace):
    return next(
        binding
        for binding in memory_native_tools.native_tool_contributions(owner)
        if binding.contract.name == "memory_capture"
    )


def _noop_binding() -> NativeToolBinding:
    async def handle(_context, _arguments):  # noqa: ANN001
        return NativeToolResult('{"status":"ok"}', "noop")

    return NativeToolBinding(
        contract=NativeToolContract(
            owner_module_id="native_agent",
            name="noop_read",
            description="Read-only test tool.",
            input_schema={"type": "object", "properties": {}, "required": []},
            effect="read_only",
            confirmation_required=False,
            source_authority="test:noop",
            user_scoped=True,
            rollout_flag="test",
            order=1,
        ),
        handler=handle,
    )


class _Embedder:
    model = "text-embedding-3-small"

    def __init__(self, vector=(1.0, 0.0)) -> None:  # noqa: ANN001
        self.vector = vector
        self.calls: list[tuple[object, dict[str, object]]] = []

    async def embed(self, inputs, **kwargs):  # noqa: ANN001, ANN003
        self.calls.append((inputs, kwargs))
        return SimpleNamespace(vectors=[self.vector])


class _ValueSensitiveEmbedder:
    """Expose whether recurrence embedding text includes model-variable fields."""

    model = "text-embedding-3-small"

    def __init__(self) -> None:
        self.texts: list[str] = []

    async def embed(self, inputs, **_kwargs):  # noqa: ANN001, ANN003
        text = str(inputs[0])
        self.texts.append(text)
        vectors = {
            "mate": (1.0, 0.0),
            "python": (0.0, 1.0),
            "grüner tee": (1.0, 0.0),
            "grüner tee am morgen": (0.98, 0.2),
            "python programmierung": (0.0, 1.0),
        }
        if text in vectors:
            vector = vectors[text]
        elif "preferred_tea" in text:
            vector = (1.0, 0.0)
        else:
            vector = (0.0, 1.0)
        return SimpleNamespace(vectors=[vector])


def test_prefilter_admits_supported_first_person_without_durable_keyword() -> None:
    assert _MEMORY_FIRST_PERSON_CUES == {
        "ich", "mir", "mich", "mein", "meine", "meinem", "meinen", "meiner", "meines",
        "wir", "uns", "unser", "unsere",
        "i", "i'm", "im", "me", "my", "we", "us",
    }
    assert _memory_learning_prefilter("ohne Chili schmeckt mir Essen nicht") is True
    assert _memory_learning_prefilter("ich koche am liebsten scharf") is True


def test_memory_learn_prompt_requires_one_bare_topic_value_with_mate_examples() -> None:
    required = (
        "single concrete core term or entity",
        "lowercase",
        "singular",
        "without any additions",
        "time, type, origin or intensity",
        "never an effect or abstraction",
        '"am morgen trinke ich am liebsten mate" -> value "mate"',
        '"ohne mate werde ich nicht wach" -> value "mate"',
        '"ich trinke den ganzen tag mate, klassisch wie in süd-amerika" -> value "mate"',
        "The predicate may preserve the nuance",
    )

    assert all(fragment in _MEMORY_LEARN_SYSTEM_PROMPT for fragment in required)


def test_memory_learn_prompt_keeps_topic_value_in_user_message_language() -> None:
    required = (
        "same language as the current user message",
        "must never be translated",
        'German "Auto" or "Autos" -> value "auto", never "car"',
    )

    assert all(fragment in _MEMORY_LEARN_SYSTEM_PROMPT for fragment in required)


def test_native_prompt_forbids_textual_memory_offers_for_ordinary_preferences(tmp_path: Path) -> None:
    forbidden = (
        "Möchtest du, dass ich mir das merke?",
        "Soll ich das speichern?",
        "Möchtest du, dass ich mir das explizit merke?",
        "Do you want me to remember that?",
        "Should I save that?",
    )
    prompts: list[str] = []

    async def run(message: str, turn_id: str):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps({
                    "claim_kind": None,
                    "subject": None,
                    "predicate": None,
                    "value": None,
                }))
            system = request["messages"][0]["content"]
            prompt = " ".join(str(block.get("text") or "") for block in system) if isinstance(system, list) else str(system)
            prompts.append(prompt)
            required = (
                "ARIA erkennt dauerhafte Praeferenzen automatisch",
                "separaten Aktions-Button",
                "ab der 2. Nennung",
                *forbidden,
                "einfach natürlich",
            )
            return _response(content=(
                "Das passt gut zu deiner Vorliebe für scharfes Essen."
                if all(fragment in prompt for fragment in required)
                else forbidden[0]
            ))

        return await run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=turn_id,
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_noop_binding(),),
            completion=completion,
            trace_root=tmp_path,
            memory_learning_enabled=True,
            observed_claim_store=ObservedClaimStore(tmp_path / f"{turn_id}.json"),
        )

    outcomes = asyncio.run(_run_prompt_pair(run))

    assert len(prompts) == 2
    for outcome in outcomes:
        assert outcome.kind == "final_answer"
        assert all(phrase not in outcome.message for phrase in forbidden)


def test_native_memory_response_rule_is_an_immutable_packaged_contract() -> None:
    contract_path = Path(memory_native_tools.__file__).resolve().parents[2] / "contracts" / "native_agent_memory_response_rule.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))

    system_prompt = payload["system_prompt"]
    assert system_prompt.strip()
    assert system_prompt.startswith("MEMORY RULE — PROMINENT AND MANDATORY")
    assert "Möchtest du, dass ich mir das merke?" in system_prompt
    required_exception = (
        "AUSNAHME — EXPLIZITE AUFFORDERUNG",
        "DIREKT bittet",
        "merken, zu speichern oder zu notieren",
        "'merk dir, dass ...'",
        "'speichere ...'",
        "'remember that ...'",
        "MUSST du memory_capture aufrufen",
        "gilt NUR für beiläufige Aussagen OHNE ausdrückliche Merk-Bitte",
    )
    assert all(fragment in system_prompt for fragment in required_exception)


async def _run_prompt_pair(run):  # noqa: ANN001, ANN202
    return (
        await run("Ich koche dauerhaft am liebsten scharf.", "prompt-cue"),
        await run("Ohne Chili schmeckt mir Essen nicht.", "prompt-no-cue"),
    )


def test_observed_claim_clear_user_uses_record_key_and_preserves_other_users(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "clear-observed.json", clock=lambda: 1000.0)
    store.record(" Alice  Smith ", DOWNBEAT_CLAIM, turn_id="a1", embedding=None, already_stored=False)
    store.record(" Alice  Smith ", CHILI_CLAIM, turn_id="a2", embedding=None, already_stored=False)
    store.record("bob", DOWNBEAT_CLAIM, turn_id="b1", embedding=None, already_stored=False)

    assert store.clear_user(" Alice  Smith ") == 2
    assert store.rows_for_user("Alice Smith") == ()
    assert len(store.rows_for_user("bob")) == 1
    assert store.clear_user("unknown") == 0
    assert store.clear_user(" Alice  Smith ") == 0


def test_two_preference_phrasings_reach_one_cluster_and_offer_on_second(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    pending = NativePendingStore(tmp_path / "chili-pending.sqlite3")
    store = ObservedClaimStore(tmp_path / "chili-observed.json", clock=lambda: 1000.0)
    extraction_messages: list[str] = []

    async def already_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
        return False

    async def run(message: str, turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                extraction_messages.append(message)
                return _response(content=json.dumps(CHILI_CLAIM))
            return _response(content="Verstanden.")

        return await run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=f"chili-{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_memory_capture_binding(owner),),
            completion=completion,
            trace_root=tmp_path,
            pending_store=pending,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=_Embedder(),
            personal_claim_semantic_checker=already_stored,
        )

    async def run_pair():
        first = await run("Ich koche am liebsten scharf", 1)
        second = await run("ohne Chili schmeckt mir Essen nicht", 2)
        return first, second

    first, second = asyncio.run(run_pair())

    assert extraction_messages == [
        "Ich koche am liebsten scharf",
        "ohne Chili schmeckt mir Essen nicht",
    ]
    assert first.memory_recurrence_count == 1
    assert first.memory_recurrence_offered is False
    assert first.suggestion_affordance is None
    assert second.memory_recurrence_count == 2
    assert second.memory_recurrence_offered is True
    assert second.suggestion_affordance
    assert len(store.rows_for_user("alice")) == 1


def test_three_mate_phrasings_share_topic_cluster_and_offer_on_second(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    pending = NativePendingStore(tmp_path / "mate-pending.sqlite3")
    store = ObservedClaimStore(tmp_path / "mate-observed.json", clock=lambda: 1000.0)
    messages = (
        "am morgen trinke ich am liebsten mate",
        "ohne mate werde ich nicht wach",
        "ich trinke den ganzen tag mate, klassisch wie in süd-amerika",
    )
    claims = iter((
        {"claim_kind": "preference", "subject": "user", "predicate": "morning_drink", "value": "mate"},
        {"claim_kind": "preference", "subject": "user", "predicate": "wakefulness_drink", "value": "mate"},
        {"claim_kind": "preference", "subject": "user", "predicate": "all_day_drink_style", "value": "mate"},
    ))

    async def already_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
        return False

    async def run(message: str, turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps(next(claims)))
            return _response(content="Verstanden.")

        return await run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=f"mate-{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_memory_capture_binding(owner),),
            completion=completion,
            trace_root=tmp_path,
            pending_store=pending,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=_ValueSensitiveEmbedder(),
            personal_claim_semantic_checker=already_stored,
        )

    async def run_all():
        return tuple([await run(message, index) for index, message in enumerate(messages, 1)])

    first, second, third = asyncio.run(run_all())

    assert len({recurrence_key({
        "claim_kind": "preference", "subject": "user", "predicate": predicate, "value": "mate",
    }) for predicate in ("morning_drink", "wakefulness_drink", "all_day_drink_style")}) == 1
    assert [first.memory_recurrence_count, second.memory_recurrence_count, third.memory_recurrence_count] == [1, 2, 3]
    assert first.suggestion_affordance is None
    assert second.memory_recurrence_offered is True
    assert second.suggestion_affordance and second.suggestion_affordance["kind"] == "memory"
    assert third.suggestion_affordance is None
    rows = store.rows_for_user("alice")
    assert len(rows) == 1
    assert rows[0].count == 3
    assert rows[0].sample_claim["value"] == "mate"


def test_value_embeddings_merge_two_phrasings_of_same_topic(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    pending = NativePendingStore(tmp_path / "green-tea-pending.sqlite3")
    store = ObservedClaimStore(tmp_path / "green-tea-observed.json", clock=lambda: 1000.0)
    embedder = _ValueSensitiveEmbedder()
    claims = iter((
        {
            "claim_kind": "preference",
            "subject": "user",
            "predicate": "preferred_tea",
            "value": "grüner tee",
        },
        {
            "claim_kind": "preference",
            "subject": "user",
            "predicate": "morning_tea_requirement",
            "value": "grüner tee am morgen",
        },
    ))

    async def already_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
        return False

    async def run(message: str, turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps(next(claims)))
            return _response(content="Verstanden.")

        return await run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=f"green-tea-{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_memory_capture_binding(owner),),
            completion=completion,
            trace_root=tmp_path,
            pending_store=pending,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=embedder,
            personal_claim_semantic_checker=already_stored,
        )

    async def run_pair():
        return (
            await run("Ich trinke am liebsten grünen Tee", 1),
            await run("Ohne grünen Tee läuft bei mir morgens nichts", 2),
        )

    first, second = asyncio.run(run_pair())

    assert embedder.texts == ["grüner tee", "grüner tee am morgen"]
    assert first.memory_recurrence_count == 1
    assert first.memory_recurrence_offered is False
    assert second.memory_recurrence_count == 2
    assert second.memory_recurrence_offered is True
    assert second.suggestion_affordance
    rows = store.rows_for_user("alice")
    assert len(rows) == 1
    assert rows[0].similarity >= 0.82
    assert rows[0].sample_claim["predicate"] == "morning_tea_requirement"


def test_recurrence_text_normalizes_only_value_and_allows_empty_skip() -> None:
    claim = {
        "subject": "user",
        "predicate": "preferred_tea",
        "value": "  Grüner\n TEE  ",
    }

    assert claim_recurrence_text(claim) == "grüner tee"
    assert claim_recurrence_text({**claim, "value": "  "}) == ""


def test_value_embeddings_keep_distinct_topics_separate(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "distinct-topics.json", clock=lambda: 1000.0)
    embedder = _ValueSensitiveEmbedder()
    claims = iter((
        {
            "claim_kind": "preference",
            "subject": "user",
            "predicate": "preferred_drink",
            "value": "mate",
        },
        {
            "claim_kind": "preference",
            "subject": "user",
            "predicate": "preferred_programming_language",
            "value": "python",
        },
    ))

    async def already_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
        return False

    async def run(message: str, turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps(next(claims)))
            return _response(content="Verstanden.")

        return await run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=f"distinct-topic-{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_noop_binding(),),
            completion=completion,
            trace_root=tmp_path,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=embedder,
            personal_claim_semantic_checker=already_stored,
        )

    async def run_pair():
        return (
            await run("Ich trinke am liebsten Mate", 1),
            await run("Ich programmiere am liebsten mit Python", 2),
        )

    first, second = asyncio.run(run_pair())

    assert embedder.texts == ["mate", "python"]
    assert first.memory_recurrence_count == 1
    assert second.memory_recurrence_count == 1
    assert first.memory_recurrence_offered is False
    assert second.memory_recurrence_offered is False
    rows = store.rows_for_user("alice")
    assert len(rows) == 2
    assert {row.count for row in rows} == {1}


def test_first_person_non_claim_uses_extraction_but_creates_no_record(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "null-observed.json", clock=lambda: 1000.0)
    extraction_calls = 0

    async def completion(**request):  # noqa: ANN003
        nonlocal extraction_calls
        if "response_format" in request:
            extraction_calls += 1
            return _response(content=json.dumps({
                "claim_kind": None,
                "subject": None,
                "predicate": None,
                "value": None,
            }))
        return _response(content="Das kann gut sein.")

    outcome = asyncio.run(run_native_agent_turn(
        message="ich glaube das stimmt nicht",
        user_id="alice",
        turn_id="null-claim",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_noop_binding(),),
        completion=completion,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=store,
    ))

    assert extraction_calls == 1
    assert outcome.memory_learn_pre_filter == "pass"
    assert outcome.memory_learn_claim is False
    assert outcome.memory_recurrence_count == 0
    assert outcome.suggestion_affordance is None
    assert store.rows_for_user("alice") == ()


def test_server_records_claim_when_native_loop_uses_no_tool(tmp_path: Path) -> None:
    store = ObservedClaimStore(tmp_path / "observed.json", clock=lambda: 1000.0)
    embedder = _Embedder()
    checked: list[tuple[str, tuple[float, ...], int]] = []

    async def already_stored(user_id: str, embedding, top_k: int):  # noqa: ANN001
        checked.append((user_id, tuple(embedding), top_k))
        return False

    async def completion(**request):  # noqa: ANN003
        if "response_format" in request:
            return _response(content=json.dumps(DOWNBEAT_CLAIM))
        return _response(content="Das klingt nach einer klaren Vorliebe.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Ich mag den Downbeat bei elektronischer Musik.",
        user_id="alice",
        turn_id="turn-1",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_noop_binding(),),
        completion=completion,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=store,
        embedding_client=embedder,
        personal_claim_semantic_checker=already_stored,
    ))

    assert outcome.kind == "final_answer"
    assert outcome.used_tool_names == ()
    assert outcome.memory_recurrence_count == 1
    assert outcome.memory_learn_pre_filter == "pass"
    assert outcome.memory_learn_claim is True
    assert len(store.rows_for_user("alice")) == 1
    assert checked == [("alice", (1.0, 0.0), 4)]
    assert len(embedder.calls) == 1


def test_prefilter_skips_non_candidates_without_extraction_call(tmp_path: Path) -> None:
    messages = (
        "",
        "ok",
        "Ja",
        "confirm action na123456",
        "Mag ich Downbeat?",
        "mach den Server aus",
        "Bitte prüfe den Serverstatus.",
        "Restart the service now.",
    )

    for index, message in enumerate(messages):
        extraction_calls = 0

        async def completion(**request):  # noqa: ANN003
            nonlocal extraction_calls
            if "response_format" in request:
                extraction_calls += 1
                return _response(content=json.dumps(DOWNBEAT_CLAIM))
            return _response(content="Okay.")

        outcome = asyncio.run(run_native_agent_turn(
            message=message,
            user_id="alice",
            turn_id=f"skip-{index}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_noop_binding(),),
            completion=completion,
            trace_root=tmp_path,
            memory_learning_enabled=True,
            observed_claim_store=ObservedClaimStore(tmp_path / f"skip-{index}.json"),
        ))

        assert extraction_calls == 0
        assert outcome.memory_learn_pre_filter == "skip"
        assert outcome.memory_learn_claim is False


def test_recurrence_key_ignores_predicate_and_offer_threshold_is_two(tmp_path: Path) -> None:
    variants = (
        {**DOWNBEAT_CLAIM, "predicate": "music_preference"},
        {**DOWNBEAT_CLAIM, "predicate": "preferred_rhythm"},
        {**DOWNBEAT_CLAIM, "predicate": "likes_musical_element"},
    )
    assert len({recurrence_key(claim) for claim in variants}) == 1
    assert MEMORY_RECURRENCE_THRESHOLD == 2

    store = ObservedClaimStore(tmp_path / "stable.json", clock=lambda: 1000.0)
    records = [
        store.record(
            "alice",
            claim,
            turn_id=f"turn-{index}",
            embedding=None,
            already_stored=False,
        )
        for index, claim in enumerate(variants, start=1)
    ]

    assert [record.count for record in records] == [1, 2, 3]
    assert [record.offer for record in records] == [False, True, False]
    assert len(store.rows_for_user("alice")) == 1


def test_second_server_observation_freezes_existing_memory_capture_offer(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    binding = _memory_capture_binding(owner)
    pending = NativePendingStore(tmp_path / "pending.sqlite3")
    store = ObservedClaimStore(tmp_path / "offers.json", clock=lambda: 1000.0)
    predicates = iter(("music_preference", "preferred_rhythm"))

    async def already_stored(_user_id: str, _embedding, _top_k: int) -> bool:  # noqa: ANN001
        return False

    async def run(turn: int):
        async def completion(**request):  # noqa: ANN003
            if "response_format" in request:
                return _response(content=json.dumps({**DOWNBEAT_CLAIM, "predicate": next(predicates)}))
            return _response(content="Verstanden.")

        return await run_native_agent_turn(
            message=(
                "Ich mag den Downbeat bei elektronischer Musik."
                if turn == 1
                else "Bei elektronischer Musik liebe ich den Downbeat."
            ),
            user_id="alice",
            turn_id=f"offer-{turn}",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(binding,),
            completion=completion,
            trace_root=tmp_path,
            pending_store=pending,
            memory_learning_enabled=True,
            observed_claim_store=store,
            embedding_client=_Embedder(),
            personal_claim_semantic_checker=already_stored,
        )

    first, second = asyncio.run(_run_pair(run))

    assert first.suggestion_affordance is None
    assert second.memory_recurrence_count == 2
    assert second.memory_recurrence_offered is True
    assert second.suggestion_affordance
    assert second.suggestion_affordance["kind"] == "memory"
    assert second.suggestion_affordance["label"] == "Als Erinnerung speichern"
    frozen = pending.consume(
        user_id="alice",
        token=second.suggestion_affordance["token"],
        now=1000,
    )
    assert frozen and frozen.tool_name == "memory_capture"
    assert frozen.frozen_arguments == {**DOWNBEAT_CLAIM, "predicate": "preferred_rhythm"}


async def _run_pair(run):  # noqa: ANN001, ANN202
    return await run(1), await run(2)


def test_learning_reuses_embedding_for_bounded_already_stored_check(tmp_path: Path) -> None:
    embedder = _Embedder(vector=(0.25, 0.75))
    calls: list[tuple[str, tuple[float, ...], int]] = []

    async def already_stored(user_id: str, embedding, top_k: int):  # noqa: ANN001
        calls.append((user_id, tuple(embedding), top_k))
        return True

    async def completion(**request):  # noqa: ANN003
        if "response_format" in request:
            return _response(content=json.dumps(DOWNBEAT_CLAIM))
        return _response(content="Verstanden.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Ich mag den Downbeat bei elektronischer Musik.",
        user_id="alice",
        turn_id="bounded",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_noop_binding(),),
        completion=completion,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=ObservedClaimStore(tmp_path / "bounded.json"),
        embedding_client=embedder,
        personal_claim_semantic_checker=already_stored,
    ))

    assert calls == [("alice", (0.25, 0.75), 4)]
    assert len(embedder.calls) == 1
    assert outcome.memory_recurrence_count == 1
    assert outcome.memory_recurrence_offered is False


def test_extraction_and_main_loop_start_concurrently(tmp_path: Path) -> None:
    extraction_started = asyncio.Event()
    loop_started = asyncio.Event()

    async def completion(**request):  # noqa: ANN003
        if "response_format" in request:
            extraction_started.set()
            await asyncio.wait_for(loop_started.wait(), timeout=0.5)
            return _response(content=json.dumps(DOWNBEAT_CLAIM))
        loop_started.set()
        await asyncio.wait_for(extraction_started.wait(), timeout=0.5)
        return _response(content="Verstanden.")

    async def run():
        return await asyncio.wait_for(run_native_agent_turn(
            message="Ich mag den Downbeat bei elektronischer Musik.",
            user_id="alice",
            turn_id="parallel",
            llm_config=LLMConfig(model="fake"),
            tool_bindings=(_noop_binding(),),
            completion=completion,
            trace_root=tmp_path,
            memory_learning_enabled=True,
            observed_claim_store=ObservedClaimStore(tmp_path / "parallel.json"),
            embedding_client=_Embedder(),
            personal_claim_semantic_checker=lambda *_args, **_kwargs: asyncio.sleep(0, result=False),
        ), timeout=1.0)

    outcome = asyncio.run(run())
    assert outcome.kind == "final_answer"
    assert outcome.memory_learn_claim is True


def test_extraction_uses_cached_strict_schema_and_configured_chat_model(tmp_path: Path) -> None:
    extraction_request: dict[str, object] = {}

    async def completion(**request):  # noqa: ANN003
        if "response_format" in request:
            extraction_request.update(request)
            return _response(content=json.dumps({
                "claim_kind": None,
                "subject": None,
                "predicate": None,
                "value": None,
            }))
        return _response(content="Verstanden.")

    outcome = asyncio.run(run_native_agent_turn(
        message="Ich mag den Downbeat bei elektronischer Musik.",
        user_id="alice",
        turn_id="cached-extraction",
        llm_config=LLMConfig(
            model="anthropic/claude-sonnet-test",
            api_base="http://proxy.invalid/v1",
            temperature=0.7,
        ),
        tool_bindings=(_noop_binding(),),
        completion=completion,
        trace_root=tmp_path,
        memory_learning_enabled=True,
        observed_claim_store=ObservedClaimStore(tmp_path / "cached.json"),
    ))

    system_content = extraction_request["messages"][0]["content"]
    assert extraction_request["model"] == "anthropic/claude-sonnet-test"
    assert extraction_request["api_base"] == "http://proxy.invalid/v1"
    assert extraction_request["temperature"] == 0.1
    assert extraction_request["response_format"]["json_schema"]["strict"] is True
    assert isinstance(system_content, list)
    assert system_content[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    assert outcome.memory_learn_pre_filter == "pass"
    assert outcome.memory_learn_claim is False


def test_candidate_tool_is_retired_and_explicit_capture_contract_remains(tmp_path: Path) -> None:
    owner = _owner(tmp_path)
    flags = {
        "native_agent_memory_enabled", "native_agent_connections_enabled", "native_agent_admin_enabled",
        "native_agent_admin_write_enabled", "native_agent_write_notes_enabled", "native_agent_write_memory_enabled",
        "native_agent_ssh_enabled", "native_agent_messaging_enabled", "native_agent_infra_write_enabled",
        "native_agent_recipe_execute_enabled", "native_agent_recipe_learn_enabled", "native_agent_memory_learn_enabled",
    }
    tools = assemble_native_tools(MODULE_MANIFESTS, runtime_owner=owner, enabled_rollout_flags=flags)
    contracts = {binding.contract.name: binding.contract for binding in tools}

    assert len(tools) == 37
    assert sum(contract.effect == "read_only" for contract in contracts.values()) == 24
    assert sum(contract.effect == "mutating" for contract in contracts.values()) == 13
    assert sum(contract.confirmation_required for contract in contracts.values()) == 13
    assert "memory_note_candidate" not in contracts

    pending = NativePendingStore(tmp_path / "explicit.sqlite3")
    extraction_calls = 0
    observed_system_prompts: list[str] = []

    async def completion(**request):  # noqa: ANN003
        nonlocal extraction_calls
        if "response_format" in request:
            extraction_calls += 1
            return _response(content=json.dumps(DOWNBEAT_CLAIM))
        system = request["messages"][0]["content"]
        if isinstance(system, list):
            observed_system_prompts.append(" ".join(str(block.get("text") or "") for block in system))
        else:
            observed_system_prompts.append(str(system or ""))
        return _response(tool_name="memory_capture", arguments=DOWNBEAT_CLAIM)

    outcome = asyncio.run(run_native_agent_turn(
        message="Merk dir, dass ich bei elektronischer Musik den Downbeat mag.",
        user_id="alice",
        turn_id="explicit",
        llm_config=LLMConfig(model="fake"),
        tool_bindings=(_memory_capture_binding(owner),),
        completion=completion,
        trace_root=tmp_path,
        pending_store=pending,
        memory_learning_enabled=True,
        observed_claim_store=ObservedClaimStore(tmp_path / "explicit.json"),
    ))

    assert extraction_calls == 0
    assert all("memory_note_candidate" not in prompt for prompt in observed_system_prompts)
    assert any(
        "AUSNAHME — EXPLIZITE AUFFORDERUNG" in prompt
        and "MUSST du memory_capture aufrufen" in prompt
        for prompt in observed_system_prompts
    )
    assert outcome.kind == "pending_confirmation"
    frozen = pending.consume(user_id="alice", token=outcome.confirmation_token, now=1000)
    assert frozen and frozen.tool_name == "memory_capture"
