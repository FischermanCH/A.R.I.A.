from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from aria.core.action_plan import ActionPlan
from aria.core.i18n import I18NStore
from aria.core.recipe_runtime_contract import DIRECT_SSH_RECIPE_ID
from aria.core.recipe_runtime_contract import RECIPE_SSH_NONZERO_EXIT_ERROR
from aria.core.result_summarizers import extract_df_metrics
from aria.core.result_summarizers import extract_docker_ps_metrics
from aria.core.result_summarizers import extract_free_metrics
from aria.core.result_summarizers import extract_systemctl_active_states
from aria.core.result_summarizers import extract_uptime_metrics
from aria.core.result_summarizers import summarize_file_result_for_chat
from aria.core.result_summarizers import summarize_http_api_result_for_chat
from aria.core.result_summarizers import summarize_imap_result_for_chat
from aria.core.result_summarizers import summarize_rss_category_result_for_chat
from aria.core.result_summarizers import summarize_rss_group_result_for_chat
from aria.core.result_summarizers import summarize_ssh_result_for_chat
from aria.core.rss_digest_options import parse_rss_digest_options_note
from aria.core.ssh_policy import validate_ssh_readonly_policy
from aria.core.website_runtime import build_website_list_text
from aria.core.website_runtime import build_website_read_text
from aria.core.website_runtime import find_matching_group_name
from aria.core.website_runtime import normalize_website_rows
from aria.skills.base import SkillResult

_CAPABILITY_EXECUTION_I18N = I18NStore(Path(__file__).resolve().parents[1] / "i18n")


