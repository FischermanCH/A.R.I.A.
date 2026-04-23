from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aria.core.capability_router import CapabilityRouter
from aria.core.capability_catalog import normalize_capability
from aria.core.connection_catalog import normalize_connection_kind
from aria.core.custom_skills import _load_custom_skill_manifests


@dataclass(slots=True)
class ActionPlanCandidate:
    candidate_kind: str
    candidate_id: str
    title: str = ""
    summary: str = ""
    intent: str = ""
    connection_kind: str = ""
    capability: str = ""
    preview: str = ""
    inputs: dict[str, str] = field(default_factory=dict)
    router_keywords: list[str] = field(default_factory=list)
    source: str = ""
    score: float = 0.0

    @property
    def key(self) -> tuple[str, str]:
        return (str(self.candidate_kind or "").strip().lower(), str(self.candidate_id or "").strip())


_ACTION_TEMPLATE_LIBRARY: dict[str, list[dict[str, Any]]] = {
    "ssh": [
        {
            "candidate_id": "ssh_health_check",
            "title": "SSH Health Check",
            "summary": "Runs a lightweight health or status check on the target host.",
            "intent": "health_check",
            "capability": "ssh_command",
            "preview": "SSH command: uptime",
            "router_keywords": [
                "health check",
                "status check",
                "uptime",
                "check server",
                "server status",
                "wie lange laeuft",
                "wie lange läuft",
                "online",
                "pruef mal",
                "prüf mal",
            ],
        },
        {
            "candidate_id": "ssh_run_command",
            "title": "SSH Run Command",
            "summary": "Runs a direct command on the target host when the request names a concrete command.",
            "intent": "run_command",
            "capability": "ssh_command",
            "preview": "SSH command from the user request",
            "router_keywords": ["run command", "execute", "fuehre aus", "führe aus", "run", "ls", "df", "systemctl"],
        },
    ],
    "sftp": [
        {
            "candidate_id": "sftp_list_files",
            "title": "SFTP List Files",
            "summary": "Lists files or directories on the target system.",
            "intent": "list_files",
            "capability": "file_list",
            "preview": "List remote files via SFTP",
            "router_keywords": ["list files", "dateien anzeigen", "liste", "verzeichnis", "ordner", "directory"],
        },
        {
            "candidate_id": "sftp_read_file",
            "title": "SFTP Read File",
            "summary": "Reads a remote file from the target system.",
            "intent": "read_file",
            "capability": "file_read",
            "preview": "Read remote file via SFTP",
            "router_keywords": ["read file", "datei lesen", "lies", "open file", "hosts datei", "config file"],
        },
        {
            "candidate_id": "sftp_write_file",
            "title": "SFTP Write File",
            "summary": "Writes prepared content back to a remote file on the target system.",
            "intent": "write_file",
            "capability": "file_write",
            "preview": "Write remote file via SFTP",
            "router_keywords": ["write file", "datei schreiben", "sync", "speichern", "save file"],
        },
    ],
    "smb": [
        {
            "candidate_id": "smb_list_files",
            "title": "SMB List Files",
            "summary": "Lists files or directories on an SMB share.",
            "intent": "list_files",
            "capability": "file_list",
            "preview": "List remote files via SMB",
            "router_keywords": ["list files", "dateien anzeigen", "share", "netzlaufwerk", "verzeichnis", "ordner"],
        },
        {
            "candidate_id": "smb_read_file",
            "title": "SMB Read File",
            "summary": "Reads a file from an SMB share.",
            "intent": "read_file",
            "capability": "file_read",
            "preview": "Read remote file via SMB",
            "router_keywords": ["read file", "datei lesen", "share", "netzlaufwerk", "open file"],
        },
        {
            "candidate_id": "smb_write_file",
            "title": "SMB Write File",
            "summary": "Writes a file to an SMB share.",
            "intent": "write_file",
            "capability": "file_write",
            "preview": "Write remote file via SMB",
            "router_keywords": ["write file", "datei schreiben", "sync", "share", "netzlaufwerk"],
        },
    ],
    "rss": [
        {
            "candidate_id": "rss_read_feed",
            "title": "RSS Read Feed",
            "summary": "Reads recent feed entries and headlines from the target feed.",
            "intent": "read_feed",
            "capability": "rss_read",
            "preview": "Read recent feed entries",
            "router_keywords": ["feed", "rss", "headlines", "latest news", "neueste meldungen", "nachrichten"],
        }
    ],
    "google_calendar": [
        {
            "candidate_id": "google_calendar_read_events",
            "title": "Google Calendar Read Events",
            "summary": "Reads upcoming appointments and events from the selected Google Calendar.",
            "intent": "read_calendar",
            "capability": "calendar_read",
            "preview": "Read upcoming events from Google Calendar",
            "router_keywords": [
                "calendar",
                "kalender",
                "termine",
                "meeting",
                "appointment",
                "heute",
                "morgen",
                "next appointment",
            ],
        }
    ],
    "discord": [
        {
            "candidate_id": "discord_send_message",
            "title": "Discord Send Message",
            "summary": "Sends a text message to the selected Discord target.",
            "intent": "send_message",
            "capability": "discord_send",
            "preview": "Send a message to Discord",
            "router_keywords": ["send message", "discord", "channel", "alert", "schick", "sende", "nachricht"],
        }
    ],
    "webhook": [
        {
            "candidate_id": "webhook_send_message",
            "title": "Webhook Send Message",
            "summary": "Sends a message or payload to the selected webhook target.",
            "intent": "send_message",
            "capability": "webhook_send",
            "preview": "Send a payload to the webhook target",
            "router_keywords": ["webhook", "hook", "callback", "send", "sende", "poste", "payload"],
        }
    ],
    "email": [
        {
            "candidate_id": "email_send_message",
            "title": "Email Send Message",
            "summary": "Sends an email through the selected SMTP profile.",
            "intent": "send_message",
            "capability": "email_send",
            "preview": "Send an email via the configured SMTP target",
            "router_keywords": ["email", "mail", "smtp", "send", "sende", "schick", "benachrichtigung"],
        }
    ],
    "imap": [
        {
            "candidate_id": "imap_read_mailbox",
            "title": "IMAP Read Mailbox",
            "summary": "Reads the latest emails from the selected mailbox.",
            "intent": "read_mail",
            "capability": "mail_read",
            "preview": "Read the latest emails from the mailbox",
            "router_keywords": ["imap", "mailbox", "postfach", "inbox", "emails lesen", "mail lesen"],
        },
        {
            "candidate_id": "imap_search_mailbox",
            "title": "IMAP Search Mailbox",
            "summary": "Searches the selected mailbox for a query.",
            "intent": "search_mail",
            "capability": "mail_search",
            "preview": "Search the mailbox with the user query",
            "router_keywords": ["imap", "mailbox", "postfach", "search mail", "suche mail", "finde emails"],
        },
    ],
    "mqtt": [
        {
            "candidate_id": "mqtt_publish_message",
            "title": "MQTT Publish Message",
            "summary": "Publishes a payload to the selected MQTT broker/topic.",
            "intent": "publish_message",
            "capability": "mqtt_publish",
            "preview": "Publish a message to the MQTT topic",
            "router_keywords": ["mqtt", "topic", "broker", "publish", "sende event", "nachricht publizieren"],
        }
    ],
    "http_api": [
        {
            "candidate_id": "http_api_request",
            "title": "HTTP API Request",
            "summary": "Calls the target API endpoint and returns the response.",
            "intent": "api_request",
            "capability": "http_api_request",
            "preview": "HTTP request to configured API target",
            "router_keywords": ["api", "call endpoint", "request", "fetch api"],
        }
    ],
}

_INTENT_HINTS: dict[str, tuple[str, ...]] = {
    "health_check": ("health", "status", "uptime", "online", "running", "laeuft", "läuft", "pruef", "prüf", "check"),
    "run_command": ("run", "execute", "fuehre", "führe", "command", "shell", "systemctl", "journalctl"),
    "list_files": ("list", "liste", "dateien", "files", "ordner", "verzeichnis", "directory"),
    "read_file": ("read", "open", "cat", "datei", "file", "hosts", "config"),
    "write_file": ("write", "save", "sync", "speicher", "schreib"),
    "read_calendar": ("calendar", "kalender", "termine", "meeting", "appointment", "agenda", "heute", "morgen", "today", "tomorrow"),
    "read_feed": ("rss", "feed", "news", "headlines", "meldungen", "nachrichten"),
    "send_message": ("send", "message", "nachricht", "discord", "channel", "alert", "notify"),
    "read_mail": ("imap", "mailbox", "postfach", "inbox", "emails", "mail lesen", "read mail"),
    "search_mail": ("imap", "mailbox", "postfach", "suche", "search", "finde", "emails"),
    "publish_message": ("mqtt", "topic", "broker", "publish", "event", "nachricht", "payload"),
    "api_request": ("api", "request", "fetch", "call", "endpoint"),
}


def _is_german_language(language: str) -> bool:
    return str(language or "").strip().lower().startswith("de")


def _localized_text(language: str, *, de: str, en: str) -> str:
    return de if _is_german_language(language) else en


def _candidate_kind_priority(value: str) -> int:
    clean = str(value or "").strip().lower()
    if clean == "template":
        return 0
    if clean == "skill":
        return 1
    return 9


