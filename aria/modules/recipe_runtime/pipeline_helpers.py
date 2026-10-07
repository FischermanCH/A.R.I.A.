from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aria.modules.platform_primitives.i18n import I18NStore
from aria.modules.platform_primitives.recipe_progress import RECIPE_PROGRESS_STORE
from aria.modules.recipe_runtime.contracts import RECIPE_MANIFEST_MISSING_ERROR
from aria.modules.recipe_runtime.contracts import build_recipe_runtime_skill_name
from aria.modules.recipe_runtime.status import build_recipe_status_text
from aria.modules.recipe_runtime.runtime import load_recipe_toggles
from aria.modules.recipe_runtime.runtime import load_stored_recipe_runtime
from aria.modules.recipe_runtime.runtime import normalize_recipe_steps
from aria.modules.recipe_runtime.steps import render_step_template
from aria.modules.recipe_runtime.runtime import sanitize_recipe_id
from aria.modules.recipe_runtime.runtime import should_skip_recipe_auto_memory_persist
from aria.modules.skill_contracts.contracts import SkillResult


_PIPELINE_RECIPE_HELPERS_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")
MAX_SSH_TARGETS = 20
_STEP_CONNECTION_KINDS = {
    "ssh_run": "ssh",
    "sftp_read": "sftp",
    "sftp_write": "sftp",
    "sftp_list": "sftp",
    "smb_read": "smb",
    "smb_write": "smb",
    "smb_list": "smb",
    "discord_send": "discord",
    "webhook_send": "webhook",
    "email_send": "email",
    "mqtt_publish": "mqtt",
    "http_api_request": "http_api",
}
_MULTI_TARGET_CONNECTION_KINDS = frozenset({"ssh", "sftp", "smb"})


@dataclass(frozen=True, slots=True)
class RecipeConnectionBindingExpansion:
    recipe: dict[str, Any]
    targets: tuple[str, ...] = ()
    error: str = ""


RecipeSSHBindingExpansion = RecipeConnectionBindingExpansion


def expand_recipe_connection_bindings(
    recipe: Mapping[str, Any], *, settings: Any,
) -> RecipeConnectionBindingExpansion:
    raw_steps = recipe.get("steps", ())
    if not isinstance(raw_steps, list):
        return RecipeConnectionBindingExpansion(dict(recipe))
    expanded_steps: list[Any] = []
    resolved_targets: list[str] = []
    for source_index, raw_step in enumerate(raw_steps, start=1):
        step_type = str(raw_step.get("type") or "").strip().lower() if isinstance(raw_step, Mapping) else ""
        expected_kind = _STEP_CONNECTION_KINDS.get(step_type, "")
        if not isinstance(raw_step, Mapping) or not expected_kind:
            expanded_steps.append(dict(raw_step) if isinstance(raw_step, Mapping) else raw_step)
            continue
        params = raw_step.get("params", {})
        params = dict(params) if isinstance(params, Mapping) else {}
        explicit_ref = str(params.get("connection_ref") or "").strip()
        if explicit_ref:
            expanded_steps.append(dict(raw_step))
            resolved_targets.append(explicit_ref)
            continue
        connection_kind = str(params.get("connection_kind") or "").strip().lower()
        if not connection_kind:
            expanded_steps.append(dict(raw_step))
            continue
        if connection_kind != expected_kind:
            return RecipeConnectionBindingExpansion(dict(recipe), error="recipe_connection_kind_mismatch")
        binding = str(params.get("binding") or "").strip().lower()
        if binding not in {"one", "all", "each"}:
            return RecipeConnectionBindingExpansion(dict(recipe), error="recipe_connection_binding_invalid")
        if binding in {"all", "each"} and expected_kind not in _MULTI_TARGET_CONNECTION_KINDS:
            return RecipeConnectionBindingExpansion(
                dict(recipe), error="recipe_connection_binding_not_allowed_for_kind",
            )
        profiles = getattr(getattr(settings, "connections", None), expected_kind, None)
        configured_refs = (
            tuple(str(ref).strip() for ref in profiles if str(ref).strip())
            if isinstance(profiles, Mapping)
            else ()
        )
        if binding == "one":
            if not configured_refs:
                return RecipeConnectionBindingExpansion(
                    dict(recipe), error="recipe_connection_no_connection_configured",
                )
            if len(configured_refs) != 1:
                return RecipeConnectionBindingExpansion(dict(recipe), error="recipe_connection_ambiguous")
            step_refs = configured_refs
        else:
            if not configured_refs:
                return RecipeConnectionBindingExpansion(
                    dict(recipe), error="recipe_connection_no_connection_configured",
                )
            if len(configured_refs) > MAX_SSH_TARGETS:
                return RecipeConnectionBindingExpansion(
                    dict(recipe), error="recipe_connection_target_cap_exceeded",
                )
            step_refs = configured_refs
        for index, connection_ref in enumerate(step_refs, start=1):
            concrete_params = dict(params)
            concrete_params["connection_ref"] = connection_ref
            concrete_step = dict(raw_step)
            concrete_step["params"] = concrete_params
            concrete_step["_aria_recipe_step_index"] = source_index
            concrete_step["_aria_recipe_step_total"] = len(raw_steps)
            if len(step_refs) > 1:
                source_step_id = str(raw_step.get("id") or expected_kind).strip()
                concrete_step["id"] = f"{source_step_id}-{index}"
                if expected_kind == "ssh":
                    concrete_step["_aria_ssh_fanout_group"] = f"{source_index}:{source_step_id}"
                    concrete_step["_aria_ssh_fanout_index"] = index
                    concrete_step["_aria_ssh_fanout_total"] = len(step_refs)
            expanded_steps.append(concrete_step)
            resolved_targets.append(connection_ref)
    expanded_recipe = dict(recipe)
    expanded_recipe["steps"] = expanded_steps
    return RecipeConnectionBindingExpansion(
        expanded_recipe, tuple(dict.fromkeys(resolved_targets)), "",
    )


