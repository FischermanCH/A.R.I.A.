from __future__ import annotations

import hmac
import json
import re
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qsl, quote_plus, urlencode, urlparse, urlunparse

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from aria.core.custom_skills import (
    _collect_skill_categories,
    _custom_skill_file,
    _delete_custom_skill_manifest,
    _load_custom_skill_manifests,
    _normalize_skill_schedule_manifest,
    _normalize_skill_steps_manifest,
    _sanitize_skill_id,
    _save_custom_skill_manifest,
    _validate_custom_skill_manifest,
)


SettingsGetter = Callable[[], Any]
UsernameResolver = Callable[[Request], str]
AuthSessionResolver = Callable[[Request], dict[str, Any] | None]
RoleSanitizer = Callable[[str | None], str]
RawConfigReader = Callable[[], dict[str, Any]]
RawConfigWriter = Callable[[dict[str, Any]], None]
RuntimeReloader = Callable[[], None]
Translate = Callable[[str, str, str], str]
LocalizeSkillDescription = Callable[[dict[str, Any], str], str]
FormatInfoMessage = Callable[[str, str], str]
SuggestKeywords = Callable[..., Awaitable[list[str]]]
DailyTimeToCron = Callable[[str], str]
DailyTimeFromCron = Callable[[str], str]

BASE_DIR = Path(__file__).resolve().parents[2]
SAMPLE_SKILLS_DIR = BASE_DIR / "samples" / "skills"

_SKILL_TYPE_PRESETS: dict[str, dict[str, Any]] = {
    "custom": {
        "label": "Custom",
        "hint": "Freier Skill ohne starke Vorgaben. Du bestimmst Schritte und Details selbst.",
        "category": "custom",
        "description": "",
        "default_step_type": "ssh_run",
        "default_step_name": "",
        "default_params": {},
    },
    "health_check": {
        "label": "Health Check",
        "hint": "Fuehrt einen sicheren Status-Check auf einem Host oder Dienst aus.",
        "category": "monitoring",
        "description": "Prueft einen Host oder Dienst und liefert einen kurzen Status.",
        "default_step_type": "ssh_run",
        "default_step_name": "Health Check",
        "default_params": {
            "command": "uptime",
        },
    },
    "monitor": {
        "label": "Monitor",
        "hint": "Liest eine Quelle aus und bereitet neue Ereignisse oder Aenderungen fuer Folge-Schritte vor.",
        "category": "monitoring",
        "description": "Liest eine Quelle aus und bereitet Aenderungen fuer weitere Schritte vor.",
        "default_step_type": "rss_read",
        "default_step_name": "Quelle lesen",
        "default_params": {},
    },
    "notify": {
        "label": "Notify",
        "hint": "Sendet eine kurze Benachrichtigung an Discord oder in den Chat.",
        "category": "automation",
        "description": "Sendet eine kurze Benachrichtigung an einen Ausgabekanal.",
        "default_step_type": "discord_send",
        "default_step_name": "Benachrichtigung senden",
        "default_params": {
            "message": "Status-Update:\n{prev_output}",
        },
    },
    "fetch": {
        "label": "Fetch",
        "hint": "Liest Daten oder Dateien aus einer Connection und gibt sie an weitere Schritte weiter.",
        "category": "automation",
        "description": "Liest Daten oder Dateien aus einer Connection.",
        "default_step_type": "sftp_read",
        "default_step_name": "Daten lesen",
        "default_params": {
            "remote_path": "/",
        },
    },
    "sync": {
        "label": "Sync",
        "hint": "Schreibt vorbereitete Inhalte kontrolliert zurueck auf ein Zielsystem.",
        "category": "automation",
        "description": "Schreibt vorbereitete Inhalte kontrolliert auf ein Zielsystem.",
        "default_step_type": "sftp_write",
        "default_step_name": "Daten schreiben",
        "default_params": {
            "remote_path": "/",
            "content": "{prev_output}",
        },
    },
}

_SKILL_TYPE_ALLOWED_STEP_TYPES: dict[str, list[str]] = {
    "custom": [
        "ssh_run",
        "sftp_read",
        "sftp_write",
        "smb_read",
        "smb_write",
        "rss_read",
        "llm_transform",
        "discord_send",
        "chat_send",
    ],
    "health_check": ["ssh_run", "llm_transform", "discord_send", "chat_send"],
    "monitor": ["rss_read", "llm_transform", "discord_send", "chat_send"],
    "notify": ["discord_send", "chat_send", "llm_transform"],
    "fetch": ["sftp_read", "smb_read", "llm_transform", "discord_send", "chat_send"],
    "sync": ["sftp_write", "smb_write", "llm_transform", "discord_send", "chat_send"],
}

_SKILL_TYPE_FOLLOWUP_STEPS: dict[str, list[dict[str, Any]]] = {
    "custom": [],
    "health_check": [
        {
            "step_type": "llm_transform",
            "label": "Zusammenfassen",
            "name": "Kurz auswerten",
            "params": {
                "prompt": "Fasse das Ergebnis kurz und klar zusammen:\n{prev_output}",
            },
        },
        {
            "step_type": "discord_send",
            "label": "An Discord senden",
            "name": "Status an Discord",
            "params": {
                "message": "Health Check Ergebnis:\n{prev_output}",
            },
        },
        {
            "step_type": "chat_send",
            "label": "Im Chat antworten",
            "name": "Antwort an Chat",
            "params": {
                "chat_message": "Health Check Ergebnis:\n{prev_output}",
            },
        },
    ],
    "monitor": [
        {
            "step_type": "llm_transform",
            "label": "Aenderungen zusammenfassen",
            "name": "Aenderungen auswerten",
            "params": {
                "prompt": "Pruefe die gelesenen Daten auf neue oder wichtige Aenderungen und fasse sie kurz zusammen:\n{prev_output}",
            },
        },
        {
            "step_type": "discord_send",
            "label": "Als Alert senden",
            "name": "Alert an Discord",
            "params": {
                "message": "Monitor-Update:\n{prev_output}",
            },
        },
    ],
    "notify": [
        {
            "step_type": "llm_transform",
            "label": "Nachricht vorbereiten",
            "name": "Nachricht verdichten",
            "params": {
                "prompt": "Formuliere aus dem vorherigen Ergebnis eine kurze, freundliche Benachrichtigung:\n{prev_output}",
            },
        },
        {
            "step_type": "chat_send",
            "label": "Auch im Chat senden",
            "name": "Antwort an Chat",
            "params": {
                "chat_message": "Benachrichtigung:\n{prev_output}",
            },
        },
    ],
    "fetch": [
        {
            "step_type": "llm_transform",
            "label": "Inhalt zusammenfassen",
            "name": "Inhalt auswerten",
            "params": {
                "prompt": "Fasse den gelesenen Inhalt kurz zusammen und hebe Wichtiges hervor:\n{prev_output}",
            },
        },
        {
            "step_type": "discord_send",
            "label": "Ergebnis an Discord",
            "name": "Ergebnis senden",
            "params": {
                "message": "Fetch-Ergebnis:\n{prev_output}",
            },
        },
    ],
    "sync": [
        {
            "step_type": "chat_send",
            "label": "Sync bestaetigen",
            "name": "Sync bestaetigen",
            "params": {
                "chat_message": "Sync abgeschlossen:\n{prev_output}",
            },
        },
        {
            "step_type": "discord_send",
            "label": "Sync an Discord melden",
            "name": "Sync melden",
            "params": {
                "message": "Sync abgeschlossen:\n{prev_output}",
            },
        },
    ],
}