def _extract_quoted_text(query: str) -> str:
    text = str(query or "")
    for pattern in (r'"([^"]+)"', r"'([^']+)'", r"“([^”]+)”"):
        match = re.search(pattern, text)
        if match:
            return str(match.group(1) or "").strip()
    return ""


def _extract_remote_path(query: str) -> str:
    text = str(query or "").strip()
    explicit = re.search(r"(?P<path>/(?:[\w.\-]+/?)+)", text)
    if explicit:
        return str(explicit.group("path") or "").strip()
    lowered = text.lower()
    known = {
        "hosts datei": "/etc/hosts",
        "hosts file": "/etc/hosts",
        "authorized_keys": "~/.ssh/authorized_keys",
        "fstab": "/etc/fstab",
        "crontab": "/etc/crontab",
        "docker compose": "docker-compose.yml",
        "compose file": "docker-compose.yml",
        "compose-datei": "docker-compose.yml",
        "config.yaml": "config.yaml",
    }
    for needle, path in known.items():
        if needle in lowered:
            return path
    return ""


def _extract_command_text(query: str) -> str:
    quoted = _extract_quoted_text(query)
    if quoted:
        return quoted
    lowered = str(query or "").strip().lower()
    known_commands = [
        "uptime",
        "df -h",
        "systemctl status",
        "systemctl is-active",
        "journalctl -xe",
        "free -h",
        "uname -a",
        "ls",
        "pwd",
    ]
    for command in known_commands:
        if command in lowered:
            return command
    match = re.search(r"(?:run|execute|fuehre aus|führe aus|befehl)\s+([a-z0-9_./:-]+(?:\s+[a-z0-9_./:=~-]+){0,4})", lowered)
    if match:
        return str(match.group(1) or "").strip()
    return CapabilityRouter._extract_natural_ssh_command(query)


def _extract_message_text(query: str) -> str:
    quoted = _extract_quoted_text(query)
    if quoted:
        return quoted
    lowered = str(query or "").strip().lower()
    if "testnachricht" in lowered or "test message" in lowered:
        return "ARIA test message"
    return ""


def _extract_mail_search_text(query: str, connection_ref: str = "") -> str:
    return CapabilityRouter._extract_mail_search_query(query, connection_ref)


def _extract_mqtt_topic_text(query: str) -> str:
    return CapabilityRouter._extract_mqtt_topic(query)


def _extract_calendar_range_text(query: str) -> str:
    return CapabilityRouter._extract_calendar_range(query)


