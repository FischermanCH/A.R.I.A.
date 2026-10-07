from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import aria.modules.recipe_runtime.runtime as recipe_runtime_module
from aria.modules.recipe_runtime.status import render_recipe_turn
from aria.modules.recipe_runtime.contracts import RECIPE_MANIFEST_MISSING_ERROR
from aria.modules.configuration_foundations.config import RoutingLanguageConfig
from aria.modules.recipe_runtime.pipeline_helpers import PipelineRecipeHelpersMixin
from aria.modules.recipe_runtime.pipeline_helpers import expand_recipe_connection_bindings
from aria.modules.recipe_runtime.pipeline_helpers import expand_recipe_ssh_bindings
from aria.modules.recipe_runtime.runtime import RecipeRuntime, load_stored_recipe_runtime
from aria.modules.recipe_runtime.steps import RecipeStepExecutor
from aria.skills.base import SkillResult


class _RecipeExecutorOwner(PipelineRecipeHelpersMixin):
    def __init__(self) -> None:
        self.executed: list[tuple[dict, str, str]] = []

    async def _execute_custom_steps(self, row: dict, message: str, *, language: str = "de") -> SkillResult:
        self.executed.append((row, message, language))
        return SkillResult(skill_name="recipe_daily", content="done", success=True)


def test_recipe_executor_is_owned_by_recipe_runtime_helpers() -> None:
    assert "_find_runtime_recipe" in PipelineRecipeHelpersMixin.__dict__
    assert "_execute_recipe_by_id" in PipelineRecipeHelpersMixin.__dict__


def test_recipe_runtime_helper_executes_and_preserves_missing_contract() -> None:
    owner = _RecipeExecutorOwner()
    row = {"id": "daily", "steps": []}

    result = asyncio.run(owner._execute_recipe_by_id("daily", "run", runtime_recipes=[row], language="en"))
    missing = asyncio.run(owner._execute_recipe_by_id("missing", "run", runtime_recipes=[row], language="en"))

    assert result.success is True
    assert owner.executed == [(row, "run", "en")]
    assert missing.success is False
    assert missing.error == RECIPE_MANIFEST_MISSING_ERROR


def _ssh_bound_recipe(*, binding: str = "all", explicit_ref: str = "") -> dict:
    params = {"command": "uptime", "connection_kind": "ssh", "binding": binding}
    if explicit_ref:
        params["connection_ref"] = explicit_ref
    return {
        "id": "fleet", "name": "Fleet", "enabled": True,
        "steps": [{"id": "check", "type": "ssh_run", "params": params, "on_error": "stop"}],
    }


def _ssh_settings(*refs: str) -> SimpleNamespace:
    return SimpleNamespace(connections=SimpleNamespace(ssh={ref: object() for ref in refs}))


def _connection_bound_recipe(
    step_type: str,
    connection_kind: str,
    *,
    binding: str = "one",
    explicit_ref: str = "",
) -> dict:
    params = {"connection_kind": connection_kind, "binding": binding}
    if explicit_ref:
        params["connection_ref"] = explicit_ref
    return {
        "id": f"{connection_kind}-recipe",
        "name": f"{connection_kind} Recipe",
        "enabled": True,
        "steps": [{"id": "action", "type": step_type, "params": params, "on_error": "stop"}],
    }


