from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from aria.core.i18n import I18NStore
from aria.core.text_utils import is_english

_SSH_I18N = I18NStore(Path(__file__).resolve().parents[2] / "i18n")


def _ssh_summary_text(language: str | None, key: str, **values: Any) -> str:
    template = _SSH_I18N.t(str(language or "de"), f"result_ssh.{key}", key)
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return template


def extract_uptime_metrics(stdout: str) -> dict[str, str]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    metrics: dict[str, str] = {}
    up_match = re.search(r"\bup\s+(.+?),\s+\d+\s+users?,\s+load average:", text)
    if up_match:
        metrics["uptime"] = up_match.group(1).strip()
    users_match = re.search(r",\s*(\d+)\s+users?,\s+load average:", text)
    if users_match:
        metrics["users"] = users_match.group(1).strip()
    load_match = re.search(r"load average:\s*([0-9.,]+\s*,\s*[0-9.,]+\s*,\s*[0-9.,]+)", text)
    if load_match:
        metrics["load"] = load_match.group(1).strip()
    if "uptime" not in metrics:
        for line in text.splitlines():
            clean = line.strip()
            if clean.lower().startswith("up "):
                metrics["uptime"] = clean
                break
    return metrics


def extract_df_metrics(stdout: str) -> dict[str, str]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    if len(rows) < 2:
        return {}
    preferred = ""
    for line in rows[1:]:
        parts = re.split(r"\s+", line)
        if len(parts) >= 6 and parts[-1] == "/":
            preferred = line
            break
    target = preferred or (rows[1] if len(rows) > 1 else "")
    parts = re.split(r"\s+", target.strip())
    if len(parts) < 6:
        return {}
    return {
        "filesystem": parts[0],
        "size": parts[1],
        "used": parts[2],
        "avail": parts[3],
        "use_percent": parts[4],
        "mount": parts[5],
    }


def _command_contains_df(command: str) -> bool:
    return bool(re.search(r"(?:^|[;&|]\s*)df\s+-[A-Za-z]*h\b", str(command or "").strip().lower()))


def _command_inspects_directory(command: str) -> bool:
    clean = str(command or "").strip().lower()
    return bool(
        re.search(r"(?:^|[;&|]\s*)du\s+.*--max-depth\s*=\s*1\b", clean)
        or re.search(r"(?:^|[;&|]\s*)ls\s+-[A-Za-z]*[ahl][A-Za-z]*\s+/", clean)
    )


def _extract_command_path(command: str) -> str:
    text = str(command or "").strip()
    for pattern in (
        r"(?:^|[;&|]\s*)du\s+.*?--max-depth\s*=\s*1\s+((?:'[^']+'|\"[^\"]+\"|/[^\s;&|]+))",
        r"(?:^|[;&|]\s*)ls\s+-[A-Za-z]*[ahl][A-Za-z]*\s+((?:'[^']+'|\"[^\"]+\"|/[^\s;&|]+))",
    ):
        match = re.search(pattern, text)
        if not match:
            continue
        path = match.group(1).strip().strip("'\"")
        if path.startswith("/"):
            return path
    return ""


def _summarize_directory_inspection(stdout: str, *, command: str, connection_ref: str, language: str | None = None) -> str:
    text = str(stdout or "").strip()
    if not text:
        return ""
    path = _extract_command_path(command) or "/"
    entries: list[str] = []
    total_line = ""
    for raw_line in text.splitlines():
        clean = raw_line.strip()
        if not clean:
            continue
        if clean.lower().startswith("total "):
            total_line = clean
            continue
        du_match = re.match(r"^(\S+)\s+(/.+)$", clean)
        if du_match:
            size, item_path = du_match.groups()
            if item_path.rstrip("/") == path.rstrip("/"):
                total_line = f"{size} {item_path}"
                continue
            entries.append(f"{size} {item_path}")
            continue
        parts = re.split(r"\s+", clean, maxsplit=8)
        if len(parts) >= 9 and re.match(r"^[bcdlps-][rwxstST-]{9}", parts[0]):
            name = parts[8].strip()
            if name in {".", ".."}:
                continue
            entries.append(f"{parts[4]} {name}")
    entries = entries[:10]
    if not entries and not total_line:
        return ""
    host_label = f"`{connection_ref}`"
    header = _ssh_summary_text(language, "directory_inspection", host=host_label, path=path)
    if total_line:
        header += " " + _ssh_summary_text(language, "directory_total", total=total_line)
    if not entries:
        return header.strip()
    return (header.rstrip() + "\n\n" + "\n".join(f"- {entry}" for entry in entries)).strip()