def expand_recipe_ssh_bindings(
    recipe: Mapping[str, Any], *, settings: Any,
) -> RecipeConnectionBindingExpansion:
    """Backward-compatible alias for generalized adaptive connection bindings."""
    return expand_recipe_connection_bindings(recipe, settings=settings)


def _pipeline_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _PIPELINE_RECIPE_HELPERS_I18N.t(language or "de", f"pipeline.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


class PipelineRecipeHelpersMixin:
    @staticmethod
    def _find_runtime_recipe(runtime_recipes: list[dict[str, Any]], recipe_id: str) -> dict[str, Any] | None:
        clean_recipe_id = str(recipe_id or "").strip()
        if not clean_recipe_id:
            return None
        for row in runtime_recipes:
            if str(row.get("id", "") or "").strip() == clean_recipe_id:
                return row
        return None

    async def _execute_recipe_by_id(
        self,
        recipe_id: str,
        message: str,
        *,
        runtime_recipes: list[dict[str, Any]],
        language: str = "de",
        user_id: str = "",
    ) -> SkillResult:
        row = self._find_runtime_recipe(runtime_recipes, recipe_id)
        if row is None:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(recipe_id or "unknown"),
                content="",
                success=False,
                error=RECIPE_MANIFEST_MISSING_ERROR,
            )
        expansion = expand_recipe_connection_bindings(row, settings=getattr(self, "settings", None))
        if expansion.error:
            return SkillResult(
                skill_name=build_recipe_runtime_skill_name(recipe_id or "unknown"),
                content="",
                success=False,
                error=expansion.error,
            )
        try:
            if user_id:
                return await self._execute_custom_steps(
                    expansion.recipe, message, language=language, user_id=user_id,
                )
            return await self._execute_custom_steps(expansion.recipe, message, language=language)
        finally:
            if user_id:
                RECIPE_PROGRESS_STORE.clear(user_id)

    @staticmethod
    def _sanitize_skill_id(value: str) -> str:
        return sanitize_recipe_id(value)

    @staticmethod
    def _normalize_skill_steps(value: Any) -> list[dict[str, Any]]:
        return normalize_recipe_steps(value)

    @staticmethod
    def _render_step_template(template: str, values: dict[str, str]) -> str:
        return render_step_template(template, values)

    def _load_recipe_toggles(self) -> dict[str, bool]:
        return load_recipe_toggles(self._config_path)

    def _load_stored_recipe_runtime(self) -> list[dict[str, Any]]:
        rows, cache = load_stored_recipe_runtime(
            skills_dir=self._stored_recipes_dir,
            config_path=self._config_path,
            cache=self._stored_recipe_cache,
        )
        self._stored_recipe_cache = cache
        self._last_stored_recipe_runtime_diagnostics = {
            "loaded": len(rows),
            "enabled": sum(1 for row in rows if isinstance(row, dict) and bool(row.get("enabled", False))),
            "disabled": sum(1 for row in rows if isinstance(row, dict) and not bool(row.get("enabled", False))),
            "invalid": len(list(cache.get("errors", []) or [])) if isinstance(cache, dict) else 0,
        }
        return rows

    @staticmethod
    def _should_skip_recipe_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_recipe_auto_memory_persist(intents)

    def _build_recipe_status_text(self, runtime_recipes: list[dict[str, Any]]) -> str:
        return build_recipe_status_text(self.settings, runtime_recipes)