_SKILL_TYPE_CONNECTION_CHOICES: dict[str, list[dict[str, str]]] = {
    "custom": [],
    "health_check": [
        {
            "kind": "ssh",
            "label": "SSH-Verbindung",
            "field": "connection_ref",
            "step_type": "ssh_run",
            "hint": "Waehle den Host oder Dienst, auf dem der Check laufen soll.",
        }
    ],
    "monitor": [
        {
            "kind": "rss",
            "label": "RSS-Quelle",
            "field": "rss_connection_ref",
            "step_type": "rss_read",
            "hint": "Waehle die Quelle, die der Monitor beobachten soll.",
        }
    ],
    "notify": [
        {
            "kind": "discord",
            "label": "Discord-Ziel",
            "field": "discord_connection_ref",
            "step_type": "discord_send",
            "hint": "Waehle den Kanal oder Webhook fuer Benachrichtigungen.",
        }
    ],
    "fetch": [
        {
            "kind": "sftp",
            "label": "SFTP-Verbindung",
            "field": "sftp_connection_ref",
            "step_type": "sftp_read",
            "hint": "Waehle die Quelle, aus der Dateien oder Daten gelesen werden.",
        },
        {
            "kind": "smb",
            "label": "SMB-Verbindung",
            "field": "smb_connection_ref",
            "step_type": "smb_read",
            "hint": "Alternativ kannst du statt SFTP auch einen SMB-Share lesen.",
        },
    ],
    "sync": [
        {
            "kind": "sftp",
            "label": "SFTP-Ziel",
            "field": "sftp_connection_ref",
            "step_type": "sftp_write",
            "hint": "Waehle das Zielsystem, auf das geschrieben werden soll.",
        },
        {
            "kind": "smb",
            "label": "SMB-Ziel",
            "field": "smb_connection_ref",
            "step_type": "smb_write",
            "hint": "Alternativ kannst du statt SFTP auch auf einen SMB-Share schreiben.",
        },
    ],
}


def _sanitize_return_to(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate or not candidate.startswith("/"):
        return ""
    if candidate.startswith("//"):
        return ""
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return ""
    path = parsed.path or "/"
    return f"{path}?{parsed.query}" if parsed.query else path


def _referer_return_to(request: Request) -> str:
    referer = str(request.headers.get("referer", "") or "").strip()
    if not referer:
        return ""
    parsed = urlparse(referer)
    if parsed.scheme or parsed.netloc:
        current = urlparse(str(request.url))
        if parsed.netloc and parsed.netloc != current.netloc:
            return ""
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    candidate = _sanitize_return_to(query.get("return_to"))
    if candidate:
        return candidate
    path = parsed.path or "/"
    current_path = request.url.path or "/"
    if path == current_path:
        return ""
    return _sanitize_return_to(f"{path}?{parsed.query}" if parsed.query else path)


def _resolve_return_to(request: Request, *, fallback: str) -> str:
    candidate = _sanitize_return_to(request.query_params.get("return_to"))
    current_path = request.url.path or "/"
    if candidate and urlparse(candidate).path != current_path:
        return candidate
    referer_target = _referer_return_to(request)
    if referer_target and urlparse(referer_target).path != current_path:
        return referer_target
    return _sanitize_return_to(fallback) or "/"


def _attach_return_to(url: str, return_to: str) -> str:
    target = _sanitize_return_to(return_to)
    if not target:
        return url
    parsed = urlparse(url)
    pairs = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "return_to"]
    pairs.append(("return_to", target))
    return urlunparse(parsed._replace(query=urlencode(pairs)))


def _redirect_with_return_to(url: str, request: Request, *, fallback: str, return_to: str | None = None) -> RedirectResponse:
    target = _sanitize_return_to(return_to) or _resolve_return_to(request, fallback=fallback)
    return RedirectResponse(url=_attach_return_to(url, target), status_code=303)


def _set_logical_back_url(request: Request, *, fallback: str) -> str:
    target = _resolve_return_to(request, fallback=fallback)
    request.state.logical_back_url = target
    return target


def _sanitize_csrf_token_local(value: str | None) -> str:
    token = str(value or "").strip()
    token = re.sub(r"[^A-Za-z0-9_-]", "", token)
    return token[:256]


def _is_valid_csrf_submission(submitted_token: str | None, expected_token: str | None) -> bool:
    supplied = _sanitize_csrf_token_local(submitted_token)
    expected = _sanitize_csrf_token_local(expected_token)
    if not supplied or not expected:
        return False
    return hmac.compare_digest(supplied, expected)


def _is_admin_mode_request(
    request: Request,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
) -> bool:
    if bool(getattr(request.state, "can_access_advanced_config", False)):
        return True
    auth = get_auth_session_from_request(request) or {}
    role = sanitize_role(auth.get("role"))
    return role == "admin" and bool(getattr(request.state, "debug_mode", False))