def extract_free_metrics(stdout: str) -> dict[str, str]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    metrics: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Mem:"):
            parts = re.split(r"\s+", stripped)
            if len(parts) >= 7:
                metrics.update(
                    {
                        "mem_total": parts[1],
                        "mem_used": parts[2],
                        "mem_free": parts[3],
                        "mem_available": parts[6],
                    }
                )
        elif stripped.startswith("Swap:"):
            parts = re.split(r"\s+", stripped)
            if len(parts) >= 4:
                metrics.update(
                    {
                        "swap_total": parts[1],
                        "swap_used": parts[2],
                        "swap_free": parts[3],
                    }
                )
    return metrics


def extract_docker_ps_metrics(stdout: str) -> dict[str, int]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    rows = [line.strip() for line in text.splitlines() if line.strip()]
    header_index = -1
    for index, line in enumerate(rows):
        if line.lower().startswith("names status"):
            header_index = index
            break
    if header_index < 0:
        return {}
    total = 0
    unhealthy = 0
    for line in rows[header_index + 1 :]:
        parts = re.split(r"\s+", line, maxsplit=1)
        if len(parts) < 2:
            continue
        total += 1
        status = parts[1].strip().lower()
        if not status.startswith("up"):
            unhealthy += 1
    if total <= 0:
        return {}
    return {
        "total": total,
        "healthy": max(0, total - unhealthy),
        "unhealthy": unhealthy,
    }


def extract_systemctl_active_states(stdout: str) -> list[str]:
    text = str(stdout or "").strip()
    if not text:
        return []
    states: list[str] = []
    for line in reversed(text.splitlines()):
        clean = line.strip().lower()
        if clean in {"active", "inactive", "failed", "activating", "deactivating"}:
            states.append(clean)
    return list(reversed(states))


