from __future__ import annotations

import re
from dataclasses import dataclass


_FILTER_COMMANDS = {
    "grep",
    "egrep",
    "fgrep",
    "awk",
    "head",
    "tail",
    "cut",
    "sort",
    "uniq",
    "tr",
    "wc",
}

_READONLY_COMMANDS = {
    "apt",
    "cat",
    "date",
    "df",
    "dig",
    "docker",
    "du",
    "echo",
    "env",
    "find",
    "free",
    "hostname",
    "host",
    "id",
    "ip",
    "journalctl",
    "last",
    "launchctl",
    "ls",
    "netstat",
    "nslookup",
    "printenv",
    "ps",
    "service",
    "ss",
    "stat",
    "sw_vers",
    "sysctl",
    "systemctl",
    "uname",
    "uptime",
    "w",
    "who",
}

_BLOCKED_HEADS = {
    "apt-get",
    "bash",
    "chmod",
    "chgrp",
    "chown",
    "cmd",
    "cp",
    "curl",
    "dd",
    "dfu",
    "dnf",
    "fdisk",
    "fish",
    "halt",
    "init",
    "kill",
    "killall",
    "mkfs",
    "mount",
    "mv",
    "npm",
    "pacman",
    "parted",
    "perl",
    "php",
    "pip",
    "pkill",
    "poweroff",
    "powershell",
    "pwsh",
    "python",
    "reboot",
    "rm",
    "ruby",
    "sed",
    "sh",
    "shutdown",
    "sudo",
    "tee",
    "umount",
    "wget",
    "yum",
    "zsh",
    "zypper",
}

_BLOCKED_PATTERNS = (
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|reload|try-restart|enable|disable|mask|unmask|edit|set-)\b"),
    re.compile(r"\bservice\s+(?:start|stop|restart|reload)\b"),
    re.compile(r"\bdocker\s+(?:run|start|stop|restart|rm|kill|exec|cp|compose)\b"),
    re.compile(r"\bnpm\s+install\b"),
    re.compile(r"\bpip\s+install\b"),
)

_ALLOW_SYSTEMCTL_SUBCOMMANDS = {
    "is-active",
    "is-enabled",
    "status",
    "show",
    "list-units",
    "list-unit-files",
    "list-timers",
    "list-sockets",
    "list-jobs",
    "cat",
}

_ALLOW_DOCKER_SUBCOMMANDS = {
    "images",
    "inspect",
    "logs",
    "ps",
}

_ALLOW_SERVICE_SUBCOMMANDS = {"status"}
_ALLOW_APT_SUBCOMMANDS = {"list"}
_ALLOW_LAUNCHCTL_SUBCOMMANDS = {"list", "print", "print-disabled", "blame"}
_ALLOW_IP_SUBCOMMANDS = {"a", "addr", "address", "link", "route", "r", "neigh", "neighbor", "rule"}
_BLOCKED_IP_VERBS = {"add", "del", "delete", "set", "replace", "change", "flush"}
_BLOCKED_FIND_TOKENS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprintf", "-fls"}
_ALLOW_DATE_OPTIONS = {"-u", "--utc", "-r", "-R", "-I", "--iso-8601", "--rfc-3339", "-d", "--date"}
_BLOCKED_DATE_OPTIONS = {"-s", "--set"}


@dataclass(frozen=True)
class SSHPolicyDecision:
    action: str
    reason: str
    normalized_command: str
    segments: tuple[str, ...] = ()


def normalize_ssh_command(command: str) -> str:
    return " ".join(str(command or "").strip().split())


def split_ssh_command_segments(command: str) -> tuple[str, ...]:
    clean = normalize_ssh_command(command)
    if not clean:
        return ()
    parts = [
        segment.strip()
        for segment in re.split(r"\s*(?:&&|\|\||\|)\s*", clean)
        if segment.strip()
    ]
    return tuple(parts)


