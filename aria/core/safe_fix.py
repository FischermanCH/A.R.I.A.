from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from aria.skills.base import SkillResult


SSHExecutor = Callable[..., Awaitable[SkillResult]]


def extract_held_packages(text: str) -> list[str]:
    content = str(text or "")
    if not content.strip():
        return []
    rows = [line.strip() for line in content.splitlines()]
    packages: list[str] = []
    seen: set[str] = set()
    collecting = False
    for line in rows:
        low = line.lower()
        if "kept back" in low or "zurückgehalten" in low or "zurückgehalten" in low:
            collecting = True
            after_colon = line.split(":", 1)[1] if ":" in line else ""
            candidates = re.findall(r"[a-z0-9][a-z0-9+_.-]*", after_colon.lower())
            for token in candidates:
                if token in {"the", "following", "packages", "have", "been", "kept", "back"}:
                    continue
                if token not in seen:
                    seen.add(token)
                    packages.append(token)
            continue

        if collecting:
            if not line:
                collecting = False
                continue
            if ":" in line and not re.search(r"\b[a-z0-9][a-z0-9+_.-]*\b", line.lower()):
                collecting = False
                continue
            candidates = re.findall(r"[a-z0-9][a-z0-9+_.-]*", line.lower())
            if not candidates:
                collecting = False
                continue
            for token in candidates:
                if token in {"reading", "building", "dependency", "state", "information", "done"}:
                    continue
                if token not in seen:
                    seen.add(token)
                    packages.append(token)
            continue

        inline_match = re.search(r"kept back:\s*(.+)$", low)
        if inline_match:
            candidates = re.findall(r"[a-z0-9][a-z0-9+_.-]*", inline_match.group(1))
            for token in candidates:
                if token not in seen:
                    seen.add(token)
                    packages.append(token)
    return packages[:30]


def format_held_packages_summary(
    held_by_connection: dict[str, list[str]],
    connection_targets: dict[str, str],
) -> str:
    if not held_by_connection:
        return ""
    lines = ["Hinweis: Zurückgehaltene Pakete erkannt:"]
    merged: list[str] = []
    seen: set[str] = set()
    for conn_ref in sorted(held_by_connection.keys()):
        pkgs = held_by_connection.get(conn_ref, [])
        if not pkgs:
            continue
        target = connection_targets.get(conn_ref, "").strip()
        place = f"{conn_ref} ({target})" if target else conn_ref
        lines.append(f"- {place}: {', '.join(pkgs)}")
        for pkg in pkgs:
            if pkg not in seen:
                seen.add(pkg)
                merged.append(pkg)
    if merged:
        lines.append("")
        lines.append("Safe-Fix (manuell bestätigen):")
        lines.append("sudo apt install --only-upgrade " + " ".join(merged))
    return "\n".join(lines)


def build_safe_fix_plan(skill_results: list[SkillResult]) -> list[dict[str, Any]]:
    per_connection: dict[str, set[str]] = {}
    for result in skill_results:
        meta = result.metadata or {}
        held_map = meta.get("custom_held_packages_by_connection", {})
        if not isinstance(held_map, dict):
            continue
        for conn_ref, packages in held_map.items():
            key = str(conn_ref).strip()
            if not key or not isinstance(packages, list):
                continue
            bucket = per_connection.setdefault(key, set())
            for pkg in packages:
                name = str(pkg).strip().lower()
                if re.fullmatch(r"[a-z0-9][a-z0-9+_.-]*", name):
                    bucket.add(name)
    plan: list[dict[str, Any]] = []
    for conn_ref in sorted(per_connection.keys()):
        pkgs = sorted(per_connection[conn_ref])
        if not pkgs:
            continue
        plan.append({"connection_ref": conn_ref, "packages": pkgs})
    return plan


class SafeFixExecutor:
    def __init__(self, execute_ssh_command: SSHExecutor):
        self._execute_ssh_command = execute_ssh_command

    async def execute_plan(self, plan: list[dict[str, Any]], language: str = "de") -> SkillResult:
        if not isinstance(plan, list) or not plan:
            return SkillResult(
                skill_name="safe_fix",
                content="Kein gültiger Safe-Fix Plan vorhanden.",
                success=False,
                error="safe_fix_empty_plan",
            )
        rows: list[str] = ["Safe-Fix ausgefuehrt:"]
        all_ok = True
        for idx, item in enumerate(plan, start=1):
            if not isinstance(item, dict):
                continue
            conn_ref = str(item.get("connection_ref", "")).strip()
            packages = item.get("packages", [])
            if not conn_ref or not isinstance(packages, list):
                continue
            clean_packages: list[str] = []
            for pkg in packages:
                package_name = str(pkg).strip().lower()
                if re.fullmatch(r"[a-z0-9][a-z0-9+_.-]*", package_name):
                    clean_packages.append(package_name)
            clean_packages = sorted(set(clean_packages))
            if not clean_packages:
                continue
            command = "sudo apt install --only-upgrade " + " ".join(clean_packages)
            ssh_result = await self._execute_ssh_command(
                skill_id="safe-fix",
                skill_name="Safe Fix",
                connection_ref=conn_ref,
                command_template=command,
                message="safe-fix",
                language=language,
            )
            if ssh_result.success:
                rows.append(f"{idx}. {conn_ref}: OK ({', '.join(clean_packages)})")
            else:
                all_ok = False
                rows.append(f"{idx}. {conn_ref}: FEHLER ({ssh_result.error or 'unknown'})")
                interpretation = (ssh_result.metadata or {}).get("error_interpretation")
                if isinstance(interpretation, dict):
                    title = str(interpretation.get("title", "")).strip()
                    cause = str(interpretation.get("cause", "")).strip()
                    next_step = str(interpretation.get("next_step", "")).strip()
                    if title:
                        rows.append(f"   {title}")
                    if cause:
                        rows.append(f"   Ursache: {cause}")
                    if next_step:
                        rows.append(f"   Nächster Schritt: {next_step}")
        if len(rows) == 1:
            return SkillResult(
                skill_name="safe_fix",
                content="Safe-Fix konnte nicht ausgefuehrt werden (kein ausführbarer Plan).",
                success=False,
                error="safe_fix_no_valid_items",
            )
        return SkillResult(
            skill_name="safe_fix",
            content="\n".join(rows),
            success=all_ok,
            error="" if all_ok else "safe_fix_partial_or_failed",
        )