def _connection_settings(**refs_by_kind: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(connections=SimpleNamespace(**{
        kind: {ref: object() for ref in refs}
        for kind, refs in refs_by_kind.items()
    }))


def test_recipe_ssh_binding_all_expands_to_concrete_steps() -> None:
    expanded = expand_recipe_ssh_bindings(
        _ssh_bound_recipe(), settings=_ssh_settings("srv-dev02", "backup-01", "db-01"),
    )

    assert expanded.error == ""
    assert expanded.targets == ("srv-dev02", "backup-01", "db-01")
    assert [step["params"]["connection_ref"] for step in expanded.recipe["steps"]] == [
        "srv-dev02", "backup-01", "db-01",
    ]
    assert expanded.recipe["steps"][0] == {
        "id": "check-1",
        "type": "ssh_run",
        "params": {
            "command": "uptime", "connection_kind": "ssh", "binding": "all",
            "connection_ref": "srv-dev02",
        },
        "on_error": "stop",
        "_aria_recipe_step_index": 1,
        "_aria_recipe_step_total": 1,
        "_aria_ssh_fanout_group": "1:check",
        "_aria_ssh_fanout_index": 1,
        "_aria_ssh_fanout_total": 3,
    }


def test_recipe_ssh_binding_one_requires_exactly_one_profile() -> None:
    resolved = expand_recipe_ssh_bindings(
        _ssh_bound_recipe(binding="one"), settings=_ssh_settings("only-ssh"),
    )
    ambiguous = expand_recipe_ssh_bindings(
        _ssh_bound_recipe(binding="one"), settings=_ssh_settings("ssh-a", "ssh-b"),
    )

    assert resolved.error == ""
    assert resolved.targets == ("only-ssh",)
    assert resolved.recipe["steps"][0]["params"]["connection_ref"] == "only-ssh"
    assert ambiguous.error == "recipe_connection_ambiguous"


def test_recipe_ssh_binding_all_enforces_target_cap() -> None:
    refs = tuple(f"ssh-{index}" for index in range(21))
    expanded = expand_recipe_ssh_bindings(_ssh_bound_recipe(), settings=_ssh_settings(*refs))

    assert expanded.error == "recipe_connection_target_cap_exceeded"


def test_recipe_ssh_binding_zero_profiles_stops_before_executor() -> None:
    calls: list[dict] = []

    class Owner(PipelineRecipeHelpersMixin):
        settings = _ssh_settings()

        async def _execute_custom_steps(self, row, message, *, language="de"):
            calls.append(row)
            return SkillResult(skill_name="recipe_fleet", content="unexpected", success=True)

    result = asyncio.run(Owner()._execute_recipe_by_id(
        "fleet", "", runtime_recipes=[_ssh_bound_recipe()], language="en",
    ))

    assert result.success is False
    assert result.error == "recipe_connection_no_connection_configured"
    assert calls == []


def test_recipe_explicit_ssh_ref_keeps_precedence_unchanged() -> None:
    recipe = _ssh_bound_recipe(binding="all", explicit_ref="fixed-ssh")
    expanded = expand_recipe_ssh_bindings(recipe, settings=_ssh_settings("other-a", "other-b"))

    assert expanded.error == ""
    assert expanded.targets == ("fixed-ssh",)
    assert expanded.recipe["steps"] == recipe["steps"]


@pytest.mark.parametrize(
    ("step_type", "connection_kind"),
    (("sftp_read", "sftp"), ("smb_write", "smb")),
)
@pytest.mark.parametrize("binding", ("one", "all"))
def test_recipe_file_connection_bindings_resolve_and_fan_out(
    step_type: str, connection_kind: str, binding: str,
) -> None:
    refs = (f"{connection_kind}-a",) if binding == "one" else (f"{connection_kind}-a", f"{connection_kind}-b")
    expanded = expand_recipe_connection_bindings(
        _connection_bound_recipe(step_type, connection_kind, binding=binding),
        settings=_connection_settings(**{connection_kind: refs}),
    )

    assert expanded.error == ""
    assert expanded.targets == refs
    assert [step["params"]["connection_ref"] for step in expanded.recipe["steps"]] == list(refs)


def test_recipe_discord_one_resolves_but_multi_binding_is_rejected() -> None:
    resolved = expand_recipe_connection_bindings(
        _connection_bound_recipe("discord_send", "discord", binding="one"),
        settings=_connection_settings(discord=("alerts",)),
    )
    forbidden = expand_recipe_connection_bindings(
        _connection_bound_recipe("discord_send", "discord", binding="all"),
        settings=_connection_settings(discord=("alerts", "ops")),
    )

    assert resolved.error == ""
    assert resolved.targets == ("alerts",)
    assert resolved.recipe["steps"][0]["params"]["connection_ref"] == "alerts"
    assert forbidden.error == "recipe_connection_binding_not_allowed_for_kind"


def test_recipe_explicit_non_ssh_ref_passes_through_unchanged() -> None:
    recipe = _connection_bound_recipe(
        "discord_send", "discord", binding="all", explicit_ref="fixed-alerts",
    )
    expanded = expand_recipe_connection_bindings(
        recipe, settings=_connection_settings(discord=("other-a", "other-b")),
    )

    assert expanded.error == ""
    assert expanded.targets == ("fixed-alerts",)
    assert expanded.recipe["steps"] == recipe["steps"]


def test_recipe_connection_binding_errors_are_bounded_and_kind_owned() -> None:
    no_connection = expand_recipe_connection_bindings(
        _connection_bound_recipe("sftp_read", "sftp"), settings=_connection_settings(sftp=()),
    )
    ambiguous = expand_recipe_connection_bindings(
        _connection_bound_recipe("sftp_read", "sftp"),
        settings=_connection_settings(sftp=("a", "b")),
    )
    over_cap = expand_recipe_connection_bindings(
        _connection_bound_recipe("smb_read", "smb", binding="all"),
        settings=_connection_settings(smb=tuple(f"smb-{index}" for index in range(21))),
    )
    mismatch = expand_recipe_connection_bindings(
        _connection_bound_recipe("sftp_read", "ssh"), settings=_connection_settings(ssh=("host",)),
    )
    invalid = expand_recipe_connection_bindings(
        _connection_bound_recipe("sftp_read", "sftp", binding="random"),
        settings=_connection_settings(sftp=("files",)),
    )
    each_for_discord = expand_recipe_connection_bindings(
        _connection_bound_recipe("discord_send", "discord", binding="each"),
        settings=_connection_settings(discord=("alerts",)),
    )

    assert no_connection.error == "recipe_connection_no_connection_configured"
    assert ambiguous.error == "recipe_connection_ambiguous"
    assert over_cap.error == "recipe_connection_target_cap_exceeded"
    assert mismatch.error == "recipe_connection_kind_mismatch"
    assert invalid.error == "recipe_connection_binding_invalid"
    assert each_for_discord.error == "recipe_connection_binding_not_allowed_for_kind"


@pytest.mark.parametrize("step_type", ("rss_read", "llm_transform", "chat_send"))
def test_recipe_non_adaptive_step_types_pass_through_unchanged(step_type: str) -> None:
    recipe = _connection_bound_recipe(step_type, "ssh", binding="all")
    expanded = expand_recipe_connection_bindings(recipe, settings=_ssh_settings("a", "b"))

    assert expanded.error == ""
    assert expanded.targets == ()
    assert expanded.recipe["steps"] == recipe["steps"]


@pytest.mark.parametrize(
    ("step_type", "connection_kind"),
    (
        ("webhook_send", "webhook"),
        ("email_send", "email"),
        ("mqtt_publish", "mqtt"),
        ("http_api_request", "http_api"),
    ),
)
def test_recipe_supported_single_target_connection_kinds_resolve(
    step_type: str, connection_kind: str,
) -> None:
    expanded = expand_recipe_connection_bindings(
        _connection_bound_recipe(step_type, connection_kind),
        settings=_connection_settings(**{connection_kind: ("primary",)}),
    )

    assert expanded.error == ""
    assert expanded.targets == ("primary",)
    assert expanded.recipe["steps"][0]["params"]["connection_ref"] == "primary"


def test_recipe_connection_binding_error_i18n_exists_in_both_languages() -> None:
    root = Path(__file__).resolve().parents[1]
    payloads = [
        json.loads((root / "aria" / "i18n" / language).read_text(encoding="utf-8"))
        for language in ("de.json", "en.json")
    ]
    for code in (
        "recipe_connection_no_connection_configured",
        "recipe_connection_ambiguous",
        "recipe_connection_target_cap_exceeded",
        "recipe_connection_binding_not_allowed_for_kind",
        "recipe_connection_binding_invalid",
        "recipe_connection_kind_mismatch",
    ):
        assert all(payload.get(f"recipe_runtime.{code}") for payload in payloads)


def test_recipe_expanded_ssh_steps_preserve_executor_guardrail_failure() -> None:
    seen_refs: list[str] = []

    class Owner(PipelineRecipeHelpersMixin):
        settings = _ssh_settings("allowed-host", "blocked-host")

        async def _execute_custom_steps(self, row, message, *, language="de"):
            seen_refs.extend(step["params"]["connection_ref"] for step in row["steps"])
            return SkillResult(
                skill_name="recipe_fleet", content="", success=False,
                error="recipe_ssh_policy_blocked",
            )

    result = asyncio.run(Owner()._execute_recipe_by_id(
        "fleet", "", runtime_recipes=[_ssh_bound_recipe()], language="en",
    ))

    assert seen_refs == ["allowed-host", "blocked-host"]
    assert result.success is False
    assert result.error == "recipe_ssh_policy_blocked"


def test_recipe_ssh_run_reaches_execution_summary_without_removed_safe_fix_state() -> None:
    class Runtime:
        settings = SimpleNamespace(llm=SimpleNamespace(model="unused"))

        @staticmethod
        def normalize_spaces(value: str) -> str:
            return " ".join(str(value).split())

        @staticmethod
        def truncate_text(value: str, limit: int) -> str:
            return str(value)[:limit]

        async def execute_custom_ssh_command(self, **kwargs) -> SkillResult:
            assert kwargs["connection_ref"] == "srv-dev02"
            return SkillResult(
                skill_name="ssh",
                content="up 12 days",
                success=True,
                metadata={
                    "custom_connection_ref": "srv-dev02",
                    "custom_connection_target": "10.0.0.12",
                    "custom_exit_code": 0,
                    "custom_duration_seconds": 0.25,
                    "custom_held_packages": [],
                    "custom_warning_hints": [],
                },
            )

    result = asyncio.run(RecipeStepExecutor(Runtime()).execute(
        {
            "id": "adaptive-uptime",
            "name": "Adaptive uptime",
            "steps": [{
                "id": "uptime-srv-dev02",
                "type": "ssh_run",
                "params": {"connection_ref": "srv-dev02", "command": "uptime"},
            }],
        },
        message="Check uptime",
        language="en",
    ))

    assert result.success is True
    assert "up 12 days" in result.content
    assert result.metadata["custom_ssh_run_summary"]
    assert result.metadata["custom_held_summary"] == ""


def test_recipe_expanded_ssh_fanout_aggregates_all_hosts_for_following_step() -> None:
    prompts: list[str] = []

    class LLM:
        async def chat(self, messages, **_kwargs):  # noqa: ANN001
            prompts.append(messages[-1]["content"])
            return SimpleNamespace(content="Combined fleet summary", usage={})

    class Runtime:
        settings = SimpleNamespace(llm=SimpleNamespace(model="fake"))
        llm_client = LLM()

        @staticmethod
        def normalize_spaces(value: str) -> str:
            return " ".join(str(value).split())

        @staticmethod
        def truncate_text(value: str, limit: int) -> str:
            return str(value)[:limit]

        async def execute_custom_ssh_command(self, **kwargs) -> SkillResult:
            ref = kwargs["connection_ref"]
            return SkillResult(
                skill_name="ssh", content=f"output from {ref}", success=True,
                metadata={"custom_connection_ref": ref},
            )

    expanded = expand_recipe_ssh_bindings(
        {
            **_ssh_bound_recipe(),
            "steps": [
                _ssh_bound_recipe()["steps"][0],
                {"id": "summary", "type": "llm_transform", "params": {"prompt": "Summarize:\n{prev_output}"}},
                {"id": "chat", "type": "chat_send", "params": {"chat_message": "{prev_output}"}},
            ],
        },
        settings=_ssh_settings("srv-a", "srv-b"),
    )
    result = asyncio.run(RecipeStepExecutor(Runtime()).execute(
        expanded.recipe, message="Check fleet", language="en",
    ))

    assert result.success is True
    assert "### srv-a\noutput from srv-a" in prompts[0]
    assert "### srv-b\noutput from srv-b" in prompts[0]
    assert result.metadata["direct_chat_text"] == "Combined fleet summary"
    assert result.metadata["custom_ssh_run_summary"]


def test_recipe_single_ssh_step_keeps_plain_prev_output_unchanged() -> None:
    prompts: list[str] = []

    class LLM:
        async def chat(self, messages, **_kwargs):  # noqa: ANN001
            prompts.append(messages[-1]["content"])
            return SimpleNamespace(content="Single summary", usage={})

    class Runtime:
        settings = SimpleNamespace(llm=SimpleNamespace(model="fake"))
        llm_client = LLM()

        @staticmethod
        def normalize_spaces(value: str) -> str:
            return " ".join(str(value).split())

        @staticmethod
        def truncate_text(value: str, limit: int) -> str:
            return str(value)[:limit]

        async def execute_custom_ssh_command(self, **_kwargs) -> SkillResult:
            return SkillResult(skill_name="ssh", content="single host output", success=True)

    result = asyncio.run(RecipeStepExecutor(Runtime()).execute(
        {
            "id": "fixed", "name": "Fixed",
            "steps": [
                {"id": "ssh", "type": "ssh_run", "params": {"connection_ref": "srv-a", "command": "uptime"}},
                {"id": "summary", "type": "llm_transform", "params": {"prompt": "Summarize: {prev_output}"}},
            ],
        },
        message="Check host", language="en",
    ))

    assert result.success is True
    assert prompts == ["Summarize: single host output"]


class _MemorySkill:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, query: str, params: dict) -> SkillResult:
        self.calls.append({"query": query, "params": dict(params)})
        return SkillResult(skill_name="memory_recall", success=True, content="")


