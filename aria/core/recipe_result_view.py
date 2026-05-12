from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore
from aria.core.recipe_runtime_contract import RECIPE_MANIFEST_MISSING_ERROR
from aria.core.recipe_runtime_contract import RECIPE_SSH_NONZERO_EXIT_ERROR

BASE_DIR = Path(__file__).resolve().parents[2]
_RECIPE_RESULT_I18N = I18NStore(BASE_DIR / "aria" / "i18n")
_STEP_MARKER_RE = re.compile(r"^(?P<index>\d+)\.(?P<kind>[a-z0-9_]+)(?:\((?P<state>[^)]+)\))?$")


def _text(language: str | None, key: str, default: str = "", **values: Any) -> str:
    template = _RECIPE_RESULT_I18N.t(language or "de", f"recipe_runtime.{key}", default or key)
    if not values:
        return template
    try:
        return template.format(**values)
    except Exception:
        return template


def format_recipe_step_marker(marker: str, *, language: str = "de") -> str:
    clean = str(marker or "").strip()
    if not clean:
        return ""
    match = _STEP_MARKER_RE.match(clean)
    if not match:
        return clean
    index = match.group("index")
    kind = match.group("kind")
    state = str(match.group("state") or "ok").strip().lower()
    if state == "skipped":
        status = _text(language, "execution_step_skipped", "skipped")
    elif state == "error-continue":
        status = _text(language, "execution_step_error_continue", "error, continued")
    else:
        status = _text(language, "execution_step_ok", "ok")
    return _text(language, "execution_step_line", "{index}. {kind}: {status}", index=index, kind=kind, status=status)


def build_recipe_execution_summary(
    *,
    recipe_name: str,
    executed: list[str],
    skipped: list[str],
    result: str,
    ssh_summary: str = "",
    held_summary: str = "",
    language: str = "de",
    truncate: Any | None = None,
) -> str:
    clean_name = str(recipe_name or "").strip() or _text(language, "execution_unknown_recipe", "Recipe")
    lines = [
        f"[Stored Recipe Steps] {clean_name}",
        _text(language, "execution_summary_title", "Recipe run: {recipe_name}", recipe_name=clean_name),
        _text(language, "execution_summary_status_success", "Status: completed"),
    ]
    readable_steps = [format_recipe_step_marker(marker, language=language) for marker in executed]
    readable_steps = [row for row in readable_steps if row]
    if readable_steps:
        lines.append(_text(language, "execution_summary_steps_title", "Steps:"))
        lines.extend(f"- {row}" for row in readable_steps)
    if skipped:
        readable_skipped = [format_recipe_step_marker(marker, language=language) for marker in skipped]
        readable_skipped = [row for row in readable_skipped if row]
        lines.append(
            _text(
                language,
                "execution_skipped_steps",
                "Skipped steps: {steps}",
                steps=", ".join(readable_skipped or skipped),
            )
        )
    if ssh_summary:
        lines.append(str(ssh_summary).strip())
    if held_summary:
        lines.append(str(held_summary).strip())
    clean_result = str(result or "").strip()
    if clean_result:
        if callable(truncate):
            clean_result = str(truncate(clean_result, 1400))
        lines.append(_text(language, "steps_result", "Result:\n{result}", result=clean_result))
    return "\n".join(line for line in lines if str(line).strip())


def friendly_recipe_error_text(error: str, *, language: str = "de") -> str:
    clean = str(error or "").strip()
    if not clean:
        return _text(language, "friendly_error_generic", "Recipe execution failed.")
    if clean == RECIPE_MANIFEST_MISSING_ERROR:
        return _text(language, "friendly_error_manifest_missing", "The recipe manifest is missing or no longer available.")
    if clean == "recipe_steps_missing":
        return _text(language, "friendly_error_steps_missing", "The recipe has no executable steps.")
    if clean.startswith("recipe_unknown_step_type:"):
        step_type = clean.split(":", 1)[1].strip() or "unknown"
        return _text(language, "friendly_error_unknown_step", "The recipe contains an unsupported step type: {step_type}.", step_type=step_type)
    if clean == RECIPE_SSH_NONZERO_EXIT_ERROR or clean.startswith(f"{RECIPE_SSH_NONZERO_EXIT_ERROR}:"):
        return _text(language, "friendly_error_ssh_nonzero", "An SSH step finished with a non-zero exit code.")
    prefix_map = {
        "recipe_sftp_read_error:": "friendly_error_sftp_read",
        "recipe_sftp_write_error:": "friendly_error_sftp_write",
        "recipe_smb_read_error:": "friendly_error_smb_read",
        "recipe_smb_write_error:": "friendly_error_smb_write",
        "recipe_rss_read_error:": "friendly_error_rss_read",
        "recipe_discord_send_error:": "friendly_error_discord_send",
    }
    for prefix, key in prefix_map.items():
        if clean.startswith(prefix):
            detail = clean.split(":", 1)[1].strip()
            return _text(language, key, "Recipe step failed: {detail}", detail=detail)
    return _text(language, "friendly_error_with_code", "Recipe execution failed: {error}", error=clean)