def extract_systemctl_failed_metrics(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    listed_match = re.search(r"\b(\d+)\s+loaded units?\s+listed\b", text, flags=re.IGNORECASE)
    if listed_match:
        return {"failed_count": int(listed_match.group(1))}
    failed_rows = 0
    for line in text.splitlines():
        clean = line.strip()
        if not clean or clean.lower().startswith(("unit ", "load ", "active ", "sub ")):
            continue
        if re.search(r"\bloaded\s+failed\s+failed\b", clean, flags=re.IGNORECASE):
            failed_rows += 1
    if failed_rows:
        return {"failed_count": failed_rows}
    return {}


def extract_journal_error_metrics(stdout: str) -> dict[str, Any]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    if "-- no entries --" in text.lower():
        return {"error_count": 0, "sample": ""}
    journal_lines: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if re.match(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+", clean):
            journal_lines.append(clean)
    if not journal_lines:
        return {}
    sample = journal_lines[0]
    if len(sample) > 120:
        sample = sample[:117].rstrip() + "..."
    categories: dict[str, int] = {}
    severity = "info"
    severity_rank = {"info": 0, "warning": 1, "critical": 2}
    for line in journal_lines:
        category, line_severity = classify_journal_error_line(line)
        categories[category] = categories.get(category, 0) + 1
        if severity_rank[line_severity] > severity_rank[severity]:
            severity = line_severity
    return {
        "error_count": len(journal_lines),
        "sample": sample,
        "categories": categories,
        "severity": severity,
    }


def classify_journal_error_line(line: str) -> tuple[str, str]:
    clean = str(line or "").strip().lower()
    if any(
        token in clean
        for token in (
            "i/o error",
            "blk_update_request",
            "buffer i/o",
            "ext4-fs error",
            "xfs ",
            "read-only file system",
            "filesystem error",
            "nvme",
            " sda",
            " sdb",
            "mmcblk",
        )
    ):
        return "storage", "critical"
    if any(token in clean for token in ("out of memory", "oom-killer", "memory allocation failure")):
        return "memory", "critical"
    if any(token in clean for token in ("segfault", "core dumped", "panic", "kernel panic")):
        return "crash", "critical"
    if any(
        token in clean
        for token in (
            "failed to start",
            "dependency failed",
            "unit entered failed state",
            "main process exited",
        )
    ):
        return "service", "warning"
    if any(
        token in clean
        for token in (
            "pam_unix",
            "sudo",
            "authentication failure",
            "conversation failed",
            "failed password",
            "invalid user",
        )
    ):
        return "auth", "info"
    if any(token in clean for token in ("dnsmasq", "pihole-ftl", "ftl", "gravity")):
        return "dns_service", "warning"
    if any(token in clean for token in ("network is unreachable", "link is down", "timed out")):
        return "network", "warning"
    return "other", "warning"


def summarize_journal_error_metrics(metrics: dict[str, Any], *, language: str | None = None) -> str:
    raw_count = metrics.get("error_count")
    if raw_count is None:
        return ""
    count = int(raw_count or 0)
    if count <= 0:
        return _ssh_summary_text(language, "journal_none")
    categories = metrics.get("categories")
    if not isinstance(categories, dict):
        categories = {}
    severity = str(metrics.get("severity", "warning") or "warning").strip().lower()
    dominant_category = ""
    if categories:
        dominant_category = max(categories.items(), key=lambda item: int(item[1] or 0))[0]
    if severity == "critical":
        if dominant_category == "storage":
            return _ssh_summary_text(language, "journal_storage_critical", count=count)
        if dominant_category == "memory":
            return _ssh_summary_text(language, "journal_memory_critical", count=count)
        if dominant_category == "crash":
            return _ssh_summary_text(language, "journal_crash_critical", count=count)
        return _ssh_summary_text(language, "journal_relevant_critical", count=count)
    if dominant_category == "auth":
        return _ssh_summary_text(language, "journal_auth", count=count)
    if dominant_category == "dns_service":
        return _ssh_summary_text(language, "journal_dns", count=count)
    if dominant_category == "network":
        return _ssh_summary_text(language, "journal_network", count=count)
    if dominant_category == "service":
        return _ssh_summary_text(language, "journal_service", count=count)
    return _ssh_summary_text(language, "journal_other", count=count)


def _parse_size_to_gib(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.match(r"([0-9]+(?:[.,][0-9]+)?)\s*([kmgt]i?b?)?$", text.lower())
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    unit = str(match.group(2) or "b").lower()
    factors = {
        "b": 1 / (1024**3),
        "k": 1 / (1024**2),
        "kb": 1 / (1024**2),
        "ki": 1 / (1024**2),
        "kib": 1 / (1024**2),
        "m": 1 / 1024,
        "mb": 1 / 1024,
        "mi": 1 / 1024,
        "mib": 1 / 1024,
        "g": 1.0,
        "gb": 1.0,
        "gi": 1.0,
        "gib": 1.0,
        "t": 1024.0,
        "tb": 1024.0,
        "ti": 1024.0,
        "tib": 1024.0,
    }
    factor = factors.get(unit)
    if factor is None:
        return None
    return number * factor


def classify_memory_available(available_value: str, *, language: str | None = None) -> str:
    del language
    gib_value = _parse_size_to_gib(available_value)
    if gib_value is None:
        return ""
    if gib_value < 0.5:
        return "critical"
    if gib_value < 1.0:
        return "tight"
    return "ok"


def classify_load(load_value: str, *, language: str | None = None) -> str:
    del language
    values: list[float] = []
    for part in str(load_value or "").split(","):
        token = part.strip().replace(",", ".")
        if not token:
            continue
        try:
            values.append(float(token))
        except ValueError:
            continue
    if not values:
        return ""
    peak = max(values)
    if peak >= 4:
        return "high"
    if peak >= 2:
        return "elevated"
    return "normal"


def classify_disk_usage(use_percent: str, *, language: str | None = None) -> str:
    del language
    match = re.search(r"(\d+)", str(use_percent or ""))
    if not match:
        return ""
    used = int(match.group(1))
    if used >= 95:
        return "critical"
    if used >= 85:
        return "tight"
    return "ok"


def _localized_health_state(language: str | None, state: str) -> str:
    clean = str(state or "").strip().lower()
    if not clean:
        return ""
    return _ssh_summary_text(language, f"state_{clean}")


def _is_full_server_healthcheck(command: str) -> bool:
    clean = str(command or "").strip().lower()
    return (
        "uptime" in clean
        and "df -h" in clean
        and "free -h" in clean
        and ("systemctl --failed" in clean or "journalctl" in clean)
    )


def _localized_uptime_value(value: str, *, language: str | None = None) -> str:
    clean = str(value or "").strip()
    if not clean:
        return ""
    if not is_english(language) and clean.lower().startswith("up "):
        return clean[3:].strip()
    return clean


def _extract_uptime_since(stdout: str) -> str:
    first_line = str(stdout or "").strip().splitlines()[0].strip() if str(stdout or "").strip() else ""
    if not first_line:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\s+\S+)?", first_line):
        return first_line
    return ""


def _healthcheck_conclusion(
    *,
    disk_state: str = "",
    mem_state: str = "",
    failed_count: Any = None,
    journal_metrics: dict[str, Any] | None = None,
    language: str | None = None,
) -> str:
    critical_states = {"critical"}
    warning_states = {"tight", "high", "elevated"}
    has_critical = str(disk_state).strip().lower() in critical_states or str(mem_state).strip().lower() in critical_states
    has_warning = str(disk_state).strip().lower() in warning_states or str(mem_state).strip().lower() in warning_states
    try:
        if failed_count is not None and int(failed_count) > 0:
            has_warning = True
    except (TypeError, ValueError):
        pass
    journal = dict(journal_metrics or {})
    if str(journal.get("severity", "") or "").strip().lower() == "critical":
        has_critical = True
    elif int(journal.get("error_count", 0) or 0) > 0 and str(journal.get("severity", "") or "").strip().lower() != "info":
        has_warning = True
    if has_critical:
        return _ssh_summary_text(language, "conclusion_action")
    if has_warning:
        return _ssh_summary_text(language, "conclusion_watch")
    return _ssh_summary_text(language, "conclusion_healthy")


def summarize_ssh_result_for_chat(
    result: Any,
    *,
    connection_ref: str,
    language: str | None = None,
) -> str:
    meta = getattr(result, "metadata", None) or {}
    command_raw = str(meta.get("custom_command", "") or "").strip()
    command = command_raw.lower()
    stdout = str(meta.get("custom_stdout", "") or "").strip()
    if not stdout:
        return ""
    if _command_inspects_directory(command):
        directory_summary = _summarize_directory_inspection(
            stdout,
            command=command_raw,
            connection_ref=connection_ref,
            language=language,
        )
        if directory_summary:
            return directory_summary
    metrics = extract_uptime_metrics(stdout)
    df_metrics = extract_df_metrics(stdout) if _command_contains_df(command) else {}
    free_metrics = extract_free_metrics(stdout)
    docker_metrics = extract_docker_ps_metrics(stdout)
    service_states = extract_systemctl_active_states(stdout)
    failed_metrics = extract_systemctl_failed_metrics(stdout) if "systemctl --failed" in command else {}
    journal_metrics = extract_journal_error_metrics(stdout) if "journalctl" in command else {}
    uptime_value = str(metrics.get("uptime", "") or "").strip()
    load_value = str(metrics.get("load", "") or "").strip()
    users_value = str(metrics.get("users", "") or "").strip()
    use_percent = str(df_metrics.get("use_percent", "") or "").strip()
    avail_value = str(df_metrics.get("avail", "") or "").strip()
    mount_value = str(df_metrics.get("mount", "") or "").strip()
    mem_available = str(free_metrics.get("mem_available", "") or "").strip()
    swap_total = str(free_metrics.get("swap_total", "") or "").strip()
    swap_used = str(free_metrics.get("swap_used", "") or "").strip()
    failed_count = failed_metrics.get("failed_count")
    journal_error_count = journal_metrics.get("error_count")
    journal_summary = summarize_journal_error_metrics(journal_metrics, language=language) if journal_metrics else ""
    host_label = f"`{connection_ref}`"
    is_full_healthcheck = _is_full_server_healthcheck(command)
    uptime_since = _extract_uptime_since(stdout) if command == "uptime -s" else ""
    if uptime_since:
        return " ".join(
            [
                _ssh_summary_text(language, "quick_check", host=host_label),
                _ssh_summary_text(language, "uptime_since", value=uptime_since),
            ]
        ).strip()
    has_health_signals = bool(
        uptime_value
        or load_value
        or use_percent
        or mem_available
        or docker_metrics
        or service_states
        or failed_metrics
        or journal_metrics
    )
    if not has_health_signals and not _command_contains_df(command):
        return ""
    if is_full_healthcheck:
        parts = [_ssh_summary_text(language, "server_healthcheck", host=host_label)]
    elif _command_contains_df(command) and not uptime_value and not load_value:
        parts = [_ssh_summary_text(language, "disk_check", host=host_label)]
    else:
        parts = [_ssh_summary_text(language, "quick_check", host=host_label)]
    if uptime_value:
        parts.append(_ssh_summary_text(language, "uptime", value=_localized_uptime_value(uptime_value, language=language)))
    if load_value:
        load_state = classify_load(load_value, language=language)
        key = "load_with_state" if load_state else "load"
        parts.append(_ssh_summary_text(language, key, value=load_value, state=_localized_health_state(language, load_state)))
    if use_percent:
        disk_state = classify_disk_usage(use_percent, language=language)
        mount_label = mount_value or "/"
        disk_text = _ssh_summary_text(language, "root_fs", mount=mount_label, percent=use_percent)
        if avail_value:
            disk_text += _ssh_summary_text(language, "root_fs_free", avail=avail_value)
        if disk_state:
            disk_text += f" ({_localized_health_state(language, disk_state)})"
        parts.append(disk_text + ".")
    if mem_available:
        mem_state = classify_memory_available(mem_available, language=language)
        mem_text = _ssh_summary_text(language, "available_ram", value=mem_available)
        if mem_state:
            mem_text += f" ({_localized_health_state(language, mem_state)})"
        parts.append(mem_text + ".")
    if failed_count is not None:
        if int(failed_count) <= 0:
            parts.append(_ssh_summary_text(language, "systemd_ok"))
        else:
            parts.append(_ssh_summary_text(language, "systemd_failed", count=failed_count))
    if journal_error_count is not None and journal_summary:
        parts.append(journal_summary)
    if swap_total and swap_used and swap_used.strip().lower() not in {"0", "0b", "0.0b"}:
        parts.append(_ssh_summary_text(language, "swap", used=swap_used, total=swap_total))
    if docker_metrics:
        unhealthy = int(docker_metrics.get("unhealthy", 0) or 0)
        total = int(docker_metrics.get("total", 0) or 0)
        if unhealthy <= 0:
            parts.append(_ssh_summary_text(language, "docker_ok", total=total))
        else:
            parts.append(_ssh_summary_text(language, "docker_issues", unhealthy=unhealthy, total=total))
    elif service_states:
        unique_states = list(dict.fromkeys(service_states))
        if unique_states == ["active"]:
            parts.append(_ssh_summary_text(language, "service_active"))
        elif "failed" in unique_states:
            parts.append(_ssh_summary_text(language, "service_failed"))
        elif "active" in unique_states:
            parts.append(_ssh_summary_text(language, "service_partial"))
        elif unique_states == ["inactive"]:
            parts.append(_ssh_summary_text(language, "service_inactive"))
        else:
            parts.append(_ssh_summary_text(language, "service_unclear"))
    if users_value and users_value != "0":
        parts.append(_ssh_summary_text(language, "users", count=users_value))
    if is_full_healthcheck:
        parts.append(
            _healthcheck_conclusion(
                disk_state=classify_disk_usage(use_percent, language=language) if use_percent else "",
                mem_state=classify_memory_available(mem_available, language=language) if mem_available else "",
                failed_count=failed_count,
                journal_metrics=journal_metrics,
                language=language,
            )
        )
    return " ".join(parts).strip()