def command_matches_allow_commands(command: str, allow_commands: list[str] | tuple[str, ...] | None) -> bool:
    allow_entries = [normalize_ssh_command(item) for item in list(allow_commands or []) if normalize_ssh_command(item)]
    if not allow_entries:
        return True
    clean = normalize_ssh_command(command)
    if not clean:
        return False
    if any(_segment_matches_allow_entry(clean, entry) for entry in allow_entries):
        return True
    segments = split_ssh_command_segments(clean)
    if not segments:
        return False
    return all(any(_segment_matches_allow_entry(segment, entry) for entry in allow_entries) for segment in segments)


def validate_ssh_readonly_policy(
    command: str,
    *,
    allow_commands: list[str] | tuple[str, ...] | None = None,
) -> SSHPolicyDecision:
    clean = normalize_ssh_command(command)
    if not clean:
        return SSHPolicyDecision("block", "ssh_command_empty", clean)
    if any(token in clean for token in (";", "`", "$(", "${", "\n", "\r")):
        return SSHPolicyDecision("block", "ssh_command_shell_injection", clean)
    if re.search(r"(^|[^&])&([^&]|$)", clean):
        return SSHPolicyDecision("block", "ssh_command_backgrounding_blocked", clean)

    scrubbed = re.sub(r"(?:^|\s)(?:1|2)?>>?\s*/dev/null\b", " ", clean)
    scrubbed = scrubbed.replace("&&", " ").replace("||", " ").replace("|", " ")
    if "<" in scrubbed or ">" in scrubbed:
        return SSHPolicyDecision("block", "ssh_command_redirect_blocked", clean)

    segments = split_ssh_command_segments(clean)
    if not segments:
        return SSHPolicyDecision("block", "ssh_command_empty", clean)

    matched_allow_commands = bool(allow_commands and command_matches_allow_commands(clean, allow_commands))
    if allow_commands and not matched_allow_commands:
        return SSHPolicyDecision("block", "ssh_command_not_in_allow_list", clean, segments)

    has_pipeline = "|" in clean.replace("||", "")
    has_fallback = "||" in clean
    chain_count = clean.count("&&") + clean.count("||")
    pipeline_count = clean.replace("||", "").count("|")
    unknown_heads = False

    for segment in segments:
        head = _segment_head(segment)
        if not head:
            return SSHPolicyDecision("block", "ssh_command_unknown_readonly", clean, segments)
        lowered = f" {segment.lower()} "
        if head in _BLOCKED_HEADS:
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean, segments)
        if any(pattern.search(lowered.strip()) for pattern in _BLOCKED_PATTERNS):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean, segments)
        if has_pipeline and _is_filter_only_segment(segment):
            continue
        if head not in _READONLY_COMMANDS:
            unknown_heads = True
            continue
        if head == "systemctl" and not _segment_allows_systemctl_readonly_form(segment):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean, segments)
        if head == "docker" and not _segment_allows_subcommand(segment, _ALLOW_DOCKER_SUBCOMMANDS):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean, segments)
        if head == "service" and not _segment_allows_subcommand(segment, _ALLOW_SERVICE_SUBCOMMANDS):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean, segments)
        form_decision = _validate_readonly_command_form(head, segment, clean, segments)
        if form_decision is not None:
            return form_decision

    if unknown_heads:
        return SSHPolicyDecision("ask_user", "ssh_command_unknown_readonly", clean, segments)
    if matched_allow_commands and not has_fallback and pipeline_count == 0:
        return SSHPolicyDecision("allow", "ssh_command_allow_list_allow", clean, segments)
    if has_fallback or pipeline_count > 0 or chain_count > 3 or len(segments) > 4:
        return SSHPolicyDecision("ask_user", "ssh_command_needs_confirmation", clean, segments)
    return SSHPolicyDecision("allow", "ssh_readonly_policy_allow", clean, segments)


def _segment_head(segment: str) -> str:
    parts = normalize_ssh_command(segment).split()
    return parts[0].lower() if parts else ""


def _segment_matches_allow_entry(segment: str, entry: str) -> bool:
    clean_segment = normalize_ssh_command(segment).lower()
    clean_entry = normalize_ssh_command(entry).lower()
    if not clean_segment or not clean_entry:
        return False
    return clean_segment == clean_entry or clean_segment.startswith(clean_entry + " ")