def test_load_stored_recipe_runtime_parses_valid_local_manifest(tmp_path) -> None:
    recipes_dir = tmp_path / "recipes"
    config_path = tmp_path / "config.json"
    recipes_dir.mkdir()
    config_path.write_text("{}", encoding="utf-8")
    (recipes_dir / "daily-status.json").write_text(
        json.dumps(
            {
                "id": "daily-status",
                "name": "Daily Status",
                "connections": ["ssh/main"],
                "steps": [
                    {
                        "id": "s1",
                        "type": "chat_send",
                        "params": {"chat_message": "ready"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rows, cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache={},
    )

    assert [row["id"] for row in rows] == ["daily-status"]
    assert rows[0]["steps"][0]["type"] == "chat_send"
    assert cache["rows"] == rows


def _write_recipe_manifest(directory, recipe_id: str, *, name: str | None = None, step_type: str = "chat_send") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    params = {"chat_message": f"{recipe_id} ready"}
    if step_type == "ssh_run":
        params = {"connection_ref": "pihole1", "command": "uptime"}
    (directory / f"{recipe_id}.json").write_text(
        json.dumps(
            {
                "id": recipe_id,
                "name": name or recipe_id.replace("-", " ").title(),
                "description": f"{recipe_id} description",
                "connections": ["chat"] if step_type == "chat_send" else ["ssh"],
                "steps": [{"id": "s1", "type": step_type, "params": params}],
                "enabled_default": True,
            }
        ),
        encoding="utf-8",
    )


def test_load_stored_recipe_runtime_matches_ui_legacy_catalog_authority(tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    legacy_dir = tmp_path / "data" / "skills"
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    _write_recipe_manifest(recipes_dir, "ssh_run_command", name="SSH Agentic Command", step_type="ssh_run")
    for recipe_id in (
        "discord-broadcast-template",
        "linux-fleet-healthcheck-to-discord-template",
        "linux-updates-check-template",
        "smb-share-list-template",
    ):
        _write_recipe_manifest(legacy_dir, recipe_id)

    rows, _cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache={},
    )

    assert [row["id"] for row in rows] == [
        "ssh_run_command",
        "discord-broadcast-template",
        "linux-fleet-healthcheck-to-discord-template",
        "linux-updates-check-template",
        "smb-share-list-template",
    ]


def test_load_stored_recipe_runtime_prefers_canonical_manifest_over_legacy_duplicate(tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    legacy_dir = tmp_path / "data" / "skills"
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    _write_recipe_manifest(recipes_dir, "shared-recipe", name="Canonical Shared Recipe")
    _write_recipe_manifest(legacy_dir, "shared-recipe", name="Legacy Shared Recipe")

    rows, _cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache={},
    )

    assert [row["id"] for row in rows] == ["shared-recipe"]
    assert rows[0]["name"] == "Canonical Shared Recipe"


def test_load_stored_recipe_runtime_applies_legacy_toggle_and_invalidates_cache(tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    legacy_dir = tmp_path / "data" / "skills"
    config_path = tmp_path / "config.yaml"
    _write_recipe_manifest(legacy_dir, "legacy-template", name="Legacy Template")
    config_path.write_text(
        json.dumps({"skills": {"custom": {"legacy-template": {"enabled": True}}}}),
        encoding="utf-8",
    )

    rows_enabled, cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache={},
    )
    config_path.write_text(
        json.dumps({"skills": {"custom": {"legacy-template": {"enabled": False}}}}),
        encoding="utf-8",
    )
    rows_disabled, _cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache=cache,
    )

    assert [row["id"] for row in rows_enabled if row["enabled"]] == ["legacy-template"]
    assert rows_disabled == [
        {
            "id": "legacy-template",
            "name": "Legacy Template",
            "connections": ["chat"],
            "description": "legacy-template description",
            "steps": [
                {
                    "id": "s1",
                    "name": "",
                    "type": "chat_send",
                    "params": {"chat_message": "legacy-template ready"},
                    "on_error": "stop",
                }
            ],
            "enabled": False,
        }
    ]


def test_render_recipe_turn_excludes_disabled_legacy_rows(tmp_path) -> None:
    recipes_dir = tmp_path / "data" / "recipes"
    legacy_dir = tmp_path / "data" / "skills"
    config_path = tmp_path / "config.yaml"
    _write_recipe_manifest(recipes_dir, "active-recipe", name="Active Recipe")
    _write_recipe_manifest(legacy_dir, "disabled-legacy-template", name="Disabled Legacy Template")
    config_path.write_text(
        json.dumps({"skills": {"custom": {"disabled-legacy-template": {"enabled": False}}}}),
        encoding="utf-8",
    )

    rows, _cache = load_stored_recipe_runtime(
        skills_dir=recipes_dir,
        config_path=config_path,
        cache={},
    )
    text = render_recipe_turn("inventory", "", rows, language="de")
    missing_text = render_recipe_turn("explain", "disabled-legacy-template", rows, language="de")

    assert {row["id"]: row["enabled"] for row in rows} == {
        "active-recipe": True,
        "disabled-legacy-template": False,
    }
    assert "Active Recipe" in text
    assert "Disabled Legacy Template" not in text
    assert "aktivierte gespeicherte rezept wurde nicht gefunden" in missing_text.casefold()


def _runtime(memory_skill: _MemorySkill) -> RecipeRuntime:
    settings = SimpleNamespace(
        memory=SimpleNamespace(top_k=5),
        auto_memory=SimpleNamespace(
            session_recall_top_k=2,
            user_recall_top_k=2,
            max_facts_per_message=3,
            agentic_extraction_enabled=False,
        ),
    )
    return RecipeRuntime(
        settings=settings,
        llm_client=None,
        memory_skill_getter=lambda: memory_skill,
        execute_custom_ssh_command=lambda *args, **kwargs: None,
        extract_memory_store_text=lambda *args, **kwargs: "",
        extract_memory_recall_query=lambda message, *_args, **_kwargs: str(message),
        facts_collection_for_user=lambda user_id: f"aria_facts_{user_id}",
        preferences_collection_for_user=lambda user_id: f"aria_preferences_{user_id}",
        normalize_spaces=lambda text: text,
        truncate_text=lambda text, _limit: text,
    )


def test_run_skills_passes_docs_only_to_memory_recall() -> None:
    memory_skill = _MemorySkill()
    runtime = _runtime(memory_skill)

    results = asyncio.run(
        runtime.run_skills(
            intents=["memory_recall"],
            message="was steht in meinen dokumenten zur UI-Regel?",
            user_id="fischerman",
            routing_profile=RoutingLanguageConfig(),
            query_overrides={"memory_recall": "UI-Regel"},
            context_overrides={
                "memory_recall_enabled": True,
                "include_documents": True,
                "docs_only": True,
                "memory_top_k": 2,
            },
        )
    )

    assert [result.skill_name for result in results] == ["memory_recall"]
    assert memory_skill.calls == [
        {
            "query": "UI-Regel",
            "params": {
                "action": "recall",
                "top_k": 2,
                "user_id": "fischerman",
                "collection": "aria_facts_fischerman",
                "target_collections": [],
                "include_documents": True,
                "docs_only": True,
            },
        }
    ]


def test_run_skills_preserves_exact_document_scope_for_answer_recall() -> None:
    memory_skill = _MemorySkill()
    runtime = _runtime(memory_skill)

    asyncio.run(
        runtime.run_skills(
            intents=["memory_recall"],
            message="Was weißt du über Simpoini?",
            user_id="fischerman",
            routing_profile=RoutingLanguageConfig(),
            query_overrides={"memory_recall": "Simpoini"},
            context_overrides={
                "memory_recall_enabled": True,
                "include_documents": True,
                "docs_only": True,
                "document_ids": ["med-a"],
                "document_names": ["Simpoini50mg.pdf"],
                "document_target_collections": ["aria_docs_whity_medikamente"],
                "memory_top_k": 5,
            },
        )
    )

    assert memory_skill.calls[-1] == {
        "query": "Simpoini",
        "params": {
            "action": "recall",
            "top_k": 5,
            "user_id": "fischerman",
            "collection": "aria_facts_fischerman",
            "target_collections": [],
            "include_documents": True,
            "docs_only": True,
            "document_ids": ["med-a"],
            "document_names": ["Simpoini50mg.pdf"],
            "document_target_collections": ["aria_docs_whity_medikamente"],
        },
    }


def test_run_skills_invokes_memory_once_for_document_inventory_contract() -> None:
    memory_skill = _MemorySkill()
    runtime = _runtime(memory_skill)

    results = asyncio.run(
        runtime.run_skills(
            intents=["memory_recall"],
            message="Welche Dokumente sind gespeichert?",
            user_id="fischerman",
            routing_profile=RoutingLanguageConfig(),
            query_overrides={"memory_recall": "gespeicherte Dokumente"},
            context_overrides={
                "memory_recall_enabled": True,
                "include_documents": True,
                "docs_only": True,
                "document_inventory": True,
                "document_ids": [],
                "document_names": [],
                "document_target_collections": [],
                "memory_top_k": 12,
            },
        )
    )

    assert [result.skill_name for result in results] == ["memory_recall"]
    assert len(memory_skill.calls) == 1
    assert memory_skill.calls[0]["params"] == {
        "action": "recall",
        "top_k": 12,
        "user_id": "fischerman",
        "collection": "aria_facts_fischerman",
        "target_collections": [],
        "include_documents": True,
        "docs_only": True,
        "document_inventory": True,
        "document_ids": [],
        "document_names": [],
        "document_target_collections": [],
    }


def test_explicit_claim_review_continues_without_legacy_candidate_write(monkeypatch) -> None:
    memory_skill = _MemorySkill()
    runtime = _runtime(memory_skill)
    claim = {
        "claim_kind": "preference",
        "subject": "user",
        "predicate": "drink_preference",
        "value": "mate",
    }

    async def consolidate(*_args, **_kwargs):
        return {"ok": True, "claims": [claim], "input_count": 1, "usage": {}}

    async def store_claim(**_kwargs):
        return {
            "stored": False,
            "claim": claim,
            "reason": "claim_requires_review",
            "activation_blockers": ["explicit_user_authority_required"],
            "relation": {"source": "exact"},
            "timings": {},
        }

    monkeypatch.setattr(recipe_runtime_module, "consolidate_personal_claim_batch", consolidate)
    monkeypatch.setattr(recipe_runtime_module, "store_personal_claim", store_claim)

    result = asyncio.run(
        runtime._store_explicit_personal_memory(
            claims=[claim],
            user_id="alice",
            memory_skill=memory_skill,
            facts_collection="aria_facts_alice",
            preferences_collection="aria_preferences_alice",
            language="en",
        )
    )

    assert result.success is True
    assert result.metadata["review_required"] is True
    assert result.metadata["personal_claim_results"][0]["claim"] == claim
    assert memory_skill.calls == []
