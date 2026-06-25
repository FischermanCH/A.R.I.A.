from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aria.core.bounded_decision import BoundedDecisionClient
from aria.core.i18n import I18NStore
from aria.core.recipe_runtime import build_recipe_status_text
from aria.core.recipe_runtime import load_recipe_toggles
from aria.core.recipe_runtime import load_stored_recipe_runtime
from aria.core.recipe_runtime import match_recipe_intents
from aria.core.recipe_runtime import match_stored_recipe_intents
from aria.core.recipe_runtime import normalize_recipe_keywords
from aria.core.recipe_runtime import normalize_recipe_steps
from aria.core.recipe_runtime import render_step_template
from aria.core.recipe_runtime import resolve_recipe_intent_with_llm
from aria.core.recipe_runtime import resolve_stored_recipe_intent_with_llm
from aria.core.recipe_runtime import sanitize_recipe_id
from aria.core.recipe_runtime import scored_stored_recipe_rows
from aria.core.recipe_runtime import should_skip_recipe_auto_memory_persist


_PIPELINE_RECIPE_HELPERS_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


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
    def _sanitize_skill_id(value: str) -> str:
        return sanitize_recipe_id(value)

    @staticmethod
    def _normalize_skill_keywords(value: Any) -> list[str]:
        return normalize_recipe_keywords(value)

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
        return rows

    def _match_stored_recipe_intents(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return match_stored_recipe_intents(message, runtime_skills)

    def _match_recipe_intents(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return match_recipe_intents(message, runtime_skills)

    async def _resolve_stored_recipe_intent_with_llm(
        self,
        message: str,
        runtime_skills: list[dict[str, Any]],
        *,
        debug_lines: list[str] | None = None,
    ) -> list[str]:
        return await resolve_stored_recipe_intent_with_llm(
            message,
            runtime_skills,
            self.llm_client,
            debug_lines=debug_lines,
        )

    async def _resolve_recipe_intent_with_llm(self, message: str, runtime_skills: list[dict[str, Any]]) -> list[str]:
        return await resolve_recipe_intent_with_llm(message, runtime_skills, self.llm_client)

    @staticmethod
    def _should_skip_recipe_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_recipe_auto_memory_persist(intents)

    @staticmethod
    def _should_skip_auto_memory_persist(intents: list[str]) -> bool:
        return should_skip_recipe_auto_memory_persist(intents)

    def _build_recipe_status_text(self, runtime_recipes: list[dict[str, Any]], auto_memory_enabled: bool) -> str:
        return build_recipe_status_text(self.settings, runtime_recipes, auto_memory_enabled)

    @staticmethod
    def _recipe_intent_was_rejected(debug_lines: list[str]) -> bool:
        return any(
            "Routing Debug: recipe_execution_intent " in str(line)
            and "execute=false" in str(line)
            for line in debug_lines
        )

    @staticmethod
    def _format_recipe_step_for_catalog_response(step: dict[str, Any]) -> str:
        step_type = str(step.get("type", "") or "").strip() or "step"
        name = str(step.get("name", "") or "").strip()
        params = step.get("params", {})
        suffix = ""
        if isinstance(params, dict):
            chat_message = str(params.get("chat_message", "") or "").strip()
            command = str(params.get("command", "") or "").strip()
            if chat_message:
                suffix = f": {chat_message[:180]}"
            elif command:
                suffix = _pipeline_text("de", "recipe_catalog.step_ssh_command_suffix", ": SSH command from stored recipe")
        label = f"{step_type} - {name}" if name else step_type
        return f"{label}{suffix}"

    @staticmethod
    def _recipe_catalog_explanation_manifest(row: dict[str, Any]) -> dict[str, Any]:
        raw_connections = row.get("connections", [])
        connections = [str(item).strip() for item in raw_connections if str(item).strip()] if isinstance(raw_connections, list) else []
        raw_steps = row.get("steps", [])
        steps: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            for step in raw_steps[:8]:
                if not isinstance(step, dict):
                    continue
                params = step.get("params", {})
                safe_params: dict[str, str] = {}
                if isinstance(params, dict):
                    for key in ("chat_message", "command", "prompt", "template"):
                        value = str(params.get(key, "") or "").strip()
                        if value:
                            safe_params[key] = value[:500]
                steps.append(
                    {
                        "id": str(step.get("id", "") or "").strip(),
                        "name": str(step.get("name", "") or "").strip(),
                        "type": str(step.get("type", "") or "").strip(),
                        "params": safe_params,
                    }
                )
        return {
            "id": str(row.get("id", "") or "").strip(),
            "name": str(row.get("name", "") or "").strip(),
            "description": str(row.get("description", "") or "").strip(),
            "connections": connections,
            "steps": steps,
        }

    def _format_recipe_catalog_explanation_fallback(
        self,
        message: str,
        runtime_recipes: list[dict[str, Any]],
    ) -> tuple[str, str, dict[str, int]]:
        rows = scored_stored_recipe_rows(message, runtime_recipes, limit=3)
        strong_rows = [row for row in rows if int(row.get("_match_score", 0) or 0) >= 55]
        if strong_rows:
            row = strong_rows[0]
            recipe_id = str(row.get("id", "") or "").strip()
            name = str(row.get("name", "") or "").strip() or recipe_id
            description = str(row.get("description", "") or "").strip()
            raw_connections = row.get("connections", [])
            connections = [str(item).strip() for item in raw_connections if str(item).strip()] if isinstance(raw_connections, list) else []
            raw_steps = row.get("steps", [])
            steps = [step for step in raw_steps if isinstance(step, dict)] if isinstance(raw_steps, list) else []
            lines = [
                _pipeline_text("de", "recipe_catalog.match_intro", "I am not running anything. Stored recipe `{name}` (`{recipe_id}`) matches your question.", name=name, recipe_id=recipe_id),
            ]
            if description:
                lines.append(f"Beschreibung: {description}")
            if connections:
                lines.append(_pipeline_text("de", "recipe_catalog.connections", "Connections: {connections}", connections=", ".join(connections)))
            if steps:
                lines.append("Ablauf:")
                lines.extend(
                    f"{idx}. {self._format_recipe_step_for_catalog_response(step)}"
                    for idx, step in enumerate(steps[:8], start=1)
                )
            debug_line = (
                "Routing Debug: recipe_catalog_explanation "
                f"source=stored_recipe_catalog matches={len(rows)} "
                f"strong_matches={len(strong_rows)} boundary=direct_response"
            )
            return "\n".join(lines), debug_line, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        lines = [
            _pipeline_text("de", "recipe_catalog.no_clear_match", "I cannot find a stored recipe that clearly matches this question."),
            _pipeline_text("de", "recipe_catalog.no_generic_runbook", "I will not invent a server update recipe or provide a generic runbook."),
        ]
        if rows:
            lines.append(_pipeline_text("de", "recipe_catalog.near_candidates", "Nearby candidates in the recipe catalog:"))
            for row in rows:
                recipe_id = str(row.get("id", "") or "").strip()
                name = str(row.get("name", "") or "").strip() or recipe_id
                description = str(row.get("description", "") or "").strip()
                score = int(row.get("_match_score", 0) or 0)
                extra = f" - {description}" if description else ""
                lines.append(f"- `{name}` (`{recipe_id}`, Score {score}){extra}")
        else:
            lines.append(_pipeline_text("de", "recipe_catalog.no_near_candidate", "The current recipe catalog does not contain a nearby candidate either."))
        debug_line = (
            "Routing Debug: recipe_catalog_explanation "
            f"source=stored_recipe_catalog matches={len(rows)} "
            "strong_matches=0 boundary=direct_response"
        )
        return "\n".join(lines), debug_line, {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def _build_recipe_catalog_explanation_response(
        self,
        message: str,
        runtime_recipes: list[dict[str, Any]],
        *,
        language: str | None = None,
    ) -> tuple[str, str, dict[str, int]]:
        rows = scored_stored_recipe_rows(message, runtime_recipes, limit=3)
        strong_rows = [row for row in rows if int(row.get("_match_score", 0) or 0) >= 55]
        if not strong_rows or self.llm_client is None:
            return self._format_recipe_catalog_explanation_fallback(message, runtime_recipes)

        manifest = self._recipe_catalog_explanation_manifest(strong_rows[0])
        recipe_id = str(manifest.get("id", "") or "").strip()
        recipe_name = str(manifest.get("name", "") or "").strip()
        payload = {
            "user_message": str(message or ""),
            "language": str(language or "de"),
            "matching_recipe": manifest,
            "contract": (
                "Explain only this stored recipe manifest. Do not invent extra server update steps, commands, packages, "
                "backups, reboots, or operational advice. State that nothing is executed. If a detail is not present in "
                "the manifest, say that it is not stored in the recipe."
            ),
        }
        decision = await BoundedDecisionClient(self.llm_client).complete_text(
            operation="recipe_catalog_explanation",
            system=(
                "You are a bounded stored-recipe explainer. Answer the user from the provided recipe manifest only. "
                "Do not execute anything, do not propose runtime actions, and do not add generic runbook steps."
            ),
            payload=payload,
        )
        if not decision.ok:
            return self._format_recipe_catalog_explanation_fallback(message, runtime_recipes)

        text = decision.content
        lowered = text.lower()
        mentions_manifest = (recipe_id and recipe_id.lower() in lowered) or (recipe_name and recipe_name.lower() in lowered)
        if not text or not mentions_manifest:
            return self._format_recipe_catalog_explanation_fallback(message, runtime_recipes)
        debug_line = (
            "Routing Debug: recipe_catalog_explanation "
            f"source=stored_recipe_catalog matches={len(rows)} "
            f"strong_matches={len(strong_rows)} boundary=bounded_llm"
        )
        return text, debug_line, decision.usage

    @staticmethod
    def _recipe_catalog_debug_has_strong_match(debug_line: str) -> bool:
        match = re.search(r"\bstrong_matches=(\d+)\b", str(debug_line or ""))
        return bool(match and int(match.group(1) or 0) > 0)

    @staticmethod
    def _message_explicitly_asks_about_recipe(message: str) -> bool:
        return bool(re.search(r"\b(?:rezept|recipe)\b", str(message or ""), flags=re.IGNORECASE))