def _is_filter_only_segment(segment: str) -> bool:
    return _segment_head(segment) in _FILTER_COMMANDS


def _segment_allows_subcommand(segment: str, allowed: set[str]) -> bool:
    parts = normalize_ssh_command(segment).split()
    if len(parts) < 2:
        return False
    return parts[1].lower() in allowed


def _segment_allows_systemctl_readonly_form(segment: str) -> bool:
    if _segment_allows_subcommand(segment, _ALLOW_SYSTEMCTL_SUBCOMMANDS):
        return True
    parts = normalize_ssh_command(segment).split()[1:]
    if not parts:
        return False
    lowered = [part.lower() for part in parts]
    if any(part in _ALLOW_SYSTEMCTL_SUBCOMMANDS for part in lowered):
        return True
    allowed_option_prefixes = (
        "--failed",
        "--no-pager",
        "--all",
        "--plain",
        "--legend",
        "--no-legend",
        "--state=",
        "--type=",
    )
    return all(any(part == prefix or part.startswith(prefix) for prefix in allowed_option_prefixes) for part in lowered)


def _validate_readonly_command_form(
    head: str,
    segment: str,
    clean_command: str,
    segments: tuple[str, ...],
) -> SSHPolicyDecision | None:
    if head == "find":
        lowered_parts = {part.lower() for part in normalize_ssh_command(segment).split()[1:]}
        if lowered_parts & _BLOCKED_FIND_TOKENS:
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
        return None
    if head == "ip":
        parts = normalize_ssh_command(segment).split()[1:]
        lowered_parts = [part.lower() for part in parts]
        if any(part in _BLOCKED_IP_VERBS for part in lowered_parts):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
        subcommand = _first_non_option_token(parts)
        if subcommand and subcommand.lower() not in _ALLOW_IP_SUBCOMMANDS:
            return SSHPolicyDecision("ask_user", "ssh_command_unknown_readonly", clean_command, segments)
        return None
    if head == "sysctl":
        parts = normalize_ssh_command(segment).split()[1:]
        lowered_parts = [part.lower() for part in parts]
        if "-w" in lowered_parts or "--write" in lowered_parts:
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
        if any(re.fullmatch(r"[A-Za-z0-9_.]+=.+" , part) for part in parts):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
        return None
    if head == "date":
        parts = normalize_ssh_command(segment).split()[1:]
        lowered_parts = [part.lower() for part in parts]
        if any(part in _BLOCKED_DATE_OPTIONS for part in lowered_parts):
            return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
        positional = [part for part in parts if not part.startswith("-") and not part.startswith("+")]
        if positional:
            return SSHPolicyDecision("ask_user", "ssh_command_unknown_readonly", clean_command, segments)
        unknown_options = [part for part in lowered_parts if part.startswith("-") and part not in _ALLOW_DATE_OPTIONS]
        if unknown_options:
            return SSHPolicyDecision("ask_user", "ssh_command_unknown_readonly", clean_command, segments)
        return None
    if head == "apt" and not _segment_allows_apt_readonly_form(segment):
        return SSHPolicyDecision("block", "ssh_command_mutating_operation", clean_command, segments)
    if head == "launchctl" and not _segment_allows_subcommand(segment, _ALLOW_LAUNCHCTL_SUBCOMMANDS):
        return SSHPolicyDecision("ask_user", "ssh_command_unknown_readonly", clean_command, segments)
    return None


def _first_non_option_token(parts: list[str]) -> str:
    for part in parts:
        clean = str(part or "").strip()
        if not clean:
            continue
        if clean.startswith("-"):
            continue
        return clean
    return ""


def _segment_allows_apt_readonly_form(segment: str) -> bool:
    parts = normalize_ssh_command(segment).split()
    if len(parts) < 2 or parts[1].lower() not in _ALLOW_APT_SUBCOMMANDS:
        return False
    allowed_options = {"--upgradable", "--installed"}
    for part in parts[2:]:
        lowered = part.lower()
        if lowered.startswith("-") and lowered not in allowed_options:
            return False
    return True