def _capability_execution_text(language: str | None, key: str, default: str = "", **values: object) -> str:
    template = _CAPABILITY_EXECUTION_I18N.t(language or "de", f"pipeline_capability_execution.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def _plan_has_user_policy_confirmation(plan: ActionPlan) -> bool:
    return any(
        str(note or "").strip().lower().startswith("user_confirmed_policy")
        for note in list(plan.notes or [])
    )


ExecuteCustomSSHCommand = Callable[..., Awaitable[SkillResult]]
BundleNoteParser = Callable[[list[str] | tuple[str, ...] | None], tuple[str, list[str]] | None]
OptionalLanguageCaller = Callable[..., Any]
WebsiteRowsGetter = Callable[[], dict[str, dict[str, object]]]
MQTTTopicGetter = Callable[[str], str]
MessageBuilder = Callable[[str | None, str, str], str]
SpaceNormalizer = Callable[[str], str]
JSONExtractor = Callable[[str], dict[str, Any] | None]


class PipelineCapabilityExecutor:
    def __init__(
        self,
        *,
        skill_runtime: Any,
        execute_custom_ssh_command: ExecuteCustomSSHCommand,
        parse_rss_group_bundle_note: BundleNoteParser,
        call_with_optional_language: OptionalLanguageCaller,
        website_rows: WebsiteRowsGetter,
        default_mqtt_topic: MQTTTopicGetter,
        msg: MessageBuilder,
        normalize_spaces: SpaceNormalizer,
        extract_json_object: JSONExtractor,
    ) -> None:
        self._skill_runtime = skill_runtime
        self._execute_custom_ssh_command = execute_custom_ssh_command
        self._parse_rss_group_bundle_note = parse_rss_group_bundle_note
        self._call_with_optional_language = call_with_optional_language
        self._website_rows = website_rows
        self._default_mqtt_topic = default_mqtt_topic
        self._msg = msg
        self._normalize_spaces = normalize_spaces
        self._extract_json_object = extract_json_object

    async def execute_file_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        del language
        if plan.connection_kind == "smb":
            return self._skill_runtime.execute_smb_read(plan.connection_ref, plan.path)
        return self._skill_runtime.execute_sftp_read(plan.connection_ref, plan.path)

    async def execute_file_write(self, plan: ActionPlan, *, language: str = "de") -> str:
        if plan.connection_kind == "smb":
            result_text = self._skill_runtime.execute_smb_write(plan.connection_ref, plan.path, plan.content)
        else:
            result_text = self._skill_runtime.execute_sftp_write(plan.connection_ref, plan.path, plan.content)
        summarized = summarize_file_result_for_chat(
            result_text,
            connection_ref=plan.connection_ref,
            connection_kind=plan.connection_kind,
            capability="file_write",
            path=plan.path,
            language=language,
        )
        return summarized or result_text

    async def execute_file_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        if plan.connection_kind == "smb":
            result_text = self._call_with_optional_language(
                self._skill_runtime.execute_smb_list,
                plan.connection_ref,
                plan.path or ".",
                language=language,
            )
        else:
            result_text = self._call_with_optional_language(
                self._skill_runtime.execute_sftp_list,
                plan.connection_ref,
                plan.path or ".",
                language=language,
            )
        summarized = summarize_file_result_for_chat(
            result_text,
            connection_ref=plan.connection_ref,
            connection_kind=plan.connection_kind,
            capability="file_list",
            path=plan.path or ".",
            language=language,
        )
        return summarized or result_text

    async def execute_feed_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        digest_options = parse_rss_digest_options_note(plan.notes)
        requested_count = int(digest_options.get("requested_count", 0) or 0)
        bundle = self._parse_rss_group_bundle_note(plan.notes)
        if bundle is not None:
            group_name, refs = bundle
            if requested_count > 0:
                try:
                    result_text = self._skill_runtime.execute_rss_group_read(
                        group_name,
                        refs,
                        language=language,
                        requested_count=requested_count,
                    )
                except TypeError as exc:
                    if "unexpected keyword argument 'requested_count'" not in str(exc):
                        raise
                    result_text = self._call_with_optional_language(
                        self._skill_runtime.execute_rss_group_read,
                        group_name,
                        refs,
                        language=language,
                    )
            else:
                result_text = self._call_with_optional_language(
                    self._skill_runtime.execute_rss_group_read,
                    group_name,
                    refs,
                    language=language,
                )
            summarized = summarize_rss_group_result_for_chat(result_text, group_name=group_name, language=language)
            return summarized or result_text
        if requested_count > 0:
            try:
                result_text = self._skill_runtime.execute_rss_read(
                    plan.connection_ref,
                    language=language,
                    requested_count=requested_count,
                )
            except TypeError as exc:
                if "unexpected keyword argument 'requested_count'" not in str(exc):
                    raise
                result_text = self._call_with_optional_language(self._skill_runtime.execute_rss_read, plan.connection_ref, language=language)
        else:
            result_text = self._call_with_optional_language(self._skill_runtime.execute_rss_read, plan.connection_ref, language=language)
        summarized = summarize_rss_category_result_for_chat(result_text, language=language)
        return summarized or result_text

    async def execute_website_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        rows = self._website_rows()
        row = rows.get(str(plan.connection_ref or "").strip())
        if row is None:
            raise ValueError(
                _capability_execution_text(
                    language,
                    "website_not_found",
                    "The watched website `{connection_ref}` could not be found.",
                    connection_ref=plan.connection_ref,
                )
            )
        return build_website_read_text(str(plan.connection_ref or "").strip(), row, language=language)

    async def execute_website_list(self, plan: ActionPlan, *, language: str = "de") -> str:
        rows = self._website_rows()
        group_name = str(plan.content or "").strip()
        if group_name:
            group_name = find_matching_group_name(group_name, rows) or group_name
        return build_website_list_text(rows, group_name=group_name, language=language)

    async def execute_calendar_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_google_calendar_read,
            plan.connection_ref,
            plan.path or "upcoming",
            plan.content,
            language=language,
        )

    async def execute_webhook_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_webhook_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def execute_discord_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_discord_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def execute_api_request(self, plan: ActionPlan, *, language: str = "de") -> str:
        result_text = self._call_with_optional_language(
            self._skill_runtime.execute_http_api_request,
            plan.connection_ref,
            plan.path,
            plan.content,
            language=language,
            confirmed=_plan_has_user_policy_confirmation(plan),
        )
        summarized = summarize_http_api_result_for_chat(
            result_text,
            connection_ref=plan.connection_ref,
            path=plan.path,
            notes=list(plan.notes or []),
            language=language,
            extract_json_object=self._extract_json_object,
        )
        return summarized or result_text

    async def execute_email_send(self, plan: ActionPlan, *, language: str = "de") -> str:
        return self._call_with_optional_language(
            self._skill_runtime.execute_email_send,
            plan.connection_ref,
            plan.content,
            language=language,
        )

    async def execute_mail_read(self, plan: ActionPlan, *, language: str = "de") -> str:
        result_text = self._call_with_optional_language(self._skill_runtime.execute_imap_read, plan.connection_ref, language=language)
        summarized = summarize_imap_result_for_chat(
            result_text,
            connection_ref=plan.connection_ref,
            capability="mail_read",
            search_query=str(plan.content or "").strip(),
            language=language,
        )
        return summarized or result_text

    async def execute_mail_search(self, plan: ActionPlan, *, language: str = "de") -> str:
        result_text = self._call_with_optional_language(
            self._skill_runtime.execute_imap_search,
            plan.connection_ref,
            plan.content,
            language=language,
        )
        summarized = summarize_imap_result_for_chat(
            result_text,
            connection_ref=plan.connection_ref,
            capability="mail_search",
            search_query=str(plan.content or "").strip(),
            language=language,
        )
        return summarized or result_text

    async def execute_mqtt_publish(self, plan: ActionPlan, *, language: str = "de") -> str:
        topic = str(plan.path or "").strip() or self._default_mqtt_topic(plan.connection_ref)
        return self._call_with_optional_language(
            self._skill_runtime.execute_mqtt_publish,
            plan.connection_ref,
            topic,
            plan.content,
            language=language,
        )

    async def execute_ssh_command(self, plan: ActionPlan, *, language: str = "de") -> str:
        ssh_kwargs: dict[str, object] = {}
        if _plan_has_user_policy_confirmation(plan):
            ssh_kwargs["policy_confirmed"] = True
        result = await self._execute_custom_ssh_command(
            skill_id=DIRECT_SSH_RECIPE_ID,
            skill_name="SSH Command",
            connection_ref=plan.connection_ref,
            command_template=plan.content,
            message=plan.content,
            language=language,
            **ssh_kwargs,
        )
        if result.success:
            summarized = summarize_ssh_result_for_chat(
                result,
                connection_ref=plan.connection_ref,
                language=language,
            )
            if summarized:
                return summarized
            return result.content
        if self.can_salvage_partial_ssh_result(result):
            summarized = summarize_ssh_result_for_chat(
                result,
                connection_ref=plan.connection_ref,
                language=language,
            )
            if summarized:
                return summarized + " " + _capability_execution_text(
                    language,
                    "partial_ssh_note",
                    "Note: at least one sub-check in the command did not complete cleanly.",
                )
        raise ValueError(
            str(result.error or "").strip()
            or _capability_execution_text(language, "ssh_command_failed", "SSH command failed.")
        )

    def can_salvage_partial_ssh_result(self, result: SkillResult) -> bool:
        if bool(result.success):
            return False
        if str(result.error or "").strip() != RECIPE_SSH_NONZERO_EXIT_ERROR:
            return False
        meta = result.metadata or {}
        stdout = str(meta.get("custom_stdout", "") or "").strip()
        command = self._normalize_spaces(str(meta.get("custom_command", "") or ""))
        if not stdout or not command:
            return False
        if validate_ssh_readonly_policy(command).action == "block":
            return False
        metrics = extract_uptime_metrics(stdout)
        df_metrics = extract_df_metrics(stdout)
        free_metrics = extract_free_metrics(stdout)
        docker_metrics = extract_docker_ps_metrics(stdout)
        service_states = extract_systemctl_active_states(stdout)
        return bool(metrics or df_metrics or free_metrics or docker_metrics or service_states)


def website_rows_from_settings(settings: Any) -> dict[str, dict[str, object]]:
    rows = getattr(getattr(settings, "connections", object()), "website", {})
    if not isinstance(rows, dict):
        return {}
    return normalize_website_rows(rows)
