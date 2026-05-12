from __future__ import annotations

from typing import Any


def ssh_guardrail_allow_terms(profile: Any | None) -> list[str]:
    if not profile:
        return []
    kind = str(profile.get("kind", "") if isinstance(profile, dict) else getattr(profile, "kind", "")).strip()
    if kind != "ssh_command":
        return []
    allow_terms = profile.get("allow_terms", []) if isinstance(profile, dict) else getattr(profile, "allow_terms", [])
    return [str(item).strip() for item in list(allow_terms or []) if str(item).strip()]


def combined_ssh_allow_commands(*command_lists: list[str] | tuple[str, ...]) -> list[str]:
    commands: list[str] = []
    for command_list in command_lists:
        for item in list(command_list or []):
            command = str(item or "").strip()
            if command and command not in commands:
                commands.append(command)
    return commands


def dossier_ssh_allow_commands(dossier: dict[str, Any]) -> list[str]:
    return combined_ssh_allow_commands(
        list(dossier.get("allow_commands", []) or []),
        list(dossier.get("guardrail_allow_terms", []) or []),
    )