def _build_connection_options(rows: dict[str, Any]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for ref in sorted(rows.keys()):
        row = rows.get(ref)
        title = str(getattr(row, "title", "") or "").strip()
        label = f"{title} · {ref}" if title and title != ref else ref
        options.append({"ref": ref, "label": label})
    return options


def _build_skill_rows(lang: str, settings: Any, translate: Translate) -> list[dict[str, Any]]:
    return [
        {
            "key": "memory",
            "title": "Memory",
            "desc": translate(lang, "skills.core_memory_desc", "Speichern und Abrufen von Wissen via Qdrant."),
            "enabled": bool(settings.memory.enabled),
            "implemented": True,
        },
        {
            "key": "auto_memory",
            "title": "Auto-Memory",
            "desc": translate(lang, "skills.core_auto_memory_desc", "Automatische Fakten-Extraktion ohne Codewörter."),
            "enabled": bool(settings.auto_memory.enabled),
            "implemented": True,
        },
    ]


def _build_custom_rows(
    custom_manifests: list[dict[str, Any]],
    custom_cfg: dict[str, Any],
    lang: str,
    localize_custom_skill_description: LocalizeSkillDescription,
    daily_time_from_cron: DailyTimeFromCron,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest in custom_manifests:
        custom_section = custom_cfg.get(manifest["id"], {})
        if not isinstance(custom_section, dict):
            custom_section = {}
        rows.append(
            {
                "key": manifest["id"],
                "title": manifest["name"],
                "desc": localize_custom_skill_description(manifest, lang),
                "enabled": bool(custom_section.get("enabled", manifest.get("enabled_default", True))),
                "implemented": True,
                "category": manifest.get("category", "custom"),
                "prompt_file": manifest.get("prompt_file", ""),
                "router_keywords": manifest.get("router_keywords", []),
                "connections": manifest.get("connections", []),
                "steps": manifest.get("steps", []),
                "schedule": manifest.get("schedule", {}),
                "schedule_time_24h": daily_time_from_cron(str((manifest.get("schedule", {}) or {}).get("cron", ""))),
                "config_path": str((manifest.get("ui", {}) or {}).get("config_path", "")).strip(),
                "hint": str((manifest.get("ui", {}) or {}).get("hint", "")).strip(),
            }
        )
    return rows


def _build_sample_skill_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not SAMPLE_SKILLS_DIR.exists():
        return rows
    for path in sorted(SAMPLE_SKILLS_DIR.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(raw, dict):
            continue
        skill_id = _sanitize_skill_id(str(raw.get("id", "")).strip())
        if not skill_id:
            continue
        rows.append(
            {
                "file_name": path.name,
                "id": skill_id,
                "name": str(raw.get("name", "")).strip() or skill_id,
                "description": str(raw.get("description", "")).strip(),
                "category": str(raw.get("category", "custom")).strip() or "custom",
            }
        )
    return rows


def _sanitize_skill_type(value: str | None) -> str:
    key = str(value or "").strip().lower()
    return key if key in _SKILL_TYPE_PRESETS else "custom"


def _skill_type_options() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": str(meta.get("label", key)).strip() or key,
            "hint": str(meta.get("hint", "")).strip(),
        }
        for key, meta in _SKILL_TYPE_PRESETS.items()
    ]


def _skill_type_allowed_steps() -> dict[str, list[str]]:
    return {key: list(values) for key, values in _SKILL_TYPE_ALLOWED_STEP_TYPES.items()}


def _skill_type_followup_steps() -> dict[str, list[dict[str, Any]]]:
    return {key: [dict(item) for item in values] for key, values in _SKILL_TYPE_FOLLOWUP_STEPS.items()}


def _skill_type_connection_choices() -> dict[str, list[dict[str, str]]]:
    return {key: [dict(item) for item in values] for key, values in _SKILL_TYPE_CONNECTION_CHOICES.items()}


def _connection_options_by_kind(settings: Any) -> dict[str, list[dict[str, str]]]:
    connections = getattr(settings, "connections", None)
    return {
        "ssh": _build_connection_options(getattr(connections, "ssh", {}) or {}),
        "sftp": _build_connection_options(getattr(connections, "sftp", {}) or {}),
        "smb": _build_connection_options(getattr(connections, "smb", {}) or {}),
        "rss": _build_connection_options(getattr(connections, "rss", {}) or {}),
        "discord": _build_connection_options(getattr(connections, "discord", {}) or {}),
    }


def _infer_skill_type(loaded: dict[str, Any] | None) -> str:
    if not isinstance(loaded, dict) or not loaded:
        return "health_check"
    steps = _normalize_skill_steps_manifest((loaded or {}).get("steps", []))
    if len(steps) != 1:
        return "custom"
    step = steps[0] if isinstance(steps[0], dict) else {}
    step_type = str(step.get("type", "")).strip().lower()
    if step_type == "ssh_run":
        return "health_check"
    if step_type == "rss_read":
        return "monitor"
    if step_type in {"discord_send", "chat_send"}:
        return "notify"
    if step_type in {"sftp_read", "smb_read"}:
        return "fetch"
    if step_type in {"sftp_write", "smb_write"}:
        return "sync"
    return "custom"


def _apply_skill_type_defaults(
    *,
    skill_type: str,
    wizard_mode: str,
    skill_category: str,
    skill_description: str,
    steps: list[dict[str, Any]],
) -> tuple[str, str, list[dict[str, Any]]]:
    clean_type = _sanitize_skill_type(skill_type)
    clean_mode = _sanitize_wizard_mode(wizard_mode)
    if clean_mode != "simple" or clean_type == "custom":
        return skill_category, skill_description, steps

    preset = _SKILL_TYPE_PRESETS.get(clean_type, _SKILL_TYPE_PRESETS["custom"])
    effective_category = str(skill_category or "").strip() or "custom"
    if effective_category == "custom":
        effective_category = str(preset.get("category", "custom")).strip() or "custom"
    effective_description = str(skill_description or "").strip() or str(preset.get("description", "")).strip()

    if not steps:
        steps = [
            {
                "id": "s1",
                "name": str(preset.get("default_step_name", "")).strip(),
                "type": str(preset.get("default_step_type", "ssh_run")).strip() or "ssh_run",
                "params": dict(preset.get("default_params", {}) or {}),
                "on_error": "stop",
            }
        ]
        return effective_category, effective_description, steps

    first = dict(steps[0] or {})
    first["type"] = str(preset.get("default_step_type", first.get("type", "ssh_run"))).strip() or "ssh_run"
    if not str(first.get("name", "")).strip():
        first["name"] = str(preset.get("default_step_name", "")).strip()
    params = first.get("params", {})
    if not isinstance(params, dict):
        params = {}
    for key, value in dict(preset.get("default_params", {}) or {}).items():
        if not str(params.get(key, "")).strip():
            params[key] = str(value).strip()
    first["params"] = params
    steps = [first, *steps[1:]]
    return effective_category, effective_description, steps


def _normalize_custom_cfg(raw: dict[str, Any]) -> dict[str, Any]:
    skills_cfg = raw.get("skills", {})
    if not isinstance(skills_cfg, dict):
        skills_cfg = {}
    custom_cfg = skills_cfg.get("custom", {})
    if not isinstance(custom_cfg, dict):
        custom_cfg = {}
    return custom_cfg


def _build_step_forms(loaded: dict[str, Any] | None) -> list[dict[str, Any]]:
    loaded_steps = _normalize_skill_steps_manifest((loaded or {}).get("steps", []))
    if not loaded_steps:
        loaded_steps = [{"id": "s1", "name": "", "type": "ssh_run", "params": {}, "on_error": "stop"}]
    step_forms: list[dict[str, Any]] = []
    for index, step in enumerate(loaded_steps, start=1):
        params = step.get("params", {}) if isinstance(step, dict) else {}
        if not isinstance(params, dict):
            params = {}
        step_forms.append(
            {
                "idx": index,
                "enabled": bool(step),
                "id": str(step.get("id", "") if isinstance(step, dict) else "").strip() or f"s{index}",
                "name": str(step.get("name", "") if isinstance(step, dict) else "").strip(),
                "type": str(step.get("type", "") if isinstance(step, dict) else "").strip() or "ssh_run",
                "on_error": str(step.get("on_error", "stop") if isinstance(step, dict) else "stop").strip().lower()
                or "stop",
                "connection_ref": str(params.get("connection_ref", "")).strip(),
                "command": str(params.get("command", "")).strip(),
                "sftp_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() in {"sftp_read", "sftp_write"}
                else "",
                "sftp_remote_path": str(params.get("remote_path", "")).strip(),
                "sftp_content": str(params.get("content", "")).strip(),
                "smb_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() in {"smb_read", "smb_write"}
                else "",
                "smb_remote_path": str(params.get("remote_path", "")).strip(),
                "smb_content": str(params.get("content", "")).strip(),
                "rss_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() == "rss_read"
                else "",
                "prompt": str(params.get("prompt", "")).strip(),
                "discord_connection_ref": str(params.get("connection_ref", "")).strip()
                if str(step.get("type", "") if isinstance(step, dict) else "").strip() == "discord_send"
                else "",
                "webhook_url": str(params.get("webhook_url", "")).strip(),
                "message": str(params.get("message", "")).strip(),
                "chat_message": str(params.get("chat_message", "")).strip(),
            }
        )
    return step_forms


def _migrate_custom_skill_config(raw: dict[str, Any], old_id: str, new_id: str, enabled: bool) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}

    custom_section = raw["skills"]["custom"]
    clean_old = _sanitize_skill_id(old_id)
    clean_new = _sanitize_skill_id(new_id)

    previous = custom_section.get(clean_old, {}) if clean_old else {}
    current = custom_section.get(clean_new, {}) if clean_new else {}
    merged: dict[str, Any] = {}
    if isinstance(previous, dict):
        merged.update(previous)
    if isinstance(current, dict):
        merged.update(current)
    merged["enabled"] = bool(enabled)

    if clean_new:
        custom_section[clean_new] = merged
    if clean_old and clean_old != clean_new:
        custom_section.pop(clean_old, None)
    return raw