def _extract_calendar_search_text(query: str) -> str:
    return CapabilityRouter._extract_calendar_search(query)


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    text = str(raw or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_candidate_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _safe_list(values: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = " ".join(str(value or "").strip().split())
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append(clean)
        if len(rows) >= max(1, int(limit)):
            break
    return rows


def _infer_skill_intent(manifest: dict[str, Any]) -> str:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return ""
    step_type = str((steps[0] or {}).get("type", "") or "").strip().lower()
    return {
        "ssh_run": "health_check",
        "rss_read": "read_feed",
        "discord_send": "send_message",
        "chat_send": "send_message",
        "sftp_read": "read_file",
        "smb_read": "read_file",
        "sftp_write": "write_file",
        "smb_write": "write_file",
        "llm_transform": "transform",
    }.get(step_type, "")


def _infer_skill_preview(manifest: dict[str, Any], language: str = "") -> str:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return ""
    step = dict((steps[0] or {}))
    step_type = str(step.get("type", "") or "").strip().lower()
    params = dict(step.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        return (
            f"{_localized_text(language, de='SSH-Befehl', en='SSH command')}: {command}"
            if command
            else _localized_text(language, de="SSH-Befehl aus Skill", en="SSH command from skill")
        )
    if step_type in {"sftp_read", "smb_read"}:
        path = str(params.get("remote_path", "") or "").strip()
        return (
            f"{_localized_text(language, de='Remote-Pfad lesen', en='Read remote path')}: {path}"
            if path
            else _localized_text(language, de="Remote-Datei aus Skill lesen", en="Read remote file from skill")
        )
    if step_type in {"sftp_write", "smb_write"}:
        path = str(params.get("remote_path", "") or "").strip()
        return (
            f"{_localized_text(language, de='Remote-Pfad schreiben', en='Write remote path')}: {path}"
            if path
            else _localized_text(language, de="Remote-Datei aus Skill schreiben", en="Write remote file from skill")
        )
    if step_type == "rss_read":
        return _localized_text(language, de="Feed ueber Skill lesen", en="Read feed via skill")
    if step_type == "discord_send":
        return _localized_text(language, de="Discord-Nachricht ueber Skill senden", en="Send Discord message via skill")
    if step_type == "chat_send":
        return _localized_text(language, de="Chat-Antwort ueber Skill senden", en="Send chat reply via skill")
    return step_type or _localized_text(language, de="Benutzerdefinierter Skill-Schritt", en="Custom skill step")


def _infer_skill_inputs(manifest: dict[str, Any]) -> dict[str, str]:
    steps = list(manifest.get("steps", []) or [])
    if not steps:
        return {}
    step = dict((steps[0] or {}))
    step_type = str(step.get("type", "") or "").strip().lower()
    params = dict(step.get("params", {}) or {})
    if step_type == "ssh_run":
        command = str(params.get("command", "") or "").strip()
        return {"command": command} if command else {}
    if step_type in {"sftp_read", "sftp_write", "smb_read", "smb_write"}:
        remote_path = str(params.get("remote_path", "") or "").strip()
        return {"remote_path": remote_path} if remote_path else {}
    if step_type in {"discord_send", "chat_send"}:
        message = str(params.get("message", "") or "").strip() or str(params.get("text", "") or "").strip()
        return {"message": message} if message else {}
    if step_type == "rss_read":
        limit = str(params.get("limit", "") or "").strip()
        return {"limit": limit} if limit else {}
    return {}


def _base_candidate_preview(candidate: ActionPlanCandidate, language: str = "") -> str:
    if candidate.candidate_kind == "skill":
        return candidate.preview
    candidate_id = str(candidate.candidate_id or "").strip().lower()
    if candidate_id == "ssh_health_check":
        return _localized_text(language, de="SSH-Befehl: uptime", en="SSH command: uptime")
    if candidate_id == "ssh_run_command":
        return _localized_text(language, de="SSH-Befehl aus der Benutzeranfrage", en="SSH command from the user request")
    if candidate_id == "sftp_list_files":
        return _localized_text(language, de="Dateien via SFTP anzeigen", en="List files via SFTP")
    if candidate_id == "sftp_read_file":
        return _localized_text(language, de="Remote-Datei via SFTP lesen", en="Read remote file via SFTP")
    if candidate_id == "sftp_write_file":
        return _localized_text(language, de="Remote-Datei via SFTP schreiben", en="Write remote file via SFTP")
    if candidate_id == "smb_list_files":
        return _localized_text(language, de="Dateien via SMB anzeigen", en="List files via SMB")
    if candidate_id == "smb_read_file":
        return _localized_text(language, de="Remote-Datei via SMB lesen", en="Read remote file via SMB")
    if candidate_id == "smb_write_file":
        return _localized_text(language, de="Remote-Datei via SMB schreiben", en="Write remote file via SMB")
    if candidate_id == "rss_read_feed":
        return _localized_text(language, de="Aktuelle Feed-Eintraege lesen", en="Read recent feed entries")
    if candidate_id == "google_calendar_read_events":
        return _localized_text(language, de="Kalendertermine lesen", en="Read calendar events")
    if candidate_id == "discord_send_message":
        return _localized_text(language, de="Nachricht an Discord senden", en="Send a message to Discord")
    if candidate_id == "webhook_send_message":
        return _localized_text(language, de="Payload an Webhook senden", en="Send a payload to the webhook")
    if candidate_id == "email_send_message":
        return _localized_text(language, de="E-Mail ueber SMTP senden", en="Send an email via SMTP")
    if candidate_id == "imap_read_mailbox":
        return _localized_text(language, de="Neueste E-Mails im Postfach lesen", en="Read the latest emails from the mailbox")
    if candidate_id == "imap_search_mailbox":
        return _localized_text(language, de="Postfach nach einer Anfrage durchsuchen", en="Search the mailbox with a query")
    if candidate_id == "mqtt_publish_message":
        return _localized_text(language, de="Nachricht an MQTT-Topic senden", en="Publish a message to the MQTT topic")
    if candidate_id == "http_api_request":
        return _localized_text(language, de="HTTP-Anfrage an das konfigurierte API-Ziel", en="HTTP request to configured API target")
    return candidate.preview


def _missing_required_reason(missing_input: str, language: str = "") -> str:
    label = _input_key_label(missing_input, language) or missing_input
    return _localized_text(
        language,
        de=f"Pflichtangabe fehlt: {label}.",
        en=f"Missing required {label}.",
    )


def _routing_target_confirmation_reason(language: str = "") -> str:
    return _localized_text(
        language,
        de="Das Ziel ist noch nicht eindeutig bestaetigt; ARIA sollte vor der Ausfuehrung nachfragen.",
        en="The target is not fully confirmed yet; ARIA should ask before execution.",
    )


def _heuristic_reason_text(reason: str, language: str = "") -> str:
    mapping = {
        "single_candidate": _localized_text(language, de="Nur ein passender Aktionskandidat vorhanden.", en="Only one suitable action candidate is available."),
        "no_signal": _localized_text(language, de="Die Anfrage ist fuer die Aktionswahl noch zu unscharf.", en="The request is still too vague for action selection."),
        "same_intent_clear_lead": _localized_text(language, de="Ein Kandidat fuehrt klar innerhalb desselben Intents.", en="One candidate has a clear lead within the same intent."),
        "explicit_intent_clear_lead": _localized_text(language, de="Die Anfrage benennt den Intent ausreichend klar.", en="The request states the intent clearly enough."),
        "score_gap": _localized_text(language, de="Ein Kandidat hat einen klaren Vorsprung.", en="One candidate has a clear lead."),
        "ambiguous": _localized_text(language, de="Die Anfrage bleibt fuer die Aktionswahl mehrdeutig.", en="The request remains ambiguous for action selection."),
    }
    return mapping.get(str(reason or "").strip(), str(reason or "").strip())


def _intent_score(query: str, intent: str, router_keywords: list[str]) -> float:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return 0.0
    score = 0.0
    for token in _INTENT_HINTS.get(intent, ()):
        if token in lowered:
            score += 2.0
    for keyword in router_keywords:
        clean = str(keyword or "").strip().lower()
        if clean and clean in lowered:
            score += 3.0
    return score


def _template_specific_score(candidate_id: str, query: str) -> float:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return 0.0
    clean_candidate_id = str(candidate_id or "").strip().lower()
    score = 0.0
    has_quoted_text = bool(_extract_quoted_text(query))
    has_remote_path = bool(_extract_remote_path(query))
    if clean_candidate_id == "ssh_health_check":
        if any(token in lowered for token in ("health", "status", "uptime", "online", "läuft", "laeuft")):
            score += 3.0
    elif clean_candidate_id == "ssh_run_command":
        if _extract_command_text(query):
            score += 4.0
    elif clean_candidate_id in {"sftp_list_files", "smb_list_files"}:
        if any(token in lowered for token in ("liste", "list", "dateien", "files", "ordner", "verzeichnis", "directory", "daten aus")):
            score += 4.0
        if has_remote_path:
            score += 1.0
    elif clean_candidate_id in {"sftp_read_file", "smb_read_file"}:
        if any(token in lowered for token in ("lies", "read", "zeige", "open", "cat", "lese")):
            score += 4.0
        if has_remote_path:
            score += 1.0
    elif clean_candidate_id in {"sftp_write_file", "smb_write_file"}:
        if any(token in lowered for token in ("schreib", "write", "speicher", "save", "mit inhalt", "with content")):
            score += 5.0
        if has_remote_path:
            score += 1.0
        if has_quoted_text:
            score += 2.0
    elif clean_candidate_id == "discord_send_message":
        if any(token in lowered for token in ("schick", "sende", "send", "nachricht", "message")):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif clean_candidate_id == "webhook_send_message":
        if any(token in lowered for token in ("webhook", "hook", "callback", "poste", "sende", "send", "payload")):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif clean_candidate_id == "email_send_message":
        if any(token in lowered for token in ("mail", "email", "smtp", "schick", "sende", "send")):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif clean_candidate_id == "imap_read_mailbox":
        if any(token in lowered for token in ("imap", "postfach", "mailbox", "inbox", "emails lesen", "mail lesen", "zeige emails")):
            score += 4.0
    elif clean_candidate_id == "imap_search_mailbox":
        if any(token in lowered for token in ("suche", "search", "finde", "durchsuche", "imap", "mailbox", "postfach")):
            score += 4.0
        if has_quoted_text:
            score += 1.0
    elif clean_candidate_id == "mqtt_publish_message":
        if any(token in lowered for token in ("mqtt", "topic", "broker", "publish", "publiziere", "sende", "event")):
            score += 4.0
        if _extract_mqtt_topic_text(query):
            score += 1.0
        if has_quoted_text:
            score += 1.0
    elif clean_candidate_id == "google_calendar_read_events":
        if any(token in lowered for token in ("calendar", "kalender", "termine", "meeting", "appointment", "agenda")):
            score += 4.0
        if any(token in lowered for token in ("heute", "today", "morgen", "tomorrow", "next", "naechst", "nächst")):
            score += 2.0
    elif clean_candidate_id == "rss_read_feed":
        if any(token in lowered for token in ("rss", "feed", "news", "meldungen", "headlines")):
            score += 3.0
    elif clean_candidate_id == "http_api_request":
        if any(token in lowered for token in ("api", "endpoint", "request", "call", "/health", "/status")):
            score += 4.0
    return score


def _intent_is_explicit(query: str, intent: str) -> bool:
    lowered = str(query or "").strip().lower()
    return any(token in lowered for token in _INTENT_HINTS.get(intent, ()))


def _template_candidates(query: str, *, connection_kind: str, language: str = "") -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    rows: list[ActionPlanCandidate] = []
    for raw in _ACTION_TEMPLATE_LIBRARY.get(clean_kind, []):
        keywords = _safe_list(raw.get("router_keywords", []))
        candidate = ActionPlanCandidate(
            candidate_kind="template",
            candidate_id=str(raw.get("candidate_id", "") or "").strip(),
            title=str(raw.get("title", "") or "").strip(),
            summary=str(raw.get("summary", "") or "").strip(),
            intent=str(raw.get("intent", "") or "").strip(),
            connection_kind=clean_kind,
            capability=normalize_capability(str(raw.get("capability", "") or "").strip()),
            preview=str(raw.get("preview", "") or "").strip(),
            router_keywords=keywords,
            source="built_in_template",
            score=_intent_score(query, str(raw.get("intent", "") or ""), keywords),
        )
        candidate.score += _template_specific_score(candidate.candidate_id, query)
        candidate.preview = _base_candidate_preview(candidate, language)
        rows.append(candidate)
    return rows


def _skill_candidates(query: str, *, connection_kind: str, language: str = "") -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    manifests, _ = _load_custom_skill_manifests()
    rows: list[ActionPlanCandidate] = []
    for manifest in manifests:
        if not bool(manifest.get("enabled_default", True)):
            continue
        connections = [str(item).strip().lower() for item in list(manifest.get("connections", []) or []) if str(item).strip()]
        if clean_kind and clean_kind not in connections:
            continue
        intent = _infer_skill_intent(manifest)
        keywords = _safe_list(manifest.get("router_keywords", []))
        rows.append(
            ActionPlanCandidate(
                candidate_kind="skill",
                candidate_id=str(manifest.get("id", "") or "").strip(),
                title=str(manifest.get("name", "") or "").strip(),
                summary=str(manifest.get("description", "") or "").strip(),
                intent=intent,
                connection_kind=clean_kind,
                capability=normalize_capability(str(connections[0] if connections else clean_kind)),
                preview=_infer_skill_preview(manifest, language),
                inputs=_infer_skill_inputs(manifest),
                router_keywords=keywords,
                source="custom_skill",
                score=_intent_score(query, intent, keywords),
            )
        )
    rows.sort(key=lambda item: (-float(item.score or 0.0), _candidate_kind_priority(item.candidate_kind), item.candidate_id))
    return rows[:8]


def bounded_action_candidates_for_target(
    query: str,
    *,
    connection_kind: str,
    language: str = "",
) -> list[ActionPlanCandidate]:
    clean_kind = normalize_connection_kind(connection_kind)
    if not clean_kind:
        return []
    rows = _template_candidates(query, connection_kind=clean_kind, language=language) + _skill_candidates(query, connection_kind=clean_kind, language=language)
    rows.sort(key=lambda item: (-float(item.score or 0.0), _candidate_kind_priority(item.candidate_kind), item.candidate_id))
    seen: set[tuple[str, str]] = set()
    result: list[ActionPlanCandidate] = []
    for row in rows:
        if row.key in seen:
            continue
        seen.add(row.key)
        result.append(row)
    return result[:10]


def _heuristic_action_decision(query: str, candidates: list[ActionPlanCandidate]) -> tuple[ActionPlanCandidate | None, str, bool, str]:
    if not candidates:
        return None, "", False, ""
    if len(candidates) == 1:
        return candidates[0], "high", False, "single_candidate"

    ordered = sorted(
        candidates,
        key=lambda item: (-float(item.score or 0.0), _candidate_kind_priority(item.candidate_kind), item.candidate_id),
    )
    top = ordered[0]
    second = ordered[1]
    top_score = float(top.score or 0.0)
    second_score = float(second.score or 0.0)
    gap = top_score - second_score
    explicit_intent = _intent_is_explicit(query, top.intent)
    same_intent = bool(top.intent and top.intent == second.intent)

    if top_score <= 0 and second_score <= 0:
        return top, "low", True, "no_signal"
    if same_intent and gap >= 1.0:
        return top, "medium", False, "same_intent_clear_lead"
    if explicit_intent and gap >= 1.0:
        return top, "medium", False, "explicit_intent_clear_lead"
    if gap >= 2.0:
        return top, "medium", False, "score_gap"
    return top, "low", True, "ambiguous"


def _recover_llm_candidate_selection(
    *,
    candidate_kind: str,
    candidate_id: str,
    intent: str,
    candidates: list[ActionPlanCandidate],
    heuristic_candidate: ActionPlanCandidate | None = None,
    heuristic_ask_user: bool = False,
) -> tuple[ActionPlanCandidate | None, str]:
    clean_kind = str(candidate_kind or "").strip().lower()
    clean_id = str(candidate_id or "").strip()
    clean_intent = str(intent or "").strip().lower()
    normalized_id = _normalize_candidate_token(clean_id)

    if clean_kind and normalized_id:
        same_kind = [candidate for candidate in candidates if candidate.candidate_kind == clean_kind]
        exact_normalized = [
            candidate
            for candidate in same_kind
            if _normalize_candidate_token(candidate.candidate_id) == normalized_id
        ]
        if len(exact_normalized) == 1:
            return exact_normalized[0], "normalized_candidate_id"
        fuzzy = [
            candidate
            for candidate in same_kind
            if normalized_id in _normalize_candidate_token(candidate.candidate_id)
            or _normalize_candidate_token(candidate.candidate_id) in normalized_id
        ]
        if len(fuzzy) == 1:
            return fuzzy[0], "fuzzy_candidate_id"

    if clean_intent:
        intent_matches = [
            candidate
            for candidate in candidates
            if (not clean_kind or candidate.candidate_kind == clean_kind) and candidate.intent == clean_intent
        ]
        if len(intent_matches) == 1:
            return intent_matches[0], "intent_match"
        if len(intent_matches) > 1:
            ordered = sorted(
                intent_matches,
                key=lambda item: (-float(item.score or 0.0), _candidate_kind_priority(item.candidate_kind), item.candidate_id),
            )
            top = ordered[0]
            second = ordered[1]
            if float(top.score or 0.0) - float(second.score or 0.0) >= 1.0:
                return top, "intent_clear_lead"

    if heuristic_candidate is not None and not heuristic_ask_user:
        if (not clean_kind or heuristic_candidate.candidate_kind == clean_kind) and (
            not clean_intent or heuristic_candidate.intent == clean_intent
        ):
            return heuristic_candidate, "heuristic_clear_fallback"

    return None, ""


def _candidate_rows_for_prompt(candidates: list[ActionPlanCandidate], language: str = "") -> list[str]:
    rows: list[str] = []
    for index, candidate in enumerate(candidates, start=1):
        parts = [
            f"{index}. {candidate.candidate_kind}/{candidate.candidate_id}",
            f"title={candidate.title or '-'}",
            f"intent={candidate.intent or '-'}",
            f"connection_kind={candidate.connection_kind or '-'}",
        ]
        if candidate.capability:
            parts.append(f"capability={candidate.capability}")
        if candidate.summary:
            parts.append(f"summary={candidate.summary}")
        preview = _derive_candidate_preview(candidate, "", language)
        if preview:
            parts.append(f"preview={preview}")
        if candidate.router_keywords:
            parts.append("router_keywords=" + ", ".join(candidate.router_keywords))
        rows.append(" | ".join(parts))
    return rows


def _candidate_payload(candidate: ActionPlanCandidate) -> dict[str, Any]:
    return {
        "found": True,
        "candidate_kind": candidate.candidate_kind,
        "candidate_kind_label": "",
        "candidate_id": candidate.candidate_id,
        "title": candidate.title,
        "intent": candidate.intent,
        "intent_label": "",
        "connection_kind": candidate.connection_kind,
        "capability": candidate.capability,
        "capability_label": "",
        "preview": candidate.preview,
        "inputs": dict(candidate.inputs or {}),
        "input_items": [],
        "score": float(candidate.score or 0.0),
        "execution_state": "",
        "execution_state_label": "",
        "summary_line": "",
        "missing_input": "",
        "missing_input_label": "",
        "clarifying_question": "",
        "example_prompt": "",
        "reason": "",
    }


def _derive_candidate_preview(candidate: ActionPlanCandidate, query: str, language: str = "") -> str:
    if candidate.candidate_kind == "skill":
        return candidate.preview
    candidate_id = str(candidate.candidate_id or "").strip().lower()
    if candidate_id == "ssh_health_check":
        return _localized_text(language, de="SSH-Befehl: uptime", en="SSH command: uptime")
    if candidate_id == "ssh_run_command":
        command = _extract_command_text(query)
        prefix = _localized_text(language, de="SSH-Befehl", en="SSH command")
        return f"{prefix}: {command}" if command else _base_candidate_preview(candidate, language)
    if candidate_id in {"sftp_list_files", "smb_list_files"}:
        path = _extract_remote_path(query) or "."
        prefix = _localized_text(language, de="Remote-Pfad anzeigen", en="List remote path")
        return f"{prefix}: {path}"
    if candidate_id in {"sftp_read_file", "smb_read_file"}:
        path = _extract_remote_path(query)
        prefix = _localized_text(language, de="Remote-Pfad lesen", en="Read remote path")
        return f"{prefix}: {path}" if path else _base_candidate_preview(candidate, language)
    if candidate_id in {"sftp_write_file", "smb_write_file"}:
        path = _extract_remote_path(query)
        prefix = _localized_text(language, de="Remote-Pfad schreiben", en="Write remote path")
        return f"{prefix}: {path}" if path else _base_candidate_preview(candidate, language)
    if candidate_id == "discord_send_message":
        message = _extract_message_text(query)
        prefix = _localized_text(language, de="Discord-Nachricht", en="Discord message")
        return f'{prefix}: "{message}"' if message else _base_candidate_preview(candidate, language)
    if candidate_id == "webhook_send_message":
        message = _extract_message_text(query)
        prefix = _localized_text(language, de="Webhook-Payload", en="Webhook payload")
        return f'{prefix}: "{message}"' if message else _base_candidate_preview(candidate, language)
    if candidate_id == "email_send_message":
        message = _extract_message_text(query)
        prefix = _localized_text(language, de="E-Mail-Inhalt", en="Email content")
        return f'{prefix}: "{message}"' if message else _base_candidate_preview(candidate, language)
    if candidate_id == "imap_search_mailbox":
        search = _extract_mail_search_text(query)
        prefix = _localized_text(language, de="Mailbox-Suche", en="Mailbox search")
        return f"{prefix}: {search}" if search else _base_candidate_preview(candidate, language)
    if candidate_id == "mqtt_publish_message":
        topic = _extract_mqtt_topic_text(query)
        prefix = _localized_text(language, de="MQTT-Topic", en="MQTT topic")
        return f"{prefix}: {topic}" if topic else _base_candidate_preview(candidate, language)
    if candidate_id == "google_calendar_read_events":
        range_hint = _extract_calendar_range_text(query)
        search = _extract_calendar_search_text(query)
        range_labels = {
            "today": _localized_text(language, de="Heute", en="Today"),
            "tomorrow": _localized_text(language, de="Morgen", en="Tomorrow"),
            "day_after_tomorrow": _localized_text(language, de="Übermorgen", en="Day after tomorrow"),
            "this_week": _localized_text(language, de="Diese Woche", en="This week"),
            "next_week": _localized_text(language, de="Nächste Woche", en="Next week"),
            "next": _localized_text(language, de="Nächster Termin", en="Next appointment"),
            "upcoming": _localized_text(language, de="Anstehende Termine", en="Upcoming events"),
        }
        label = range_labels.get(range_hint, range_labels["upcoming"])
        prefix = _localized_text(language, de="Kalender", en="Calendar")
        return f"{prefix}: {label}" + (f" · {search}" if search else "")
    return _base_candidate_preview(candidate, language)


def _derive_candidate_inputs(candidate: ActionPlanCandidate, query: str) -> dict[str, str]:
    if candidate.candidate_kind == "skill":
        return dict(candidate.inputs or {})
    candidate_id = str(candidate.candidate_id or "").strip().lower()
    if candidate_id in {"ssh_health_check"}:
        return {"command": "uptime"}
    if candidate_id == "ssh_run_command":
        command = _extract_command_text(query)
        return {"command": command} if command else {}
    if candidate_id in {"sftp_list_files", "smb_list_files"}:
        path = _extract_remote_path(query)
        return {"remote_path": path} if path else {}
    if candidate_id in {"sftp_read_file", "sftp_write_file", "smb_read_file", "smb_write_file"}:
        path = _extract_remote_path(query)
        return {"remote_path": path} if path else {}
    if candidate_id == "google_calendar_read_events":
        rows = {"range": _extract_calendar_range_text(query) or "upcoming"}
        search = _extract_calendar_search_text(query)
        if search:
            rows["search_query"] = search
        return rows
    if candidate_id == "discord_send_message":
        message = _extract_message_text(query)
        return {"message": message} if message else {}
    if candidate_id in {"webhook_send_message", "email_send_message"}:
        message = _extract_message_text(query)
        return {"message": message} if message else {}
    if candidate_id == "imap_search_mailbox":
        search = _extract_mail_search_text(query)
        return {"search_query": search} if search else {}
    if candidate_id == "mqtt_publish_message":
        rows: dict[str, str] = {}
        topic = _extract_mqtt_topic_text(query)
        message = _extract_message_text(query)
        if topic:
            rows["topic"] = topic
        if message:
            rows["message"] = message
        return rows
    return {}


def _missing_required_input(candidate: ActionPlanCandidate, query: str, *, connection_ref: str = "") -> str:
    if candidate.candidate_kind == "skill":
        return ""
    candidate_id = str(candidate.candidate_id or "").strip().lower()
    if candidate_id == "ssh_run_command":
        return "" if _extract_command_text(query) else "command"
    if candidate_id in {"sftp_read_file", "sftp_write_file", "smb_read_file", "smb_write_file"}:
        return "" if _extract_remote_path(query) else "remote_path"
    if candidate_id == "discord_send_message":
        return "" if _extract_message_text(query) else "message"
    if candidate_id in {"webhook_send_message", "email_send_message"}:
        return "" if _extract_message_text(query) else "message"
    if candidate_id == "imap_search_mailbox":
        return "" if _extract_mail_search_text(query) else "search_query"
    if candidate_id == "mqtt_publish_message":
        if not _extract_mqtt_topic_text(query) and not str(connection_ref or "").strip():
            return "topic"
        return "" if _extract_message_text(query) else "message"
    return ""


def _execution_state(*, ask_user: bool = False, missing_input: str = "") -> str:
    if str(missing_input or "").strip():
        return "needs_input"
    if ask_user:
        return "needs_confirmation"
    return "ready"


def _execution_state_label(state: str, language: str = "") -> str:
    clean = str(state or "").strip().lower()
    mapping = {
        "ready": _localized_text(language, de="Bereit", en="Ready"),
        "needs_input": _localized_text(language, de="Braucht Eingabe", en="Needs input"),
        "needs_confirmation": _localized_text(language, de="Braucht Bestaetigung", en="Needs confirmation"),
    }
    return mapping.get(clean, clean)


def _planner_source_label(source: str, language: str = "") -> str:
    clean = str(source or "").strip().lower()
    mapping = {
        "heuristic": _localized_text(language, de="Heuristik", en="Heuristic"),
        "llm": "LLM",
        "catalog": _localized_text(language, de="Katalog", en="Catalog"),
    }
    return mapping.get(clean, clean)


def _candidate_kind_label(kind: str, language: str = "") -> str:
    clean = str(kind or "").strip().lower()
    mapping = {
        "template": _localized_text(language, de="Template", en="Template"),
        "skill": _localized_text(language, de="Skill", en="Skill"),
    }
    return mapping.get(clean, clean)


def _intent_label(intent: str, language: str = "") -> str:
    clean = str(intent or "").strip().lower()
    mapping = {
        "health_check": _localized_text(language, de="Gesundheitscheck", en="Health check"),
        "run_command": _localized_text(language, de="Kommando ausfuehren", en="Run command"),
        "list_files": _localized_text(language, de="Dateien anzeigen", en="List files"),
        "read_file": _localized_text(language, de="Datei lesen", en="Read file"),
        "write_file": _localized_text(language, de="Datei schreiben", en="Write file"),
        "read_calendar": _localized_text(language, de="Kalender lesen", en="Read calendar"),
        "read_feed": _localized_text(language, de="Feed lesen", en="Read feed"),
        "send_message": _localized_text(language, de="Nachricht senden", en="Send message"),
        "read_mail": _localized_text(language, de="Postfach lesen", en="Read mailbox"),
        "search_mail": _localized_text(language, de="Postfach durchsuchen", en="Search mailbox"),
        "publish_message": _localized_text(language, de="Nachricht publizieren", en="Publish message"),
        "api_request": _localized_text(language, de="API-Anfrage", en="API request"),
        "transform": _localized_text(language, de="Transformieren", en="Transform"),
    }
    return mapping.get(clean, clean)


def _capability_label(capability: str, language: str = "") -> str:
    clean = str(capability or "").strip().lower()
    mapping = {
        "ssh_command": _localized_text(language, de="SSH-Befehl", en="SSH command"),
        "ssh": "SSH",
        "file_read": _localized_text(language, de="Datei lesen", en="Read file"),
        "file_write": _localized_text(language, de="Datei schreiben", en="Write file"),
        "sftp": "SFTP",
        "smb": "SMB",
        "calendar_read": _localized_text(language, de="Kalendertermine lesen", en="Read calendar events"),
        "google_calendar": _localized_text(language, de="Google Kalender", en="Google Calendar"),
        "discord_send": _localized_text(language, de="Discord-Nachricht senden", en="Send Discord message"),
        "discord": "Discord",
        "rss_read": _localized_text(language, de="Feed lesen", en="Read feed"),
        "rss": "RSS",
        "webhook_send": _localized_text(language, de="Webhook senden", en="Send webhook"),
        "webhook": "Webhook",
        "email_send": _localized_text(language, de="E-Mail senden", en="Send email"),
        "email": _localized_text(language, de="E-Mail", en="Email"),
        "mail_read": _localized_text(language, de="Postfach lesen", en="Read mailbox"),
        "mail_search": _localized_text(language, de="Postfach durchsuchen", en="Search mailbox"),
        "imap": "IMAP",
        "mqtt_publish": _localized_text(language, de="MQTT-Nachricht senden", en="Publish MQTT message"),
        "mqtt": "MQTT",
        "http_api_request": _localized_text(language, de="HTTP-API-Anfrage", en="HTTP API request"),
        "http_api": _localized_text(language, de="HTTP-API", en="HTTP API"),
        "chat_send": _localized_text(language, de="Chat-Antwort senden", en="Send chat reply"),
    }
    return mapping.get(clean, clean)


def _input_key_label(key: str, language: str = "") -> str:
    clean = str(key or "").strip().lower()
    mapping = {
        "command": _localized_text(language, de="Befehl", en="Command"),
        "connection_ref": _localized_text(language, de="Zielprofil", en="Target profile"),
        "remote_path": _localized_text(language, de="Remote-Pfad", en="Remote path"),
        "message": _localized_text(language, de="Nachricht", en="Message"),
        "range": _localized_text(language, de="Zeitraum", en="Range"),
        "search_query": _localized_text(language, de="Suchanfrage", en="Search query"),
        "topic": _localized_text(language, de="Topic", en="Topic"),
        "limit": _localized_text(language, de="Limit", en="Limit"),
    }
    return mapping.get(clean, clean)


def _plan_summary_line(
    *,
    candidate_kind_label: str = "",
    intent_label: str = "",
    capability_label: str = "",
    target_context: str = "",
    language: str = "",
) -> str:
    clean_kind = str(candidate_kind_label or "").strip()
    clean_intent = str(intent_label or "").strip()
    clean_capability = str(capability_label or "").strip()
    clean_target = str(target_context or "").strip()
    action_label = clean_intent or clean_capability
    capability_duplicate = _labels_are_semantically_duplicate(clean_intent, clean_capability)
    if clean_capability and not capability_duplicate and action_label:
        connector = _localized_text(language, de=" via ", en=" via ")
        action_label = f"{action_label}{connector}{clean_capability}"
    elif not action_label:
        action_label = clean_kind
        clean_kind = ""
    prefix = f"{clean_kind}: " if clean_kind and action_label else clean_kind
    target_suffix = ""
    if clean_target:
        target_suffix = _localized_text(language, de=f" auf {clean_target}", en=f" on {clean_target}")
    return f"{prefix}{action_label}{target_suffix}".strip()


def _labels_are_semantically_duplicate(primary: str, secondary: str) -> bool:
    clean_primary = str(primary or "").strip().lower()
    clean_secondary = str(secondary or "").strip().lower()
    if not clean_primary or not clean_secondary:
        return False
    if clean_primary == clean_secondary:
        return True
    primary_tokens = {token for token in re.split(r"[^a-z0-9]+", clean_primary) if token}
    secondary_tokens = {token for token in re.split(r"[^a-z0-9]+", clean_secondary) if token}
    if not primary_tokens or not secondary_tokens:
        return False
    return primary_tokens.issubset(secondary_tokens) or secondary_tokens.issubset(primary_tokens)


def _serialize_input_items(inputs: dict[str, str], language: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in (inputs or {}).items():
        clean_key = str(key or "").strip()
        clean_value = str(value or "").strip()
        if not clean_key:
            continue
        rows.append(
            {
                "key": clean_key,
                "key_label": _input_key_label(clean_key, language),
                "value": clean_value,
            }
        )
    return rows


def _apply_candidate_labels(
    payload: dict[str, Any],
    candidate: ActionPlanCandidate,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
) -> str:
    payload["candidate_kind_label"] = _candidate_kind_label(candidate.candidate_kind, language)
    payload["intent_label"] = _intent_label(str(payload.get("intent") or candidate.intent), language)
    payload["capability_label"] = _capability_label(candidate.capability, language)
    payload["preview"] = _derive_candidate_preview(candidate, query, language)
    payload["inputs"] = _derive_candidate_inputs(candidate, query)
    payload["input_items"] = _serialize_input_items(payload["inputs"], language)
    missing_input = _missing_required_input(candidate, query, connection_ref=connection_ref)
    payload["missing_input_label"] = _input_key_label(missing_input, language)
    payload["summary_line"] = _plan_summary_line(
        candidate_kind_label=str(payload.get("candidate_kind_label") or ""),
        intent_label=str(payload.get("intent_label") or ""),
        capability_label=str(payload.get("capability_label") or ""),
        target_context=target_context,
        language=language,
    )
    return missing_input


def _build_serialized_candidate(
    candidate: ActionPlanCandidate,
    query: str,
    *,
    language: str = "",
    connection_ref: str = "",
    target_context: str = "",
) -> dict[str, Any]:
    payload = _candidate_payload(candidate)
    missing_input = _apply_candidate_labels(
        payload,
        candidate,
        query,
        language=language,
        connection_ref=connection_ref,
        target_context=target_context,
    )
    execution_state = _execution_state(missing_input=missing_input)
    payload["execution_state"] = execution_state
    payload["execution_state_label"] = _execution_state_label(execution_state, language)
    payload["missing_input"] = missing_input
    payload["clarifying_question"] = _clarifying_question(candidate, missing_input, language) if missing_input else ""
    payload["example_prompt"] = (
        _suggested_follow_up_prompt(
            query,
            candidate,
            connection_ref=connection_ref,
            missing_input=missing_input,
            language=language,
        )
        if missing_input
        else ""
    )
    return payload


def _confidence_label(confidence: str, language: str = "") -> str:
    clean = str(confidence or "").strip().lower()
    mapping = {
        "high": _localized_text(language, de="Hoch", en="High"),
        "medium": _localized_text(language, de="Mittel", en="Medium"),
        "low": _localized_text(language, de="Niedrig", en="Low"),
    }
    return mapping.get(clean, clean)


def _execution_state_rank(state: str) -> int:
    clean = str(state or "").strip().lower()
    return {
        "ready": 0,
        "needs_confirmation": 1,
        "needs_input": 2,
    }.get(clean, 9)


def _target_context(kind: str, ref: str) -> str:
    clean_kind = str(kind or "").strip()
    clean_ref = str(ref or "").strip()
    if clean_kind and clean_ref:
        return f"{clean_kind}/{clean_ref}"
    return clean_ref or clean_kind


def _sort_serialized_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        list(rows or []),
        key=lambda item: (
            _execution_state_rank(str(item.get("execution_state", "") or "")),
            _candidate_kind_priority(str(item.get("candidate_kind", "") or "")),
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("candidate_id", "") or ""),
        ),
    )


def _clarifying_question(candidate: ActionPlanCandidate, missing_input: str, language: str = "") -> str:
    if missing_input == "command":
        return _localized_text(language, de="Welchen Befehl soll ARIA auf diesem Ziel ausfuehren?", en="Which command should ARIA run on this target?")
    if missing_input == "remote_path":
        if str(candidate.intent or "").strip().lower() == "write_file":
            return _localized_text(language, de="Auf welchen Remote-Pfad soll ARIA schreiben?", en="Which remote path should ARIA write to?")
        return _localized_text(language, de="Welchen Remote-Pfad soll ARIA lesen?", en="Which remote path should ARIA read?")
    if missing_input == "message":
        return _localized_text(language, de="Welche Nachricht soll ARIA senden?", en="What message should ARIA send?")
    if missing_input == "search_query":
        return _localized_text(language, de="Wonach soll ARIA im Postfach suchen?", en="What should ARIA search for in the mailbox?")
    if missing_input == "topic":
        return _localized_text(language, de="Auf welches MQTT-Topic soll ARIA senden?", en="Which MQTT topic should ARIA publish to?")
    return _localized_text(language, de="Was genau soll ARIA auf diesem Ziel tun?", en="What exactly should ARIA do on this target?")


def _follow_up_target_phrase(query: str, connection_ref: str, *, mode: str, language: str = "") -> str:
    lowered = str(query or "").strip().lower()
    clean_ref = str(connection_ref or "").strip()
    if mode == "read":
        if "management server" in lowered:
            return _localized_text(language, de="vom management server", en="from the management server")
        if "pi-hole" in lowered or "pi hole" in lowered:
            return _localized_text(language, de="vom pi-hole", en="from the pi-hole")
        return _localized_text(language, de=f"von {clean_ref}", en=f"from {clean_ref}") if clean_ref else _localized_text(language, de="von diesem Ziel", en="from this target")
    if mode == "write":
        if "management server" in lowered:
            return _localized_text(language, de="auf den management server", en="to the management server")
        return _localized_text(language, de=f"auf {clean_ref}", en=f"to {clean_ref}") if clean_ref else _localized_text(language, de="auf dieses Ziel", en="to this target")
    if mode == "message":
        if "alerts channel" in lowered:
            return _localized_text(language, de="an meinen alerts channel", en="to my alerts channel")
        if "channel" in lowered:
            return _localized_text(language, de="an den Kanal", en="to the channel")
        return _localized_text(language, de=f"an {clean_ref}", en=f"to {clean_ref}") if clean_ref else _localized_text(language, de="an dieses Ziel", en="to this target")
    if "pi-hole" in lowered or "pi hole" in lowered:
        return _localized_text(language, de="auf dem pi-hole", en="on the pi-hole")
    if "dns server" in lowered or "dns-server" in lowered:
        return _localized_text(language, de="auf dem DNS-Server", en="on the DNS server")
    return _localized_text(language, de=f"auf {clean_ref}", en=f"on {clean_ref}") if clean_ref else _localized_text(language, de="auf diesem Ziel", en="on this target")


def _suggested_follow_up_prompt(
    query: str,
    candidate: ActionPlanCandidate,
    *,
    connection_ref: str,
    missing_input: str = "",
    language: str = "",
) -> str:
    candidate_id = str(candidate.candidate_id or "").strip().lower()
    if candidate_id == "ssh_run_command":
        target = _follow_up_target_phrase(query, connection_ref, mode="ssh", language=language)
        return _localized_text(language, de=f'Fuehre "df -h" {target} aus', en=f'Run "df -h" {target}')
    if candidate_id == "ssh_health_check":
        if connection_ref:
            return _localized_text(language, de=f"Wie lange laeuft {connection_ref} schon?", en=f"How long has {connection_ref} been running?")
        return _localized_text(language, de="Wie lange laeuft der Server schon?", en="How long has the server been running?")
    if candidate_id in {"sftp_read_file", "smb_read_file"}:
        target = _follow_up_target_phrase(query, connection_ref, mode="read", language=language)
        example_path = "/etc/hosts" if missing_input == "remote_path" else (_extract_remote_path(query) or "/etc/hosts")
        return _localized_text(language, de=f"Lies {example_path} {target}", en=f"Read {example_path} {target}")
    if candidate_id in {"sftp_write_file", "smb_write_file"}:
        target = _follow_up_target_phrase(query, connection_ref, mode="write", language=language)
        example_path = "/tmp/example.txt" if missing_input == "remote_path" else (_extract_remote_path(query) or "/tmp/example.txt")
        return _localized_text(language, de=f'Schreibe "..." nach {example_path} {target}', en=f'Write "..." to {example_path} {target}')
    if candidate_id == "discord_send_message":
        target = _follow_up_target_phrase(query, connection_ref, mode="message", language=language)
        message = _extract_message_text(query) or "ARIA lebt"
        return _localized_text(language, de=f'Schick {target} "{message}"', en=f'Send {target} "{message}"')
    if candidate_id == "webhook_send_message":
        message = _extract_message_text(query) or "ARIA webhook test"
        clean_ref = str(connection_ref or "").strip()
        return _localized_text(language, de=f'Sende an {clean_ref or "den Webhook"} "{message}"', en=f'Send to {clean_ref or "the webhook"} "{message}"')
    if candidate_id == "email_send_message":
        message = _extract_message_text(query) or "ARIA Mail-Test"
        clean_ref = str(connection_ref or "").strip()
        return _localized_text(language, de=f'Sende ueber {clean_ref or "das Mail-Profil"} "{message}"', en=f'Send via {clean_ref or "the mail profile"} "{message}"')
    if candidate_id == "imap_read_mailbox":
        clean_ref = str(connection_ref or "").strip()
        return _localized_text(language, de=f"Lies die neuesten E-Mails aus {clean_ref}" if clean_ref else "Lies die neuesten E-Mails aus dem Postfach", en=f"Read the latest emails from {clean_ref}" if clean_ref else "Read the latest emails from the mailbox")
    if candidate_id == "imap_search_mailbox":
        clean_ref = str(connection_ref or "").strip()
        search = _extract_mail_search_text(query) or "Rechnung"
        return _localized_text(language, de=f'Suche in {clean_ref or "dem Postfach"} nach "{search}"', en=f'Search {clean_ref or "the mailbox"} for "{search}"')
    if candidate_id == "mqtt_publish_message":
        clean_ref = str(connection_ref or "").strip()
        topic = _extract_mqtt_topic_text(query) or "aria/events"
        message = _extract_message_text(query) or "ARIA Event"
        return _localized_text(language, de=f'Sende ueber {clean_ref or "MQTT"} an Topic {topic} "{message}"', en=f'Publish via {clean_ref or "MQTT"} to topic {topic} "{message}"')
    if candidate_id == "google_calendar_read_events":
        clean_ref = str(connection_ref or "").strip()
        range_hint = _extract_calendar_range_text(query) or "today"
        examples = {
            "today": _localized_text(language, de="Was steht heute in meinem Kalender?", en="What is on my calendar today?"),
            "tomorrow": _localized_text(language, de="Was habe ich morgen im Kalender?", en="What do I have on my calendar tomorrow?"),
            "next": _localized_text(language, de="Wann ist mein nächster Termin?", en="When is my next appointment?"),
        }
        return examples.get(
            range_hint,
            _localized_text(
                language,
                de=f"Zeig mir die nächsten Termine aus {clean_ref}" if clean_ref else "Zeig mir die nächsten Termine",
                en=f"Show me the next events from {clean_ref}" if clean_ref else "Show me my next events",
            ),
        )
    if candidate_id == "rss_read_feed":
        clean_ref = str(connection_ref or "").strip()
        return _localized_text(language, de=f"Lies die neuesten Meldungen aus {clean_ref}" if clean_ref else "Lies die neuesten Meldungen aus dem Feed", en=f"Read the latest headlines from {clean_ref}" if clean_ref else "Read the latest headlines from the feed")
    if candidate_id == "http_api_request":
        clean_ref = str(connection_ref or "").strip()
        return _localized_text(language, de=f"Rufe den Status-Endpunkt von {clean_ref} ab" if clean_ref else "Rufe den Status-Endpunkt ab", en=f"Call the status endpoint on {clean_ref}" if clean_ref else "Call the status endpoint")
    return ""


def _result_payload(
    *,
    available: bool,
    used: bool,
    status: str,
    message: str,
    decision: dict[str, Any] | None = None,
    confidence: str = "",
    confidence_label: str = "",
    ask_user: bool = False,
    execution_state: str = "",
    execution_state_label: str = "",
    planner_source: str = "",
    planner_source_label: str = "",
    candidate_count: int = 0,
    candidates: list[dict[str, Any]] | None = None,
    target_context: str = "",
    target_reason: str = "",
    missing_input: str = "",
    missing_input_label: str = "",
    clarifying_question: str = "",
    example_prompt: str = "",
    raw_response: str = "",
) -> dict[str, Any]:
    clean_status = str(status or "warn").strip().lower() or "warn"
    return {
        "available": bool(available),
        "used": bool(used),
        "status": clean_status,
        "visual_status": clean_status,
        "message": str(message or "").strip(),
        "decision": dict(decision or {}),
        "confidence": str(confidence or "").strip().lower(),
        "confidence_label": str(confidence_label or "").strip(),
        "ask_user": bool(ask_user),
        "execution_state": str(execution_state or "").strip().lower(),
        "execution_state_label": str(execution_state_label or "").strip(),
        "planner_source": str(planner_source or "").strip().lower(),
        "planner_source_label": str(planner_source_label or "").strip(),
        "candidate_count": int(candidate_count or 0),
        "candidates": list(candidates or []),
        "target_context": str(target_context or "").strip(),
        "target_reason": str(target_reason or "").strip(),
        "missing_input": str(missing_input or "").strip(),
        "missing_input_label": str(missing_input_label or "").strip(),
        "clarifying_question": str(clarifying_question or "").strip(),
        "example_prompt": str(example_prompt or "").strip(),
        "raw_response": str(raw_response or "").strip(),
    }


async def debug_bounded_action_plan_decision(
    query: str,
    *,
    llm_client: Any | None,
    routing_decision: dict[str, Any] | None = None,
    language: str = "",
) -> dict[str, Any]:
    clean_query = str(query or "").strip()
    decision = dict(routing_decision or {})
    if not bool(decision.get("found")):
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message=_localized_text(language, de="Action-Dry-run uebersprungen: Zuerst wurde kein Routing-Ziel aufgeloest.", en="Action dry-run skipped: no routing target was resolved first."),
        )

    connection_kind = normalize_connection_kind(str(decision.get("kind", "") or ""))
    connection_ref = str(decision.get("ref", "") or "").strip()
    target_context = _target_context(connection_kind, connection_ref)
    target_reason = str(decision.get("reason", "") or "").strip()
    routing_requires_confirmation = bool(
        decision.get("routing_ask_user")
        or decision.get("llm_ask_user")
        or decision.get("target_ask_user")
    )
    candidates = bounded_action_candidates_for_target(clean_query, connection_kind=connection_kind, language=language)
    serialized_candidates = _sort_serialized_candidates(
        [
            _build_serialized_candidate(
                candidate,
                clean_query,
                language=language,
                connection_ref=connection_ref,
            )
            for candidate in candidates
        ]
    )
    if not candidates:
        return _result_payload(
            available=True,
            used=False,
            status="warn",
            message=_localized_text(
                language,
                de=f"Action-Dry-run uebersprungen: Keine passenden Templates oder Skills fuer {connection_kind}/{connection_ref} gefunden.",
                en=f"Action dry-run skipped: no compatible templates or skills were found for {connection_kind}/{connection_ref}.",
            ),
            planner_source="catalog",
            planner_source_label=_planner_source_label("catalog", language),
            candidate_count=0,
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    valid_by_key = {candidate.key: candidate for candidate in candidates}
    heuristic_candidate, heuristic_confidence, heuristic_ask_user, heuristic_reason = _heuristic_action_decision(clean_query, candidates)
    if llm_client is None:
        if heuristic_candidate is not None and not heuristic_ask_user:
            payload = _candidate_payload(heuristic_candidate)
            missing_input = _apply_candidate_labels(
                payload,
                heuristic_candidate,
                clean_query,
                language=language,
                target_context=target_context,
            )
            payload["execution_state"] = _execution_state(ask_user=bool(missing_input), missing_input=missing_input)
            payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
            if missing_input:
                payload["reason"] = _missing_required_reason(missing_input, language)
                return _result_payload(
                    available=False,
                    used=False,
                    status="warn",
                    message=_localized_text(language, de="Action-Dry-run empfiehlt vor der Ausfuehrung eine Rueckfrage.", en="Action dry-run recommends asking the user before execution."),
                    decision=payload,
                    confidence="low",
                    confidence_label=_confidence_label("low", language),
                    ask_user=True,
                    execution_state=_execution_state(ask_user=True, missing_input=missing_input),
                    execution_state_label=_execution_state_label(_execution_state(ask_user=True, missing_input=missing_input), language),
                    planner_source="heuristic",
                    planner_source_label=_planner_source_label("heuristic", language),
                    candidate_count=len(candidates),
                    candidates=serialized_candidates,
                    target_context=target_context,
                    target_reason=target_reason,
                    missing_input=missing_input,
                    missing_input_label=_input_key_label(missing_input, language),
                    clarifying_question=_clarifying_question(heuristic_candidate, missing_input, language),
                    example_prompt=_suggested_follow_up_prompt(clean_query, heuristic_candidate, connection_ref=connection_ref, missing_input=missing_input, language=language),
                )
            effective_ask_user = routing_requires_confirmation
            payload["reason"] = (
                _routing_target_confirmation_reason(language)
                if routing_requires_confirmation
                else payload["preview"] or heuristic_candidate.title or _heuristic_reason_text(heuristic_reason, language)
            )
            return _result_payload(
                available=False,
                used=False,
                status="warn" if effective_ask_user else "ok",
                message=(
                    _localized_text(
                        language,
                        de="Heuristischer Action-Kandidat erkannt, aber das Ziel sollte vor der Ausfuehrung bestaetigt werden.",
                        en="A heuristic action candidate was inferred, but the target should be confirmed before execution.",
                    )
                    if effective_ask_user
                    else _localized_text(
                        language,
                        de=f"Heuristischer Action-Kandidat erkannt: {heuristic_candidate.candidate_kind}/{heuristic_candidate.candidate_id}.",
                        en=f"Heuristic action candidate inferred: {heuristic_candidate.candidate_kind}/{heuristic_candidate.candidate_id}.",
                    )
                ),
                decision=payload,
                confidence=heuristic_confidence or "medium",
                confidence_label=_confidence_label(heuristic_confidence or "medium", language),
                ask_user=effective_ask_user,
                execution_state=_execution_state(ask_user=effective_ask_user),
                execution_state_label=_execution_state_label(_execution_state(ask_user=effective_ask_user), language),
                planner_source="heuristic",
                planner_source_label=_planner_source_label("heuristic", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
            )
        if heuristic_candidate is not None and heuristic_ask_user:
            payload = _candidate_payload(heuristic_candidate)
            missing_input = _apply_candidate_labels(
                payload,
                heuristic_candidate,
                clean_query,
                language=language,
                target_context=target_context,
            )
            payload["reason"] = (
                _missing_required_reason(missing_input, language)
                if missing_input
                else _routing_target_confirmation_reason(language)
                if routing_requires_confirmation
                else _heuristic_reason_text(heuristic_reason, language) or payload["preview"] or heuristic_candidate.title
            )
            payload["execution_state"] = _execution_state(ask_user=True, missing_input=missing_input)
            payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
            return _result_payload(
                available=False,
                used=False,
                status="warn",
                message=_localized_text(language, de="Action-Dry-run empfiehlt vor der Ausfuehrung eine Rueckfrage.", en="Action dry-run recommends asking the user before execution."),
                decision=payload,
                confidence=heuristic_confidence or "low",
                confidence_label=_confidence_label(heuristic_confidence or "low", language),
                ask_user=True,
                execution_state=_execution_state(ask_user=True, missing_input=missing_input),
                execution_state_label=_execution_state_label(_execution_state(ask_user=True, missing_input=missing_input), language),
                planner_source="heuristic",
                planner_source_label=_planner_source_label("heuristic", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
                missing_input=missing_input,
                missing_input_label=_input_key_label(missing_input, language),
                clarifying_question=_clarifying_question(heuristic_candidate, missing_input, language),
                example_prompt=_suggested_follow_up_prompt(clean_query, heuristic_candidate, connection_ref=connection_ref, missing_input=missing_input, language=language),
            )
        return _result_payload(
            available=False,
            used=False,
            status="warn",
            message=_localized_text(language, de="Action-Dry-run nicht verfuegbar: Es ist kein LLM-Client konfiguriert.", en="Action dry-run unavailable: no LLM client is configured."),
            execution_state="",
            execution_state_label="",
            planner_source="heuristic",
            planner_source_label=_planner_source_label("heuristic", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    system_prompt = (
        "You are ARIA's bounded action planner for admin/debug dry-runs. "
        "A routing target is already resolved. Choose only from the provided action candidates. "
        "Prefer safe built-in templates for generic requests like health checks, file reads, or sending messages. "
        "Prefer an existing custom skill when it clearly matches the request and target. "
        "If the request is ambiguous or the action still needs clarification, set ask_user to true. "
        "Respond only as JSON in this format: "
        '{"candidate_kind":"template|skill","candidate_id":"<id or empty>","intent":"<intent or empty>",'
        '"confidence":"high|medium|low","ask_user":true|false,"reason":"short explanation"}.'
    )
    user_prompt = "\n".join(
        [
            f"User request: {str(query or '').strip()}",
            f"Language: {str(language or '').strip().lower() or '-'}",
            f"Resolved target: {connection_kind}/{connection_ref}",
            f"Routing reason: {str(decision.get('reason', '') or '-').strip()}",
            "",
            "Bounded action candidates:",
            *_candidate_rows_for_prompt(candidates, language),
        ]
    )
    try:
        response = await llm_client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            source="action_plan_debug",
            operation="action_plan_debug",
        )
    except Exception as exc:
        return _result_payload(
            available=True,
            used=True,
            status="error",
            message=_localized_text(language, de=f"LLM-Action-Planer fehlgeschlagen: {exc}", en=f"LLM action planner failed: {exc}"),
            execution_state="",
            execution_state_label="",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
        )

    raw_response = str(getattr(response, "content", "") or "").strip()
    payload = _extract_json_object(raw_response) or {}
    candidate_kind = str(payload.get("candidate_kind", "") or "").strip().lower()
    candidate_id = str(payload.get("candidate_id", "") or "").strip()
    intent = str(payload.get("intent", "") or "").strip()
    confidence = str(payload.get("confidence", "") or "").strip().lower()
    ask_user = bool(payload.get("ask_user", False))
    reason = str(payload.get("reason", "") or "").strip()
    if confidence not in {"high", "medium", "low"}:
        return _result_payload(
            available=True,
            used=True,
            status="warn",
            message=_localized_text(language, de="LLM-Action-Planer lieferte eine ungueltige Confidence.", en="LLM action planner returned invalid confidence."),
            execution_state="",
            execution_state_label="",
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
            raw_response=raw_response[:500],
        )

    candidate = valid_by_key.get((candidate_kind, candidate_id))
    if not candidate:
        candidate, recovery_reason = _recover_llm_candidate_selection(
            candidate_kind=candidate_kind,
            candidate_id=candidate_id,
            intent=intent,
            candidates=candidates,
            heuristic_candidate=heuristic_candidate,
            heuristic_ask_user=heuristic_ask_user,
        )
        if not candidate:
            return _result_payload(
                available=True,
                used=True,
                status="warn",
                message=_localized_text(language, de="LLM-Action-Planer hat einen Kandidaten ausserhalb der begrenzten Menge gewaehlt.", en="LLM action planner chose a candidate outside the bounded set."),
                confidence=confidence,
                confidence_label=_confidence_label(confidence, language),
                ask_user=ask_user,
                execution_state=_execution_state(ask_user=ask_user),
                execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user), language),
                planner_source="llm",
                planner_source_label=_planner_source_label("llm", language),
                candidate_count=len(candidates),
                candidates=serialized_candidates,
                target_context=target_context,
                target_reason=target_reason,
                raw_response=raw_response[:500],
            )
        payload = _candidate_payload(candidate)
        payload["intent"] = intent or candidate.intent
        missing_input = _apply_candidate_labels(
            payload,
            candidate,
            clean_query,
            language=language,
            target_context=target_context,
        )
        if missing_input:
            ask_user = True
            confidence = "low" if confidence == "high" else confidence or "low"
        elif routing_requires_confirmation:
            ask_user = True
        payload["execution_state"] = _execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input)
        payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
        payload["reason"] = (
            _missing_required_reason(missing_input, language)
            if missing_input
            else _routing_target_confirmation_reason(language)
            if routing_requires_confirmation
            else reason
            or _localized_text(
                language,
                de=f"LLM-Auswahl wurde ueber bounded Recovery ({recovery_reason}) aufgeloest.",
                en=f"LLM selection was recovered via bounded recovery ({recovery_reason}).",
            )
        )
        return _result_payload(
            available=True,
            used=True,
            status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
            message=(
                _localized_text(
                    language,
                    de="LLM-Action-Planer wurde zwar normalisiert, aber das Ziel sollte vor der Ausfuehrung bestaetigt werden.",
                    en="The LLM action planner was normalized, but the target should be confirmed before execution.",
                )
                if routing_requires_confirmation
                else _localized_text(
                    language,
                    de=f"LLM-Action-Planer wurde ueber bounded Recovery auf {candidate.candidate_kind}/{candidate.candidate_id} normalisiert.",
                    en=f"LLM action planner was normalized to {candidate.candidate_kind}/{candidate.candidate_id} via bounded recovery.",
                )
            ),
            decision=payload,
            confidence=confidence,
            confidence_label=_confidence_label(confidence, language),
            ask_user=ask_user,
            execution_state=_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input),
            execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input), language),
            planner_source="llm",
            planner_source_label=_planner_source_label("llm", language),
            candidate_count=len(candidates),
            candidates=serialized_candidates,
            target_context=target_context,
            target_reason=target_reason,
            missing_input=missing_input,
            missing_input_label=_input_key_label(missing_input, language),
            clarifying_question=_clarifying_question(candidate, missing_input, language) if ask_user else "",
            example_prompt=_suggested_follow_up_prompt(clean_query, candidate, connection_ref=connection_ref, missing_input=missing_input, language=language) if ask_user else "",
            raw_response=raw_response[:500],
        )

    payload = _candidate_payload(candidate)
    payload["intent"] = intent or candidate.intent
    missing_input = _apply_candidate_labels(
        payload,
        candidate,
        clean_query,
        language=language,
        target_context=target_context,
    )
    if missing_input:
        ask_user = True
        confidence = "low" if confidence == "high" else confidence or "low"
    elif routing_requires_confirmation:
        ask_user = True
    payload["execution_state"] = _execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input)
    payload["execution_state_label"] = _execution_state_label(payload["execution_state"], language)
    payload["reason"] = (
        _missing_required_reason(missing_input, language)
        if missing_input
        else _routing_target_confirmation_reason(language)
        if routing_requires_confirmation
        else reason or payload["preview"] or candidate.title
    )
    message = _localized_text(
        language,
        de=f"LLM-Action-Planer waehlt {candidate.candidate_kind}/{candidate.candidate_id}.",
        en=f"LLM action planner selected {candidate.candidate_kind}/{candidate.candidate_id}.",
    )
    if routing_requires_confirmation:
        message = _localized_text(
            language,
            de="LLM-Action-Planer hat eine passende Aktion gefunden, aber das Ziel sollte vor der Ausfuehrung bestaetigt werden.",
            en="The LLM action planner found a suitable action, but the target should be confirmed before execution.",
        )
    elif ask_user or confidence == "low":
        message = _localized_text(language, de="LLM-Action-Planer empfiehlt vor der Ausfuehrung eine Rueckfrage.", en="LLM action planner recommends asking the user before execution.")
    return _result_payload(
        available=True,
        used=True,
        status="ok" if not ask_user and confidence in {"high", "medium"} else "warn",
        message=message,
        decision=payload,
        confidence=confidence,
        confidence_label=_confidence_label(confidence, language),
        ask_user=ask_user,
        execution_state=_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input),
        execution_state_label=_execution_state_label(_execution_state(ask_user=ask_user or confidence == "low", missing_input=missing_input), language),
        planner_source="llm",
        planner_source_label=_planner_source_label("llm", language),
        candidate_count=len(candidates),
        candidates=serialized_candidates,
        target_context=target_context,
        target_reason=target_reason,
        missing_input=missing_input,
        missing_input_label=_input_key_label(missing_input, language),
        clarifying_question=_clarifying_question(candidate, missing_input, language) if ask_user else "",
        example_prompt=_suggested_follow_up_prompt(clean_query, candidate, connection_ref=connection_ref, missing_input=missing_input, language=language) if ask_user else "",
        raw_response=raw_response[:500],
    )