def _remove_custom_skill_config(raw: dict[str, Any], skill_id: str) -> dict[str, Any]:
    raw.setdefault("skills", {})
    if not isinstance(raw["skills"], dict):
        raw["skills"] = {}
    raw["skills"].setdefault("custom", {})
    if not isinstance(raw["skills"]["custom"], dict):
        raw["skills"]["custom"] = {}
    clean_id = _sanitize_skill_id(skill_id)
    if clean_id:
        raw["skills"]["custom"].pop(clean_id, None)
    return raw


def _extract_steps_from_form(form: Any) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    indices: list[int] = []
    seen_idx: set[int] = set()
    for key in form.keys():
        match = re.match(r"^step_(\d+)_", str(key))
        if not match:
            continue
        idx = int(match.group(1))
        if idx not in seen_idx:
            seen_idx.add(idx)
            indices.append(idx)
    indices.sort()

    for idx in indices:
        enabled = str(form.get(f"step_{idx}_enabled", "")).strip().lower() in {"1", "true", "on", "yes"}
        if not enabled:
            continue
        step_type = str(form.get(f"step_{idx}_type", "")).strip().lower()
        if step_type not in {
            "ssh_run",
            "llm_transform",
            "discord_send",
            "chat_send",
            "sftp_read",
            "sftp_write",
            "smb_read",
            "smb_write",
            "rss_read",
        }:
            continue
        step_name = str(form.get(f"step_{idx}_name", "")).strip()
        step_id = _sanitize_skill_id(str(form.get(f"step_{idx}_id", "")).strip()) or f"s{idx}"
        on_error = str(form.get(f"step_{idx}_on_error", "stop")).strip().lower() or "stop"
        if on_error not in {"stop", "continue"}:
            on_error = "stop"
        params: dict[str, str] = {}
        if step_type == "ssh_run":
            params["connection_ref"] = str(form.get(f"step_{idx}_connection_ref", "")).strip()
            params["command"] = str(form.get(f"step_{idx}_command", "")).strip()
        elif step_type in {"sftp_read", "sftp_write"}:
            params["connection_ref"] = str(form.get(f"step_{idx}_sftp_connection_ref", "")).strip()
            params["remote_path"] = str(form.get(f"step_{idx}_sftp_remote_path", "")).strip()
            if step_type == "sftp_write":
                params["content"] = str(form.get(f"step_{idx}_sftp_content", "")).strip()
        elif step_type in {"smb_read", "smb_write"}:
            params["connection_ref"] = str(form.get(f"step_{idx}_smb_connection_ref", "")).strip()
            params["remote_path"] = str(form.get(f"step_{idx}_smb_remote_path", "")).strip()
            if step_type == "smb_write":
                params["content"] = str(form.get(f"step_{idx}_smb_content", "")).strip()
        elif step_type == "rss_read":
            params["connection_ref"] = str(form.get(f"step_{idx}_rss_connection_ref", "")).strip()
        elif step_type == "llm_transform":
            params["prompt"] = str(form.get(f"step_{idx}_prompt", "")).strip()
        elif step_type == "discord_send":
            params["connection_ref"] = str(form.get(f"step_{idx}_discord_connection_ref", "")).strip()
            params["webhook_url"] = str(form.get(f"step_{idx}_webhook_url", "")).strip()
            params["message"] = str(form.get(f"step_{idx}_message", "")).strip()
        elif step_type == "chat_send":
            params["chat_message"] = str(form.get(f"step_{idx}_chat_message", "")).strip()
        steps.append(
            {
                "id": step_id,
                "name": step_name,
                "type": step_type,
                "params": params,
                "on_error": on_error,
            }
        )
    return steps


def _sanitize_wizard_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    return "advanced" if mode == "advanced" else "simple"


def _default_wizard_mode(loaded: dict[str, Any] | None) -> str:
    if not isinstance(loaded, dict) or not loaded:
        return "simple"
    steps = loaded.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    if len(steps) > 1:
        return "advanced"
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("on_error", "stop")).strip().lower() == "continue":
            return "advanced"
        if isinstance(step.get("condition"), dict) and step.get("condition"):
            return "advanced"
    if str((loaded.get("ui", {}) or {}).get("config_path", "")).strip():
        return "advanced"
    return "simple"


_SKILL_SURFACE_PATHS = {
    "/skills",
    "/skills/start",
    "/skills/mine",
    "/skills/system",
    "/skills/templates",
}


def _skill_surface_path(candidate: str | None, *, fallback: str = "/skills") -> str:
    clean = _sanitize_return_to(candidate)
    if clean:
        parsed = urlparse(clean)
        path = parsed.path or ""
        if path in _SKILL_SURFACE_PATHS:
            return path
    return fallback


def register_skills_routes(
    app: FastAPI,
    *,
    templates: Jinja2Templates,
    get_settings: SettingsGetter,
    get_username_from_request: UsernameResolver,
    get_auth_session_from_request: AuthSessionResolver,
    sanitize_role: RoleSanitizer,
    read_raw_config: RawConfigReader,
    write_raw_config: RawConfigWriter,
    reload_runtime: RuntimeReloader,
    translate: Translate,
    localize_custom_skill_description: LocalizeSkillDescription,
    format_skill_routing_info: FormatInfoMessage,
    suggest_skill_keywords_with_llm: SuggestKeywords,
    daily_time_to_cron: DailyTimeToCron,
    daily_time_from_cron: DailyTimeFromCron,
) -> None:
    def _build_skills_overview_checks(
        *,
        lang: str,
        skill_rows: list[dict[str, Any]],
        custom_rows: list[dict[str, Any]],
        sample_skill_rows: list[dict[str, str]],
        advanced_mode: bool,
    ) -> list[dict[str, str]]:
        return [
            {
                "title": translate(lang, "skills.my_skills_title", "Meine Skills"),
                "status": "ok" if custom_rows else "warn",
                "summary": str(len(custom_rows)),
                "meta": translate(lang, "skills.overview_custom_meta", "{count} aktiv").replace(
                    "{count}", str(sum(1 for row in custom_rows if bool(row.get("enabled"))))
                ),
            },
            {
                "title": translate(lang, "skills.system_title", "Core / System"),
                "status": "ok" if skill_rows else "warn",
                "summary": str(len(skill_rows)),
                "meta": translate(lang, "skills.overview_core_meta", "{count} aktiv").replace(
                    "{count}", str(sum(1 for row in skill_rows if bool(row.get("enabled"))))
                ),
            },
            {
                "title": translate(lang, "skills.templates_title", "Vorlagen"),
                "status": "ok" if sample_skill_rows else "warn",
                "summary": str(len(sample_skill_rows)),
                "meta": translate(lang, "skills.overview_templates_meta", "importierbare Samples"),
            },
            {
                "title": translate(lang, "skills.overview_mode_title", "Modus"),
                "status": "ok" if advanced_mode else "warn",
                "summary": (
                    translate(lang, "skills.overview_mode_edit", "Bearbeiten")
                    if advanced_mode
                    else translate(lang, "skills.overview_mode_readonly", "Nur ansehen")
                ),
                "meta": (
                    translate(lang, "skills.overview_mode_meta_admin", "Admin-Modus aktiv")
                    if advanced_mode
                    else translate(lang, "skills.overview_mode_meta_readonly", "Aenderungen sind gerade gesperrt")
                ),
            },
        ]

    def _build_skills_page_context(
        request: Request,
        *,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/skills",
        page_return_to: str = "/skills",
        skills_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> dict[str, Any]:
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        _set_logical_back_url(request, fallback=logical_back_fallback)
        custom_cfg = _normalize_custom_cfg(read_raw_config())
        custom_manifests, custom_errors = _load_custom_skill_manifests()
        advanced_mode = bool(getattr(request.state, "can_access_advanced_config", False))
        skill_rows = _build_skill_rows(lang, settings, translate)
        custom_rows = _build_custom_rows(
            custom_manifests,
            custom_cfg,
            lang,
            localize_custom_skill_description,
            daily_time_from_cron,
        )
        sample_skill_rows = _build_sample_skill_rows()
        overview_checks = _build_skills_overview_checks(
            lang=lang,
            skill_rows=skill_rows,
            custom_rows=custom_rows,
            sample_skill_rows=sample_skill_rows,
            advanced_mode=advanced_mode,
        )
        has_custom_skills = bool(custom_rows)
        next_steps = [
            {
                "icon": "plus",
                "title": translate(
                    lang,
                    "skills.next_step_create_title_empty" if not has_custom_skills else "skills.next_step_create_title_more",
                    "Ersten Skill erstellen" if not has_custom_skills else "Neuen Skill erstellen",
                ),
                "desc": translate(
                    lang,
                    "skills.next_step_create_desc_empty" if not has_custom_skills else "skills.next_step_create_desc_more",
                    (
                        "Der Wizard bleibt der schnellste Einstieg fuer einen ersten gefuehrten Skill."
                        if not has_custom_skills
                        else "Nutze den Wizard fuer einen weiteren gefuehrten Skill, ohne erst JSON von Hand zu pflegen."
                    ),
                ),
                "href": "/skills/start",
                "badge": translate(lang, "skills.next_step_badge_wizard", "Wizard"),
            },
            {
                "icon": "upload",
                "title": translate(
                    lang,
                    "skills.next_step_template_title",
                    "Vorlage uebernehmen" if not has_custom_skills else "Weitere Vorlage pruefen",
                ),
                "desc": translate(
                    lang,
                    "skills.next_step_template_desc",
                    (
                        "Sample-Skills geben dir einen schnellen Startpunkt, wenn du den Ablauf nicht ganz von null bauen willst."
                    ),
                ),
                "href": "/skills/templates",
                "badge": str(len(sample_skill_rows)),
            },
            {
                "icon": "skills",
                "title": translate(
                    lang,
                    "skills.next_step_manage_title_mine" if has_custom_skills else "skills.next_step_manage_title_system",
                    "Eigene Skills pruefen" if has_custom_skills else "Core / System kennenlernen",
                ),
                "desc": translate(
                    lang,
                    "skills.next_step_manage_desc_mine" if has_custom_skills else "skills.next_step_manage_desc_system",
                    (
                        "Hier siehst du nur deine eigenen Faehigkeiten und kannst sie weiterentwickeln oder aufraeumen."
                        if has_custom_skills
                        else "Schau dir zuerst die eingebauten Faehigkeiten an, bevor du eigene Skills daneben aufbaust."
                    ),
                ),
                "href": "/skills/mine" if has_custom_skills else "/skills/system",
                "badge": str(len(custom_rows)) if has_custom_skills else str(len(skill_rows)),
            },
        ]
        return {
            "title": settings.ui.title,
            "username": username,
            "saved": bool(saved),
            "error_message": error,
            "info_message": format_skill_routing_info(lang, info),
            "skill_rows": skill_rows,
            "custom_rows": custom_rows,
            "sample_skill_rows": sample_skill_rows,
            "custom_errors": custom_errors,
            "skills_readonly": not advanced_mode,
            "page_return_to": _skill_surface_path(page_return_to, fallback="/skills"),
            "overview_checks": overview_checks,
            "active_core_count": sum(1 for row in skill_rows if bool(row.get("enabled"))),
            "active_custom_count": sum(1 for row in custom_rows if bool(row.get("enabled"))),
            "custom_count": len(custom_rows),
            "sample_count": len(sample_skill_rows),
            "sample_category_count": len(
                {str(row.get("category", "")).strip().lower() for row in sample_skill_rows if str(row.get("category", "")).strip()}
            ),
            "next_steps": next_steps,
            "skills_nav": skills_nav,
            "skills_page_heading": page_heading,
            "show_overview_checks": bool(show_overview_checks),
        }

    def _render_skills_surface(
        request: Request,
        *,
        template_name: str,
        saved: int = 0,
        error: str = "",
        info: str = "",
        logical_back_fallback: str = "/skills",
        page_return_to: str = "/skills",
        skills_nav: str = "overview",
        page_heading: str,
        show_overview_checks: bool = False,
    ) -> HTMLResponse:
        context = _build_skills_page_context(
            request,
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback=logical_back_fallback,
            page_return_to=page_return_to,
            skills_nav=skills_nav,
            page_heading=page_heading,
            show_overview_checks=show_overview_checks,
        )
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    @app.get("/skills", response_class=HTMLResponse)
    async def skills_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_skills_surface(
            request,
            template_name="skills_overview.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/",
            page_return_to="/skills",
            skills_nav="overview",
            page_heading=translate(lang, "skills.title", "Fähigkeiten"),
            show_overview_checks=True,
        )

    @app.get("/skills/start", response_class=HTMLResponse)
    async def skills_start_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_skills_surface(
            request,
            template_name="skills_start.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/skills",
            page_return_to="/skills/start",
            skills_nav="start",
            page_heading=translate(lang, "skills.start_title", "Skill starten"),
        )

    @app.get("/skills/mine", response_class=HTMLResponse)
    async def skills_mine_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_skills_surface(
            request,
            template_name="skills_mine.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/skills",
            page_return_to="/skills/mine",
            skills_nav="mine",
            page_heading=translate(lang, "skills.my_skills_title", "Meine Skills"),
        )

    @app.get("/skills/system", response_class=HTMLResponse)
    async def skills_system_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_skills_surface(
            request,
            template_name="skills_system.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/skills",
            page_return_to="/skills/system",
            skills_nav="system",
            page_heading=translate(lang, "skills.system_title", "Core / System"),
        )

    @app.get("/skills/templates", response_class=HTMLResponse)
    async def skills_templates_page(request: Request, saved: int = 0, error: str = "", info: str = "") -> HTMLResponse:
        lang = str(getattr(request.state, "lang", "de") or "de")
        return _render_skills_surface(
            request,
            template_name="skills_templates.html",
            saved=saved,
            error=error,
            info=info,
            logical_back_fallback="/skills",
            page_return_to="/skills/templates",
            skills_nav="templates",
            page_heading=translate(lang, "skills.templates_title", "Vorlagen"),
        )

    @app.post("/skills/save")
    async def skills_save(
        request: Request,
        memory_enabled: str = Form("0"),
        auto_memory_enabled: str = Form("0"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _skill_surface_path(return_to, fallback="/skills")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        try:
            form = await request.form()
            raw = read_raw_config()
            raw.setdefault("memory", {})
            if not isinstance(raw["memory"], dict):
                raw["memory"] = {}
            if "memory_enabled" in form:
                raw["memory"]["enabled"] = str(memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("auto_memory", {})
            if not isinstance(raw["auto_memory"], dict):
                raw["auto_memory"] = {}
            if "auto_memory_enabled" in form:
                raw["auto_memory"]["enabled"] = str(auto_memory_enabled).strip().lower() in {"1", "true", "on", "yes"}

            raw.setdefault("skills", {})
            if not isinstance(raw["skills"], dict):
                raw["skills"] = {}
            raw["skills"].setdefault("custom", {})
            if not isinstance(raw["skills"]["custom"], dict):
                raw["skills"]["custom"] = {}

            custom_manifest_rows, _ = _load_custom_skill_manifests()
            known_ids = {row["id"] for row in custom_manifest_rows}
            for skill_id in known_ids:
                key = f"custom_enabled__{skill_id}"
                if key not in form:
                    continue
                raw["skills"]["custom"].setdefault(skill_id, {})
                if not isinstance(raw["skills"]["custom"][skill_id], dict):
                    raw["skills"]["custom"][skill_id] = {}
                raw["skills"]["custom"][skill_id]["enabled"] = str(form.get(key, "")).strip().lower() in {
                    "1",
                    "true",
                    "on",
                    "yes",
                }

            write_raw_config(raw)
            reload_runtime()
            return _redirect_with_return_to(f"{surface_path}?saved=1", request, fallback="/", return_to=return_to)
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.get("/skills/wizard", response_class=HTMLResponse)
    async def skills_wizard_page(
        request: Request,
        skill_id: str = "",
        mode: str = "",
        saved: int = 0,
        error: str = "",
        info: str = "",
    ) -> HTMLResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to("/skills?error=readonly", request, fallback="/skills")
        settings = get_settings()
        username = get_username_from_request(request)
        lang = str(getattr(request.state, "lang", "de") or "de")
        return_to = _set_logical_back_url(request, fallback="/skills")
        loaded: dict[str, Any] | None = None
        clean_id = _sanitize_skill_id(skill_id)
        if clean_id:
            path = _custom_skill_file(clean_id)
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        loaded = _validate_custom_skill_manifest(payload)
                except Exception as exc:  # noqa: BLE001
                    error = error or str(exc)

        all_manifests, _ = _load_custom_skill_manifests()
        category_options = _collect_skill_categories(all_manifests)
        selected_category = str((loaded or {}).get("category", "")).strip().lower()
        if selected_category and selected_category not in category_options:
            category_options.append(selected_category)

        effective_id = _sanitize_skill_id((loaded or {}).get("id", "")) or _sanitize_skill_id((loaded or {}).get("name", ""))
        prompt_preview = f"prompts/skills/{effective_id or '<skill-id>'}.md"
        prompt_file_value = str((loaded or {}).get("prompt_file", "")).strip() or (
            f"prompts/skills/{effective_id}.md" if effective_id else ""
        )
        schema_version_value = str((loaded or {}).get("schema_version", "1.1")).strip() or "1.1"
        connections_value = (loaded or {}).get("connections", [])
        connections_text = ", ".join(connections_value) if isinstance(connections_value, list) else ""
        loaded_schedule = _normalize_skill_schedule_manifest((loaded or {}).get("schedule", {}))
        loaded_schedule["time_24h"] = daily_time_from_cron(str(loaded_schedule.get("cron", "")))
        wizard_mode = _sanitize_wizard_mode(mode) if mode else _default_wizard_mode(loaded)
        selected_skill_type = _infer_skill_type(loaded)

        return templates.TemplateResponse(
            request=request,
            name="skills_wizard.html",
            context={
                "title": settings.ui.title,
                "username": username,
                "saved": bool(saved),
                "error_message": error,
                "info_message": format_skill_routing_info(lang, info),
                "skills_nav": "start",
                "skills_page_heading": translate(
                    lang,
                    "skills.wizard_page_heading",
                    "Bestehenden Skill bearbeiten" if loaded else "Neuen Skill erstellen",
                ),
                "skills_readonly": False,
                "custom_errors": [],
                "show_overview_checks": False,
                "skill": loaded or {},
                "category_options": category_options,
                "ssh_connection_options": _build_connection_options(get_settings().connections.ssh),
                "sftp_connection_options": _build_connection_options(get_settings().connections.sftp),
                "smb_connection_options": _build_connection_options(get_settings().connections.smb),
                "rss_connection_options": _build_connection_options(get_settings().connections.rss),
                "discord_connection_options": _build_connection_options(get_settings().connections.discord),
                "prompt_preview": prompt_preview,
                "prompt_file_value": prompt_file_value,
                "schema_version_value": schema_version_value,
                "connections_text": connections_text,
                "step_forms": _build_step_forms(loaded),
                "schedule": loaded_schedule,
                "return_to": return_to,
                "wizard_mode": wizard_mode,
                "skill_type_options": _skill_type_options(),
                "selected_skill_type": selected_skill_type,
                "skill_type_presets_json": _SKILL_TYPE_PRESETS,
                "skill_type_allowed_steps_json": _skill_type_allowed_steps(),
                "skill_type_followup_steps_json": _skill_type_followup_steps(),
                "skill_type_connection_choices_json": _skill_type_connection_choices(),
                "connection_options_by_kind_json": _connection_options_by_kind(settings),
            },
        )

    @app.post("/skills/wizard/save")
    async def skills_wizard_save(
        request: Request,
        original_skill_id: str = Form(""),
        skill_id: str = Form(""),
        skill_name: str = Form(...),
        skill_version: str = Form("0.1.0"),
        skill_description: str = Form(""),
        skill_category: str = Form("custom"),
        skill_type: str = Form("health_check"),
        skill_router_keywords: str = Form(""),
        skill_connections: str = Form(""),
        skill_prompt_file: str = Form(""),
        skill_schema_version: str = Form("1.1"),
        auto_generate_keywords: str = Form("1"),
        schedule_enabled: str = Form("0"),
        schedule_time: str = Form(""),
        schedule_timezone: str = Form("Europe/Zurich"),
        schedule_run_on_startup: str = Form("0"),
        skill_ui_config_path: str = Form(""),
        skill_ui_hint: str = Form(""),
        enabled_default: str = Form("0"),
        wizard_mode: str = Form("simple"),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to("/skills?error=readonly", request, fallback="/skills", return_to=return_to)
        try:
            form = await request.form()
            keywords = [item.strip() for item in str(skill_router_keywords).split(",") if item.strip()]
            connections = [item.strip().lower() for item in str(skill_connections).split(",") if item.strip()]
            original_clean_id = _sanitize_skill_id(original_skill_id)
            resolved_id = _sanitize_skill_id(skill_id) or _sanitize_skill_id(skill_name)
            if not resolved_id:
                raise ValueError("Skill-ID konnte nicht automatisch erzeugt werden. Bitte Namen anpassen.")
            prompt_file = str(skill_prompt_file).strip() or f"prompts/skills/{resolved_id}.md"
            auto_generate = str(auto_generate_keywords).strip().lower() in {"1", "true", "on", "yes"}
            steps = _extract_steps_from_form(form)
            clean_mode = _sanitize_wizard_mode(wizard_mode)
            skill_category, skill_description, steps = _apply_skill_type_defaults(
                skill_type=skill_type,
                wizard_mode=clean_mode,
                skill_category=skill_category,
                skill_description=skill_description,
                steps=steps,
            )
            if not steps:
                raise ValueError("Bitte mindestens einen aktiven Step konfigurieren.")
            schedule_enabled_bool = str(schedule_enabled).strip().lower() in {"1", "true", "on", "yes"}
            schedule_cron = daily_time_to_cron(schedule_time) if schedule_enabled_bool else ""
            schedule = _normalize_skill_schedule_manifest(
                {
                    "enabled": schedule_enabled_bool,
                    "cron": schedule_cron,
                    "timezone": schedule_timezone,
                    "run_on_startup": str(schedule_run_on_startup).strip().lower() in {"1", "true", "on", "yes"},
                }
            )

            language = str(getattr(request.state, "lang", "de") or "de")
            if auto_generate and not keywords:
                draft_manifest = {
                    "id": resolved_id,
                    "name": skill_name,
                    "version": skill_version,
                    "description": skill_description,
                    "category": skill_category,
                    "prompt_file": prompt_file,
                    "router_keywords": [],
                    "connections": connections,
                    "steps": steps,
                    "schedule": schedule,
                    "schema_version": str(skill_schema_version).strip() or "1.1",
                    "enabled_default": str(enabled_default).strip().lower() in {"1", "true", "on", "yes"},
                    "ui": {
                        "config_path": skill_ui_config_path,
                        "hint": skill_ui_hint,
                    },
                }
                keywords = await suggest_skill_keywords_with_llm(draft_manifest, language=language)

            clean = _save_custom_skill_manifest(
                {
                    "id": resolved_id,
                    "name": skill_name,
                    "version": skill_version,
                    "description": skill_description,
                    "category": skill_category,
                    "prompt_file": prompt_file,
                    "router_keywords": keywords,
                    "connections": connections,
                    "steps": steps,
                    "schedule": schedule,
                    "schema_version": str(skill_schema_version).strip() or "1.1",
                    "enabled_default": str(enabled_default).strip().lower() in {"1", "true", "on", "yes"},
                    "ui": {
                        "config_path": skill_ui_config_path,
                        "hint": skill_ui_hint,
                    },
                },
                previous_id=original_clean_id,
            )
            raw = read_raw_config()
            raw = _migrate_custom_skill_config(
                raw,
                old_id=original_clean_id,
                new_id=clean["id"],
                enabled=bool(clean.get("enabled_default", True)),
            )
            write_raw_config(raw)
            reload_runtime()
            info_suffix = ""
            if auto_generate and keywords:
                info_suffix = f"&info={quote_plus(f'keywords:auto:{len(keywords)}')}"
            return _redirect_with_return_to(
                f"/skills/wizard?skill_id={quote_plus(clean['id'])}&mode={quote_plus(clean_mode)}&saved=1{info_suffix}",
                request,
                fallback="/skills",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            clean_mode = _sanitize_wizard_mode(wizard_mode)
            return _redirect_with_return_to(
                f"/skills/wizard?mode={quote_plus(clean_mode)}&error={quote_plus(str(exc))}",
                request,
                fallback="/skills",
                return_to=return_to,
            )

    @app.post("/skills/import")
    async def skills_import(
        request: Request,
        csrf_token: str = Form(""),
        skill_file: UploadFile = File(...),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _skill_surface_path(return_to, fallback="/skills")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            payload = await skill_file.read()
            raw = json.loads(payload.decode("utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_custom_skill_manifest(raw)
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info=imported:{quote_plus(clean['id'])}",
                request,
                fallback="/",
                return_to=return_to,
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.post("/skills/import-sample")
    async def skills_import_sample(
        request: Request,
        sample_file: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _skill_surface_path(return_to, fallback="/skills")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            clean_name = Path(str(sample_file or "").strip()).name
            if not clean_name or not clean_name.endswith(".json"):
                raise ValueError("Unbekanntes Sample-Skill-Manifest.")
            sample_path = SAMPLE_SKILLS_DIR / clean_name
            if not sample_path.exists() or not sample_path.is_file():
                raise ValueError("Sample-Skill nicht gefunden.")
            raw = json.loads(sample_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("Import erwartet ein JSON-Objekt.")
            clean = _save_custom_skill_manifest(raw)
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info=imported:{quote_plus(clean['id'])}",
                request,
                fallback="/",
                return_to=return_to,
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError, OSError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.post("/skills/delete")
    async def skills_delete(
        request: Request,
        skill_id: str = Form(""),
        csrf_token: str = Form(""),
        return_to: str = Form(""),
    ) -> RedirectResponse:
        surface_path = _skill_surface_path(return_to, fallback="/skills")
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return _redirect_with_return_to(f"{surface_path}?error=readonly", request, fallback="/", return_to=return_to)
        expected_csrf = str(getattr(getattr(request, "state", object()), "csrf_token", "") or "")
        if not _is_valid_csrf_submission(csrf_token, expected_csrf):
            return _redirect_with_return_to(f"{surface_path}?error=csrf_failed", request, fallback="/", return_to=return_to)
        try:
            result = _delete_custom_skill_manifest(skill_id)
            raw = read_raw_config()
            raw = _remove_custom_skill_config(raw, skill_id)
            write_raw_config(raw)
            reload_runtime()
            info_value = quote_plus(f"deleted:{result['id']}")
            return _redirect_with_return_to(
                f"{surface_path}?saved=1&info={info_value}",
                request,
                fallback="/",
                return_to=return_to,
            )
        except (OSError, ValueError) as exc:
            return _redirect_with_return_to(
                f"{surface_path}?error={quote_plus(str(exc))}",
                request,
                fallback="/",
                return_to=return_to,
            )

    @app.get("/skills/export/{skill_id}")
    async def skills_export(request: Request, skill_id: str) -> Response:
        if not _is_admin_mode_request(request, get_auth_session_from_request, sanitize_role):
            return JSONResponse({"error": "readonly"}, status_code=403)
        clean_id = _sanitize_skill_id(skill_id)
        path = _custom_skill_file(clean_id)
        if not path.exists():
            return JSONResponse({"error": "not_found"}, status_code=404)
        content = path.read_text(encoding="utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{clean_id}.json"'},
        )
